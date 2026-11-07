"""Local tests for the native snapshot capture gates."""

import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import capture


def topology():
    return (
        {"status": "enabled", "peer_id": 42, "peers": {"42": {}},
         "raft_info": {"pending_operations": 0}},
        {"status": "green", "config": {"params": {
            "shard_number": 1, "replication_factor": 1, "write_consistency_factor": 1,
        }}},
        {"peer_id": 42, "local_shards": [{"shard_id": 0, "state": "Active", "points_count": 7}],
         "remote_shards": [], "shard_transfers": []},
    )


def private_file(path, data=b"snapshot data"):
    path.write_bytes(data)
    path.chmod(0o600)


class TopologyTest(unittest.TestCase):
    def test_only_single_peer_holding_all_points_is_accepted(self):
        source, detail, shards = topology()
        capture.validate_qdrant_topology(source, detail, shards, 7)
        for mutate in (
            lambda s, d, t: s["peers"].update({"51": {}}),
            lambda s, d, t: s["raft_info"].update(pending_operations=1),
            lambda s, d, t: t["local_shards"][0].update(state="Dead"),
            lambda s, d, t: t["local_shards"][0].update(points_count=6),
            lambda s, d, t: t["remote_shards"].append({"shard_id": 0}),
            lambda s, d, t: t["shard_transfers"].append({"shard_id": 0}),
        ):
            changed = copy.deepcopy((source, detail, shards))
            mutate(*changed)
            with self.assertRaisesRegex(RuntimeError, "cluster|placement"):
                capture.validate_qdrant_topology(*changed, 7)

    def test_nats_inventory_refuses_active_clients_in_capture(self):
        with patch.object(capture, "nats_monitor", return_value={"version": "2.15.2", "connections": 1}):
            with self.assertRaisesRegex(RuntimeError, "active client"):
                capture.nats_inventory(Mock(), capture=True)


class SourceIdentityTest(unittest.TestCase):
    def test_replacement_pod_refused_even_with_original_claim(self):
        name, expected = next(iter(capture.SOURCES.items()))
        cluster = Mock()
        resources = {
            ("statefulset", name): {"metadata": {"uid": expected["sts_uid"]}},
            ("pod", f"{name}-0"): {
                "metadata": {"uid": "replacement", "ownerReferences": [{"controller": True, "uid": expected["sts_uid"]}]},
                "spec": {"nodeName": capture.SOURCE_NODE},
                "status": {"containerStatuses": [
                    {"name": name, "imageID": image, "ready": True} for name, image in expected["images"].items()
                ]},
            },
            ("pvc", expected["pvc"]): {},
            ("pv", expected["pv"]): {"spec": {"claimRef": {}}},
        }
        cluster.get.side_effect = lambda kind, name: resources[kind, name]
        with patch.dict(capture.SHARED, {"release_pin": Mock(return_value=({"helm_revision": 5}, ""))}):
            with self.assertRaisesRegex(RuntimeError, "pod, node or image changed"):
                capture.source_identity(cluster, capture=True)


