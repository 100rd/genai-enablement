#!/usr/bin/env python3
"""Inventory or capture native Omniscience NATS and Qdrant snapshots."""

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import runpy
import selectors
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = runpy.run_path(str(HERE.parent / "omniscience-storage" / "recover.py"))
Cluster = SHARED["Cluster"]
NAMESPACE = SHARED["NAMESPACE"]
PRIVATE = SHARED["PRIVATE"]
require = SHARED["require"]
BACKUP_ROOT = PRIVATE / "frankfurt-activation" / "secondary-storage-backups"
RELEASE = 5
SOURCE_NODE = "ip-10-1-14-115.eu-central-1.compute.internal"
NATS_ARCHIVES = {
    "arm64": "39a68a0673f1b87d0887f48b02ca17f5d803f5689d4a9cff8e74b6411d6baef7",
    "x86_64": "87cbc208a9fb1dcd3be364ab351a14901c9c29d50ef6a7a2fd897362dbb0db47",
}
NATS_CLI_VERSION = "0.4.0"
NATS_STREAMS = {
    "INGEST_CHANGES": {"omniscience-ingestion-worker"},
    "INGEST_DLQ": set(),
    "OUTBOX": {
        "omniscience-outbox-entity-consumer",
        "omniscience-outbox-edge-consumer",
        "omniscience-outbox-merge-consumer",
    },
}
QDRANT_COLLECTION = "omniscience__all-MiniLM-L6-v2__d384"
SOURCES = {
    "omniscience-nats": {
        "sts_uid": "2e4356df-c974-431d-855b-0f1a43f1d53d",
        "pod_uid": "ae111a93-448b-453f-8953-93d9e9e523da",
        "pvc": "omniscience-nats-js-omniscience-nats-0",
        "pvc_uid": "18b96c9a-a4c2-40ce-869e-d68758cac553",
        "pv": "pv-splatform-nats-noniac",
        "pv_uid": "7406b00b-6788-4065-bc92-d2d8496a0845",
        "path": "/tmp/splatform-nats-noniac",
        "images": {
            "nats": "docker.io/library/nats@sha256:afae2fdbe2e326c65e1246cb83b9d05d319188734f3bd577ac8072daae78a10f",
            "reloader": "docker.io/natsio/nats-server-config-reloader@sha256:d758a82a9c20337e46c2f7356a413faa52cf4d6b02497c3ad81f72f1ba106464",
        },
    },
    "omniscience-qdrant": {
        "sts_uid": "a7aab595-2ad1-42cd-b87b-73e9fd483b4a",
        "pod_uid": "e9f94ffc-2064-41fc-96ed-8b426bc901c1",
        "pvc": "qdrant-storage-omniscience-qdrant-0",
        "pvc_uid": "db4ff201-cc89-4406-a0ef-3a7d3215a090",
        "pv": "pv-splatform-qdrant-noniac",
        "pv_uid": "f09888d2-f417-465b-84b7-8d67fa416fb4",
        "path": "/tmp/splatform-qdrant-noniac",
        "images": {
            "qdrant": "docker.io/qdrant/qdrant@sha256:9bfc89f9914fc14876a88c05270685921a55b8877b254a98bcc1cc2f0a424cd2",
        },
    },
}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_identity(cluster, capture):
    pin, _ = SHARED["release_pin"](cluster, RELEASE)
    identities = {}
    for name, expected in SOURCES.items():
        sts = cluster.get("statefulset", name)
        pod = cluster.get("pod", f"{name}-0")
        claim = cluster.get("pvc", expected["pvc"])
        pv = cluster.get("pv", expected["pv"])
        ref = pv["spec"]["claimRef"]
        status = pod["status"]["containerStatuses"]
        images = {container["name"]: container["imageID"] for container in status}
        owner = [ref["uid"] for ref in pod["metadata"]["ownerReferences"] if ref.get("controller")]
        require(sts["metadata"]["uid"] == expected["sts_uid"]
                and pod["metadata"]["uid"] == expected["pod_uid"] and owner == [expected["sts_uid"]]
                and pod["spec"]["nodeName"] == SOURCE_NODE
                and images == expected["images"] and all(container["ready"] for container in status),
                f"{name} source StatefulSet, pod, node or image changed")
        require(claim["metadata"]["uid"] == expected["pvc_uid"]
                and claim["status"]["phase"] == "Bound" and claim["spec"]["volumeName"] == expected["pv"]
                and pv["metadata"]["uid"] == expected["pv_uid"]
                and (ref["namespace"], ref["name"], ref["uid"]) == (NAMESPACE, expected["pvc"], expected["pvc_uid"])
                and pv["spec"]["persistentVolumeReclaimPolicy"] == "Retain"
                and pv["spec"]["hostPath"] == {"path": expected["path"], "type": "DirectoryOrCreate"}
                and [v["persistentVolumeClaim"]["claimName"] for v in pod["spec"]["volumes"]
                     if "persistentVolumeClaim" in v] == [expected["pvc"]],
                f"{name} source claim or volume changed")
        protected = pod["metadata"].get("annotations", {}).get("karpenter.sh/do-not-disrupt") == "true"
        if capture:
            require(protected, f"{name} lacks temporary disruption protection")
        identities[name] = {**expected, "node": SOURCE_NODE, "disruption_protected": protected,
                            "containers": {item["name"]: item["containerID"] for item in status}}
    secret = cluster.get("secret", "omniscience-api-secret")["metadata"]
    return {"release": pin, "stores": identities,
            "qdrant_auth_ref": {"uid": secret["uid"], "resource_version": secret["resourceVersion"]}}


