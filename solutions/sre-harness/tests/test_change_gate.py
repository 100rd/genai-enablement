"""Unit tests for the change-validation gate (check #1: required StorageClass present).

This is the deterministic, rules-based verification tier (the strongest tier per
`research/2026-agentic-sre-refresh.md` §4). The gate never executes anything:
the *analysis* is T1 and emitting the *verdict* is T2 (advisory).

Verdict rules:
- proceed       : required ⊆ available in *every* target cluster
- block         : a required class is absent in *every* target cluster
- require_human : absent in some but not all target clusters
"""

import pytest

from sre_harness.autonomy_tiers import Tier
from sre_harness.change_gate import (
    ChangeRequest,
    Verdict,
    evaluate_change,
    parse_change_request,
)
from sre_harness.platform_graph import Entity, InMemoryPlatformGraph


def _graph() -> InMemoryPlatformGraph:
    return InMemoryPlatformGraph(
        entities=[
            Entity(kind="StorageClass", name="silver", cluster="prod-eu-1"),
            Entity(kind="StorageClass", name="silver", cluster="prod-us-1"),
            Entity(kind="StorageClass", name="gold", cluster="prod-eu-1"),
        ]
    )


@pytest.mark.unit
class TestCanonicalBlock:
    """The canonical test from the task spec (written first)."""

    def test_gold_required_no_cluster_has_it_blocks(self) -> None:
        graph = InMemoryPlatformGraph(
            entities=[
                Entity(kind="StorageClass", name="silver", cluster="prod-eu-1"),
                Entity(kind="StorageClass", name="silver", cluster="prod-us-1"),
            ]
        )
        request = ChangeRequest(
            service="payments",
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required_storageclasses={"gold"},
        )

        result = evaluate_change(request, graph)

        assert result.verdict is Verdict.BLOCK
        # Rationale names every target cluster that lacks the class.
        assert "prod-eu-1" in result.rationale
        assert "prod-us-1" in result.rationale
        assert "gold" in result.rationale


@pytest.mark.unit
class TestProceed:
    def test_present_in_all_targets_proceeds(self) -> None:
        graph = InMemoryPlatformGraph(
            entities=[
                Entity(kind="StorageClass", name="gold", cluster="prod-eu-1"),
                Entity(kind="StorageClass", name="gold", cluster="prod-us-1"),
            ]
        )
        request = ChangeRequest(
            service="payments",
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required_storageclasses={"gold"},
        )
        result = evaluate_change(request, graph)
        assert result.verdict is Verdict.PROCEED
        assert result.missing_by_cluster == {}


@pytest.mark.unit
class TestRequireHuman:
    def test_present_in_some_targets_requires_human(self) -> None:
        # gold exists in prod-eu-1 but not prod-us-1.
        request = ChangeRequest(
            service="payments",
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required_storageclasses={"gold"},
        )
        result = evaluate_change(request, _graph())
        assert result.verdict is Verdict.REQUIRE_HUMAN
        assert result.missing_by_cluster == {"prod-us-1": {"gold"}}
        assert "prod-us-1" in result.rationale
        assert "prod-eu-1" not in result.missing_by_cluster


@pytest.mark.unit
class TestMultipleRequiredClasses:
    def test_block_only_when_class_absent_in_every_target(self) -> None:
        # "gold" present in prod-eu-1 only; "platinum" present nowhere.
        request = ChangeRequest(
            service="payments",
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required_storageclasses={"gold", "platinum"},
        )
        result = evaluate_change(request, _graph())
        # platinum is absent everywhere -> block dominates.
        assert result.verdict is Verdict.BLOCK
        assert result.classes_absent_everywhere == {"platinum"}


@pytest.mark.unit
class TestTierWrapping:
    def test_analysis_is_t1_and_verdict_is_t2(self) -> None:
        request = ChangeRequest(
            service="payments",
            target_cluster_ids=["prod-eu-1"],
            required_storageclasses={"gold"},
        )
        result = evaluate_change(request, _graph())
        assert result.analysis_tier is Tier.T1
        assert result.recommendation_tier is Tier.T2


@pytest.mark.unit
class TestValidation:
    def test_empty_target_clusters_rejected(self) -> None:
        with pytest.raises(ValueError):
            ChangeRequest(
                service="payments",
                target_cluster_ids=[],
                required_storageclasses={"gold"},
            )

    def test_no_required_classes_proceeds_trivially(self) -> None:
        request = ChangeRequest(
            service="payments",
            target_cluster_ids=["prod-eu-1"],
            required_storageclasses=set(),
        )
        result = evaluate_change(request, _graph())
        assert result.verdict is Verdict.PROCEED


@pytest.mark.unit
class TestParserStub:
    def test_parse_structured_payload(self) -> None:
        payload = {
            "service": "payments",
            "target_cluster_ids": ["prod-eu-1", "prod-us-1"],
            "required_storageclasses": ["gold"],
        }
        request = parse_change_request(payload)
        assert request.service == "payments"
        assert request.target_cluster_ids == ["prod-eu-1", "prod-us-1"]
        assert request.required_storageclasses == {"gold"}

    def test_parse_missing_field_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_change_request({"service": "payments"})
