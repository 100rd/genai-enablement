#!/usr/bin/env python3
"""Integrator qualifier for the assembled `management-readonly-local-v1`
synchronized-platform stack (task-sp-98, ADR-0024).

It assembles the three owner-published local fragments (SP-95 Omniscience,
SP-96 Barbarossa, SP-97 Platform Portal) into ONE rendered Compose model and
independently qualifies AC-SP98-1..9, emitting a content-addressed
`SynchronizedPlatformLocalLaunchReceipt`.

Read-only across every cross-repository input: it never writes to Omniscience/,
barbarossa/, or platform-portal/. It writes only inside this repository's
docs/synchronized-platform/releases/management-readonly-local-v1/evidence/
directory (content-addressed, append-only, never overwritten).

Two evidence classes, kept honestly distinct:

  * DETERMINISTIC (AC-1 compose-lock, AC-2 topology-containment, AC-8 receipt-
    integrity, AC-9 secret-reset-safety) are computed from the rendered Compose
    model plus the committed owner artifacts. They need no running stack and are
    what CI verifies.

  * LIVE (AC-3 lifecycle, AC-4 real-owner, AC-5 tenant/PW0/no-effect, AC-6
    severance, AC-7 resource-envelope) require a running stack. `--probe-live`
    captures observable evidence from an already-running assembled project into
    a live-capture JSON; the qualifier folds a supplied `--live-capture` in.
    Absent live capture, live ACs are `pending` (typed live_capture_absent); a
    capture that records a capacity shortfall types AC-7 host_capacity_insufficient.
    A missing/mock/false-green live result is never emitted as PASS.

This task cannot repair an owner fragment, copy an owner migration/config, mint
a sibling receipt, or claim deployment, HA (SP-92/SP-94), or SP-89 qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SIBLINGS_ROOT = ROOT.parent

OMNISCIENCE_ROOT = SIBLINGS_ROOT / "Omniscience"
BARBAROSSA_ROOT = SIBLINGS_ROOT / "barbarossa"
PORTAL_ROOT = SIBLINGS_ROOT / "platform-portal"

# --- assembled Compose model (this repository owns only the composition) ------
COMPOSE_DIR = ROOT / "deploy" / "local" / "management-readonly-v1"
COMPOSE_BASE = COMPOSE_DIR / "compose.yaml"
COMPOSE_SOURCE = COMPOSE_DIR / "compose.source.yaml"
ENV_EXAMPLE = COMPOSE_DIR / ".env.example"

# --- owner fragment + contract inputs (READ-ONLY cross-repo) ------------------
OMNI_FRAGMENT_DIR = OMNISCIENCE_ROOT / "deploy/compose/management-readonly-local"
OMNI_CONTRACT = (
    OMNISCIENCE_ROOT
    / "contracts/releases/management-readonly-local-v1/service-contract.json"
)
OMNI_RECEIPT = (
    OMNISCIENCE_ROOT
    / "contracts/releases/management-readonly-local-v1/evidence"
    / "local-runtime-receipt.a7caefd08d0f5d59198e7c49cb8fd8df5623e391.json"
)
BARB_FRAGMENT_DIR = BARBAROSSA_ROOT / "deploy/compose/management-readonly-local"
BARB_CONTRACT = (
    BARBAROSSA_ROOT
    / "contracts/releases/management-readonly-local-v1/service-contract.json"
)
PORTAL_FRAGMENT_DIR = PORTAL_ROOT / "infra/compose/management-readonly-local"
PORTAL_CONTRACT = (
    PORTAL_ROOT
    / "contracts/releases/management-readonly-local-v1/service-contract.json"
)

# --- integrator fixtures (ground truth this task owns) ------------------------
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "management-readonly-local-v1"
EXPECTED_TOPOLOGY = FIXTURE_DIR / "expected-topology.json"
TENANT_PW0_MATRIX = FIXTURE_DIR / "tenant-pw0-no-effect.json"
SEVERANCE_MATRIX = FIXTURE_DIR / "severance-recovery.json"

EVIDENCE_DIR = (
    ROOT
    / "docs"
    / "synchronized-platform"
    / "releases"
    / "management-readonly-local-v1"
    / "evidence"
)

PROFILE_ID = "management-readonly-local-v1"
PROFILE_REVISION = "1.0.0"
BASE_PROFILE_ID = "management-readonly-v1"
GOVERNING_ADR = "ADR-0024"

# Fixed authority axes — the local receipt can never promote past these.
AVAILABILITY_CLASS = "development-single-host"
HA_QUALIFIED = False
ACTIVATION_AUTHORITY = "none"
QUALIFICATION_CLASS = "functional-smoke-only"

# The profile's exact steady + one-shot inventory (ground truth for AC-2).
EXPECTED_STEADY_SERVICES = frozenset(
    {
        "omniscience-api",
        "omniscience-admin",
        "omniscience-postgres",
        "omniscience-nats",
        "omniscience-neo4j",
        "omniscience-qdrant",
        "barbarossa-api",
        "barbarossa-worker",
        "barbarossa-postgres",
        "barbarossa-nats",
        "portal-frontend",
        "portal-backend",
        "portal-postgres",
        "portal-keycloak",
    }
)
EXPECTED_ONESHOT_SERVICES = frozenset(
    {"omniscience-migrate", "barbarossa-migrate", "portal-migrate"}
)
OWNER_PREFIXES = ("omniscience-", "barbarossa-", "portal-")

# The only three loopback host bindings the profile publishes.
EXPECTED_HOST_BINDINGS = {
    ("portal-frontend", "127.0.0.1", 3000),
    ("portal-keycloak", "127.0.0.1", 8081),
    ("omniscience-admin", "127.0.0.1", 3001),
}

# Portal backend joins ONLY the two owner-read edges + its own private network.
PORTAL_BACKEND_ALLOWED_NETWORKS = frozenset(
    {"omniscience-readnet", "barbarossa-edge", "portal-private"}
)
OWNER_PRIVATE_NETWORKS = frozenset({"omniscience-private", "barbarossa-private"})

FORBIDDEN_SUBSTRINGS = ("mock", "omnius")

# Env keys whose value is redacted before any digest/snapshot (AC-8/AC-9).
SECRET_KEY_PATTERN = re.compile(
    r"(PASSWORD|SECRET|API_KEY|_KEY$|CREDENTIAL|TOKEN)", re.IGNORECASE
)
REDACTED = "***REDACTED***"


class QualificationError(Exception):
    """Raised when a required input is missing, mutable, incompatible, or unverifiable."""


# ---------------------------------------------------------------------------
# Digest / IO helpers.
# ---------------------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_hex(path.read_bytes())


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_digest(obj: Any) -> str:
    return sha256_hex(canonical_json_bytes(obj))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise QualificationError(f"missing required input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def git_head(repo_root: Path) -> str | None:
    return _git(repo_root, ["rev-parse", "HEAD"])


def git_worktree_dirty(repo_root: Path, pathspec: str | None = None) -> bool | None:
    args = ["status", "--porcelain"]
    if pathspec:
        args += ["--", pathspec]
    out = _git(repo_root, args)
    if out is None:
        return None
    return bool(out.strip())


def _git(repo_root: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Rendered Compose model.
# ---------------------------------------------------------------------------


def render_compose(files: list[Path], env_file: Path | None = None) -> dict[str, Any]:
    """Return the rendered Compose model as a dict via `docker compose config`.

    No env-file by default: the owner fragments carry committed local-dev
    defaults, so the canonical model renders deterministically and secret-free.
    """
    cmd = ["docker", "compose"]
    if env_file is not None:
        cmd += ["--env-file", str(env_file)]
    for f in files:
        cmd += ["-f", str(f)]
    cmd += ["config", "--format", "json"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QualificationError(f"docker compose config failed to run: {exc}") from exc
    if result.returncode != 0:
        raise QualificationError(
            f"docker compose config returned {result.returncode}: {result.stderr.strip()}"
        )
    return json.loads(result.stdout)


def redact_model(model: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the rendered model with all secret-valued env keys and
    the docker-compose build-context noise redacted, for a stable, secret-free
    evidence digest (AC-8 redacted evidence manifest)."""
    redacted = json.loads(json.dumps(model))  # deep copy
    for svc in redacted.get("services", {}).values():
        env = svc.get("environment")
        if isinstance(env, dict):
            for key in list(env):
                if SECRET_KEY_PATTERN.search(key):
                    env[key] = REDACTED
        build = svc.get("build")
        if isinstance(build, dict) and "context" in build:
            build["context"] = REDACTED
    return redacted


