"""Unit tests for the Sentinel lead-time eval (scorer + replay runner)."""

from __future__ import annotations

import pytest

from sre_harness.eval.score import ScoreKind, lead_time
from sre_harness.sentinel.eval import LeadTimeScenario, run_sentinel_eval
from sre_harness.sentinel.scenarios import load_lead_time_scenarios
from sre_harness.sentinel.state import SaturationSample, SentinelState

# --- the lead_time scorer --------------------------------------------------


def test_firing_before_the_page_scores_proportional_lead() -> None:
    score = lead_time(paged_at_index=4, first_fire_index=2, horizon=6)

    assert score.kind is ScoreKind.LEAD_TIME
    assert score.passed
    assert score.value == pytest.approx(2 / 6)


def test_lead_beyond_horizon_is_capped_at_one() -> None:
    score = lead_time(paged_at_index=10, first_fire_index=0, horizon=4)

    assert score.value == 1.0
    assert score.passed


def test_firing_at_the_page_gives_no_lead() -> None:
    score = lead_time(paged_at_index=3, first_fire_index=3, horizon=6)

    assert not score.passed
    assert score.value == 0.0


def test_never_firing_on_an_incident_fails() -> None:
    score = lead_time(paged_at_index=3, first_fire_index=None, horizon=6)

    assert not score.passed


def test_clean_timeline_passes_when_silent() -> None:
    score = lead_time(paged_at_index=None, first_fire_index=None, horizon=6)

    assert score.passed
    assert score.value == 1.0


def test_clean_timeline_fails_on_a_false_positive() -> None:
    score = lead_time(paged_at_index=None, first_fire_index=1, horizon=6)

    assert not score.passed


def test_horizon_must_be_positive() -> None:
    with pytest.raises(ValueError, match="horizon must be > 0"):
        lead_time(paged_at_index=4, first_fire_index=2, horizon=0)


# --- the replay runner over the seed suite ---------------------------------


def test_seed_suite_all_passes() -> None:
    summary = run_sentinel_eval(load_lead_time_scenarios())

    assert summary.passed == summary.total
    assert summary.pass_rate == 1.0


def test_seed_suite_mean_lead_time_matches_fired_scenarios() -> None:
    summary = run_sentinel_eval(load_lead_time_scenarios())

    # Leads: disk-ramp=2, cert-countdown=2, new-signature=1, error-rate=2,
    # change-regression=2, config-state-drift=2;
    # clean scenarios never fire and are excluded from the mean.
    assert summary.mean_lead_time == pytest.approx((2 + 2 + 1 + 2 + 2 + 2) / 6)


def test_seed_suite_reports_explicit_early_detection_and_false_positive_metrics() -> None:
    summary = run_sentinel_eval(load_lead_time_scenarios())

    assert summary.incident_scenarios == 6
    assert summary.early_detections == 6
    assert summary.early_detection_rate == 1.0
    assert summary.clean_scenarios == 14
    assert summary.false_positives == 0
    assert summary.false_positive_rate == 0.0


def test_b7_error_rate_corpus_has_lead_and_three_distinct_clean_controls() -> None:
    scenarios = load_lead_time_scenarios()
    by_id = {scenario.id: scenario for scenario in scenarios}

    for scenario_id in (
        "clean-error-rate-stable-high-baseline",
        "clean-error-rate-low-volume-spike",
        "clean-error-rate-inside-slo-budget",
    ):
        scenario = by_id[scenario_id]
        assert scenario.paged_at_index is None
        assert scenario.expected_detector_id is None

    result_by_id = {result.scenario_id: result for result in run_sentinel_eval(scenarios).results}
    regression = result_by_id["error-rate-regression-before-page"]
    assert regression.first_fire_index == 2
    assert regression.lead == 2
    assert regression.score.passed


def test_b7_change_regression_has_lead_and_five_distinct_clean_controls() -> None:
    scenarios = load_lead_time_scenarios()
    by_id = {scenario.id: scenario for scenario in scenarios}

    for scenario_id in (
        "clean-change-regression-stable-high-baseline",
        "clean-change-regression-low-volume-spike",
        "clean-change-regression-inside-slo-budget",
        "clean-change-regression-expired-association",
        "clean-change-regression-intervening-deploy",
    ):
        scenario = by_id[scenario_id]
        assert scenario.paged_at_index is None
        assert scenario.expected_detector_id is None

    result_by_id = {result.scenario_id: result for result in run_sentinel_eval(scenarios).results}
    regression = result_by_id["change-induced-regression-before-page"]
    assert regression.first_fire_index == 2
    assert regression.lead == 2
    assert regression.score.passed


def test_b7_drift_has_lead_and_five_distinct_clean_controls() -> None:
    scenarios = load_lead_time_scenarios()
    by_id = {scenario.id: scenario for scenario in scenarios}

    for scenario_id in (
        "clean-drift-converged",
        "clean-drift-single-observation",
        "clean-drift-inside-grace",
        "clean-drift-missing-inside-grace",
        "clean-drift-desired-revision-reset",
    ):
        scenario = by_id[scenario_id]
        assert scenario.paged_at_index is None
        assert scenario.expected_detector_id is None

    result_by_id = {result.scenario_id: result for result in run_sentinel_eval(scenarios).results}
    drift = result_by_id["config-state-drift-before-page"]
    assert drift.first_fire_index == 2
    assert drift.lead == 2
    assert drift.score.passed


def test_runner_finds_the_earliest_fire_index() -> None:
    # Warn band (75%) first trips at index 2 of this ramp.
    timeline = tuple(
        SentinelState(
            saturation_samples=(
                SaturationSample(resource="pvc", kind="disk", used=level, capacity=100.0),
            )
        )
        for level in (50.0, 70.0, 80.0, 95.0)
    )
    scenario = LeadTimeScenario(
        id="ramp",
        timeline=timeline,
        paged_at_index=3,
        expected_detector_id="saturation_expiry",
        expected_kind="saturation",
    )

    (result,) = run_sentinel_eval([scenario]).results

    assert result.first_fire_index == 2
    assert result.lead == 1


def test_clean_scenario_that_actually_fires_is_a_false_positive() -> None:
    # A "clean" label (no incident) over a timeline that trips the critical band
    # must FAIL — this is the false-positive control working.
    noisy_timeline = (
        SentinelState(
            saturation_samples=(
                SaturationSample(resource="pvc", kind="disk", used=99.0, capacity=100.0),
            )
        ),
    )
    scenario = LeadTimeScenario(
        id="mislabelled-clean",
        timeline=noisy_timeline,
        paged_at_index=None,
        expected_detector_id=None,
    )

    summary = run_sentinel_eval([scenario])

    assert summary.passed == 0
    assert summary.clean_scenarios == 1
    assert summary.false_positives == 1
    assert summary.false_positive_rate == 1.0


def test_empty_scenarios_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one scenario"):
        run_sentinel_eval([])


def test_blank_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="scenario id must not be blank"):
        LeadTimeScenario(
            id="  ",
            timeline=(SentinelState(),),
            paged_at_index=None,
            expected_detector_id=None,
        )


def test_empty_timeline_is_rejected() -> None:
    with pytest.raises(ValueError, match="timeline must not be empty"):
        LeadTimeScenario(
            id="x",
            timeline=(),
            paged_at_index=None,
            expected_detector_id=None,
        )


# --- the __main__ entrypoint -----------------------------------------------


def test_main_returns_zero_on_the_seed_suite() -> None:
    from sre_harness.sentinel.__main__ import main

    assert main([]) == 0
    assert main(["--verbose"]) == 0
