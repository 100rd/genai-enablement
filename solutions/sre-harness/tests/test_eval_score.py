"""Unit tests for the scorer.

Pass@1 (verdict-correctness) is the only scorer implemented now. The other
score kinds (Pass@k, trajectory, depth, signal-surfacing) are declared on the
``ScoreKind`` enum and the ``Score`` type so callers can extend cleanly, but
their scorers are explicit ``NotImplementedError`` stubs — they never fabricate
numbers.
"""

import dataclasses

import pytest

from sre_harness.change_gate import Verdict
from sre_harness.eval import (
    Score,
    ScoreKind,
    pass_at_1,
    score_not_implemented,
)


@pytest.mark.unit
class TestPassAt1:
    def test_correct_verdict_scores_one(self) -> None:
        score = pass_at_1(expected=Verdict.BLOCK, actual=Verdict.BLOCK)
        assert isinstance(score, Score)
        assert score.kind is ScoreKind.PASS_AT_1
        assert score.value == 1.0
        assert score.passed is True

    def test_wrong_verdict_scores_zero(self) -> None:
        score = pass_at_1(expected=Verdict.BLOCK, actual=Verdict.PROCEED)
        assert score.value == 0.0
        assert score.passed is False

    def test_score_is_frozen(self) -> None:
        score = pass_at_1(expected=Verdict.PROCEED, actual=Verdict.PROCEED)
        with pytest.raises(dataclasses.FrozenInstanceError):
            score.value = 0.0  # type: ignore[misc]


@pytest.mark.unit
class TestScoreValueBounds:
    def test_value_must_be_in_unit_interval(self) -> None:
        with pytest.raises(ValueError):
            Score(kind=ScoreKind.PASS_AT_1, value=1.5, passed=True)


@pytest.mark.unit
class TestExtensionStubs:
    @pytest.mark.parametrize(
        "kind",
        [
            ScoreKind.PASS_AT_K,
            ScoreKind.TRAJECTORY,
            ScoreKind.DEPTH,
            ScoreKind.SIGNAL_SURFACING,
        ],
    )
    def test_unimplemented_scorers_raise(self, kind: ScoreKind) -> None:
        with pytest.raises(NotImplementedError):
            score_not_implemented(kind)
