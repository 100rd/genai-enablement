# SPEC-B6 — Permanent-fix chase

**Specification type:** Capability SPEC
**Status:** Draft / portable construction
**Owner:** `genai-enablement` Autonomous SRE harness
**Governing decisions:** [ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md) and the
[Autonomous SRE harness plan](../autonomous-sre-harness-plan.md)
**Roadmap gate:** `B6`
**Depends on:** SPEC-B1 RCA evidence, SPEC-B5 mitigation/HITL joins, ADR-0003 unified SDLC,
factory-owned canonical OutcomeEvent
**Evidence scope:** `local-portable-only`
**Operational state:** `incomplete`
**Next gate:** `human-policy-and-live-provider-drills`
**Authority:** `non-authorizing`; at most one bounded issue write, while change, verification, approval,
merge, close, and incident-lifecycle authority remain external

## Goal and boundary

After mitigation, create exactly one durable work item for the real code/IaC fix and chase the
incident-spawned factory task through a reviewable MR/PR to `LANDED`. The portable harness owns the
strict intake artifact, an externally authorized issue-create capability, deterministic provider/factory
rejoins, a finite chase state, and sanitized audit. It does not author code, push a branch, open or edit a
change request, run CI, approve, merge, close an issue, close an incident, or treat model/provider prose as
completion evidence.

The checked examples and fakes are construction evidence only. They do not authorize a real provider.

## User journey

**As the on-call owner**, after service mitigation I want one incident-linked permanent-fix task to enter
the normal factory and remain visible until the exact reviewed revision has landed, so the incident cannot
be declared resolved from a ticket, draft, green-looking provider flag, or agent summary alone.

## Inputs and outputs

**Inputs:** one closed, content-addressed permanent-fix request; one closed, content-addressed and
externally verified tracker-policy publication; exact UTC time; a provider port bound to one origin and
repository; an externally verified canonical factory outcome when available; an audit sink.
**Outputs:** one sealed finite chase case plus sanitized idempotent audit events.
**External side effect:** at most one idempotent `create issue` call. Every other provider/factory call is
read-only.

## Requirements

[REQ-B6-1] **The request is closed, bounded, content-addressed, and sanitized.** The only accepted schema
is `sre-harness.permanent-fix-request/v1`; strict UTF-8 JSON is capped at 1 MiB and rejects duplicate keys,
non-finite values, symlinks, unknown fields, blank/oversized text, malformed UUID/timestamp/revision/ref,
non-canonical JSON, and revision mismatch. The request binds one `incidentId` to one `taskId`, factory,
provider/origin/repository, P0 priority, task class, exact immutable evidence refs, title/body, labels,
target branch, creation/expiry times, and evidence scope. It contains no credential, raw log, prompt,
diff, approval, merge, close, or verification boolean. — **Fallback:** reject before any provider call.

[REQ-B6-2] **Issue creation requires an exact external policy capability.** A closed
`sre-harness.permanent-fix-policy-publication/v1` binds provider/origin/repository, permitted factories,
task classes, labels, target branch, max request age, publication lifetime, human approval revision, and
verifier. An allowlisted unchanged verifier must return exact boolean `True`; fixture policy is never
usable. Request, policy, current time, and provider binding rejoin exactly. — **Fallback:** reject without
searching or writing the provider.

[REQ-B6-3] **Exactly one issue is opened through a durable dedupe boundary.** The dedupe key is derived
from provider/origin/repository plus exact `incidentId`, `taskId`, and request revision. The provider first
searches by that opaque marker across open and closed issues and must implement `create_issue` as
idempotent for the same key because neither GitHub nor GitLab exposes a portable create idempotency token.
An existing exact issue is adopted; a foreign kind, repository, marker, incident, task, or request is
rejected. GitHub issue results that are pull requests are never accepted as issues. — **Fallback:** no
second create; ambiguous/conflicting search escalates to a human.

[REQ-B6-4] **The issue call is bounded and cannot smuggle authority.** The call contains only exact
repository, sanitized title/body, policy-required labels plus request labels, and opaque dedupe key/marker.
No assignee, milestone, confidential toggle, state, state reason, close instruction, token, callback,
approval, merge, auto-merge, pipeline, or branch mutation field exists. — **Fallback:** reject the request
or adapter result.

[REQ-B6-5] **The permanent change is factory-owned and read-only to the harness.** A provider may expose
zero or one factory-created MR/PR snapshot joined by exact repository, `incidentId`, `taskId`, target
branch, numeric change id, and immutable 40-hex head revision. Multiple or foreign matches fail closed.
The harness has no create/update/approve/merge/close/push/pipeline method. — **Fallback:** remain
`issue_open` or escalate ambiguity; never manufacture a change.

[REQ-B6-6] **Verification and gating come only from a canonical externally verified factory outcome.** A
closed outcome binds exact task/factory/head/change ref, lifecycle, verdict, gate, evidence manifest,
emission time, origin, and verifier. The configured verifier must return exact `True` over an unchanged,
fresh outcome. Provider CI/approval/mergeability summaries and model conclusions are non-authoritative.
`VERIFIED` requires `verdict=pass`; `GATED` additionally requires `gate=human`; failure, rejection,
inconclusive, foreign, stale, future, or regressed lifecycle escalates. — **Fallback:** wait or escalate;
never claim verified/gated.

