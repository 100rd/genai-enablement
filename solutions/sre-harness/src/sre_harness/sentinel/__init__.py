"""Sentinel — continuous / periodic preventive detection (Stage 7).

The harness's proactive surface: long-running or periodic detectors evaluate
platform *state* for emerging risk and *new problem classes*, deterministic-first,
and emit confidence-scored, deduped, ranked **findings** into the advisory loop.
Detection is read-only (T1); a finding is advisory (T2) — Sentinel never executes
remediation. See ``docs/decisions/0001-continuous-detection-sentinel.md``.

Build-order step 1 plus the SPEC-B7 increment: detector contract + registry +
dedup + ranking + five deterministic detectors, scored offline by the eval
harness on **lead-time** and explicit false-positive rate. No LLM, no live
sources — pure rules over a state snapshot, unit-/eval-testable exactly like the
change-validation gate.
"""

from sre_harness.sentinel.detectors import (
    DEFAULT_DETECTORS,
    detect_change_induced_regression,
    detect_config_state_drift,
    detect_error_rate_vs_baseline,
    detect_new_error_signature,
    detect_saturation_expiry,
)
from sre_harness.sentinel.finding import Detector, Finding, Severity
from sre_harness.sentinel.scan import SentinelReport, run_sentinel
from sre_harness.sentinel.state import (
    ChangeRegressionWindow,
    DriftObservation,
    ErrorRateWindow,
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)

__all__ = [
    "ChangeRegressionWindow",
    "DEFAULT_DETECTORS",
    "Detector",
    "DriftObservation",
    "ErrorRateWindow",
    "ErrorSignatureWindow",
    "ExpiryItem",
    "Finding",
    "SaturationSample",
    "SentinelReport",
    "SentinelState",
    "Severity",
    "detect_error_rate_vs_baseline",
    "detect_change_induced_regression",
    "detect_config_state_drift",
    "detect_new_error_signature",
    "detect_saturation_expiry",
    "run_sentinel",
]
