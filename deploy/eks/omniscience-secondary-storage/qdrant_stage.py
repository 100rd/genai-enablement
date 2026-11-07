#!/usr/bin/env python3
"""Restore the reviewed Qdrant capture into an isolated, retained EBS claim."""

import argparse
import base64
import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager

import capture as native

require = native.require
NS = native.NAMESPACE
SOURCE = "omniscience-qdrant"
IMAGE = native.SOURCES[SOURCE]["images"]["qdrant"]
BACKUP = native.BACKUP_ROOT / "capture-nmq_o7wh"
RECEIPT_SHA = "da0a5889296385a577671d42984f04e7d36c7010e6a0fc746cadd4cb03601576"
POINT_SHA = "0b33b2866404b1bd204cd49b0f52c0b9976efaff5b3ab05b744060e4c09804d4"
STATE_DIR = native.BACKUP_ROOT.parent / "qdrant-stage"
INCIDENT_STATE_DIR = STATE_DIR.with_name("qdrant-stage-spot-20261107")
REPLACEMENT_POD_UID = "9b9530c8-6561-4630-b2f8-9fb88aa78543"
REPLACEMENT_NODE = "ip-10-1-40-64.eu-central-1.compute.internal"
REPLACEMENT_NODE_UID = "2e7d56f0-34ad-445a-841d-a45735ba01c1"
ON_DEMAND = {"eks.amazonaws.com/capacityType": "ON_DEMAND"}
AUTH_SECRET = "omniscience-api-secret"
AUTH_KEY = "QDRANT_API_KEY"
LABEL = "recovery.omniscience.io/qdrant-stage"
INTENT = "recovery.omniscience.io/create-intent"
STORAGE_CLASS = "splatform-gp3"
POD_TOPOLOGY_LABELS = {"topology.kubernetes.io/region", "topology.kubernetes.io/zone"}
PEER_URI = "http://127.0.0.1:6335/"
PHASES = ("new", "uploading", "verified", "restarting", "accepted")


def private(path, mode, directory=False):
    require(not path.is_symlink() and (path.is_dir() if directory else path.is_file())
            and path.stat().st_mode & 0o777 == mode and path.stat().st_uid == os.getuid(),
            f"Missing or unsafe private {path.name}")


def verified_backup(directory=BACKUP):
    private(directory.parent, 0o700, directory=True)
    private(directory, 0o700, directory=True)
    path = directory / "receipt.json"
    private(path, 0o600)
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == RECEIPT_SHA, "Capture receipt pin differs")
    receipt = json.loads(data)
    require(receipt["status"] == "complete", "Capture is incomplete")
    files = receipt["files"]
    expected = {"qdrant.snapshot"} | {
        f"nats/{stream}/{name}" for stream in native.NATS_STREAMS for name in ("backup.json", "stream.tar.s2")
    }
    require(files.keys() == expected, "Capture artifact list differs")
    for name, entry in files.items():
        artifact = directory / name
        for parent in artifact.relative_to(directory).parents:
            private(directory / parent, 0o700, directory=True)
        private(artifact, 0o600)
        require(artifact.stat().st_size == entry["bytes"] > 0 and native.file_hash(artifact) == entry["sha256"],
                f"Capture artifact differs: {name}")
    snapshot = receipt["qdrant_snapshot"]
    require(files["qdrant.snapshot"] == {key: snapshot[key] for key in ("bytes", "sha256")},
            "Native snapshot checksum or byte length differs")
    inventory = receipt["source_inventory"]
    qdrant = inventory["qdrant"]
    require(qdrant["version"] == "1.20.0" and qdrant["collection"] == native.QDRANT_COLLECTION
            and qdrant["points"] == 7 and qdrant["point_digest"] == POINT_SHA and qdrant["aliases"] == []
            and len(qdrant["peers"]) == 1 and qdrant["local_shards"] == [
                {"shard_id": 0, "state": "Active", "points_count": 7}
            ], "Captured Qdrant inventory differs from review")
    return receipt


def manifest(kind, api, name, stage, intent, spec):
    return {"apiVersion": api, "kind": kind, "metadata": {
        "name": name, "namespace": NS, "labels": {LABEL: stage}, "annotations": {INTENT: intent},
    }, "spec": spec}


