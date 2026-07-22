# SPEC-B0 — Offline evaluation harness

**Specification type:** Capability SPEC
**Status:** Draft / portable construction
**Owner:** `genai-enablement` Autonomous SRE harness
**Governing decisions:** [ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md) and the
[Autonomous SRE harness plan](../autonomous-sre-harness-plan.md)
**Roadmap gate:** `B0`
**Depends on:** —
**Evidence scope:** `local-portable-only`
**Operational state:** `incomplete`
**Next gate:** `human-corpus-and-regression-policy-publication`
**Authority:** `non-authorizing`; offline measurement only, with no runtime or mutation authority

## Goal and boundary

Provide one deterministic, offline measurement seam before any SRE capability is trusted. The portable
baseline owns immutable replay labels, an explicit target/scorer boundary, honest implemented metrics,
aggregate reporting, seed fixtures, and AgentOps spans. It does not own incident-label truth, production
thresholds, model approval, a live provider, deployment, or an operational acceptance decision.

**As a harness maintainer**, I need the same frozen scenario to replay through a selected target and an
explicit scorer so that a regression is visible without letting the target choose its own ground truth or
fabricate an unsupported metric.

## Requirements

[REQ-B0-1] **A replay label is immutable and explicit.** `Scenario` carries a stable non-blank id, a
declared kind, one snapshot, and external ground truth. `GateSnapshot` binds the exact change request and
read-only platform graph used by the seed target. Neither contract contains approval, mutation, provider
credentials, or a production-evidence flag. — **Fallback:** malformed labels do not enter a suite.

[REQ-B0-2] **Target execution and scoring remain separate.** `run_eval` invokes a supplied target and
passes the resulting value plus the scenario's expected value to either the explicit scorer or the
default deterministic change-gate scorer. The target cannot replace the expected result, scorer, or
scenario identity. — **Fallback:** incompatible ground-truth types fail rather than being coerced.

[REQ-B0-3] **Pass@1 is exact and bounded.** The implemented verdict scorer returns `1.0/pass` only for
identity-equal expected and actual deterministic verdicts and `0.0/fail` otherwise. Every `Score` is
immutable and its numeric value is restricted to `[0, 1]`. — **Fallback:** invalid score construction
fails closed.

[REQ-B0-4] **Suite aggregation is deterministic and preserves failures.** A non-empty suite yields one
result per input scenario in input order, total/passed/pass-rate values, and per-kind pass rates. A failed
target result is retained as a failed result rather than swallowed or rewritten. — **Fallback:** an empty
suite is invalid, not a vacuous pass.

[REQ-B0-5] **The seed suite covers the complete current gate verdict space.** Stable unique fixtures cover
`proceed`, `block`, and `require_human` across StorageClass, namespace, and blast-radius checks, including
dominance combinations. These labels are deterministic code fixtures, not independently curated incident
truth. — **Fallback:** missing coverage leaves the baseline incomplete.

[REQ-B0-6] **AgentOps records measurement without changing it.** One `eval.suite` span parents one
`eval.scenario` span per replay and records scenario id/kind, score, suite count, passed count, and pass
rate. Tracing is no-op by default and cannot change target or scorer behavior. — **Fallback:** an
unconfigured exporter produces no fabricated telemetry.

[REQ-B0-7] **Unsupported metrics are explicit fail-closed extension points.** `Pass@k`, trajectory,
depth, and signal-surfacing kinds are declared but raise `NotImplementedError` until their required
stochastic samples, trajectories, and external labels exist. Lead-time is implemented separately for
Sentinel timelines. No placeholder score may be reported as evidence. — **Fallback:** callers receive an
explicit unsupported result.

[REQ-B0-8] **Portable fixture conformance is not operational evaluation evidence.** A B0 operational exit
requires a human-owned representative corpus, immutable labels and provenance, externally published
regression/stop thresholds, selected metric applicability, retention, and observed evaluation runs bound
to an immutable harness revision. Local seed results cannot approve a model, source, rollout, remediation,
or pilot. — **Fallback:** B0 remains operationally incomplete.

## Portable interfaces

```text
Scenario{id, kind, snapshot, ground_truth}
run_eval(Scenario[], Target, Scorer?) -> EvalSummary
pass_at_1(expected, actual) -> Score
lead_time(paged_at_index, first_fire_index, horizon) -> Score
python -m sre_harness.eval [--verbose]
```

## Verification matrix

- **P-B0-1 label-contract:** scenarios and gate snapshots retain exact fields, reject blank ids, and are
  immutable.
- **P-B0-2 target-scorer-separation:** the target receives the exact scenario, the explicit scorer owns
  interpretation, and incompatible default ground truth does not become a fabricated pass.
- **P-B0-3 exact-pass-at-1:** correct/wrong verdicts produce exact one/zero scores; scores are immutable
  and reject values outside the unit interval.
- **P-B0-4 aggregation:** complete and failing targets remain visible in exact totals, pass rates,
  per-kind breakdowns, and result rows; an empty suite fails.
- **P-B0-5 seed-coverage:** seed ids are unique and cover all three verdicts plus namespace and
  blast-radius cases.
- **P-B0-6 tracing:** suite/scenario spans retain count, identity, kind, and score while no-op tracing
  preserves behavior.
- **P-B0-7 unsupported-metrics:** each declared but unimplemented scorer raises instead of returning a
  placeholder value.
- **P-B0-8 evidence-boundary:** the SPEC, portfolio status, and harness docs retain the local-only,
  non-authorizing, operationally incomplete boundary.

## Exit evidence

The closed local
[`SPEC-B0` portable traceability manifest](../../solutions/sre-harness/spec-traceability/SPEC-B0.json)
binds this exact Draft digest and all eight probes to existing pytest nodes and the bounded eval and
observability implementation paths. It is a static index, not a cached PASS or a corpus publication.

B0 remains operationally incomplete until REQ-B0-8 evidence exists. The portable baseline is usable by
other construction SPECs, but its fixtures cannot become human acceptance or production authority.
