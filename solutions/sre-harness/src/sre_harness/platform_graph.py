"""Platform-graph port.

The harness reasons over an authoritative platform-state graph (clusters,
namespaces, services, storageclasses, ...). It depends on the ``PlatformGraph``
*protocol*, not a concrete store, so it can be built and tested against an
in-memory fake while the real adapter (Omniscience MCP) is wired up separately.

The port mirrors the Omniscience MCP ``list_entities`` contract:
    list_entities(kind, cluster, name, as_of) -> [entity]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class Entity:
    """A node in the platform-state graph."""

    kind: str
    name: str
    cluster: str | None = None


@runtime_checkable
class PlatformGraph(Protocol):
    """Read-only port over the platform-state graph."""

    def list_entities(
        self,
        kind: str,
        cluster: str | None = None,
        name: str | None = None,
    ) -> list[Entity]:
        """Return entities matching ``kind`` and the optional filters."""
        ...

    def storageclasses_in_cluster(self, cluster_id: str) -> set[str]:
        """Return the set of StorageClass names available in ``cluster_id``."""
        ...


class InMemoryPlatformGraph:
    """In-memory ``PlatformGraph`` for tests and local runs."""

    def __init__(self, entities: list[Entity]) -> None:
        self._entities: tuple[Entity, ...] = tuple(entities)

    def list_entities(
        self,
        kind: str,
        cluster: str | None = None,
        name: str | None = None,
    ) -> list[Entity]:
        return [
            entity
            for entity in self._entities
            if entity.kind == kind
            and (cluster is None or entity.cluster == cluster)
            and (name is None or entity.name == name)
        ]

    def storageclasses_in_cluster(self, cluster_id: str) -> set[str]:
        return {
            entity.name
            for entity in self._entities
            if entity.kind == "StorageClass" and entity.cluster == cluster_id
        }


_LIST_ENTITIES_TOOL = "list_entities"


@runtime_checkable
class McpToolClient(Protocol):
    """Minimal structural client for invoking a single MCP tool.

    A thin seam so the adapter is testable without depending on an MCP SDK.
    A real client (e.g. one wrapping the ``mcp`` Python SDK) implements
    ``call_tool``; if that client is async, wrap it to expose this sync surface.
    """

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call MCP tool ``name`` with ``arguments`` and return its result."""
        ...


class OmniscienceMcpPlatformGraph:
    """``PlatformGraph`` backed by the Omniscience MCP ``list_entities`` tool.

    Contract (matches the Omniscience tool exactly):
        list_entities(kind, cluster?, name?, as_of?) ->
            {"entities": [{name, kind, source, chunk_text,
                           valid_from, valid_to, recorded_at}, ...],
             "effective_as_of": ..., "meta": ...}

    The tool exposes ``cluster`` as a *query filter*, not a per-entity field, so
    entities resolved with a ``cluster`` argument carry that cluster; an
    unfiltered query leaves :attr:`Entity.cluster` as ``None``.
    """

    def __init__(self, client: McpToolClient, *, as_of: str | None = None) -> None:
        self._client = client
        self._as_of = as_of

    def list_entities(
        self,
        kind: str,
        cluster: str | None = None,
        name: str | None = None,
    ) -> list[Entity]:
        result = self._client.call_tool(
            _LIST_ENTITIES_TOOL,
            {"kind": kind, "cluster": cluster, "name": name, "as_of": self._as_of},
        )
        rows = result.get("entities", []) if isinstance(result, dict) else []
        return [
            Entity(
                kind=str(row.get("kind", kind)),
                name=str(row["name"]),
                cluster=cluster,
            )
            for row in rows
            if isinstance(row, dict) and row.get("name") is not None
        ]

    def storageclasses_in_cluster(self, cluster_id: str) -> set[str]:
        return {
            entity.name
            for entity in self.list_entities("StorageClass", cluster=cluster_id)
        }


__all__ = [
    "Entity",
    "InMemoryPlatformGraph",
    "McpToolClient",
    "OmniscienceMcpPlatformGraph",
    "PlatformGraph",
]
