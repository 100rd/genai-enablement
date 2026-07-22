"""``sre-harness`` command-line entry point.

Stage 2 of the plan (``docs/autonomous-sre-harness-plan.md``) makes the
change-validation gate usable *in a pipeline*. The ``gate`` subcommand:

1. loads a change request (structured JSON, or best-effort from a k8s manifest
   / PR diff),
2. loads a :class:`PlatformGraph` from a JSON fixture (the live
   ``OmniscienceMcpPlatformGraph`` adapter plugs in at the same seam later),
3. runs :func:`evaluate_change` (deterministic, no LLM),
4. wraps the verdict through the autonomy-tier engine (analysis T1 / verdict
   T2 — advisory), and
5. prints the verdict + rationale as JSON and exits with a CI-meaningful code.

The gate runs multiple deterministic checks (StorageClass presence, blast-radius
action classification, Namespace presence) and aggregates them; the JSON output
includes the aggregate verdict plus per-check ``check_results``.

Exit codes (so a CI stage can branch on them) derive from the *aggregate*
verdict:

    0  proceed         — every check is satisfied
    1  block           — a check blocked (e.g. required class/namespace absent
                          in every target)
    2  require_human   — a check needs a human (partial coverage, or a
                          high-blast-radius action)

A usage error (bad args, missing/invalid input) also exits ``2`` and writes a
human-readable message to stderr; ``argparse`` itself exits ``2`` on bad CLI
syntax, so this is consistent.

The verdict is **advisory (T2)**: the CLI never executes anything. A controller
or a human acts on the exit code (e.g. an advisory, ``allow_failure`` CI stage,
or an ArgoCD PreSync hook).

``gate-integration`` is the strict SPEC-B2 surface. It accepts one closed,
content-addressed v1 envelope, optionally writes one versioned result artifact,
and uses distinct exits: 0 proceed, 10 block, 20 require-human, 64 invalid input
or result sink. The older ``gate`` command and its 0/1/2 behavior remain for
local compatibility.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sre_harness.advisory_integration import (
    AdvisoryIntegrationError,
    evaluate_change_advisory,
    load_change_advisory_invocation,
    write_change_advisory_result,
)
from sre_harness.autonomy_tiers import TierClassification, classify
from sre_harness.change_checks import CheckResult
from sre_harness.change_gate import (
    ChangeRequest,
    GateResult,
    Verdict,
    evaluate_change,
    parse_change_request,
)
from sre_harness.change_parsers import parse_k8s_manifest, parse_pr_diff
from sre_harness.platform_graph import Entity, InMemoryPlatformGraph, PlatformGraph
from sre_harness.sentinel import cli as sentinel_cli

EXIT_PROCEED = 0
EXIT_BLOCK = 1
EXIT_REQUIRE_HUMAN = 2
EXIT_USAGE = 2
EXIT_INTEGRATION_PROCEED = 0
EXIT_INTEGRATION_BLOCK = 10
EXIT_INTEGRATION_REQUIRE_HUMAN = 20
EXIT_INTEGRATION_INVALID = 64

# The action this gate emits a verdict for; mapped to T2 in the action-tier
# table. Classified at full confidence — the gate's analysis is deterministic.
_VERDICT_ACTION = "change_validation_verdict"
_VERDICT_CONFIDENCE = 1.0

_VERDICT_EXIT = {
    Verdict.PROCEED: EXIT_PROCEED,
    Verdict.BLOCK: EXIT_BLOCK,
    Verdict.REQUIRE_HUMAN: EXIT_REQUIRE_HUMAN,
}

_INTEGRATION_VERDICT_EXIT = {
    Verdict.PROCEED: EXIT_INTEGRATION_PROCEED,
    Verdict.BLOCK: EXIT_INTEGRATION_BLOCK,
    Verdict.REQUIRE_HUMAN: EXIT_INTEGRATION_REQUIRE_HUMAN,
}


class CliError(Exception):
    """A user-facing error: bad arguments or invalid input."""


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code.

    Poetry's console-script convention uses this return value as the process
    exit status, so the CLI never calls ``sys.exit`` itself (except for the
    ``argparse`` usage path, which raises ``SystemExit`` on bad syntax).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "gate":
        return _run_gate(args)
    if args.command == "gate-integration":
        return _run_gate_integration(args)
    if args.command == "sentinel":
        return sentinel_cli.dispatch(args)

    parser.print_help(sys.stderr)
    return EXIT_USAGE


def _run_gate(args: argparse.Namespace) -> int:
    try:
        request = _load_change_request(args)
        graph = _load_graph(Path(args.graph))
    except CliError as exc:
        print(f"sre-harness: error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    result = evaluate_change(request, graph)
    tier = classify(_VERDICT_ACTION, _VERDICT_CONFIDENCE)
    print(json.dumps(_render(request, result, tier), indent=2, sort_keys=True))
    return _VERDICT_EXIT[result.verdict]


def _run_gate_integration(args: argparse.Namespace) -> int:
    """Evaluate one strict SPEC-B2 envelope and preserve its disposition."""
    try:
        invocation = load_change_advisory_invocation(Path(args.input))
        result = evaluate_change_advisory(invocation)
        if args.result is not None:
            write_change_advisory_result(result, Path(args.result))
    except AdvisoryIntegrationError as exc:
        print(f"sre-harness: integration error: {exc}", file=sys.stderr)
        return EXIT_INTEGRATION_INVALID

    print(json.dumps(result.to_document(), indent=2, sort_keys=True))
    return _INTEGRATION_VERDICT_EXIT[result.verdict]


# --- loading ----------------------------------------------------------------


def _load_change_request(args: argparse.Namespace) -> ChangeRequest:
    payload = _read_json(Path(args.change), what="change request")
    fallback_clusters: list[str] = list(args.target_cluster or [])

    try:
        if args.change_format == "json":
            return parse_change_request(payload)
        if args.change_format == "k8s":
            if not isinstance(payload, dict):
                raise ValueError("k8s manifest must be a JSON object")
            return parse_k8s_manifest(payload, fallback_clusters=fallback_clusters)
        # pr-diff: the file holds the unified diff as a JSON string.
        if not isinstance(payload, str):
            raise ValueError("pr-diff input must be a JSON string holding the unified diff")
        return parse_pr_diff(
            payload, service=args.service or "", fallback_clusters=fallback_clusters
        )
    except ValueError as exc:
        raise CliError(str(exc)) from exc


def _load_graph(path: Path) -> PlatformGraph:
    payload = _read_json(path, what="graph fixture")
    if not isinstance(payload, dict):
        raise CliError("graph fixture must be a JSON object with an 'entities' list")
    rows = payload.get("entities", [])
    if not isinstance(rows, list):
        raise CliError("graph fixture 'entities' must be a list")

    entities = [_entity_from_row(row) for row in rows]
    return InMemoryPlatformGraph(entities=entities)


def _entity_from_row(row: Any) -> Entity:
    if not isinstance(row, dict) or "kind" not in row or "name" not in row:
        raise CliError("each graph entity needs at least 'kind' and 'name'")
    return Entity(
        kind=str(row["kind"]),
        name=str(row["name"]),
        cluster=(str(row["cluster"]) if row.get("cluster") is not None else None),
    )


def _read_json(path: Path, what: str) -> Any:
    if not path.is_file():
        raise CliError(f"{what} file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"{what} is not valid JSON ({path}): {exc}") from exc


# --- rendering --------------------------------------------------------------


def _render(
    request: ChangeRequest,
    result: GateResult,
    tier: TierClassification,
) -> dict[str, Any]:
    return {
        "service": request.service,
        "target_cluster_ids": list(request.target_cluster_ids),
        "required_storageclasses": sorted(request.required_storageclasses),
        "verdict": result.verdict.value,
        "rationale": result.rationale,
        "missing_by_cluster": {
            cluster: sorted(missing)
            for cluster, missing in sorted(result.missing_by_cluster.items())
        },
        "classes_absent_everywhere": sorted(result.classes_absent_everywhere),
        "analysis_tier": result.analysis_tier.name,
        "recommendation_tier": result.recommendation_tier.name,
        "advisory": True,
        "tier_classification": _render_tier(tier),
        "check_results": [_render_check(check) for check in result.check_results],
    }


def _render_check(check: CheckResult) -> dict[str, Any]:
    return {
        "check_id": check.check_id,
        "verdict": check.verdict.value,
        "rationale": check.rationale,
        "evidence": _jsonable(check.evidence),
    }


def _jsonable(value: Any) -> Any:
    """Render check evidence (tuples / nested dicts) as JSON-friendly types."""
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list | set):
        return [_jsonable(item) for item in value]
    return value


def _render_tier(tier: TierClassification) -> dict[str, Any]:
    return {
        "action": _VERDICT_ACTION,
        "tier": tier.tier.name,
        "base_tier": tier.base_tier.name,
        "degraded": tier.degraded,
        "off_plan": tier.off_plan,
        "rationale": tier.rationale,
    }


# --- argument parsing -------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sre-harness",
        description="Autonomous SRE harness command-line tools.",
    )
    sub = parser.add_subparsers(dest="command")

    gate_help = "Run the change-validation gate over a change request."
    gate = sub.add_parser("gate", help=gate_help, description=gate_help)
    gate.add_argument(
        "--change",
        required=True,
        help="Path to the change request (JSON: structured, k8s manifest, or diff string).",
    )
    gate.add_argument(
        "--graph",
        required=True,
        help="Path to the platform-graph JSON fixture ({'entities': [...]}).",
    )
    gate.add_argument(
        "--change-format",
        choices=("json", "k8s", "pr-diff"),
        default="json",
        help="How to interpret --change (default: json).",
    )
    gate.add_argument(
        "--target-cluster",
        action="append",
        metavar="CLUSTER_ID",
        help="Target cluster id; repeatable. Used when k8s/pr-diff omit clusters.",
    )
    gate.add_argument(
        "--service",
        help="Service name (required for --change-format pr-diff).",
    )
    integration_help = "Run the strict SPEC-B2 advisory CI / PreSync envelope."
    integration = sub.add_parser(
        "gate-integration",
        help=integration_help,
        description=integration_help,
    )
    integration.add_argument(
        "--input",
        required=True,
        help="Path to a closed sre-harness.change-advisory-request/v1 envelope.",
    )
    integration.add_argument(
        "--result",
        help="Optional local path for the versioned advisory result artifact.",
    )
    sentinel_cli.add_subparser(sub)
    return parser


__all__ = [
    "EXIT_BLOCK",
    "EXIT_INTEGRATION_BLOCK",
    "EXIT_INTEGRATION_INVALID",
    "EXIT_INTEGRATION_PROCEED",
    "EXIT_INTEGRATION_REQUIRE_HUMAN",
    "EXIT_PROCEED",
    "EXIT_REQUIRE_HUMAN",
    "EXIT_USAGE",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - exercised via `python -m sre_harness.cli`
    raise SystemExit(main())
