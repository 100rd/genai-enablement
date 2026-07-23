"""SPEC-B4 Tier-4 authorization and finite SSM compensation orchestration.

The core owns no AWS credentials or live adapters.  It accepts only explicit
ports and externally verified, exact policy material.
"""

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
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Protocol

from sre_harness.autonomy_tiers import Tier, classify
from sre_harness.autonomy_tiers.action_table import ACTION_TIER_TABLE

REMEDIATION_POLICY_SCHEMA = "sre-harness.remediation-policy-publication/v1"
REMEDIATION_REQUEST_SCHEMA = "sre-harness.remediation-request/v1"
MAX_REMEDIATION_BYTES = 1024 * 1024

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_ACCOUNT_ID = re.compile(r"^[0-9]{12}$")
_REGION = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-[1-9][0-9]*$")
_IAM_ROLE_ARN = re.compile(r"^arn:aws:iam::(?P<account>[0-9]{12}):role/[A-Za-z0-9+=,.@_/-]{1,512}$")
_SNS_TOPIC_ARN = re.compile(
    r"^arn:aws:sns:(?P<region>[a-z]{2}(?:-gov)?-[a-z]+-[1-9][0-9]*):"
    r"(?P<account>[0-9]{12}):[A-Za-z0-9_-]{1,256}$"
)
_DOCUMENT_NAME = re.compile(r"^[A-Za-z0-9_\-.:/]{3,128}$")
_DOCUMENT_VERSION = re.compile(r"^[1-9][0-9]*$")
_PARAMETER_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_CANONICAL_DECIMAL = re.compile(r"^(?:0|1|0\.\d*[1-9])$")
_BOUNDED_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_CREDENTIAL_PARAMETER_TERMS = ("password", "secret", "token", "api_key", "apikey")
_POLICY_TOKEN = object()
_VERIFIED_TOKEN = object()
_REQUEST_TOKEN = object()
_DECISION_TOKEN = object()
_RUN_TOKEN = object()
_INTEGRITY_KEY = secrets.token_bytes(32)

_POLICY_ENVELOPE_FIELDS = frozenset({"schemaVersion", "publicationRevision", "policy"})
_POLICY_FIELDS = frozenset(
    {
        "approvalRevision",
        "approvedBy",
        "awsAccountId",
        "confidenceThreshold",
        "entries",
        "evidenceScope",
        "executionRoleArn",
        "expiresAt",
        "maxRequestAgeSeconds",
        "notificationTopicArn",
        "origin",
        "policyId",
        "publishedAt",
        "region",
        "verifierRef",
    }
)
_ENTRY_FIELDS = frozenset(
    {
        "action",
        "environment",
        "forward",
        "parameterAllowlist",
        "rollback",
        "rollbackExecutionIdParameter",
    }
)
_DOCUMENT_FIELDS = frozenset({"documentName", "documentVersion", "documentSha256"})
_REQUEST_ENVELOPE_FIELDS = frozenset({"schemaVersion", "requestRevision", "request"})
_REQUEST_FIELDS = frozenset(
    {
        "action",
        "confidence",
        "environment",
        "parameters",
        "planRevision",
        "policyId",
        "policyRevision",
        "requestId",
        "requestedAt",
        "triggerId",
    }
)
_ENVIRONMENTS = frozenset({"development", "staging", "production"})
_EVIDENCE_SCOPES = frozenset({"fixture", "external_candidate"})
ACTION_T4 = frozenset(action for action, tier in ACTION_TIER_TABLE.items() if tier is Tier.T4)
_ACTION_PARAMETERS = {
    "restart_stateless_pod": frozenset(
        {"AutomationAssumeRole", "Cluster", "Namespace", "Workload"}
    ),
    "retrigger_argocd_sync": frozenset({"Application", "AutomationAssumeRole"}),
    "scale_stateless_service": frozenset(
        {
            "AutomationAssumeRole",
            "Cluster",
            "DesiredReplicas",
            "Namespace",
            "Workload",
        }
    ),
}


class RemediationPolicyError(ValueError):
    """Policy, request, authority, or classification input is inadmissible."""


class RemediationExecutionError(RuntimeError):
    """A T4 start/reconciliation precondition or external result is invalid."""


class RemediationDisposition(Enum):
    EXECUTE_T4 = "execute_t4"
    REQUIRE_T3 = "require_t3"


class RemediationRunState(Enum):
    FORWARD_RUNNING = "forward_running"
    SUCCEEDED = "succeeded"
    ROLLBACK_RUNNING = "rollback_running"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"
    ESCALATED = "escalated"


class RemediationNotificationType(Enum):
    FORWARD_STARTED = "forward_started"
    FORWARD_SUCCEEDED = "forward_succeeded"
    ROLLBACK_STARTED = "rollback_started"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"
    ESCALATED = "escalated"


class AutomationExecutionStatus(Enum):
    PENDING = "Pending"
    IN_PROGRESS = "InProgress"
    WAITING = "Waiting"
    SUCCESS = "Success"
    TIMED_OUT = "TimedOut"
    CANCELLING = "Cancelling"
    CANCELLED = "Cancelled"
    FAILED = "Failed"
    PENDING_APPROVAL = "PendingApproval"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    SCHEDULED = "Scheduled"
    RUNBOOK_IN_PROGRESS = "RunbookInProgress"
    PENDING_CHANGE_CALENDAR_OVERRIDE = "PendingChangeCalendarOverride"
    CHANGE_CALENDAR_OVERRIDE_APPROVED = "ChangeCalendarOverrideApproved"
    CHANGE_CALENDAR_OVERRIDE_REJECTED = "ChangeCalendarOverrideRejected"
    COMPLETED_WITH_SUCCESS = "CompletedWithSuccess"
    COMPLETED_WITH_FAILURE = "CompletedWithFailure"
    EXITED = "Exited"


_RUNNING_STATUSES = frozenset(
    {
        AutomationExecutionStatus.PENDING,
        AutomationExecutionStatus.IN_PROGRESS,
        AutomationExecutionStatus.WAITING,
        AutomationExecutionStatus.CANCELLING,
        AutomationExecutionStatus.SCHEDULED,
        AutomationExecutionStatus.RUNBOOK_IN_PROGRESS,
    }
)
_SUCCESS_STATUSES = frozenset(
    {
        AutomationExecutionStatus.SUCCESS,
        AutomationExecutionStatus.COMPLETED_WITH_SUCCESS,
    }
)
_FAILURE_STATUSES = frozenset(
    {
        AutomationExecutionStatus.TIMED_OUT,
        AutomationExecutionStatus.CANCELLED,
        AutomationExecutionStatus.FAILED,
        AutomationExecutionStatus.COMPLETED_WITH_FAILURE,
        AutomationExecutionStatus.EXITED,
    }
)
_HUMAN_STATUSES = frozenset(
    {
        AutomationExecutionStatus.PENDING_APPROVAL,
        AutomationExecutionStatus.APPROVED,
        AutomationExecutionStatus.REJECTED,
        AutomationExecutionStatus.PENDING_CHANGE_CALENDAR_OVERRIDE,
        AutomationExecutionStatus.CHANGE_CALENDAR_OVERRIDE_APPROVED,
        AutomationExecutionStatus.CHANGE_CALENDAR_OVERRIDE_REJECTED,
    }
)
_TERMINAL_RUN_STATES = frozenset(
    {
        RemediationRunState.SUCCEEDED,
        RemediationRunState.ROLLED_BACK,
        RemediationRunState.ROLLBACK_FAILED,
        RemediationRunState.ESCALATED,
    }
)


