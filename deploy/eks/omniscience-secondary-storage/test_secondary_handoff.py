"""Tests for the journaled preparation, pause and staged writer shutdown."""

import copy
import json
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

import secondary_handoff as handoff


class PauseTest(unittest.TestCase):
    def setUp(self):
        self.api = {"uid": "api-uid", "resource_version": "r1", "replicas": 1, "spec_sha256": "unchanged"}
        self.state = {"phase": "prepared", "api": self.api, "source": {"identity": "same"}, "stages": {},
                      "source_inventory": {"nats": {"streams": {}}}}
        self.cluster = Mock()

    def test_patch_only_changes_replica_count_with_uid_and_version_tests(self):
        handoff.patch_api(self.cluster, self.api, 0)
        args = self.cluster.kubectl.call_args.args
        self.assertEqual(args[:-1], ("patch", "deployment", handoff.API, "--type=json", "-p"))
        self.assertEqual(json.loads(args[-1]), [
            {"op": "test", "path": "/metadata/uid", "value": "api-uid"},
            {"op": "test", "path": "/metadata/resourceVersion", "value": "r1"},
            {"op": "test", "path": "/spec/replicas", "value": 1},
            {"op": "replace", "path": "/spec/replicas", "value": 0},
        ])

    def test_api_spec_pin_excludes_replicas_but_rejects_template_drift(self):
        deployment = {"metadata": {"uid": "api-uid", "resourceVersion": "r1"},
                      "spec": {"replicas": 1, "template": {"spec": {"containers": [{"image": "pinned"}]}}}}
        self.cluster.get.return_value = deployment
        before = handoff.api_identity(self.cluster)
        deployment["spec"]["replicas"] = 0
        deployment["metadata"]["resourceVersion"] = "r2"
        self.assertEqual(handoff.api_identity(self.cluster, before)["replicas"], 0)
        deployment["spec"]["template"]["spec"]["containers"][0]["image"] = "foreign"
        with self.assertRaisesRegex(RuntimeError, "specification changed"):
            handoff.api_identity(self.cluster, before)

    def test_lost_patch_acknowledgment_resumes_existing_pause_intent(self):
        disk = {}

        def save(state):
            disk.update(copy.deepcopy(state))

        def patch_then_lose_ack(*_args):
            self.assertEqual(disk["phase"], "pause-intent")
            self.assertEqual(disk["pause_api"], self.api)
            raise TimeoutError("lost reply")

        observed = {"nats": "exact", "qdrant": "empty"}
        with patch.multiple(
            handoff,
            source_identity=Mock(return_value=self.state["source"]),
            api_identity=Mock(side_effect=[self.api, {**self.api, "resource_version": "r2", "replicas": 0}]),
            verify_stage_writers=Mock(),
            source_inventory=Mock(return_value=self.state["source_inventory"]),
            save=Mock(side_effect=save),
            patch_api=Mock(side_effect=patch_then_lose_ack),
            wait_api_drain=Mock(),
            quiesced_source=Mock(return_value=observed),
        ):
            with self.assertRaisesRegex(TimeoutError, "lost reply"):
                handoff.pause_api(self.cluster, self.state, {})
            handoff.pause_api(self.cluster, copy.deepcopy(disk), {})
            handoff.patch_api.assert_called_once()
        self.assertEqual(disk["phase"], "quiesced")
        self.assertEqual(disk["quiesced"], observed)

    def test_unjournaled_zero_replica_state_is_rejected(self):
        with patch.multiple(
            handoff,
            source_identity=Mock(return_value=self.state["source"]),
            api_identity=Mock(return_value={**self.api, "replicas": 0}),
            save=Mock(),
            patch_api=Mock(),
        ):
            with self.assertRaisesRegex(RuntimeError, "replica count before pause"):
                handoff.pause_api(self.cluster, self.state, {})
            handoff.save.assert_not_called()
            handoff.patch_api.assert_not_called()

    def test_cancel_recovers_lost_resume_acknowledgment(self):
        self.state["phase"] = "quiesced"
        disk = {}

        def save(state):
            disk.update(copy.deepcopy(state))

        with patch.multiple(
            handoff,
            source_identity=Mock(return_value=self.state["source"]),
            api_identity=Mock(side_effect=[{**self.api, "replicas": 0}, self.api, self.api]),
            save=Mock(side_effect=save),
            patch_api=Mock(side_effect=TimeoutError("lost reply")),
        ):
            with self.assertRaises(TimeoutError):
                handoff.cancel(self.cluster, self.state, {})
            self.assertEqual(disk["phase"], "cancel-intent")
            handoff.cancel(self.cluster, copy.deepcopy(disk), {})
            handoff.patch_api.assert_called_once()
        self.assertEqual(disk["phase"], "cancelled")


