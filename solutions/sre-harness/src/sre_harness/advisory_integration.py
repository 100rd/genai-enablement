"""Closed SPEC-B2 envelope for advisory CI / Argo CD change validation."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from sre_harness.change_gate import ChangeRequest, GateResult, Verdict, evaluate_change
from sre_harness.platform_graph import Entity, InMemoryPlatformGraph

ADVISORY_REQUEST_SCHEMA = "sre-harness.change-advisory-request/v1"
ADVISORY_RESULT_SCHEMA = "sre-harness.change-advisory-result/v1"
MAX_ADVISORY_ENVELOPE_BYTES = 1024 * 1024
MAX_PLATFORM_SNAPSHOT_AGE_SECONDS = 300

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_INVOCATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_INVOCATION_TOKEN = object()
_RESULT_TOKEN = object()
_INTEGRITY_KEY = secrets.token_bytes(32)

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schemaVersion",
        "invocationId",
        "source",
        "requestedAt",
        "changeRevision",
        "platformRevision",
        "change",
        "platformSnapshot",
    }
)
_CHANGE_FIELDS = frozenset(
    {
        "service",
        "targetClusterIds",
        "requiredStorageClasses",
        "actions",
        "requiredNamespaces",
    }
)
_PLATFORM_FIELDS = frozenset({"asOf", "entities"})
_ENTITY_FIELDS = frozenset({"kind", "name", "cluster"})


class AdvisoryIntegrationError(ValueError):
    """The integration envelope or declared local result sink is inadmissible."""


class AdvisorySource(Enum):
    """Explicit portable integration contexts; neither proves a live execution."""

    GITLAB_CI = "gitlab_ci"
    ARGOCD_PRESYNC = "argocd_presync"


def canonical_digest(value: object) -> str:
    """Return the exact canonical JSON SHA-256 used by the v1 envelope."""
    try:
        canonical = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise AdvisoryIntegrationError("value is not canonical JSON") from exc
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, init=False)
class ChangeAdvisoryInvocation:
    """Opaque, immutable integration input issued only by the strict parser."""

    invocation_id: str
    source: AdvisorySource
    requested_at: datetime
    platform_as_of: datetime
    change_revision: str
    platform_revision: str
    service: str
    target_cluster_ids: tuple[str, ...]
    required_storageclasses: tuple[str, ...]
    actions: tuple[str, ...]
    required_namespaces: tuple[str, ...]
    platform_entities: tuple[Entity, ...]
    invocation_digest: str
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        invocation_id: str,
        source: AdvisorySource,
        requested_at: datetime,
        platform_as_of: datetime,
        change_revision: str,
        platform_revision: str,
        service: str,
        target_cluster_ids: tuple[str, ...],
        required_storageclasses: tuple[str, ...],
        actions: tuple[str, ...],
        required_namespaces: tuple[str, ...],
        platform_entities: tuple[Entity, ...],
        invocation_digest: str,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _INVOCATION_TOKEN:
            raise TypeError("change advisory invocations must come from the strict parser")
        values = locals().copy()
        values.pop("self")
        values.pop("_construction_token")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _invocation_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is ChangeAdvisoryInvocation and hmac.compare_digest(
            self._integrity_seal,
            _invocation_seal(self),
        )

    def _change_request(self) -> ChangeRequest:
        return ChangeRequest(
            service=self.service,
            target_cluster_ids=list(self.target_cluster_ids),
            required_storageclasses=set(self.required_storageclasses),
            actions=frozenset(self.actions),
            required_namespaces=frozenset(self.required_namespaces),
        )


@dataclass(frozen=True, init=False)
class ChangeAdvisoryResult:
    """Closed v1 advisory artifact constructed only by deterministic evaluation."""

    verdict: Verdict
    _document_json: bytes = field(repr=False, compare=False)
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        verdict: Verdict,
        document: dict[str, object],
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _RESULT_TOKEN:
            raise TypeError("change advisory results must come from deterministic evaluation")
        object.__setattr__(self, "verdict", verdict)
        object.__setattr__(
            self,
            "_document_json",
            json.dumps(
                document,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode(),
        )
        object.__setattr__(self, "_integrity_seal", _result_seal(self))

    def to_document(self) -> dict[str, Any]:
        """Return a fresh mapping so callers cannot mutate the sealed result."""
        if not hmac.compare_digest(self._integrity_seal, _result_seal(self)):
            raise AdvisoryIntegrationError("change advisory result is mutated")
        document = json.loads(self._document_json)
        assert isinstance(document, dict)
        return document


def parse_change_advisory_invocation(raw: bytes) -> ChangeAdvisoryInvocation:
    """Parse one exact v1 envelope from bounded strict UTF-8 JSON bytes."""
    if type(raw) is not bytes:
        raise AdvisoryIntegrationError("advisory envelope must be exact bytes")
    if len(raw) > MAX_ADVISORY_ENVELOPE_BYTES:
        raise AdvisoryIntegrationError(
            f"advisory envelope exceeds maximum {MAX_ADVISORY_ENVELOPE_BYTES} bytes"
        )
    try:
        text = raw.decode("utf-8", errors="strict")
        payload = json.loads(
            text,
            object_pairs_hook=_closed_object,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdvisoryIntegrationError("advisory envelope is not strict UTF-8 JSON") from exc
    if type(payload) is not dict:
        raise AdvisoryIntegrationError("advisory envelope must be a JSON object")
    _exact_fields(payload, _TOP_LEVEL_FIELDS, "advisory envelope")
    if payload["schemaVersion"] != ADVISORY_REQUEST_SCHEMA:
        raise AdvisoryIntegrationError("unsupported advisory envelope schemaVersion")

    invocation_id = _exact_text(payload["invocationId"], "invocationId")
    if not _INVOCATION_ID.fullmatch(invocation_id):
        raise AdvisoryIntegrationError("invocationId is not a bounded integration id")
    try:
        source = AdvisorySource(_exact_text(payload["source"], "source"))
    except ValueError as exc:
        raise AdvisoryIntegrationError("source must be gitlab_ci or argocd_presync") from exc
    requested_at = _canonical_utc(payload["requestedAt"], "requestedAt")

    change = _exact_object(payload["change"], "change")
    _exact_fields(change, _CHANGE_FIELDS, "change")
    platform = _exact_object(payload["platformSnapshot"], "platformSnapshot")
    _exact_fields(platform, _PLATFORM_FIELDS, "platformSnapshot")
    platform_as_of = _canonical_utc(platform["asOf"], "platformSnapshot.asOf")
    platform_age = requested_at - platform_as_of
    if platform_age < timedelta(0):
        raise AdvisoryIntegrationError("platform snapshot must not be in the future")
    if platform_age > timedelta(seconds=MAX_PLATFORM_SNAPSHOT_AGE_SECONDS):
        raise AdvisoryIntegrationError("platform snapshot is older than the five-minute maximum")

    change_revision = _exact_sha256(payload["changeRevision"], "changeRevision")
    platform_revision = _exact_sha256(payload["platformRevision"], "platformRevision")
    if change_revision != canonical_digest(change):
        raise AdvisoryIntegrationError("changeRevision does not match the exact change content")
    if platform_revision != canonical_digest(platform):
        raise AdvisoryIntegrationError(
            "platformRevision does not match the exact platform snapshot content"
        )

    service = _exact_text(change["service"], "change.service")
    target_cluster_ids = _sorted_strings(
        change["targetClusterIds"],
        "change.targetClusterIds",
        require_nonempty=True,
    )
    required_storageclasses = _sorted_strings(
        change["requiredStorageClasses"],
        "change.requiredStorageClasses",
    )
    actions = _sorted_strings(change["actions"], "change.actions")
    required_namespaces = _sorted_strings(
        change["requiredNamespaces"],
        "change.requiredNamespaces",
    )
    platform_entities = _platform_entities(platform["entities"])

    return ChangeAdvisoryInvocation(
        invocation_id=invocation_id,
        source=source,
        requested_at=requested_at,
        platform_as_of=platform_as_of,
        change_revision=change_revision,
        platform_revision=platform_revision,
        service=service,
        target_cluster_ids=target_cluster_ids,
        required_storageclasses=required_storageclasses,
        actions=actions,
        required_namespaces=required_namespaces,
        platform_entities=platform_entities,
        invocation_digest=canonical_digest(payload),
        _construction_token=_INVOCATION_TOKEN,
    )


def load_change_advisory_invocation(path: Path) -> ChangeAdvisoryInvocation:
    """Read one regular non-symlink bounded envelope and parse it strictly."""
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise AdvisoryIntegrationError(f"advisory envelope file unavailable: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise AdvisoryIntegrationError("advisory envelope file must not be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise AdvisoryIntegrationError("advisory envelope file must be a regular file")
    if metadata.st_size > MAX_ADVISORY_ENVELOPE_BYTES:
        raise AdvisoryIntegrationError(
            f"advisory envelope exceeds maximum {MAX_ADVISORY_ENVELOPE_BYTES} bytes"
        )

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise AdvisoryIntegrationError("advisory envelope must remain a regular file")
            raw = handle.read(MAX_ADVISORY_ENVELOPE_BYTES + 1)
    except AdvisoryIntegrationError:
        raise
    except OSError as exc:
        raise AdvisoryIntegrationError(f"advisory envelope file unavailable: {path}") from exc
    return parse_change_advisory_invocation(raw)


def evaluate_change_advisory(invocation: ChangeAdvisoryInvocation) -> ChangeAdvisoryResult:
    """Run only the registered deterministic gate over one intact invocation."""
    if type(invocation) is not ChangeAdvisoryInvocation or not invocation._is_intact():
        raise AdvisoryIntegrationError("change advisory invocation is raw or mutated")
    graph = InMemoryPlatformGraph(list(invocation.platform_entities))
    gate_result = evaluate_change(invocation._change_request(), graph)
    document = _result_document(invocation, gate_result)
    return ChangeAdvisoryResult(
        verdict=gate_result.verdict,
        document=document,
        _construction_token=_RESULT_TOKEN,
    )


def write_change_advisory_result(result: ChangeAdvisoryResult, path: Path) -> None:
    """Atomically write one local result artifact without following symlinks."""
    if type(result) is not ChangeAdvisoryResult:
        raise AdvisoryIntegrationError("result must come from deterministic advisory evaluation")
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise AdvisoryIntegrationError("result parent must be a real directory")
    if path.is_symlink():
        raise AdvisoryIntegrationError("result path must not be a symlink")
    if path.exists() and not path.is_file():
        raise AdvisoryIntegrationError("result path must be a regular file")

    document = result.to_document()
    encoded = (
        json.dumps(document, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    temporary: str | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=parent)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise AdvisoryIntegrationError(f"could not write advisory result: {path}") from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def _invocation_document(invocation: ChangeAdvisoryInvocation) -> dict[str, object]:
    return {
        "schemaVersion": ADVISORY_REQUEST_SCHEMA,
        "invocationId": invocation.invocation_id,
        "source": invocation.source.value,
        "requestedAt": _utc_text(invocation.requested_at),
        "changeRevision": invocation.change_revision,
        "platformRevision": invocation.platform_revision,
        "change": {
            "service": invocation.service,
            "targetClusterIds": list(invocation.target_cluster_ids),
            "requiredStorageClasses": list(invocation.required_storageclasses),
            "actions": list(invocation.actions),
            "requiredNamespaces": list(invocation.required_namespaces),
        },
        "platformSnapshot": {
            "asOf": _utc_text(invocation.platform_as_of),
            "entities": [
                {"kind": entity.kind, "name": entity.name, "cluster": entity.cluster}
                for entity in invocation.platform_entities
            ],
        },
    }


def _invocation_seal(invocation: ChangeAdvisoryInvocation) -> str:
    canonical = json.dumps(
        _invocation_document(invocation),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    payload = canonical + b"\0" + invocation.invocation_digest.encode()
    return hmac.new(_INTEGRITY_KEY, payload, hashlib.sha256).hexdigest()


def _result_seal(result: ChangeAdvisoryResult) -> str:
    payload = result._document_json + b"\0" + result.verdict.value.encode()
    return hmac.new(_INTEGRITY_KEY, payload, hashlib.sha256).hexdigest()


def _result_document(
    invocation: ChangeAdvisoryInvocation,
    result: GateResult,
) -> dict[str, object]:
    return {
        "schemaVersion": ADVISORY_RESULT_SCHEMA,
        "invocationId": invocation.invocation_id,
        "source": invocation.source.value,
        "requestedAt": _utc_text(invocation.requested_at),
        "platformAsOf": _utc_text(invocation.platform_as_of),
        "invocationDigest": invocation.invocation_digest,
        "changeRevision": invocation.change_revision,
        "platformRevision": invocation.platform_revision,
        "subject": {
            "service": invocation.service,
            "targetClusterIds": list(invocation.target_cluster_ids),
        },
        "verdict": result.verdict.value,
        "rationale": result.rationale,
        "analysisTier": result.analysis_tier.name,
        "recommendationTier": result.recommendation_tier.name,
        "advisory": True,
        "mutationAuthorized": False,
        "checkResults": [
            {
                "checkId": check.check_id,
                "verdict": check.verdict.value,
                "rationale": check.rationale,
                "evidence": _jsonable(check.evidence),
            }
            for check in result.check_results
        ],
    }


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AdvisoryIntegrationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> object:
    raise AdvisoryIntegrationError(f"non-finite JSON number is not allowed: {value}")


def _exact_object(value: object, field_name: str) -> dict[str, object]:
    if type(value) is not dict:
        raise AdvisoryIntegrationError(f"{field_name} must be an exact object")
    return value


def _exact_fields(value: dict[str, object], expected: frozenset[str], field_name: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise AdvisoryIntegrationError(
            f"{field_name} fields are not closed (missing={missing}, unknown={unknown})"
        )


def _exact_text(value: object, field_name: str) -> str:
    if type(value) is not str or not value.strip():
        raise AdvisoryIntegrationError(f"{field_name} must be a non-blank exact string")
    return value


def _exact_sha256(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name)
    if not _SHA256.fullmatch(text):
        raise AdvisoryIntegrationError(f"{field_name} must be an exact SHA-256")
    return text


def _sorted_strings(
    value: object,
    field_name: str,
    *,
    require_nonempty: bool = False,
) -> tuple[str, ...]:
    if type(value) is not list:
        raise AdvisoryIntegrationError(f"{field_name} must be an exact list")
    values = tuple(_exact_text(item, field_name) for item in value)
    if require_nonempty and not values:
        raise AdvisoryIntegrationError(f"{field_name} must not be empty")
    if values != tuple(sorted(set(values))):
        raise AdvisoryIntegrationError(f"{field_name} must be sorted and unique")
    return values


def _platform_entities(value: object) -> tuple[Entity, ...]:
    if type(value) is not list:
        raise AdvisoryIntegrationError("platformSnapshot.entities must be an exact list")
    entities: list[Entity] = []
    keys: list[tuple[str, str, str]] = []
    for index, raw in enumerate(value):
        row = _exact_object(raw, f"platformSnapshot.entities[{index}]")
        _exact_fields(row, _ENTITY_FIELDS, f"platformSnapshot.entities[{index}]")
        kind = _exact_text(row["kind"], f"platformSnapshot.entities[{index}].kind")
        name = _exact_text(row["name"], f"platformSnapshot.entities[{index}].name")
        cluster_value = row["cluster"]
        if cluster_value is not None and type(cluster_value) is not str:
            raise AdvisoryIntegrationError(
                f"platformSnapshot.entities[{index}].cluster must be a string or null"
            )
        cluster = cluster_value
        if cluster == "":
            raise AdvisoryIntegrationError(
                f"platformSnapshot.entities[{index}].cluster must not be blank"
            )
        entities.append(Entity(kind=kind, name=name, cluster=cluster))
        keys.append((kind, name, cluster or ""))
    if keys != sorted(set(keys)):
        raise AdvisoryIntegrationError("platformSnapshot.entities must be sorted and unique")
    return tuple(entities)


def _canonical_utc(value: object, field_name: str) -> datetime:
    text = _exact_text(value, field_name)
    if not text.endswith("Z"):
        raise AdvisoryIntegrationError(f"{field_name} must use canonical UTC Z form")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise AdvisoryIntegrationError(f"{field_name} must be a valid UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0) or _utc_text(parsed) != text:
        raise AdvisoryIntegrationError(f"{field_name} must use canonical UTC Z form")
    return parsed


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _jsonable(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple | list | set | frozenset):
        rendered = [_jsonable(item) for item in value]
        return sorted(rendered, key=lambda item: json.dumps(item, sort_keys=True))
    return value


__all__ = [
    "ADVISORY_REQUEST_SCHEMA",
    "ADVISORY_RESULT_SCHEMA",
    "MAX_ADVISORY_ENVELOPE_BYTES",
    "MAX_PLATFORM_SNAPSHOT_AGE_SECONDS",
    "AdvisoryIntegrationError",
    "AdvisorySource",
    "ChangeAdvisoryInvocation",
    "ChangeAdvisoryResult",
    "canonical_digest",
    "evaluate_change_advisory",
    "load_change_advisory_invocation",
    "parse_change_advisory_invocation",
    "write_change_advisory_result",
]
