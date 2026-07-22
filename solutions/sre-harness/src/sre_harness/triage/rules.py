"""Deterministic seed analyzer for offline B1 incident replays.

This is intentionally a small regression oracle, not a claim of production RCA
intelligence. Live model/source adapters remain separate future work.
"""

from __future__ import annotations

from sre_harness.triage.contracts import (
    AnalysisDraft,
    CitedClaim,
    EvidenceItem,
    EvidenceKind,
    GatheredContext,
    Hypothesis,
    RootCause,
)


class DeterministicTriageAnalyzer:
    """Recognise two high-signal seed patterns and otherwise stay uncertain."""

    def analyze(self, context: GatheredContext) -> AnalysisDraft:
        facts = tuple(
            CitedClaim(text=item.statement, evidence_ids=(item.evidence_id,))
            for item in context.evidence
        )
        hypotheses = [
            hypothesis
            for hypothesis in (
                self._deployment_regression(context.evidence),
                self._resource_saturation(context.evidence),
            )
            if hypothesis is not None
        ]
        if not hypotheses:
            evidence_ids = tuple(item.evidence_id for item in context.evidence)
            hypotheses.append(
                Hypothesis(
                    cause=RootCause.UNDETERMINED,
                    summary="Available evidence does not identify a supported root cause",
                    confidence=0.1 if evidence_ids else 0.0,
                    evidence_ids=evidence_ids,
                )
            )

        unresolved = ("Which independent signal would falsify the primary hypothesis?",)
        if hypotheses[0].cause is RootCause.UNDETERMINED:
            unresolved = (
                "Which additional metric, trace, deploy, or dependency signal is required?",
            )
        return AnalysisDraft(
            facts=facts,
            hypotheses=tuple(hypotheses),
            unresolved_questions=unresolved,
        )

    @staticmethod
    def _deployment_regression(
        evidence: tuple[EvidenceItem, ...],
    ) -> Hypothesis | None:
        deployments = [item for item in evidence if item.kind is EvidenceKind.DEPLOYMENT]
        elevated_errors = [
            item
            for item in evidence
            if item.kind is EvidenceKind.ERROR_RATE
            and item.value is not None
            and item.value >= 0.05
        ]
        joined = [
            (deployment, error)
            for deployment in deployments
            for error in elevated_errors
            if deployment.observed_at <= error.observed_at
        ]
        if not joined:
            return None
        deployment, error = max(
            joined,
            key=lambda pair: (pair[0].observed_at, pair[1].observed_at),
        )
        return Hypothesis(
            cause=RootCause.DEPLOYMENT_REGRESSION,
            summary="An error-rate increase followed the latest observed deployment",
            confidence=0.85,
            evidence_ids=(deployment.evidence_id, error.evidence_id),
        )

    @staticmethod
    def _resource_saturation(
        evidence: tuple[EvidenceItem, ...],
    ) -> Hypothesis | None:
        saturated = [
            item
            for item in evidence
            if item.kind is EvidenceKind.RESOURCE_SATURATION
            and item.value is not None
            and item.value >= 0.9
        ]
        if not saturated:
            return None
        strongest = max(
            saturated,
            key=lambda item: (item.value or 0.0, item.observed_at, item.evidence_id),
        )
        return Hypothesis(
            cause=RootCause.RESOURCE_SATURATION,
            summary="A resource crossed the precommitted saturation threshold",
            confidence=0.8,
            evidence_ids=(strongest.evidence_id,),
        )


__all__ = ["DeterministicTriageAnalyzer"]
