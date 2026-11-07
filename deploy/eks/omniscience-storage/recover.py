#!/usr/bin/env python3
"""Omniscience recovery commands for the verified nonprod-euc1 EKS context."""

import argparse
import base64
import copy
import gzip
import hashlib
import json
import os
import re
import runpy
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIVATE = HERE.parents[2] / ".local-observe"
HELPER = PRIVATE / "eks-verification/aws_context.py"
RECEIPT = PRIVATE / "frankfurt-activation/omniscience-postgres-stage-verified.json"
RESTORE_RECEIPT = PRIVATE / "frankfurt-activation/omniscience-postgres-stage-restored.json"
NAMESPACE = "splatform"
CLAIM = "omniscience-postgres-data-retained"
STAGE = "omniscience-postgres-restore"
PROBE_EGRESS = "omniscience-storage-probe-egress"
BOOTSTRAP_RECEIPT = PRIVATE / "frankfurt-activation/omniscience-postgres-stage-bootstrap.json"
DIGEST = "sha256:b418fd5f001c272aad93ac1febf783f543ee45d8e359d58bd5afc3d2a9b62290"
IMAGE = f"registry-1.docker.io/bitnami/postgresql@{DIGEST}"
SOURCE = "omniscience-postgres"
DATABASE = "omniscience"
EXPECTED_ALEMBIC = "0015"
WRITERS = ("omniscience-api",)
CAPTURE = PRIVATE / "frankfurt-activation/omniscience-storage-current"
DUMP = CAPTURE / "omniscience-postgres.sql"
CAPTURE_RECEIPT = CAPTURE / "capture.json"
STOPPED_RECEIPT = CAPTURE / "stage-stopped.json"
LIVE_RECEIPT = CAPTURE / "live-verified.json"
EXPECTED_ARN = "arn:aws:eks:eu-central-1:120736097561:cluster/nonprod-euc1"
EXPECTED_REPLICAS = {"omniscience-api": 1}

PROBE_IMAGE = (
    "120736097561.dkr.ecr.eu-central-1.amazonaws.com/genai-enablement/portal-backend"
    "@sha256:e1e0a3d9e65ca6b4d0999c7de549dc2a3dde7ff0ea2a4ab8d3f94f211ab80e09"
)
TABLES = {
    "alembic_version", "api_tokens", "audit_log", "chunks", "documents", "edges",
    "entities", "entity_emitter", "ingestion_runs", "outbox_events", "sources", "workspaces",
}
DEPENDENCIES = {
    "postgresql": (
        "18.12.18", "oci://registry-1.docker.io/bitnamicharts/postgresql",
        "ea56d67d7e265d8ca1fe9b9746fd54e77a3224f14ed534d9115535154bf078e3",
    ),
    "nats": (
        "2.15.2", "https://nats-io.github.io/k8s/helm/charts/",
        "a7e829a5cfa06591b02534ee76e2acaaab8fd0bfd2e8a4785629e8df5a6b8427",
    ),
    "neo4j": (
        "2026.10.1", "https://helm.neo4j.com/neo4j",
        "bfc4747a685aed5ae79531457e80831326f25c5422896dbeeb66fdcc501d7243",
    ),
    "qdrant": (
        "1.20.0", "https://qdrant.github.io/qdrant-helm",
        "dbd9a79e4d00e9d4fc117aa0a568b53ccf07f13dd8d26ac858b76fa14eb36bac",
    ),
}
EXPECTED_HOOKS = [
    ("omniscience-qdrant-test-db-interaction", "ConfigMap", ["test"]),
    ("omniscience-qdrant-test-db-interaction", "Pod", ["test"]),
    ("omniscience-api-bootstrap", "Job", ["post-install", "post-upgrade"]),
]
DUPLICATE_DDL = (
    r"CREATE ROLE omniscience;",
    r"CREATE ROLE postgres;",
    r"ALTER ROLE postgres WITH [^\n]+;",
    r"CREATE DATABASE omniscience WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'en_US\.UTF-8';",
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def dump_hash(data):
    return hashlib.sha256(data).hexdigest()


def filtered_dump(data, expected_sha256):
    require(dump_hash(data) == expected_sha256, "Backup SHA-256 mismatch")
    sql = data.decode("utf-8")
    require(re.findall(r"^CREATE ROLE (.+);$", sql, re.MULTILINE)
            == ["omniscience", "postgres"], "Unexpected role definitions in dump")
    require(re.findall(r"^CREATE DATABASE (\S+) ", sql, re.MULTILINE)
            == [DATABASE], "Unexpected database definitions in dump")
    require(sorted(re.findall(r"^COPY public\.([a-z_]+) ", sql, re.MULTILINE)) == sorted(TABLES),
            "Unexpected table data sections in dump")
    for pattern in DUPLICATE_DDL:
        sql, count = re.subn(rf"^{pattern}\n", "", sql, flags=re.MULTILINE)
        require(count == 1, "Expected exactly one matching bootstrap statement")
    return sql


class Cluster:
    def __init__(self):
        self.helper = runpy.run_path(str(HELPER))
        self.env = self.helper["environment"]()
        self.config = validated_context(self)


    def kubectl(self, *args, input=None):
        with tempfile.TemporaryDirectory(prefix="omniscience-kube-", dir=PRIVATE) as directory:
            env = helm_context(self, Path(directory) / "kubeconfig")
            return subprocess.run(
                ["kubectl", "--context", self.helper["CONTEXT"], "-n", NAMESPACE, *args],
                env=env, input=input, capture_output=True, text=True, check=True,
            ).stdout

    def get(self, resource, name):
        return json.loads(self.kubectl("get", resource, name, "-o", "json"))

    def absent(self, resource, name):
        return not self.kubectl("get", resource, name, "--ignore-not-found", "-o", "name").strip()

    def psql(self, pod, database, sql):
        return self.kubectl(
            "exec", "-i", pod, "--", "sh", "-ec",
            'export PGPASSWORD="$(cat "$POSTGRES_POSTGRES_PASSWORD_FILE")"; '
            'exec psql -XqAt -v ON_ERROR_STOP=1 -U postgres -d "$1"',
            "psql", database, input=sql,
        ).strip()


def stage(cluster):
    for resource, name in (
        ("pvc", CLAIM), ("service", STAGE), ("pod", STAGE),
        ("networkpolicy", f"{STAGE}-probe"), ("networkpolicy", PROBE_EGRESS),
    ):
        require(cluster.absent(resource, name), f"Staging {resource} {name} already exists")
    require(not any(path.exists() for path in (RECEIPT, RESTORE_RECEIPT, BOOTSTRAP_RECEIPT)),
            "Previous staging receipt exists")
    storage = cluster.get("storageclass", "splatform-gp3")
    require(storage["provisioner"] == "ebs.csi.aws.com"
            and storage["reclaimPolicy"] == "Retain"
            and storage["volumeBindingMode"] == "WaitForFirstConsumer"
            and storage["parameters"].get("encrypted") == "true",
            "Unexpected staging StorageClass")
    source_identity(cluster)
    sts = cluster.get("statefulset", SOURCE)
    template = sts["spec"]["template"]
    spec = template["spec"]
    require(len(spec["containers"]) == 1 and not spec.get("initContainers"),
            "Unexpected PostgreSQL workload shape")
    container = spec["containers"][0]
    require(container["name"] == "postgresql", "Unexpected PostgreSQL container")
    container["image"] = IMAGE
    volumes = [volume for volume in spec["volumes"] if volume["name"] == "data"]
    require(volumes == [{"name": "data", "emptyDir": {}}], "Expected old data emptyDir")
    volumes[0].pop("emptyDir")
    volumes[0]["persistentVolumeClaim"] = {"claimName": CLAIM}
    spec["restartPolicy"] = "Never"
    labels = template["metadata"]["labels"]
    labels["app.kubernetes.io/instance"] = STAGE
    selector = cluster.get("service", SOURCE)["spec"]["selector"]
    require(bool(selector) and not all(labels.get(key) == value for key, value in selector.items()),
            "Original PostgreSQL Service would select the staging pod")
    verify_endpoint(cluster, SOURCE, cluster.get("pod", f"{SOURCE}-0")["metadata"]["uid"])
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": STAGE, "namespace": NAMESPACE, "labels": labels},
        "spec": spec,
    }
    cluster.kubectl("create", "-f", str(HERE / "staging.yaml"), "-f", str(HERE / "probe-egress.yaml"))
    cluster.kubectl("create", "-f", "-", input=json.dumps(pod))


