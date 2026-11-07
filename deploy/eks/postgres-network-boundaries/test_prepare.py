"""Regression cases for the policy-only Frankfurt preparation guard."""

import copy
import json

import pytest

import prepare as boundary


@pytest.fixture
def legacy():
    name = boundary.NAME
    component = boundary.COMPONENT
    instance = boundary.INSTANCE
    dns = {"ports": boundary.DNS_PORTS}
    open_pg = {"ports": [*boundary.DNS_PORTS, boundary.PG_PORT]}
    directions = ["Ingress", "Egress"]

    def policy(selector, ingress, egress):
        return {
            "podSelector": selector, "policyTypes": directions,
            "ingress": ingress, "egress": egress,
        }

    def named(*names):
        return {"matchExpressions": [{"key": name, "operator": "In", "values": list(names)}]}

    snapshot = {
        kind: {} for kind in ("networkpolicy", "ciliumnetworkpolicy", "ciliumclusterwidenetworkpolicy",
                              "pod", "service", "deployment", "statefulset", "job", "cronjob")
    }
    specs = {}
    for owner, (database, _) in boundary.OWNERS.items():
        selector = boundary.database(owner)
        specs[database] = policy(selector, [{"ports": [boundary.PG_PORT]}], [{}])
        snapshot["service"][database] = {
            "selector": selector["matchLabels"], "uid": f"svc-{database}",
            "cluster_ips": [f"10.0.0.{len(snapshot['service']) + 1}"],
            "postgres_port": [{"port": 5432, "targetPort": "tcp-postgresql"}],
        }
        snapshot["statefulset"][database] = {
            "selector": selector, "labels": selector["matchLabels"], "uid": f"sts-{database}",
            "replicas": 1,
        }
        snapshot["pod"][f"{database}-0"] = {
            "phase": "Running", "labels": selector["matchLabels"], "owner_uid": f"sts-{database}",
        }
    api_port = {"ports": [*open_pg["ports"], *[
        {"port": p, "protocol": "TCP"} for p in (4222, 6333, 6334, 7474, 7687)
    ]]}
    specs["omniscience-api-readnet"] = policy(named("omniscience"), [], [api_port])
    specs["portal-backend-isolation"] = policy(named("platform-portal"), [], [open_pg])
    specs["barbarossa-api-edge"] = policy({"matchLabels": {
        name: "barbarossa", component: "api",
    }}, [], [open_pg])
    specs["barbarossa-observer-isolation"] = policy({
        "matchLabels": {name: "barbarossa"},
        "matchExpressions": [{"key": component, "operator": "In", "values": ["observer", "migrate"]}],
    }, [], [open_pg])
    specs["omniscience-api-private-stores"] = policy(
        named("postgresql", "nats", "neo4j", "qdrant"),
        [boundary.rule("from", {"matchLabels": {name: "omniscience"}},
                       5432, 4222, 8222, 7687, 7474, 6333, 6334)], [dns],
    )
    specs["omniscience-api-neo4j-private"] = policy(
        {"matchLabels": {"app": "omniscience-neo4j"}},
        [boundary.rule("from", {"matchLabels": {name: "omniscience"}}, 7474, 7687)], [dns],
    )
    specs["portal-private-stores"] = policy(
        named("postgresql", "keycloak"),
        [boundary.rule("from", {"matchLabels": {name: "platform-portal"}}, 5432, 8080, 8081)],
        [open_pg],
    )
    for store in ("nats", "qdrant", "neo4j"):
        labels = ({"app": "omniscience-neo4j"} if store == "neo4j"
                  else {name: store, instance: "omniscience"})
        snapshot["pod"][f"omniscience-{store}-0"] = {"phase": "Running", "labels": labels}
    for deployment, owner, role, replicas in (
        ("omniscience-api", "omniscience", "api", 0),
        ("barbarossa-api", "barbarossa", "api", 1),
        ("barbarossa-observer", "barbarossa", "observer", 1),
        ("portal-backend", "platform-portal", "backend", 1),
        ("portal-frontend", "platform-portal", "frontend", 1),
    ):
        snapshot["deployment"][deployment] = {"replicas": replicas, "labels": {name: owner, component: role}}
    snapshot["ciliumclusterwidenetworkpolicy"] = {
        key: {"specs": [copy.deepcopy(spec)]} for key, spec in boundary.CLUSTER_POLICIES.items()
    }
    snapshot["networkpolicy"] = {
        key: {"uid": f"uid-{key}", "resourceVersion": "100", "spec": spec, "helm_release": "fixture"}
        for key, spec in specs.items()
    }
    return snapshot, specs


