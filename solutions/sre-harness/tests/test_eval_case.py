"""Unit tests for the eval scenario/label format.

A scenario is a frozen, replayable label: ``{id, kind, snapshot, ground_truth}``.
For the change-validation gate the snapshot is a ``GateSnapshot`` (a platform-graph
fixture plus the ``ChangeRequest`` input) and the ground truth is the expected
``Verdict``. The format must stay general enough to later carry richer worlds
(logs/metrics/deploys) and RCA ground truth.
"""

import dataclasses

import pytest

from sre_harness.change_gate import ChangeRequest, Verdict
from sre_harness.eval import GateSnapshot, Scenario, ScenarioKind
from sre_harness.platform_graph import Entity, InMemoryPlatformGraph


def _gate_snapshot() -> GateSnapshot:
    graph = InMemoryPlatformGraph(
        entities=[Entity(kind="StorageClass", name="gold", cluster="prod-eu-1")]
    )
    request = ChangeRequest(
        service="payments",
        target_cluster_ids=["prod-eu-1"],
        required_storageclasses={"gold"},
    )
    return GateSnapshot(graph=graph, request=request)


@pytest.mark.unit
class TestScenario:
    def test_scenario_carries_id_kind_snapshot_and_ground_truth(self) -> None:
        scenario = Scenario(
            id="gate-proceed-basic",
            kind=ScenarioKind.CHANGE_GATE,
            snapshot=_gate_snapshot(),
            ground_truth=Verdict.PROCEED,
        )
        assert scenario.id == "gate-proceed-basic"
        assert scenario.kind is ScenarioKind.CHANGE_GATE
        assert scenario.ground_truth is Verdict.PROCEED
        assert isinstance(scenario.snapshot, GateSnapshot)

    def test_scenario_is_frozen(self) -> None:
        scenario = Scenario(
            id="x",
            kind=ScenarioKind.CHANGE_GATE,
            snapshot=_gate_snapshot(),
            ground_truth=Verdict.PROCEED,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            scenario.id = "y"  # type: ignore[misc]

    def test_blank_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            Scenario(
                id="  ",
                kind=ScenarioKind.CHANGE_GATE,
                snapshot=_gate_snapshot(),
                ground_truth=Verdict.PROCEED,
            )


@pytest.mark.unit
class TestGateSnapshot:
    def test_gate_snapshot_is_frozen(self) -> None:
        snapshot = _gate_snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            snapshot.request = snapshot.request  # type: ignore[misc]
