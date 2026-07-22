# SPEC-B5 — Tier-3 HITL remediation

**Specification type:** Capability SPEC  
**Status:** Draft / construction  
**Owner:** `genai-enablement` Autonomous SRE harness  
**Governing decisions:** [ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md), the
[Autonomous SRE harness plan](../autonomous-sre-harness-plan.md), and the canonical
[`ACTION_TIER_TABLE`](../../solutions/sre-harness/src/sre_harness/autonomy_tiers/action_table.py)  
**Roadmap gate:** `B5`  
**Depends on:** —  
**Evidence scope:** `local-portable-only`  
**Operational state:** `incomplete`  
**Next gate:** `human-authority-and-live-provider-drills`  
**Authority:** `non-authorizing`; fixture receipts cannot issue provider or human-approval authority

## User journey and boundary

As an on-call human approver, I need to review one immutable remediation proposal and make an explicit,
short-lived approve or reject decision that is joined to the exact action and execution subject, so the
harness can resume only that subject without treating an agent-authored flag, stale approval, changed
runbook, or changed merge-request head as my authority.

SPEC-B5 owns the portable Tier-3 proposal, classification, externally verified human-receipt, AWS
Systems Manager approval-signal, GitLab merge-request approval-observation, finite state, and sanitized
audit contracts. It does not own human identity proofing, MFA, reviewer-group administration, production
runbooks, GitLab protected-branch configuration, durable workflow storage, credentials, merge authority,
or the underlying remediation. B4 remains the only autonomous T4 path; B5 cannot promote a T1/T2 action
or consume a T4 action that still qualifies for autonomous execution.

AWS `aws:approve` pauses an Automation until designated principals approve or reject it. The API signal
surface accepts `Approve` and `Reject` but has no idempotency token. GitLab's summary `approved` boolean is
not sufficient evidence because it may be true when no approval rules apply; the exact protected target,
source SHA, non-overridden approval rules, eligible reviewer, and zero unsatisfied rules must rejoin.

**Inputs:** one closed content-addressed Tier-3 proposal; the exact UTC evaluation time; one externally
verifiable human decision receipt; and explicit provider/audit ports.  
**Outputs:** a sealed `awaiting_human`, `route_t4`, `require_t2`, or `deny` admission and, only for an exact
Tier-3 proposal plus verified receipt, a sealed finite approval case.  
**Out:** caller booleans, raw tokens/comments, agent or proposer self-approval, wildcard subjects,
arbitrary actions, mutable document versions or MR heads, approval-rule discovery as authority,
`StartStep`/`Resume`/`Revoke`, automatic MR approval/merge, direct remediation calls, and live claims from
fixtures or fakes.

## Requirements

[REQ-B5-1] **The proposal is closed, bounded, content-addressed, and reviewable.** The only accepted schema
is `sre-harness.hitl-remediation-proposal/v1`; strict UTF-8 JSON is capped at 1 MiB and rejects duplicate
keys, non-finite numbers, symlinks, non-files, unknown/missing fields, wrong primitives, non-canonical
lists/maps, and a proposal revision that does not match the exact body. The body binds one UUID, canonical
creation/expiry, proposer, trigger and plan revision, current action-tier-table revision, action,
confidence, environment, exact parameters, mechanism-specific subject, evidence references, risk summary,
and rollback reference/revision. It contains no approval, reviewer, signal, merge, credential, or execution
authorization field. — **Fallback:** no human case opens.

[REQ-B5-2] **The canonical classifier is the only tier authority.** Admission rejoins the proposal's
action-tier revision to the runtime table and calls the existing `classify()` with the canonical threshold.
Only an on-plan action whose effective tier is exactly T3 becomes `awaiting_human`: a native T3 action may
qualify at sufficient confidence, and a T4 action may qualify only after deterministic confidence
degradation to T3. Effective T4 routes back to B4, effective T1/T2 requires T2/human execution, and unknown
or revision-mismatched input denies. The receipt cannot change classification. — **Fallback:** no provider
or audit side effect.

