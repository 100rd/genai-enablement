#!/usr/bin/env python3
"""Execute the journaled secondary-store handoff in explicitly selected phases."""

import argparse
import copy
import json
import secrets
import subprocess
import time
from pathlib import Path

import capture
import nats_stage
import qdrant_stage
import secondary_cutover

SHARED = capture.SHARED
require = capture.require
API = "omniscience-api"
ROOT = capture.BACKUP_ROOT.parent / "secondary-handoff"
RECORD = "receipt.json"
HELM_MARKER_LABEL = "secondary-handoff-id"
NATS = nats_stage.SOURCE
QDRANT = qdrant_stage.SOURCE
QDRANT_REPLACEMENT_PEER = 3792830686241729
QDRANT_REPLACEMENT_URI = "http://omniscience-qdrant-0.omniscience-qdrant-headless:6335/"
CANCELLABLE = {"pause-intent", "quiesced", "stage-stop-intent", "stages-stopped", "cancel-intent", "cancelled"}
PHASES = {"prepared", *CANCELLABLE, "source-stop-intent", "sources-stopped",
          "install-intent", "installed", "live-verified", "resume-intent", "resumed"}


def save(state):
    nats_stage.sync_json(ROOT, RECORD, state)


def load():
    path = ROOT / RECORD
    nats_stage.private(path, 0o600)
    state = SHARED["read_private_json"](path)
    require(state.get("schema") == 2 and {"protected", "originals", "old_claims", "source_observed_at", "admission"} <= state.keys(),
            "Secondary handoff receipt uses an older schema; archive only a confirmed prepared receipt and reprepare")
    require(state["phase"] in PHASES and state["backup_sha256"] == nats_stage.RECEIPT_SHA,
            "Secondary handoff receipt differs")
    return state


def api_identity(cluster, expected=None):
    api = cluster.get("deployment", API)
    meta = api["metadata"]
    spec = api["spec"]
    digest = capture.canonical_hash({key: value for key, value in spec.items() if key != "replicas"})
    require(not meta.get("deletionTimestamp") and
            (expected is None or (meta["uid"], digest) == (expected["uid"], expected["spec_sha256"])),
            "Omniscience API Deployment identity or specification changed")
    return {"uid": meta["uid"], "resource_version": meta["resourceVersion"], "replicas": spec["replicas"],
            "spec_sha256": digest}


def patch_api(cluster, identity, desired):
    require({identity["replicas"], desired} == {0, 1}, "Unexpected API replica transition")
    patch = [
        {"op": "test", "path": "/metadata/uid", "value": identity["uid"]},
        {"op": "test", "path": "/metadata/resourceVersion", "value": identity["resource_version"]},
        {"op": "test", "path": "/spec/replicas", "value": identity["replicas"]},
        {"op": "replace", "path": "/spec/replicas", "value": desired},
    ]
    cluster.kubectl("patch", "deployment", API, "--type=json", "-p", json.dumps(patch))


def source_identity(cluster, backup):
    nats, _ = nats_stage.source_pin(cluster, backup, incident=True)
    qdrant_stage.source_guard(cluster, backup, incident=True)
    pod = cluster.get("pod", f"{QDRANT}-0")
    require(pod["metadata"]["uid"] == qdrant_stage.REPLACEMENT_POD_UID
            and pod["spec"]["nodeName"] == qdrant_stage.REPLACEMENT_NODE
            and all(item["ready"] for item in pod["status"]["containerStatuses"]),
            "Qdrant incident source runtime changed")
    return {NATS: nats, QDRANT: {
        "pod_uid": pod["metadata"]["uid"],
        "node": pod["spec"]["nodeName"],
        "containers": {item["name"]: item["containerID"] for item in pod["status"]["containerStatuses"]},
    }}


def protected_stores(cluster):
    result = {}
    for name, claim_name in (
        ("omniscience-postgres", "omniscience-postgres-data-retained"),
        ("omniscience-neo4j", "omniscience-neo4j-data-retained"),
    ):
        sts = cluster.get("statefulset", name)
        pod = cluster.get("pod", f"{name}-0")
        claim = cluster.get("pvc", claim_name)
        require(claim["status"]["phase"] == "Bound"
                and [volume["persistentVolumeClaim"]["claimName"] for volume in pod["spec"]["volumes"]
                     if "persistentVolumeClaim" in volume] == [claim_name], "Protected store claim changed")
        result[name] = {
            "sts": sts["metadata"]["uid"], "pod": pod["metadata"]["uid"],
            "containers": {item["name"]: item["containerID"] for item in pod["status"]["containerStatuses"]},
            "claim": claim["metadata"]["uid"], "pv": claim["spec"]["volumeName"],
        }
    return result


def stage_records(attempt):
    nats = SHARED["read_private_json"](attempt / "restore-verified.json")
    qdrant = SHARED["read_private_json"](qdrant_stage.INCIDENT_STATE_DIR / RECORD)
    return {
        NATS: {"name": attempt.name, "pod": attempt.name, "uid": nats["ready"]["uids"]["pod"],
               "volume": nats["ready"]["volume"], "proof": nats},
        QDRANT: {"name": qdrant["stage"], "pod": qdrant["stage"] + "-restart",
                 "uid": qdrant["resources"]["restart"]["uid"], "volume": qdrant["volume"], "proof": qdrant},
    }


