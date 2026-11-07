#!/usr/bin/env python3
"""Portal recovery commands for the verified nonprod-euc1 EKS context."""

import argparse
import base64
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
RECEIPT = PRIVATE / "frankfurt-activation/portal-postgres-stage-verified.json"
RESTORE_RECEIPT = PRIVATE / "frankfurt-activation/portal-postgres-stage-restored.json"
NAMESPACE = "splatform"
CLAIM = "portal-postgres-data-retained"
STAGE = "portal-postgres-restore"
DIGEST = "sha256:b418fd5f001c272aad93ac1febf783f543ee45d8e359d58bd5afc3d2a9b62290"
IMAGE = f"registry-1.docker.io/bitnami/postgresql@{DIGEST}"
DUMP_HASH = "77cb9fc2f83bb331ede5c1fa54e244e17e90566d5ebd70e04f965fbce465d0ca"
REVISION = "0009_kv_owner_entitlement"
TABLE_COUNTS = {
    "alembic_version": 1,
    "audit_events": 0,
    "invoice_records": 0,
    "oidc_login_attempts": 1,
    "plans": 0,
    "reingest_attempts": 0,
    "sessions": 1,
    "source_configs": 0,
    "step_up_assertions": 0,
    "stripe_ref_tenant_map": 0,
    "stripe_webhook_events": 0,
    "subscriptions": 0,
    "tenant_spec_refs": 0,
    "tenant_workspaces": 2,
    "tenants": 2,
    "usage_records": 0,
    "users": 2,
}
DUPLICATE_DDL = (
    r"CREATE ROLE platform_portal_owner;",
    r"CREATE ROLE postgres;",
    r"ALTER ROLE postgres WITH [^\n]+;",
    r"CREATE DATABASE platform_portal WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'en_US\.UTF-8';",
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def filtered_dump(path):
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == DUMP_HASH, "Backup SHA-256 mismatch")
    sql = data.decode("utf-8")
    for pattern in DUPLICATE_DDL:
        sql, count = re.subn(rf"^{pattern}\n", "", sql, flags=re.MULTILINE)
        require(count == 1, "Expected exactly one matching bootstrap statement")
    return sql


class Cluster:
    def __init__(self):
        self.helper = runpy.run_path(str(HELPER))
        self.env = self.helper["environment"]()

    def kubectl(self, *args, input=None):
        return self.helper["kubectl"](["-n", NAMESPACE, *args], env=self.env, input=input)

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
    for resource, name in (("pvc", CLAIM), ("service", STAGE), ("pod", STAGE)):
        require(cluster.absent(resource, name), f"Staging {resource} {name} already exists")
    require(not (RECEIPT.exists() or RESTORE_RECEIPT.exists()), "Previous staging receipt exists")
    storage = cluster.get("storageclass", "splatform-gp3")
    require(storage["provisioner"] == "ebs.csi.aws.com"
            and storage["reclaimPolicy"] == "Retain"
            and storage["volumeBindingMode"] == "WaitForFirstConsumer"
            and storage["parameters"].get("encrypted") == "true",
            "Unexpected staging StorageClass")
    sts = cluster.get("statefulset", "portal-postgres")
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
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": STAGE, "namespace": NAMESPACE, "labels": labels},
        "spec": spec,
    }
    cluster.kubectl("create", "-f", str(HERE / "staging.yaml"))
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
    slices = json.loads(cluster.kubectl(
        "get", "endpointslices", "-l", f"kubernetes.io/service-name={STAGE}", "-o", "json",
    ))
    endpoints = [ep for item in slices["items"] for ep in item["endpoints"]]
    require(bool(endpoints) and all(
        ep.get("targetRef", {}).get("uid") == pod["metadata"]["uid"]
        and ep.get("conditions", {}).get("ready") is True
        for ep in endpoints
    ), "Staging Service must target only the ready staging pod")
    return pod["metadata"]["uid"]


