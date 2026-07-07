"""Unit tests for the Sentinel ``StateSource`` port (Stage 7, step 2).

Mirrors the ``PlatformGraph`` port: detectors depend on a ``StateSource``
protocol, not a concrete source, so the CLI and tests run against a
fixture/static source today while live observability adapters are wired up
separately once their query contracts exist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sre_harness.sentinel.source import JsonFileStateSource, StateSource, StaticStateSource
from sre_harness.sentinel.state import SaturationSample, SentinelState


@pytest.mark.unit
class TestProtocolConformance:
    def test_static_source_is_a_state_source(self) -> None:
        assert isinstance(StaticStateSource(SentinelState()), StateSource)

    def test_json_file_source_is_a_state_source(self, tmp_path: Path) -> None:
        assert isinstance(JsonFileStateSource(tmp_path / "state.json"), StateSource)


@pytest.mark.unit
class TestStaticStateSource:
    def test_snapshot_returns_the_wrapped_state(self) -> None:
        state = SentinelState(
            saturation_samples=(
                SaturationSample(resource="r", kind="disk", used=1.0, capacity=10.0),
            )
        )

        assert StaticStateSource(state).snapshot() is state


@pytest.mark.unit
class TestJsonFileStateSource:
    def test_reads_a_valid_fixture(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text(
            json.dumps(
                {
                    "saturation_samples": [
                        {"resource": "pvc-payments", "kind": "disk", "used": 90.0, "capacity": 100.0}
                    ]
                }
            ),
            encoding="utf-8",
        )

        state = JsonFileStateSource(path).snapshot()

        assert len(state.saturation_samples) == 1
        assert state.saturation_samples[0].resource == "pvc-payments"

    def test_empty_object_yields_default_state(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text("{}", encoding="utf-8")

        assert JsonFileStateSource(path).snapshot() == SentinelState()


@pytest.mark.unit
class TestJsonFileStateSourceErrors:
    def test_missing_file_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            JsonFileStateSource(tmp_path / "nope.json").snapshot()

    def test_directory_path_is_rejected(self, tmp_path: Path) -> None:
        directory = tmp_path / "state-as-dir"
        directory.mkdir()

        with pytest.raises(ValueError, match="not a file"):
            JsonFileStateSource(directory).snapshot()

    def test_invalid_json_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text("{not json", encoding="utf-8")

        with pytest.raises(ValueError, match="not valid JSON"):
            JsonFileStateSource(path).snapshot()

    def test_non_object_payload_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

        with pytest.raises(ValueError, match="object"):
            JsonFileStateSource(path).snapshot()

    def test_invalid_saturation_sample_propagates(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text(
            json.dumps(
                {"saturation_samples": [{"resource": "r", "kind": "disk", "used": 1.0, "capacity": 0.0}]}
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="capacity must be > 0"):
            JsonFileStateSource(path).snapshot()
