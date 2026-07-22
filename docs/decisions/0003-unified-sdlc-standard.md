# ADR-0003: Unified SDLC standard — dark-factory invariants for multiqlti and omnius

- **Status:** Proposed
- **Date:** 2026-07-02
- **Last reviewed:** 2026-07-16 (acceptance-readiness reconciliation; status unchanged)
- **Deciders:** platform owner
- **Scope:** intended cross-repo compatibility standard for multiqlti and omnius; non-binding while
  Proposed; informative for PB-SRE / sre-harness
- **Vocabulary:** [platform-glossary.md](../platform-glossary.md) ·
  candidate shared-skill trust per proposed [ADR-0002](0002-platform-skills-registry.md)

## Context

The platform runs two factories that must interoperate: **multiqlti** (personal tier,
proving ground) and **omnius** (centralized tier, governed). A code-level analysis of both
(2026-07-02) found they hold different — and in one place dangerously different — models of
what a "dark factory" is:

| # | Dimension | multiqlti | omnius |
|---|---|---|---|
| 1 | Work axis | **phases**: planning → architecture → development → testing → code_review → deployment → monitoring (`shared/constants.ts` TEAM_ORDER) | **reversibility × environment**: task classes A/B/C/E via Cedar (`mvp_core/pool`); explicitly rejects the phase axis |
| 2 | Definition of Done | **process completion**: run is `completed` when all stages produced output without errors; `code_review.approved` and `fact_check.verdict` are **advisory** — the controller never enforces them | **quality-gated**: verdict `pass` + 7-condition fail-closed `can_auto_merge` or human approval; post-hoc **escaped** tracking |
| 3 | Verifier independence | opt-in (consensus engine with blind verdict + independent voters exists but is not required); `testing` *generates* tests, does not run them (sandbox default off) | structural: Worker family A ≠ Evaluator family B (attested), dual sandbox, proofs A/A′/B/E, mutation + null-agent canaries |
| 4 | Failure & rollback | stage failure fails the run; no retries (outside guardrails) | saga compensators, IntentClaim idempotency, ROLLBACK/EXPIRED, "the disposable env *is* the rollback" |
| 5 | Vocabulary | run / stage / team / approval gate / completed | workflow / task class / zone / verdict / DONE / parked / escaped |

The key structural observation — the two factories are **mirror images**:

- multiqlti is **autonomous by default but produces only text** (git/sandbox/deploy are
  opt-in) — low stakes, so autonomy is safe *by accident*;
- omnius is **locked down by default but produces real changes** (diff → PR → merge) —
  high stakes, so autonomy is bounded *by structure*.

Both embody the same principle — **autonomy is inversely proportional to
irreversibility** — one implicitly, one explicitly. The standard's job is to make the
shared principle explicit and portable, *without* replacing either engine.

The dangerous divergence is #2: today a multiqlti run can finish `completed` with
`approved: false` inside its own artifacts. Any cross-factory workflow (graduation path,
shared metrics, handoffs) silently inherits that ambiguity until Done means one thing.

The comparison above is a **2026-07-02 design snapshot**, not current conformance evidence. A
2026-07-16 read-only recheck still finds multiqlti's local `RunStatus` and stage vocabulary but no
canonical WorkOrder, task class, or OutcomeEvent symbols. Omnius has extensive dirty/local WorkOrder
and outcome construction plus a draft `SPEC-OT`, while its legacy `phase_2.OutcomeEvent` remains a
minimal non-canonical model. None of those local mechanisms accepts this ADR, publishes the shared
schema, or proves cross-factory conformance.

## Acceptance boundary and precedence

This proposal predates and is subordinate to the accepted authority chain:

1. [ADR-0009](0009-organizational-dark-factory-sdd.md) — ADR → capability SPEC → task SPEC → evidence;
2. [ADR-0010](0010-goal-oriented-organizational-dark-factory.md) — durable WorkOrder intake and
   probe-defined end-to-end completion; and
3. [ADR-0012](0012-capability-readiness-profiles.md) — exact human-owned REQ/probe/revision readiness.

