"""Unit tests for the eval runner and seed-suite loader.

``run_eval(scenarios, target)`` replays each scenario through a target callable
and scores the outcome with Pass@1, producing per-scenario results and an
aggregate summary (overall pass rate + per-kind breakdown).
"""

import pytest

from sre_harness.change_gate import Verdict
from sre_harness.eval import (
    EvalResult,
    EvalSummary,
    Scenario,
    ScenarioKind,
    change_gate_target,
    load_seed_scenarios,
    run_eval,
)


@pytest.mark.unit
class TestChangeGateTarget:
    def test_target_replays_scenario_through_evaluate_change(self) -> None:
        scenarios = load_seed_scenarios()
        scenario = next(s for s in scenarios if s.ground_truth is Verdict.BLOCK)
        assert change_gate_target(scenario) is Verdict.BLOCK


@pytest.mark.unit
class TestRunEval:
    def test_perfect_target_passes_every_scenario(self) -> None:
        scenarios = load_seed_scenarios()
        summary = run_eval(scenarios, change_gate_target)
        assert isinstance(summary, EvalSummary)
        assert summary.total == len(scenarios)
        assert summary.passed == len(scenarios)
        assert summary.pass_rate == 1.0
        assert all(isinstance(r, EvalResult) for r in summary.results)
        assert all(r.score.passed for r in summary.results)

    def test_failing_target_is_reported_not_swallowed(self) -> None:
        scenarios = load_seed_scenarios()

        def always_proceed(_: Scenario) -> Verdict:
            return Verdict.PROCEED

        summary = run_eval(scenarios, always_proceed)
        # Some seed scenarios expect BLOCK / REQUIRE_HUMAN, so this target fails them.
        assert summary.passed < summary.total
        assert 0.0 <= summary.pass_rate < 1.0
        failed = [r for r in summary.results if not r.score.passed]
        assert failed
        assert all(r.actual is Verdict.PROCEED for r in failed)

    def test_per_kind_breakdown_present(self) -> None:
        scenarios = load_seed_scenarios()
        summary = run_eval(scenarios, change_gate_target)
        assert ScenarioKind.CHANGE_GATE in summary.pass_rate_by_kind
        assert summary.pass_rate_by_kind[ScenarioKind.CHANGE_GATE] == 1.0

    def test_empty_suite_rejected(self) -> None:
        with pytest.raises(ValueError):
            run_eval([], change_gate_target)


@pytest.mark.unit
class TestSeedScenarios:
    def test_seed_suite_covers_all_three_verdicts(self) -> None:
        scenarios = load_seed_scenarios()
        verdicts = {s.ground_truth for s in scenarios}
        assert {Verdict.PROCEED, Verdict.BLOCK, Verdict.REQUIRE_HUMAN} <= verdicts

    def test_seed_suite_has_unique_ids(self) -> None:
        scenarios = load_seed_scenarios()
        ids = [s.id for s in scenarios]
        assert len(ids) == len(set(ids))

    def test_seed_suite_has_at_least_three_scenarios(self) -> None:
        assert len(load_seed_scenarios()) >= 3
