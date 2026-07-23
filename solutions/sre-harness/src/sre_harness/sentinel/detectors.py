"""The deterministic Sentinel detectors (Stage 7 — build-order step 1).

Five pure ``(state) -> list[Finding]`` detectors, deterministic-first per the ADR
(no model in the loop). Each mirrors a gate check: small, pure, registered in
:data:`DEFAULT_DETECTORS`. Adding a detector means adding a callable to the
registry, nothing else.

- ``saturation_expiry`` — resources trending toward exhaustion (observed breach
  *or* projected exhaustion within a horizon) and credentials/certs expiring
  within a horizon. ADR catalog #5.
- ``new_error_signature`` — an error signature present in the current window but
  absent from the baseline window (a *novel* class, not raw volume). ADR
  catalog #2's deterministic core; naming/clustering is a future model step.
- ``error_rate_vs_baseline`` — a statistically sufficient aggregate current rate
  that exceeds both its rolling baseline and declared SLO error budget. ADR
  catalog #1; no raw request/error content enters the signal or finding.
- ``change_induced_regression`` — the same complete regression rule bound to one
  recent immutable deployment with no intervening change. ADR catalog #3;
  correlation is reported without claiming causation.
- ``config_state_drift`` — persistent normalized desired↔observed digest
  divergence after a convergence grace period. ADR catalog #4; no raw config or
  reconciliation surface enters the detector.

All emit **anomaly / new-class / risk relative to a baseline or a horizon** —
never "there are errors" or "utilisation is nonzero" — honouring the ADR's
signal-over-volume principle.
"""

from __future__ import annotations

from decimal import Decimal

from sre_harness.sentinel.finding import Detector, Finding, Severity
from sre_harness.sentinel.state import (
    ChangeRegressionWindow,
    DriftObservation,
    ErrorRateWindow,
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)

# --- saturation / expiry thresholds ----------------------------------------

#: Utilisation at/above this is an observed critical breach (exhaustion imminent).
SATURATION_CRITICAL: float = 0.90
#: Utilisation at/above this is worth surfacing as an early warning.
SATURATION_WARN: float = 0.75
#: Snapshots ahead over which a growth trend is projected toward capacity.
SATURATION_PROJECTION_HORIZON: int = 6
#: Confidence for an observed threshold breach — a direct measurement is certain.
_OBSERVED_CONFIDENCE: float = 1.0
#: Confidence for a *projected* (forecast) exhaustion — inherently less certain.
_PROJECTED_CONFIDENCE: float = 0.7

#: Days remaining at/below which an expiry is critical.
EXPIRY_CRITICAL_DAYS: int = 7
#: Days remaining at/below which an expiry is worth an early warning.
EXPIRY_WARN_DAYS: int = 30

_SATURATION_DETECTOR_ID = "saturation_expiry"
_NEW_SIGNATURE_DETECTOR_ID = "new_error_signature"
_ERROR_RATE_DETECTOR_ID = "error_rate_vs_baseline"
_CHANGE_REGRESSION_DETECTOR_ID = "change_induced_regression"
_DRIFT_DETECTOR_ID = "config_state_drift"

# --- error-rate-vs-baseline candidate thresholds ---------------------------

#: Both aggregate windows need this many requests before the rule may fire.
ERROR_RATE_MIN_REQUESTS: int = 100
#: Current rate must be at least this multiple of the rolling baseline.
ERROR_RATE_BASELINE_MULTIPLIER: float = 3.0
#: Current rate must also exceed baseline by this absolute fraction.
ERROR_RATE_ABSOLUTE_DELTA: float = 0.01
#: Current rate must exceed the service's declared SLO error budget by this factor.
ERROR_RATE_BUDGET_MULTIPLIER: float = 2.0
#: Critical severity uses a stricter relative baseline multiplier.
ERROR_RATE_CRITICAL_BASELINE_MULTIPLIER: float = 5.0
#: Critical severity uses a stricter absolute increase.
ERROR_RATE_CRITICAL_ABSOLUTE_DELTA: float = 0.05
#: Critical severity uses a stricter SLO budget multiplier.
ERROR_RATE_CRITICAL_BUDGET_MULTIPLIER: float = 10.0
_ERROR_RATE_CONFIDENCE: float = 0.9

