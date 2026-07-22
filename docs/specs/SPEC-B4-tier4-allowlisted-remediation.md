# SPEC-B4 — Tier-4 allowlisted remediation

**Specification type:** Capability SPEC  
**Status:** Draft / construction  
**Owner:** `genai-enablement` Autonomous SRE harness  
**Governing decisions:** [ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md) and the
[Autonomous SRE harness plan](../autonomous-sre-harness-plan.md)  
**Roadmap gate:** `B4`  
**Depends on:** —  
**Evidence scope:** `local-portable-only`  
**Operational state:** `incomplete`  
**Next gate:** `human-allowlist-and-live-provider-drills`  
**Authority:** `non-authorizing`; fixture policy cannot issue live Tier-4 execution authority

## User journey and boundary

As an on-call platform owner, I need a pre-approved, low-blast-radius remediation to execute through an
exact immutable AWS Systems Manager Automation runbook, notify me, and compensate automatically if the
forward action fails, while every off-plan, low-confidence, stale, or approval-bearing path degrades to
Tier 3 instead of acquiring autonomous authority.

SPEC-B4 owns the portable authorization and orchestration contract for the three actions already mapped
to Tier 4 by the canonical action-tier table: restart a stuck stateless pod, re-trigger a stuck Argo CD
sync, and scale a stateless service within exact bounds. It does not own production runbook content, AWS
credentials, IAM policy, the notification topic, a durable workflow engine, target discovery, incident
reasoning, human approval, or deployment. B5 owns the explicit HITL approval receipt and resume path.

AWS Systems Manager Automation runbooks use schema `0.3`. The runtime contract uses only numeric
`DocumentVersion` values, verifies the exact active Automation document owner and SHA-256 before each
start, supplies a UUID `ClientToken`, and fixes `MaxConcurrency=1` plus `MaxErrors=0`. These are portable
construction constraints, not evidence that any AWS account contains the documents.

**Inputs:** one externally verifiable, time-bounded allowlist publication; one exact content-addressed
remediation request; an exact UTC decision time; and explicit SSM/notification ports.  
**Outputs:** a sealed `execute_t4` or `require_t3` decision and, only for `execute_t4`, a sealed finite
execution state with idempotent start/compensation/notification calls.  
**Out:** credentials or SDK-global discovery, `$LATEST`/`$DEFAULT`, caller-authored approval flags,
arbitrary parameter forwarding, public/AWS-owned runbooks, dynamic document/target selection, T3 approval,
recursive remediation, Git/config changes, database/IAM/security-group/data-delete actions, and claims of
live execution from fakes.

## Requirements

[REQ-B4-1] **The policy publication is closed, bounded, content-addressed, and externally authorized.**
The only accepted schema is `sre-harness.remediation-policy-publication/v1`; strict UTF-8 JSON is capped
at 1 MiB and rejects duplicate keys, non-finite numbers, symlinks, non-files, unknown/missing fields,
wrong primitives, non-canonical lists, and a publication revision that does not match the exact nested
policy. A gate accepts only an allowlisted origin and preconfigured verifier, requires exact boolean
`True` over an unchanged publication, and issues an opaque process-local capability. — **Fallback:** no
T4 decision.

[REQ-B4-2] **Human-owned authority is explicit, finite, and non-self-authorizing.** The policy binds a
policy id, evidence scope, origin/verifier, human owner and approval revision, canonical UTC publication
and expiry, AWS account/region, execution role ARN, notification topic ARN, confidence threshold,
request-age ceiling, and sorted unique runbook entries. `fixture` publications can exercise parsing but
always require T3; only an externally verified `external_candidate` can enter the T4 mechanism. A caller
cannot supply `approved`, `trusted`, `tier`, or credentials. — **Fallback:** expired, future, raw,
fabricated, mutated, foreign, truthy-verified, or fixture authority fails closed.