[REQ-B5-3] **Each provider subject is exact and immutable.** An `aws_ssm` subject binds account, region,
pending Automation execution UUID, numeric document version, document SHA-256, first approval-step name,
and exact input-parameter revision. A `gitlab_mr` subject binds an HTTPS instance origin, numeric project
and MR ids, exact source commit SHA, target branch, protected-branch/rule revisions, and exact approval-
settings revision. Subject revisions include the proposal's action and exact parameters. Wildcards,
`$LATEST`/`$DEFAULT`, credentials, or provider-selected targets are forbidden. — **Fallback:** proposal
parsing fails.

[REQ-B5-4] **Human authority is an externally verified receipt, never a payload flag.** The only receipt
schema is `sre-harness.hitl-approval-receipt/v1`. It is closed, bounded, content-addressed, and binds one
receipt UUID, evidence scope, origin/verifier, exact proposal and subject revisions, `approved` or
`rejected`, human reviewer, eligibility revision, MFA/reauthentication evidence revision, canonical
decision/expiry, and immutable evidence reference/revision. A gate accepts only an allowlisted origin and
configured verifier, requires exact boolean `True` over an unchanged receipt, and issues an opaque
process-local capability. Fixture receipts never authorize or signal. Agent/service/bot principals and the
proposal's own proposer cannot approve. — **Fallback:** the case remains awaiting human or escalates.

[REQ-B5-5] **Receipt use is fresh, exact, and replay bounded.** The verified receipt must rejoin proposal
id/revision, mechanism, subject revision, reviewer and validity window at the moment of use. The decision
must be no earlier than proposal creation and both proposal and receipt use exclusive expiry. A stable
dedupe key derives from the proposal, receipt, and decision. Mutated, copied, foreign, future, expired,
cross-proposal, cross-subject, or already-conflicting receipts fail before a provider call. — **Fallback:**
no authorization is inferred.

[REQ-B5-6] **The AWS path can signal only an exact first-step approval.** Before a signal, the explicit
client account/region binding and a fresh snapshot must rejoin execution id, document name/version/hash,
schema `0.3`, exact input revision, approval-step name, `approvalFirst=true`, and `PendingApproval`. The
call contains the same account/region/execution, only `Approve` or `Reject`, and a bounded non-secret
receipt reference in `Comment`; no `StartStep`, `Resume`, `Revoke`, raw comment, or parameter is exposed.
The signal port must deduplicate by the stable key because AWS supplies no client token. Matching observed
`Approved`/`Rejected` state is idempotent; conflicting or drifted state escalates. — **Fallback:** no
signal.

[REQ-B5-7] **The GitLab path observes approval but never approves or merges.** A fresh read-only snapshot
must rejoin instance/project/MR, `opened`, exact source SHA and target branch, protected target, required
reset-on-push and reauthentication settings, non-overridden rule set, exact rule/settings revisions,
zero approvals left, every required rule satisfied, and the receipt reviewer among eligible rule-matching
approvers while distinct from author and committers. A rejected receipt terminates without a GitLab call.
No B5 port exposes approve, unapprove, reset, merge, branch push, or pipeline mutation. — **Fallback:**
stale, empty-rule, summary-only, self-approved, or mismatched evidence escalates.

[REQ-B5-8] **The case is finite and fail-closed.** A sealed case moves only from `awaiting_human` to
`approval_signal_sent` / `rejection_signal_sent` for AWS, or directly to `approved` / `rejected` for
GitLab, then to terminal `approved`, `rejected`, `expired`, or `escalated`. Pending provider state preserves
the current state; terminal reconciliation is side-effect-free. Expiry never sends an approval signal.
Reject cannot later become approve, one receipt cannot cross subjects, and no state grants generic or
future authority. — **Fallback:** no fabricated approval or execution success.

[REQ-B5-9] **Every material transition produces an idempotent non-secret audit event.** Awaiting-human,
receipt-bound signal or terminal decision, approved, rejected, expired, and escalated events bind stable
dedupe key, proposal/action/mechanism, receipt revision when present, state, provider subject id, and stable reason.
They omit parameters, risk/rollback text, reviewer identity, MFA evidence, comments, tokens, runbook
content, MR title/body/diff, and exception detail. Audit failure leaves the caller at its prior state so
the same key can retry. — **Fallback:** no unrecorded transition is returned.