def resources(stage, intents):
    selector = {"matchLabels": {LABEL: stage}}
    claim = manifest("PersistentVolumeClaim", "v1", stage, stage, intents["claim"], {
        "storageClassName": STORAGE_CLASS, "accessModes": ["ReadWriteOnce"], "volumeMode": "Filesystem",
        "resources": {"requests": {"storage": "10Gi"}},
    })
    knp = manifest("NetworkPolicy", "networking.k8s.io/v1", stage, stage, intents["knp"], {
        "podSelector": selector, "policyTypes": ["Ingress", "Egress"],
    })
    cnp = manifest("CiliumNetworkPolicy", "cilium.io/v2", stage, stage, intents["cnp"], {
        "endpointSelector": selector, "ingressDeny": [{"fromEntities": ["all"]}],
        "egressDeny": [{"toEntities": ["all"]}],
    })
    return {"claim": claim, "knp": knp, "cnp": cnp}


def pod_manifest(stage, role, intent, *, incident=False):
    mounts = [{"name": name, "mountPath": path} for name, path in (
        ("storage", "/qdrant/storage"), ("snapshots", "/qdrant/snapshots"), ("tmp", "/tmp"),
    )]
    env = [{"name": "QDRANT__SERVICE__API_KEY", "valueFrom": {"secretKeyRef": {
        "name": AUTH_SECRET, "key": AUTH_KEY,
    }}}]
    env.extend({"name": name, "value": value} for name, value in {
        "QDRANT__CLUSTER__ENABLED": "true",
        "QDRANT__CLUSTER__P2P__HOST": "127.0.0.1",
        "QDRANT__CLUSTER__P2P__PORT": "6335",
        "QDRANT__SERVICE__HOST": "127.0.0.1",
        "QDRANT__SERVICE__MAX_REQUEST_SIZE_MB": "128",
    }.items())
    return manifest("Pod", "v1", f"{stage}-{role}", stage, intent, {
        **({"nodeSelector": ON_DEMAND} if incident else {}),
        "automountServiceAccountToken": False, "enableServiceLinks": False, "restartPolicy": "Never",
        "terminationGracePeriodSeconds": 60,
        "securityContext": {"fsGroup": 3000, "fsGroupChangePolicy": "Always", "seccompProfile": {
            "type": "RuntimeDefault",
        }},
        "volumes": [
            {"name": "storage", "persistentVolumeClaim": {"claimName": stage}},
            {"name": "snapshots", "emptyDir": {}}, {"name": "tmp", "emptyDir": {}},
        ],
        "initContainers": [{
            "name": "ensure-dir-ownership", "image": IMAGE,
            "command": ["chown", "-R", "1000:3000", "/qdrant/storage", "/qdrant/snapshots"],
            "securityContext": {"runAsUser": 0, "allowPrivilegeEscalation": False,
                                "capabilities": {"drop": ["ALL"], "add": ["CHOWN", "DAC_OVERRIDE"]}},
            "resources": {},
            "volumeMounts": mounts[:2],
        }],
        "containers": [{
            "name": "qdrant", "image": IMAGE, "command": ["/qdrant/qdrant"],
            "args": ["--uri", PEER_URI, "--disable-telemetry"], "env": env,
            "workingDir": "/qdrant",
            "securityContext": {
                "runAsNonRoot": True, "runAsUser": 1000, "runAsGroup": 2000,
                "allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                "capabilities": {"drop": ["ALL"]},
            },
            "resources": {"requests": {"cpu": "250m", "memory": "512Mi"}},
            "volumeMounts": mounts,
        }],
    })


def list_items(cluster, kind, *args):
    return json.loads(cluster.kubectl("get", kind, *args, "-o", "json"))["items"]


def verify_service_scope(cluster, labels):
    for svc in list_items(cluster, "services"):
        selector = svc["spec"].get("selector")
        require(not selector or not all(labels.get(key) == value for key, value in selector.items()),
                "A namespace Service selects the staged Pod")


