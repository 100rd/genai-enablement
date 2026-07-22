"""SPEC-B1 P-B1-1/2/3: strict JSON and read-only incident-source boundary."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sre_harness.triage import RootCause
from sre_harness.triage.source import (
    MAX_SNAPSHOT_BYTES,
    JsonFileIncidentSnapshotSource,
    SnapshotRequest,
    load_snapshot,
    run_triage_from_source,
)

AS_OF = datetime(2026, 7, 16, 8, 20, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict[str, object]:
    return {
        "schemaVersion": "sre-harness.incident-snapshot/v1",
        "alert": {
            "incidentId": "inc-payments-001",
            "service": "payments-api",
            "startedAt": "2026-07-16T08:00:00Z",
            "summary": "Elevated checkout errors",
        },
        "capturedAt": "2026-07-16T08:20:00Z",
        "evidence": [
            {
                "evidenceId": "deploy-42",
                "kind": "deployment",
                "service": "payments-api",
                "observedAt": "2026-07-16T07:56:00Z",
                "statement": "payments-api revision 42 deployed",
            },
            {
                "evidenceId": "errors",
                "kind": "error_rate",
                "service": "payments-api",
                "observedAt": "2026-07-16T08:02:00Z",
                "statement": "payments-api error rate reached 18%",
                "value": 0.18,
            },
        ],
    }


def _request(**updates: object) -> SnapshotRequest:
    values: dict[str, object] = {
        "incident_id": "inc-payments-001",
        "as_of": AS_OF,
    }
    values.update(updates)
    return SnapshotRequest(**values)  # type: ignore[arg-type]


def _write(path: Path, payload: object | None = None) -> Path:
    path.write_text(
        json.dumps(_payload() if payload is None else payload),
        encoding="utf-8",
    )
    return path


@pytest.mark.unit
class TestSnapshotRequestAndSourceRejoin:
    def test_request_is_exact_utc_and_immutable(self) -> None:
        request = _request()

        assert request.incident_id == "inc-payments-001"
        with pytest.raises(ValueError, match="UTC"):
            _request(as_of=AS_OF.replace(tzinfo=None))
        with pytest.raises(ValueError, match="blank"):
            _request(incident_id=" ")

    def test_only_snapshot_is_called_and_exact_result_is_admitted(self, tmp_path: Path) -> None:
        expected = JsonFileIncidentSnapshotSource(_write(tmp_path / "snapshot.json")).snapshot(
            _request()
        )

        class SourceWithWriteTrap:
            snapshot_calls = 0
            write_calls = 0

            def snapshot(self, request: SnapshotRequest):
                self.snapshot_calls += 1
                assert request == _request()
                return expected

            def write(self) -> None:
                self.write_calls += 1
                raise AssertionError("write surface must never be called")

            def execute(self) -> None:
                raise AssertionError("execute surface must never be called")

        source = SourceWithWriteTrap()
        observed = load_snapshot(_request(), source)

        assert observed is expected
        assert source.snapshot_calls == 1
        assert source.write_calls == 0

    @pytest.mark.parametrize(
        ("snapshot_request", "reason"),
        [
            (_request(incident_id="inc-foreign"), "incident id mismatch"),
            (_request(as_of=AS_OF + timedelta(seconds=1)), "as_of mismatch"),
        ],
    )
    def test_foreign_incident_or_as_of_fails_closed(
        self,
        tmp_path: Path,
        snapshot_request: SnapshotRequest,
        reason: str,
    ) -> None:
        source = JsonFileIncidentSnapshotSource(_write(tmp_path / "snapshot.json"))

        with pytest.raises(ValueError, match=reason):
            load_snapshot(snapshot_request, source)

    def test_invalid_or_unavailable_source_never_becomes_an_empty_success(self) -> None:
        class InvalidSource:
            @staticmethod
            def snapshot(_request: SnapshotRequest):
                return object()

        class OfflineSource:
            @staticmethod
            def snapshot(_request: SnapshotRequest):
                raise RuntimeError("provider offline")

        with pytest.raises(TypeError, match="IncidentSnapshot"):
            load_snapshot(_request(), InvalidSource())
        with pytest.raises(RuntimeError, match="provider offline"):
            load_snapshot(_request(), OfflineSource())

    def test_source_integrates_with_action_free_triage_pipeline(self, tmp_path: Path) -> None:
        source = JsonFileIncidentSnapshotSource(_write(tmp_path / "snapshot.json"))

        report = run_triage_from_source(_request(), source)

        assert report.primary_cause is RootCause.DEPLOYMENT_REGRESSION
        assert report.evidence_ids == ("deploy-42", "errors")
        assert not hasattr(report, "actions")
        assert not hasattr(report, "remediation")


@pytest.mark.unit
class TestStrictJsonSnapshotSource:
    def test_committed_example_is_a_valid_replayable_snapshot(self) -> None:
        source = JsonFileIncidentSnapshotSource(ROOT / "examples" / "incident-snapshot.json")

        snapshot = source.snapshot(_request())

        assert snapshot.alert.incident_id == "inc-payments-001"
        assert len(snapshot.evidence) == 2

    def test_valid_v1_json_loads_exact_snapshot(self, tmp_path: Path) -> None:
        source = JsonFileIncidentSnapshotSource(_write(tmp_path / "snapshot.json"))

        snapshot = source.snapshot(_request())

        assert snapshot.alert.incident_id == "inc-payments-001"
        assert snapshot.alert.service == "payments-api"
        assert snapshot.captured_at == AS_OF
        assert tuple(item.evidence_id for item in snapshot.evidence) == (
            "deploy-42",
            "errors",
        )
        assert snapshot.evidence[1].value == pytest.approx(0.18)

    @pytest.mark.parametrize(
        ("mutation", "reason"),
        [
            (lambda payload: payload.update({"unexpected": True}), "unknown fields"),
            (lambda payload: payload.pop("capturedAt"), "missing fields"),
            (
                lambda payload: payload.update({"schemaVersion": "v0"}),
                "schema version",
            ),
            (
                lambda payload: payload["alert"].update({"owner": "attacker"}),
                "unknown fields",
            ),
            (
                lambda payload: payload["evidence"][0].update({"kind": "shell"}),
                "evidence kind",
            ),
            (
                lambda payload: payload["evidence"][0].update({"evidenceId": 7}),
                "evidenceId must be a string",
            ),
            (
                lambda payload: payload["evidence"][1].update({"value": True}),
                "evidence value must be a number",
            ),
            (
                lambda payload: payload.update({"evidence": [payload["evidence"][0]] * 129}),
                "maximum 128",
            ),
        ],
    )
    def test_closed_schema_and_types_fail_closed(
        self,
        tmp_path: Path,
        mutation,
        reason: str,
    ) -> None:
        payload = deepcopy(_payload())
        mutation(payload)
        source = JsonFileIncidentSnapshotSource(_write(tmp_path / "snapshot.json", payload))

        with pytest.raises((TypeError, ValueError), match=reason):
            source.snapshot(_request())

    @pytest.mark.parametrize(
        ("raw", "reason"),
        [
            (
                '{"schemaVersion":"sre-harness.incident-snapshot/v1","schemaVersion":"duplicate"}',
                "duplicate JSON key",
            ),
            ('{"value": NaN}', "non-finite JSON number"),
            ('{"schemaVersion":', "malformed JSON"),
        ],
    )
    def test_duplicate_non_finite_and_malformed_json_fail_closed(
        self,
        tmp_path: Path,
        raw: str,
        reason: str,
    ) -> None:
        path = tmp_path / "snapshot.json"
        path.write_text(raw, encoding="utf-8")

        with pytest.raises(ValueError, match=reason):
            JsonFileIncidentSnapshotSource(path).snapshot(_request())

    def test_invalid_utf8_oversize_symlink_and_non_file_fail_closed(self, tmp_path: Path) -> None:
        invalid_utf8 = tmp_path / "invalid.json"
        invalid_utf8.write_bytes(b"\xff\xfe")
        oversize = tmp_path / "oversize.json"
        oversize.write_bytes(b" " * (MAX_SNAPSHOT_BYTES + 1))
        target = _write(tmp_path / "target.json")
        symlink = tmp_path / "link.json"
        symlink.symlink_to(target)

        with pytest.raises(ValueError, match="UTF-8"):
            JsonFileIncidentSnapshotSource(invalid_utf8).snapshot(_request())
        with pytest.raises(ValueError, match="exceeds maximum"):
            JsonFileIncidentSnapshotSource(oversize).snapshot(_request())
        with pytest.raises(ValueError, match="symlink"):
            JsonFileIncidentSnapshotSource(symlink).snapshot(_request())
        with pytest.raises(ValueError, match="regular file"):
            JsonFileIncidentSnapshotSource(tmp_path).snapshot(_request())
        with pytest.raises(ValueError, match="not found"):
            JsonFileIncidentSnapshotSource(tmp_path / "missing.json").snapshot(_request())