def expected_admitted_statefulset(original, proposed, claim):
    spec = copy.deepcopy(original)
    templates = spec.pop("volumeClaimTemplates")
    require(len(templates) == 1, "Original StatefulSet admission baseline claim differs")
    volume = templates[0]["metadata"]["name"]
    pod = spec["template"]["spec"]
    desired = proposed["template"]["spec"]
    pod["volumes"].append({"name": volume, "persistentVolumeClaim": {"claimName": claim}})
    pod["nodeSelector"] = desired["nodeSelector"]
    for field in ("containers", "initContainers"):
        images = {item["name"]: item["image"] for item in desired.get(field, [])}
        require({item["name"] for item in pod.get(field, [])} == images.keys(),
                "Original StatefulSet container admission baseline differs")
        for item in pod.get(field, []):
            item["image"] = images[item["name"]]
    return spec


def verify_create_admission(cluster, proposed, claims):
    proof = {}
    token = secrets.token_hex(8)
    for name, claim in claims.items():
        manifest = copy.deepcopy(proposed[("StatefulSet", name)])
        metadata = manifest["metadata"]
        validation_name = f"handoff-validation-{token}-{name.removeprefix('omniscience-')}"
        metadata["name"] = validation_name
        original = cluster.get("statefulset", name)
        require(original["metadata"]["uid"] == capture.SOURCES[name]["sts_uid"],
                "Original StatefulSet changed before admission")
        expected = expected_admitted_statefulset(original["spec"], manifest["spec"], claim)
        observed = json.loads(cluster.kubectl("create", "--dry-run=server", "-f", "-", "-o", "json",
                                              input=json.dumps(manifest)))
        actual_metadata = observed["metadata"]
        require(observed["kind"] == "StatefulSet" and actual_metadata["name"] == validation_name
                and actual_metadata["namespace"] == capture.NAMESPACE
                and actual_metadata.get("labels", {}) == metadata.get("labels", {})
                and actual_metadata.get("annotations", {}) == metadata.get("annotations", {})
                and observed["spec"] == expected, "Renamed StatefulSet CREATE admission changed the reviewed layout")
        proof[name] = capture.canonical_hash(observed["spec"])
    return {"scope": "renamed-statefulset-create-server-dry-run", "production_name_admitted": False,
            "spec_sha256": proof}


def qualified_render(cluster, nats, qdrant):
    proofs = []
    claims = {NATS: nats, QDRANT: qdrant}

    def qualify(proposed):
        proofs.append(verify_create_admission(cluster, proposed, claims))

    with secondary_cutover.render_session(cluster, nats, qdrant, admission_check=qualify) as (plan, _, _):
        return plan, proofs[0]


def prepare(cluster, attempt):
    attempt = nats_stage.prepare_attempt(attempt, incident=True)
    if (ROOT / RECORD).exists():
        existing = load()
        require(existing["phase"] == "prepared" and existing["nats_attempt"] == attempt.name,
                "A different or advanced secondary handoff receipt already exists")
        return
    backup = nats_stage.verified_capture()
    api = api_identity(cluster)
    require(api["replicas"] == 1, "Prepare requires the original API at one replica")
    source = source_identity(cluster, backup)
    observed = source_inventory(cluster, backup, paused=False)
    protected = protected_stores(cluster)
    originals = {name: source_sts(cluster, name) for name in (NATS, QDRANT)}
    claims = old_claims(cluster)
    require(all(item["replicas"] == 1 for item in originals.values()), "Original StatefulSet replica count changed")
    with secondary_cutover.accepted_claims(cluster, attempt) as (nats, qdrant):
        plan, admission = qualified_render(cluster, nats, qdrant)
        stages = stage_records(attempt)
    require(persistent_inventory(source_inventory(cluster, backup, paused=False)) == persistent_inventory(observed)
            and source_identity(cluster, backup) == source and api_identity(cluster, api)["replicas"] == 1
            and protected_stores(cluster) == protected and old_claims(cluster) == claims
            and all(source_sts(cluster, name, original)["replicas"] == 1
                    for name, original in originals.items()),
            "API or incident source changed during preparation")
    require(plan["claims"] == {name: stage["name"] for name, stage in stages.items()},
            "Rendered and accepted claim names differ")
    save({
        "schema": 2, "phase": "prepared", "backup_sha256": nats_stage.RECEIPT_SHA,
        "created_at": capture.timestamp(), "api": api, "source": source, "source_inventory": observed, "source_observed_at": capture.timestamp(),
        "nats_attempt": attempt.name, "stages": stages, "plan": plan, "protected": protected,
        "originals": originals, "old_claims": claims, "admission": admission,
    })


def wait_for(condition, timeout, failure):
    deadline = time.monotonic() + timeout
    while not condition():
        remaining = deadline - time.monotonic()
        require(remaining > 0, failure)
        time.sleep(min(2, remaining))


def wait_api_drain(cluster, api):
    def drained():
        require(api_identity(cluster, api)["replicas"] == 0, "Omniscience API was resumed during drain")
        deployment = cluster.get("deployment", API)
        selector = deployment["spec"]["selector"]["matchLabels"]
        require(deployment["metadata"]["uid"] == api["uid"] and selector
                and not deployment["spec"]["selector"].get("matchExpressions"), "Omniscience API selector changed")
        return not any(
            all(pod["metadata"].get("labels", {}).get(key) == value for key, value in selector.items())
            for pod in nats_stage.objects(cluster, "pods")
        )

    wait_for(drained, 180, "Omniscience API Pods did not drain")
    SHARED["paused"](cluster, check_source_clients=False)
    wait_for(lambda: capture.nats_monitor(cluster, "varz")["connections"] == 0, 90,
             "NATS client connections did not drain")