def verify_staging_target(cluster):
    pod = cluster.get("pod", STAGE)
    spec = pod["spec"]
    labels = {"app.kubernetes.io/instance": STAGE, "app.kubernetes.io/name": "postgresql"}
    require(all(pod["metadata"]["labels"].get(key) == value for key, value in labels.items()),
            "Staging pod labels differ")
    require(spec["containers"][0]["image"] == IMAGE
            and any(v.get("persistentVolumeClaim") == {"claimName": CLAIM}
                    for v in spec["volumes"] if v["name"] == "data"),
            "Staging pod image or PVC differs")
    require(cluster.get("service", STAGE)["spec"]["selector"] == labels,
            "Staging Service selector differs")
    original_selector = cluster.get("service", SOURCE)["spec"]["selector"]
    require(not all(pod["metadata"]["labels"].get(key) == value for key, value in original_selector.items()),
            "Original PostgreSQL Service selects the staging pod")
    source = cluster.get("pod", f"{SOURCE}-0")
    verify_endpoint(cluster, SOURCE, source["metadata"]["uid"])
    pod_uid = pod["metadata"]["uid"]
    verify_endpoint(cluster, STAGE, pod_uid)
    require(pvc_consumers(cluster) == [pod_uid], "Another pod references the staged PVC")
    return pod_uid


def verify_endpoint(cluster, service, pod_uid):
    slices = json.loads(cluster.kubectl(
        "get", "endpointslices", "-l", f"kubernetes.io/service-name={service}", "-o", "json",
    ))
    endpoints = [ep for item in slices["items"] for ep in item["endpoints"]]
    require(bool(endpoints) and all(
        ep.get("targetRef", {}).get("uid") == pod_uid
        and ep.get("conditions", {}).get("ready") is True
        for ep in endpoints
    ), "PostgreSQL Service must target only the expected ready pod")


def pvc_consumers(cluster):
    pods = json.loads(cluster.kubectl("get", "pods", "-o", "json"))["items"]
    return [
        pod["metadata"]["uid"] for pod in pods
        if any(v.get("persistentVolumeClaim", {}).get("claimName") == CLAIM
               for v in pod["spec"].get("volumes", []))
    ]


