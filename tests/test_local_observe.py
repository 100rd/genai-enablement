"""Safety invariants for the source-only local profile launcher."""
import importlib.util
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization

SPEC = importlib.util.spec_from_file_location("local_observe", Path(__file__).parents[1] / "scripts/local_observe.py")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


def test_init_preserves_identity_and_credentials(tmp_path):
    state = tmp_path / "state"
    first = launcher.initialize(state)
    before = {p.name: p.read_bytes() for p in state.iterdir() if p.is_file()}
    assert launcher.initialize(state) == first
    assert before == {p.name: p.read_bytes() for p in state.iterdir() if p.is_file()}
    assert len({first[k] for k in launcher.SECRET_KEYS}) == len(launcher.SECRET_KEYS)
    assert (state.stat().st_mode & 0o777) == 0o700
    assert all((p.stat().st_mode & 0o777) == 0o600 for p in state.iterdir())
    private = serialization.load_pem_private_key((state / "portal-private.pem").read_bytes(), None)
    public = serialization.load_pem_public_key((state / "portal-public.pem").read_bytes())
    public.verify(private.sign(b"local profile"), b"local profile")
    assert (state / "runner.token").read_text().strip() != (state / "probe.token").read_text().strip()


def test_partial_state_never_rotates_passwords(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "runner.token").write_text("existing")
    with pytest.raises(ValueError, match="incomplete"):
        launcher.initialize(state)
    assert (state / "runner.token").read_text() == "existing"


def test_composition_preserves_owner_network_boundaries():
    common = {"networks": {"omniscience-readnet": {"name": "management-local-observe-v1-omniscience-readnet"}}}
    omni = {**common, "services": {"omniscience-api": {"networks": {"omniscience-readnet": {}}}}, "volumes": {"omniscience-pgdata": {"name": "management-local-observe-v1-omniscience-pgdata"}}}
    portal = {"networks": {"omniscience-readnet": {"name": "management-local-observe-v1-omniscience-readnet", "external": True}}, "services": {"portal-backend": {"networks": {"omniscience-readnet": {}}}}}
    merged = launcher.merge_fragments([omni, portal])
    assert merged["name"] == "management-local-observe-v1"
    assert not merged["networks"]["omniscience-readnet"].get("external")
    assert "omniscience-private" not in merged["services"]["portal-backend"]["networks"]
    with pytest.raises(ValueError, match="duplicate service"):
        launcher.merge_fragments([omni, omni])


def test_composition_rejects_old_volumes_and_published_stores():
    with pytest.raises(ValueError, match="isolated"):
        launcher.merge_fragments([{"volumes": {"data": {"name": "old-data"}}}])
    with pytest.raises(ValueError, match="store"):
        launcher.merge_fragments([{"services": {"portal-postgres": {"ports": [{"host_ip": "127.0.0.1", "target": 5432, "published": "5432"}]}}}])


def test_stop_preserves_volumes_and_does_not_touch_other_projects(tmp_path, monkeypatch):
    calls = []
    state = tmp_path / "state"
    launcher.initialize(state)
    launcher.private_write(state / "compose.json", json.dumps({"name": launcher.PROFILE}))
    monkeypatch.setattr(launcher, "local_docker", lambda: ["docker"])
    monkeypatch.setattr(launcher, "guard_state", lambda *args: None)
    monkeypatch.setattr(launcher, "run", lambda args, **kw: calls.append(args))
    launcher.stop(state)
    assert calls == [["docker", "compose", "-p", launcher.PROFILE, "-f", str(state / "compose.json"), "down"]]
    assert (state / "runner.token").exists()