def verify_empty_qdrant(observed, expected):
    fields = ("version", "collection", "aliases", "config")
    empty_indexes = {key: {**schema, "points": 0} for key, schema in expected["payload_schema"].items()}
    require(all(observed[key] == expected[key] for key in fields) and observed["aliases"] == []
            and observed["payload_schema"] == empty_indexes
            and observed["points"] == 0 and observed["point_digest"] == capture.canonical_hash([])
            and observed["local_shards"] == [{"shard_id": 0, "state": "Active", "points_count": 0}]
            and observed["peer_id"] == QDRANT_REPLACEMENT_PEER
            and observed["peers"] == {str(QDRANT_REPLACEMENT_PEER): {"uri": QDRANT_REPLACEMENT_URI}},
            "Qdrant incident source is not the reviewed empty collection")


def persistent_nats(inventory, *, paused=False):
    normalized = copy.deepcopy(inventory)
    for stream in normalized["streams"].values():
        for consumer in stream["consumers"].values():
            waiting = consumer["num_waiting"]
            require(type(waiting) is int and waiting >= 0 and (not paused or waiting == 0),
                    "Unexpected NATS pull waiters in the source inventory")
            consumer["num_waiting"] = 0
    return normalized


def persistent_inventory(inventory, *, paused=False):
    return {**inventory, "nats": persistent_nats(inventory["nats"], paused=paused)}


def source_inventory(cluster, backup, *, paused):
    nats = capture.nats_inventory(cluster, capture=paused)
    nats_stage.restore_evidence(persistent_nats(nats, paused=paused), backup["source_inventory"]["nats"])
    with capture.qdrant_client(cluster) as client:
        qdrant = capture.qdrant_inventory(client)
    verify_empty_qdrant(qdrant, backup["source_inventory"]["qdrant"])
    return {"nats": nats, "qdrant": qdrant}


def quiesced_source(cluster, state, backup):
    require(api_identity(cluster, state["api"])["replicas"] == 0
            and source_identity(cluster, backup) == state["source"], "Quiesced source identity changed")
    SHARED["paused"](cluster, check_source_clients=False)
    observed = source_inventory(cluster, backup, paused=True)
    require(persistent_inventory(observed, paused=True) == persistent_inventory(state["source_inventory"]),
            "Replacement store inventory changed after preparation")
    require(source_identity(cluster, backup) == state["source"], "Incident source changed during quiescence check")
    SHARED["paused"](cluster, check_source_clients=False)
    require(api_identity(cluster, state["api"])["replicas"] == 0
            and capture.nats_monitor(cluster, "varz")["connections"] == 0, "An API replica or NATS client returned")
    return observed


def pause_api(cluster, state, backup):
    require(state["phase"] in {"prepared", "pause-intent", "quiesced"}, "Handoff cannot pause in this phase")
    require(source_identity(cluster, backup) == state["source"], "Incident source changed before API pause")
    api = api_identity(cluster, state["api"])
    if state["phase"] == "quiesced":
        require(quiesced_source(cluster, state, backup) == state["quiesced"], "Quiesced source state changed")
        return
    require(api["replicas"] == 1 or state["phase"] == "pause-intent" and api["replicas"] == 0,
            "Unexpected Omniscience API replica count before pause")
    if api["replicas"] == 1:
        verify_stage_writers(cluster, state["stages"], allow_absent=False)
        require(persistent_inventory(source_inventory(cluster, backup, paused=False))
                == persistent_inventory(state["source_inventory"])
                and source_identity(cluster, backup) == state["source"],
                "Replacement store inventory or identity changed before API pause")
        state.update(phase="pause-intent", pause_api=api)
        save(state)
        patch_api(cluster, api, 0)
    wait_api_drain(cluster, state["api"])
    inventory = quiesced_source(cluster, state, backup)
    state.update(phase="quiesced", quiesced=inventory)
    save(state)


def claim_identity(cluster, name, stage):
    volume = stage["volume"]
    if name == NATS:
        return nats_stage.volume_identity(cluster, stage["name"], volume["pvc_uid"])
    return qdrant_stage.volume_identity(cluster, cluster.get("pvc", stage["name"]))


def verify_stage_writers(cluster, stages, allow_absent):
    for name, stage in stages.items():
        require(claim_identity(cluster, name, stage) == stage["volume"], "Retained stage EBS identity changed")
        consumers = nats_stage.claim_consumers(cluster, stage["name"])
        if cluster.absent("pod", stage["pod"]):
            require(allow_absent and not consumers, "Staged writer disappeared or another Pod uses its claim")
            continue
        pod = cluster.get("pod", stage["pod"])
        require(pod["metadata"]["uid"] == stage["uid"] and consumers == [stage["uid"]],
                "Staged writer UID or sole claim ownership changed")


def detached(cluster, stage):
    volume = stage["volume"]
    pv = volume.get("pv") or volume["pv_name"]
    attachments = nats_stage.objects(cluster, "volumeattachments")
    if any(item["spec"]["source"].get("persistentVolumeName") == pv for item in attachments):
        return False
    ebs = json.loads(cluster.helper["aws"]([
        "ec2", "describe-volumes", "--region", "eu-central-1", "--volume-ids", volume["volume_handle"],
        "--output", "json",
    ], env=cluster.env))["Volumes"]
    require(len(ebs) == 1 and ebs[0]["VolumeId"] == volume["volume_handle"], "Retained EBS volume disappeared")
    return ebs[0]["State"] == "available" and ebs[0]["Attachments"] == []