#: A deploy correlation older than one hour is too ambiguous for this candidate.
CHANGE_ASSOCIATION_MAX_AGE_SECONDS: int = 3600
_CHANGE_REGRESSION_CONFIDENCE: float = 0.85

# --- config↔state drift candidate thresholds ------------------------------

#: Ignore normal reconciliation for this many seconds after mismatch starts.
DRIFT_GRACE_SECONDS: int = 300
#: Require more than one observation before treating divergence as persistent.
DRIFT_MIN_CONSECUTIVE_OBSERVATIONS: int = 2
#: A digest mismatch that persists this long is elevated from MEDIUM to HIGH.
DRIFT_HIGH_AGE_SECONDS: int = 3600
_DRIFT_CONFIDENCE: float = 0.95


def detect_saturation_expiry(state: SentinelState) -> list[Finding]:
    """Surface resources heading for exhaustion and near-expiry credentials."""
    findings: list[Finding] = []
    for sample in state.saturation_samples:
        finding = _saturation_finding(sample)
        if finding is not None:
            findings.append(finding)
    for item in state.expiry_items:
        finding = _expiry_finding(item)
        if finding is not None:
            findings.append(finding)
    return findings


def _saturation_finding(sample: SaturationSample) -> Finding | None:
    utilization = sample.utilization
    scope = f"{sample.cluster}/{sample.resource}" if sample.cluster else sample.resource

    if utilization >= SATURATION_CRITICAL:
        return _saturation_result(
            sample,
            scope=scope,
            severity=Severity.CRITICAL,
            confidence=_OBSERVED_CONFIDENCE,
            rationale=(
                f"{sample.kind} {scope!r} at {utilization:.0%} of capacity "
                f"(>= critical {SATURATION_CRITICAL:.0%})."
            ),
        )

    projected = sample.used + sample.growth_per_interval * SATURATION_PROJECTION_HORIZON
    if sample.growth_per_interval > 0 and projected >= sample.capacity:
        return _saturation_result(
            sample,
            scope=scope,
            severity=Severity.HIGH,
            confidence=_PROJECTED_CONFIDENCE,
            rationale=(
                f"{sample.kind} {scope!r} projected to reach capacity within "
                f"{SATURATION_PROJECTION_HORIZON} intervals at the current growth rate."
            ),
        )

    if utilization >= SATURATION_WARN:
        return _saturation_result(
            sample,
            scope=scope,
            severity=Severity.MEDIUM,
            confidence=_OBSERVED_CONFIDENCE,
            rationale=(
                f"{sample.kind} {scope!r} at {utilization:.0%} of capacity "
                f"(>= warn {SATURATION_WARN:.0%})."
            ),
        )

    return None


def _saturation_result(
    sample: SaturationSample,
    *,
    scope: str,
    severity: Severity,
    confidence: float,
    rationale: str,
) -> Finding:
    return Finding(
        detector_id=_SATURATION_DETECTOR_ID,
        kind="saturation",
        severity=severity,
        confidence=confidence,
        fingerprint=scope,
        rationale=rationale,
        evidence={
            "resource": sample.resource,
            "resource_kind": sample.kind,
            "cluster": sample.cluster,
            "utilization": round(sample.utilization, 4),
            "used": sample.used,
            "capacity": sample.capacity,
            "growth_per_interval": sample.growth_per_interval,
        },
        suggested_runbook=f"scale-or-provision-{sample.kind}",
    )