@dataclass(frozen=True)
class DocumentBinding:
    document_name: str
    document_version: str
    document_sha256: str


@dataclass(frozen=True)
class RemediationEntry:
    action: str
    environment: str
    forward: DocumentBinding
    rollback: DocumentBinding
    parameter_allowlist: tuple[tuple[str, tuple[str, ...]], ...]
    rollback_execution_id_parameter: str


@dataclass(frozen=True, init=False)
class RemediationPolicyPublication:
    publication_revision: str
    policy_id: str
    evidence_scope: str
    origin: str
    verifier_ref: str
    approved_by: str
    approval_revision: str
    published_at: datetime
    expires_at: datetime
    aws_account_id: str
    region: str
    execution_role_arn: str
    notification_topic_arn: str
    max_request_age_seconds: int
    confidence_threshold: str
    entries: tuple[RemediationEntry, ...]
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        publication_revision: str,
        policy_id: str,
        evidence_scope: str,
        origin: str,
        verifier_ref: str,
        approved_by: str,
        approval_revision: str,
        published_at: datetime,
        expires_at: datetime,
        aws_account_id: str,
        region: str,
        execution_role_arn: str,
        notification_topic_arn: str,
        max_request_age_seconds: int,
        confidence_threshold: str,
        entries: tuple[RemediationEntry, ...],
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _POLICY_TOKEN:
            raise TypeError("remediation policies must come from the strict parser")
        values = locals().copy()
        values.pop("self")
        values.pop("_construction_token")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _publication_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is RemediationPolicyPublication and hmac.compare_digest(
            self._integrity_seal,
            _publication_seal(self),
        )


class RemediationPolicyVerifier(Protocol):
    def verify(self, publication: RemediationPolicyPublication) -> object:
        """Return exact True only for one unchanged externally authorized publication."""