def restore(cluster, backup):
    sql = filtered_dump(backup)
    identity = verification_identity(cluster)
    pod_uid = verify_staging_target(cluster)
    require(cluster.psql(STAGE, "platform_portal", """
        SELECT
            (SELECT count(*) FROM pg_roles WHERE rolname = 'platform_portal_owner') = 1
            AND NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'portal_app')
            AND NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public')
            AND EXISTS (
                SELECT FROM pg_database WHERE datname = 'platform_portal'
                AND pg_encoding_to_char(encoding) = 'UTF8'
                AND datlocprovider = 'c' AND datcollate = 'en_US.UTF-8'
                AND datctype = 'en_US.UTF-8'
            );
    """) == "t", "Restore target does not match fresh bootstrap")
    require(verify_staging_target(cluster) == pod_uid, "Staging pod changed before restore")
    cluster.psql(STAGE, "postgres", sql)
    require(verify_staging_target(cluster) == pod_uid and verification_identity(cluster) == identity,
            "Staging identity changed during restore")
    write_private_json(RESTORE_RECEIPT, {**identity, "staging_pod_uid": pod_uid})


def verify(cluster, pod, counts):
    tables = cluster.psql(pod, "platform_portal", """
        SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
    """).splitlines()
    require(tables == sorted(TABLE_COUNTS), "Public table list differs")
    if counts:
        checks = " UNION ALL ".join(
            f'SELECT count(*) = {count} FROM public."{table}"'
            for table, count in TABLE_COUNTS.items()
        )
        require(cluster.psql(pod, "platform_portal", f"SELECT bool_and(ok) FROM ({checks}) t(ok);") == "t",
                "Backup row count differs")
    require(cluster.psql(pod, "platform_portal", "SELECT version_num FROM alembic_version;") == REVISION,
            "Alembic revision differs")
    require(cluster.psql(pod, "platform_portal", """
        SELECT count(*) = 2 AND bool_and(
            rolcanlogin AND rolinherit AND NOT (rolsuper OR rolcreaterole OR rolreplication OR rolbypassrls)
            AND rolcreatedb = (rolname = 'platform_portal_owner')
        )
        FROM pg_roles WHERE rolname IN ('portal_app', 'platform_portal_owner');
    """) == "t", "Role flags differ")


PROBE_CODE = """
import os
import sys
from urllib.parse import urlsplit

import psycopg
from psycopg.conninfo import conninfo_to_dict

host = sys.argv[1]
for key, role in (("DATABASE_URL", "portal_app"), ("DATABASE_URL_MIGRATIONS", "postgres")):
    phase = "url"
    try:
        url = os.environ[key].replace("postgresql+psycopg://", "postgresql://", 1)
        params = conninfo_to_dict(url)
        if (urlsplit(url).hostname not in ("portal-postgres", "portal-postgres.splatform",
                                              "portal-postgres.splatform.svc", "portal-postgres.splatform.svc.cluster.local")
                or params.get("user") != role or not params.get("password")):
            raise ValueError()
        params["host"] = host
        params.pop("hostaddr", None)
        params["connect_timeout"] = 5
        phase = "connect"
        with psycopg.connect(**params) as connection:
            phase = "identity"
            actual = connection.execute("SELECT current_user, current_database()").fetchone()
            if actual != (role, "platform_portal"):
                raise ValueError()
            phase = "read"
            if role == "portal_app":
                connection.execute(
                    "SELECT set_config('portal.tenant_id', %s, true)",
                    ("00000000-0000-0000-0000-000000000000",),
                )
            connection.execute("SELECT count(*) FROM public.tenants").fetchone()
    except Exception as error:
        sqlstate = getattr(error, "sqlstate", None) or "none"
        print(f"{key} {phase} failed {type(error).__name__} {sqlstate}", flush=True)
        sys.exit(1)
    print(key + " passed", flush=True)
"""


