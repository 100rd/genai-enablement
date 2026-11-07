"""Pure Neo4j empty-graph and Helm transition guards."""

import copy
import hashlib
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import recover


def inventory(application=True):
    return {
        "edition": [{"versions": ["2026.10.1"], "edition": "community"}],
        "current_user": [{"user": "neo4j"}],
        "databases": [{**entry, "databaseID": digit * 64}
                      for entry, digit in zip(recover.EXPECTED_DATABASES, ("A", "B"))],
        "users": copy.deepcopy(recover.EXPECTED_USERS),
        "wrong_password_denied": True,
        **recover.expected_schema(application),
        "nodes": [{"count": 0}],
        "relationships": [{"count": 0}],
        "transactions": [{"own": 1, "other": 0}],
    }


class InventoryTest(unittest.TestCase):
    def test_empty_state_can_have_new_internal_ids(self):
        original = inventory()
        restored = inventory()
        restored["databases"][0]["databaseID"] = "C" * 64
        recover.validate_inventory(original)
        recover.validate_inventory(restored)
        self.assertNotEqual(original, restored)
        self.assertEqual(recover.logical_state(original), recover.logical_state(restored))

    def test_graph_data_and_extra_constraints_block_recreation(self):
        for field in ("nodes", "relationships"):
            with self.subTest(field=field):
                observed = inventory()
                observed[field][0]["count"] = 1
                with self.assertRaisesRegex(RuntimeError, "graph data"):
                    recover.validate_inventory(observed)
        observed = inventory()
        observed["constraints"].append({"name": "extra"})
        with self.assertRaisesRegex(RuntimeError, "constraints"):
            recover.validate_inventory(observed)

    def test_custom_user_index_and_database_block_recreation(self):
        for field, key, value, reason in (
            ("users", "user", "custom", "authorization"),
            ("indexes", "type", "TEXT", "indexes"),
            ("databases", "name", "other", "databases"),
        ):
            with self.subTest(field=field):
                observed = inventory()
                observed[field][0][key] = value
                with self.assertRaisesRegex(RuntimeError, reason):
                    recover.validate_inventory(observed)

    def test_tokens_aliases_and_wrong_password_acceptance_block_recreation(self):
        for field in ("labels", "relationship_types", "property_keys"):
            with self.subTest(field=field):
                observed = inventory()
                observed[field].append("unknown_token")
                with self.assertRaisesRegex(RuntimeError, "token names"):
                    recover.validate_inventory(observed)
        observed = inventory()
        observed["databases"][0]["aliases"] = ["custom-alias"]
        with self.assertRaisesRegex(RuntimeError, "databases"):
            recover.validate_inventory(observed)
        observed = inventory()
        observed["wrong_password_denied"] = False
        with self.assertRaisesRegex(RuntimeError, "wrong password"):
            recover.validate_inventory(observed)

    def test_other_transactions_allowed_only_for_bootstrap(self):
        observed = inventory()
        observed["transactions"][0]["other"] = 1
        recover.validate_inventory(observed, quiesced=False)
        with self.assertRaisesRegex(RuntimeError, "another open transaction"):
            recover.validate_inventory(observed)

    def test_probe_syntax(self):
        compile(recover.PROBE_CODE, "<probe>", "exec")


