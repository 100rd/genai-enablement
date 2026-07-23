"""Unit tests for the deterministic Sentinel detectors."""

from __future__ import annotations

from sre_harness.sentinel.detectors import (
    DEFAULT_DETECTORS,
    detect_change_induced_regression,
    detect_config_state_drift,
    detect_error_rate_vs_baseline,
    detect_new_error_signature,
    detect_saturation_expiry,
)
from sre_harness.sentinel.finding import Severity
from sre_harness.sentinel.state import (
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)

# --- saturation ------------------------------------------------------------


def test_observed_critical_saturation_is_critical_and_certain() -> None:
    state = SentinelState(
        saturation_samples=(
            SaturationSample(resource="pvc", kind="disk", used=95.0, capacity=100.0),
        )
    )

    (finding,) = detect_saturation_expiry(state)

    assert finding.kind == "saturation"
    assert finding.severity is Severity.CRITICAL
    assert finding.confidence == 1.0
    assert finding.suggested_runbook == "scale-or-provision-disk"


def test_warn_band_saturation_is_medium() -> None:
    state = SentinelState(
        saturation_samples=(
            SaturationSample(resource="pvc", kind="disk", used=80.0, capacity=100.0),
        )
    )

    (finding,) = detect_saturation_expiry(state)

    assert finding.severity is Severity.MEDIUM


def test_healthy_resource_with_no_growth_yields_no_finding() -> None:
    state = SentinelState(
        saturation_samples=(
            SaturationSample(resource="pvc", kind="disk", used=10.0, capacity=100.0),
        )
    )

    assert detect_saturation_expiry(state) == []


def test_projected_exhaustion_is_high_but_less_certain() -> None:
    # 60 + 8 * 6 = 108 >= 100 within the projection horizon, though only at 60% now.
    state = SentinelState(
        saturation_samples=(
            SaturationSample(
                resource="pool-a",
                kind="connections",
                used=60.0,
                capacity=100.0,
                growth_per_interval=8.0,
            ),
        )
    )

    (finding,) = detect_saturation_expiry(state)

    assert finding.severity is Severity.HIGH
    assert finding.confidence == 0.7
    assert "projected" in finding.rationale


def test_slow_growth_that_does_not_reach_capacity_yields_no_finding() -> None:
    # 60 + 1 * 6 = 66 < 100, and 60% is below the warn band.
    state = SentinelState(
        saturation_samples=(
            SaturationSample(
                resource="pool-a",
                kind="connections",
                used=60.0,
                capacity=100.0,
                growth_per_interval=1.0,
            ),
        )
    )

    assert detect_saturation_expiry(state) == []


def test_cluster_qualifies_the_fingerprint() -> None:
    state = SentinelState(
        saturation_samples=(
            SaturationSample(
                resource="pvc", kind="disk", used=95.0, capacity=100.0, cluster="prod-eu-1"
            ),
        )
    )

    (finding,) = detect_saturation_expiry(state)

    assert finding.fingerprint == "prod-eu-1/pvc"


# --- expiry ----------------------------------------------------------------


def test_already_expired_item_is_critical() -> None:
    state = SentinelState(
        expiry_items=(ExpiryItem(name="api-tls", kind="cert", expires_in_days=0),)
    )

    (finding,) = detect_saturation_expiry(state)

    assert finding.kind == "expiry"
    assert finding.severity is Severity.CRITICAL
    assert finding.suggested_runbook == "rotate-cert"


def test_expiry_within_critical_window_is_high() -> None:
    state = SentinelState(
        expiry_items=(ExpiryItem(name="api-tls", kind="cert", expires_in_days=5),)
    )

    (finding,) = detect_saturation_expiry(state)

    assert finding.severity is Severity.HIGH


def test_expiry_within_warn_window_is_medium() -> None:
    state = SentinelState(
        expiry_items=(ExpiryItem(name="svc-token", kind="token", expires_in_days=20),)
    )

    (finding,) = detect_saturation_expiry(state)

    assert finding.severity is Severity.MEDIUM


def test_far_future_expiry_yields_no_finding() -> None:
    state = SentinelState(
        expiry_items=(ExpiryItem(name="api-tls", kind="cert", expires_in_days=180),)
    )

    assert detect_saturation_expiry(state) == []


# --- new error signature ---------------------------------------------------


def test_novel_signature_is_surfaced_as_high() -> None:
    state = SentinelState(
        error_windows=(
            ErrorSignatureWindow(
                service="payments",
                baseline=frozenset({"E1", "E2"}),
                current=frozenset({"E1", "E2", "E_NEW"}),
            ),
        )
    )

    (finding,) = detect_new_error_signature(state)

    assert finding.kind == "new_error_signature"
    assert finding.severity is Severity.HIGH
    assert finding.evidence["signature"] == "E_NEW"
    assert finding.fingerprint == "payments:E_NEW"


def test_no_novel_signature_yields_no_finding() -> None:
    state = SentinelState(
        error_windows=(
            ErrorSignatureWindow(
                service="payments",
                baseline=frozenset({"E1", "E2", "E3"}),
                current=frozenset({"E1", "E2"}),
            ),
        )
    )

    assert detect_new_error_signature(state) == []


def test_multiple_novel_signatures_are_emitted_sorted() -> None:
    state = SentinelState(
        error_windows=(
            ErrorSignatureWindow(
                service="payments",
                baseline=frozenset(),
                current=frozenset({"Z_ERR", "A_ERR"}),
            ),
        )
    )

    findings = detect_new_error_signature(state)

    assert [f.evidence["signature"] for f in findings] == ["A_ERR", "Z_ERR"]


def test_novelty_is_per_service() -> None:
    # 'E_NEW' is baseline-known for 'a' but novel for 'b'.
    state = SentinelState(
        error_windows=(
            ErrorSignatureWindow("a", baseline=frozenset({"E_NEW"}), current=frozenset({"E_NEW"})),
            ErrorSignatureWindow("b", baseline=frozenset(), current=frozenset({"E_NEW"})),
        )
    )

    findings = detect_new_error_signature(state)

    assert [f.fingerprint for f in findings] == ["b:E_NEW"]


# --- registry --------------------------------------------------------------


def test_empty_state_yields_nothing_from_any_detector() -> None:
    state = SentinelState()

    assert detect_saturation_expiry(state) == []
    assert detect_new_error_signature(state) == []
    assert detect_error_rate_vs_baseline(state) == []
    assert detect_change_induced_regression(state) == []
    assert detect_config_state_drift(state) == []


def test_default_registry_contains_all_five_detectors() -> None:
    assert DEFAULT_DETECTORS == (
        detect_saturation_expiry,
        detect_new_error_signature,
        detect_error_rate_vs_baseline,
        detect_change_induced_regression,
        detect_config_state_drift,
    )