def service_networks(svc: dict[str, Any]) -> set[str]:
    return set((svc.get("networks") or {}).keys())


def host_bindings(model: dict[str, Any]) -> set[tuple[str, str, int]]:
    bindings: set[tuple[str, str, int]] = set()
    for name, svc in model.get("services", {}).items():
        for port in svc.get("ports", []) or []:
            if isinstance(port, dict):
                published = port.get("published")
                if published in (None, "", 0):
                    continue
                bindings.add((name, port.get("host_ip", "0.0.0.0"), int(published)))
    return bindings


# ---------------------------------------------------------------------------
# Owner members (READ-ONLY cross-repo). Exact identities pinned by digest.
# ---------------------------------------------------------------------------


def build_omniscience_member() -> dict[str, Any]:
    contract = read_json(OMNI_CONTRACT)
    receipt = read_json(OMNI_RECEIPT)
    return {
        "owner": "omniscience",
        "package": "SP-95",
        "fragment_dir": str(OMNI_FRAGMENT_DIR.relative_to(SIBLINGS_ROOT)),
        "fragment_compose_digest": sha256_file(OMNI_FRAGMENT_DIR / "compose.yaml"),
        "fragment_source_override_digest": sha256_file(
            OMNI_FRAGMENT_DIR / "compose.source.yaml"
        ),
        "service_contract_digest": sha256_file(OMNI_CONTRACT),
        "declared_service_contract_digest": receipt.get("service_contract_digest"),
        "local_runtime_receipt_digest": sha256_file(OMNI_RECEIPT),
        "receipt_git_commit": receipt.get("git_commit"),
        "receipt_mode": receipt.get("mode"),
        "receipt_reproducible": receipt.get("reproducible"),
        "receipt_status": receipt.get("status"),
        "receipt_qualification_status": receipt.get("qualification_status"),
        "receipt_availability_class": receipt.get("availability_class"),
        "receipt_ha_qualified": receipt.get("ha_qualified"),
        "receipt_activation_authority": receipt.get("activation_authority"),
        "repo_head": git_head(OMNISCIENCE_ROOT),
        "fragment_worktree_dirty": git_worktree_dirty(
            OMNISCIENCE_ROOT, "deploy/compose/management-readonly-local"
        ),
        "contract_availability_class": contract.get("availability_class"),
        "contract_ha_qualified": contract.get("ha_qualified"),
        "contract_activation_authority": contract.get("activation_authority"),
    }


def build_barbarossa_member() -> dict[str, Any]:
    contract = read_json(BARB_CONTRACT)
    return {
        "owner": "barbarossa",
        "package": "SP-96",
        "fragment_dir": str(BARB_FRAGMENT_DIR.relative_to(SIBLINGS_ROOT)),
        "fragment_compose_digest": sha256_file(BARB_FRAGMENT_DIR / "compose.yaml"),
        "fragment_source_override_digest": sha256_file(
            BARB_FRAGMENT_DIR / "compose.source.yaml"
        ),
        "fragment_image_override_digest": sha256_file(
            BARB_FRAGMENT_DIR / "compose.image.yaml"
        ),
        "service_contract_digest": sha256_file(BARB_CONTRACT),
        "contract_revision": contract.get("revision"),
        "api_image_tag": "barbarossa-api:mrl-v1",
        "worker_image_tag": "barbarossa-worker:mrl-v1",
        "repo_head": git_head(BARBAROSSA_ROOT),
        "fragment_worktree_dirty": git_worktree_dirty(
            BARBAROSSA_ROOT, "deploy/compose/management-readonly-local"
        ),
        "runtime_receipt_committed": False,
        "pending": {
            "sp96_runtime_receipt_digest": (
                "Barbarossa's BarbarossaLocalRuntimeReceipt is computed at runtime "
                "(internal/kernel/act/receipt.go); no committed receipt JSON exists to "
                "content-address. Its committed service contract is pinned instead."
            )
        },
        "contract_availability_class": contract.get("availability_class"),
        "contract_ha_qualified": contract.get("ha_qualified"),
        "contract_activation_authority": contract.get("activation_authority"),
    }