def nats_monitor(cluster, path):
    return json.loads(cluster.kubectl(
        "exec", "omniscience-nats-0", "-c", "nats", "--",
        "wget", "-qO-", "http://127.0.0.1:8222/" + path,
    ))


def nats_inventory(cluster, capture):
    server = nats_monitor(cluster, "varz")
    require(server["version"] == "2.15.2" and not any(server.get(key) for key in ("routes", "gateways", "leafnodes")),
            "NATS server version or topology differs")
    if capture:
        require(server["connections"] == 0, "NATS still has active client connections")
    detail = nats_monitor(cluster, "jsz?accounts=true&streams=true&consumers=true&config=true")
    accounts = detail["account_details"]
    require(len(accounts) == detail["accounts"] == 1, "Unexpected JetStream account count")
    raw_streams = accounts[0]["stream_detail"]
    require(len(raw_streams) == detail["streams"] == len(NATS_STREAMS)
            and {stream["name"] for stream in raw_streams} == NATS_STREAMS.keys(),
            "Unexpected JetStream stream inventory")
    streams = {}
    for stream in raw_streams:
        name, config, state = stream["name"], stream["config"], stream["state"]
        require(config["storage"] == "file" and config["num_replicas"] == 1,
                "JetStream is not a single-replica file stream")
        consumers = stream.get("consumer_detail", [])
        require(len(consumers) == state["consumer_count"] == len(NATS_STREAMS[name])
                and {item["name"] for item in consumers} == NATS_STREAMS[name],
                "Unexpected JetStream durable consumer inventory")
        require(all(item["config"]["durable_name"] == item["name"] for item in consumers),
                "Unexpected ephemeral JetStream consumer")
        streams[name] = {
            "config": config, "state": state,
            "consumers": {
                item["name"]: {key: value for key, value in item.items() if key != "ts"} for item in consumers
            },
        }
    require(detail["consumers"] == sum(len(x) for x in NATS_STREAMS.values()), "JetStream consumer total differs")
    return {"version": server["version"], "account": accounts[0]["id"], "streams": streams}


@contextmanager
def port_forward(cluster, pod, remote):
    with tempfile.TemporaryDirectory(prefix="secondary-storage-kube-", dir=PRIVATE) as directory:
        env = SHARED["helm_context"](cluster, Path(directory) / "kubeconfig")
        command = [
            "kubectl", "--context", cluster.helper["CONTEXT"], "-n", NAMESPACE,
            "port-forward", "--address", "127.0.0.1", f"pod/{pod}", f":{remote}",
        ]
        with subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True) as proc:
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(proc.stdout, selectors.EVENT_READ)
                    require(bool(selector.select(timeout=20)), "Loopback port-forward did not become ready")
                    line = proc.stdout.readline()
                match = re.fullmatch(r"Forwarding from 127\.0\.0\.1:(\d+) -> (\d+)\n", line)
                require(match is not None and int(match.group(2)) == remote, "Unexpected port-forward endpoint")
                yield f"127.0.0.1:{match.group(1)}"
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Qdrant unexpectedly redirected a loopback request")


