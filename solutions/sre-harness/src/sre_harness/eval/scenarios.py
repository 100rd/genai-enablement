"""Seed scenario suite for the change-validation gate.

Five code-fixture scenarios that cover the gate's full verdict space against the
in-memory platform graph. Keeping them as code (not a data file) keeps the suite
zero-dependency and refactor-safe while there is a single target; a data-dir
loader can replace :func:`load_seed_scenarios` later without changing callers.
"""

from __future__ import annotations

from sre_harness.change_gate import ChangeRequest, Verdict
from sre_harness.eval.case import GateSnapshot, Scenario, ScenarioKind
from sre_harness.platform_graph import Entity, InMemoryPlatformGraph


def _scenario(
    scenario_id: str,
    *,
    entities: list[Entity],
    target_cluster_ids: list[str],
    required: set[str],
    expected: Verdict,
) -> Scenario:
    return Scenario(
        id=scenario_id,
        kind=ScenarioKind.CHANGE_GATE,
        snapshot=GateSnapshot(
            graph=InMemoryPlatformGraph(entities=entities),
            request=ChangeRequest(
                service="payments",
                target_cluster_ids=target_cluster_ids,
                required_storageclasses=required,
            ),
        ),
        ground_truth=expected,
    )


def load_seed_scenarios() -> tuple[Scenario, ...]:
    """Return the seed change-gate suite (deterministic order)."""
    return (
        # 1. Required class present in every target -> proceed.
        _scenario(
            "gate-proceed-present-everywhere",
            entities=[
                Entity(kind="StorageClass", name="gold", cluster="prod-eu-1"),
                Entity(kind="StorageClass", name="gold", cluster="prod-us-1"),
            ],
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required={"gold"},
            expected=Verdict.PROCEED,
        ),
        # 2. Empty required set -> proceed trivially.
        _scenario(
            "gate-proceed-no-requirements",
            entities=[Entity(kind="StorageClass", name="silver", cluster="prod-eu-1")],
            target_cluster_ids=["prod-eu-1"],
            required=set(),
            expected=Verdict.PROCEED,
        ),
        # 3. Required class absent in every target -> block.
        _scenario(
            "gate-block-absent-everywhere",
            entities=[
                Entity(kind="StorageClass", name="silver", cluster="prod-eu-1"),
                Entity(kind="StorageClass", name="silver", cluster="prod-us-1"),
            ],
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required={"gold"},
            expected=Verdict.BLOCK,
        ),
        # 4. Required class present in some but not all targets -> require human.
        _scenario(
            "gate-require-human-partial-coverage",
            entities=[
                Entity(kind="StorageClass", name="gold", cluster="prod-eu-1"),
                Entity(kind="StorageClass", name="silver", cluster="prod-us-1"),
            ],
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required={"gold"},
            expected=Verdict.REQUIRE_HUMAN,
        ),
        # 5. Multi-class: one absent everywhere -> block dominates require-human.
        _scenario(
            "gate-block-multiclass-one-absent-everywhere",
            entities=[
                Entity(kind="StorageClass", name="gold", cluster="prod-eu-1"),
                Entity(kind="StorageClass", name="silver", cluster="prod-us-1"),
            ],
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required={"gold", "platinum"},
            expected=Verdict.BLOCK,
        ),
    )


__all__ = ["load_seed_scenarios"]
