"""Scenario / label format for the offline eval harness.

A :class:`Scenario` is one frozen, replayable label following the plan's
incident-replay shape ``{ground_truth, snapshot}`` (see
``docs/autonomous-sre-harness-plan.md`` Stage 0). A scenario carries:

- ``id``           : stable identifier (used in reports and regression diffs)
- ``kind``         : which target/check this scenario exercises
- ``snapshot``     : the world state needed to replay the scenario
- ``ground_truth`` : the expected outcome the target should produce

Today the only wired target is the deterministic change-validation gate, so the
snapshot is a :class:`GateSnapshot` (a platform-graph fixture + the
``ChangeRequest`` input) and the ground truth is the expected ``Verdict``. The
types stay deliberately general (``snapshot``/``ground_truth`` are ``object``)
so a later RCA scenario can carry a richer world (logs/metrics/deploys) and a
root-cause ground truth without changing this contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sre_harness.change_gate import ChangeRequest
from sre_harness.platform_graph import PlatformGraph


class ScenarioKind(Enum):
    """The class of scenario, i.e. which target/check it exercises.

    Only ``CHANGE_GATE`` is wired today. The remaining members mark the
    extension surface for the read-only triage / RCA stages of the plan; the
    eval format already accommodates them via the general ``snapshot`` /
    ``ground_truth`` fields.
    """

    CHANGE_GATE = "change_gate"
    TRIAGE = "triage"
    RCA = "rca"


@dataclass(frozen=True)
class GateSnapshot:
    """Replayable world for a change-validation-gate scenario.

    The platform graph is the world state; the change request is the input the
    gate evaluates against it. Both are already immutable, so the snapshot can
    be replayed deterministically any number of times.
    """

    graph: PlatformGraph
    request: ChangeRequest


@dataclass(frozen=True)
class Scenario:
    """One replayable eval label: ``{id, kind, snapshot, ground_truth}``."""

    id: str
    kind: ScenarioKind
    snapshot: object
    ground_truth: object

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("scenario id must not be blank")


__all__ = [
    "GateSnapshot",
    "Scenario",
    "ScenarioKind",
]