def paused(cluster, check_source_clients=True):
    pods = json.loads(cluster.kubectl("get", "pods", "-o", "json"))["items"]
    for writer in WRITERS:
        deployment = cluster.get("deployment", writer)
        selector = deployment["spec"]["selector"]["matchLabels"]
        require(deployment["spec"]["replicas"] == 0 and not any(
            all(pod["metadata"].get("labels", {}).get(key) == value for key, value in selector.items())
            for pod in pods
        ), f"Scale {writer} to zero and wait for its pods to terminate")
    jobs = json.loads(cluster.kubectl("get", "jobs", "-o", "json"))["items"]
    require(not any(j["metadata"]["name"].startswith("omniscience-") and j["status"].get("active", 0)
                    for j in jobs), "A Omniscience Job is still active")
    if not check_source_clients:
        return
    require(cluster.psql(f"{SOURCE}-0", DATABASE, """
        SELECT NOT EXISTS (
            SELECT FROM pg_stat_activity
            WHERE datname = current_database() AND backend_type = 'client backend'
              AND pid <> pg_backend_pid()
        );
    """) == "t", "A client remains connected to the source database")


def release_pin(cluster, revision):
    revisions = cluster.kubectl(
        "get", "secret", "-l", "owner=helm,name=omniscience", "-o", "name",
    ).splitlines()
    name = f"sh.helm.release.v1.omniscience.v{revision}"
    require(sorted(revisions) == sorted(
        f"secret/sh.helm.release.v1.omniscience.v{i}" for i in range(1, revision + 1)
    ), f"Unexpected Omniscience release history at revision {revision}")
    secret = cluster.get("secret", name)
    meta = secret["metadata"]
    require(meta["labels"]["status"] == "deployed", "Expected deployed Helm revision")
    payload = secret["data"]["release"]
    return {
        "helm_revision": revision,
        "helm_secret_uid": meta["uid"],
        "helm_secret_resource_version": meta["resourceVersion"],
        "helm_payload_sha256": dump_hash(payload.encode()),
    }, payload


def source_identity(cluster):
    release, _ = release_pin(cluster, 1)
    source = cluster.get("statefulset", SOURCE)
    volumes = [v for v in source["spec"]["template"]["spec"]["volumes"] if v["name"] == "data"]
    require(volumes == [{"name": "data", "emptyDir": {}}],
            "Source StatefulSet no longer uses the expected emptyDir")
    pod = cluster.get("pod", f"{SOURCE}-0")
    status = pod["status"]["containerStatuses"][0]
    require(status["imageID"].endswith("@" + DIGEST) and status["ready"],
            "Source PostgreSQL container image or readiness differs")
    return {
        **release,
        "image": IMAGE,
        "source_statefulset_uid": source["metadata"]["uid"],
        "source_pod_uid": pod["metadata"]["uid"],
        "source_container_id": status["containerID"],
    }


def inventory(cluster, pod):
    tables = cluster.psql(pod, DATABASE, """
        SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
    """).splitlines()
    require(tables == sorted(TABLES), "Public table inventory differs")
    role_flags = cluster.psql(pod, DATABASE, """
        SELECT rolname, rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole,
               rolreplication, rolbypassrls
        FROM pg_roles WHERE left(rolname, 3) <> 'pg_' ORDER BY rolname;
    """).splitlines()
    require(role_flags == ["omniscience|t|t|f|t|f|f|f", "postgres|t|t|t|t|t|t|t"],
            "Database role inventory differs")
    sql = "\n".join(
        f"""SELECT '{table}', count(*),
                   encode(sha256(convert_to(coalesce(string_agg(row_hash, '' ORDER BY row_hash), ''), 'UTF8')), 'hex')
            FROM (
                SELECT encode(sha256(convert_to(to_jsonb(t)::text, 'UTF8')), 'hex') AS row_hash
                FROM public."{table}" t
            ) hashes;"""
        for table in tables
    )
    rows = cluster.psql(pod, DATABASE, "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n" + sql + "\nCOMMIT;")
    return dict((table, [int(count), fingerprint])
                for table, count, fingerprint in (line.split("|") for line in rows.splitlines()))


def postgres_command(cluster, pod, command):
    return cluster.kubectl(
        "exec", pod, "--", "sh", "-ec",
        'export PGPASSWORD="$(cat "$POSTGRES_POSTGRES_PASSWORD_FILE")"; exec "$@"',
        "postgres-client", *command,
    ).encode("utf-8")


def normalized_schema_hash(data):
    # pg_dump and pg_dumpall use random psql restriction keys.
    return dump_hash(re.sub(rb"^\\(?:un)?restrict [A-Za-z0-9]+\n", b"", data, flags=re.MULTILINE))


def database_fingerprint(cluster, pod):
    schema = postgres_command(cluster, pod, ["pg_dump", "--schema-only", "-U", "postgres", "-d", DATABASE])
    sequences = cluster.psql(pod, DATABASE, r"""
        SELECT format('SELECT %L,last_value,is_called FROM %I.%I;',
                      schemaname || '.' || sequencename, schemaname, sequencename)
        FROM pg_sequences WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY schemaname, sequencename
        \gexec
    """)
    revision = cluster.psql(pod, DATABASE, "SELECT version_num FROM public.alembic_version;")
    require(revision == EXPECTED_ALEMBIC, "Omniscience migration revision differs from reviewed baseline")
    owner = cluster.psql(pod, DATABASE, """
        SELECT rolpassword FROM pg_authid WHERE rolname = 'omniscience';
    """)
    require(owner.startswith("SCRAM-SHA-256$"), "Expected Omniscience owner SCRAM verifier")
    return {
        "tables": inventory(cluster, pod),
        "alembic_revision": revision,
        "owner_verifier_sha256": dump_hash(owner.encode()),
        "database_schema_sha256": normalized_schema_hash(schema),
        "sequence_state_sha256": dump_hash(sequences.encode()),
    }