[REQ-B5-10] **Portable tests are not live HITL evidence.** B5 exit requires approved identity/MFA and
reviewer-eligibility sources; immutable provider policies and exact runbook/MR settings; separate proposer,
approver, and execution identities; a durable compare-and-swap/outbox ledger; idempotent signal/audit
delivery; retained CloudTrail/GitLab audit evidence; and observed approve, reject, expiry, stale-head,
changed-rule, duplicate, concurrent, permission-denial, notification-loss, and recovery drills. —
**Fallback:** B5 remains incomplete and checked fixtures cannot activate it.

## Portable interfaces

```text
load_hitl_proposal(path) -> HitlRemediationProposal
authorize_hitl_proposal(proposal, audit, now) -> HitlCase
load_hitl_receipt(path) -> HitlApprovalReceipt
HitlApprovalGate.verify(receipt, now) -> VerifiedHitlApprovalReceipt
apply_hitl_receipt(case, receipt, provider, audit, now) -> HitlCase
reconcile_hitl_case(case, provider, audit, now) -> HitlCase
```

The AWS provider exposes only exact account/region binding, read-only approval snapshot, and an idempotent
`send_approval_signal(AutomationApprovalSignalCall)`. The GitLab provider exposes only exact instance
binding and a read-only approval snapshot. The audit port exposes only `record(HitlAuditEvent)` and must
deduplicate by `dedupe_key`.

## Verification / acceptance probes

- **P-B5-1 closed-proposal:** exact v1 proposals load; oversize/symlink, duplicate/non-finite,
  malformed, unknown/missing/wrong-type, non-canonical, secret-like, or digest-mismatched proposals fail.
- **P-B5-2 tier-authority:** native T3 and T4→T3 proposals await human; T4 routes B4, T1/T2 routes T2,
  and unknown/table-revision drift denies with zero provider calls.
- **P-B5-3 exact-subject:** only numeric pinned SSM and protected pinned GitLab unions load; mutable,
  wildcard, credential-bearing, incomplete, or cross-field subjects fail.
- **P-B5-4 receipt-authority:** only allowlisted unchanged exact-boolean external verification issues the
  opaque capability; fixture, agent/bot/service, proposer-self, raw, copied, truthy, or mutated receipts
  cannot authorize.
- **P-B5-5 receipt-rejoin:** exact fresh proposal/subject/reviewer/time bindings pass; future, expired,
  mismatched, conflicting, or replayed-cross-subject receipts make no provider call.
- **P-B5-6 AWS-flow:** exact pending first-step snapshot produces one deduped `Approve` or `Reject` call;
  matching observed terminal state is idempotent, while drift/conflict/escalation emits no other signal.
- **P-B5-7 GitLab-flow:** exact protected opened head with unchanged satisfied rules and eligible independent
  reviewer approves read-only; empty/overridden/stale/self/committer/unsatisfied evidence escalates and no
  GitLab write surface exists.
- **P-B5-8 lifecycle:** pending is stable; approve/reject reconcile terminally; expiry never signals;
  terminal calls are side-effect-free and reject cannot transition to approve.
- **P-B5-9 audit:** each transition has a stable retry key and sanitized payload; audit failure returns no
  advanced state and retry reuses the same provider/audit keys.
- **P-B5-10 evidence-scope:** docs/status retain the fake/portable boundary until live identity, policy,
  durable orchestration, audit, and positive/negative/concurrency drills exist.

## Current evidence and blockers

This SPEC defines a portable construction target. Fake provider/verifier/audit tests can prove strict
parsing, classification, exact call shapes, finite transitions, and retry keys; they cannot prove a human
identity, MFA, reviewer eligibility, protected GitLab policy, runbook step order, AWS signal idempotence,
durable recovery, or any underlying remediation in a real environment.

The closed local
[`SPEC-B5` portable traceability manifest](../../solutions/sre-harness/spec-traceability/SPEC-B5.json)
binds this exact SPEC digest and all ten probe ids to existing pytest nodes plus bounded implementation
paths. The portfolio checker parses the test file with the Python AST and rejects a stale source digest,
missing/extra probe, missing test node, path escape, symlink, malformed shape, or authority/evidence
overclaim. The manifest is a static local traceability index, not a stored test result, human approval,
provider signal, protected-branch observation, live drill, or authority grant; its referenced tests must
still pass in the declared Python 3.11+ environment.

B5 remains incomplete until REQ-B5-10 evidence exists. No checked-in fixture may authorize a provider
signal, approve or merge an MR, or claim that a human reviewed a live action.
