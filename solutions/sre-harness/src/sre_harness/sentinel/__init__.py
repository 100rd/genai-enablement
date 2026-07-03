"""Sentinel — continuous / periodic preventive detection (Stage 7).

The harness's proactive surface: long-running or periodic detectors evaluate
platform *state* for emerging risk and *new problem classes*, deterministic-first,
and emit confidence-scored, deduped, ranked **findings** into the advisory loop.
Detection is read-only (T1); a finding is advisory (T2) — Sentinel never executes
remediation. See ``docs/decisions/0001-continuous-detection-sentinel.md``.

Build-order step 1 (this slice): the detector contract + registry + dedup +
ranking + two deterministic detectors, scored offline by the eval harness on
**lead-time**. No LLM, no live sources — pure rules over a state snapshot,
unit-/eval-testable exactly like the change-validation gate.
"""

from sre_harness.sentinel.detectors import (
    DEFAULT_DETECTORS,
    detect_new_error_signature,
    detect_saturation_expiry,
)
from sre_harness.sentinel.finding import Detector, Finding, Severity
from sre_harness.sentinel.scan import SentinelReport, run_sentinel
from sre_harness.sentinel.state import (
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)

__all__ = [
    "DEFAULT_DETECTORS",
    "Detector",
    "ErrorSignatureWindow",
    "ExpiryItem",
    "Finding",
    "SaturationSample",
    "SentinelReport",
    "SentinelState",
    "Severity",
    "detect_new_error_signature",
    "detect_saturation_expiry",
    "run_sentinel",
]
