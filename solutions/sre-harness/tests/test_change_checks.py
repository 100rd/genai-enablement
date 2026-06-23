"""Unit tests for the individual change-validation checks (Stage 2 — multi-check).

Each check is a pure callable ``(request, graph) -> CheckResult``. The gate runs a
list of them and aggregates (see ``test_change_gate.py``). These tests pin each
check in isolation. Written first (RED).

The three deterministic checks:

- ``storageclass_present`` — required StorageClass present in target clusters.
- ``blast_radius``         — any action mapped to T3 (or off-plan) escalates to human.
- ``namespace_present``    — required namespace present in target clusters.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from sre_harness.change_checks import (
    CheckResult,
    check_blast_radius,
    check_namespace_present,
    check_storageclass_present,
)
from sre_harness.change_gate import ChangeRequest, Verdict
from sre_harness.platform_graph import Entity, InMemoryPlatformGraph


def _graph() -> InMemoryPlatformGraph:
    return InMemoryPlatformGraph(
        entities=[
            Entity(kind="StorageClass", name="silver", cluster="prod-eu-1"),
            Entity(kind="StorageClass", name="silver", cluster="prod-us-1"),
            Entity(kind="StorageClass", name="gold", cluster="prod-eu-1"),
            Entity(kind="Namespace", name="payments", cluster="prod-eu-1"),
            Entity(kind="Namespace", name="payments", cluster="prod-us-1"),
            Entity(kind="Namespace", name="staging", cluster="prod-eu-1"),
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
class TestStorageClassCheck:
    def test_present_everywhere_proceeds(self) -> None:
        req = _request(required_storageclasses={"silver"})
        result = check_storageclass_present(req, _graph())
        assert isinstance(result, CheckResult)
        assert result.check_id == "storageclass_present"
        assert result.verdict is Verdict.PROCEED

    def test_absent_everywhere_blocks(self) -> None:
        req = _request(required_storageclasses={"platinum"})
        result = check_storageclass_present(req, _graph())
        assert result.verdict is Verdict.BLOCK
        assert "platinum" in result.rationale
        assert result.evidence["classes_absent_everywhere"] == ("platinum",)

    def test_partial_coverage_requires_human(self) -> None:
        req = _request(required_storageclasses={"gold"})  # gold only in prod-eu-1
        result = check_storageclass_present(req, _graph())
        assert result.verdict is Verdict.REQUIRE_HUMAN
        assert result.evidence["missing_by_cluster"] == {"prod-us-1": ("gold",)}

    def test_no_requirements_proceeds(self) -> None:
        result = check_storageclass_present(_request(), _graph())
        assert result.verdict is Verdict.PROCEED


@pytest.mark.unit
class TestBlastRadiusCheck:
    def test_no_actions_proceeds(self) -> None:
        result = check_blast_radius(_request(), _graph())
        assert result.check_id == "blast_radius"
        assert result.verdict is Verdict.PROCEED

    def test_t4_action_proceeds(self) -> None:
        req = _request(actions=frozenset({"restart_stateless_pod"}))
        result = check_blast_radius(req, _graph())
        assert result.verdict is Verdict.PROCEED

    def test_t3_action_requires_human(self) -> None:
        req = _request(actions=frozenset({"rds_failover"}))
        result = check_blast_radius(req, _graph())
        assert result.verdict is Verdict.REQUIRE_HUMAN
        assert "rds_failover" in result.rationale
        assert "T3" in result.rationale

    def test_iam_and_sg_changes_require_human(self) -> None:
        req = _request(actions=frozenset({"iam_change", "security_group_change"}))
        result = check_blast_radius(req, _graph())
        assert result.verdict is Verdict.REQUIRE_HUMAN
        assert "iam_change" in result.rationale
        assert "security_group_change" in result.rationale

    def test_off_plan_action_requires_human(self) -> None:
        req = _request(actions=frozenset({"delete_everything"}))
        result = check_blast_radius(req, _graph())
        assert result.verdict is Verdict.REQUIRE_HUMAN
        assert "delete_everything" in result.rationale
        assert "off-plan" in result.rationale.lower()

    def test_mixed_low_tier_actions_proceed(self) -> None:
        req = _request(actions=frozenset({"restart_stateless_pod", "scale_stateless_service"}))
        result = check_blast_radius(req, _graph())
        assert result.verdict is Verdict.PROCEED

    def test_escalating_actions_listed_with_tiers(self) -> None:
        req = _request(actions=frozenset({"rds_failover", "restart_stateless_pod"}))
        result = check_blast_radius(req, _graph())
        # Only the escalating action is named; the safe one is not the reason.
        assert result.verdict is Verdict.REQUIRE_HUMAN
        assert "rds_failover" in result.rationale
        assert tuple(result.evidence["escalating_actions"]) == ("rds_failover",)


@pytest.mark.unit
class TestNamespaceCheck:
    def test_no_requirements_proceeds(self) -> None:
        result = check_namespace_present(_request(), _graph())
        assert result.check_id == "namespace_present"
        assert result.verdict is Verdict.PROCEED

    def test_present_everywhere_proceeds(self) -> None:
        req = _request(required_namespaces=frozenset({"payments"}))
        result = check_namespace_present(req, _graph())
        assert result.verdict is Verdict.PROCEED

    def test_absent_everywhere_blocks(self) -> None:
        req = _request(required_namespaces=frozenset({"ghost"}))
        result = check_namespace_present(req, _graph())
        assert result.verdict is Verdict.BLOCK
        assert "ghost" in result.rationale
        assert result.evidence["namespaces_absent_everywhere"] == ("ghost",)

    def test_partial_coverage_requires_human(self) -> None:
        # "staging" exists only in prod-eu-1.
        req = _request(required_namespaces=frozenset({"staging"}))
        result = check_namespace_present(req, _graph())
        assert result.verdict is Verdict.REQUIRE_HUMAN
        assert result.evidence["missing_by_cluster"] == {"prod-us-1": ("staging",)}


@pytest.mark.unit
class TestCheckResultImmutability:
    def test_check_result_is_frozen(self) -> None:
        result = check_storageclass_present(_request(), _graph())
        with pytest.raises(FrozenInstanceError):
            result.verdict = Verdict.BLOCK  # type: ignore[misc]
