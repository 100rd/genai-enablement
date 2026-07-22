# ADR-0006: Unified loop decision model — how a task-loop decides, for multiqlti and omnius

- **Status:** Proposed
- **Date:** 2026-07-03
- **Last reviewed:** 2026-07-16
- **Deciders:** platform owner
- **Scope:** cross-repository compatibility proposal for `multiqlti` and `omnius`; informative for the
  Autonomous SRE harness
- **Builds on:** proposed [ADR-0003](0003-unified-sdlc-standard.md) and accepted
  [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0010](0010-goal-oriented-organizational-dark-factory.md), and
  [ADR-0012](0012-capability-readiness-profiles.md)
- **Vocabulary:** [platform-glossary.md](../platform-glossary.md); skills remain governed by proposed
  [ADR-0002](0002-platform-skills-registry.md)

## Context

The platform has factory loops with different internal engines: `multiqlti` uses task orchestration and a
Consilium/SDLC loop, while `omnius` is constructing a durable Conductor FSM. Shared organizational work
needs compatible branch semantics without requiring one engine, one stage vocabulary, one model, or one
implementation language.

The original 2026-07-03 reconnaissance is no longer current evidence. As of 2026-07-16:

- the local `multiqlti` checkout at `44a6a33...` is dirty, although the dirty files are outside its loop
  core. Commit `42af803` retired the legacy `PipelineController` and `guardrail-runner` files this ADR
  previously treated as the autonomous base path. The current Consilium loop has a deterministic reducer,
  structured convergence, optional per-criterion checks, a refute-by-default model-verifier parser, and a
  Draft-PR human gate. Its `class` field is explicitly metadata-only, `autonomyTier` remains unset, no
  admission logic reads either field, and no indexed `WorkOrder`, canonical `OutcomeEvent`, or
  `ReturnEvent` contract exists. Optional planner/verification switches and a human-visible flagged result
  are useful construction seams, not a complete decision authority;
- the local `omnius` checkout at `a32fecd...` is extensively dirty. It contains strong candidate contracts
  for frozen execution bundles, deterministic FSM replay, breakers, readiness, action and delivery gates,
  transactions, outcomes, and return-source health. Those mechanisms sit beside legacy seams, including a
  broad `phase_3` autonomy table and a minimal `phase_2.OutcomeEvent`; their governing component SPECs are
  draft and their exact revisions are not published or activated. Static conformance probes and local tests
  demonstrate mechanisms, not adoption of this ADR or production authority.

The current evidence therefore supports a compatibility decision and an adoption map, not a claim that
either component is already conformant. In particular, a deterministic transition is not enough when its
input can be supplied by the producer, an action-tier lookup is not provider authorization, a human gate
does not repair missing technical evidence, and a return inside a time window does not by itself prove an
escape.

## Acceptance boundary and precedence

This ADR is non-binding while `Proposed`. Proposed ADR-0003, ADR-0006, ADR-0014, ADR-0015, and ADR-0016
cannot accept one another by reference. Accepted ADR-0009, ADR-0010, and ADR-0012 remain authoritative:
humans own ADRs and profiles, mutation requires a governed WorkOrder/SPEC, Done is end-to-end and
probe-defined, and readiness is an exact human-owned requirement/probe/revision decision.

The platform owner may accept a mutually compatible ADR-0003/0006 revision set or supersede either
proposal. Acceptance would authorize component-owned SPEC and conformance work. It would not publish a
shared schema or action catalog, accept component drafts, activate a profile or Realm, admit an action,
grant a provider credential, approve a merge/deploy, widen autonomy, create a cloud resource, or make
dirty/local evidence immutable. Those transitions keep their own owners and exact evidence gates.

This proposal edit changes no ADR status, component code/SPEC/schema, WorkOrder or workflow state,
readiness decision, credential, provider/cloud/Kubernetes resource, repository revision, external policy,
or deployed system.

## Decision

The proposed standard is seven rules for load-bearing branch decisions. A branch decision consumes a
frozen decision context containing the exact WorkOrder/task/SPEC/requirement revisions, readiness profile
and Realm, action/effect/target, class and requested tier, producer/verifier/executor identities, policy and
evidence authorities, budget/clock, state epoch, and compensation posture. A missing, stale, ambiguous,
caller-substituted, or mismatched field produces no positive authority.