class StageSchemaTest(unittest.TestCase):
    def test_pristine_and_application_catalogs_are_distinct_and_exact(self):
        pristine = inventory(application=False)
        prepared = inventory()
        recover.validate_inventory(pristine, application=False)
        recover.validate_inventory(prepared)
        self.assertEqual(len(prepared["indexes"]), 14)
        self.assertEqual(len(prepared["constraints"]), 4)
        self.assertEqual(len(prepared["labels"]), 4)
        self.assertEqual(len(prepared["property_keys"]), 10)
        for data, application in ((pristine, True), (prepared, False)):
            with self.assertRaisesRegex(RuntimeError, "reviewed definitions"):
                recover.validate_inventory(data, application=application)
        unexpected = copy.deepcopy(prepared)
        unexpected["indexes"].append({"name": "unknown_index"})
        with self.assertRaisesRegex(RuntimeError, "reviewed definitions"):
            recover.validate_inventory(unexpected)

    def test_reviewed_file_contains_only_exact_allowlisted_schema(self):
        ddl = (recover.HERE / "application-schema.cypher").read_text()
        self.assertEqual(ddl, recover.reviewed_ddl())
        self.assertEqual(ddl.count("CREATE INDEX "), 8)
        self.assertEqual(ddl.count("CREATE CONSTRAINT "), 4)

    def test_schema_preparation_sends_fixed_ddl_only_to_staging(self):
        cluster = Mock()
        cluster.get.return_value = {"spec": {"replicas": 1}}
        source = inventory()
        candidate = inventory()
        candidate["databases"][0]["databaseID"] = "C" * 64
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            with patch.multiple(
                recover, BOOTSTRAP=path / "bootstrap.json", CAPTURE=path / "capture.json",
                wait_stage=Mock(), source_identity=Mock(return_value={"source": "uid"}),
                staged_identity=Mock(return_value={"stage": "uid"}),
                probe=Mock(side_effect=[source, inventory(False), candidate, source]),
                write_private_json=Mock(),
            ):
                recover.prepare_stage_schema(cluster)
            args, kwargs = cluster.kubectl.call_args
            self.assertEqual(args[:3], ("exec", "-i", recover.STAGE))
            self.assertEqual(kwargs["input"], recover.reviewed_ddl() + "CALL db.awaitIndexes(120);\n")

    def test_quiesced_catalog_mismatch_blocks_cutover(self):
        captured = {"source": {"source": "uid"}, "stage": {"volume": {"volume": "uid"}},
                    "source_inventory": inventory()}
        current = copy.deepcopy(captured["source_inventory"])
        current["indexes"][0]["properties"] = ["unexpected"]
        cluster = Mock()
        cluster.absent.return_value = True
        with patch.multiple(
            recover, pause_check=Mock(), read_private_json=Mock(return_value=captured),
            source_identity=Mock(return_value=captured["source"]),
            volume_identity=Mock(return_value=captured["stage"]["volume"]),
            consumers=Mock(return_value=[]), verify_policies=Mock(), probe=Mock(return_value=current),
        ):
            with self.assertRaisesRegex(RuntimeError, "Quiesced Neo4j source state changed"):
                recover.verify_cutover(cluster)


class ReplacementRecoveryTest(unittest.TestCase):
    def test_replacement_requires_same_release_and_post_capture_pod(self):
        previous = {
            "helm_revision": 3, "statefulset_uid": "same-sts", "pod_uid": "old-pod",
            "container_id": "old-container", "protected_stores": {},
        }
        current = {**previous, "pod_uid": "new-pod", "container_id": "new-container"}
        capture = {"source": previous, "stage": {"volume": {"id": "retained"}}}
        cluster = Mock()
        meta = {"uid": "new-pod", "creationTimestamp": "2030-01-01T00:00:00Z",
                "annotations": {"karpenter.sh/do-not-disrupt": "true"}}
        cluster.get.return_value = {"metadata": meta}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "capture.json"
            path.write_text("{}")
            with patch.multiple(
                recover, CAPTURE=path, pause_check=Mock(), read_private_json=Mock(return_value=capture),
                source_identity=Mock(return_value=current), verify_replacement_pg=Mock(), verify_policies=Mock(),
                volume_identity=Mock(return_value=capture["stage"]["volume"]),
            ):
                self.assertEqual(recover.replacement_source(cluster, capture), current)
                current["helm_revision"] = 4
                with self.assertRaisesRegex(RuntimeError, "StatefulSet or Helm"):
                    recover.replacement_source(cluster, capture)
                current["helm_revision"] = 3
                meta["creationTimestamp"] = "2020-01-01T00:00:00Z"
                with self.assertRaisesRegex(RuntimeError, "after the quiesced capture"):
                    recover.replacement_source(cluster, capture)

    def test_other_protected_store_replacement_is_rejected(self):
        original = {
            "omniscience-postgres": {"pod_uid": "old-pg", "claims": {"pg": "same"}},
            "omniscience-nats": {"pod_uid": "old-nats", "claims": {"nats": "same"}},
        }
        current = copy.deepcopy(original)
        current["omniscience-postgres"]["pod_uid"] = "new-pg"
        current["omniscience-nats"]["pod_uid"] = "new-nats"
        with self.assertRaisesRegex(RuntimeError, "NATS or Qdrant"):
            recover.verify_replacement_pg(Mock(), original, current)
        current["omniscience-nats"]["pod_uid"] = "old-nats"
        current["omniscience-postgres"]["claims"]["pg"] = "other"
        with self.assertRaisesRegex(RuntimeError, "claim identity"):
            recover.verify_replacement_pg(Mock(), original, current)

    def test_recovery_cutover_requires_distinct_matching_shutdown_receipt(self):
        cluster = Mock()
        cluster.absent.return_value = True
        capture = {"source": "original"}
        reopened = {"replacement": {"source": "new"}, "stage": "verified"}
        with patch.multiple(
            recover, consumers=Mock(return_value=[]),
            read_private_json=Mock(side_effect=[capture, reopened, {"stage": "different"}]),
        ):
            with self.assertRaisesRegex(RuntimeError, "stage shutdown"):
                recover.verify_recovery_cutover(cluster)


