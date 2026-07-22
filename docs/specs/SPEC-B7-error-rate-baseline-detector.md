# SPEC-B7 — Error-rate-vs-baseline Sentinel detector

**Specification type:** Capability SPEC
**Status:** Draft / portable construction
**Owner:** `genai-enablement` Autonomous SRE harness
**Governing decisions:** [ADR-0001](../decisions/0001-continuous-detection-sentinel.md),
[ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md), and the
[Autonomous SRE harness plan](../autonomous-sre-harness-plan.md)
**Roadmap gate:** `B7`
**Depends on:** SPEC-B0 offline evaluation harness, SPEC-B7-CORE Sentinel portable core
**Evidence scope:** `local-portable-only`
**Operational state:** `incomplete`
**Next gate:** `human-policy-source-and-live-calibration`
**Authority:** `non-authorizing`; detection T1 and finding T2 advisory, with no remediation authority

## Goal and boundary

Add ADR-0001 catalog detector `error-rate-vs-baseline` only together with replay evidence that it surfaces
an incident before the page and stays silent on deliberately messy clean worlds. The detector compares a
current aggregate error window with both its rolling baseline and the service's declared SLO error budget;
it never fires merely because errors exist or because an absolute global threshold was crossed.

This slice owns one immutable state signal, deterministic rule, JSON ingestion, default-registry entry,
explicit lead-time/false-positive summary metrics, and fixture replay labels. It does not own live
Datadog/Loki/CloudWatch queries, window materialization, baseline/SLO publication, detector scheduling,
model clustering, alert delivery, remediation, or production threshold acceptance.

## User journey

**As the on-call owner**, I want Sentinel to surface a statistically supported error-rate regression before
the existing page while ignoring stable noisy services and low-volume spikes, so continuous detection adds
lead-time instead of becoming a duplicate threshold-alert stream.

## Candidate rule

For one exact service window:

```text
baseline_rate = baseline_errors / baseline_requests
current_rate  = current_errors  / current_requests
candidate_threshold = max(
  baseline_rate * 3,
  baseline_rate + 0.01,
  allowed_error_rate * 2,
)
```

The candidate detector may fire only when both baseline and current windows contain at least 100 requests
and `current_rate >= candidate_threshold`. A critical finding additionally requires
`current_rate >= max(baseline_rate * 5, baseline_rate + 0.05, allowed_error_rate * 10)`; otherwise it is
high severity. These constants are construction candidates protected by fixture eval, not accepted live
production policy.

## Requirements

[REQ-B7-1] **The signal is exact, immutable, finite, and internally consistent.** `ErrorRateWindow` binds a
bounded non-blank service, exact non-negative integer baseline/current error and request counts, and one
finite `0 < allowed_error_rate < 1`. Booleans, float/string counts, negative/oversized counts, errors above
requests, NaN/Inf, blank/oversized service, and mutable records fail before detector execution. Empty or
sub-minimum request windows are valid incomplete evidence and must stay silent. — **Fallback:** no finding.

[REQ-B7-2] **JSON ingestion is fail-closed at the shared state boundary.** `error_rate_windows` is limited
to 1,000 rows and parsed through typed extraction, never `**kwargs` coercion. The file reader accepts only
a regular non-symlink UTF-8 JSON object up to 1 MiB, opens without special-file blocking, and rejects
duplicate keys, non-finite numbers, malformed JSON,
oversize input, and non-object roots. It does not log or persist raw input on error. — **Fallback:** reject
the snapshot; do not run a partial scan.

[REQ-B7-3] **Detection requires statistical sufficiency.** Both request counts must be at least 100. A
low-volume percentage spike, missing/zero window, or one sufficient and one insufficient window produces
no finding. The detector never guesses or divides by zero. — **Fallback:** remain silent and await the next
snapshot.

[REQ-B7-4] **Detection is relative to both baseline and SLO budget.** A finding requires the current rate to
meet the maximum of the relative multiplier, absolute delta, and SLO-budget multiplier. Stable high error
rates, a small relative increase, or a rate still inside the declared SLO budget stays silent even if it
would cross another service's threshold. — **Fallback:** no finding; no fixed global-rate alert.

[REQ-B7-5] **Output is deterministic, bounded, and non-sensitive.** One qualifying service window emits one
`error_rate_regression` finding with detector id `error_rate_vs_baseline`, exact service fingerprint,
candidate HIGH/CRITICAL severity, fixed confidence, rounded derived rates/threshold plus aggregate counts,
and `triage-error-rate-regression` runbook suggestion. Evidence excludes raw request/log/error bodies,
signatures, credentials, URLs, user ids, and model text. Input order deterministically controls output;
scan-level existing dedup/rank remains authoritative. — **Fallback:** invalid signal never constructs a
finding.

