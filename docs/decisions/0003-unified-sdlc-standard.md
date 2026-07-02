# ADR-0003: Unified SDLC standard — dark-factory invariants for multiqlti and omnius

- **Status:** Proposed
- **Date:** 2026-07-02
- **Deciders:** platform owner
- **Scope:** binding for multiqlti and omnius; informative for PB-SRE / sre-harness
  (operational changes follow the same invariants via the action-tier table)
- **Vocabulary:** [platform-glossary.md](../platform-glossary.md) ·
  skills per [ADR-0002](0002-platform-skills-registry.md)

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

## Decision

The standard is **eight invariants over a task's life** — not a shared engine, not shared
stage names. Each factory keeps its execution model (multiqlti's staged pipeline, omnius's
FSM) and MUST satisfy the invariants through its own mechanisms. Conformance mapping is in
the Appendix.

### I1 — Task envelope

Every unit of work carries: a stable **`task_id`**, the **intent** (human-readable
description), a **task class**, and an **autonomy tier** (T1–T4 per the glossary).

Task class adopts the omnius axis as the platform governance dimension, extended with a
zero class for the personal tier:

| Class | Meaning | Default gate posture |
|---|---|---|
| **R0** | no side effects — text/JSON artifacts only, nothing leaves the run | light: advisory verification allowed |
| **A** | reversible change, dev/staging | quality-gated DoD (I3), auto-land possible |
| **B** | irreversible change, dev/staging | quality-gated DoD + human gate |
| **C** | reversible change, production | quality-gated DoD + human gate |
| **E** | irreversible change, production | human-gated always; never auto |

A multiqlti run defaults to **R0**; attaching a workspace commit, sandbox execution with
external effects, or a deployment target **escalates the class automatically** — the run
inherits the obligations of what it touches. This is how the standard preserves the
personal tier's exploratory speed: R0 stays light.

### I2 — Canonical lifecycle vocabulary

Seven canonical phases every task passes through (or terminally exits):

```
TRIGGERED → PLANNED → PRODUCED → VERIFIED → GATED → LANDED → OBSERVED
             (terminal exits: FAILED / CANCELLED / REJECTED / EXPIRED)
             (post-landing outcome: ESCAPED)
```

Factories keep their internal state names; cross-repo docs, telemetry (I6), and contracts
use the canonical names. Mapping is normative (Appendix A/B).

### I3 — Definition of Done is quality-gated, never process-gated

A task is **Done** only when:
(a) an I4-compliant verifier issued verdict **pass**, and
(b) the gate required by its class approved (auto-gate for R0/A within policy, human for
B/C/E).

Process completion without (a)+(b) is **Produced**, not Done.

Consequence for multiqlti (the single biggest change): for runs of class ≥ A, the default
pipeline template MUST wire `code_review.approved == true` and `fact_check.verdict != fail`
as **blocking** guardrails/DAG-conditions. The mechanism already exists
(`guardrail-runner`, DAG condition evaluator) — this changes the default, not the engine.
R0 runs may keep advisory mode.

Consequence for omnius: none — `can_auto_merge` already implements this.

### I4 — Producer ≠ verifier

The verifying agent/stage MUST use a **different model family** than the producing one,
and the run records the attestation (families used, distinct = true).

- omnius: already structural (`FamilyAttestation`).
- multiqlti: a configuration preset pins `testing` / `code_review` / `fact_check` to a
  different family than `development` (per-stage model assignment already exists); the
  consensus engine remains the stronger, optional form.

### I5 — Side-effect boundary

No autonomous irreversible action, anywhere. Operationally:

- every state-changing action kind maps to a minimum tier via the **action-tier table**
  (sre-harness `ACTION_TIER_TABLE` is the seed; extend for factory actions);
- production never auto-lands (omnius `target_tier` rule becomes platform law);
- shared-branch changes land via PR only — no direct pushes by agents (matches the
  monorepo git rules and ADR-0002 D4);
- multiqlti's sandbox / workspace / deployment features classify their actions before
  executing them.

### I6 — Common telemetry and the OutcomeEvent

Both factories emit OpenTelemetry GenAI semantic-convention traces (already chosen
independently by both) **plus** one structured event per task at terminal state:

```json
{
  "task_id": "…", "factory": "multiqlti|omnius",
  "class": "R0|A|B|C|E", "tier": "T1|T2|T3|T4",
  "lifecycle": "LANDED", "verdict": "pass|fail|parked|none",
  "gate": "auto|human|rejected", "verifier_families": ["…"],
  "landed_at": "2026-07-02T00:00:00Z", "cost_usd": 0.0
}
```

This makes **Autonomous Yield** and **escape rate** computable platform-wide with one
query, and gives the graduation path its evidence dossier for free.

### I7 — Skills from the platform registry only

Stages/workers consume skills from the registry (ADR-0002), with per-runtime trust. Where
a registry skill exists, inline ad-hoc how-to prompts are non-conformant.

### I8 — Escape tracking

A landed task that returns (bug, incident, revert, regression) within window **W** is
marked **ESCAPED**, joined by `task_id`. The return signal's source MUST be independent of
the verifier that passed the task (omnius rule, adopted platform-wide). Yield metrics
without I8 are considered invalid — a silent-zero escape stream is precisely the failure
the metric exists to catch.

## Consequences

**multiqlti (the personal factory changes most, but only in policy/config):**
- I1: add class field to runs; auto-escalation on workspace/sandbox/deploy attach
- I3: default blocking guardrails for class ≥ A
- I4: family-separation preset for verifying stages
- I6: OutcomeEvent emission
- Engine unchanged: stages, DAG, strategies, guardrails all stay.