def incident_source_guard(cluster, receipt):
    source = receipt["source_inventory"]["source"]
    release, _ = native.SHARED["release_pin"](cluster, native.RELEASE)
    require(release == source["release"], "Incident Helm revision differs from the pinned capture")
    check_secret(cluster.get("secret", AUTH_SECRET), receipt)
    require(cluster.absent("node", native.SOURCE_NODE), "Original capture node still exists")
    replacement_node = cluster.get("node", REPLACEMENT_NODE)
    require(replacement_node["metadata"]["uid"] == REPLACEMENT_NODE_UID, "Incident replacement Node UID changed")
    expected = source["stores"][SOURCE]
    sts = cluster.get("statefulset", SOURCE)
    pod = cluster.get("pod", f"{SOURCE}-0")
    claim = cluster.get("pvc", expected["pvc"])
    volume = cluster.get("pv", expected["pv"])
    owner = [ref["uid"] for ref in pod["metadata"].get("ownerReferences", []) if ref.get("controller")]
    images = {item["name"]: item["imageID"] for item in pod["status"]["containerStatuses"]}
    require(sts["metadata"]["uid"] == expected["sts_uid"] and owner == [expected["sts_uid"]]
            and pod["metadata"]["uid"] == REPLACEMENT_POD_UID and pod["spec"]["nodeName"] == REPLACEMENT_NODE
            and not pod["metadata"].get("deletionTimestamp") and images == expected["images"],
            "Incident source StatefulSet, Pod or image changed")
    ref = volume["spec"]["claimRef"]
    require(claim["metadata"]["uid"] == expected["pvc_uid"] and claim["status"]["phase"] == "Bound"
            and claim["spec"]["volumeName"] == expected["pv"] and volume["metadata"]["uid"] == expected["pv_uid"]
            and (ref["namespace"], ref["name"], ref["uid"]) == (NS, expected["pvc"], expected["pvc_uid"])
            and volume["spec"]["persistentVolumeReclaimPolicy"] == "Retain"
            and volume["spec"]["hostPath"] == {"path": expected["path"], "type": "DirectoryOrCreate"}
            and [v["persistentVolumeClaim"]["claimName"] for v in pod["spec"]["volumes"]
                 if "persistentVolumeClaim" in v] == [expected["pvc"]],
            "Incident source PVC/PV binding changed")


def source_guard(cluster, receipt, *, incident=False):
    if incident:
        incident_source_guard(cluster, receipt)
    else:
        current = native.source_identity(cluster, capture=True)
        require(current == receipt["source_inventory"]["source"], "Source release, identity or auth reference changed")
    storage = cluster.get("storageclass", STORAGE_CLASS)
    require(storage["provisioner"] == "ebs.csi.aws.com" and storage["reclaimPolicy"] == "Retain"
            and storage["volumeBindingMode"] == "WaitForFirstConsumer"
            and storage["parameters"].get("encrypted") == "true"
            and storage["parameters"].get("type") == "gp3", "Staging StorageClass differs")


def check_secret(secret, receipt):
    ref = receipt["source_inventory"]["source"]["qdrant_auth_ref"]
    meta = secret["metadata"]
    require(ref == {"uid": meta["uid"], "resource_version": meta["resourceVersion"]},
            "Qdrant authentication Secret changed")
    return base64.b64decode(secret["data"][AUTH_KEY], validate=True).decode()


def check_metadata(live, desired, uid=None, *, allow_terminating=False):
    meta = live["metadata"]
    expected = desired["metadata"]
    labels = meta.get("labels", {})
    if desired["kind"] == "Pod" and live["spec"].get("nodeName"):
        labels = {key: value for key, value in labels.items() if key not in POD_TOPOLOGY_LABELS}
    require(live["kind"] == desired["kind"] and meta["name"] == expected["name"]
            and meta["namespace"] == expected["namespace"]
            and labels == expected["labels"]
            and meta.get("annotations", {}).get(INTENT) == expected["annotations"][INTENT]
            and meta.get("uid") and (uid is None or meta["uid"] == uid)
            and not meta.get("ownerReferences") and (allow_terminating or not meta.get("deletionTimestamp")),
            "Stage resource does not match the durable create intent or UID")
    return meta["uid"]


def normalized_spec(obj):
    spec = obj["spec"].copy()
    if obj["kind"] == "PersistentVolumeClaim":
        spec.pop("volumeName", None)
    if obj["kind"] == "Pod":
        spec.pop("nodeName", None)
    return spec


