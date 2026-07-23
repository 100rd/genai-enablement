"""Immutable contracts for B1 read-only incident triage and RCA drafting."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from sre_harness.autonomy_tiers import Tier

MAX_GATHERED_EVIDENCE = 128


def _text(value: str, field: str) -> None:
    if not value.strip():
        raise ValueError(f"{field} must not be blank")


def _utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be timezone-aware UTC")


def _unique(values: tuple[str, ...], field: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError(f"{field} must not contain blank values")
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique")


class EvidenceKind(Enum):
    """Normalised read-only signal types understood by the seed analyzer."""

    DEPLOYMENT = "deployment"
    ERROR_RATE = "error_rate"
    RESOURCE_SATURATION = "resource_saturation"
    LOG_SIGNATURE = "log_signature"
    DEPENDENCY_HEALTH = "dependency_health"
    TOPOLOGY = "topology"


class RootCause(Enum):
    """Bounded root-cause classes emitted by the deterministic seed analyzer."""

    DEPLOYMENT_REGRESSION = "deployment_regression"
    RESOURCE_SATURATION = "resource_saturation"
    UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class IncidentAlert:
    incident_id: str
    service: str
    started_at: datetime
    summary: str

    def __post_init__(self) -> None:
        _text(self.incident_id, "incident id")
        _text(self.service, "incident service")
        _text(self.summary, "incident summary")
        _utc(self.started_at, "incident started_at")


@dataclass(frozen=True)
class EvidenceItem:
    """One immutable cited observation; ``value`` is normalised to ``[0, 1]``."""

    evidence_id: str
    kind: EvidenceKind
    service: str
    observed_at: datetime
    statement: str
    value: float | None = None

    def __post_init__(self) -> None:
        _text(self.evidence_id, "evidence id")
        _text(self.service, "evidence service")
        _text(self.statement, "evidence statement")
        _utc(self.observed_at, "evidence observed_at")
        if not isinstance(self.kind, EvidenceKind):
            raise TypeError("evidence kind must be an EvidenceKind")
        if self.value is not None and (
            not math.isfinite(self.value) or not 0.0 <= self.value <= 1.0
        ):
            raise ValueError(f"evidence value must be in [0.0, 1.0], got {self.value}")


@dataclass(frozen=True)
class IncidentSnapshot:
    """Frozen replay input captured at one explicit temporal boundary."""

    alert: IncidentAlert
    captured_at: datetime
    evidence: tuple[EvidenceItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.alert, IncidentAlert):
            raise TypeError("snapshot alert must be an IncidentAlert")
        _utc(self.captured_at, "snapshot captured_at")
        if self.captured_at < self.alert.started_at:
            raise ValueError("snapshot capture cannot precede incident start")
        if len(self.evidence) > MAX_GATHERED_EVIDENCE:
            raise ValueError(f"snapshot evidence exceeds maximum {MAX_GATHERED_EVIDENCE} items")
        if any(type(item) is not EvidenceItem for item in self.evidence):
            raise TypeError("snapshot evidence must contain exact EvidenceItem values")
        ids = tuple(item.evidence_id for item in self.evidence)
        _unique(ids, "snapshot evidence ids")
        if any(item.observed_at > self.captured_at for item in self.evidence):
            raise ValueError("evidence observed after snapshot capture is not admissible")


@dataclass(frozen=True)
class GatheredContext:
    """Bounded service-local evidence selected by the gather node."""

    alert: IncidentAlert
    as_of: datetime
    evidence: tuple[EvidenceItem, ...]
    analysis_tier: Tier = Tier.T1

    def __post_init__(self) -> None:
        _utc(self.as_of, "gathered context as_of")
        if self.analysis_tier is not Tier.T1:
            raise ValueError("incident context gathering must remain T1 read-only")


@dataclass(frozen=True)
class CitedClaim:
    """A fact whose evidence references are explicit and inspectable."""

    text: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.text, "claim text")
        _unique(self.evidence_ids, "claim evidence ids")
        if not self.evidence_ids:
            raise ValueError("a fact must cite at least one evidence id")


@dataclass(frozen=True)
class Hypothesis:
    """An inference, deliberately separate from observed facts."""

    cause: RootCause
    summary: str
    confidence: float
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.cause, RootCause):
            raise TypeError("hypothesis cause must be a RootCause")
        _text(self.summary, "hypothesis summary")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"hypothesis confidence must be in [0.0, 1.0], got {self.confidence}")
        _unique(self.evidence_ids, "hypothesis evidence ids")
        if self.cause is not RootCause.UNDETERMINED and not self.evidence_ids:
            raise ValueError("a determined hypothesis must cite evidence")


@dataclass(frozen=True)
class AnalysisDraft:
    """Analyzer output before the harness rejoins citations and drafts an RCA."""

    facts: tuple[CitedClaim, ...]
    hypotheses: tuple[Hypothesis, ...]
    unresolved_questions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.hypotheses:
            raise ValueError("analysis must contain at least one hypothesis")
        _unique(self.unresolved_questions, "unresolved questions")


@dataclass(frozen=True)
class TimelineEntry:
    observed_at: datetime
    statement: str
    evidence_id: str

    def __post_init__(self) -> None:
        _utc(self.observed_at, "timeline observed_at")
        _text(self.statement, "timeline statement")
        _text(self.evidence_id, "timeline evidence id")


@dataclass(frozen=True)
class RcaDraft:
    """Reviewable T1 artifact; it intentionally contains no action surface."""

    incident_id: str
    service: str
    as_of: datetime
    timeline: tuple[TimelineEntry, ...]
    facts: tuple[CitedClaim, ...]
    hypotheses: tuple[Hypothesis, ...]
    primary_cause: RootCause
    overall_confidence: float
    unresolved_questions: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    analysis_tier: Tier = Tier.T1

    def __post_init__(self) -> None:
        _utc(self.as_of, "RCA as_of")
        if self.analysis_tier is not Tier.T1:
            raise ValueError("RCA drafting must remain T1 read-only")
        if not self.hypotheses or self.primary_cause is not self.hypotheses[0].cause:
            raise ValueError("RCA primary cause must match its first hypothesis")
        if self.overall_confidence != self.hypotheses[0].confidence:
            raise ValueError("RCA confidence must match its primary hypothesis")
        _unique(self.evidence_ids, "RCA evidence ids")


__all__ = [
    "AnalysisDraft",
    "CitedClaim",
    "EvidenceItem",
    "EvidenceKind",
    "GatheredContext",
    "Hypothesis",
    "IncidentAlert",
    "IncidentSnapshot",
    "MAX_GATHERED_EVIDENCE",
    "RcaDraft",
    "RootCause",
    "TimelineEntry",
]
