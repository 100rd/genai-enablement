"""Seed scenario suite for the change-validation gate.

Code-fixture scenarios covering the gate's full verdict space — across all three
checks (StorageClass presence, blast-radius action classification, Namespace
presence) — against the in-memory platform graph. Keeping them as code (not a
data file) keeps the suite zero-dependency and refactor-safe while there is a
single target; a data-dir loader can replace :func:`load_seed_scenarios` later
without changing callers.
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
    actions: frozenset[str] = frozenset(),
    required_namespaces: frozenset[str] = frozenset(),
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
                actions=actions,
                required_namespaces=required_namespaces,
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
        # 6. Blast radius: an RDS failover escalates to a human (T3 action).
        _scenario(
            "gate-require-human-blast-radius-rds",
            entities=[
                Entity(kind="StorageClass", name="gold", cluster="prod-eu-1"),
                Entity(kind="StorageClass", name="gold", cluster="prod-us-1"),
            ],
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required={"gold"},
            actions=frozenset({"rds_failover"}),
            expected=Verdict.REQUIRE_HUMAN,
        ),
        # 7. Namespace absent in every target -> block.
        _scenario(
            "gate-block-namespace-absent-everywhere",
            entities=[
                Entity(kind="Namespace", name="staging", cluster="prod-eu-1"),
                Entity(kind="Namespace", name="staging", cluster="prod-us-1"),
            ],
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required=set(),
            required_namespaces=frozenset({"payments"}),
            expected=Verdict.BLOCK,
        ),
        # 8. Namespace present in some-but-not-all targets -> require human.
        _scenario(
            "gate-require-human-namespace-partial-coverage",
            entities=[
                Entity(kind="Namespace", name="payments", cluster="prod-eu-1"),
            ],
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required=set(),
            required_namespaces=frozenset({"payments"}),
            expected=Verdict.REQUIRE_HUMAN,
        ),
        # 9. Combined: namespace absent everywhere (block) dominates an RDS
        #    action (require_human) -> block.
        _scenario(
            "gate-block-namespace-dominates-blast-radius",
            entities=[
                Entity(kind="StorageClass", name="gold", cluster="prod-eu-1"),
                Entity(kind="StorageClass", name="gold", cluster="prod-us-1"),
            ],
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required={"gold"},
            actions=frozenset({"rds_failover"}),
            required_namespaces=frozenset({"payments"}),
            expected=Verdict.BLOCK,
        ),
        # 10. All three checks clean -> proceed (storageclass + namespace present,
        #     only low-tier autonomous action).
        _scenario(
            "gate-proceed-all-checks-clean",
            entities=[
                Entity(kind="StorageClass", name="gold", cluster="prod-eu-1"),
                Entity(kind="StorageClass", name="gold", cluster="prod-us-1"),
                Entity(kind="Namespace", name="payments", cluster="prod-eu-1"),
                Entity(kind="Namespace", name="payments", cluster="prod-us-1"),
            ],
            target_cluster_ids=["prod-eu-1", "prod-us-1"],
            required={"gold"},
            actions=frozenset({"restart_stateless_pod"}),
            required_namespaces=frozenset({"payments"}),
            expected=Verdict.PROCEED,
        ),
    )


__all__ = ["load_seed_scenarios"]