class QdrantSnapshotTest(unittest.TestCase):
    def test_missing_empty_and_invalid_checksums_stop_before_download(self):
        for checksum in (None, "", "not-a-sha", "a" * 63):
            with tempfile.TemporaryDirectory() as temp, self.subTest(checksum=checksum):
                target = Path(temp) / "qdrant.snapshot"
                client = Mock()
                client.json.return_value = {"name": "sample.snapshot", "size": 4}
                if checksum is not None:
                    client.json.return_value["checksum"] = checksum
                with self.assertRaisesRegex(RuntimeError, "valid SHA-256"):
                    capture.snapshot_qdrant(client, target, {})
                client.request.assert_not_called()
                receipt = json.loads((target.parent / "receipt.json").read_bytes())
                self.assertEqual(receipt["status"], "incomplete")
                self.assertEqual(receipt["qdrant_snapshot"]["source_snapshot"], "sample.snapshot")

    def test_interrupted_download_preserves_incomplete_source_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "qdrant.snapshot"
            expected = hashlib.sha256(b"data").hexdigest()
            client = Mock()
            client.json.return_value = {"name": "sample.snapshot", "size": 4, "checksum": expected}

            def fail_download(*args):
                receipt = json.loads((target.parent / "receipt.json").read_bytes())
                self.assertEqual(receipt, {"status": "incomplete", "qdrant_snapshot": {
                    "source_snapshot": "sample.snapshot", "sha256": expected, "bytes": 4,
                }})
                raise TimeoutError()

            client.request.side_effect = fail_download
            with self.assertRaises(TimeoutError):
                capture.snapshot_qdrant(client, target, {})
            self.assertFalse(target.exists())
            self.assertEqual(json.loads((target.parent / "receipt.json").read_bytes())["status"], "incomplete")

    def test_mismatching_checksum_rejects_download(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "qdrant.snapshot"
            client = Mock()
            client.json.return_value = {"name": "sample.snapshot", "size": 4, "checksum": "a" * 64}
            client.request.return_value = io.BytesIO(b"data")
            with self.assertRaisesRegex(RuntimeError, "length or checksum"):
                capture.snapshot_qdrant(client, target, {})
            self.assertEqual(json.loads((target.parent / "receipt.json").read_bytes())["status"], "incomplete")


class ReceiptTest(unittest.TestCase):
    def test_incomplete_or_changed_capture_never_gets_complete_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            receipt = directory / "receipt.json"
            private_file(receipt, b'{"status":"incomplete"}')
            initial = {"source": {"pod_uid": "pinned"}, "fingerprint": "digest"}
            with self.assertRaisesRegex(RuntimeError, "changed"):
                capture.complete_receipt(directory, {}, initial, {**initial, "fingerprint": "different"})
            with self.assertRaisesRegex(RuntimeError, "changed"):
                capture.complete_receipt(directory, {}, initial, {**initial, "source": {"pod_uid": "new"}})
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                capture.complete_receipt(directory, {}, initial, initial)
            self.assertEqual(json.loads(receipt.read_bytes())["status"], "incomplete")

    def test_only_complete_private_hashed_snapshot_set_gets_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            receipt = directory / "receipt.json"
            private_file(receipt, b'{"status":"incomplete"}')
            (directory / "nats").mkdir(mode=0o700)
            for name in capture.NATS_STREAMS:
                stream = directory / "nats" / name
                stream.mkdir(mode=0o700)
                private_file(stream / "backup.json", b"{}")
                private_file(stream / "stream.tar.s2")
            snapshot = directory / "qdrant.snapshot"
            private_file(snapshot)
            snapshot.chmod(0o644)
            initial = {"source": {"pod_uid": "pinned"}, "fingerprint": "digest"}
            with self.assertRaisesRegex(RuntimeError, "not private"):
                capture.complete_receipt(directory, {}, initial, initial)
            self.assertEqual(json.loads(receipt.read_bytes())["status"], "incomplete")
            snapshot.chmod(0o600)
            with patch.object(capture.os, "fsync", side_effect=OSError("artifact sync failed")):
                with self.assertRaisesRegex(OSError, "artifact sync failed"):
                    capture.complete_receipt(directory, {}, initial, initial)
            self.assertEqual(json.loads(receipt.read_bytes())["status"], "incomplete")
            original_sync = capture.sync_directory

            def fail_complete_sync(path):
                if path == directory and json.loads(receipt.read_bytes())["status"] == "complete":
                    raise OSError("final directory sync failed")
                original_sync(path)

            with patch.object(capture, "sync_directory", side_effect=fail_complete_sync):
                with self.assertRaisesRegex(OSError, "final directory sync failed"):
                    capture.complete_receipt(directory, {}, initial, initial)
            self.assertEqual(json.loads(receipt.read_bytes())["status"], "incomplete")
            capture.complete_receipt(directory, {"started_at": "now"}, initial, initial)
            completed = json.loads(receipt.read_bytes())
            self.assertEqual(completed["status"], "complete")
            self.assertEqual(completed["source_inventory"], initial)
            self.assertEqual(len(completed["files"]), 7)
            self.assertEqual(completed["files"]["qdrant.snapshot"]["sha256"], capture.file_hash(snapshot))


if __name__ == "__main__":
    unittest.main()