def stop_stage_writers(cluster, state, backup):
    require(state["phase"] in {"quiesced", "stage-stop-intent", "stages-stopped"}, "API is not quiesced")
    require(quiesced_source(cluster, state, backup) == state["quiesced"], "Quiesced source state changed")
    stages = state["stages"]
    attempt = nats_stage.prepare_attempt(nats_stage.ATTEMPTS / state["nats_attempt"], incident=True)
    with nats_stage.lock_attempt(attempt), qdrant_stage.journal(
        qdrant_stage.INCIDENT_STATE_DIR, create=False, incident=True,
    ) as record:
        require(stage_records(attempt) == stages, "Accepted stage receipts changed")
        if state["phase"] == "quiesced":
            nats = secondary_cutover.verified_nats_claim(cluster, attempt, backup)
            qdrant = secondary_cutover.verified_qdrant_claim(cluster, record, backup)
            require(nats == (stages[NATS]["name"], stages[NATS]["volume"])
                    and qdrant == (stages[QDRANT]["name"], stages[QDRANT]["volume"]),
                    "Accepted stage EBS identity changed")
            verify_stage_writers(cluster, stages, allow_absent=False)
            state["phase"] = "stage-stop-intent"
            save(state)
        verify_stage_writers(cluster, stages, allow_absent=True)
        for stage in stages.values():
            if not cluster.absent("pod", stage["pod"]):
                require(state["phase"] == "stage-stop-intent", "A stopped staged writer returned")
                pod = cluster.get("pod", stage["pod"])
                require(pod["metadata"]["uid"] == stage["uid"], "Refusing to delete a replacement staged Pod")
                if not pod["metadata"].get("deletionTimestamp"):
                    SHARED["delete_owned"](cluster, f"/api/v1/namespaces/{capture.NAMESPACE}/pods/{stage['pod']}",
                                           stage["uid"])
            wait_for(lambda: cluster.absent("pod", stage["pod"]), 180, "Staged writer did not terminate")
            require(not nats_stage.claim_consumers(cluster, stage["name"]), "A Pod still uses the staged claim")
            wait_for(lambda: detached(cluster, stage), 300, "Staged EBS volume did not detach")
        verify_stage_writers(cluster, stages, allow_absent=True)
        require(quiesced_source(cluster, state, backup) == state["quiesced"], "Quiesced source changed during shutdown")
        state["phase"] = "stages-stopped"
        save(state)


def cancel(cluster, state, backup):
    """Resume the original API while both source StatefulSets still pass their original pins."""
    require(state["phase"] in CANCELLABLE, "Cancellation is unavailable after source shutdown begins")
    require(source_identity(cluster, backup) == state["source"], "Original source cannot be verified for cancellation")
    api = api_identity(cluster, state["api"])
    if state["phase"] == "cancelled":
        require(api["replicas"] == 1, "Cancelled handoff API replica count changed")
        return
    require(api["replicas"] in (0, 1)
            and (api["replicas"] == 0 or state["phase"] in {"pause-intent", "cancel-intent"}),
            "Original API replica count differs from its cancellation state")
    state.update(phase="cancel-intent", cancel_api=api)
    save(state)
    if api["replicas"] == 0:
        patch_api(cluster, api, 1)
    cluster.kubectl("rollout", "status", f"deployment/{API}", "--timeout=180s")
    require(api_identity(cluster, state["api"])["replicas"] == 1
            and source_identity(cluster, backup) == state["source"], "Original API or source differs after resume")
    state["phase"] = "cancelled"
    save(state)


def old_claims(cluster):
    claims = {}
    for name in (NATS, QDRANT):
        expected = capture.SOURCES[name]
        claim = cluster.get("pvc", expected["pvc"])
        pv = cluster.get("pv", expected["pv"])
        spec = pv["spec"]
        ref = spec["claimRef"]
        require(claim["metadata"]["uid"] == expected["pvc_uid"] and not claim["metadata"].get("ownerReferences")
                and not claim["metadata"].get("deletionTimestamp") and claim["status"]["phase"] == "Bound"
                and claim["spec"]["volumeName"] == expected["pv"] and pv["metadata"]["uid"] == expected["pv_uid"]
                and (ref["namespace"], ref["name"], ref["uid"]) == (capture.NAMESPACE, expected["pvc"], expected["pvc_uid"])
                and spec["persistentVolumeReclaimPolicy"] == "Retain"
                and spec["hostPath"] == {"path": expected["path"], "type": "DirectoryOrCreate"},
                "Original hostPath claim or retention differs")
        claims[name] = {"pvc": expected["pvc_uid"], "pv": expected["pv_uid"]}
    return claims


def source_sts(cluster, name, pinned=None, *, allow_terminating=False):
    sts = cluster.get("statefulset", name)
    meta, spec = sts["metadata"], sts["spec"]
    retention = {"whenDeleted": "Retain", "whenScaled": "Retain", **(spec.get("persistentVolumeClaimRetentionPolicy") or {})}
    selector = spec["selector"]
    digest = capture.canonical_hash({key: value for key, value in spec.items() if key != "replicas"})
    require(meta["uid"] == capture.SOURCES[name]["sts_uid"] and (allow_terminating or not meta.get("deletionTimestamp"))
            and retention == {"whenDeleted": "Retain", "whenScaled": "Retain"}
            and selector["matchLabels"] and not selector.get("matchExpressions"),
            "Original StatefulSet UID, selector or PVC retention differs")
    identity = {"uid": meta["uid"], "resource_version": meta["resourceVersion"], "replicas": spec["replicas"],
                "spec_sha256": digest, "selector": selector["matchLabels"], "terminating": bool(meta.get("deletionTimestamp"))}
    if pinned is not None:
        require(all(identity[key] == pinned[key] for key in ("uid", "spec_sha256", "selector")),
                "Original StatefulSet specification changed")
    return identity


