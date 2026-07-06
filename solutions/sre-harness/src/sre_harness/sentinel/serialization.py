"""JSON (de)serialization for Sentinel findings and state (Stage 7, step 2).

The Sentinel CLI and :class:`~sre_harness.sentinel.store.JsonFileFindingStore`
need :class:`~sre_harness.sentinel.finding.Finding` and
:class:`~sre_harness.sentinel.state.SentinelState` to cross a JSON boundary —
findings persisted between periodic scans, and state snapshots loaded from a
fixture/ConfigMap file. This module is the single seam that maps those
dataclasses to and from plain JSON-safe dicts, with **typed field extraction**
(no ``**kwargs`` into a dataclass constructor) so malformed input fails with a
clear :class:`ValueError` naming the field, never a bare ``KeyError`` or
``TypeError`` raised deep inside a dataclass.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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

    Raises ``ValueError`` (naming the field) on a missing required key, an
    unknown ``severity`` name, or non-object ``evidence`` — everything else
    (confidence range, blank fingerprint) is enforced by ``Finding`` itself.
    """
    _require_fields(data, _FINDING_REQUIRED_FIELDS, what="finding")
    evidence = data.get("evidence") or {}
    if not isinstance(evidence, dict):
        raise ValueError(f"finding evidence must be an object, got {type(evidence).__name__}")
    runbook = data.get("suggested_runbook")
    return Finding(
        detector_id=str(data["detector_id"]),
        kind=str(data["kind"]),
        severity=_parse_severity(data["severity"]),
        confidence=float(data["confidence"]),
        fingerprint=str(data["fingerprint"]),
        rationale=str(data["rationale"]),
        evidence=dict(evidence),
        suggested_runbook=(str(runbook) if runbook is not None else None),
    )


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
        used=float(row["used"]),
        capacity=float(row["capacity"]),
        cluster=(str(cluster) if cluster is not None else None),
        growth_per_interval=float(row.get("growth_per_interval", 0.0)),
    )


def _expiry_item_from_dict(row: Any) -> ExpiryItem:
    _require_fields(row, ("name", "kind", "expires_in_days"), what="expiry item")
    return ExpiryItem(
        name=str(row["name"]),
        kind=str(row["kind"]),
        expires_in_days=int(row["expires_in_days"]),
    )


def _error_window_from_dict(row: Any) -> ErrorSignatureWindow:
    _require_fields(row, ("service", "baseline", "current"), what="error window")
    return ErrorSignatureWindow(
        service=str(row["service"]),
        baseline=frozenset(str(item) for item in row["baseline"]),
        current=frozenset(str(item) for item in row["current"]),
    )


def _require_fields(data: Any, fields: Sequence[str], *, what: str) -> None:
    if not isinstance(data, Mapping):
        raise ValueError(f"{what} must be an object, got {type(data).__name__}")
    missing = [field for field in fields if field not in data]
    if missing:
        raise ValueError(f"{what} missing required field(s): {', '.join(missing)}")


__all__ = [
    "finding_from_dict",
    "finding_to_dict",
    "state_from_dict",
]
