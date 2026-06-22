"""Best-effort parsers from k8s manifests / PR diffs into a ``ChangeRequest``.

Stage 2 of the harness wires the change-validation gate into a pipeline, so the
gate has to accept the artifacts a pipeline actually has: a k8s manifest about to
be applied, or a PR's unified diff. These parsers are deliberately *best-effort*
and conservative — they extract what they can (``service``,
``target_cluster_ids``, ``required_storageclasses``) and raise a clear
``ValueError`` when a field cannot be determined, rather than guessing.

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


def parse_k8s_manifest(
    manifest: dict[str, Any],
    fallback_clusters: list[str],
) -> ChangeRequest:
    """Extract a :class:`ChangeRequest` from a single k8s manifest dict.

    - ``service`` comes from ``metadata.name``.
    - ``required_storageclasses`` are collected from
      ``spec.volumeClaimTemplates[].spec.storageClassName`` and a top-level
      ``spec.storageClassName`` (PVC).
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

    return ChangeRequest(
        service=str(service),
        target_cluster_ids=clusters,
        required_storageclasses=required,
    )


def parse_pr_diff(
    diff: str,
    service: str,
    fallback_clusters: list[str],
) -> ChangeRequest:
    """Extract a :class:`ChangeRequest` from a unified PR diff.

    Only *added* (`+`) lines declaring ``storageClassName`` are counted — the
    change introduces a dependency on those classes. ``service`` and clusters
    cannot be inferred reliably from a raw diff, so both are supplied by the
    caller (``--service`` / ``--target-cluster``).
    """
    if not service:
        raise ValueError("a service name is required to parse a PR diff (--service)")
    if not fallback_clusters:
        raise ValueError(
            "could not determine target cluster(s) for a PR diff (pass --target-cluster)"
        )

    required: set[str] = set()
    for line in diff.splitlines():
        match = _ADDED_STORAGECLASS.match(line)
        if match:
            required.add(match.group("name"))

    return ChangeRequest(
        service=service,
        target_cluster_ids=list(fallback_clusters),
        required_storageclasses=required,
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
