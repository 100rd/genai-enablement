# SPEC-B7-CIR — Change-induced-regression Sentinel detector

**Specification type:** Capability SPEC
**Status:** Draft / portable construction
**Owner:** `genai-enablement` Autonomous SRE harness
**Governing decisions:** [ADR-0001](../decisions/0001-continuous-detection-sentinel.md),
[ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md), and the
[Autonomous SRE harness plan](../autonomous-sre-harness-plan.md)
**Roadmap gate:** `B7`
**Depends on:** SPEC-B0 offline evaluation harness, SPEC-B7 error-rate candidate rule, SPEC-B7-CORE
Sentinel portable core
**Evidence scope:** `local-portable-only`
**Operational state:** `incomplete`
**Next gate:** `human-policy-source-and-live-calibration`
**Authority:** `non-authorizing`; correlation detection T1 and finding T2, with no causal or action authority

## Goal and boundary

Add the ADR-0001 `change-induced-regression` family only with exact deploy/window correlation, positive
lead-time evidence, detector-specific clean worlds, and a no-duplicate rule against the generic
`error_rate_vs_baseline` finding. The portable detector associates a qualifying pre/post aggregate
error-rate regression with one recent immutable deployment. It reports correlation, never causation.

This slice owns one immutable fixture signal, a deterministic detector, strict JSON ingestion, registry
admission, within-scan specificity collapse, and replay labels. It does not own deploy-event or metric
queries, window materialization, source completeness, production thresholds, alert delivery, scheduling,
rollback, remediation, or deployment.

## User journey

**As the on-call owner**, I want Sentinel to associate a new SLO regression with the latest deployment
while suppressing the less-specific duplicate error-rate advisory, so I receive earlier actionable context
without a second alert or an unsupported claim that the change caused the regression.

## Candidate rule

For one service and exact deployed revision:

```text
baseline_rate = baseline_errors / baseline_requests
current_rate  = current_errors  / current_requests
candidate_threshold = max(
  baseline_rate * 3,
  baseline_rate + 0.01,
  allowed_error_rate * 2,
)
```

Both windows require at least 100 requests. The signal is attributable only when its pre-deploy baseline
ends no later than the deploy, its post-deploy window begins no earlier than the deploy and ends after it,
the observation is within 3,600 seconds of the deploy, and no intervening deployment is present. A
critical finding additionally requires the existing stricter maximum of baseline ×5, baseline +0.05,
and allowed error rate ×10. These are fixture candidates inherited from SPEC-B7, not accepted production
policy.

## Requirements

[REQ-B7C-1] **The signal is exact, immutable, bounded, and internally consistent.**
`ChangeRegressionWindow` binds bounded non-blank service text, distinct canonical lowercase SHA-256
previous/deployed revisions, exact non-negative bounded UTC epoch seconds, an exact bounded intervening
deployment count, exact aggregate pre/post error/request counts, and one exact finite
`0 < allowed_error_rate < 1`. Booleans, coercion, malformed revisions, invalid time order, inconsistent
counts, NaN/Inf, blank/oversized service, and mutation fail before detector execution. — **Fallback:**
reject invalid state; emit nothing.

[REQ-B7C-2] **JSON ingestion is typed, closed, and bounded.** `change_regression_windows` accepts at most
1,000 rows through exact field extraction, never `**kwargs` coercion. It inherits the shared regular
non-symlink, non-blocking, stable-read, strict UTF-8 JSON-object boundary of at most 1 MiB, including
duplicate-key and non-finite-number rejection. Missing, null, extra, wrong-type, over-limit, and malformed
rows reject the complete snapshot before a scan. — **Fallback:** no partial state or finding.

[REQ-B7C-3] **Attribution requires one recent unambiguous deployment.** A signal qualifies only when
`baseline_ended_at <= deployed_at <= current_started_at < observed_at`, deploy age is at most 3,600
seconds, and `intervening_deployments == 0`. An older observation or any later deployment stays silent;
the detector does not guess which change is associated. — **Fallback:** retain the generic detector only.

[REQ-B7C-4] **The regression rule requires statistical sufficiency and the complete baseline/SLO
threshold.** Both request counts must be at least 100 and current rate must meet the maximum of the
relative multiplier, absolute delta, and SLO-budget multiplier. Stable-high baselines, low-volume spikes,
small deltas, and rates inside the declared budget stay silent. — **Fallback:** no change-associated
finding.

[REQ-B7C-5] **Output is deterministic, bounded, non-sensitive, and epistemically honest.** One qualifying
window emits one `change_induced_regression` finding with detector id `change_induced_regression`,
HIGH/CRITICAL severity, fixed candidate confidence, a `service:deployed_revision` fingerprint, bounded
aggregate/time/revision/rate evidence, and `triage-change-induced-regression` suggestion. Rationale uses
“associated with” and never “caused by”. It excludes raw requests/logs/errors, user identities, URLs,
credentials, model text, diffs, and change descriptions. Input order controls output order. —
**Fallback:** invalid input cannot construct a finding.

