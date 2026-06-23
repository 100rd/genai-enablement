"""Eval runner: replay scenarios through a target and score the outcomes.

``run_eval(scenarios, target)`` maps each :class:`Scenario` through a ``target``
callable, scores the outcome with Pass@1 against the scenario's ground truth, and
aggregates per-scenario results into an :class:`EvalSummary` (overall pass rate +
per-kind breakdown). It is pure and offline — the only side effect is whatever
the target itself does, and the seed target (:func:`change_gate_target`) just
calls the deterministic gate.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sre_harness.change_gate import Verdict, evaluate_change
from sre_harness.eval.case import GateSnapshot, Scenario, ScenarioKind
from sre_harness.eval.score import Score, pass_at_1
from sre_harness.observability import attributes as attrs
from sre_harness.observability import set_attributes, span

# A target maps a scenario to the outcome under test. The seed target returns a
# ``Verdict``; later targets (triage/RCA) may return a different outcome type,
# which is why the scorer — not the runner — owns outcome interpretation.
Target = Callable[[Scenario], Verdict]


@dataclass(frozen=True)
class EvalResult:
    """The outcome of replaying and scoring one scenario."""

    scenario_id: str
    kind: ScenarioKind
    expected: Verdict
    actual: Verdict
    score: Score


@dataclass(frozen=True)
class EvalSummary:
    """Aggregate view over a run: pass rate overall and per scenario kind."""

    results: tuple[EvalResult, ...]
    total: int
    passed: int
    pass_rate: float
    pass_rate_by_kind: dict[ScenarioKind, float]


def change_gate_target(scenario: Scenario) -> Verdict:
    """Seed target: replay a change-gate scenario through ``evaluate_change``."""
    snapshot = scenario.snapshot
    if not isinstance(snapshot, GateSnapshot):
        raise TypeError(
            f"change_gate_target requires a GateSnapshot, got {type(snapshot).__name__}"
        )
    return evaluate_change(snapshot.request, snapshot.graph).verdict


def run_eval(scenarios: Sequence[Scenario], target: Target) -> EvalSummary:
    """Replay every scenario through ``target`` and score with Pass@1.

    Instrumented (AgentOps): an ``eval.suite`` span with a child ``eval.scenario``
    span per scenario. Tracing is no-op by default — behaviour is unchanged when
    no OTel provider is configured.
    """
    if not scenarios:
        raise ValueError("run_eval requires at least one scenario")

    with span(
        "eval.suite",
        {attrs.EVAL_SCENARIO_COUNT: len(scenarios)},
        service="sre-harness",
    ) as suite_span:
        results = tuple(_evaluate_one(scenario, target) for scenario in scenarios)
        passed = sum(1 for result in results if result.score.passed)
        total = len(results)
        pass_rate = passed / total
        set_attributes(
            suite_span,
            {attrs.EVAL_PASSED_COUNT: passed, attrs.EVAL_PASS_RATE: pass_rate},
        )

    return EvalSummary(
        results=results,
        total=total,
        passed=passed,
        pass_rate=pass_rate,
        pass_rate_by_kind=_pass_rate_by_kind(results),
    )


def _evaluate_one(scenario: Scenario, target: Target) -> EvalResult:
    expected = scenario.ground_truth
    if not isinstance(expected, Verdict):
        raise TypeError(
            f"scenario {scenario.id!r} ground_truth must be a Verdict, "
            f"got {type(expected).__name__}"
        )
    with span(
        "eval.scenario",
        {
            attrs.EVAL_SCENARIO_ID: scenario.id,
            attrs.EVAL_SCENARIO_KIND: scenario.kind.name,
        },
    ) as scenario_span:
        actual = target(scenario)
        score = pass_at_1(expected=expected, actual=actual)
        set_attributes(
            scenario_span,
            {attrs.EVAL_SCORE: score.value, attrs.EVAL_SCORE_PASSED: score.passed},
        )

    return EvalResult(
        scenario_id=scenario.id,
        kind=scenario.kind,
        expected=expected,
        actual=actual,
        score=score,
    )


def _pass_rate_by_kind(results: Sequence[EvalResult]) -> dict[ScenarioKind, float]:
    rates: dict[ScenarioKind, float] = {}
    for kind in {result.kind for result in results}:
        of_kind = [result for result in results if result.kind is kind]
        passed = sum(1 for result in of_kind if result.score.passed)
        rates[kind] = passed / len(of_kind)
    return rates


__all__ = [
    "EvalResult",
    "EvalSummary",
    "Target",
    "change_gate_target",
    "run_eval",
]