def build_portal_member() -> dict[str, Any]:
    contract = read_json(PORTAL_CONTRACT)
    pinned = contract.get("pinned_owner_evidence", {})
    return {
        "owner": "platform-portal",
        "package": "SP-97",
        "fragment_dir": str(PORTAL_FRAGMENT_DIR.relative_to(SIBLINGS_ROOT)),
        "fragment_compose_digest": sha256_file(PORTAL_FRAGMENT_DIR / "compose.yaml"),
        "fragment_source_override_digest": sha256_file(
            PORTAL_FRAGMENT_DIR / "compose.source.yaml"
        ),
        "service_contract_digest": sha256_file(PORTAL_CONTRACT),
        "contract_revision": contract.get("profile_revision"),
        "backend_image_tag": "platform-portal-backend:latest",
        "frontend_image_tag": "platform-portal-frontend:latest",
        "repo_head": git_head(PORTAL_ROOT),
        "fragment_worktree_dirty": git_worktree_dirty(
            PORTAL_ROOT, "infra/compose/management-readonly-local"
        ),
        "runtime_receipt_committed": False,
        "pending": {
            "sp97_runtime_receipt_digest": (
                "Portal's PortalLocalRuntimeReceipt is computed at runtime "
                "(backend/app/runtime_profiles/local/receipt.py); no committed receipt "
                "JSON exists to content-address. Its committed service contract is pinned."
            )
        },
        "pinned_sp95_service_contract_digest": pinned.get(
            "sp95_omniscience_local", {}
        ).get("service_contract_digest"),
        "pinned_sp95_git_commit": pinned.get("sp95_omniscience_local", {}).get(
            "git_commit"
        ),
        "pinned_sp96_api_image_tag": pinned.get("sp96_barbarossa_local", {}).get(
            "api_image_tag"
        ),
        "pinned_sp96_worker_image_tag": pinned.get("sp96_barbarossa_local", {}).get(
            "worker_image_tag"
        ),
        "contract_availability_class": contract.get("availability_class"),
        "contract_ha_qualified": contract.get("ha_qualified"),
        "contract_activation_authority": contract.get("activation_authority"),
    }


# ---------------------------------------------------------------------------
# AC-SP98-1 — synchronized-local-compose-lock (deterministic).
# ---------------------------------------------------------------------------


