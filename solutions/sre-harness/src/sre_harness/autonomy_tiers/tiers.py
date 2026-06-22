"""Tier definitions and the classification result type."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

# Confidence at or above this keeps an action at its mapped tier; below it the
# action degrades one tier toward more human control.
DEFAULT_CONFIDENCE_THRESHOLD = 0.7


class Tier(IntEnum):
    """Autonomy tiers, ordered from most to least human-controlled.

    ``T1 < T2 < T3 < T4`` — a *lower* tier means *more* human control, so
    "degrading" an action moves its tier down.
    """

    T1 = 1  # read-only        — auto, no approval
    T2 = 2  # advised          — recommend; a human acts
    T3 = 3  # approved (HITL)  — execute only after explicit human approval
    T4 = 4  # autonomous (HOTL)— bounded, reversible action; human monitors

    @classmethod
    def safest(cls) -> Tier:
        """The most human-controlled (safest) tier."""
        return cls.T1

    def degraded(self) -> Tier:
        """Return the next tier toward more human control, floored at T1."""
        return Tier(max(self.value - 1, Tier.T1.value))


@dataclass(frozen=True)
class TierClassification:
    """The outcome of classifying an action.

    ``tier`` is the effective tier after any degradation; ``base_tier`` is the
    tier the action maps to before degradation.
    """

    tier: Tier
    base_tier: Tier
    degraded: bool
    off_plan: bool
    rationale: str