def source_fingerprint(cluster):
    pod = f"{SOURCE}-0"
    globals_and_schema = postgres_command(cluster, pod, ["pg_dumpall", "--schema-only", "-U", "postgres"])
    return {
        **database_fingerprint(cluster, pod),
        "cluster_schema_sha256": normalized_schema_hash(globals_and_schema),
    }


def capture(cluster):
    verify_bootstrap_receipt(cluster)
    paused(cluster)
    source = source_identity(cluster)
    before = source_fingerprint(cluster)
    require(before["tables"]["workspaces"][0] >= 3 and before["tables"]["sources"][0] >= 2,
            "Workspace or source count is below the reviewed floor")
    data = postgres_command(cluster, f"{SOURCE}-0", ["pg_dumpall", "-U", "postgres"])
    filtered_dump(data, dump_hash(data))
    paused(cluster)
    require(source == source_identity(cluster) and before == source_fingerprint(cluster),
            "Source identity or data changed during capture")
    CAPTURE.mkdir(mode=0o700)
    descriptor = os.open(DUMP, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    write_private_json(CAPTURE_RECEIPT, {**source, "backup_sha256": dump_hash(data), **before})


def verified_capture(cluster):
    receipt = read_private_json(CAPTURE_RECEIPT)
    require(all(receipt[key] == value for key, value in source_identity(cluster).items()),
            "Source identity differs from the captured backup")
    return receipt


def restore(cluster):
    verify_bootstrap_receipt(cluster)
    identity = verification_identity(cluster)
    pod_uid = verify_staging_target(cluster)
    require(DUMP.stat().st_mode & 0o777 == 0o600, "Expected a private dump file")
    sql = filtered_dump(DUMP.read_bytes(), identity["backup_sha256"])
    require(cluster.psql(STAGE, DATABASE, """
        SELECT
            (SELECT array_agg(rolname ORDER BY rolname) FROM pg_roles WHERE left(rolname, 3) <> 'pg_')
                = ARRAY['omniscience', 'postgres']::name[]
            AND NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public')
            AND EXISTS (
                SELECT FROM pg_database WHERE datname = 'omniscience'
                AND pg_encoding_to_char(encoding) = 'UTF8'
                AND datlocprovider = 'c' AND datcollate = 'en_US.UTF-8'
                AND datctype = 'en_US.UTF-8'
                AND pg_get_userbyid(datdba) = 'omniscience'
            );
    """) == "t", "Restore target does not match fresh bootstrap")
    require(verify_staging_target(cluster) == pod_uid, "Staging pod changed before restore")
    cluster.psql(STAGE, "postgres", sql)
    require(verify_staging_target(cluster) == pod_uid and verification_identity(cluster) == identity,
            "Staging identity changed during restore")
    write_private_json(RESTORE_RECEIPT, {**identity, "staging_pod_uid": pod_uid})


PROBE_CODE = """
import os
import sys

import psycopg
from psycopg.conninfo import conninfo_to_dict

mode = sys.argv[2]
if mode not in ("bootstrap", "restored"):
    sys.exit(1)

for key in ("DATABASE_URL", "MIGRATION_DATABASE_URL"):
    phase = "url"
    try:
        url = os.environ[key]
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError()
        params = conninfo_to_dict(url.replace("postgresql+asyncpg://", "postgresql://", 1))
        if (params.get("host"), params.get("port"), params.get("user"), params.get("dbname")) != (
            "omniscience-postgres", "5432", "omniscience", "omniscience",
        ) or not params.get("password"):
            raise ValueError()
        params["host"] = sys.argv[1]
        params.pop("hostaddr", None)
        params["connect_timeout"] = 5
        phase = "connect"
        with psycopg.connect(**params) as connection:
            phase = "read"
            role, database = connection.execute("SELECT current_user, current_database()").fetchone()
            if (role, database) != ("omniscience", "omniscience"):
                raise ValueError()
            if mode == "bootstrap":
                if connection.execute("SELECT 1").fetchone() != (1,):
                    raise ValueError()
            elif connection.execute("SELECT version_num FROM public.alembic_version").fetchall() != [("0015",)]:
                raise ValueError()
    except Exception as error:
        print(f"{key} {phase} failed {type(error).__name__} {getattr(error, 'sqlstate', None)}", flush=True)
        sys.exit(1)
    print(key + " passed", flush=True)
"""


def validate_probe_target(host, mode):
    require((host, mode) in ((STAGE, "bootstrap"), (STAGE, "restored"), (SOURCE, "restored")),
            "Unexpected PostgreSQL probe target or mode")


def probe(cluster, host, mode="restored"):
    validate_probe_target(host, mode)
    name = "omniscience-postgres-auth-probe"
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": name,
            "namespace": NAMESPACE,
            "labels": {
                "app.kubernetes.io/name": "omniscience-storage-probe",
                "app.kubernetes.io/component": "storage-auth-probe",
            },
        },
        "spec": {
            "automountServiceAccountToken": False,
            "restartPolicy": "Never",
            "activeDeadlineSeconds": 120,
            "containers": [{
                "name": "probe",
                "image": PROBE_IMAGE,
                "command": ["python", "-c", PROBE_CODE, host, mode],
                "env": [
                    {"name": key, "valueFrom": {"secretKeyRef": {"name": "omniscience-api-secret", "key": key}}}
                    for key in ("DATABASE_URL", "MIGRATION_DATABASE_URL")
                ],
            }],
        },
    }
    cluster.kubectl("create", "-f", "-", input=json.dumps(pod))
    try:
        cluster.kubectl("wait", "pod", name, "--for=jsonpath={.status.phase}=Succeeded", "--timeout=130s")
    finally:
        cluster.kubectl("delete", "pod", name, "--wait=true", "--timeout=60s")


