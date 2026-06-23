"""Best-effort parsers from k8s manifests / PR diffs into a ``ChangeRequest``.

Stage 2 of the harness wires the change-validation gate into a pipeline, so the
gate has to accept the artifacts a pipeline actually has: a k8s manifest about to
be applied, or a PR's unified diff. These parsers are deliberately *best-effort*
and conservative — they extract what they can (``service``,
``target_cluster_ids``, ``required_storageclasses`` and, since Stage 2,
``required_namespaces`` and high-blast-radius ``actions``) and raise a clear
``ValueError`` when a required field cannot be determined, rather than guessing.
The new signals are advisory-only: when absent they stay empty, leaving the
namespace and blast-radius checks to proceed.

The structured-JSON path stays the source of truth: see
:func:`sre_harness.change_gate.parse_change_request`.
"""

from __future__ import annotations

import re
from typing import Any

from sre_harness.change_gate import ChangeRequest

# Matches an *added* unified-diff line declaring a StorageClass, e.g.
#   "+      storageClassName: gold"
# Context/removed lines are intentionally excluded (matches `+`, not `+++`).
_ADDED_STORAGECLASS = re.compile(
    r"^\+(?!\+)\s*storageClassName:\s*[\"']?(?P<name>[A-Za-z0-9._-]+)[\"']?\s*$"
)

# Best-effort mapping of high-blast-radius k8s "kinds" (AWS ACK / Crossplane
# style CRDs) to action ids in the autonomy-tier table. Conservative and small:
# only kinds whose blast radius is unambiguous are mapped. Unmapped kinds yield
# no action (the blast-radius check then proceeds for them).
_HIGH_BLAST_RADIUS_KINDS: dict[str, str] = {
    "DBInstance": "rds_param_change",
    "DBCluster": "rds_param_change",
    "Role": "iam_change",
    "Policy": "iam_change",
    "SecurityGroup": "security_group_change",
}

# Best-effort detection of *added* high-risk resource declarations in a diff
# (Terraform/CloudFormation-ish substrings). Keyed substring -> action id; the
# first matching substring on an added line wins. Conservative by design: this
# is advisory signal, not authoritative parsing.
_HIGH_RISK_DIFF_MARKERS: tuple[tuple[str, str], ...] = (
    ("aws_db_instance", "rds_param_change"),
    ("aws_rds_cluster", "rds_param_change"),
    ("aws_iam_", "iam_change"),
    ("aws_security_group", "security_group_change"),
)


def parse_k8s_manifest(
    manifest: dict[str, Any],
    fallback_clusters: list[str],
) -> ChangeRequest:
    """Extract a :class:`ChangeRequest` from a single k8s manifest dict.

    - ``service`` comes from ``metadata.name``.
    - ``required_storageclasses`` are collected from
      ``spec.volumeClaimTemplates[].spec.storageClassName`` and a top-level
      ``spec.storageClassName`` (PVC).
    - ``required_namespaces`` is ``{metadata.namespace}`` when present (best-effort).
    - ``actions`` map obvious high-blast-radius ``kind``s (AWS ACK / Crossplane
      CRDs like ``DBInstance``, ``Role``, ``SecurityGroup``) to action ids so the
      blast-radius check can escalate them; ordinary kinds map to nothing.
    - ``target_cluster_ids`` come from ``metadata.labels.cluster`` if present,
      else from ``fallback_clusters`` (e.g. ``--target-cluster`` flags).

    Raises ``ValueError`` if the service name or target clusters cannot be
    determined.
    """
    metadata = manifest.get("metadata") or {}
    service = metadata.get("name")
    if not service:
        raise ValueError("k8s manifest is missing metadata.name (service)")

    spec = manifest.get("spec") or {}
    required = _storageclasses_from_spec(spec)

    labels = metadata.get("labels") or {}
    cluster_label = labels.get("cluster")
    clusters = [cluster_label] if cluster_label else list(fallback_clusters)
    if not clusters:
        raise ValueError(
            "could not determine target cluster(s): no metadata.labels.cluster "
            "and no fallback clusters supplied (pass --target-cluster)"
        )

    namespace = metadata.get("namespace")
    required_namespaces = (
        frozenset({str(namespace)}) if isinstance(namespace, str) and namespace else frozenset()
    )

    action = _HIGH_BLAST_RADIUS_KINDS.get(str(manifest.get("kind", "")))
    actions = frozenset({action}) if action else frozenset()

    return ChangeRequest(
        service=str(service),
        target_cluster_ids=clusters,
        required_storageclasses=required,
        actions=actions,
        required_namespaces=required_namespaces,
    )


def parse_pr_diff(
    diff: str,
    service: str,
    fallback_clusters: list[str],
) -> ChangeRequest:
    """Extract a :class:`ChangeRequest` from a unified PR diff.

    Best-effort, advisory parsing of *added* (`+`) lines only:

    - ``storageClassName`` declarations -> ``required_storageclasses``.
    - high-risk resource declarations (Terraform-ish substrings such as
      ``aws_db_instance`` / ``aws_iam_*`` / ``aws_security_group``) -> ``actions``
      so the blast-radius check can escalate them.

    Removed (`-`) and context lines are ignored. ``service`` and clusters cannot
    be inferred reliably from a raw diff, so both are supplied by the caller
    (``--service`` / ``--target-cluster``).
    """
    if not service:
        raise ValueError("a service name is required to parse a PR diff (--service)")
    if not fallback_clusters:
        raise ValueError(
            "could not determine target cluster(s) for a PR diff (pass --target-cluster)"
        )

    required: set[str] = set()
    actions: set[str] = set()
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        match = _ADDED_STORAGECLASS.match(line)
        if match:
            required.add(match.group("name"))
        for marker, action in _HIGH_RISK_DIFF_MARKERS:
            if marker in line:
                actions.add(action)

    return ChangeRequest(
        service=service,
        target_cluster_ids=list(fallback_clusters),
        required_storageclasses=required,
        actions=frozenset(actions),
    )


def _storageclasses_from_spec(spec: dict[str, Any]) -> set[str]:
    """Collect StorageClass names from a k8s ``spec`` (PVC + volumeClaimTemplates)."""
    found: set[str] = set()

    top_level = spec.get("storageClassName")
    if isinstance(top_level, str) and top_level:
        found.add(top_level)

    for template in spec.get("volumeClaimTemplates") or []:
        if not isinstance(template, dict):
            continue
        name = (template.get("spec") or {}).get("storageClassName")
        if isinstance(name, str) and name:
            found.add(name)

    return found


__all__ = ["parse_k8s_manifest", "parse_pr_diff"]