ADR-0009's historical `Builds on` reference does **not** retroactively accept ADR-0003. Where this
proposal conflicts with any accepted decision, the accepted decision wins. The proposed disposition is
to accept ADR-0003 only as the compatible lifecycle/telemetry standard revised below; the platform owner
may instead supersede it. Either choice is human-owned. An agent cannot change its status, publish the
shared schema, or open dependent component execution merely because mappings or local tests exist.

## Decision

The standard is **eight invariants over a task's life** — not a shared engine, not shared
stage names. Each factory keeps its execution model (multiqlti's staged pipeline, omnius's
FSM) and MUST satisfy the invariants through its own mechanisms. Conformance mapping is in
the Appendix.

### I1 — WorkOrder and immutable task envelope

Every organizational input first normalizes to a durable, idempotent **WorkOrder** under ADR-0010. Before
any persistent mutation, an admitted child task freezes an immutable execution contract containing at
least: `work_order_id`, stable `task_id`, exact task-SPEC revision, governing ADR and capability-SPEC
revisions, readiness-profile revision/digest where applicable, intent, scope, effective Realm, task
class, autonomy limit, Conditions of Done and registered probes, policy/path/skill/tool/model/verifier
pins, budget, credential boundary, compensation, and provenance.

Task class and autonomy tier in source/frontmatter are requests, never authority. Deterministic
classification, Realm policy, the exact readiness profile, and admitted evidence may only widen risk/
assurance obligations or preserve/lower autonomy; they cannot make a request less governed. Unknown,
conflicting, unready, or unmeasurable inputs park before mutation.

Task class adopts the omnius axis as the platform governance dimension, extended with a
zero class for the personal tier:

| Class | Meaning | Default gate posture |
|---|---|---|
| **R0** | no side effects — text/JSON artifacts only, nothing leaves the run | light: advisory verification allowed |
| **A** | reversible change, dev/staging | quality-gated DoD (I3), auto-land possible |
| **B** | irreversible change, dev/staging | quality-gated DoD + human gate |
| **C** | reversible change, production | quality-gated DoD + human gate |
| **E** | irreversible change, production | human-gated always; never auto |

A multiqlti local run may remain a provisional R0 exploration while it has no persistent side effect and
makes no organizational completion claim. Cross-factory handoff or attachment of a workspace commit,
sandbox execution with external effects, or a deployment target requires a committed task SPEC and
reclassification before the effect. R0 keeps lighter document weight, not weaker traceability or a bypass
around the mutation boundary.

### I2 — Canonical lifecycle observations

Seven canonical milestones describe cross-factory progress:

```
TRIGGERED → PLANNED → PRODUCED → VERIFIED → GATED → LANDED → OBSERVED
             (terminal exits: FAILED / CANCELLED / REJECTED / EXPIRED)
             (post-landing return classification: ESCAPED)
```

These are telemetry observations, not a universal engine FSM and not a claim that every task must
fabricate every milestone. A research/R0 task may have no landing; an A-to-Z delivery may remain
incomplete after `LANDED` until runtime observation probes pass. `DONE` is the task/WorkOrder terminal
state defined by I3, not an alias for any single milestone. `PARKED` is a reason-coded non-terminal
control state. `FROZEN` is a reason-coded containment hold whose workflow terminality, release path, and
resource reclaimability are component-owned and must be stated separately: a component may treat it as
terminal for workflow progression while keeping resources pinned and release human-only. Cross-factory
telemetry must not infer `DONE` or reclaimability from that terminal label. Factories keep internal state
names; an accepted component SPEC must provide a total deterministic mapping for every internal state,
state its terminality and reclaimability semantics, and explicitly mark inapplicable milestones.

### I3 — Definition of Done is probe-defined and end-to-end

A task or WorkOrder is **Done** only when its frozen Conditions of Done are satisfied by the exact
registered I4-compliant probes, all required policy/landing gates have passed, and every applicable
delivery/runtime/compensation obligation is closed. A verifier verdict, completed pipeline, merged PR,
deployment, or telemetry event alone is never enough. Research completion uses precommitted process-
quality probes; it does not claim objective truth for every conclusion.

For multiqlti, `code_review.approved` and `fact_check.verdict` may be useful inputs but cannot become an
organizational oracle merely by being wired as blocking guardrails. A conformant non-R0 handoff needs the
frozen SPEC/Condition-of-Done contract, registered probes, independent evidence, and applicable gate.
Personal R0 output may remain advisory but cannot emit a verified organizational outcome.

