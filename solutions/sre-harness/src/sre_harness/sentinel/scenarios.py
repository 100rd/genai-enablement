"""Seed lead-time scenario suite for Sentinel.

Code-fixture timelines exercising the deterministic detectors' lead-time and
false-positive behaviour. B7 adds error-rate, change-regression, and normalized
config-state-drift incident timelines plus detector-specific clean controls.
Kept as code (not a data file) for the same reason as the gate seed suite — zero
dependency, refactor-safe — while there is a single offline target; a data-dir
loader can replace :func:`load_lead_time_scenarios` later without changing callers.
"""

from __future__ import annotations

from sre_harness.sentinel.eval import LeadTimeScenario
from sre_harness.sentinel.state import (
    ChangeRegressionWindow,
    DriftObservation,
    ErrorRateWindow,
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)

_DISK_CAPACITY = 100.0
_BASELINE_SIGNATURES = frozenset({"E1", "E2"})
_PREVIOUS_REVISION = "a" * 64
_DEPLOYED_REVISION = "b" * 64
_DEPLOYED_AT = 1100
_DRIFT_POLICY_REVISION = "c" * 64
_DRIFT_DESIRED_REVISION = "b" * 64
_DRIFT_OBSERVED_REVISION = "a" * 64


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


def _error_rate_timeline(
    current_errors: tuple[int, ...],
    *,
    baseline_errors: int = 1,
    baseline_requests: int = 1000,
    current_requests: int = 1000,
    allowed_error_rate: float = 0.001,
) -> tuple[SentinelState, ...]:
    return tuple(
        SentinelState(
            error_rate_windows=(
                ErrorRateWindow(
                    service="payments",
                    baseline_errors=baseline_errors,
                    baseline_requests=baseline_requests,
                    current_errors=errors,
                    current_requests=current_requests,
                    allowed_error_rate=allowed_error_rate,
                ),
            )
        )
        for errors in current_errors
    )


def _change_regression_timeline(
    current_errors: tuple[int, ...],
    *,
    baseline_errors: int = 1,
    baseline_requests: int = 1000,
    current_requests: int = 1000,
    allowed_error_rate: float = 0.001,
    first_observation_age: int = 300,
    intervening_deployments: int = 0,
) -> tuple[SentinelState, ...]:
    return tuple(
        SentinelState(
            change_regression_windows=(
                ChangeRegressionWindow(
                    service="payments",
                    previous_revision=_PREVIOUS_REVISION,
                    deployed_revision=_DEPLOYED_REVISION,
                    baseline_ended_at=_DEPLOYED_AT - 100,
                    deployed_at=_DEPLOYED_AT,
                    current_started_at=_DEPLOYED_AT,
                    observed_at=_DEPLOYED_AT + first_observation_age + index * 300,
                    intervening_deployments=intervening_deployments,
                    baseline_errors=baseline_errors,
                    baseline_requests=baseline_requests,
                    current_errors=errors,
                    current_requests=current_requests,
                    allowed_error_rate=allowed_error_rate,
                ),
            )
        )
        for index, errors in enumerate(current_errors)
    )


def _drift_state(
    *,
    desired_revision: str = _DRIFT_DESIRED_REVISION,
    observed_revision: str | None = _DRIFT_OBSERVED_REVISION,
    desired_recorded_at: int = 1200,
    mismatch_started_at: int | None = 1200,
    observed_at: int = 1200,
    consecutive_mismatches: int = 1,
) -> SentinelState:
    return SentinelState(
        drift_observations=(
            DriftObservation(
                resource_kind="deployment",
                resource_id="prod-eu-1/payments",
                tracking_policy_revision=_DRIFT_POLICY_REVISION,
                desired_revision=desired_revision,
                observed_revision=observed_revision,
                desired_recorded_at=desired_recorded_at,
                mismatch_started_at=mismatch_started_at,
                observed_at=observed_at,
                consecutive_mismatches=consecutive_mismatches,
            ),
        )
    )


