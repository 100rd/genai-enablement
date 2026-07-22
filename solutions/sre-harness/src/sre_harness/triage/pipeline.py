"""B1 gather -> analyze -> RCA nodes with a read-only analyzer seam."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Protocol

from sre_harness.observability import attributes as attrs
from sre_harness.observability import set_attributes, span
from sre_harness.triage.contracts import (
    MAX_GATHERED_EVIDENCE,
    AnalysisDraft,
    GatheredContext,
    IncidentSnapshot,
    RcaDraft,
    RootCause,
    TimelineEntry,
)


class ReadOnlyAnalyzer(Protocol):
    """The only model/rule surface the triage pipeline can invoke."""

    def analyze(self, context: GatheredContext) -> AnalysisDraft: ...


def gather_context(
    snapshot: IncidentSnapshot,
    *,
    lookback: timedelta = timedelta(minutes=30),
    max_items: int = MAX_GATHERED_EVIDENCE,
) -> GatheredContext:
    """Select a deterministic, service-local, temporally bounded evidence slice."""
    if type(snapshot) is not IncidentSnapshot:
        raise TypeError("gather_context requires an exact IncidentSnapshot")
    if lookback <= timedelta(0):
        raise ValueError("lookback must be positive")
    if not 1 <= max_items <= MAX_GATHERED_EVIDENCE:
        raise ValueError(f"max_items must be in [1, {MAX_GATHERED_EVIDENCE}], got {max_items}")

    lower_bound = snapshot.alert.started_at - lookback
    selected = sorted(
        (
            item
            for item in snapshot.evidence
            if item.service == snapshot.alert.service
            and lower_bound <= item.observed_at <= snapshot.captured_at
        ),
        key=lambda item: (item.observed_at, item.evidence_id),
    )
    if len(selected) > max_items:
        selected = selected[-max_items:]
    return GatheredContext(
        alert=snapshot.alert,
        as_of=snapshot.captured_at,
        evidence=tuple(selected),
    )


def analyze_context(
    context: GatheredContext,
    analyzer: ReadOnlyAnalyzer,
) -> AnalysisDraft:
    """Invoke only ``analyze`` and reject any provenance escape."""
    proposal = analyzer.analyze(context)
    if type(proposal) is not AnalysisDraft:
        raise TypeError("analyzer must return an exact AnalysisDraft")

    admitted = {item.evidence_id for item in context.evidence}
    cited = [evidence_id for claim in proposal.facts for evidence_id in claim.evidence_ids]
    cited.extend(
        evidence_id for hypothesis in proposal.hypotheses for evidence_id in hypothesis.evidence_ids
    )
    unknown = sorted(set(cited) - admitted)
    if unknown:
        raise ValueError("analysis cites unknown evidence: " + ", ".join(unknown))

    if any(
        hypothesis.cause is RootCause.UNDETERMINED
        and not hypothesis.evidence_ids
        and hypothesis.confidence != 0.0
        for hypothesis in proposal.hypotheses
    ):
        raise ValueError("an evidence-free hypothesis must have zero confidence")
    return proposal


def draft_rca(context: GatheredContext, analysis: AnalysisDraft) -> RcaDraft:
    """Materialise a review-only RCA draft from the admitted context and analysis."""
    hypotheses = tuple(
        sorted(
            analysis.hypotheses,
            key=lambda item: (-item.confidence, item.cause.value, item.summary),
        )
    )
    primary = hypotheses[0]
    timeline = tuple(
        TimelineEntry(
            observed_at=item.observed_at,
            statement=item.statement,
            evidence_id=item.evidence_id,
        )
        for item in context.evidence
    )
    return RcaDraft(
        incident_id=context.alert.incident_id,
        service=context.alert.service,
        as_of=context.as_of,
        timeline=timeline,
        facts=analysis.facts,
        hypotheses=hypotheses,
        primary_cause=primary.cause,
        overall_confidence=primary.confidence,
        unresolved_questions=analysis.unresolved_questions,
        evidence_ids=tuple(item.evidence_id for item in context.evidence),
    )


def run_triage(
    snapshot: IncidentSnapshot,
    *,
    analyzer: ReadOnlyAnalyzer | None = None,
) -> RcaDraft:
    """Run the bounded B1 pipeline; no node can execute or recommend an action."""
    if type(snapshot) is not IncidentSnapshot:
        raise TypeError("run_triage requires an exact IncidentSnapshot")
    if analyzer is None:
        from sre_harness.triage.rules import DeterministicTriageAnalyzer

        analyzer = DeterministicTriageAnalyzer()
    with span(
        "triage.run",
        {
            attrs.TRIAGE_INCIDENT_ID: snapshot.alert.incident_id,
            attrs.TRIAGE_SERVICE: snapshot.alert.service,
            attrs.TRIAGE_ANALYSIS_TIER: "T1",
        },
        service="sre-harness",
    ) as run_span:
        with span("triage.gather"):
            context = gather_context(snapshot)
        with span("triage.analyze"):
            analysis = analyze_context(context, analyzer)
        with span("triage.draft"):
            report = draft_rca(context, analysis)
        set_attributes(
            run_span,
            {
                attrs.TRIAGE_EVIDENCE_COUNT: len(context.evidence),
                attrs.TRIAGE_ROOT_CAUSE: report.primary_cause.value,
                attrs.TRIAGE_CONFIDENCE: report.overall_confidence,
            },
        )
    return report


__all__: Sequence[str] = (
    "ReadOnlyAnalyzer",
    "analyze_context",
    "draft_rca",
    "gather_context",
    "run_triage",
)