def check_dry_run(admitted, desired):
    """Permit Kubernetes defaults while failing closed on workload injection."""
    actual = normalized_spec(admitted)
    expected = desired["spec"]
    if desired["kind"] != "Pod":
        if desired["kind"] == "PersistentVolumeClaim":
            require(not admitted["spec"].get("volumeName"), "Admission prebound the staging PVC")
        require(actual == expected, "Admission changed the stage claim or isolation policy")
        return
    defaults = {"dnsPolicy", "priority", "preemptionPolicy", "schedulerName", "serviceAccount",
                "serviceAccountName", "tolerations", "imagePullSecrets"}
    require(actual.keys() <= expected.keys() | defaults
            and not admitted["spec"].get("nodeName")
            and actual.get("serviceAccountName", "default") == "default"
            and admitted["metadata"].get("labels") == desired["metadata"]["labels"],
            "Admission changed stage Pod scope")
    for field in expected.keys() - {"containers", "initContainers"}:
        require(actual[field] == expected[field], "Admission changed stage Pod configuration")
    for field in ("containers", "initContainers"):
        require(len(actual[field]) == 1, "Admission injected a stage container")
        container, reference = actual[field][0], expected[field][0]
        defaults = {"imagePullPolicy", "terminationMessagePath", "terminationMessagePolicy"}
        require(container.keys() <= reference.keys() | defaults
                and all(container[key] == value for key, value in reference.items())
                and all(mount.get("subPath") is None for mount in container["volumeMounts"]),
                "Admission changed stage container configuration")


class Journal:
    def __init__(self, path, state):
        self.path = path
        self.state = state

    def save(self):
        candidate = native.receipt_candidate(self.path.parent, self.state)
        try:
            candidate.replace(self.path)
            native.sync_directory(self.path.parent)
        finally:
            candidate.unlink(missing_ok=True)


