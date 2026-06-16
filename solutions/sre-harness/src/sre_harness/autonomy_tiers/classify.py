"""Classify an action into an autonomy tier, degrading on low confidence."""

from __future__ import annotations

from sre_harness.autonomy_tiers.action_table import ACTION_TIER_TABLE
from sre_harness.autonomy_tiers.tiers import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    Tier,
    TierClassification,
)


def classify(
    action: str,
    confidence: float,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> TierClassification:
    """Classify ``action`` into a tier given the agent's ``confidence``.

    - An unknown / off-plan action resolves to the safest tier.
    - A known action keeps its mapped tier when ``confidence >= threshold``.
    - Otherwise it degrades one tier toward more human control.

    Degradation never moves a tier *up* (toward more autonomy).
    """
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"confidence must be in [0.0, 1.0], got {confidence}")

    if action not in ACTION_TIER_TABLE:
        safest = Tier.safest()
        return TierClassification(
            tier=safest,
            base_tier=safest,
            degraded=False,
            off_plan=True,
            rationale=(
                f"Action {action!r} is off-plan (absent from the action-tier "
                f"table); resolved to the safest tier {safest.name}."
            ),
        )

    base_tier = ACTION_TIER_TABLE[action]

    if confidence >= threshold:
        return TierClassification(
            tier=base_tier,
            base_tier=base_tier,
            degraded=False,
            off_plan=False,
            rationale=(
                f"Action {action!r} at confidence {confidence:.2f} "
                f"(>= threshold {threshold:.2f}) keeps tier {base_tier.name}."
            ),
        )

    degraded_tier = base_tier.degraded()
    return TierClassification(
        tier=degraded_tier,
        base_tier=base_tier,
        degraded=degraded_tier != base_tier,
        off_plan=False,
        rationale=(
            f"Action {action!r} degraded {base_tier.name}->{degraded_tier.name}: "
            f"confidence {confidence:.2f} < threshold {threshold:.2f}."
        ),
    )


__all__ = ["classify"]