def probe(cluster, host):
    backend = cluster.get("deployment", "portal-backend")
    spec = backend["spec"]["template"]["spec"]
    image = next(c["image"] for c in spec["containers"] if c["name"] == "backend")
    require(image.startswith("120736097561.dkr.ecr.eu-central-1.amazonaws.com/genai-enablement/portal-backend:"),
            "Unexpected backend image registry")
    name = "portal-postgres-auth-probe"
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": name,
            "namespace": NAMESPACE,
            "labels": {"app.kubernetes.io/name": "platform-portal", "app.kubernetes.io/component": "auth-probe"},
        },
        "spec": {
            "automountServiceAccountToken": False,
            "restartPolicy": "Never",
            "activeDeadlineSeconds": 120,
            "imagePullSecrets": spec.get("imagePullSecrets", []),
            "containers": [{
                "name": "probe",
                "image": image,
                "command": ["python", "-c", PROBE_CODE, host],
                "env": [
                    {"name": key, "valueFrom": {"secretKeyRef": {"name": "platform-portal-secret", "key": key}}}
                    for key in ("DATABASE_URL", "DATABASE_URL_MIGRATIONS")
                ],
            }],
        },
    }
    cluster.kubectl("create", "-f", "-", input=json.dumps(pod))
    try:
        cluster.kubectl("wait", "pod", name, "--for=jsonpath={.status.phase}=Succeeded", "--timeout=130s")
    finally:
        cluster.kubectl("delete", "pod", name, "--wait=true", "--timeout=60s")


def restore_chart(chart_dir, release):
    chart = release["chart"]
    auth = chart["values"]["postgresql"]["auth"]
    require(not any(auth.get(key) for key in ("password", "postgresPassword", "replicationPassword")),
            "Refusing to write chart defaults containing database credentials")
    require(not any(chart["values"]["secrets"].values()),
            "Refusing to write chart defaults containing Portal credentials")
    require(chart["metadata"]["name"] == "platform-portal"
            and [(dep["name"], dep["version"]) for dep in chart["metadata"]["dependencies"]]
            == [("postgresql", "18.12.18")], "Unexpected installed Helm chart")
    chart_dir.mkdir()
    (chart_dir / "charts").mkdir()
    for key, name in (("metadata", "Chart.yaml"), ("values", "values.yaml"), ("lock", "Chart.lock")):
        if chart.get(key):
            (chart_dir / name).write_text(json.dumps(chart[key]))
    if chart.get("schema"):
        (chart_dir / "values.schema.json").write_bytes(base64.b64decode(chart["schema"]))
    for file in chart["templates"] + (chart.get("files") or []):
        path = (chart_dir / file["name"]).resolve()
        require(path.is_relative_to(chart_dir), "Unexpected chart file path")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(file["data"]))
    pull = subprocess.run(
        ["helm", "pull", "oci://registry-1.docker.io/bitnamicharts/postgresql",
         "--version", "18.12.18", "--destination", str(chart_dir / "charts")],
        capture_output=True, text=True, check=True,
    )
    require("sha256:5096e4ceed6e1a746be3abd50e4cd71392a7fc2b38e63d35504a905f99ae5e21" in (pull.stdout + pull.stderr),
            "Unexpected PostgreSQL OCI chart digest")


def helm_context(cluster, path):
    context = cluster.helper["CONTEXT"]
    result = subprocess.run(
        ["kubectl", "--context", context, "config", "view", "--minify", "--raw", "-o", "json"],
        capture_output=True, text=True, check=True,
    )
    config = json.loads(result.stdout)
    user = config["users"][0]["user"]
    require(set(user) == {"exec"} and Path(user["exec"]["command"]).name == "aws",
            "Expected EKS exec authentication")
    executor = user["exec"]
    executor["command"] = "aws"
    executor["args"] = ["eks", "get-token", "--region", "eu-central-1",
                        "--cluster-name", context, "--output", "json"]
    executor["env"] = []
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    return {**cluster.env, "KUBECONFIG": str(path)}