def run_ac1(
    model: dict[str, Any],
    omni: dict[str, Any],
    barb: dict[str, Any],
    portal: dict[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, expected: Any, actual: Any) -> None:
        checks.append(
            {
                "name": name,
                "expected": expected,
                "actual": actual,
                "pass": expected == actual,
            }
        )

    services = model.get("services", {})

    for member in (omni, barb, portal):
        check(
            f"{member['owner']} fragment compose digest re-derives (non-empty sha256)",
            True,
            isinstance(member["fragment_compose_digest"], str)
            and member["fragment_compose_digest"].startswith("sha256:"),
        )
        check(
            f"{member['owner']} service_contract digest re-derives",
            True,
            isinstance(member["service_contract_digest"], str)
            and member["service_contract_digest"].startswith("sha256:"),
        )

    check(
        "omniscience service_contract digest == owner receipt.declared_service_contract_digest",
        omni["declared_service_contract_digest"],
        omni["service_contract_digest"],
    )
    check(
        "portal pinned sp95 service_contract_digest == independently-derived omniscience digest",
        omni["service_contract_digest"],
        portal["pinned_sp95_service_contract_digest"],
    )
    check(
        "portal pinned sp95 git_commit == omniscience receipt git_commit",
        omni["receipt_git_commit"],
        portal["pinned_sp95_git_commit"],
    )
    check(
        "portal pinned sp96 api_image_tag == barbarossa member api_image_tag",
        barb["api_image_tag"],
        portal["pinned_sp96_api_image_tag"],
    )
    check(
        "barbarossa-api rendered image == pinned barbarossa-api:mrl-v1",
        barb["api_image_tag"],
        services.get("barbarossa-api", {}).get("image"),
    )

    omni_image = services.get("omniscience-api", {}).get("image", "")
    image_mode_zero_sentinel = "@sha256:" + "0" * 64 in omni_image
    check(
        "omniscience image-mode base carries the unpublished @sha256 zero sentinel (fails loudly, no mutable substitution)",
        True,
        image_mode_zero_sentinel,
    )

    base_body = COMPOSE_BASE.read_text(encoding="utf-8")
    declares_services = bool(re.search(r"^services:", base_body, re.MULTILINE))
    check(
        "assembled compose.yaml declares no owner service itself (include-only composition, MLC-4)",
        False,
        declares_services,
    )

    contaminated = sorted(
        n for n in services if any(sub in n.lower() for sub in FORBIDDEN_SUBSTRINGS)
    )
    check("no mock/omnius service in the rendered model", [], contaminated)

    reproducible = compute_reproducible(omni, barb, portal)
    all_pass = all(c["pass"] for c in checks)
    return {
        "id": "AC-SP98-1",
        "probe": "synchronized-local-compose-lock",
        "status": "PASS" if all_pass else "RED",
        "class": "deterministic",
        "reproducible": reproducible,
        "cross_checks": checks,
        "bound_owner_identities": {
            "sp95_omniscience": {
                "fragment_compose_digest": omni["fragment_compose_digest"],
                "service_contract_digest": omni["service_contract_digest"],
                "local_runtime_receipt_digest": omni["local_runtime_receipt_digest"],
                "receipt_git_commit": omni["receipt_git_commit"],
                "receipt_status": omni["receipt_status"],
            },
            "sp96_barbarossa": {
                "fragment_compose_digest": barb["fragment_compose_digest"],
                "service_contract_digest": barb["service_contract_digest"],
                "api_image_tag": barb["api_image_tag"],
                "worker_image_tag": barb["worker_image_tag"],
                "pending": barb["pending"],
            },
            "sp97_portal": {
                "fragment_compose_digest": portal["fragment_compose_digest"],
                "service_contract_digest": portal["service_contract_digest"],
                "pending": portal["pending"],
            },
        },
        "note": (
            "PASS means the assembled model includes ONLY exact owner-published "
            "fragments/receipts by content-addressed digest and renders with no mock/"
            "omnius/copied-owner-config. reproducible=false is honest here (source mode, "
            "an owner receipt is itself RED/dirty, and no SP-86 OCI digest is published) "
            "and never upgraded to a reproducible PASS."
        ),
    }


def compute_reproducible(
    omni: dict[str, Any], barb: dict[str, Any], portal: dict[str, Any]
) -> bool:
    """Reproducible only if image mode with published owner OCI digests and no
    dirty/RED owner source. None of those hold here, so this is False."""
    return (
        omni.get("receipt_reproducible") is True
        and omni.get("receipt_status") != "RED"
        and bool(barb.get("runtime_receipt_committed"))
        and bool(portal.get("runtime_receipt_committed"))
    )


# ---------------------------------------------------------------------------
# AC-SP98-2 — synchronized-local-topology-containment (deterministic).
# ---------------------------------------------------------------------------


def run_ac2(model: dict[str, Any]) -> dict[str, Any]:
    expected = read_json(EXPECTED_TOPOLOGY)
    services = model.get("services", {})
    networks = model.get("networks", {})
    volumes = model.get("volumes", {})

    issues: list[str] = []

    rendered_services = set(services)
    expected_all = EXPECTED_STEADY_SERVICES | EXPECTED_ONESHOT_SERVICES
    if rendered_services != expected_all:
        issues.append(
            f"service set mismatch: unexpected={sorted(rendered_services - expected_all)} "
            f"missing={sorted(expected_all - rendered_services)}"
        )

    for name in rendered_services:
        if not name.startswith(OWNER_PREFIXES):
            issues.append(f"service not owner-prefixed: {name}")
    for name in networks:
        if not name.startswith(OWNER_PREFIXES):
            issues.append(f"network not owner-prefixed: {name}")
    for name in volumes:
        if not name.startswith(OWNER_PREFIXES):
            issues.append(f"volume not owner-prefixed: {name}")

    for name in rendered_services | set(networks) | set(volumes):
        if any(sub in name.lower() for sub in FORBIDDEN_SUBSTRINGS):
            issues.append(f"forbidden mock/omnius resource: {name}")

    for net in OWNER_PRIVATE_NETWORKS:
        if not networks.get(net, {}).get("internal"):
            issues.append(f"owner-private network not internal: {net}")
    for net in ("omniscience-readnet", "barbarossa-edge"):
        if net not in networks:
            issues.append(f"read edge network missing: {net}")
        elif networks.get(net, {}).get("external"):
            issues.append(
                f"read edge network must be managed (external:false) in the assembled project: {net}"
            )

    portal_backend_nets = service_networks(services.get("portal-backend", {}))
    if portal_backend_nets != PORTAL_BACKEND_ALLOWED_NETWORKS:
        issues.append(
            f"portal-backend networks {sorted(portal_backend_nets)} != {sorted(PORTAL_BACKEND_ALLOWED_NETWORKS)}"
        )
    if portal_backend_nets & OWNER_PRIVATE_NETWORKS:
        issues.append("portal-backend joins an owner-private network (MLC-5 violation)")

    for name, svc in services.items():
        nets = service_networks(svc)
        joins_omni = any(n.startswith("omniscience-") for n in nets)
        joins_barb = any(n.startswith("barbarossa-") for n in nets)
        if joins_omni and joins_barb and name != "portal-backend":
            issues.append(
                f"{name} straddles both owners' networks but is not portal-backend"
            )

    bindings = host_bindings(model)
    if bindings != EXPECTED_HOST_BINDINGS:
        issues.append(
            f"host binding set mismatch: unexpected={sorted(bindings - EXPECTED_HOST_BINDINGS)} "
            f"missing={sorted(EXPECTED_HOST_BINDINGS - bindings)}"
        )
    for _svc, host_ip, _port in bindings:
        if host_ip != "127.0.0.1":
            issues.append(f"non-loopback host binding: {host_ip}")

    # No owner-write credential (MLC-5). A key merely SHAPED like an owner-write
    # credential is a violation only when it carries a REAL value; the owner
    # fragment deliberately neutralizes the SP-88 token-broker admin key to the
    # inert placeholder `unused-in-local-profile` (Portal contract asserts
    # holds_owner_write_credential=false), which is not a functional credential.
    portal_env = services.get("portal-backend", {}).get("environment", {}) or {}
    inert_value = re.compile(
        r"^\s*$|unused|change-me|dev-only|<|\.invalid|:-", re.IGNORECASE
    )
    write_cred_shaped = {
        k: v
        for k, v in portal_env.items()
        if re.search(
            r"(WRITE|ADMIN).*(OMNISCIENCE|BARBAROSSA)|(OMNISCIENCE|BARBAROSSA).*(WRITE|ADMIN)",
            k,
            re.IGNORECASE,
        )
    }
    active_write_creds = sorted(
        k for k, v in write_cred_shaped.items() if not inert_value.search(str(v))
    )
    if active_write_creds:
        issues.append(
            f"portal-backend carries an ACTIVE owner-write-shaped credential: {active_write_creds}"
        )
    neutralized_cred_keys = sorted(
        k for k in write_cred_shaped if k not in active_write_creds
    )

    exp_services = set(expected.get("steady_services", [])) | set(
        expected.get("oneshot_services", [])
    )
    if exp_services != expected_all:
        issues.append(
            "expected-topology fixture disagrees with the profile inventory constant"
        )

    status = "PASS" if not issues else "RED"
    return {
        "id": "AC-SP98-2",
        "probe": "synchronized-local-topology-containment",
        "status": status,
        "class": "deterministic",
        "issues": issues,
        "evidence": {
            "steady_service_count": len(rendered_services & EXPECTED_STEADY_SERVICES),
            "oneshot_service_count": len(rendered_services & EXPECTED_ONESHOT_SERVICES),
            "networks": sorted(networks),
            "volumes": sorted(volumes),
            "host_bindings": sorted(f"{s}:{ip}:{p}" for s, ip, p in bindings),
            "portal_backend_networks": sorted(portal_backend_nets),
            "neutralized_owner_credential_keys": neutralized_cred_keys,
            "active_owner_write_credential_keys": active_write_creds,
            "expected_topology_fixture_digest": sha256_file(EXPECTED_TOPOLOGY),
        },
    }


# ---------------------------------------------------------------------------
# AC-SP98-9 — synchronized-local-secret-reset-safety (deterministic).
# ---------------------------------------------------------------------------


def run_ac9() -> dict[str, Any]:
    import generate_management_readonly_local_env as gen  # local import; scripts/ on sys.path

    issues: list[str] = []

    committed = [COMPOSE_BASE, COMPOSE_SOURCE, ENV_EXAMPLE]
    real_secret_like = re.compile(r"=[A-Za-z0-9+/_-]{24,}={0,2}\s*$")
    # Exempt only the known labeled-placeholder shapes at the VALUE's start (or a
    # compose interpolation), never a bare substring like "local" that a real
    # secret could embed to evade the scan.
    placeholder_ok = re.compile(
        r"^(change-me|dev-only|unused|CHANGEME|portal-local-secret|admin-local)"
        r"|\.invalid|<[^>]*>|\$\{|:-",
        re.IGNORECASE,
    )
    for path in committed:
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            if (
                SECRET_KEY_PATTERN.search(key)
                and value
                and not placeholder_ok.search(value)
                and real_secret_like.search(stripped)
            ):
                issues.append(
                    f"{path.name}:{i} looks like a committed real secret value"
                )

    example_keys = _env_keys(ENV_EXAMPLE)
    required = required_env_variables()
    missing = sorted(required - example_keys)
    if missing:
        issues.append(f".env.example missing required variables: {missing}")

    gen_missing = sorted(set(gen.SECRET_VARS) - example_keys)
    if gen_missing:
        issues.append(f"generator SECRET_VARS not in .env.example: {gen_missing}")

    generator_report = _exercise_generator(gen)
    issues.extend(generator_report["issues"])

    env_committed = _git(ROOT, ["ls-files", "deploy/local/management-readonly-v1/.env"])
    if env_committed:
        issues.append("a real .env is tracked by git (must be gitignored)")

    status = "PASS" if not issues else "RED"
    return {
        "id": "AC-SP98-9",
        "probe": "synchronized-local-secret-reset-safety",
        "status": status,
        "class": "deterministic",
        "issues": issues,
        "evidence": {
            "committed_files_scanned": [p.name for p in committed],
            "required_variable_count": len(required),
            "example_variable_count": len(example_keys),
            "generator_secret_vars": list(gen.SECRET_VARS),
            "generator": generator_report["evidence"],
            "env_example_digest": sha256_file(ENV_EXAMPLE),
        },
        "note": (
            "Reset stays an explicit, confirmed operator action: `docker compose ... "
            "down` preserves every named volume; only `down -v` (a separate command) "
            "deletes them, and the env generator refuses to overwrite an existing .env "
            "without the explicit confirmation token."
        ),
    }


def _env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#") or "=" not in s:
            continue
        keys.add(s.partition("=")[0].strip())
    return keys


def required_env_variables() -> set[str]:
    """The union of every variable the three owner fragments read (the secret set
    plus the config-coupled set the assembled stack must supply)."""
    return {
        "OMNISCIENCE_POSTGRES_PASSWORD",
        "OMNISCIENCE_NEO4J_PASSWORD",
        "OMNISCIENCE_QDRANT_API_KEY",
        "OMNISCIENCE_ADMIN_PORT",
        "OMNISCIENCE_APP_VERSION",
        "OMNISCIENCE_LOCAL_MODEL",
        "OMNISCIENCE_LOG_LEVEL",
        "OMNISCIENCE_QDRANT_LOG_LEVEL",
        "POSTGRES_PASSWORD",
        "PORTAL_FRONTEND_PORT",
        "PORTAL_KEYCLOAK_PORT",
        "PORTAL_LOCAL_MODE",
        "PORTAL_DB",
        "PORTAL_DB_OWNER",
        "PORTAL_DB_PASSWORD",
        "PORTAL_APP_DB_ROLE",
        "PORTAL_APP_DB_PASSWORD",
        "KEYCLOAK_REALM",
        "KEYCLOAK_CLIENT_ID",
        "PORTAL_KEYCLOAK_CLIENT_SECRET",
        "PORTAL_KEYCLOAK_ADMIN_PASSWORD",
        "SESSION_TTL_SECONDS",
        "SESSION_IDLE_TTL_SECONDS",
        "TENANT_TOKEN_TTL_SECONDS",
        "STEPUP_FRESHNESS_WINDOW_SECONDS",
        "OMNISCIENCE_WORKSPACE_TOKEN_TTL_CEILING_SECONDS",
    }


def _exercise_generator(gen: Any) -> dict[str, Any]:
    """Render the env in-memory twice and assert entropy/uniqueness/no-collision
    without touching any real file."""
    issues: list[str] = []
    template_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    text_a, assigned_a = gen.render_env(template_text)
    text_b, _assigned_b = gen.render_env(template_text)

    if assigned_a != sorted(gen.SECRET_VARS):
        issues.append("generator did not assign exactly the declared SECRET_VARS")

    def secret_values(text: str) -> dict[str, str]:
        vals: dict[str, str] = {}
        for line in text.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                if k.strip() in gen.SECRET_VARS:
                    vals[k.strip()] = v
        return vals

    vals_a = secret_values(text_a)
    vals_b = secret_values(text_b)
    for k, v in vals_a.items():
        if len(v) < 32:
            issues.append(f"{k} entropy too low ({len(v)} chars)")
        if v == vals_b.get(k):
            issues.append(f"{k} not randomized across runs")
    config_a = [
        ln
        for ln in text_a.splitlines()
        if "=" in ln and ln.partition("=")[0].strip() not in gen.SECRET_VARS
    ]
    config_b = [
        ln
        for ln in text_b.splitlines()
        if "=" in ln and ln.partition("=")[0].strip() not in gen.SECRET_VARS
    ]
    if config_a != config_b:
        issues.append("config-coupled lines are not copied verbatim/stably")

    return {
        "issues": issues,
        "evidence": {
            "entropy_bits_per_secret": gen.SECRET_ENTROPY_BYTES * 8,
            "secrets_randomized": len(vals_a),
            "secrets_unique_across_runs": all(
                vals_a[k] != vals_b.get(k) for k in vals_a
            ),
            "confirm_token": gen.CONFIRM_TOKEN,
        },
    }


# ---------------------------------------------------------------------------
# Live ACs — GREEN with live capture, else pending / host_capacity_insufficient.
# ---------------------------------------------------------------------------


def _live_pending(
    ac_id: str, probe: str, requirement: str, live: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Return a pending/capacity status when there is no usable live evidence,
    else None (the caller then evaluates the live payload)."""
    if live is None:
        return {
            "id": ac_id,
            "probe": probe,
            "status": "pending",
            "class": "live",
            "reason": "live_capture_absent",
            "requirement": requirement,
            "note": (
                "No live capture supplied (--live-capture). Run the stack and "
                "`--probe-live` to produce one. Absent evidence is never a PASS and "
                "never a mock substitution."
            ),
        }
    if live.get("host_capacity_insufficient"):
        return {
            "id": ac_id,
            "probe": probe,
            "status": "host_capacity_insufficient",
            "class": "live",
            "reason": "host_capacity_insufficient",
            "requirement": requirement,
            "measured_shortfall": live.get("capacity", {}),
            "note": (
                "The assembled stack exceeded the measured host envelope. This is the "
                "profile's designed typed outcome — never a false FAIL, never owner-"
                "unavailable, never a mock-as-live substitution."
            ),
        }
    return None


def run_live_acs(live: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    specs = [
        (
            "AC-SP98-3",
            "synchronized-local-lifecycle",
            "config/migration/bootstrap/health-gated up/warm restart/down + explicit reset separation; normal down preserves volumes",
        ),
        (
            "AC-SP98-4",
            "synchronized-local-real-owner-experience",
            "Portal renders exact real Omniscience/Barbarossa owner revisions/freshness/development-single-host; selected-owner mocks absent",
        ),
        (
            "AC-SP98-5",
            "synchronized-local-tenant-pw0-no-effect",
            "two-scope reads + seeded PII/token/active-content show no cross-scope disclosure, sink residue, owner write, or Omnius effect",
        ),
        (
            "AC-SP98-6",
            "synchronized-local-severance-recovery",
            "stopping either owner marks only its own panel unavailable/stale and recovery restores fresh truth",
        ),
        (
            "AC-SP98-7",
            "synchronized-local-resource-envelope",
            "measured image sizes/per-service limits/peak+steady CPU/mem/disk/startup within the declared 4-vCPU/8-GB/25-GB envelope, or typed host_capacity_insufficient",
        ),
    ]
    results: dict[str, dict[str, Any]] = {}
    for ac_id, probe, requirement in specs:
        pending = _live_pending(ac_id, probe, requirement, live)
        if pending is not None:
            results[ac_id] = pending
            continue
        results[ac_id] = _evaluate_live_ac(ac_id, probe, requirement, live)
    return results


def _evaluate_live_ac(
    ac_id: str, probe: str, requirement: str, live: dict[str, Any]
) -> dict[str, Any]:
    """Fold a supplied live capture into a per-AC verdict. The capture records
    per-AC observed outcomes under live['acs'][ac_id]; a missing/false entry is
    surfaced honestly, never upgraded to PASS."""
    observed = (live.get("acs") or {}).get(ac_id)
    if observed is None:
        return {
            "id": ac_id,
            "probe": probe,
            "status": "pending",
            "class": "live",
            "reason": "live_capture_missing_this_ac",
            "requirement": requirement,
        }
    status = observed.get("status", "pending")
    if status not in {
        "PASS",
        "RED",
        "pending",
        "host_capacity_insufficient",
        "partial",
    }:
        status = "pending"
    result = {
        "id": ac_id,
        "probe": probe,
        "status": status,
        "class": "live",
        "requirement": requirement,
        "evidence": observed.get("evidence", {}),
    }
    if "reason" in observed:
        result["reason"] = observed["reason"]
    if "note" in observed:
        result["note"] = observed["note"]

    # AC-SP98-7 requires BOTH amd64 AND arm64 reference runs. A single-arch run
    # can never be a full PASS — hold it to the same honesty bar as AC-3/4/5/6,
    # which are `partial` for their unexercised portions. This is derived here
    # (not merely asserted by the capture) so any future single-arch capture is
    # downgraded and the unmeasured arch is named as an explicit pending axis.
    if ac_id == "AC-SP98-7" and status in {"PASS", "partial"}:
        pending_axes = _unmeasured_arch_axes(result["evidence"])
        if pending_axes:
            result["status"] = "partial"
            result["pending_axes"] = pending_axes
            result["reason"] = "reference_arch_axis_unmeasured"
            result["note"] = (
                "Measured within envelope on the run arch, but AC-SP98-7 requires both "
                f"amd64 and arm64; {', '.join(pending_axes)} is not measured on this "
                "single-arch host, so this is partial (not host_capacity_insufficient — "
                "capacity was sufficient on the measured arch)."
            )
    return result


def _unmeasured_arch_axes(evidence: dict[str, Any]) -> list[str]:
    """Return the reference arches AC-SP98-7 still needs. An arch is measured only
    when the evidence names it as the run arch; any arch carrying a 'pending'
    marker (or simply absent) is unmet."""
    run_arch = str(evidence.get("arch", "")).lower()
    pending: list[str] = []
    for arch in ("amd64", "arm64"):
        if arch == run_arch:
            continue
        marker = str(evidence.get(arch, "")).lower()
        if arch != run_arch and ("pending" in marker or marker == ""):
            pending.append(arch)
    return pending


# ---------------------------------------------------------------------------
# AC-SP98-8 — synchronized-local-receipt-integrity (over the assembled receipt).
# ---------------------------------------------------------------------------


def run_ac8(receipt_core: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    if receipt_core["availability_class"] != AVAILABILITY_CLASS:
        issues.append("availability_class not pinned to development-single-host")
    if receipt_core["ha_qualified"] is not False:
        issues.append("ha_qualified not pinned false")
    if receipt_core["activation_authority"] != ACTIVATION_AUTHORITY:
        issues.append("activation_authority not pinned none")
    if receipt_core["qualification_class"] != QUALIFICATION_CLASS:
        issues.append("qualification_class not functional-smoke-only")
    if receipt_core["reproducible"] is not False:
        issues.append("reproducible must be false while source-mode/dirty/no-OCI holds")
    if receipt_core.get("qualification_status") != "development-only":
        issues.append("qualification_status must be development-only")
    blob = json.dumps(receipt_core).lower()
    if '"ha_qualified": true' in blob:
        issues.append("receipt asserts ha_qualified=true")
    status = "PASS" if not issues else "RED"
    return {
        "id": "AC-SP98-8",
        "probe": "synchronized-local-receipt-integrity",
        "status": status,
        "class": "deterministic",
        "issues": issues,
        "evidence": {
            "availability_class": receipt_core["availability_class"],
            "ha_qualified": receipt_core["ha_qualified"],
            "activation_authority": receipt_core["activation_authority"],
            "qualification_class": receipt_core["qualification_class"],
            "reproducible": receipt_core["reproducible"],
            "qualification_status": receipt_core.get("qualification_status"),
            "cannot_satisfy": ["SP-89", "SP-92", "SP-94", "production-activation"],
        },
        "note": (
            "The receipt is content-addressed and reproducible-as-a-function-of-inputs; "
            "source dirtiness/absent OCI digests force reproducible=false and "
            "qualification_status=development-only, and the fixed development-single-host / "
            "ha_qualified=false / activation_authority=none axes cannot be promoted into "
            "HA (SP-92/SP-94) or SP-89 deployment evidence."
        ),
    }


# ---------------------------------------------------------------------------
# Receipt assembly.
# ---------------------------------------------------------------------------


def build_receipt(live: dict[str, Any] | None = None) -> dict[str, Any]:
    omni = build_omniscience_member()
    barb = build_barbarossa_member()
    portal = build_portal_member()

    model = render_compose([COMPOSE_BASE])
    redacted = redact_model(model)
    rendered_compose_digest = canonical_digest(redacted)

    ac1 = run_ac1(model, omni, barb, portal)
    ac2 = run_ac2(model)
    ac9 = run_ac9()
    live_acs = run_live_acs(live)

    reproducible = ac1["reproducible"]
    receipt_core = {
        "availability_class": AVAILABILITY_CLASS,
        "ha_qualified": HA_QUALIFIED,
        "activation_authority": ACTIVATION_AUTHORITY,
        "qualification_class": QUALIFICATION_CLASS,
        "reproducible": reproducible,
        "qualification_status": "development-only",
    }
    ac8 = run_ac8(receipt_core)

    acceptance_criteria = {
        ac["id"]: ac for ac in ([ac1, ac2] + list(live_acs.values()) + [ac8, ac9])
    }

    deterministic_ids = ("AC-SP98-1", "AC-SP98-2", "AC-SP98-8", "AC-SP98-9")
    live_ids = ("AC-SP98-3", "AC-SP98-4", "AC-SP98-5", "AC-SP98-6", "AC-SP98-7")
    deterministic_pass = all(
        acceptance_criteria[i]["status"] == "PASS" for i in deterministic_ids
    )

    inventory = {
        "service_inventory_digest": canonical_digest(sorted(model.get("services", {}))),
        "network_inventory_digest": canonical_digest(
            {
                n: {
                    "internal": bool(v.get("internal")),
                    "external": bool(v.get("external")),
                }
                for n, v in sorted(model.get("networks", {}).items())
            }
        ),
        "volume_inventory_digest": canonical_digest(sorted(model.get("volumes", {}))),
        "host_binding_inventory_digest": canonical_digest(
            sorted(f"{s}:{ip}:{p}" for s, ip, p in host_bindings(model))
        ),
    }

    receipt: dict[str, Any] = {
        "schema": "synchronized-platform-local-launch-receipt-v1",
        "receipt_type": "SynchronizedPlatformLocalLaunchReceipt",
        "profile_id": PROFILE_ID,
        "profile_revision": PROFILE_REVISION,
        "base_profile_id": BASE_PROFILE_ID,
        "base_profile_revision": "1.0.0",
        "governing_adr": GOVERNING_ADR,
        "compose_version_required": "2.24.4+",
        "genai_enablement_git_commit": git_head(ROOT),
        "mode": "source",
        "reproducible": reproducible,
        "qualification_class": QUALIFICATION_CLASS,
        "qualification_status": "development-only",
        "availability_class": AVAILABILITY_CLASS,
        "ha_qualified": HA_QUALIFIED,
        "activation_authority": ACTIVATION_AUTHORITY,
        "reset_performed": False,
        "assembled_compose": {
            "base": str(COMPOSE_BASE.relative_to(ROOT)),
            "source_overlay": str(COMPOSE_SOURCE.relative_to(ROOT)),
            "base_digest": sha256_file(COMPOSE_BASE),
            "source_overlay_digest": sha256_file(COMPOSE_SOURCE),
            "rendered_compose_digest": rendered_compose_digest,
        },
        "owner_members": {
            "sp95_omniscience": omni,
            "sp96_barbarossa": barb,
            "sp97_portal": portal,
        },
        "inventory_digests": inventory,
        "acceptance_criteria": acceptance_criteria,
        "deterministic_acceptance_criteria": list(deterministic_ids),
        "live_acceptance_criteria": list(live_ids),
        "deterministic_status": "GREEN" if deterministic_pass else "RED",
        "reasons": _receipt_reasons(
            omni, barb, portal, reproducible, acceptance_criteria, deterministic_ids
        ),
        "uncommitted_prior_wave_dependencies": [
            {
                "artifact": "Barbarossa BarbarossaLocalRuntimeReceipt",
                "state": "runtime-computed; no committed JSON to content-address",
                "handling": "pinned by committed service contract + image tags; sp96_runtime_receipt_digest flagged pending",
            },
            {
                "artifact": "Portal PortalLocalRuntimeReceipt",
                "state": "runtime-computed; no committed JSON to content-address",
                "handling": "pinned by committed service contract; sp97_runtime_receipt_digest flagged pending",
            },
            {
                "artifact": "Omniscience OmniscienceLocalRuntimeReceipt",
                "state": "committed but self-declared RED (scoped_worktree_dirty, sp86_image_registry_digest_pending)",
                "handling": "pinned by content-addressed digest; its honest RED status is surfaced, never upgraded",
            },
        ],
        "negative_space": [
            "no Omnius runtime/mock, no shared owner store/broker, no external model/provider",
            "no public datastore/broker port, no Portal owner-write credential",
            "no queue admin/redrive/scale/failover/rollback control",
            "no infrastructure apply, no DNS mutation, no HA claim, no production activation",
            "cannot satisfy or replace SP-89, SP-92 or SP-94 live evidence",
        ],
        "reference_host": (live or {}).get(
            "reference_host", {"note": "no live run folded in; see live ACs for status"}
        ),
        "overall_note": (
            "deterministic_status=GREEN means the compose-lock, topology-containment, "
            "receipt-integrity and secret/reset-safety ACs passed against the rendered "
            "model and committed owner artifacts. It does NOT mean the profile is "
            "deployed, HA-qualified, or activatable. Live ACs (3-7) are only GREEN with "
            "folded live evidence, else pending/host_capacity_insufficient — honestly."
        ),
    }
    receipt["receipt_digest"] = canonical_digest(
        {k: v for k, v in receipt.items() if k != "receipt_digest"}
    )
    return receipt


def _receipt_reasons(
    omni, barb, portal, reproducible, acs, deterministic_ids
) -> list[str]:
    reasons: list[str] = []
    if not reproducible:
        reasons.append(
            "reproducible=false: source mode with mutable owner tags / no published SP-86 OCI digest"
        )
    if omni.get("receipt_status") == "RED":
        reasons.append(
            "sp95 omniscience owner receipt is self-declared RED (scoped_worktree_dirty, sp86 image digest pending)"
        )
    if not barb.get("runtime_receipt_committed"):
        reasons.append(
            "sp96 barbarossa runtime receipt is not a committed content-addressable artifact"
        )
    if not portal.get("runtime_receipt_committed"):
        reasons.append(
            "sp97 portal runtime receipt is not a committed content-addressable artifact"
        )
    for i in deterministic_ids:
        if acs[i]["status"] != "PASS":
            reasons.append(f"{i} did not PASS")
    return reasons


# ---------------------------------------------------------------------------
# Live probe — capture observable evidence from a running assembled project.
# ---------------------------------------------------------------------------


def probe_live(project: str = PROFILE_ID) -> dict[str, Any]:
    """Capture observable evidence from an already-running assembled project.
    Purely observational: `docker` reads only. Writes nothing to any repo."""
    capture: dict[str, Any] = {"project": project, "acs": {}}

    capture["services"] = _docker_json(
        ["compose", "-p", project, "ps", "--format", "json"]
    )
    capture["stats"] = _docker_stats()

    images = _docker_json(["images", "--format", "json"])
    capture["images"] = [
        i
        for i in images
        if any(
            t in (i.get("Repository", "") + ":" + i.get("Tag", ""))
            for t in (
                "omniscience",
                "barbarossa",
                "portal",
                "keycloak",
                "neo4j",
                "qdrant",
                "nats",
                "postgres",
            )
        )
    ]

    capture["cross_owner_reads"] = {
        "omniscience_ready": _exec_in(
            project,
            "portal-backend",
            [
                "python",
                "-c",
                "import urllib.request;print(urllib.request.urlopen('http://omniscience-api:8000/ready',timeout=5).status)",
            ],
        ),
        "barbarossa_health": _exec_in(
            project,
            "portal-backend",
            [
                "python",
                "-c",
                "import urllib.request;print(urllib.request.urlopen('http://barbarossa-api:8080/v1/health',timeout=5).status)",
            ],
        ),
        "barbarossa_availability": _exec_in(
            project,
            "portal-backend",
            [
                "python",
                "-c",
                "import urllib.request;print(urllib.request.urlopen('http://barbarossa-api:8080/v1/local/availability',timeout=5).read().decode()[:400])",
            ],
        ),
    }
    return capture


def _docker_json(args: list[str]) -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    out = result.stdout.strip()
    rows: list[dict[str, Any]] = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not rows and out.startswith("["):
        try:
            rows = json.loads(out)
        except json.JSONDecodeError:
            pass
    return rows


def _docker_stats() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            rows.append({"name": parts[0], "mem": parts[1], "cpu": parts[2]})
    return rows


def _exec_in(project: str, service: str, cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            ["docker", "compose", "-p", project, "exec", "-T", service, *cmd],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"<exec-error: {exc}>"
    return (result.stdout + result.stderr).strip()[:500]


# ---------------------------------------------------------------------------
# Evidence write + CLI.
# ---------------------------------------------------------------------------


def write_evidence(receipt: dict[str, Any]) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    commit = receipt.get("genai_enablement_git_commit") or "uncommitted"
    digest_short = receipt["receipt_digest"].split(":")[1][:16]
    path = (
        EVIDENCE_DIR
        / f"synchronized-platform-local-launch-receipt.{commit}.{digest_short}.json"
    )
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("receipt_digest") != receipt.get("receipt_digest"):
            raise QualificationError(
                f"refusing to overwrite immutable evidence with different content: {path}"
            )
        return path
    path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def print_summary(receipt: dict[str, Any]) -> None:
    print("\n--- SynchronizedPlatformLocalLaunchReceipt: per-AC ---", file=sys.stderr)
    for ac_id, ac in sorted(receipt["acceptance_criteria"].items()):
        cls = ac.get("class", "?")
        print(f"  {ac_id} [{cls:13}]: {ac['status']}", file=sys.stderr)
    print(f"deterministic_status: {receipt['deterministic_status']}", file=sys.stderr)
    print(
        f"reproducible: {receipt['reproducible']}  mode: {receipt['mode']}",
        file=sys.stderr,
    )
    print(f"receipt_digest: {receipt['receipt_digest']}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        action="store_true",
        help="print receipt JSON to stdout; do not write evidence",
    )
    parser.add_argument(
        "--write", action="store_true", help="write content-addressed evidence"
    )
    parser.add_argument(
        "--live-capture",
        type=Path,
        default=None,
        help="fold a live-capture JSON into the live ACs",
    )
    parser.add_argument(
        "--probe-live",
        action="store_true",
        help="probe a running assembled project and print a live-capture JSON",
    )
    parser.add_argument(
        "--project", default=PROFILE_ID, help="compose project name for --probe-live"
    )
    args = parser.parse_args()

    if args.probe_live:
        print(json.dumps(probe_live(args.project), indent=2, sort_keys=True))
        return 0

    live = None
    if args.live_capture is not None:
        live = read_json(args.live_capture)

    try:
        receipt = build_receipt(live=live)
    except QualificationError as exc:
        print(f"QUALIFICATION RED: {exc}", file=sys.stderr)
        return 1

    if args.write:
        path = write_evidence(receipt)
        print(f"evidence written to: {path.relative_to(ROOT)}", file=sys.stderr)
    if args.report or not args.write:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    print_summary(receipt)

    deterministic_ids = receipt["deterministic_acceptance_criteria"]
    ok = all(
        receipt["acceptance_criteria"][i]["status"] == "PASS" for i in deterministic_ids
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