For omnius, `can_auto_merge` decides one landing branch; it does not by itself implement end-to-end Done.
Completion remains open through the exact delivery and runtime probes required by the WorkOrder.

### I4 — Producer cannot control the verifier or ground truth

Verification authority, probe definition, expected result, policy, evidence source, and immutable
result must be independent of the producing identity. Deterministic external probes are preferred. If a
model is used as a verifier, the execution records its exact identity and uses a different model family
or provider where the risk profile requires and availability permits. Different model family alone is
not independence when the producer can change the prompt, criteria, evidence, gate, or result.

`FamilyAttestation`, per-stage model assignment, consensus, and blind voting are supporting mechanisms,
not self-sufficient proof. Missing or unmeasured independence is `inconclusive`/parked for governed work,
never `pass`.

### I5 — Side-effect classification is not authorization

Every state-changing action kind maps to a minimum autonomy tier through a closed versioned action
catalog. That mapping classifies risk; it does **not** grant a provider call. Execution additionally
requires the exact ready requirement/profile, effective Realm and deny policy, immutable action and
target, step-scoped identity, required human receipt or bounded-autonomy capability, idempotency,
compensation/rollback posture, and retained evidence. Unknown or broad action labels route to human and
cannot authorize a more specific effect.

No agent request, model output, task frontmatter, or action-table entry can self-authorize an irreversible
or production action. Production landing/auto-merge remains default-off and may occur only under a
separately accepted policy, exact ready profile/path, certified required assurance, and external gates;
this ADR grants none. Shared-branch changes use protected PR/MR paths, never direct agent pushes.
multiqlti must classify and admit sandbox/workspace/deployment effects before execution, not after.

### I6 — Canonical telemetry is versioned, append-only, and signal-only

Both factories emit severable OpenTelemetry correlation plus versioned, closed canonical events derived
from durable workflow truth **after** a transition. Telemetry never authorizes, advances, completes, or
escapes a task.

An `OutcomeEvent` binds at least schema/event identity and sequence; occurrence time; factory,
`work_order_id`, `task_id`, workflow and task-SPEC revision; governing ADR/capability SPEC/REQ/probe
revisions; Realm, class/tier, readiness profile, PlatformPath and policy pins; canonical lifecycle/outcome;
gate/verifier attestation; immutable evidence manifest; applicable landing/observation time; cost; and
trace correlation. A separate `ReturnEvent` binds its exact independent source identity/revision,
coverage/freshness, occurrence time, return type, and exact WorkOrder/task/revision join.

Events are idempotent and ordered per workflow through a transactional outbox or equivalently proven
durable boundary. They contain no prompt body, chain of thought, secret/credential, raw diff, unrestricted
log, or caller-authored success flag. Unknown schema, unresolved lineage, missing source health, or stale
coverage yields dead-letter/`unavailable`, never a plausible success or zero escape rate. The JSON shape
is published only through the follow-up shared schema and conformance fixtures; local draft models are not
the platform contract.

### I7 — Skills are pinned guidance, never authority

ADR-0002 is still Proposed, so this ADR cannot activate a shared registry or trust root by reference.
Until that decision is accepted or replaced, a reusable skill used by governed work must be pinned to
exact content, locally admitted under an independently owned trust policy, and recorded in the execution
contract. Skills guide planning; policy, identities, gates, probes, and provider boundaries enforce
safety. A task-specific instruction is allowed, but it cannot silently shadow an admitted reusable skill
or redefine its success criteria. Missing trust degrades to no skill/human review, not inline authority.

### I8 — Escape tracking requires exact independent return evidence

A bug, incident, revert, or regression signal becomes a candidate `ReturnEvent` only when it resolves to
the exact WorkOrder, task/SPEC revision, landed artifact/deployment, source revision, and human-owned
window policy. Its source and ingestion authority must be independent of the verifier that passed the
task. Mere temporal correlation cannot mark a task `ESCAPED`; the accepted return/attribution policy and
independent evidence must establish the relation or route it to human review.

Every return source publishes coverage, freshness, and liveness. Missing/stale/partial coverage makes
escape rate and Autonomous Yield `unavailable`, not zero. The verifier cannot create, suppress, or close
its own return event, and a dashboard cannot change durable workflow truth.

