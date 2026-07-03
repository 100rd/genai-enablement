# ADR-0004: Unified loop decision model — how a task-loop decides, for multiqlti and omnius

- **Status:** Proposed
- **Date:** 2026-07-03
- **Deciders:** platform owner
- **Scope:** binding for multiqlti and omnius; informative for PB-SRE / sre-harness
  (the action-tier table is the shared seed for D1)
- **Builds on:** [ADR-0003](0003-unified-sdlc-standard.md) (task-lifecycle invariants I1–I8).
  ADR-0003 defines *what* Produced / Verified / Done / Landed / Escaped mean; this ADR defines
  *how* each branch point in the loop is decided.
- **Vocabulary:** [platform-glossary.md](../platform-glossary.md) (autonomy tiers T1–T4,
  task classes, gate vs guardrail) · skills per [ADR-0002](0002-platform-skills-registry.md)

## Context

The platform runs two factory loops that must make decisions the same *way*, without sharing
an engine: **multiqlti** (personal tier, staged DAG pipeline) and **omnius** (centralized tier,
durable FSM). ADR-0003 unified the task lifecycle. It did **not** unify the *decision rules* at
the loop's branch points — how the next step is chosen, how a verdict is reached, when work
escalates to a human, when the loop stops or rolls back.

A code-level reconnaissance of both loops (2026-07-03, two independent read-only passes) found:

- **omnius** already decides every load-bearing branch by a deterministic, out-of-LLM rule that
  fails closed. Two conformance probes (`probe_cc5_gate_deterministic`,
  `probe_bm3_no_llm_judge_in_gate`) statically grep the gate/verifier packages for an LLM import
  or a `route_turn(` call and **block the merge** if found. The LLM is a *producer*, never an
  *arbiter*.
- **multiqlti** has **two execution paths** with opposite decision postures:
  - the base `PipelineController` is **autonomous-by-default with a process-completion DoD** —
    its only hard blocks are deterministic *structural* checks (DAG readiness/conditions,
    sandbox exit code) and *opt-in, default-off* human gates. Its quality machinery
    (`guardrail-runner`, the "Dark Factory" plan/DoD evaluators) is **unwired** — `applyGuardrails`
    has zero callers, `GuardrailValidator.validate()` is never invoked, the evaluator services
    have no callers and return stubs. Quality is aspirational here.
  - the separate **Consilium / SDLC FSM** genuinely enforces a DoD: a deterministic convergence
    derivation (converged ⟺ zero open P0 action points), a refute-by-default per-AP judge
    verifier (schema requires `passed: bool`; absence ⇒ not-passed), a mechanical weak-criterion
    lint, and a human `merge_approved` + Draft-PR gate.

So the two loops *already agree* on decision posture **in their strict paths** — deterministic
control-flow, out-of-LLM gates, fail-closed, human-owns-the-irreversible. The divergence is that
this posture is omnius's **only** path but multiqlti's **non-default** path. This is a correctness
hazard: a cross-factory workflow (graduation, shared yield) that assumes a task was *decided* the
same way inherits multiqlti's autonomous base path silently.

