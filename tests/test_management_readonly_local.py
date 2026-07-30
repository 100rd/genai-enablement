"""Tests for the SP-98 assembled management-readonly-local-v1 integrator
(task-sp-98, ADR-0024).

Two tiers, kept honestly separate:

  * SIBLING-INDEPENDENT tests run everywhere (CI included): the env generator's
    safety contract, .env.example coverage, fixture well-formedness, the
    assembled Compose files' static shape, and the qualifier's pure functions.

  * DOCKER+SIBLING tests skip when Docker or the owner fragments are absent
    (as in CI, where the three owner repos are not checked out). They exercise
    the full rendered model and the deterministic receipt.

Every assertion targets an observable invariant that can fail before the
implementation is correct — never a constant-true tautology.
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
COMPOSE_DIR = ROOT / "deploy" / "local" / "management-readonly-v1"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "management-readonly-local-v1"

sys.path.insert(0, str(SCRIPTS))

gen = importlib.import_module("generate_management_readonly_local_env")
qual = importlib.import_module("qualify_management_readonly_local")


# ---------------------------------------------------------------------------
# Skip helpers.
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return (
            subprocess.run(
                ["docker", "info"], capture_output=True, timeout=15, check=False
            ).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


def _siblings_present() -> bool:
    return (
        (qual.OMNI_FRAGMENT_DIR / "compose.yaml").exists()
        and (qual.BARB_FRAGMENT_DIR / "compose.yaml").exists()
        and (qual.PORTAL_FRAGMENT_DIR / "compose.yaml").exists()
    )


requires_stack = pytest.mark.skipif(
    not (_docker_available() and _siblings_present()),
    reason="requires Docker and the three owner fragments (absent in CI)",
)


# ---------------------------------------------------------------------------
# Env generator — AC-SP98-9 safety contract (sibling-independent).
# ---------------------------------------------------------------------------


def test_env_example_declares_every_secret_var():
    keys = qual._env_keys(qual.ENV_EXAMPLE)
    assert set(gen.SECRET_VARS) <= keys, (
        "every generator SECRET_VAR must appear in .env.example"
    )


def test_env_example_covers_all_required_variables():
    keys = qual._env_keys(qual.ENV_EXAMPLE)
    missing = qual.required_env_variables() - keys
    assert not missing, f".env.example is missing required variables: {sorted(missing)}"


def test_env_example_contains_no_real_secret_value():
    # Committed placeholders must be labeled non-secrets, never a high-entropy value.
    for line in qual.ENV_EXAMPLE.read_text().splitlines():
        s = line.strip()
        if s.startswith("#") or "=" not in s:
            continue
        key, _, value = s.partition("=")
        if key.strip() in gen.SECRET_VARS:
            assert value.startswith("change-me"), (
                f"{key} must ship a labeled placeholder, got {value!r}"
            )


def test_render_env_randomizes_secrets_and_copies_config():
    template = qual.ENV_EXAMPLE.read_text()
    text_a, assigned = gen.render_env(template)
    text_b, _ = gen.render_env(template)
    assert assigned == sorted(gen.SECRET_VARS)

    def secrets_of(text: str) -> dict[str, str]:
        return {
            ln.partition("=")[0].strip(): ln.partition("=")[2]
            for ln in text.splitlines()
            if "=" in ln and ln.partition("=")[0].strip() in gen.SECRET_VARS
        }

    sa, sb = secrets_of(text_a), secrets_of(text_b)
    for k in gen.SECRET_VARS:
        assert len(sa[k]) >= 32, f"{k} entropy too low"
        assert sa[k] != sb[k], f"{k} must be randomized across runs"
    # Non-secret (config-coupled) lines are copied verbatim and stably.
    conf_a = [
        ln
        for ln in text_a.splitlines()
        if "=" in ln and ln.partition("=")[0].strip() not in gen.SECRET_VARS
    ]
    conf_b = [
        ln
        for ln in text_b.splitlines()
        if "=" in ln and ln.partition("=")[0].strip() not in gen.SECRET_VARS
    ]
    assert conf_a == conf_b


def test_generate_writes_0600_and_reports_no_secret_value(tmp_path, capsys):
    env_file = tmp_path / ".env"
    assigned = gen.generate(template=qual.ENV_EXAMPLE, env_file=env_file)
    assert env_file.exists()
    assert oct(env_file.stat().st_mode & 0o777) == "0o600"
    written = env_file.read_text()
    secret_values = [
        ln.partition("=")[2]
        for ln in written.splitlines()
        if "=" in ln and ln.partition("=")[0].strip() in gen.SECRET_VARS
    ]
    # main() prints only names; call it and assert no secret value leaks.
    old = sys.argv
    try:
        sys.argv = ["prog", "--env-file", str(tmp_path / ".env2")]
        gen.main()
    finally:
        sys.argv = old
    out = capsys.readouterr()
    console = out.out + out.err
    for v in secret_values:
        assert v not in console, "a secret value leaked to the console"
    assert set(assigned) == set(gen.SECRET_VARS)


def test_generate_refuses_to_overwrite(tmp_path):
    env_file = tmp_path / ".env"
    gen.generate(template=qual.ENV_EXAMPLE, env_file=env_file)
    with pytest.raises(gen.EnvGenerationError, match="refusing to overwrite"):
        gen.generate(template=qual.ENV_EXAMPLE, env_file=env_file)


def test_generate_force_requires_confirmation_token(tmp_path):
    env_file = tmp_path / ".env"
    gen.generate(template=qual.ENV_EXAMPLE, env_file=env_file)
    with pytest.raises(gen.EnvGenerationError, match="confirmation token"):
        gen.generate(
            template=qual.ENV_EXAMPLE, env_file=env_file, force=True, confirmed=False
        )
    original = env_file.read_text()
    gen.generate(
        template=qual.ENV_EXAMPLE, env_file=env_file, force=True, confirmed=True
    )
    assert env_file.read_text() != original, "confirmed force must rotate the secrets"


# ---------------------------------------------------------------------------
# Assembled Compose files — static shape (sibling-independent).
# ---------------------------------------------------------------------------


def test_compose_base_is_include_only_no_owner_services():
    yaml = pytest.importorskip("yaml")
    model = yaml.safe_load(qual.COMPOSE_BASE.read_text())
    assert "services" not in model, (
        "the assembled compose declares no owner service itself (MLC-4)"
    )
    assert "include" in model and len(model["include"]) == 3, (
        "must include exactly the three owner fragments"
    )
    # Network reconciliation makes the two read edges managed in the assembled project.
    nets = model["networks"]
    assert nets["omniscience-readnet"]["external"] is False
    assert nets["barbarossa-edge"]["external"] is False


def test_compose_includes_reference_the_exact_owner_fragments():
    text = qual.COMPOSE_BASE.read_text()
    assert "Omniscience/deploy/compose/management-readonly-local/compose.yaml" in text
    assert "barbarossa/deploy/compose/management-readonly-local/compose.yaml" in text
    assert (
        "platform-portal/infra/compose/management-readonly-local/compose.yaml" in text
    )


def test_compose_files_have_no_hardcoded_public_binding():
    for path in (qual.COMPOSE_BASE, qual.COMPOSE_SOURCE):
        for line in path.read_text().splitlines():
            if "0.0.0.0" in line:
                pytest.fail(
                    f"{path.name} publishes a non-loopback binding: {line.strip()}"
                )


# ---------------------------------------------------------------------------
# Fixtures — well-formedness (sibling-independent).
# ---------------------------------------------------------------------------


def test_expected_topology_matches_profile_inventory():
    fx = json.loads((FIXTURE_DIR / "expected-topology.json").read_text())
    assert set(fx["steady_services"]) == set(qual.EXPECTED_STEADY_SERVICES)
    assert set(fx["oneshot_services"]) == set(qual.EXPECTED_ONESHOT_SERVICES)
    assert set(fx["portal_backend_networks"]) == set(
        qual.PORTAL_BACKEND_ALLOWED_NETWORKS
    )


def test_tenant_pw0_matrix_never_lists_a_forbidden_outcome_as_expected():
    fx = json.loads((FIXTURE_DIR / "tenant-pw0-no-effect.json").read_text())
    forbidden = set(fx["forbidden_outcomes"])
    for case in fx["cases"]:
        assert case["expected_outcome"] not in forbidden, (
            f"{case['id']} expects a forbidden favorable outcome"
        )


def test_severance_matrix_preserves_sibling_and_readiness():
    fx = json.loads((FIXTURE_DIR / "severance-recovery.json").read_text())
    for sc in fx["scenarios"]:
        assert sc["portal_readiness_preserved"] is True
        assert "unrelated_owner_preserved" in sc


# ---------------------------------------------------------------------------
# Qualifier pure functions (sibling-independent).
# ---------------------------------------------------------------------------


def test_reproducible_is_false_for_source_dirty_no_oci():
    omni = {"receipt_reproducible": False, "receipt_status": "RED"}
    barb = {"runtime_receipt_committed": False}
    portal = {"runtime_receipt_committed": False}
    assert qual.compute_reproducible(omni, barb, portal) is False


def test_ac8_pins_non_promotable_axes():
    core = {
        "availability_class": "development-single-host",
        "ha_qualified": False,
        "activation_authority": "none",
        "qualification_class": "functional-smoke-only",
        "reproducible": False,
        "qualification_status": "development-only",
    }
    assert qual.run_ac8(core)["status"] == "PASS"
    for bad_key, bad_val in [
        ("ha_qualified", True),
        ("activation_authority", "platform"),
        ("availability_class", "ha"),
    ]:
        broken = dict(core, **{bad_key: bad_val})
        assert qual.run_ac8(broken)["status"] == "RED", (
            f"AC-8 must RED when {bad_key} is promoted"
        )


def test_redact_model_masks_secret_values():
    model = {
        "services": {
            "x": {"environment": {"DB_PASSWORD": "hunter2", "LOG_LEVEL": "info"}}
        }
    }
    red = qual.redact_model(model)
    assert red["services"]["x"]["environment"]["DB_PASSWORD"] == qual.REDACTED
    assert red["services"]["x"]["environment"]["LOG_LEVEL"] == "info"


def test_live_acs_pending_without_capture():
    live_acs = qual.run_live_acs(None)
    assert set(live_acs) == {
        "AC-SP98-3",
        "AC-SP98-4",
        "AC-SP98-5",
        "AC-SP98-6",
        "AC-SP98-7",
    }
    for ac in live_acs.values():
        assert ac["status"] == "pending"
        assert ac["reason"] == "live_capture_absent"


def test_live_acs_type_host_capacity_insufficient():
    capture = {
        "host_capacity_insufficient": True,
        "capacity": {"required_mib": 8036, "available_mib": 5200},
    }
    live_acs = qual.run_live_acs(capture)
    assert live_acs["AC-SP98-7"]["status"] == "host_capacity_insufficient"
    assert live_acs["AC-SP98-7"]["measured_shortfall"]["available_mib"] == 5200


def test_live_capture_pass_is_only_from_explicit_observed_status():
    capture = {
        "acs": {"AC-SP98-4": {"status": "PASS", "evidence": {"omniscience_ready": 200}}}
    }
    live_acs = qual.run_live_acs(capture)
    assert live_acs["AC-SP98-4"]["status"] == "PASS"
    # An AC with no observed entry never becomes PASS.
    assert live_acs["AC-SP98-5"]["status"] == "pending"


def test_ac7_downgrades_to_partial_when_amd64_unmeasured():
    # A single-arch (arm64) capture cannot be a full AC-SP98-7 PASS, which
    # requires both amd64 AND arm64 — mirror how AC-3/4/5/6 stay partial.
    capture = {
        "acs": {
            "AC-SP98-7": {
                "status": "PASS",
                "evidence": {"arch": "arm64", "amd64": "pending (single host)"},
            }
        }
    }
    ac7 = qual.run_live_acs(capture)["AC-SP98-7"]
    assert ac7["status"] == "partial"
    assert ac7["pending_axes"] == ["amd64"]
    assert ac7["reason"] == "reference_arch_axis_unmeasured"


def test_ac7_stays_pass_only_when_both_arches_measured():
    capture = {
        "acs": {
            "AC-SP98-7": {
                "status": "PASS",
                "evidence": {"arch": "arm64", "amd64": "measured: 2.0 GiB steady"},
            }
        }
    }
    ac7 = qual.run_live_acs(capture)["AC-SP98-7"]
    assert ac7["status"] == "PASS"
    assert "pending_axes" not in ac7


# ---------------------------------------------------------------------------
# Full rendered model + deterministic receipt (docker + siblings required).
# ---------------------------------------------------------------------------


@requires_stack
def test_rendered_inventory_is_exactly_the_profile():
    model = qual.render_compose([qual.COMPOSE_BASE])
    services = set(model["services"])
    assert services == set(qual.EXPECTED_STEADY_SERVICES) | set(
        qual.EXPECTED_ONESHOT_SERVICES
    )
    for name in services | set(model["networks"]) | set(model["volumes"]):
        assert "mock" not in name.lower() and "omnius" not in name.lower()


@requires_stack
def test_host_bindings_are_exactly_three_loopback():
    model = qual.render_compose([qual.COMPOSE_BASE])
    assert qual.host_bindings(model) == qual.EXPECTED_HOST_BINDINGS


@requires_stack
def test_portal_backend_never_joins_an_owner_private_network():
    model = qual.render_compose([qual.COMPOSE_BASE])
    nets = qual.service_networks(model["services"]["portal-backend"])
    assert nets == qual.PORTAL_BACKEND_ALLOWED_NETWORKS
    assert not (nets & qual.OWNER_PRIVATE_NETWORKS)


@requires_stack
def test_deterministic_acs_pass_and_receipt_is_reproducible():
    r1 = qual.build_receipt()
    r2 = qual.build_receipt()
    for ac_id in ("AC-SP98-1", "AC-SP98-2", "AC-SP98-8", "AC-SP98-9"):
        assert r1["acceptance_criteria"][ac_id]["status"] == "PASS", ac_id
    assert r1["deterministic_status"] == "GREEN"
    assert r1["reproducible"] is False
    assert r1["ha_qualified"] is False
    assert r1["activation_authority"] == "none"
    assert r1["availability_class"] == "development-single-host"
    assert r1["receipt_digest"] == r2["receipt_digest"]


@requires_stack
def test_source_overlay_resolves_prebuilt_runnable_images():
    model = qual.render_compose([qual.COMPOSE_BASE, qual.COMPOSE_SOURCE])
    assert (
        model["services"]["omniscience-api"]["image"]
        == "omniscience-local/omniscience-server:source"
    )
    assert model["services"]["barbarossa-api"]["image"] == "barbarossa-api:mrl-v1"
    assert (
        model["services"]["portal-backend"]["image"] == "platform-portal-backend:latest"
    )
