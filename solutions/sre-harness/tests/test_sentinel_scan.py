"""Unit tests for the Sentinel scan: dedup, ranking, advisory tiers."""

from __future__ import annotations

from sre_harness.autonomy_tiers import Tier
from sre_harness.sentinel.finding import Finding, Severity
from sre_harness.sentinel.scan import run_sentinel
from sre_harness.sentinel.state import (
    ChangeRegressionWindow,
    ErrorRateWindow,
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)

_PREVIOUS_REVISION = "a" * 64
_DEPLOYED_REVISION = "b" * 64


def _busy_state() -> SentinelState:
    """A state that trips all three finding classes at different ranks."""
    return SentinelState(
        saturation_samples=(
            SaturationSample(resource="pvc", kind="disk", used=95.0, capacity=100.0),  # CRITICAL
            SaturationSample(
                resource="pool",
                kind="connections",
                used=60.0,
                capacity=100.0,
                growth_per_interval=8.0,
            ),  # HIGH x0.7
        ),
        expiry_items=(ExpiryItem(name="api-tls", kind="cert", expires_in_days=3),),  # HIGH
        error_windows=(
            ErrorSignatureWindow(
                service="payments", baseline=frozenset({"E1"}), current=frozenset({"E1", "E_NEW"})
            ),  # HIGH
        ),
    )


def test_empty_state_produces_empty_report_with_advisory_tiers() -> None:
    report = run_sentinel(SentinelState())

    assert report.findings == ()
    assert report.suppressed == ()
    assert report.detection_tier is Tier.T1
    assert report.recommendation_tier is Tier.T2


def test_findings_are_ranked_most_urgent_first() -> None:
    report = run_sentinel(_busy_state())

    ranks = [finding.rank for finding in report.findings]
    assert ranks == sorted(ranks, reverse=True)
    assert report.findings[0].severity is Severity.CRITICAL


def test_open_finding_is_suppressed_not_re_alerted() -> None:
    first = run_sentinel(_busy_state())
    top = first.findings[0]

    second = run_sentinel(_busy_state(), open_findings=[top])

    fresh_keys = {finding.dedup_key for finding in second.findings}
    assert top.dedup_key not in fresh_keys
    assert [s.dedup_key for s in second.suppressed] == [top.dedup_key]
    assert len(second.findings) == len(first.findings) - 1


def test_unrelated_open_finding_does_not_suppress_anything() -> None:
    unrelated = Finding(
        detector_id="saturation_expiry",
        kind="saturation",
        severity=Severity.LOW,
        confidence=1.0,
        fingerprint="some/other-resource",
        rationale="unrelated",
    )

    report = run_sentinel(_busy_state(), open_findings=[unrelated])

    assert report.suppressed == ()
    assert len(report.findings) == 4


def test_within_scan_duplicate_keys_collapse_to_higher_rank() -> None:
    low = Finding(
        detector_id="d",
        kind="k",
        severity=Severity.LOW,
        confidence=1.0,
        fingerprint="x",
        rationale="lo",
    )
    high = Finding(
        detector_id="d",
        kind="k",
        severity=Severity.CRITICAL,
        confidence=1.0,
        fingerprint="x",
        rationale="hi",
    )

    def duplicating_detector(_: SentinelState) -> list[Finding]:
        return [low, high]

    report = run_sentinel(SentinelState(), detectors=(duplicating_detector,))

    assert len(report.findings) == 1
    assert report.findings[0].severity is Severity.CRITICAL


def test_custom_detector_list_is_respected() -> None:
    def silent_detector(_: SentinelState) -> list[Finding]:
        return []

    report = run_sentinel(_busy_state(), detectors=(silent_detector,))

    assert report.findings == ()


def test_suppressed_findings_are_ranked() -> None:
    first = run_sentinel(_busy_state())
    # Re-open every finding: all become suppressed on the next scan.
    second = run_sentinel(_busy_state(), open_findings=list(first.findings))

    assert second.findings == ()
    suppressed_ranks = [finding.rank for finding in second.suppressed]
    assert suppressed_ranks == sorted(suppressed_ranks, reverse=True)


def _qualifying_error_rate(service: str = "payments") -> ErrorRateWindow:
    return ErrorRateWindow(
        service=service,
        baseline_errors=1,
        baseline_requests=1000,
        current_errors=12,
        current_requests=1000,
        allowed_error_rate=0.001,
    )


