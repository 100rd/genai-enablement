"""Offline safety and equivalence checks for the isolated restore coordinator."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import qdrant_stage as stage


class BackupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.backup = Path(directory.name) / "capture"
        self.backup.mkdir(mode=0o700)
        files = {}
        names = ["qdrant.snapshot"]
        names.extend(
            f"nats/{stream}/{name}"
            for stream in stage.native.NATS_STREAMS for name in ("backup.json", "stream.tar.s2")
        )
        for name in names:
            artifact = self.backup / name
            artifact.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            for parent in artifact.parents:
                if parent == self.backup:
                    break
                parent.chmod(0o700)
            artifact.write_bytes(b"fixture")
            artifact.chmod(0o600)
            files[name] = {"bytes": 7, "sha256": hashlib.sha256(b"fixture").hexdigest()}
        self.receipt = self.backup / "receipt.json"
        self.receipt.write_text(json.dumps({
            "status": "complete", "files": files, "qdrant_snapshot": files["qdrant.snapshot"],
            "source_inventory": {"qdrant": {
                "version": "1.20.0", "collection": stage.native.QDRANT_COLLECTION, "points": 7,
                "point_digest": stage.POINT_SHA, "aliases": [], "peers": {"1": {}},
                "local_shards": [{"shard_id": 0, "state": "Active", "points_count": 7}],
            }},
        }))
        self.receipt.chmod(0o600)
        pinned = patch.object(stage, "RECEIPT_SHA", hashlib.sha256(self.receipt.read_bytes()).hexdigest())
        pinned.start()
        self.addCleanup(pinned.stop)

    def test_valid_backup(self):
        self.assertEqual(stage.verified_backup(self.backup)["status"], "complete")

    def test_missing_or_corrupted_snapshot(self):
        artifact = self.backup / "qdrant.snapshot"
        artifact.write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "Capture artifact differs"):
            stage.verified_backup(self.backup)
        artifact.unlink()
        with self.assertRaisesRegex(RuntimeError, "Missing or unsafe private qdrant.snapshot"):
            stage.verified_backup(self.backup)

    def test_wrong_receipt_pin(self):
        self.receipt.write_bytes(self.receipt.read_bytes() + b"\n")
        with self.assertRaisesRegex(RuntimeError, "Capture receipt pin differs"):
            stage.verified_backup(self.backup)


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.name = "omniscience-qdrant-stage-0123456789ab"
        self.pod = stage.pod_manifest(self.name, "restore", "first-intent")
        self.live = copy.deepcopy(self.pod)
        self.live["metadata"]["uid"] = "exact-uid"

    def test_manifest_has_only_stage_claim_and_loopback_peer(self):
        spec = self.pod["spec"]
        server = spec["containers"][0]
        self.assertEqual(server["args"], ["--uri", stage.PEER_URI, "--disable-telemetry"])
        self.assertEqual({item["name"]: item["value"] for item in server["env"] if "value" in item}[
            "QDRANT__CLUSTER__P2P__HOST"], "127.0.0.1")
        self.assertEqual(spec["volumes"][0]["persistentVolumeClaim"]["claimName"], self.name)
        self.assertFalse(spec["automountServiceAccountToken"])
        self.assertEqual(self.pod["metadata"]["labels"], {stage.LABEL: self.name})
        policies = stage.resources(self.name, {"claim": "c", "knp": "k", "cnp": "n"})
        self.assertEqual(policies["knp"]["spec"]["policyTypes"], ["Ingress", "Egress"])
        self.assertEqual(policies["cnp"]["spec"]["ingressDeny"], [{"fromEntities": ["all"]}])
        self.assertEqual(policies["cnp"]["spec"]["egressDeny"], [{"toEntities": ["all"]}])

    def test_injected_host_network_and_sidecar_rejected(self):
        for inject in (
            lambda obj: obj["spec"].update(hostNetwork=True),
            lambda obj: obj["spec"]["containers"].append({"name": "foreign"}),
        ):
            admitted = copy.deepcopy(self.pod)
            inject(admitted)
            with self.assertRaises(RuntimeError):
                stage.check_dry_run(admitted, self.pod)

    def test_init_container_accepts_default_empty_resources_only(self):
        admitted = copy.deepcopy(self.pod)
        init = admitted["spec"]["initContainers"][0]
        init.update(resources={}, imagePullPolicy="IfNotPresent",
                    terminationMessagePath="/dev/termination-log", terminationMessagePolicy="File")
        stage.check_dry_run(admitted, self.pod)
        init["resources"] = {"requests": {"cpu": "1"}}
        with self.assertRaisesRegex(RuntimeError, "Admission changed stage container configuration"):
            stage.check_dry_run(admitted, self.pod)

    def test_admission_cannot_prebind_the_staging_claim(self):
        claim = stage.resources(self.name, {"claim": "c", "knp": "k", "cnp": "n"})["claim"]
        stage.check_dry_run(claim, claim)
        admitted = copy.deepcopy(claim)
        admitted["spec"]["volumeName"] = "prebound-volume"
        with self.assertRaisesRegex(RuntimeError, "Admission prebound"):
            stage.check_dry_run(admitted, claim)
        self.assertEqual(stage.normalized_spec(admitted), claim["spec"])

    def test_service_selector_collision_rejected(self):
        cluster = Mock()
        cluster.kubectl.return_value = json.dumps({"items": [{"spec": {"selector": {stage.LABEL: self.name}}}]})
        with self.assertRaisesRegex(RuntimeError, "namespace Service"):
            stage.verify_service_scope(cluster, self.pod["metadata"]["labels"])

    def test_foreign_uid_cannot_be_adopted_or_deleted(self):
        cluster = Mock()
        cluster.absent.return_value = False
        cluster.get.return_value = self.live
        record = Mock(state={"resources": {"restore": {
            "uid": "recorded-uid", "spec_sha256": stage.native.canonical_hash(self.pod["spec"]),
        }}})
        with self.assertRaisesRegex(RuntimeError, "durable create intent or UID"):
            stage.create_or_check(cluster, record, "restore", self.pod, allow_create=True)
        cluster.kubectl.assert_not_called()
        record.save.assert_not_called()

    def test_only_scheduler_topology_labels_are_allowed_after_binding(self):
        labels = self.live["metadata"]["labels"]
        labels["topology.kubernetes.io/region"] = "eu-central-1"
        labels["topology.kubernetes.io/zone"] = "eu-central-1a"
        with self.assertRaisesRegex(RuntimeError, "durable create intent or UID"):
            stage.check_metadata(self.live, self.pod, "exact-uid")
        self.live["spec"]["nodeName"] = "stage-node"
        self.assertEqual(stage.check_metadata(self.live, self.pod, "exact-uid"), "exact-uid")
        labels["app"] = "foreign"
        with self.assertRaisesRegex(RuntimeError, "durable create intent or UID"):
            stage.check_metadata(self.live, self.pod, "exact-uid")

    def test_unrecorded_resource_requires_matching_create_intent(self):
        self.live["metadata"]["annotations"][stage.INTENT] = "foreign-intent"
        with self.assertRaisesRegex(RuntimeError, "durable create intent or UID"):
            stage.check_metadata(self.live, self.pod)


class IncidentTests(unittest.TestCase):
    def setUp(self):
        self.expected = stage.native.SOURCES[stage.SOURCE]
        source = {"release": {"helm_revision": 5}, "stores": {stage.SOURCE: self.expected},
                  "qdrant_auth_ref": {"uid": "key", "resource_version": "1"}}
        self.backup = {"source_inventory": {"source": source}}
        self.cluster = Mock()
        self.cluster.absent.return_value = True
        self.objects = {
            "secret": {"metadata": {"uid": "key", "resourceVersion": "1"},
                       "data": {stage.AUTH_KEY: "Zml4dHVyZQ=="}},
            "node": {"metadata": {"uid": stage.REPLACEMENT_NODE_UID}},
            "statefulset": {"metadata": {"uid": self.expected["sts_uid"]}},
            "pod": {
                "metadata": {"uid": stage.REPLACEMENT_POD_UID, "ownerReferences": [
                    {"uid": self.expected["sts_uid"], "controller": True},
                ]},
                "spec": {"nodeName": stage.REPLACEMENT_NODE, "volumes": [
                    {"persistentVolumeClaim": {"claimName": self.expected["pvc"]}},
                ]},
                "status": {"containerStatuses": [{"name": "qdrant", "imageID": stage.IMAGE}]},
            },
            "pvc": {"metadata": {"uid": self.expected["pvc_uid"]}, "status": {"phase": "Bound"},
                    "spec": {"volumeName": self.expected["pv"]}},
            "pv": {"metadata": {"uid": self.expected["pv_uid"]}, "spec": {
                "claimRef": {"namespace": stage.NS, "name": self.expected["pvc"], "uid": self.expected["pvc_uid"]},
                "persistentVolumeReclaimPolicy": "Retain",
                "hostPath": {"path": self.expected["path"], "type": "DirectoryOrCreate"},
            }},
        }
        self.cluster.get.side_effect = lambda kind, name: self.objects[kind]
        self.release_pin = Mock(return_value=(source["release"], None))
        pin = patch.dict(stage.native.SHARED, release_pin=self.release_pin)
        pin.start()
        self.addCleanup(pin.stop)

    def test_incident_guard_pins_only_identity_without_reading_live_store_contents(self):
        stage.incident_source_guard(self.cluster, self.backup)
        self.cluster.absent.assert_called_once_with("node", stage.native.SOURCE_NODE)
        self.cluster.kubectl.assert_not_called()

    def test_incident_guard_rejects_identity_drift(self):
        for kind, field in (("pod", "uid"), ("pvc", "uid"), ("pv", "uid"),
                            ("node", "uid"), ("statefulset", "uid"), ("secret", "resourceVersion")):
            with (self.subTest(kind=kind), patch.dict(self.objects[kind]["metadata"], {field: "foreign"}),
                  self.assertRaises(RuntimeError)):
                stage.incident_source_guard(self.cluster, self.backup)
        self.cluster.absent.return_value = False
        with self.assertRaisesRegex(RuntimeError, "Original capture node still exists"):
            stage.incident_source_guard(self.cluster, self.backup)
        self.release_pin.return_value = ({"helm_revision": 6}, None)
        with self.assertRaisesRegex(RuntimeError, "Incident Helm revision"):
            stage.incident_source_guard(self.cluster, self.backup)

    def test_incident_has_fresh_intent_and_does_not_touch_original_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / stage.STATE_DIR.name
            incident = root / stage.INCIDENT_STATE_DIR.name
            with stage.journal(original, create=True) as original_record:
                saved = original_record.path.read_bytes()
                with stage.journal(incident, create=True, incident=True) as incident_record:
                    self.assertNotEqual(original_record.state["stage"], incident_record.state["stage"])
                    self.assertTrue(incident_record.state["spot_incident"])
                    self.assertEqual(original_record.path.read_bytes(), saved)
            with self.assertRaisesRegex(RuntimeError, "different mode"), stage.journal(incident, create=False):
                self.fail("Incident journal opened in original mode")

    def test_incident_pod_requires_observed_on_demand_class(self):
        incident = stage.pod_manifest("isolated-stage", "restore", "intent", incident=True)
        self.assertEqual(incident["spec"]["nodeSelector"], {"eks.amazonaws.com/capacityType": "ON_DEMAND"})
        ordinary = stage.pod_manifest("isolated-stage", "restore", "intent")
        self.assertNotIn("nodeSelector", ordinary["spec"])


class ReadinessTests(unittest.TestCase):
    def test_request_timeout_is_capped_by_remaining_deadline(self):
        client = stage.native.Qdrant("127.0.0.1:6333", "fixture-key")
        client.opener = MagicMock()
        response = client.opener.open.return_value.__enter__.return_value
        response.status = 200
        with patch.object(stage.time, "monotonic", side_effect=[0, 89]):
            stage.ready(client)
        self.assertEqual(client.opener.open.call_args.kwargs["timeout"], 1)


class InventoryTests(unittest.TestCase):
    def test_point_config_payload_alias_and_shard_mismatches_rejected(self):
        expected = {
            "version": "1.20.0", "collection": stage.native.QDRANT_COLLECTION, "aliases": [],
            "config": {"params": {}}, "payload_schema": {}, "local_shards": [{"state": "Active"}],
            "points": 7, "point_digest": stage.POINT_SHA,
        }
        actual = {**expected, "peer_id": 2, "peers": {"2": {"uri": stage.PEER_URI}}}
        stage.equivalent(actual, expected, 2)
        for name, wrong in {
            "aliases": [{"alias_name": "unexpected"}], "config": {}, "payload_schema": {"index": {}},
            "local_shards": [{"state": "Dead"}], "points": 6, "point_digest": "different",
            "peers": {"2": {"uri": "http://source-peer:6335/"}}, "peer_id": 3,
        }.items():
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, "logical inventory differs"):
                stage.equivalent({**actual, name: wrong}, expected, 2)


if __name__ == "__main__":
    unittest.main()