class Qdrant:
    def __init__(self, endpoint, key):
        require(bool(re.fullmatch(r"127\.0\.0\.1:\d+", endpoint)) and bool(key), "Invalid Qdrant loopback connection")
        self.base = "http://" + endpoint
        self.key = key
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, path, method="GET", data=None):
        body = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(self.base + path, method=method, data=body,
                                         headers={"api-key": self.key, "Content-Type": "application/json"})
        return self.opener.open(request, timeout=120)

    def json(self, path, method="GET", data=None):
        with self.request(path, method, data) as response:
            result = json.load(response)
        return result.get("result", result)


@contextmanager
def qdrant_client(cluster):
    secret = cluster.get("secret", "omniscience-api-secret")
    key = base64.b64decode(secret["data"]["QDRANT_API_KEY"], validate=True).decode()
    with port_forward(cluster, "omniscience-qdrant-0", 6333) as endpoint:
        yield Qdrant(endpoint, key)


def collection_path():
    return "/collections/" + urllib.parse.quote(QDRANT_COLLECTION, safe="")


def validate_qdrant_topology(cluster, detail, topology, count):
    local = topology["local_shards"]
    raft = cluster["raft_info"]
    params = detail["config"]["params"]
    require(cluster["status"] == "enabled" and len(cluster["peers"]) == 1
            and str(cluster["peer_id"]) in cluster["peers"] and raft["pending_operations"] == 0
            and not cluster.get("consensus_thread_status", {}).get("consensus_thread_status") == "stopped",
            "Qdrant is not the reviewed single-peer distributed cluster")
    require(detail["status"] == "green" and params["shard_number"] == params["replication_factor"]
            == params["write_consistency_factor"] == 1 and len(local) == 1
            and local[0]["shard_id"] == 0 and local[0]["state"] == "Active" and local[0]["points_count"] == count
            and not topology["remote_shards"] and not topology["shard_transfers"]
            and topology["peer_id"] == cluster["peer_id"], "Qdrant shard placement or status differs")


def qdrant_inventory(client):
    version = client.json("/")["version"]
    require(version == "1.20.0", "Unexpected Qdrant server version")
    cluster = client.json("/cluster")
    require(client.json("/collections")["collections"] == [{"name": QDRANT_COLLECTION}],
            "Unexpected Qdrant collection inventory")
    aliases = client.json("/aliases")["aliases"]
    require(all(alias["collection_name"] == QDRANT_COLLECTION for alias in aliases), "Unexpected alias target")
    path = collection_path()
    detail = client.json(path)
    topology = client.json(path + "/cluster")
    count = client.json(path + "/points/count", "POST", {"exact": True})["count"]
    require(0 <= count <= 10_000, "Qdrant capture inventory exceeds reviewed fingerprint bound")
    validate_qdrant_topology(cluster, detail, topology, count)
    points, seen_offsets = [], set()
    query = {"limit": 256, "with_payload": True, "with_vector": True}
    while True:
        page = client.json(path + "/points/scroll", "POST", query)
        points.extend(page["points"])
        offset = page["next_page_offset"]
        if offset is None:
            break
        require(offset not in seen_offsets and len(points) <= count, "Qdrant scroll pagination differs from exact count")
        seen_offsets.add(offset)
        query["offset"] = offset
    require(len(points) == count and len({point["id"] for point in points}) == count,
            "Qdrant scroll inventory differs from exact count")
    return {
        "version": version, "peer_id": cluster["peer_id"], "peers": cluster["peers"],
        "collection": QDRANT_COLLECTION, "aliases": sorted(aliases, key=lambda item: item["alias_name"]),
        "config": detail["config"], "payload_schema": detail["payload_schema"],
        "local_shards": topology["local_shards"], "points": count,
        "point_digest": canonical_hash(sorted(points, key=lambda point: str(point["id"]))),
    }


