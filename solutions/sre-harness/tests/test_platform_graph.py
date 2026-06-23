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
            Entity(kind="Namespace", name="payments", cluster="prod-eu-1"),
            Entity(kind="Namespace", name="staging", cluster="prod-eu-1"),
            Entity(kind="Namespace", name="payments", cluster="prod-us-1"),
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
class TestNamespacesInCluster:
    def test_returns_set_of_names_for_cluster(self, graph: InMemoryPlatformGraph) -> None:
        assert graph.namespaces_in_cluster("prod-eu-1") == {"payments", "staging"}

    def test_returns_only_matching_cluster(self, graph: InMemoryPlatformGraph) -> None:
        assert graph.namespaces_in_cluster("prod-us-1") == {"payments"}

    def test_unknown_cluster_returns_empty_set(self, graph: InMemoryPlatformGraph) -> None:
        assert graph.namespaces_in_cluster("does-not-exist") == set()


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


class _FakeMcpClient:
    """Records calls and returns a canned ``list_entities`` response."""

    def __init__(self, response: dict) -> None:
        self._response = response
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        return self._response


@pytest.mark.unit
class TestOmniscienceAdapter:
    def test_list_entities_maps_response_rows_to_entities(self) -> None:
        client = _FakeMcpClient(
            {
                "entities": [
                    {"name": "gold", "kind": "StorageClass"},
                    {"name": "silver", "kind": "StorageClass"},
                ]
            }
        )
        adapter = OmniscienceMcpPlatformGraph(client=client)

        result = adapter.list_entities(kind="StorageClass", cluster="prod-eu-1")

        # cluster comes from the query argument (the tool filters by it).
        assert {(e.kind, e.name, e.cluster) for e in result} == {
            ("StorageClass", "gold", "prod-eu-1"),
            ("StorageClass", "silver", "prod-eu-1"),
        }

    def test_list_entities_sends_the_contract_arguments(self) -> None:
        client = _FakeMcpClient({"entities": []})
        adapter = OmniscienceMcpPlatformGraph(client=client, as_of="2026-06-16T00:00:00Z")

        adapter.list_entities(kind="Service", cluster="c1", name="payments")

        assert client.calls == [
            (
                "list_entities",
                {
                    "kind": "Service",
                    "cluster": "c1",
                    "name": "payments",
                    "as_of": "2026-06-16T00:00:00Z",
                },
            )
        ]

    def test_storageclasses_in_cluster_returns_name_set(self) -> None:
        client = _FakeMcpClient(
            {
                "entities": [
                    {"name": "gold", "kind": "StorageClass"},
                    {"name": "silver", "kind": "StorageClass"},
                ]
            }
        )
        adapter = OmniscienceMcpPlatformGraph(client=client)

        assert adapter.storageclasses_in_cluster("prod-eu-1") == {"gold", "silver"}
        # queried by kind=StorageClass scoped to the cluster
        name, args = client.calls[-1]
        assert name == "list_entities"
        assert args["kind"] == "StorageClass"
        assert args["cluster"] == "prod-eu-1"

    def test_namespaces_in_cluster_returns_name_set(self) -> None:
        client = _FakeMcpClient(
            {
                "entities": [
                    {"name": "payments", "kind": "Namespace"},
                    {"name": "staging", "kind": "Namespace"},
                ]
            }
        )
        adapter = OmniscienceMcpPlatformGraph(client=client)

        assert adapter.namespaces_in_cluster("prod-eu-1") == {"payments", "staging"}
        name, args = client.calls[-1]
        assert name == "list_entities"
        assert args["kind"] == "Namespace"
        assert args["cluster"] == "prod-eu-1"

    def test_missing_or_empty_entities_yields_empty(self) -> None:
        assert (
            OmniscienceMcpPlatformGraph(client=_FakeMcpClient({})).list_entities("StorageClass")
            == []
        )
        empty = OmniscienceMcpPlatformGraph(client=_FakeMcpClient({"entities": []}))
        assert empty.storageclasses_in_cluster("c1") == set()