class RecoveryIntentTest(unittest.TestCase):
    def test_create_retry_recovers_owned_service_after_interrupted_create(self):
        intent = {"token": "unique-token", "resources": {}}
        manifest = {"kind": "Service", "metadata": {"name": recover.STAGE}}
        cluster = Mock()
        cluster.absent.return_value = True
        cluster.kubectl.side_effect = TimeoutError
        with patch.object(recover, "write_private_json") as save:
            with self.assertRaises(TimeoutError):
                recover.ensure_recovery_resource(cluster, manifest, intent)
            self.assertEqual(intent["resources"], {})
            cluster.absent.return_value = False
            cluster.get.return_value = {"metadata": {
                "uid": "owned-service", "labels": {recover.RECOVERY_LABEL: intent["token"]},
            }}
            recover.ensure_recovery_resource(cluster, manifest, intent)
            self.assertEqual(cluster.kubectl.call_count, 1)
            self.assertEqual(intent["resources"], {"service": "owned-service"})
            save.assert_called_once()
            cluster.get.return_value["metadata"]["uid"] = "another-service"
            with self.assertRaisesRegex(RuntimeError, "UID changed"):
                recover.ensure_recovery_resource(cluster, manifest, intent)

    def test_stage_wait_failure_reuses_intent_and_owned_objects(self):
        replacement = {"source": "replacement"}
        volume = {"name": "retained"}
        captured = {"stage": {"volume": volume}, "stage_inventory": "verified"}
        stage = {"volume": volume, "resources": {"pod": "owned-pod", "service": "owned-service"}}
        pod_manifest = {"kind": "Pod", "metadata": {"name": recover.STAGE}}
        cluster = Mock()
        cluster.absent.return_value = True

        def own(_cluster, manifest, intent):
            kind = manifest["kind"].lower()
            intent["resources"].setdefault(kind, f"owned-{kind}")
            recover.write_private_json(recover.RECOVERY_CREATE_INTENT, intent)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            capture = root / "capture.json"
            create = root / "create.json"
            stage_verified = root / "verified.json"
            recover.write_private_json(capture, captured)
            with patch.multiple(
                recover, CAPTURE=capture, RECOVERY_CREATE_INTENT=create, RECOVERY_STAGE=stage_verified,
                RECOVERY_STOP=root / "stopped.json", RECOVERY_LIVE=root / "live.json",
                consumers=Mock(return_value=[]), verified_replacement=Mock(return_value=replacement),
                staged_pod_manifest=Mock(return_value=pod_manifest),
                ensure_recovery_resource=Mock(side_effect=own), wait_stage=Mock(side_effect=[TimeoutError, None]),
                staged_identity=Mock(return_value=stage), probe=Mock(return_value="verified"),
            ):
                with self.assertRaises(TimeoutError):
                    recover.recover_stage(cluster)
                intent = recover.read_private_json(create)
                self.assertEqual(intent["resources"], stage["resources"])
                self.assertFalse(stage_verified.exists())
                recover.recover_stage(cluster)
                self.assertEqual(recover.read_private_json(create), intent)
                self.assertEqual(recover.read_private_json(stage_verified)["stage"], stage)

    def test_create_retry_does_not_adopt_foreign_resource(self):
        cluster = Mock()
        cluster.absent.return_value = False
        cluster.get.return_value = {"metadata": {"uid": "foreign", "labels": {}}}
        intent = {"token": "unique-token", "resources": {}}
        manifest = {"kind": "Pod", "metadata": {"name": recover.STAGE}}
        with self.assertRaisesRegex(RuntimeError, "foreign"):
            recover.ensure_recovery_resource(cluster, manifest, intent)
        cluster.kubectl.assert_not_called()

    def test_delete_is_uid_guarded_and_absence_is_resumable(self):
        cluster = Mock()
        cluster.absent.return_value = False
        cluster.get.return_value = {"metadata": {"uid": "foreign"}}
        with patch.object(recover, "delete_owned") as delete:
            with self.assertRaisesRegex(RuntimeError, "UID changed"):
                recover.delete_recovery_resource(cluster, "service", "owned")
            delete.assert_not_called()
            cluster.absent.return_value = True
            recover.delete_recovery_resource(cluster, "pod", "already-deleted")
            delete.assert_not_called()

    def test_shutdown_retries_service_after_pod_already_deleted(self):
        capture = {"stage_inventory": "verified-catalog"}
        replacement = {"source": "new"}
        stage = {"resources": {"pod": "stage-pod", "service": "stage-service"}}
        recovery = {"replacement": replacement, "stage": stage}
        objects = {"pod": "stage-pod", "service": "stage-service"}
        cluster = Mock()
        cluster.absent.side_effect = lambda kind, name: kind not in objects
        cluster.get.side_effect = lambda kind, name: {"metadata": {"uid": objects[kind]}}
        attempts = []

        def delete(_cluster, route, uid):
            kind = "pod" if "/pods/" in route else "service"
            attempts.append((kind, uid))
            if kind == "service" and len(attempts) == 2:
                raise TimeoutError
            del objects[kind]

        with tempfile.TemporaryDirectory() as temp:
            intent = Path(temp) / "stop-intent.json"
            stop = Path(temp) / "stopped.json"
            with patch.multiple(
                recover, RECOVERY_STOP_INTENT=intent, RECOVERY_STOP=stop,
                read_private_json=Mock(side_effect=lambda path: capture if path == recover.CAPTURE else recovery),
                verified_replacement=Mock(return_value=replacement), staged_identity=Mock(return_value=stage),
                probe=Mock(return_value="verified-catalog"), resources=Mock(return_value=stage["resources"]),
                consumers=Mock(side_effect=lambda _cluster: [objects["pod"]] if "pod" in objects else []),
                delete_owned=Mock(side_effect=delete),
            ):
                with self.assertRaises(TimeoutError):
                    recover.stop_recovery_stage(cluster)
                self.assertTrue(intent.is_file())
                self.assertFalse(stop.exists())
                self.assertNotIn("pod", objects)
                recover.stop_recovery_stage(cluster)
                self.assertTrue(stop.is_file())
                self.assertEqual(attempts, [("pod", "stage-pod"), ("service", "stage-service"),
                                            ("service", "stage-service")])