[REQ-B4-3] **The allowlist is exact and immutable.** Every entry names one canonical T4 action and exact
environment, forward and compensation document name, positive numeric version, SHA-256, exact parameter
names, sorted allowed values, and one compensation execution-id parameter. Documents are distinct,
account-owned, and version-pinned; `$LATEST`, `$DEFAULT`, unknown/T1/T2/T3 actions, arbitrary regexes,
wildcards, and credential-like parameters are forbidden. `AutomationAssumeRole` is required and has the
single policy-owned role ARN. Every target selector has exactly one allowed value so an entry author
cannot accidentally authorize a Cartesian product of clusters, namespaces, applications, or workloads;
only the bounded `DesiredReplicas` value may enumerate more than one canonical integer. — **Fallback:**
the policy does not load.

[REQ-B4-4] **The request is closed, exact, fresh, and bound to one policy revision.** The only accepted
schema is `sre-harness.remediation-request/v1`; its exact request body is SHA-256 addressed and contains
one UUID request id, canonical UTC request time, trigger id, plan revision, policy id/revision, action,
environment, canonical confidence string, and sorted parameter map. It has no approval or execution
field. — **Fallback:** malformed requests fail before classification; future/stale or binding-mismatched
requests return `require_t3`.

[REQ-B4-5] **The existing action-tier table remains the classification authority.** Authorization calls
the registered `classify()` function with the policy threshold. Only an exact entry whose effective tier
is T4, scope is `external_candidate`, environment and all parameter names/values match, and request/policy
times are valid can produce `execute_t4`. Low confidence degrades T4→T3; unknown/off-plan or any mismatch
also routes to T3. The model cannot override the disposition. — **Fallback:** B5/HITL owns any later
execution.

[REQ-B4-6] **The SSM start is exact, least-concurrent, and retry-idempotent.** Before starting, the client
must declare an exact account/region binding that rejoins the decision, then describe the numeric version
and rejoin name/version, owner account, `Automation`, `Active`, schema `0.3`, and SHA-256 to the allowlist.
The start call also carries that account/region binding. The exact allowed parameter map is sent with
`MaxConcurrency="1"`, `MaxErrors="0"`, bounded audit tags, and a deterministic UUID client token derived
from the request/policy/phase. The returned execution id must be a UUID. No SDK credential, region, role,
or document discovery occurs inside the core. — **Fallback:** no start on any mismatch.

[REQ-B4-7] **Execution is a finite, fail-closed state machine.** A sealed run progresses only through
`forward_running → succeeded`, `forward_running → rollback_running → rolled_back`, or a terminal
`rollback_failed` / `escalated`. Pending/running SSM states preserve the current state. Forward terminal
failure starts exactly one pinned compensation runbook with the original exact parameters plus the
forward execution id. Compensation never recursively compensates. Raw/mutated states and mismatched SSM
execution identity/document/version fail before another action. — **Fallback:** no fabricated success.

[REQ-B4-8] **Approval and calendar-override states never remain Tier 4.** `PendingApproval`, `Approved`,
`Rejected`, and change-calendar override states contradict an autonomous runbook and terminally escalate
to T3 without sending an approve/reject/resume signal. B4 exposes no `SendAutomationSignal` surface.
— **Fallback:** a human-owned B5 flow may inspect and decide separately.

[REQ-B4-9] **Every material transition emits an idempotent, non-secret notification.** Forward started,
forward succeeded, rollback started, rolled back, rollback failed, and escalated transitions emit a
bounded event to the exact policy topic. The event carries a deterministic dedupe key, request/action,
policy revision, execution id, state, and stable reason, but never request parameters, role credentials,
tokens, document content, or exception detail. The notification port must deduplicate retries by key.
— **Fallback:** notification failure leaves the caller with the prior state so the same key can retry.

[REQ-B4-10] **Portable mechanism tests are not live T4 evidence.** B4 exit requires human-approved and
immutable production allowlist/runbook publications; independently verified owner/version/hash/schema and
rollback semantics; least-privilege IAM/PassRole and target boundaries; a durable compare-and-swap
workflow/ledger; idempotent notification delivery; CloudTrail/audit retention; positive, retry,
off-plan, forced-failure, rollback-failure, notification-failure, expired-policy, and permission-denial
drills in the selected account/region; and measured blast radius, rollback latency, and false positives.
— **Fallback:** B4 remains incomplete and no fixture may activate it.

