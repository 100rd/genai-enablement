#!/usr/bin/env python3
"""Rehearse a captured NATS account restore on an isolated retained EBS claim."""

import argparse
import copy
import fcntl
import json
import os
import re
import socket
import stat
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import capture

SHARED = capture.SHARED
require = capture.require
PRIVATE = capture.PRIVATE
NAMESPACE = capture.NAMESPACE
SOURCE = "omniscience-nats"
INCIDENT_NODE = "ip-10-1-40-64.eu-central-1.compute.internal"
INCIDENT_NODE_UID = "2e7d56f0-34ad-445a-841d-a45735ba01c1"
ON_DEMAND = {"eks.amazonaws.com/capacityType": "ON_DEMAND"}
INCIDENT_POD_UID = "2bdba0ec-737a-4dff-b7ef-9ff828bfc752"
CONFIG = "omniscience-nats-config"
TEMPLATE_SHA = "fd8b428b73c93198a32d4544014687938f34e4025097e76a42c943ef4a0eaa48"
CONFIG_SHA = "0f8af5df6ae5de6d44375f18caf96d2dd9965349b63d8b3ae47044574b2c699d"
BACKUP = capture.BACKUP_ROOT / "capture-nmq_o7wh"
RECEIPT_SHA = "da0a5889296385a577671d42984f04e7d36c7010e6a0fc746cadd4cb03601576"
ATTEMPTS = PRIVATE / "frankfurt-activation" / "secondary-storage-rehearsals"
LABEL = "recovery.omniscience.io/nats-attempt"
POD_TOPOLOGY_LABELS = {"topology.kubernetes.io/region", "topology.kubernetes.io/zone"}
CLAIM_SPEC = {
    "storageClassName": "splatform-gp3", "accessModes": ["ReadWriteOnce"],
    "resources": {"requests": {"storage": "10Gi"}}, "volumeMode": "Filesystem",
}
ALLOWED_BASELINE = {
    "endpointSelector": {},
    "ingress": [{"fromEntities": ["host", "remote-node", "kube-apiserver"]}],
    "egress": [
        {"toEntities": ["host", "remote-node", "kube-apiserver"]},
        {"toEndpoints": [{"matchLabels": {
            "k8s-app": "kube-dns", "k8s:io.kubernetes.pod.namespace": "kube-system",
        }}], "toPorts": [{"ports": [{"port": "53", "protocol": "UDP"}, {"port": "53", "protocol": "TCP"}]}]},
    ],
}