[REQ-B7-6] **The detector is T1/T2 only and has no action surface.** It is a pure function registered in
`DEFAULT_DETECTORS`; no state mutation, network, filesystem, acknowledgement, alert-send, model, token,
runbook execution, remediation, issue, pipeline, or merge method exists. Suggested runbook text remains
advisory. — **Fallback:** downstream human/gates decide separately.

[REQ-B7-7] **Lead-time is proven by a replay label before registry admission.** The fixture incident timeline
holds baseline and SLO budget constant, ramps current aggregate rate, first crosses the complete candidate
threshold at least one snapshot before the labelled page, and expects the exact detector/kind. The eval
runner records first fire and positive lead. — **Fallback:** a late/missing fire makes the suite fail and
the registry change ineligible.

[REQ-B7-8] **False-positive evidence is explicit, not inferred from pass rate.** `SentinelEvalSummary`
reports incident scenario count, early detections/rate, clean scenario count, false-positive count/rate,
and mean positive lead. The B7 fixture corpus contains at least three detector-specific clean timelines:
stable-high baseline, low-volume spike, and current rate inside the declared SLO-budget multiplier. All
must remain silent and the aggregate false-positive rate must be exactly zero. — **Fallback:** any clean
fire fails the suite and blocks registry admission.

[REQ-B7-9] **Portable replay is not production detector evidence.** B7 live exit additionally requires
human-owned versioned window/baseline/SLO definitions, minimum-volume and multiplier calibration from a
curated real incident/clean corpus, source freshness/coverage/liveness, read-only source identity,
dedup/delivery retention, observed lead-time and false-positive confidence intervals, cost/noise budgets,
and a rollback/disable owner. Runtime wiring remains separate. — **Fallback:** label the constants and
results fixture-only; make no live usefulness claim.

## Portable interfaces

```text
ErrorRateWindow(service, baseline_errors, baseline_requests,
                current_errors, current_requests, allowed_error_rate)
detect_error_rate_vs_baseline(state) -> list[Finding]
state_from_dict({"error_rate_windows": [...]}) -> SentinelState
run_sentinel_eval(scenarios, detectors) -> SentinelEvalSummary
```

## Verification matrix

- **P-B7-1 exact-signal:** valid counts/rate freeze; bool/float/string/negative/overflow/inconsistent,
  non-finite, blank/oversized, and post-construction mutation fail.
- **P-B7-2 input-boundary:** typed round trip; over-1,000/missing/null/wrong-type rows and
  duplicate/non-finite, symlink, oversize, malformed, non-object files reject without a partial state.
- **P-B7-3 sufficiency:** each zero/under-minimum combination stays silent; exact minimum qualifies.
- **P-B7-4 relative-rule:** stable-high, insufficient delta/multiplier, and inside-budget worlds stay
  silent; exact maximum threshold fires.
- **P-B7-5 finding:** HIGH/CRITICAL boundaries, fingerprint, rounded aggregate evidence, fixed confidence,
  runbook and absence of sensitive/raw fields are deterministic.
- **P-B7-6 authority:** default registry contains the pure detector; Sentinel remains T1/T2 and exposes no
  action method.
- **P-B7-7 lead-time:** the labelled regression first fires before page with the expected detector/kind.
- **P-B7-8 false-positive:** at least three B7 clean controls remain silent; summary explicitly reports
  zero false positives/rate and complete early detection.
- **P-B7-9 evidence-scope:** docs/status distinguish fixture replay from live source/calibration/runtime
  evidence.

## Portable traceability

The closed local manifest at `solutions/sre-harness/spec-traceability/SPEC-B7.json` binds this exact Draft
digest and P-B7-1..9 to existing AST-discovered pytest nodes and the bounded Sentinel implementation. It
is static `local-portable-only`, operationally `incomplete`, and `non-authorizing`; it stores no PASS
result, live source observation, accepted threshold, calibration result, runtime deployment, or delivery
authority.

## Exit evidence

The portable increment is conformant only when P-B7-1..9 pass with at least 80% branch coverage for the
affected Sentinel surface and the full harness remains green. B7 live operation remains incomplete until
REQ-B7-9 is satisfied; checked code fixtures cannot publish thresholds, bind sources, schedule a runtime,
or establish operational usefulness.
