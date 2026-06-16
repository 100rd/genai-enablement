"""Unit tests for the platform-graph port and its in-memory fake.

The port mirrors the Omniscience MCP `list_entities` contract so the harness
can be built and tested against a fake while the real adapter is wired up in
the Omniscience repo in parallel.
"""

import pytest

from sre_harness.platform_graph import (
    Entity,
    InMemoryPlatformGraph,
    OmniscienceMcpPlatformGraph,
    PlatformGraph,
)


@pytest.fixture
def graph() -> InMemoryPlatformGraph:
    return InMemoryPlatformGraph(
        entities=[
            Entity(kind="StorageClass", name="gold", cluster="prod-eu-1"),
            Entity(kind="StorageClass", name="silver", cluster="prod-eu-1"),
            Entity(kind="StorageClass", name="silver", cluster="prod-us-1"),
            Entity(kind="Service", name="payments", cluster="prod-eu-1"),
        ]
    )


@pytest.mark.unit
class TestProtocolConformance:
    def test_in_memory_is_a_platform_graph(self, graph: InMemoryPlatformGraph) -> None:
        assert isinstance(graph, PlatformGraph)

    def test_adapter_is_a_platform_graph(self) -> None:
        assert isinstance(OmniscienceMcpPlatformGraph(client=object()), PlatformGraph)


@pytest.mark.unit
class TestStorageClassesInCluster:
    def test_returns_set_of_names_for_cluster(self, graph: InMemoryPlatformGraph) -> None:
        assert graph.storageclasses_in_cluster("prod-eu-1") == {"gold", "silver"}

    def test_returns_only_matching_cluster(self, graph: InMemoryPlatformGraph) -> None:
        assert graph.storageclasses_in_cluster("prod-us-1") == {"silver"}

    def test_unknown_cluster_returns_empty_set(self, graph: InMemoryPlatformGraph) -> None:
        assert graph.storageclasses_in_cluster("does-not-exist") == set()


@pytest.mark.unit
class TestListEntities:
    def test_filter_by_kind(self, graph: InMemoryPlatformGraph) -> None:
        names = {e.name for e in graph.list_entities(kind="StorageClass")}
        assert names == {"gold", "silver"}

    def test_filter_by_kind_and_cluster(self, graph: InMemoryPlatformGraph) -> None:
        result = graph.list_entities(kind="StorageClass", cluster="prod-us-1")
        assert {e.name for e in result} == {"silver"}

    def test_filter_by_name(self, graph: InMemoryPlatformGraph) -> None:
        result = graph.list_entities(kind="StorageClass", name="gold")
        assert [e.cluster for e in result] == ["prod-eu-1"]

    def test_no_match_returns_empty_list(self, graph: InMemoryPlatformGraph) -> None:
        assert graph.list_entities(kind="StorageClass", name="platinum") == []

    def test_returned_list_does_not_mutate_internal_state(
        self, graph: InMemoryPlatformGraph
    ) -> None:
        result = graph.list_entities(kind="StorageClass")
        result.clear()
        # Internal state is unaffected by mutating the returned list.
        assert graph.storageclasses_in_cluster("prod-eu-1") == {"gold", "silver"}


@pytest.mark.unit
class TestOmniscienceAdapterStub:
    def test_list_entities_not_implemented(self) -> None:
        adapter = OmniscienceMcpPlatformGraph(client=object())
        with pytest.raises(NotImplementedError):
            adapter.list_entities(kind="StorageClass")

    def test_storageclasses_in_cluster_not_implemented(self) -> None:
        adapter = OmniscienceMcpPlatformGraph(client=object())
        with pytest.raises(NotImplementedError):
            adapter.storageclasses_in_cluster("prod-eu-1")
