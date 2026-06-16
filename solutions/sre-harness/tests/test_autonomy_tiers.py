"""Unit tests for the autonomy-tier engine.

These tests are written first (TDD). They pin the safety-critical behaviour
described in `docs/autonomous-sre-harness-plan.md` §3:

- A pre-approved action keeps its mapped tier when confidence is high.
- An action degrades *down* (toward more human control) on low confidence.
- An unknown / off-plan action resolves to the safest tier.
- Degradation never moves a tier *up* (toward more autonomy).
"""

import pytest

from sre_harness.autonomy_tiers import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    Tier,
    TierClassification,
    classify,
)
from sre_harness.autonomy_tiers.action_table import ACTION_TIER_TABLE


@pytest.mark.unit
class TestTierOrdering:
    def test_tiers_are_ordered_t1_most_human_controlled(self) -> None:
        # T1 (read-only) is the safest / most human-controlled tier.
        assert Tier.T1 < Tier.T2 < Tier.T3 < Tier.T4

    def test_safest_is_t1(self) -> None:
        assert Tier.safest() is Tier.T1

    def test_degrade_moves_toward_more_human_control(self) -> None:
        assert Tier.T4.degraded() is Tier.T3
        assert Tier.T3.degraded() is Tier.T2
        assert Tier.T2.degraded() is Tier.T1

    def test_degrade_floors_at_t1(self) -> None:
        assert Tier.T1.degraded() is Tier.T1


@pytest.mark.unit
class TestActionTable:
    def test_seeded_from_plan(self) -> None:
        # Spot-check entries seeded from the plan's action-tier table (§3).
        assert ACTION_TIER_TABLE["query_logs"] is Tier.T1
        assert ACTION_TIER_TABLE["draft_rca"] is Tier.T1
        assert ACTION_TIER_TABLE["restart_stateless_pod"] is Tier.T4
        assert ACTION_TIER_TABLE["scale_stateless_service"] is Tier.T4
        assert ACTION_TIER_TABLE["config_change_prod"] is Tier.T3
        assert ACTION_TIER_TABLE["rds_failover"] is Tier.T3


@pytest.mark.unit
class TestClassify:
    def test_high_confidence_known_action_keeps_tier(self) -> None:
        result = classify("restart_stateless_pod", confidence=0.95)
        assert isinstance(result, TierClassification)
        assert result.tier is Tier.T4
        assert result.base_tier is Tier.T4
        assert result.degraded is False
        assert result.off_plan is False

    def test_low_confidence_degrades_one_tier(self) -> None:
        result = classify("restart_stateless_pod", confidence=0.40)
        assert result.base_tier is Tier.T4
        assert result.tier is Tier.T3
        assert result.degraded is True
        assert "confidence" in result.rationale.lower()

    def test_low_confidence_on_t1_stays_t1(self) -> None:
        result = classify("query_logs", confidence=0.10)
        assert result.tier is Tier.T1
        assert result.base_tier is Tier.T1

    def test_unknown_action_is_off_plan_and_safest_tier(self) -> None:
        result = classify("delete_production_database", confidence=0.99)
        assert result.off_plan is True
        assert result.tier is Tier.safest()
        assert result.tier is Tier.T1
        assert "off-plan" in result.rationale.lower()

    def test_threshold_is_inclusive_lower_bound(self) -> None:
        # Confidence exactly at the threshold is considered confident enough.
        result = classify("scale_stateless_service", confidence=DEFAULT_CONFIDENCE_THRESHOLD)
        assert result.degraded is False
        assert result.tier is Tier.T4

    def test_just_below_threshold_degrades(self) -> None:
        result = classify(
            "scale_stateless_service",
            confidence=DEFAULT_CONFIDENCE_THRESHOLD - 0.01,
        )
        assert result.degraded is True
        assert result.tier is Tier.T3

    def test_custom_threshold_respected(self) -> None:
        result = classify("scale_stateless_service", confidence=0.80, threshold=0.90)
        assert result.degraded is True

    def test_confidence_out_of_range_rejected(self) -> None:
        with pytest.raises(ValueError):
            classify("query_logs", confidence=1.5)
        with pytest.raises(ValueError):
            classify("query_logs", confidence=-0.1)

    def test_result_is_immutable(self) -> None:
        result = classify("query_logs", confidence=0.9)
        with pytest.raises(Exception):
            result.tier = Tier.T4  # type: ignore[misc]
