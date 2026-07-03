"""Scoring for the offline eval harness.

What is scored *now*: **Pass@1** — did the target produce the correct verdict on
its single attempt (:func:`pass_at_1`)? — and **lead-time** — how early did a
Sentinel detector surface a problem before it paged (:func:`lead_time`, Stage 7,
ADR-0001)? Both are honest measures against the deterministic surfaces they score.

Extension surface (declared, not faked): the plan calls for ``Pass@k`` /
trajectory / depth / signal-surfacing scoring once there is a stochastic,
multi-step agent target to measure (Stage 1+). Those kinds are enumerated on
:class:`ScoreKind` and share the :class:`Score` shape, but their scorers are not
implemented — :func:`score_not_implemented` raises rather than fabricate a
number. Replace it with real scorers when the trajectory/sample data exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sre_harness.change_gate import Verdict


class ScoreKind(Enum):
    """The metric a :class:`Score` represents.

    ``PASS_AT_1`` and ``LEAD_TIME`` are implemented. The rest are the documented
    extension points for richer agent evaluation; see
    :func:`score_not_implemented`.
    """

    PASS_AT_1 = "pass_at_1"
    LEAD_TIME = "lead_time"
    PASS_AT_K = "pass_at_k"
    TRAJECTORY = "trajectory"
    DEPTH = "depth"
    SIGNAL_SURFACING = "signal_surfacing"


@dataclass(frozen=True)
class Score:
    """A single metric outcome in the unit interval.

    ``value`` is normalised to ``[0.0, 1.0]`` so heterogeneous metrics aggregate
    uniformly; ``passed`` is the boolean view used for Pass-rate roll-ups.
    """

    kind: ScoreKind
    value: float
    passed: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"score value must be in [0.0, 1.0], got {self.value}")


def pass_at_1(*, expected: Verdict, actual: Verdict) -> Score:
    """Score a single-attempt verdict: 1.0 iff ``actual`` matches ``expected``."""
    correct = actual is expected
    return Score(
        kind=ScoreKind.PASS_AT_1,
        value=1.0 if correct else 0.0,
        passed=correct,
    )


def lead_time(
    *,
    paged_at_index: int | None,
    first_fire_index: int | None,
    horizon: int,
) -> Score:
    """Score how early a Sentinel detector surfaced a problem before it paged.

    Replaying a timeline of state snapshots, ``first_fire_index`` is the earliest
    snapshot at which the detector fired (or ``None`` if it never did) and
    ``paged_at_index`` is the snapshot at which the incident actually paged
    (``None`` for a *clean* timeline with no incident).

    - **Clean timeline** (``paged_at_index is None``): a false-positive check —
      pass iff the detector stayed silent (``first_fire_index is None``).
    - **Incident timeline**: reward firing *strictly before* the page. The lead is
      ``paged_at_index - first_fire_index`` snapshots, normalised to ``[0, 1]`` by
      ``horizon``. Never firing, or firing only at/after the page, scores 0.0.

    ``horizon`` (> 0) is the number of snapshots of lead treated as a full score.
    """
    if horizon <= 0:
        raise ValueError(f"horizon must be > 0, got {horizon}")

    if paged_at_index is None:
        fired = first_fire_index is not None
        return Score(kind=ScoreKind.LEAD_TIME, value=0.0 if fired else 1.0, passed=not fired)

    if first_fire_index is None or first_fire_index >= paged_at_index:
        return Score(kind=ScoreKind.LEAD_TIME, value=0.0, passed=False)

    lead = paged_at_index - first_fire_index
    return Score(kind=ScoreKind.LEAD_TIME, value=min(lead / horizon, 1.0), passed=True)


def score_not_implemented(kind: ScoreKind) -> Score:
    """Extension-point stub for the not-yet-implemented score kinds.

    Raises rather than returning a placeholder so the harness never reports a
    fabricated number. Wire a real scorer here (per ``kind``) when there is a
    stochastic, multi-step target and trajectory/sample data to score against.
    """
    raise NotImplementedError(
        f"scorer for {kind.value!r} is not implemented yet; "
        "Pass@1 is the only scored metric while the target is the deterministic gate"
    )


__all__ = [
    "Score",
    "ScoreKind",
    "lead_time",
    "pass_at_1",
    "score_not_implemented",
]