def _expiry_finding(item: ExpiryItem) -> Finding | None:
    if item.expires_in_days <= 0:
        severity = Severity.CRITICAL
        rationale = f"{item.kind} {item.name!r} has already expired."
    elif item.expires_in_days <= EXPIRY_CRITICAL_DAYS:
        severity = Severity.HIGH
        rationale = (
            f"{item.kind} {item.name!r} expires in {item.expires_in_days}d "
            f"(<= critical {EXPIRY_CRITICAL_DAYS}d)."
        )
    elif item.expires_in_days <= EXPIRY_WARN_DAYS:
        severity = Severity.MEDIUM
        rationale = (
            f"{item.kind} {item.name!r} expires in {item.expires_in_days}d "
            f"(<= warn {EXPIRY_WARN_DAYS}d)."
        )
    else:
        return None

    return Finding(
        detector_id=_SATURATION_DETECTOR_ID,
        kind="expiry",
        severity=severity,
        confidence=_OBSERVED_CONFIDENCE,
        fingerprint=f"{item.kind}:{item.name}",
        rationale=rationale,
        evidence={
            "name": item.name,
            "item_kind": item.kind,
            "expires_in_days": item.expires_in_days,
        },
        suggested_runbook=f"rotate-{item.kind}",
    )


def detect_new_error_signature(state: SentinelState) -> list[Finding]:
    """Surface error signatures present now but absent from the baseline window."""
    findings: list[Finding] = []
    for window in state.error_windows:
        findings.extend(_novel_signature_findings(window))
    return findings


def _novel_signature_findings(window: ErrorSignatureWindow) -> list[Finding]:
    novel = window.current - window.baseline
    return [
        Finding(
            detector_id=_NEW_SIGNATURE_DETECTOR_ID,
            kind="new_error_signature",
            severity=Severity.HIGH,
            confidence=_OBSERVED_CONFIDENCE,
            fingerprint=f"{window.service}:{signature}",
            rationale=(
                f"Novel error signature {signature!r} on service "
                f"{window.service!r} — absent from the baseline window."
            ),
            evidence={
                "service": window.service,
                "signature": signature,
                "baseline_size": len(window.baseline),
                "current_size": len(window.current),
            },
            suggested_runbook="triage-new-error-signature",
        )
        for signature in sorted(novel)
    ]


def detect_error_rate_vs_baseline(state: SentinelState) -> list[Finding]:
    """Surface statistically sufficient error-rate regressions.

    The rule is relative to both the exact rolling baseline and the service SLO
    budget. Aggregate counts only: it never inspects request/error bodies.
    """

    findings: list[Finding] = []
    for window in state.error_rate_windows:
        finding = _error_rate_finding(window)
        if finding is not None:
            findings.append(finding)
    return findings


def _error_rate_finding(window: ErrorRateWindow) -> Finding | None:
    if (
        window.baseline_requests < ERROR_RATE_MIN_REQUESTS
        or window.current_requests < ERROR_RATE_MIN_REQUESTS
    ):
        return None

    baseline_rate, current_rate, candidate_threshold, critical_threshold = _error_rate_thresholds(
        baseline_errors=window.baseline_errors,
        baseline_requests=window.baseline_requests,
        current_errors=window.current_errors,
        current_requests=window.current_requests,
        allowed_error_rate=window.allowed_error_rate,
    )
    if current_rate < candidate_threshold:
        return None

    severity = Severity.CRITICAL if current_rate >= critical_threshold else Severity.HIGH
    return Finding(
        detector_id=_ERROR_RATE_DETECTOR_ID,
        kind="error_rate_regression",
        severity=severity,
        confidence=_ERROR_RATE_CONFIDENCE,
        fingerprint=window.service,
        rationale=(
            f"Service {window.service!r} aggregate error rate {float(current_rate):.2%} "
            f"meets the baseline/SLO candidate threshold "
            f"{float(candidate_threshold):.2%}."
        ),
        evidence={
            "service": window.service,
            "baseline_errors": window.baseline_errors,
            "baseline_requests": window.baseline_requests,
            "current_errors": window.current_errors,
            "current_requests": window.current_requests,
            "baseline_rate": round(float(baseline_rate), 6),
            "current_rate": round(float(current_rate), 6),
            "candidate_threshold": round(float(candidate_threshold), 6),
            "allowed_error_rate": round(window.allowed_error_rate, 6),
        },
        suggested_runbook="triage-error-rate-regression",
    )