def extract_nats_cli(archive, directory):
    machine = platform.machine()
    expected = NATS_ARCHIVES.get(machine)
    require(platform.system() == "Darwin" and expected is not None, "No reviewed NATS CLI archive for this host")
    go_arch = "amd64" if machine == "x86_64" else machine
    name = f"nats-{NATS_CLI_VERSION}-darwin-{go_arch}"
    require(archive.name == name + ".zip" and file_hash(archive) == expected, "NATS CLI archive name or SHA-256 differs")
    with zipfile.ZipFile(archive) as source:
        binary = source.read(name + "/nats")
    path = directory / "nats"
    path.write_bytes(binary)
    path.chmod(0o700)
    return path, {"version": NATS_CLI_VERSION, "archive_sha256": expected,
                  "source": f"https://github.com/nats-io/natscli/releases/download/v{NATS_CLI_VERSION}/{name}.zip"}


def snapshot_nats(cluster, binary, target, initial):
    env = {key: value for key, value in os.environ.items() if not key.startswith("NATS_")}
    with port_forward(cluster, "omniscience-nats-0", 4222) as endpoint:
        subprocess.run(
            [str(binary), "--no-context", "--server", f"nats://{endpoint}", "--timeout", "2m",
             "account", "backup", "--check", "--consumers", "--force", "--critical-warnings", str(target)],
            env=env, capture_output=True, check=True, timeout=300,
        )
    require({path.name for path in target.iterdir()} == NATS_STREAMS.keys(), "NATS backup stream directories differ")
    for name in NATS_STREAMS:
        stream = target / name
        require({path.name for path in stream.iterdir()} == {"backup.json", "stream.tar.s2"}
                and (stream / "stream.tar.s2").stat().st_size > 0, "NATS snapshot archive missing")
        meta = json.loads((stream / "backup.json").read_bytes())
        expected = initial["streams"][name]
        require(meta["config"]["name"] == name and all(
            meta["state"].get(key, 0) == expected["state"].get(key, 0)
            for key in ("messages", "bytes", "first_seq", "last_seq", "consumer_count")
        ), "NATS backup manifest stream or snapshot state differs")


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def receipt_candidate(directory, data):
    with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as file:
        path = Path(file.name)
        try:
            json.dump(data, file)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    return path


def persist_receipt(directory, data):
    target = directory / "receipt.json"
    previous = None
    candidate = receipt_candidate(directory, data)
    try:
        if data["status"] == "complete":
            old = json.loads(target.read_bytes())
            require(old["status"] == "incomplete", "A complete receipt requires an incomplete attempt")
            previous = receipt_candidate(directory, old)
        candidate.replace(target)
        try:
            sync_directory(directory)
        except OSError:
            if previous is not None:
                previous.replace(target)
                try:
                    sync_directory(directory)
                except OSError:
                    pass
            raise
    finally:
        candidate.unlink(missing_ok=True)
        if previous is not None:
            previous.unlink(missing_ok=True)


def snapshot_qdrant(client, target, receipt):
    path = collection_path() + "/snapshots"
    created = client.json(path + "?wait=true", "POST")
    name = created["name"]
    checksum = created.get("checksum")
    size = created["size"]
    require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+\.snapshot", name)), "Unexpected Qdrant snapshot filename")
    require(type(size) is int and size > 0, "Qdrant did not provide a valid snapshot size")
    valid_checksum = isinstance(checksum, str) and bool(re.fullmatch(r"[a-f0-9]{64}", checksum))
    receipt["qdrant_snapshot"] = {"source_snapshot": name, "sha256": checksum if valid_checksum else None, "bytes": size}
    persist_receipt(target.parent, {**receipt, "status": "incomplete"})
    require(valid_checksum, "Qdrant did not provide a valid SHA-256 snapshot checksum")
    with client.request(path + "/" + urllib.parse.quote(name, safe="")) as response, target.open("xb") as file:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            file.write(chunk)
        file.flush()
        os.fsync(file.fileno())
    require(target.stat().st_size == size and file_hash(target) == checksum,
            "Qdrant snapshot byte length or checksum differs")


