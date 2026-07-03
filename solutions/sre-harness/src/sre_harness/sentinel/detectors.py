"""The deterministic Sentinel detectors (Stage 7 — build-order step 1).

Two pure ``(state) -> list[Finding]`` detectors, deterministic-first per the ADR
(no model in the loop). Each mirrors a gate check: small, pure, registered in
:data:`DEFAULT_DETECTORS`. Adding a detector means adding a callable to the
registry, nothing else.

- ``saturation_expiry`` — resources trending toward exhaustion (observed breach
  *or* projected exhaustion within a horizon) and credentials/certs expiring
  within a horizon. ADR catalog #5.
- ``new_error_signature`` — an error signature present in the current window but
  absent from the baseline window (a *novel* class, not raw volume). ADR
  catalog #2's deterministic core; naming/clustering is a future model step.

Both emit **anomaly / new-class / risk relative to a baseline or a horizon** —
never "there are errors" or "utilisation is nonzero" — honouring the ADR's
signal-over-volume principle.
"""

from __future__ import annotations

from sre_harness.sentinel.finding import Detector, Finding, Severity
from sre_harness.sentinel.state import (
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


DEFAULT_DETECTORS: tuple[Detector, ...] = (
    detect_saturation_expiry,
    detect_new_error_signature,
)


__all__ = [
    "DEFAULT_DETECTORS",
    "EXPIRY_CRITICAL_DAYS",
    "EXPIRY_WARN_DAYS",
    "SATURATION_CRITICAL",
    "SATURATION_PROJECTION_HORIZON",
    "SATURATION_WARN",
    "detect_new_error_signature",
    "detect_saturation_expiry",
]