def detect_change_induced_regression(state: SentinelState) -> list[Finding]:
    """Associate a qualifying pre/post regression with one recent deployment."""

    findings: list[Finding] = []
    for window in state.change_regression_windows:
        finding = _change_regression_finding(window)
        if finding is not None:
            findings.append(finding)
    return findings


def _change_regression_finding(window: ChangeRegressionWindow) -> Finding | None:
    if (
        window.deploy_age_seconds > CHANGE_ASSOCIATION_MAX_AGE_SECONDS
        or window.intervening_deployments != 0
        or window.baseline_requests < ERROR_RATE_MIN_REQUESTS
        or window.current_requests < ERROR_RATE_MIN_REQUESTS
    ):
        return None

    baseline_rate, current_rate, candidate_threshold, critical_threshold = _error_rate_thresholds(
        baseline_errors=window.baseline_errors,
        baseline_requests=window.baseline_requests,
        current_errors=window.current_errors,
        current_requests=window.current_requests,
        allowed_error_rate=window.allowed_error_rate,
    )
    if current_rate < candidate_threshold:
        return None

    severity = Severity.CRITICAL if current_rate >= critical_threshold else Severity.HIGH
    return Finding(
        detector_id=_CHANGE_REGRESSION_DETECTOR_ID,
        kind="change_induced_regression",
        severity=severity,
        confidence=_CHANGE_REGRESSION_CONFIDENCE,
        fingerprint=f"{window.service}:{window.deployed_revision}",
        rationale=(
            f"Service {window.service!r} aggregate error-rate regression is associated with "
            f"recent deployment {window.deployed_revision!r}; correlation does not establish "
            "causation."
        ),
        evidence={
            "service": window.service,
            "previous_revision": window.previous_revision,
            "deployed_revision": window.deployed_revision,
            "baseline_ended_at": window.baseline_ended_at,
            "deployed_at": window.deployed_at,
            "current_started_at": window.current_started_at,
            "observed_at": window.observed_at,
            "deploy_age_seconds": window.deploy_age_seconds,
            "intervening_deployments": window.intervening_deployments,
            "baseline_errors": window.baseline_errors,
            "baseline_requests": window.baseline_requests,
            "current_errors": window.current_errors,
            "current_requests": window.current_requests,
            "baseline_rate": round(float(baseline_rate), 6),
            "current_rate": round(float(current_rate), 6),
            "candidate_threshold": round(float(candidate_threshold), 6),
            "allowed_error_rate": round(window.allowed_error_rate, 6),
        },
        suggested_runbook="triage-change-induced-regression",
    )


