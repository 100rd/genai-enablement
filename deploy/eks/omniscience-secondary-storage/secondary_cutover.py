#!/usr/bin/env python3
"""Render and verify the proposed secondary-store Helm handoff without applying it."""

import argparse
import base64
import copy
import json
import re
import runpy
import subprocess
import tempfile
import sys
from contextlib import contextmanager
from pathlib import Path

import capture
import nats_stage
import qdrant_stage

SHARED = capture.SHARED
require = capture.require
HERE = Path(__file__).resolve().parent
NEO4J = runpy.run_path(str(HERE.parent / "neo4j-storage" / "recover.py"))
parse_manifest = NEO4J["resources_by_name"]
NATS = "omniscience-nats"
QDRANT = "omniscience-qdrant"
ON_DEMAND = qdrant_stage.ON_DEMAND
QDRANT_CONFIG_SHA = "ccbaeb87949c91e370b5e55e8e1630fb2a480fb18a5e59c0f69778f19894d13b"
POSTRENDERER = "secondary-store-handoff"
QDRANT_FIRST_PEER = "exec ./entrypoint.sh --uri 'http://omniscience-qdrant-0.omniscience-qdrant-headless:6335'"


def set_api_paused(resources):
    api = resources[("Deployment", "omniscience-api")]["spec"]
    require(api["replicas"] == 1, "Expected Helm revision 5 with one configured API replica")
    api["replicas"] = 0


def expected_store(resources, name, volume_name, claim):
    sts = resources[("StatefulSet", name)]["spec"]
    require(sts.get("replicas", 1) == 1, "Secondary store must have a single replica")
    require([entry["metadata"]["name"] for entry in sts["volumeClaimTemplates"]] == [volume_name],
            "Unexpected secondary store claim template")
    del sts["volumeClaimTemplates"]
    pod = sts["template"]["spec"]
    require(not any(item["name"] == volume_name for item in pod["volumes"]), "Existing store data volume")
    pod["volumes"].append({"name": volume_name, "persistentVolumeClaim": {"claimName": claim}})
    pod["nodeSelector"] = {**pod.get("nodeSelector", {}), **ON_DEMAND}
    return pod


def expected_nats(resources, claim):
    pod = expected_store(resources, NATS, "omniscience-nats-js", claim)
    images = capture.SOURCES[NATS]["images"]
    require([container["name"] for container in pod["containers"]] == ["nats", "reloader"],
            "Unexpected NATS container layout")
    for container in pod["containers"]:
        container["image"] = images[container["name"]]


def preserve_qdrant_file_modes(pod):
    # The Helm template spells these as YAML octal; yq parses the digits as decimal.
    # Encode the equivalent Kubernetes integer before emitting the patched JSON document.
    volumes = {item["name"]: item for item in pod["volumes"]}
    for name, kind, yaml_digits, api_value in (
        ("qdrant-config", "configMap", 755, 0o755),
        ("qdrant-secret", "secret", 600, 0o600),
    ):
        source = volumes[name][kind]
        require(source["defaultMode"] in (yaml_digits, api_value), "Unexpected Qdrant volume file mode")
        source["defaultMode"] = api_value


def qdrant_postrender(resources, claim):
    pod = expected_store(resources, QDRANT, "qdrant-storage", claim)
    preserve_qdrant_file_modes(pod)
    require([container["name"] for container in pod["containers"]] == ["qdrant"]
            and [container["name"] for container in pod["initContainers"]] == ["ensure-dir-ownership"],
            "Unexpected Qdrant container layout")
    for container in pod["containers"] + pod["initContainers"]:
        container["image"] = qdrant_stage.IMAGE
    data = resources[("ConfigMap", QDRANT)]["data"]
    require(capture.canonical_hash(data) == QDRANT_CONFIG_SHA, "Qdrant production config digest differs")
    script = data["initialize.sh"]
    require(script.count(QDRANT_FIRST_PEER) == 1, "Unexpected Qdrant first peer command")
    data["initialize.sh"] = script.replace(QDRANT_FIRST_PEER, f"exec ./entrypoint.sh --uri '{qdrant_stage.PEER_URI}'")
    config = data["production.yaml"]
    require(config.count("  p2p:\n") == 1, "Unexpected Qdrant P2P configuration")
    data["production.yaml"] = config.replace("  p2p:\n", "  p2p:\n    host: 127.0.0.1\n")


def nats_values(claim):
    images = capture.SOURCES[NATS]["images"]
    return {
        "replicaCount": 0,
        "nats": {
            "statefulSet": {"patch": [{"op": "remove", "path": "/spec/volumeClaimTemplates"}]},
            "podTemplate": {
                "merge": {"spec": {"nodeSelector": ON_DEMAND}},
                "patch": [
                    {"op": "add", "path": "/spec/volumes/-", "value": {
                        "name": "omniscience-nats-js", "persistentVolumeClaim": {"claimName": claim},
                    }},
                    {"op": "replace", "path": "/spec/containers/0/image", "value": images["nats"]},
                    {"op": "replace", "path": "/spec/containers/1/image", "value": images["reloader"]},
                ],
            },
        },
    }


