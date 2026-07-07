"""Unit tests for the Sentinel scan: dedup, ranking, advisory tiers."""

from __future__ import annotations

from sre_harness.autonomy_tiers import Tier
from sre_harness.sentinel.finding import Finding, Severity
from sre_harness.sentinel.scan import run_sentinel
from sre_harness.sentinel.state import (
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)


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
