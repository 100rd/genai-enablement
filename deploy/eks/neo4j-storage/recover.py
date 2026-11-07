#!/usr/bin/env python3
"""Migrate the verified empty Omniscience graph to retained EBS storage."""

import argparse
import base64
import json
import re
import runpy
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = runpy.run_path(str(HERE.parent / "omniscience-storage" / "recover.py"))
Cluster = SHARED["Cluster"]
NAMESPACE = SHARED["NAMESPACE"]
PRIVATE = SHARED["PRIVATE"]
require = SHARED["require"]
release_pin = SHARED["release_pin"]
decode_release = SHARED["decode_release"]
restore_chart = SHARED["restore_chart"]
helm_context = SHARED["helm_context"]
verify_endpoint = SHARED["verify_endpoint"]
write_private_json = SHARED["write_private_json"]
read_private_json = SHARED["read_private_json"]
delete_owned = SHARED["delete_owned"]
pause_check = SHARED["paused"]
EXPECTED_HOOKS = SHARED["EXPECTED_HOOKS"]

SOURCE = "omniscience-neo4j"
STAGE = "omniscience-neo4j-restore"
CLAIM = "omniscience-neo4j-data-retained"
DIGEST = "sha256:7dbd307cc8f35d6a061cf71659d3d8f783c3db9e8c2f5bb9d54f77921931952a"
IMAGE = f"docker.io/library/neo4j@{DIGEST}"
PROBE_IMAGE = (
    "120736097561.dkr.ecr.eu-central-1.amazonaws.com/genai-enablement/omniscience-api"
    "@sha256:dc6aafe29eb578d7dcb65f41487b185690e1bc652b16aea284deab7fbcd252e0"
)
PROBE = "omniscience-neo4j-storage-probe"
POLICIES = ("omniscience-neo4j-storage-ingress", "omniscience-neo4j-storage-egress")
RECEIPTS = PRIVATE / "frankfurt-activation"
BOOTSTRAP = RECEIPTS / "neo4j-storage-bootstrap.json"
CAPTURE = RECEIPTS / "neo4j-storage-logical-capture.json"
STOPPED = RECEIPTS / "neo4j-storage-stage-stopped.json"
LIVE = RECEIPTS / "neo4j-storage-live-verified.json"
RECOVERY_CREATE_INTENT = RECEIPTS / "neo4j-storage-replacement-create-intent.json"
RECOVERY_STOP_INTENT = RECEIPTS / "neo4j-storage-replacement-stop-intent.json"
RECOVERY_LABEL = "recovery.omniscience.io/attempt"
RECOVERY_STAGE = RECEIPTS / "neo4j-storage-replacement-stage-verified.json"
RECOVERY_STOP = RECEIPTS / "neo4j-storage-replacement-stage-stopped.json"
RECOVERY_LIVE = RECEIPTS / "neo4j-storage-replacement-live-verified.json"
SOURCE_LABELS = {"app": SOURCE, "helm.neo4j.com/instance": SOURCE}
STAGE_LABELS = {"app": STAGE, "helm.neo4j.com/instance": STAGE}
EXPECTED_DATABASES = [
    {"name": "neo4j", "type": "standard", "requestedStatus": "online", "currentStatus": "online",
     "default": True, "home": True, "aliases": []},
    {"name": "system", "type": "system", "requestedStatus": "online", "currentStatus": "online",
     "default": False, "home": False, "aliases": []},
]
EXPECTED_USERS = [{"user": "neo4j", "passwordChangeRequired": False, "suspended": None, "home": None}]
EXPECTED_INDEXES = {
    "index_1b9dcc97": "RELATIONSHIP",
    "index_460996c0": "NODE",
}

# Omniscience 639c52dac220b461d286b86a6fdeb36cf89300a4, Neo4j _BOOTSTRAP_STATEMENTS.
# Each entry is the name, label, ordered properties, and whether it is a uniqueness constraint.
APPLICATION_SCHEMA = (
    ("entity_workspace_id_unique", "Entity", ("workspace_id", "id"), True),
    ("entity_workspace_kind", "Entity", ("workspace_id", "kind"), False),
    ("entity_workspace_name", "Entity", ("workspace_id", "name"), False),
    ("entity_source_id", "Entity", ("source_id",), False),
    ("entity_workspace_kind_cluster", "Entity", ("workspace_id", "kind", "cluster"), False),
    ("entity_state_workspace_kind_cluster", "EntityState", ("workspace_id", "kind", "cluster"), False),
    ("entity_state_workspace_id_valid_from_unique", "EntityState", ("workspace_id", "id", "valid_from"), True),
    ("entity_workspace_recorded_at", "Entity", ("workspace_id", "recorded_at"), False),
    ("entity_state_workspace_valid_window", "EntityState", ("workspace_id", "id", "valid_from", "valid_to"), False),
    ("entity_state_workspace_recorded_at", "EntityState", ("workspace_id", "recorded_at"), False),
    ("store_checkpoint_workspace_source_unique", "StoreCheckpoint", ("workspace_id", "source_id"), True),
    ("document_checkpoint_workspace_source_document_unique", "DocumentCheckpoint",
     ("workspace_id", "source_id", "document_id"), True),
)