def decode_release(payload):
    return json.loads(gzip.decompress(base64.b64decode(base64.b64decode(payload))))


POSTGRES_SECRET_DEFAULTS = ("password", "postgresPassword", "replicationPassword", "metricsPassword")
APP_SECRET_DEFAULTS = ("brokerToken", "migrationDatabaseUrl", "neo4jPassword", "qdrantApiKey", "runtimeDatabaseUrl")


def sanitized_chart_values(values):
    result = copy.deepcopy(values)
    redacted = []

    def blank(section, keys):
        for key in keys:
            if key in section:
                value = section[key]
                require(isinstance(value, str) or value is None, "Unexpected type in Helm credential field")
                if value:
                    redacted.append(value)
                section[key] = ""

    app = result["secrets"]
    require(not any(value for key, value in app.items() if key not in (*APP_SECRET_DEFAULTS, "existingSecret")),
            "Unexpected populated app credential field in chart defaults")
    blank(app, APP_SECRET_DEFAULTS)
    blank(result["postgresql"]["auth"], POSTGRES_SECRET_DEFAULTS)
    blank(result["neo4j"]["neo4j"], ("password",))
    blank(result["qdrant"], ("apiKey",))

    def assert_no_duplicates(value):
        if isinstance(value, dict):
            for item in value.values():
                assert_no_duplicates(item)
        elif isinstance(value, list):
            for item in value:
                assert_no_duplicates(item)
        elif isinstance(value, str):
            require(not any(value == secret or (len(secret) >= 8 and secret in value) for secret in redacted),
                    "A chart credential remains outside reviewed defaults")

    assert_no_duplicates(result)
    return result


def restore_chart(chart_dir, release):
    chart = release["chart"]
    values = sanitized_chart_values(chart["values"])
    require(chart["metadata"]["name"] == "omniscience"
            and {dep["name"]: dep["version"] for dep in chart["metadata"]["dependencies"]}
            == {name: version for name, (version, _, _) in DEPENDENCIES.items()},
            "Unexpected installed Helm chart dependencies")
    chart_dir.mkdir()
    (chart_dir / "charts").mkdir()
    for key, name in (("metadata", "Chart.yaml"), ("values", "values.yaml"), ("lock", "Chart.lock")):
        if chart.get(key):
            (chart_dir / name).write_text(json.dumps(values if key == "values" else chart[key]))
    if chart.get("schema"):
        (chart_dir / "values.schema.json").write_bytes(base64.b64decode(chart["schema"]))
    for file in chart["templates"] + (chart.get("files") or []):
        path = (chart_dir / file["name"]).resolve()
        require(path.is_relative_to(chart_dir), "Unexpected chart file path")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(file["data"]))
    for name, (version, repository, archive_sha256) in DEPENDENCIES.items():
        source = [repository] if repository.startswith("oci://") else [name, "--repo", repository]
        subprocess.run(
            ["helm", "pull", *source, "--version", version, "--destination", str(chart_dir / "charts")],
            capture_output=True, text=True, check=True,
        )
        archive = chart_dir / "charts" / f"{name}-{version}.tgz"
        require(dump_hash(archive.read_bytes()) == archive_sha256, f"Unexpected {name} chart archive")


def validated_context(cluster):
    context = cluster.helper["CONTEXT"]
    result = subprocess.run(
        ["kubectl", "--context", context, "config", "view", "--minify", "--raw", "-o", "json"],
        capture_output=True, text=True, check=True,
    )
    config = json.loads(result.stdout)
    require(len(config["clusters"]) == len(config["users"]) == 1, "Expected one scoped EKS cluster and user")
    live = json.loads(cluster.helper["aws"](
        ["eks", "describe-cluster", "--name", context, "--region", "eu-central-1", "--output", "json"],
        env=cluster.env,
    ))["cluster"]
    target = config["clusters"][0]["cluster"]
    require(live["arn"] == EXPECTED_ARN and target == {
        "server": live["endpoint"],
        "certificate-authority-data": live["certificateAuthority"]["data"],
    }, "Kubeconfig endpoint or certificate does not match the authorized EKS cluster")
    user = config["users"][0]["user"]
    require(set(user) == {"exec"} and Path(user["exec"]["command"]).name == "aws",
            "Expected EKS exec authentication")
    executor = user["exec"]
    executor["command"] = "aws"
    executor["args"] = ["eks", "get-token", "--region", "eu-central-1",
                        "--cluster-name", context, "--output", "json"]
    executor["env"] = []
    return config


def helm_context(cluster, path):
    path.write_text(json.dumps(cluster.config))
    path.chmod(0o600)
    return {**cluster.env, "KUBECONFIG": str(path)}


def change_manifest(expected, resume):
    for name, replicas in EXPECTED_REPLICAS.items():
        deployment = expected[("Deployment", name)]["spec"]
        require(deployment["replicas"] == (0 if resume else replicas),
                "Installed writer replica count differs from expected baseline")
        deployment["replicas"] = replicas if resume else 0
    pod = expected[("StatefulSet", SOURCE)]["spec"]["template"]["spec"]
    old_volume = next(v for v in pod["volumes"] if v["name"] == "data")
    if resume:
        require(old_volume == {"name": "data", "persistentVolumeClaim": {"claimName": CLAIM}}
                and pod["containers"][0]["image"] == IMAGE,
                "Resume baseline does not use the verified image and retained claim")
    else:
        require(old_volume == {"name": "data", "emptyDir": {}},
                "Helm baseline does not use the expected emptyDir")
        old_volume.pop("emptyDir")
        old_volume["persistentVolumeClaim"] = {"claimName": CLAIM}
        pod["containers"][0]["image"] = IMAGE