class DirectoryGuardTest(unittest.TestCase):
    def test_refuses_custom_content_in_each_guarded_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "neo4j-home"
            for folder in ("import", "backups", "licenses", "data", "data/dumps", "plugins",
                           "neo4j-home/conf", "neo4j-home/plugins"):
                (root / folder).mkdir(parents=True)
            readme = b"synthetic stock readme"
            (home / "plugins/README.txt").write_bytes(readme)
            paths = {"/var/lib/neo4j": str(home)}
            paths.update({f"/{name}": str(root / name) for name in ("import", "backups", "licenses", "data", "plugins")})
            pattern = "|".join(re.escape(path) for path in sorted(paths, key=len, reverse=True))
            script = re.sub(pattern, lambda match: paths[match.group()], recover.DIRECTORY_CHECK)
            # The Neo4j home plugin directory is relative to NEO4J_HOME, even inside this fixture.
            script = script.replace(f'$NEO4J_HOME{root / "plugins"}', '$NEO4J_HOME/plugins')
            script = script.replace("44ffadeb14a99af475dea24eca6049b587f0e08a07b211ea28886f38a16dc0e7",
                                    hashlib.sha256(readme).hexdigest())
            (home / "conf/neo4j.conf").write_text(f"server.directories.import={root / 'import'}\n")

            def validate():
                return subprocess.run(
                    ["sh", "-ec", script], env={**os.environ, "NEO4J_HOME": str(home)},
                    capture_output=True, text=True,
                )

            self.assertEqual(validate().stdout, "standard-empty-layout")
            for folder in ("import", "backups", "licenses", "data/dumps", "plugins", "neo4j-home/plugins"):
                with self.subTest(folder=folder):
                    custom = root / folder / "custom.fixture"
                    custom.write_text("unexpected")
                    self.assertNotEqual(validate().returncode, 0)
                    custom.unlink()
            (home / "conf/neo4j.conf").write_text("server.directories.import=/custom-location\n")
            self.assertNotEqual(validate().returncode, 0)