**omnius (mostly already conformant):**
- I2: state-name mapping (incl. internal `FROZEN` vs `PARKED_AWAITING_HUMAN` cleanup)
- I6: OutcomeEvent schema adoption (FactoryObservability already close)
- I7: registry adapter (ADR-0002 D5)

**Platform:**
- Done means one thing everywhere; the graduation path gets a common measuring stick;
  an engineer (or agent) moving between factories re-learns nothing about safety.

**Costs / risks:**
- multiqlti default-blocking DoD will fail runs that used to "complete" — expected and
  desired, but needs a migration note and the R0 escape hatch.
- Class auto-escalation needs careful implementation (a run must not silently stay R0
  after gaining a workspace).
- Two OutcomeEvent emitters can drift → schema lives in this repo, versioned, with
  conformance fixtures.

## Alternatives considered

1. **Adopt the omnius FSM inside multiqlti** — rejected: engine rewrite, kills the
   exploratory tier's speed; the platform *wants* a light tier.
2. **Adopt multiqlti's phase model inside omnius** — rejected: omnius explicitly rejects
   the phase axis for safety reasons; regressing that design would weaken the governed tier.
3. **Glossary only, no invariants** — rejected: divergence #2 (Done semantics) is a live
   correctness hazard, not a naming problem.
4. **Full shared engine (one factory)** — rejected earlier (component map): the two tiers
   optimize different things; peers, not competitors.

## Appendix A — multiqlti conformance mapping

| Invariant | Mechanism (existing unless noted) |
|---|---|
| I1 class/tier | **new**: run field + auto-escalation; classes map to feature flags (workspace/sandbox/deploy attached) |
| I2 TRIGGERED | run created (`pending`/`running`) |
| I2 PLANNED | `planning` + `architecture` stage outputs |
| I2 PRODUCED | `development` / `deployment` stage outputs (`files[]`) |
| I2 VERIFIED | `testing` + `code_review` + `fact_check` outputs, sandbox execution results |
| I2 GATED | approval gates (`awaiting_approval` → approve/reject), blocking guardrails |
| I2 LANDED | run `completed` **and** (class ≥ A) workspace commit / PR created |
| I2 OBSERVED | `monitoring` stage + trigger-driven follow-ups |
| I2 terminal exits | `failed` / `cancelled` / `rejected` |
| I3 | guardrail `llm_check`/`json_schema` on `approved`/`verdict` — **default changes to blocking for class ≥ A** |
| I4 | per-stage `defaultModelSlug` + `model_skill_bindings` — **new preset**; consensus engine as strong form |
| I5 | sandbox presets, workspace commit path, connections allow-list — **classify against action-tier table** |
| I6 | OpenTelemetry (#94) — **add OutcomeEvent** |
| I7 | `git-skill-sync` → registry (ADR-0002 D5) |
| I8 | **new**: join incident/revert signals to `run.id` |

## Appendix B — omnius conformance mapping

| Invariant | Mechanism |
|---|---|
| I1 class/tier | CedarPDP classes A/B/C/E (R0 not applicable — omnius tasks are side-effectful by definition); Autonomy Matrix dispositions map to tiers |
| I2 TRIGGERED | `TRIGGERED` |
| I2 PLANNED | `PLANNING` → `CLASSIFIED` |
| I2 PRODUCED | `RUNNING` (worker diff + snapshot) |
| I2 VERIFIED | `VERIFYING` (Verdict with proofs A/A′/B/E, canaries) |
| I2 GATED | `DRAFT_PR` + `can_auto_merge` / `PARKED_AWAITING_HUMAN` (+ internal `FROZEN`) |
| I2 LANDED | `MERGED` → `CI_APPLY` → `DONE` |
| I2 OBSERVED | post-merge validation + escape window (FactoryObservability) |
| I2 terminal exits | `ABORTED` / `EXPIRED` (via `ROLLBACK`) |
| I3 | `can_auto_merge` 7 conditions, fail-closed |
| I4 | `FamilyAttestation.distinct`, worker pool ≠ evaluator pool, independence weights |
| I5 | Autonomy Matrix (17 rows), prod-main-branch guard, Class E freeze, L5CompositionProbe |
| I6 | OutcomeEvent/ReturnEvent in FactoryObservability — **align schema with I6** |
| I7 | `SkillStore.admit` ← registry (ADR-0002 D5) |
| I8 | escape rate from the incident plane, independent of evaluator — already the model for the platform |

## Follow-ups

- [ ] Publish the OutcomeEvent JSON schema (versioned) in this repo + conformance fixtures.
- [ ] multiqlti issues: run class field + auto-escalation; blocking-DoD default template
      (class ≥ A); verifier family preset; OutcomeEvent emitter.
- [ ] omnius issues: canonical-state mapping doc (incl. `FROZEN`/`PARKED` naming);
      OutcomeEvent schema alignment.
- [ ] Extend the sre-harness action-tier table with factory action kinds (commit, PR,
      merge, deploy, migration).
- [ ] Add an "SDLC standard" row to the glossary's Part 2 after acceptance.

## References

- Analysis inputs: multiqlti `shared/constants.ts`, `server/controller/pipeline-controller.ts`,
  `server/pipeline/{guardrail-runner,dag-executor}.ts`, `server/consensus/consensus-engine.ts`;
  omnius `mvp_core/conductor/__init__.py`, `mvp_core/verifier/__init__.py`,
  `mvp_core/pool/__init__.py`, `conformance/can_auto_merge.py`, `phase_3/human_boundary.py`,
  `mainplan.md`, `architecture/MASTER-ARCHITECTURE.md`
- [platform-glossary.md](../platform-glossary.md) — autonomy tiers, gate/guardrail ruling,
  graduation path
- [ADR-0002](0002-platform-skills-registry.md) — skills registry
- sre-harness `ACTION_TIER_TABLE` — action-tier seed
