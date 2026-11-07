"""Local guards. No Kubernetes calls or production SQL fixtures."""

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import recover

from recover import (
    CLAIM, EXPECTED_REPLICAS, IMAGE, REPLICA_NEW, REPLICA_OLD, SOURCE, TABLES,
    WORKER_NEW, WORKER_OLD, change_manifest, dump_hash, filtered_dump, normalized_schema_hash, sanitized_chart_values,
    worker_template,
)


def dump():
    bootstrap = (
        "CREATE ROLE barbarossa_observe;\n"
        "CREATE ROLE postgres;\n"
        "ALTER ROLE postgres WITH SUPERUSER;\n"
        "CREATE DATABASE barbarossa_observe WITH TEMPLATE = template0 ENCODING = 'UTF8' "
        "LOCALE_PROVIDER = libc LOCALE = 'en_US.UTF-8';\n"
    )
    preserved = "ALTER ROLE barbarossa_observe WITH LOGIN CREATEDB;\n" + "".join(
        f"COPY public.{table} (id) FROM stdin;\n1\n\\.\n" for table in sorted(TABLES)
    )
    return bootstrap.encode() + preserved.encode(), preserved


class RestoreFilterTest(unittest.TestCase):
    def test_removes_only_duplicate_bootstrap(self):
        data, expected = dump()
        self.assertEqual(filtered_dump(data, dump_hash(data)), expected)

    def test_refuses_modified_backup(self):
        data, _ = dump()
        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            filtered_dump(data + b"\n", dump_hash(data))

    def test_refuses_duplicate_or_missing_table_section(self):
        data, _ = dump()
        changed = data.replace(b"COPY public.schema_migrations", b"COPY public.local_observe_jobs")
        with self.assertRaisesRegex(RuntimeError, "table data sections"):
            filtered_dump(changed, dump_hash(changed))

    def test_refuses_extra_role_and_unexpected_database(self):
        data, _ = dump()
        for statement, expected in ((b'CREATE ROLE "extra";\n', "role definitions"),
                                    (b"CREATE DATABASE extra WITH TEMPLATE = template0;\n", "database definitions")):
            changed = data + statement
            with self.subTest(statement=statement), self.assertRaisesRegex(RuntimeError, expected):
                filtered_dump(changed, dump_hash(changed))

    def test_refuses_missing_admin_role_bootstrap(self):
        data, _ = dump()
        changed = data.replace(b"ALTER ROLE postgres WITH SUPERUSER;\n", b"")
        with self.assertRaisesRegex(RuntimeError, "matching bootstrap statement"):
            filtered_dump(changed, dump_hash(changed))


class CutoverGuardTest(unittest.TestCase):
    def test_schema_hash_ignores_only_restriction_tokens(self):
        first = b"\\restrict token1\nCREATE TABLE t();\n\\unrestrict token1\n"
        second = first.replace(b"token1", b"token2")
        self.assertEqual(normalized_schema_hash(first), normalized_schema_hash(second))
        self.assertNotEqual(normalized_schema_hash(first), normalized_schema_hash(first.replace(b"t()", b"u()")))

    def test_worker_template_requires_exact_guard_and_replica(self):
        original = WORKER_OLD + b"spec:\n" + REPLICA_OLD
        patched = WORKER_NEW + b"spec:\n" + REPLICA_NEW
        self.assertEqual(worker_template(original, resume=False), patched)
        self.assertEqual(worker_template(patched, resume=True), patched)
        with self.assertRaisesRegex(RuntimeError, "maintenance change"):
            worker_template(original, resume=True)
        with self.assertRaisesRegex(RuntimeError, "single-observer baseline"):
            worker_template(original + REPLICA_OLD, resume=False)

    def test_manifest_pause_and_resume_preserve_storage(self):
        expected = {("Deployment", name): {"spec": {"replicas": replicas}}
                    for name, replicas in EXPECTED_REPLICAS.items()}
        pod = {"containers": [{"image": "old"}], "volumes": [{"name": "data", "emptyDir": {}}]}
        expected[("StatefulSet", SOURCE)] = {"spec": {"template": {"spec": pod}}}
        change_manifest(expected, resume=False)
        self.assertTrue(all(expected[("Deployment", name)]["spec"]["replicas"] == 0 for name in EXPECTED_REPLICAS))
        self.assertEqual(pod["volumes"][0]["persistentVolumeClaim"]["claimName"], CLAIM)
        self.assertEqual(pod["containers"][0]["image"], IMAGE)
        change_manifest(expected, resume=True)
        self.assertTrue(all(expected[("Deployment", name)]["spec"]["replicas"] == 1 for name in EXPECTED_REPLICAS))
        self.assertEqual(pod["volumes"][0]["persistentVolumeClaim"]["claimName"], CLAIM)

    def test_chart_resume_redacts_coalesced_defaults_without_changing_source(self):
        values = {
            "postgresql": {"auth": {"password": "fake-owner-credential", "username": "owner"}},
            "secrets": {"runtimeDatabaseUrl": "postgres://fake-credential"},
            "neo4j": {"neo4j": {"password": "fake-graph-credential"}},
            "qdrant": {"apiKey": "fake-vector-credential"},
            "replicaCount": 0,
        }
        sanitized = sanitized_chart_values(values)
        self.assertEqual(sanitized["postgresql"]["auth"], {"password": "", "username": "owner"})
        self.assertEqual(sanitized["secrets"]["runtimeDatabaseUrl"], "")
        self.assertEqual(sanitized["replicaCount"], 0)
        self.assertEqual(values["postgresql"]["auth"]["password"], "fake-owner-credential")
        values["extra"] = "prefix-fake-owner-credential"
        with self.assertRaisesRegex(RuntimeError, "outside reviewed defaults"):
            sanitized_chart_values(values)

    def test_reconstruction_does_not_write_coalesced_credentials(self):
        chart_values = {
            "postgresql": {"auth": {"password": "fake-owner-credential"}},
            "secrets": {"runtimeDatabaseUrl": "postgres://fake-credential"},
        }
        release = {
            "config": {"original": "sensitive-config-value"},
            "chart": {
                "metadata": {
                    "name": "barbarossa",
                    "dependencies": [{"name": "postgresql", "version": "18.12.18"}],
                },
                "values": chart_values,
                "templates": [],
            },
        }
        before = copy.deepcopy(release)
        with tempfile.TemporaryDirectory() as temporary:
            chart_dir = Path(temporary).resolve() / "chart"
            pulled = subprocess.CompletedProcess([], 0, "", "sha256:5096e4ceed6e1a746be3abd50e4cd71392a7fc2b38e63d35504a905f99ae5e21")
            with patch.object(recover.subprocess, "run", return_value=pulled):
                recover.restore_chart(chart_dir, release, resume=True)
            files = [path.read_bytes() for path in chart_dir.rglob("*") if path.is_file()]
            for secret in (b"fake-owner-credential", b"fake-credential", b"fake-graph-credential",
                           b"fake-vector-credential", b"sensitive-config-value"):
                self.assertFalse(any(secret in data for data in files))
            self.assertEqual(json.loads((chart_dir / "values.yaml").read_bytes())["secrets"]["runtimeDatabaseUrl"], "")
        self.assertEqual(release, before)

    def test_refuses_unexpected_replica_baseline(self):
        expected = {("Deployment", name): {"spec": {"replicas": 2}} for name in EXPECTED_REPLICAS}
        with self.assertRaisesRegex(RuntimeError, "replica count differs"):
            change_manifest(expected, resume=False)


if __name__ == "__main__":
    unittest.main()