def test_bootstrap_rechecks_owner_without_rotating_mapping_receipt(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from urllib.error import HTTPError
    state = tmp_path / "state"
    launcher.initialize(state)
    monkeypatch.setattr(launcher, "local_docker", lambda: ["docker"])
    monkeypatch.setattr(launcher, "guard_state", lambda *args: None)
    receipts = []
    nonce = [0]

    def compose(_state, *args, **kwargs):
        if "input" in kwargs:
            receipts.append(json.loads(kwargs["input"]))
        return SimpleNamespace(stdout="{}")

    def request(url, token=None, body=None):
        if url.endswith("/api/v1/search"):
            return {"hits": [{"text": "Local platform observation runbook.", "citation": {"uri": f"fixture://{launcher.PROFILE}/alpha/platform.md"}}], "degraded_subsystems": []}
        if body is not None:
            return {"secret": "alpha" if body["workspace_id"] == launcher.ALPHA else "beta"}
        own = f"observe-{token}-database" in url
        if not own:
            raise HTTPError(url, 404, "not found", {}, None)
        nonce[0] += 1
        return {"seed_entity_id": f"service://observe-{token}-database", "action_type": "restart", "effective_as_of": str(nonce[0]), "impacted": [{"entity_id": f"service://observe-{token}-{component}", "entity_type": "service"} for component in ("worker", "api")]}

    monkeypatch.setattr(launcher, "compose", compose)
    monkeypatch.setattr(launcher, "request_json", request)
    launcher.bootstrap(state)
    launcher.bootstrap(state)
    assert nonce[0] == 4  # Both workspaces genuinely reverified on each run.
    assert receipts[0] == receipts[1]


def test_remote_docker_context_rejected_before_compose(monkeypatch):
    from types import SimpleNamespace
    calls = []
    def fake(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout="remote" if args[-1] == "show" else json.dumps([{"Endpoints": {"docker": {"Host": "tcp://example.invalid:2376"}}}]))
    monkeypatch.setattr(launcher, "run", fake)
    with pytest.raises(ValueError, match="local Unix-socket"):
        launcher.local_docker()
    assert all("compose" not in args for args in calls)


def test_broker_redirect_and_proxy_inheritance_are_disabled(monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from urllib.error import HTTPError
    leaked = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/start":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/leak")
                self.end_headers()
            else:
                leaked.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
        monkeypatch.setenv("no_proxy", "")
        with pytest.raises(HTTPError) as error:
            launcher.request_json(f"http://127.0.0.1:{server.server_port}/start", "broker-secret")
        assert error.value.code == 302
        assert leaked == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_build_pins_local_builder_and_limits_source_access(tmp_path, monkeypatch):
    from types import SimpleNamespace
    source = tmp_path / "source"
    source.mkdir()
    state = tmp_path / "state"
    launcher.initialize(state)
    launcher.private_write(state / "compose.json", json.dumps({"services": {"api": {"build": {"context": str(source)}}}}))
    monkeypatch.setattr(launcher, "local_docker", lambda: ["docker", "--context", "local"])
    monkeypatch.setattr(launcher, "guard_state", lambda *args: None)
    monkeypatch.setenv("BUILDX_BUILDER", "remote-builder")
    monkeypatch.setenv("BUILDKIT_HOST", "tcp://example.invalid:1234")
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout="Driver: docker\nEndpoint: local\n")
    monkeypatch.setattr(launcher, "run", run)
    launcher.compose(state, "build", "api")
    args, kwargs = calls[-1]
    assert args[:6] == ["docker", "--context", "local", "buildx", "bake", "--builder"]
    assert "--allow=fs.read=" + str(source) in args
    assert args[-2:] == ["--load", "api"]
    assert "BUILDX_BUILDER" not in kwargs["env"] and "BUILDKIT_HOST" not in kwargs["env"]
    assert (state / "compose.build.yaml").stat().st_mode & 0o777 == 0o600
    calls.clear()
    def remote(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout="Driver: remote\nEndpoint: tcp://remote.invalid\n")
    monkeypatch.setattr(launcher, "run", remote)
    with pytest.raises(ValueError, match="local Docker context-backed"):
        launcher.compose(state, "build", "api")
    assert len(calls) == 1 and "bake" not in calls[0]


def test_runner_exiting_before_queue_ready_is_not_reported_started(tmp_path, monkeypatch):
    from types import SimpleNamespace
    state = tmp_path / "state"
    launcher.initialize(state)
    monkeypatch.setattr(launcher, "local_docker", lambda: ["docker"])
    monkeypatch.setattr(launcher, "guard_state", lambda *args: None)
    monkeypatch.setattr(launcher, "run", lambda *args, **kwargs: SimpleNamespace(stdout=""))
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "/local/codex")
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: SimpleNamespace(poll=lambda: 1))
    with pytest.raises(ValueError, match="failed during startup"):
        launcher.start_runner(state, tmp_path)
    assert not (state / "runner.pid.json").exists()


def test_topology_receipt_requires_actual_scoped_entities():
    with pytest.raises(ValueError):
        launcher.verify_topology({"error": "observe-alpha-worker observe-alpha-api", "impacted": []}, "alpha")
    valid = {"seed_entity_id": "service://observe-alpha-database", "action_type": "restart", "impacted": [{"entity_id": "service://observe-alpha-" + name, "entity_type": "service"} for name in ("worker", "api")]}
    launcher.verify_topology(valid, "alpha")
    with pytest.raises(ValueError, match="foreign evidence"):
        launcher.verify_topology({**valid, "metadata": {"leak": "service://observe-beta-database"}}, "alpha")
    for field, value in (("seed_entity_id", "service://observe-beta-database"), ("action_type", "delete"), ("impacted", [valid["impacted"][0]] * 2)):
        with pytest.raises(ValueError):
            launcher.verify_topology({**valid, field: value}, "alpha")


def test_profile_binding_rejects_other_state_and_unbound_existing_data(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import subprocess
    first, second = tmp_path / "first", tmp_path / "second"
    launcher.initialize(first)
    launcher.initialize(second)
    labels = {"io.barbarossa.observe.state": launcher.state_fingerprint(first)}
    monkeypatch.setattr(launcher, "run", lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps([{"Labels": labels}])))
    launcher.guard_state(first, ["docker"], {})
    with pytest.raises(ValueError, match="another credential directory"):
        launcher.guard_state(second, ["docker"], {})
    calls = []
    def unbound(args, **kwargs):
        calls.append(args)
        if "inspect" in args:
            raise subprocess.CalledProcessError(1, args)
        return SimpleNamespace(stdout=launcher.PROFILE + "-portal-pgdata\n")
    monkeypatch.setattr(launcher, "run", unbound)
    with pytest.raises(ValueError, match="no state binding"):
        launcher.guard_state(first, ["docker"], {})
    assert all("create" not in args for args in calls)
