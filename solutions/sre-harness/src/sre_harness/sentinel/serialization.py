"""JSON (de)serialization for Sentinel findings and state (Stage 7, step 2).

The Sentinel CLI and :class:`~sre_harness.sentinel.store.JsonFileFindingStore`
need :class:`~sre_harness.sentinel.finding.Finding` and
:class:`~sre_harness.sentinel.state.SentinelState` to cross a JSON boundary —
findings persisted between periodic scans, and state snapshots loaded from a
fixture/ConfigMap file. This module is the single seam that maps those
dataclasses to and from plain JSON-safe dicts, with **typed field extraction**
(no ``**kwargs`` into a dataclass constructor) so malformed input fails with a
clear :class:`ValueError` naming the field — never a bare ``KeyError`` from a
missing key, or a ``TypeError`` from a numeric coercion or a non-iterable
value, raised deep inside a dataclass.

Also hosts :func:`read_json_object`, the one shared "read a JSON file, require
an object" helper used by both
:class:`~sre_harness.sentinel.store.JsonFileFindingStore` and
:class:`~sre_harness.sentinel.source.JsonFileStateSource`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sre_harness.sentinel.finding import Finding, Severity
from sre_harness.sentinel.state import (
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)

_FINDING_REQUIRED_FIELDS = (
    "detector_id",
    "kind",
    "severity",
    "confidence",
    "fingerprint",
    "rationale",
)


def finding_to_dict(finding: Finding) -> dict[str, Any]:
    """Render ``finding`` as a JSON-safe dict (``Severity`` -> its name)."""
    return {
        "detector_id": finding.detector_id,
        "kind": finding.kind,
        "severity": finding.severity.name,
        "confidence": finding.confidence,
        "fingerprint": finding.fingerprint,
        "rationale": finding.rationale,
        "evidence": dict(finding.evidence),
        "suggested_runbook": finding.suggested_runbook,
    }


def finding_from_dict(data: Mapping[str, Any]) -> Finding:
    """Parse one :class:`Finding` from a dict produced by :func:`finding_to_dict`.

    Raises ``ValueError`` (naming the field) on a missing/``null`` required
    key, an unknown ``severity`` name, a non-numeric ``confidence``, or a
    non-object ``evidence`` — everything else (confidence range, blank
    fingerprint) is enforced by ``Finding`` itself.
    """
    _require_fields(data, _FINDING_REQUIRED_FIELDS, what="finding")
    runbook = data.get("suggested_runbook")
    return Finding(
        detector_id=str(data["detector_id"]),
        kind=str(data["kind"]),
        severity=_parse_severity(data["severity"]),
        confidence=_as_float(data["confidence"], field="confidence"),
        fingerprint=str(data["fingerprint"]),
        rationale=str(data["rationale"]),
        evidence=_as_evidence(data.get("evidence")),
        suggested_runbook=(str(runbook) if runbook is not None else None),
    )


def _as_evidence(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"finding evidence must be an object, got {type(value).__name__}")
    return dict(value)


def _parse_severity(raw: Any) -> Severity:
    if not isinstance(raw, str):
        raise ValueError(f"severity must be a string, got {type(raw).__name__}")
    try:
        return Severity[raw]
    except KeyError:
        raise ValueError(f"unknown severity {raw!r}") from None


def state_from_dict(data: Mapping[str, Any]) -> SentinelState:
    """Parse a :class:`SentinelState` snapshot from a dict; all fields optional."""
    return SentinelState(
        saturation_samples=tuple(
            _saturation_sample_from_dict(row) for row in _list_field(data, "saturation_samples")
        ),
        expiry_items=tuple(
            _expiry_item_from_dict(row) for row in _list_field(data, "expiry_items")
        ),
        error_windows=tuple(
            _error_window_from_dict(row) for row in _list_field(data, "error_windows")
        ),
    )


def _list_field(data: Mapping[str, Any], key: str) -> Sequence[Any]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"'{key}' must be a list, got {type(value).__name__}")
    return value


def _saturation_sample_from_dict(row: Any) -> SaturationSample:
    _require_fields(row, ("resource", "kind", "used", "capacity"), what="saturation sample")
    cluster = row.get("cluster")
    return SaturationSample(
        resource=str(row["resource"]),
        kind=str(row["kind"]),
        used=_as_float(row["used"], field="used"),
        capacity=_as_float(row["capacity"], field="capacity"),
        cluster=(str(cluster) if cluster is not None else None),
        growth_per_interval=_as_float(
            row.get("growth_per_interval", 0.0), field="growth_per_interval"
        ),
    )


def _expiry_item_from_dict(row: Any) -> ExpiryItem:
    _require_fields(row, ("name", "kind", "expires_in_days"), what="expiry item")
    return ExpiryItem(
        name=str(row["name"]),
        kind=str(row["kind"]),
        expires_in_days=_as_int(row["expires_in_days"], field="expires_in_days"),
    )


def _error_window_from_dict(row: Any) -> ErrorSignatureWindow:
    _require_fields(row, ("service", "baseline", "current"), what="error window")
    return ErrorSignatureWindow(
        service=str(row["service"]),
        baseline=_string_set(row["baseline"], field="baseline"),
        current=_string_set(row["current"], field="current"),
    )


def _string_set(value: Any, *, field: str) -> frozenset[str]:
    if not isinstance(value, list):
        raise ValueError(f"'{field}' must be a list, got {type(value).__name__}")
    return frozenset(str(item) for item in value)


def _as_float(value: Any, *, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{field}' must be a number, got {value!r}") from None


def _as_int(value: Any, *, field: str) -> int:
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{field}' must be an integer, got {value!r}") from None
    if not as_float.is_integer():
        raise ValueError(f"'{field}' must be an integer, got {value!r}")
    return int(as_float)


def _require_fields(data: Any, fields: Sequence[str], *, what: str) -> None:
    """Reject a missing key AND an explicit ``null`` as "missing" alike.

    A required *string* field left as JSON ``null`` would otherwise silently
    coerce via ``str(None)`` into the literal string ``"None"`` with no error
    — funneling both cases through one check closes that gap.
    """
    if not isinstance(data, Mapping):
        raise ValueError(f"{what} must be an object, got {type(data).__name__}")
    missing = [field for field in fields if data.get(field) is None]
    if missing:
        raise ValueError(f"{what} missing required field(s): {', '.join(missing)}")


def read_json_object(path: Path) -> dict[str, Any]:
    """Read ``path`` as JSON, requiring the top-level value to be an object.

    Shared by :class:`~sre_harness.sentinel.store.JsonFileFindingStore` and
    :class:`~sre_harness.sentinel.source.JsonFileStateSource`. Raises
    ``ValueError`` (naming ``path``) if it is not a regular file, contains
    invalid JSON, or the parsed value is not a JSON object.
    """
    if not path.is_file():
        raise ValueError(f"{path} is not a file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, RecursionError) as exc:
        # Deeply-nested JSON makes the decoder recurse per level and raise a
        # bare RecursionError, not JSONDecodeError — fold it into the same
        # clean ValueError path rather than an uncaught crash.
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object, got {type(payload).__name__}")
    return payload


__all__ = [
    "finding_from_dict",
    "finding_to_dict",
    "read_json_object",
    "state_from_dict",
]
