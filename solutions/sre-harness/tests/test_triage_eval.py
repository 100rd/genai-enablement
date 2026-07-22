"""B1 incident-replay scenarios run through the shared eval harness."""

from __future__ import annotations

from dataclasses import replace

import pytest

from sre_harness.eval import Scenario, ScenarioKind, run_eval
from sre_harness.triage import RcaDraft, RootCause, run_triage
from sre_harness.triage.eval import (
    CorpusProvenance,
    TriageEvalPolicy,
    TriageEvidenceScope,
    TriageGroundTruth,
    evaluate_triage_suite,
    load_triage_seed_scenarios,
    triage_pass_at_1,
    triage_target,
)


def _policy(**updates: object) -> TriageEvalPolicy:
    values: dict[str, object] = {
        "policy_id": "b1-candidate-thresholds-v1",
        "revision": "sha256:" + "a" * 64,
        "minimum_scenarios": 3,
        "minimum_per_cause": 1,
        "minimum_pass_rate": 1.0,
        "maximum_unknown_confidence": 0.25,
    }
    values.update(updates)
    return TriageEvalPolicy(**values)  # type: ignore[arg-type]


@pytest.mark.unit
class TestTriageEval:
    def test_seed_replays_cover_deploy_saturation_and_unknown(self) -> None:
        scenarios = load_triage_seed_scenarios()

        assert len(scenarios) >= 3
        assert len({scenario.id for scenario in scenarios}) == len(scenarios)
        assert {scenario.kind for scenario in scenarios} == {ScenarioKind.RCA}
        assert {scenario.ground_truth.primary_cause for scenario in scenarios} == {
            RootCause.DEPLOYMENT_REGRESSION,
            RootCause.RESOURCE_SATURATION,
            RootCause.UNDETERMINED,
        }
        assert {scenario.ground_truth.provenance for scenario in scenarios} == {
            CorpusProvenance.FIXTURE
        }

    def test_triage_pipeline_passes_its_seed_suite_through_shared_runner(self) -> None:
        scenarios = load_triage_seed_scenarios()
        summary = run_eval(scenarios, triage_target, scorer=triage_pass_at_1)

        assert summary.total == len(scenarios)
        assert summary.passed == summary.total
        assert summary.pass_rate == 1.0
        assert summary.pass_rate_by_kind == {ScenarioKind.RCA: 1.0}

    def test_wrong_root_cause_or_missing_required_citation_fails(self) -> None:
        scenario = load_triage_seed_scenarios()[0]
        actual = run_triage(scenario.snapshot)
        expected = scenario.ground_truth
        assert isinstance(expected, TriageGroundTruth)

        wrong_cause = TriageGroundTruth(
            primary_cause=RootCause.UNDETERMINED,
            required_evidence_ids=expected.required_evidence_ids,
            provenance=expected.provenance,
        )
        missing_citation = TriageGroundTruth(
            primary_cause=expected.primary_cause,
            required_evidence_ids=("not-cited",),
            provenance=expected.provenance,
        )

        assert not triage_pass_at_1(expected=wrong_cause, actual=actual).passed
        assert not triage_pass_at_1(expected=missing_citation, actual=actual).passed

    def test_target_rejects_non_rca_snapshot_instead_of_guessing(self) -> None:
        scenario = Scenario(
            id="wrong-snapshot",
            kind=ScenarioKind.RCA,
            snapshot=object(),
            ground_truth=TriageGroundTruth(
                primary_cause=RootCause.UNDETERMINED,
                required_evidence_ids=(),
                provenance=CorpusProvenance.FIXTURE,
            ),
        )

        with pytest.raises(TypeError, match="IncidentSnapshot"):
            triage_target(scenario)