def verify_render(cluster, stdout, baseline, resume):
    manifest = stdout.split("MANIFEST:\n", 1)[1]

    def resources(source):
        result = subprocess.run(
            ["yq", "ea", "-o=json", "-I=0", "[.]", "-"],
            input=source, capture_output=True, text=True, check=True,
        )
        documents = [obj for obj in json.loads(result.stdout) if obj]
        indexed = {(obj["kind"], obj["metadata"]["name"]): obj for obj in documents}
        require(len(indexed) == len(documents), "Duplicate resource in Helm manifest")
        return indexed

    expected = resources(baseline)
    actual = resources(manifest)
    pg_key = ("StatefulSet", "omniscience-postgres")
    change_manifest(expected, resume)
    require(actual == expected, "Rendered resources differ outside the approved storage or replica changes")

    live = cluster.get("statefulset", "omniscience-postgres")["spec"]
    rendered = actual[pg_key]["spec"]
    for key in ("serviceName", "selector", "volumeClaimTemplates", "podManagementPolicy"):
        default = "OrderedReady" if key == "podManagementPolicy" else None
        require(rendered.get(key, default) == live.get(key, default), f"Unexpected StatefulSet {key} change")
    spec = rendered["template"]["spec"]
    volumes = {volume["name"]: volume for volume in spec["volumes"]}
    require(volumes["data"].get("persistentVolumeClaim") == {"claimName": CLAIM},
            "Rendered pod does not use the retained PVC")
    require(volumes["postgresql-password"]["secret"]["secretName"] == "omniscience-postgres",
            "Rendered PostgreSQL Secret reference differs")
    require(spec["containers"][0]["image"] == IMAGE, "Rendered image digest differs")
    live_service = cluster.get("service", "omniscience-postgres")["spec"]
    require(actual[("Service", "omniscience-postgres")]["spec"]["selector"] == live_service["selector"],
            "Rendered PostgreSQL Service selector differs")
    for (kind, name), rendered_secret in actual.items():
        if kind != "Secret":
            continue
        rendered_data = {
            key: base64.b64decode(value) for key, value in rendered_secret.get("data", {}).items()
        }
        rendered_data.update({
            key: value.encode() for key, value in rendered_secret.get("stringData", {}).items()
        })
        live_secret = cluster.get("secret", name)
        live_data = {key: base64.b64decode(value) for key, value in live_secret.get("data", {}).items()}
        require(rendered_data == live_data and rendered_secret.get("type", "Opaque") == live_secret["type"],
                f"Rendered Secret {name} differs from its live data or type")


def verification_identity(cluster):
    capture_receipt = verified_capture(cluster)
    return {**capture_receipt, **volume_identity(cluster)}


def volume_identity(cluster):
    claim = cluster.get("pvc", CLAIM)
    require(claim["status"]["phase"] == "Bound" and claim["spec"]["storageClassName"] == "splatform-gp3"
            and claim["spec"]["accessModes"] == ["ReadWriteOnce"]
            and claim["spec"]["resources"]["requests"]["storage"] == "8Gi",
            "Recovery claim does not match the expected 8 GiB RWO binding")
    volume = cluster.get("pv", claim["spec"]["volumeName"])
    spec = volume["spec"]
    ref = spec["claimRef"]
    require((ref["namespace"], ref["name"], ref["uid"]) == (NAMESPACE, CLAIM, claim["metadata"]["uid"])
            and spec["persistentVolumeReclaimPolicy"] == "Retain"
            and spec["csi"]["driver"] == "ebs.csi.aws.com", "Recovery PV binding or class differs")
    handle = spec["csi"]["volumeHandle"]
    require(re.fullmatch(r"vol-[0-9a-f]+", handle), "Unexpected EBS volume handle")
    ebs = json.loads(cluster.helper["aws"](
        ["ec2", "describe-volumes", "--region", "eu-central-1", "--volume-ids", handle, "--output", "json"],
        env=cluster.env,
    ))["Volumes"]
    terms = spec["nodeAffinity"]["required"]["nodeSelectorTerms"]
    zones = {
        zone for term in terms for expr in term.get("matchExpressions", [])
        if expr["key"] in ("topology.ebs.csi.aws.com/zone", "topology.kubernetes.io/zone")
        and expr["operator"] == "In" for zone in expr["values"]
    }
    require(len(ebs) == 1 and ebs[0]["VolumeId"] == handle
            and ebs[0]["Encrypted"] is True and ebs[0]["Size"] == 8
            and ebs[0]["VolumeType"] == "gp3"
            and zones == {ebs[0]["AvailabilityZone"]}, "EBS volume size, encryption or topology differs")
    return {
        "pvc_uid": claim["metadata"]["uid"],
        "pv_name": volume["metadata"]["name"],
        "pv_uid": volume["metadata"]["uid"],
        "volume_handle": handle,
        "availability_zone": ebs[0]["AvailabilityZone"],
    }


def write_private_json(destination, identity):
    with tempfile.NamedTemporaryFile(mode="w", dir=destination.parent, delete=False) as file:
        path = Path(file.name)
        try:
            json.dump(identity, file)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
            path.replace(destination)
        finally:
            path.unlink(missing_ok=True)


def read_private_json(path):
    require(path.is_file() and path.stat().st_mode & 0o777 == 0o600, f"Expected a private {path.name} receipt")
    return json.loads(path.read_text())


