"""B1 read-only incident-triage and RCA pipeline contracts.

User journey: as an on-call engineer, I want a replayable T1 RCA draft from a
bounded incident snapshot so that facts, inferences, confidence, and provenance
are reviewable before any human decides whether to act.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta

import pytest

from sre_harness.autonomy_tiers import Tier
from sre_harness.triage import (
    AnalysisDraft,
    CitedClaim,
    EvidenceItem,
    EvidenceKind,
    Hypothesis,
    IncidentAlert,
    IncidentSnapshot,
    RootCause,
    gather_context,
    run_triage,
)

STARTED_AT = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
CAPTURED_AT = STARTED_AT + timedelta(minutes=20)


def _alert() -> IncidentAlert:
    return IncidentAlert(
        incident_id="inc-payments-001",
        service="payments-api",
        started_at=STARTED_AT,
        summary="Elevated checkout errors",
    )


def _evidence(
    evidence_id: str,
    kind: EvidenceKind,
    *,
    minute: int,
    value: float | None = None,
    service: str = "payments-api",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        kind=kind,
        service=service,
        observed_at=STARTED_AT + timedelta(minutes=minute),
        statement=f"observed {evidence_id}",
        value=value,
    )


def _snapshot(*evidence: EvidenceItem) -> IncidentSnapshot:
    return IncidentSnapshot(
        alert=_alert(),
        captured_at=CAPTURED_AT,
        evidence=tuple(evidence),
    )


@pytest.mark.unit
class TestTriageContracts:
    def test_contracts_require_timezone_aware_utc_and_bounded_values(self) -> None:
        with pytest.raises(ValueError, match="UTC"):
            IncidentAlert(
                incident_id="inc-1",
                service="payments-api",
                started_at=STARTED_AT.replace(tzinfo=None),
                summary="alert",
            )

        with pytest.raises(ValueError, match=r"\[0.0, 1.0\]"):
            _evidence("cpu", EvidenceKind.RESOURCE_SATURATION, minute=1, value=1.01)

    def test_snapshot_rejects_duplicate_or_future_evidence(self) -> None:
        duplicate = _evidence("same", EvidenceKind.LOG_SIGNATURE, minute=1)
        with pytest.raises(ValueError, match="unique"):
            _snapshot(duplicate, duplicate)

        future = _evidence("future", EvidenceKind.ERROR_RATE, minute=21, value=0.2)
        with pytest.raises(ValueError, match="after snapshot capture"):
            _snapshot(future)

    def test_snapshot_and_pipeline_reject_copied_invalid_inputs(self) -> None:
        with pytest.raises(TypeError, match="EvidenceItem"):
            IncidentSnapshot(
                alert=_alert(),
                captured_at=CAPTURED_AT,
                evidence=(object(),),  # type: ignore[arg-type]
            )

        with pytest.raises(TypeError, match="IncidentSnapshot"):
            run_triage(object())  # type: ignore[arg-type]

    def test_snapshot_and_evidence_are_immutable(self) -> None:
        evidence = _evidence("log", EvidenceKind.LOG_SIGNATURE, minute=1)
        snapshot = _snapshot(evidence)

        with pytest.raises(FrozenInstanceError):
            snapshot.captured_at = STARTED_AT  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            evidence.statement = "rewritten"  # type: ignore[misc]


@pytest.mark.unit
class TestGatherNode:
    def test_gather_is_bounded_to_service_time_window_and_stable_order(self) -> None:
        context = gather_context(
            _snapshot(
                _evidence("later", EvidenceKind.LOG_SIGNATURE, minute=5),
                _evidence(
                    "foreign", EvidenceKind.ERROR_RATE, minute=2, value=0.3, service="orders"
                ),
                _evidence("too-old", EvidenceKind.DEPLOYMENT, minute=-31),
                _evidence("earlier", EvidenceKind.DEPLOYMENT, minute=-5),
            ),
            lookback=timedelta(minutes=30),
        )

        assert tuple(item.evidence_id for item in context.evidence) == ("earlier", "later")
        assert context.as_of == CAPTURED_AT
        assert context.analysis_tier is Tier.T1

    def test_gather_rejects_non_positive_or_excessive_limits(self) -> None:
        snapshot = _snapshot()

        with pytest.raises(ValueError, match="max_items"):
            gather_context(snapshot, max_items=0)
        with pytest.raises(ValueError, match="max_items"):
            gather_context(snapshot, max_items=129)


@pytest.mark.unit
class TestAnalyzeAndRcaNodes:
    @pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf")])
    def test_invalid_hypothesis_confidence_fails_closed(self, confidence: float) -> None:
        with pytest.raises(ValueError, match="hypothesis confidence"):
            Hypothesis(
                cause=RootCause.UNDETERMINED,
                summary="unsupported",
                confidence=confidence,
                evidence_ids=(),
            )

    def test_deployment_regression_draft_separates_facts_from_inference(self) -> None:
        report = run_triage(
            _snapshot(
                _evidence("deploy-42", EvidenceKind.DEPLOYMENT, minute=-4),
                _evidence("errors", EvidenceKind.ERROR_RATE, minute=2, value=0.18),
                _evidence("log", EvidenceKind.LOG_SIGNATURE, minute=3),
            )
        )

        assert report.primary_cause is RootCause.DEPLOYMENT_REGRESSION
        assert 0.8 <= report.overall_confidence <= 0.9
        assert report.analysis_tier is Tier.T1
        assert {claim.evidence_ids for claim in report.facts} == {
            ("deploy-42",),
            ("errors",),
            ("log",),
        }
        assert report.hypotheses[0].evidence_ids == ("deploy-42", "errors")
        assert tuple(entry.evidence_id for entry in report.timeline) == (
            "deploy-42",
            "errors",
            "log",
        )
        assert report.evidence_ids == ("deploy-42", "errors", "log")
        assert not hasattr(report, "actions")
        assert not hasattr(report, "remediation")

    def test_resource_saturation_and_unknown_cases_are_calibrated(self) -> None:
        saturated = run_triage(
            _snapshot(
                _evidence("cpu", EvidenceKind.RESOURCE_SATURATION, minute=1, value=0.96),
                _evidence("latency", EvidenceKind.LOG_SIGNATURE, minute=2),
            )
        )
        unknown = run_triage(_snapshot(_evidence("log-only", EvidenceKind.LOG_SIGNATURE, minute=1)))

        assert saturated.primary_cause is RootCause.RESOURCE_SATURATION
        assert 0.75 <= saturated.overall_confidence <= 0.85
        assert saturated.hypotheses[0].evidence_ids == ("cpu",)
        assert unknown.primary_cause is RootCause.UNDETERMINED
        assert unknown.overall_confidence <= 0.25
        assert unknown.unresolved_questions

    def test_empty_context_stays_explicitly_unknown_instead_of_fabricating_evidence(self) -> None:
        report = run_triage(_snapshot())

        assert report.primary_cause is RootCause.UNDETERMINED
        assert report.overall_confidence == 0.0
        assert report.facts == ()
        assert report.timeline == ()
        assert report.evidence_ids == ()
        assert report.hypotheses[0].evidence_ids == ()

    def test_rca_contract_exposes_no_authority_bearing_fields(self) -> None:
        report = run_triage(_snapshot())
        field_names = {field.name for field in fields(report)}

        assert report.analysis_tier is Tier.T1
        assert field_names.isdisjoint(
            {"action", "actions", "remediation", "credential", "approval", "execution"}
        )

    def test_analyzer_cannot_cite_evidence_outside_the_gathered_context(self) -> None:
        class ForeignCitationAnalyzer:
            def analyze(self, _context):
                return AnalysisDraft(
                    facts=(CitedClaim(text="fabricated fact", evidence_ids=("missing",)),),
                    hypotheses=(
                        Hypothesis(
                            cause=RootCause.UNDETERMINED,
                            summary="unknown",
                            confidence=0.1,
                            evidence_ids=("missing",),
                        ),
                    ),
                    unresolved_questions=("What evidence is missing?",),
                )

        with pytest.raises(ValueError, match="unknown evidence"):
            run_triage(
                _snapshot(_evidence("real", EvidenceKind.LOG_SIGNATURE, minute=1)),
                analyzer=ForeignCitationAnalyzer(),
            )

    def test_pipeline_calls_only_the_read_only_analyze_surface(self) -> None:
        class AnalyzerWithForbiddenWrite:
            executed = False

            def analyze(self, context):
                evidence_id = context.evidence[0].evidence_id
                return AnalysisDraft(
                    facts=(CitedClaim(text="observed", evidence_ids=(evidence_id,)),),
                    hypotheses=(
                        Hypothesis(
                            cause=RootCause.UNDETERMINED,
                            summary="insufficient evidence",
                            confidence=0.1,
                            evidence_ids=(evidence_id,),
                        ),
                    ),
                    unresolved_questions=("Need another signal",),
                )

            def execute(self) -> None:
                self.executed = True
                raise AssertionError("write/action surface must never be called")

        analyzer = AnalyzerWithForbiddenWrite()
        report = run_triage(
            _snapshot(_evidence("log", EvidenceKind.LOG_SIGNATURE, minute=1)),
            analyzer=analyzer,
        )

        assert report.primary_cause is RootCause.UNDETERMINED
        assert analyzer.executed is False
