"""Run the seed Sentinel lead-time eval and print a summary.

    python -m sre_harness.sentinel

No external dependencies — argparse only, with a single ``--verbose`` flag to
also print the per-scenario lead-time. Exit code is non-zero when any scenario
fails (a detector fired too late, or a false positive on a clean timeline) so the
suite can gate CI later.
"""

from __future__ import annotations

import argparse
import sys

from sre_harness.sentinel.eval import SentinelEvalSummary, run_sentinel_eval
from sre_harness.sentinel.scenarios import load_lead_time_scenarios


def _format_summary(summary: SentinelEvalSummary, *, verbose: bool) -> str:
    lines = [
        "Sentinel lead-time eval — seed suite (offline, deterministic)",
        "=" * 62,
    ]
    if verbose:
        for result in summary.results:
            mark = "PASS" if result.score.passed else "FAIL"
            lead = "silent" if result.lead is None else f"lead={result.lead} snapshot(s)"
            lines.append(
                f"  [{mark}] {result.scenario_id}: {lead} (score {result.score.value:.2f})"
            )
        lines.append("-" * 62)
    lines.append(f"  mean lead-time (fired scenarios): {summary.mean_lead_time:.2f} snapshot(s)")
    lines.append(
        f"  early detection  {summary.early_detections}/{summary.incident_scenarios} "
        f"({summary.early_detection_rate:.1%})"
    )
    lines.append(
        f"  false positives {summary.false_positives}/{summary.clean_scenarios} "
        f"({summary.false_positive_rate:.1%})"
    )
    lines.append(
        f"  TOTAL          {summary.passed}/{summary.total} passed "
        f"(pass rate {summary.pass_rate:.1%})"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the seed lead-time suite; return 0 iff every scenario passes."""
    parser = argparse.ArgumentParser(prog="sre_harness.sentinel")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print per-scenario lead-time",
    )
    args = parser.parse_args(argv)

    summary = run_sentinel_eval(load_lead_time_scenarios())
    print(_format_summary(summary, verbose=args.verbose))
    return 0 if summary.passed == summary.total else 1


if __name__ == "__main__":
    sys.exit(main())
