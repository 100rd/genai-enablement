"""Change-validation gate — check #1: required StorageClass present in targets.

This is the deterministic, rules-based verification tier (the strongest tier per
``research/2026-agentic-sre-refresh.md`` Section 4). The gate never executes
anything: the *analysis* is T1 (read-only) and emitting the *verdict* is T2
(advisory) — a controller or human acts on it.

Verdict rules:
- proceed       : required ⊆ available in *every* target cluster
- block         : a required class is absent in *every* target cluster
- require_human : absent in some but not all target clusters
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from sre_harness.autonomy_tiers import Tier
from sre_harness.platform_graph import PlatformGraph


class Verdict(Enum):
    PROCEED = "proceed"
    BLOCK = "block"
    REQUIRE_HUMAN = "require_human"


@dataclass(frozen=True)
class ChangeRequest:
    """A proposed change to validate before it reaches production."""

    service: str
    target_cluster_ids: list[str]
    required_storageclasses: set[str]

    def __post_init__(self) -> None:
        if not self.target_cluster_ids:
            raise ValueError("target_cluster_ids must not be empty")


@dataclass(frozen=True)
class GateResult:
    """The gate's verdict plus the evidence behind it."""

    verdict: Verdict
    rationale: str
    missing_by_cluster: dict[str, set[str]]
    classes_absent_everywhere: set[str]
    analysis_tier: Tier
    recommendation_tier: Tier


def evaluate_change(request: ChangeRequest, graph: PlatformGraph) -> GateResult:
    """Evaluate a change request against the platform graph (deterministic)."""
    required = request.required_storageclasses
    targets = request.target_cluster_ids

    available_by_cluster = {
        cluster: graph.storageclasses_in_cluster(cluster) for cluster in targets
    }
    missing_by_cluster = {
        cluster: missing
        for cluster in targets
        if (missing := required - available_by_cluster[cluster])
    }
    classes_absent_everywhere = {
        storageclass
        for storageclass in required
        if all(storageclass not in available_by_cluster[c] for c in targets)
    }

    if not required:
        verdict = Verdict.PROCEED
    elif classes_absent_everywhere:
        verdict = Verdict.BLOCK
    elif missing_by_cluster:
        verdict = Verdict.REQUIRE_HUMAN
    else:
        verdict = Verdict.PROCEED

    return GateResult(
        verdict=verdict,
        rationale=_build_rationale(verdict, missing_by_cluster, classes_absent_everywhere),
        missing_by_cluster=missing_by_cluster,
        classes_absent_everywhere=classes_absent_everywhere,
        analysis_tier=Tier.T1,  # read-only analysis
        recommendation_tier=Tier.T2,  # advisory verdict; the gate never executes
    )


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


def _build_rationale(
    verdict: Verdict,
    missing_by_cluster: dict[str, set[str]],
    classes_absent_everywhere: set[str],
) -> str:
    if verdict is Verdict.PROCEED:
        return "All required storageclasses are present in every target cluster."

    detail = "; ".join(
        f"{cluster} lacks {{{', '.join(sorted(missing))}}}"
        for cluster, missing in sorted(missing_by_cluster.items())
    )
    if verdict is Verdict.BLOCK:
        absent = ", ".join(sorted(classes_absent_everywhere))
        return (
            f"BLOCK: storageclass(es) absent in every target cluster: {absent}. "
            f"Details: {detail}."
        )
    return f"REQUIRE_HUMAN: storageclass gaps in some target clusters. Details: {detail}."


__all__ = [
    "ChangeRequest",
    "GateResult",
    "Verdict",
    "evaluate_change",
    "parse_change_request",
]