Every positive decision is a closed, versioned, integrity-protected record or opaque capability binding
the complete input projection, policy/verifier/profile revisions, decision and expiry times, outcome,
reason codes, and issuing authority. Free text, a raw boolean, a model self-report, a task label, a local
enum, or an action-table row is never that decision. Components may implement the record differently but
must prove equivalent semantics and replay behavior.

### D1 — Action admission separates risk classification from authorization

Before every state-changing effect, a closed versioned catalog deterministically maps the exact action
kind and target class to minimum obligations. Unknown, broad, conflicting, or unregistered actions select
the most restrictive posture and reach no provider. Task class and autonomy tier are risk/admission
inputs, not permissions.

The effect executes only after a separate, atomic admission step joins the exact ready requirement/profile,
effective Realm and deny policy, immutable action/target/plan, executor identity and credential scope,
required human receipt or bounded-autonomy capability, idempotency claim, compensation/forbidden posture,
budget, and audit sink. The resulting step-scoped capability cannot authorize another effect or survive a
relevant revision change. Admission establishes an exclusive effect/state fence, and an enforced mutation
boundary atomically redeems the single-use capability against the complete unchanged projection before the
provider call. A caller-side check followed by an independently credentialed mutation is insufficient.
Classification without this join performs no mutation.

Production and non-compensatable effects remain default-deny for autonomous execution. This proposal does
not create an exception merely because an action is labeled reversible, low-tier, or human-reviewed. An
R0 task that acquires a persistent workspace, provider, network, repository, or deployment effect must
park and reclassify before the first effect.

### D2 — Control-flow selection is deterministic, replayable, and out of the model

The next state/step is a pure, replayable function of committed structured state plus independently
verified decision capabilities and recorded events. Models may propose plans, content, criteria, or
candidate actions; their text, tool choice, confidence, or self-reported status cannot select a transition.
Clock, randomness, provider responses, and human signals enter the reducer only as bounded, persisted,
schema-validated events with provenance and idempotency identity.

Missing, duplicated, reordered, future, unknown-schema, or conflicting events fail closed or replay to the
same result. A parser, planner, verifier, source, or durable-store failure parks/stops the affected branch;
there is no unskilled, cached, local-state, or model-text fallback that preserves mutation authority.

### D3 — Verification authority and ground truth are independent of the producer

The producer cannot define or alter the verifier identity, acceptance criterion, expected result, policy,
evidence source, gate configuration, or immutable result for its own work. Deterministic external probes
are preferred. Verification deterministically derives `pass`, `fail`, or `inconclusive` from closed
structured evidence; missing/unmeasured/errored evidence is `inconclusive`, never pass.

A model may analyze evidence only when the accepted risk/profile permits it. Its output is schema-clamped
and refute-by-default, but that does not make a model an independent oracle. Different family/provider,
blind voting, debate, judge prompts, or consensus is supporting evidence only; it is insufficient when the
producer controls the prompt, criteria, diff, sources, policy, routing, or result. A governed mutation or
completion gate cannot use an LLM as its sole arbiter.

A human decision is also exact evidence rather than a universal fallback. It must come from a pre-admitted
eligible identity and bind the specific revision/action/target; it cannot turn an unavailable technical
fact, forged provenance, unready profile, or forbidden effect into a verified one.

### D4 — Verification, landing, and Done are separate decisions

Landing may proceed only when every precommitted landing condition is measured true, the exact verification
and delivery-trust capabilities are current, the class/profile permits the branch, and D1/D5 authority is
present. `None`, missing, stale, partial, copied, or mismatched inputs park. A human gate may choose among
technically admissible branches but cannot waive an absent invariant unless a separately accepted,
revision-bound waiver policy explicitly permits it.

Auto-landing is default-off and requires its own accepted policy plus an exact ready profile/path and
certified required assurance. Production auto-landing is not authorized by this ADR. A verifier pass,
`converged` label, Draft PR, merge, deploy, or `can_auto_merge` result proves only its own branch; Done still
requires every frozen delivery/runtime/compensation Condition of Done under ADR-0010/ADR-0003.

### D5 — Disposition is closed, human-owned, and cannot self-widen

