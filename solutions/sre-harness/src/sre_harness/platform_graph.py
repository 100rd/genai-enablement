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
from typing import Protocol, runtime_checkable


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


_NOT_WIRED = (
    "OmniscienceMcpPlatformGraph is a stub. Wire it to the Omniscience MCP "
    "`list_entities` tool: input {kind, cluster, name, as_of}, workspace-scoped, "
    "returning entities (same shape as the `get_entity` tool). The tool is being "
    "implemented on the Omniscience `feat/sre-gate-graph` branch."
)


class OmniscienceMcpPlatformGraph:
    """Adapter that will call the Omniscience MCP ``list_entities`` tool.

    Contract (must match the Omniscience tool exactly):
        list_entities(kind: str, cluster: str | None, name: str | None,
                      as_of: ISO-8601 str | None) -> list[entity]

    Not yet wired — methods raise ``NotImplementedError``. All harness logic is
    exercised through :class:`InMemoryPlatformGraph` until the live tool lands.
    """

    def __init__(self, client: object, *, as_of: str | None = None) -> None:
        self._client = client
        self._as_of = as_of

    def list_entities(
        self,
        kind: str,
        cluster: str | None = None,
        name: str | None = None,
    ) -> list[Entity]:
        raise NotImplementedError(_NOT_WIRED)

    def storageclasses_in_cluster(self, cluster_id: str) -> set[str]:
        raise NotImplementedError(_NOT_WIRED)


__all__ = [
    "Entity",
    "InMemoryPlatformGraph",
    "OmniscienceMcpPlatformGraph",
    "PlatformGraph",
]
