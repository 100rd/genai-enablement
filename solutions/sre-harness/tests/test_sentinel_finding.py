"""Unit tests for the Sentinel detector contract (Finding + Severity)."""

from __future__ import annotations

import pytest

from sre_harness.sentinel.finding import Finding, Severity


def _finding(**overrides: object) -> Finding:
    base: dict[str, object] = {
        "detector_id": "saturation_expiry",
        "kind": "saturation",
        "severity": Severity.HIGH,
        "confidence": 1.0,
        "fingerprint": "prod-eu-1/pvc-payments",
        "rationale": "disk at 95% of capacity",
    }
    base.update(overrides)
    return Finding(**base)  # type: ignore[arg-type]


def test_severity_orders_low_to_critical() -> None:
    # Arrange / Act / Assert — IntEnum ordering underpins ranking.
    assert Severity.LOW < Severity.MEDIUM < Severity.HIGH < Severity.CRITICAL
    assert Severity.CRITICAL.value == 4


def test_dedup_key_is_scoped_by_detector_kind_and_fingerprint() -> None:
    finding = _finding()

    assert finding.dedup_key == "saturation_expiry:saturation:prod-eu-1/pvc-payments"


def test_same_fingerprint_different_detector_do_not_collide() -> None:
    a = _finding(detector_id="saturation_expiry", fingerprint="shared")
    b = _finding(detector_id="new_error_signature", fingerprint="shared")

    assert a.dedup_key != b.dedup_key


def test_rank_is_severity_times_confidence() -> None:
    finding = _finding(severity=Severity.HIGH, confidence=0.7)

    assert finding.rank == pytest.approx(3 * 0.7)


def test_confidence_out_of_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="confidence must be in"):
        _finding(confidence=1.5)


def test_blank_fingerprint_is_rejected() -> None:
    with pytest.raises(ValueError, match="fingerprint must not be blank"):
        _finding(fingerprint="   ")


def test_finding_is_frozen() -> None:
    finding = _finding()

    with pytest.raises(Exception):  # noqa: B017 — FrozenInstanceError is a dataclass detail
        finding.severity = Severity.LOW  # type: ignore[misc]


def test_suggested_runbook_defaults_to_none() -> None:
    assert _finding().suggested_runbook is None