def _error_rate_thresholds(
    *,
    baseline_errors: int,
    baseline_requests: int,
    current_errors: int,
    current_requests: int,
    allowed_error_rate: float,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Return exact baseline/current rates and shared candidate/critical thresholds."""
    baseline_rate = Decimal(baseline_errors) / Decimal(baseline_requests)
    current_rate = Decimal(current_errors) / Decimal(current_requests)
    allowed_rate = Decimal(str(allowed_error_rate))
    candidate_threshold = max(
        baseline_rate * Decimal(str(ERROR_RATE_BASELINE_MULTIPLIER)),
        baseline_rate + Decimal(str(ERROR_RATE_ABSOLUTE_DELTA)),
        allowed_rate * Decimal(str(ERROR_RATE_BUDGET_MULTIPLIER)),
    )
    critical_threshold = max(
        baseline_rate * Decimal(str(ERROR_RATE_CRITICAL_BASELINE_MULTIPLIER)),
        baseline_rate + Decimal(str(ERROR_RATE_CRITICAL_ABSOLUTE_DELTA)),
        allowed_rate * Decimal(str(ERROR_RATE_CRITICAL_BUDGET_MULTIPLIER)),
    )
    return baseline_rate, current_rate, candidate_threshold, critical_threshold


def detect_config_state_drift(state: SentinelState) -> list[Finding]:
    """Surface persistent normalized desired↔observed resource divergence."""

    findings: list[Finding] = []
    for observation in state.drift_observations:
        finding = _drift_finding(observation)
        if finding is not None:
            findings.append(finding)
    return findings


def _drift_finding(observation: DriftObservation) -> Finding | None:
    if observation.observed_revision == observation.desired_revision:
        return None
    if (
        observation.consecutive_mismatches < DRIFT_MIN_CONSECUTIVE_OBSERVATIONS
        or observation.drift_age_seconds < DRIFT_GRACE_SECONDS
    ):
        return None

    missing = observation.observed_revision is None
    severity = (
        Severity.HIGH
        if missing or observation.drift_age_seconds >= DRIFT_HIGH_AGE_SECONDS
        else Severity.MEDIUM
    )
    if missing:
        rationale = (
            f"{observation.resource_kind} {observation.resource_id!r} is absent from "
            f"observed state for {observation.drift_age_seconds}s after desired-state recording."
        )
    else:
        rationale = (
            f"{observation.resource_kind} {observation.resource_id!r} observed revision "
            f"{observation.observed_revision!r} differs from desired revision "
            f"{observation.desired_revision!r} for {observation.drift_age_seconds}s."
        )
    return Finding(
        detector_id=_DRIFT_DETECTOR_ID,
        kind="config_state_drift",
        severity=severity,
        confidence=_DRIFT_CONFIDENCE,
        fingerprint=f"{observation.resource_kind}:{observation.resource_id}",
        rationale=rationale,
        evidence={
            "resource_kind": observation.resource_kind,
            "resource_id": observation.resource_id,
            "tracking_policy_revision": observation.tracking_policy_revision,
            "desired_revision": observation.desired_revision,
            "observed_revision": observation.observed_revision,
            "desired_recorded_at": observation.desired_recorded_at,
            "mismatch_started_at": observation.mismatch_started_at,
            "observed_at": observation.observed_at,
            "drift_age_seconds": observation.drift_age_seconds,
            "consecutive_mismatches": observation.consecutive_mismatches,
            "observed_present": not missing,
        },
        suggested_runbook="triage-config-state-drift",
    )


DEFAULT_DETECTORS: tuple[Detector, ...] = (
    detect_saturation_expiry,
    detect_new_error_signature,
    detect_error_rate_vs_baseline,
    detect_change_induced_regression,
    detect_config_state_drift,
)


__all__ = [
    "DEFAULT_DETECTORS",
    "CHANGE_ASSOCIATION_MAX_AGE_SECONDS",
    "DRIFT_GRACE_SECONDS",
    "DRIFT_HIGH_AGE_SECONDS",
    "DRIFT_MIN_CONSECUTIVE_OBSERVATIONS",
    "ERROR_RATE_ABSOLUTE_DELTA",
    "ERROR_RATE_BASELINE_MULTIPLIER",
    "ERROR_RATE_BUDGET_MULTIPLIER",
    "ERROR_RATE_CRITICAL_ABSOLUTE_DELTA",
    "ERROR_RATE_CRITICAL_BASELINE_MULTIPLIER",
    "ERROR_RATE_CRITICAL_BUDGET_MULTIPLIER",
    "ERROR_RATE_MIN_REQUESTS",
    "EXPIRY_CRITICAL_DAYS",
    "EXPIRY_WARN_DAYS",
    "SATURATION_CRITICAL",
    "SATURATION_PROJECTION_HORIZON",
    "SATURATION_WARN",
    "detect_error_rate_vs_baseline",
    "detect_change_induced_regression",
    "detect_config_state_drift",
    "detect_new_error_signature",
    "detect_saturation_expiry",
]