def complete_receipt(directory, receipt, initial, final):
    require(initial == final, "Source identities or logical fingerprints changed during capture")
    files = {}
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), "Unexpected symlink in snapshot capture")
        if path.is_dir():
            require(path.stat().st_mode & 0o777 == 0o700, "Snapshot directory is not private")
        elif path != directory / "receipt.json":
            require(path.is_file() and path.stat().st_mode & 0o777 == 0o600, "Snapshot file is not private")
            files[str(path.relative_to(directory))] = {"bytes": path.stat().st_size, "sha256": file_hash(path)}
    expected = {"qdrant.snapshot"}
    expected.update(f"nats/{stream}/{name}" for stream in NATS_STREAMS for name in ("backup.json", "stream.tar.s2"))
    require(files.keys() == expected and all(item["bytes"] > 0 for item in files.values()),
            "Snapshot set is incomplete")
    for name in files:
        with (directory / name).open("rb") as artifact:
            os.fsync(artifact.fileno())
    for path in sorted((path for path in directory.rglob("*") if path.is_dir()),
                       key=lambda path: len(path.parts), reverse=True):
        sync_directory(path)
    sync_directory(directory)
    persist_receipt(directory, {
        **receipt, "status": "complete", "completed_at": timestamp(),
        "source_inventory": initial, "files": files,
    })


def inventory(cluster, capture=False):
    source = source_identity(cluster, capture)
    with qdrant_client(cluster) as client:
        qdrant = qdrant_inventory(client)
    return {"source": source, "nats": nats_inventory(cluster, capture), "qdrant": qdrant}


def capture(cluster, archive):
    SHARED["paused"](cluster, check_source_clients=False)
    initial = inventory(cluster, capture=True)
    previous_umask = os.umask(0o077)
    try:
        BACKUP_ROOT.mkdir(mode=0o700, exist_ok=True)
        require(not BACKUP_ROOT.is_symlink() and BACKUP_ROOT.stat().st_mode & 0o777 == 0o700,
                "Backup root is not private")
        sync_directory(BACKUP_ROOT.parent)
        with tempfile.TemporaryDirectory(prefix="nats-cli-", dir=PRIVATE) as temp:
            binary, cli = extract_nats_cli(archive, Path(temp))
            directory = Path(tempfile.mkdtemp(prefix="capture-", dir=BACKUP_ROOT))
            receipt = {"started_at": timestamp(), "nats_cli": cli}
            sync_directory(BACKUP_ROOT)
            persist_receipt(directory, {**receipt, "status": "incomplete"})
            print(f"Capture directory {directory.relative_to(PRIVATE)}", flush=True)
            SHARED["paused"](cluster, check_source_clients=False)
            require(source_identity(cluster, capture=True) == initial["source"], "Source changed before snapshot")
            require(nats_inventory(cluster, capture=True) == initial["nats"], "NATS state changed before snapshot")
            snapshot_nats(cluster, binary, directory / "nats", initial["nats"])
            with qdrant_client(cluster) as client:
                require(qdrant_inventory(client) == initial["qdrant"], "Qdrant state changed before snapshot")
                snapshot_qdrant(client, directory / "qdrant.snapshot", receipt)
            SHARED["paused"](cluster, check_source_clients=False)
            final = inventory(cluster, capture=True)
            require(source_identity(cluster, capture=True) == initial["source"], "Source changed after snapshot")
            SHARED["paused"](cluster, check_source_clients=False)
            complete_receipt(directory, receipt, initial, final)
    finally:
        os.umask(previous_umask)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("inventory")
    snapshot = actions.add_parser("capture")
    snapshot.add_argument("--nats-archive", type=Path, required=True)
    snapshot.add_argument("--writers-paused", action="store_true", required=True)
    args = parser.parse_args()
    try:
        cluster = Cluster()
        if args.action == "capture":
            capture(cluster, args.nats_archive)
        else:
            result = inventory(cluster)
            print(f"NATS streams: {len(result['nats']['streams'])}; Qdrant points: {result['qdrant']['points']}")
    except RuntimeError as error:
        parser.exit(1, f"{args.action} failed: {error}\n")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile):
        parser.exit(1, f"{args.action} failed. Inspect status without printing credentials or snapshot data.\n")
    print(f"{args.action} passed")


if __name__ == "__main__":
    main()