class QuiescenceTest(unittest.TestCase):
    def test_only_active_ephemeral_waiters_are_ignored(self):
        source = {"streams": {"stream": {"consumers": {"durable": {
            "num_waiting": 4, "num_pending": 0, "created": "first",
        }}}}}
        alternate = copy.deepcopy(source)
        consumer = alternate["streams"]["stream"]["consumers"]["durable"]
        consumer["num_waiting"] = 2
        self.assertEqual(handoff.persistent_nats(source), handoff.persistent_nats(alternate))
        self.assertEqual(source["streams"]["stream"]["consumers"]["durable"]["num_waiting"], 4)
        with self.assertRaisesRegex(RuntimeError, "pull waiters"):
            handoff.persistent_nats(alternate, paused=True)
        for field, value in (("num_pending", 1), ("created", "recreated")):
            with self.subTest(field=field):
                changed = copy.deepcopy(alternate)
                changed["streams"]["stream"]["consumers"]["durable"][field] = value
                self.assertNotEqual(handoff.persistent_nats(source), handoff.persistent_nats(changed))

    def test_qdrant_requires_exact_empty_reviewed_collection_and_peer(self):
        expected = {"version": "1.20.0", "collection": "reviewed", "aliases": [], "config": {},
                    "payload_schema": {"indexed": {"data_type": "keyword", "points": 7}}}
        observed = {
            **expected, "payload_schema": {"indexed": {"data_type": "keyword", "points": 0}},
            "points": 0, "point_digest": handoff.capture.canonical_hash([]),
            "local_shards": [{"shard_id": 0, "state": "Active", "points_count": 0}],
            "peer_id": handoff.QDRANT_REPLACEMENT_PEER,
            "peers": {str(handoff.QDRANT_REPLACEMENT_PEER): {"uri": handoff.QDRANT_REPLACEMENT_URI}},
        }
        handoff.verify_empty_qdrant(observed, expected)
        for change in ({"points": 1}, {"collection": "new"}, {"aliases": [{"alias_name": "new"}]}, {"peer_id": 42},
                       {"payload_schema": expected["payload_schema"]}):
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, "reviewed empty"):
                handoff.verify_empty_qdrant({**observed, **change}, expected)


class StageStopTest(unittest.TestCase):
    def setUp(self):
        self.stage = {"name": "nats-incident-111111111111", "pod": "stage-pod", "uid": "stage-uid",
                      "volume": {"pvc_uid": "claim-uid"}}
        self.state = {"phase": "stage-stop-intent", "quiesced": {"proof": "same"},
                      "nats_attempt": self.stage["name"], "stages": {handoff.NATS: self.stage}}
        self.cluster = Mock()

    def test_resumes_after_delete_without_removing_any_other_resource(self):
        self.cluster.absent.return_value = True
        attempt = Path("/private") / self.stage["name"]
        with patch.multiple(
            handoff,
            stage_records=Mock(return_value=self.state["stages"]),
            quiesced_source=Mock(return_value=self.state["quiesced"]),
            claim_identity=Mock(return_value=self.stage["volume"]),
            detached=Mock(return_value=True),
            save=Mock(),
        ), patch.multiple(
            handoff.nats_stage,
            prepare_attempt=Mock(return_value=attempt),
            lock_attempt=Mock(return_value=nullcontext()),
            claim_consumers=Mock(return_value=[]),
        ), patch.object(
            handoff.qdrant_stage, "journal", return_value=nullcontext(),
        ), patch.dict(handoff.SHARED, {"delete_owned": Mock()}) as shared:
            handoff.stop_stage_writers(self.cluster, self.state, {})
            shared["delete_owned"].assert_not_called()
            handoff.save.assert_called_once()
        self.assertEqual(self.state["phase"], "stages-stopped")

    def test_replaced_writer_is_refused(self):
        self.cluster.absent.return_value = False
        self.cluster.get.return_value = {"metadata": {"uid": "foreign-uid"}}
        with patch.object(handoff, "claim_identity", return_value=self.stage["volume"]), \
                patch.object(handoff.nats_stage, "claim_consumers", return_value=["foreign-uid"]):
            with self.assertRaisesRegex(RuntimeError, "writer UID"):
                handoff.verify_stage_writers(self.cluster, self.state["stages"], allow_absent=True)
        self.cluster.kubectl.assert_not_called()


