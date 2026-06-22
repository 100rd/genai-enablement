"""Scoring for the offline eval harness.

What is scored *now*: **Pass@1** — did the target produce the correct verdict on
its single attempt (:func:`pass_at_1`)? That is the only honest measure available
while the wired target is the deterministic change-validation gate.

Extension surface (declared, not faked): the plan calls for ``Pass@k`` /
trajectory / depth / signal-surfacing scoring once there is a stochastic,
multi-step agent target to measure (Stage 1+). Those kinds are enumerated on
:class:`ScoreKind` and share the :class:`Score` shape, but their scorers are not
implemented — :func:`score_not_implemented` raises rather than fabricate a
number. Replace it with real scorers when the trajectory/sample data exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sre_harness.change_gate import Verdict


class ScoreKind(Enum):
    """The metric a :class:`Score` represents.

    ``PASS_AT_1`` is implemented. The rest are the documented extension points
    for richer agent evaluation; see :func:`score_not_implemented`.
    """

    PASS_AT_1 = "pass_at_1"
    PASS_AT_K = "pass_at_k"
    TRAJECTORY = "trajectory"
    DEPTH = "depth"
    SIGNAL_SURFACING = "signal_surfacing"


@dataclass(frozen=True)
class Score:
    """A single metric outcome in the unit interval.

    ``value`` is normalised to ``[0.0, 1.0]`` so heterogeneous metrics aggregate
    uniformly; ``passed`` is the boolean view used for Pass-rate roll-ups.
    """

    kind: ScoreKind
    value: float
    passed: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"score value must be in [0.0, 1.0], got {self.value}")


def pass_at_1(*, expected: Verdict, actual: Verdict) -> Score:
    """Score a single-attempt verdict: 1.0 iff ``actual`` matches ``expected``."""
    correct = actual is expected
    return Score(
        kind=ScoreKind.PASS_AT_1,
        value=1.0 if correct else 0.0,
        passed=correct,
    )


def score_not_implemented(kind: ScoreKind) -> Score:
    """Extension-point stub for the not-yet-implemented score kinds.

    Raises rather than returning a placeholder so the harness never reports a
    fabricated number. Wire a real scorer here (per ``kind``) when there is a
    stochastic, multi-step target and trajectory/sample data to score against.
    """
    raise NotImplementedError(
        f"scorer for {kind.value!r} is not implemented yet; "
        "Pass@1 is the only scored metric while the target is the deterministic gate"
    )


__all__ = [
    "Score",
    "ScoreKind",
    "pass_at_1",
    "score_not_implemented",
]