[REQ-B6-7] **`LANDED` requires two-source agreement on the exact revision.** The factory outcome must be
`LANDED`, `verdict=pass`, `gate=human`, and bind the same change/head; the provider snapshot must report
that exact head merged with an immutable 40-hex merge revision. Provider merge alone, outcome alone, a
closed issue, or a newer/stale head is insufficient. — **Fallback:** remain awaiting human merge or
escalate mismatch; the harness never closes the issue or incident.

[REQ-B6-8] **The case is sealed, monotonic, finite, and timeout bounded.** Allowed states are
`issue_open`, `change_open`, `verifying`, `awaiting_human_merge`, `landed`, and `escalated`. Lifecycle
progress never regresses. Request expiry before issue creation blocks the write; after creation it becomes
the chase deadline and escalates. An issue closed before exact `LANDED`, missing/closed unmerged change,
revision drift, provider ambiguity/error, rejected/failed factory outcome, or timeout escalates. Terminal
states are stable. — **Fallback:** human chase; no automatic reopen, retry mutation, merge, or close.

[REQ-B6-9] **Every material transition produces an idempotent non-secret audit event.** Event payloads
contain only stable ids/revisions, provider/repository, numeric issue/change ids, state/reason, timestamp,
and a retry key. They exclude title/body, evidence contents, raw outcome, URLs with credentials, user
identity, comments, diff, logs, tokens, and stack traces. Audit append is required before returning a new
state; retry dedupe is an adapter responsibility. — **Fallback:** fail without returning the transition.

[REQ-B6-10] **Portable tests are not live permanent-fix evidence.** B6 exit requires a human-owned and
immutably published provider/repository/label/branch policy; separate least-privilege issue-write and
read-only chase principals; durable CAS/outbox and dedupe ledger; retained create/retry/concurrency,
ambiguous-search, issue/PR-confusion, stale-head, failed verification, human-gate, merge-race, timeout,
permission-denial, audit-failure, and recovery drills; plus observed `incidentId`→`taskId`→exact landed
revision lineage. — **Fallback:** report construction only and keep fixtures incapable of activation.

## Portable interfaces

```text
load_permanent_fix_request(path) -> PermanentFixRequest
load_permanent_fix_policy(path) -> PermanentFixPolicyPublication
PermanentFixPolicyGate.verify(policy, now) -> VerifiedPermanentFixPolicy
open_permanent_fix(request, policy, provider, audit, now) -> PermanentFixCase
FactoryOutcomeGate.verify(outcome, now) -> VerifiedFactoryOutcome
reconcile_permanent_fix(case, provider, outcome?, audit, now) -> PermanentFixCase
```

The provider protocol exposes only `binding`, `find_issue`, `create_issue`, `read_issue`, and
`find_change`. The factory outcome verifier protocol exposes only verification. No portable interface
contains merge, close, approve, comment, push, branch, pipeline-trigger, or incident-resolution authority.

## Verification matrix

- **P-B6-1 closed request:** valid canonical v1 loads; symlink/oversize, duplicate/non-finite,
  unknown/missing, secret-shaped/authority fields, bad refs/times/revisions, and noncanonical JSON fail.
- **P-B6-2 external policy:** exact allowlisted unchanged boolean verification issues an opaque
  capability; fixture/future/expired/untrusted/truthy-nonboolean/mutating verification fails.
- **P-B6-3 dedupe:** existing exact issue is adopted; absent issue creates once; retries/races use one
  dedupe key; PR-as-issue and foreign/ambiguous matches fail closed.
- **P-B6-4 call shape:** exact bounded fields and labels only; neither call nor protocol exposes
  authority-bearing operations.
- **P-B6-5 change tracking:** zero change waits; exact factory-created change advances; multiple, closed
  unmerged, cross-repo/task/incident/target/head drift escalates.
- **P-B6-6 factory outcome:** only exact externally verified monotonic pass/human lifecycle advances;
  provider status and unverified/mutated/foreign/future/stale/failed/regressed outcomes do not.
- **P-B6-7 landed join:** outcome plus provider merged exact head lands; either source alone or merge/head
  mismatch never lands.
- **P-B6-8 lifecycle:** exhaustive transition table, expiry, terminal stability, and no post-open writes.
- **P-B6-9 audit:** stable retry keys, sanitized payload, idempotent retry, and audit failure semantics.
- **P-B6-10 evidence scope:** checked fixtures remain fixture-only; docs/status retain the portable/live
  boundary.

## Exit evidence

The closed local
[`SPEC-B6` portable traceability manifest](../../solutions/sre-harness/spec-traceability/SPEC-B6.json)
binds this exact SPEC digest and all ten probe ids to existing pytest nodes plus the bounded
`sre_harness.permanent_fix` implementation path. The portfolio checker parses the test file with the
Python AST and rejects source, probe, node, path, scope, operational-state, or authority drift. This is a
static `local-portable-only` index: it stores no PASS result and grants no tracker, factory, merge, close,
incident-lifecycle, credential, or production authority.

B6 remains incomplete until REQ-B6-10 evidence exists. Passing local tests proves only the portable
contract and negative authority surface; it does not prove provider identity, durable exactly-once
behavior, a working factory bridge, human review, merge protection, incident closure, or production use.
