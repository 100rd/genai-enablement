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
``actions`` / ``required_namespaces``). The six seed signals here back the
five shipped deterministic detectors:

- :class:`SaturationSample` / :class:`ExpiryItem` → ``saturation_expiry``
- :class:`ErrorSignatureWindow` → ``new_error_signature``
- :class:`ErrorRateWindow` → ``error_rate_vs_baseline``
- :class:`ChangeRegressionWindow` → ``change_induced_regression``
- :class:`DriftObservation` → ``config_state_drift``
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

_MAX_AGGREGATE_COUNT = 2**63 - 1


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
class ErrorRateWindow:
    """Aggregate rolling-baseline and current error counts for one service.

    Counts remain aggregate and non-sensitive: raw requests, logs, error bodies,
    identities, and signatures do not belong in this signal.
    """

    service: str
    baseline_errors: int
    baseline_requests: int
    current_errors: int
    current_requests: int
    allowed_error_rate: float

    def __post_init__(self) -> None:
        if (
            type(self.service) is not str
            or not self.service
            or self.service != self.service.strip()
            or len(self.service) > 200
        ):
            raise ValueError("service must be bounded non-blank text")
        for name in (
            "baseline_errors",
            "baseline_requests",
            "current_errors",
            "current_requests",
        ):
            value = getattr(self, name)
            if type(value) is not int:
                raise ValueError(f"{name} must be an exact integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
            if value > _MAX_AGGREGATE_COUNT:
                raise ValueError(f"{name} must be a bounded aggregate count")
        if self.baseline_errors > self.baseline_requests:
            raise ValueError("baseline errors cannot exceed baseline requests")
        if self.current_errors > self.current_requests:
            raise ValueError("current errors cannot exceed current requests")
        if type(self.allowed_error_rate) is not float or not math.isfinite(self.allowed_error_rate):
            raise ValueError("allowed_error_rate must be an exact finite float")
        if not 0.0 < self.allowed_error_rate < 1.0:
            raise ValueError("allowed_error_rate must be between zero and one")

    @property
    def baseline_rate(self) -> float:
        return self.baseline_errors / self.baseline_requests if self.baseline_requests else 0.0

    @property
    def current_rate(self) -> float:
        return self.current_errors / self.current_requests if self.current_requests else 0.0


@dataclass(frozen=True)
class ChangeRegressionWindow:
    """Exact pre/post error aggregates bound to one immutable deployment."""

    service: str
    previous_revision: str
    deployed_revision: str
    baseline_ended_at: int
    deployed_at: int
    current_started_at: int
    observed_at: int
    intervening_deployments: int
    baseline_errors: int
    baseline_requests: int
    current_errors: int
    current_requests: int
    allowed_error_rate: float

    def __post_init__(self) -> None:
        if (
            type(self.service) is not str
            or not self.service
            or self.service != self.service.strip()
            or len(self.service) > 200
        ):
            raise ValueError("service must be bounded non-blank text")
        for name in ("previous_revision", "deployed_revision"):
            value = getattr(self, name)
            if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError(f"{name} must be a canonical SHA-256 revision")
        if self.previous_revision == self.deployed_revision:
            raise ValueError("previous and deployed revisions must be distinct")
        for name in (
            "baseline_ended_at",
            "deployed_at",
            "current_started_at",
            "observed_at",
            "intervening_deployments",
            "baseline_errors",
            "baseline_requests",
            "current_errors",
            "current_requests",
        ):
            value = getattr(self, name)
            if type(value) is not int:
                raise ValueError(f"{name} must be an exact integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
            if value > _MAX_AGGREGATE_COUNT:
                raise ValueError(f"{name} must be bounded")
        if self.intervening_deployments > 1000:
            raise ValueError("intervening_deployments must be at most 1000")
        if self.baseline_ended_at > self.deployed_at:
            raise ValueError("baseline window must end no later than deployment")
        if self.current_started_at < self.deployed_at:
            raise ValueError("current window must start no earlier than deployment")
        if self.observed_at <= self.current_started_at:
            raise ValueError("observed time must be after current window start")
        if self.baseline_errors > self.baseline_requests:
            raise ValueError("baseline errors cannot exceed baseline requests")
        if self.current_errors > self.current_requests:
            raise ValueError("current errors cannot exceed current requests")
        if type(self.allowed_error_rate) is not float or not math.isfinite(self.allowed_error_rate):
            raise ValueError("allowed_error_rate must be an exact finite float")
        if not 0.0 < self.allowed_error_rate < 1.0:
            raise ValueError("allowed_error_rate must be between zero and one")

    @property
    def baseline_rate(self) -> float:
        return self.baseline_errors / self.baseline_requests if self.baseline_requests else 0.0

    @property
    def current_rate(self) -> float:
        return self.current_errors / self.current_requests if self.current_requests else 0.0

    @property
    def deploy_age_seconds(self) -> int:
        return self.observed_at - self.deployed_at


@dataclass(frozen=True)
class DriftObservation:
    """One normalized desired↔observed digest fact for a tracked resource.

    Raw manifests, configuration values, diffs, and Secret data do not belong
    in this signal. ``None`` for ``observed_revision`` means the tracked
    resource is absent from the normalized observed state.
    """

    resource_kind: str
    resource_id: str
    tracking_policy_revision: str
    desired_revision: str
    observed_revision: str | None
    desired_recorded_at: int
    mismatch_started_at: int | None
    observed_at: int
    consecutive_mismatches: int

    def __post_init__(self) -> None:
        if (
            type(self.resource_kind) is not str
            or re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]{0,99}", self.resource_kind) is None
        ):
            raise ValueError("resource_kind must be safe bounded text")
        if (
            type(self.resource_id) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", self.resource_id) is None
        ):
            raise ValueError("resource_id must be safe bounded text")
        for name in ("tracking_policy_revision", "desired_revision"):
            value = getattr(self, name)
            if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError(f"{name} must be a canonical SHA-256 revision")
        if self.observed_revision is not None and (
            type(self.observed_revision) is not str
            or re.fullmatch(r"[0-9a-f]{64}", self.observed_revision) is None
        ):
            raise ValueError("observed_revision must be a canonical SHA-256 revision or null")
        for name in ("desired_recorded_at", "observed_at", "consecutive_mismatches"):
            value = getattr(self, name)
            if type(value) is not int:
                raise ValueError(f"{name} must be an exact integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
            if value > _MAX_AGGREGATE_COUNT:
                raise ValueError(f"{name} must be bounded")
        if self.mismatch_started_at is not None:
            if type(self.mismatch_started_at) is not int:
                raise ValueError("mismatch_started_at must be an exact integer or null")
            if self.mismatch_started_at < 0:
                raise ValueError("mismatch_started_at must be non-negative")
            if self.mismatch_started_at > _MAX_AGGREGATE_COUNT:
                raise ValueError("mismatch_started_at must be bounded")
        if self.consecutive_mismatches > 1_000_000:
            raise ValueError("consecutive_mismatches must be at most 1000000")
        if self.desired_recorded_at > self.observed_at:
            raise ValueError("desired state must be recorded no later than observation")

        matches = self.observed_revision == self.desired_revision
        if matches:
            if self.mismatch_started_at is not None or self.consecutive_mismatches != 0:
                raise ValueError("matching revisions cannot carry mismatch evidence")
            return
        if self.mismatch_started_at is None:
            raise ValueError("mismatch start is required when revisions differ or state is absent")
        if self.consecutive_mismatches < 1:
            raise ValueError("a mismatch requires at least one consecutive observation")
        if self.mismatch_started_at < self.desired_recorded_at:
            raise ValueError("mismatch start cannot predate the desired revision")
        if self.mismatch_started_at > self.observed_at:
            raise ValueError("mismatch start cannot be after the observed time")

    @property
    def drift_age_seconds(self) -> int:
        return (
            self.observed_at - self.mismatch_started_at
            if self.mismatch_started_at is not None
            else 0
        )


@dataclass(frozen=True)
class SentinelState:
    """An immutable snapshot of platform signals for one detection pass."""

    saturation_samples: tuple[SaturationSample, ...] = ()
    expiry_items: tuple[ExpiryItem, ...] = ()
    error_windows: tuple[ErrorSignatureWindow, ...] = field(default_factory=tuple)
    error_rate_windows: tuple[ErrorRateWindow, ...] = field(default_factory=tuple)
    change_regression_windows: tuple[ChangeRegressionWindow, ...] = field(default_factory=tuple)
    drift_observations: tuple[DriftObservation, ...] = field(default_factory=tuple)


__all__ = [
    "ChangeRegressionWindow",
    "DriftObservation",
    "ErrorRateWindow",
    "ErrorSignatureWindow",
    "ExpiryItem",
    "SaturationSample",
    "SentinelState",
]