One versioned disposition policy maps the exact action, environment/Realm, class, and current assurance to
`autonomous`, `requires-human`, or `prohibited`. An unknown action or policy row is prohibited until a human
owner publishes an admitted classification; a known but unmeasurable row is non-autonomous. A factory,
model, skill, task frontmatter field, local administrator flag, or transitive tool chain cannot widen its
own row, eligibility, tier, target, or profile.

Human execution requires an immutable, append-only, single-purpose receipt binding the eligible human
identity/role, any required MFA or step-up evidence, decision, exact action/target/revisions, issue and
expiry times, and one-time/replay semantics. A generic `approved`, mutable toggle, actor string, UI click,
or factory-authored receipt is invalid. Composition analysis must fail any autonomous chain that reaches a
correctness-defining, boundary-expanding, credential-minting, policy-changing, or self-approval node.

### D6 — Breakers stop new effects; claims, compensation, and reconciliation close old ones

Every side effect has an atomic intent claim and an exact idempotency/concurrency strategy before the
provider call. It also has a pre-registered, independently admitted, idempotent compensator or is classified
non-compensatable and prohibited from autonomous execution. Task class informs the obligations; it does
not create a fictional rollback for an irreversible action or exempt a reversible action from effect
safety.

Precommitted class/profile budgets bound steps/retries, wall-clock, spend, provider calls, parked capacity,
and other accepted axes. A tripped breaker prevents new effects and drives the durable loop into a typed
stop/compensate/park state; it does not erase an in-flight external effect. Crash, timeout, response loss,
duplicate delivery, and controller disappearance reconcile exact provider truth under the persisted
claim. Compensation order and completion are decided by deterministic external probes, never an agent
signal. Unknown or failed reconciliation remains pinned/FROZEN for human resolution.

Retries cannot produce a second effect, cancellation cannot release an unresolved effect fence, and a
disposable filesystem/environment counts as rollback only for state proven not to have escaped that
boundary.

### D7 — Outcome and escape decisions require exact independent return evidence

`OutcomeEvent` and `ReturnEvent` are versioned, append-only, signal-only records emitted after durable
state changes. They never authorize a transition, provider action, landing, completion, rollback, or
autonomy widening. Exporter/backend failure cannot change workflow truth.

A return inside window `W` is only a candidate. `ESCAPED` requires an accepted attribution policy to join
the exact WorkOrder/task/SPEC, landed artifact/deployment and state epoch, independently owned return
source/revision, source coverage/freshness/liveness, return type, and human-owned window-policy revision.
Temporal proximity, matching text, a dashboard correlation, or a producer/verifier-authored incident is
insufficient and routes to human review or `unavailable`.

Missing/stale/partial return coverage makes escape rate and Autonomous Yield unavailable, never zero. The
verifier cannot create, suppress, close, or attest its own return. Replay, duplicates, late returns, source
severance, and disputed attribution preserve an append-only audit and cannot rewrite the original outcome.

## Consequences

**multiqlti:**

- the current Consilium reducer, CAS transitions, bounded rounds, Draft-PR pause, structured convergence,
  refute-by-default parser, and optional mechanical checks are useful construction mechanisms;
- current `class`/`autonomyTier` metadata, model-proposed criteria, optional verification/planner switches,
  human-visible flagged results, and local `converged` state do not jointly implement D1-D7;
- adoption needs a governed non-R0 WorkOrder/SPEC envelope, atomic effect admission, accepted external
  verification/landing authorities, closed disposition policy and receipts, effect claim/compensation,
  breaker/reconciliation semantics, and canonical outcome/return joins. The retired legacy pipeline is no
  longer an adoption target.

**omnius:**

- current dirty/local execution-bundle, Conductor, readiness, transaction, delivery, outcome, and Human
  Boundary contracts are candidate implementation evidence;
- legacy and candidate seams must be reconciled under accepted component SPECs, immutable revisions, exact
  profiles, protected identities, and real-path probes before any conformance claim;
- `can_auto_merge`, static no-LLM probes, a broad legacy autonomy row, a local HMAC test double, or a draft
  outcome model cannot independently establish D1-D7 or end-to-end Done.

**Platform:**

- equivalent branch decisions can be compared across engines without equating local state names;
- every decision has an explicit authority, frozen input projection, failure posture, expiry/replay rule,
  and non-authority boundary; and
