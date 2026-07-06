"""``sre-harness sentinel scan`` — Stage 7 build-order step 2.

Makes one Sentinel scan runnable from the command line (and, per the ADR's
step 2, from a periodic ``CronJob``): load a :class:`SentinelState` snapshot
(``--state``), optionally load+persist an open-findings set
(``--open-findings``) so repeat scans dedupe against history, run
:func:`~sre_harness.sentinel.scan.run_sentinel`, and print the report as JSON.

**Sentinel is advisory, never a gate.** Detection is Tier 1 (read-only);
emitting a finding is Tier 2 (advisory) — this command never executes
anything, and its exit code is informational, not a pass/fail signal for a
pipeline:

    0  no fresh findings   — nothing new since the last scan
    1  fresh findings      — new findings this scan (act on the JSON output)
    2  usage error         — bad args, missing/invalid input

A CronJob wiring this command must NOT fail the job on exit 1 (see
``integrations/sentinel-cronjob.yaml``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sre_harness.sentinel.finding import Finding
from sre_harness.sentinel.scan import SentinelReport, run_sentinel
from sre_harness.sentinel.serialization import finding_to_dict
from sre_harness.sentinel.source import JsonFileStateSource
from sre_harness.sentinel.state import SentinelState
from sre_harness.sentinel.store import FindingStore, JsonFileFindingStore

EXIT_NO_FRESH_FINDINGS = 0
EXIT_FRESH_FINDINGS = 1
EXIT_USAGE = 2


class _SentinelCliError(Exception):
    """A user-facing error: bad arguments or invalid input."""


def add_subparser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``sentinel`` (and its ``scan`` subcommand) on the top-level parser."""
    sentinel_help = "Sentinel continuous-detection commands (Stage 7)."
    sentinel = sub.add_parser("sentinel", help=sentinel_help, description=sentinel_help)
    sentinel_sub = sentinel.add_subparsers(dest="sentinel_command")

    scan_help = "Run one Sentinel scan over a state snapshot (advisory, never a gate)."
    scan = sentinel_sub.add_parser("scan", help=scan_help, description=scan_help)
    scan.add_argument(
        "--state",
        required=True,
        help="Path to the SentinelState JSON snapshot.",
    )
    scan.add_argument(
        "--open-findings",
        help=(
            "Path to the open-findings JSON file. Read at the start of the scan and "
            "overwritten at the end with the fresh+suppressed union so the next scan "
            "can dedupe against it. Omit for a stateless, one-off run."
        ),
    )
    scan.add_argument(
        "--verbose",
        action="store_true",
        help="Also include suppressed (already-open) findings in the output.",
    )


def dispatch(args: argparse.Namespace) -> int:
    """Entry point for the ``sentinel`` command family. Returns a process exit code."""
    if getattr(args, "sentinel_command", None) != "scan":
        print("sre-harness: error: sentinel requires a subcommand (scan)", file=sys.stderr)
        return EXIT_USAGE
    return _run_scan(args)


def _run_scan(args: argparse.Namespace) -> int:
    try:
        state = _load_state(Path(args.state))
        store = _open_finding_store(args.open_findings)
        open_findings = _load_open_findings(store)
    except _SentinelCliError as exc:
        print(f"sre-harness: error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    report = run_sentinel(state, open_findings=open_findings)
    if store is not None:
        store.save_open((*report.findings, *report.suppressed))

    print(json.dumps(_render(report, verbose=args.verbose), indent=2, sort_keys=True))
    return EXIT_FRESH_FINDINGS if report.findings else EXIT_NO_FRESH_FINDINGS


# --- loading ------------------------------------------------------------


def _load_state(path: Path) -> SentinelState:
    try:
        return JsonFileStateSource(path).snapshot()
    except ValueError as exc:
        raise _SentinelCliError(str(exc)) from exc


def _open_finding_store(path_str: str | None) -> FindingStore | None:
    return JsonFileFindingStore(Path(path_str)) if path_str is not None else None


def _load_open_findings(store: FindingStore | None) -> tuple[Finding, ...]:
    if store is None:
        return ()
    try:
        return store.load_open()
    except ValueError as exc:
        raise _SentinelCliError(str(exc)) from exc


# --- rendering ------------------------------------------------------------


def _render(report: SentinelReport, *, verbose: bool) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "detection_tier": report.detection_tier.name,
        "recommendation_tier": report.recommendation_tier.name,
        "advisory": True,
        "finding_count": len(report.findings),
        "findings": [_render_finding(finding) for finding in report.findings],
    }
    if verbose:
        doc["suppressed_count"] = len(report.suppressed)
        doc["suppressed"] = [_render_finding(finding) for finding in report.suppressed]
    return doc


def _render_finding(finding: Finding) -> dict[str, Any]:
    payload = finding_to_dict(finding)
    payload["rank"] = finding.rank
    payload["dedup_key"] = finding.dedup_key
    return payload


__all__ = [
    "EXIT_FRESH_FINDINGS",
    "EXIT_NO_FRESH_FINDINGS",
    "EXIT_USAGE",
    "add_subparser",
    "dispatch",
]