def equal_resources(actual, expected):
    differing = sorted(key for key in actual.keys() | expected.keys() if actual.get(key) != expected.get(key))
    require(not differing, f"Unexpected rendered resource changes: {', '.join('/'.join(key) for key in differing)}")


def expected_helm_render(baseline, nats_claim):
    expected = copy.deepcopy(baseline)
    set_api_paused(expected)
    expected_nats(expected, nats_claim)
    return expected


def verify_final_render(baseline, proposed, nats_claim, qdrant_claim):
    expected = expected_helm_render(baseline, nats_claim)
    qdrant_postrender(expected, qdrant_claim)
    equal_resources(proposed, expected)


def verify_helm_render(baseline, actual, nats_claim):
    equal_resources(actual, expected_helm_render(baseline, nats_claim))


def verified_nats_claim(cluster, attempt, backup):
    intent, ready = nats_stage.pre_restore(cluster, attempt, backup, incident=True)
    restore_intent = {"backup_sha256": nats_stage.RECEIPT_SHA, "ready": ready}
    require(SHARED["read_private_json"](attempt / "restore-intent.json") == restore_intent,
            "NATS restore intent differs")
    nats = SHARED["read_private_json"](attempt / "restore-verified.json")
    expected = backup["source_inventory"]["nats"]
    observed = nats_stage.stage_inventory(cluster, intent["name"], expected["account"])
    require(SHARED["read_private_json"](attempt / "restored-inventory.json") == observed
            and nats == {**restore_intent, **nats_stage.restore_evidence(observed, expected)},
            "NATS accepted rehearsal evidence differs")
    require(nats_stage.pre_restore(cluster, attempt, backup, incident=True) == (intent, ready),
            "NATS accepted rehearsal state changed")
    return intent["name"], ready["volume"]


def verified_qdrant_claim(cluster, record, backup):
    state = record.state
    require(state["phase"] == "accepted" and state["accepted_at"]
            and state["point_digest"] == qdrant_stage.POINT_SHA and state["peer_uri"] == qdrant_stage.PEER_URI,
            "Qdrant accepted rehearsal evidence differs")
    qdrant_stage.rehearse(cluster, record, backup, verify_only=True)
    return state["stage"], state["volume"]


@contextmanager
def accepted_claims(cluster, nats_attempt):
    attempt = nats_stage.prepare_attempt(nats_attempt, incident=True)
    nats_backup = nats_stage.verified_capture()
    qdrant_backup = qdrant_stage.verified_backup()
    with nats_stage.lock_attempt(attempt), qdrant_stage.journal(
        qdrant_stage.INCIDENT_STATE_DIR, create=False, incident=True,
    ) as record:
        nats = verified_nats_claim(cluster, attempt, nats_backup)
        qdrant = verified_qdrant_claim(cluster, record, qdrant_backup)
        yield nats[0], qdrant[0]
        require(verified_nats_claim(cluster, attempt, nats_backup) == nats
                and verified_qdrant_claim(cluster, record, qdrant_backup) == qdrant,
                "Accepted claim identities changed during render")


def verify_live_secrets(cluster, resources):
    for (kind, name), obj in resources.items():
        if kind != "Secret":
            continue
        live = cluster.get("secret", name)
        data = dict(obj.get("data", {}))
        data.update({key: base64.b64encode(value.encode()).decode() for key, value in obj.get("stringData", {}).items()})
        require(data == live.get("data", {}) and obj.get("type", "Opaque") == live["type"],
                f"Rendered Secret {name} differs from live")


def install_local_postrenderer(directory):
    plugins = directory / "plugins"
    plugin = plugins / POSTRENDERER
    plugin.mkdir(parents=True)
    (plugin / "plugin.yaml").write_text(json.dumps({
        "apiVersion": "v1", "type": "postrenderer/v1", "runtime": "subprocess",
        "name": POSTRENDERER, "version": "0.1.0",
        "runtimeConfig": {"platformCommand": [{
            "command": sys.executable, "args": [str(Path(__file__).resolve()), "--post-render-qdrant"],
        }]},
    }))
    return plugins


def postrender(stream, claim):
    require(re.fullmatch(r"omniscience-qdrant-stage-[a-f0-9]{12}", claim),
            "Unexpected Qdrant postrenderer claim name")
    resources = parse_manifest(stream)
    qdrant_postrender(resources, claim)
    targets = {("StatefulSet", QDRANT), ("ConfigMap", QDRANT)}
    documents = re.split(r"(?m)^---[ \t]*\r?$", stream)
    for index, document in enumerate(documents):
        parsed = parse_manifest(document)
        if parsed.keys() & targets:
            key, = parsed
            documents[index] = "\n" + json.dumps(resources[key]) + "\n"
            targets.remove(key)
    require(not targets, "Qdrant postrenderer did not replace both intended documents")
    return "---".join(documents)


