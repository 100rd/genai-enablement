"""Individual change-validation checks (Stage 2 — multi-check gate).

Each check is a pure callable ``(request, graph) -> CheckResult``. The gate
(:func:`sre_harness.change_gate.evaluate_change`) runs a registered list of them
and aggregates their verdicts. Keeping each check small and pure makes the gate
trivially extensible: add a callable to the registry, nothing else changes.

The three deterministic checks shipped here:

- ``storageclass_present`` — is every required StorageClass present in the target
  clusters? (the original gate logic, behaviour-preserving).
- ``blast_radius``        — does any action in the change touch a high-blast-radius
  resource (RDS / IAM / security groups / data deletion)? Mapped through the
  action-tier table: any **T3** action — or an off-plan (unknown) one — escalates
  to ``require_human``. T4/T2/T1 actions proceed. (Reversible-but-significant
  escalates to a human, matching the action-tier table.)
- ``namespace_present``    — is every required Namespace present in the target
  clusters? (StorageClass logic, for namespaces.)

All three are read-only analysis (T1) emitting an advisory verdict (T2); none
execute anything.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sre_harness.autonomy_tiers import Tier, classify
from sre_harness.platform_graph import PlatformGraph

if TYPE_CHECKING:
    from sre_harness.change_gate import ChangeRequest, Verdict

# The tier that gates an action behind explicit human approval (HITL). Note the
# tier *value* ordering (T1<T2<T3<T4) is not a severity ordering: T4 is
# autonomous (proceed), T3 is the approval gate. So this is an identity check,
# not ``>= T3``.
_HUMAN_GATE_TIER = Tier.T3
# The blast-radius classification is deterministic, so confidence is maximal.
_BLAST_RADIUS_CONFIDENCE = 1.0


@dataclass(frozen=True)
class CheckResult:
    """One check's verdict plus the evidence behind it.

    ``evidence`` is a JSON-serialisable mapping (tuples/dicts of primitives) so
    the CLI can surface per-check findings without bespoke serialisation.
    """

    check_id: str
    verdict: Verdict
    rationale: str
    evidence: dict[str, Any] = field(default_factory=dict)


# A check maps a request + graph to a single :class:`CheckResult`.
Check = Callable[["ChangeRequest", PlatformGraph], CheckResult]


def check_storageclass_present(request: ChangeRequest, graph: PlatformGraph) -> CheckResult:
    """Check #1: every required StorageClass present in the target clusters.

    - proceed       : required ⊆ available in *every* target cluster
    - block         : a required class is absent in *every* target cluster
    - require_human : absent in some but not all target clusters
    """
    return _presence_check(
        check_id="storageclass_present",
        required=set(request.required_storageclasses),
        targets=request.target_cluster_ids,
        available=graph.storageclasses_in_cluster,
        label="storageclass",
        plural="storageclasses",
        absent_key="classes_absent_everywhere",
    )


def check_namespace_present(request: ChangeRequest, graph: PlatformGraph) -> CheckResult:
    """Check #3: every required Namespace present in the target clusters.

    Same presence semantics as the StorageClass check, for namespaces.
    """
    return _presence_check(
        check_id="namespace_present",
        required=set(request.required_namespaces),
        targets=request.target_cluster_ids,
        available=graph.namespaces_in_cluster,
        label="namespace",
        plural="namespaces",
        absent_key="namespaces_absent_everywhere",
    )


def check_blast_radius(request: ChangeRequest, graph: PlatformGraph) -> CheckResult:
    """Check #2: escalate high-blast-radius actions to a human.

    Each action is classified via the action-tier table. Any T3 action
    (:data:`_HUMAN_GATE_TIER` — RDS / IAM / security groups / data deletion) or
    an off-plan (unknown) action escalates the change to ``require_human``.
    T4 (autonomous) / T2 / T1 actions proceed. The check never blocks: a
    high-blast-radius change is a *human decision*, not an automatic rejection.
    """
    from sre_harness.change_gate import Verdict

    escalating: list[tuple[str, str]] = []  # (action, reason)
    for action in sorted(request.actions):
        classification = classify(action, confidence=_BLAST_RADIUS_CONFIDENCE)
        if classification.off_plan:
            escalating.append((action, "off-plan (unknown action)"))
        elif classification.tier is _HUMAN_GATE_TIER:
            escalating.append((action, classification.tier.name))

    if not escalating:
        return CheckResult(
            check_id="blast_radius",
            verdict=Verdict.PROCEED,
            rationale="No high-blast-radius actions in the change.",
            evidence={"escalating_actions": ()},
        )

    detail = ", ".join(f"{action} [{reason}]" for action, reason in escalating)
    return CheckResult(
        check_id="blast_radius",
        verdict=Verdict.REQUIRE_HUMAN,
        rationale=(f"REQUIRE_HUMAN: high-blast-radius action(s) need human approval: {detail}."),
        evidence={"escalating_actions": tuple(action for action, _ in escalating)},
    )


def _presence_check(
    *,
    check_id: str,
    required: set[str],
    targets: list[str],
    available: Callable[[str], set[str]],
    label: str,
    plural: str,
    absent_key: str,
) -> CheckResult:
    """Shared presence logic for StorageClass / Namespace checks."""
    from sre_harness.change_gate import Verdict

    if not required:
        return CheckResult(
            check_id=check_id,
            verdict=Verdict.PROCEED,
            rationale=f"No required {plural}; nothing to verify.",
            evidence={"missing_by_cluster": {}, absent_key: ()},
        )

    available_by_cluster = {cluster: available(cluster) for cluster in targets}
    missing_by_cluster = {
        cluster: tuple(sorted(missing))
        for cluster in targets
        if (missing := required - available_by_cluster[cluster])
    }
    absent_everywhere = tuple(
        sorted(
            name for name in required if all(name not in available_by_cluster[c] for c in targets)
        )
    )

    evidence: dict[str, Any] = {
        "missing_by_cluster": missing_by_cluster,
        absent_key: absent_everywhere,
    }

    if absent_everywhere:
        verdict = Verdict.BLOCK
        rationale = (
            f"BLOCK: {label}(s) absent in every target cluster: "
            f"{', '.join(absent_everywhere)}. {_missing_detail(missing_by_cluster)}"
        )
    elif missing_by_cluster:
        verdict = Verdict.REQUIRE_HUMAN
        rationale = (
            f"REQUIRE_HUMAN: {label} gaps in some target clusters. "
            f"{_missing_detail(missing_by_cluster)}"
        )
    else:
        verdict = Verdict.PROCEED
        rationale = f"All required {plural} present in every target cluster."

    return CheckResult(check_id=check_id, verdict=verdict, rationale=rationale, evidence=evidence)


def _missing_detail(missing_by_cluster: dict[str, tuple[str, ...]]) -> str:
    if not missing_by_cluster:
        return ""
    detail = "; ".join(
        f"{cluster} lacks {{{', '.join(missing)}}}"
        for cluster, missing in sorted(missing_by_cluster.items())
    )
    return f"Details: {detail}."


DEFAULT_CHECKS: tuple[Check, ...] = (
    check_storageclass_present,
    check_blast_radius,
    check_namespace_present,
)


__all__ = [
    "DEFAULT_CHECKS",
    "Check",
    "CheckResult",
    "check_blast_radius",
    "check_namespace_present",
    "check_storageclass_present",
]