class AdmissionTest(unittest.TestCase):
    def test_renamed_server_create_dry_run_checks_exact_admitted_statefulset(self):
        name = handoff.NATS
        original = {
            "volumeClaimTemplates": [{"metadata": {"name": "data"}}],
            "template": {"spec": {"volumes": [], "containers": [{"name": "nats", "image": "original"}]}},
        }
        proposed = {
            "kind": "StatefulSet", "metadata": {"name": name, "labels": {"app": "nats"}},
            "spec": {"template": {"spec": {"nodeSelector": {"capacity": "On-Demand"},
                                           "containers": [{"name": "nats", "image": "pinned"}]}}},
        }
        cluster = Mock()
        cluster.get.return_value = {
            "metadata": {"uid": handoff.capture.SOURCES[name]["sts_uid"]}, "spec": original,
        }
        expected = handoff.expected_admitted_statefulset(original, proposed["spec"], "accepted-claim")

        def dry_run(*args, **kwargs):
            self.assertEqual(args, ("create", "--dry-run=server", "-f", "-", "-o", "json"))
            body = json.loads(kwargs["input"])
            self.assertNotEqual(body["metadata"]["name"], name)
            self.assertTrue(body["metadata"]["name"].startswith("handoff-validation-"))
            return json.dumps({
                **body, "metadata": {**body["metadata"], "namespace": handoff.capture.NAMESPACE},
                "spec": expected,
            })

        cluster.kubectl.side_effect = dry_run
        proof = handoff.verify_create_admission(cluster, {("StatefulSet", name): proposed}, {name: "accepted-claim"})
        self.assertFalse(proof["production_name_admitted"])
        self.assertEqual(proof["spec_sha256"], {name: handoff.capture.canonical_hash(expected)})
        expected["template"]["spec"]["containers"][0]["image"] = "injected"
        with self.assertRaisesRegex(RuntimeError, "admission changed"):
            handoff.verify_create_admission(cluster, {("StatefulSet", name): proposed}, {name: "accepted-claim"})


class SourceStopTest(unittest.TestCase):
    def test_scale_and_delete_are_resource_version_guarded_and_orphan_dependents(self):
        cluster = Mock()
        identity = {"uid": "original-sts", "resource_version": "version-10"}
        handoff.scale_source_zero(cluster, handoff.NATS, identity)
        self.assertEqual(json.loads(cluster.kubectl.call_args.args[-1]), [
            {"op": "test", "path": "/metadata/uid", "value": "original-sts"},
            {"op": "test", "path": "/metadata/resourceVersion", "value": "version-10"},
            {"op": "test", "path": "/spec/replicas", "value": 1},
            {"op": "replace", "path": "/spec/replicas", "value": 0},
        ])
        handoff.delete_source(cluster, handoff.NATS, identity)
        args, kwargs = cluster.kubectl.call_args
        self.assertEqual(args[:2], ("delete", "--raw"))
        self.assertTrue(args[2].endswith("/statefulsets/" + handoff.NATS))
        self.assertEqual(json.loads(kwargs["input"]), {
            "apiVersion": "v1", "kind": "DeleteOptions", "propagationPolicy": "Orphan",
            "preconditions": {"uid": "original-sts", "resourceVersion": "version-10"},
        })

    def test_retry_accepts_absent_original_only_with_matching_delete_intent(self):
        cluster = Mock()
        cluster.absent.return_value = True
        claims = {"original": "retained"}
        state = {"phase": "source-stop-intent", "old_claims": claims,
                 "originals": {handoff.NATS: {"uid": "original-uid"}},
                 "source_steps": {handoff.NATS: {"delete": {"uid": "foreign"}}}}
        with patch.multiple(
            handoff, require_api_paused=Mock(), verify_retained_detached=Mock(),
            old_claims=Mock(return_value=claims), source_pods=Mock(return_value=[]),
            delete_source=Mock(), save=Mock(),
        ):
            with self.assertRaisesRegex(RuntimeError, "before its delete intent"):
                handoff.stop_sources(cluster, state, {})
            handoff.delete_source.assert_not_called()
            state["source_steps"][handoff.NATS]["delete"]["uid"] = "original-uid"
            handoff.stop_sources(cluster, state, {})
            self.assertEqual(state["phase"], "sources-stopped")
            handoff.delete_source.assert_not_called()