@contextmanager
def journal(root, create, *, incident=False):
    if create and not root.exists():
        root.mkdir(mode=0o700)
        native.sync_directory(root.parent)
    private(root, 0o700, directory=True)
    lock = root / "lock"
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        private(lock, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = root / "receipt.json"
        if path.exists() or path.is_symlink():
            private(path, 0o600)
            state = json.loads(path.read_bytes())
            require(state["backup_sha256"] == RECEIPT_SHA and state["phase"] in PHASES
                    and re.fullmatch(r"omniscience-qdrant-stage-[0-9a-f]{12}", state["stage"]),
                    "Stage journal does not match the reviewed rehearsal")
            require(state.get("spot_incident", False) is incident, "Stage journal belongs to a different mode")
            yield Journal(path, state)
        else:
            require(create, "No Qdrant stage receipt exists")
            state = {
                "backup_sha256": RECEIPT_SHA, "phase": "new", "started_at": native.timestamp(),
                "stage": "omniscience-qdrant-stage-" + uuid.uuid4().hex[:12], "resources": {
                    role: {"intent": uuid.uuid4().hex}
                    for role in ("claim", "knp", "cnp", "restore", "restart")
                },
            }
            if incident:
                state["spot_incident"] = True
            record = Journal(path, state)
            record.save()
            yield record
    finally:
        os.close(fd)


def create_or_check(cluster, journal, role, desired, *, allow_create=False, allow_terminating=False):
    entry = journal.state["resources"][role]
    kind, name = desired["kind"], desired["metadata"]["name"]
    exists = not cluster.absent(kind, name)
    if not exists:
        require(allow_create and not entry.get("uid"), "Recorded stage resource is absent")
        admitted = json.loads(cluster.kubectl("create", "--dry-run=server", "-o", "json", "-f", "-",
                                               input=json.dumps(desired)))
        check_dry_run(admitted, desired)
        spec_hash = native.canonical_hash(normalized_spec(admitted))
        require(entry.get("spec_sha256", spec_hash) == spec_hash, "Stage admission changed after create intent")
        entry["spec_sha256"] = spec_hash
        journal.save()
        cluster.kubectl("create", "-o", "name", "-f", "-", input=json.dumps(desired))
    live = cluster.get(kind, name)
    uid = check_metadata(live, desired, entry.get("uid"), allow_terminating=allow_terminating)
    require(entry.get("spec_sha256") == native.canonical_hash(normalized_spec(live)),
            "Live stage resource spec differs from the durable create intent")
    if not entry.get("uid"):
        require(allow_create, "Stage resource UID has not been recorded")
        entry["uid"] = uid
        journal.save()
    return live


def volume_identity(cluster, claim, pod=None):
    spec = claim["spec"]
    require(claim["status"]["phase"] == "Bound" and spec["storageClassName"] == STORAGE_CLASS
            and spec["accessModes"] == ["ReadWriteOnce"] and spec["volumeMode"] == "Filesystem"
            and spec["resources"]["requests"]["storage"] == "10Gi", "Stage PVC differs")
    volume = cluster.get("pv", spec["volumeName"])
    pv = volume["spec"]
    ref = pv["claimRef"]
    name, uid = claim["metadata"]["name"], claim["metadata"]["uid"]
    require((ref["namespace"], ref["name"], ref["uid"]) == (NS, name, uid)
            and pv["persistentVolumeReclaimPolicy"] == "Retain"
            and pv["storageClassName"] == STORAGE_CLASS and pv["csi"]["driver"] == "ebs.csi.aws.com"
            and pv["capacity"]["storage"] == "10Gi", "Stage PV binding or retention differs")
    handle = pv["csi"]["volumeHandle"]
    require(re.fullmatch(r"vol-[0-9a-f]+", handle), "Stage PV has an invalid EBS volume handle")
    volumes = json.loads(cluster.helper["aws"]([
        "ec2", "describe-volumes", "--region", "eu-central-1", "--volume-ids", handle, "--output", "json",
    ], env=cluster.env))["Volumes"]
    zones = {
        zone for term in pv["nodeAffinity"]["required"]["nodeSelectorTerms"]
        for expr in term.get("matchExpressions", [])
        if expr["key"] in {"topology.ebs.csi.aws.com/zone", "topology.kubernetes.io/zone"}
        and expr["operator"] == "In" for zone in expr["values"]
    }
    require(len(volumes) == 1 and volumes[0]["VolumeId"] == handle and volumes[0]["Encrypted"] is True
            and volumes[0]["Size"] == 10 and volumes[0]["VolumeType"] == "gp3"
            and zones == {volumes[0]["AvailabilityZone"]}, "EBS encryption, type or AZ differs")
    az = volumes[0]["AvailabilityZone"]
    if pod is not None:
        node = cluster.get("node", pod["spec"]["nodeName"])
        node_labels = node["metadata"]["labels"]
        pod_labels = pod["metadata"]["labels"]
        require(node_labels["topology.kubernetes.io/zone"] == az
                and all(pod_labels[key] == node_labels.get(key) for key in POD_TOPOLOGY_LABELS & pod_labels.keys()),
                "Stage Pod topology differs from the EBS volume or Node")
    return {"pvc_uid": uid, "pv_uid": volume["metadata"]["uid"], "pv_name": volume["metadata"]["name"],
            "volume_handle": handle, "availability_zone": az}


def verify_pod_runtime(pod):
    status = pod["status"]
    for field, name in (("containerStatuses", "qdrant"), ("initContainerStatuses", "ensure-dir-ownership")):
        statuses = status[field]
        require(len(statuses) == 1 and statuses[0]["name"] == name and statuses[0]["imageID"] == IMAGE,
                "Stage runtime image identity differs")
    require(status["initContainerStatuses"][0]["state"]["terminated"]["exitCode"] == 0
            and status["containerStatuses"][0]["ready"], "Stage container startup differs")


def claim_users(cluster, stage):
    return [
        item["metadata"]["uid"] for item in list_items(cluster, "pods")
        if any(volume.get("persistentVolumeClaim", {}).get("claimName") == stage
               for volume in item["spec"].get("volumes", []))
    ]


def stage_objects(cluster, record, role, *, allow_create=False, allow_terminating=False):
    state = record.state
    stage = state["stage"]
    intents = {key: entry["intent"] for key, entry in state["resources"].items()}
    incident = state.get("spot_incident", False)
    desired_pod = pod_manifest(stage, role, intents[role], incident=incident)
    verify_service_scope(cluster, desired_pod["metadata"]["labels"])
    desired = resources(stage, intents)
    for key in ("knp", "cnp"):
        create_or_check(cluster, record, key, desired[key], allow_create=allow_create)
    claim = create_or_check(cluster, record, "claim", desired["claim"], allow_create=allow_create)
    entry = state["resources"][role]
    if allow_create and cluster.absent("pod", desired_pod["metadata"]["name"]):
        if incident:
            require(any(all(node["metadata"]["labels"].get(key) == value for key, value in ON_DEMAND.items())
                        and not node["spec"].get("unschedulable")
                        and not any(taint["effect"] in {"NoSchedule", "NoExecute"}
                                    for taint in node["spec"].get("taints", []))
                        and any(c["type"] == "Ready" and c["status"] == "True"
                                for c in node["status"]["conditions"])
                        for node in list_items(cluster, "nodes")),
                    "No schedulable EKS on-demand node is ready for the incident stage")
        require(not claim_users(cluster, stage), "Stage claim already has a Pod consumer")
        if claim["spec"].get("volumeName"):
            require(volume_identity(cluster, claim) == state.get("volume"),
                    "Bound EBS identity differs before creating the staged Pod")
    pod = create_or_check(cluster, record, role, desired_pod, allow_create=allow_create,
                          allow_terminating=allow_terminating)
    verify_service_scope(cluster, pod["metadata"]["labels"])
    require(claim_users(cluster, stage) == [entry["uid"]], "Stage claim has an unexpected Pod consumer")
    return claim, pod


def prepare_pod(cluster, record, role, *, allow_create):
    _, pod = stage_objects(cluster, record, role, allow_create=allow_create)
    name = pod["metadata"]["name"]
    cluster.kubectl("wait", "pod", name, "--for=condition=Ready", "--timeout=10m")
    claim, pod = stage_objects(cluster, record, role)
    verify_pod_runtime(pod)
    volume = volume_identity(cluster, claim, pod)
    if "volume" in record.state:
        require(record.state["volume"] == volume, "Staged EBS identity changed")
    else:
        require(allow_create and role == "restore", "Stage journal is missing the initial volume identity")
        record.state["volume"] = volume
        record.save()
    return name


def peer_id(client, old_peer):
    require(client.json("/")["version"] == "1.20.0", "Stage Qdrant version differs")
    cluster = client.json("/cluster")
    peer = cluster["peer_id"]
    require(peer != old_peer and cluster["status"] == "enabled"
            and cluster["peers"] == {str(peer): {"uri": PEER_URI}}
            and cluster["raft_info"]["leader"] == peer and cluster["raft_info"]["pending_operations"] == 0
            and cluster["consensus_thread_status"]["consensus_thread_status"] == "working",
            "Stage Qdrant is not a healthy independent loopback peer")
    return peer


def equivalent(actual, expected, peer):
    fields = ("version", "collection", "aliases", "config", "payload_schema", "local_shards", "points", "point_digest")
    require(all(actual[field] == expected[field] for field in fields)
            and actual["peer_id"] == peer and actual["peers"] == {str(peer): {"uri": PEER_URI}},
            "Staged Qdrant logical inventory differs from the reviewed backup")


def ready(client):
    deadline = time.monotonic() + 90
    request = urllib.request.Request(client.base + "/readyz", headers={"api-key": client.key})
    while True:
        remaining = deadline - time.monotonic()
        require(remaining > 0, "Qdrant did not become ready")
        try:
            with client.opener.open(request, timeout=min(5, remaining)) as response:
                require(response.status == 200, "Unexpected Qdrant readiness result")
            return
        except (urllib.error.URLError, TimeoutError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code != 503:
                raise
            time.sleep(min(1, max(0, deadline - time.monotonic())))


def upload(client, artifact, snapshot):
    data = artifact.read_bytes()
    require(len(data) == snapshot["bytes"] and hashlib.sha256(data).hexdigest() == snapshot["sha256"],
            "Snapshot bytes changed before upload")
    boundary = uuid.uuid4().hex
    head = (f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="snapshot"; filename="qdrant.snapshot"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n").encode()
    body = head + data + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        client.base + native.collection_path() + f"/snapshots/upload?priority=snapshot&wait=true&checksum={snapshot['sha256']}",
        method="POST", data=body, headers={
            "api-key": client.key, "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with client.opener.open(request, timeout=300) as response:
        result = json.load(response)
    require(result.get("status") == "ok" and result.get("result") is True, "Qdrant snapshot upload did not complete")


def read_stage(cluster, record, role, name, backup, *, restore=False):
    expected = backup["source_inventory"]["qdrant"]
    state = record.state
    secret = cluster.get("secret", AUTH_SECRET)
    key = check_secret(secret, backup)
    with native.port_forward(cluster, name, 6333) as endpoint:
        stage_objects(cluster, record, role)
        client = native.Qdrant(endpoint, key)
        ready(client)
        peer = peer_id(client, expected["peer_id"])
        if restore and state["phase"] == "new":
            require(client.json("/collections")["collections"] == [] and client.json("/aliases")["aliases"] == [],
                    "Initial staged Qdrant is not empty")
            source_guard(cluster, backup, incident=state.get("spot_incident", False))
            stage_objects(cluster, record, role)
            state["peer_id"] = peer
            state["phase"] = "uploading"
            record.save()
            upload(client, BACKUP / "qdrant.snapshot", backup["qdrant_snapshot"])
        require(peer == state.get("peer_id"), "Staged Qdrant peer identity changed")
        equivalent(native.qdrant_inventory(client), expected, peer)
    claim, pod = stage_objects(cluster, record, role)
    verify_pod_runtime(pod)
    require(volume_identity(cluster, claim, pod) == state["volume"], "Staged EBS identity changed")
    source_guard(cluster, backup, incident=state.get("spot_incident", False))


def retire_first_pod(cluster, record, backup):
    state = record.state
    first = f"{state['stage']}-restore"
    if not cluster.absent("pod", first):
        _, pod = stage_objects(cluster, record, "restore", allow_terminating=True)
        require(cluster.absent("pod", f"{state['stage']}-restart"), "Replacement Pod already exists")
        source_guard(cluster, backup, incident=state.get("spot_incident", False))
        if not pod["metadata"].get("deletionTimestamp"):
            native.SHARED["delete_owned"](cluster, f"/api/v1/namespaces/{NS}/pods/{first}", pod["metadata"]["uid"])
        if not cluster.absent("pod", first):
            cluster.kubectl("wait", "pod", first, "--for=delete", "--timeout=180s")


def rehearse(cluster, record, backup, *, verify_only=False):
    state = record.state
    source_guard(cluster, backup, incident=state.get("spot_incident", False))
    if verify_only:
        require(state["phase"] == "accepted", "Qdrant rehearsal is not accepted")
    if state["phase"] in {"new", "uploading", "verified"}:
        name = prepare_pod(cluster, record, "restore", allow_create=state["phase"] == "new")
        read_stage(cluster, record, "restore", name, backup, restore=True)
        state["phase"] = "verified"
        record.save()
        state["phase"] = "restarting"
        record.save()
    if state["phase"] == "restarting":
        retire_first_pod(cluster, record, backup)
    require(cluster.absent("pod", f"{state['stage']}-restore"), "Initial staged Pod still exists")
    name = prepare_pod(cluster, record, "restart", allow_create=state["phase"] == "restarting")
    read_stage(cluster, record, "restart", name, backup)
    require(state["resources"]["restore"]["uid"] != state["resources"]["restart"]["uid"],
            "Rehearsal did not replace the Pod")
    if state["phase"] == "restarting":
        state["phase"] = "accepted"
        state["accepted_at"] = native.timestamp()
        state["point_digest"] = POINT_SHA
        state["peer_uri"] = PEER_URI
        record.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check-backup", "run", "verify", "recover-spot-stage", "verify-spot-stage"))
    args = parser.parse_args()
    os.umask(0o077)
    try:
        backup = verified_backup()
        if args.action == "check-backup":
            print("Pinned Qdrant capture and all seven backup artifacts verified.")
            return
        incident = args.action in {"recover-spot-stage", "verify-spot-stage"}
        create = args.action in {"run", "recover-spot-stage"}
        root = INCIDENT_STATE_DIR if incident else STATE_DIR
        with journal(root, create=create, incident=incident) as record:
            rehearse(native.Cluster(), record, backup, verify_only=not create)
        print("Qdrant staged restore and restart verified. The retained stage is running.")
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
        if type(error) is RuntimeError:
            parser.exit(1, f"Qdrant stage stopped. {error}\n")
        parser.exit(1, f"Qdrant stage stopped with {type(error).__name__}. See the private stage receipt.\n")


if __name__ == "__main__":
    main()
