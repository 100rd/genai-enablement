"""Stable span-attribute names for the SRE harness (AgentOps).

The OpenTelemetry **GenAI semantic conventions** (``gen_ai.*``) are still marked
*experimental* and have churned across releases. The plan calls AgentOps a
cross-cutting concern that must outlive that churn, so the harness defines its
**own** stable attribute names under the ``sre_harness.*`` namespace and sets
those on spans. The mapping to the (unstable) OTel GenAI names lives in
:mod:`sre_harness.observability.tracer` and is applied *internally only* — the
unstable names never leak into call sites.

Grouped by surface:

- ``gate.*``  — the change-validation gate (overall verdict + per-check).
- ``eval.*``  — the offline eval harness (suite + per-scenario).
- ``llm.*``   — token / cost scaffold for future LLM steps (triage / RCA). No
  LLM runs today, so these are defined but not yet emitted.
"""

from __future__ import annotations

from typing import Final

# --- common ----------------------------------------------------------------

#: Logical service/component a span belongs to.
SERVICE: Final = "sre_harness.service"

# --- change-validation gate ------------------------------------------------

#: Aggregate verdict of a gate run (``proceed`` / ``block`` / ``require_human``).
GATE_VERDICT: Final = "sre_harness.gate.verdict"
#: The service named in the evaluated change request.
GATE_SERVICE: Final = "sre_harness.gate.service"
#: Number of target clusters in the change request.
GATE_TARGET_CLUSTER_COUNT: Final = "sre_harness.gate.target_cluster_count"
#: Number of checks the gate ran.
GATE_CHECK_COUNT: Final = "sre_harness.gate.check_count"
#: Autonomy tier of the (read-only) analysis.
GATE_ANALYSIS_TIER: Final = "sre_harness.gate.analysis_tier"
#: Autonomy tier of the (advisory) recommendation/verdict.
GATE_RECOMMENDATION_TIER: Final = "sre_harness.gate.recommendation_tier"
#: Identifier of an individual check (child span).
GATE_CHECK_ID: Final = "sre_harness.gate.check_id"
#: Verdict of an individual check (child span).
GATE_CHECK_VERDICT: Final = "sre_harness.gate.check_verdict"

# --- offline eval harness --------------------------------------------------

#: Number of scenarios in the suite.
EVAL_SCENARIO_COUNT: Final = "sre_harness.eval.scenario_count"
#: Number of scenarios that passed.
EVAL_PASSED_COUNT: Final = "sre_harness.eval.passed_count"
#: Overall pass rate of the suite (0.0–1.0).
EVAL_PASS_RATE: Final = "sre_harness.eval.pass_rate"
#: Identifier of an individual scenario (child span).
EVAL_SCENARIO_ID: Final = "sre_harness.eval.scenario_id"
#: Kind of an individual scenario (child span).
EVAL_SCENARIO_KIND: Final = "sre_harness.eval.scenario_kind"
#: Whether the scenario passed (child span).
EVAL_SCORE_PASSED: Final = "sre_harness.eval.passed"
#: Numeric score value for the scenario (child span).
EVAL_SCORE: Final = "sre_harness.eval.score"

# --- LLM token / cost scaffold (future triage / RCA steps) -----------------

#: Input (prompt) tokens consumed by an LLM step.
LLM_INPUT_TOKENS: Final = "sre_harness.llm.input_tokens"
#: Output (completion) tokens produced by an LLM step.
LLM_OUTPUT_TOKENS: Final = "sre_harness.llm.output_tokens"
#: Estimated cost of an LLM step, in USD.
LLM_COST_USD: Final = "sre_harness.llm.cost_usd"
#: Model identifier used for an LLM step.
LLM_MODEL: Final = "sre_harness.llm.model"

#: Maps our stable names to the (experimental) OTel GenAI convention names.
#: **Internal only** (leading underscore, not in ``__all__``): applied where the
#: OTel name is safe/additive, never at call sites — this keeps the unstable
#: ``gen_ai.*`` strings contained. Kept deliberately small: only the genuinely
#: standardised GenAI fields. Consumed by ``tracer._with_genai_aliases``.
_GEN_AI_CONVENTION_ALIASES: Final[dict[str, str]] = {
    LLM_INPUT_TOKENS: "gen_ai.usage.input_tokens",
    LLM_OUTPUT_TOKENS: "gen_ai.usage.output_tokens",
    LLM_MODEL: "gen_ai.request.model",
}


__all__ = [
    "EVAL_PASSED_COUNT",
    "EVAL_PASS_RATE",
    "EVAL_SCENARIO_COUNT",
    "EVAL_SCENARIO_ID",
    "EVAL_SCENARIO_KIND",
    "EVAL_SCORE",
    "EVAL_SCORE_PASSED",
    "GATE_ANALYSIS_TIER",
    "GATE_CHECK_COUNT",
    "GATE_CHECK_ID",
    "GATE_CHECK_VERDICT",
    "GATE_RECOMMENDATION_TIER",
    "GATE_SERVICE",
    "GATE_TARGET_CLUSTER_COUNT",
    "GATE_VERDICT",
    "LLM_COST_USD",
    "LLM_INPUT_TOKENS",
    "LLM_MODEL",
    "LLM_OUTPUT_TOKENS",
    "SERVICE",
]
