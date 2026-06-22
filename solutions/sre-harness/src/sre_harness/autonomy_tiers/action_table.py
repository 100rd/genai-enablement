"""Action -> tier mapping.

Seeded from the action-tier table in ``docs/autonomous-sre-harness-plan.md``
Section 3. This is the governance artifact: every action an agent can take is
mapped to the tier that gates it. Actions absent from this table are treated as
*off-plan* and resolve to the safest tier.
"""

from __future__ import annotations

from sre_harness.autonomy_tiers.tiers import Tier

ACTION_TIER_TABLE: dict[str, Tier] = {
    # T1 — read-only
    "query_logs": Tier.T1,
    "query_metrics": Tier.T1,
    "query_traces": Tier.T1,
    "read_k8s_state": Tier.T1,
    "read_argocd_state": Tier.T1,
    "draft_rca": Tier.T1,
    "change_impact_analysis": Tier.T1,
    # T2 — advised (recommend; a human acts)
    "recommend_remediation": Tier.T2,
    "change_validation_verdict": Tier.T2,
    # T4 — autonomous (idempotent, reversible, low blast radius)
    "restart_stateless_pod": Tier.T4,
    "retrigger_argocd_sync": Tier.T4,
    "scale_stateless_service": Tier.T4,
    # T3 — approved (reversible-but-significant or high blast radius -> human)
    "config_change_prod": Tier.T3,
    "rds_failover": Tier.T3,
    "rds_param_change": Tier.T3,
    "iam_change": Tier.T3,
    "security_group_change": Tier.T3,
}

__all__ = ["ACTION_TIER_TABLE"]