[REQ-B7C-6] **The more-specific change finding replaces its generic duplicate in one scan.** If the
default registry emits both `change_induced_regression` and `error_rate_regression` for the same exact
service, the scan retains only the change-associated finding before open-finding dedup/ranking. It must
not suppress an unrelated service, a generic finding when the change detector is silent, or a different
finding kind. Existing `suppressed` semantics remain reserved for already-open dedup keys. — **Fallback:**
prefer one honest specific advisory, not two alerts.

[REQ-B7C-7] **The detector remains T1/T2 and action-free.** It is a pure registered function with no
network, filesystem, clock read, model, acknowledgement, send, runbook execution, rollback, remediation,
issue, pipeline, merge, or close surface. Revisions and epoch values are supplied state facts, not fetched
or inferred by the detector. — **Fallback:** downstream humans and deterministic gates decide separately.

[REQ-B7C-8] **Registry admission requires positive replay lead-time.** A fixture timeline binds one deploy
and fixed pre-deploy baseline/SLO, increases only the post-deploy aggregate rate, first crosses the full
candidate threshold at least one snapshot before the labelled page, and expects the exact detector/kind.
The eval records first fire and positive lead. — **Fallback:** late/missing detection fails the suite.

[REQ-B7C-9] **False-positive evidence covers attribution and regression ambiguity.** The fixture corpus
contains at least five detector-specific clean timelines: stable-high baseline, low-volume spike,
inside-SLO rate, expired association window, and intervening deployment. All remain silent; the aggregate
eval reports explicit clean count and zero false positives/rate. — **Fallback:** any clean fire blocks
registry admission.

[REQ-B7C-10] **Portable correlation is not production attribution evidence.** Live exit additionally
requires a human-owned versioned deploy-event/window/SLO contract, exact source completeness and ordering,
immutable revision-to-workload binding, clock-skew/freshness policy, real incident/clean calibration,
observed lead-time and false-positive confidence intervals, overlap/dedup retention, cost/noise budgets,
read-only source identity, and a disable owner. — **Fallback:** label all constants and results fixture-only;
make no causation, deployment, or operational-usefulness claim.

## Portable interfaces

```text
ChangeRegressionWindow(service, previous_revision, deployed_revision,
                       baseline_ended_at, deployed_at, current_started_at,
                       observed_at, intervening_deployments,
                       baseline_errors, baseline_requests,
                       current_errors, current_requests, allowed_error_rate)
detect_change_induced_regression(state) -> list[Finding]
state_from_dict({"change_regression_windows": [...]}) -> SentinelState
run_sentinel(state) -> SentinelReport  # specific-over-generic collapse
```

## Verification matrix

- **P-B7C-1 exact-signal:** valid frozen signal derives rates/age; coercion, malformed/equal revisions,
  epoch/count/rate bounds, time-order, inconsistent count, service, and mutation cases fail.
- **P-B7C-2 input-boundary:** typed row round trip; missing/null/extra/wrong-type/over-1,000 rows and the
  inherited shared file attacks reject the whole state.
- **P-B7C-3 attribution:** exact 3,600-second boundary qualifies; 3,601 seconds and any intervening deploy
  stay silent.
- **P-B7C-4 rule:** exact sample/threshold boundaries fire; insufficient samples, stable-high, small
  delta, and inside-budget cases stay silent.
- **P-B7C-5 finding:** severity, confidence, fingerprint, bounded evidence, honest wording, ordering, and
  absence of sensitive/raw fields are exact.
- **P-B7C-6 specificity:** same-service generic duplicate drops; unrelated/generic-only findings remain;
  open-specific state cannot resurrect a fresh generic duplicate.
- **P-B7C-7 authority:** registry includes the pure detector; source contains no action capability.
- **P-B7C-8 lead-time:** labelled change regression first fires before page with expected detector/kind.
- **P-B7C-9 false-positive:** five named clean controls stay silent and aggregate false-positive rate is
  exactly zero.
- **P-B7C-10 evidence-scope:** docs/status distinguish portable association from live source/calibration/
  runtime evidence and never claim causation.

The closed local `solutions/sre-harness/spec-traceability/SPEC-B7-CIR.json` manifest binds this exact
Draft digest and P-B7C-1..10 to existing pytest nodes and the bounded Sentinel implementation paths. It
is static `local-portable-only`, operationally `incomplete`, and `non-authorizing`; it stores no PASS
result and grants no deploy-source, causal-attribution, runtime, delivery, or remediation authority.

## Exit evidence

The portable increment is conformant only when P-B7C-1..10 pass with at least 80% branch coverage for
the affected Sentinel surface and the complete harness remains green. Live operation remains incomplete
until REQ-B7C-10 is satisfied. Fixture inputs cannot prove deploy-source completeness, publish thresholds,
establish causality, schedule runtime, deliver alerts, or authorize actions.