PROBE_CODE = """
import json
import os
import sys
import uuid

from neo4j import GraphDatabase, Query, READ_ACCESS
from neo4j.exceptions import AuthError


def query(driver, database, text, **params):
    with driver.session(database=database, default_access_mode=READ_ACCESS) as session:
        return session.run(text, **params).data()


def inventory(driver):
    current_user = query(driver, "system", "SHOW CURRENT USER YIELD user RETURN user")
    edition = query(driver, "system",
        "CALL dbms.components() YIELD name, versions, edition "
        "WHERE edition = 'community' RETURN versions, edition")
    databases = query(driver, "system",
        "SHOW DATABASES YIELD name, databaseID, type, requestedStatus, currentStatus, default, home, aliases "
        "RETURN name, databaseID, type, requestedStatus, currentStatus, default, home, aliases ORDER BY name")
    users = query(driver, "system",
        "SHOW USERS YIELD user, passwordChangeRequired, suspended, home "
        "RETURN user, passwordChangeRequired, suspended, home ORDER BY user")
    indexes = query(driver, "neo4j",
        "SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties, state, owningConstraint, "
        "indexProvider, options RETURN name, type, entityType, labelsOrTypes, properties, state, "
        "owningConstraint, indexProvider, options ORDER BY name")
    constraints = query(driver, "neo4j",
        "SHOW CONSTRAINTS YIELD name,type,entityType,labelsOrTypes,properties,ownedIndex,propertyType "
        "RETURN name,type,entityType,labelsOrTypes,properties,ownedIndex,propertyType ORDER BY name")
    nodes = query(driver, "neo4j", "MATCH (n) RETURN count(n) AS count")
    relationships = query(driver, "neo4j", "MATCH ()-[r]->() RETURN count(r) AS count")
    labels = [row["label"] for row in query(driver, "neo4j", "CALL db.labels() YIELD label RETURN label ORDER BY label")]
    types = [row["relationshipType"] for row in query(driver, "neo4j",
        "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType")]
    keys = [row["propertyKey"] for row in query(driver, "neo4j",
        "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey ORDER BY propertyKey")]
    marker = str(uuid.uuid4())
    transaction = Query(
        "SHOW TRANSACTIONS YIELD metaData "
        "RETURN count(CASE WHEN metaData.storageRecovery = $marker THEN 1 END) AS own, "
        "count(CASE WHEN coalesce(metaData.storageRecovery, '') <> $marker THEN 1 END) AS other",
        metadata={"storageRecovery": marker},
    )
    transactions = query(driver, "system", transaction, marker=marker)
    return {"edition": edition, "current_user": current_user, "databases": databases, "users": users, "indexes": indexes,
            "constraints": constraints, "nodes": nodes, "relationships": relationships,
            "labels": labels, "relationship_types": types, "property_keys": keys,
            "transactions": transactions}


host = sys.argv[1]
try:
    if os.environ["NEO4J_URI"] != "bolt://omniscience-neo4j:7687" or os.environ["NEO4J_USERNAME"] != "neo4j":
        raise ValueError()
    password = os.environ["NEO4J_PASSWORD"]
    if not password:
        raise ValueError()
    uri = f"bolt://{host}:7687"
    with GraphDatabase.driver(uri, auth=("neo4j", password),
                              connection_timeout=5, connection_acquisition_timeout=8) as driver:
        driver.verify_connectivity()
        result = inventory(driver)
    wrong = uuid.uuid4().hex
    if wrong == password:
        raise ValueError()
    try:
        with GraphDatabase.driver(uri, auth=("neo4j", wrong),
                                  connection_timeout=5, connection_acquisition_timeout=8) as driver:
            driver.verify_connectivity()
    except AuthError as error:
        if error.code != "Neo.ClientError.Security.Unauthorized":
            raise
        result["wrong_password_denied"] = True
    else:
        raise ValueError()
    print(json.dumps(result), flush=True)
except Exception as error:
    print("Neo4j probe failed " + type(error).__name__, flush=True)
    sys.exit(1)
"""


