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
import math
import os
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sre_harness.sentinel.finding import Finding, Severity
from sre_harness.sentinel.state import (
    ChangeRegressionWindow,
    DriftObservation,
    ErrorRateWindow,
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)

_MAX_JSON_BYTES = 1024 * 1024
_MAX_ERROR_RATE_WINDOWS = 1000
_MAX_CHANGE_REGRESSION_WINDOWS = 1000
_MAX_DRIFT_OBSERVATIONS = 1000

_STATE_FIELDS = (
    "_comment",
    "saturation_samples",
    "expiry_items",
    "error_windows",
    "error_rate_windows",
    "change_regression_windows",
    "drift_observations",
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
    if not isinstance(data, Mapping):
        raise ValueError(f"Sentinel state must be an object, got {type(data).__name__}")
    _reject_extra_fields(data, _STATE_FIELDS, what="Sentinel state")
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
        error_rate_windows=tuple(
            _error_rate_window_from_dict(row)
            for row in _bounded_list_field(
                data,
                "error_rate_windows",
                max_items=_MAX_ERROR_RATE_WINDOWS,
            )
        ),
        change_regression_windows=tuple(
            _change_regression_window_from_dict(row)
            for row in _bounded_list_field(
                data,
                "change_regression_windows",
                max_items=_MAX_CHANGE_REGRESSION_WINDOWS,
            )
        ),
        drift_observations=tuple(
            _drift_observation_from_dict(row)
            for row in _bounded_list_field(
                data,
                "drift_observations",
                max_items=_MAX_DRIFT_OBSERVATIONS,
            )
        ),
    )


def _list_field(data: Mapping[str, Any], key: str) -> Sequence[Any]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"'{key}' must be a list, got {type(value).__name__}")
    return value


def _bounded_list_field(data: Mapping[str, Any], key: str, *, max_items: int) -> Sequence[Any]:
    value = _list_field(data, key)
    if len(value) > max_items:
        raise ValueError(f"'{key}' must contain at most {max_items} items")
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


def _error_rate_window_from_dict(row: Any) -> ErrorRateWindow:
    fields = (
        "service",
        "baseline_errors",
        "baseline_requests",
        "current_errors",
        "current_requests",
        "allowed_error_rate",
    )
    _require_fields(row, fields, what="error rate window")
    return ErrorRateWindow(
        service=_as_exact_text(row["service"], field="service"),
        baseline_errors=_as_exact_int(row["baseline_errors"], field="baseline_errors"),
        baseline_requests=_as_exact_int(row["baseline_requests"], field="baseline_requests"),
        current_errors=_as_exact_int(row["current_errors"], field="current_errors"),
        current_requests=_as_exact_int(row["current_requests"], field="current_requests"),
        allowed_error_rate=_as_finite_float(row["allowed_error_rate"], field="allowed_error_rate"),
    )


def _change_regression_window_from_dict(row: Any) -> ChangeRegressionWindow:
    fields = (
        "service",
        "previous_revision",
        "deployed_revision",
        "baseline_ended_at",
        "deployed_at",
        "current_started_at",
        "observed_at",
        "intervening_deployments",
        "baseline_errors",
        "baseline_requests",
        "current_errors",
        "current_requests",
        "allowed_error_rate",
    )
    _require_fields(row, fields, what="change regression window")
    _reject_extra_fields(row, fields, what="change regression window")
    return ChangeRegressionWindow(
        service=_as_exact_text(row["service"], field="service"),
        previous_revision=_as_exact_text(row["previous_revision"], field="previous_revision"),
        deployed_revision=_as_exact_text(row["deployed_revision"], field="deployed_revision"),
        baseline_ended_at=_as_exact_int(row["baseline_ended_at"], field="baseline_ended_at"),
        deployed_at=_as_exact_int(row["deployed_at"], field="deployed_at"),
        current_started_at=_as_exact_int(row["current_started_at"], field="current_started_at"),
        observed_at=_as_exact_int(row["observed_at"], field="observed_at"),
        intervening_deployments=_as_exact_int(
            row["intervening_deployments"], field="intervening_deployments"
        ),
        baseline_errors=_as_exact_int(row["baseline_errors"], field="baseline_errors"),
        baseline_requests=_as_exact_int(row["baseline_requests"], field="baseline_requests"),
        current_errors=_as_exact_int(row["current_errors"], field="current_errors"),
        current_requests=_as_exact_int(row["current_requests"], field="current_requests"),
        allowed_error_rate=_as_finite_float(row["allowed_error_rate"], field="allowed_error_rate"),
    )


