"""Unit tests for Sentinel Finding/SentinelState JSON (de)serialization.

Stage 7 build-order step 2 needs findings and state snapshots to cross a JSON
boundary (persisted between periodic scans, loaded from a fixture file). These
tests drive typed field extraction with clear ``ValueError`` messages on
malformed input — never a bare ``KeyError``/``TypeError`` from blindly
``**kwargs``-ing untrusted data into a dataclass.
"""

from __future__ import annotations

import pytest

from sre_harness.sentinel.finding import Finding, Severity
from sre_harness.sentinel.serialization import (
    finding_from_dict,
    finding_to_dict,
    state_from_dict,
)
from sre_harness.sentinel.state import SentinelState

# --- Finding round trip ------------------------------------------------------


def _finding(**overrides: object) -> Finding:
    base: dict[str, object] = {
        "detector_id": "saturation_expiry",
        "kind": "saturation",
        "severity": Severity.HIGH,
        "confidence": 0.9,
        "fingerprint": "prod-eu-1/pvc-payments",
        "rationale": "disk at 95% of capacity",
        "evidence": {"utilization": 0.95},
        "suggested_runbook": "scale-or-provision-disk",
    }
    base.update(overrides)
    return Finding(**base)  # type: ignore[arg-type]


@pytest.mark.unit
class TestFindingRoundTrip:
    def test_to_dict_then_from_dict_reconstructs_the_finding(self) -> None:
        finding = _finding()

        assert finding_from_dict(finding_to_dict(finding)) == finding

    def test_to_dict_serializes_severity_as_its_name(self) -> None:
        assert finding_to_dict(_finding(severity=Severity.CRITICAL))["severity"] == "CRITICAL"

    def test_round_trip_with_no_suggested_runbook(self) -> None:
        finding = _finding(suggested_runbook=None)

        assert finding_from_dict(finding_to_dict(finding)) == finding

    def test_round_trip_with_empty_evidence(self) -> None:
        finding = _finding(evidence={})

        assert finding_from_dict(finding_to_dict(finding)) == finding


@pytest.mark.unit
class TestFindingFromDictErrors:
    def _valid(self, **overrides: object) -> dict[str, object]:
        payload = finding_to_dict(_finding())
        payload.update(overrides)
        return payload

    @pytest.mark.parametrize(
        "field",
        ["detector_id", "kind", "severity", "confidence", "fingerprint", "rationale"],
    )
    def test_missing_required_field_is_rejected(self, field: str) -> None:
        payload = self._valid()
        del payload[field]

        with pytest.raises(ValueError, match=field):
            finding_from_dict(payload)

    def test_unknown_severity_name_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="severity"):
            finding_from_dict(self._valid(severity="SUPER_CRITICAL"))

    def test_non_string_severity_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="severity"):
            finding_from_dict(self._valid(severity=4))

    def test_non_dict_evidence_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="evidence"):
            finding_from_dict(self._valid(evidence="not-a-dict"))

    def test_confidence_out_of_range_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="confidence must be in"):
            finding_from_dict(self._valid(confidence=1.5))

    def test_blank_fingerprint_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="fingerprint must not be blank"):
            finding_from_dict(self._valid(fingerprint="   "))

    def test_non_mapping_payload_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="object"):
            finding_from_dict(["not", "a", "mapping"])  # type: ignore[arg-type]


# --- SentinelState round trip ------------------------------------------------


@pytest.mark.unit
class TestStateFromDict:
    def test_empty_object_yields_default_state(self) -> None:
        assert state_from_dict({}) == SentinelState()

    def test_unknown_top_level_keys_are_ignored(self) -> None:
        assert state_from_dict({"unexpected": "field"}) == SentinelState()

    def test_parses_saturation_samples(self) -> None:
        state = state_from_dict(
            {
                "saturation_samples": [
                    {
                        "resource": "pvc-payments",
                        "kind": "disk",
                        "used": 90.0,
                        "capacity": 100.0,
                        "cluster": "prod-eu-1",
                        "growth_per_interval": 2.0,
                    }
                ]
            }
        )

        assert len(state.saturation_samples) == 1
        sample = state.saturation_samples[0]
        assert sample.resource == "pvc-payments"
        assert sample.cluster == "prod-eu-1"
        assert sample.growth_per_interval == 2.0

    def test_saturation_sample_defaults_cluster_and_growth(self) -> None:
        state = state_from_dict(
            {
                "saturation_samples": [
                    {"resource": "r", "kind": "disk", "used": 1.0, "capacity": 10.0}
                ]
            }
        )

        sample = state.saturation_samples[0]
        assert sample.cluster is None
        assert sample.growth_per_interval == 0.0

    def test_saturation_sample_invalid_capacity_propagates(self) -> None:
        with pytest.raises(ValueError, match="capacity must be > 0"):
            state_from_dict(
                {
                    "saturation_samples": [
                        {"resource": "r", "kind": "disk", "used": 1.0, "capacity": 0.0}
                    ]
                }
            )

    def test_parses_expiry_items(self) -> None:
        state = state_from_dict(
            {"expiry_items": [{"name": "api-tls", "kind": "cert", "expires_in_days": 5}]}
        )

        assert state.expiry_items == (
            state.expiry_items[0].__class__(name="api-tls", kind="cert", expires_in_days=5),
        )

    def test_parses_error_windows(self) -> None:
        state = state_from_dict(
            {
                "error_windows": [
                    {"service": "payments", "baseline": ["E1"], "current": ["E1", "E2"]}
                ]
            }
        )

        window = state.error_windows[0]
        assert window.service == "payments"
        assert window.baseline == frozenset({"E1"})
        assert window.current == frozenset({"E1", "E2"})


@pytest.mark.unit
class TestStateFromDictErrors:
    def test_saturation_samples_not_a_list_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="saturation_samples"):
            state_from_dict({"saturation_samples": "nope"})

    def test_expiry_items_not_a_list_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="expiry_items"):
            state_from_dict({"expiry_items": {"not": "a list"}})

    def test_error_windows_not_a_list_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="error_windows"):
            state_from_dict({"error_windows": 42})

    def test_saturation_sample_missing_field_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="saturation sample"):
            state_from_dict({"saturation_samples": [{"resource": "r"}]})

    def test_expiry_item_missing_field_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="expiry item"):
            state_from_dict({"expiry_items": [{"name": "x"}]})

    def test_error_window_missing_field_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="error window"):
            state_from_dict({"error_windows": [{"service": "payments"}]})

    def test_non_mapping_row_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="saturation sample"):
            state_from_dict({"saturation_samples": ["not-a-mapping"]})
