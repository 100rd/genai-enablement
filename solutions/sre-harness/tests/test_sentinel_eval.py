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

    # Leads: disk-ramp=2, cert-countdown=2, new-signature=1; the clean scenario
    # never fires and is excluded from the mean.
    assert summary.mean_lead_time == pytest.approx((2 + 2 + 1) / 3)


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