def _drift_observation_from_dict(row: Any) -> DriftObservation:
    fields = (
        "resource_kind",
        "resource_id",
        "tracking_policy_revision",
        "desired_revision",
        "observed_revision",
        "desired_recorded_at",
        "mismatch_started_at",
        "observed_at",
        "consecutive_mismatches",
    )
    _require_keys(row, fields, what="drift observation")
    _reject_extra_fields(row, fields, what="drift observation")
    return DriftObservation(
        resource_kind=_as_exact_text(row["resource_kind"], field="resource_kind"),
        resource_id=_as_exact_text(row["resource_id"], field="resource_id"),
        tracking_policy_revision=_as_exact_text(
            row["tracking_policy_revision"], field="tracking_policy_revision"
        ),
        desired_revision=_as_exact_text(row["desired_revision"], field="desired_revision"),
        observed_revision=_as_optional_exact_text(
            row["observed_revision"], field="observed_revision"
        ),
        desired_recorded_at=_as_exact_int(row["desired_recorded_at"], field="desired_recorded_at"),
        mismatch_started_at=_as_optional_exact_int(
            row["mismatch_started_at"], field="mismatch_started_at"
        ),
        observed_at=_as_exact_int(row["observed_at"], field="observed_at"),
        consecutive_mismatches=_as_exact_int(
            row["consecutive_mismatches"], field="consecutive_mismatches"
        ),
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


def _as_exact_text(value: Any, *, field: str) -> str:
    if type(value) is not str:
        raise ValueError(f"'{field}' must be a string")
    return value


def _as_optional_exact_text(value: Any, *, field: str) -> str | None:
    return None if value is None else _as_exact_text(value, field=field)


def _as_exact_int(value: Any, *, field: str) -> int:
    if type(value) is not int:
        raise ValueError(f"'{field}' must be an exact integer")
    return value


def _as_optional_exact_int(value: Any, *, field: str) -> int | None:
    return None if value is None else _as_exact_int(value, field=field)


def _as_finite_float(value: Any, *, field: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError(f"'{field}' must be an exact finite float")
    return value


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


def _require_keys(data: Any, fields: Sequence[str], *, what: str) -> None:
    """Require key presence while allowing a field's schema to admit null."""
    if not isinstance(data, Mapping):
        raise ValueError(f"{what} must be an object, got {type(data).__name__}")
    missing = [field for field in fields if field not in data]
    if missing:
        raise ValueError(f"{what} missing required field(s): {', '.join(missing)}")


def _reject_extra_fields(data: Mapping[str, Any], fields: Sequence[str], *, what: str) -> None:
    unexpected = set(data) - set(fields)
    if unexpected:
        names = ", ".join(sorted(str(name) for name in unexpected))
        raise ValueError(f"{what} has unexpected field(s): {names}")


def read_json_object(path: Path) -> dict[str, Any]:
    """Read ``path`` as JSON, requiring the top-level value to be an object.

    Shared by :class:`~sre_harness.sentinel.store.JsonFileFindingStore` and
    :class:`~sre_harness.sentinel.source.JsonFileStateSource`. Raises
    ``ValueError`` (naming ``path``) if it is not a regular file, contains
    invalid JSON, or the parsed value is not a JSON object.
    """
    if path.is_symlink():
        raise ValueError(f"{path} must not be a symlink")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"{path} is unavailable") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"{path} is not a file")
        if before.st_size > _MAX_JSON_BYTES:
            raise ValueError(f"{path} is too large")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(_MAX_JSON_BYTES + 1)
        after = os.fstat(descriptor)
        if len(raw) > _MAX_JSON_BYTES:
            raise ValueError(f"{path} is too large")
        if (
            len(raw) != before.st_size
            or after.st_size != before.st_size
            or after.st_mtime_ns != before.st_mtime_ns
        ):
            raise ValueError(f"{path} changed while reading")
        payload = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_closed_json_object,
            parse_constant=_reject_nonfinite_json,
        )
    except (json.JSONDecodeError, RecursionError, UnicodeDecodeError) as exc:
        # Deeply-nested JSON makes the decoder recurse per level and raise a
        # bare RecursionError, not JSONDecodeError — fold it into the same
        # clean ValueError path rather than an uncaught crash.
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"{path} is unavailable") from exc
    finally:
        os.close(descriptor)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object, got {type(payload).__name__}")
    return payload


def _closed_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON field: {key}")
        value[key] = item
    return value


def _reject_nonfinite_json(value: str) -> None:
    raise ValueError(f"JSON number must be finite, got {value}")


__all__ = [
    "finding_from_dict",
    "finding_to_dict",
    "read_json_object",
    "state_from_dict",
]