class ManifestTest(unittest.TestCase):
    def test_normalizes_only_expected_neo4j_null_empty_dir(self):
        claim = {"claimName": recover.CLAIM}
        volumes = [
            {"name": "data", "emptyDir": None, "persistentVolumeClaim": claim},
            {"name": "other", "emptyDir": None, "persistentVolumeClaim": claim},
        ]
        manifest = {("StatefulSet", recover.SOURCE): {"spec": {"template": {"spec": {"volumes": volumes}}}}}
        recover.normalize_neo4j_volume_null(manifest)
        self.assertEqual(volumes[0], {"name": "data", "persistentVolumeClaim": claim})
        self.assertIn("emptyDir", volumes[1])
        for volume in (
            {"name": "data", "emptyDir": {}, "persistentVolumeClaim": claim},
            {"name": "data", "emptyDir": None, "persistentVolumeClaim": {"claimName": "wrong"}},
            {"name": "data", "emptyDir": None, "persistentVolumeClaim": claim, "hostPath": {"path": "/tmp"}},
        ):
            with self.subTest(volume=volume):
                volumes[0] = copy.deepcopy(volume)
                recover.normalize_neo4j_volume_null(manifest)
                self.assertEqual(volumes[0], volume)

    def test_preserves_other_stores_and_restores_api_replica(self):
        manifest = {
            ("Deployment", "omniscience-api"): {"spec": {"replicas": 1}},
            ("StatefulSet", recover.SOURCE): {"spec": {"template": {"spec": {
                "containers": [{"image": "original"}], "volumes": [{"name": "data", "emptyDir": {}}],
            }}}},
        }
        protected = {
            ("StatefulSet", "omniscience-postgres"): {"spec": {"protected": True}},
            ("StatefulSet", "omniscience-nats"): {"spec": {"protected": True}},
            ("StatefulSet", "omniscience-qdrant"): {"spec": {"protected": True}},
        }
        manifest.update(copy.deepcopy(protected))
        recover.change_manifest(manifest, resume=False)
        self.assertEqual(manifest[("Deployment", "omniscience-api")]["spec"]["replicas"], 0)
        recover.change_manifest(manifest, resume=True)
        self.assertEqual(manifest[("Deployment", "omniscience-api")]["spec"]["replicas"], 1)
        self.assertEqual({key: manifest[key] for key in protected}, protected)


if __name__ == "__main__":
    unittest.main()