## Portable interfaces

```text
load_remediation_policy(path) -> RemediationPolicyPublication
RemediationPolicyGate.verify(publication, now) -> VerifiedRemediationPolicy
load_remediation_request(path) -> RemediationRequest
authorize_remediation(request, verified_policy, now) -> RemediationDecision
start_t4_remediation(decision, client, notifier, now) -> RemediationRun
reconcile_t4_remediation(run, client, notifier) -> RemediationRun
```

The SSM port exposes only `binding() -> AutomationClientBinding`,
`describe_document(name, numeric_version)`,
`start_automation(StartAutomationCall)`, and `get_automation_execution(execution_id)`. The notification
port exposes only `notify(RemediationNotification)` and must be idempotent by `dedupe_key`.

## Verification / acceptance probes

- **P-B4-1 closed-policy:** exact v1 publication loads; oversize/symlink, duplicate/non-finite,
  malformed, unknown/missing/wrong-type, unsorted, and digest-mismatched policy fails.
- **P-B4-2 authority:** only allowlisted unchanged exact-boolean external verification issues the opaque
  capability; fixture, future, expired, raw, copied, foreign, truthy, and mutated authority cannot T4.
- **P-B4-3 allowlist:** only canonical T4 actions with numeric exact document bindings, required role,
  one exact target tuple, bounded replica alternatives, distinct compensation, and no
  wildcard/credential material load.
- **P-B4-4 closed-request:** exact content-addressed request loads; malformed, duplicate, non-finite,
  unknown/missing, non-canonical time/confidence/parameters, or fabricated revisions fail.
- **P-B4-5 classification:** exact high-confidence match executes T4; fixture, low confidence, off-plan,
  stale/future, policy/environment/parameter mismatch, or non-T4 action requires T3 with zero client calls.
- **P-B4-6 exact-start:** client and call account/region plus document owner/type/status/schema/version/hash
  are all rejoined; the exact numeric call uses concurrency one, zero errors, UUID token, bounded tags,
  and UUID result.
- **P-B4-7 lifecycle:** pending/running is stable; success terminates; forward failures start the one
  compensation; compensation success rolls back; compensation failure terminates without recursion.
- **P-B4-8 escalation:** approval/calendar states and identity/document/version drift escalate or error
  without any approval signal or second autonomous action.
- **P-B4-9 notifications:** each transition has a stable dedupe key and no parameters/secrets; retries
  reuse start tokens/notification keys and terminal reconciliation is side-effect-free.
- **P-B4-10 evidence-scope:** docs/status retain the fake/portable boundary until immutable live policy,
  IAM, durable orchestration, audit, and positive/negative drills exist.

## Current evidence and blockers

The strict policy/request readers, exact-boolean external capability gate, canonical tier classifier,
account/region/document-bound SSM port, sealed finite compensation state, and idempotent notification
contract exist in the dirty local worktree. Green fake-client tests prove only exact portable authorization,
calls, compensation transitions, and notification contracts; they cannot prove a runbook's actual behavior,
IAM containment, SSM idempotency, notification delivery, durable recovery, or rollback in an AWS account.

The closed local
[`SPEC-B4` portable traceability manifest](../../solutions/sre-harness/spec-traceability/SPEC-B4.json)
binds this exact SPEC digest and all ten probe ids to existing pytest nodes plus bounded implementation
paths. The portfolio checker parses the test file with the Python AST and rejects a stale source digest,
missing/extra probe, missing test node, path escape, symlink, malformed shape, or authority/evidence
overclaim. The manifest is a static local traceability index, not a stored test result, immutable production
allowlist, CloudTrail/audit receipt, live drill, or authority grant; its referenced tests must still pass in
the declared Python 3.11+ environment.

B4 remains incomplete until REQ-B4-10 evidence exists. No checked-in fixture may authorize a live
execution, and no local test may clear that gate.
