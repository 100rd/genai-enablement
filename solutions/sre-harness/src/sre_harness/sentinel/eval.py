"""Lead-time eval for Sentinel detectors (Stage 7 — build-order step 1).

The ADR's measurement contract: "Sentinel detectors are scored by the eval
harness on **lead-time** — replay past incidents and verify a detector would have
surfaced the problem *earlier*, with low false-positive rate on the messy worlds."

A :class:`LeadTimeScenario` is an ordered *timeline* of :class:`SentinelState`
snapshots (e.g. hourly), plus the snapshot index at which the incident actually
paged and which detector should have caught it first. :func:`run_sentinel_eval`
replays each timeline through :func:`~sre_harness.sentinel.scan.run_sentinel`,
finds the earliest snapshot the expected detector fires, and scores the gap with
:func:`~sre_harness.eval.score.lead_time`. A *clean* timeline (``paged_at_index is
None``) is the false-positive control: the detector must stay silent.

Pure, offline, deterministic — the Sentinel analogue of the gate's Pass@1 eval.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sre_harness.eval.score import Score, lead_time
from sre_harness.sentinel.detectors import DEFAULT_DETECTORS
from sre_harness.sentinel.finding import Detector, Finding
from sre_harness.sentinel.scan import run_sentinel
from sre_harness.sentinel.state import SentinelState

#: Default snapshots-of-lead treated as a full lead-time score.
DEFAULT_LEAD_TIME_HORIZON = 6


@dataclass(frozen=True)
class LeadTimeScenario:
    """One replayable lead-time label: a timeline plus what should fire, when.

    - ``timeline``            : ordered state snapshots (index 0 = earliest).
    - ``paged_at_index``      : snapshot at which the incident paged; ``None`` for
      a clean timeline (the detector must stay silent).
    - ``expected_detector_id``: the ``Finding.detector_id`` expected to fire;
      ``None`` on a clean timeline.
    - ``expected_kind``       : optionally narrow the match to one finding kind.
    - ``horizon``             : lead normalisation (snapshots for a full score).
    """

    id: str
    timeline: tuple[SentinelState, ...]
    paged_at_index: int | None
    expected_detector_id: str | None
    expected_kind: str | None = None
    horizon: int = DEFAULT_LEAD_TIME_HORIZON

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("scenario id must not be blank")
        if not self.timeline:
            raise ValueError("scenario timeline must not be empty")


@dataclass(frozen=True)
class LeadTimeResult:
    """The outcome of replaying and scoring one lead-time scenario."""

    scenario_id: str
    paged_at_index: int | None
    first_fire_index: int | None
    score: Score

    @property
    def lead(self) -> int | None:
        """Snapshots of warning the detector gave, or ``None`` if it did not."""
        if self.paged_at_index is None or self.first_fire_index is None:
            return None
        return self.paged_at_index - self.first_fire_index


@dataclass(frozen=True)
class SentinelEvalSummary:
    """Aggregate view: pass rate + mean lead-time over the scenarios that fired."""

    results: tuple[LeadTimeResult, ...]
    total: int
    passed: int
    pass_rate: float
    mean_lead_time: float


def run_sentinel_eval(
    scenarios: Sequence[LeadTimeScenario],
    detectors: Sequence[Detector] = DEFAULT_DETECTORS,
) -> SentinelEvalSummary:
    """Replay every timeline, score lead-time, and aggregate."""
    if not scenarios:
        raise ValueError("run_sentinel_eval requires at least one scenario")

    results = tuple(_evaluate_one(scenario, detectors) for scenario in scenarios)
    passed = sum(1 for result in results if result.score.passed)
    total = len(results)
    leads = [result.lead for result in results if result.lead is not None and result.lead > 0]
    mean_lead = sum(leads) / len(leads) if leads else 0.0

    return SentinelEvalSummary(
        results=results,
        total=total,
        passed=passed,
        pass_rate=passed / total,
        mean_lead_time=mean_lead,
    )


def _evaluate_one(scenario: LeadTimeScenario, detectors: Sequence[Detector]) -> LeadTimeResult:
    first_fire = _first_fire_index(scenario, detectors)
    score = lead_time(
        paged_at_index=scenario.paged_at_index,
        first_fire_index=first_fire,
        horizon=scenario.horizon,
    )
    return LeadTimeResult(
        scenario_id=scenario.id,
        paged_at_index=scenario.paged_at_index,
        first_fire_index=first_fire,
        score=score,
    )


def _first_fire_index(scenario: LeadTimeScenario, detectors: Sequence[Detector]) -> int | None:
    """Earliest snapshot at which a matching finding appears, else ``None``.

    Each snapshot is scanned independently (no cross-snapshot dedup): we are
    measuring *when the detector would first surface the problem*, which is a
    detection-time question, not a re-alert one.
    """
    for index, state in enumerate(scenario.timeline):
        report = run_sentinel(state, detectors=detectors)
        if any(_matches(finding, scenario) for finding in report.findings):
            return index
    return None


def _matches(finding: Finding, scenario: LeadTimeScenario) -> bool:
    # Clean timeline (no expected detector): *any* finding is a false positive,
    # so it counts as a fire — the scenario then fails the silence check.
    if scenario.expected_detector_id is None:
        return True
    if finding.detector_id != scenario.expected_detector_id:
        return False
    return scenario.expected_kind is None or finding.kind == scenario.expected_kind


__all__ = [
    "DEFAULT_LEAD_TIME_HORIZON",
    "LeadTimeResult",
    "LeadTimeScenario",
    "SentinelEvalSummary",
    "run_sentinel_eval",
]