def test_network_union(legacy):
    snapshot, specs = legacy
    changes = boundary.plan(specs)
    after = {**specs, **changes}
    assert boundary.verify_union(snapshot, after) > 50

    owner, component = boundary.NAME, boundary.COMPONENT
    database = boundary.database("platform-portal")["matchLabels"]
    assert not boundary.allows(after, {owner: "platform-portal", component: "frontend"}, database, "egress", 5432)
    assert not boundary.allows(after, database, {owner: "omniscience", component: "migrate"}, "ingress", 5432)
    assert not boundary.allows(after, database, boundary.database("barbarossa")["matchLabels"], "egress", 5432)
    assert boundary.allows(after, database, {owner: "platform-portal", component: "bootstrap-mappings"}, "ingress", 5432)
    assert after["omniscience-api-neo4j-private"] == specs["omniscience-api-neo4j-private"]


@pytest.mark.parametrize("reintroduce", ["portal-private-stores", "omniscience-api-readnet", "barbarossa-postgres"])
def test_full_union_rejects_an_unreconciled_broad_policy(legacy, reintroduce):
    snapshot, specs = legacy
    after = {**specs, **boundary.plan(specs), reintroduce: specs[reintroduce]}
    with pytest.raises(RuntimeError, match="Unexpected (additive ingress policy|ingress verdict|egress verdict|PostgreSQL egress scope)"):
        boundary.verify_union(snapshot, after)


def test_unexpected_cilium_allow_halts(legacy):
    snapshot, specs = legacy
    snapshot["ciliumnetworkpolicy"]["new"] = {"specs": [{"endpointSelector": {}, "ingress": [{}]}]}
    with pytest.raises(RuntimeError, match="Unreviewed Cilium"):
        boundary.verify_union(snapshot, {**specs, **boundary.plan(specs)})


def test_dry_run_compares_admission_and_preserves_patch_identity(legacy):
    snapshot, specs = legacy
    changes = boundary.plan(specs)
    steps = list(boundary.operations(snapshot, changes))
    assert [step["action"] for step in steps] == ["create"] * 4 + ["patch"] * 9
    assert steps[-1]["name"] == "omniscience-api-private-stores"
    assert all([p["path"] for p in s["json_patch"]] ==
               ["/metadata/uid", "/metadata/resourceVersion", "/spec", "/spec"]
               for s in steps if s["action"] == "patch")

    class Admission:
        modified = False

        def kubectl(self, *args, input=None):
            assert "--dry-run=server" in args
            if args[0] == "create":
                obj = json.loads(input)
                if self.modified:
                    obj["spec"]["egress"] = [{}]
            else:
                name = args[2]
                patches = json.loads(args[args.index("-p") + 1])
                record = snapshot["networkpolicy"][name]
                obj = {
                    "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
                    "metadata": {
                        "name": name, "namespace": boundary.NAMESPACE, "uid": record["uid"],
                        "resourceVersion": record["resourceVersion"],
                        "annotations": {"meta.helm.sh/release-name": record["helm_release"]},
                    },
                    "spec": patches[-1]["value"],
                }
            return json.dumps(obj)

    assert boundary.dry_run(Admission(), steps, changes, snapshot) == {
        name: boundary.digest(spec) for name, spec in changes.items()
    }
    bad_admission = Admission()
    bad_admission.modified = True
    with pytest.raises(RuntimeError, match="Admission differs"):
        boundary.dry_run(bad_admission, steps, changes, snapshot)


def test_order_preserves_paths_at_each_prefix(legacy):
    snapshot, specs = legacy
    changes = boundary.plan(specs)
    steps = list(boundary.operations(snapshot, changes))
    boundary.verify_order(snapshot, specs, steps, changes)
    premature = next(step for step in steps if step["name"] == "barbarossa-api-edge")
    with pytest.raises(RuntimeError, match="would interrupt barbarossa/api"):
        boundary.verify_order(snapshot, specs, [premature, *steps], changes)


def test_cilium_projection_rejects_ambiguous_rule_sets():
    with pytest.raises(RuntimeError, match="both spec and specs"):
        boundary.projection("ciliumclusterwidenetworkpolicy", {
            "metadata": {"uid": "fixture", "resourceVersion": "1"},
            "spec": {"endpointSelector": {}, "ingress": []},
            "specs": [{"endpointSelector": {}, "ingress": [{}]}],
        })


def test_reject_specific_other_namespace_egress(legacy):
    snapshot, specs = legacy
    after = {**specs, **boundary.plan(specs)}
    after["other-namespace"] = {
        "podSelector": boundary.clients("platform-portal"),
        "policyTypes": ["Egress"],
        "egress": [{
            "to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "other"}}}],
            "ports": [boundary.PG_PORT],
        }],
    }
    with pytest.raises(RuntimeError, match="Unexpected PostgreSQL egress scope"):
        boundary.verify_union(snapshot, after)
