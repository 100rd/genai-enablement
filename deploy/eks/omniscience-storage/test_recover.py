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
    CLAIM, EXPECTED_REPLICAS, IMAGE, PROBE_CODE, SOURCE, STAGE, TABLES,
    change_manifest, dump_hash, filtered_dump, normalized_schema_hash, sanitized_chart_values, validate_probe_target,
)


def dump():
    bootstrap = (
        "CREATE ROLE omniscience;\n"
        "CREATE ROLE postgres;\n"
        "ALTER ROLE postgres WITH SUPERUSER;\n"
        "CREATE DATABASE omniscience WITH TEMPLATE = template0 ENCODING = 'UTF8' "
        "LOCALE_PROVIDER = libc LOCALE = 'en_US.UTF-8';\n"
    )
    preserved = "ALTER ROLE omniscience WITH LOGIN CREATEDB;\n" + "".join(
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
        changed = data.replace(b"COPY public.alembic_version", b"COPY public.audit_log")
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

    def test_bootstrap_probe_is_only_valid_against_staging(self):
        compile(PROBE_CODE, "<probe>", "exec")
        validate_probe_target(STAGE, "bootstrap")
        validate_probe_target(STAGE, "restored")
        validate_probe_target(SOURCE, "restored")
        for host, mode in ((SOURCE, "bootstrap"), (STAGE, "invalid"), ("unrelated-db", "restored")):
            with self.subTest(host=host, mode=mode), self.assertRaisesRegex(RuntimeError, "probe target or mode"):
                validate_probe_target(host, mode)

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
        self.assertEqual(sanitized["neo4j"]["neo4j"]["password"], "")
        self.assertEqual(sanitized["qdrant"]["apiKey"], "")
        self.assertEqual(values["postgresql"]["auth"]["password"], "fake-owner-credential")
        values["extra"] = "prefix-fake-owner-credential"
        with self.assertRaisesRegex(RuntimeError, "outside reviewed defaults"):
            sanitized_chart_values(values)

    def test_reconstruction_does_not_write_coalesced_credentials(self):
        chart_values = {
            "postgresql": {"auth": {"password": "fake-owner-credential"}},
            "secrets": {"runtimeDatabaseUrl": "postgres://fake-credential"},
            "neo4j": {"neo4j": {"password": "fake-graph-credential"}},
            "qdrant": {"apiKey": "fake-vector-credential"},
        }
        release = {
            "config": {"original": "sensitive-config-value"},
            "chart": {
                "metadata": {
                    "name": "omniscience",
                    "dependencies": [{"name": "postgresql", "version": "18.12.18"}],
                },
                "values": chart_values,
                "templates": [],
            },
        }
        before = copy.deepcopy(release)
        with tempfile.TemporaryDirectory() as temporary:
            chart_dir = Path(temporary).resolve() / "chart"
            archive = b"synthetic-archive"
            dependencies = {"postgresql": ("18.12.18", "oci://example/postgresql", dump_hash(archive))}

            def pull(command, **options):
                (Path(command[-1]) / "postgresql-18.12.18.tgz").write_bytes(archive)
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(recover, "DEPENDENCIES", dependencies), patch.object(recover.subprocess, "run", side_effect=pull):
                recover.restore_chart(chart_dir, release)
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
