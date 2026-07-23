"""Portable, fail-closed Tier-3 human approval contracts for SPEC-B5."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import urlsplit

from sre_harness.autonomy_tiers.action_table import ACTION_TIER_TABLE
from sre_harness.autonomy_tiers.classify import classify
from sre_harness.autonomy_tiers.tiers import DEFAULT_CONFIDENCE_THRESHOLD, Tier

HITL_PROPOSAL_SCHEMA = "sre-harness.hitl-remediation-proposal/v1"
HITL_RECEIPT_SCHEMA = "sre-harness.hitl-approval-receipt/v1"

_MAX_FILE_BYTES = 1024 * 1024
_MAX_APPROVAL_WINDOW = timedelta(days=7)
_PROPOSAL_TOKEN = object()
_RECEIPT_TOKEN = object()
_VERIFIED_RECEIPT_TOKEN = object()
_CASE_TOKEN = object()
_INTEGRITY_KEY = secrets.token_bytes(32)

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_AWS_ACCOUNT = re.compile(r"^[0-9]{12}$")
_AWS_REGION = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-[0-9]$")
_DOCUMENT_NAME = re.compile(r"^[A-Za-z0-9_.-]{3,128}$")
_STEP_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
_PARAMETER_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,63}$")
_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_HUMAN_PRINCIPAL = re.compile(r"^human:[a-z0-9][a-z0-9._/-]{2,127}$")
_SECRET_PARAMETER = re.compile(
    r"password|secret|token|credential|privatekey|accesskey|sessionkey",
    re.IGNORECASE,
)

_PROPOSAL_ENVELOPE_FIELDS = frozenset({"schemaVersion", "proposalRevision", "proposal"})
_PROPOSAL_FIELDS = frozenset(
    {
        "proposalId",
        "createdAt",
        "expiresAt",
        "proposerPrincipal",
        "triggerId",
        "planRevision",
        "actionTierRevision",
        "action",
        "confidence",
        "environment",
        "parameters",
        "mechanism",
        "subject",
        "subjectRevision",
        "evidenceRefs",
        "riskSummary",
        "rollbackRef",
        "rollbackRevision",
    }
)
_AWS_SUBJECT_FIELDS = frozenset(
    {
        "type",
        "awsAccountId",
        "region",
        "automationExecutionId",
        "documentName",
        "documentVersion",
        "documentSha256",
        "schemaVersion",
        "approvalStepName",
        "approvalFirst",
        "inputRevision",
    }
)
_GITLAB_SUBJECT_FIELDS = frozenset(
    {
        "type",
        "instanceOrigin",
        "projectId",
        "mergeRequestIid",
        "sourceSha",
        "targetBranch",
        "protectedBranchRevision",
        "approvalRulesRevision",
        "approvalSettingsRevision",
    }
)
_RECEIPT_ENVELOPE_FIELDS = frozenset({"schemaVersion", "receiptRevision", "receipt"})
_RECEIPT_FIELDS = frozenset(
    {
        "receiptId",
        "evidenceScope",
        "origin",
        "verifierRef",
        "proposalId",
        "proposalRevision",
        "mechanism",
        "subjectRevision",
        "decision",
        "reviewerPrincipal",
        "reviewerEligibilityRevision",
        "authenticationEvidenceRevision",
        "decidedAt",
        "expiresAt",
        "evidenceRef",
        "evidenceRevision",
    }
)


class HitlPolicyError(ValueError):
    """A B5 proposal, receipt, authority, or join is invalid."""


class HitlExecutionError(RuntimeError):
    """A provider or audit operation failed without disclosing its detail."""


class HitlMechanism(Enum):
    AWS_SSM = "aws_ssm"
    GITLAB_MR = "gitlab_mr"


class HitlReceiptDecision(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class HitlCaseState(Enum):
    AWAITING_HUMAN = "awaiting_human"
    ROUTE_T4 = "route_t4"
    REQUIRE_T2 = "require_t2"
    DENIED = "denied"
    APPROVAL_SIGNAL_SENT = "approval_signal_sent"
    REJECTION_SIGNAL_SENT = "rejection_signal_sent"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ESCALATED = "escalated"


class AutomationApprovalStatus(Enum):
    PENDING_APPROVAL = "PendingApproval"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    TIMED_OUT = "TimedOut"
    CANCELLED = "Cancelled"
    FAILED = "Failed"
    SUCCESS = "Success"
    IN_PROGRESS = "InProgress"


_TERMINAL_CASE_STATES = frozenset(
    {
        HitlCaseState.ROUTE_T4,
        HitlCaseState.REQUIRE_T2,
        HitlCaseState.DENIED,
        HitlCaseState.APPROVED,
        HitlCaseState.REJECTED,
        HitlCaseState.EXPIRED,
        HitlCaseState.ESCALATED,
    }
)


@dataclass(frozen=True)
class SsmApprovalSubject:
    aws_account_id: str
    region: str
    automation_execution_id: str
    document_name: str
    document_version: str
    document_sha256: str
    schema_version: str
    approval_step_name: str
    approval_first: bool
    input_revision: str


@dataclass(frozen=True)
class GitlabApprovalSubject:
    instance_origin: str
    project_id: int
    merge_request_iid: int
    source_sha: str
    target_branch: str
    protected_branch_revision: str
    approval_rules_revision: str
    approval_settings_revision: str


ApprovalSubject = SsmApprovalSubject | GitlabApprovalSubject


@dataclass(frozen=True, init=False)
class HitlRemediationProposal:
    proposal_revision: str
    proposal_id: str
    created_at: datetime
    expires_at: datetime
    proposer_principal: str
    trigger_id: str
    plan_revision: str
    action_tier_revision: str
    action: str
    confidence: str
    environment: str
    parameters: tuple[tuple[str, tuple[str, ...]], ...]
    mechanism: HitlMechanism
    subject: ApprovalSubject
    subject_revision: str
    evidence_refs: tuple[str, ...]
    risk_summary: str
    rollback_ref: str
    rollback_revision: str
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        proposal_revision: str,
        proposal_id: str,
        created_at: datetime,
        expires_at: datetime,
        proposer_principal: str,
        trigger_id: str,
        plan_revision: str,
        action_tier_revision: str,
        action: str,
        confidence: str,
        environment: str,
        parameters: tuple[tuple[str, tuple[str, ...]], ...],
        mechanism: HitlMechanism,
        subject: ApprovalSubject,
        subject_revision: str,
        evidence_refs: tuple[str, ...],
        risk_summary: str,
        rollback_ref: str,
        rollback_revision: str,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _PROPOSAL_TOKEN:
            raise TypeError("HITL proposals must come from the strict parser")
        values = locals().copy()
        values.pop("self")
        values.pop("_construction_token")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _proposal_seal(self))

    def _is_intact(self) -> bool:
        try:
            expected = _proposal_seal(self)
            actual = self._integrity_seal
        except Exception:
            return False
        return type(self) is HitlRemediationProposal and hmac.compare_digest(actual, expected)


@dataclass(frozen=True, init=False)
class HitlApprovalReceipt:
    receipt_revision: str
    receipt_id: str
    evidence_scope: str
    origin: str
    verifier_ref: str
    proposal_id: str
    proposal_revision: str
    mechanism: HitlMechanism
    subject_revision: str
    decision: HitlReceiptDecision
    reviewer_principal: str
    reviewer_eligibility_revision: str
    authentication_evidence_revision: str
    decided_at: datetime
    expires_at: datetime
    evidence_ref: str
    evidence_revision: str
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        receipt_revision: str,
        receipt_id: str,
        evidence_scope: str,
        origin: str,
        verifier_ref: str,
        proposal_id: str,
        proposal_revision: str,
        mechanism: HitlMechanism,
        subject_revision: str,
        decision: HitlReceiptDecision,
        reviewer_principal: str,
        reviewer_eligibility_revision: str,
        authentication_evidence_revision: str,
        decided_at: datetime,
        expires_at: datetime,
        evidence_ref: str,
        evidence_revision: str,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _RECEIPT_TOKEN:
            raise TypeError("HITL receipts must come from the strict parser")
        values = locals().copy()
        values.pop("self")
        values.pop("_construction_token")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _receipt_seal(self))

    def _is_intact(self) -> bool:
        try:
            expected = _receipt_seal(self)
            actual = self._integrity_seal
        except Exception:
            return False
        return type(self) is HitlApprovalReceipt and hmac.compare_digest(actual, expected)


class HitlReceiptVerifier(Protocol):
    verifier_ref: str

    def verify(self, receipt: HitlApprovalReceipt) -> object: ...


@dataclass(frozen=True, init=False)
class VerifiedHitlApprovalReceipt:
    receipt_revision: str
    receipt_id: str
    evidence_scope: str
    origin: str
    verifier_ref: str
    proposal_id: str
    proposal_revision: str
    mechanism: HitlMechanism
    subject_revision: str
    decision: HitlReceiptDecision
    reviewer_principal: str
    reviewer_eligibility_revision: str
    authentication_evidence_revision: str
    decided_at: datetime
    expires_at: datetime
    evidence_ref: str
    evidence_revision: str
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        receipt: HitlApprovalReceipt,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _VERIFIED_RECEIPT_TOKEN:
            raise TypeError("verified HITL receipts must come from the approval gate")
        for name in (
            "receipt_revision",
            "receipt_id",
            "evidence_scope",
            "origin",
            "verifier_ref",
            "proposal_id",
            "proposal_revision",
            "mechanism",
            "subject_revision",
            "decision",
            "reviewer_principal",
            "reviewer_eligibility_revision",
            "authentication_evidence_revision",
            "decided_at",
            "expires_at",
            "evidence_ref",
            "evidence_revision",
        ):
            object.__setattr__(self, name, getattr(receipt, name))
        object.__setattr__(self, "_integrity_seal", _verified_receipt_seal(self))

    def _is_intact(self) -> bool:
        try:
            expected = _verified_receipt_seal(self)
            actual = self._integrity_seal
        except Exception:
            return False
        return type(self) is VerifiedHitlApprovalReceipt and hmac.compare_digest(actual, expected)


class HitlApprovalGate:
    """Verify one unchanged receipt through a preconfigured external verifier."""

    def __init__(
        self,
        *,
        allowed_origins: frozenset[str],
        verifiers: dict[str, HitlReceiptVerifier],
    ) -> None:
        self._allowed_origins = allowed_origins
        self._verifiers = dict(verifiers)

    def verify(
        self,
        receipt: HitlApprovalReceipt,
        *,
        now: datetime,
    ) -> VerifiedHitlApprovalReceipt:
        _require_receipt(receipt)
        instant = _require_utc(now, "approval verification time")
        if receipt.origin not in self._allowed_origins:
            raise HitlPolicyError("HITL receipt origin is not allowlisted")
        verifier = self._verifiers.get(receipt.verifier_ref)
        if verifier is None or verifier.verifier_ref != receipt.verifier_ref:
            raise HitlPolicyError("HITL receipt verifier is not configured")
        if instant < receipt.decided_at:
            raise HitlPolicyError("HITL receipt is future-dated")
        if instant >= receipt.expires_at:
            raise HitlPolicyError("HITL receipt is expired")
        before = _canonical_json(_receipt_envelope(receipt))
        try:
            verified = verifier.verify(receipt)
        except Exception as exc:
            raise HitlPolicyError("HITL receipt verification failed") from exc
        after = _canonical_json(_receipt_envelope(receipt))
        if before != after or not receipt._is_intact():
            raise HitlPolicyError("HITL receipt was mutated during verification")
        if type(verified) is not bool or verified is not True:
            raise HitlPolicyError("HITL receipt verification did not return exact true")
        return VerifiedHitlApprovalReceipt(
            receipt,
            _construction_token=_VERIFIED_RECEIPT_TOKEN,
        )


@dataclass(frozen=True)
class AwsApprovalClientBinding:
    aws_account_id: str
    region: str


@dataclass(frozen=True)
class GitlabApprovalClientBinding:
    instance_origin: str


@dataclass(frozen=True)
class AutomationApprovalSnapshot:
    aws_account_id: str
    region: str
    automation_execution_id: str
    document_name: str
    document_version: str
    document_sha256: str
    schema_version: str
    input_revision: str
    approval_step_name: str
    approval_first: bool
    status: AutomationApprovalStatus


@dataclass(frozen=True)
class AutomationApprovalSignalCall:
    aws_account_id: str
    region: str
    automation_execution_id: str
    signal_type: str
    receipt_id: str
    dedupe_key: str

    @property
    def payload(self) -> dict[str, list[str]]:
        return {"Comment": [f"sre-harness-receipt:{self.receipt_id}"]}


@dataclass(frozen=True)
class GitlabApprovalRuleSnapshot:
    rule_id: int
    name: str
    required_approvals: int
    approvals_left: int
    approved: bool
    approved_by: tuple[str, ...]


@dataclass(frozen=True)
class GitlabApprovalSnapshot:
    instance_origin: str
    project_id: int
    merge_request_iid: int
    state: str
    source_sha: str
    target_branch: str
    protected_target: bool
    reset_approvals_on_push: bool
    require_reauthentication: bool
    approval_rules_overwritten: bool
    protected_branch_revision: str
    approval_rules_revision: str
    approval_settings_revision: str
    approvals_left: int
    approved: bool
    rules: tuple[GitlabApprovalRuleSnapshot, ...]
    author_principal: str
    committer_principals: tuple[str, ...]


class AwsApprovalProvider(Protocol):
    def binding(self) -> AwsApprovalClientBinding: ...

    def get_approval_snapshot(self, execution_id: str) -> AutomationApprovalSnapshot: ...

    def send_approval_signal(self, call: AutomationApprovalSignalCall) -> None: ...


class GitlabApprovalProvider(Protocol):
    def binding(self) -> GitlabApprovalClientBinding: ...

    def get_approval_snapshot(
        self, project_id: int, merge_request_iid: int
    ) -> GitlabApprovalSnapshot: ...


@dataclass(frozen=True)
class HitlAuditEvent:
    dedupe_key: str
    event_type: str
    proposal_id: str
    proposal_revision: str
    action: str
    mechanism: str
    receipt_revision: str | None
    state: str
    subject_id: str
    reason: str


class HitlAuditSink(Protocol):
    def record(self, event: HitlAuditEvent) -> None: ...


@dataclass(frozen=True, init=False)
class HitlCase:
    state: HitlCaseState
    reason: str
    proposal_id: str
    proposal_revision: str
    created_at: datetime
    expires_at: datetime
    proposer_principal: str
    action: str
    mechanism: HitlMechanism
    subject: ApprovalSubject
    subject_revision: str
    receipt_id: str | None
    receipt_revision: str | None
    receipt_decision: HitlReceiptDecision | None
    receipt_expires_at: datetime | None
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        state: HitlCaseState | None = None,
        reason: str | None = None,
        proposal: HitlRemediationProposal | None = None,
        source_case: HitlCase | None = None,
        receipt: VerifiedHitlApprovalReceipt | None = None,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _CASE_TOKEN:
            raise TypeError("HITL cases must come from authorization")
        if state is None or reason is None:
            raise TypeError("authorized HITL cases require state and reason")
        if (proposal is None) == (source_case is None):
            raise TypeError("HITL case construction requires one exact source")
        if proposal is not None:
            _require_proposal(proposal)
            values: dict[str, object] = {
                "proposal_id": proposal.proposal_id,
                "proposal_revision": proposal.proposal_revision,
                "created_at": proposal.created_at,
                "expires_at": proposal.expires_at,
                "proposer_principal": proposal.proposer_principal,
                "action": proposal.action,
                "mechanism": proposal.mechanism,
                "subject": proposal.subject,
                "subject_revision": proposal.subject_revision,
                "receipt_id": None,
                "receipt_revision": None,
                "receipt_decision": None,
                "receipt_expires_at": None,
            }
        else:
            if source_case is None:
                raise TypeError("HITL case source is missing")
            _require_case(source_case)
            values = {
                "proposal_id": source_case.proposal_id,
                "proposal_revision": source_case.proposal_revision,
                "created_at": source_case.created_at,
                "expires_at": source_case.expires_at,
                "proposer_principal": source_case.proposer_principal,
                "action": source_case.action,
                "mechanism": source_case.mechanism,
                "subject": source_case.subject,
                "subject_revision": source_case.subject_revision,
                "receipt_id": source_case.receipt_id,
                "receipt_revision": source_case.receipt_revision,
                "receipt_decision": source_case.receipt_decision,
                "receipt_expires_at": source_case.receipt_expires_at,
            }
        values["state"] = state
        values["reason"] = reason
        if receipt is not None:
            _require_verified_receipt(receipt)
            values.update(
                {
                    "receipt_id": receipt.receipt_id,
                    "receipt_revision": receipt.receipt_revision,
                    "receipt_decision": receipt.decision,
                    "receipt_expires_at": receipt.expires_at,
                }
            )
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _case_seal(self))

    def _is_intact(self) -> bool:
        try:
            expected = _case_seal(self)
            actual = self._integrity_seal
        except Exception:
            return False
        return type(self) is HitlCase and hmac.compare_digest(actual, expected)


def hitl_action_tier_revision() -> str:
    """Return the canonical revision of the table and threshold B5 classifies."""

    return _canonical_revision(
        {
            "actions": [[action, tier.name] for action, tier in sorted(ACTION_TIER_TABLE.items())],
            "confidenceThreshold": _decimal_text(Decimal(str(DEFAULT_CONFIDENCE_THRESHOLD))),
        }
    )


def parse_hitl_proposal(raw: bytes) -> HitlRemediationProposal:
    envelope = _parse_json_envelope(raw, "HITL proposal")
    _exact_fields(envelope, _PROPOSAL_ENVELOPE_FIELDS, "HITL proposal envelope")
    if envelope["schemaVersion"] != HITL_PROPOSAL_SCHEMA:
        raise HitlPolicyError("HITL proposal schema is unsupported")
    proposal_revision = _exact_sha256(envelope["proposalRevision"], "proposal revision")
    body = _exact_object(envelope["proposal"], "HITL proposal body")
    _exact_fields(body, _PROPOSAL_FIELDS, "HITL proposal body")

    proposal_id = _exact_uuid(body["proposalId"], "proposal id")
    created_at = _canonical_utc(body["createdAt"], "proposal creation time")
    expires_at = _canonical_utc(body["expiresAt"], "proposal expiry")
    if expires_at <= created_at or expires_at - created_at > _MAX_APPROVAL_WINDOW:
        raise HitlPolicyError("HITL proposal expiry window is invalid")
    proposer_principal = _exact_text(body["proposerPrincipal"], "proposal proposer", maximum=256)
    trigger_id = _exact_text(body["triggerId"], "proposal trigger", maximum=256)
    plan_revision = _exact_sha256(body["planRevision"], "plan revision")
    action_tier_revision = _exact_sha256(body["actionTierRevision"], "action-tier revision")
    action = _exact_text(body["action"], "proposal action", maximum=128)
    confidence = _canonical_decimal(body["confidence"], "proposal confidence")
    environment = _exact_text(body["environment"], "proposal environment", maximum=64)
    parameters = _parameter_map(body["parameters"])
    mechanism = _mechanism(body["mechanism"])
    subject = _parse_subject(body["subject"], mechanism, parameters)
    subject_revision = _exact_sha256(body["subjectRevision"], "subject revision")
    expected_subject_revision = _canonical_revision(
        {
            "action": action,
            "parameters": _parameter_document(parameters),
            "subject": _subject_document(subject),
        }
    )
    if subject_revision != expected_subject_revision:
        raise HitlPolicyError("subject revision does not match the exact subject")
    evidence_refs = _reference_list(body["evidenceRefs"], "proposal evidence")
    risk_summary = _exact_text(body["riskSummary"], "proposal risk summary", maximum=1024)
    rollback_ref = _reference(body["rollbackRef"], "proposal rollback reference")
    rollback_revision = _exact_sha256(body["rollbackRevision"], "proposal rollback revision")

    proposal = HitlRemediationProposal(
        proposal_revision=proposal_revision,
        proposal_id=proposal_id,
        created_at=created_at,
        expires_at=expires_at,
        proposer_principal=proposer_principal,
        trigger_id=trigger_id,
        plan_revision=plan_revision,
        action_tier_revision=action_tier_revision,
        action=action,
        confidence=confidence,
        environment=environment,
        parameters=parameters,
        mechanism=mechanism,
        subject=subject,
        subject_revision=subject_revision,
        evidence_refs=evidence_refs,
        risk_summary=risk_summary,
        rollback_ref=rollback_ref,
        rollback_revision=rollback_revision,
        _construction_token=_PROPOSAL_TOKEN,
    )
    if proposal_revision != _canonical_revision(_proposal_body(proposal)):
        raise HitlPolicyError("proposal revision does not match the exact proposal")
    return proposal


def load_hitl_proposal(path: Path) -> HitlRemediationProposal:
    return parse_hitl_proposal(_load_bounded_file(path, "HITL proposal"))


def parse_hitl_receipt(raw: bytes) -> HitlApprovalReceipt:
    envelope = _parse_json_envelope(raw, "HITL receipt")
    _exact_fields(envelope, _RECEIPT_ENVELOPE_FIELDS, "HITL receipt envelope")
    if envelope["schemaVersion"] != HITL_RECEIPT_SCHEMA:
        raise HitlPolicyError("HITL receipt schema is unsupported")
    receipt_revision = _exact_sha256(envelope["receiptRevision"], "receipt revision")
    body = _exact_object(envelope["receipt"], "HITL receipt body")
    _exact_fields(body, _RECEIPT_FIELDS, "HITL receipt body")
    receipt_id = _exact_uuid(body["receiptId"], "receipt id")
    evidence_scope = _exact_text(body["evidenceScope"], "receipt evidence scope", maximum=32)
    if evidence_scope not in {"fixture", "external_candidate"}:
        raise HitlPolicyError("receipt evidence scope is unsupported")
    origin = _reference(body["origin"], "receipt origin")
    verifier_ref = _reference(body["verifierRef"], "receipt verifier")
    proposal_id = _exact_uuid(body["proposalId"], "receipt proposal id")
    proposal_revision = _exact_sha256(body["proposalRevision"], "receipt proposal revision")
    mechanism = _mechanism(body["mechanism"])
    subject_revision = _exact_sha256(body["subjectRevision"], "receipt subject revision")
    decision_text = _exact_text(body["decision"], "receipt decision", maximum=16)
    try:
        decision = HitlReceiptDecision(decision_text)
    except ValueError as exc:
        raise HitlPolicyError("receipt decision is unsupported") from exc
    reviewer_principal = _exact_text(body["reviewerPrincipal"], "receipt reviewer", maximum=256)
    if not _HUMAN_PRINCIPAL.fullmatch(reviewer_principal):
        raise HitlPolicyError("receipt reviewer must be an external human principal")
    reviewer_eligibility_revision = _exact_sha256(
        body["reviewerEligibilityRevision"], "reviewer eligibility revision"
    )
    authentication_evidence_revision = _exact_sha256(
        body["authenticationEvidenceRevision"],
        "reviewer authentication evidence revision",
    )
    decided_at = _canonical_utc(body["decidedAt"], "receipt decision time")
    expires_at = _canonical_utc(body["expiresAt"], "receipt expiry")
    if expires_at <= decided_at or expires_at - decided_at > _MAX_APPROVAL_WINDOW:
        raise HitlPolicyError("HITL receipt expiry window is invalid")
    evidence_ref = _reference(body["evidenceRef"], "receipt evidence reference")
    evidence_revision = _exact_sha256(body["evidenceRevision"], "receipt evidence revision")
    receipt = HitlApprovalReceipt(
        receipt_revision=receipt_revision,
        receipt_id=receipt_id,
        evidence_scope=evidence_scope,
        origin=origin,
        verifier_ref=verifier_ref,
        proposal_id=proposal_id,
        proposal_revision=proposal_revision,
        mechanism=mechanism,
        subject_revision=subject_revision,
        decision=decision,
        reviewer_principal=reviewer_principal,
        reviewer_eligibility_revision=reviewer_eligibility_revision,
        authentication_evidence_revision=authentication_evidence_revision,
        decided_at=decided_at,
        expires_at=expires_at,
        evidence_ref=evidence_ref,
        evidence_revision=evidence_revision,
        _construction_token=_RECEIPT_TOKEN,
    )
    if receipt_revision != _canonical_revision(_receipt_body(receipt)):
        raise HitlPolicyError("receipt revision does not match the exact receipt")
    return receipt


def load_hitl_receipt(path: Path) -> HitlApprovalReceipt:
    return parse_hitl_receipt(_load_bounded_file(path, "HITL receipt"))


def authorize_hitl_proposal(
    proposal: HitlRemediationProposal,
    audit: HitlAuditSink,
    *,
    now: datetime,
) -> HitlCase:
    _require_proposal(proposal)
    instant = _require_utc(now, "HITL authorization time")
    if instant < proposal.created_at or instant >= proposal.expires_at:
        state = HitlCaseState.EXPIRED
        reason = "proposal-outside-validity-window"
    elif proposal.action_tier_revision != hitl_action_tier_revision():
        state = HitlCaseState.DENIED
        reason = "action-tier-revision-mismatch"
    else:
        classification = classify(
            proposal.action,
            float(Decimal(proposal.confidence)),
            threshold=DEFAULT_CONFIDENCE_THRESHOLD,
        )
        if classification.off_plan:
            state = HitlCaseState.DENIED
            reason = "off-plan-action-denied"
        elif classification.tier is Tier.T4:
            state = HitlCaseState.ROUTE_T4
            reason = "effective-tier-t4-routes-b4"
        elif classification.tier is Tier.T3:
            state = HitlCaseState.AWAITING_HUMAN
            reason = "effective-tier-t3-awaiting-human"
        else:
            state = HitlCaseState.REQUIRE_T2
            reason = "effective-tier-below-t3"
    case = _new_case(proposal, state, reason)
    _record_audit(audit, case)
    return case


def apply_hitl_receipt(
    case: HitlCase,
    receipt: VerifiedHitlApprovalReceipt,
    provider: AwsApprovalProvider | GitlabApprovalProvider,
    audit: HitlAuditSink,
    *,
    now: datetime,
) -> HitlCase:
    _require_case(case)
    _require_verified_receipt(receipt)
    instant = _require_utc(now, "HITL receipt use time")
    if case.state is not HitlCaseState.AWAITING_HUMAN:
        raise HitlPolicyError("HITL receipt cannot be applied to a terminal or active case")
    _rejoin_receipt(case, receipt)
    if receipt.evidence_scope != "external_candidate":
        raise HitlPolicyError("fixture HITL receipt cannot authorize a provider")
    if receipt.reviewer_principal == case.proposer_principal:
        raise HitlPolicyError("HITL proposer cannot self-approve")
    if receipt.decided_at < case.created_at or receipt.decided_at >= case.expires_at:
        raise HitlPolicyError("HITL receipt decision is outside the proposal window")
    if instant >= min(case.expires_at, receipt.expires_at):
        expired = _transition(case, receipt, HitlCaseState.EXPIRED, "approval-expired")
        _record_audit(audit, expired)
        return expired
    if instant < receipt.decided_at:
        raise HitlPolicyError("HITL receipt use precedes its decision")
    if case.mechanism is HitlMechanism.AWS_SSM:
        return _apply_aws_receipt(case, receipt, provider, audit)
    return _apply_gitlab_receipt(case, receipt, provider, audit)


def reconcile_hitl_case(
    case: HitlCase,
    provider: AwsApprovalProvider | GitlabApprovalProvider,
    audit: HitlAuditSink,
    *,
    now: datetime,
) -> HitlCase:
    _require_case(case)
    instant = _require_utc(now, "HITL reconciliation time")
    if case.state in _TERMINAL_CASE_STATES:
        return case
    if case.state is HitlCaseState.AWAITING_HUMAN:
        if instant >= case.expires_at:
            expired = _transition_without_receipt(
                case, HitlCaseState.EXPIRED, "proposal-expired-awaiting-human"
            )
            _record_audit(audit, expired)
            return expired
        return case
    if case.mechanism is not HitlMechanism.AWS_SSM:
        return _escalate(case, audit, "unexpected-nonterminal-gitlab-state")
    if case.state not in {
        HitlCaseState.APPROVAL_SIGNAL_SENT,
        HitlCaseState.REJECTION_SIGNAL_SENT,
    }:
        return _escalate(case, audit, "unknown-hitl-state")
    subject = case.subject
    if type(subject) is not SsmApprovalSubject:
        return _escalate(case, audit, "provider-subject-type-drift")
    binding = _aws_binding(provider)
    if binding != AwsApprovalClientBinding(subject.aws_account_id, subject.region):
        return _escalate(case, audit, "provider-client-binding-drift")
    snapshot = _aws_snapshot(provider, subject.automation_execution_id)
    if not _aws_subject_matches(subject, snapshot):
        return _escalate(case, audit, "provider-subject-drift")
    expected = (
        AutomationApprovalStatus.APPROVED
        if case.state is HitlCaseState.APPROVAL_SIGNAL_SENT
        else AutomationApprovalStatus.REJECTED
    )
    if snapshot.status is AutomationApprovalStatus.PENDING_APPROVAL:
        return case
    if snapshot.status is expected:
        terminal_state = (
            HitlCaseState.APPROVED
            if expected is AutomationApprovalStatus.APPROVED
            else HitlCaseState.REJECTED
        )
        terminal = _transition_existing(case, terminal_state, f"aws-{terminal_state.value}")
        _record_audit(audit, terminal)
        return terminal
    if snapshot.status is AutomationApprovalStatus.TIMED_OUT:
        expired = _transition_existing(case, HitlCaseState.EXPIRED, "aws-approval-timed-out")
        _record_audit(audit, expired)
        return expired
    return _escalate(case, audit, "provider-approval-state-conflict")


def _apply_aws_receipt(
    case: HitlCase,
    receipt: VerifiedHitlApprovalReceipt,
    provider: AwsApprovalProvider | GitlabApprovalProvider,
    audit: HitlAuditSink,
) -> HitlCase:
    subject = case.subject
    if type(subject) is not SsmApprovalSubject:
        return _escalate(case, audit, "provider-subject-type-drift", receipt)
    binding = _aws_binding(provider)
    if binding != AwsApprovalClientBinding(subject.aws_account_id, subject.region):
        return _escalate(case, audit, "provider-client-binding-drift", receipt)
    snapshot = _aws_snapshot(provider, subject.automation_execution_id)
    if not _aws_subject_matches(subject, snapshot):
        return _escalate(case, audit, "provider-subject-drift", receipt)
    expected_status = (
        AutomationApprovalStatus.APPROVED
        if receipt.decision is HitlReceiptDecision.APPROVED
        else AutomationApprovalStatus.REJECTED
    )
    if snapshot.status is expected_status:
        state = (
            HitlCaseState.APPROVED
            if receipt.decision is HitlReceiptDecision.APPROVED
            else HitlCaseState.REJECTED
        )
        terminal = _transition(case, receipt, state, f"aws-{state.value}-observed")
        _record_audit(audit, terminal)
        return terminal
    if snapshot.status is not AutomationApprovalStatus.PENDING_APPROVAL:
        return _escalate(case, audit, "provider-approval-state-conflict", receipt)
    signal_type = "Approve" if receipt.decision is HitlReceiptDecision.APPROVED else "Reject"
    call = AutomationApprovalSignalCall(
        aws_account_id=subject.aws_account_id,
        region=subject.region,
        automation_execution_id=subject.automation_execution_id,
        signal_type=signal_type,
        receipt_id=receipt.receipt_id,
        dedupe_key=_dedupe_key(
            "provider-signal",
            case.proposal_revision,
            receipt.receipt_revision,
            receipt.decision.value,
        ),
    )
    try:
        cast(AwsApprovalProvider, provider).send_approval_signal(call)
    except Exception as exc:
        raise HitlExecutionError("approval signal failed") from exc
    state = (
        HitlCaseState.APPROVAL_SIGNAL_SENT
        if receipt.decision is HitlReceiptDecision.APPROVED
        else HitlCaseState.REJECTION_SIGNAL_SENT
    )
    signalled = _transition(case, receipt, state, f"aws-{signal_type.casefold()}-signal-sent")
    _record_audit(audit, signalled)
    return signalled


def _apply_gitlab_receipt(
    case: HitlCase,
    receipt: VerifiedHitlApprovalReceipt,
    provider: AwsApprovalProvider | GitlabApprovalProvider,
    audit: HitlAuditSink,
) -> HitlCase:
    if receipt.decision is HitlReceiptDecision.REJECTED:
        rejected = _transition(case, receipt, HitlCaseState.REJECTED, "gitlab-human-rejected")
        _record_audit(audit, rejected)
        return rejected
    subject = case.subject
    if type(subject) is not GitlabApprovalSubject:
        return _escalate(case, audit, "provider-subject-type-drift", receipt)
    binding = _gitlab_binding(provider)
    if binding != GitlabApprovalClientBinding(subject.instance_origin):
        return _escalate(case, audit, "provider-client-binding-drift", receipt)
    snapshot = _gitlab_snapshot(provider, subject.project_id, subject.merge_request_iid)
    if not _gitlab_approval_matches(subject, snapshot, receipt.reviewer_principal):
        return _escalate(case, audit, "provider-subject-drift", receipt)
    approved = _transition(case, receipt, HitlCaseState.APPROVED, "gitlab-approval-observed")
    _record_audit(audit, approved)
    return approved


def _aws_binding(
    provider: AwsApprovalProvider | GitlabApprovalProvider,
) -> AwsApprovalClientBinding | None:
    try:
        binding = provider.binding()
    except Exception:
        return None
    return binding if type(binding) is AwsApprovalClientBinding else None


def _gitlab_binding(
    provider: AwsApprovalProvider | GitlabApprovalProvider,
) -> GitlabApprovalClientBinding | None:
    try:
        binding = provider.binding()
    except Exception:
        return None
    return binding if type(binding) is GitlabApprovalClientBinding else None


def _aws_snapshot(
    provider: AwsApprovalProvider | GitlabApprovalProvider,
    execution_id: str,
) -> AutomationApprovalSnapshot:
    try:
        snapshot = cast(AwsApprovalProvider, provider).get_approval_snapshot(execution_id)
    except Exception as exc:
        raise HitlExecutionError("approval snapshot lookup failed") from exc
    if type(snapshot) is not AutomationApprovalSnapshot:
        raise HitlExecutionError("approval snapshot lookup returned an invalid result")
    return snapshot


def _gitlab_snapshot(
    provider: AwsApprovalProvider | GitlabApprovalProvider,
    project_id: int,
    merge_request_iid: int,
) -> GitlabApprovalSnapshot:
    try:
        snapshot = cast(GitlabApprovalProvider, provider).get_approval_snapshot(
            project_id, merge_request_iid
        )
    except Exception as exc:
        raise HitlExecutionError("approval snapshot lookup failed") from exc
    if type(snapshot) is not GitlabApprovalSnapshot:
        raise HitlExecutionError("approval snapshot lookup returned an invalid result")
    return snapshot


def _aws_subject_matches(
    subject: SsmApprovalSubject,
    snapshot: AutomationApprovalSnapshot,
) -> bool:
    return (
        snapshot.aws_account_id == subject.aws_account_id
        and snapshot.region == subject.region
        and snapshot.automation_execution_id == subject.automation_execution_id
        and snapshot.document_name == subject.document_name
        and snapshot.document_version == subject.document_version
        and snapshot.document_sha256 == subject.document_sha256
        and snapshot.schema_version == subject.schema_version == "0.3"
        and snapshot.input_revision == subject.input_revision
        and snapshot.approval_step_name == subject.approval_step_name
        and snapshot.approval_first is True
    )


def _gitlab_approval_matches(
    subject: GitlabApprovalSubject,
    snapshot: GitlabApprovalSnapshot,
    reviewer: str,
) -> bool:
    rules = snapshot.rules
    rule_ids = tuple(rule.rule_id for rule in rules)
    valid_rules = (
        bool(rules)
        and len(rule_ids) == len(set(rule_ids))
        and all(
            type(rule.required_approvals) is int
            and rule.required_approvals > 0
            and type(rule.approvals_left) is int
            and rule.approvals_left == 0
            and rule.approved is True
            and bool(rule.approved_by)
            and tuple(sorted(set(rule.approved_by))) == rule.approved_by
            for rule in rules
        )
        and any(reviewer in rule.approved_by for rule in rules)
    )
    return (
        snapshot.instance_origin == subject.instance_origin
        and snapshot.project_id == subject.project_id
        and snapshot.merge_request_iid == subject.merge_request_iid
        and snapshot.state == "opened"
        and snapshot.source_sha == subject.source_sha
        and snapshot.target_branch == subject.target_branch
        and snapshot.protected_target is True
        and snapshot.reset_approvals_on_push is True
        and snapshot.require_reauthentication is True
        and snapshot.approval_rules_overwritten is False
        and snapshot.protected_branch_revision == subject.protected_branch_revision
        and snapshot.approval_rules_revision == subject.approval_rules_revision
        and snapshot.approval_settings_revision == subject.approval_settings_revision
        and type(snapshot.approvals_left) is int
        and snapshot.approvals_left == 0
        and snapshot.approved is True
        and reviewer != snapshot.author_principal
        and reviewer not in snapshot.committer_principals
        and valid_rules
    )


def _rejoin_receipt(case: HitlCase, receipt: VerifiedHitlApprovalReceipt) -> None:
    if (
        receipt.proposal_id != case.proposal_id
        or receipt.proposal_revision != case.proposal_revision
    ):
        raise HitlPolicyError("HITL receipt proposal binding mismatch")
    if receipt.mechanism is not case.mechanism:
        raise HitlPolicyError("HITL receipt mechanism binding mismatch")
    if receipt.subject_revision != case.subject_revision:
        raise HitlPolicyError("HITL receipt subject binding mismatch")


def _new_case(
    proposal: HitlRemediationProposal,
    state: HitlCaseState,
    reason: str,
) -> HitlCase:
    return HitlCase(
        state=state,
        reason=reason,
        proposal=proposal,
        _construction_token=_CASE_TOKEN,
    )


def _transition(
    case: HitlCase,
    receipt: VerifiedHitlApprovalReceipt,
    state: HitlCaseState,
    reason: str,
) -> HitlCase:
    return HitlCase(
        state=state,
        reason=reason,
        source_case=case,
        receipt=receipt,
        _construction_token=_CASE_TOKEN,
    )


def _transition_existing(
    case: HitlCase,
    state: HitlCaseState,
    reason: str,
) -> HitlCase:
    return HitlCase(
        state=state,
        reason=reason,
        source_case=case,
        _construction_token=_CASE_TOKEN,
    )


def _transition_without_receipt(
    case: HitlCase,
    state: HitlCaseState,
    reason: str,
) -> HitlCase:
    return HitlCase(
        state=state,
        reason=reason,
        source_case=case,
        _construction_token=_CASE_TOKEN,
    )


def _escalate(
    case: HitlCase,
    audit: HitlAuditSink,
    reason: str,
    receipt: VerifiedHitlApprovalReceipt | None = None,
) -> HitlCase:
    if receipt is not None:
        escalated = _transition(case, receipt, HitlCaseState.ESCALATED, reason)
    elif case.receipt_revision is not None:
        escalated = _transition_existing(case, HitlCaseState.ESCALATED, reason)
    else:
        escalated = _transition_without_receipt(case, HitlCaseState.ESCALATED, reason)
    _record_audit(audit, escalated)
    return escalated


def _record_audit(audit: HitlAuditSink, case: HitlCase) -> None:
    event = HitlAuditEvent(
        dedupe_key=_dedupe_key(
            "audit",
            case.proposal_revision,
            case.receipt_revision or "none",
            case.state.value,
            case.reason,
        ),
        event_type=case.state.value,
        proposal_id=case.proposal_id,
        proposal_revision=case.proposal_revision,
        action=case.action,
        mechanism=case.mechanism.value,
        receipt_revision=case.receipt_revision,
        state=case.state.value,
        subject_id=_subject_id(case.subject),
        reason=case.reason,
    )
    try:
        audit.record(event)
    except Exception as exc:
        raise HitlExecutionError("audit recording failed") from exc


def _subject_id(subject: ApprovalSubject) -> str:
    if type(subject) is SsmApprovalSubject:
        return subject.automation_execution_id
    if type(subject) is GitlabApprovalSubject:
        return f"project:{subject.project_id}/mr:{subject.merge_request_iid}"
    return "invalid-subject"


def _parse_subject(
    value: object,
    mechanism: HitlMechanism,
    parameters: tuple[tuple[str, tuple[str, ...]], ...],
) -> ApprovalSubject:
    subject = _exact_object(value, "proposal provider subject")
    if mechanism is HitlMechanism.AWS_SSM:
        _exact_fields(subject, _AWS_SUBJECT_FIELDS, "AWS approval subject")
        if subject["type"] != mechanism.value:
            raise HitlPolicyError("AWS subject type does not match mechanism")
        account = _exact_text(subject["awsAccountId"], "AWS account", maximum=12)
        if not _AWS_ACCOUNT.fullmatch(account):
            raise HitlPolicyError("AWS account id is invalid")
        region = _exact_text(subject["region"], "AWS region", maximum=32)
        if not _AWS_REGION.fullmatch(region):
            raise HitlPolicyError("AWS region is invalid")
        execution_id = _exact_uuid(subject["automationExecutionId"], "Automation execution id")
        document_name = _exact_text(
            subject["documentName"], "Automation document name", maximum=128
        )
        if not _DOCUMENT_NAME.fullmatch(document_name):
            raise HitlPolicyError("Automation document name is invalid")
        document_version = _numeric_version(
            subject["documentVersion"], "Automation document version"
        )
        document_sha256 = _exact_sha256(subject["documentSha256"], "Automation document hash")
        schema_version = _exact_text(subject["schemaVersion"], "Automation schema", maximum=8)
        if schema_version != "0.3":
            raise HitlPolicyError("Automation schema must be 0.3")
        approval_step_name = _exact_text(
            subject["approvalStepName"], "approval step name", maximum=128
        )
        if not _STEP_NAME.fullmatch(approval_step_name):
            raise HitlPolicyError("approval step name is invalid")
        if type(subject["approvalFirst"]) is not bool or subject["approvalFirst"] is not True:
            raise HitlPolicyError("approval must be the first Automation step")
        input_revision = _exact_sha256(subject["inputRevision"], "Automation input revision")
        if input_revision != _canonical_revision(_parameter_document(parameters)):
            raise HitlPolicyError("Automation input revision does not match parameters")
        return SsmApprovalSubject(
            account,
            region,
            execution_id,
            document_name,
            document_version,
            document_sha256,
            schema_version,
            approval_step_name,
            True,
            input_revision,
        )

    _exact_fields(subject, _GITLAB_SUBJECT_FIELDS, "GitLab approval subject")
    if subject["type"] != mechanism.value:
        raise HitlPolicyError("GitLab subject type does not match mechanism")
    instance_origin = _https_origin(subject["instanceOrigin"])
    project_id = _exact_int(subject["projectId"], "GitLab project id", 1, 2**63 - 1)
    merge_request_iid = _exact_int(
        subject["mergeRequestIid"], "GitLab merge request id", 1, 2**31 - 1
    )
    source_sha = _exact_text(subject["sourceSha"], "GitLab source SHA", maximum=40)
    if not _GIT_SHA.fullmatch(source_sha):
        raise HitlPolicyError("GitLab source SHA is invalid")
    target_branch = _exact_text(subject["targetBranch"], "GitLab target branch", maximum=255)
    if (
        not _BRANCH.fullmatch(target_branch)
        or "*" in target_branch
        or ".." in target_branch
        or target_branch.endswith("/")
    ):
        raise HitlPolicyError("GitLab target branch is invalid")
    return GitlabApprovalSubject(
        instance_origin=instance_origin,
        project_id=project_id,
        merge_request_iid=merge_request_iid,
        source_sha=source_sha,
        target_branch=target_branch,
        protected_branch_revision=_exact_sha256(
            subject["protectedBranchRevision"], "protected branch revision"
        ),
        approval_rules_revision=_exact_sha256(
            subject["approvalRulesRevision"], "approval rules revision"
        ),
        approval_settings_revision=_exact_sha256(
            subject["approvalSettingsRevision"], "approval settings revision"
        ),
    )


def _mechanism(value: object) -> HitlMechanism:
    text = _exact_text(value, "HITL mechanism", maximum=32)
    try:
        return HitlMechanism(text)
    except ValueError as exc:
        raise HitlPolicyError("HITL mechanism is unsupported") from exc


def _parameter_map(
    value: object,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    mapping = _exact_object(value, "proposal parameters")
    if not mapping or len(mapping) > 16 or tuple(mapping) != tuple(sorted(mapping)):
        raise HitlPolicyError("proposal parameter names must be non-empty and sorted")
    result: list[tuple[str, tuple[str, ...]]] = []
    for name, raw_values in mapping.items():
        if not _PARAMETER_NAME.fullmatch(name) or _SECRET_PARAMETER.search(name):
            raise HitlPolicyError("proposal parameter name is invalid or secret-like")
        if type(raw_values) is not list or not raw_values or len(raw_values) > 16:
            raise HitlPolicyError("proposal parameter values must be a bounded list")
        values = tuple(
            _exact_text(item, f"proposal parameter {name}", maximum=512) for item in raw_values
        )
        if values != tuple(sorted(set(values))):
            raise HitlPolicyError("proposal parameter values must be sorted and unique")
        result.append((name, values))
    return tuple(result)


def _reference_list(value: object, field_name: str) -> tuple[str, ...]:
    if type(value) is not list or not value or len(value) > 32:
        raise HitlPolicyError(f"{field_name} must be a bounded non-empty list")
    refs = tuple(_reference(item, field_name) for item in value)
    if refs != tuple(sorted(set(refs))):
        raise HitlPolicyError(f"{field_name} references must be sorted and unique")
    return refs


def _reference(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name, maximum=512)
    parsed = urlsplit(text)
    if not parsed.scheme or not (parsed.netloc or parsed.path):
        raise HitlPolicyError(f"{field_name} must be an immutable reference")
    if parsed.username is not None or parsed.password is not None:
        raise HitlPolicyError(f"{field_name} must not contain credentials")
    return text


def _https_origin(value: object) -> str:
    text = _exact_text(value, "GitLab instance origin", maximum=256)
    parsed = urlsplit(text)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise HitlPolicyError("GitLab instance origin must be an exact HTTPS origin")
    return f"https://{parsed.netloc}"


def _proposal_body(proposal: HitlRemediationProposal) -> dict[str, object]:
    return {
        "proposalId": proposal.proposal_id,
        "createdAt": _utc_text(proposal.created_at),
        "expiresAt": _utc_text(proposal.expires_at),
        "proposerPrincipal": proposal.proposer_principal,
        "triggerId": proposal.trigger_id,
        "planRevision": proposal.plan_revision,
        "actionTierRevision": proposal.action_tier_revision,
        "action": proposal.action,
        "confidence": proposal.confidence,
        "environment": proposal.environment,
        "parameters": _parameter_document(proposal.parameters),
        "mechanism": proposal.mechanism.value,
        "subject": _subject_document(proposal.subject),
        "subjectRevision": proposal.subject_revision,
        "evidenceRefs": list(proposal.evidence_refs),
        "riskSummary": proposal.risk_summary,
        "rollbackRef": proposal.rollback_ref,
        "rollbackRevision": proposal.rollback_revision,
    }


def _proposal_envelope(proposal: HitlRemediationProposal) -> dict[str, object]:
    return {
        "schemaVersion": HITL_PROPOSAL_SCHEMA,
        "proposalRevision": proposal.proposal_revision,
        "proposal": _proposal_body(proposal),
    }


def _receipt_body(
    receipt: HitlApprovalReceipt | VerifiedHitlApprovalReceipt,
) -> dict[str, object]:
    return {
        "receiptId": receipt.receipt_id,
        "evidenceScope": receipt.evidence_scope,
        "origin": receipt.origin,
        "verifierRef": receipt.verifier_ref,
        "proposalId": receipt.proposal_id,
        "proposalRevision": receipt.proposal_revision,
        "mechanism": receipt.mechanism.value,
        "subjectRevision": receipt.subject_revision,
        "decision": receipt.decision.value,
        "reviewerPrincipal": receipt.reviewer_principal,
        "reviewerEligibilityRevision": receipt.reviewer_eligibility_revision,
        "authenticationEvidenceRevision": receipt.authentication_evidence_revision,
        "decidedAt": _utc_text(receipt.decided_at),
        "expiresAt": _utc_text(receipt.expires_at),
        "evidenceRef": receipt.evidence_ref,
        "evidenceRevision": receipt.evidence_revision,
    }


def _receipt_envelope(
    receipt: HitlApprovalReceipt | VerifiedHitlApprovalReceipt,
) -> dict[str, object]:
    return {
        "schemaVersion": HITL_RECEIPT_SCHEMA,
        "receiptRevision": receipt.receipt_revision,
        "receipt": _receipt_body(receipt),
    }


def _subject_document(subject: ApprovalSubject) -> dict[str, object]:
    if type(subject) is SsmApprovalSubject:
        return {
            "type": HitlMechanism.AWS_SSM.value,
            "awsAccountId": subject.aws_account_id,
            "region": subject.region,
            "automationExecutionId": subject.automation_execution_id,
            "documentName": subject.document_name,
            "documentVersion": subject.document_version,
            "documentSha256": subject.document_sha256,
            "schemaVersion": subject.schema_version,
            "approvalStepName": subject.approval_step_name,
            "approvalFirst": subject.approval_first,
            "inputRevision": subject.input_revision,
        }
    if type(subject) is GitlabApprovalSubject:
        return {
            "type": HitlMechanism.GITLAB_MR.value,
            "instanceOrigin": subject.instance_origin,
            "projectId": subject.project_id,
            "mergeRequestIid": subject.merge_request_iid,
            "sourceSha": subject.source_sha,
            "targetBranch": subject.target_branch,
            "protectedBranchRevision": subject.protected_branch_revision,
            "approvalRulesRevision": subject.approval_rules_revision,
            "approvalSettingsRevision": subject.approval_settings_revision,
        }
    raise HitlPolicyError("HITL provider subject type is invalid")


def _parameter_document(
    parameters: tuple[tuple[str, tuple[str, ...]], ...],
) -> dict[str, list[str]]:
    return {name: list(values) for name, values in parameters}


def _case_document(case: HitlCase) -> dict[str, object]:
    return {
        "state": case.state.value,
        "reason": case.reason,
        "proposalId": case.proposal_id,
        "proposalRevision": case.proposal_revision,
        "createdAt": _utc_text(case.created_at),
        "expiresAt": _utc_text(case.expires_at),
        "proposerPrincipal": case.proposer_principal,
        "action": case.action,
        "mechanism": case.mechanism.value,
        "subject": _subject_document(case.subject),
        "subjectRevision": case.subject_revision,
        "receiptId": case.receipt_id,
        "receiptRevision": case.receipt_revision,
        "receiptDecision": (
            case.receipt_decision.value if case.receipt_decision is not None else None
        ),
        "receiptExpiresAt": (
            _utc_text(case.receipt_expires_at) if case.receipt_expires_at is not None else None
        ),
    }


def _proposal_seal(proposal: HitlRemediationProposal) -> str:
    return _seal(_proposal_envelope(proposal))


def _receipt_seal(receipt: HitlApprovalReceipt) -> str:
    return _seal(_receipt_envelope(receipt))


def _verified_receipt_seal(receipt: VerifiedHitlApprovalReceipt) -> str:
    return _seal(_receipt_envelope(receipt))


def _case_seal(case: HitlCase) -> str:
    return _seal(_case_document(case))


def _seal(value: object) -> str:
    return hmac.new(_INTEGRITY_KEY, _canonical_json(value), hashlib.sha256).hexdigest()


def _require_proposal(proposal: HitlRemediationProposal) -> None:
    if type(proposal) is not HitlRemediationProposal or not proposal._is_intact():
        raise HitlPolicyError("HITL proposal integrity check failed")


def _require_receipt(receipt: HitlApprovalReceipt) -> None:
    if type(receipt) is not HitlApprovalReceipt or not receipt._is_intact():
        raise HitlPolicyError("HITL receipt integrity check failed")


def _require_verified_receipt(receipt: VerifiedHitlApprovalReceipt) -> None:
    if type(receipt) is not VerifiedHitlApprovalReceipt or not receipt._is_intact():
        raise HitlPolicyError("verified HITL receipt integrity check failed")


def _require_case(case: HitlCase) -> None:
    if type(case) is not HitlCase or not case._is_intact():
        raise HitlPolicyError("HITL case integrity check failed")


def _parse_json_envelope(raw: bytes, field_name: str) -> dict[str, object]:
    if type(raw) is not bytes:
        raise HitlPolicyError(f"{field_name} must be bytes")
    if len(raw) > _MAX_FILE_BYTES:
        raise HitlPolicyError(f"{field_name} is too large")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise HitlPolicyError(f"{field_name} must be strict UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_closed_object,
            parse_constant=_reject_nonfinite,
        )
    except HitlPolicyError:
        raise
    except json.JSONDecodeError as exc:
        raise HitlPolicyError(f"{field_name} is malformed JSON") from exc
    return _exact_object(value, field_name)


def _load_bounded_file(path: Path, field_name: str) -> bytes:
    if not isinstance(path, Path):
        raise HitlPolicyError(f"{field_name} path must be a Path")
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise HitlPolicyError(f"{field_name} file is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise HitlPolicyError(f"{field_name} file must not be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise HitlPolicyError(f"{field_name} path must be a regular file")
    if metadata.st_size > _MAX_FILE_BYTES:
        raise HitlPolicyError(f"{field_name} file is too large")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            data = handle.read(_MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise HitlPolicyError(f"{field_name} file is unavailable") from exc
    if len(data) > _MAX_FILE_BYTES:
        raise HitlPolicyError(f"{field_name} file is too large")
    return data


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise HitlPolicyError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> object:
    raise HitlPolicyError(f"non-finite JSON number is forbidden: {value}")


def _exact_object(value: object, field_name: str) -> dict[str, object]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise HitlPolicyError(f"{field_name} must be an exact object")
    return value


def _exact_fields(value: dict[str, object], expected: frozenset[str], field_name: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise HitlPolicyError(f"{field_name} fields mismatch; missing={missing}, extra={extra}")


def _exact_text(value: object, field_name: str, *, maximum: int) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise HitlPolicyError(f"{field_name} must be exact non-empty text")
    if len(value) > maximum or any(ord(character) < 32 for character in value):
        raise HitlPolicyError(f"{field_name} exceeds its text boundary")
    return value


def _exact_sha256(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name, maximum=71)
    if not _SHA256.fullmatch(text):
        raise HitlPolicyError(f"{field_name} must be a canonical sha256 revision")
    return text


def _exact_uuid(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name, maximum=36)
    try:
        parsed = uuid.UUID(text)
    except ValueError as exc:
        raise HitlPolicyError(f"{field_name} must be a UUID") from exc
    if str(parsed) != text:
        raise HitlPolicyError(f"{field_name} must be a canonical UUID")
    return text


def _numeric_version(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name, maximum=10)
    if not text.isdigit() or text.startswith("0") or int(text) < 1:
        raise HitlPolicyError(f"{field_name} must be a positive numeric version")
    return text


def _exact_int(value: object, field_name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        raise HitlPolicyError(f"{field_name} must be an exact integer")
    integer = int(value)
    if integer < minimum or integer > maximum:
        raise HitlPolicyError(f"{field_name} is outside its allowed range")
    return integer


def _canonical_decimal(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name, maximum=16)
    try:
        decimal = Decimal(text)
    except InvalidOperation as exc:
        raise HitlPolicyError(f"{field_name} must be a canonical decimal") from exc
    if not decimal.is_finite() or decimal < 0 or decimal > 1:
        raise HitlPolicyError(f"{field_name} must be between zero and one")
    canonical = _decimal_text(decimal)
    if canonical != text:
        raise HitlPolicyError(f"{field_name} must be a canonical confidence string")
    return text


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return "0" if text in {"-0", ""} else text


def _canonical_utc(value: object, field_name: str) -> datetime:
    text = _exact_text(value, field_name, maximum=20)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise HitlPolicyError(f"{field_name} must be canonical UTC") from exc
    if _utc_text(parsed) != text:
        raise HitlPolicyError(f"{field_name} must be canonical UTC")
    return parsed


def _require_utc(value: datetime, field_name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        raise HitlPolicyError(f"{field_name} must be an aware UTC datetime")
    instant = value.astimezone(UTC)
    if instant != value or value.utcoffset() != timedelta(0):
        raise HitlPolicyError(f"{field_name} must be UTC")
    return instant


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_revision(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value)).hexdigest()}"


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HitlPolicyError("HITL artifact is not canonical JSON") from exc


def _dedupe_key(*parts: str) -> str:
    return _canonical_revision(list(parts))


__all__ = [
    "HITL_PROPOSAL_SCHEMA",
    "HITL_RECEIPT_SCHEMA",
    "AutomationApprovalSignalCall",
    "AutomationApprovalSnapshot",
    "AutomationApprovalStatus",
    "AwsApprovalClientBinding",
    "GitlabApprovalClientBinding",
    "GitlabApprovalRuleSnapshot",
    "GitlabApprovalSnapshot",
    "HitlApprovalGate",
    "HitlApprovalReceipt",
    "HitlAuditEvent",
    "HitlCase",
    "HitlCaseState",
    "HitlExecutionError",
    "HitlMechanism",
    "HitlPolicyError",
    "HitlReceiptDecision",
    "HitlRemediationProposal",
    "VerifiedHitlApprovalReceipt",
    "apply_hitl_receipt",
    "authorize_hitl_proposal",
    "hitl_action_tier_revision",
    "load_hitl_proposal",
    "load_hitl_receipt",
    "parse_hitl_proposal",
    "parse_hitl_receipt",
    "reconcile_hitl_case",
]