def private(path, mode, directory=False):
    info = path.lstat()
    require((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            and stat.S_IMODE(info.st_mode) == mode, "Unexpected backup or rehearsal path type/permissions")


def verified_capture():
    private(BACKUP, 0o700, directory=True)
    receipt_path = BACKUP / "receipt.json"
    private(receipt_path, 0o600)
    require(capture.file_hash(receipt_path) == RECEIPT_SHA, "Captured receipt SHA-256 differs")
    receipt = SHARED["read_private_json"](receipt_path)
    expected = {"qdrant.snapshot"}
    expected.update(f"nats/{stream}/{artifact}" for stream in capture.NATS_STREAMS
                    for artifact in ("backup.json", "stream.tar.s2"))
    require(receipt["status"] == "complete" and receipt["files"].keys() == expected,
            "Native capture receipt is incomplete")
    entries = list(BACKUP.rglob("*"))
    require(not any(path.is_symlink() for path in entries)
            and {path.relative_to(BACKUP).as_posix() for path in entries}
            == expected | {"receipt.json", "nats"} | {f"nats/{stream}" for stream in capture.NATS_STREAMS},
            "Native backup has missing or unexpected files")
    for name, evidence in receipt["files"].items():
        path = BACKUP / name
        for directory in path.parents:
            if directory == BACKUP:
                break
            private(directory, 0o700, directory=True)
        private(path, 0o600)
        require(path.stat().st_size == evidence["bytes"] and capture.file_hash(path) == evidence["sha256"],
                "Native snapshot artifact changed")
    return receipt


def incident_source_identity(cluster, captured):
    original = captured["stores"][SOURCE]
    expected = capture.SOURCES[SOURCE]
    require(all(original[key] == value for key, value in expected.items())
            and original["node"] == capture.SOURCE_NODE and original["node"] != INCIDENT_NODE
            and original["pod_uid"] != INCIDENT_POD_UID, "Captured NATS source pins differ")
    require(cluster.absent("node", original["node"]), "Original NATS source Node still exists")
    require(cluster.get("node", INCIDENT_NODE)["metadata"]["uid"] == INCIDENT_NODE_UID,
            "Incident NATS replacement Node UID changed")
    release, _ = SHARED["release_pin"](cluster, capture.RELEASE)
    secret = cluster.get("secret", "omniscience-api-secret")["metadata"]
    require({"uid": secret["uid"], "resource_version": secret["resourceVersion"]}
            == captured["qdrant_auth_ref"], "Omniscience authentication Secret metadata changed")
    sts = cluster.get("statefulset", SOURCE)
    pod = cluster.get("pod", f"{SOURCE}-0")
    meta = pod["metadata"]
    containers = pod["status"]["containerStatuses"]
    owners = [owner for owner in meta["ownerReferences"] if owner.get("controller")]
    require(sts["metadata"]["uid"] == expected["sts_uid"] and len(owners) == 1
            and owners[0]["kind"] == "StatefulSet" and owners[0]["name"] == SOURCE
            and owners[0]["uid"] == expected["sts_uid"]
            and meta["uid"] == INCIDENT_POD_UID and not meta.get("deletionTimestamp")
            and pod["spec"]["nodeName"] == INCIDENT_NODE
            and {container["name"]: container["imageID"] for container in containers} == expected["images"]
            and all(container["ready"] for container in containers), "Incident NATS source Pod or StatefulSet changed")
    claim = cluster.get("pvc", expected["pvc"])
    pv = cluster.get("pv", expected["pv"])
    ref = pv["spec"]["claimRef"]
    require(claim["metadata"]["uid"] == expected["pvc_uid"] and claim["status"]["phase"] == "Bound"
            and claim["spec"]["volumeName"] == expected["pv"] and pv["metadata"]["uid"] == expected["pv_uid"]
            and (ref["namespace"], ref["name"], ref["uid"]) == (NAMESPACE, expected["pvc"], expected["pvc_uid"])
            and pv["spec"]["persistentVolumeReclaimPolicy"] == "Retain"
            and pv["spec"]["hostPath"] == {"path": expected["path"], "type": "DirectoryOrCreate"}
            and [volume["persistentVolumeClaim"]["claimName"] for volume in pod["spec"]["volumes"]
                 if "persistentVolumeClaim" in volume] == [expected["pvc"]],
            "Incident NATS source claim or volume changed")
    return release, {
        **expected, "pod_uid": INCIDENT_POD_UID, "node": INCIDENT_NODE,
        "containers": {container["name"]: container["containerID"] for container in containers},
    }


def source_pin(cluster, receipt, incident=False):
    captured = receipt["source_inventory"]["source"]
    if incident:
        release, source = incident_source_identity(cluster, captured)
    else:
        identity = capture.source_identity(cluster, capture=False)
        release, source = identity["release"], identity["stores"][SOURCE]
        require(source == captured["stores"][SOURCE], "NATS source differs from native capture")
    require(release == captured["release"], "Omniscience Helm release differs from native capture")
    config = cluster.get("configmap", CONFIG)
    data = config["data"]
    require(set(data) == {"nats.conf"} and capture.hashlib.sha256(data["nats.conf"].encode()).hexdigest() == CONFIG_SHA,
            "NATS source ConfigMap content differs")
    return {
        "release": release, "source": source,
        "config": {"uid": config["metadata"]["uid"], "resource_version": config["metadata"]["resourceVersion"]},
    }, data["nats.conf"]


def loopback_config(raw):
    require(raw.count('  "http_port": 8222,') == raw.count('  "port": 4222,') == 1,
            "NATS source listen configuration differs")
    return raw.replace('  "http_port": 8222,', '  "http": "127.0.0.1:8222",').replace(
        '  "port": 4222,', '  "listen": "127.0.0.1:4222",',
    )


def matches(selector, labels):
    require(set(selector) <= {"matchLabels", "matchExpressions"}, "Unrecognized policy selector")
    def key_name(key):
        if ":" in key:
            prefix, key = key.split(":", 1)
            require(prefix in ("k8s", "any"), "Unrecognized Cilium selector label source")
        return key

    for key, value in selector.get("matchLabels", {}).items():
        if labels.get(key_name(key)) != value:
            return False
    for expression in selector.get("matchExpressions", []):
        key = key_name(expression["key"])
        operator = expression["operator"]
        values = expression.get("values", [])
        require(operator in ("In", "NotIn", "Exists", "DoesNotExist"), "Unrecognized selector operator")
        if (operator == "In" and labels.get(key) not in values
                or operator == "NotIn" and labels.get(key) in values
                or operator == "Exists" and key not in labels
                or operator == "DoesNotExist" and key in labels):
            return False
    return True


def objects(cluster, kind):
    return json.loads(cluster.kubectl("get", kind, "-o", "json"))["items"]


def isolation_check(cluster, labels):
    for svc in objects(cluster, "services"):
        selector = svc["spec"].get("selector")
        require(not selector or not matches({"matchLabels": selector}, labels),
                "An existing Service would select the rehearsal pod")
    for policy in objects(cluster, "networkpolicy"):
        spec = policy["spec"]
        if matches(spec["podSelector"], labels):
            require(not (spec.get("ingress") or spec.get("egress")),
                    "An existing Kubernetes allow policy selects the rehearsal pod")
    cilium_labels = {**labels, "io.kubernetes.pod.namespace": NAMESPACE,
                     "io.cilium.k8s.policy.serviceaccount": "default"}
    baseline_seen = False
    for kind in ("ciliumnetworkpolicy", "ciliumclusterwidenetworkpolicy"):
        for policy in objects(cluster, kind):
            name = policy["metadata"]["name"]
            rules = [policy["spec"]] if "spec" in policy else policy["specs"]
            for rule in rules:
                if kind == "ciliumclusterwidenetworkpolicy" and name == "default-deny-all":
                    require(len(rules) == 1 and {k: v for k, v in rule.items() if k != "description"} == ALLOWED_BASELINE,
                            "Clusterwide Cilium baseline changed")
                    baseline_seen = True
                    continue
                if "endpointSelector" not in rule:
                    require(not (rule.get("ingress") or rule.get("egress")), "Unrecognized Cilium allow rule")
                    continue
                if matches(rule["endpointSelector"], cilium_labels):
                    require(not (rule.get("ingress") or rule.get("egress")),
                            "An existing Cilium allow policy selects the rehearsal pod")
    require(baseline_seen, "Reviewed clusterwide Cilium baseline is absent")


def manifests(cluster, name, token, raw_config, incident=False):
    labels = {LABEL: token, "app.kubernetes.io/name": "nats-isolated-rehearsal"}
    isolation_check(cluster, labels)
    statefulset = cluster.get("statefulset", SOURCE)["spec"]
    template = statefulset["template"]
    require(capture.canonical_hash(template) == TEMPLATE_SHA, "Reviewed NATS pod template changed")
    spec = copy.deepcopy(template["spec"])
    require(spec["volumes"] == [
        {"configMap": {"defaultMode": 420, "name": CONFIG}, "name": "config"},
        {"emptyDir": {}, "name": "pid"},
    ], "Unexpected source NATS volume layout")
    require(not (spec.get("hostNetwork") or spec.get("hostPID") or spec.get("hostIPC")
                 or spec.get("hostAliases") or spec.get("initContainers"))
            and all("hostPath" not in v for v in spec["volumes"]), "Unexpected source pod template")
    require({c["name"] for c in spec["containers"]} == capture.SOURCES[SOURCE]["images"].keys(),
            "Unexpected NATS source container layout")
    cfg_volume = next(v for v in spec["volumes"] if v["name"] == "config")
    require(cfg_volume["configMap"]["name"] == CONFIG, "Unexpected source NATS config mount")
    cfg_volume["configMap"]["name"] = name
    templates = statefulset["volumeClaimTemplates"]
    require(len(templates) == 1, "Unexpected source NATS claim template count")
    volume = templates[0]
    require(volume["metadata"]["name"] == "omniscience-nats-js", "Unexpected source NATS claim template")
    spec["volumes"].append({"name": "omniscience-nats-js", "persistentVolumeClaim": {"claimName": name}})
    spec["automountServiceAccountToken"] = False
    spec["restartPolicy"] = "Never"
    if incident:
        spec["nodeSelector"] = {**spec.get("nodeSelector", {}), **ON_DEMAND}
    expected_mounts = {"nats": ["config", "pid", "omniscience-nats-js"], "reloader": ["pid", "config"]}
    for container in spec["containers"]:
        require([mount["name"] for mount in container["volumeMounts"]] == expected_mounts[container["name"]],
                "Unexpected source NATS container mounts")
        container["image"] = capture.SOURCES[SOURCE]["images"][container["name"]]
        require(not container.get("securityContext", {}).get("privileged")
                and not any(port.get("hostPort") for port in container.get("ports", [])),
                "Unexpected NATS container privileges or host port")
        for probe_name in ("startupProbe", "readinessProbe", "livenessProbe"):
            probe = container.get(probe_name)
            if probe is not None:
                http = probe.pop("httpGet")
                require(http["port"] == "monitor" and http["scheme"] == "HTTP", "Unexpected NATS probe")
                probe["exec"] = {"command": ["wget", "-qO", "/dev/null", "http://127.0.0.1:8222" + http["path"]]}
    metadata = {"name": name, "namespace": NAMESPACE, "labels": labels}
    return [
        {"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": metadata,
         "spec": copy.deepcopy(CLAIM_SPEC)},
        {"apiVersion": "v1", "kind": "ConfigMap", "metadata": metadata,
         "immutable": True, "data": {"nats.conf": loopback_config(raw_config)}},
        {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy", "metadata": metadata,
         "spec": {"podSelector": {"matchLabels": labels}, "policyTypes": ["Ingress", "Egress"],
                  "ingress": [], "egress": []}},
        {"apiVersion": "cilium.io/v2", "kind": "CiliumNetworkPolicy", "metadata": metadata,
         "spec": {"endpointSelector": {"matchLabels": labels},
                  "ingressDeny": [{"fromEntities": ["all"]}], "egressDeny": [{"toEntities": ["all"]}]}},
        {"apiVersion": "v1", "kind": "Pod", "metadata": {
            **metadata, "annotations": {"karpenter.sh/do-not-disrupt": "true"},
        }, "spec": spec},
    ]


def sync_json(directory, file, data):
    SHARED["write_private_json"](directory / file, data)
    capture.sync_directory(directory)


def attempt_prefix(incident):
    return "nats-incident-" if incident else "nats-rehearsal-"


def get_intent(directory, incident=False):
    private(directory, 0o700, directory=True)
    intent = SHARED["read_private_json"](directory / "intent.json")
    mode = "incident" if incident else "normal"
    require(directory.name.startswith(attempt_prefix(incident))
            and intent["name"] == directory.name
            and intent["token"] == directory.name.removeprefix(attempt_prefix(incident))
            and intent.get("mode", "normal") == mode
            and intent["backup_sha256"] == RECEIPT_SHA, "Rehearsal intent does not match its directory or mode")
    return intent


def prepare_attempt(path, incident=False):
    prefix = attempt_prefix(incident)
    ATTEMPTS.mkdir(mode=0o700, exist_ok=True)
    private(ATTEMPTS, 0o700, directory=True)
    capture.sync_directory(ATTEMPTS.parent)
    if path is None:
        token = uuid.uuid4().hex[:12]
        directory = ATTEMPTS / (prefix + token)
        directory.mkdir(mode=0o700)
        capture.sync_directory(ATTEMPTS)
        return directory
    require(path.parent.resolve() == ATTEMPTS.resolve() and not path.is_symlink()
            and bool(re.fullmatch(prefix + r"[a-f0-9]{12}", path.name)), "Unexpected rehearsal path")
    private(path, 0o700, directory=True)
    return path.resolve()


@contextmanager
def lock_attempt(directory):
    descriptor = os.open(directory / "lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def deny_policy_matches(actual, expected, kind):
    if kind == "networkpolicy":
        # Kubernetes omits empty rule arrays on read-back.
        return {"ingress": [], "egress": [], **actual} == expected
    return actual == expected


POD_DEFAULTS = {
    "preemptionPolicy": "PreemptLowerPriority",
    "priority": 0,
    "serviceAccount": "default",
    "serviceAccountName": "default",
    "tolerations": [
        {"effect": "NoExecute", "key": "node.kubernetes.io/not-ready", "operator": "Exists", "tolerationSeconds": 300},
        {"effect": "NoExecute", "key": "node.kubernetes.io/unreachable", "operator": "Exists", "tolerationSeconds": 300},
    ],
}


def verify_pod_spec(actual, expected):
    spec = copy.deepcopy(actual)
    for field, default in POD_DEFAULTS.items():
        if field in spec and field not in expected:
            require(spec.pop(field) == default, f"Rehearsal pod default {field} differs")
    if "nodeName" not in expected:
        spec.pop("nodeName", None)
    require(spec == expected, "Rehearsal pod specification differs from the pinned template")


def verify_claim_spec(spec, allow_binding=False):
    actual = {"volumeMode": "Filesystem", **spec}
    bound_volume = actual.pop("volumeName", "")
    require(not bound_volume or allow_binding, "Unexpected prebinding on rehearsal claim")
    require(actual == CLAIM_SPEC, "Rehearsal claim specification differs")
    return bound_volume


def claim_consumers(cluster, name):
    return [
        pod["metadata"]["uid"] for pod in objects(cluster, "pods")
        if any(volume.get("persistentVolumeClaim", {}).get("claimName") == name
               for volume in pod["spec"].get("volumes", []))
    ]


def verify_claim_before_pod(cluster, intent):
    name = intent["name"]
    pvc_uid = intent["uids"]["persistentvolumeclaim"]
    claim = cluster.get("pvc", name)
    require(claim["metadata"]["uid"] == pvc_uid, "Rehearsal PVC UID changed before pod creation")
    bound_volume = verify_claim_spec(claim["spec"], allow_binding=True)
    phase = claim["status"]["phase"]
    require(phase in ("Pending", "Bound"), "Rehearsal claim has unexpected status")
    if bound_volume or phase == "Bound":
        require(intent.get("volume") is not None
                and volume_identity(cluster, name, pvc_uid) == intent["volume"],
                "Prebound rehearsal claim lacks its previously verified EBS identity")
    require(not claim_consumers(cluster, name), "Another pod already references the rehearsal claim")


def resource_labels_match(resource, expected, kind):
    labels = resource["metadata"]["labels"]
    if kind == "pod" and resource["spec"].get("nodeName"):
        labels = {key: value for key, value in labels.items() if key not in POD_TOPOLOGY_LABELS}
    return labels == expected


def verify_pod_topology(cluster, pod, availability_zone, incident=False):
    node = cluster.get("node", pod["spec"]["nodeName"])
    node_labels = node["metadata"]["labels"]
    pod_labels = pod["metadata"]["labels"]
    if incident:
        require(all(node_labels.get(key) == value for key, value in ON_DEMAND.items()),
                "Incident NATS rehearsal requires an On-Demand Node")
    require(node_labels.get("topology.kubernetes.io/zone") == availability_zone
            and all(pod_labels[key] == node_labels.get(key) for key in POD_TOPOLOGY_LABELS & pod_labels.keys()),
            "Rehearsal Pod topology differs from its Node or EBS volume")


def ensure_owned(cluster, directory, intent, manifest):
    kind = manifest["kind"].lower()
    name = intent["name"]
    uids = intent["uids"]
    if cluster.absent(kind, name):
        require(kind not in uids, f"Previously owned rehearsal {kind} is missing")
        payload = json.dumps(manifest)
        if kind == "pod":
            verify_claim_before_pod(cluster, intent)
        if kind in ("persistentvolumeclaim", "pod"):
            admitted = json.loads(cluster.kubectl("create", "--dry-run=server", "-f", "-", "-o", "json",
                                                  input=payload))
            if kind == "persistentvolumeclaim":
                verify_claim_spec(admitted["spec"])
            else:
                verify_pod_spec(admitted["spec"], manifest["spec"])
                verify_claim_before_pod(cluster, intent)
        cluster.kubectl("create", "-f", "-", input=payload)
    current = cluster.get(kind, name)
    meta = current["metadata"]
    require(resource_labels_match(current, manifest["metadata"]["labels"], kind)
            and uids.get(kind, meta["uid"]) == meta["uid"],
            f"Foreign or replaced rehearsal {kind}")
    if kind in ("networkpolicy", "ciliumnetworkpolicy"):
        require(deny_policy_matches(current["spec"], manifest["spec"], kind), "Rehearsal network policy differs")
    if kind == "configmap":
        require(current.get("immutable") is True and current["data"] == manifest["data"],
                "Rehearsal NATS configuration differs")
    if kind == "pod":
        verify_pod_spec(current["spec"], manifest["spec"])
    if kind == "persistentvolumeclaim":
        verify_claim_spec(current["spec"], allow_binding=True)
    if kind not in uids:
        uids[kind] = meta["uid"]
        sync_json(directory, "intent.json", intent)


def volume_identity(cluster, name, pvc_uid):
    claim = cluster.get("pvc", name)
    spec = claim["spec"]
    verify_claim_spec(spec, allow_binding=True)
    require(claim["metadata"]["uid"] == pvc_uid and claim["status"]["phase"] == "Bound"
            and spec["storageClassName"] == "splatform-gp3" and spec["accessModes"] == ["ReadWriteOnce"]
            and spec["resources"]["requests"]["storage"] == "10Gi", "Unexpected rehearsal claim")
    volume = cluster.get("pv", spec["volumeName"])
    pv = volume["spec"]
    ref = pv["claimRef"]
    handle = pv["csi"]["volumeHandle"]
    require((ref["namespace"], ref["name"], ref["uid"]) == (NAMESPACE, name, pvc_uid)
            and pv["persistentVolumeReclaimPolicy"] == "Retain" and pv["csi"]["driver"] == "ebs.csi.aws.com"
            and bool(re.fullmatch(r"vol-[0-9a-f]+", handle)), "Unexpected rehearsal EBS PV binding")
    ebs = json.loads(cluster.helper["aws"](
        ["ec2", "describe-volumes", "--region", "eu-central-1", "--volume-ids", handle, "--output", "json"],
        env=cluster.env,
    ))["Volumes"]
    terms = pv["nodeAffinity"]["required"]["nodeSelectorTerms"]
    zones = {zone for term in terms for expr in term["matchExpressions"]
             if expr["key"] in ("topology.ebs.csi.aws.com/zone", "topology.kubernetes.io/zone")
             and expr["operator"] == "In" for zone in expr["values"]}
    require(len(ebs) == 1 and ebs[0]["VolumeId"] == handle and ebs[0]["Encrypted"] is True
            and ebs[0]["Size"] == 10 and ebs[0]["VolumeType"] == "gp3"
            and zones == {ebs[0]["AvailabilityZone"]}, "Unexpected rehearsal EBS capacity, encryption or AZ")
    return {"pvc_uid": pvc_uid, "pv_uid": volume["metadata"]["uid"], "pv": volume["metadata"]["name"],
            "volume_handle": handle, "availability_zone": ebs[0]["AvailabilityZone"]}


def stage_identity(cluster, intent, expected_manifests):
    name = intent["name"]
    uids = intent["uids"]
    for manifest in expected_manifests:
        kind = manifest["kind"].lower()
        current = cluster.get(kind, name)
        require(current["metadata"]["uid"] == uids[kind]
                and resource_labels_match(current, manifest["metadata"]["labels"], kind),
                f"Rehearsal {kind} identity changed")
        if kind in ("networkpolicy", "ciliumnetworkpolicy"):
            require(deny_policy_matches(current["spec"], manifest["spec"], kind), "Rehearsal deny policy changed")
        if kind == "configmap":
            require(current.get("immutable") is True and current["data"] == manifest["data"],
                    "Rehearsal configuration changed")
        if kind == "pod":
            verify_pod_spec(current["spec"], manifest["spec"])
            pod = current
    specs = pod["spec"]
    containers = pod["status"]["containerStatuses"]
    actual = {c["name"]: c["imageID"] for c in containers}
    require(actual == capture.SOURCES[SOURCE]["images"] and all(c["ready"] for c in containers)
            and not specs.get("hostNetwork")
            and specs.get("automountServiceAccountToken") is False,
            "Rehearsal pod images or isolation flags differ")
    mounted = [v["persistentVolumeClaim"]["claimName"] for v in specs["volumes"] if "persistentVolumeClaim" in v]
    config_mounts = [v["configMap"]["name"] for v in specs["volumes"] if "configMap" in v]
    require(mounted == [name] and config_mounts == [name], "Rehearsal pod data or configuration mount differs")
    require(claim_consumers(cluster, name) == [uids["pod"]], "Unexpected rehearsal PVC consumer")
    for item in objects(cluster, "endpointslices"):
        endpoints = item["endpoints"]
        if endpoints is None:
            continue
        require(not any((ep.get("targetRef") or {}).get("uid") == uids["pod"] for ep in endpoints),
                "A Service endpoint targets the rehearsal pod")
    volume = volume_identity(cluster, name, uids["persistentvolumeclaim"])
    verify_pod_topology(cluster, pod, volume["availability_zone"], incident=intent.get("mode") == "incident")
    isolation_check(cluster, pod["metadata"]["labels"])
    return volume


def stage_inventory(cluster, name, expected_account, empty=False):
    def monitor(path):
        return json.loads(cluster.kubectl("exec", name, "-c", "nats", "--", "wget", "-qO-",
                                         "http://127.0.0.1:8222/" + path))

    server = monitor("varz")
    require(server["version"] == "2.15.2" and server["server_name"] == name
            and server["host"] == server["http_host"] == "127.0.0.1"
            and server["port"] == 4222 and server["http_port"] == 8222
            and not any(server.get(key) for key in ("routes", "gateways", "leafnodes", "connections")),
            "Rehearsal NATS bind, version, peer topology or connections differ")
    detail = monitor("jsz?accounts=true&streams=true&consumers=true&config=true")
    accounts = detail["account_details"]
    require(len(accounts) == detail["accounts"] == 1 and accounts[0]["id"] == expected_account,
            "Rehearsal JetStream account differs")
    raw_streams = accounts[0].get("stream_detail", [])
    if empty:
        require(detail["streams"] == detail["consumers"] == detail["messages"] == 0 and not raw_streams,
                "Rehearsal NATS is not empty")
    else:
        require(len(raw_streams) == detail["streams"] == len(capture.NATS_STREAMS)
                and detail["consumers"] == sum(map(len, capture.NATS_STREAMS.values()))
                and {stream["name"] for stream in raw_streams} == capture.NATS_STREAMS.keys(),
                "Restored JetStream inventory differs")
    streams = {}
    for stream in raw_streams:
        consumers = stream.get("consumer_detail", [])
        require(len(consumers) == stream["state"]["consumer_count"] and
                {item["name"] for item in consumers} == capture.NATS_STREAMS[stream["name"]],
                "Restored JetStream durable inventory differs")
        streams[stream["name"]] = {
            "config": stream["config"], "state": stream["state"],
            "consumers": {item["name"]: {key: value for key, value in item.items() if key != "ts"}
                          for item in consumers},
        }
    return {"version": server["version"], "account": accounts[0]["id"], "streams": streams}


def verify_greeting(endpoint, name):
    host, port = endpoint.split(":")
    require(host == "127.0.0.1", "Unexpected NATS port-forward address")
    with socket.create_connection((host, int(port)), timeout=5) as connection:
        with connection.makefile("rb") as stream:
            line = stream.readline(8192)
    require(line.startswith(b"INFO ") and line.endswith(b"\r\n"), "No NATS greeting over loopback port-forward")
    info = json.loads(line[5:])
    require(info["version"] == "2.15.2" and info["server_name"] == name
            and not info.get("auth_required") and not info.get("tls_required"),
            "Port-forward reached an unexpected NATS server")


def verify_forward(cluster, name):
    with capture.port_forward(cluster, name, 4222) as endpoint:
        verify_greeting(endpoint, name)


def stage(cluster, directory, receipt, incident=False):
    source, raw = source_pin(cluster, receipt, incident)
    name = directory.name
    token = name.removeprefix(attempt_prefix(incident))
    if (directory / "intent.json").exists():
        intent = get_intent(directory, incident)
        require(intent["name"] == name and intent["token"] == token and intent["source"] == source
                and intent["backup_sha256"] == RECEIPT_SHA, "Rehearsal intent differs from source or capture")
    else:
        intent = {"name": name, "token": token, "source": source, "backup_sha256": RECEIPT_SHA,
                  "mode": "incident" if incident else "normal", "uids": {}}
        sync_json(directory, "intent.json", intent)
    require(not (directory / "stop-intent.json").exists(), "Rehearsal is stopping or stopped")
    storage = cluster.get("storageclass", "splatform-gp3")
    require(storage["provisioner"] == "ebs.csi.aws.com" and storage["reclaimPolicy"] == "Retain"
            and storage["volumeBindingMode"] == "WaitForFirstConsumer"
            and storage["parameters"].get("encrypted") == "true", "Unexpected EBS rehearsal StorageClass")
    desired = manifests(cluster, name, token, raw, incident)
    for manifest in desired:
        ensure_owned(cluster, directory, intent, manifest)
    cluster.kubectl("wait", "pod", name, "--for=condition=Ready", "--timeout=10m")
    require(source_pin(cluster, receipt, incident)[0] == source, "NATS source changed while staging")
    volume = stage_identity(cluster, intent, desired)
    require(intent.get("volume", volume) == volume, "Rehearsal EBS volume identity changed")
    if "volume" not in intent:
        intent["volume"] = volume
        sync_json(directory, "intent.json", intent)
    expected = receipt["source_inventory"]["nats"]
    if not (directory / "restore-intent.json").exists():
        stage_inventory(cluster, name, expected["account"], empty=True)
    verify_forward(cluster, name)
    sync_json(directory, "stage-ready.json", {"source": source, "uids": intent["uids"], "volume": volume})


def pre_restore(cluster, directory, receipt, incident=False):
    intent = get_intent(directory, incident)
    require(not (directory / "stop-intent.json").exists(), "Rehearsal is stopping or stopped")
    source, raw = source_pin(cluster, receipt, incident)
    require(intent["source"] == source and intent["backup_sha256"] == RECEIPT_SHA,
            "Rehearsal source or backup differs")
    desired = manifests(cluster, intent["name"], intent["token"], raw, incident)
    ready = SHARED["read_private_json"](directory / "stage-ready.json")
    require(ready == {"source": source, "uids": intent["uids"],
                      "volume": stage_identity(cluster, intent, desired)}, "Rehearsal readiness identity changed")
    return intent, ready


def creation_time(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z", value)
    if not match:
        return None
    try:
        second = datetime.fromisoformat(match[1])
    except ValueError:
        return None
    return second, int((match[2] or "").ljust(9, "0"))


def restore_evidence(observed, expected):
    """Compare the pinned NATS file-store restore, retaining the raw evidence digest."""
    compared = copy.deepcopy(observed)
    if observed.get("version") == expected.get("version") == "2.15.2":
        for name, source in expected["streams"].items():
            restored = compared["streams"].get(name)
            if restored is None or source["config"].get("storage") != "file":
                continue
            before, after = source["state"], restored["state"]
            if not all(state.get(key) == 0 for state in (before, after)
                       for key in ("messages", "bytes", "last_seq")):
                continue
            if before.get("first_seq") == 0 and after.get("first_seq") == 1:
                # RestoreStreamV2 compacts before replay. File-store purge sets FirstSeq to LastSeq + 1.
                after["first_seq"] = 0
            if after.get("first_seq") != before.get("first_seq") or before.get("first_seq") not in (0, 1):
                continue
            for durable, original in source["consumers"].items():
                current = restored["consumers"].get(durable)
                if current is None or original["config"].get("durable_name") != durable:
                    continue
                zero_cursor = {"consumer_seq": 0, "stream_seq": 0}
                if not all(
                    item.get("delivered") == item.get("ack_floor") == zero_cursor
                    and all(item.get(key) == 0 for key in ("num_ack_pending", "num_redelivered", "num_waiting",
                                                           "num_pending"))
                    for item in (original, current)
                ):
                    continue
                # addConsumerForRestore initializes the consumer's creation time before restoring its cursor.
                original_time, restored_time = creation_time(original.get("created")), creation_time(current.get("created"))
                if original_time is not None and restored_time is not None and restored_time > original_time:
                    current["created"] = original["created"]
    require(compared == expected, "Restored JetStream config, consumer cursors, or stream state differs from capture")
    return {
        "logical_sha256": capture.canonical_hash(expected),
        "observed_sha256": capture.canonical_hash(observed),
        "comparison": "nats-2.15.2-empty-native-restore-v1",
        "streams": len(expected["streams"]),
        "consumers": sum(len(stream["consumers"]) for stream in expected["streams"].values()),
    }


def verify_restore(cluster, directory, receipt, incident=False):
    intent, ready = pre_restore(cluster, directory, receipt, incident)
    restore_intent = SHARED["read_private_json"](directory / "restore-intent.json")
    require(restore_intent == {"backup_sha256": RECEIPT_SHA, "ready": ready},
            "Rehearsal restore intent changed")
    expected = receipt["source_inventory"]["nats"]
    observed = stage_inventory(cluster, intent["name"], expected["account"])
    if incident:
        evidence = restore_evidence(observed, expected)
    else:
        require(observed == expected, "Restored JetStream config, consumer cursors, or stream state differs from capture")
        evidence = {
            "logical_sha256": capture.canonical_hash(observed),
            "streams": len(observed["streams"]),
            "consumers": sum(len(stream["consumers"]) for stream in observed["streams"].values()),
        }
    require(pre_restore(cluster, directory, receipt, incident) == (intent, ready), "Rehearsal identities changed during verification")
    if incident:
        inventory = directory / "restored-inventory.json"
        if inventory.exists():
            require(SHARED["read_private_json"](inventory) == observed, "Existing raw restore inventory differs")
        else:
            sync_json(directory, inventory.name, observed)
    sync_json(directory, "restore-verified.json", {**restore_intent, **evidence})


def restore(cluster, directory, receipt, archive, incident=False):
    require(not (directory / "restore-intent.json").exists(),
            "Restore was already attempted. Verify its result or stop and open a new retained attempt.")
    intent, ready = pre_restore(cluster, directory, receipt, incident)
    name = intent["name"]
    with tempfile.TemporaryDirectory(prefix="nats-restore-cli-", dir=PRIVATE) as tmp:
        binary, metadata = capture.extract_nats_cli(archive, Path(tmp))
        require(metadata == receipt["nats_cli"], "NATS CLI archive differs from captured version")
        expected = receipt["source_inventory"]["nats"]
        env = {key: value for key, value in os.environ.items() if not key.startswith("NATS_")}
        with capture.port_forward(cluster, name, 4222) as endpoint:
            stage_inventory(cluster, name, expected["account"], empty=True)
            verify_greeting(endpoint, name)
            require(pre_restore(cluster, directory, receipt, incident) == (intent, ready), "Rehearsal changed before restore")
            sync_json(directory, "restore-intent.json", {"backup_sha256": RECEIPT_SHA, "ready": ready})
            subprocess.run(
                [str(binary), "--no-context", "--server", f"nats://{endpoint}", "--timeout", "2m",
                 "account", "restore", str(BACKUP / "nats")],
                env=env, capture_output=True, check=True, timeout=300,
            )
    verify_restore(cluster, directory, receipt, incident)


def stop(cluster, directory, incident=False):
    intent = get_intent(directory, incident)
    name = intent["name"]
    uids = intent["uids"]
    paths = {
        "pod": ("/api/v1", "pods"), "configmap": ("/api/v1", "configmaps"),
        "networkpolicy": ("/apis/networking.k8s.io/v1", "networkpolicies"),
        "ciliumnetworkpolicy": ("/apis/cilium.io/v2", "ciliumnetworkpolicies"),
    }
    for kind in paths:
        if not cluster.absent(kind, name):
            require(kind in uids and cluster.get(kind, name)["metadata"]["uid"] == uids[kind],
                    f"Cannot remove foreign or unpinned rehearsal {kind}; reconcile stage before stopping")
    stop_path = directory / "stop-intent.json"
    proof = {"name": name, "uids": uids, "backup_sha256": RECEIPT_SHA}
    if stop_path.exists():
        require(SHARED["read_private_json"](stop_path) == proof, "Rehearsal shutdown intent changed")
    else:
        sync_json(directory, "stop-intent.json", proof)
    for kind, (prefix, resource) in paths.items():
        if cluster.absent(kind, name):
            continue
        require(kind in uids and cluster.get(kind, name)["metadata"]["uid"] == uids[kind],
                f"Cannot remove foreign or unpinned rehearsal {kind}")
        SHARED["delete_owned"](cluster, f"{prefix}/namespaces/{NAMESPACE}/{resource}/{name}", uids[kind])
        if not cluster.absent(kind, name):
            require(cluster.get(kind, name)["metadata"]["uid"] == uids[kind], "Rehearsal resource UID changed")
            cluster.kubectl("wait", kind, name, "--for=delete", "--timeout=120s")
    if "persistentvolumeclaim" in uids:
        require(cluster.get("pvc", name)["metadata"]["uid"] == uids["persistentvolumeclaim"],
                "Rehearsal PVC changed during shutdown")
    sync_json(directory, "stopped.json", proof)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("preflight").add_argument("--incident", action="store_true")
    for name in ("stage", "restore", "verify", "stop"):
        command = commands.add_parser(name)
        command.add_argument("--incident", action="store_true")
        command.add_argument("--attempt", type=Path, required=name != "stage")
        if name == "restore":
            command.add_argument("--nats-archive", type=Path, required=True)
    args = parser.parse_args()
    try:
        cluster = capture.Cluster()
        receipt = None if args.action == "stop" else verified_capture()
        if args.action == "preflight":
            _, raw = source_pin(cluster, receipt, args.incident)
            manifests(cluster, attempt_prefix(args.incident) + "preflight", "preflight", raw, args.incident)
        else:
            directory = prepare_attempt(args.attempt, args.incident)
            print(f"Rehearsal directory {directory}", flush=True)
            with lock_attempt(directory):
                if args.action == "stage":
                    stage(cluster, directory, receipt, args.incident)
                elif args.action == "restore":
                    restore(cluster, directory, receipt, args.nats_archive, args.incident)
                elif args.action == "verify":
                    verify_restore(cluster, directory, receipt, args.incident)
                else:
                    stop(cluster, directory, args.incident)
    except RuntimeError as error:
        parser.exit(1, f"{args.action} failed: {error}\n")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        parser.exit(1, f"{args.action} failed. Inspect rehearsal status without printing credentials or backup data.\n")
    print(f"{args.action} passed")


if __name__ == "__main__":
    main()
