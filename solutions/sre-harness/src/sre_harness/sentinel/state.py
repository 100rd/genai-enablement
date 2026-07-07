"""The read-only state snapshot Sentinel detectors evaluate.

A :class:`SentinelState` is the continuous-detection counterpart to the gate's
:class:`~sre_harness.eval.case.GateSnapshot`: an immutable, replayable view of the
running platform at a point in time. Detectors are *pure rules over this state*
(the strongest verification tier per the plan), so the whole surface is
unit-/eval-testable offline against hand-built snapshots — exactly like the gate
against the ``PlatformGraph`` fake — while the live observability adapters
(Datadog / Loki / CloudWatch / Omniscience) are wired up separately.

Every signal is optional and defaults empty, so a detector whose inputs are
absent simply surfaces nothing (mirroring the gate's optional
``actions`` / ``required_namespaces``). The three seed signals here back the two
shipped deterministic detectors:

- :class:`SaturationSample` / :class:`ExpiryItem` → ``saturation_expiry``
- :class:`ErrorSignatureWindow` → ``new_error_signature``

Later detectors (error-rate-vs-baseline, change-induced-regression, drift) add
their own signal fields here without changing the detector contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SaturationSample:
    """A tracked resource's utilisation, with an optional growth trend.

    ``used`` / ``capacity`` are in the same arbitrary unit (bytes, connections,
    pods, ...); ``growth_per_interval`` is the per-snapshot increase used to
    project exhaustion. ``capacity`` must be positive.
    """

    resource: str
    kind: str
    used: float
    capacity: float
    cluster: str | None = None
    growth_per_interval: float = 0.0

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError(f"capacity must be > 0, got {self.capacity}")

    @property
    def utilization(self) -> float:
        """Current fraction of capacity in use (``used / capacity``)."""
        return self.used / self.capacity


@dataclass(frozen=True)
class ExpiryItem:
    """A credential / certificate that expires, with days remaining.

    ``expires_in_days`` may be ``<= 0`` to represent an already-expired item.
    """

    name: str
    kind: str
    expires_in_days: int


@dataclass(frozen=True)
class ErrorSignatureWindow:
    """Baseline vs. current error signatures for one service.

    A *signature* is an already-normalised error identity (e.g. a stack-trace
    fingerprint or an error code) — the deterministic detector only takes the
    set difference; the *clustering/naming* of raw errors into signatures is the
    (future, optional) cheap-model step the ADR calls out, not done here.
    """

    service: str
    baseline: frozenset[str]
    current: frozenset[str]


@dataclass(frozen=True)
class SentinelState:
    """An immutable snapshot of platform signals for one detection pass."""

    saturation_samples: tuple[SaturationSample, ...] = ()
    expiry_items: tuple[ExpiryItem, ...] = ()
    error_windows: tuple[ErrorSignatureWindow, ...] = field(default_factory=tuple)


__all__ = [
    "ErrorSignatureWindow",
    "ExpiryItem",
    "SaturationSample",
    "SentinelState",
]
