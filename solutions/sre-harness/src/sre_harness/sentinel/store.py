"""Persisted "open findings" across periodic Sentinel scans (Stage 7, step 2).

:func:`~sre_harness.sentinel.scan.run_sentinel` dedupes a scan's findings
against a caller-supplied ``open_findings`` sequence; it has no memory of its
own. A :class:`FindingStore` is the seam that gives a periodic runner (the
build-order step 2 ``CronJob``) that memory: load what was open before this
scan, run the scan, then save the union of fresh + still-suppressed findings
for the next tick — exactly what "never re-alert a known/open finding"
requires *across* invocations, not just within one.

Mirrors the :class:`~sre_harness.platform_graph.PlatformGraph` port shape: a
``Protocol`` plus an in-memory fake for tests, with a simple file-backed
adapter usable today (a CronJob mounts a file/PVC) while a database-backed
store is future work.

Finding resolution/closure (removing a finding from the open set once it is
fixed) is manual for this step: an operator edits the open-findings file. A
finding-lifecycle mechanism is future work.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from sre_harness.sentinel.finding import Finding
from sre_harness.sentinel.serialization import finding_from_dict, finding_to_dict

_OPEN_FINDINGS_KEY = "open_findings"


@runtime_checkable
class FindingStore(Protocol):
    """Read/write access to the findings considered open between scans."""

    def load_open(self) -> tuple[Finding, ...]:
        """Return the findings considered open before this scan."""
        ...

    def save_open(self, findings: Sequence[Finding]) -> None:
        """Replace the open set with ``findings`` after this scan."""
        ...


class InMemoryFindingStore:
    """In-memory ``FindingStore`` for tests and single-process ad-hoc runs."""

    def __init__(self, findings: Sequence[Finding] = ()) -> None:
        self._findings: tuple[Finding, ...] = tuple(findings)

    def load_open(self) -> tuple[Finding, ...]:
        return self._findings

    def save_open(self, findings: Sequence[Finding]) -> None:
        self._findings = tuple(findings)


class JsonFileFindingStore:
    """``FindingStore`` backed by a JSON file (CLI / CronJob use today).

    ``load_open`` returns an empty tuple when the file does not exist yet (the
    first scan of a fresh deployment has no history). ``save_open`` overwrites
    the file wholesale — the file *is* the open set, not an append log.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def load_open(self) -> tuple[Finding, ...]:
        if not self._path.exists():
            return ()
        payload = _read_json_object(self._path)
        rows = payload.get(_OPEN_FINDINGS_KEY, [])
        if not isinstance(rows, list):
            raise ValueError(f"'{_OPEN_FINDINGS_KEY}' must be a list, got {type(rows).__name__}")
        return tuple(finding_from_dict(row) for row in rows)

    def save_open(self, findings: Sequence[Finding]) -> None:
        if self._path.exists() and not self._path.is_file():
            raise ValueError(f"{self._path} is not a file")
        payload = {_OPEN_FINDINGS_KEY: [finding_to_dict(finding) for finding in findings]}
        self._path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{path} is not a file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object, got {type(payload).__name__}")
    return payload


__all__ = [
    "FindingStore",
    "InMemoryFindingStore",
    "JsonFileFindingStore",
]