class HelmReconciliationTest(unittest.TestCase):
    def test_lost_helm_acknowledgment_reconciles_own_deployed_revision_without_reapplying(self):
        cluster = Mock()
        plan = {"manifest_sha256": "reviewed", "api_replicas": 0}
        state = {"phase": "sources-stopped", "plan": plan,
                 "stages": {handoff.NATS: {"name": "nats"}, handoff.QDRANT: {"name": "qdrant"}}}
        disk = {}
        installed = ({"helm_revision": 6}, {})
        pin = {"helm_revision": 5}

        def save(receipt):
            disk.update(copy.deepcopy(receipt))

        def lose_reply(*_args, **_kwargs):
            self.assertEqual(disk["phase"], "install-intent")
            self.assertTrue(disk["install-intent"]["marker"].startswith("secondary-handoff-"))
            raise TimeoutError("lost Helm reply")

        with patch.multiple(
            handoff,
            next_release_present=Mock(side_effect=[False, False, True]),
            installed_release=Mock(return_value=installed),
            save=Mock(side_effect=save),
        ), patch.dict(handoff.SHARED, {
            "release_pin": Mock(return_value=(pin, "payload")),
            "decode_release": Mock(return_value={}),
        }), patch.multiple(
            handoff.secondary_cutover,
            render_session=Mock(return_value=nullcontext((plan, ["helm", "upgrade"], {}))),
            hook_resources=Mock(return_value={}),
        ), patch.object(handoff.subprocess, "run", side_effect=lose_reply) as invoke:
            with self.assertRaisesRegex(TimeoutError, "lost Helm reply"):
                handoff.apply_upgrade(cluster, state, 5, "install-intent", plan, Mock())
            resumed = handoff.apply_upgrade(cluster, copy.deepcopy(disk), 5, "install-intent", plan, Mock())
            self.assertEqual(resumed, installed)
            invoke.assert_called_once()
            handoff.installed_release.assert_called_once_with(cluster, 6, disk["install-intent"])

    def test_foreign_or_failed_revision_is_never_reapplied(self):
        cluster = Mock()
        cluster.get.return_value = {"metadata": {"labels": {"status": "failed", handoff.HELM_MARKER_LABEL: "foreign"}},
                                    "data": {"release": "payload"}}
        intent = {"marker": "ours", "plan": {"manifest_sha256": "same", "api_replicas": 0},
                  "hooks_sha256": "same"}
        release = {"name": "omniscience", "namespace": handoff.capture.NAMESPACE, "version": 6, "manifest": "",
                   "info": {"description": "foreign", "status": "failed"}, "config": {"replicaCount": 0}}
        with patch.dict(handoff.SHARED, {"decode_release": Mock(return_value=release)}), patch.multiple(
            handoff.secondary_cutover, parse_manifest=Mock(return_value={}), normalize_postgres_annotations=Mock(),
            manifest_digest=Mock(return_value="same"), hook_resources=Mock(return_value={}),
        ):
            with self.assertRaisesRegex(RuntimeError, "foreign"):
                handoff.installed_release(cluster, 6, intent)
            cluster.get.return_value["metadata"]["labels"][handoff.HELM_MARKER_LABEL] = "ours"
            with self.assertRaisesRegex(RuntimeError, "review forward repair"):
                handoff.installed_release(cluster, 6, intent)
        cluster.kubectl.assert_not_called()


class RuntimeLayoutTest(unittest.TestCase):
    def test_runtime_layout_rejects_extra_environment_and_forged_api_volume(self):
        spec = {"volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": "retained"}}],
                "containers": [{"name": "db", "env": [{"name": "EXPECTED", "value": "yes"}]}]}
        handoff.verify_runtime_layout(copy.deepcopy(spec), spec)
        changed = copy.deepcopy(spec)
        changed["containers"][0]["env"].append({"name": "UNKNOWN", "value": "yes"})
        with self.assertRaisesRegex(RuntimeError, "environment"):
            handoff.verify_runtime_layout(changed, spec)
        changed = copy.deepcopy(spec)
        changed["volumes"].append({"name": "kube-api-access-fake", "secret": {"secretName": "foreign"}})
        with self.assertRaisesRegex(RuntimeError, "service-account volume contents"):
            handoff.verify_runtime_layout(changed, spec)


if __name__ == "__main__":
    unittest.main()