def verify_render(cluster, stdout, baseline):
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
    pg_key = ("StatefulSet", "portal-postgres")
    expected_pod = expected[pg_key]["spec"]["template"]["spec"]
    expected_pod["containers"][0]["image"] = IMAGE
    old_volume = next(v for v in expected_pod["volumes"] if v["name"] == "data")
    require(old_volume == {"name": "data", "emptyDir": {}}, "Helm baseline does not use the expected emptyDir")
    old_volume.pop("emptyDir")
    old_volume["persistentVolumeClaim"] = {"claimName": CLAIM}
    require(actual == expected, "Rendered resources differ outside the two PostgreSQL pod template changes")

    live = cluster.get("statefulset", "portal-postgres")["spec"]
    rendered = actual[pg_key]["spec"]
    for key in ("serviceName", "selector", "volumeClaimTemplates", "podManagementPolicy"):
        default = "OrderedReady" if key == "podManagementPolicy" else None
        require(rendered.get(key, default) == live.get(key, default), f"Unexpected StatefulSet {key} change")
    spec = rendered["template"]["spec"]
    volumes = {volume["name"]: volume for volume in spec["volumes"]}
    require(volumes["data"].get("persistentVolumeClaim") == {"claimName": CLAIM},
            "Rendered pod does not use the retained PVC")
    require(volumes["postgresql-password"]["secret"]["secretName"] == "portal-postgres",
            "Rendered PostgreSQL Secret reference differs")
    require(spec["containers"][0]["image"] == IMAGE, "Rendered image digest differs")
    live_service = cluster.get("service", "portal-postgres")["spec"]
    require(actual[("Service", "portal-postgres")]["spec"]["selector"] == live_service["selector"],
            "Rendered PostgreSQL Service selector differs")
    for name in ("portal-postgres", "platform-portal-secret"):
        rendered_secret = actual[("Secret", name)]
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
    revisions = cluster.kubectl(
        "get", "secret", "-l", "owner=helm,name=platform-portal", "-o", "name",
    ).splitlines()
    require(revisions == ["secret/sh.helm.release.v1.platform-portal.v1"],
            "Expected only Portal Helm revision 1")
    source = cluster.get("statefulset", "portal-postgres")
    data_volumes = [v for v in source["spec"]["template"]["spec"]["volumes"] if v["name"] == "data"]
    require(data_volumes == [{"name": "data", "emptyDir": {}}],
            "Source StatefulSet no longer uses the expected emptyDir")
    claim = cluster.get("pvc", CLAIM)
    require(claim["status"]["phase"] == "Bound", "Recovery claim is not bound")
    volume = cluster.get("pv", claim["spec"]["volumeName"])
    require(volume["spec"]["persistentVolumeReclaimPolicy"] == "Retain", "Recovery PV must use Retain")
    require(volume["spec"]["csi"]["driver"] == "ebs.csi.aws.com", "Recovery PV must use EBS CSI")
    return {
        "backup_sha256": DUMP_HASH,
        "image": IMAGE,
        "helm_revision": 1,
        "source_statefulset_uid": source["metadata"]["uid"],
        "pvc_uid": claim["metadata"]["uid"],
        "pv_name": volume["metadata"]["name"],
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


def verify_cutover_target(cluster):
    require(cluster.absent("pod", STAGE), "Terminate and wait for staging pod before cutover")
    pods = json.loads(cluster.kubectl("get", "pods", "-o", "json"))["items"]
    require(not any(v.get("persistentVolumeClaim", {}).get("claimName") == CLAIM
                    for pod in pods for v in pod["spec"].get("volumes", [])),
            "A pod still references the retained PVC")
    require(read_private_json(RECEIPT) == verification_identity(cluster),
            "Staging verification receipt no longer matches the cutover target")
    require(cluster.get("deployment", "portal-backend")["spec"]["replicas"] == 0
            and not any(pod["metadata"].get("labels", {}).get("app.kubernetes.io/component") == "backend"
                        and pod["metadata"].get("labels", {}).get("app.kubernetes.io/name") == "platform-portal"
                        for pod in pods),
            "Scale the Portal backend to zero and wait for its pods to terminate")
    require(cluster.psql("portal-postgres-0", "platform_portal", """
        SELECT NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public')
               AND NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'portal_app');
    """) == "t", "Original database contains app tables or runtime role")


def helm(cluster, cutover):
    if cutover:
        verify_cutover_target(cluster)
    secret = cluster.get("secret", "sh.helm.release.v1.platform-portal.v1")
    release = json.loads(gzip.decompress(base64.b64decode(base64.b64decode(secret["data"]["release"]))))
    hooks = [(hook["name"], hook["kind"], hook["events"]) for hook in release.get("hooks", [])]
    require(hooks == [("platform-portal-bootstrap-mappings", "Job", ["post-install", "post-upgrade"])],
            "Installed Helm hooks differ from the reviewed baseline")
    with tempfile.TemporaryDirectory(prefix="portal-recovery-", dir=PRIVATE) as directory:
        path = Path(directory).resolve()
        chart_dir = path / "platform-portal"
        restore_chart(chart_dir, release)
        env = helm_context(cluster, path / "kubeconfig")
        base = ["helm", "upgrade", "platform-portal", str(chart_dir), "--kube-context",
                cluster.helper["CONTEXT"], "-n", NAMESPACE, "--reuse-values", "--no-hooks",
                "-f", str(HERE / "helm-values.yaml")]
        dry_run = subprocess.run(
            # Capture the unredacted manifest in memory to compare credentials byte for byte.
            base + ["--dry-run=server"],
            env=env, capture_output=True, text=True, check=True,
        )
        verify_render(cluster, dry_run.stdout, release["manifest"])
        if cutover:
            verify_cutover_target(cluster)
            subprocess.run(
                base + ["--wait", "--timeout", "10m"],
                env=env, capture_output=True, text=True, check=True,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("stage")
    commands.add_parser("stop-stage")
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("backup", type=Path)
    commands.add_parser("verify-stage")
    commands.add_parser("verify-live")
    commands.add_parser("dryrun")
    commands.add_parser("cutover")
    args = parser.parse_args()
    try:
        cluster = Cluster()
        if args.action == "stage":
            stage(cluster)
            cluster.kubectl("wait", "pod", STAGE, "--for=condition=Ready", "--timeout=10m")
        elif args.action == "stop-stage":
            cluster.kubectl("delete", "pod", STAGE, "--wait=true", "--timeout=120s")
            cluster.kubectl("delete", "service", STAGE, "--wait=true", "--timeout=60s")
        elif args.action == "restore":
            restore(cluster, args.backup)
        elif args.action == "verify-stage":
            identity = verification_identity(cluster)
            pod_uid = verify_staging_target(cluster)
            require(read_private_json(RESTORE_RECEIPT) == {**identity, "staging_pod_uid": pod_uid},
                    "Restore receipt does not match staging target and backup")
            verify(cluster, STAGE, counts=True)
            probe(cluster, STAGE)
            require(identity == verification_identity(cluster) and pod_uid == verify_staging_target(cluster),
                    "Staging identity changed during verification")
            write_private_json(RECEIPT, identity)
        elif args.action == "verify-live":
            verify(cluster, "portal-postgres-0", counts=False)
            probe(cluster, "portal-postgres")
            require(cluster.get("deployment", "portal-backend")["spec"]["replicas"] > 0,
                    "Restore the Portal backend replica count before live verification")
            cluster.kubectl("rollout", "status", "deployment/portal-backend", "--timeout=180s")
        else:
            helm(cluster, cutover=args.action == "cutover")
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"{args.action} failed (command exit {error.returncode}). Inspect workload status without dumping secrets.\n")
    except RuntimeError as error:
        parser.exit(1, f"{args.action} failed: {error}\n")
    print(f"{args.action} passed")


if __name__ == "__main__":
    main()