def reviewed_ddl():
    lines = []
    aliases = {"Entity": "n", "EntityState": "s", "StoreCheckpoint": "c", "DocumentCheckpoint": "d"}
    for name, label, properties, unique in APPLICATION_SCHEMA:
        alias = aliases[label]
        columns = ", ".join(f"{alias}.{key}" for key in properties)
        if unique:
            lines.append(f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR ({alias}:{label}) REQUIRE ({columns}) IS UNIQUE;")
        else:
            lines.append(f"CREATE INDEX {name} IF NOT EXISTS FOR ({alias}:{label}) ON ({columns});")
    return "\n".join(lines) + "\n"


def expected_schema(application):
    def index(name, kind, entity, labels, properties, owner, provider):
        return {
            "name": name, "type": kind, "entityType": entity, "labelsOrTypes": labels,
            "properties": properties, "state": "ONLINE", "owningConstraint": owner,
            "indexProvider": provider, "options": {"indexConfig": {}, "indexProvider": provider},
        }

    indexes = [
        index(name, "LOOKUP", entity, None, None, None, "token-lookup-1.0")
        for name, entity in EXPECTED_INDEXES.items()
    ]
    constraints = []
    schema = APPLICATION_SCHEMA if application else ()
    for name, label, properties, unique in schema:
        indexes.append(index(name, "RANGE", "NODE", [label], list(properties),
                             name if unique else None, "range-1.0"))
        if unique:
            constraints.append({
                "name": name, "type": "UNIQUENESS", "entityType": "NODE", "labelsOrTypes": [label],
                "properties": list(properties), "ownedIndex": name, "propertyType": None,
            })
    return {
        "indexes": sorted(indexes, key=lambda item: item["name"]),
        "constraints": sorted(constraints, key=lambda item: item["name"]),
        "labels": sorted({label for _, label, _, _ in schema}),
        "relationship_types": [],
        "property_keys": sorted({key for _, _, properties, _ in schema for key in properties}),
    }


def validate_inventory(data, quiesced=True, application=True):
    require(data["edition"] == [{"versions": ["2026.10.1"], "edition": "community"}],
            "Neo4j edition or version differs")
    require(data["wrong_password_denied"] is True, "Neo4j did not deny a wrong password")
    require(data["nodes"] == [{"count": 0}] and data["relationships"] == [{"count": 0}],
            "Neo4j has graph data")
    require(all(data[key] == value for key, value in expected_schema(application).items()),
            "Neo4j schema, indexes, constraints or token names differ from reviewed definitions")
    require(data["current_user"] == [{"user": "neo4j"}] and data["users"] == EXPECTED_USERS,
            "Neo4j users or authorization state differ")
    database_meta = [{k: value for k, value in db.items() if k != "databaseID"} for db in data["databases"]]
    require(database_meta == EXPECTED_DATABASES and all(
        isinstance(db.get("databaseID"), str) and re.fullmatch(r"[A-Fa-f0-9]{64}", db["databaseID"])
        for db in data["databases"]
    ), "Neo4j databases or internal IDs differ from reviewed shape")
    transactions = data["transactions"]
    require(len(transactions) == 1 and transactions[0]["own"] == 1,
            "Neo4j transaction check did not identify the probe transaction")
    if quiesced:
        require(transactions[0]["other"] == 0, "Neo4j has another open transaction")


def logical_state(data):
    return {
        **{key: value for key, value in data.items() if key != "transactions"},
        "databases": [{key: value for key, value in db.items() if key != "databaseID"}
                      for db in data["databases"]],
    }


def probe(cluster, host, quiesced=True, application=True):
    require(host in (SOURCE, STAGE), "Unexpected Bolt probe host")
    pod = {
        "apiVersion": "v1", "kind": "Pod",
        "metadata": {"name": PROBE, "namespace": NAMESPACE, "labels": {"app.kubernetes.io/name": PROBE}},
        "spec": {
            "automountServiceAccountToken": False, "restartPolicy": "Never", "activeDeadlineSeconds": 90,
            "containers": [{
                "name": "probe", "image": PROBE_IMAGE,
                "command": ["python", "-c", PROBE_CODE, host],
                "env": [
                    {"name": "NEO4J_PASSWORD", "valueFrom": {"secretKeyRef": {
                        "name": "omniscience-api-secret", "key": "NEO4J_PASSWORD",
                    }}},
                    *({"name": key, "valueFrom": {"configMapKeyRef": {"name": "omniscience-api", "key": key}}}
                      for key in ("NEO4J_URI", "NEO4J_USERNAME")),
                ],
            }],
        },
    }
    created = json.loads(cluster.kubectl("create", "-f", "-", "-o", "json", input=json.dumps(pod)))
    uid = created["metadata"]["uid"]
    try:
        cluster.kubectl("wait", "pod", PROBE, "--for=jsonpath={.status.phase}=Succeeded", "--timeout=100s")
        require(cluster.get("pod", PROBE)["metadata"]["uid"] == uid, "Probe pod changed")
        data = json.loads(cluster.kubectl("logs", PROBE))
        validate_inventory(data, quiesced, application)
        return data
    finally:
        delete_owned(cluster, f"/api/v1/namespaces/{NAMESPACE}/pods/{PROBE}", uid)
        if not cluster.absent("pod", PROBE):
            cluster.kubectl("wait", "pod", PROBE, "--for=delete", "--timeout=60s")


def resources(cluster):
    return {
        "pod": cluster.get("pod", STAGE)["metadata"]["uid"],
        "service": cluster.get("service", STAGE)["metadata"]["uid"],
        **{name: cluster.get("networkpolicy", name)["metadata"]["uid"] for name in POLICIES},
    }


def volume_identity(cluster):
    claim = cluster.get("pvc", CLAIM)
    require(claim["status"]["phase"] == "Bound" and claim["spec"]["storageClassName"] == "splatform-gp3"
            and claim["spec"]["accessModes"] == ["ReadWriteOnce"]
            and claim["spec"]["resources"]["requests"]["storage"] == "8Gi",
            "Recovery claim does not match the expected 8 GiB RWO binding")
    volume = cluster.get("pv", claim["spec"]["volumeName"])
    spec = volume["spec"]
    ref = spec["claimRef"]
    require((ref["namespace"], ref["name"], ref["uid"]) == (NAMESPACE, CLAIM, claim["metadata"]["uid"])
            and spec["persistentVolumeReclaimPolicy"] == "Retain"
            and spec["csi"]["driver"] == "ebs.csi.aws.com", "Recovery PV binding or class differs")
    handle = spec["csi"]["volumeHandle"]
    require(re.fullmatch(r"vol-[0-9a-f]+", handle), "Unexpected EBS volume handle")
    ebs = json.loads(cluster.helper["aws"](
        ["ec2", "describe-volumes", "--region", "eu-central-1", "--volume-ids", handle, "--output", "json"],
        env=cluster.env,
    ))["Volumes"]
    terms = spec["nodeAffinity"]["required"]["nodeSelectorTerms"]
    zones = {
        zone for term in terms for expr in term.get("matchExpressions", [])
        if expr["key"] in ("topology.ebs.csi.aws.com/zone", "topology.kubernetes.io/zone")
        and expr["operator"] == "In" for zone in expr["values"]
    }
    require(len(ebs) == 1 and ebs[0]["VolumeId"] == handle
            and ebs[0]["Encrypted"] is True and ebs[0]["Size"] == 8
            and ebs[0]["VolumeType"] == "gp3"
            and zones == {ebs[0]["AvailabilityZone"]}, "EBS volume size, encryption or topology differs")
    return {
        "pvc_uid": claim["metadata"]["uid"],
        "pv_name": volume["metadata"]["name"],
        "pv_uid": volume["metadata"]["uid"],
        "volume_handle": handle,
        "availability_zone": ebs[0]["AvailabilityZone"],
    }


def consumers(cluster):
    pods = json.loads(cluster.kubectl("get", "pods", "-o", "json"))["items"]
    return [pod["metadata"]["uid"] for pod in pods if any(
        volume.get("persistentVolumeClaim", {}).get("claimName") == CLAIM
        for volume in pod["spec"].get("volumes", [])
    )]


DIRECTORY_CHECK = r"""
[ "$NEO4J_HOME" = /var/lib/neo4j ]
conf="$NEO4J_HOME/conf/neo4j.conf"
[ -r "$conf" ]
awk '
    /^[[:space:]]*server\.directories\.(data|import|plugins|licenses|dumps\.root)[[:space:]]*=/ {
        sub(/^[[:space:]]*/, ""); sub(/[[:space:]]*$/, "");
        if ($0 != "server.directories.import=/import" &&
            $0 != "server.directories.licenses=/licenses" &&
            $0 != "server.directories.data=/data" &&
            $0 != "server.directories.plugins=/plugins" &&
            $0 != "server.directories.plugins=/var/lib/neo4j/plugins" &&
            $0 != "server.directories.dumps.root=/backups" &&
            $0 != "server.directories.dumps.root=/data/dumps") exit 1;
    }
' "$conf"
for dir in /import /backups /licenses; do
    [ -d "$dir" ]
    contents="$(find -L "$dir" -mindepth 1 -print)"
    [ -z "$contents" ]
done
for dir in /data/dumps /plugins; do
    if [ -e "$dir" ] || [ -L "$dir" ]; then
        [ -d "$dir" ]
        contents="$(find -L "$dir" -mindepth 1 -print)"
        [ -z "$contents" ]
    fi
done
plugin_dir="$NEO4J_HOME/plugins"
[ -d "$plugin_dir" ]
contents="$(find -L "$plugin_dir" -mindepth 1 -print)"
[ "$contents" = "$plugin_dir/README.txt" ]
[ -f "$plugin_dir/README.txt" ] && [ ! -L "$plugin_dir/README.txt" ]
checksum="$(sha256sum "$plugin_dir/README.txt")"
[ "${checksum%% *}" = 44ffadeb14a99af475dea24eca6049b587f0e08a07b211ea28886f38a16dc0e7 ]
for file in /data/* /data/.[!.]* /data/..?*; do
    [ -e "$file" ] || [ -L "$file" ] || continue
    case "${file##*/}" in
        databases|dbms|server_id|transactions|dumps) ;;
        *) exit 1 ;;
    esac
done
printf 'standard-empty-layout'
"""


def verify_directories(cluster, pod):
    try:
        result = cluster.kubectl("exec", pod, "--", "sh", "-ec", DIRECTORY_CHECK)
    except subprocess.CalledProcessError:
        raise RuntimeError("Neo4j filesystem layout includes custom content or could not be verified") from None
    require(result == "standard-empty-layout", "Unexpected Neo4j filesystem inventory result")


def live_pod(cluster, retained):
    pod = cluster.get("pod", f"{SOURCE}-0")
    volume = next(v for v in pod["spec"]["volumes"] if v["name"] == "data")
    expected = {"persistentVolumeClaim": {"claimName": CLAIM}} if retained else {"emptyDir": {}}
    require(volume == {"name": "data", **expected}, "Unexpected Neo4j source data volume")
    status = pod["status"]["containerStatuses"][0]
    require(status["imageID"].endswith("@" + DIGEST) and status["ready"], "Neo4j image or readiness differs")
    uid = pod["metadata"]["uid"]
    verify_directories(cluster, f"{SOURCE}-0")
    for service in (SOURCE, f"{SOURCE}-admin"):
        require(cluster.get("service", service)["spec"]["selector"] == SOURCE_LABELS,
                "Neo4j service selector differs")
        verify_endpoint(cluster, service, uid)
    return {"pod_uid": uid, "container_id": status["containerID"]}


def source_identity(cluster):
    release, _ = release_pin(cluster, 3)
    return {**release, **live_pod(cluster, retained=False),
            "statefulset_uid": cluster.get("statefulset", SOURCE)["metadata"]["uid"],
            "protected_stores": protected_store_identity(cluster)}


def staged_identity(cluster):
    pod = cluster.get("pod", STAGE)
    labels = pod["metadata"]["labels"]
    require(all(labels.get(key) == value for key, value in STAGE_LABELS.items()), "Neo4j stage labels differ")
    require(pod["spec"]["containers"][0]["image"] == IMAGE and any(
        v == {"name": "data", "persistentVolumeClaim": {"claimName": CLAIM}} for v in pod["spec"]["volumes"]
    ), "Neo4j stage image or data claim differs")
    require(cluster.get("service", STAGE)["spec"]["selector"] == STAGE_LABELS, "Neo4j stage selector differs")
    ids = resources(cluster)
    require(ids["pod"] == pod["metadata"]["uid"] and consumers(cluster) == [ids["pod"]],
            "Unexpected Neo4j stage writer or PVC consumer")
    verify_endpoint(cluster, STAGE, ids["pod"])
    verify_directories(cluster, STAGE)
    return {"resources": ids, "volume": volume_identity(cluster)}


def stage(cluster):
    source_identity(cluster)
    names = [("pvc", CLAIM), ("pod", STAGE), ("service", STAGE), ("pod", PROBE)]
    names.extend(("networkpolicy", name) for name in POLICIES)
    require(all(cluster.absent(kind, name) for kind, name in names), "Neo4j stage resource name already exists")
    require(not any(path.exists() for path in (BOOTSTRAP, CAPTURE, STOPPED, LIVE)), "Neo4j recovery receipt already exists")
    storage = cluster.get("storageclass", "splatform-gp3")
    require(storage["provisioner"] == "ebs.csi.aws.com" and storage["reclaimPolicy"] == "Retain"
            and storage["volumeBindingMode"] == "WaitForFirstConsumer"
            and storage["parameters"].get("encrypted") == "true", "Unexpected retained StorageClass")
    pod = staged_pod_manifest(cluster)
    cluster.kubectl("create", "-f", str(HERE / "staging.yaml"))
    cluster.kubectl("create", "-f", "-", input=json.dumps(pod))
    wait_stage(cluster)


def staged_pod_manifest(cluster):
    template = cluster.get("statefulset", SOURCE)["spec"]["template"]
    spec = template["spec"]
    require(len(spec["containers"]) == 1 and not spec.get("initContainers")
            and spec["containers"][0]["name"] == "neo4j", "Unexpected Neo4j StatefulSet container shape")
    labels = {**template["metadata"]["labels"], **STAGE_LABELS}
    require(not all(labels.get(key) == value for key, value in SOURCE_LABELS.items()),
            "Source services would select stage")
    data = next(v for v in spec["volumes"] if v["name"] == "data")
    require(data == {"name": "data", "emptyDir": {}}, "Expected source Neo4j emptyDir")
    data.pop("emptyDir")
    data["persistentVolumeClaim"] = {"claimName": CLAIM}
    spec["restartPolicy"] = "Never"
    spec["containers"][0]["image"] = IMAGE
    pod = {"apiVersion": "v1", "kind": "Pod", "metadata": {
        "name": STAGE, "namespace": NAMESPACE, "labels": labels,
    }, "spec": spec}
    return pod


def wait_stage(cluster):
    cluster.kubectl("wait", "pod", STAGE, "--for=condition=Ready", "--timeout=10m")
    cluster.kubectl("wait", "endpointslices", "-l", f"kubernetes.io/service-name={STAGE}",
                    "--for=jsonpath={.endpoints[0].conditions.ready}=true", "--timeout=60s")

def prepare_stage_schema(cluster):
    require(not BOOTSTRAP.exists() and not CAPTURE.exists(), "Neo4j schema preparation must precede bootstrap and capture")
    require(cluster.get("deployment", "omniscience-api")["spec"]["replicas"] == 1,
            "Keep Omniscience API running during stage preparation")
    wait_stage(cluster)
    source = source_identity(cluster)
    stage_state = staged_identity(cluster)
    original = probe(cluster, SOURCE, quiesced=False)
    probe(cluster, STAGE, application=False)
    require(source == source_identity(cluster) and stage_state == staged_identity(cluster),
            "Neo4j source or stage changed before schema preparation")
    ddl = (HERE / "application-schema.cypher").read_text()
    require(ddl == reviewed_ddl(), "Neo4j DDL differs from reviewed application schema")
    cluster.kubectl(
        "exec", "-i", STAGE, "--", "sh", "-ec",
        'test "$POD_NAME" = "$1"; '
        'auth="$(cat /config/neo4j-auth/NEO4J_AUTH)"; '
        'export NEO4J_USERNAME="${auth%%/*}" NEO4J_PASSWORD="${auth#*/}"; '
        'exec cypher-shell --address bolt://127.0.0.1:7687 --database neo4j --fail-fast',
        "stage-schema", STAGE,
        input=ddl + "CALL db.awaitIndexes(120);\n",
    )
    require(source == source_identity(cluster) and stage_state == staged_identity(cluster),
            "Neo4j source or stage changed during schema preparation")
    candidate = probe(cluster, STAGE)
    rechecked = probe(cluster, SOURCE, quiesced=False)
    require(logical_state(original) == logical_state(rechecked) == logical_state(candidate),
            "Prepared stage or original Neo4j logical state differs")
    require(source == source_identity(cluster) and stage_state == staged_identity(cluster),
            "Neo4j identities changed after schema preparation")
    write_private_json(BOOTSTRAP, {"source": source, "stage": stage_state,
                                  "source_inventory": rechecked, "stage_inventory": candidate})


def bootstrap(cluster):
    require(not CAPTURE.exists(), "Bootstrap must precede quiesced capture")
    source = source_identity(cluster)
    wait_stage(cluster)
    stage_state = staged_identity(cluster)
    original = probe(cluster, SOURCE, quiesced=False)
    candidate = probe(cluster, STAGE)
    require(logical_state(original) == logical_state(candidate), "Staged Neo4j graph differs")
    require(source == source_identity(cluster) and stage_state == staged_identity(cluster),
            "Neo4j identities changed during bootstrap")
    write_private_json(BOOTSTRAP, {"source": source, "stage": stage_state,
                                  "source_inventory": original, "stage_inventory": candidate})


def capture(cluster):
    pause_check(cluster, check_source_clients=False)
    baseline = read_private_json(BOOTSTRAP)
    source = source_identity(cluster)
    staged = staged_identity(cluster)
    require(baseline["source"] == source and baseline["stage"] == staged,
            "Neo4j bootstrap identities changed")
    original = probe(cluster, SOURCE)
    candidate = probe(cluster, STAGE)
    baseline_source = {key: value for key, value in baseline["source_inventory"].items() if key != "transactions"}
    require({key: value for key, value in original.items() if key != "transactions"} == baseline_source
            and candidate == baseline["stage_inventory"] and logical_state(original) == logical_state(candidate),
            "Quiesced Neo4j state differs from verified empty graph")
    require(source == source_identity(cluster) and staged == staged_identity(cluster),
            "Neo4j identities changed during capture")
    pause_check(cluster, check_source_clients=False)
    write_private_json(CAPTURE, {"source": source, "stage": staged,
                                "source_inventory": original, "stage_inventory": candidate})


def verify_policies(cluster, receipt):
    require(all(cluster.get("networkpolicy", name)["metadata"]["uid"] == receipt["stage"]["resources"][name]
                for name in POLICIES), "Neo4j probe policy identity changed")


def stop_stage(cluster):
    pause_check(cluster, check_source_clients=False)
    receipt = read_private_json(CAPTURE)
    require(receipt["source"] == source_identity(cluster) and receipt["stage"] == staged_identity(cluster)
            and probe(cluster, STAGE) == receipt["stage_inventory"], "Neo4j staged state changed")
    owned = receipt["stage"]["resources"]
    require(resources(cluster) == owned, "Neo4j staging resources changed before shutdown")
    delete_owned(cluster, f"/api/v1/namespaces/{NAMESPACE}/pods/{STAGE}", owned["pod"])
    if not cluster.absent("pod", STAGE):
        cluster.kubectl("wait", "pod", STAGE, "--for=delete", "--timeout=120s")
    delete_owned(cluster, f"/api/v1/namespaces/{NAMESPACE}/services/{STAGE}", owned["service"])
    require(not consumers(cluster), "A pod still references the Neo4j retained PVC")
    write_private_json(STOPPED, receipt)


def verify_cutover(cluster):
    pause_check(cluster, check_source_clients=False)
    receipt = read_private_json(CAPTURE)
    require(receipt == read_private_json(STOPPED) and receipt["source"] == source_identity(cluster)
            and receipt["stage"]["volume"] == volume_identity(cluster)
            and cluster.absent("pod", STAGE) and not consumers(cluster),
            "Neo4j cutover source, stage shutdown or volume identity changed")
    verify_policies(cluster, receipt)
    require(probe(cluster, SOURCE) == receipt["source_inventory"], "Quiesced Neo4j source state changed")
    require(receipt["source"] == source_identity(cluster), "Neo4j source changed during verification")
    pause_check(cluster, check_source_clients=False)


def verify_replacement_pg(cluster, original, current):
    pg = "omniscience-postgres"
    require({key: value for key, value in current.items() if key != pg}
            == {key: value for key, value in original.items() if key != pg},
            "NATS or Qdrant identity changed after Neo4j capture")
    require({key: value for key, value in current[pg].items() if key != "pod_uid"}
            == {key: value for key, value in original[pg].items() if key != "pod_uid"},
            "Protected PostgreSQL StatefulSet or claim identity changed")
    capture = SHARED["read_private_json"](SHARED["CAPTURE_RECEIPT"])
    verified = SHARED["read_private_json"](SHARED["RECEIPT"])
    fingerprint = SHARED["database_fingerprint"](cluster, f"{pg}-0")
    volume = SHARED["volume_identity"](cluster)
    require(all(capture.get(key) == value for key, value in fingerprint.items())
            and all(verified.get(key) == value for key, value in volume.items()),
            "Protected PostgreSQL data or retained EBS identity differs from its verified capture")


def replacement_source(cluster, captured):
    pause_check(cluster, check_source_clients=False)
    require(captured == read_private_json(STOPPED), "Original capture and shutdown receipts differ")
    prior = captured["source"]
    current = source_identity(cluster)
    variable_keys = {"pod_uid", "container_id", "protected_stores"}
    require({key: value for key, value in current.items() if key not in variable_keys}
            == {key: value for key, value in prior.items() if key not in variable_keys},
            "Neo4j source StatefulSet or Helm revision changed")
    require(current["pod_uid"] != prior["pod_uid"] and current["container_id"] != prior["container_id"],
            "Explicit replacement recovery requires a different Neo4j pod and container")
    replacement = cluster.get("pod", f"{SOURCE}-0")["metadata"]
    for store in (SOURCE, *current["protected_stores"]):
        meta = replacement if store == SOURCE else cluster.get("pod", f"{store}-0")["metadata"]
        require(meta.get("annotations", {}).get("karpenter.sh/do-not-disrupt") == "true",
                f"Temporary disruption protection is missing from {store}")
    created = datetime.fromisoformat(replacement["creationTimestamp"].replace("Z", "+00:00"))
    captured_at = datetime.fromtimestamp(CAPTURE.stat().st_mtime, tz=timezone.utc)
    require(replacement["uid"] == current["pod_uid"] and created > captured_at,
            "Replacement Neo4j pod did not start after the quiesced capture")
    verify_replacement_pg(cluster, prior["protected_stores"], current["protected_stores"])
    verify_policies(cluster, captured)
    require(volume_identity(cluster) == captured["stage"]["volume"], "Captured Neo4j EBS volume changed")
    return current


def verified_replacement(cluster, captured):
    source = replacement_source(cluster, captured)
    inventory = probe(cluster, SOURCE, application=False)
    require(replacement_source(cluster, captured) == source, "Replacement source changed during verification")
    return {"source": source, "inventory": inventory}


def ensure_recovery_resource(cluster, manifest, intent):
    kind = manifest["kind"].lower()
    name = manifest["metadata"]["name"]
    token = intent["token"]
    manifest["metadata"].setdefault("labels", {})[RECOVERY_LABEL] = token
    owned = intent["resources"]
    if cluster.absent(kind, name):
        require(kind not in owned, f"Previously owned recovery {kind} disappeared")
        cluster.kubectl("create", "-f", "-", input=json.dumps(manifest))
    obj = cluster.get(kind, name)
    meta = obj["metadata"]
    require(meta.get("labels", {}).get(RECOVERY_LABEL) == token,
            f"Existing recovery {kind} is foreign")
    uid = meta["uid"]
    require(owned.get(kind, uid) == uid, f"Recovery {kind} UID changed")
    if kind not in owned:
        owned[kind] = uid
        write_private_json(RECOVERY_CREATE_INTENT, intent)


def recover_stage(cluster):
    captured = read_private_json(CAPTURE)
    require(not any(path.exists() for path in (RECOVERY_STAGE, RECOVERY_STOP, RECOVERY_LIVE)),
            "Replacement recovery already has a verification receipt")
    replacement = verified_replacement(cluster, captured)
    volume = captured["stage"]["volume"]
    if RECOVERY_CREATE_INTENT.exists():
        intent = read_private_json(RECOVERY_CREATE_INTENT)
        require(intent["replacement"] == replacement and intent["volume"] == volume,
                "Replacement recovery create intent no longer matches the source or volume")
    else:
        require(cluster.absent("pod", STAGE) and cluster.absent("service", STAGE) and not consumers(cluster),
                "Stage resources or another PVC consumer already exist")
        intent = {"replacement": replacement, "volume": volume, "token": uuid.uuid4().hex, "resources": {}}
        write_private_json(RECOVERY_CREATE_INTENT, intent)
    manifest = staged_pod_manifest(cluster)
    manifest["metadata"]["annotations"] = {"karpenter.sh/do-not-disrupt": "true"}
    service = {
        "apiVersion": "v1", "kind": "Service", "metadata": {"name": STAGE, "namespace": NAMESPACE},
        "spec": {"selector": STAGE_LABELS, "ports": [{"name": "bolt", "port": 7687, "targetPort": 7687}]},
    }
    existing_consumers = consumers(cluster)
    if existing_consumers:
        require(not cluster.absent("pod", STAGE), "A foreign pod references the recovery claim")
        pod = cluster.get("pod", STAGE)["metadata"]
        require(existing_consumers == [pod["uid"]] and pod.get("labels", {}).get(RECOVERY_LABEL) == intent["token"]
                and intent["resources"].get("pod", pod["uid"]) == pod["uid"],
                "A foreign pod references the recovery claim")
    ensure_recovery_resource(cluster, service, intent)
    ensure_recovery_resource(cluster, manifest, intent)
    wait_stage(cluster)
    stage_state = staged_identity(cluster)
    require(stage_state["volume"] == volume
            and all(stage_state["resources"][kind] == uid for kind, uid in intent["resources"].items())
            and probe(cluster, STAGE) == captured["stage_inventory"],
            "Reopened stage differs from the original verified catalog or internal database IDs")
    require(verified_replacement(cluster, captured) == replacement
            and staged_identity(cluster) == stage_state, "Replacement source or reopened stage changed")
    write_private_json(RECOVERY_STAGE, {"replacement": replacement, "stage": stage_state})


def delete_recovery_resource(cluster, kind, uid):
    if cluster.absent(kind, STAGE):
        return
    require(cluster.get(kind, STAGE)["metadata"]["uid"] == uid, f"Reopened stage {kind} UID changed")
    delete_owned(cluster, f"/api/v1/namespaces/{NAMESPACE}/{kind}s/{STAGE}", uid)
    if not cluster.absent(kind, STAGE):
        require(cluster.get(kind, STAGE)["metadata"]["uid"] == uid, f"Reopened stage {kind} UID changed")
        cluster.kubectl("wait", kind, STAGE, "--for=delete", "--timeout=120s")


def stop_recovery_stage(cluster):
    captured = read_private_json(CAPTURE)
    recovery = read_private_json(RECOVERY_STAGE)
    require(verified_replacement(cluster, captured) == recovery["replacement"],
            "Replacement source changed before shutdown")
    if RECOVERY_STOP_INTENT.exists():
        require(read_private_json(RECOVERY_STOP_INTENT) == recovery, "Replacement shutdown intent differs")
    else:
        require(staged_identity(cluster) == recovery["stage"]
                and probe(cluster, STAGE) == captured["stage_inventory"],
                "Reopened stage changed before shutdown")
        require(resources(cluster) == recovery["stage"]["resources"], "Reopened stage UIDs changed")
        write_private_json(RECOVERY_STOP_INTENT, recovery)
    owned = recovery["stage"]["resources"]
    existing_consumers = consumers(cluster)
    require(not existing_consumers or existing_consumers == [owned["pod"]],
            "An unexpected pod references the captured Neo4j PVC")
    delete_recovery_resource(cluster, "pod", owned["pod"])
    delete_recovery_resource(cluster, "service", owned["service"])
    require(cluster.absent("pod", STAGE) and cluster.absent("service", STAGE) and not consumers(cluster),
            "A stage resource or PVC consumer remains")
    write_private_json(RECOVERY_STOP, recovery)


def verify_recovery_cutover(cluster):
    captured = read_private_json(CAPTURE)
    recovery = read_private_json(RECOVERY_STAGE)
    require(recovery == read_private_json(RECOVERY_STOP)
            and cluster.absent("pod", STAGE) and cluster.absent("service", STAGE) and not consumers(cluster),
            "Reopened stage shutdown or PVC ownership differs")
    require(verified_replacement(cluster, captured) == recovery["replacement"],
            "Replacement source changed before recovery cutover")


def protected_for_verification(captured, recovery):
    if recovery:
        return read_private_json(RECOVERY_STOP)["replacement"]["source"]["protected_stores"]
    return captured["source"]["protected_stores"]


def protected_store_identity(cluster):
    result = {}
    for name in ("omniscience-postgres", "omniscience-nats", "omniscience-qdrant"):
        sts = cluster.get("statefulset", name)
        pod = cluster.get("pod", f"{name}-0")
        claims = {}
        for volume in pod["spec"]["volumes"]:
            reference = volume.get("persistentVolumeClaim")
            if reference:
                claim_name = reference["claimName"]
                claim = cluster.get("pvc", claim_name)
                require(claim["status"]["phase"] == "Bound", "Protected Omniscience claim is not bound")
                claims[claim_name] = [claim["metadata"]["uid"], claim["spec"]["volumeName"]]
        require(bool(claims), "Protected Omniscience store does not use a PVC")
        if name == "omniscience-postgres":
            require(set(claims) == {"omniscience-postgres-data-retained"}, "Retained PostgreSQL claim differs")
        result[name] = {
            "statefulset_uid": sts["metadata"]["uid"],
            "pod_uid": pod["metadata"]["uid"],
            "claims": claims,
        }
    return result


def normalize_neo4j_volume_null(resources):
    neo4j = resources.get(("StatefulSet", SOURCE))
    if neo4j is None:
        return
    volumes = neo4j["spec"]["template"]["spec"]["volumes"]
    nullable = {
        "name": "data",
        "emptyDir": None,
        "persistentVolumeClaim": {"claimName": CLAIM},
    }
    for volume in volumes:
        # The Kubernetes API decodes this explicit YAML null as an absent volume source.
        if volume == nullable:
            del volume["emptyDir"]


def resources_by_name(source):
    result = subprocess.run(
        ["yq", "ea", "-o=json", "-I=0", "[.]", "-"],
        input=source, capture_output=True, text=True, check=True,
    )
    documents = [obj for obj in json.loads(result.stdout) if obj]
    indexed = {(obj["kind"], obj["metadata"]["name"]): obj for obj in documents}
    require(len(indexed) == len(documents), "Duplicate resource in Helm manifest")
    normalize_neo4j_volume_null(indexed)
    return indexed


def change_manifest(expected, resume):
    api = expected[("Deployment", "omniscience-api")]["spec"]
    require(api["replicas"] == (0 if resume else 1), "Unexpected Omniscience API replica baseline")
    api["replicas"] = 1 if resume else 0
    spec = expected[("StatefulSet", SOURCE)]["spec"]["template"]["spec"]
    volume = next(v for v in spec["volumes"] if v["name"] == "data")
    retained = {"name": "data", "persistentVolumeClaim": {"claimName": CLAIM}}
    if resume:
        require(volume == retained and spec["containers"][0]["image"] == IMAGE,
                "Resume baseline does not mount the verified Neo4j claim and image")
    else:
        require(volume == {"name": "data", "emptyDir": {}}, "Expected Neo4j emptyDir baseline")
        volume.clear()
        volume.update(retained)
        spec["containers"][0]["image"] = IMAGE


def verify_render(cluster, rendered, baseline, resume):
    original = resources_by_name(baseline)
    actual = resources_by_name(rendered)
    change_manifest(original, resume)
    require(actual == original, "Rendered resources differ beyond approved Neo4j storage and API replica changes")
    current = cluster.get("statefulset", SOURCE)["spec"]
    new = actual[("StatefulSet", SOURCE)]["spec"]
    for key in ("serviceName", "selector", "volumeClaimTemplates", "podManagementPolicy"):
        default = "OrderedReady" if key == "podManagementPolicy" else None
        require(new.get(key, default) == current.get(key, default), f"Neo4j StatefulSet field {key} differs")
    for (kind, name), rendered_secret in actual.items():
        if kind != "Secret":
            continue
        live = cluster.get("secret", name)
        data = {key: value for key, value in rendered_secret.get("data", {}).items()}
        if rendered_secret.get("stringData"):
            data.update({key: base64.b64encode(value.encode()).decode()
                         for key, value in rendered_secret["stringData"].items()})
        require(data == live.get("data", {}) and rendered_secret.get("type", "Opaque") == live["type"],
                f"Rendered Secret {name} differs from live")


def verify_live(cluster, recovery=False):
    pause_check(cluster, check_source_clients=False)
    release, _ = release_pin(cluster, 4)
    receipt = read_private_json(CAPTURE)
    verify_policies(cluster, receipt)
    pod = live_pod(cluster, retained=True)
    volume = volume_identity(cluster)
    previous = {receipt["source"]["pod_uid"]}
    if recovery:
        previous.add(read_private_json(RECOVERY_STOP)["replacement"]["source"]["pod_uid"])
    require(volume == receipt["stage"]["volume"] and consumers(cluster) == [pod["pod_uid"]]
            and pod["pod_uid"] not in previous, "Live Neo4j PVC or pod identity differs")
    require(protected_store_identity(cluster) == protected_for_verification(receipt, recovery),
            "Protected Omniscience stores changed during Neo4j cutover")
    data = probe(cluster, SOURCE)
    require(data == receipt["stage_inventory"] and logical_state(data) == logical_state(receipt["source_inventory"]),
            "Live Neo4j graph, auth or staged internal IDs differ")
    require(live_pod(cluster, retained=True) == pod and volume_identity(cluster) == volume
            and release_pin(cluster, 4)[0] == release, "Neo4j identities changed during live verification")
    write_private_json(RECOVERY_LIVE if recovery else LIVE, {
        "release": release, "pod": pod, "volume": volume, "inventory": data,
        "old_database_ids": {db["name"]: db["databaseID"] for db in receipt["source_inventory"]["databases"]},
        "new_database_ids": {db["name"]: db["databaseID"] for db in data["databases"]},
    })


def verify_resume(cluster, recovery=False):
    pause_check(cluster, check_source_clients=False)
    captured = read_private_json(CAPTURE)
    receipt = read_private_json(RECOVERY_LIVE if recovery else LIVE)
    verify_policies(cluster, captured)
    pod = live_pod(cluster, retained=True)
    require(receipt["release"] == release_pin(cluster, 4)[0] and receipt["pod"] == pod
            and receipt["volume"] == volume_identity(cluster) and consumers(cluster) == [pod["pod_uid"]]
            and protected_store_identity(cluster) == protected_for_verification(captured, recovery),
            "Neo4j or protected store identity changed after verification")
    require(probe(cluster, SOURCE) == receipt["inventory"], "Live Neo4j logical state changed before resume")


def helm(cluster, action):
    recovery = action.endswith("-recovery")
    resume = action in ("resume", "dryrun-resume", "resume-recovery")
    mutate = action in ("cutover", "resume", "cutover-recovery", "resume-recovery")
    revision = 4 if resume else 3

    def guard(target):
        if resume:
            verify_resume(target, recovery)
        elif recovery:
            verify_recovery_cutover(target)
        else:
            verify_cutover(target)
    if mutate:
        guard(cluster)
    pin, payload = release_pin(cluster, revision)
    release = decode_release(payload)
    hooks = [(hook["name"], hook["kind"], hook["events"]) for hook in release.get("hooks", [])]
    require(hooks == EXPECTED_HOOKS, "Omniscience Helm hooks differ from reviewed baseline")
    replicas = 1 if resume else 0
    with tempfile.TemporaryDirectory(prefix="neo4j-storage-", dir=PRIVATE) as directory:
        path = Path(directory).resolve()
        chart_dir = path / "omniscience"
        restore_chart(chart_dir, release)
        env = helm_context(cluster, path / "kubeconfig")
        base = ["helm", "upgrade", "omniscience", str(chart_dir), "--kube-context",
                cluster.helper["CONTEXT"], "-n", NAMESPACE, "--reuse-values", "--no-hooks",
                "-f", str(HERE / "helm-values.yaml")]

        def dryrun(count):
            result = subprocess.run(
                base + ["--set", f"replicaCount={count}", "--dry-run=server"],
                env=env, capture_output=True, text=True, check=True,
            )
            return result.stdout.split("MANIFEST:\n", 1)[1]

        proposed = dryrun(replicas)
        verify_render(cluster, proposed, release["manifest"], resume)
        if action == "dryrun":
            verify_render(cluster, dryrun(1), proposed, resume=True)
        if mutate:
            guard(cluster)
            require(release_pin(cluster, revision)[0] == pin, "Helm release changed after dry run")
            verify_render(cluster, proposed, release["manifest"], resume)
            subprocess.run(
                base + ["--set", f"replicaCount={replicas}", "--wait", "--timeout", "10m"],
                env=env, capture_output=True, text=True, check=True,
            )
            _, payload = release_pin(cluster, revision + 1)
            installed = decode_release(payload)
            require(installed["config"]["replicaCount"] == replicas
                    and resources_by_name(installed["manifest"]) == resources_by_name(proposed),
                    "Installed Neo4j Helm manifest or API replica count differs")
            if resume:
                captured = read_private_json(CAPTURE)
                require(protected_store_identity(cluster) == protected_for_verification(captured, recovery),
                        "Protected Omniscience stores changed during Neo4j resume")
                for name in POLICIES:
                    delete_owned(cluster, f"/apis/networking.k8s.io/v1/namespaces/{NAMESPACE}/networkpolicies/{name}",
                                 captured["stage"]["resources"][name])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    operations = {
        "stage": stage,
        "prepare-stage-schema": prepare_stage_schema,
        "verify-bootstrap": bootstrap,
        "capture": capture,
        "stop-stage": stop_stage,
        "verify-live": verify_live,
        "recover-stage": recover_stage,
        "stop-recovery-stage": stop_recovery_stage,
        "verify-live-recovery": lambda cluster: verify_live(cluster, recovery=True),
    }
    for action in (*operations, "dryrun", "dryrun-resume", "cutover", "resume", "cutover-recovery", "resume-recovery"):
        commands.add_parser(action)
    args = parser.parse_args()
    try:
        cluster = Cluster()
        if args.action in operations:
            operations[args.action](cluster)
        else:
            helm(cluster, args.action)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"{args.action} failed (command exit {error.returncode}). Inspect status without printing secrets.\n")
    except (FileNotFoundError, FileExistsError, json.JSONDecodeError, KeyError):
        parser.exit(1, f"{args.action} failed: missing, existing or unexpected recovery input.\n")
    except RuntimeError as error:
        parser.exit(1, f"{args.action} failed: {error}\n")
    print(f"{args.action} passed")


if __name__ == "__main__":
    main()