@pytest.mark.unit
class TestTriageEvalAdmission:
    def test_perfect_fixture_suite_is_threshold_conformant_but_never_production_evidence(
        self,
    ) -> None:
        report = evaluate_triage_suite(
            load_triage_seed_scenarios(),
            triage_target,
            policy=_policy(),
        )

        assert report.summary.pass_rate == 1.0
        assert report.threshold_conformant is True
        assert report.evidence_scope is TriageEvidenceScope.FIXTURE_ONLY
        assert report.production_evidence_eligible is False
        assert report.production_evidence is None
        assert "fixture-corpus-not-production-evidence" in report.reasons
        assert "verified-corpus-publication-unconfigured" in report.reasons

    def test_absent_or_unmet_thresholds_fail_closed(self) -> None:
        scenarios = load_triage_seed_scenarios()

        unconfigured = evaluate_triage_suite(scenarios, triage_target, policy=None)
        too_few = evaluate_triage_suite(
            scenarios,
            triage_target,
            policy=_policy(minimum_scenarios=4),
        )
        missing_cause = evaluate_triage_suite(
            scenarios[:2],
            triage_target,
            policy=_policy(minimum_scenarios=2),
        )

        assert unconfigured.threshold_conformant is False
        assert "eval-thresholds-unconfigured" in unconfigured.reasons
        assert too_few.threshold_conformant is False
        assert "minimum-scenario-count-not-met" in too_few.reasons
        assert missing_cause.threshold_conformant is False
        assert "root-cause-coverage-incomplete" in missing_cause.reasons

    def test_pass_rate_duplicate_ids_and_unknown_overconfidence_are_reported(self) -> None:
        scenarios = load_triage_seed_scenarios()

        def always_unknown(scenario: Scenario) -> RcaDraft:
            actual = triage_target(scenario)
            if actual.primary_cause is RootCause.UNDETERMINED:
                return actual
            unknown = replace(
                actual.hypotheses[0],
                cause=RootCause.UNDETERMINED,
                summary="unsupported",
                confidence=0.1,
            )
            return replace(
                actual,
                hypotheses=(unknown,),
                primary_cause=RootCause.UNDETERMINED,
                overall_confidence=0.1,
            )

        def overconfident_unknown(scenario: Scenario) -> RcaDraft:
            actual = triage_target(scenario)
            if actual.primary_cause is not RootCause.UNDETERMINED:
                return actual
            hypothesis = replace(actual.hypotheses[0], confidence=0.9)
            return replace(
                actual,
                hypotheses=(hypothesis,),
                overall_confidence=0.9,
            )

        low_pass = evaluate_triage_suite(scenarios, always_unknown, policy=_policy())
        overconfident = evaluate_triage_suite(
            scenarios,
            overconfident_unknown,
            policy=_policy(),
        )
        duplicate = evaluate_triage_suite(
            (scenarios[0], replace(scenarios[1], id=scenarios[0].id), scenarios[2]),
            triage_target,
            policy=_policy(),
        )

        assert "minimum-pass-rate-not-met" in low_pass.reasons
        assert "unknown-confidence-ceiling-exceeded" in overconfident.reasons
        assert "duplicate-scenario-id" in duplicate.reasons
        assert not low_pass.threshold_conformant
        assert not overconfident.threshold_conformant
        assert not duplicate.threshold_conformant

    def test_even_candidate_curated_cases_need_external_publication(self) -> None:
        scenarios = tuple(
            replace(
                scenario,
                ground_truth=replace(
                    scenario.ground_truth,
                    provenance=CorpusProvenance.CURATED_REAL,
                ),
            )
            for scenario in load_triage_seed_scenarios()
        )

        report = evaluate_triage_suite(scenarios, triage_target, policy=_policy())

        assert report.threshold_conformant is True
        assert report.evidence_scope is TriageEvidenceScope.CANDIDATE_CURATED
        assert report.production_evidence_eligible is False
        assert report.reasons == ("verified-corpus-publication-unconfigured",)

    @pytest.mark.parametrize(
        ("updates", "reason"),
        [
            ({"policy_id": " "}, "policy id"),
            ({"revision": "main"}, "revision"),
            ({"minimum_scenarios": 0}, "minimum_scenarios"),
            ({"minimum_per_cause": 0}, "minimum_per_cause"),
            ({"minimum_pass_rate": 1.1}, "minimum_pass_rate"),
            ({"maximum_unknown_confidence": -0.1}, "maximum_unknown_confidence"),
        ],
    )
    def test_threshold_policy_is_closed_and_bounded(
        self,
        updates: dict[str, object],
        reason: str,
    ) -> None:
        with pytest.raises((TypeError, ValueError), match=reason):
            _policy(**updates)
