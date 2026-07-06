"""Unit tests for the ``sre-harness sentinel scan`` CLI (Stage 7, step 2).

The command is a thin, deterministic shell around
:func:`~sre_harness.sentinel.scan.run_sentinel`: it loads a state snapshot
(``--state``) and, optionally, a persisted open-findings set
(``--open-findings``), runs one scan, prints the report as JSON, persists the
updated open set back to ``--open-findings`` (if given), and sets an exit code:

    0 = no fresh findings, 1 = fresh findings emitted, 2 = usage error

Sentinel is **advisory, never a gate** — exit 1 is informational (something new
to look at), not a pipeline failure signal. These tests are written first (RED)
and drive the implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sre_harness.cli import main
from sre_harness.sentinel.cli import (
    EXIT_FRESH_FINDINGS,
    EXIT_NO_FRESH_FINDINGS,
    EXIT_USAGE,
)

# --- fixtures ---------------------------------------------------------------


def _write(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _clean_state_file(tmp_path: Path) -> Path:
    return _write(tmp_path / "state.json", {})


def _hot_state_payload() -> dict[str, Any]:
    return {
        "saturation_samples": [
            {"resource": "pvc-payments", "kind": "disk", "used": 97.0, "capacity": 100.0}
        ]
    }


def _hot_state_file(tmp_path: Path, name: str = "state.json") -> Path:
    return _write(tmp_path / name, _hot_state_payload())


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any]]:
    code = main(argv)
    out = capsys.readouterr().out
    return code, json.loads(out)


# --- exit codes / output shape -----------------------------------------------


@pytest.mark.unit
class TestExitCodes:
    def test_clean_state_exits_0_with_no_findings(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _clean_state_file(tmp_path)
        code, doc = _run(["sentinel", "scan", "--state", str(state)], capsys)

        assert code == EXIT_NO_FRESH_FINDINGS == 0
        assert doc["findings"] == []
        assert doc["finding_count"] == 0

    def test_hot_state_exits_1_with_fresh_findings(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _hot_state_file(tmp_path)
        code, doc = _run(["sentinel", "scan", "--state", str(state)], capsys)

        assert code == EXIT_FRESH_FINDINGS == 1
        assert doc["finding_count"] == 1
        assert doc["findings"][0]["detector_id"] == "saturation_expiry"


@pytest.mark.unit
class TestOutputShape:
    def test_emits_advisory_tiers(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _clean_state_file(tmp_path)
        _, doc = _run(["sentinel", "scan", "--state", str(state)], capsys)

        assert doc["detection_tier"] == "T1"
        assert doc["recommendation_tier"] == "T2"
        assert doc["advisory"] is True

    def test_verbose_includes_suppressed_block(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _clean_state_file(tmp_path)
        _, doc = _run(["sentinel", "scan", "--state", str(state), "--verbose"], capsys)

        assert doc["suppressed"] == []
        assert doc["suppressed_count"] == 0

    def test_non_verbose_omits_suppressed_block(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _clean_state_file(tmp_path)
        _, doc = _run(["sentinel", "scan", "--state", str(state)], capsys)

        assert "suppressed" not in doc
        assert "suppressed_count" not in doc

    def test_finding_fields_include_rank_and_dedup_key(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _hot_state_file(tmp_path)
        _, doc = _run(["sentinel", "scan", "--state", str(state)], capsys)

        finding = doc["findings"][0]
        assert {
            "detector_id",
            "kind",
            "severity",
            "confidence",
            "rationale",
            "rank",
            "dedup_key",
        } <= set(finding)
        assert finding["severity"] == "CRITICAL"


# --- open-findings persistence (dedup across scans) --------------------------


@pytest.mark.unit
class TestOpenFindingsPersistence:
    def test_first_run_seeds_the_open_findings_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _hot_state_file(tmp_path)
        open_findings = tmp_path / "open.json"

        code, doc = _run(
            ["sentinel", "scan", "--state", str(state), "--open-findings", str(open_findings)],
            capsys,
        )

        assert code == EXIT_FRESH_FINDINGS
        assert doc["finding_count"] == 1
        assert open_findings.is_file()
        persisted = json.loads(open_findings.read_text(encoding="utf-8"))
        assert len(persisted["open_findings"]) == 1

    def test_second_run_against_the_same_state_suppresses_the_repeat(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _hot_state_file(tmp_path)
        open_findings = tmp_path / "open.json"
        argv = ["sentinel", "scan", "--state", str(state), "--open-findings", str(open_findings)]

        first_code, _ = _run(argv, capsys)
        second_code, second_doc = _run(argv, capsys)

        assert first_code == EXIT_FRESH_FINDINGS
        assert second_code == EXIT_NO_FRESH_FINDINGS
        assert second_doc["findings"] == []

    def test_second_run_shows_the_repeat_as_suppressed_when_verbose(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _hot_state_file(tmp_path)
        open_findings = tmp_path / "open.json"
        argv = [
            "sentinel",
            "scan",
            "--state",
            str(state),
            "--open-findings",
            str(open_findings),
            "--verbose",
        ]

        _run(argv, capsys)
        _, second_doc = _run(argv, capsys)

        assert second_doc["suppressed_count"] == 1

    def test_omitting_open_findings_is_stateless_across_runs(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _hot_state_file(tmp_path)
        argv = ["sentinel", "scan", "--state", str(state)]

        first_code, _ = _run(argv, capsys)
        second_code, second_doc = _run(argv, capsys)

        assert first_code == EXIT_FRESH_FINDINGS
        assert second_code == EXIT_FRESH_FINDINGS
        assert second_doc["finding_count"] == 1

    def test_finding_auto_drops_once_the_detector_stops_reproducing_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Closure-by-omission: save_open only ever persists what THIS scan
        # produced, so a finding the detector no longer reproduces (condition
        # resolved) silently drops out of the open set — not tracked history.
        open_findings = tmp_path / "open.json"
        hot_state = _hot_state_file(tmp_path, name="hot.json")
        healthy_state = _clean_state_file(tmp_path)

        _run(
            ["sentinel", "scan", "--state", str(hot_state), "--open-findings", str(open_findings)],
            capsys,
        )
        code, doc = _run(
            [
                "sentinel",
                "scan",
                "--state",
                str(healthy_state),
                "--open-findings",
                str(open_findings),
            ],
            capsys,
        )

        assert code == EXIT_NO_FRESH_FINDINGS
        assert doc["findings"] == []
        persisted = json.loads(open_findings.read_text(encoding="utf-8"))
        assert persisted["open_findings"] == []


# --- error handling -----------------------------------------------------------


@pytest.mark.unit
class TestErrors:
    def test_missing_state_file_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(["sentinel", "scan", "--state", str(tmp_path / "nope.json")])

        assert code == EXIT_USAGE
        assert "nope.json" in capsys.readouterr().err

    def test_invalid_json_state_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")

        code = main(["sentinel", "scan", "--state", str(bad)])

        assert code == EXIT_USAGE
        assert "not valid json" in capsys.readouterr().err.lower()

    def test_invalid_json_open_findings_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _clean_state_file(tmp_path)
        bad_open = tmp_path / "open.json"
        bad_open.write_text("{not json", encoding="utf-8")

        code = main(
            ["sentinel", "scan", "--state", str(state), "--open-findings", str(bad_open)]
        )

        assert code == EXIT_USAGE
        assert "not valid json" in capsys.readouterr().err.lower()

    def test_sentinel_without_subcommand_errors(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["sentinel"])

        assert code == EXIT_USAGE
        assert "scan" in capsys.readouterr().err.lower()

    def test_null_typed_state_field_errors_cleanly_not_a_traceback(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _write(
            tmp_path / "state.json",
            {
                "saturation_samples": [
                    {"resource": "r", "kind": "disk", "used": None, "capacity": 10.0}
                ]
            },
        )

        code = main(["sentinel", "scan", "--state", str(state)])

        assert code == EXIT_USAGE
        assert "used" in capsys.readouterr().err.lower()

    def test_open_findings_save_failure_errors_cleanly_not_a_traceback(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = _clean_state_file(tmp_path)
        unwritable = tmp_path / "does-not-exist" / "open.json"

        code = main(
            ["sentinel", "scan", "--state", str(state), "--open-findings", str(unwritable)]
        )

        assert code == EXIT_USAGE
        assert capsys.readouterr().err.strip() != ""