def read_helm_render(output, expected_hooks):
    header, manifest = output.split("MANIFEST:\n", 1)
    hooks = header.split("\nHOOKS:\n", 1)[1]
    equal_resources(parse_manifest(hooks), expected_hooks)
    return parse_manifest(manifest)


def normalize_postgres_annotations(resources):
    # Helm 4 omits the null map after removing its temporary postrenderer annotation.
    metadata = resources[("Service", "omniscience-postgres-hl")]["metadata"]
    metadata.setdefault("annotations", None)


def manifest_digest(resources):
    return capture.canonical_hash([resources[key] for key in sorted(resources)])


def hook_resources(release):
    hooks = [(hook["name"], hook["kind"], hook["events"]) for hook in release["hooks"]]
    require(hooks == SHARED["EXPECTED_HOOKS"], "Helm hook inventory differs")
    return parse_manifest("\n---\n".join(hook["manifest"] for hook in release["hooks"]))


@contextmanager
def render_session(cluster, nats_claim, qdrant_claim, *, revision=capture.RELEASE, previous_plan=None,
                   admission_check=None):
    pin, payload = SHARED["release_pin"](cluster, revision)
    release = SHARED["decode_release"](payload)
    baseline = parse_manifest(release["manifest"])
    expected_hooks = hook_resources(release)
    if revision == capture.RELEASE:
        captured = nats_stage.verified_capture()["source_inventory"]["source"]
        require(pin == captured["release"], "Helm revision 5 identity differs from the native capture")
        values_override = nats_values(nats_claim)
        replicas = 0
    else:
        require(revision == capture.RELEASE + 1 and previous_plan is not None, "Unexpected resume render revision")
        normalize_postgres_annotations(baseline)
        require(manifest_digest(baseline) == previous_plan["manifest_sha256"]
                and baseline[("Deployment", "omniscience-api")]["spec"]["replicas"] == 0,
                "Installed secondary-store Helm baseline differs")
        values_override = {"replicaCount": 1}
        replicas = 1
    with tempfile.TemporaryDirectory(prefix="secondary-cutover-", dir=capture.PRIVATE) as directory:
        path = Path(directory).resolve()
        chart = path / "omniscience"
        SHARED["restore_chart"](chart, release)
        values = path / "handoff-values.json"
        values.write_text(json.dumps(values_override))
        env = SHARED["helm_context"](cluster, path / "kubeconfig")
        env["HELM_PLUGINS"] = str(install_local_postrenderer(path))
        command = [
            "helm", "upgrade", "omniscience", str(chart), "--kube-context", cluster.helper["CONTEXT"],
            "-n", capture.NAMESPACE, "--reuse-values", "--no-hooks", "-f", str(values),
        ]
        if replicas == 0:
            plain = subprocess.run(command + ["--dry-run=server"], env=env, capture_output=True, text=True,
                                   check=True).stdout
            verify_helm_render(baseline, read_helm_render(plain, expected_hooks), nats_claim)
        command += ["--post-renderer", POSTRENDERER, "--post-renderer-args", qdrant_claim]
        output = subprocess.run(command + ["--dry-run=server"], env=env, capture_output=True, text=True,
                                check=True).stdout
        proposed = read_helm_render(output, expected_hooks)
        normalize_postgres_annotations(proposed)
        if replicas == 0:
            verify_final_render(baseline, proposed, nats_claim, qdrant_claim)
        else:
            expected = copy.deepcopy(baseline)
            expected[("Deployment", "omniscience-api")]["spec"]["replicas"] = 1
            equal_resources(proposed, expected)
        verify_live_secrets(cluster, proposed)
        require(SHARED["release_pin"](cluster, revision)[0] == pin, "Helm revision changed during render")
        plan = {
            "status": "render-verified", "admission_verified": False, "helm_revision": revision,
            "api_replicas": replicas, "claims": {NATS: nats_claim, QDRANT: qdrant_claim},
            "changed": ["/".join(key) for key in sorted(proposed) if proposed[key] != baseline[key]],
            "manifest_sha256": manifest_digest(proposed),
        }
        if admission_check is not None:
            admission_check(proposed)
        yield plan, command, env


def render(cluster, nats_claim, qdrant_claim):
    with render_session(cluster, nats_claim, qdrant_claim) as (plan, _, _):
        return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nats-attempt", type=Path, required=True)
    args = parser.parse_args()
    try:
        cluster = capture.Cluster()
        with accepted_claims(cluster, args.nats_attempt) as claims:
            plan = render(cluster, *claims)
    except RuntimeError as error:
        parser.exit(1, f"Secondary-store render refused. {error}\n")
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        parser.exit(1, "Secondary-store render failed. Inspect without printing Helm or Secret payloads.\n")
    print(json.dumps(plan, indent=2, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--post-render-qdrant":
        try:
            sys.stdout.write(postrender(sys.stdin.read(), sys.argv[2]))
        except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError):
            sys.exit("Secondary-store postrenderer refused the manifest.")
    else:
        main()
