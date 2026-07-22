"""Unit tests for Sentinel Finding/SentinelState JSON (de)serialization.

Stage 7 build-order step 2 needs findings and state snapshots to cross a JSON
boundary (persisted between periodic scans, loaded from a fixture file). These
tests drive typed field extraction with clear ``ValueError`` messages on
malformed input — never a bare ``KeyError``/``TypeError`` from blindly
``**kwargs``-ing untrusted data into a dataclass.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sre_harness.sentinel.finding import Finding, Severity
from sre_harness.sentinel.serialization import (
    finding_from_dict,
    finding_to_dict,
    read_json_object,
    state_from_dict,
)
from sre_harness.sentinel.state import (
    ChangeRegressionWindow,
    ErrorRateWindow,
    SentinelState,
)

_PREVIOUS_REVISION = "a" * 64
_DEPLOYED_REVISION = "b" * 64


def _change_regression_row() -> dict[str, object]:
    return {
        "service": "payments",
        "previous_revision": _PREVIOUS_REVISION,
        "deployed_revision": _DEPLOYED_REVISION,
        "baseline_ended_at": 1000,
        "deployed_at": 1100,
        "current_started_at": 1100,
        "observed_at": 1400,
        "intervening_deployments": 0,
        "baseline_errors": 1,
        "baseline_requests": 1000,
        "current_errors": 12,
        "current_requests": 1000,
        "allowed_error_rate": 0.001,
    }


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

    def test_missing_evidence_key_defaults_to_empty(self) -> None:
        payload = finding_to_dict(_finding())
        del payload["evidence"]

        assert finding_from_dict(payload).evidence == {}


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

    @pytest.mark.parametrize(
        "field",
        ["detector_id", "kind", "severity", "confidence", "fingerprint", "rationale"],
    )
    def test_null_required_field_is_rejected(self, field: str) -> None:
        payload = self._valid(**{field: None})

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

    @pytest.mark.parametrize("falsy_value", ["", [], False])
    def test_falsy_non_dict_evidence_is_rejected(self, falsy_value: object) -> None:
        with pytest.raises(ValueError, match="evidence"):
            finding_from_dict(self._valid(evidence=falsy_value))

    def test_non_numeric_confidence_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            finding_from_dict(self._valid(confidence=[1, 2, 3]))

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

    def test_unknown_top_level_keys_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="unexpected field"):
            state_from_dict({"unexpected": "field"})

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

    def test_expiry_item_accepts_a_whole_number_float(self) -> None:
        state = state_from_dict(
            {"expiry_items": [{"name": "api-tls", "kind": "cert", "expires_in_days": 5.0}]}
        )

        assert state.expiry_items[0].expires_in_days == 5

    def test_parses_exact_error_rate_windows(self) -> None:
        state = state_from_dict(
            {
                "error_rate_windows": [
                    {
                        "service": "payments",
                        "baseline_errors": 1,
                        "baseline_requests": 1000,
                        "current_errors": 12,
                        "current_requests": 1000,
                        "allowed_error_rate": 0.001,
                    }
                ]
            }
        )

        assert state.error_rate_windows == (
            ErrorRateWindow(
                service="payments",
                baseline_errors=1,
                baseline_requests=1000,
                current_errors=12,
                current_requests=1000,
                allowed_error_rate=0.001,
            ),
        )

    def test_parses_exact_change_regression_windows(self) -> None:
        state = state_from_dict({"change_regression_windows": [_change_regression_row()]})

        assert state.change_regression_windows == (
            ChangeRegressionWindow(
                service="payments",
                previous_revision=_PREVIOUS_REVISION,
                deployed_revision=_DEPLOYED_REVISION,
                baseline_ended_at=1000,
                deployed_at=1100,
                current_started_at=1100,
                observed_at=1400,
                intervening_deployments=0,
                baseline_errors=1,
                baseline_requests=1000,
                current_errors=12,
                current_requests=1000,
                allowed_error_rate=0.001,
            ),
        )


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

    def test_error_rate_windows_not_a_list_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="error_rate_windows"):
            state_from_dict({"error_rate_windows": {"not": "a list"}})

    def test_error_rate_windows_over_signal_limit_is_rejected_before_row_parsing(
        self,
    ) -> None:
        with pytest.raises(ValueError, match="at most 1000"):
            state_from_dict({"error_rate_windows": [None] * 1001})

    def test_error_rate_window_non_mapping_row_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="error rate window"):
            state_from_dict({"error_rate_windows": ["not-a-mapping"]})

    def test_change_regression_windows_not_a_list_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="change_regression_windows"):
            state_from_dict({"change_regression_windows": {"not": "a list"}})

    def test_change_regression_windows_over_limit_is_rejected_before_row_parsing(
        self,
    ) -> None:
        with pytest.raises(ValueError, match="at most 1000"):
            state_from_dict({"change_regression_windows": [None] * 1001})

    def test_change_regression_non_mapping_row_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="change regression window"):
            state_from_dict({"change_regression_windows": ["not-a-mapping"]})

    @pytest.mark.parametrize(
        "missing",
        [
            "service",
            "previous_revision",
            "deployed_revision",
            "baseline_ended_at",
            "deployed_at",
            "current_started_at",
            "observed_at",
            "intervening_deployments",
            "baseline_errors",
            "baseline_requests",
            "current_errors",
            "current_requests",
            "allowed_error_rate",
        ],
    )
    def test_change_regression_missing_or_null_field_is_rejected(self, missing: str) -> None:
        row = _change_regression_row()
        row[missing] = None

        with pytest.raises(ValueError, match="change regression window"):
            state_from_dict({"change_regression_windows": [row]})

    def test_change_regression_extra_field_is_rejected(self) -> None:
        row = _change_regression_row()
        row["caused_by"] = True

        with pytest.raises(ValueError, match="unexpected field"):
            state_from_dict({"change_regression_windows": [row]})

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("service", 7, "service"),
            ("previous_revision", 7, "previous_revision"),
            ("baseline_ended_at", True, "baseline_ended_at"),
            ("deployed_at", 1100.0, "deployed_at"),
            ("current_started_at", "1100", "current_started_at"),
            ("intervening_deployments", 0.0, "intervening_deployments"),
            ("baseline_errors", "1", "baseline_errors"),
            ("current_requests", 1000.0, "current_requests"),
            ("allowed_error_rate", 1, "allowed_error_rate"),
            ("allowed_error_rate", float("nan"), "allowed_error_rate"),
        ],
    )
    def test_change_regression_rejects_coercion_and_nonfinite_values(
        self, field: str, value: object, match: str
    ) -> None:
        row = _change_regression_row()
        row[field] = value

        with pytest.raises(ValueError, match=match):
            state_from_dict({"change_regression_windows": [row]})

    def test_saturation_sample_missing_field_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="saturation sample"):
            state_from_dict({"saturation_samples": [{"resource": "r"}]})

    def test_expiry_item_missing_field_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="expiry item"):
            state_from_dict({"expiry_items": [{"name": "x"}]})

    def test_error_window_missing_field_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="error window"):
            state_from_dict({"error_windows": [{"service": "payments"}]})

    @pytest.mark.parametrize(
        "missing",
        [
            "service",
            "baseline_errors",
            "baseline_requests",
            "current_errors",
            "current_requests",
            "allowed_error_rate",
        ],
    )
    def test_error_rate_window_missing_or_null_field_is_rejected(self, missing: str) -> None:
        row: dict[str, object] = {
            "service": "payments",
            "baseline_errors": 1,
            "baseline_requests": 1000,
            "current_errors": 12,
            "current_requests": 1000,
            "allowed_error_rate": 0.001,
        }
        row[missing] = None

        with pytest.raises(ValueError, match="error rate window"):
            state_from_dict({"error_rate_windows": [row]})

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("baseline_errors", True, "baseline_errors"),
            ("baseline_requests", 1000.0, "baseline_requests"),
            ("current_errors", "12", "current_errors"),
            ("current_requests", -1, "non-negative"),
            ("allowed_error_rate", True, "allowed_error_rate"),
            ("allowed_error_rate", float("nan"), "allowed_error_rate"),
            ("allowed_error_rate", float("inf"), "allowed_error_rate"),
        ],
    )
    def test_error_rate_window_rejects_coercion_and_nonfinite_values(
        self, field: str, value: object, match: str
    ) -> None:
        row: dict[str, object] = {
            "service": "payments",
            "baseline_errors": 1,
            "baseline_requests": 1000,
            "current_errors": 12,
            "current_requests": 1000,
            "allowed_error_rate": 0.001,
        }
        row[field] = value

        with pytest.raises(ValueError, match=match):
            state_from_dict({"error_rate_windows": [row]})

    def test_non_mapping_row_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="saturation sample"):
            state_from_dict({"saturation_samples": ["not-a-mapping"]})

    def test_saturation_sample_null_field_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="saturation sample"):
            state_from_dict(
                {
                    "saturation_samples": [
                        {"resource": None, "kind": "disk", "used": 1.0, "capacity": 10.0}
                    ]
                }
            )

    def test_expiry_item_null_field_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="expiry item"):
            state_from_dict(
                {"expiry_items": [{"name": None, "kind": "cert", "expires_in_days": 5}]}
            )

    def test_error_window_null_field_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="error window"):
            state_from_dict(
                {"error_windows": [{"service": None, "baseline": ["E1"], "current": ["E1"]}]}
            )

    def test_saturation_sample_non_numeric_used_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="used"):
            state_from_dict(
                {
                    "saturation_samples": [
                        {"resource": "r", "kind": "disk", "used": [1], "capacity": 10.0}
                    ]
                }
            )

    def test_saturation_sample_non_numeric_capacity_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="capacity"):
            state_from_dict(
                {
                    "saturation_samples": [
                        {"resource": "r", "kind": "disk", "used": 1.0, "capacity": {}}
                    ]
                }
            )

    def test_saturation_sample_non_numeric_growth_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="growth_per_interval"):
            state_from_dict(
                {
                    "saturation_samples": [
                        {
                            "resource": "r",
                            "kind": "disk",
                            "used": 1.0,
                            "capacity": 10.0,
                            "growth_per_interval": "fast",
                        }
                    ]
                }
            )

    def test_expiry_item_non_numeric_expires_in_days_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="expires_in_days"):
            state_from_dict(
                {"expiry_items": [{"name": "x", "kind": "cert", "expires_in_days": [1]}]}
            )

    def test_expiry_item_non_integral_float_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="expires_in_days"):
            state_from_dict(
                {"expiry_items": [{"name": "x", "kind": "cert", "expires_in_days": 5.5}]}
            )

    def test_baseline_not_a_list_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="baseline"):
            state_from_dict(
                {"error_windows": [{"service": "payments", "baseline": "E1E2", "current": ["E1"]}]}
            )

    def test_current_not_a_list_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="current"):
            state_from_dict(
                {"error_windows": [{"service": "payments", "baseline": ["E1"], "current": "E1E2"}]}
            )


@pytest.mark.unit
class TestReadJsonObject:
    def test_reads_a_valid_object(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        path.write_text('{"a": 1}', encoding="utf-8")

        assert read_json_object(path) == {"a": 1}

    def test_directory_is_rejected(self, tmp_path: Path) -> None:
        directory = tmp_path / "as-dir"
        directory.mkdir()

        with pytest.raises(ValueError, match="not a file"):
            read_json_object(directory)

    def test_invalid_json_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")

        with pytest.raises(ValueError, match="not valid JSON"):
            read_json_object(path)

    def test_invalid_utf8_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "invalid-utf8.json"
        path.write_bytes(b'{"value":"\xff"}')

        with pytest.raises(ValueError, match="not valid JSON"):
            read_json_object(path)

    def test_non_object_payload_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "list.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")

        with pytest.raises(ValueError, match="object"):
            read_json_object(path)

    def test_deeply_nested_json_is_rejected_not_a_raw_recursion_error(self, tmp_path: Path) -> None:
        # json.loads() recurses per nesting level; deep-enough input raises a
        # bare RecursionError, not json.JSONDecodeError — must still surface
        # as the documented ValueError, not crash the CLI uncaught.
        path = tmp_path / "deep.json"
        depth = 2000
        path.write_text("[" * depth + "]" * depth, encoding="utf-8")

        with pytest.raises(ValueError, match="not valid JSON"):
            read_json_object(path)

    def test_symlink_is_rejected(self, tmp_path: Path) -> None:
        target = tmp_path / "target.json"
        target.write_text('{"a": 1}', encoding="utf-8")
        link = tmp_path / "link.json"
        link.symlink_to(target)

        with pytest.raises(ValueError, match="symlink"):
            read_json_object(link)

    @pytest.mark.skipif(not hasattr(os, "O_NONBLOCK"), reason="POSIX open flag")
    def test_open_is_nonblocking_so_special_files_cannot_stall_the_reader(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "state.json"
        path.write_text("{}", encoding="utf-8")
        opened_with: list[int] = []

        def reject_open(candidate: object, flags: int) -> int:
            opened_with.append(flags)
            raise OSError("synthetic open failure")

        monkeypatch.setattr(os, "open", reject_open)

        with pytest.raises(ValueError, match="unavailable"):
            read_json_object(path)
        assert opened_with[0] & os.O_NONBLOCK

    def test_oversized_file_is_rejected_before_decode(self, tmp_path: Path) -> None:
        path = tmp_path / "large.json"
        path.write_bytes(b" " * (1024 * 1024 + 1))

        with pytest.raises(ValueError, match="too large"):
            read_json_object(path)

    def test_duplicate_keys_are_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "duplicate.json"
        path.write_text('{"error_rate_windows": [], "error_rate_windows": []}', encoding="utf-8")

        with pytest.raises(ValueError, match="duplicate"):
            read_json_object(path)

    def test_file_changed_while_reading_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "changing.json"
        path.write_text("{}", encoding="utf-8")
        real_fstat = os.fstat
        calls = 0

        def changed_after_read(descriptor: int):
            nonlocal calls
            result = real_fstat(descriptor)
            calls += 1
            if calls == 2:
                values = list(result)
                values[8] = result.st_mtime + 1
                return os.stat_result(values)
            return result

        monkeypatch.setattr(os, "fstat", changed_after_read)

        with pytest.raises(ValueError, match="changed while reading"):
            read_json_object(path)
        assert calls == 2

    @pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
    def test_nonfinite_json_numbers_are_rejected(self, tmp_path: Path, constant: str) -> None:
        path = tmp_path / "nonfinite.json"
        path.write_text(f'{{"value": {constant}}}', encoding="utf-8")

        with pytest.raises(ValueError, match="finite"):
            read_json_object(path)