## Consequences

**multiqlti:**
- may keep its stages, DAG, strategies, guardrails, and interactive R0 experience;
- needs a real non-R0 mutation-admission boundary, WorkOrder/task-SPEC correlation, deterministic
  class/tier derivation, frozen Conditions of Done, independent probe evidence, and canonical events;
- cannot promote `completed`, blocking LLM guardrails, or model-family diversity into organizational
  completion evidence without those boundaries.

**omnius:**
- owns its WorkOrder/FSM/readiness/compiler and component SPEC implementations;
- must map every internal state to the canonical observation contract without treating `can_auto_merge`
  or a PR merge as end-to-end completion;
- must replace or explicitly version-gate its minimal legacy outcome models against the future shared
  OutcomeEvent/ReturnEvent schemas. Dirty/local mechanisms and a draft `SPEC-OT` are construction
  evidence, not published conformance.

**Platform:**
- Done means one thing everywhere; the graduation path gets a common measuring stick;
  an engineer (or agent) moving between factories re-learns nothing about safety.

**Costs / risks:**
- multiqlti's non-R0 path becomes a real admission feature, not only a default-template change;
- class escalation and effect admission must be atomic so a run cannot gain a workspace or provider
  capability while silently staying R0;
- two event producers can drift, so the shared schemas, compatibility policy, mapping fixtures, and
  source-health semantics become governed platform surfaces;
- accepted ADR-0009/0010/0012 must remain visibly authoritative so accepting this compatibility standard
  cannot reopen their human/readiness boundaries.

## Alternatives considered

1. **Adopt the omnius FSM inside multiqlti** — rejected: engine rewrite, kills the
   exploratory tier's speed; the platform *wants* a light tier.
2. **Adopt multiqlti's phase model inside omnius** — rejected: omnius explicitly rejects
   the phase axis for safety reasons; regressing that design would weaken the governed tier.
3. **Glossary only, no invariants** — rejected: divergence #2 (Done semantics) is a live
   correctness hazard, not a naming problem.
4. **Full shared engine (one factory)** — rejected earlier (component map): the two tiers
   optimize different things; peers, not competitors.

## Appendix A — multiqlti historical mapping and gaps

This is a planning map from the 2026-07-16 read-only source/index observation. It is not a component
SPEC, readiness decision, or conformance result.

| Invariant | Current evidence | Required adoption |
|---|---|---|
| I1 | local `RunStatus`; no indexed WorkOrder/task-class contract | committed non-R0 WorkOrder/task-SPEC envelope and pre-effect reclassification |
| I2 | `TEAM_ORDER` plus local run/stage statuses | total internal-state → canonical-observation mapping; no fabricated milestones |
| I3 | review/fact-check artifacts and configurable approval/guardrails | frozen Conditions of Done plus registered independent probe and gate evidence |
| I4 | per-stage model assignment and optional consensus | independent oracle/evidence authority; model separation only when applicable |
| I5 | sandbox/workspace/deployment and connection controls | closed action classification plus separate exact authorization before every effect |
| I6 | local telemetry mechanisms; no indexed canonical OutcomeEvent | shared closed OutcomeEvent/ReturnEvent producer and durable emission evidence |
| I7 | local skills and sync mechanisms | exact content pin plus accepted/local trust; no skill-based authority |
| I8 | no canonical return join found | independent exact return source, window policy, liveness, and attribution evidence |

## Appendix B — omnius candidate mapping and gaps

This map describes dirty/local construction and component-owned drafts. Only immutable component SPEC,
readiness, implementation, and probe evidence can establish conformance.

| Invariant | Candidate mechanism | Remaining boundary |
|---|---|---|
| I1 | WorkOrder, Realm, execution-compiler, and readiness-profile construction | immutable published component revisions and human/external admission |
| I2 | Conductor FSM and draft SPEC-OT mapping | total mapping over exact released FSM; PARKED stays non-terminal, while the current FROZEN candidate is a terminal-but-pinned hold with human-only release and must not imply Done or reclaimability |
| I3 | `can_auto_merge`, completion-gate, and HTTP runtime probes | prove the complete frozen Condition of Done; merge alone is non-terminal |
| I4 | `FamilyAttestation`, external probes, verifier gates | prove authority/evidence independence; family distinction alone is insufficient |
| I5 | Autonomy Matrix, Human Boundary, compiler and provider gates | exact action/profile/Realm/identity authorization and real-path evidence |
| I6 | minimal legacy `phase_2` models plus draft `SPEC-OT` | future shared schemas, compatibility, transactional outbox, lineage and redaction evidence |
| I7 | local skill admission and proposed registry consumer | accepted trust root/exact pin or explicit no-skill fallback |
| I8 | draft incident/return and source-health contracts | independent live source, exact joins, window authority, liveness and no-silent-zero evidence |

