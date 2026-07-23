"""SPEC-B1 closed read-only incident-snapshot ingestion boundary."""

from __future__ import annotations

import errno
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from sre_harness.triage.contracts import (
    EvidenceItem,
    EvidenceKind,
    IncidentAlert,
    IncidentSnapshot,
    RcaDraft,
)
from sre_harness.triage.pipeline import ReadOnlyAnalyzer, run_triage

SNAPSHOT_SCHEMA_VERSION = "sre-harness.incident-snapshot/v1"
MAX_SNAPSHOT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class SnapshotRequest:
    """Exact incident and temporal boundary requested from a read-only source."""

    incident_id: str
    as_of: datetime

    def __post_init__(self) -> None:
        if not self.incident_id.strip():
            raise ValueError("snapshot request incident id must not be blank")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() != timedelta(0):
            raise ValueError("snapshot request as_of must be timezone-aware UTC")


class IncidentSnapshotSource(Protocol):
    """Minimal read-only source port; no write or acknowledgement method exists."""

    def snapshot(self, request: SnapshotRequest) -> IncidentSnapshot: ...


class JsonFileIncidentSnapshotSource:
    """Strict local-file adapter for portable fixtures and offline operator input."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def snapshot(self, request: SnapshotRequest) -> IncidentSnapshot:
        if type(request) is not SnapshotRequest:
            raise TypeError("JSON incident source requires an exact SnapshotRequest")
        payload = _parse_json(_read_bounded_utf8(self._path))
        snapshot = _snapshot_from_payload(payload)
        return _rejoin(request, snapshot)


def load_snapshot(
    request: SnapshotRequest,
    source: IncidentSnapshotSource,
) -> IncidentSnapshot:
    """Read once through ``snapshot`` and rejoin exact incident/as-of authority."""
    if type(request) is not SnapshotRequest:
        raise TypeError("load_snapshot requires an exact SnapshotRequest")
    observed = source.snapshot(request)
    if type(observed) is not IncidentSnapshot:
        raise TypeError("incident source must return an exact IncidentSnapshot")
    return _rejoin(request, observed)


def run_triage_from_source(
    request: SnapshotRequest,
    source: IncidentSnapshotSource,
    *,
    analyzer: ReadOnlyAnalyzer | None = None,
) -> RcaDraft:
    """Load an exact read-only snapshot and run the action-free triage pipeline."""
    snapshot = load_snapshot(request, source)
    return run_triage(snapshot, analyzer=analyzer)


def _rejoin(
    request: SnapshotRequest,
    snapshot: IncidentSnapshot,
) -> IncidentSnapshot:
    if snapshot.alert.incident_id != request.incident_id:
        raise ValueError("incident snapshot incident id mismatch")
    if snapshot.captured_at != request.as_of:
        raise ValueError("incident snapshot as_of mismatch")
    return snapshot


def _read_bounded_utf8(path: Path) -> str:
    if path.is_symlink():
        raise ValueError("incident snapshot path must not be a symlink")

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise ValueError(f"incident snapshot file not found: {path}") from exc
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError("incident snapshot path must not be a symlink") from exc
        raise ValueError(f"incident snapshot file cannot be opened: {path}") from exc

    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("incident snapshot path must be a regular file")
        if metadata.st_size > MAX_SNAPSHOT_BYTES:
            raise ValueError(f"incident snapshot exceeds maximum {MAX_SNAPSHOT_BYTES} bytes")
        chunks: list[bytes] = []
        remaining = MAX_SNAPSHOT_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    finally:
        os.close(descriptor)

    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError(f"incident snapshot exceeds maximum {MAX_SNAPSHOT_BYTES} bytes")
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("incident snapshot must be valid UTF-8") from exc


def _parse_json(document: str) -> dict[str, object]:
    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON number is forbidden: {value}")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key is forbidden: {key}")
            result[key] = value
        return result

    try:
        payload = json.loads(
            document,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError("incident snapshot contains malformed JSON") from exc
    if type(payload) is not dict:
        raise TypeError("incident snapshot document must be a JSON object")
    return payload


def _closed_object(
    value: object,
    *,
    name: str,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> dict[str, object]:
    if type(value) is not dict:
        raise TypeError(f"{name} must be a JSON object")
    keys = set(value)
    missing = sorted(required - keys)
    unknown = sorted(keys - required - optional)
    if missing:
        raise ValueError(f"{name} has missing fields: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{name} has unknown fields: {', '.join(unknown)}")
    return value


def _string(value: object, field: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field} must be a string")
    return value


def _timestamp(value: object, field: str) -> datetime:
    raw = _string(value, field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be timezone-aware UTC")
    return parsed


def _snapshot_from_payload(payload: dict[str, object]) -> IncidentSnapshot:
    document = _closed_object(
        payload,
        name="incident snapshot",
        required=frozenset({"schemaVersion", "alert", "capturedAt", "evidence"}),
    )
    if _string(document["schemaVersion"], "schemaVersion") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("incident snapshot schema version is unsupported")

    alert_data = _closed_object(
        document["alert"],
        name="incident alert",
        required=frozenset({"incidentId", "service", "startedAt", "summary"}),
    )
    alert = IncidentAlert(
        incident_id=_string(alert_data["incidentId"], "incidentId"),
        service=_string(alert_data["service"], "alert service"),
        started_at=_timestamp(alert_data["startedAt"], "startedAt"),
        summary=_string(alert_data["summary"], "alert summary"),
    )

    evidence_data = document["evidence"]
    if type(evidence_data) is not list:
        raise TypeError("evidence must be a JSON array")
    evidence = tuple(
        _evidence_from_payload(value, index=index) for index, value in enumerate(evidence_data)
    )
    return IncidentSnapshot(
        alert=alert,
        captured_at=_timestamp(document["capturedAt"], "capturedAt"),
        evidence=evidence,
    )


def _evidence_from_payload(value: object, *, index: int) -> EvidenceItem:
    name = f"evidence[{index}]"
    evidence = _closed_object(
        value,
        name=name,
        required=frozenset({"evidenceId", "kind", "service", "observedAt", "statement"}),
        optional=frozenset({"value"}),
    )
    kind_value = _string(evidence["kind"], "evidence kind")
    try:
        kind = EvidenceKind(kind_value)
    except ValueError as exc:
        raise ValueError(f"evidence kind is unsupported: {kind_value}") from exc

    metric_value: float | None = None
    if "value" in evidence:
        raw_value = evidence["value"]
        if isinstance(raw_value, bool) or not isinstance(raw_value, int | float):
            raise TypeError("evidence value must be a number")
        metric_value = float(raw_value)
    return EvidenceItem(
        evidence_id=_string(evidence["evidenceId"], "evidenceId"),
        kind=kind,
        service=_string(evidence["service"], "evidence service"),
        observed_at=_timestamp(evidence["observedAt"], "observedAt"),
        statement=_string(evidence["statement"], "evidence statement"),
        value=metric_value,
    )


__all__ = [
    "IncidentSnapshotSource",
    "JsonFileIncidentSnapshotSource",
    "MAX_SNAPSHOT_BYTES",
    "SNAPSHOT_SCHEMA_VERSION",
    "SnapshotRequest",
    "load_snapshot",
    "run_triage_from_source",
]
