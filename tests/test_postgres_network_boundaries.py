"""Render the owner charts and check same-namespace NetworkPolicy unions.

Set POSTGRES_BOUNDARY_CHART_ROOTS to the three chart directories separated by
os.pathsep. Optionally set POSTGRES_BOUNDARY_DEPENDENCIES to a directory of
pre-fetched, versioned Helm chart archives. Otherwise Helm pulls the versions
from the owner Chart.yaml files. All rendered credentials are test fixtures.
"""
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

CLIENTS = {
    "omniscience": ("api", "migrate", "bootstrap"),
    "barbarossa": ("api", "migrate", "observer"),
    "platform-portal": ("backend", "migrate", "bootstrap-mappings"),
}
STORES = {
    "omniscience": "omniscience-postgres",
    "barbarossa": "barbarossa-postgres",
    "platform-portal": "portal-postgres",
}
OPTIONS = {
    "omniscience": {"nats": {"enabled": True}, "neo4j": {"enabled": True}, "qdrant": {"enabled": True}},
    "platform-portal": {"oidc": {"embeddedKeycloak": {"enabled": True}}},
}
NAMESPACE = "splatform"


def helm(*args):
    return subprocess.run(
        ["helm", *map(str, args)], check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture(scope="module")
def charts():
    configured = os.environ.get("POSTGRES_BOUNDARY_CHART_ROOTS")
    if not configured:
        pytest.skip("set POSTGRES_BOUNDARY_CHART_ROOTS to the three owner chart directories")
    assert shutil.which("helm"), "helm is required for the network boundary regression"
    sources = dict(
        (yaml.safe_load((path / "Chart.yaml").read_text())["name"], path)
        for path in map(Path, configured.split(os.pathsep))
    )
    assert sources.keys() == CLIENTS.keys()
    archive_dir = os.environ.get("POSTGRES_BOUNDARY_DEPENDENCIES")

    # Keep downloaded dependencies and generated fixture charts inside this project.
    with TemporaryDirectory(prefix=".postgres-boundary-", dir=Path(__file__).parents[1]) as directory:
        stage = Path(directory)
        umbrella = stage / "umbrella"
        umbrella_charts = umbrella / "charts"
        umbrella_charts.mkdir(parents=True)
        cache = stage / "dependencies"
        cache.mkdir()
        for name, source in sources.items():
            chart = umbrella_charts / name
            chart.mkdir()
            for filename in ("Chart.yaml", "values.yaml"):
                shutil.copyfile(source / filename, chart / filename)
            shutil.copytree(source / "templates", chart / "templates")
            dependencies = chart / "charts"
            dependencies.mkdir()
            for dep in yaml.safe_load((chart / "Chart.yaml").read_text())["dependencies"]:
                dep_name, version, repo = dep["name"], dep["version"], dep["repository"]
                archive_name = f"{dep_name}-{version}.tgz"
                archive = Path(archive_dir) / archive_name if archive_dir else cache / archive_name
                if not archive_dir and not archive.exists():
                    if repo == "https://charts.bitnami.com/bitnami":
                        helm("pull", f"oci://registry-1.docker.io/bitnamicharts/{dep_name}",
                             "--version", version, "--destination", cache)
                    else:
                        helm("pull", dep_name, "--repo", repo, "--version", version,
                             "--destination", cache)
                shutil.copyfile(archive, dependencies / archive_name)
        (umbrella / "Chart.yaml").write_text(yaml.safe_dump({
            "apiVersion": "v2", "name": "postgres-boundary", "version": "0.1.0",
        }))
        yield stage, umbrella


def render(release, chart, values, stage):
    fixture = stage / "fixture-values.yaml"
    fixture.write_text(yaml.safe_dump(values))
    # Read only network-relevant objects from the captured Helm output.
    manifests = helm("template", release, chart, "--namespace", NAMESPACE, "--values", fixture)
    return [
        doc for doc in yaml.safe_load_all(manifests)
        if doc and doc["kind"] in {"Deployment", "Job", "StatefulSet", "NetworkPolicy", "Service", "ConfigMap", "CronJob"}
    ]


def matches(selector, labels):
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
        assert operator in {"In", "NotIn", "Exists", "DoesNotExist"}
    return True


def allows(policies, endpoint, peer, direction, port):
    policy_type = direction.capitalize()
    peer_key = {"ingress": "from", "egress": "to"}[direction]
    selected = [
        spec for spec in policies
        if policy_type in spec["policyTypes"] and matches(spec["podSelector"], endpoint)
    ]
    if not selected:
        return True
    for spec in selected:
        for rule in spec.get(direction, []):
            if rule.get("ports") and not any(
                port_rule.get("protocol", "TCP") == "TCP"
                and port_rule.get("port", port) <= port
                <= port_rule.get("endPort", port_rule.get("port", port))
                for port_rule in rule["ports"]
            ):
                continue
            if not rule.get(peer_key) or any(
                "ipBlock" not in candidate
                and matches(candidate.get("namespaceSelector", {}), {"kubernetes.io/metadata.name": NAMESPACE})
                and matches(candidate.get("podSelector", {}), peer)
                for candidate in rule[peer_key]
            ):
                return True
    return False


def values(owner, bundled=True):
    return {
        "secrets": {"existingSecret": "network-boundary-test"},
        "postgresql": {"enabled": bundled},
        **OPTIONS.get(owner, {}),
    }


@pytest.mark.parametrize("shared_release", [False, True], ids=["independent", "umbrella"])
def test_postgres_network_policy_union(charts, shared_release):
    stage, umbrella = charts
    if shared_release:
        docs = render("shared-release", umbrella, {owner: values(owner) for owner in CLIENTS}, stage)
    else:
        docs = [
            doc for owner in CLIENTS
            for doc in render(owner, umbrella / "charts" / owner, values(owner), stage)
        ]

    pods = {
        doc["metadata"]["name"]: doc["spec"]["template"]["metadata"]["labels"]
        for doc in docs if doc["kind"] in {"Deployment", "Job", "StatefulSet"}
    }
    policies = [doc["spec"] for doc in docs if doc["kind"] == "NetworkPolicy"]
    for pod, labels in pods.items():
        owner = labels.get("app.kubernetes.io/name")
        if owner not in CLIENTS:
            continue
        component = labels.get("app.kubernetes.io/component")
        for db_owner, db in STORES.items():
            expected = owner == db_owner and component in CLIENTS[owner]
            egress = allows(policies, labels, pods[db], "egress", 5432)
            ingress = allows(policies, pods[db], labels, "ingress", 5432)
            assert (egress and ingress) is expected, f"{pod} -> {db}: {egress=}, {ingress=}"
            if not expected:
                assert not egress and not ingress, f"{pod} -> {db}: expected both directions to deny"

    for owner, components in CLIENTS.items():
        assert set(components) <= {
            labels.get("app.kubernetes.io/component")
            for labels in pods.values() if labels.get("app.kubernetes.io/name") == owner
        }
    assert "portal-frontend" in pods
    for owner, db in STORES.items():
        service = next(
            doc for doc in docs if doc["kind"] == "Service" and doc["metadata"]["name"] == db
        )
        selector = {"matchLabels": service["spec"]["selector"]}
        assert {pod for pod, labels in pods.items() if matches(selector, labels)} == {db}
        statefulset = next(
            doc for doc in docs if doc["kind"] == "StatefulSet" and doc["metadata"]["name"] == db
        )
        assert statefulset["spec"]["selector"] == selector
        if not shared_release:
            # These match the canonical independent release selectors before the change.
            assert selector["matchLabels"] == {
                "app.kubernetes.io/name": "postgresql",
                "app.kubernetes.io/instance": owner,
                "app.kubernetes.io/component": "primary",
            }
        for db_peer in STORES.values():
            if db_peer != db:
                assert not allows(policies, pods[db], pods[db_peer], "egress", 5432)
                assert not allows(policies, pods[db_peer], pods[db], "ingress", 5432)

    for store, ports in {
        "omniscience-nats": (4222, 8222),
        "omniscience-neo4j": (7474, 7687),
        "omniscience-qdrant": (6333, 6334),
    }.items():
        for port in ports:
            assert allows(policies, pods[store], pods["omniscience-api"], "ingress", port)
            if port != 8222:  # The existing NATS monitoring ingress has no API egress counterpart.
                assert allows(policies, pods["omniscience-api"], pods[store], "egress", port)


def test_external_postgres_egress_stays_available_to_database_callers(charts):
    stage, umbrella = charts
    docs = render(
        "shared-release", umbrella,
        {owner: values(owner, bundled=False) for owner in CLIENTS}, stage,
    )
    policies = [doc["spec"] for doc in docs if doc["kind"] == "NetworkPolicy"]
    external_database = {}
    for doc in docs:
        if doc["kind"] not in {"Deployment", "Job"}:
            continue
        labels = doc["spec"]["template"]["metadata"]["labels"]
        owner = labels.get("app.kubernetes.io/name")
        if owner in CLIENTS:
            assert allows(policies, labels, external_database, "egress", 5432) is (
                labels.get("app.kubernetes.io/component") in CLIENTS[owner]
            ), doc["metadata"]["name"]


def test_optional_keycloak_database_is_separate_from_portal_database(charts):
    stage, umbrella = charts
    portal_values = values("platform-portal")
    portal_values["oidc"]["embeddedKeycloak"]["enabled"] = False
    portal_values["keycloak"] = {"enabled": True}
    docs = render("platform-portal", umbrella / "charts" / "platform-portal", portal_values, stage)
    pods = {
        doc["metadata"]["name"]: doc["spec"]["template"]["metadata"]["labels"]
        for doc in docs if doc["kind"] in {"Deployment", "StatefulSet"}
    }
    config = next(
        doc["data"] for doc in docs if doc["kind"] == "ConfigMap" and "KC_DB_URL" in doc["data"]
    )
    db_url = config["KC_DB_URL"]
    assert db_url.startswith("jdbc:postgresql://")
    keycloak_db = db_url.removeprefix("jdbc:postgresql://").split(":", 1)[0]
    assert keycloak_db == "platform-portal-postgresql"
    portal_db = STORES["platform-portal"]
    assert portal_db != keycloak_db
    for db in (portal_db, keycloak_db):
        service = next(
            doc for doc in docs if doc["kind"] == "Service" and doc["metadata"]["name"] == db
        )
        selector = {"matchLabels": service["spec"]["selector"]}
        assert {pod for pod, labels in pods.items() if matches(selector, labels)} == {db}

    policies = [doc["spec"] for doc in docs if doc["kind"] == "NetworkPolicy"]
    keycloak = pods["portal-keycloak"]
    assert allows(policies, keycloak, pods[keycloak_db], "egress", 5432)
    assert allows(policies, pods[keycloak_db], keycloak, "ingress", 5432)
    assert not allows(policies, pods[portal_db], keycloak, "ingress", 5432)
    assert allows(policies, pods[portal_db], pods["portal-backend"], "ingress", 5432)
    for caller in ("portal-backend", "portal-frontend", portal_db):
        assert not allows(policies, pods[keycloak_db], pods[caller], "ingress", 5432)


def test_bundled_database_backup_reaches_only_its_own_database(charts):
    stage, umbrella = charts
    settings = {owner: values(owner) for owner in CLIENTS}
    for owner_values in settings.values():
        owner_values["postgresql"]["backup"] = {"enabled": True}
    docs = render("shared-release", umbrella, settings, stage)
    databases = {
        doc["metadata"]["name"]: doc["spec"]["template"]["metadata"]["labels"]
        for doc in docs if doc["kind"] == "StatefulSet" and doc["metadata"]["name"] in STORES.values()
    }
    assert databases.keys() == set(STORES.values())
    policies = [doc["spec"] for doc in docs if doc["kind"] == "NetworkPolicy"]
    for db in databases:
        cronjob = next(
            doc for doc in docs
            if doc["kind"] == "CronJob" and doc["metadata"]["name"] == f"{db}-pgdumpall"
        )
        backup = cronjob["spec"]["jobTemplate"]["spec"]["template"]
        backup_labels = backup["metadata"]["labels"]
        env = {var["name"]: var.get("value") for var in backup["spec"]["containers"][0]["env"]}
        assert env["PGHOST"] == db
        assert allows(policies, backup_labels, databases[db], "egress", 5432)
        for peer, labels in databases.items():
            assert allows(policies, labels, backup_labels, "ingress", 5432) is (peer == db)