def source_pods(cluster, name, pinned):
    return [pod for pod in nats_stage.objects(cluster, "pods")
            if pod["metadata"]["name"] == f"{name}-0"
            or any(ref["uid"] == pinned["uid"] for ref in pod["metadata"].get("ownerReferences", []))
            or all(pod["metadata"].get("labels", {}).get(key) == value for key, value in pinned["selector"].items())]


def scale_source_zero(cluster, name, identity):
    patch = [
        {"op": "test", "path": "/metadata/uid", "value": identity["uid"]},
        {"op": "test", "path": "/metadata/resourceVersion", "value": identity["resource_version"]},
        {"op": "test", "path": "/spec/replicas", "value": 1},
        {"op": "replace", "path": "/spec/replicas", "value": 0},
    ]
    cluster.kubectl("patch", "statefulset", name, "--type=json", "-p", json.dumps(patch))


def delete_source(cluster, name, identity):
    options = {"apiVersion": "v1", "kind": "DeleteOptions", "propagationPolicy": "Orphan",
               "preconditions": {"uid": identity["uid"], "resourceVersion": identity["resource_version"]}}
    cluster.kubectl("delete", "--raw", f"/apis/apps/v1/namespaces/{capture.NAMESPACE}/statefulsets/{name}",
                    "-f", "-", input=json.dumps(options))


def verify_retained_detached(cluster, state):
    verify_stage_writers(cluster, state["stages"], allow_absent=True)
    require(all(cluster.absent("pod", stage["pod"]) and detached(cluster, stage)
                for stage in state["stages"].values()), "A retained stage claim is still in use or attached")


def verify_remaining_source(cluster, state, backup, name):
    if name == NATS:
        identity, _ = nats_stage.source_pin(cluster, backup, incident=True)
        require(identity == state["source"][name]
                and capture.nats_inventory(cluster, capture=True) == state["quiesced"]["nats"],
                "Quiesced NATS source changed before shutdown")
    else:
        qdrant_stage.source_guard(cluster, backup, incident=True)
        pod = cluster.get("pod", f"{QDRANT}-0")
        require({item["name"]: item["containerID"] for item in pod["status"]["containerStatuses"]}
                == state["source"][name]["containers"], "Quiesced Qdrant source restarted")
        with capture.qdrant_client(cluster) as client:
            require(capture.qdrant_inventory(client) == state["quiesced"]["qdrant"],
                    "Quiesced Qdrant source changed before shutdown")
        qdrant_stage.source_guard(cluster, backup, incident=True)


def require_api_paused(cluster, state):
    require(api_identity(cluster, state["api"])["replicas"] == 0, "Omniscience API is no longer paused")
    SHARED["paused"](cluster, check_source_clients=False)
    require(protected_stores(cluster) == state["protected"], "Protected PostgreSQL or Neo4j identity changed")


def stop_sources(cluster, state, backup):
    require(state["phase"] in {"stages-stopped", "source-stop-intent", "sources-stopped"},
            "Source shutdown requires detached stage writers")
    require_api_paused(cluster, state)
    verify_retained_detached(cluster, state)
    claims = old_claims(cluster)
    if state["phase"] == "stages-stopped":
        require(quiesced_source(cluster, state, backup) == state["quiesced"], "Quiesced source changed")
        originals = {name: source_sts(cluster, name, pinned) for name, pinned in state["originals"].items()}
        require(all(item["replicas"] == 1 for item in originals.values()), "Original StatefulSet replica count changed")
        plan, admission = qualified_render(cluster, state["stages"][NATS]["name"], state["stages"][QDRANT]["name"])
        require(plan == state["plan"] and admission == state["admission"]
                and quiesced_source(cluster, state, backup) == state["quiesced"],
                "Prepared Helm render or source differs immediately before shutdown")
        require(claims == state["old_claims"], "Original claims changed before shutdown")
        state.update(phase="source-stop-intent", source_steps={})
        save(state)
    require(claims == state["old_claims"], "Original claims changed during source shutdown")
    for name, pinned in state["originals"].items():
        require_api_paused(cluster, state)
        steps = state["source_steps"].setdefault(name, {})
        if not cluster.absent("statefulset", name):
            require(state["phase"] == "source-stop-intent", "A removed original StatefulSet returned")
            current = source_sts(cluster, name, pinned, allow_terminating="delete" in steps)
            if current["replicas"] == 1:
                require("delete" not in steps, "An original StatefulSet was resumed during deletion")
                verify_remaining_source(cluster, state, backup, name)
                require_api_paused(cluster, state)
                steps["scale"] = current
                save(state)
                scale_source_zero(cluster, name, current)
            else:
                require(current["replicas"] == 0 and "scale" in steps,
                        "Unjournaled original StatefulSet replica change")
            wait_for(lambda: not source_pods(cluster, name, pinned), 180, "Original StatefulSet Pods did not stop")
            require_api_paused(cluster, state)
            if not cluster.absent("statefulset", name):
                current = source_sts(cluster, name, pinned, allow_terminating="delete" in steps)
                require(current["replicas"] == 0 and old_claims(cluster) == claims, "Source retention or scale changed")
                if not current["terminating"]:
                    steps["delete"] = current
                    save(state)
                    delete_source(cluster, name, current)
            else:
                require(steps.get("delete", {}).get("uid") == pinned["uid"],
                        "Original StatefulSet disappeared before its delete intent")
        else:
            require(steps.get("delete", {}).get("uid") == pinned["uid"], "Original StatefulSet disappeared before its delete intent")
        wait_for(lambda: cluster.absent("statefulset", name), 180, "Original StatefulSet did not terminate")
        require(not source_pods(cluster, name, pinned), "A Pod still matches the original StatefulSet selector")
    require(old_claims(cluster) == claims, "Original claims changed during source shutdown")
    state["phase"] = "sources-stopped"
    save(state)