def _drift_incident_timeline() -> tuple[SentinelState, ...]:
    return (
        _drift_state(
            desired_revision=_DRIFT_OBSERVED_REVISION,
            observed_revision=_DRIFT_OBSERVED_REVISION,
            desired_recorded_at=1000,
            mismatch_started_at=None,
            observed_at=1100,
            consecutive_mismatches=0,
        ),
        _drift_state(observed_at=1200, consecutive_mismatches=1),
        _drift_state(observed_at=1500, consecutive_mismatches=2),
        _drift_state(observed_at=1800, consecutive_mismatches=3),
        _drift_state(observed_at=2100, consecutive_mismatches=4),
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
        # Baseline=0.1%, SLO budget=0.1%. The complete threshold is 1.1%;
        # current reaches 1.2% at index 2 and pages at 6% on index 4.
        LeadTimeScenario(
            id="error-rate-regression-before-page",
            timeline=_error_rate_timeline((1, 2, 12, 25, 60)),
            paged_at_index=4,
            expected_detector_id="error_rate_vs_baseline",
            expected_kind="error_rate_regression",
        ),
        # The same aggregate ramp is now bound to one exact recent deployment;
        # it crosses at index 2 and therefore leads the page by two snapshots.
        LeadTimeScenario(
            id="change-induced-regression-before-page",
            timeline=_change_regression_timeline((1, 2, 12, 25, 60)),
            paged_at_index=4,
            expected_detector_id="change_induced_regression",
            expected_kind="change_induced_regression",
        ),
        # Desired revision changes at index 1. The second observation at index 2
        # reaches the five-minute persistence boundary, two snapshots before page.
        LeadTimeScenario(
            id="config-state-drift-before-page",
            timeline=_drift_incident_timeline(),
            paged_at_index=4,
            expected_detector_id="config_state_drift",
            expected_kind="config_state_drift",
        ),
        # Healthy disk throughout — no incident; the detectors must stay silent
        # (false-positive control).
        LeadTimeScenario(
            id="clean-no-incident",
            timeline=_disk_timeline((30.0, 35.0, 40.0)),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        # A high but stable 3% rolling baseline is not a global fixed threshold:
        # current 3.0→3.5% remains far below the relative 9% threshold.
        LeadTimeScenario(
            id="clean-error-rate-stable-high-baseline",
            timeline=_error_rate_timeline(
                (30, 32, 35),
                baseline_errors=30,
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        # One error in twenty requests is a noisy 5% rate, but the current
        # window is below the exact 100-request sufficiency floor.
        LeadTimeScenario(
            id="clean-error-rate-low-volume-spike",
            timeline=_error_rate_timeline(
                (0, 1, 1),
                baseline_errors=0,
                current_requests=20,
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        # With a declared 1% budget, current 0.5→1.5% stays below the 2%
        # SLO-budget multiplier even though it is above a near-zero baseline.
        LeadTimeScenario(
            id="clean-error-rate-inside-slo-budget",
            timeline=_error_rate_timeline(
                (5, 10, 15),
                baseline_errors=0,
                allowed_error_rate=0.01,
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        LeadTimeScenario(
            id="clean-change-regression-stable-high-baseline",
            timeline=_change_regression_timeline(
                (30, 32, 35),
                baseline_errors=30,
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        LeadTimeScenario(
            id="clean-change-regression-low-volume-spike",
            timeline=_change_regression_timeline(
                (0, 1, 1),
                baseline_errors=0,
                current_requests=20,
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        LeadTimeScenario(
            id="clean-change-regression-inside-slo-budget",
            timeline=_change_regression_timeline(
                (5, 10, 15),
                baseline_errors=0,
                allowed_error_rate=0.01,
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        LeadTimeScenario(
            id="clean-change-regression-expired-association",
            timeline=_change_regression_timeline(
                (12, 25, 60),
                first_observation_age=3601,
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        LeadTimeScenario(
            id="clean-change-regression-intervening-deploy",
            timeline=_change_regression_timeline(
                (12, 25, 60),
                intervening_deployments=1,
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        LeadTimeScenario(
            id="clean-drift-converged",
            timeline=(
                _drift_state(
                    observed_revision=_DRIFT_DESIRED_REVISION,
                    mismatch_started_at=None,
                    consecutive_mismatches=0,
                    observed_at=1500,
                ),
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        LeadTimeScenario(
            id="clean-drift-single-observation",
            timeline=(_drift_state(observed_at=1500, consecutive_mismatches=1),),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        LeadTimeScenario(
            id="clean-drift-inside-grace",
            timeline=(
                _drift_state(observed_at=1200, consecutive_mismatches=1),
                _drift_state(observed_at=1499, consecutive_mismatches=2),
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        LeadTimeScenario(
            id="clean-drift-missing-inside-grace",
            timeline=(
                _drift_state(
                    observed_revision=None,
                    observed_at=1200,
                    consecutive_mismatches=1,
                ),
                _drift_state(
                    observed_revision=None,
                    observed_at=1499,
                    consecutive_mismatches=2,
                ),
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
        LeadTimeScenario(
            id="clean-drift-desired-revision-reset",
            timeline=(
                _drift_state(observed_at=1200, consecutive_mismatches=1),
                _drift_state(
                    desired_revision="d" * 64,
                    desired_recorded_at=1400,
                    mismatch_started_at=1400,
                    observed_at=1400,
                    consecutive_mismatches=1,
                ),
                _drift_state(
                    desired_revision="d" * 64,
                    desired_recorded_at=1400,
                    mismatch_started_at=1400,
                    observed_at=1699,
                    consecutive_mismatches=2,
                ),
            ),
            paged_at_index=None,
            expected_detector_id=None,
        ),
    )


__all__ = ["load_lead_time_scenarios"]