@dataclass(frozen=True, init=False)
class VerifiedRemediationPolicy:
    publication_revision: str
    policy_id: str
    evidence_scope: str
    origin: str
    verifier_ref: str
    published_at: datetime
    expires_at: datetime
    aws_account_id: str
    region: str
    execution_role_arn: str
    notification_topic_arn: str
    max_request_age_seconds: int
    confidence_threshold: str
    entries: tuple[RemediationEntry, ...]
    _approval_revision: str = field(repr=False, compare=False)
    _approved_by: str = field(repr=False, compare=False)
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        publication: RemediationPolicyPublication,
        *,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _VERIFIED_TOKEN:
            raise TypeError("verified remediation policies must come from the policy gate")
        values = {
            "publication_revision": publication.publication_revision,
            "policy_id": publication.policy_id,
            "evidence_scope": publication.evidence_scope,
            "origin": publication.origin,
            "verifier_ref": publication.verifier_ref,
            "published_at": publication.published_at,
            "expires_at": publication.expires_at,
            "aws_account_id": publication.aws_account_id,
            "region": publication.region,
            "execution_role_arn": publication.execution_role_arn,
            "notification_topic_arn": publication.notification_topic_arn,
            "max_request_age_seconds": publication.max_request_age_seconds,
            "confidence_threshold": publication.confidence_threshold,
            "entries": publication.entries,
            "_approval_revision": publication.approval_revision,
            "_approved_by": publication.approved_by,
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _verified_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is VerifiedRemediationPolicy and hmac.compare_digest(
            self._integrity_seal,
            _verified_seal(self),
        )


class RemediationPolicyGate:
    """Issue an opaque capability only through one preconfigured exact verifier."""

    def __init__(
        self,
        *,
        allowed_origins: frozenset[str],
        verifiers: dict[str, RemediationPolicyVerifier],
    ) -> None:
        self._allowed_origins = allowed_origins
        self._verifiers = dict(verifiers)

    def verify(
        self,
        publication: RemediationPolicyPublication,
        *,
        now: datetime,
    ) -> VerifiedRemediationPolicy:
        _require_publication(publication)
        instant = _require_utc_instant(now, "now")
        if publication.origin not in self._allowed_origins:
            raise RemediationPolicyError("remediation policy origin is not allowlisted")
        verifier = self._verifiers.get(publication.verifier_ref)
        if verifier is None:
            raise RemediationPolicyError("remediation policy verifier is not configured")
        if publication.published_at > instant or instant >= publication.expires_at:
            raise RemediationPolicyError("remediation policy publication is future or expired")

        before = _canonical_json(_publication_envelope(publication))
        try:
            result = verifier.verify(publication)
        except Exception as exc:
            raise RemediationPolicyError("remediation policy verification failed") from exc
        after = _canonical_json(_publication_envelope(publication))
        if before != after or not publication._is_intact():
            raise RemediationPolicyError("remediation policy was mutated during verification")
        if type(result) is not bool or result is not True:
            raise RemediationPolicyError(
                "remediation policy verification did not return exact true"
            )
        return VerifiedRemediationPolicy(publication, _construction_token=_VERIFIED_TOKEN)


@dataclass(frozen=True, init=False)
class RemediationRequest:
    request_revision: str
    request_id: str
    requested_at: datetime
    trigger_id: str
    plan_revision: str
    policy_id: str
    policy_revision: str
    action: str
    confidence: str
    environment: str
    parameters: tuple[tuple[str, tuple[str, ...]], ...]
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        request_revision: str,
        request_id: str,
        requested_at: datetime,
        trigger_id: str,
        plan_revision: str,
        policy_id: str,
        policy_revision: str,
        action: str,
        confidence: str,
        environment: str,
        parameters: tuple[tuple[str, tuple[str, ...]], ...],
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _REQUEST_TOKEN:
            raise TypeError("remediation requests must come from the strict parser")
        values = locals().copy()
        values.pop("self")
        values.pop("_construction_token")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _request_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is RemediationRequest and hmac.compare_digest(
            self._integrity_seal,
            _request_seal(self),
        )


@dataclass(frozen=True, init=False)
class RemediationDecision:
    disposition: RemediationDisposition
    reason: str
    authorized_at: datetime
    valid_until: datetime
    request_id: str
    request_revision: str
    policy_id: str
    policy_revision: str
    action: str
    environment: str
    parameters: tuple[tuple[str, tuple[str, ...]], ...]
    aws_account_id: str
    region: str
    notification_topic_arn: str
    forward_document: DocumentBinding | None
    rollback_document: DocumentBinding | None
    rollback_execution_id_parameter: str | None
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        disposition: RemediationDisposition,
        reason: str,
        authorized_at: datetime,
        valid_until: datetime,
        request: RemediationRequest,
        policy: VerifiedRemediationPolicy,
        entry: RemediationEntry | None,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _DECISION_TOKEN:
            raise TypeError("remediation decisions must come from authorization")
        values = {
            "disposition": disposition,
            "reason": reason,
            "authorized_at": authorized_at,
            "valid_until": valid_until,
            "request_id": request.request_id,
            "request_revision": request.request_revision,
            "policy_id": policy.policy_id,
            "policy_revision": policy.publication_revision,
            "action": request.action,
            "environment": request.environment,
            "parameters": request.parameters,
            "aws_account_id": policy.aws_account_id,
            "region": policy.region,
            "notification_topic_arn": policy.notification_topic_arn,
            "forward_document": entry.forward if entry is not None else None,
            "rollback_document": entry.rollback if entry is not None else None,
            "rollback_execution_id_parameter": (
                entry.rollback_execution_id_parameter if entry is not None else None
            ),
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _decision_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is RemediationDecision and hmac.compare_digest(
            self._integrity_seal,
            _decision_seal(self),
        )


@dataclass(frozen=True)
class AutomationClientBinding:
    aws_account_id: str
    region: str


@dataclass(frozen=True)
class AutomationDocumentSnapshot:
    document_name: str
    document_version: str
    document_sha256: str
    owner: str
    document_type: str
    status: str
    schema_version: str


@dataclass(frozen=True)
class StartAutomationCall:
    document_name: str
    document_version: str
    aws_account_id: str
    region: str
    parameters: dict[str, list[str]]
    client_token: str
    max_concurrency: str
    max_errors: str
    tags: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class AutomationExecutionSnapshot:
    execution_id: str
    document_name: str
    document_version: str
    status: AutomationExecutionStatus


@dataclass(frozen=True)
class RemediationNotification:
    event_type: RemediationNotificationType
    dedupe_key: str
    topic_arn: str
    request_id: str
    policy_revision: str
    action: str
    execution_id: str
    state: str
    reason: str

    def to_document(self) -> dict[str, str]:
        return {
            "eventType": self.event_type.value,
            "dedupeKey": self.dedupe_key,
            "topicArn": self.topic_arn,
            "requestId": self.request_id,
            "policyRevision": self.policy_revision,
            "action": self.action,
            "executionId": self.execution_id,
            "state": self.state,
            "reason": self.reason,
        }


class SsmAutomationClient(Protocol):
    def binding(self) -> AutomationClientBinding: ...

    def describe_document(
        self,
        document_name: str,
        document_version: str,
    ) -> AutomationDocumentSnapshot: ...

    def start_automation(self, call: StartAutomationCall) -> str: ...

    def get_automation_execution(self, execution_id: str) -> AutomationExecutionSnapshot: ...


class RemediationNotifier(Protocol):
    def notify(self, notification: RemediationNotification) -> None:
        """Deliver once per dedupe key, including across caller retries."""


@dataclass(frozen=True, init=False)
class RemediationRun:
    state: RemediationRunState
    reason: str
    request_id: str
    request_revision: str
    policy_id: str
    policy_revision: str
    action: str
    parameters: tuple[tuple[str, tuple[str, ...]], ...]
    aws_account_id: str
    region: str
    notification_topic_arn: str
    forward_document: DocumentBinding
    rollback_document: DocumentBinding
    rollback_execution_id_parameter: str
    forward_execution_id: str
    rollback_execution_id: str | None
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        state: RemediationRunState,
        reason: str,
        request_id: str,
        request_revision: str,
        policy_id: str,
        policy_revision: str,
        action: str,
        parameters: tuple[tuple[str, tuple[str, ...]], ...],
        aws_account_id: str,
        region: str,
        notification_topic_arn: str,
        forward_document: DocumentBinding,
        rollback_document: DocumentBinding,
        rollback_execution_id_parameter: str,
        forward_execution_id: str,
        rollback_execution_id: str | None,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _RUN_TOKEN:
            raise TypeError("remediation runs must come from the B4 state machine")
        values = locals().copy()
        values.pop("self")
        values.pop("_construction_token")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _run_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is RemediationRun and hmac.compare_digest(
            self._integrity_seal,
            _run_seal(self),
        )


def parse_remediation_policy(raw: bytes) -> RemediationPolicyPublication:
    payload = _parse_envelope(raw, "remediation policy")
    _exact_fields(payload, _POLICY_ENVELOPE_FIELDS, "remediation policy")
    if payload["schemaVersion"] != REMEDIATION_POLICY_SCHEMA:
        raise RemediationPolicyError("unsupported remediation policy schemaVersion")
    publication_revision = _exact_sha256(
        payload["publicationRevision"],
        "publicationRevision",
    )
    policy = _exact_object(payload["policy"], "policy")
    _exact_fields(policy, _POLICY_FIELDS, "policy")
    if publication_revision != _canonical_digest(policy):
        raise RemediationPolicyError("publicationRevision does not match exact policy content")

    policy_id = _bounded_id(policy["policyId"], "policy.policyId")
    evidence_scope = _exact_text(policy["evidenceScope"], "policy.evidenceScope", maximum=32)
    if evidence_scope not in _EVIDENCE_SCOPES:
        raise RemediationPolicyError("policy.evidenceScope is not fixture or external_candidate")
    origin = _bounded_id(policy["origin"], "policy.origin")
    verifier_ref = _bounded_id(policy["verifierRef"], "policy.verifierRef")
    approved_by = _bounded_id(policy["approvedBy"], "policy.approvedBy")
    approval_revision = _exact_sha256(policy["approvalRevision"], "policy.approvalRevision")
    published_at = _canonical_utc(policy["publishedAt"], "policy.publishedAt")
    expires_at = _canonical_utc(policy["expiresAt"], "policy.expiresAt")
    if expires_at <= published_at:
        raise RemediationPolicyError("policy expiry must be after publication")

    aws_account_id = _exact_text(policy["awsAccountId"], "policy.awsAccountId", maximum=12)
    if not _ACCOUNT_ID.fullmatch(aws_account_id):
        raise RemediationPolicyError("policy.awsAccountId must be a 12-digit account id")
    region = _exact_text(policy["region"], "policy.region", maximum=32)
    if not _REGION.fullmatch(region):
        raise RemediationPolicyError("policy.region must be a canonical AWS region")
    execution_role_arn = _exact_text(
        policy["executionRoleArn"],
        "policy.executionRoleArn",
        maximum=600,
    )
    role_match = _IAM_ROLE_ARN.fullmatch(execution_role_arn)
    if role_match is None or role_match.group("account") != aws_account_id:
        raise RemediationPolicyError("policy.executionRoleArn must be an account-owned role")
    notification_topic_arn = _exact_text(
        policy["notificationTopicArn"],
        "policy.notificationTopicArn",
        maximum=400,
    )
    topic_match = _SNS_TOPIC_ARN.fullmatch(notification_topic_arn)
    if (
        topic_match is None
        or topic_match.group("account") != aws_account_id
        or topic_match.group("region") != region
    ):
        raise RemediationPolicyError(
            "policy.notificationTopicArn must match the policy account and region"
        )
    max_request_age_seconds = _exact_int(
        policy["maxRequestAgeSeconds"],
        "policy.maxRequestAgeSeconds",
        minimum=1,
        maximum=3600,
    )
    confidence_threshold = _canonical_decimal(
        policy["confidenceThreshold"],
        "policy.confidenceThreshold",
        allow_zero=False,
        allow_one=False,
    )
    entries = _parse_entries(
        policy["entries"],
        execution_role_arn=execution_role_arn,
    )
    return RemediationPolicyPublication(
        publication_revision=publication_revision,
        policy_id=policy_id,
        evidence_scope=evidence_scope,
        origin=origin,
        verifier_ref=verifier_ref,
        approved_by=approved_by,
        approval_revision=approval_revision,
        published_at=published_at,
        expires_at=expires_at,
        aws_account_id=aws_account_id,
        region=region,
        execution_role_arn=execution_role_arn,
        notification_topic_arn=notification_topic_arn,
        max_request_age_seconds=max_request_age_seconds,
        confidence_threshold=confidence_threshold,
        entries=entries,
        _construction_token=_POLICY_TOKEN,
    )


def load_remediation_policy(path: Path) -> RemediationPolicyPublication:
    return parse_remediation_policy(_load_bounded_file(path, "remediation policy"))


def parse_remediation_request(raw: bytes) -> RemediationRequest:
    payload = _parse_envelope(raw, "remediation request")
    _exact_fields(payload, _REQUEST_ENVELOPE_FIELDS, "remediation request")
    if payload["schemaVersion"] != REMEDIATION_REQUEST_SCHEMA:
        raise RemediationPolicyError("unsupported remediation request schemaVersion")
    request_revision = _exact_sha256(payload["requestRevision"], "requestRevision")
    request = _exact_object(payload["request"], "request")
    _exact_fields(request, _REQUEST_FIELDS, "request")
    if request_revision != _canonical_digest(request):
        raise RemediationPolicyError("requestRevision does not match exact request content")

    request_id = _canonical_uuid(request["requestId"], "request.requestId")
    requested_at = _canonical_utc(request["requestedAt"], "request.requestedAt")
    trigger_id = _bounded_id(request["triggerId"], "request.triggerId")
    plan_revision = _exact_sha256(request["planRevision"], "request.planRevision")
    policy_id = _bounded_id(request["policyId"], "request.policyId")
    policy_revision = _exact_sha256(request["policyRevision"], "request.policyRevision")
    action = _bounded_id(request["action"], "request.action")
    confidence = _canonical_decimal(
        request["confidence"],
        "request.confidence",
        allow_zero=True,
        allow_one=True,
    )
    environment = _exact_text(request["environment"], "request.environment", maximum=32)
    if environment not in _ENVIRONMENTS:
        raise RemediationPolicyError("request.environment is unknown")
    parameters = _parameter_map(request["parameters"], "request.parameters")
    return RemediationRequest(
        request_revision=request_revision,
        request_id=request_id,
        requested_at=requested_at,
        trigger_id=trigger_id,
        plan_revision=plan_revision,
        policy_id=policy_id,
        policy_revision=policy_revision,
        action=action,
        confidence=confidence,
        environment=environment,
        parameters=parameters,
        _construction_token=_REQUEST_TOKEN,
    )


def load_remediation_request(path: Path) -> RemediationRequest:
    return parse_remediation_request(_load_bounded_file(path, "remediation request"))


def authorize_remediation(
    request: RemediationRequest,
    policy: VerifiedRemediationPolicy,
    *,
    now: datetime,
) -> RemediationDecision:
    _require_request(request)
    _require_verified(policy)
    instant = _require_utc_instant(now, "now")
    entry = next((item for item in policy.entries if item.action == request.action), None)
    request_expires = request.requested_at + timedelta(seconds=policy.max_request_age_seconds)
    valid_until = min(request_expires, policy.expires_at)

    if (
        request.policy_id != policy.policy_id
        or request.policy_revision != policy.publication_revision
    ):
        return _decision(
            request,
            policy,
            entry,
            instant,
            valid_until,
            RemediationDisposition.REQUIRE_T3,
            "policy-binding-mismatch-requires-t3",
        )
    if request.requested_at > instant or instant > request_expires:
        return _decision(
            request,
            policy,
            entry,
            instant,
            valid_until,
            RemediationDisposition.REQUIRE_T3,
            "request-time-requires-t3",
        )
    if instant < policy.published_at or instant >= policy.expires_at:
        return _decision(
            request,
            policy,
            entry,
            instant,
            valid_until,
            RemediationDisposition.REQUIRE_T3,
            "policy-time-requires-t3",
        )
    if policy.evidence_scope == "fixture":
        return _decision(
            request,
            policy,
            entry,
            instant,
            valid_until,
            RemediationDisposition.REQUIRE_T3,
            "fixture-policy-requires-t3",
        )

    exact_confidence = Decimal(request.confidence)
    exact_threshold = Decimal(policy.confidence_threshold)
    classification = classify(
        request.action,
        float(exact_confidence),
        threshold=float(exact_threshold),
    )
    if classification.off_plan:
        return _decision(
            request,
            policy,
            entry,
            instant,
            valid_until,
            RemediationDisposition.REQUIRE_T3,
            "off-plan-action-requires-t3",
        )
    if exact_confidence < exact_threshold or classification.tier is not Tier.T4:
        return _decision(
            request,
            policy,
            entry,
            instant,
            valid_until,
            RemediationDisposition.REQUIRE_T3,
            "confidence-degraded-to-t3",
        )
    if entry is None:
        return _decision(
            request,
            policy,
            None,
            instant,
            valid_until,
            RemediationDisposition.REQUIRE_T3,
            "action-not-allowlisted-requires-t3",
        )
    if request.environment != entry.environment:
        return _decision(
            request,
            policy,
            entry,
            instant,
            valid_until,
            RemediationDisposition.REQUIRE_T3,
            "environment-not-allowlisted-requires-t3",
        )
    if not _parameters_allowed(request.parameters, entry.parameter_allowlist):
        return _decision(
            request,
            policy,
            entry,
            instant,
            valid_until,
            RemediationDisposition.REQUIRE_T3,
            "parameters-not-allowlisted-requires-t3",
        )
    return _decision(
        request,
        policy,
        entry,
        instant,
        valid_until,
        RemediationDisposition.EXECUTE_T4,
        "exact-preauthorized-t4-match",
    )


def start_t4_remediation(
    decision: RemediationDecision,
    client: SsmAutomationClient,
    notifier: RemediationNotifier,
    *,
    now: datetime,
) -> RemediationRun:
    _require_decision(decision)
    if decision.disposition is not RemediationDisposition.EXECUTE_T4:
        raise RemediationExecutionError("remediation decision does not authorize T4")
    instant = _require_utc_instant(now, "now")
    if instant < decision.authorized_at or instant >= decision.valid_until:
        raise RemediationExecutionError("remediation decision is future or expired")
    forward = decision.forward_document
    rollback = decision.rollback_document
    rollback_parameter = decision.rollback_execution_id_parameter
    if forward is None or rollback is None or rollback_parameter is None:
        raise RemediationExecutionError("T4 decision has no exact runbook bindings")

    _verify_client_binding(client, decision.aws_account_id, decision.region)
    snapshot = _describe_document(client, forward)
    _verify_document(forward, snapshot, decision.aws_account_id)
    call = _start_call(
        decision.request_revision,
        decision.policy_revision,
        decision.request_id,
        decision.policy_id,
        decision.action,
        decision.aws_account_id,
        decision.region,
        forward,
        decision.parameters,
        phase="forward",
    )
    execution_id = _start(client, call)
    run = RemediationRun(
        state=RemediationRunState.FORWARD_RUNNING,
        reason="forward-automation-running",
        request_id=decision.request_id,
        request_revision=decision.request_revision,
        policy_id=decision.policy_id,
        policy_revision=decision.policy_revision,
        action=decision.action,
        parameters=decision.parameters,
        aws_account_id=decision.aws_account_id,
        region=decision.region,
        notification_topic_arn=decision.notification_topic_arn,
        forward_document=forward,
        rollback_document=rollback,
        rollback_execution_id_parameter=rollback_parameter,
        forward_execution_id=execution_id,
        rollback_execution_id=None,
        _construction_token=_RUN_TOKEN,
    )
    _notify(
        notifier,
        run,
        RemediationNotificationType.FORWARD_STARTED,
        execution_id,
        "forward-automation-started",
    )
    return run


def reconcile_t4_remediation(
    run: RemediationRun,
    client: SsmAutomationClient,
    notifier: RemediationNotifier,
) -> RemediationRun:
    _require_run(run)
    if run.state in _TERMINAL_RUN_STATES:
        return run
    _verify_client_binding(client, run.aws_account_id, run.region)
    if run.state is RemediationRunState.FORWARD_RUNNING:
        return _reconcile_forward(run, client, notifier)
    if run.state is RemediationRunState.ROLLBACK_RUNNING:
        return _reconcile_rollback(run, client, notifier)
    raise RemediationExecutionError("remediation run has an unknown state")


def _reconcile_forward(
    run: RemediationRun,
    client: SsmAutomationClient,
    notifier: RemediationNotifier,
) -> RemediationRun:
    snapshot = _get_execution(client, run.forward_execution_id)
    _verify_execution(snapshot, run.forward_execution_id, run.forward_document)
    if snapshot.status in _RUNNING_STATUSES:
        return run
    if snapshot.status in _SUCCESS_STATUSES:
        _notify(
            notifier,
            run,
            RemediationNotificationType.FORWARD_SUCCEEDED,
            run.forward_execution_id,
            "forward-automation-succeeded",
        )
        return _transition(run, RemediationRunState.SUCCEEDED, "forward-automation-succeeded")
    if snapshot.status in _HUMAN_STATUSES:
        _notify(
            notifier,
            run,
            RemediationNotificationType.ESCALATED,
            run.forward_execution_id,
            "automation-requires-human-control",
        )
        return _transition(
            run,
            RemediationRunState.ESCALATED,
            "automation-requires-human-control",
        )
    if snapshot.status in _FAILURE_STATUSES:
        try:
            rollback_snapshot = _describe_document(client, run.rollback_document)
            _verify_document(run.rollback_document, rollback_snapshot, run.aws_account_id)
        except Exception:
            _notify(
                notifier,
                run,
                RemediationNotificationType.ESCALATED,
                run.forward_execution_id,
                "rollback-document-verification-failed",
            )
            return _transition(
                run,
                RemediationRunState.ESCALATED,
                "rollback-document-verification-failed",
            )
        parameters = _parameter_dict(run.parameters)
        parameters[run.rollback_execution_id_parameter] = [run.forward_execution_id]
        call = _start_call(
            run.request_revision,
            run.policy_revision,
            run.request_id,
            run.policy_id,
            run.action,
            run.aws_account_id,
            run.region,
            run.rollback_document,
            tuple((key, tuple(values)) for key, values in sorted(parameters.items())),
            phase="rollback",
        )
        rollback_execution_id = _start(client, call)
        transitioned = _transition(
            run,
            RemediationRunState.ROLLBACK_RUNNING,
            "rollback-automation-running",
            rollback_execution_id=rollback_execution_id,
        )
        _notify(
            notifier,
            transitioned,
            RemediationNotificationType.ROLLBACK_STARTED,
            rollback_execution_id,
            "rollback-automation-started",
        )
        return transitioned
    raise RemediationExecutionError("forward automation returned an unknown status")


def _reconcile_rollback(
    run: RemediationRun,
    client: SsmAutomationClient,
    notifier: RemediationNotifier,
) -> RemediationRun:
    execution_id = run.rollback_execution_id
    if execution_id is None:
        raise RemediationExecutionError("rollback-running state has no execution id")
    snapshot = _get_execution(client, execution_id)
    _verify_execution(snapshot, execution_id, run.rollback_document)
    if snapshot.status in _RUNNING_STATUSES:
        return run
    if snapshot.status in _SUCCESS_STATUSES:
        _notify(
            notifier,
            run,
            RemediationNotificationType.ROLLED_BACK,
            execution_id,
            "rollback-automation-succeeded",
        )
        return _transition(run, RemediationRunState.ROLLED_BACK, "rollback-automation-succeeded")
    if snapshot.status in _FAILURE_STATUSES:
        _notify(
            notifier,
            run,
            RemediationNotificationType.ROLLBACK_FAILED,
            execution_id,
            "rollback-automation-failed",
        )
        return _transition(run, RemediationRunState.ROLLBACK_FAILED, "rollback-automation-failed")
    if snapshot.status in _HUMAN_STATUSES:
        _notify(
            notifier,
            run,
            RemediationNotificationType.ESCALATED,
            execution_id,
            "rollback-requires-human-control",
        )
        return _transition(run, RemediationRunState.ESCALATED, "rollback-requires-human-control")
    raise RemediationExecutionError("rollback automation returned an unknown status")


def _parse_entries(value: object, *, execution_role_arn: str) -> tuple[RemediationEntry, ...]:
    if type(value) is not list or not value or len(value) > 16:
        raise RemediationPolicyError("policy.entries must be a non-empty bounded exact list")
    entries: list[RemediationEntry] = []
    for index, raw in enumerate(value):
        row = _exact_object(raw, f"policy.entries[{index}]")
        _exact_fields(row, _ENTRY_FIELDS, f"policy.entries[{index}]")
        action = _bounded_id(row["action"], f"policy.entries[{index}].action")
        if action not in ACTION_T4:
            raise RemediationPolicyError("policy entries may contain only canonical T4 actions")
        environment = _exact_text(
            row["environment"],
            f"policy.entries[{index}].environment",
            maximum=32,
        )
        if environment not in _ENVIRONMENTS:
            raise RemediationPolicyError("policy entry environment is unknown")
        forward = _document_binding(row["forward"], f"policy.entries[{index}].forward")
        rollback = _document_binding(row["rollback"], f"policy.entries[{index}].rollback")
        if forward == rollback or forward.document_name == rollback.document_name:
            raise RemediationPolicyError("forward and rollback documents must be distinct")
        allowlist = _parameter_map(
            row["parameterAllowlist"],
            f"policy.entries[{index}].parameterAllowlist",
        )
        allowed = dict(allowlist)
        if allowed.get("AutomationAssumeRole") != (execution_role_arn,):
            raise RemediationPolicyError(
                "every entry must bind AutomationAssumeRole to the policy execution role"
            )
        if frozenset(allowed) != _ACTION_PARAMETERS[action]:
            raise RemediationPolicyError(
                "policy entry parameters must match the closed action-specific v1 contract"
            )
        for parameter_name, values in allowlist:
            if parameter_name != "DesiredReplicas" and len(values) != 1:
                raise RemediationPolicyError(
                    "target parameters must bind one exact value without cross-product scope"
                )
        if action == "scale_stateless_service":
            desired_replicas = allowed["DesiredReplicas"]
            try:
                replica_values = tuple(int(value) for value in desired_replicas)
            except ValueError as exc:
                raise RemediationPolicyError(
                    "DesiredReplicas allowlist must contain positive canonical integers"
                ) from exc
            if (
                any(value < 1 or value > 100 for value in replica_values)
                or tuple(str(value) for value in replica_values) != desired_replicas
                or replica_values != tuple(sorted(set(replica_values)))
            ):
                raise RemediationPolicyError(
                    "DesiredReplicas allowlist must be sorted positive canonical integers up to 100"
                )
        rollback_parameter = _parameter_name(
            row["rollbackExecutionIdParameter"],
            f"policy.entries[{index}].rollbackExecutionIdParameter",
            allow_execution_id=True,
        )
        if rollback_parameter in allowed:
            raise RemediationPolicyError("rollback execution id parameter must be runtime-supplied")
        entries.append(
            RemediationEntry(
                action=action,
                environment=environment,
                forward=forward,
                rollback=rollback,
                parameter_allowlist=allowlist,
                rollback_execution_id_parameter=rollback_parameter,
            )
        )
    actions = tuple(entry.action for entry in entries)
    if actions != tuple(sorted(set(actions))):
        raise RemediationPolicyError("policy entries must be sorted and unique by action")
    return tuple(entries)


def _document_binding(value: object, field_name: str) -> DocumentBinding:
    row = _exact_object(value, field_name)
    _exact_fields(row, _DOCUMENT_FIELDS, field_name)
    name = _exact_text(row["documentName"], f"{field_name}.documentName", maximum=128)
    if not _DOCUMENT_NAME.fullmatch(name):
        raise RemediationPolicyError(f"{field_name}.documentName is invalid")
    version = _exact_text(row["documentVersion"], f"{field_name}.documentVersion", maximum=16)
    if not _DOCUMENT_VERSION.fullmatch(version):
        raise RemediationPolicyError(
            f"{field_name}.documentVersion must be a positive numeric version"
        )
    digest = _exact_sha256(row["documentSha256"], f"{field_name}.documentSha256")
    return DocumentBinding(name, version, digest)


def _parameter_map(
    value: object,
    field_name: str,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    mapping = _exact_object(value, field_name)
    if not mapping or len(mapping) > 16 or tuple(mapping) != tuple(sorted(mapping)):
        raise RemediationPolicyError(f"{field_name} keys must be non-empty, sorted, and bounded")
    result: list[tuple[str, tuple[str, ...]]] = []
    for name, raw_values in mapping.items():
        parameter_name = _parameter_name(name, f"{field_name}.{name}")
        if type(raw_values) is not list or not raw_values or len(raw_values) > 64:
            raise RemediationPolicyError(f"{field_name}.{name} must be a non-empty bounded list")
        values = tuple(
            _exact_text(item, f"{field_name}.{name}", maximum=512) for item in raw_values
        )
        if values != tuple(sorted(set(values))) or any("*" in item for item in values):
            raise RemediationPolicyError(
                f"{field_name}.{name} values must be sorted, unique, and wildcard-free"
            )
        result.append((parameter_name, values))
    return tuple(result)


def _parameter_name(value: object, field_name: str, *, allow_execution_id: bool = False) -> str:
    text = _exact_text(value, field_name, maximum=64)
    if not _PARAMETER_NAME.fullmatch(text):
        raise RemediationPolicyError(f"{field_name} is not a bounded SSM parameter name")
    lowered = text.lower()
    if not allow_execution_id and any(term in lowered for term in _CREDENTIAL_PARAMETER_TERMS):
        raise RemediationPolicyError(f"{field_name} is credential-like and forbidden")
    return text


def _parameters_allowed(
    requested: tuple[tuple[str, tuple[str, ...]], ...],
    allowed: tuple[tuple[str, tuple[str, ...]], ...],
) -> bool:
    if tuple(name for name, _ in requested) != tuple(name for name, _ in allowed):
        return False
    allowed_map = dict(allowed)
    return all(set(values).issubset(allowed_map[name]) for name, values in requested)


def _decision(
    request: RemediationRequest,
    policy: VerifiedRemediationPolicy,
    entry: RemediationEntry | None,
    authorized_at: datetime,
    valid_until: datetime,
    disposition: RemediationDisposition,
    reason: str,
) -> RemediationDecision:
    return RemediationDecision(
        disposition=disposition,
        reason=reason,
        authorized_at=authorized_at,
        valid_until=valid_until,
        request=request,
        policy=policy,
        entry=entry,
        _construction_token=_DECISION_TOKEN,
    )


def _describe_document(
    client: SsmAutomationClient,
    binding: DocumentBinding,
) -> AutomationDocumentSnapshot:
    try:
        snapshot = client.describe_document(binding.document_name, binding.document_version)
    except Exception as exc:
        raise RemediationExecutionError("SSM document description failed") from exc
    if type(snapshot) is not AutomationDocumentSnapshot:
        raise RemediationExecutionError("SSM document description is not exact")
    return snapshot


def _verify_client_binding(
    client: SsmAutomationClient,
    aws_account_id: str,
    region: str,
) -> None:
    try:
        binding = client.binding()
    except Exception as exc:
        raise RemediationExecutionError("SSM client binding is unavailable") from exc
    if (
        type(binding) is not AutomationClientBinding
        or binding.aws_account_id != aws_account_id
        or binding.region != region
    ):
        raise RemediationExecutionError(
            "SSM client binding does not match policy account and region"
        )


def _verify_document(
    binding: DocumentBinding,
    snapshot: AutomationDocumentSnapshot,
    account_id: str,
) -> None:
    if (
        snapshot.document_name != binding.document_name
        or snapshot.document_version != binding.document_version
        or snapshot.document_sha256 != binding.document_sha256
        or snapshot.owner != account_id
        or snapshot.document_type != "Automation"
        or snapshot.status != "Active"
        or snapshot.schema_version != "0.3"
    ):
        raise RemediationExecutionError("SSM document binding does not match the allowlist")


def _start_call(
    request_revision: str,
    policy_revision: str,
    request_id: str,
    policy_id: str,
    action: str,
    aws_account_id: str,
    region: str,
    binding: DocumentBinding,
    parameters: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    phase: str,
) -> StartAutomationCall:
    client_token = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"sre-harness:{request_revision}:{policy_revision}:{phase}",
        )
    )
    return StartAutomationCall(
        document_name=binding.document_name,
        document_version=binding.document_version,
        aws_account_id=aws_account_id,
        region=region,
        parameters=_parameter_dict(parameters),
        client_token=client_token,
        max_concurrency="1",
        max_errors="0",
        tags=(
            ("sre-harness-action", action),
            ("sre-harness-policy", policy_id),
            ("sre-harness-request", request_id),
        ),
    )


def _start(client: SsmAutomationClient, call: StartAutomationCall) -> str:
    try:
        execution_id = client.start_automation(call)
    except Exception as exc:
        raise RemediationExecutionError("SSM automation start failed") from exc
    try:
        return _canonical_uuid(execution_id, "automation execution id")
    except RemediationPolicyError as exc:
        raise RemediationExecutionError("SSM returned an invalid execution id") from exc


def _get_execution(
    client: SsmAutomationClient,
    execution_id: str,
) -> AutomationExecutionSnapshot:
    try:
        snapshot = client.get_automation_execution(execution_id)
    except Exception as exc:
        raise RemediationExecutionError("SSM automation observation failed") from exc
    if type(snapshot) is not AutomationExecutionSnapshot:
        raise RemediationExecutionError("SSM automation observation is not exact")
    return snapshot


def _verify_execution(
    snapshot: AutomationExecutionSnapshot,
    execution_id: str,
    binding: DocumentBinding,
) -> None:
    if (
        snapshot.execution_id != execution_id
        or snapshot.document_name != binding.document_name
        or snapshot.document_version != binding.document_version
        or type(snapshot.status) is not AutomationExecutionStatus
    ):
        raise RemediationExecutionError("SSM automation execution identity does not match")


def _notify(
    notifier: RemediationNotifier,
    run: RemediationRun,
    event_type: RemediationNotificationType,
    execution_id: str,
    reason: str,
) -> None:
    key_content = {
        "requestRevision": run.request_revision,
        "policyRevision": run.policy_revision,
        "eventType": event_type.value,
        "executionId": execution_id,
    }
    notification = RemediationNotification(
        event_type=event_type,
        dedupe_key=_canonical_digest(key_content),
        topic_arn=run.notification_topic_arn,
        request_id=run.request_id,
        policy_revision=run.policy_revision,
        action=run.action,
        execution_id=execution_id,
        state=event_type.value,
        reason=reason,
    )
    try:
        notifier.notify(notification)
    except Exception as exc:
        raise RemediationExecutionError("remediation notification failed") from exc


def _transition(
    run: RemediationRun,
    state: RemediationRunState,
    reason: str,
    *,
    rollback_execution_id: str | None = None,
) -> RemediationRun:
    return RemediationRun(
        state=state,
        reason=reason,
        request_id=run.request_id,
        request_revision=run.request_revision,
        policy_id=run.policy_id,
        policy_revision=run.policy_revision,
        action=run.action,
        parameters=run.parameters,
        aws_account_id=run.aws_account_id,
        region=run.region,
        notification_topic_arn=run.notification_topic_arn,
        forward_document=run.forward_document,
        rollback_document=run.rollback_document,
        rollback_execution_id_parameter=run.rollback_execution_id_parameter,
        forward_execution_id=run.forward_execution_id,
        rollback_execution_id=(
            rollback_execution_id
            if rollback_execution_id is not None
            else run.rollback_execution_id
        ),
        _construction_token=_RUN_TOKEN,
    )


def _publication_policy(publication: RemediationPolicyPublication) -> dict[str, object]:
    return {
        "approvalRevision": publication.approval_revision,
        "approvedBy": publication.approved_by,
        "awsAccountId": publication.aws_account_id,
        "confidenceThreshold": publication.confidence_threshold,
        "entries": [_entry_document(entry) for entry in publication.entries],
        "evidenceScope": publication.evidence_scope,
        "executionRoleArn": publication.execution_role_arn,
        "expiresAt": _utc_text(publication.expires_at),
        "maxRequestAgeSeconds": publication.max_request_age_seconds,
        "notificationTopicArn": publication.notification_topic_arn,
        "origin": publication.origin,
        "policyId": publication.policy_id,
        "publishedAt": _utc_text(publication.published_at),
        "region": publication.region,
        "verifierRef": publication.verifier_ref,
    }


def _publication_envelope(publication: RemediationPolicyPublication) -> dict[str, object]:
    return {
        "schemaVersion": REMEDIATION_POLICY_SCHEMA,
        "publicationRevision": publication.publication_revision,
        "policy": _publication_policy(publication),
    }


def _entry_document(entry: RemediationEntry) -> dict[str, object]:
    return {
        "action": entry.action,
        "environment": entry.environment,
        "forward": _binding_document(entry.forward),
        "parameterAllowlist": _parameter_dict(entry.parameter_allowlist),
        "rollback": _binding_document(entry.rollback),
        "rollbackExecutionIdParameter": entry.rollback_execution_id_parameter,
    }


def _binding_document(binding: DocumentBinding) -> dict[str, str]:
    return {
        "documentName": binding.document_name,
        "documentVersion": binding.document_version,
        "documentSha256": binding.document_sha256,
    }


def _publication_seal(publication: RemediationPolicyPublication) -> str:
    return _seal(_publication_envelope(publication))


def _verified_document(policy: VerifiedRemediationPolicy) -> dict[str, object]:
    return {
        "publicationRevision": policy.publication_revision,
        "policyId": policy.policy_id,
        "evidenceScope": policy.evidence_scope,
        "origin": policy.origin,
        "verifierRef": policy.verifier_ref,
        "approvedBy": policy._approved_by,
        "approvalRevision": policy._approval_revision,
        "publishedAt": _utc_text(policy.published_at),
        "expiresAt": _utc_text(policy.expires_at),
        "awsAccountId": policy.aws_account_id,
        "region": policy.region,
        "executionRoleArn": policy.execution_role_arn,
        "notificationTopicArn": policy.notification_topic_arn,
        "maxRequestAgeSeconds": policy.max_request_age_seconds,
        "confidenceThreshold": policy.confidence_threshold,
        "entries": [_entry_document(entry) for entry in policy.entries],
    }


def _verified_seal(policy: VerifiedRemediationPolicy) -> str:
    return _seal(_verified_document(policy))


def _request_body(request: RemediationRequest) -> dict[str, object]:
    return {
        "requestId": request.request_id,
        "requestedAt": _utc_text(request.requested_at),
        "triggerId": request.trigger_id,
        "planRevision": request.plan_revision,
        "policyId": request.policy_id,
        "policyRevision": request.policy_revision,
        "action": request.action,
        "confidence": request.confidence,
        "environment": request.environment,
        "parameters": _parameter_dict(request.parameters),
    }


def _request_envelope(request: RemediationRequest) -> dict[str, object]:
    return {
        "schemaVersion": REMEDIATION_REQUEST_SCHEMA,
        "requestRevision": request.request_revision,
        "request": _request_body(request),
    }


def _request_seal(request: RemediationRequest) -> str:
    return _seal(_request_envelope(request))


def _decision_document(decision: RemediationDecision) -> dict[str, object]:
    return {
        "disposition": decision.disposition.value,
        "reason": decision.reason,
        "authorizedAt": _utc_text(decision.authorized_at),
        "validUntil": _utc_text(decision.valid_until),
        "requestId": decision.request_id,
        "requestRevision": decision.request_revision,
        "policyId": decision.policy_id,
        "policyRevision": decision.policy_revision,
        "action": decision.action,
        "environment": decision.environment,
        "parameters": _parameter_dict(decision.parameters),
        "awsAccountId": decision.aws_account_id,
        "region": decision.region,
        "notificationTopicArn": decision.notification_topic_arn,
        "forwardDocument": (
            _binding_document(decision.forward_document)
            if decision.forward_document is not None
            else None
        ),
        "rollbackDocument": (
            _binding_document(decision.rollback_document)
            if decision.rollback_document is not None
            else None
        ),
        "rollbackExecutionIdParameter": decision.rollback_execution_id_parameter,
    }


def _decision_seal(decision: RemediationDecision) -> str:
    return _seal(_decision_document(decision))


def _run_document(run: RemediationRun) -> dict[str, object]:
    return {
        "state": run.state.value,
        "reason": run.reason,
        "requestId": run.request_id,
        "requestRevision": run.request_revision,
        "policyId": run.policy_id,
        "policyRevision": run.policy_revision,
        "action": run.action,
        "parameters": _parameter_dict(run.parameters),
        "awsAccountId": run.aws_account_id,
        "region": run.region,
        "notificationTopicArn": run.notification_topic_arn,
        "forwardDocument": _binding_document(run.forward_document),
        "rollbackDocument": _binding_document(run.rollback_document),
        "rollbackExecutionIdParameter": run.rollback_execution_id_parameter,
        "forwardExecutionId": run.forward_execution_id,
        "rollbackExecutionId": run.rollback_execution_id,
    }


def _run_seal(run: RemediationRun) -> str:
    return _seal(_run_document(run))


def _seal(value: object) -> str:
    return hmac.new(_INTEGRITY_KEY, _canonical_json(value), hashlib.sha256).hexdigest()


def _require_publication(publication: RemediationPolicyPublication) -> None:
    if type(publication) is not RemediationPolicyPublication or not publication._is_intact():
        raise RemediationPolicyError("remediation policy is raw or mutated")


def _require_verified(policy: VerifiedRemediationPolicy) -> None:
    if type(policy) is not VerifiedRemediationPolicy or not policy._is_intact():
        raise RemediationPolicyError("verified remediation policy is raw or mutated")


def _require_request(request: RemediationRequest) -> None:
    if type(request) is not RemediationRequest or not request._is_intact():
        raise RemediationPolicyError("remediation request is raw or mutated")


def _require_decision(decision: RemediationDecision) -> None:
    if type(decision) is not RemediationDecision or not decision._is_intact():
        raise RemediationExecutionError("remediation decision is raw or mutated")


def _require_run(run: RemediationRun) -> None:
    if type(run) is not RemediationRun or not run._is_intact():
        raise RemediationExecutionError("remediation run is raw or mutated")


def _parse_envelope(raw: bytes, field_name: str) -> dict[str, object]:
    if type(raw) is not bytes:
        raise RemediationPolicyError(f"{field_name} must be exact bytes")
    if len(raw) > MAX_REMEDIATION_BYTES:
        raise RemediationPolicyError(f"{field_name} exceeds maximum {MAX_REMEDIATION_BYTES} bytes")
    try:
        text = raw.decode("utf-8", errors="strict")
        payload = json.loads(
            text,
            object_pairs_hook=_closed_object,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RemediationPolicyError(f"{field_name} is not strict UTF-8 JSON") from exc
    if type(payload) is not dict:
        raise RemediationPolicyError(f"{field_name} must be a JSON object")
    return payload


def _load_bounded_file(path: Path, field_name: str) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RemediationPolicyError(f"{field_name} file unavailable: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise RemediationPolicyError(f"{field_name} file must not be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise RemediationPolicyError(f"{field_name} file must be a regular file")
    if metadata.st_size > MAX_REMEDIATION_BYTES:
        raise RemediationPolicyError(f"{field_name} exceeds maximum {MAX_REMEDIATION_BYTES} bytes")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise RemediationPolicyError(f"{field_name} must remain a regular file")
            return handle.read(MAX_REMEDIATION_BYTES + 1)
    except RemediationPolicyError:
        raise
    except OSError as exc:
        raise RemediationPolicyError(f"{field_name} file unavailable: {path}") from exc


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RemediationPolicyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> object:
    raise RemediationPolicyError(f"non-finite JSON number is not allowed: {value}")


def _exact_object(value: object, field_name: str) -> dict[str, object]:
    if type(value) is not dict:
        raise RemediationPolicyError(f"{field_name} must be an exact object")
    return value


def _exact_fields(value: dict[str, object], expected: frozenset[str], field_name: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise RemediationPolicyError(
            f"{field_name} fields are not closed "
            f"(missing={sorted(expected - actual)}, unknown={sorted(actual - expected)})"
        )


def _exact_text(value: object, field_name: str, *, maximum: int = 256) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise RemediationPolicyError(f"{field_name} must be a non-blank exact string")
    if len(value) > maximum or any(ord(character) < 32 for character in value):
        raise RemediationPolicyError(f"{field_name} must be bounded printable text")
    return value


def _bounded_id(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name)
    if not _BOUNDED_ID.fullmatch(text):
        raise RemediationPolicyError(f"{field_name} is not a bounded identifier")
    return text


def _exact_sha256(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name)
    if not _SHA256.fullmatch(text):
        raise RemediationPolicyError(f"{field_name} must be an exact SHA-256")
    return text


def _exact_int(
    value: object,
    field_name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int:
        raise RemediationPolicyError(f"{field_name} must be an exact integer")
    integer = int(value)
    if integer < minimum or integer > maximum:
        raise RemediationPolicyError(f"{field_name} must be between {minimum} and {maximum}")
    return integer


def _canonical_decimal(
    value: object,
    field_name: str,
    *,
    allow_zero: bool,
    allow_one: bool,
) -> str:
    text = _exact_text(value, field_name, maximum=32)
    if not _CANONICAL_DECIMAL.fullmatch(text):
        raise RemediationPolicyError(f"{field_name} must be a canonical decimal in [0, 1]")
    decimal = Decimal(text)
    if (decimal == 0 and not allow_zero) or (decimal == 1 and not allow_one):
        raise RemediationPolicyError(f"{field_name} is outside its allowed open bounds")
    return text


def _canonical_uuid(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name, maximum=36)
    try:
        parsed = uuid.UUID(text)
    except (ValueError, AttributeError) as exc:
        raise RemediationPolicyError(f"{field_name} must be a canonical UUID") from exc
    if str(parsed) != text:
        raise RemediationPolicyError(f"{field_name} must be a canonical lowercase UUID")
    return text


def _canonical_utc(value: object, field_name: str) -> datetime:
    text = _exact_text(value, field_name, maximum=32)
    if not text.endswith("Z"):
        raise RemediationPolicyError(f"{field_name} must use canonical UTC Z form")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise RemediationPolicyError(f"{field_name} is not a valid UTC timestamp") from exc
    if parsed.utcoffset() != timedelta(0) or _utc_text(parsed) != text:
        raise RemediationPolicyError(f"{field_name} must use canonical UTC Z form")
    return parsed


def _require_utc_instant(value: datetime, field_name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise RemediationPolicyError(f"{field_name} must be an exact UTC datetime")
    return value


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parameter_dict(
    values: tuple[tuple[str, tuple[str, ...]], ...],
) -> dict[str, list[str]]:
    return {name: list(items) for name, items in values}


def _canonical_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise RemediationPolicyError("value is not canonical JSON") from exc


__all__ = [
    "MAX_REMEDIATION_BYTES",
    "REMEDIATION_POLICY_SCHEMA",
    "REMEDIATION_REQUEST_SCHEMA",
    "AutomationClientBinding",
    "AutomationDocumentSnapshot",
    "AutomationExecutionSnapshot",
    "AutomationExecutionStatus",
    "DocumentBinding",
    "RemediationDecision",
    "RemediationDisposition",
    "RemediationEntry",
    "RemediationExecutionError",
    "RemediationNotification",
    "RemediationNotificationType",
    "RemediationNotifier",
    "RemediationPolicyError",
    "RemediationPolicyGate",
    "RemediationPolicyPublication",
    "RemediationPolicyVerifier",
    "RemediationRequest",
    "RemediationRun",
    "RemediationRunState",
    "SsmAutomationClient",
    "StartAutomationCall",
    "VerifiedRemediationPolicy",
    "authorize_remediation",
    "load_remediation_policy",
    "load_remediation_request",
    "parse_remediation_policy",
    "parse_remediation_request",
    "reconcile_t4_remediation",
    "start_t4_remediation",
]