def next_release_present(cluster, revision):
    return not cluster.absent("secret", f"sh.helm.release.v1.omniscience.v{revision}")


def installed_release(cluster, revision, intent):
    name = f"sh.helm.release.v1.omniscience.v{revision}"
    secret = cluster.get("secret", name)
    release = SHARED["decode_release"](secret["data"]["release"])
    resources = secondary_cutover.parse_manifest(release["manifest"])
    secondary_cutover.normalize_postgres_annotations(resources)
    require(release["name"] == "omniscience" and release["namespace"] == capture.NAMESPACE
            and release["version"] == revision
            and secret["metadata"]["labels"].get(HELM_MARKER_LABEL) == intent["marker"]
            and secondary_cutover.manifest_digest(resources) == intent["plan"]["manifest_sha256"]
            and release["config"]["replicaCount"] == intent["plan"]["api_replicas"]
            and secondary_cutover.manifest_digest(secondary_cutover.hook_resources(release)) == intent["hooks_sha256"],
            "Next Helm release is foreign or differs from the journaled proposal")
    status = release["info"]["status"]
    require(status == secret["metadata"]["labels"]["status"], "Owned Helm release status is inconsistent")
    require(status == "deployed", "Owned Helm release is pending or failed; keep API paused and review forward repair")
    require(release["info"]["description"] == intent["marker"], "Deployed Helm release description differs")
    pin, payload = SHARED["release_pin"](cluster, revision)
    require(payload == secret["data"]["release"] and pin["helm_secret_uid"] == secret["metadata"]["uid"]
            and pin["helm_secret_resource_version"] == secret["metadata"]["resourceVersion"],
            "Helm release changed during journal reconciliation")
    return pin, resources


def no_source_statefulsets(cluster, state):
    require_api_paused(cluster, state)
    require(old_claims(cluster) == state["old_claims"], "Original claims changed after source shutdown")
    require(all(cluster.absent("statefulset", name) and not source_pods(cluster, name, original)
                for name, original in state["originals"].items()), "Original StatefulSet or matching Pod returned")
    verify_retained_detached(cluster, state)


def apply_upgrade(cluster, state, base_revision, intent_key, expected_plan, guard):
    revision = base_revision + 1
    if next_release_present(cluster, revision):
        require(intent_key in state, "Unexpected next Helm revision without a local intent")
        return installed_release(cluster, revision, state[intent_key])
    nats = state["stages"][NATS]["name"]
    qdrant = state["stages"][QDRANT]["name"]
    with secondary_cutover.render_session(
        cluster, nats, qdrant, revision=base_revision, previous_plan=state["plan"],
    ) as (plan, command, env):
        if expected_plan is not None:
            require(plan == expected_plan, "Fresh Helm render differs from the journaled proposal")
        pin, payload = SHARED["release_pin"](cluster, base_revision)
        hooks = secondary_cutover.hook_resources(SHARED["decode_release"](payload))
        if intent_key not in state:
            state[intent_key] = {"plan": plan, "marker": "secondary-handoff-" + secrets.token_hex(16),
                                 "base": pin, "hooks_sha256": secondary_cutover.manifest_digest(hooks)}
            state["phase"] = intent_key
            save(state)
        intent = state[intent_key]
        require(plan == intent["plan"] and pin == intent["base"] and not next_release_present(cluster, revision),
                "Helm base or upgrade intent changed")
        guard()
        require(SHARED["release_pin"](cluster, base_revision)[0] == pin, "Helm base changed before upgrade")
        subprocess.run(command + ["--description", intent["marker"], "--labels",
                                  f"{HELM_MARKER_LABEL}={intent['marker']}"], env=env, capture_output=True, text=True,
                       check=True, timeout=600)
    return installed_release(cluster, revision, intent)


def install(cluster, state, _backup):
    require(state["phase"] in {"sources-stopped", "install-intent", "installed"}, "Source shutdown is incomplete")
    pin, _ = apply_upgrade(cluster, state, capture.RELEASE, "install-intent", state["plan"],
                           lambda: no_source_statefulsets(cluster, state))
    require(state.get("helm6", pin) == pin, "Installed Helm revision 6 changed")
    state.update(phase="installed", helm6=pin)
    save(state)


def verify_service_endpoints(cluster, resources, name, pod):
    uid = pod["metadata"]["uid"]
    labels = pod["metadata"]["labels"]
    services = {service: obj for (kind, service), obj in resources.items()
                if kind == "Service" and (service == name or service.startswith(name + "-"))}
    require(name in services and f"{name}-headless" in services, "Expected store Services are missing")
    for service, manifest in services.items():
        expected = manifest["spec"]["selector"]
        require(cluster.get("service", service)["spec"]["selector"] == expected
                and all(labels.get(key) == value for key, value in expected.items()), "Store Service selector changed")
        SHARED["verify_endpoint"](cluster, service, uid)


