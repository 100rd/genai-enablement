"""Seed lead-time scenario suite for Sentinel.

Code-fixture timelines exercising the two deterministic detectors' lead-time
behaviour: three incident timelines where a detector fires *before* the page, plus
one clean timeline the detectors must stay silent on (the false-positive control).
Kept as code (not a data file) for the same reason as the gate seed suite — zero
dependency, refactor-safe — while there is a single offline target; a data-dir
loader can replace :func:`load_lead_time_scenarios` later without changing callers.
"""

from __future__ import annotations

from sre_harness.sentinel.eval import LeadTimeScenario
from sre_harness.sentinel.state import (
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)

_DISK_CAPACITY = 100.0
_BASELINE_SIGNATURES = frozenset({"E1", "E2"})


def _disk_timeline(levels: tuple[float, ...]) -> tuple[SentinelState, ...]:
    return tuple(
        SentinelState(
            saturation_samples=(
                SaturationSample(
                    resource="pvc-payments", kind="disk", used=level, capacity=_DISK_CAPACITY
                ),
            )
        )
        for level in levels
    )


def _expiry_timeline(days: tuple[int, ...]) -> tuple[SentinelState, ...]:
    return tuple(
        SentinelState(expiry_items=(ExpiryItem(name="api-tls", kind="cert", expires_in_days=d),))
        for d in days
    )


def _signature_timeline(current_windows: tuple[frozenset[str], ...]) -> tuple[SentinelState, ...]:
    return tuple(
        SentinelState(
            error_windows=(
                ErrorSignatureWindow(
                    service="payments", baseline=_BASELINE_SIGNATURES, current=current
                ),
            )
        )
        for current in current_windows
    )


def load_lead_time_scenarios() -> tuple[LeadTimeScenario, ...]:
    """Return the seed lead-time suite (deterministic order)."""
    return (
        # Disk ramps 50→97%; the warn band (75%) fires at index 2, two snapshots
        # before the page at index 4.
        LeadTimeScenario(
            id="sat-disk-ramp-to-critical",
            timeline=_disk_timeline((50.0, 70.0, 80.0, 92.0, 97.0)),
            paged_at_index=4,
            expected_detector_id="saturation_expiry",
            expected_kind="saturation",
        ),
        # Cert countdown 60→2 days; the warn window (30d) fires at index 1, two
        # snapshots before the expiry-driven page at index 3.
        LeadTimeScenario(
            id="expiry-cert-countdown",
            timeline=_expiry_timeline((60, 28, 10, 2)),
            paged_at_index=3,
            expected_detector_id="saturation_expiry",
            expected_kind="expiry",
        ),
        # A novel signature appears at index 1 and pages at index 2 — one snapshot
        # of lead.
        LeadTimeScenario(
            id="new-signature-appears",
            timeline=_signature_timeline(
                (
                    _BASELINE_SIGNATURES,
                    _BASELINE_SIGNATURES | {"E_NEW"},
                    _BASELINE_SIGNATURES | {"E_NEW"},
                )
            ),
            paged_at_index=2,
            expected_detector_id="new_error_signature",
        ),
        # Healthy disk throughout — no incident; the detectors must stay silent
        # (false-positive control).
        LeadTimeScenario(
            id="clean-no-incident",
            timeline=_disk_timeline((30.0, 35.0, 40.0)),
            paged_at_index=None,
            expected_detector_id=None,
        ),
    )


__all__ = ["load_lead_time_scenarios"]
