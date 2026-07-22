"""Portable permanent-fix chase boundary for SPEC-B6.

The only write port is idempotent issue creation. Change requests, factory outcomes,
verification, merge, issue closure, and incident closure remain externally owned.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import stat
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import urlsplit
from uuid import UUID

REQUEST_SCHEMA_VERSION = "sre-harness.permanent-fix-request/v1"
POLICY_SCHEMA_VERSION = "sre-harness.permanent-fix-policy-publication/v1"
OUTCOME_SCHEMA_VERSION = "sre-harness.factory-outcome/v1"
MAX_DOCUMENT_BYTES = 1024 * 1024

_REQUEST_TOKEN = object()
_POLICY_TOKEN = object()
_VERIFIED_POLICY_TOKEN = object()
_OUTCOME_TOKEN = object()
_VERIFIED_OUTCOME_TOKEN = object()
_CASE_TOKEN = object()

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEAD_REVISION = re.compile(r"^[0-9a-f]{40}$")
_REFERENCE = re.compile(r"^[a-z][a-z0-9+.-]*://[^\s]{1,1000}$")
_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/ -]{0,99}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+$")
_BRANCH = re.compile(r"^(?!/)(?!.*(?:\.\.|//|@\{|\\))[A-Za-z0-9._/-]{1,255}(?<![/.])$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
_SENSITIVE = re.compile(
    r"(?i)(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
    r"\b(?:password|passwd|api[_-]?key|secret|access[_-]?token)\s*[:=]\s*\S+)"
)
_RESERVED_LABELS = frozenset({"incident", "permanent-fix"})

_REQUEST_FIELDS = frozenset(
    {
        "body",
        "evidenceRefs",
        "evidenceScope",
        "expiresAt",
        "factory",
        "incidentId",
        "labels",
        "origin",
        "policyId",
        "policyRevision",
        "priority",
        "provider",
        "repository",
        "requestId",
        "requestedAt",
        "targetBranch",
        "taskClass",
        "taskId",
        "title",
    }
)
_POLICY_FIELDS = frozenset(
    {
        "approvalRevision",
        "approvedBy",
        "evidenceScope",
        "expiresAt",
        "factories",
        "maxOutcomeAgeSeconds",
        "maxRequestAgeSeconds",
        "origin",
        "policyId",
        "provider",
        "publishedAt",
        "repository",
        "requiredLabels",
        "targetBranch",
        "taskClasses",
        "verifierRef",
    }
)
_OUTCOME_FIELDS = frozenset(
    {
        "changeNumber",
        "evidenceManifest",
        "evidenceScope",
        "factory",
        "gate",
        "incidentId",
        "lifecycle",
        "occurredAt",
        "origin",
        "provider",
        "repository",
        "taskId",
        "taskRevision",
        "verdict",
        "verifierRef",
    }
)
_EVIDENCE_SCOPES = frozenset({"fixture", "external_candidate"})
_FACTORIES = frozenset({"omnius", "multiqlti"})
_TASK_CLASSES = frozenset({"A", "B", "C", "E"})


class PermanentFixError(ValueError):
    """A request, policy, provider snapshot, or factory outcome is inadmissible."""


class ProviderKind(Enum):
    GITHUB = "github"
    GITLAB = "gitlab"


class IssueKind(Enum):
    ISSUE = "issue"
    CHANGE = "change"


class IssueState(Enum):
    OPEN = "open"
    CLOSED = "closed"


class ChangeState(Enum):
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class FactoryLifecycle(Enum):
    TRIGGERED = "TRIGGERED"
    PLANNED = "PLANNED"
    PRODUCED = "PRODUCED"
    VERIFIED = "VERIFIED"
    GATED = "GATED"
    LANDED = "LANDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PermanentFixState(Enum):
    ISSUE_OPEN = "issue_open"
    CHANGE_OPEN = "change_open"
    VERIFYING = "verifying"
    AWAITING_HUMAN_MERGE = "awaiting_human_merge"
    LANDED = "landed"
    ESCALATED = "escalated"


_LIFECYCLE_RANK = {
    FactoryLifecycle.TRIGGERED: 0,
    FactoryLifecycle.PLANNED: 1,
    FactoryLifecycle.PRODUCED: 2,
    FactoryLifecycle.VERIFIED: 3,
    FactoryLifecycle.GATED: 4,
    FactoryLifecycle.LANDED: 5,
}
_TERMINAL_FACTORY_LIFECYCLES = frozenset(
    {
        FactoryLifecycle.FAILED,
        FactoryLifecycle.CANCELLED,
        FactoryLifecycle.REJECTED,
        FactoryLifecycle.EXPIRED,
    }
)
_TERMINAL_STATES = frozenset({PermanentFixState.LANDED, PermanentFixState.ESCALATED})


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _reject_constant(_: str) -> None:
    raise PermanentFixError("JSON number must be finite")


def _closed_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise PermanentFixError(f"duplicate JSON field: {key}")
        value[key] = item
    return value


def _parse_json(data: bytes) -> dict[str, object]:
    if type(data) is not bytes:
        raise TypeError("permanent-fix documents must be exact bytes")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise PermanentFixError("permanent-fix document is too large")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PermanentFixError("permanent-fix document must be UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_closed_pairs,
            parse_constant=_reject_constant,
        )
    except PermanentFixError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise PermanentFixError("permanent-fix document is invalid JSON") from exc
    if type(value) is not dict:
        raise PermanentFixError("permanent-fix document must be a JSON object")
    canonical = _canonical_json(value)
    if data not in {canonical, canonical + b"\n"}:
        raise PermanentFixError("permanent-fix document must use canonical JSON")
    return cast(dict[str, object], value)


def _load(path: Path) -> bytes:
    if not isinstance(path, Path):
        raise TypeError("permanent-fix path must be a Path")
    if path.is_symlink():
        raise PermanentFixError("permanent-fix path must not be a symlink")
    try:
        metadata = path.stat()
    except OSError as exc:
        raise PermanentFixError("permanent-fix document is unavailable") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise PermanentFixError("permanent-fix path must be a regular file")
    if metadata.st_size > MAX_DOCUMENT_BYTES:
        raise PermanentFixError("permanent-fix document is too large")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PermanentFixError("permanent-fix document is unreadable") from exc
    if len(data) != metadata.st_size:
        raise PermanentFixError("permanent-fix document changed while reading")
    return data


def _closed_object(
    value: object,
    *,
    name: str,
    required: frozenset[str],
) -> dict[str, object]:
    if type(value) is not dict:
        raise PermanentFixError(f"{name} must be an object")
    document = cast(dict[str, object], value)
    if frozenset(document) != required:
        raise PermanentFixError(f"{name} fields must match the closed schema")
    return document


def _text(value: object, name: str, *, maximum: int = 200) -> str:
    if type(value) is not str:
        raise PermanentFixError(f"{name} must be a string")
    if not value or value != value.strip() or len(value) > maximum:
        raise PermanentFixError(f"{name} must be bounded non-blank text")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise PermanentFixError(f"{name} contains a control character")
    return value


def _identifier(value: object, name: str) -> str:
    text = _text(value, name)
    if _IDENTIFIER.fullmatch(text) is None:
        raise PermanentFixError(f"{name} has an invalid identifier")
    return text


def _uuid(value: object, name: str) -> str:
    text = _text(value, name, maximum=36)
    try:
        parsed = UUID(text)
    except ValueError as exc:
        raise PermanentFixError(f"{name} must be a UUID") from exc
    if str(parsed) != text or parsed.version != 4:
        raise PermanentFixError(f"{name} must be a canonical UUIDv4")
    return text


def _revision(value: object, name: str) -> str:
    text = _text(value, name, maximum=71)
    if _SHA256.fullmatch(text) is None:
        raise PermanentFixError(f"{name} must be a sha256 revision")
    return text


def _head_revision(value: object, name: str) -> str:
    text = _text(value, name, maximum=40)
    if _HEAD_REVISION.fullmatch(text) is None:
        raise PermanentFixError(f"{name} must be an immutable 40-hex head revision")
    return text


def _timestamp(value: object, name: str) -> datetime:
    text = _text(value, name, maximum=20)
    if not text.endswith("Z"):
        raise PermanentFixError(f"{name} timestamp must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise PermanentFixError(f"{name} timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise PermanentFixError(f"{name} timestamp must be UTC")
    if parsed.microsecond or parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != text:
        raise PermanentFixError(f"{name} timestamp must be canonical UTC")
    return parsed


def _utc(value: datetime, name: str) -> datetime:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise PermanentFixError(f"{name} must be an exact UTC datetime")
    return value


def _positive_int(value: object, name: str, *, maximum: int = 31_536_000) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise PermanentFixError(f"{name} must be a bounded positive integer")
    return value


def _provider(value: object) -> ProviderKind:
    text = _text(value, "provider", maximum=20)
    try:
        return ProviderKind(text)
    except ValueError as exc:
        raise PermanentFixError("provider is unsupported") from exc


def _origin(value: object, name: str) -> str:
    text = _text(value, name, maximum=500)
    try:
        parsed = urlsplit(text)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise PermanentFixError(f"{name} must be a credential-free exact HTTPS origin") from exc
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or text.endswith("/")
    ):
        raise PermanentFixError(f"{name} must be a credential-free exact HTTPS origin")
    return text


def _repository(value: object) -> str:
    text = _text(value, "repository", maximum=300)
    if _REPOSITORY.fullmatch(text) is None:
        raise PermanentFixError("repository must be an exact provider path")
    return text


def _branch(value: object) -> str:
    text = _text(value, "target branch", maximum=255)
    if _BRANCH.fullmatch(text) is None or text.endswith(".lock"):
        raise PermanentFixError("target branch is invalid or mutable")
    return text


def _scope(value: object) -> str:
    text = _text(value, "evidence scope", maximum=30)
    if text not in _EVIDENCE_SCOPES:
        raise PermanentFixError("evidence scope is unsupported")
    return text


def _string_tuple(
    value: object,
    *,
    name: str,
    allowed: frozenset[str] | None = None,
    pattern: re.Pattern[str] | None = None,
    maximum_items: int = 20,
) -> tuple[str, ...]:
    if type(value) is not list or not value or len(value) > maximum_items:
        raise PermanentFixError(f"{name} must be a bounded non-empty array")
    items = tuple(_text(item, name) for item in value)
    if len(set(items)) != len(items) or tuple(sorted(items)) != items:
        raise PermanentFixError(f"{name} must be unique and sorted")
    if allowed is not None and not set(items).issubset(allowed):
        raise PermanentFixError(f"{name} contains an unsupported value")
    if pattern is not None and any(pattern.fullmatch(item) is None for item in items):
        raise PermanentFixError(f"{name} contains an invalid value")
    return items


def _refs(value: object, name: str) -> tuple[str, ...]:
    items = _string_tuple(value, name=name, maximum_items=50)
    return tuple(_reference(item, name) for item in items)


def _reference(value: object, name: str) -> str:
    text = _text(value, name, maximum=1000)
    try:
        parsed = urlsplit(text)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise PermanentFixError(f"{name} contains an invalid immutable reference") from exc
    if _REFERENCE.fullmatch(text) is None or not parsed.netloc or hostname is None:
        raise PermanentFixError(f"{name} contains an invalid immutable reference")
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or _SENSITIVE.search(text)
    ):
        raise PermanentFixError(f"{name} must contain only credential-free immutable references")
    return text


def _sensitive_text(value: object, name: str, *, maximum: int) -> str:
    text = _text(value, name, maximum=maximum)
    if _SENSITIVE.search(text) or "sre-harness-permanent-fix:" in text:
        raise PermanentFixError(f"{name} contains sensitive or reserved content")
    return text


@dataclass(frozen=True, init=False)
class PermanentFixRequest:
    request_revision: str
    request_id: str
    incident_id: str
    task_id: str
    factory: str
    requested_at: datetime
    expires_at: datetime
    priority: str
    task_class: str
    provider: ProviderKind
    origin: str
    repository: str
    policy_id: str
    policy_revision: str
    title: str
    body: str
    labels: tuple[str, ...]
    target_branch: str
    evidence_refs: tuple[str, ...]
    evidence_scope: str
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        request_revision: str,
        request_id: str,
        incident_id: str,
        task_id: str,
        factory: str,
        requested_at: datetime,
        expires_at: datetime,
        priority: str,
        task_class: str,
        provider: ProviderKind,
        origin: str,
        repository: str,
        policy_id: str,
        policy_revision: str,
        title: str,
        body: str,
        labels: tuple[str, ...],
        target_branch: str,
        evidence_refs: tuple[str, ...],
        evidence_scope: str,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _REQUEST_TOKEN:
            raise TypeError("permanent-fix requests must come from the strict parser")
        values = locals().copy()
        values.pop("self")
        values.pop("_construction_token")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _request_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is PermanentFixRequest and hmac.compare_digest(
            self._integrity_seal, _request_seal(self)
        )


def _request_body(request: PermanentFixRequest) -> dict[str, object]:
    return {
        "body": request.body,
        "evidenceRefs": list(request.evidence_refs),
        "evidenceScope": request.evidence_scope,
        "expiresAt": _utc_text(request.expires_at),
        "factory": request.factory,
        "incidentId": request.incident_id,
        "labels": list(request.labels),
        "origin": request.origin,
        "policyId": request.policy_id,
        "policyRevision": request.policy_revision,
        "priority": request.priority,
        "provider": request.provider.value,
        "repository": request.repository,
        "requestId": request.request_id,
        "requestedAt": _utc_text(request.requested_at),
        "targetBranch": request.target_branch,
        "taskClass": request.task_class,
        "taskId": request.task_id,
        "title": request.title,
    }


def _request_seal(request: PermanentFixRequest) -> str:
    return _digest(
        {
            "request": _request_body(request),
            "requestRevision": request.request_revision,
            "schemaVersion": REQUEST_SCHEMA_VERSION,
        }
    )


@dataclass(frozen=True, init=False)
class PermanentFixPolicyPublication:
    publication_revision: str
    policy_id: str
    evidence_scope: str
    provider: ProviderKind
    origin: str
    repository: str
    factories: tuple[str, ...]
    task_classes: tuple[str, ...]
    required_labels: tuple[str, ...]
    target_branch: str
    max_request_age_seconds: int
    max_outcome_age_seconds: int
    published_at: datetime
    expires_at: datetime
    approved_by: str
    approval_revision: str
    verifier_ref: str
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        publication_revision: str,
        policy_id: str,
        evidence_scope: str,
        provider: ProviderKind,
        origin: str,
        repository: str,
        factories: tuple[str, ...],
        task_classes: tuple[str, ...],
        required_labels: tuple[str, ...],
        target_branch: str,
        max_request_age_seconds: int,
        max_outcome_age_seconds: int,
        published_at: datetime,
        expires_at: datetime,
        approved_by: str,
        approval_revision: str,
        verifier_ref: str,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _POLICY_TOKEN:
            raise TypeError("permanent-fix policies must come from the strict parser")
        values = locals().copy()
        values.pop("self")
        values.pop("_construction_token")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _policy_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is PermanentFixPolicyPublication and hmac.compare_digest(
            self._integrity_seal, _policy_seal(self)
        )


def _policy_body(policy: PermanentFixPolicyPublication) -> dict[str, object]:
    return {
        "approvalRevision": policy.approval_revision,
        "approvedBy": policy.approved_by,
        "evidenceScope": policy.evidence_scope,
        "expiresAt": _utc_text(policy.expires_at),
        "factories": list(policy.factories),
        "maxOutcomeAgeSeconds": policy.max_outcome_age_seconds,
        "maxRequestAgeSeconds": policy.max_request_age_seconds,
        "origin": policy.origin,
        "policyId": policy.policy_id,
        "provider": policy.provider.value,
        "publishedAt": _utc_text(policy.published_at),
        "repository": policy.repository,
        "requiredLabels": list(policy.required_labels),
        "targetBranch": policy.target_branch,
        "taskClasses": list(policy.task_classes),
        "verifierRef": policy.verifier_ref,
    }


def _policy_seal(policy: PermanentFixPolicyPublication) -> str:
    return _digest(
        {
            "policy": _policy_body(policy),
            "publicationRevision": policy.publication_revision,
            "schemaVersion": POLICY_SCHEMA_VERSION,
        }
    )


class PermanentFixPolicyVerifier(Protocol):
    def verify(self, publication: PermanentFixPolicyPublication) -> object: ...


@dataclass(frozen=True, init=False)
class VerifiedPermanentFixPolicy:
    publication_revision: str
    policy_id: str
    evidence_scope: str
    provider: ProviderKind
    origin: str
    repository: str
    factories: tuple[str, ...]
    task_classes: tuple[str, ...]
    required_labels: tuple[str, ...]
    target_branch: str
    max_request_age_seconds: int
    max_outcome_age_seconds: int
    published_at: datetime
    expires_at: datetime
    verifier_ref: str
    _approval_revision: str = field(repr=False, compare=False)
    _approved_by: str = field(repr=False, compare=False)
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        publication: PermanentFixPolicyPublication,
        *,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _VERIFIED_POLICY_TOKEN:
            raise TypeError("verified permanent-fix policies must come from the policy gate")
        values = {
            "publication_revision": publication.publication_revision,
            "policy_id": publication.policy_id,
            "evidence_scope": publication.evidence_scope,
            "provider": publication.provider,
            "origin": publication.origin,
            "repository": publication.repository,
            "factories": publication.factories,
            "task_classes": publication.task_classes,
            "required_labels": publication.required_labels,
            "target_branch": publication.target_branch,
            "max_request_age_seconds": publication.max_request_age_seconds,
            "max_outcome_age_seconds": publication.max_outcome_age_seconds,
            "published_at": publication.published_at,
            "expires_at": publication.expires_at,
            "verifier_ref": publication.verifier_ref,
            "_approval_revision": publication.approval_revision,
            "_approved_by": publication.approved_by,
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _verified_policy_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is VerifiedPermanentFixPolicy and hmac.compare_digest(
            self._integrity_seal, _verified_policy_seal(self)
        )


def _verified_policy_seal(policy: VerifiedPermanentFixPolicy) -> str:
    return _digest(
        {
            "approvalRevision": policy._approval_revision,
            "approvedBy": policy._approved_by,
            "evidenceScope": policy.evidence_scope,
            "expiresAt": _utc_text(policy.expires_at),
            "factories": list(policy.factories),
            "maxOutcomeAgeSeconds": policy.max_outcome_age_seconds,
            "maxRequestAgeSeconds": policy.max_request_age_seconds,
            "origin": policy.origin,
            "policyId": policy.policy_id,
            "provider": policy.provider.value,
            "publicationRevision": policy.publication_revision,
            "publishedAt": _utc_text(policy.published_at),
            "repository": policy.repository,
            "requiredLabels": list(policy.required_labels),
            "targetBranch": policy.target_branch,
            "taskClasses": list(policy.task_classes),
            "verifierRef": policy.verifier_ref,
        }
    )


class PermanentFixPolicyGate:
    """Issue an opaque provider-write capability from exact external authority."""

    def __init__(
        self,
        *,
        allowed_origins: frozenset[str],
        verifiers: dict[str, PermanentFixPolicyVerifier],
    ) -> None:
        self._allowed_origins = frozenset(allowed_origins)
        self._verifiers = dict(verifiers)

    def verify(
        self,
        publication: PermanentFixPolicyPublication,
        *,
        now: datetime,
    ) -> VerifiedPermanentFixPolicy:
        _require_policy(publication)
        instant = _utc(now, "now")
        if publication.evidence_scope == "fixture":
            raise PermanentFixError("fixture permanent-fix policy cannot authorize a provider")
        if publication.origin not in self._allowed_origins:
            raise PermanentFixError("permanent-fix policy origin is not allowlisted")
        verifier = self._verifiers.get(publication.verifier_ref)
        if verifier is None:
            raise PermanentFixError("permanent-fix policy verifier is not configured")
        if instant < publication.published_at:
            raise PermanentFixError("permanent-fix policy publication is future")
        if instant >= publication.expires_at:
            raise PermanentFixError("permanent-fix policy publication is expired")
        before = _policy_seal(publication)
        try:
            result = verifier.verify(publication)
        except Exception as exc:
            raise PermanentFixError("permanent-fix policy verification failed") from exc
        if before != _policy_seal(publication) or not publication._is_intact():
            raise PermanentFixError("permanent-fix policy was mutated during verification")
        if type(result) is not bool or result is not True:
            raise PermanentFixError("permanent-fix policy verification did not return exact true")
        return VerifiedPermanentFixPolicy(publication, _construction_token=_VERIFIED_POLICY_TOKEN)


def _utc_text(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_permanent_fix_request(data: bytes) -> PermanentFixRequest:
    document = _closed_object(
        _parse_json(data),
        name="permanent-fix request envelope",
        required=frozenset({"schemaVersion", "requestRevision", "request"}),
    )
    if _text(document["schemaVersion"], "schema version") != REQUEST_SCHEMA_VERSION:
        raise PermanentFixError("permanent-fix request schema version is unsupported")
    body = _closed_object(
        document["request"], name="permanent-fix request", required=_REQUEST_FIELDS
    )
    requested_at = _timestamp(body["requestedAt"], "requestedAt")
    expires_at = _timestamp(body["expiresAt"], "expiresAt")
    if expires_at <= requested_at:
        raise PermanentFixError("permanent-fix request expiry must follow creation")
    if (expires_at - requested_at).total_seconds() > 7 * 24 * 3600:
        raise PermanentFixError("permanent-fix request expiry window is too large")
    factory = _text(body["factory"], "factory", maximum=20)
    if factory not in _FACTORIES:
        raise PermanentFixError("factory is unsupported")
    priority = _text(body["priority"], "priority", maximum=2)
    if priority != "P0":
        raise PermanentFixError("permanent-fix priority must be P0")
    task_class = _text(body["taskClass"], "task class", maximum=1)
    if task_class not in _TASK_CLASSES:
        raise PermanentFixError("task class is unsupported")
    labels = _string_tuple(body["labels"], name="labels", pattern=_LABEL)
    if set(labels) & _RESERVED_LABELS:
        raise PermanentFixError("request labels contain a reserved policy label")
    request_revision = _revision(document["requestRevision"], "request revision")
    if request_revision != _digest(body):
        raise PermanentFixError("permanent-fix request revision mismatch")
    request = PermanentFixRequest(
        request_revision=request_revision,
        request_id=_uuid(body["requestId"], "request id"),
        incident_id=_identifier(body["incidentId"], "incident id"),
        task_id=_identifier(body["taskId"], "task id"),
        factory=factory,
        requested_at=requested_at,
        expires_at=expires_at,
        priority=priority,
        task_class=task_class,
        provider=_provider(body["provider"]),
        origin=_origin(body["origin"], "request origin"),
        repository=_repository(body["repository"]),
        policy_id=_uuid(body["policyId"], "policy id"),
        policy_revision=_revision(body["policyRevision"], "policy revision"),
        title=_sensitive_text(body["title"], "title", maximum=200),
        body=_sensitive_text(body["body"], "body", maximum=20_000),
        labels=labels,
        target_branch=_branch(body["targetBranch"]),
        evidence_refs=_refs(body["evidenceRefs"], "evidence refs"),
        evidence_scope=_scope(body["evidenceScope"]),
        _construction_token=_REQUEST_TOKEN,
    )
    return request


def load_permanent_fix_request(path: Path) -> PermanentFixRequest:
    return parse_permanent_fix_request(_load(path))


def parse_permanent_fix_policy(data: bytes) -> PermanentFixPolicyPublication:
    document = _closed_object(
        _parse_json(data),
        name="permanent-fix policy envelope",
        required=frozenset({"schemaVersion", "publicationRevision", "policy"}),
    )
    if _text(document["schemaVersion"], "schema version") != POLICY_SCHEMA_VERSION:
        raise PermanentFixError("permanent-fix policy schema version is unsupported")
    body = _closed_object(document["policy"], name="permanent-fix policy", required=_POLICY_FIELDS)
    published_at = _timestamp(body["publishedAt"], "publishedAt")
    expires_at = _timestamp(body["expiresAt"], "expiresAt")
    if expires_at <= published_at:
        raise PermanentFixError("permanent-fix policy expiry must follow publication")
    publication_revision = _revision(document["publicationRevision"], "publication revision")
    if publication_revision != _digest(body):
        raise PermanentFixError("permanent-fix policy publication revision mismatch")
    approved_by = _identifier(body["approvedBy"], "policy approver")
    if not approved_by.startswith("human:"):
        raise PermanentFixError("permanent-fix policy approver must be human")
    publication = PermanentFixPolicyPublication(
        publication_revision=publication_revision,
        policy_id=_uuid(body["policyId"], "policy id"),
        evidence_scope=_scope(body["evidenceScope"]),
        provider=_provider(body["provider"]),
        origin=_origin(body["origin"], "policy origin"),
        repository=_repository(body["repository"]),
        factories=_string_tuple(body["factories"], name="factories", allowed=_FACTORIES),
        task_classes=_string_tuple(body["taskClasses"], name="task classes", allowed=_TASK_CLASSES),
        required_labels=_string_tuple(
            body["requiredLabels"], name="required labels", pattern=_LABEL
        ),
        target_branch=_branch(body["targetBranch"]),
        max_request_age_seconds=_positive_int(body["maxRequestAgeSeconds"], "max request age"),
        max_outcome_age_seconds=_positive_int(body["maxOutcomeAgeSeconds"], "max outcome age"),
        published_at=published_at,
        expires_at=expires_at,
        approved_by=approved_by,
        approval_revision=_revision(body["approvalRevision"], "approval revision"),
        verifier_ref=_identifier(body["verifierRef"], "policy verifier ref"),
        _construction_token=_POLICY_TOKEN,
    )
    if not _RESERVED_LABELS.issubset(publication.required_labels):
        raise PermanentFixError(
            "permanent-fix policy must include incident and permanent-fix governance labels"
        )
    return publication


def load_permanent_fix_policy(path: Path) -> PermanentFixPolicyPublication:
    return parse_permanent_fix_policy(_load(path))


def _require_request(request: PermanentFixRequest) -> None:
    if type(request) is not PermanentFixRequest or not request._is_intact():
        raise PermanentFixError("permanent-fix request is not intact")


def _require_policy(policy: PermanentFixPolicyPublication) -> None:
    if type(policy) is not PermanentFixPolicyPublication or not policy._is_intact():
        raise PermanentFixError("permanent-fix policy is not intact")


def _require_verified_policy(policy: VerifiedPermanentFixPolicy) -> None:
    if type(policy) is not VerifiedPermanentFixPolicy or not policy._is_intact():
        raise PermanentFixError("verified permanent-fix policy is not intact")


@dataclass(frozen=True, init=False)
class FactoryOutcome:
    outcome_revision: str
    incident_id: str
    task_id: str
    factory: str
    provider: ProviderKind
    repository: str
    change_number: int
    task_revision: str
    lifecycle: FactoryLifecycle
    verdict: str
    gate: str
    evidence_manifest: str
    occurred_at: datetime
    origin: str
    verifier_ref: str
    evidence_scope: str
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        outcome_revision: str,
        incident_id: str,
        task_id: str,
        factory: str,
        provider: ProviderKind,
        repository: str,
        change_number: int,
        task_revision: str,
        lifecycle: FactoryLifecycle,
        verdict: str,
        gate: str,
        evidence_manifest: str,
        occurred_at: datetime,
        origin: str,
        verifier_ref: str,
        evidence_scope: str,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _OUTCOME_TOKEN:
            raise TypeError("factory outcomes must come from the strict parser")
        values = locals().copy()
        values.pop("self")
        values.pop("_construction_token")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _outcome_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is FactoryOutcome and hmac.compare_digest(
            self._integrity_seal, _outcome_seal(self)
        )


def _outcome_body(outcome: FactoryOutcome) -> dict[str, object]:
    return {
        "changeNumber": outcome.change_number,
        "evidenceManifest": outcome.evidence_manifest,
        "evidenceScope": outcome.evidence_scope,
        "factory": outcome.factory,
        "gate": outcome.gate,
        "incidentId": outcome.incident_id,
        "lifecycle": outcome.lifecycle.value,
        "occurredAt": _utc_text(outcome.occurred_at),
        "origin": outcome.origin,
        "provider": outcome.provider.value,
        "repository": outcome.repository,
        "taskId": outcome.task_id,
        "taskRevision": outcome.task_revision,
        "verdict": outcome.verdict,
        "verifierRef": outcome.verifier_ref,
    }


def _outcome_seal(outcome: FactoryOutcome) -> str:
    return _digest(
        {
            "outcome": _outcome_body(outcome),
            "outcomeRevision": outcome.outcome_revision,
            "schemaVersion": OUTCOME_SCHEMA_VERSION,
        }
    )


def parse_factory_outcome(data: bytes) -> FactoryOutcome:
    document = _closed_object(
        _parse_json(data),
        name="factory outcome envelope",
        required=frozenset({"schemaVersion", "outcomeRevision", "outcome"}),
    )
    if _text(document["schemaVersion"], "schema version") != OUTCOME_SCHEMA_VERSION:
        raise PermanentFixError("factory outcome schema version is unsupported")
    body = _closed_object(document["outcome"], name="factory outcome", required=_OUTCOME_FIELDS)
    factory = _text(body["factory"], "factory", maximum=20)
    if factory not in _FACTORIES:
        raise PermanentFixError("factory is unsupported")
    lifecycle_text = _text(body["lifecycle"], "lifecycle", maximum=20)
    try:
        lifecycle = FactoryLifecycle(lifecycle_text)
    except ValueError as exc:
        raise PermanentFixError("factory lifecycle is unsupported") from exc
    verdict = _text(body["verdict"], "verdict", maximum=20)
    if verdict not in {"pass", "fail", "parked", "none"}:
        raise PermanentFixError("factory verdict is unsupported")
    gate = _text(body["gate"], "gate", maximum=20)
    if gate not in {"auto", "human", "rejected"}:
        raise PermanentFixError("factory gate is unsupported")
    evidence_manifest = _reference(body["evidenceManifest"], "evidence manifest")
    outcome_revision = _revision(document["outcomeRevision"], "outcome revision")
    if outcome_revision != _digest(body):
        raise PermanentFixError("factory outcome revision mismatch")
    return FactoryOutcome(
        outcome_revision=outcome_revision,
        incident_id=_identifier(body["incidentId"], "incident id"),
        task_id=_identifier(body["taskId"], "task id"),
        factory=factory,
        provider=_provider(body["provider"]),
        repository=_repository(body["repository"]),
        change_number=_positive_int(body["changeNumber"], "change number", maximum=2**31 - 1),
        task_revision=_head_revision(body["taskRevision"], "task head revision"),
        lifecycle=lifecycle,
        verdict=verdict,
        gate=gate,
        evidence_manifest=evidence_manifest,
        occurred_at=_timestamp(body["occurredAt"], "occurredAt"),
        origin=_origin(body["origin"], "outcome origin"),
        verifier_ref=_identifier(body["verifierRef"], "outcome verifier ref"),
        evidence_scope=_scope(body["evidenceScope"]),
        _construction_token=_OUTCOME_TOKEN,
    )


class FactoryOutcomeVerifier(Protocol):
    def verify(self, outcome: FactoryOutcome) -> object: ...


@dataclass(frozen=True, init=False)
class VerifiedFactoryOutcome:
    outcome_revision: str
    incident_id: str
    task_id: str
    factory: str
    provider: ProviderKind
    repository: str
    change_number: int
    task_revision: str
    lifecycle: FactoryLifecycle
    verdict: str
    gate: str
    occurred_at: datetime
    origin: str
    verifier_ref: str
    _evidence_manifest: str = field(repr=False, compare=False)
    _evidence_scope: str = field(repr=False, compare=False)
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        outcome: FactoryOutcome,
        *,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _VERIFIED_OUTCOME_TOKEN:
            raise TypeError("verified factory outcomes must come from the outcome gate")
        values = {
            "outcome_revision": outcome.outcome_revision,
            "incident_id": outcome.incident_id,
            "task_id": outcome.task_id,
            "factory": outcome.factory,
            "provider": outcome.provider,
            "repository": outcome.repository,
            "change_number": outcome.change_number,
            "task_revision": outcome.task_revision,
            "lifecycle": outcome.lifecycle,
            "verdict": outcome.verdict,
            "gate": outcome.gate,
            "occurred_at": outcome.occurred_at,
            "origin": outcome.origin,
            "verifier_ref": outcome.verifier_ref,
            "_evidence_manifest": outcome.evidence_manifest,
            "_evidence_scope": outcome.evidence_scope,
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _verified_outcome_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is VerifiedFactoryOutcome and hmac.compare_digest(
            self._integrity_seal, _verified_outcome_seal(self)
        )


def _verified_outcome_seal(outcome: VerifiedFactoryOutcome) -> str:
    return _digest(
        {
            "changeNumber": outcome.change_number,
            "evidenceManifest": outcome._evidence_manifest,
            "evidenceScope": outcome._evidence_scope,
            "factory": outcome.factory,
            "gate": outcome.gate,
            "incidentId": outcome.incident_id,
            "lifecycle": outcome.lifecycle.value,
            "occurredAt": _utc_text(outcome.occurred_at),
            "origin": outcome.origin,
            "outcomeRevision": outcome.outcome_revision,
            "provider": outcome.provider.value,
            "repository": outcome.repository,
            "taskId": outcome.task_id,
            "taskRevision": outcome.task_revision,
            "verdict": outcome.verdict,
            "verifierRef": outcome.verifier_ref,
        }
    )


class FactoryOutcomeGate:
    """Verify one fresh immutable factory projection; it never drives the factory."""

    def __init__(
        self,
        *,
        allowed_origins: frozenset[str],
        verifiers: dict[str, FactoryOutcomeVerifier],
        max_age_seconds: int,
    ) -> None:
        if type(max_age_seconds) is not int or max_age_seconds <= 0:
            raise PermanentFixError("factory outcome max age must be positive")
        self._allowed_origins = frozenset(allowed_origins)
        self._verifiers = dict(verifiers)
        self._max_age_seconds = max_age_seconds

    def verify(
        self,
        outcome: FactoryOutcome,
        *,
        now: datetime,
    ) -> VerifiedFactoryOutcome:
        _require_outcome(outcome)
        instant = _utc(now, "now")
        if outcome._is_intact() and outcome.evidence_scope == "fixture":
            raise PermanentFixError("fixture factory outcome cannot advance a chase")
        if outcome.origin not in self._allowed_origins:
            raise PermanentFixError("factory outcome origin is not allowlisted")
        verifier = self._verifiers.get(outcome.verifier_ref)
        if verifier is None:
            raise PermanentFixError("factory outcome verifier is not configured")
        age = (instant - outcome.occurred_at).total_seconds()
        if age < 0:
            raise PermanentFixError("factory outcome is future")
        if age > self._max_age_seconds:
            raise PermanentFixError("factory outcome is stale")
        before = _outcome_seal(outcome)
        try:
            result = verifier.verify(outcome)
        except Exception as exc:
            raise PermanentFixError("factory outcome verification failed") from exc
        if before != _outcome_seal(outcome) or not outcome._is_intact():
            raise PermanentFixError("factory outcome was mutated during verification")
        if type(result) is not bool or result is not True:
            raise PermanentFixError("factory outcome verification did not return exact true")
        return VerifiedFactoryOutcome(outcome, _construction_token=_VERIFIED_OUTCOME_TOKEN)


def _require_outcome(outcome: FactoryOutcome) -> None:
    if type(outcome) is not FactoryOutcome or not outcome._is_intact():
        raise PermanentFixError("factory outcome is not intact")


def _require_verified_outcome(outcome: VerifiedFactoryOutcome) -> None:
    if type(outcome) is not VerifiedFactoryOutcome or not outcome._is_intact():
        raise PermanentFixError("verified factory outcome is not intact")


@dataclass(frozen=True)
class TrackerBinding:
    provider: ProviderKind
    origin: str
    repository: str


@dataclass(frozen=True)
class IssueSnapshot:
    repository: str
    number: int
    kind: IssueKind
    state: IssueState
    dedupe_key: str
    incident_id: str
    task_id: str
    request_revision: str


@dataclass(frozen=True)
class ChangeSnapshot:
    repository: str
    number: int
    state: ChangeState
    head_revision: str
    target_branch: str
    incident_id: str
    task_id: str
    merged_revision: str | None = None


@dataclass(frozen=True)
class IssueCreateCall:
    repository: str
    title: str
    body: str
    labels: tuple[str, ...]
    dedupe_key: str
    request_revision: str


class PermanentFixProvider(Protocol):
    def binding(self) -> TrackerBinding: ...

    def find_issue(self, dedupe_key: str) -> IssueSnapshot | tuple[IssueSnapshot, ...] | None: ...

    def create_issue(self, call: IssueCreateCall) -> IssueSnapshot: ...

    def read_issue(self, number: int) -> IssueSnapshot: ...

    def find_change(
        self, incident_id: str, task_id: str
    ) -> ChangeSnapshot | tuple[ChangeSnapshot, ...] | None: ...


@dataclass(frozen=True)
class PermanentFixAuditEvent:
    request_id: str
    request_revision: str
    incident_id: str
    task_id: str
    provider: str
    repository: str
    issue_number: int
    change_number: int | None
    head_revision: str | None
    merged_revision: str | None
    state: str
    reason: str
    occurred_at: datetime
    retry_key: str


class PermanentFixAuditSink(Protocol):
    def append(self, event: PermanentFixAuditEvent) -> None: ...


@dataclass(frozen=True, init=False)
class PermanentFixCase:
    request_id: str
    request_revision: str
    incident_id: str
    task_id: str
    factory: str
    provider: ProviderKind
    origin: str
    repository: str
    target_branch: str
    deadline: datetime
    max_outcome_age_seconds: int
    issue_number: int
    dedupe_key: str
    state: PermanentFixState
    reason: str
    change_number: int | None
    head_revision: str | None
    merged_revision: str | None
    lifecycle_rank: int
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        request_id: str = "",
        request_revision: str = "",
        incident_id: str = "",
        task_id: str = "",
        factory: str = "",
        provider: ProviderKind = ProviderKind.GITHUB,
        origin: str = "",
        repository: str = "",
        target_branch: str = "",
        deadline: datetime | None = None,
        max_outcome_age_seconds: int = 0,
        issue_number: int = 0,
        dedupe_key: str = "",
        state: PermanentFixState = PermanentFixState.ISSUE_OPEN,
        reason: str = "",
        change_number: int | None = None,
        head_revision: str | None = None,
        merged_revision: str | None = None,
        lifecycle_rank: int = -1,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _CASE_TOKEN:
            raise TypeError("permanent-fix cases must come from open or reconcile")
        if deadline is None:
            raise TypeError("permanent-fix case deadline is required")
        values = locals().copy()
        values.pop("self")
        values.pop("_construction_token")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _case_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is PermanentFixCase and hmac.compare_digest(
            self._integrity_seal, _case_seal(self)
        )


def _case_seal(case: PermanentFixCase) -> str:
    return _digest(
        {
            "changeNumber": case.change_number,
            "deadline": _utc_text(case.deadline),
            "dedupeKey": case.dedupe_key,
            "factory": case.factory,
            "headRevision": case.head_revision,
            "incidentId": case.incident_id,
            "issueNumber": case.issue_number,
            "lifecycleRank": case.lifecycle_rank,
            "mergedRevision": case.merged_revision,
            "maxOutcomeAgeSeconds": case.max_outcome_age_seconds,
            "origin": case.origin,
            "provider": case.provider.value,
            "reason": case.reason,
            "repository": case.repository,
            "requestId": case.request_id,
            "requestRevision": case.request_revision,
            "state": case.state.value,
            "targetBranch": case.target_branch,
            "taskId": case.task_id,
        }
    )


def _require_case(case: PermanentFixCase) -> None:
    if type(case) is not PermanentFixCase or not case._is_intact():
        raise PermanentFixError("permanent-fix case is not intact")


def _dedupe_key(request: PermanentFixRequest) -> str:
    return _digest(
        {
            "incidentId": request.incident_id,
            "origin": request.origin,
            "provider": request.provider.value,
            "repository": request.repository,
            "requestRevision": request.request_revision,
            "taskId": request.task_id,
        }
    )


def _validate_binding(
    binding: TrackerBinding,
    *,
    provider: ProviderKind,
    origin: str,
    repository: str,
) -> None:
    if type(binding) is not TrackerBinding:
        raise PermanentFixError("provider binding has an invalid type")
    if binding.provider is not provider:
        raise PermanentFixError("provider binding provider mismatch")
    if binding.origin != origin:
        raise PermanentFixError("provider binding origin mismatch")
    if binding.repository != repository:
        raise PermanentFixError("provider binding repository mismatch")


def _issue_problem(
    snapshot: IssueSnapshot,
    *,
    repository: str,
    dedupe_key: str,
    incident_id: str,
    task_id: str,
    request_revision: str,
) -> str | None:
    if type(snapshot) is not IssueSnapshot:
        return "issue snapshot type is invalid"
    if type(snapshot.kind) is not IssueKind:
        return "issue kind is invalid"
    if snapshot.kind is not IssueKind.ISSUE:
        return "issue kind is not an issue"
    if type(snapshot.repository) is not str:
        return "issue repository is invalid"
    if snapshot.repository != repository:
        return "issue repository mismatch"
    if type(snapshot.number) is not int or snapshot.number <= 0:
        return "issue number is invalid"
    if type(snapshot.dedupe_key) is not str:
        return "issue dedupe key is invalid"
    if snapshot.dedupe_key != dedupe_key:
        return "issue dedupe key mismatch"
    if type(snapshot.incident_id) is not str:
        return "issue incident is invalid"
    if snapshot.incident_id != incident_id:
        return "issue incident mismatch"
    if type(snapshot.task_id) is not str:
        return "issue task is invalid"
    if snapshot.task_id != task_id:
        return "issue task mismatch"
    if type(snapshot.request_revision) is not str:
        return "issue request revision is invalid"
    if snapshot.request_revision != request_revision:
        return "issue request revision mismatch"
    if type(snapshot.state) is not IssueState:
        return "issue state is invalid"
    if snapshot.state is not IssueState.OPEN:
        return "issue is closed before permanent-fix landing"
    return None


def _new_case(
    *,
    request_id: str,
    request_revision: str,
    incident_id: str,
    task_id: str,
    factory: str,
    provider: ProviderKind,
    origin: str,
    repository: str,
    target_branch: str,
    deadline: datetime,
    max_outcome_age_seconds: int,
    issue_number: int,
    dedupe_key: str,
    state: PermanentFixState,
    reason: str,
    change_number: int | None = None,
    head_revision: str | None = None,
    merged_revision: str | None = None,
    lifecycle_rank: int = -1,
) -> PermanentFixCase:
    return PermanentFixCase(
        request_id=request_id,
        request_revision=request_revision,
        incident_id=incident_id,
        task_id=task_id,
        factory=factory,
        provider=provider,
        origin=origin,
        repository=repository,
        target_branch=target_branch,
        deadline=deadline,
        max_outcome_age_seconds=max_outcome_age_seconds,
        issue_number=issue_number,
        dedupe_key=dedupe_key,
        state=state,
        reason=reason,
        change_number=change_number,
        head_revision=head_revision,
        merged_revision=merged_revision,
        lifecycle_rank=lifecycle_rank,
        _construction_token=_CASE_TOKEN,
    )


def _audit_event(case: PermanentFixCase, *, occurred_at: datetime) -> PermanentFixAuditEvent:
    retry_key = _digest(
        {
            "changeNumber": case.change_number,
            "headRevision": case.head_revision,
            "issueNumber": case.issue_number,
            "lifecycleRank": case.lifecycle_rank,
            "mergedRevision": case.merged_revision,
            "reason": case.reason,
            "requestId": case.request_id,
            "requestRevision": case.request_revision,
            "state": case.state.value,
        }
    )
    return PermanentFixAuditEvent(
        request_id=case.request_id,
        request_revision=case.request_revision,
        incident_id=case.incident_id,
        task_id=case.task_id,
        provider=case.provider.value,
        repository=case.repository,
        issue_number=case.issue_number,
        change_number=case.change_number,
        head_revision=case.head_revision,
        merged_revision=case.merged_revision,
        state=case.state.value,
        reason=case.reason,
        occurred_at=occurred_at,
        retry_key=retry_key,
    )


def _append_audit(
    case: PermanentFixCase,
    audit: PermanentFixAuditSink,
    *,
    occurred_at: datetime,
) -> None:
    audit.append(_audit_event(case, occurred_at=occurred_at))


def open_permanent_fix(
    request: PermanentFixRequest,
    policy: VerifiedPermanentFixPolicy,
    provider: PermanentFixProvider,
    audit: PermanentFixAuditSink,
    *,
    now: datetime,
) -> PermanentFixCase:
    """Create or adopt exactly one issue after all policy joins pass."""

    _require_request(request)
    _require_verified_policy(policy)
    instant = _utc(now, "now")
    if request.evidence_scope == "fixture":
        raise PermanentFixError("fixture permanent-fix request cannot reach a provider")
    if instant < request.requested_at:
        raise PermanentFixError("permanent-fix request is future")
    if instant >= request.expires_at:
        raise PermanentFixError("permanent-fix request is expired")
    if instant < policy.published_at or instant >= policy.expires_at:
        raise PermanentFixError("verified permanent-fix policy is expired or future")
    if (instant - request.requested_at).total_seconds() > policy.max_request_age_seconds:
        raise PermanentFixError("permanent-fix request is stale")
    if (
        request.policy_id != policy.policy_id
        or request.policy_revision != policy.publication_revision
    ):
        raise PermanentFixError("permanent-fix request policy mismatch")
    if request.provider is not policy.provider:
        raise PermanentFixError("permanent-fix request provider policy mismatch")
    if request.origin != policy.origin:
        raise PermanentFixError("permanent-fix request origin policy mismatch")
    if request.repository != policy.repository:
        raise PermanentFixError("permanent-fix request repository policy mismatch")
    if request.factory not in policy.factories:
        raise PermanentFixError("permanent-fix request factory is not allowed by policy")
    if request.task_class not in policy.task_classes:
        raise PermanentFixError("permanent-fix request task class is not allowed by policy")
    if request.target_branch != policy.target_branch:
        raise PermanentFixError("permanent-fix request target branch policy mismatch")

    try:
        binding = provider.binding()
    except Exception as exc:
        raise PermanentFixError("provider binding is unavailable") from exc
    _validate_binding(
        binding,
        provider=request.provider,
        origin=request.origin,
        repository=request.repository,
    )
    dedupe_key = _dedupe_key(request)
    try:
        snapshot = provider.find_issue(dedupe_key)
    except Exception as exc:
        raise PermanentFixError("provider issue search failed") from exc
    if isinstance(snapshot, tuple):
        if len(snapshot) != 1:
            raise PermanentFixError("permanent-fix issue search is ambiguous")
        snapshot = snapshot[0]
    if snapshot is None:
        labels = tuple(sorted(set(policy.required_labels) | set(request.labels)))
        marker = f"<!-- sre-harness-permanent-fix:{dedupe_key} -->"
        call = IssueCreateCall(
            repository=request.repository,
            title=request.title,
            body=f"{request.body}\n\n{marker}",
            labels=labels,
            dedupe_key=dedupe_key,
            request_revision=request.request_revision,
        )
        try:
            snapshot = provider.create_issue(call)
        except Exception as exc:
            raise PermanentFixError("provider issue create failed") from exc
    problem = _issue_problem(
        snapshot,
        repository=request.repository,
        dedupe_key=dedupe_key,
        incident_id=request.incident_id,
        task_id=request.task_id,
        request_revision=request.request_revision,
    )
    if problem is not None:
        raise PermanentFixError(problem)
    case = _new_case(
        request_id=request.request_id,
        request_revision=request.request_revision,
        incident_id=request.incident_id,
        task_id=request.task_id,
        factory=request.factory,
        provider=request.provider,
        origin=request.origin,
        repository=request.repository,
        target_branch=request.target_branch,
        deadline=request.expires_at,
        max_outcome_age_seconds=policy.max_outcome_age_seconds,
        issue_number=snapshot.number,
        dedupe_key=dedupe_key,
        state=PermanentFixState.ISSUE_OPEN,
        reason="permanent-fix issue is open",
    )
    _append_audit(case, audit, occurred_at=instant)
    return case


def _change_problem(case: PermanentFixCase, change: ChangeSnapshot) -> str | None:
    if type(change) is not ChangeSnapshot:
        return "change snapshot type is invalid"
    if type(change.repository) is not str:
        return "change repository is invalid"
    if change.repository != case.repository:
        return "change repository mismatch"
    if type(change.number) is not int or change.number <= 0:
        return "change number is invalid"
    if type(change.incident_id) is not str:
        return "change incident is invalid"
    if change.incident_id != case.incident_id:
        return "change incident mismatch"
    if type(change.task_id) is not str:
        return "change task is invalid"
    if change.task_id != case.task_id:
        return "change task mismatch"
    if type(change.target_branch) is not str:
        return "change target branch is invalid"
    if change.target_branch != case.target_branch:
        return "change target branch mismatch"
    if type(change.state) is not ChangeState:
        return "change state is invalid"
    if (
        type(change.head_revision) is not str
        or _HEAD_REVISION.fullmatch(change.head_revision) is None
    ):
        return "change head revision is invalid"
    if case.change_number is not None and change.number != case.change_number:
        return "change number drifted"
    if case.head_revision is not None and change.head_revision != case.head_revision:
        return "change head revision drifted"
    if change.state is ChangeState.CLOSED:
        return "change closed without merge"
    if change.state is ChangeState.MERGED:
        if (
            type(change.merged_revision) is not str
            or _HEAD_REVISION.fullmatch(change.merged_revision) is None
        ):
            return "merged change has an invalid merge revision"
    elif change.state is ChangeState.OPEN:
        if change.merged_revision is not None:
            return "open change unexpectedly has a merge revision"
    else:
        return "change state is invalid"
    if case.merged_revision is not None:
        if change.state is not ChangeState.MERGED:
            return "change merge state regressed"
        if change.merged_revision != case.merged_revision:
            return "change merge revision drifted"
    return None


def _outcome_problem(
    case: PermanentFixCase,
    change: ChangeSnapshot,
    outcome: VerifiedFactoryOutcome,
) -> str | None:
    if outcome.incident_id != case.incident_id:
        return "factory outcome incident mismatch"
    if outcome.task_id != case.task_id:
        return "factory outcome task mismatch"
    if outcome.factory != case.factory:
        return "factory outcome factory mismatch"
    if outcome.provider is not case.provider:
        return "factory outcome provider mismatch"
    if outcome.repository != case.repository:
        return "factory outcome repository mismatch"
    if outcome.change_number != change.number:
        return "factory outcome change mismatch"
    if outcome.task_revision != change.head_revision:
        return "factory outcome head revision mismatch"
    if outcome.lifecycle in _TERMINAL_FACTORY_LIFECYCLES:
        return "factory outcome is terminal without landing"
    rank = _LIFECYCLE_RANK.get(outcome.lifecycle)
    if rank is None:
        return "factory outcome lifecycle is invalid"
    if rank < case.lifecycle_rank:
        return "factory outcome lifecycle regressed"
    if outcome.verdict == "fail" or outcome.gate == "rejected":
        return "factory outcome verdict failed or was rejected"
    if rank >= _LIFECYCLE_RANK[FactoryLifecycle.VERIFIED] and outcome.verdict != "pass":
        return "factory outcome verdict is not pass"
    if rank >= _LIFECYCLE_RANK[FactoryLifecycle.GATED] and outcome.gate != "human":
        return "factory outcome lacks the required human gate"
    return None


def _transition(
    case: PermanentFixCase,
    audit: PermanentFixAuditSink,
    *,
    now: datetime,
    state: PermanentFixState,
    reason: str,
    change_number: int | None = None,
    head_revision: str | None = None,
    merged_revision: str | None = None,
    lifecycle_rank: int | None = None,
) -> PermanentFixCase:
    next_case = _new_case(
        request_id=case.request_id,
        request_revision=case.request_revision,
        incident_id=case.incident_id,
        task_id=case.task_id,
        factory=case.factory,
        provider=case.provider,
        origin=case.origin,
        repository=case.repository,
        target_branch=case.target_branch,
        deadline=case.deadline,
        max_outcome_age_seconds=case.max_outcome_age_seconds,
        issue_number=case.issue_number,
        dedupe_key=case.dedupe_key,
        state=state,
        reason=reason,
        change_number=change_number if change_number is not None else case.change_number,
        head_revision=head_revision if head_revision is not None else case.head_revision,
        merged_revision=(merged_revision if merged_revision is not None else case.merged_revision),
        lifecycle_rank=(lifecycle_rank if lifecycle_rank is not None else case.lifecycle_rank),
    )
    if next_case == case:
        return case
    _append_audit(next_case, audit, occurred_at=now)
    return next_case


def _escalate(
    case: PermanentFixCase,
    audit: PermanentFixAuditSink,
    *,
    now: datetime,
    reason: str,
    change: ChangeSnapshot | None = None,
    lifecycle_rank: int | None = None,
) -> PermanentFixCase:
    return _transition(
        case,
        audit,
        now=now,
        state=PermanentFixState.ESCALATED,
        reason=reason,
        change_number=change.number if change is not None else None,
        head_revision=change.head_revision if change is not None else None,
        merged_revision=change.merged_revision if change is not None else None,
        lifecycle_rank=lifecycle_rank,
    )


def reconcile_permanent_fix(
    case: PermanentFixCase,
    provider: PermanentFixProvider,
    outcome: VerifiedFactoryOutcome | None,
    audit: PermanentFixAuditSink,
    *,
    now: datetime,
) -> PermanentFixCase:
    """Observe the issue/change/factory and advance monotonically without mutating them."""

    _require_case(case)
    instant = _utc(now, "now")
    if case.state in _TERMINAL_STATES:
        return case
    if outcome is not None:
        _require_verified_outcome(outcome)
    if instant >= case.deadline:
        return _escalate(
            case,
            audit,
            now=instant,
            reason="permanent-fix chase deadline expired",
        )
    if outcome is not None:
        outcome_age = (instant - outcome.occurred_at).total_seconds()
        if outcome_age < 0 or outcome_age > case.max_outcome_age_seconds:
            return _escalate(
                case,
                audit,
                now=instant,
                reason="factory outcome exceeds the permanent-fix policy age boundary",
            )

    try:
        binding = provider.binding()
        _validate_binding(
            binding,
            provider=case.provider,
            origin=case.origin,
            repository=case.repository,
        )
    except Exception:
        return _escalate(
            case,
            audit,
            now=instant,
            reason="provider binding became unavailable or foreign",
        )

    try:
        issue = provider.read_issue(case.issue_number)
    except Exception:
        return _escalate(
            case,
            audit,
            now=instant,
            reason="provider issue read failed",
        )
    issue_problem = _issue_problem(
        issue,
        repository=case.repository,
        dedupe_key=case.dedupe_key,
        incident_id=case.incident_id,
        task_id=case.task_id,
        request_revision=case.request_revision,
    )
    issue_closed = issue_problem == "issue is closed before permanent-fix landing"
    if issue_problem is not None and not issue_closed:
        return _escalate(case, audit, now=instant, reason=issue_problem)

    try:
        found = provider.find_change(case.incident_id, case.task_id)
    except Exception:
        return _escalate(
            case,
            audit,
            now=instant,
            reason="provider change search failed",
        )
    if type(found) is tuple:
        if len(found) != 1:
            return _escalate(
                case,
                audit,
                now=instant,
                reason="multiple permanent-fix changes are ambiguous",
            )
        change: ChangeSnapshot | None = found[0]
    elif found is None or type(found) is ChangeSnapshot:
        change = found
    else:
        return _escalate(
            case,
            audit,
            now=instant,
            reason="change snapshot type is invalid",
        )

    if change is None:
        if outcome is not None:
            return _escalate(
                case,
                audit,
                now=instant,
                reason="factory outcome has no exact change to join",
            )
        if case.change_number is not None or case.head_revision is not None:
            return _escalate(
                case,
                audit,
                now=instant,
                reason="tracked permanent-fix change is missing",
            )
        if issue_closed:
            return _escalate(
                case,
                audit,
                now=instant,
                reason="issue closed before exact permanent-fix landing",
            )
        return case

    change_problem = _change_problem(case, change)
    if change_problem is not None:
        return _escalate(
            case,
            audit,
            now=instant,
            reason=change_problem,
        )

    if issue_closed:
        return _escalate(
            case,
            audit,
            now=instant,
            reason="issue closed before exact permanent-fix landing",
            change=change,
        )

    if outcome is None:
        if change.state is ChangeState.MERGED:
            reason = (
                "provider reports merge; exact factory LANDED outcome is pending"
                if case.lifecycle_rank >= _LIFECYCLE_RANK[FactoryLifecycle.PRODUCED]
                else "provider reports merge; exact factory outcome is pending"
            )
            return _transition(
                case,
                audit,
                now=instant,
                state=(
                    PermanentFixState.CHANGE_OPEN
                    if case.state is PermanentFixState.ISSUE_OPEN
                    else case.state
                ),
                reason=reason,
                change_number=change.number,
                head_revision=change.head_revision,
                merged_revision=change.merged_revision,
            )
        if case.state in {
            PermanentFixState.VERIFYING,
            PermanentFixState.AWAITING_HUMAN_MERGE,
        }:
            return case
        return _transition(
            case,
            audit,
            now=instant,
            state=PermanentFixState.CHANGE_OPEN,
            reason="factory-created change is open; factory outcome is pending",
            change_number=change.number,
            head_revision=change.head_revision,
        )

    outcome_problem = _outcome_problem(case, change, outcome)
    rank = _LIFECYCLE_RANK.get(outcome.lifecycle, case.lifecycle_rank)
    if outcome_problem is not None:
        return _escalate(
            case,
            audit,
            now=instant,
            reason=outcome_problem,
            change=change,
            lifecycle_rank=max(case.lifecycle_rank, rank),
        )

    if outcome.lifecycle is FactoryLifecycle.LANDED:
        if change.state is ChangeState.MERGED:
            landed = _transition(
                case,
                audit,
                now=instant,
                state=PermanentFixState.LANDED,
                reason="exact human-gated factory revision landed and provider merge agrees",
                change_number=change.number,
                head_revision=change.head_revision,
                merged_revision=change.merged_revision,
                lifecycle_rank=rank,
            )
            return landed
        return _transition(
            case,
            audit,
            now=instant,
            state=PermanentFixState.AWAITING_HUMAN_MERGE,
            reason="factory reports landed but exact provider merge observation is pending",
            change_number=change.number,
            head_revision=change.head_revision,
            lifecycle_rank=rank,
        )

    if outcome.lifecycle is FactoryLifecycle.GATED:
        state = PermanentFixState.AWAITING_HUMAN_MERGE
        reason = "factory verification passed and the human merge gate is pending"
    elif rank >= _LIFECYCLE_RANK[FactoryLifecycle.PRODUCED]:
        state = PermanentFixState.VERIFYING
        reason = "factory change is produced or verified and remains under chase"
    else:
        state = PermanentFixState.CHANGE_OPEN
        reason = "factory task is active and its change remains open"
    if change.state is ChangeState.MERGED:
        reason = "provider reports merge; exact factory LANDED outcome is pending"
    return _transition(
        case,
        audit,
        now=instant,
        state=state,
        reason=reason,
        change_number=change.number,
        head_revision=change.head_revision,
        merged_revision=change.merged_revision,
        lifecycle_rank=rank,
    )