> Note — this corrects an assumption in ADR-0003 Appendix A ("the mechanism already exists,
> guardrail-runner + DAG condition evaluator — this changes the default, not the engine"): the
> guardrail path is not wired into the base pipeline. multiqlti's conformant path is the
> Consilium/SDLC loop; adoption routes class ≥ A there (or wires blocking guardrails into the
> base pipeline). See Appendix A.

## Decision

The standard is **seven decision rules over a task-loop** — the *model*, not the engine, not the
tools, not the prompts, not the model choices. Each factory keeps its loop (multiqlti's DAG +
Consilium FSM, omnius's conductor FSM) and MUST decide each branch point by the rule below,
through its own mechanism. Conformance mapping is in Appendices A/B.

Two principles govern all seven (both already visible in code): **autonomy is inversely
proportional to irreversibility**, and **ground truth for a decision comes from outside the
producer**.

### D1 — Action admission (before every side effect)

Every side-effecting action is classified — task **class** (R0/A/B/C/E per ADR-0003 I1) and a
minimum **tier** — by a deterministic classifier **before** it executes. Irreversible or
production actions are never auto-admitted. An **unknown** action classifies to the most
restrictive posture (→ human), never the least. The action-tier table (sre-harness
`ACTION_TIER_TABLE`) is the shared seed; each factory extends it for its own action kinds
(commit, PR, merge, deploy, migration, sandbox exec).

- *Inherited (norm):* classify-before-execute, unknown → most-restrictive, prod/irreversible ≠ auto.
- *Per factory (execution):* which classifier (Cedar policy vs a TS action map), the exact table.

### D2 — Control-flow selection (deterministic, out-of-LLM)

Which step/transition runs next is decided by deterministic code reading **structured fields** —
never by an LLM's free text, never by `eval()`. An LLM may *produce* the content a step consumes;
it may not *choose* the control flow. (This is the control/data-flow separation of SPEC-CD
REQ-CD-9 / SPEC-BM REQ-BM-15, raised to platform law.)

- *Inherited (norm):* control flow is a pure function of structured state; content ≠ routing.
- *Per factory (execution):* FSM transition table (omnius) vs topological DAG + condition
  evaluator (multiqlti).

### D3 — Verification decision (producer ≠ verifier, LLM never the sole arbiter)

A pass/fail verdict is issued by a verifier **independent of the producer** (different model
family, ADR-0003 I4) and is **derived by deterministic rule over structured signals**. An LLM is
**never the sole arbiter of a gate** (SPEC-BM REQ-BM-3). Where an LLM verifier is used, its output
is schema/enum-clamped and **refute-by-default**: absence, error, or unparseable output ⇒
not-passed, never a silent pass.

- *Inherited (norm):* independent verifier, deterministic derivation, LLM-refute-by-default,
  no-LLM-as-sole-gate.
- *Per factory (execution):* proofs A/A′/B/E + canaries + independence weights (omnius) vs
  convergence derivation + per-AP refute-by-default judge + weak-criterion lint (multiqlti
  Consilium loop).

### D4 — Landing decision (fail-closed: auto vs human)

Landing (merge / commit / deploy) is auto **only if every condition is measurable and true and
the class permits it**; any condition that is `None` / unmeasured / unknown routes to a **human
gate** (fail-closed). Production never auto-lands.

- *Inherited (norm):* all-conditions-measurable-and-true, else human; `None` = fail, not pass;
  prod = human.
- *Per factory (execution):* `can_auto_merge` 7-condition predicate (omnius) vs `awaiting_merge →
  merge_approved` + Draft-PR (multiqlti Consilium loop).

### D5 — Autonomy disposition & escalation (one matrix, no self-widening)

Escalation is decided by a single disposition model — `{ auto, human-gate, human-forever }` — over
(action, environment). An **unknown row escalates to human.** No autonomous chain may widen its own
autonomy: the autonomy toggle is **human-set and out of the factory's reach** (no-self-promotion,
L4-never-L5); a chain that transitively reaches a correctness-defining or boundary-expanding node
must not run autonomously.

- *Inherited (norm):* one disposition table, unknown → human, human-owned toggle,
  no-self-promotion / L5 composition check.
- *Per factory (execution):* Autonomy Matrix (17 rows) + L5CompositionProbe (omnius) vs the
  disposition table multiqlti must adopt (today: only default-off `approvalRequired` + human merge).

### D6 — Stop & rollback decision (breakers; compensate for class ≥ B)

The loop stops on deterministic **circuit breakers** scoped per class (cost, wall-clock, retry
ceiling, crash). For class ≥ B, a landed-then-failed task **must** roll back — a registered
compensator, or "the disposable environment *is* the rollback". Effects are **idempotent**: a
duplicate execution is a no-op, not a second effect.

- *Inherited (norm):* per-class breakers, mandatory rollback for class ≥ B, idempotent effects.
- *Per factory (execution):* saga reconciler + IntentClaim (DB-unique) + breakers (omnius) vs the
  compensator/idempotency model multiqlti must add (today: stage-fail ⇒ run-fail, no rollback).

### D7 — Outcome & escape decision (return signal independent of the verifier)

A landed task that returns (bug, incident, revert, regression) within window **W** is decided
**ESCAPED**, and the return signal's source MUST be **independent of the verifier that passed it**
(ADR-0003 I8). A yield figure computed without D7 is invalid.

- *Inherited (norm):* independent return signal, ESCAPED within W, no-escape-tracking = invalid-yield.
- *Per factory (execution):* incident-plane escape rate (omnius, already the platform model) vs the
  OutcomeEvent/return join multiqlti must add.

## Consequences

**multiqlti (most of the change is here):**
- The **conformant loop is the Consilium/SDLC FSM**, which already satisfies D2/D3/D4 and the human
  half of D5. Any run of **class ≥ A must be decided on that path** — OR the base pipeline must wire
  blocking guardrails (currently dead) + an action-admission classifier before it may run class ≥ A.
- **D1**: add a before-execute action classifier (workspace/commit/PR/deploy/sandbox) with
  auto-escalation (ADR-0003 I1).
- **D5**: adopt an explicit disposition table (seed from sre-harness `ACTION_TIER_TABLE`) instead of
  the single default-off `approvalRequired` flag.
- **D6**: add a compensator/idempotency model for class ≥ B (today none).
- **D7**: emit the OutcomeEvent + escape join (ADR-0003 I8, already tracked as multiqlti#445).
- Engine unchanged: DAG, strategies, Consilium FSM all stay.

**omnius (already conformant):**
- D1–D7 each map to an existing deterministic mechanism (Appendix B). No behavioral change.
- Only alignment work: keep the `probe_cc5` / `probe_bm3` gate-determinism probes as the machine
  enforcement of D2/D3 (already present), and emit the platform OutcomeEvent for D7 (ADR-0003 I6).

**Platform:**
- A decision made in either factory means the same thing; the graduation path can trust that a
  task was *decided*, not just *labeled*, the same way.
- The gate-determinism probes (omnius) become the reference conformance mechanism other loops
  should mirror.

**Costs / risks:**
- Routing multiqlti class ≥ A exclusively through the Consilium loop narrows what the fast base
  pipeline may autonomously land — intended, but needs a migration note and the R0 escape hatch
  (base pipeline stays fully autonomous for R0/text-only work).
- D6 (compensators) is real new engineering for multiqlti, not a config change.
- Two loops asserting D3 differently (proofs vs convergence) must both be expressible as
  "deterministic derivation over structured signals" — the conformance fixtures must test the
  *rule*, not the mechanism.

## Alternatives considered

1. **Fold the decision model into ADR-0003** — rejected: I1–I8 are lifecycle *states*; D1–D7 are
   branch *rules*. Mixing them hides that a task can be in the right state via the wrong decision.
2. **Standardize the loop engine (one harness/action-space)** — rejected (matches the component-map
   ruling): the tiers optimize different things; the owner wants a light base pipeline for R0.
   This ADR standardizes the *rules*, explicitly not the engine, tools, prompts, or models.
3. **Wire multiqlti's base-pipeline guardrails and call it done** — insufficient alone: guardrails
   are a validator hook, not the independent-verifier + fail-closed-landing + disposition model
   D3/D4/D5 require. The Consilium loop already implements those; adoption should build on it.

## Appendix A — multiqlti conformance mapping

> Two paths. **Base `PipelineController`** = the autonomous default. **Consilium/SDLC FSM** = the
> strict path. Class ≥ A must decide on the strict path (or the base pipeline gains the missing
> gates). Anchors are `project/multiqlti/`.

| Rule | Base pipeline (default) | Consilium/SDLC loop (conformant path) | Gap to close |
|---|---|---|---|
| D1 admission | sandbox/workspace/deploy classified only opt-in; no before-execute class check | class carried by the SDLC run | **new**: action classifier + auto-escalation (I1) |
| D2 control-flow | ✅ `dag-executor` topological + `dag-condition-evaluator` (safe ops, never `eval()`) | ✅ FSM `decide()` | none — already deterministic both paths |
| D3 verification | ✗ no quality gate; `guardrail-runner` **unwired** (zero callers); consensus opt-in/default-off | ✅ convergence (zero-open-P0) + per-AP refute-by-default judge + weak-criterion lint | route class ≥ A to Consilium **or** wire blocking guardrails |
| D4 landing | ✗ run `completed` on process completion; no landing gate | ✅ `awaiting_merge → merge_approved` (human) + Draft-PR | route class ≥ A to Consilium |
| D5 disposition | opt-in `approvalRequired` (**default-off**) only | human `merge_approved` gate | **new**: explicit disposition table (seed `ACTION_TIER_TABLE`) |
| D6 stop/rollback | stage-fail ⇒ run-fail (deterministic); **no rollback/compensator**, no idempotency | — | **new**: compensator + idempotency for class ≥ B |
| D7 outcome/escape | telemetry only | — | **new**: OutcomeEvent + escape join (I8, multiqlti#445) |

## Appendix B — omnius conformance mapping

> Single path, already conformant. Anchors are `project/omnius/`.

| Rule | Mechanism (deterministic, fail-closed) | Anchor |
|---|---|---|
| D1 admission | `CedarPDP.classify` (default class E), `AutonomyMatrix.evaluate_action`, `tx_ledger.check_forbidden_actions`; prod-from-merged-main guard | `pool/__init__.py:22-51`, `conductor/__init__.py:249-258,274-295` |
| D2 control-flow | conductor FSM transitions C1–C13; verdict branch reads `verdict.result`, not LLM text | `conductor/__init__.py:219-527` |
| D3 verification | `VerificationCore.verify` (family-mismatch, canaries, secrets/migration scan, independence weights) — no LLM import; enforced by `probe_cc5`/`probe_bm3` | `verifier/__init__.py:42-183`, `conformance/probes.py:156,312` |
| D4 landing | `can_auto_merge` — 7 conditions, each `!= expected` / `is not True` ⇒ `None` fails closed → PARKED_AWAITING_HUMAN | `conformance/can_auto_merge.py:76-101`, `conductor/__init__.py:478-495` |
| D5 disposition | `AutonomyMatrix` 17 rows, unknown → HUMAN row_id −1; `L5CompositionProbe`; toggle `policy_set_by=="human"` | `phase_3/human_boundary.py:77-130`, `can_auto_merge.py:82-97` |
| D6 stop/rollback | breakers (timeout / retry>3 / crash); saga reconciler commit-or-compensate; IntentClaim DB-UNIQUE dedup; never reclaim FROZEN | `conductor/__init__.py:305-330,374-381`, `phase_2/tx_ledger.py:225-271` |
| D7 outcome/escape | escape rate from the incident plane, independent of the evaluator (FactoryObservability) | `phase_2/observability.py` |

## Follow-ups

- [ ] Accept this ADR (Proposed → Accepted) — platform owner.
- [ ] multiqlti issue(s): route class ≥ A through the Consilium/SDLC loop (or wire blocking
      guardrails into the base pipeline); D1 action classifier; D5 disposition table; D6
      compensator/idempotency for class ≥ B. (D7 already in multiqlti#445.)
- [ ] omnius: no behavioral change; confirm `probe_cc5`/`probe_bm3` stay Required; emit platform
      OutcomeEvent (D7 / ADR-0003 I6).
- [ ] genai-enablement: publish conformance fixtures that test the D1–D7 **rules** (mechanism-
      agnostic) alongside the OutcomeEvent schema (ADR-0003 follow-up).
- [ ] Extend the sre-harness `ACTION_TIER_TABLE` with factory action kinds (D1 seed).
- [ ] Add a "loop decision model" row to the glossary Part 2 after acceptance.

## References

- Reconnaissance inputs — omnius: `mvp_core/conductor/__init__.py`, `mvp_core/verifier/__init__.py`,
  `mvp_core/pool/__init__.py`, `conformance/can_auto_merge.py`, `conformance/probes.py`,
  `phase_3/human_boundary.py`, `phase_2/{tx_ledger,observability}.py`.
- Reconnaissance inputs — multiqlti: `server/pipeline/{dag-executor,dag-condition-evaluator,
  guardrail-runner}.ts`, `server/controller/pipeline-controller.ts`,
  `services/strategy-executor.ts`, `services/orchestrator/convergence.ts`,
  `services/consilium/consilium-loop-controller.ts`, `services/sdlc/executor.ts`,
  `pipeline/{plan-evaluator-gate,evaluator-worker,meta-loop}.ts`.
- [ADR-0003](0003-unified-sdlc-standard.md) — task-lifecycle invariants I1–I8.
- [ADR-0002](0002-platform-skills-registry.md) — skills registry.
- [platform-glossary.md](../platform-glossary.md) — autonomy tiers, task classes, gate vs guardrail.
