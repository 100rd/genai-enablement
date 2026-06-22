"""Run the seed eval suite and print a summary.

    python -m sre_harness.eval

No external dependencies — argparse only, with a single ``--verbose`` flag to
also print the per-scenario verdicts. Exit code is non-zero when any scenario
fails so the suite can gate CI later.
"""

from __future__ import annotations

import argparse
import sys

from sre_harness.eval.runner import EvalSummary, change_gate_target, run_eval
from sre_harness.eval.scenarios import load_seed_scenarios


def _format_summary(summary: EvalSummary, *, verbose: bool) -> str:
    lines = [
        "Offline eval harness — seed suite (Pass@1, change-validation gate)",
        "=" * 66,
    ]
    if verbose:
        for result in summary.results:
            mark = "PASS" if result.score.passed else "FAIL"
            lines.append(
                f"  [{mark}] {result.scenario_id}: "
                f"expected={result.expected.value} actual={result.actual.value}"
            )
        lines.append("-" * 66)
    for kind, rate in sorted(summary.pass_rate_by_kind.items(), key=lambda kv: kv[0].value):
        lines.append(f"  {kind.value:<14} pass rate: {rate:6.1%}")
    lines.append("-" * 66)
    lines.append(
        f"  TOTAL          {summary.passed}/{summary.total} passed "
        f"(pass rate {summary.pass_rate:.1%})"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the seed suite; return 0 if every scenario passes, else 1."""
    parser = argparse.ArgumentParser(prog="sre_harness.eval")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print per-scenario verdicts",
    )
    args = parser.parse_args(argv)

    summary = run_eval(load_seed_scenarios(), change_gate_target)
    print(_format_summary(summary, verbose=args.verbose))
    return 0 if summary.passed == summary.total else 1


if __name__ == "__main__":
    sys.exit(main())
