"""Offline eval harness — the measurement foundation (plan Stage 0).

Pure, offline, deterministic. The harness replays frozen incident-replay labels
(:class:`Scenario`, shape ``{id, kind, snapshot, ground_truth}``) through a
``target`` callable and scores the outcome. The first wired target replays a
scenario through the deterministic change-validation gate; **Pass@1** verdict
correctness is the only scored metric today. Richer score kinds (Pass@k /
trajectory / depth / signal-surfacing) are declared on :class:`ScoreKind` as the
extension surface — see ``score_not_implemented`` — and are not faked.

See ``docs/autonomous-sre-harness-plan.md`` Stage 0.
"""

from sre_harness.eval.case import GateSnapshot, Scenario, ScenarioKind
from sre_harness.eval.runner import (
    EvalResult,
    EvalSummary,
    Target,
    change_gate_target,
    run_eval,
)
from sre_harness.eval.scenarios import load_seed_scenarios
from sre_harness.eval.score import (
    Score,
    ScoreKind,
    pass_at_1,
    score_not_implemented,
)

__all__ = [
    "EvalResult",
    "EvalSummary",
    "GateSnapshot",
    "Scenario",
    "ScenarioKind",
    "Score",
    "ScoreKind",
    "Target",
    "change_gate_target",
    "load_seed_scenarios",
    "pass_at_1",
    "run_eval",
    "score_not_implemented",
]
