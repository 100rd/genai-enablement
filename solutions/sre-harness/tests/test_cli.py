"""Unit tests for the ``sre-harness gate`` CLI (Stage 2 — advisory).

The CLI is a thin, deterministic shell around :func:`evaluate_change`. It loads
a change request and a platform graph from files, runs the gate, prints the
verdict + rationale as JSON, and sets a CI-meaningful exit code:

    0 = proceed, 1 = block, 2 = require_human

These tests are written first (RED) and drive the implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sre_harness.cli import (
    EXIT_BLOCK,
    EXIT_PROCEED,
    EXIT_REQUIRE_HUMAN,
    EXIT_USAGE,
    main,
)

# --- fixtures ---------------------------------------------------------------

_GRAPH_ENTITIES = [
    {"kind": "StorageClass", "name": "silver", "cluster": "prod-eu-1"},
    {"kind": "StorageClass", "name": "silver", "cluster": "prod-us-1"},
    {"kind": "StorageClass", "name": "gold", "cluster": "prod-eu-1"},
]


def _write(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _graph_file(tmp_path: Path) -> Path:
    return _write(tmp_path / "graph.json", {"entities": _GRAPH_ENTITIES})


def _change_file(tmp_path: Path, **overrides: Any) -> Path:
    payload = {
        "service": "payments",
        "target_cluster_ids": ["prod-eu-1", "prod-us-1"],
        "required_storageclasses": ["gold"],
    }
    payload.update(overrides)
    return _write(tmp_path / "change.json", payload)


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any]]:
    code = main(argv)
    out = capsys.readouterr().out
    return code, json.loads(out)


# --- exit codes -------------------------------------------------------------


@pytest.mark.unit
class TestExitCodes:
    def test_proceed_exits_0(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        graph = _graph_file(tmp_path)
        change = _change_file(tmp_path, required_storageclasses=["silver"])
        code, doc = _run(["gate", "--change", str(change), "--graph", str(graph)], capsys)
        assert code == EXIT_PROCEED == 0
        assert doc["verdict"] == "proceed"

    def test_block_exits_1(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        graph = _graph_file(tmp_path)
        change = _change_file(tmp_path, required_storageclasses=["platinum"])
        code, doc = _run(["gate", "--change", str(change), "--graph", str(graph)], capsys)
        assert code == EXIT_BLOCK == 1
        assert doc["verdict"] == "block"

    def test_require_human_exits_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        graph = _graph_file(tmp_path)
        # gold present in prod-eu-1 only -> some-but-not-all -> require_human
        change = _change_file(tmp_path, required_storageclasses=["gold"])
        code, doc = _run(["gate", "--change", str(change), "--graph", str(graph)], capsys)
        assert code == EXIT_REQUIRE_HUMAN == 2
        assert doc["verdict"] == "require_human"


# --- JSON output shape ------------------------------------------------------


@pytest.mark.unit
class TestOutputShape:
    def test_emits_verdict_rationale_and_tiers(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        graph = _graph_file(tmp_path)
        change = _change_file(tmp_path, required_storageclasses=["gold"])
        _, doc = _run(["gate", "--change", str(change), "--graph", str(graph)], capsys)
        assert doc["service"] == "payments"
        assert "rationale" in doc
        assert doc["analysis_tier"] == "T1"
        assert doc["recommendation_tier"] == "T2"
        assert doc["advisory"] is True
        # evidence is serialized as sorted lists, not sets
        assert doc["missing_by_cluster"] == {"prod-us-1": ["gold"]}
        assert isinstance(doc["classes_absent_everywhere"], list)

    def test_tier_classification_wraps_verdict(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        graph = _graph_file(tmp_path)
        change = _change_file(tmp_path)
        _, doc = _run(["gate", "--change", str(change), "--graph", str(graph)], capsys)
        tier = doc["tier_classification"]
        assert tier["action"] == "change_validation_verdict"
        assert tier["tier"] == "T2"
        assert tier["off_plan"] is False

    def test_emits_per_check_results(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        graph = _graph_file(tmp_path)
        change = _change_file(tmp_path, required_storageclasses=["gold"])
        _, doc = _run(["gate", "--change", str(change), "--graph", str(graph)], capsys)
        checks = doc["check_results"]
        assert isinstance(checks, list)
        ids = {check["check_id"] for check in checks}
        assert ids == {"storageclass_present", "blast_radius", "namespace_present"}
        for check in checks:
            assert {"check_id", "verdict", "rationale", "evidence"} <= set(check)


# --- manifest / PR-diff parsing ---------------------------------------------


@pytest.mark.unit
class TestManifestParsing:
    def test_k8s_manifest_change_format(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        manifest = {
            "kind": "StatefulSet",
            "metadata": {"name": "payments", "labels": {"cluster": "prod-eu-1"}},
            "spec": {
                "volumeClaimTemplates": [
                    {"spec": {"storageClassName": "gold"}},
                    {"spec": {"storageClassName": "silver"}},
                ]
            },
        }
        change = _write(tmp_path / "manifest.json", manifest)
        graph = _graph_file(tmp_path)
        code, doc = _run(
            [
                "gate",
                "--change",
                str(change),
                "--change-format",
                "k8s",
                "--graph",
                str(graph),
            ],
            capsys,
        )
        assert doc["service"] == "payments"
        assert set(doc["required_storageclasses"]) == {"gold", "silver"}
        # label scopes the target to prod-eu-1, which has both gold and silver.
        assert doc["target_cluster_ids"] == ["prod-eu-1"]
        assert code == EXIT_PROCEED

    def test_k8s_manifest_needs_explicit_clusters_when_absent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        manifest = {
            "kind": "StatefulSet",
            "metadata": {"name": "payments"},
            "spec": {"volumeClaimTemplates": [{"spec": {"storageClassName": "gold"}}]},
        }
        change = _write(tmp_path / "manifest.json", manifest)
        graph = _graph_file(tmp_path)
        code, doc = _run(
            [
                "gate",
                "--change",
                str(change),
                "--change-format",
                "k8s",
                "--target-cluster",
                "prod-eu-1",
                "--target-cluster",
                "prod-us-1",
                "--graph",
                str(graph),
            ],
            capsys,
        )
        assert doc["target_cluster_ids"] == ["prod-eu-1", "prod-us-1"]
        assert code == EXIT_REQUIRE_HUMAN


# --- error handling ---------------------------------------------------------


@pytest.mark.unit
class TestErrors:
    def test_missing_change_file_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        graph = _graph_file(tmp_path)
        code = main(["gate", "--change", str(tmp_path / "nope.json"), "--graph", str(graph)])
        assert code == 2  # usage error
        assert "nope.json" in capsys.readouterr().err

    def test_invalid_change_payload_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        graph = _graph_file(tmp_path)
        change = _write(tmp_path / "bad.json", {"service": "payments"})
        code = main(["gate", "--change", str(change), "--graph", str(graph)])
        assert code == 2
        assert "required" in capsys.readouterr().err.lower()

    def test_unknown_subcommand_errors(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main(["frobnicate"])

    def test_no_subcommand_prints_help_and_exits_2(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main([])
        assert code == EXIT_USAGE
        assert "usage" in capsys.readouterr().err.lower()

    def test_invalid_json_change_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        graph = _graph_file(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        code = main(["gate", "--change", str(bad), "--graph", str(graph)])
        assert code == EXIT_USAGE
        assert "not valid json" in capsys.readouterr().err.lower()

    def test_graph_fixture_not_object_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        change = _change_file(tmp_path)
        graph = _write(tmp_path / "graph.json", ["not", "an", "object"])
        code = main(["gate", "--change", str(change), "--graph", str(graph)])
        assert code == EXIT_USAGE
        assert "graph fixture" in capsys.readouterr().err.lower()

    def test_graph_entity_missing_fields_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        change = _change_file(tmp_path)
        graph = _write(tmp_path / "graph.json", {"entities": [{"kind": "StorageClass"}]})
        code = main(["gate", "--change", str(change), "--graph", str(graph)])
        assert code == EXIT_USAGE
        assert "entity" in capsys.readouterr().err.lower()

    def test_graph_entities_not_a_list_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        change = _change_file(tmp_path)
        graph = _write(tmp_path / "graph.json", {"entities": "nope"})
        code = main(["gate", "--change", str(change), "--graph", str(graph)])
        assert code == EXIT_USAGE
        assert "list" in capsys.readouterr().err.lower()

    def test_k8s_payload_not_object_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        change = _write(tmp_path / "manifest.json", ["not", "an", "object"])
        graph = _graph_file(tmp_path)
        code = main(
            ["gate", "--change", str(change), "--change-format", "k8s", "--graph", str(graph)]
        )
        assert code == EXIT_USAGE
        assert "k8s manifest" in capsys.readouterr().err.lower()


@pytest.mark.unit
class TestPrDiffFormat:
    def test_pr_diff_change_format(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        diff = "+++ b/k8s/orders.yaml\n+      storageClassName: gold\n"
        change = _write(tmp_path / "diff.json", diff)
        graph = _graph_file(tmp_path)
        code, doc = _run(
            [
                "gate",
                "--change",
                str(change),
                "--change-format",
                "pr-diff",
                "--service",
                "orders",
                "--target-cluster",
                "prod-eu-1",
                "--target-cluster",
                "prod-us-1",
                "--graph",
                str(graph),
            ],
            capsys,
        )
        assert doc["service"] == "orders"
        assert doc["required_storageclasses"] == ["gold"]
        # gold present in prod-eu-1 only -> require_human
        assert code == EXIT_REQUIRE_HUMAN

    def test_pr_diff_non_string_payload_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        change = _write(tmp_path / "diff.json", {"not": "a string"})
        graph = _graph_file(tmp_path)
        code = main(
            [
                "gate",
                "--change",
                str(change),
                "--change-format",
                "pr-diff",
                "--service",
                "orders",
                "--target-cluster",
                "prod-eu-1",
                "--graph",
                str(graph),
            ]
        )
        assert code == EXIT_USAGE
        assert "pr-diff" in capsys.readouterr().err.lower()
