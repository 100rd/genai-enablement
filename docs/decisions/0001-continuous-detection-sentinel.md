# ADR 0001: Continuous Detection / Sentinel

**Status**: Accepted — 2026-06-23
**Context doc**: [`docs/autonomous-sre-harness-plan.md`](../autonomous-sre-harness-plan.md)

## Context

The harness today is **reactive + at-change**:
- **Pre-triage** (Stage 1): investigate *after* an alert fires.
- **Change-validation gate** (Stage 2, shipped): validate a deploy/config change *at the moment of change* (PR / sync) — e.g. required-StorageClass-present, blast-radius/action-tier, namespace-presence.

The missing capability is **continuous, proactive detection**: catch emerging problems *before* they page, and — per the target operating model — **catch a *class* of incident before it recurs**. The naive version ("continuously grep logs for ERROR/CRITICAL") is an anti-pattern: critical logs always exist, volume ≠ problem, and a 24/7 LLM scan burns budget and produces noise while duplicating existing alerting.

## Decision

Adopt **Continuous Detection / Sentinel** as a new harness stage: a long-running (or periodic) surface that evaluates platform state for **emerging risk and new problem classes**, deterministic-first, and emits confidence-scored **findings** into the existing advisory loop.

### The two preventive surfaces (taxonomy)

Both are "preventive"; they differ in *when* they run.

| Surface | When | Trigger | Examples |
|---|---|---|---|
| **Change-validation gate** (Stage 2) | point-in-time | a PR / deploy / sync | required-StorageClass present; **secret/ExternalSecret declared**; **deployment-strategy fits workload role** (canary on a queue-worker → not recommended); blast-radius/action-tier; namespace presence |
| **Sentinel** (this ADR) | continuous / periodic | the running system | error-rate-vs-baseline anomaly; **new** error signature; change-induced regression (good-deploy vs bad-deploy); config↔state drift; saturation / quota / cert-expiry trends |

> The canary-on-a-worker and missing-secret examples are **gate** checks (they fire "immediately" at the change), not Sentinel. They are listed here only to draw the boundary; their implementation extends the Stage-2 multi-check gate.

### Principles (non-negotiable)
- **Anomaly / new-class / risk, not raw volume.** Detect relative to a baseline, SLO burn-rate, and *novel* signatures — never "there are errors."
- **Deterministic-first.** Detectors are rules over platform state (the strongest verification tier). A **cheap model** (Haiku) only clusters/names *novel* patterns; an **expensive model** (Sonnet/Opus) only drafts the final finding.
- **Read-only detection.** Detection is **Tier 1**; emitting a finding/recommendation is **Tier 2 (advisory)**. Sentinel never executes remediation — it feeds the gate → runbook → permanent-fix loop.
- **Dedup + budget.** Never re-alert a known/open finding; hard budget limits on any model use (silent token burn is the failure mode).
- **Augments, not replaces, existing alerting.** Sentinel surfaces what fixed thresholds miss (trends, new classes, cross-signal correlation) — it is not a second copy of Datadog monitors.
- **Generalize the loop.** Every one-off problem found by hand becomes a new detector ("catch the class before it recurs") — this is the leverage scoreboard.

### Detector contract (mirrors the gate-check shape)

```
Detector(state) -> Finding{
    detector_id, kind, severity, confidence, evidence, suggested_runbook?
}
```

A registry of detectors runs against a state snapshot; findings are deduped against open findings, ranked by severity × confidence, and emitted as advisory (T2).

### Initial detector catalog
1. **error-rate-vs-baseline** — burn-rate / anomaly vs rolling baseline (not a fixed threshold).
2. **new-error-signature** — a stack/signature not seen in the baseline window.
3. **change-induced-regression** — correlate a metric/SLO regression with the most recent deploy (good-vs-bad-deploy diff).
4. **drift** — config↔state divergence on a tracked resource (consumes Omniscience drift).
5. **saturation / expiry** — quota/disk/connection-pool trend toward exhaustion; expiring certs/tokens.

### Measurement
Sentinel detectors are scored by the **eval harness** (Stage 0) on **lead-time**: replay past incidents and verify a detector would have surfaced the problem *earlier*, with low false-positive rate on the "messy worlds."

## Consequences

- **Runtime is deferred.** Truly-continuous operation needs a runtime (EKS: a `monitor` Deployment or a `CronJob`), live observability sources (Datadog/Loki/CloudWatch), and the populated platform graph (Omniscience). The **detector logic is buildable and unit-/eval-testable offline now** (against the `PlatformGraph` port + fakes), exactly like the gate; the runtime wiring + live sources land when the cluster/Omniscience are ready.
- **Graph facts are an Omniscience dependency.** Several detectors (and the gate's secret/strategy checks) need facts the graph must carry — workload role (HTTP-service vs queue-worker vs cron), secret/ESO inventory (names/keys, never values), queue-consumption edges, deploy events. Some exist; others are new Omniscience connector/operator work.
- **Cost & noise are the primary risks**, mitigated by deterministic-first, budget limits, dedup, baselines-not-thresholds, and signal-over-volume.
- **Governance (SR 11-7)**: detection is read-only (T1) → low risk; only the human-acted recommendations (T2) and any downstream remediation carry model-risk obligations.

## Build order (within this stage)
1. Detector contract + registry + dedup + a couple of **deterministic detectors**, scored by the eval harness on lead-time (offline).
2. Runtime: `monitor`/`CronJob` wiring + observability source adapters (needs cluster).
3. Cheap-model novelty clustering for `new-error-signature`; expensive-model finding draft.

## Implementation map

| Decision surface | Capability SPEC | Current evidence boundary |
|---|---|---|
| Common finding/state/source/scan/store/CLI contract | [`SPEC-B7-CORE`](../specs/SPEC-B7-core-sentinel-runtime-contract.md) | Portable local construction only |
| `error-rate-vs-baseline` | [`SPEC-B7`](../specs/SPEC-B7-error-rate-baseline-detector.md) | Portable candidate rule and fixtures |
| `new-error-signature` deterministic core | [`SPEC-B7-NES`](../specs/SPEC-B7-new-error-signature-detector.md) | Normalized identities only; model clustering deferred |
| `change-induced-regression` | [`SPEC-B7-CIR`](../specs/SPEC-B7-change-induced-regression-detector.md) | Portable correlation only, never causation |
| `drift` | [`SPEC-B7-DRIFT`](../specs/SPEC-B7-drift-detector.md) | Normalized digest observation only; no reconciliation |
| `saturation / expiry` | [`SPEC-B7-SAT`](../specs/SPEC-B7-saturation-expiry-detector.md) | Candidate thresholds and fixture timelines only |

The map closes source-SPEC coverage for the accepted detector catalog. It does not realize the live
runtime, source, delivery, calibration, model, or operational evidence gates.

## See also
- Plan: [`docs/autonomous-sre-harness-plan.md`](../autonomous-sre-harness-plan.md)
- Eval harness (Stage 0): `solutions/sre-harness/src/sre_harness/eval/`
- Change-validation gate (Stage 2): `solutions/sre-harness/src/sre_harness/change_gate.py`, `change_checks.py`
</content>