- ADR-0016 may consume the final D6/D7 semantics only after the platform owner accepts compatible exact
  revisions; its proposed status does not bootstrap this proposal.

**Costs and risks:**

- both components need closed conformance fixtures and component-owned adoption contracts;
- multiqlti needs real effect admission and compensation rather than metadata plus a human-visible flag;
- omnius must retire or version-gate conflicting legacy seams rather than let strong candidate modules
  imply whole-system conformance; and
- conservative `inconclusive`/park behavior reduces apparent throughput but prevents unmeasured work from
  becoming authority.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Standardize one loop engine | Shared semantics do not require shared orchestration technology. |
| Action class/tier row is authorization | Classification omits profile, Realm, target, identity, compensation, and evidence. |
| Structured model boolean is a gate | Schema validity does not make the model an independent ground-truth authority. |
| Different model family proves independence | The producer may still control criteria, prompt, sources, routing, or result. |
| Human approval repairs missing evidence | A human may choose an admissible branch, not fabricate technical truth or readiness. |
| Merge, deploy, or `converged` means Done | Landing is only one condition in the frozen end-to-end contract. |
| All class-B effects must roll back | An irreversible action may have no honest rollback and must instead be prohibited/autonomy-gated. |
| Breaker expiration releases all locks | An unresolved external effect must remain fenced through reconciliation. |
| Return inside `W` means ESCAPED | Time correlation alone does not establish exact attribution. |
| Telemetry advances the workflow | Exporter compromise or outage would become execution authority. |

## Current component adoption map

These tables are a 2026-07-16 read-only observation, not a component SPEC, conformance result, or
readiness decision.

### multiqlti

| Rule | Current candidate mechanism | Required adoption boundary |
|---|---|---|
| D1 | Consilium `class` launch metadata (`R0`/`A`; higher classes reserved) | field is explicitly unread metadata; add frozen WorkOrder/profile/Realm/action authority and atomic pre-effect admission |
| D2 | Consilium reducer and state CAS; task-orchestrator dependency scheduling | prove total released-state/event mapping; remove fail-soft mutation fallbacks and bind every routing input to admitted structured authority |
| D3 | structured convergence, optional test/web/judge methods, refute-by-default judge parser | independently own criteria/oracle/evidence; model judge and optional/flag-only checks cannot be sole governed gate |
| D4 | Draft-PR human merge pause; optional verify-before-merge | exact delivery-trust/readiness join and end-to-end Conditions of Done; local `converged` is not organizational completion |
| D5 | selected human routes and trigger restrictions | closed disposition matrix, eligible-human authority, exact immutable receipts, composition and no-self-widen probes |
| D6 | max-round/anti-stall/throttle/cancel controls and some local idempotency | class/profile budgets, atomic effect claims, external compensators/reconciliation, crash and ambiguous-result fencing |
| D7 | local outcome/experience statistics | canonical append-only OutcomeEvent/ReturnEvent, independent live source health, exact attribution, no-silent-zero |

### omnius

| Rule | Current candidate mechanism | Required adoption boundary |
|---|---|---|
| D1 | execution compiler/readiness/action contracts and transaction ledger | reconcile legacy/broad action seams; publish exact action/profile/Realm/identity authority and real-path negative evidence |
| D2 | `mvp_core.conductor.contracts` deterministic FSM/replay and static probes | bind one released durable engine/state/event schema; prove crash/replay behavior rather than module purity alone |
| D3 | verifier, delivery trust-chain, observer/HTTP evidence candidates | exact independent production authorities, protected evidence, closed schemas and external positive/negative probes |
| D4 | `can_auto_merge`, completion and delivery-observation candidate gates | accepted policy/profile and complete delivery/runtime Conditions of Done; no merge-only completion |
| D5 | Human Boundary and readiness candidate contracts | retire/version-gate broad legacy matrix rows; pin human eligibility, receipts, profiles and composition evidence |
| D6 | SPEC-TX/CD candidates, intent claims, compensators, breakers and proposed reclaim issuer | publish effect/compensator catalog and durable store/engine bindings; qualify ambiguity, FROZEN, and exact reclaim fences |
| D7 | draft SPEC-OT, `mvp_core.outcomes`, source-health candidates and legacy `phase_2` model | publish shared schemas/outbox/compatibility; bind independent live return sources and prove liveness/attribution |

