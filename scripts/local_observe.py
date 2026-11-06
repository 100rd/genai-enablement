#!/usr/bin/env python3
"""Source-only management-local-observe-v1 launcher; all state is local/private.

Install pyyaml/cryptography for bootstrap. Normal stop retains named volumes and
credentials. This launcher deliberately has no reset, publish, or production mode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PROFILE = "management-local-observe-v1"
ALPHA = "a34f0802-8321-5c7c-8a6b-dea95391faf5"
BETA = "beac9cbb-b8e1-52da-9fe7-5c5e591825f5"
SECRET_KEYS = (
    "OMNISCIENCE_POSTGRES_PASSWORD", "OMNISCIENCE_NEO4J_PASSWORD",
    "OMNISCIENCE_QDRANT_API_KEY", "KV_OMNISCIENCE_BROKER_ADMIN_CREDENTIAL",
    "BARBAROSSA_OBSERVE_DB_PASSWORD", "PORTAL_DB_PASSWORD",
    "PORTAL_APP_DB_PASSWORD", "PORTAL_KEYCLOAK_CLIENT_SECRET",
    "PORTAL_KEYCLOAK_ADMIN_PASSWORD", "LOCAL_OBSERVE_ALPHA_PASSWORD",
    "LOCAL_OBSERVE_BETA_PASSWORD",
)
DEFAULTS = {
    "PORTAL_FRONTEND_PORT": "13000", "PORTAL_BACKEND_PORT": "18001",
    "PORTAL_KEYCLOAK_PORT": "18081", "OMNISCIENCE_OBSERVE_API_PORT": "18000",
    "OMNISCIENCE_OBSERVE_ADMIN_PORT": "13001", "PORTAL_LOCAL_MODE": "source",
    "PORTAL_LOCAL_OBSERVE_ALPHA_TENANT_ID": ALPHA,
    "PORTAL_LOCAL_OBSERVE_BETA_TENANT_ID": BETA,
    "BARBAROSSA_PORTAL_TENANT_IDS": json.dumps([ALPHA]),
    "KV_OMNISCIENCE_BASE_URL": "http://omniscience-api:8000",
    "OMNISCIENCE_WORKSPACE_TOKEN_TTL_CEILING_SECONDS": "900",
}


def private_write(path: Path, contents: str | bytes) -> None:
    """Atomic replacement without a transient world-readable file."""
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(contents.encode() if isinstance(contents, str) else contents)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def initialize(state: Path) -> dict[str, str]:
    state = state.resolve()
    required = {"credentials.json", "portal-private.pem", "portal-public.pem", "runner.token", "probe.token", "initialized.json"}
    if state.exists():
        if not required.issubset(p.name for p in state.iterdir()):
            raise ValueError("incomplete local state: restore its original credentials; refusing to rotate")
        marker = json.loads((state / "initialized.json").read_text())
        if marker != {"schema_version": 1, "profile": PROFILE}:
            raise ValueError("state belongs to a different profile")
        credentials = json.loads((state / "credentials.json").read_text())
        if any(not credentials.get(key) for key in SECRET_KEYS):
            raise ValueError("incomplete local credentials; refusing to rotate")
        return credentials
    state.mkdir(parents=True, mode=0o700)
    state.chmod(0o700)
    credentials = {**DEFAULTS, **{key: secrets.token_hex(32) for key in SECRET_KEYS}}
    credentials["LOCAL_OBSERVE_STATE_DIR"] = str(state)
    private = Ed25519PrivateKey.generate()
    private_write(state / "portal-private.pem", private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    private_write(state / "portal-public.pem", private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    for name in ("runner.token", "probe.token"):
        private_write(state / name, secrets.token_hex(32) + "\n")
    private_write(state / "credentials.json", json.dumps(credentials, indent=2) + "\n")
    private_write(state / "knowledge-context.json", "[]\n")
    private_write(state / "initialized.json", json.dumps({"schema_version": 1, "profile": PROFILE}))
    return credentials


def run(args: list[str], *, env=None, input=None, capture=False, cwd=None):
    return subprocess.run(args, env=env, input=input, cwd=cwd, check=True,
                          text=True, stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def merge_fragments(fragments: list[dict]) -> dict:
    result = {"name": PROFILE, "services": {}, "networks": {}, "volumes": {}}
    for fragment in fragments:
        for service, config in fragment.get("services", {}).items():
            if service in result["services"]:
                raise ValueError(f"duplicate service: {service}")
            if any(store in service for store in ("postgres", "nats", "neo4j", "qdrant")) and config.get("ports"):
                raise ValueError(f"store must not be published: {service}")
            for port in config.get("ports", []):
                if not isinstance(port, dict) or port.get("host_ip") != "127.0.0.1":
                    raise ValueError(f"non-loopback published port: {service}")
            result["services"][service] = config
        for kind in ("networks", "volumes"):
            for key, value in fragment.get(kind, {}).items():
                if value.get("name") != f"{PROFILE}-{key}":
                    raise ValueError(f"{kind} must be isolated: {key}")
                previous = result[kind].get(key)
                if previous is None or previous.get("external"):
                    result[kind][key] = value
                elif not value.get("external") and previous != value:
                    raise ValueError(f"conflicting {kind}: {key}")
    if any(v.get("external") for v in result["networks"].values()):
        raise ValueError("every network requires an owner in this profile")
    for service, config in result["services"].items():
        networks = set(config.get("networks", {}))
        if service.startswith("portal-") and networks.intersection({"barbarossa-private", "omniscience-private"}):
            raise ValueError("Portal must not join owner-private networks")
        if service == "barbarossa-observer" and "portal-private" in networks:
            raise ValueError("observer must not join Portal private network")
    return result


def docker_environment(env=None):
    return {key: value for key, value in (env or os.environ).items()
            if key not in {"DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "BUILDX_BUILDER", "BUILDKIT_HOST", "COMPOSE_BAKE"}}


def local_docker() -> list[str]:
    """Resolve local metadata only; never connect to an unchecked daemon."""
    env = docker_environment()
    name = run(["docker", "context", "show"], env=env, capture=True).stdout.strip()
    metadata = json.loads(run(["docker", "context", "inspect", name], env=env, capture=True).stdout)
    endpoint = metadata[0]["Endpoints"]["docker"]["Host"]
    if not isinstance(endpoint, str) or not endpoint.startswith("unix:///"):
        raise ValueError("local Observe requires a local Unix-socket Docker context; remote daemons are refused")
    return ["docker", "--context", name]


def state_fingerprint(state: Path) -> str:
    credentials = initialize(state)
    material = json.dumps({"state": str(state.resolve()), "credentials": credentials}, sort_keys=True).encode()
    return hashlib.sha256(material + (state / "portal-public.pem").read_bytes()).hexdigest()


def guard_state(state: Path, docker: list[str], env: dict, create: bool = False) -> None:
    """Bind fixed project/volume names to one durable credential directory."""
    name = PROFILE + "-state-binding"
    label = "io.barbarossa.observe.state"
    expected = state_fingerprint(state)
    try:
        raw = run([*docker, "volume", "inspect", name], env=env, capture=True).stdout
    except subprocess.CalledProcessError:
        names = run([*docker, "volume", "ls", "--format", "{{.Name}}", "--filter", "name=" + PROFILE + "-"], env=env, capture=True).stdout.splitlines()
        if any(value.startswith(PROFILE + "-") for value in names):
            raise ValueError("existing profile volumes have no state binding; restore the original binding before mutation") from None
        if not create:
            raise ValueError("profile state is not bound; initialize it with build or up before this operation") from None
        run([*docker, "volume", "create", "--label", label + "=" + expected, name], env=env, capture=True)
        raw = run([*docker, "volume", "inspect", name], env=env, capture=True).stdout
    metadata = json.loads(raw)
    if len(metadata) != 1 or (metadata[0].get("Labels") or {}).get(label) != expected:
        raise ValueError("this profile belongs to another credential directory; refusing to alter its services or volumes")


def compose(state: Path, *args: str, **kwargs):
    kwargs["env"] = docker_environment(kwargs.get("env"))
    docker = local_docker()
    if args and args[0] in {"build", "up", "down", "run", "exec", "start", "stop", "restart"}:
        guard_state(state, docker, kwargs["env"], args[0] in {"build", "up"})
    if args and args[0] == "build":
        name = docker[-1]
        details = run([*docker, "buildx", "inspect", name], env=kwargs["env"], capture=True).stdout
        fields = [line.strip().split(":", 1) for line in details.splitlines() if ":" in line]
        drivers = [value.strip() for key, value in fields if key == "Driver"]
        endpoints = [value.strip() for key, value in fields if key == "Endpoint"]
        if drivers != ["docker"] or endpoints != [name]:
            raise ValueError("source build requires the selected local Docker context-backed builder")
        # Invoke Buildx directly: Compose may lose its global context when
        # selecting a context-backed builder. A YAML suffix selects its Compose
        # parser; JSON is also valid YAML. Grant only selected source contexts.
        document = json.loads((state / "compose.json").read_text())
        selected = list(args[1:]) or [key for key, value in document["services"].items() if value.get("build")]
        contexts = set()
        for service in selected:
            if service not in document["services"] or not document["services"][service].get("build"):
                raise ValueError("build requires a named source service")
            build = document["services"][service]["build"]
            context = Path(build["context"] if isinstance(build, dict) else build)
            if not context.is_absolute() or not context.is_dir():
                raise ValueError("build context must be an existing local source directory")
            contexts.add(str(context.resolve()))
        build_file = state / "compose.build.yaml"
        private_write(build_file, json.dumps(document))
        return run([*docker, "buildx", "bake", "--builder", name, "-f", str(build_file),
                    *["--allow=fs.read=" + path for path in sorted(contexts)], "--load", *selected], **kwargs)
    return run([*docker, "compose", "-p", PROFILE, "-f", str(state / "compose.json"), *args], **kwargs)


def render(state: Path, roots: dict[str, Path]) -> dict:
    credentials = initialize(state)
    env = {key: os.environ[key] for key in ("HOME", "PATH", "USER", "TMPDIR") if key in os.environ}
    env.update(credentials)
    # Identity parameters match the immutable generated realm. Inherited shell
    # settings must not silently select another realm, client or store.
    env.update(KEYCLOAK_REALM="synchronised-platform", KEYCLOAK_CLIENT_ID="portal-backend")
    if not (state / "knowledge-context.json").exists():
        private_write(state / "knowledge-context.json", "[]\n")
    if not (state / "realm.json").exists():
        run([sys.executable, str(roots["portal"] / "scripts/local_observe_realm.py"), "--output", str(state / "realm.json")], env=env)
    files = {
        "omniscience": ["deploy/compose/management-readonly-local/compose.yaml", "deploy/compose/management-readonly-local/compose.source.yaml", "deploy/compose/management-local-observe-v1/compose.yaml"],
        "barbarossa": ["deploy/compose/management-local-observe-v1/compose.yaml"],
        "portal": ["infra/compose/management-readonly-local/compose.yaml", "infra/compose/management-readonly-local/compose.source.yaml", "infra/compose/management-local-observe-v1/compose.yaml"],
    }
    fragments = []
    for owner, paths in files.items():
        cmd = [*local_docker(), "compose", "--env-file", "/dev/null", "-p", PROFILE]
        for path in paths:
            cmd.extend(["-f", str(roots[owner] / path)])
        cmd.extend(["config", "--format", "json"])
        fragments.append(json.loads(run(cmd, env=docker_environment(env), capture=True).stdout))
    document = merge_fragments(fragments)
    private_write(state / "compose.json", json.dumps(document, indent=2) + "\n")
    private_write(state / "roots.json", json.dumps({key: str(value) for key, value in roots.items()}, indent=2))
    return document


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url: str, token=None, body=None):
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("bootstrap may only read the fixed numeric loopback owner")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=None if body is None else json.dumps(body).encode(), headers=headers)
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=15) as response:
        raw = response.read(512 * 1024 + 1)
        if len(raw) > 512 * 1024:
            raise ValueError("bootstrap owner reply exceeds limit")
        return json.loads(raw)


def verify_topology(payload, name: str) -> None:
    expected = {f"service://observe-{name}-worker", f"service://observe-{name}-api"}
    foreign_name, foreign_id = ("beta", BETA) if name == "alpha" else ("alpha", ALPHA)
    serialized = json.dumps(payload)
    if f"observe-{foreign_name}-" in serialized or foreign_id in serialized:
        raise ValueError("workspace topology contains foreign evidence")
    if not isinstance(payload, dict) or payload.get("seed_entity_id") != f"service://observe-{name}-database" or payload.get("action_type") != "restart":
        raise ValueError("workspace topology identity verification failed")
    impacted = payload.get("impacted")
    if not isinstance(impacted, list) or len(impacted) != len(expected) or any(not isinstance(item, dict) or item.get("entity_type") != "service" or not isinstance(item.get("entity_id"), str) for item in impacted):
        raise ValueError("workspace topology impacted contract invalid")
    if {item.get("entity_id") for item in impacted} != expected:
        raise ValueError("workspace topology dependent verification failed")


def bootstrap(state: Path) -> None:
    """Seed owners; independently verify scoped reads before mapping tenants."""
    from datetime import datetime, timedelta, timezone
    credentials = initialize(state)
    guard_state(state, local_docker(), docker_environment())
    env = {**os.environ, "OMNISCIENCE_LOCAL_OBSERVE_BROKER_TOKEN": credentials["KV_OMNISCIENCE_BROKER_ADMIN_CREDENTIAL"]}
    seeded = compose(state, "exec", "-T", "-e", "OMNISCIENCE_LOCAL_OBSERVE_BROKER_TOKEN", "omniscience-api", "python", "-m", "omniscience_server.local_observe", env=env, capture=True)
    # Persist no token-bearing response. The owner bootstrap receipt is safe topology.
    private_write(state / "omniscience-bootstrap.log", seeded.stdout)
    base = "http://127.0.0.1:" + credentials["OMNISCIENCE_OBSERVE_API_PORT"]
    evidence = []
    prepared_context = []
    for workspace, name, foreign in ((ALPHA, "alpha", "beta"), (BETA, "beta", "alpha")):
        issued = request_json(base + "/api/v1/tokens/profiles/omniscience-mcp-read-v1", credentials["KV_OMNISCIENCE_BROKER_ADMIN_CREDENTIAL"], {"name": "observe-qualification-" + name, "workspace_id": workspace, "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=600)).isoformat()})
        token = issued["secret"]
        own = request_json(base + f"/api/v1/blast-radius?entity_id=service://observe-{name}-database&action=restart", token)
        verify_topology(own, name)
        try:
            request_json(base + f"/api/v1/blast-radius?entity_id=service://observe-{foreign}-database&action=restart", token)
        except HTTPError as error:
            if error.code != 404:
                raise ValueError("foreign workspace verification must return 404") from error
        else:
            raise ValueError("foreign workspace data was disclosed")
        # The entitlement attests a stable binding, not the owner's changing
        # as_of timestamp. Reruns verify the live read again and retain the same
        # identity receipt; the raw reading remains separate audit evidence.
        private_write(state / f"workspace-{name}-latest-reading.json", json.dumps(own))
        evidence.append({"workspace_id": workspace,
                         "verified_subject": f"service://observe-{name}-database",
                         "verified_dependents": [f"service://observe-{name}-worker", f"service://observe-{name}-api"],
                         "foreign_status": 404})
        if workspace == ALPHA:
            knowledge = request_json(base + "/api/v1/search", token, {"query": "Local platform observation runbook", "top_k": 10})
            candidates = [hit for hit in knowledge.get("hits", [])
                          if hit.get("citation", {}).get("uri") == f"fixture://{PROFILE}/alpha/platform.md"]
            if knowledge.get("degraded_subsystems") or len(candidates) != 1:
                raise ValueError("prepared platform knowledge unavailable or ambiguous")
            content = candidates[0]["text"]
            if not isinstance(content, str) or not content.strip() or len(content.encode()) > 8000 or any(ord(c) < 32 and c not in "\n\t" for c in content):
                raise ValueError("prepared platform knowledge invalid")
            observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            revision = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
            identity = hashlib.sha256((content + "\0" + observed).encode()).hexdigest()
            prepared_context = [{"id": "knowledge-" + identity, "revision": revision,
                                 "observed_at": observed, "source": "omniscience",
                                 "workspace_id": ALPHA, "content": content}]
    encoded = json.dumps(evidence, sort_keys=True).encode()
    reference = "sha256:" + hashlib.sha256(encoded).hexdigest()
    private_write(state / "workspace-verification.json", encoded)
    receipt = {"workspace_ids": [ALPHA, BETA], "verification_ref": reference}
    compose(state, "exec", "-T", "portal-backend", "python", "-m", "app.local_observe.bootstrap", "mappings", input=json.dumps(receipt))
    private_write(state / "knowledge-context.json", json.dumps(prepared_context))
    # Apply the selected source image's additive schema before refreshing API.
    compose(state, "run", "--rm", "--no-deps", "barbarossa-migrate")
    # Recreate refreshes the read-only bind after atomic file replacement.
    compose(state, "up", "-d", "--no-build", "--no-deps", "--force-recreate", "barbarossa-api")
    print("Two workspaces verified; tenant mappings installed. Receipt:", reference)


def stop(state: Path) -> None:
    guard_state(state, local_docker(), docker_environment())
    stop_runner(state)
    compose(state, "down")


def stop_runner(state: Path) -> None:
    pidfile = state / "runner.pid.json"
    if not pidfile.exists():
        return
    record = json.loads(pidfile.read_text())
    current = subprocess.run(["ps", "-ww", "-p", str(record["pid"]), "-o", "lstart=", "-o", "command="], capture_output=True, text=True, check=False)
    if current.returncode == 1 and not current.stdout.strip():
        pidfile.unlink()
        return
    if current.returncode != 0 or current.stdout.strip() != record["identity"]:
        raise ValueError("runner process identity changed; refusing to signal it")
    os.killpg(record["pid"], signal.SIGTERM)
    for _ in range(50):
        try:
            os.kill(record["pid"], 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        raise ValueError("runner did not stop within five seconds; its supervisor still holds the host lock")
    pidfile.unlink()


def start_runner(state: Path, root: Path, retain_failed_result: bool = False) -> None:
    initialize(state)
    guard_state(state, local_docker(), docker_environment())
    pidfile = state / "runner.pid.json"
    if pidfile.exists():
        raise ValueError("runner already recorded; use status or stop-runner before starting")
    binary = state / "barbarossa-codex-runner"
    env = {name: os.environ[name] for name in ("HOME", "PATH", "USER", "TMPDIR") if name in os.environ}
    run(["go", "build", "-trimpath", "-o", str(binary), "./cmd/barbarossa-codex-runner"],
        cwd=root, env={**env, "GOCACHE": str(root / ".cache/go-build")})
    codex = shutil.which("codex")
    if not codex:
        raise ValueError("Codex CLI is not installed")
    run([str(binary), "-codex", codex, "-preflight"], env=env)
    log_path = state / "runner.log"
    ready_path = state / "runner.ready.json"
    ready_path.unlink(missing_ok=True)
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    diagnostics = ["-failed-result-file", str(state / f"failed-model-response-{time.time_ns()}.json")] if retain_failed_result else []
    with os.fdopen(fd, "ab") as log:
        process = subprocess.Popen([str(binary), "-codex", codex, "-credential-file", str(state / "runner.token"), "-ready-file", str(ready_path), *diagnostics],
                                   env=env, cwd=state, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=log, start_new_session=True)
    for _ in range(40):
        if process.poll() is not None:
            raise ValueError("runner failed during startup; inspect its private log")
        if ready_path.exists():
            ready = json.loads(ready_path.read_text())
            if ready.get("ready") is True and ready.get("pid") == process.pid:
                break
        time.sleep(0.5)
    else:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
        raise ValueError("runner has not confirmed its host lock and queue contact")
    identity = run(["ps", "-ww", "-p", str(process.pid), "-o", "lstart=", "-o", "command="], capture=True).stdout.strip()
    private_write(pidfile, json.dumps({"pid": process.pid, "identity": identity}))
    print("Host runner started; credentials stay on the host.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "render", "build", "up", "bootstrap", "start-runner", "activate", "status", "stop", "stop-runner"))
    parser.add_argument("--state", type=Path, default=Path(__file__).resolve().parents[1] / ".local-observe/runtime")
    parser.add_argument("--omniscience", type=Path)
    parser.add_argument("--barbarossa", type=Path)
    parser.add_argument("--portal", type=Path)
    parser.add_argument("--service", action="append", default=[], help="Build only a named service; repeatable")
    parser.add_argument("--retain-failed-result", action="store_true", help="Privately retain the first bounded rejected model response for qualification")
    args = parser.parse_args()
    state = args.state.resolve()
    common = Path(run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=Path(__file__).resolve().parents[1], capture=True).stdout.strip())
    base = common.parent.parent
    roots = {name: (getattr(args, name) or base / repo / ".worktrees/local-observe-v1").resolve() for name, repo in (("omniscience", "Omniscience"), ("barbarossa", "Barbarossa"), ("portal", "platform-portal"))}
    if args.command == "init":
        initialize(state)
        print(f"Local credentials initialized at {state}; values are not printed.")
    elif args.command == "render":
        document = render(state, roots)
        print(f"Validated isolated profile: {len(document['services'])} services, {len(document['volumes'])} preserved volumes")
    elif args.command == "build":
        render(state, roots)
        compose(state, "build", *args.service)
    elif args.command == "up":
        render(state, roots)
        compose(state, "up", "-d", "--no-build")
    elif args.command == "bootstrap":
        bootstrap(state)
    elif args.command == "start-runner":
        start_runner(state, roots["barbarossa"], args.retain_failed_result)
    elif args.command == "activate":
        render(state, roots)
        compose(state, "up", "-d", "--no-build", "--wait", "--wait-timeout", "180")
        bootstrap(state)
        start_runner(state, roots["barbarossa"], args.retain_failed_result)
    elif args.command == "status":
        compose(state, "ps")
    elif args.command == "stop-runner":
        stop_runner(state)
    else:
        stop(state)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"Local profile command failed (exit {error.returncode}); inspect owner logs. No credentials printed.", file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
