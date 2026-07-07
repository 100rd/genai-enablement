"""The detector contract: a :class:`Finding` and the :class:`Severity` scale.

Sentinel (Stage 7 — see [`docs/decisions/0001-continuous-detection-sentinel.md`])
is the harness's *continuous / periodic* preventive surface, the counterpart to
the *point-in-time* change-validation gate (Stage 2). Where the gate answers "is
*this change* safe?", Sentinel answers "is the *running system* drifting toward a
problem, or showing a *new* class of problem?".

A **detector** mirrors the gate-check shape (a pure function over platform state),
generalised from the ADR's ``Detector(state) -> Finding`` to
``Detector(state) -> Sequence[Finding]``: one detector scans *many* resources
(certs, queues, signatures), so it naturally surfaces zero-or-more findings in a
single pass, exactly as a presence check surfaces zero-or-more missing names.

Per the ADR, **detection is read-only (Tier 1)** and **emitting a finding is
advisory (Tier 2)** — Sentinel never executes remediation; it feeds the
gate → runbook → permanent-fix loop.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sre_harness.sentinel.state import SentinelState


class Severity(IntEnum):
    """How bad the surfaced condition is, ordered ``LOW < ... < CRITICAL``.

    An :class:`~enum.IntEnum` so findings rank numerically; the value doubles as
    the severity weight in :attr:`Finding.rank`.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class Finding:
    """One thing a detector surfaced, with the evidence behind it.

    Fields follow the ADR contract
    (``detector_id, kind, severity, confidence, evidence, suggested_runbook?``)
    plus a ``fingerprint`` — a stable identity for the *specific* condition
    (e.g. the resource name or the novel signature) so repeat scans dedupe
    against an already-open finding instead of re-alerting.

    ``evidence`` is a JSON-serialisable mapping (primitives / tuples / dicts) so a
    report can be surfaced without bespoke serialisation, like ``CheckResult``.
    """

    detector_id: str
    kind: str
    severity: Severity
    confidence: float
    fingerprint: str
    rationale: str
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_runbook: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        if not self.fingerprint.strip():
            raise ValueError("finding fingerprint must not be blank")

    @property
    def dedup_key(self) -> str:
        """Stable identity of the *condition* — the key repeat scans dedupe on.

        Scoped by ``detector_id`` and ``kind`` so two detectors that happen to use
        the same fingerprint (e.g. a resource name) never collide.
        """
        return f"{self.detector_id}:{self.kind}:{self.fingerprint}"

    @property
    def rank(self) -> float:
        """Ranking score ``severity × confidence`` (higher is more urgent).

        The ADR ranks findings "by severity × confidence"; this is that product,
        used to order a report's findings most-urgent-first.
        """
        return float(self.severity.value) * self.confidence


# A detector maps a read-only state snapshot to zero-or-more findings. Pure and
# side-effect-free, exactly like a gate ``Check``.
Detector = Callable[["SentinelState"], Sequence[Finding]]


__all__ = [
    "Detector",
    "Finding",
    "Severity",
]