## Required conformance evidence

Component-owned fixtures must prove, without activating a production path:

- a proposed ADR, draft/unselected requirement, raw readiness field, task class, autonomy tier, action row,
  model output, or caller boolean cannot authorize mutation;
- every effect requires an exact frozen WorkOrder/task/SPEC/profile/Realm/action/target/identity projection,
  exclusive state/effect fence and atomic single-use redemption at an enforced mutation boundary; any
  post-freeze change conflicts or invalidates the capability before the provider call, and direct caller
  mutation is denied;
- unknown/broad/conflicting actions and missing profile/policy/receipt/capability evidence perform zero
  provider calls;
- equivalent committed state and recorded events replay to the same branch, while model text, duplicated,
  reordered, malformed, or unavailable events cannot select a positive transition;
- producer-controlled criteria, oracle, evidence, prompt, verifier policy, identity, or result cannot pass;
  model-family separation, debate, consensus, and schema-valid `passed: true` alone remain insufficient;
- `inconclusive`, stale, unmeasured, copied, or mismatched verification cannot land, and landing cannot
  close a WorkOrder whose frozen delivery/runtime/compensation probes remain open;
- autonomous composition cannot reach correctness/policy/credential/boundary/self-approval nodes; forged,
  wrong-human, wrong-revision/target, reused, expired, or mutable approvals fail;
- breakers prevent new effects without releasing unresolved ones; crash/timeout/response-loss/concurrent
  replay produces one claimed effect and a deterministic confirmed/compensated/pinned outcome;
- non-compensatable actions are prohibited from autonomy, failed/ambiguous compensation remains FROZEN,
  and disposable-environment rollback cannot erase an escaped external effect;
- OutcomeEvent/ReturnEvent payloads are closed, ordered, idempotent, redacted, lineage-complete and
  signal-only; forged/duplicate/reordered telemetry cannot change workflow state;
- temporal-only, wrong-artifact/task/revision/source/window, verifier-owned, stale, or partial returns
  cannot mark ESCAPED, and missing source liveness makes escape/yield unavailable rather than zero; and
- both factories derive the same decision meaning from equivalent frozen fixtures while retaining their
  own engines, and dirty/local evidence cannot satisfy an immutable release/profile requirement.

## Follow-ups

- [ ] Platform owner accepts this precedence-compatible revision with the matching ADR-0003 revision or
      marks ADR-0006 superseded.
- [ ] After acceptance, publish closed versioned decision-record/capability fixtures for D1-D7 and exact
      action/disposition catalogs without granting provider authority.
- [ ] `multiqlti` component SPEC: non-R0 WorkOrder/effect admission, independent verification/landing,
      disposition/receipt, breaker/compensation, and canonical outcome/return adoption.
- [ ] `omnius` component SPEC/readiness updates: reconcile legacy/candidate seams and pin exact released
      D1-D7 authorities, schemas, identities, durable stores, and probes.
- [ ] Add the loop-decision-model glossary row only after human acceptance.

## References

- Current multiqlti evidence: `shared/schema.ts`, `server/services/task-orchestrator.ts`,
  `server/services/consilium/consilium-loop-controller.ts`,
  `server/services/orchestrator/convergence.ts`, and `server/services/sdlc/executor.ts`.
- Current omnius evidence: `mvp_core/conductor/contracts.py`, `mvp_core/outcomes/__init__.py`,
  `mvp_core/human_boundary/contracts.py`, `conformance/can_auto_merge.py`,
  `phase_2/{tx_ledger,observability}.py`, `phase_3/human_boundary.py`, and draft
  `specs/SPEC-{CD,TX,OT}*.md`.
- [ADR-0003](0003-unified-sdlc-standard.md) — proposed lifecycle/telemetry compatibility standard.
- [ADR-0009](0009-organizational-dark-factory-sdd.md) — accepted ADR/SPEC/evidence authority.
- [ADR-0010](0010-goal-oriented-organizational-dark-factory.md) — accepted WorkOrder and end-to-end Done.
- [ADR-0012](0012-capability-readiness-profiles.md) — accepted exact readiness authority.
- [ADR-0016](0016-independent-safe-to-reclaim-decision-issuer.md) — proposed reclaim decision consumer.
