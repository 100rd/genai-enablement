"""Autonomy-tier engine.

Every agent action is classified into a tier (T1 read-only -> T4 autonomous).
Classification *degrades down* (toward more human control) on low confidence or
when an action is off-plan. See ``docs/autonomous-sre-harness-plan.md`` Section 3.
"""

from sre_harness.autonomy_tiers.classify import classify
from sre_harness.autonomy_tiers.tiers import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    Tier,
    TierClassification,
)

__all__ = [
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "Tier",
    "TierClassification",
    "classify",
]
