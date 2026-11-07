#!/usr/bin/env python3
"""Prepare and validate policy-only replacements for the canonical Frankfurt owners."""

import copy
import hashlib
import json
import os
import runpy
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIVATE = ROOT / ".local-observe/frankfurt-activation"
NAMESPACE = "splatform"
NAME = "app.kubernetes.io/name"
INSTANCE = "app.kubernetes.io/instance"
COMPONENT = "app.kubernetes.io/component"
PG_PORT = {"port": 5432, "protocol": "TCP"}
DNS_PORTS = [{"port": 53, "protocol": protocol} for protocol in ("UDP", "TCP")]
OWNERS = {
    "omniscience": ("omniscience-postgres", ("api", "migrate", "bootstrap")),
    "barbarossa": ("barbarossa-postgres", ("api", "migrate", "observer")),
    "platform-portal": ("portal-postgres", ("backend", "migrate", "bootstrap-mappings")),
}
CALLER_POLICIES = {
    "omniscience-api-readnet": "omniscience",
    "barbarossa-api-edge": "barbarossa",
    "barbarossa-observer-isolation": "barbarossa",
    "portal-backend-isolation": "platform-portal",
}
STORES = {"nats": (4222, 8222), "qdrant": (6333, 6334), "neo4j": (7474, 7687)}
CLUSTER_POLICIES = {
    "app-namespaces-internal-traffic": {
        "endpointSelector": {"matchExpressions": [{
            "key": "k8s:io.kubernetes.pod.namespace", "operator": "In",
            "values": ["stage-casino", "stage-core", "stage-crm", "stage-payment"],
        }]},
    },
    "app-namespaces-internet-egress": {
        "endpointSelector": {"matchExpressions": [{
            "key": "k8s:io.kubernetes.pod.namespace", "operator": "In",
            "values": ["stage-casino", "stage-core", "stage-crm", "stage-payment"],
        }]},
    },
    "default-deny-all": {
        "description": "Baseline default-deny with bootstrap and DNS carve-outs",
        "endpointSelector": {},
        "ingress": [{"fromEntities": ["host", "remote-node", "kube-apiserver"]}],
        "egress": [
            {"toEntities": ["host", "remote-node", "kube-apiserver"]},
            {"toEndpoints": [{"matchLabels": {
                "k8s-app": "kube-dns", "k8s:io.kubernetes.pod.namespace": "kube-system",
            }}], "toPorts": [{"ports": [{"port": "53", "protocol": p} for p in ("UDP", "TCP")]}]},
        ],
    },
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def labels_selector(**labels):
    return {"matchLabels": labels}


def database(owner):
    return labels_selector(**{NAME: "postgresql", INSTANCE: owner, COMPONENT: "primary"})


def clients(owner):
    return {
        **labels_selector(**{NAME: owner}),
        "matchExpressions": [{"key": COMPONENT, "operator": "In", "values": list(OWNERS[owner][1])}],
    }


def rule(peer_key, selector, *ports):
    return {peer_key: [{"podSelector": selector}],
            "ports": [{"port": port, "protocol": "TCP"} for port in ports]}


def matches(selector, labels):
    require(set(selector) <= {"matchLabels", "matchExpressions"}, "Unexpected selector fields")
    if any(labels.get(key) != value for key, value in selector.get("matchLabels", {}).items()):
        return False
    for expr in selector.get("matchExpressions", []):
        key, operator = expr["key"], expr["operator"]
        if operator == "In" and labels.get(key) not in expr["values"]:
            return False
        if operator == "NotIn" and labels.get(key) in expr["values"]:
            return False
        if operator == "Exists" and key not in labels:
            return False
        if operator == "DoesNotExist" and key in labels:
            return False
        require(operator in {"In", "NotIn", "Exists", "DoesNotExist"}, "Unexpected selector operator")
    return True


def allows(policies, endpoint, peer, direction, port, namespace=NAMESPACE):
    """Evaluate ordinary pod traffic over the verified Cilium default-deny baseline."""
    selected = [spec for spec in policies.values() if direction.capitalize() in spec["policyTypes"]
                and matches(spec["podSelector"], endpoint)]
    peer_key = {"ingress": "from", "egress": "to"}[direction]
    for spec in selected:
        for entry in spec.get(direction, []):
            ports = entry.get("ports", [])
            if ports and not any(port_matches(p, port) for p in ports):
                continue
            if not entry.get(peer_key):
                return True
            for candidate in entry[peer_key]:
                require(set(candidate) <= {"namespaceSelector", "podSelector"},
                        "Unsupported NetworkPolicy peer in checked union")
                if "namespaceSelector" in candidate:
                    if not matches(candidate["namespaceSelector"], {"kubernetes.io/metadata.name": namespace}):
                        continue
                elif namespace != NAMESPACE:
                    continue
                if matches(candidate.get("podSelector", {}), peer):
                    return True
    return False


def port_matches(port_rule, port):
    if port_rule.get("protocol", "TCP") != "TCP":
        return False
    start = port_rule.get("port", port)
    require(isinstance(start, int), "Named port in checked union requires explicit evaluation")
    return start <= port <= port_rule.get("endPort", start)


def remove_open_postgres(spec, direction):
    """Only edit the live single, unrestricted ports rule."""
    rules = spec[direction]
    require(len(rules) == 1 and set(rules[0]) == {"ports"}
            and rules[0]["ports"].count(PG_PORT) == 1, "Unrecognized open PostgreSQL rule")
    rules[0]["ports"].remove(PG_PORT)
    require(rules[0]["ports"], "Refusing to turn a filtered rule into an all-ports rule")


def plan(policies):
    changes = {}
    for owner, (name, _) in OWNERS.items():
        spec = policies[name]
        require(spec == {
            "podSelector": database(owner), "policyTypes": ["Ingress", "Egress"],
            "ingress": [{"ports": [PG_PORT]}], "egress": [{}],
        }, f"{name} is outside the expected legacy policy state")
        changes[name] = {
            "podSelector": database(owner), "policyTypes": ["Ingress", "Egress"],
            "ingress": [rule("from", clients(owner), 5432)],
            "egress": [{"ports": DNS_PORTS}],
        }
    for name, owner in CALLER_POLICIES.items():
        spec = copy.deepcopy(policies[name])
        allowed_components = OWNERS[owner][1]
        for candidate in ({"x": "outsider"}, {NAME: owner}, {NAME: owner, COMPONENT: "frontend"}):
            if name.startswith("barbarossa"):
                require(not matches(spec["podSelector"], candidate), f"{name} selector widened")
        require(any(matches(spec["podSelector"], {NAME: owner, COMPONENT: component})
                    for component in allowed_components), f"{name} has an unexpected caller selector")
        remove_open_postgres(spec, "egress")
        changes[name] = spec
    for owner, (name, _) in OWNERS.items():
        new = name.removesuffix("-postgres") + "-postgresql-clients"
        require(new not in policies, f"{new} already exists")
        changes[new] = {
            "podSelector": clients(owner), "policyTypes": ["Egress"],
            "egress": [rule("to", database(owner), 5432)],
        }

    name = "portal-private-stores"
    portal = copy.deepcopy(policies[name])
    require(portal["podSelector"] == {"matchExpressions": [
        {"key": NAME, "operator": "In", "values": ["postgresql", "keycloak"]},
    ]}, f"{name} selector drifted")
    portal["podSelector"] = labels_selector(**{NAME: "keycloak"})
    require(len(portal["ingress"]) == 1 and PG_PORT in portal["ingress"][0]["ports"],
            f"{name} ingress drifted")
    portal["ingress"][0]["ports"].remove(PG_PORT)
    require(portal["ingress"][0]["ports"], f"{name} retained no ingress ports")
    changes[name] = portal

    name = "omniscience-api-private-stores"
    old_store = {
        "podSelector": {"matchExpressions": [
            {"key": NAME, "operator": "In", "values": ["postgresql", "nats", "neo4j", "qdrant"]},
        ]},
        "policyTypes": ["Ingress", "Egress"],
        "ingress": [rule("from", labels_selector(**{NAME: "omniscience"}),
                         5432, 4222, 8222, 7687, 7474, 6333, 6334)],
        "egress": [{"ports": DNS_PORTS}],
    }
    require(policies[name] == old_store, f"{name} differs from reviewed legacy rules")
    for store in ("nats", "qdrant"):
        new = name if store == "nats" else "omniscience-qdrant-private"
        require(new == name or new not in policies, f"{new} already exists")
        changes[new] = {
            "podSelector": labels_selector(**{NAME: store, INSTANCE: "omniscience"}),
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [rule("from", labels_selector(**{NAME: "omniscience"}), *STORES[store])],
            "egress": [{"ports": DNS_PORTS}],
        }
    return changes


def verify_cilium(snapshot, endpoints):
    global_policies = snapshot["ciliumclusterwidenetworkpolicy"]
    require(global_policies.keys() == CLUSTER_POLICIES.keys(), "Unexpected clusterwide Cilium policy set")
    for name, baseline in CLUSTER_POLICIES.items():
        specs = global_policies[name]["specs"]
        require(len(specs) == 1, f"Unexpected multiple Cilium specs for {name}")
        if name == "default-deny-all":
            require(specs[0] == baseline, "Clusterwide default-deny exceptions drifted")
        else:
            require(specs[0]["endpointSelector"] == baseline["endpointSelector"]
                    and not set(specs[0]) - {"description", "endpointSelector", "ingress", "egress"},
                    f"Clusterwide policy scope drifted for {name}")
    for name, record in snapshot["ciliumnetworkpolicy"].items():
        for spec in record["specs"]:
            require(spec.keys() == {"endpointSelector", "ingressDeny", "egressDeny"}
                    and spec["ingressDeny"] == [{"fromEntities": ["all"]}]
                    and spec["egressDeny"] == [{"toEntities": ["all"]}]
                    and all(not matches(spec["endpointSelector"], labels) for labels in endpoints),
                    f"Unreviewed Cilium scope or overlap for {name}")


def verify_union(snapshot, policies):
    pods = {name: record["labels"] for name, record in snapshot["pod"].items()}
    services = snapshot["service"]
    expected_databases = {}
    service_ips = set()
    for owner, (name, _) in OWNERS.items():
        db = database(owner)["matchLabels"]
        require(services[name]["selector"] == db
                and services[name]["postgres_port"] == [{"port": 5432, "targetPort": "tcp-postgresql"}],
                f"Unexpected selector or port on {name} Service")
        ips = services[name]["cluster_ips"]
        require(ips and "None" not in ips and not service_ips.intersection(ips),
                f"Missing or overlapping ClusterIP for {name}")
        service_ips.update(ips)
        require(snapshot["statefulset"][name]["selector"] == database(owner)
                and snapshot["statefulset"][name]["replicas"] == 1
                and matches(database(owner), snapshot["statefulset"][name]["labels"]),
                f"Unexpected {name} StatefulSet identity")
        require({pod for pod, labels in pods.items() if matches(database(owner), labels)}
                == {f"{name}-0"}, f"Unexpected pod membership for {name}")
        require(snapshot["pod"][f"{name}-0"]["phase"] == "Running"
                and snapshot["pod"][f"{name}-0"]["owner_uid"] == snapshot["statefulset"][name]["uid"],
                f"Unexpected running StatefulSet member for {name}")
        expected_databases[owner] = db
    require({name for name, labels in pods.items() if labels.get(NAME) == "postgresql"}
            == {f"{name}-0" for name, _ in OWNERS.values()}, "Unexpected PostgreSQL pod or transition")
    require(snapshot["deployment"]["omniscience-api"]["replicas"] in (0, 1),
            "Unexpected Omniscience API replica count")
    for name, owner, component in (
        ("omniscience-api", "omniscience", "api"),
        ("barbarossa-api", "barbarossa", "api"),
        ("barbarossa-observer", "barbarossa", "observer"),
        ("portal-backend", "platform-portal", "backend"),
        ("portal-frontend", "platform-portal", "frontend"),
    ):
        require(matches(labels_selector(**{NAME: owner, COMPONENT: component}),
                        snapshot["deployment"][name]["labels"]), f"Unexpected live labels on {name}")
    for name in snapshot["cronjob"]:
        require(not name.endswith("-pgdumpall"), "Unexpected backup CronJob needs its own policy")

    all_endpoints = {
        **pods,
        **{f"template/{kind}/{name}": record["labels"]
           for kind in ("deployment", "statefulset", "job", "cronjob")
           for name, record in snapshot[kind].items()},
        "anonymous": {},
    }
    for owner, (_, components) in OWNERS.items():
        for component in (*components, "unknown-component", "frontend", "keycloak"):
            all_endpoints[f"synthetic/{owner}/{component}"] = {NAME: owner, COMPONENT: component}
        all_endpoints[f"synthetic/{owner}/no-component"] = {NAME: owner}
    verify_cilium(snapshot, [labels for labels in all_endpoints.values()
                            if labels.get(NAME) in OWNERS or labels.get(NAME) == "postgresql"
                            or labels.get(INSTANCE) == "omniscience" or labels.get("app") == "omniscience-neo4j"])

    for peer_name, peer in all_endpoints.items():
        if peer.get(NAME) in OWNERS or peer.get(NAME) == "postgresql":
            require_scoped_postgres_egress(policies, peer_name, peer)

    cases = 0
    for owner, db in expected_databases.items():
        name = OWNERS[owner][0]
        require({key for key, spec in policies.items() if "Ingress" in spec["policyTypes"]
                 and matches(spec["podSelector"], db)} == {name}, f"Unexpected additive ingress policy on {name}")
        for peer_name, peer in all_endpoints.items():
            expected = matches(clients(owner), peer)
            require(allows(policies, db, peer, "ingress", 5432) == expected,
                    f"Unexpected ingress verdict: {peer_name} to {name}")
            if peer.get(NAME) in OWNERS or peer.get(NAME) == "postgresql":
                require(allows(policies, peer, db, "egress", 5432) == expected,
                        f"Unexpected egress verdict: {peer_name} to {name}")
                require(not allows(policies, peer, db, "egress", 5432, namespace="outside"),
                        f"Unexpected cross-namespace egress: {peer_name}")
            require(not allows(policies, db, peer, "ingress", 5432, namespace="outside"),
                    f"Unexpected cross-namespace ingress to {name}")
            cases += 1

    return cases + verify_store_paths(snapshot, policies)


def require_scoped_postgres_egress(policies, endpoint_name, labels):
    owner = labels.get(NAME)
    allowed = (rule("to", database(owner), 5432)
               if owner in OWNERS and matches(clients(owner), labels) else None)
    for name, spec in policies.items():
        if "Egress" not in spec["policyTypes"] or not matches(spec["podSelector"], labels):
            continue
        for entry in spec.get("egress", []):
            if not entry.get("ports") or any(port_matches(p, 5432) for p in entry["ports"]):
                require(entry == allowed, f"Unexpected PostgreSQL egress scope: {name} selects {endpoint_name}")


def verify_store_paths(snapshot, policies):
    api = snapshot["deployment"]["omniscience-api"]["labels"]
    pods = {name: record["labels"] for name, record in snapshot["pod"].items()}
    cases = 0
    for store, ports in STORES.items():
        selector = (labels_selector(app="omniscience-neo4j") if store == "neo4j"
                    else labels_selector(**{NAME: store, INSTANCE: "omniscience"}))
        require({name for name, labels in pods.items() if matches(selector, labels)}
                == {f"omniscience-{store}-0"}, f"Unexpected {store} Pod membership")
        endpoint = pods[f"omniscience-{store}-0"]
        for port in ports:
            require(allows(policies, endpoint, api, "ingress", port)
                    and allows(policies, api, endpoint, "egress", port) == (port != 8222),
                    f"Omniscience {store}:{port} connectivity changed")
            cases += 1
    return cases


def projection(kind, obj):
    metadata, spec = obj["metadata"], obj.get("spec", {})
    record = {"uid": metadata["uid"]}
    if kind in ("networkpolicy", "ciliumnetworkpolicy", "ciliumclusterwidenetworkpolicy"):
        record["resourceVersion"] = metadata["resourceVersion"]
        if kind == "networkpolicy":
            record["spec"] = spec
            record["helm_release"] = metadata.get("annotations", {}).get("meta.helm.sh/release-name")
        else:
            require(not (obj.get("spec") and obj.get("specs")), "Cilium policy uses both spec and specs")
            record["specs"] = [obj["spec"]] if obj.get("spec") else obj.get("specs", [])
            require(record["specs"], "Cilium policy has no rules")
        return record
    if kind == "pod":
        record.update(
            labels=metadata.get("labels", {}),
            phase=obj["status"]["phase"],
            owner_uid=next((ref["uid"] for ref in metadata.get("ownerReferences", [])
                            if ref.get("controller")), None),
        )
    elif kind == "service":
        record.update(
            selector=spec.get("selector"),
            cluster_ips=spec.get("clusterIPs", []),
            postgres_port=[{key: port.get(key) for key in ("port", "targetPort")}
                           for port in spec.get("ports", []) if port["port"] == 5432
                           and port.get("protocol", "TCP") == "TCP"],
        )
    else:
        template = (spec["jobTemplate"]["spec"] if kind == "cronjob" else spec)["template"]
        record["labels"] = template.get("metadata", {}).get("labels", {})
        if kind in ("statefulset", "deployment"):
            record["selector"] = spec["selector"]
            record["replicas"] = spec["replicas"]
    return record


def capture(cluster):
    return {
        kind: {obj["metadata"]["name"]: projection(kind, obj)
               for obj in json.loads(cluster.kubectl("get", kind, "-o", "json"))["items"]}
        for kind in ("networkpolicy", "ciliumnetworkpolicy", "ciliumclusterwidenetworkpolicy",
                     "pod", "service", "deployment", "statefulset", "job", "cronjob")
    }


def reviewed_sources():
    paths = {
        "Omniscience": ("eks-direct-collectors", "omniscience"),
        "Barbarossa": ("eks-platform-activation", "barbarossa"),
        "platform-portal": ("eks-platform-activation", "platform-portal"),
    }
    receipt = ROOT / ("docs/synchronized-platform/releases/management-platform-frankfurt-v1/"
                      "source-checks/postgres-network-boundaries.json")
    historical = json.loads(receipt.read_text())["files"]
    evidence = {}
    for repo, (worktree, owner) in paths.items():
        chart = ROOT.parents[2] / repo / ".worktrees" / worktree / "deploy/helm" / owner
        for relative in ("values.yaml", "templates/networkpolicy.yaml"):
            data = (chart / relative).read_bytes()
            key = f"{repo}/deploy/helm/{owner}/{relative}"
            actual = hashlib.sha256(data).hexdigest()
            evidence[key] = {"current_sha256": actual, "historical_sha256": historical[key]}
            if relative == "values.yaml":
                settings = yaml.safe_load(data)["postgresql"]
                primary = settings["primary"]["networkPolicy"]
                require(all(primary.get(key) is False for key in (
                    "allowExternal", "allowExternalEgress", "addExternalClientAccess",
                )) and primary["extraIngress"] == [rule("from", clients(owner), 5432)],
                        f"Owner source disagrees with proposed PostgreSQL ingress: {owner}")
            else:
                text = data.decode()
                require(all(component in text for component in OWNERS[owner][1])
                        and "postgresql-clients" in text and "postgresql.commonLabels" in text,
                        f"Owner source disagrees with proposed PostgreSQL egress: {owner}")
    return evidence


def operations(snapshot, changes):
    baseline = snapshot["networkpolicy"]
    # Stage equivalent narrow grants before editing the policies currently providing those grants.
    order = sorted(changes, key=lambda name: name in baseline)
    order.remove("omniscience-api-private-stores")
    order.append("omniscience-api-private-stores")
    for name in order:
        spec = changes[name]
        if name not in baseline:
            yield {"action": "create", "name": name, "object": {
                "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
                "metadata": {"name": name, "namespace": NAMESPACE}, "spec": spec,
            }}
            continue
        old = baseline[name]
        yield {"action": "patch", "name": name, "json_patch": [
            {"op": "test", "path": "/metadata/uid", "value": old["uid"]},
            {"op": "test", "path": "/metadata/resourceVersion", "value": old["resourceVersion"]},
            {"op": "test", "path": "/spec", "value": old["spec"]},
            {"op": "replace", "path": "/spec", "value": spec},
        ]}


def verify_order(snapshot, policies, steps, changes):
    """Each prefix retains current required pod paths even while restrictions are incomplete."""
    current = dict(policies)
    keycloak_paths = [
        (endpoint, peer, port)
        for endpoint in ({NAME: "keycloak"}, {NAME: "platform-portal", COMPONENT: "keycloak"})
        for peer in ({NAME: "keycloak"}, {NAME: "platform-portal", COMPONENT: "backend"})
        for port in (8080, 8081)
        if allows(policies, endpoint, peer, "ingress", port)
    ]
    for step in steps:
        name = step["name"]
        current[name] = changes[name]
        for owner, (db_name, components) in OWNERS.items():
            db = database(owner)["matchLabels"]
            for component in components:
                peer = {NAME: owner, COMPONENT: component}
                require(allows(current, peer, db, "egress", 5432)
                        and allows(current, db, peer, "ingress", 5432),
                        f"{name} would interrupt {owner}/{component} to {db_name}")
        verify_store_paths(snapshot, current)
        for endpoint, peer, port in keycloak_paths:
            require(allows(current, endpoint, peer, "ingress", port),
                    f"{name} would interrupt existing Keycloak ingress on {port}")


def dry_run(cluster, steps, changes, snapshot):
    admitted = {}
    for step in steps:
        name = step["name"]
        if step["action"] == "create":
            result = cluster.kubectl("create", "--dry-run=server", "-f", "-", "-o", "json",
                                     input=json.dumps(step["object"]))
        else:
            result = cluster.kubectl("patch", "networkpolicy", name, "--dry-run=server",
                                     "--type=json", "-p", json.dumps(step["json_patch"]), "-o", "json")
        obj = json.loads(result)
        require(obj["kind"] == "NetworkPolicy" and obj["apiVersion"] == "networking.k8s.io/v1"
                and obj["metadata"]["name"] == name and obj["metadata"]["namespace"] == NAMESPACE
                and obj["spec"] == changes[name], f"Admission differs for {name}")
        if step["action"] == "patch":
            old = snapshot["networkpolicy"][name]
            current = projection("networkpolicy", obj)
            require(current["uid"] == old["uid"] and current["helm_release"] == old["helm_release"],
                    f"Admission changed identity or ownership for {name}")
        admitted[name] = digest(obj["spec"])
    return admitted


def write_private(snapshot, steps, changes, receipt):
    output = Path(tempfile.mkdtemp(prefix="postgres-boundaries-", dir=PRIVATE))
    for name, obj in (
        ("snapshot.json", snapshot),
        ("operations.json", steps),
        ("planned-specs.json", changes),
        ("receipt.json", receipt),
    ):
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(obj, stream, indent=2, sort_keys=True)
            stream.write("\n")
    return output


def prepare(cluster):
    evidence = reviewed_sources()
    before = capture(cluster)
    policies = {name: item["spec"] for name, item in before["networkpolicy"].items()}
    changes = plan(policies)
    cases = verify_union(before, {**policies, **changes})
    steps = list(operations(before, changes))
    verify_order(before, policies, steps, changes)
    admitted = dry_run(cluster, steps, changes, before)
    require(capture(cluster) == before, "Live policy or workload identity changed during preparation")
    require(reviewed_sources() == evidence, "Owner chart sources changed during preparation")
    receipt = {
        "status": "prepared-server-dry-run-only",
        "context": "nonprod-euc1",
        "namespace": NAMESPACE,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_sha256": digest(before),
        "operations_sha256": digest(steps),
        "planned_specs_sha256": digest(changes),
        "source_hashes": evidence,
        "admitted_spec_sha256": admitted,
        "union_checks": cases,
        "patches": sum(step["action"] == "patch" for step in steps),
        "creates": sum(step["action"] == "create" for step in steps),
        "traffic_checks": "pending",
    }
    return write_private(before, steps, changes, receipt)


if __name__ == "__main__":
    try:
        cluster_class = runpy.run_path(str(HERE.parent / "omniscience-storage/recover.py"))["Cluster"]
        print(prepare(cluster_class()))
    except subprocess.CalledProcessError as error:
        # Kubernetes command arguments and raw diagnostics can contain object data.
        raise SystemExit(f"Verified Kubernetes/AWS command failed (exit {error.returncode})") from None
    except (KeyError, RuntimeError) as error:
        raise SystemExit(f"Preparation halted: {error}") from None