## Required conformance evidence

Component-owned fixtures must prove, without activating a profile or production path:

- a proposed ADR, draft/unselected requirement, raw readiness field, or caller-supplied tier cannot admit
  mutation;
- an R0 run that gains a persistent workspace, provider, or deployment effect parks and reclassifies
  before the first effect, while a pure local exploration cannot claim organizational completion;
- every released internal state maps deterministically to one canonical milestone/terminal outcome or an
  explicit inapplicable value; a merge/`LANDED` event cannot close a WorkOrder whose runtime probes remain,
  and a component-terminal `FROZEN` hold cannot imply `DONE` or resource reclaimability;
- producer-controlled criteria, evidence, prompt, verifier policy, or result cannot pass; changing model
  family alone cannot satisfy independence;
- an action-tier lookup without the exact profile/Realm/policy/identity/target/receipt/capability evidence
  reaches no provider, and an unknown/broad action routes to human;
- forged, duplicated, reordered, unknown-schema, lineage-incomplete, or sensitive OutcomeEvent/ReturnEvent
  payloads cannot change workflow state or produce a trusted metric;
- telemetry/backend severance leaves durable workflow truth unchanged, while missing return-source
  coverage makes escape/yield unavailable and emits liveness evidence rather than zero;
- an untrusted or changed skill cannot authorize a tool/action or redefine acceptance criteria; and
- both factories produce the same canonical meaning from equivalent frozen task/evidence fixtures while
  retaining independent internal engines.

## Follow-ups

- [ ] Platform owner accepts this precedence-compatible revision or marks ADR-0003 superseded.
- [ ] After acceptance, publish closed versioned OutcomeEvent and ReturnEvent schemas, compatibility
      policy, lifecycle/source-health fixtures, and privacy/lineage negative cases in this repo.
- [ ] multiqlti component SPEC: non-R0 WorkOrder/task-SPEC admission, atomic class escalation,
      Condition-of-Done probes, independent verification, action authorization, and event/return emission.
- [ ] omnius component SPEC/readiness updates: exact canonical-state mapping and shared event-schema
      adoption without treating dirty/local `SPEC-OT` or legacy models as publication evidence.
- [ ] Add exact direction-specific factory action kinds (commit, PR, merge, deploy, migration) only through
      an accepted action-catalog SPEC that keeps classification separate from provider authorization.
- [ ] Add an "SDLC standard" row to the glossary's Part 2 after acceptance.

## References

- Analysis inputs: multiqlti `shared/constants.ts`, `server/controller/pipeline-controller.ts`,
  `server/pipeline/{guardrail-runner,dag-executor}.ts`, `server/consensus/consensus-engine.ts`;
  omnius `mvp_core/conductor/__init__.py`, `mvp_core/verifier/__init__.py`,
  `mvp_core/pool/__init__.py`, `conformance/can_auto_merge.py`, `phase_3/human_boundary.py`,
  `mainplan.md`, `architecture/MASTER-ARCHITECTURE.md`
- [platform-glossary.md](../platform-glossary.md) — autonomy tiers, gate/guardrail ruling,
  graduation path
- [ADR-0002](0002-platform-skills-registry.md) — proposed skills registry; not authority until accepted
- [ADR-0009](0009-organizational-dark-factory-sdd.md) — accepted ADR/SPEC/evidence authority
- [ADR-0010](0010-goal-oriented-organizational-dark-factory.md) — accepted WorkOrder and end-to-end Done
- [ADR-0012](0012-capability-readiness-profiles.md) — accepted exact readiness authority
- omnius `specs/SPEC-OT-outcome-telemetry.md` — informative component draft, not shared-schema authority
- sre-harness `ACTION_TIER_TABLE` — action-tier seed