def normalized_container(container, api_volume=None):
    fields = ("command", "args", "env", "envFrom", "ports", "workingDir", "volumeMounts", "volumeDevices",
              "securityContext", "startupProbe", "readinessProbe", "livenessProbe", "lifecycle")
    result = {key: copy.deepcopy(container[key]) for key in fields if key in container}
    for port in result.get("ports", []):
        port.setdefault("protocol", "TCP")
    for item in result.get("env", []):
        field = item.get("valueFrom", {}).get("fieldRef")
        if field is not None:
            field.setdefault("apiVersion", "v1")
    if api_volume is not None:
        mount = {"name": api_volume, "mountPath": "/var/run/secrets/kubernetes.io/serviceaccount", "readOnly": True}
        if mount in result.get("volumeMounts", []):
            result["volumeMounts"].remove(mount)
    for name in ("startupProbe", "readinessProbe", "livenessProbe"):
        probe = result.get(name)
        if probe is not None:
            for key, value in {"timeoutSeconds": 1, "periodSeconds": 10, "successThreshold": 1,
                               "failureThreshold": 3}.items():
                probe.setdefault(key, value)
            if "httpGet" in probe:
                probe["httpGet"].setdefault("scheme", "HTTP")
    return result


def projected_api_volume(volumes):
    candidates = [item for item in volumes if item["name"].startswith("kube-api-access-")]
    require(len(candidates) <= 1, "Unexpected projected service-account volume count")
    if not candidates:
        return None
    expected = {
        "name": candidates[0]["name"],
        "projected": {"defaultMode": 420, "sources": [
            {"serviceAccountToken": {"expirationSeconds": 3607, "path": "token"}},
            {"configMap": {"items": [{"key": "ca.crt", "path": "ca.crt"}], "name": "kube-root-ca.crt"}},
            {"downwardAPI": {"items": [{"fieldRef": {"apiVersion": "v1", "fieldPath": "metadata.namespace"},
                                       "path": "namespace"}]}},
        ]},
    }
    require(candidates[0] == expected, "Unexpected projected service-account volume contents")
    return expected["name"]


def verify_runtime_layout(pod_spec, expected):
    require(not (pod_spec.get("hostNetwork") or pod_spec.get("hostPID") or pod_spec.get("hostIPC")
                 or pod_spec.get("ephemeralContainers"))
            and pod_spec.get("securityContext", {}) == expected.get("securityContext", {})
            and pod_spec.get("serviceAccountName", "default") == expected.get("serviceAccountName", "default"),
            "Replacement Pod security context differs")
    api_volume = projected_api_volume(pod_spec["volumes"])
    for kind in ("containers", "initContainers"):
        actual = {item["name"]: normalized_container(item, api_volume) for item in pod_spec.get(kind, [])}
        reviewed = {item["name"]: normalized_container(item) for item in expected.get(kind, [])}
        require(actual == reviewed, "Replacement Pod command, environment, security or mount differs")
    volumes = {item["name"]: copy.deepcopy(item) for item in pod_spec["volumes"] if item["name"] != api_volume}
    for item in expected["volumes"]:
        current = volumes.get(item["name"], {})
        for field in ("configMap", "secret", "projected"):
            if current.get(field, {}).get("defaultMode") == 420 and "defaultMode" not in item.get(field, {}):
                del current[field]["defaultMode"]
    require(volumes == {item["name"]: item for item in expected["volumes"]}, "Replacement Pod volumes differ")


def production_runtime(cluster, state, resources):
    require(old_claims(cluster) == state["old_claims"] and protected_stores(cluster) == state["protected"],
            "Original hostPath claims or protected stores changed")
    identities = {}
    for name in (NATS, QDRANT):
        actual = cluster.get("configmap", nats_stage.CONFIG if name == NATS else QDRANT)
        expected_config = resources[("ConfigMap", nats_stage.CONFIG if name == NATS else QDRANT)]
        require(actual["data"] == expected_config["data"], "Live store ConfigMap differs from Helm")
    for name, stage in state["stages"].items():
        sts = cluster.get("statefulset", name)
        expected = resources[("StatefulSet", name)]["spec"]
        meta, spec = sts["metadata"], sts["spec"]
        require(meta["uid"] != state["originals"][name]["uid"] and not meta.get("deletionTimestamp")
                and spec["replicas"] == 1 and not spec.get("volumeClaimTemplates")
                and spec["selector"] == expected["selector"] and spec["serviceName"] == expected["serviceName"],
                "Replacement StatefulSet identity or layout differs")
        pod = cluster.get("pod", f"{name}-0")
        pod_meta, pod_spec, status = pod["metadata"], pod["spec"], pod["status"]
        owners = [item["uid"] for item in pod_meta["ownerReferences"] if item.get("controller")]
        require(owners == [meta["uid"]] and not pod_meta.get("deletionTimestamp"),
                "Replacement Pod owner differs")
        expected_pod = expected["template"]["spec"]
        verify_runtime_layout(pod_spec, expected_pod)
        claims = [item["persistentVolumeClaim"]["claimName"] for item in pod_spec["volumes"]
                  if "persistentVolumeClaim" in item]
        require(claims == [stage["name"]] and nats_stage.claim_consumers(cluster, stage["name"]) == [pod_meta["uid"]]
                and pod_spec["nodeSelector"] == expected_pod["nodeSelector"]
                and claim_identity(cluster, name, stage) == stage["volume"], "Live retained claim ownership differs")
        node = cluster.get("node", pod_spec["nodeName"])
        node_labels = node["metadata"]["labels"]
        require(node_labels.get("topology.kubernetes.io/zone") == stage["volume"]["availability_zone"]
                and all(node_labels.get(key) == value for key, value in secondary_cutover.ON_DEMAND.items()),
                "Replacement Pod is not on a reviewed On-Demand node in its EBS zone")
        runtime = {}
        for field, statuses in (("containers", "containerStatuses"), ("initContainers", "initContainerStatuses")):
            configured = {item["name"]: item["image"] for item in expected_pod.get(field, [])}
            actual = status.get(statuses, [])
            require({item["name"]: item["imageID"] for item in actual} == configured,
                    "Replacement store runtime image differs")
            for item in actual:
                require(item["ready"] if field == "containers" else item["state"]["terminated"]["exitCode"] == 0,
                        "Replacement store container is not ready or init did not finish")
                runtime[item["name"]] = item["containerID"]
        verify_service_endpoints(cluster, resources, name, pod)
        identities[name] = {"sts_uid": meta["uid"], "pod_uid": pod_meta["uid"], "containers": runtime}
    return identities