def stage_resources(cluster):
    return {
        "pod": cluster.get("pod", STAGE)["metadata"]["uid"],
        "service": cluster.get("service", STAGE)["metadata"]["uid"],
        "networkpolicy": cluster.get("networkpolicy", f"{STAGE}-probe")["metadata"]["uid"],
        "probe_egress": cluster.get("networkpolicy", PROBE_EGRESS)["metadata"]["uid"],
    }


def verify_bootstrap(cluster):
    require(not CAPTURE.exists(), "Bootstrap verification must precede capture")
    cluster.kubectl("wait", "pod", STAGE, "--for=condition=Ready", "--timeout=10m")
    cluster.kubectl(
        "wait", "endpointslices", "-l", f"kubernetes.io/service-name={STAGE}",
        "--for=jsonpath={.endpoints[0].conditions.ready}=true", "--timeout=60s",
    )
    uid = verify_staging_target(cluster)
    resources = stage_resources(cluster)
    volume = volume_identity(cluster)
    require(resources["pod"] == uid, "Staging bootstrap pod changed")
    probe(cluster, STAGE, mode="bootstrap")
    require(verify_staging_target(cluster) == uid and stage_resources(cluster) == resources
            and volume_identity(cluster) == volume, "Staging bootstrap identity changed")
    write_private_json(BOOTSTRAP_RECEIPT, {**volume, "stage_resources": resources})


def verify_bootstrap_receipt(cluster):
    uid = verify_staging_target(cluster)
    resources = stage_resources(cluster)
    require(resources["pod"] == uid, "Staging bootstrap pod changed")
    require(read_private_json(BOOTSTRAP_RECEIPT) == {**volume_identity(cluster), "stage_resources": resources},
            "Bootstrap authentication receipt differs from current staging identities")


def verify_probe_policy(cluster, receipt):
    require(cluster.get("networkpolicy", PROBE_EGRESS)["metadata"]["uid"]
            == receipt["stage_resources"]["probe_egress"], "Probe policy identity changed")



def check_database_fingerprint(cluster, pod, receipt):
    require(all(receipt[key] == value for key, value in database_fingerprint(cluster, pod).items()),
            "PostgreSQL table, schema, role verifier or sequence state differs from capture")


def delete_owned(cluster, route, uid):
    options = {"apiVersion": "v1", "kind": "DeleteOptions", "preconditions": {"uid": uid}}
    cluster.kubectl("delete", "--raw", route, "-f", "-", input=json.dumps(options))


def stop_stage(cluster):
    receipt = read_private_json(RECEIPT)
    identity = verification_identity(cluster)
    resources = stage_resources(cluster)
    require(receipt == {**identity, "stage_resources": resources}, "Staged verification identity differs")
    require(verify_staging_target(cluster) == resources["pod"], "Staged writer identity differs")
    paused(cluster)
    check_database_fingerprint(cluster, STAGE, receipt)
    require(stage_resources(cluster) == resources, "Staging resources changed before shutdown")
    delete_owned(cluster, f"/api/v1/namespaces/{NAMESPACE}/pods/{STAGE}", resources["pod"])
    if not cluster.absent("pod", STAGE):
        cluster.kubectl("wait", "pod", STAGE, "--for=delete", "--timeout=120s")
    delete_owned(cluster, f"/api/v1/namespaces/{NAMESPACE}/services/{STAGE}", resources["service"])
    delete_owned(cluster, f"/apis/networking.k8s.io/v1/namespaces/{NAMESPACE}/networkpolicies/{STAGE}-probe",
                 resources["networkpolicy"])
    require(not pvc_consumers(cluster), "A pod still references the retained PVC")
    write_private_json(STOPPED_RECEIPT, receipt)


def verify_cutover_target(cluster):
    require(cluster.absent("pod", STAGE), "Terminate and wait for staging pod before cutover")
    require(not pvc_consumers(cluster), "A pod still references the retained PVC")
    receipt = read_private_json(RECEIPT)
    verify_probe_policy(cluster, receipt)
    require(receipt == read_private_json(STOPPED_RECEIPT)
            and {key: value for key, value in receipt.items() if key != "stage_resources"}
            == verification_identity(cluster),
            "Staging verification and shutdown receipts no longer match the cutover target")
    paused(cluster)
    verify_endpoint(cluster, SOURCE, cluster.get("pod", f"{SOURCE}-0")["metadata"]["uid"])
    captured = verified_capture(cluster)
    require(all(captured[key] == value for key, value in source_fingerprint(cluster).items()),
            "Source schema, data or sequences changed after capture")


def verify_live(cluster):
    paused(cluster)
    release, _ = release_pin(cluster, 2)
    receipt = read_private_json(RECEIPT)
    verify_probe_policy(cluster, receipt)
    volume = volume_identity(cluster)
    require(all(receipt[key] == value for key, value in volume.items()), "Live PV identity differs from staging")
    pod = cluster.get("pod", f"{SOURCE}-0")
    require(pod["status"]["containerStatuses"][0]["imageID"].endswith("@" + DIGEST)
            and any(v.get("persistentVolumeClaim", {}).get("claimName") == CLAIM
                    for v in pod["spec"]["volumes"] if v["name"] == "data"),
            "Live PostgreSQL pod image or PVC differs")
    pod_uid = pod["metadata"]["uid"]
    verify_endpoint(cluster, SOURCE, pod_uid)
    require(pvc_consumers(cluster) == [pod_uid], "Unexpected live PVC consumer")
    check_database_fingerprint(cluster, f"{SOURCE}-0", receipt)
    probe(cluster, SOURCE)
    require(release_pin(cluster, 2)[0] == release and volume_identity(cluster) == volume
            and cluster.get("pod", f"{SOURCE}-0")["metadata"]["uid"] == pod_uid,
            "Live release, pod or volume changed during verification")
    write_private_json(LIVE_RECEIPT, {**release, **volume, "live_pod_uid": pod_uid})


