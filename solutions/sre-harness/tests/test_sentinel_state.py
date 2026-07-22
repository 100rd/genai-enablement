"""Unit tests for the Sentinel state records."""

from __future__ import annotations

import pytest

from sre_harness.sentinel.state import (
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)


def test_saturation_utilization_is_used_over_capacity() -> None:
    sample = SaturationSample(resource="pool-a", kind="connections", used=75.0, capacity=100.0)

    assert sample.utilization == pytest.approx(0.75)


def test_saturation_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError, match="capacity must be > 0"):
        SaturationSample(resource="pool-a", kind="connections", used=1.0, capacity=0.0)


def test_state_defaults_to_empty_signals() -> None:
    state = SentinelState()

    assert state.saturation_samples == ()
    assert state.expiry_items == ()
    assert state.error_windows == ()
    assert state.error_rate_windows == ()
    assert state.change_regression_windows == ()
    assert state.drift_observations == ()


def test_records_are_frozen() -> None:
    item = ExpiryItem(name="api-tls", kind="cert", expires_in_days=3)

    with pytest.raises(Exception):  # noqa: B017 — FrozenInstanceError is a dataclass detail
        item.expires_in_days = 99  # type: ignore[misc]


def test_error_window_holds_frozensets() -> None:
    window = ErrorSignatureWindow(
        service="payments",
        baseline=frozenset({"E1"}),
        current=frozenset({"E1", "E2"}),
    )

    assert window.current - window.baseline == {"E2"}