def live_inventory(cluster, state, backup, resources):
    require_api_paused(cluster, state)
    before = production_runtime(cluster, state, resources)
    nats = capture.nats_inventory(cluster, capture=True)
    nats_evidence = nats_stage.restore_evidence(nats, backup["source_inventory"]["nats"])
    require(all(nats_evidence[key] == state["stages"][NATS]["proof"][key] for key in nats_evidence),
            "Live JetStream evidence differs from the accepted stage")
    secondary_cutover.verify_live_secrets(cluster, resources)
    secret = cluster.get("secret", qdrant_stage.AUTH_SECRET)
    key = qdrant_stage.check_secret(secret, backup)
    with capture.port_forward(cluster, f"{QDRANT}-0", 6333) as endpoint:
        client = capture.Qdrant(endpoint, key)
        qdrant_stage.ready(client)
        peer = qdrant_stage.peer_id(client, backup["source_inventory"]["qdrant"]["peer_id"])
        observed = capture.qdrant_inventory(client)
    require(peer == state["stages"][QDRANT]["proof"]["peer_id"], "Live Qdrant peer differs from the accepted stage")
    qdrant_stage.equivalent(observed, backup["source_inventory"]["qdrant"], peer)
    require(production_runtime(cluster, state, resources) == before, "Production store identities changed during verification")
    require_api_paused(cluster, state)
    return {"runtime": before, "nats": nats_evidence, "qdrant_sha256": capture.canonical_hash(observed)}


def verify_live(cluster, state, backup):
    require(state["phase"] in {"installed", "live-verified"}, "Helm revision 6 installation is incomplete")
    pin, resources = installed_release(cluster, capture.RELEASE + 1, state["install-intent"])
    require(pin == state["helm6"], "Installed Helm revision 6 changed")
    for name in (NATS, QDRANT):
        cluster.kubectl("rollout", "status", f"statefulset/{name}", "--timeout=180s")
    evidence = live_inventory(cluster, state, backup, resources)
    require(state.get("live", evidence) == evidence, "Live verification receipt differs")
    state.update(phase="live-verified", live=evidence)
    save(state)


def resume_api(cluster, state, backup):
    require(state["phase"] in {"live-verified", "resume-intent", "resumed"}, "Production stores are not verified")

    def guard():
        pin, resources = installed_release(cluster, capture.RELEASE + 1, state["install-intent"])
        require(pin == state["helm6"] and live_inventory(cluster, state, backup, resources) == state["live"],
                "Production store state changed before API resume")

    if not next_release_present(cluster, capture.RELEASE + 2):
        guard()
    pin, resources = apply_upgrade(cluster, state, capture.RELEASE + 1, "resume-intent", None, guard)
    require(state.get("helm7", pin) == pin, "Installed Helm revision 7 changed")
    cluster.kubectl("rollout", "status", f"deployment/{API}", "--timeout=180s")
    secondary_cutover.verify_live_secrets(cluster, resources)
    require(api_identity(cluster, state["api"])["replicas"] == 1
            and production_runtime(cluster, state, resources) == state["live"]["runtime"],
            "API or retained production store identity changed during resume")
    state.update(phase="resumed", helm7=pin)
    save(state)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=("A matching deployed revision can be reconciled by repeating the interrupted command. "
                "For a matching pending or failed revision, inspect live replicas and preserve the journal "
                "and claims for reviewed forward recovery. Revision 7 may already have resumed the API; "
                "use a reviewed UID/spec/resource-version guarded pause if recovery requires quiescence."),
    )
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("prepare").add_argument("--nats-attempt", type=Path, required=True)
    for action in ("pause-api", "stop-stage-writers", "cancel", "stop-sources", "install", "verify-live", "resume-api"):
        commands.add_parser(action)
    args = parser.parse_args()
    try:
        cluster = capture.Cluster()
        ROOT.mkdir(mode=0o700, exist_ok=True)
        nats_stage.private(ROOT, 0o700, directory=True)
        capture.sync_directory(ROOT.parent)
        with nats_stage.lock_attempt(ROOT):
            if args.action == "prepare":
                prepare(cluster, args.nats_attempt)
            else:
                state = load()
                backup = nats_stage.verified_capture()
                operation = {
                    "pause-api": pause_api, "stop-stage-writers": stop_stage_writers, "cancel": cancel,
                    "stop-sources": stop_sources, "install": install, "verify-live": verify_live, "resume-api": resume_api,
                }
                operation[args.action](cluster, state, backup)
            print(json.dumps({"action": args.action, "phase": load()["phase"]}))
    except RuntimeError as error:
        parser.exit(1, f"Secondary handoff refused. {error}\n")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        parser.exit(1, "Secondary handoff failed. Retry the same phase after inspecting private status.\n")


if __name__ == "__main__":
    main()