def verify_resume_target(cluster):
    paused(cluster)
    release, _ = release_pin(cluster, 2)
    pod_uid = cluster.get("pod", f"{SOURCE}-0")["metadata"]["uid"]
    require(read_private_json(LIVE_RECEIPT) == {**release, **volume_identity(cluster), "live_pod_uid": pod_uid},
            "Live verification receipt no longer matches the release or volume")
    verify_endpoint(cluster, SOURCE, pod_uid)
    require(pvc_consumers(cluster) == [pod_uid], "Unexpected live PVC consumer")
    receipt = read_private_json(RECEIPT)
    verify_probe_policy(cluster, receipt)
    check_database_fingerprint(cluster, f"{SOURCE}-0", receipt)


def helm(cluster, action):
    resume = action in ("resume", "dryrun-resume")
    mutate = action in ("cutover", "resume")
    revision = 2 if resume else 1
    guard = verify_resume_target if resume else verify_cutover_target
    if mutate:
        guard(cluster)
    pin, payload = release_pin(cluster, revision)
    release = decode_release(payload)
    hooks = [(hook["name"], hook["kind"], hook["events"]) for hook in release.get("hooks", [])]
    require(hooks == EXPECTED_HOOKS, "Installed Helm release hooks differ from reviewed baseline")
    replicas = 1 if resume else 0
    with tempfile.TemporaryDirectory(prefix="omniscience-storage-", dir=PRIVATE) as directory:
        path = Path(directory).resolve()
        chart_dir = path / "omniscience"
        restore_chart(chart_dir, release)
        env = helm_context(cluster, path / "kubeconfig")
        base = ["helm", "upgrade", "omniscience", str(chart_dir), "--kube-context",
                cluster.helper["CONTEXT"], "-n", NAMESPACE, "--reuse-values", "--no-hooks",
                "-f", str(HERE / "helm-values.yaml"),
                "--set", f"replicaCount={replicas}"]
        dry_run = subprocess.run(
            # Keep the unredacted manifest in memory to compare credentials byte for byte.
            base + ["--dry-run=server"],
            env=env, capture_output=True, text=True, check=True,
        )
        verify_render(cluster, dry_run.stdout, release["manifest"], resume)
        if action == "dryrun":
            restored_replicas = subprocess.run(
                base[:-1] + ["replicaCount=1", "--dry-run=server"],
                env=env, capture_output=True, text=True, check=True,
            )
            paused_manifest = dry_run.stdout.split("MANIFEST:\n", 1)[1]
            verify_render(cluster, restored_replicas.stdout, paused_manifest, resume=True)
        elif mutate:
            guard(cluster)
            require(release_pin(cluster, revision)[0] == pin, "Helm release changed since dry run")
            verify_render(cluster, dry_run.stdout, release["manifest"], resume)
            subprocess.run(
                base + ["--wait", "--timeout", "10m"],
                env=env, capture_output=True, text=True, check=True,
            )
            _, next_payload = release_pin(cluster, revision + 1)
            next_release = decode_release(next_payload)
            require(next_release["config"]["replicaCount"] == replicas,
                    "Helm API replica count differs from intended value")
            if resume:
                uid = read_private_json(RECEIPT)["stage_resources"]["probe_egress"]
                delete_owned(cluster,
                             f"/apis/networking.k8s.io/v1/namespaces/{NAMESPACE}/networkpolicies/{PROBE_EGRESS}",
                             uid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("stage")
    commands.add_parser("verify-bootstrap")
    commands.add_parser("stop-stage")
    commands.add_parser("capture")
    commands.add_parser("restore")
    commands.add_parser("verify-stage")
    commands.add_parser("verify-live")
    commands.add_parser("dryrun")
    commands.add_parser("dryrun-resume")
    commands.add_parser("cutover")
    commands.add_parser("resume")
    args = parser.parse_args()
    try:
        cluster = Cluster()
        if args.action == "stage":
            stage(cluster)
            verify_bootstrap(cluster)
        elif args.action == "verify-bootstrap":
            verify_bootstrap(cluster)
        elif args.action == "stop-stage":
            stop_stage(cluster)
        elif args.action == "capture":
            capture(cluster)
        elif args.action == "restore":
            restore(cluster)
        elif args.action == "verify-stage":
            identity = verification_identity(cluster)
            pod_uid = verify_staging_target(cluster)
            require(read_private_json(RESTORE_RECEIPT) == {**identity, "staging_pod_uid": pod_uid},
                    "Restore receipt does not match staging target and backup")
            resources = stage_resources(cluster)
            check_database_fingerprint(cluster, STAGE, identity)
            probe(cluster, STAGE)
            require(identity == verification_identity(cluster) and pod_uid == verify_staging_target(cluster)
                    and stage_resources(cluster) == resources,
                    "Staging identity changed during verification")
            write_private_json(RECEIPT, {**identity, "stage_resources": resources})
        elif args.action == "verify-live":
            verify_live(cluster)
        else:
            helm(cluster, args.action)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"{args.action} failed (command exit {error.returncode}). Inspect workload status without dumping secrets.\n")
    except (FileNotFoundError, FileExistsError):
        parser.exit(1, f"{args.action} failed: a required path is missing or a recovery artifact already exists.\n")
    except RuntimeError as error:
        parser.exit(1, f"{args.action} failed: {error}\n")
    print(f"{args.action} passed")


if __name__ == "__main__":
    main()
