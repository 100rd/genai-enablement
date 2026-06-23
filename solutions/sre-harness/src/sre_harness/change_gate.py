"""Change-validation gate — runs a list of deterministic checks and aggregates.

This is the deterministic, rules-based verification tier (the strongest tier per
``research/2026-agentic-sre-refresh.md`` Section 4). The gate never executes
anything: the *analysis* is T1 (read-only) and emitting the *verdict* is T2
(advisory) — a controller or human acts on it.

Stage 2 deepens the gate from a single check into a multi-check gate. Each check
(:mod:`sre_harness.change_checks`) is a pure ``(request, graph) -> CheckResult``;
the gate runs all registered checks and aggregates their verdicts:

    block dominates -> else require_human if any -> else proceed.

The shipped checks are ``storageclass_present`` (required StorageClass present),
``blast_radius`` (high-blast-radius actions escalate to a human), and
``namespace_present`` (required Namespace present).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sre_harness.autonomy_tiers import Tier
from sre_harness.change_checks import DEFAULT_CHECKS, Check, CheckResult
from sre_harness.observability import attributes as attrs
from sre_harness.observability import set_attributes, span
from sre_harness.platform_graph import PlatformGraph


class Verdict(Enum):
    PROCEED = "proceed"
    BLOCK = "block"
    REQUIRE_HUMAN = "require_human"


# Aggregation precedence: a more severe verdict dominates a less severe one.
_VERDICT_SEVERITY = {
    Verdict.PROCEED: 0,
    Verdict.REQUIRE_HUMAN: 1,
    Verdict.BLOCK: 2,
}

# The check whose evidence backs the legacy StorageClass-specific fields.
_STORAGECLASS_CHECK_ID = "storageclass_present"


@dataclass(frozen=True)
class ChangeRequest:
    """A proposed change to validate before it reaches production.

    ``actions`` and ``required_namespaces`` are optional signals consumed by the
    blast-radius and namespace checks respectively; the StorageClass check
    ignores them, so a request that supplies neither behaves exactly as before.
    """

    service: str
    target_cluster_ids: list[str]
    required_storageclasses: set[str]
    actions: frozenset[str] = frozenset()
    required_namespaces: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.target_cluster_ids:
            raise ValueError("target_cluster_ids must not be empty")


@dataclass(frozen=True)
class GateResult:
    """The gate's aggregate verdict plus per-check results and evidence.

    The StorageClass-specific fields (``missing_by_cluster`` /
    ``classes_absent_everywhere``) are retained for back-compat and sourced from
    the ``storageclass_present`` check's evidence.
    """

    verdict: Verdict
    rationale: str
    missing_by_cluster: dict[str, set[str]]
    classes_absent_everywhere: set[str]
    analysis_tier: Tier
    recommendation_tier: Tier
    check_results: tuple[CheckResult, ...] = field(default_factory=tuple)


def evaluate_change(
    request: ChangeRequest,
    graph: PlatformGraph,
    checks: tuple[Check, ...] = DEFAULT_CHECKS,
) -> GateResult:
    """Evaluate a change request against the platform graph (deterministic).

    Runs every registered check and aggregates their verdicts (block dominates,
    then require_human, then proceed). Each check is pure and read-only.

    Instrumented (AgentOps): an overall ``gate.evaluate`` span with a child span
    per check. Tracing is no-op by default, so behaviour is unchanged when no
    OTel provider is configured.
    """
    with span(
        "gate.evaluate",
        {
            attrs.GATE_SERVICE: request.service,
            attrs.GATE_TARGET_CLUSTER_COUNT: len(request.target_cluster_ids),
            attrs.GATE_CHECK_COUNT: len(checks),
            attrs.GATE_ANALYSIS_TIER: Tier.T1.name,
            attrs.GATE_RECOMMENDATION_TIER: Tier.T2.name,
        },
        service="sre-harness",
    ) as gate_span:
        check_results = tuple(_run_check(check, request, graph) for check in checks)
        verdict = _aggregate(check_results)
        set_attributes(gate_span, {attrs.GATE_VERDICT: verdict.value})

    missing_by_cluster, classes_absent_everywhere = _storageclass_back_compat(check_results)

    return GateResult(
        verdict=verdict,
        rationale=_combine_rationale(check_results),
        missing_by_cluster=missing_by_cluster,
        classes_absent_everywhere=classes_absent_everywhere,
        analysis_tier=Tier.T1,  # read-only analysis
        recommendation_tier=Tier.T2,  # advisory verdict; the gate never executes
        check_results=check_results,
    )


def _run_check(check: Check, request: ChangeRequest, graph: PlatformGraph) -> CheckResult:
    """Run one check inside a child ``gate.check`` span (AgentOps).

    Wrapping at this boundary keeps :mod:`sre_harness.change_checks` free of any
    tracing concern. The span is no-op when tracing is off.
    """
    with span("gate.check") as check_span:
        result = check(request, graph)
        set_attributes(
            check_span,
            {
                attrs.GATE_CHECK_ID: result.check_id,
                attrs.GATE_CHECK_VERDICT: result.verdict.value,
            },
        )
        return result


def _aggregate(check_results: tuple[CheckResult, ...]) -> Verdict:
    """block dominates -> else require_human if any -> else proceed."""
    if not check_results:
        return Verdict.PROCEED
    return max(
        (result.verdict for result in check_results),
        key=lambda verdict: _VERDICT_SEVERITY[verdict],
    )


def _combine_rationale(check_results: tuple[CheckResult, ...]) -> str:
    """One line per check, prefixed by its id, so the verdict is auditable."""
    return " | ".join(f"[{result.check_id}] {result.rationale}" for result in check_results)


def _storageclass_back_compat(
    check_results: tuple[CheckResult, ...],
) -> tuple[dict[str, set[str]], set[str]]:
    """Rehydrate the legacy StorageClass fields from check #1's evidence."""
    for result in check_results:
        if result.check_id != _STORAGECLASS_CHECK_ID:
            continue
        missing = {
            cluster: set(names)
            for cluster, names in result.evidence.get("missing_by_cluster", {}).items()
        }
        absent = set(result.evidence.get("classes_absent_everywhere", ()))
        return missing, absent
    return {}, set()


def parse_change_request(payload: dict[str, Any]) -> ChangeRequest:
    """Build a :class:`ChangeRequest` from a structured payload.

    A thin stub for now; parsing a real PR diff / k8s manifest into this shape
    is a follow-up.
    """
    try:
        service = payload["service"]
        target_cluster_ids = payload["target_cluster_ids"]
        required = payload["required_storageclasses"]
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc.args[0]}") from exc

    return ChangeRequest(
        service=service,
        target_cluster_ids=list(target_cluster_ids),
        required_storageclasses=set(required),
    )


__all__ = [
    "ChangeRequest",
    "GateResult",
    "Verdict",
    "evaluate_change",
    "parse_change_request",
]
