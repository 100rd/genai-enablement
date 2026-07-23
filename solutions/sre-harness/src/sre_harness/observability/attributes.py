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
- ``triage.*`` — B1 read-only gather/analyze/RCA provenance.
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

# --- read-only incident triage / RCA ---------------------------------------

#: Stable incident identifier for one triage run.
TRIAGE_INCIDENT_ID: Final = "sre_harness.triage.incident_id"
#: Service whose incident snapshot is being analyzed.
TRIAGE_SERVICE: Final = "sre_harness.triage.service"
#: Number of evidence items admitted by the bounded gather node.
TRIAGE_EVIDENCE_COUNT: Final = "sre_harness.triage.evidence_count"
#: Root-cause class selected for the RCA draft.
TRIAGE_ROOT_CAUSE: Final = "sre_harness.triage.root_cause"
#: Confidence of the primary hypothesis.
TRIAGE_CONFIDENCE: Final = "sre_harness.triage.confidence"
#: Autonomy tier of the pipeline; always T1 for this surface.
TRIAGE_ANALYSIS_TIER: Final = "sre_harness.triage.analysis_tier"

# --- Sentinel (continuous detection) ---------------------------------------

#: Number of detectors run in a Sentinel scan.
SENTINEL_DETECTOR_COUNT: Final = "sre_harness.sentinel.detector_count"
#: Number of findings emitted after dedup + ranking.
SENTINEL_FINDING_COUNT: Final = "sre_harness.sentinel.finding_count"
#: Number of findings suppressed as already-open (deduped away).
SENTINEL_SUPPRESSED_COUNT: Final = "sre_harness.sentinel.suppressed_count"
#: Autonomy tier of the (read-only) detection.
SENTINEL_DETECTION_TIER: Final = "sre_harness.sentinel.detection_tier"
#: Autonomy tier of the (advisory) finding/recommendation.
SENTINEL_RECOMMENDATION_TIER: Final = "sre_harness.sentinel.recommendation_tier"
#: Identifier of an individual detector (child span).
SENTINEL_DETECTOR_ID: Final = "sre_harness.sentinel.detector_id"
#: Number of findings a single detector produced (child span).
SENTINEL_DETECTOR_FINDING_COUNT: Final = "sre_harness.sentinel.detector_finding_count"

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
    "SENTINEL_DETECTION_TIER",
    "SENTINEL_DETECTOR_COUNT",
    "SENTINEL_DETECTOR_FINDING_COUNT",
    "SENTINEL_DETECTOR_ID",
    "SENTINEL_FINDING_COUNT",
    "SENTINEL_RECOMMENDATION_TIER",
    "SENTINEL_SUPPRESSED_COUNT",
    "SERVICE",
    "TRIAGE_ANALYSIS_TIER",
    "TRIAGE_CONFIDENCE",
    "TRIAGE_EVIDENCE_COUNT",
    "TRIAGE_INCIDENT_ID",
    "TRIAGE_ROOT_CAUSE",
    "TRIAGE_SERVICE",
]
