"""Incident-replay labels and scorer for the B1 read-only RCA slice."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import secrets
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Protocol

from sre_harness.eval import EvalSummary, Scenario, ScenarioKind, Target, run_eval
from sre_harness.eval.score import Score, ScoreKind
from sre_harness.triage.contracts import (
    EvidenceItem,
    EvidenceKind,
    IncidentAlert,
    IncidentSnapshot,
    RcaDraft,
    RootCause,
)
from sre_harness.triage.pipeline import run_triage

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_PUBLICATION_TOKEN = object()
_REPORT_TOKEN = object()
_PUBLICATION_SEAL_KEY = secrets.token_bytes(32)
_REPORT_SEAL_KEY = secrets.token_bytes(32)


class CorpusProvenance(Enum):
    """Truth about where an eval label came from; never inferred from its score."""

    FIXTURE = "fixture"
    CURATED_REAL = "curated_real"


class TriageEvidenceScope(Enum):
    """Maximum claim the local eval report may make about its corpus."""

    FIXTURE_ONLY = "fixture_only"
    CANDIDATE_CURATED = "candidate_curated"


@dataclass(frozen=True)
class TriageGroundTruth:
    """Minimum causal/citation label for one offline incident replay."""

    primary_cause: RootCause
    required_evidence_ids: tuple[str, ...]
    provenance: CorpusProvenance

    def __post_init__(self) -> None:
        if not isinstance(self.primary_cause, RootCause):
            raise TypeError("triage ground truth cause must be a RootCause")
        if not isinstance(self.provenance, CorpusProvenance):
            raise TypeError("triage ground truth provenance must be explicit")
        if any(not value.strip() for value in self.required_evidence_ids):
            raise ValueError("triage ground-truth evidence ids must not be blank")
        if len(self.required_evidence_ids) != len(set(self.required_evidence_ids)):
            raise ValueError("triage ground-truth evidence ids must be unique")


@dataclass(frozen=True)
class TriageEvalPolicy:
    """Candidate local thresholds; this is not human/publication authority."""

    policy_id: str
    revision: str
    minimum_scenarios: int
    minimum_per_cause: int
    minimum_pass_rate: float
    maximum_unknown_confidence: float

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("triage eval policy id must not be blank")
        if not _SHA256.fullmatch(self.revision):
            raise ValueError("triage eval policy revision must be an exact SHA-256")
        if type(self.minimum_scenarios) is not int or self.minimum_scenarios <= 0:
            raise ValueError("minimum_scenarios must be a positive integer")
        if type(self.minimum_per_cause) is not int or self.minimum_per_cause <= 0:
            raise ValueError("minimum_per_cause must be a positive integer")
        self._unit_interval(self.minimum_pass_rate, "minimum_pass_rate")
        self._unit_interval(
            self.maximum_unknown_confidence,
            "maximum_unknown_confidence",
        )

    @staticmethod
    def _unit_interval(value: float, field: str) -> None:
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
        ):
            raise ValueError(f"{field} must be finite and in [0.0, 1.0]")


@dataclass(frozen=True)
class TriageCorpusPublication:
    """Exact external binding between a corpus, its labels, and eval policy."""

    corpus_id: str
    corpus_revision: str
    policy_id: str
    policy_revision: str
    scenario_ids: tuple[str, ...]
    scenario_manifest_digest: str
    approved_by: str
    approval_revision: str
    origin: str
    publication_revision: str
    verifier_ref: str

    def __post_init__(self) -> None:
        for name in ("corpus_id", "policy_id", "approved_by", "origin", "verifier_ref"):
            value = getattr(self, name)
            if type(value) is not str or not value.strip():
                raise ValueError(f"{name} must be a non-blank exact string")
        for name in (
            "corpus_revision",
            "policy_revision",
            "scenario_manifest_digest",
            "approval_revision",
            "publication_revision",
        ):
            value = getattr(self, name)
            if type(value) is not str or not _SHA256.fullmatch(value):
                raise ValueError(f"{name} must be an exact SHA-256")
        if type(self.scenario_ids) is not tuple or not self.scenario_ids:
            raise ValueError("scenario_ids must be a non-empty exact tuple")
        if any(type(value) is not str or not value.strip() for value in self.scenario_ids):
            raise ValueError("scenario_ids must contain non-blank exact strings")
        if self.scenario_ids != tuple(sorted(set(self.scenario_ids))):
            raise ValueError("scenario_ids must be sorted and unique")


def _publication_payload(
    publication: TriageCorpusPublication | VerifiedTriageCorpusPublication,
) -> dict[str, object]:
    return {
        "approval_revision": publication.approval_revision,
        "approved_by": publication.approved_by,
        "corpus_id": publication.corpus_id,
        "corpus_revision": publication.corpus_revision,
        "origin": publication.origin,
        "policy_id": publication.policy_id,
        "policy_revision": publication.policy_revision,
        "publication_revision": publication.publication_revision,
        "scenario_ids": list(publication.scenario_ids),
        "scenario_manifest_digest": publication.scenario_manifest_digest,
        "verifier_ref": publication.verifier_ref,
    }


def _canonical_publication(
    publication: TriageCorpusPublication | VerifiedTriageCorpusPublication,
) -> bytes:
    return json.dumps(
        _publication_payload(publication),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _publication_seal(
    publication: TriageCorpusPublication | VerifiedTriageCorpusPublication,
) -> str:
    return hmac.new(
        _PUBLICATION_SEAL_KEY,
        _canonical_publication(publication),
        hashlib.sha256,
    ).hexdigest()


@dataclass(frozen=True, init=False)
class VerifiedTriageCorpusPublication:
    """Process-local capability issued only after exact external verification."""

    corpus_id: str
    corpus_revision: str
    policy_id: str
    policy_revision: str
    scenario_ids: tuple[str, ...]
    scenario_manifest_digest: str
    approved_by: str
    approval_revision: str
    origin: str
    publication_revision: str
    verifier_ref: str
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        publication: TriageCorpusPublication,
        *,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _PUBLICATION_TOKEN:
            raise TypeError("verified publication can only be issued by the publication gate")
        for name, value in _publication_payload(publication).items():
            if name == "scenario_ids":
                value = tuple(value)  # type: ignore[arg-type]
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _publication_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is VerifiedTriageCorpusPublication and hmac.compare_digest(
            self._integrity_seal,
            _publication_seal(self),
        )


class TriageCorpusPublicationVerifier(Protocol):
    """External authority adapter; truthy substitutes are deliberately rejected."""

    verifier_ref: str

    def verify(self, publication: TriageCorpusPublication) -> bool: ...


@dataclass(frozen=True)
class TriageCorpusPublicationDecision:
    """Fail-closed result of evaluating one external corpus publication."""

    capability: VerifiedTriageCorpusPublication | None
    reasons: tuple[str, ...]

    @property
    def admissible(self) -> bool:
        return (
            type(self.capability) is VerifiedTriageCorpusPublication
            and self.capability._is_intact()
            and not self.reasons
        )


@dataclass(frozen=True)
class TriageCorpusPublicationGate:
    """Issue a sealed capability only for an allowlisted, unchanged binding."""

    binding: TriageCorpusPublication | None
    binding_verifier: TriageCorpusPublicationVerifier | None
    allowed_origins: tuple[str, ...]
    allowed_verifier_refs: tuple[str, ...]

    def evaluate(self) -> TriageCorpusPublicationDecision:
        if type(self.binding) is not TriageCorpusPublication or self.binding_verifier is None:
            return TriageCorpusPublicationDecision(
                capability=None,
                reasons=("corpus-publication-gate-unconfigured",),
            )

        binding = self.binding
        verifier = self.binding_verifier
        verifier_ref = getattr(verifier, "verifier_ref", None)
        reasons: list[str] = []
        if binding.origin not in self.allowed_origins:
            reasons.append("corpus-publication-origin-not-allowed")
        if verifier_ref not in self.allowed_verifier_refs:
            reasons.append("corpus-publication-verifier-not-allowed")
        if verifier_ref != binding.verifier_ref:
            reasons.append("corpus-publication-verifier-mismatch")
        if reasons:
            return TriageCorpusPublicationDecision(None, tuple(reasons))

        before = _canonical_publication(binding)
        try:
            outcome = verifier.verify(binding)
        except Exception:
            outcome = False
        after = _canonical_publication(binding)
        if not hmac.compare_digest(before, after):
            return TriageCorpusPublicationDecision(
                None,
                ("corpus-publication-changed-during-verification",),
            )
        if type(outcome) is not bool or outcome is not True:
            return TriageCorpusPublicationDecision(
                None,
                ("corpus-publication-verification-failed",),
            )
        capability = VerifiedTriageCorpusPublication(
            binding,
            _construction_token=_PUBLICATION_TOKEN,
        )
        return TriageCorpusPublicationDecision(capability, ())


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _scenario_manifest_record(scenario: Scenario) -> dict[str, object]:
    if scenario.kind is not ScenarioKind.RCA:
        raise TypeError("triage corpus manifest requires RCA scenarios")
    if type(scenario.snapshot) is not IncidentSnapshot:
        raise TypeError("triage corpus manifest requires exact IncidentSnapshot values")
    if type(scenario.ground_truth) is not TriageGroundTruth:
        raise TypeError("triage corpus manifest requires exact TriageGroundTruth labels")
    snapshot = scenario.snapshot
    truth = scenario.ground_truth
    return {
        "ground_truth": {
            "primary_cause": truth.primary_cause.value,
            "provenance": truth.provenance.value,
            "required_evidence_ids": list(truth.required_evidence_ids),
        },
        "id": scenario.id,
        "kind": scenario.kind.value,
        "snapshot": {
            "alert": {
                "incident_id": snapshot.alert.incident_id,
                "service": snapshot.alert.service,
                "started_at": _utc_text(snapshot.alert.started_at),
                "summary": snapshot.alert.summary,
            },
            "captured_at": _utc_text(snapshot.captured_at),
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "kind": item.kind.value,
                    "observed_at": _utc_text(item.observed_at),
                    "service": item.service,
                    "statement": item.statement,
                    "value": item.value,
                }
                for item in snapshot.evidence
            ],
        },
    }


def triage_corpus_manifest_digest(scenarios: Sequence[Scenario]) -> str:
    """Bind every replay input and causal label in a canonical SHA-256 manifest."""
    suite = tuple(scenarios)
    ids = tuple(scenario.id for scenario in suite)
    if not suite:
        raise ValueError("triage corpus manifest requires at least one scenario")
    if len(ids) != len(set(ids)):
        raise ValueError("triage corpus manifest requires unique scenario ids")
    canonical = json.dumps(
        sorted(
            (_scenario_manifest_record(scenario) for scenario in suite), key=lambda row: row["id"]
        ),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _report_seal(
    summary: EvalSummary,
    threshold_conformant: bool,
    evidence_scope: TriageEvidenceScope,
    reasons: tuple[str, ...],
    policy: TriageEvalPolicy | None,
    production_evidence: VerifiedTriageCorpusPublication | None,
) -> str:
    payload = repr(
        (
            summary,
            threshold_conformant,
            evidence_scope,
            reasons,
            policy,
            production_evidence,
        )
    ).encode()
    return hmac.new(_REPORT_SEAL_KEY, payload, hashlib.sha256).hexdigest()


@dataclass(frozen=True, init=False)
class TriageEvalReport:
    """Separate metric conformance from externally authorizing evidence."""

    summary: EvalSummary
    threshold_conformant: bool
    evidence_scope: TriageEvidenceScope
    reasons: tuple[str, ...]
    policy: TriageEvalPolicy | None
    production_evidence: VerifiedTriageCorpusPublication | None
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        summary: EvalSummary,
        threshold_conformant: bool,
        evidence_scope: TriageEvidenceScope,
        reasons: tuple[str, ...],
        policy: TriageEvalPolicy | None,
        production_evidence: VerifiedTriageCorpusPublication | None,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _REPORT_TOKEN:
            raise TypeError("triage eval reports can only be issued by evaluate_triage_suite")
        values = (
            ("summary", summary),
            ("threshold_conformant", threshold_conformant),
            ("evidence_scope", evidence_scope),
            ("reasons", reasons),
            ("policy", policy),
            ("production_evidence", production_evidence),
        )
        for name, value in values:
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "_integrity_seal",
            _report_seal(
                summary,
                threshold_conformant,
                evidence_scope,
                reasons,
                policy,
                production_evidence,
            ),
        )

    @property
    def production_evidence_eligible(self) -> bool:
        current_seal = _report_seal(
            self.summary,
            self.threshold_conformant,
            self.evidence_scope,
            self.reasons,
            self.policy,
            self.production_evidence,
        )
        return (
            hmac.compare_digest(self._integrity_seal, current_seal)
            and type(self.production_evidence) is VerifiedTriageCorpusPublication
            and self.production_evidence._is_intact()
        )


def triage_target(scenario: Scenario) -> RcaDraft:
    """Replay an RCA scenario through the bounded triage pipeline."""
    if scenario.kind is not ScenarioKind.RCA:
        raise TypeError("triage_target requires an RCA scenario")
    if not isinstance(scenario.snapshot, IncidentSnapshot):
        raise TypeError(
            f"triage_target requires an IncidentSnapshot, got {type(scenario.snapshot).__name__}"
        )
    return run_triage(scenario.snapshot)


def triage_pass_at_1(*, expected: object, actual: object) -> Score:
    """Pass when root-cause class and primary-hypothesis citations match."""
    if not isinstance(expected, TriageGroundTruth):
        raise TypeError("triage scorer requires TriageGroundTruth")
    if not isinstance(actual, RcaDraft):
        raise TypeError("triage scorer requires an RcaDraft")
    primary_citations = set(actual.hypotheses[0].evidence_ids)
    correct = (
        actual.primary_cause is expected.primary_cause
        and set(expected.required_evidence_ids) <= primary_citations
    )
    return Score(
        kind=ScoreKind.PASS_AT_1,
        value=1.0 if correct else 0.0,
        passed=correct,
    )


def evaluate_triage_suite(
    scenarios: Sequence[Scenario],
    target: Target,
    *,
    policy: TriageEvalPolicy | None,
    publication: VerifiedTriageCorpusPublication | None = None,
) -> TriageEvalReport:
    """Run B1 replay and fail closed on thresholds, provenance, and publication."""
    suite = tuple(scenarios)
    summary = run_eval(suite, target, scorer=triage_pass_at_1)
    ground_truth = tuple(_ground_truth(scenario) for scenario in suite)
    threshold_reasons: list[str] = []

    ids = [scenario.id for scenario in suite]
    if len(ids) != len(set(ids)):
        threshold_reasons.append("duplicate-scenario-id")

    if policy is None:
        threshold_reasons.append("eval-thresholds-unconfigured")
    else:
        if summary.total < policy.minimum_scenarios:
            threshold_reasons.append("minimum-scenario-count-not-met")
        cause_counts = Counter(label.primary_cause for label in ground_truth)
        if any(cause_counts[cause] < policy.minimum_per_cause for cause in RootCause):
            threshold_reasons.append("root-cause-coverage-incomplete")
        if summary.pass_rate < policy.minimum_pass_rate:
            threshold_reasons.append("minimum-pass-rate-not-met")
        if any(
            label.primary_cause is RootCause.UNDETERMINED
            and isinstance(result.actual, RcaDraft)
            and result.actual.overall_confidence > policy.maximum_unknown_confidence
            for label, result in zip(ground_truth, summary.results, strict=True)
        ):
            threshold_reasons.append("unknown-confidence-ceiling-exceeded")

    provenances = {label.provenance for label in ground_truth}
    if CorpusProvenance.FIXTURE in provenances:
        evidence_scope = TriageEvidenceScope.FIXTURE_ONLY
        evidence_reasons = ["fixture-corpus-not-production-evidence"]
    else:
        evidence_scope = TriageEvidenceScope.CANDIDATE_CURATED
        evidence_reasons = []
    production_evidence: VerifiedTriageCorpusPublication | None = None
    publication_reasons: list[str] = []
    if publication is None:
        publication_reasons.append("verified-corpus-publication-unconfigured")
    elif type(publication) is not VerifiedTriageCorpusPublication or not publication._is_intact():
        publication_reasons.append("verified-corpus-publication-invalid")
    else:
        if (
            policy is None
            or publication.policy_id != policy.policy_id
            or publication.policy_revision != policy.revision
        ):
            publication_reasons.append("corpus-policy-mismatch")
        expected_ids = tuple(sorted(ids))
        if publication.scenario_ids != expected_ids:
            publication_reasons.append("corpus-scenario-ids-mismatch")
        elif publication.scenario_manifest_digest != triage_corpus_manifest_digest(suite):
            publication_reasons.append("corpus-manifest-mismatch")
        if (
            not threshold_reasons
            and not publication_reasons
            and evidence_scope is TriageEvidenceScope.CANDIDATE_CURATED
        ):
            production_evidence = publication

    return TriageEvalReport(
        summary=summary,
        threshold_conformant=not threshold_reasons,
        evidence_scope=evidence_scope,
        reasons=tuple(dict.fromkeys((*threshold_reasons, *evidence_reasons, *publication_reasons))),
        policy=policy,
        production_evidence=production_evidence,
        _construction_token=_REPORT_TOKEN,
    )


def _ground_truth(scenario: Scenario) -> TriageGroundTruth:
    if not isinstance(scenario.ground_truth, TriageGroundTruth):
        raise TypeError("triage eval requires exact TriageGroundTruth labels")
    return scenario.ground_truth


def load_triage_seed_scenarios() -> tuple[Scenario, ...]:
    """Three deterministic seed worlds: deploy, saturation, and honest unknown."""
    start = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
    captured = start + timedelta(minutes=20)

    def snapshot(
        incident_id: str,
        service: str,
        evidence: tuple[EvidenceItem, ...],
    ) -> IncidentSnapshot:
        return IncidentSnapshot(
            alert=IncidentAlert(
                incident_id=incident_id,
                service=service,
                started_at=start,
                summary=f"{service} incident",
            ),
            captured_at=captured,
            evidence=evidence,
        )

    deploy = EvidenceItem(
        evidence_id="deploy-42",
        kind=EvidenceKind.DEPLOYMENT,
        service="payments-api",
        observed_at=start - timedelta(minutes=4),
        statement="payments-api revision 42 deployed",
    )
    errors = EvidenceItem(
        evidence_id="errors-payments",
        kind=EvidenceKind.ERROR_RATE,
        service="payments-api",
        observed_at=start + timedelta(minutes=2),
        statement="payments-api error rate rose to 18%",
        value=0.18,
    )
    saturation = EvidenceItem(
        evidence_id="worker-cpu",
        kind=EvidenceKind.RESOURCE_SATURATION,
        service="worker",
        observed_at=start + timedelta(minutes=1),
        statement="worker CPU saturation reached 96%",
        value=0.96,
    )
    log_only = EvidenceItem(
        evidence_id="novel-log",
        kind=EvidenceKind.LOG_SIGNATURE,
        service="catalog-api",
        observed_at=start + timedelta(minutes=1),
        statement="catalog-api emitted a novel error signature",
    )
    return (
        Scenario(
            id="rca-deployment-regression",
            kind=ScenarioKind.RCA,
            snapshot=snapshot("inc-deploy", "payments-api", (deploy, errors)),
            ground_truth=TriageGroundTruth(
                primary_cause=RootCause.DEPLOYMENT_REGRESSION,
                required_evidence_ids=("deploy-42", "errors-payments"),
                provenance=CorpusProvenance.FIXTURE,
            ),
        ),
        Scenario(
            id="rca-resource-saturation",
            kind=ScenarioKind.RCA,
            snapshot=snapshot("inc-saturation", "worker", (saturation,)),
            ground_truth=TriageGroundTruth(
                primary_cause=RootCause.RESOURCE_SATURATION,
                required_evidence_ids=("worker-cpu",),
                provenance=CorpusProvenance.FIXTURE,
            ),
        ),
        Scenario(
            id="rca-undetermined",
            kind=ScenarioKind.RCA,
            snapshot=snapshot("inc-unknown", "catalog-api", (log_only,)),
            ground_truth=TriageGroundTruth(
                primary_cause=RootCause.UNDETERMINED,
                required_evidence_ids=("novel-log",),
                provenance=CorpusProvenance.FIXTURE,
            ),
        ),
    )


__all__ = [
    "CorpusProvenance",
    "TriageCorpusPublication",
    "TriageCorpusPublicationDecision",
    "TriageCorpusPublicationGate",
    "TriageCorpusPublicationVerifier",
    "TriageEvalPolicy",
    "TriageEvalReport",
    "TriageEvidenceScope",
    "TriageGroundTruth",
    "VerifiedTriageCorpusPublication",
    "evaluate_triage_suite",
    "load_triage_seed_scenarios",
    "triage_corpus_manifest_digest",
    "triage_pass_at_1",
    "triage_target",
]
