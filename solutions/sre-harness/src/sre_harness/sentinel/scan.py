"""Sentinel scan — run the detector registry, dedupe, rank, emit an advisory report.

The continuous-detection counterpart to :func:`sre_harness.change_gate.evaluate_change`.
:func:`run_sentinel` runs a registered list of pure detectors over a state
snapshot and:

1. **collapses** duplicate findings within the scan (same ``dedup_key`` → keep the
   higher-ranked),
2. **dedupes** against the caller's already-open findings (the ADR's "never
   re-alert a known/open finding"), and
3. **ranks** the survivors most-urgent-first by ``severity × confidence``.

Detection is read-only (**T1**); emitting the findings is advisory (**T2**) — the
scan never executes anything, exactly like the gate. Instrumented (AgentOps) with
a ``sentinel.scan`` span and one child ``sentinel.detector`` span per detector;
tracing is no-op by default.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sre_harness.autonomy_tiers import Tier
from sre_harness.observability import attributes as attrs
from sre_harness.observability import set_attributes, span
from sre_harness.sentinel.detectors import DEFAULT_DETECTORS
from sre_harness.sentinel.finding import Detector, Finding
from sre_harness.sentinel.state import SentinelState

# Detection is T1 (read-only); emitting a finding/recommendation is T2 (advisory).
_DETECTION_TIER = Tier.T1
_RECOMMENDATION_TIER = Tier.T2


@dataclass(frozen=True)
class SentinelReport:
    """A scan's advisory output: fresh findings, plus what was suppressed.

    ``findings`` are deduped against the open set and ranked most-urgent-first;
    ``suppressed`` are the findings dropped because they matched an already-open
    finding (kept for auditability — "we saw it, we did not re-alert").
    """

    findings: tuple[Finding, ...]
    suppressed: tuple[Finding, ...]
    detection_tier: Tier = _DETECTION_TIER
    recommendation_tier: Tier = _RECOMMENDATION_TIER


def run_sentinel(
    state: SentinelState,
    detectors: Sequence[Detector] = DEFAULT_DETECTORS,
    open_findings: Sequence[Finding] = (),
) -> SentinelReport:
    """Run every detector over ``state``; dedupe against ``open_findings``; rank.

    Pure and deterministic: the only side effect is the (no-op-by-default) spans.
    """
    open_keys = {finding.dedup_key for finding in open_findings}

    with span(
        "sentinel.scan",
        {
            attrs.SENTINEL_DETECTOR_COUNT: len(detectors),
            attrs.SENTINEL_DETECTION_TIER: _DETECTION_TIER.name,
            attrs.SENTINEL_RECOMMENDATION_TIER: _RECOMMENDATION_TIER.name,
        },
        service="sre-harness",
    ) as scan_span:
        produced = _collapse_by_key(_run_all(detectors, state))
        fresh = [finding for finding in produced if finding.dedup_key not in open_keys]
        suppressed = [finding for finding in produced if finding.dedup_key in open_keys]
        ranked = _rank(fresh)
        ranked_suppressed = _rank(suppressed)
        set_attributes(
            scan_span,
            {
                attrs.SENTINEL_FINDING_COUNT: len(ranked),
                attrs.SENTINEL_SUPPRESSED_COUNT: len(ranked_suppressed),
            },
        )

    return SentinelReport(findings=ranked, suppressed=ranked_suppressed)


def _run_all(detectors: Sequence[Detector], state: SentinelState) -> list[Finding]:
    """Run each detector inside a child ``sentinel.detector`` span (AgentOps)."""
    out: list[Finding] = []
    for detector in detectors:
        with span("sentinel.detector") as detector_span:
            found = list(detector(state))
            set_attributes(
                detector_span,
                {
                    attrs.SENTINEL_DETECTOR_ID: getattr(detector, "__name__", repr(detector)),
                    attrs.SENTINEL_DETECTOR_FINDING_COUNT: len(found),
                },
            )
            out.extend(found)
    return out


def _collapse_by_key(findings: Sequence[Finding]) -> list[Finding]:
    """Collapse same-``dedup_key`` findings within one scan, keeping the higher rank."""
    best: dict[str, Finding] = {}
    for finding in findings:
        incumbent = best.get(finding.dedup_key)
        if incumbent is None or finding.rank > incumbent.rank:
            best[finding.dedup_key] = finding
    return list(best.values())


def _rank(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    """Order most-urgent-first by ``severity × confidence``; ``dedup_key`` breaks ties."""
    return tuple(sorted(findings, key=lambda finding: (-finding.rank, finding.dedup_key)))


__all__ = [
    "SentinelReport",
    "run_sentinel",
]
