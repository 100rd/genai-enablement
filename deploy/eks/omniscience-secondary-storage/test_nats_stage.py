"""Local tests for NATS snapshot, isolation, ownership and restore guards."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import nats_stage as stage


class IncidentTest(unittest.TestCase):
    def setUp(self):
        self.source = stage.capture.SOURCES[stage.SOURCE]
        self.release = {"helm_revision": stage.capture.RELEASE}
        self.captured = {
            "release": self.release,
            "stores": {stage.SOURCE: {**self.source, "node": stage.capture.SOURCE_NODE}},
            "qdrant_auth_ref": {"uid": "auth", "resource_version": "23"},
        }
        pod = {
            "metadata": {
                "uid": stage.INCIDENT_POD_UID,
                "ownerReferences": [{"controller": True, "kind": "StatefulSet", "name": stage.SOURCE,
                                     "uid": self.source["sts_uid"]}],
            },
            "spec": {"nodeName": stage.INCIDENT_NODE, "volumes": [
                {"persistentVolumeClaim": {"claimName": self.source["pvc"]}},
            ]},
            "status": {"containerStatuses": [
                {"name": name, "imageID": image, "ready": True, "containerID": "runtime-" + name}
                for name, image in self.source["images"].items()
            ]},
        }
        self.pod = pod
        self.resources = {
            "node": {"metadata": {"uid": stage.INCIDENT_NODE_UID}},
            "statefulset": {"metadata": {"uid": self.source["sts_uid"]}},
            "secret": {"metadata": {"uid": "auth", "resourceVersion": "23"}},
            "pod": pod,
            "pvc": {"metadata": {"uid": self.source["pvc_uid"]}, "status": {"phase": "Bound"},
                    "spec": {"volumeName": self.source["pv"]}},
            "pv": {"metadata": {"uid": self.source["pv_uid"]}, "spec": {
                "claimRef": {"namespace": stage.NAMESPACE, "name": self.source["pvc"],
                             "uid": self.source["pvc_uid"]},
                "persistentVolumeReclaimPolicy": "Retain",
                "hostPath": {"path": self.source["path"], "type": "DirectoryOrCreate"},
            }},
        }
        self.cluster = Mock()
        self.cluster.get.side_effect = lambda kind, _name: self.resources[kind]
        self.cluster.absent.return_value = True

    def test_incident_validates_replacement_metadata_without_probing_source_data(self):
        with patch.dict(stage.SHARED, {"release_pin": Mock(return_value=(self.release, None))}):
            release, source = stage.incident_source_identity(self.cluster, self.captured)
            self.assertEqual(release, self.release)
            self.assertEqual(source["pod_uid"], stage.INCIDENT_POD_UID)
            self.assertEqual(source["node"], stage.INCIDENT_NODE)
            self.cluster.kubectl.assert_not_called()
            self.cluster.absent.assert_called_once_with("node", stage.capture.SOURCE_NODE)
            self.cluster.absent.return_value = False
            with self.assertRaisesRegex(RuntimeError, "still exists"):
                stage.incident_source_identity(self.cluster, self.captured)

    def test_incident_rejects_foreign_pod_and_auth_metadata(self):
        with patch.dict(stage.SHARED, {"release_pin": Mock(return_value=(self.release, None))}):
            self.pod["metadata"]["uid"] = "foreign"
            with self.assertRaisesRegex(RuntimeError, "Pod or StatefulSet"):
                stage.incident_source_identity(self.cluster, self.captured)
            self.pod["metadata"]["uid"] = stage.INCIDENT_POD_UID
            self.resources["secret"]["metadata"]["resourceVersion"] = "24"
            with self.assertRaisesRegex(RuntimeError, "Secret metadata"):
                stage.incident_source_identity(self.cluster, self.captured)

    def test_only_incident_manifest_adds_on_demand_to_source_selector(self):
        template = {"spec": {
            "volumes": [
                {"configMap": {"defaultMode": 420, "name": stage.CONFIG}, "name": "config"},
                {"emptyDir": {}, "name": "pid"},
            ],
            "containers": [
                {"name": "nats", "volumeMounts": [
                    {"name": name} for name in ("config", "pid", "omniscience-nats-js")
                ]},
                {"name": "reloader", "volumeMounts": [{"name": "pid"}, {"name": "config"}]},
            ],
            "nodeSelector": {"kubernetes.io/os": "linux"},
        }}
        self.resources["statefulset"]["spec"] = {
            "template": template, "volumeClaimTemplates": [{"metadata": {"name": "omniscience-nats-js"}}],
        }
        raw = '  "http_port": 8222,\n  "port": 4222,'
        with patch.object(stage, "TEMPLATE_SHA", stage.capture.canonical_hash(template)), \
                patch.object(stage, "isolation_check"):
            normal = stage.manifests(self.cluster, "normal", "token", raw)[-1]["spec"]
            incident = stage.manifests(self.cluster, "incident", "token", raw, incident=True)[-1]["spec"]
        self.assertEqual(normal["nodeSelector"], {"kubernetes.io/os": "linux"})
        self.assertEqual(incident["nodeSelector"], {**normal["nodeSelector"], **stage.ON_DEMAND})

    def test_incident_rejects_reused_node_name_with_different_uid(self):
        self.resources["node"]["metadata"]["uid"] = "another-node"
        with self.assertRaisesRegex(RuntimeError, "Node UID changed"):
            stage.incident_source_identity(self.cluster, self.captured)

    def test_normal_mode_never_falls_back_to_incident_mode(self):
        with patch.object(stage.capture, "source_identity", side_effect=RuntimeError("original pin differs")), \
                patch.object(stage, "incident_source_identity") as incident:
            with self.assertRaisesRegex(RuntimeError, "original pin differs"):
                stage.source_pin(self.cluster, {"source_inventory": {"source": self.captured}})
            incident.assert_not_called()

    def test_attempt_prefix_and_persisted_mode_prevent_cross_mode_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "nats-incident-0123456789ab"
            directory.mkdir(mode=0o700)
            intent = {"name": directory.name, "token": "0123456789ab",
                      "backup_sha256": stage.RECEIPT_SHA, "mode": "incident"}
            stage.sync_json(directory, "intent.json", intent)
            self.assertEqual(stage.get_intent(directory, incident=True), intent)
            with self.assertRaisesRegex(RuntimeError, "directory or mode"):
                stage.get_intent(directory)
            stage.sync_json(directory, "intent.json", {**intent, "mode": "normal"})
            with self.assertRaisesRegex(RuntimeError, "directory or mode"):
                stage.get_intent(directory, incident=True)


class IsolationTest(unittest.TestCase):
    def setUp(self):
        self.labels = {stage.LABEL: "test-token", "app.kubernetes.io/name": "nats-isolated-rehearsal"}
        self.baseline = {"metadata": {"name": "default-deny-all"}, "spec": copy.deepcopy(stage.ALLOWED_BASELINE)}
        self.policies = {"services": [], "networkpolicy": [], "ciliumnetworkpolicy": [],
                         "ciliumclusterwidenetworkpolicy": [self.baseline]}

    def verify(self):
        with patch.object(stage, "objects", side_effect=lambda cluster, kind: self.policies[kind]):
            stage.isolation_check(Mock(), self.labels)

    def test_stage_excludes_production_selectors_and_allows_known_global_baseline(self):
        self.policies["services"].append({"spec": {"selector": {"app.kubernetes.io/name": "nats"}}})
        self.policies["networkpolicy"].append({"spec": {
            "podSelector": {"matchExpressions": [
                {"key": "app.kubernetes.io/name", "operator": "In", "values": ["nats", "qdrant"]},
            ]},
            "ingress": [{}],
        }})
        self.verify()
        self.policies["services"].append({"spec": {"selector": {stage.LABEL: "test-token"}}})
        with self.assertRaisesRegex(RuntimeError, "existing Service"):
            self.verify()

    def test_rejects_other_allow_policies_and_changed_global_baseline(self):
        allow = {"spec": {"podSelector": {}, "egress": [{}]}}
        self.policies["networkpolicy"].append(allow)
        with self.assertRaisesRegex(RuntimeError, "Kubernetes allow"):
            self.verify()
        self.policies["networkpolicy"].clear()
        self.policies["ciliumnetworkpolicy"].append({
            "metadata": {"name": "unexpected"}, "spec": {"endpointSelector": {}, "ingress": [{}]},
        })
        with self.assertRaisesRegex(RuntimeError, "Cilium allow"):
            self.verify()
        self.policies["ciliumnetworkpolicy"].clear()
        self.baseline["spec"]["egress"].append({"toEntities": ["world"]})
        with self.assertRaisesRegex(RuntimeError, "baseline changed"):
            self.verify()

    def test_kubernetes_readback_accepts_only_omitted_empty_deny_arrays(self):
        expected = {"podSelector": {"matchLabels": self.labels}, "policyTypes": ["Ingress", "Egress"],
                    "ingress": [], "egress": []}
        actual = {key: value for key, value in expected.items() if key not in ("ingress", "egress")}
        self.assertTrue(stage.deny_policy_matches(actual, expected, "networkpolicy"))
        self.assertFalse(stage.deny_policy_matches({**actual, "ingress": [{}]}, expected, "networkpolicy"))
        self.assertFalse(stage.deny_policy_matches({**actual, "policyTypes": ["Ingress"]}, expected, "networkpolicy"))

    def test_loopback_config_changes_only_listener_keys(self):
        raw = '{\n  "http_port": 8222,\n  "port": 4222,\n  "server_name": $SERVER_NAME\n}\n'
        self.assertEqual(stage.loopback_config(raw),
                         '{\n  "http": "127.0.0.1:8222",\n  "listen": "127.0.0.1:4222",\n  "server_name": $SERVER_NAME\n}\n')
        with self.assertRaisesRegex(RuntimeError, "listen configuration"):
            stage.loopback_config(raw.replace("4222", "4223"))


class BackupTest(unittest.TestCase):
    def test_changed_backup_bytes_rejected_even_with_complete_pinned_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup = Path(tmp)
            files = {}
            for name in ["qdrant.snapshot", *(f"nats/{stream}/{artifact}" for stream in stage.capture.NATS_STREAMS
                                              for artifact in ("backup.json", "stream.tar.s2"))]:
                path = backup / name
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                path.parent.chmod(0o700)
                path.write_text("captured")
                path.chmod(0o600)
                files[name] = {"bytes": path.stat().st_size, "sha256": stage.capture.file_hash(path)}
            (backup / "nats").chmod(0o700)
            stage.sync_json(backup, "receipt.json", {"status": "complete", "files": files})
            pin = stage.capture.file_hash(backup / "receipt.json")
            with patch.multiple(stage, BACKUP=backup, RECEIPT_SHA=pin):
                self.assertEqual(stage.verified_capture()["files"], files)
                (backup / "qdrant.snapshot").write_text("tampered")
                with self.assertRaisesRegex(RuntimeError, "artifact changed"):
                    stage.verified_capture()


class OwnershipTest(unittest.TestCase):
    def test_interrupted_creation_adopts_only_matching_attempt_label_then_pins_uid(self):
        cluster = Mock()
        cluster.absent.return_value = False
        manifest = {"kind": "Pod", "metadata": {"labels": {stage.LABEL: "attempt"}}, "spec": {}}
        intent = {"name": "test", "uids": {}}
        cluster.get.return_value = {"metadata": {"labels": {stage.LABEL: "foreign"}, "uid": "other"}, "spec": {}}
        with patch.object(stage, "sync_json") as save:
            with self.assertRaisesRegex(RuntimeError, "Foreign"):
                stage.ensure_owned(cluster, Path("."), intent, manifest)
            save.assert_not_called()
            cluster.get.return_value["metadata"]["labels"][stage.LABEL] = "attempt"
            stage.ensure_owned(cluster, Path("."), intent, manifest)
            self.assertEqual(intent["uids"], {"pod": "other"})
            cluster.get.return_value["metadata"]["uid"] = "replaced"
            with self.assertRaisesRegex(RuntimeError, "replaced"):
                stage.ensure_owned(cluster, Path("."), intent, manifest)
            cluster.kubectl.assert_not_called()

    def test_pod_defaults_are_exact_and_sensitive_drift_is_rejected(self):
        desired = {"containers": [{"name": "nats", "args": ["--config", "/known"]}],
                   "volumes": [{"name": "config", "configMap": {"name": "stage"}}],
                   "automountServiceAccountToken": False}
        admitted = {**copy.deepcopy(desired), **copy.deepcopy(stage.POD_DEFAULTS), "nodeName": "scheduled"}
        stage.verify_pod_spec(admitted, desired)
        for field, value in (
            ("volumes", [{"name": "source", "persistentVolumeClaim": {"claimName": "source"}}]),
            ("volumes", [{"name": "source", "csi": {"driver": "unreviewed"}}]),
            ("containers", [{"name": "nats", "args": ["--config", "/different"]}]),
            ("serviceAccountName", "unexpected"),
            ("hostNetwork", True),
        ):
            with self.subTest(field=field, value=value), self.assertRaisesRegex(RuntimeError, "differs"):
                stage.verify_pod_spec({**admitted, field: value}, desired)

    def test_adoption_checks_sensitive_pod_spec_before_saving_uid(self):
        cluster = Mock()
        cluster.absent.return_value = False
        labels = {stage.LABEL: "attempt"}
        manifest = {"kind": "Pod", "metadata": {"labels": labels}, "spec": {"volumes": []}}
        intent = {"name": "test", "uids": {}}
        cluster.get.return_value = {"metadata": {"labels": labels, "uid": "same-label"},
                                    "spec": {"volumes": [{"name": "production", "secret": {"secretName": "prod"}}]}}
        with patch.object(stage, "sync_json") as save:
            with self.assertRaisesRegex(RuntimeError, "pinned template"):
                stage.ensure_owned(cluster, Path("."), intent, manifest)
            save.assert_not_called()
            self.assertEqual(intent["uids"], {})

    def test_only_scheduled_topology_labels_can_extend_attempt_labels(self):
        expected = {stage.LABEL: "attempt"}
        topology = {"topology.kubernetes.io/region": "eu-central-1",
                    "topology.kubernetes.io/zone": "eu-central-1a"}
        pod = {"metadata": {"labels": {**expected, **topology}}, "spec": {}}
        self.assertFalse(stage.resource_labels_match(pod, expected, "pod"))
        pod["spec"]["nodeName"] = "stage-node"
        self.assertTrue(stage.resource_labels_match(pod, expected, "pod"))
        self.assertFalse(stage.resource_labels_match(pod, expected, "configmap"))
        pod["metadata"]["labels"]["app"] = "foreign"
        self.assertFalse(stage.resource_labels_match(pod, expected, "pod"))

    def test_pod_topology_matches_its_node_and_ebs_zone(self):
        topology = {"topology.kubernetes.io/region": "eu-central-1",
                    "topology.kubernetes.io/zone": "eu-central-1a"}
        pod = {"metadata": {"labels": dict(topology)}, "spec": {"nodeName": "stage-node"}}
        cluster = Mock()
        cluster.get.return_value = {"metadata": {"labels": topology}}
        stage.verify_pod_topology(cluster, pod, "eu-central-1a")
        cluster.get.assert_called_once_with("node", "stage-node")
        with self.assertRaisesRegex(RuntimeError, "topology"):
            stage.verify_pod_topology(cluster, pod, "eu-central-1b")
        pod["metadata"]["labels"]["topology.kubernetes.io/region"] = "foreign"
        with self.assertRaisesRegex(RuntimeError, "topology"):
            stage.verify_pod_topology(cluster, pod, "eu-central-1a")

    def test_incident_runtime_requires_on_demand_node(self):
        zone = "eu-central-1a"
        pod = {"metadata": {"labels": {}}, "spec": {"nodeName": "stage-node"}}
        cluster = Mock()
        labels = {"topology.kubernetes.io/zone": zone, "eks.amazonaws.com/capacityType": "SPOT"}
        cluster.get.return_value = {"metadata": {"labels": labels}}
        stage.verify_pod_topology(cluster, pod, zone)
        with self.assertRaisesRegex(RuntimeError, "On-Demand"):
            stage.verify_pod_topology(cluster, pod, zone, incident=True)
        labels.update(stage.ON_DEMAND)
        stage.verify_pod_topology(cluster, pod, zone, incident=True)

    def test_stage_identity_checks_isolation_with_live_topology_labels(self):
        name = "stage"
        expected = {stage.LABEL: "attempt"}
        topology = {"topology.kubernetes.io/region": "eu-central-1",
                    "topology.kubernetes.io/zone": "eu-central-1a"}
        spec = {"automountServiceAccountToken": False, "volumes": [
            {"name": "data", "persistentVolumeClaim": {"claimName": name}},
            {"name": "config", "configMap": {"name": name}},
        ]}
        manifest = {"kind": "Pod", "metadata": {"labels": expected}, "spec": spec}
        pod = {
            "metadata": {"uid": "owned", "labels": {**expected, **topology}},
            "spec": {**spec, "nodeName": "stage-node"},
            "status": {"containerStatuses": [
                {"name": container, "imageID": image, "ready": True}
                for container, image in stage.capture.SOURCES[stage.SOURCE]["images"].items()
            ]},
        }
        intent = {"name": name, "uids": {"pod": "owned", "persistentvolumeclaim": "claim-uid"}}
        cluster = Mock()
        volume = {"availability_zone": "eu-central-1a"}
        endpoint_slices = [{"endpoints": None}, {"endpoints": []},
                           {"endpoints": [{"targetRef": None}, {"targetRef": {"uid": "other"}}]}]
        with patch.object(stage, "objects", return_value=endpoint_slices), \
                patch.object(stage, "claim_consumers", return_value=["owned"]), \
                patch.object(stage, "volume_identity", return_value=volume) as verify_volume, \
                patch.object(stage, "isolation_check") as isolation:
            cluster.get.side_effect = [pod, {"metadata": {"labels": topology}}]
            self.assertEqual(stage.stage_identity(cluster, intent, [manifest]), volume)
            isolation.assert_called_once_with(cluster, pod["metadata"]["labels"])

            endpoint_slices.append({"endpoints": [{"targetRef": {"uid": "owned"}}]})
            cluster.get.side_effect = [pod]
            verify_volume.reset_mock()
            with self.assertRaisesRegex(RuntimeError, "Service endpoint targets the rehearsal pod"):
                stage.stage_identity(cluster, intent, [manifest])
            verify_volume.assert_not_called()

    def test_claim_drift_blocks_before_pod_create(self):
        cluster = Mock()
        cluster.absent.return_value = True
        manifest = {"kind": "Pod", "metadata": {"labels": {}}, "spec": {}}
        intent = {"name": "stage", "uids": {"persistentvolumeclaim": "owned"}}
        for spec, phase, reason in (
            ({**stage.CLAIM_SPEC, "storageClassName": "foreign"}, "Pending", "claim specification"),
            ({**stage.CLAIM_SPEC, "volumeName": "foreign-pv"}, "Bound", "previously verified"),
            ({**stage.CLAIM_SPEC, "selector": {"matchLabels": {"unsafe": "true"}}}, "Pending", "claim specification"),
        ):
            with self.subTest(reason=reason):
                cluster.get.return_value = {"metadata": {"uid": "owned"}, "spec": spec, "status": {"phase": phase}}
                with self.assertRaisesRegex(RuntimeError, reason):
                    stage.ensure_owned(cluster, Path("."), intent, manifest)
                cluster.kubectl.assert_not_called()
        intent["volume"] = {"pv_uid": "expected"}
        cluster.get.return_value = {
            "metadata": {"uid": "owned"}, "spec": {**stage.CLAIM_SPEC, "volumeName": "foreign-pv"},
            "status": {"phase": "Bound"},
        }
        with patch.object(stage, "volume_identity", side_effect=RuntimeError("Unexpected rehearsal EBS PV binding")):
            with self.assertRaisesRegex(RuntimeError, "PV binding"):
                stage.ensure_owned(cluster, Path("."), intent, manifest)
        cluster.kubectl.assert_not_called()

    def test_pvc_admission_prebinding_blocks_actual_create(self):
        cluster = Mock()
        cluster.absent.return_value = True
        cluster.kubectl.return_value = json.dumps({"spec": {**stage.CLAIM_SPEC, "volumeName": "foreign"}})
        manifest = {"kind": "PersistentVolumeClaim", "metadata": {"labels": {}}, "spec": stage.CLAIM_SPEC}
        with self.assertRaisesRegex(RuntimeError, "prebinding"):
            stage.ensure_owned(cluster, Path("."), {"name": "stage", "uids": {}}, manifest)
        self.assertEqual(cluster.kubectl.call_count, 1)
        self.assertIn("--dry-run=server", cluster.kubectl.call_args.args)

    def test_pod_admission_spec_drift_blocks_actual_create(self):
        cluster = Mock()
        cluster.absent.return_value = True
        cluster.kubectl.return_value = json.dumps({"spec": {"hostNetwork": True}})
        manifest = {"kind": "Pod", "metadata": {"labels": {}}, "spec": {}}
        with patch.object(stage, "verify_claim_before_pod"):
            with self.assertRaisesRegex(RuntimeError, "pinned template"):
                stage.ensure_owned(cluster, Path("."), {"name": "stage", "uids": {}}, manifest)
        self.assertEqual(cluster.kubectl.call_count, 1)
        self.assertIn("--dry-run=server", cluster.kubectl.call_args.args)

    def test_unpinned_resource_refuses_shutdown_before_intent(self):
        cluster = Mock()
        cluster.absent.side_effect = lambda kind, _name: kind not in ("pod", "configmap")
        cluster.get.return_value = {"metadata": {"uid": "owned"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            with patch.object(stage, "get_intent", return_value={"name": "test", "uids": {"pod": "owned"}}), \
                    patch.dict(stage.SHARED, {"delete_owned": Mock()}) as helper:
                with self.assertRaisesRegex(RuntimeError, "reconcile stage"):
                    stage.stop(cluster, path)
                helper["delete_owned"].assert_not_called()
                self.assertFalse((path / "stop-intent.json").exists())

    def test_shutdown_refuses_foreign_uid_without_deleting(self):
        cluster = Mock()
        cluster.absent.return_value = False
        cluster.get.return_value = {"metadata": {"uid": "foreign"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            with patch.object(stage, "get_intent", return_value={"name": "test", "uids": {"pod": "expected"}}), \
                    patch.dict(stage.SHARED, {"delete_owned": Mock()}) as helper:
                with self.assertRaisesRegex(RuntimeError, "foreign"):
                    stage.stop(cluster, path)
                helper["delete_owned"].assert_not_called()


class RestoreTest(unittest.TestCase):
    def test_nonempty_jetstream_rejected_before_restore(self):
        cluster = Mock()
        server = {"version": "2.15.2", "server_name": "stage", "host": "127.0.0.1", "http_host": "127.0.0.1",
                  "port": 4222, "http_port": 8222, "connections": 0}
        jsz = {"accounts": 1, "streams": 1, "consumers": 0, "messages": 0,
               "account_details": [{"id": "$G", "stream_detail": [{"name": "existing"}]}]}
        cluster.kubectl.side_effect = [json.dumps(server), json.dumps(jsz)]
        with self.assertRaisesRegex(RuntimeError, "not empty"):
            stage.stage_inventory(cluster, "stage", "$G", empty=True)

    def test_empty_native_restore_comparison_is_narrow_and_keeps_raw_inventory(self):
        cursor = {"consumer_seq": 0, "stream_seq": 0}
        expected = {"version": "2.15.2", "account": "$G", "streams": {"one": {
            "config": {"storage": "file"}, "state": {"messages": 0, "bytes": 0, "last_seq": 0, "first_seq": 0},
            "consumers": {"durable": {
                "config": {"durable_name": "durable"}, "created": "2026-11-07T12:00:00.123456789Z",
                "delivered": cursor, "ack_floor": dict(cursor), "num_ack_pending": 0,
                "num_redelivered": 0, "num_waiting": 0, "num_pending": 0,
            }},
        }}}
        observed = copy.deepcopy(expected)
        stream = observed["streams"]["one"]
        stream["state"]["first_seq"] = 1
        stream["consumers"]["durable"]["created"] = "2026-11-07T12:00:00.123456790Z"
        raw = copy.deepcopy(observed)
        evidence = stage.restore_evidence(observed, expected)
        self.assertEqual(evidence["logical_sha256"], stage.capture.canonical_hash(expected))
        self.assertEqual(evidence["observed_sha256"], stage.capture.canonical_hash(raw))
        self.assertEqual(observed, raw)

        for path, value in (
            (("version",), "2.15.3"),
            (("account",), "foreign"),
            (("streams", "one", "config", "storage"), "memory"),
            (("streams", "one", "state", "first_seq"), 2),
            (("streams", "one", "state", "last_seq"), 1),
            (("streams", "one", "state", "bytes"), 1),
            (("streams", "one", "consumers", "durable", "created"), "2026-11-07T12:00:00.123456788Z"),
            (("streams", "one", "consumers", "durable", "created"), "2026-02-30T12:00:00Z"),
            (("streams", "one", "consumers", "durable", "num_pending"), 1),
            (("streams", "one", "consumers", "durable", "ack_floor", "stream_seq"), 1),
        ):
            with self.subTest(path=path, value=value):
                invalid = copy.deepcopy(observed)
                target = invalid
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaisesRegex(RuntimeError, "consumer cursors"):
                    stage.restore_evidence(invalid, expected)

        advanced_expected = copy.deepcopy(expected)
        advanced_observed = copy.deepcopy(observed)
        for inventory in (advanced_expected, advanced_observed):
            inventory["streams"]["one"]["state"].update(first_seq=4, last_seq=3)
        with self.assertRaisesRegex(RuntimeError, "consumer cursors"):
            stage.restore_evidence(advanced_observed, advanced_expected)

    def test_semantic_difference_never_marks_restore_verified(self):
        captured = {"source_inventory": {"nats": {"account": "$G", "streams": {"one": {"cursor": 0}}}}}
        intent, ready = {"name": "stage"}, {"volume": "same"}
        with patch.object(stage, "pre_restore", return_value=(intent, ready)), \
                patch.object(stage, "stage_inventory", return_value={"account": "$G", "streams": {"one": {"cursor": 1}}}), \
                patch.object(stage, "sync_json") as save, \
                patch.dict(stage.SHARED, {"read_private_json": Mock(return_value={
                    "backup_sha256": stage.RECEIPT_SHA, "ready": ready,
                })}):
            with self.assertRaisesRegex(RuntimeError, "consumer cursors"):
                stage.verify_restore(Mock(), Path("."), captured)
            save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