def _qualifying_change(**overrides: object) -> ChangeRegressionWindow:
    values: dict[str, object] = {
        "service": "payments",
        "previous_revision": _PREVIOUS_REVISION,
        "deployed_revision": _DEPLOYED_REVISION,
        "baseline_ended_at": 1000,
        "deployed_at": 1100,
        "current_started_at": 1100,
        "observed_at": 1400,
        "intervening_deployments": 0,
        "baseline_errors": 1,
        "baseline_requests": 1000,
        "current_errors": 12,
        "current_requests": 1000,
        "allowed_error_rate": 0.001,
    }
    values.update(overrides)
    return ChangeRegressionWindow(**values)  # type: ignore[arg-type]


def test_specific_change_regression_replaces_same_service_generic_finding() -> None:
    report = run_sentinel(
        SentinelState(
            error_rate_windows=(_qualifying_error_rate(),),
            change_regression_windows=(_qualifying_change(),),
        )
    )

    assert [finding.detector_id for finding in report.findings] == ["change_induced_regression"]
    assert report.suppressed == ()


def test_specificity_collapse_keeps_unrelated_service_generic_finding() -> None:
    report = run_sentinel(
        SentinelState(
            error_rate_windows=(
                _qualifying_error_rate(),
                _qualifying_error_rate("orders"),
            ),
            change_regression_windows=(_qualifying_change(),),
        )
    )

    assert {finding.detector_id for finding in report.findings} == {
        "change_induced_regression",
        "error_rate_vs_baseline",
    }
    assert {finding.evidence["service"] for finding in report.findings} == {
        "payments",
        "orders",
    }


def test_silent_change_detector_does_not_hide_qualifying_generic_finding() -> None:
    report = run_sentinel(
        SentinelState(
            error_rate_windows=(_qualifying_error_rate(),),
            change_regression_windows=(_qualifying_change(observed_at=1100 + 3601),),
        )
    )

    assert [finding.detector_id for finding in report.findings] == ["error_rate_vs_baseline"]


def test_open_specific_finding_does_not_resurrect_fresh_generic_duplicate() -> None:
    state = SentinelState(
        error_rate_windows=(_qualifying_error_rate(),),
        change_regression_windows=(_qualifying_change(),),
    )
    first = run_sentinel(state)
    (specific,) = first.findings

    second = run_sentinel(state, open_findings=(specific,))

    assert second.findings == ()
    assert second.suppressed == (specific,)


def test_specificity_collapse_does_not_crash_on_custom_non_string_service() -> None:
    specific = Finding(
        detector_id="change_induced_regression",
        kind="change_induced_regression",
        severity=Severity.HIGH,
        confidence=0.85,
        fingerprint=f"payments:{_DEPLOYED_REVISION}",
        rationale="associated",
        evidence={"service": "payments"},
    )
    malformed_generic = Finding(
        detector_id="error_rate_vs_baseline",
        kind="error_rate_regression",
        severity=Severity.HIGH,
        confidence=0.9,
        fingerprint="custom",
        rationale="custom detector output",
        evidence={"service": ["payments"]},
    )

    def custom_detector(_: SentinelState) -> list[Finding]:
        return [specific, malformed_generic]

    report = run_sentinel(SentinelState(), detectors=(custom_detector,))

    assert [finding.dedup_key for finding in report.findings] == [
        malformed_generic.dedup_key,
        specific.dedup_key,
    ]


def test_specificity_collapse_keeps_same_service_different_finding_kind() -> None:
    specific = Finding(
        detector_id="change_induced_regression",
        kind="change_induced_regression",
        severity=Severity.HIGH,
        confidence=0.85,
        fingerprint=f"payments:{_DEPLOYED_REVISION}",
        rationale="associated",
        evidence={"service": "payments"},
    )
    different_kind = Finding(
        detector_id="error_rate_vs_baseline",
        kind="latency_regression",
        severity=Severity.MEDIUM,
        confidence=0.9,
        fingerprint="payments",
        rationale="different signal",
        evidence={"service": "payments"},
    )

    def custom_detector(_: SentinelState) -> list[Finding]:
        return [specific, different_kind]

    report = run_sentinel(SentinelState(), detectors=(custom_detector,))

    assert {finding.kind for finding in report.findings} == {
        "change_induced_regression",
        "latency_regression",
    }
