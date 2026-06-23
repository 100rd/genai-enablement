"""Unit tests for the multi-check aggregation in ``evaluate_change`` (Stage 2).

The gate now runs a list of checks and aggregates their verdicts:

    block dominates -> else require_human if any -> else proceed.

``GateResult`` keeps its back-compat fields (verdict, rationale,
missing_by_cluster, classes_absent_everywhere, analysis_tier, recommendation_tier)
and gains ``check_results``. These tests pin the aggregation and the new fields.
Written first (RED).
"""

from __future__ import annotations

import pytest

from sre_harness.change_gate import ChangeRequest, GateResult, Verdict, evaluate_change
from sre_harness.platform_graph import Entity, InMemoryPlatformGraph


def _graph() -> InMemoryPlatformGraph:
    return InMemoryPlatformGraph(
        entities=[
            Entity(kind="StorageClass", name="gold", cluster="prod-eu-1"),
            Entity(kind="StorageClass", name="gold", cluster="prod-us-1"),
            Entity(kind="Namespace", name="payments", cluster="prod-eu-1"),
            Entity(kind="Namespace", name="payments", cluster="prod-us-1"),
        ]
    )


def _request(**overrides: object) -> ChangeRequest:
    payload: dict[str, object] = {
        "service": "payments",
        "target_cluster_ids": ["prod-eu-1", "prod-us-1"],
        "required_storageclasses": set(),
    }
    payload.update(overrides)
    return ChangeRequest(**payload)  # type: ignore[arg-type]


@pytest.mark.unit
class TestAggregation:
    def test_all_clean_proceeds(self) -> None:
        req = _request(
            required_storageclasses={"gold"},
            required_namespaces=frozenset({"payments"}),
            actions=frozenset({"restart_stateless_pod"}),
        )
        result = evaluate_change(req, _graph())
        assert result.verdict is Verdict.PROCEED

    def test_blast_radius_escalates_to_human(self) -> None:
        # StorageClass + namespace clean, but an RDS failover is in the change.
        req = _request(
            required_storageclasses={"gold"},
            required_namespaces=frozenset({"payments"}),
            actions=frozenset({"rds_failover"}),
        )
        result = evaluate_change(req, _graph())
        assert result.verdict is Verdict.REQUIRE_HUMAN
        assert "rds_failover" in result.rationale

    def test_block_dominates_require_human(self) -> None:
        # Namespace absent everywhere (block) AND an RDS action (require_human).
        req = _request(
            required_namespaces=frozenset({"ghost"}),
            actions=frozenset({"rds_failover"}),
        )
        result = evaluate_change(req, _graph())
        assert result.verdict is Verdict.BLOCK

    def test_missing_namespace_everywhere_blocks(self) -> None:
        req = _request(required_namespaces=frozenset({"ghost"}))
        result = evaluate_change(req, _graph())
        assert result.verdict is Verdict.BLOCK
        assert "ghost" in result.rationale


@pytest.mark.unit
class TestCheckResultsField:
    def test_gate_result_exposes_per_check_results(self) -> None:
        req = _request(required_storageclasses={"gold"})
        result = evaluate_change(req, _graph())
        assert isinstance(result, GateResult)
        ids = {check.check_id for check in result.check_results}
        assert ids == {"storageclass_present", "blast_radius", "namespace_present"}

    def test_combined_rationale_includes_each_check(self) -> None:
        req = _request(required_storageclasses={"gold"})
        result = evaluate_change(req, _graph())
        for check in result.check_results:
            assert check.check_id in result.rationale


@pytest.mark.unit
class TestBackCompatFields:
    def test_storageclass_fields_preserved(self) -> None:
        # Partial coverage on storageclass -> require_human, evidence preserved.
        graph = InMemoryPlatformGraph(
            entities=[Entity(kind="StorageClass", name="gold", cluster="prod-eu-1")]
        )
        req = _request(required_storageclasses={"gold"})
        result = evaluate_change(req, graph)
        assert result.verdict is Verdict.REQUIRE_HUMAN
        assert result.missing_by_cluster == {"prod-us-1": {"gold"}}

    def test_classes_absent_everywhere_preserved(self) -> None:
        graph = InMemoryPlatformGraph(
            entities=[Entity(kind="StorageClass", name="silver", cluster="prod-eu-1")]
        )
        req = _request(required_storageclasses={"gold"})
        result = evaluate_change(req, graph)
        assert result.verdict is Verdict.BLOCK
        assert result.classes_absent_everywhere == {"gold"}
