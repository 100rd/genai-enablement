#!/usr/bin/env python3
"""Join the SP-86 (Omniscience), SP-87 (Barbarossa), SP-88 (Platform Portal)
owner release receipts -- and the SP-90 Go baseline transitively bound by
SP-87 -- into one content-addressed `management-readonly-v1` profile lock,
and independently qualify AC-SP89-1..6 (task-sp-89-management-readonly-
profile-qualification).

Read-only across every cross-repository input: this script never writes to
Omniscience/, Barbarossa/, or platform-portal/. It writes only inside this
repository's docs/synchronized-platform/releases/management-readonly-v1/
evidence/ directory (content-addressed by the joined lock's own digest,
append-only, never overwritten).

AC-SP89-3 (real-environment e2e matrix), AC-SP89-5 (ops/rollback in a named
environment), and AC-SP89-6 (Barbarossa image/SBOM/process inventory from a
named environment) require one named non-production environment receipt
(identity, owner, allowed operations, observation window, rollback target)
that does not exist. This script is forbidden from creating one (see
docs/specs/task-sp-89-management-readonly-profile-qualification.md
"Authority boundary": no Terraform/OpenTofu/Terragrunt apply or destroy, no
deployment, no secret, no DNS change, no policy activation, no Omnius
enablement). Those three ACs are emitted as honest RED/decision-required
evidence naming the exact missing input -- never a mock substitution, never
a partial PASS.
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
BARBAROSSA_ROOT = SIBLINGS_ROOT / "Barbarossa"
PORTAL_ROOT = SIBLINGS_ROOT / "platform-portal"

SP86_EVIDENCE_PATH = (
    OMNISCIENCE_ROOT
    / "contracts/releases/management-readonly-v1/evidence"
    / "release-lock.c733a0d445c090187461814263be7a07d20b7af3.json"
)
BARBAROSSA_RUNBOOK_PATH = (
    BARBAROSSA_ROOT / "docs/runbooks/management-readonly-release.md"
)
SP90_RUNBOOK_PATH = BARBAROSSA_ROOT / "docs/runbooks/go-runtime-migration.md"
PORTAL_PINS_PATH = PORTAL_ROOT / "backend/app/runtime_profiles/pins.py"
PORTAL_SCHEMAS_PATH = PORTAL_ROOT / "backend/app/runtime_profiles/schemas.py"
PORTAL_RELEASE_LOCK_PATH = PORTAL_ROOT / "backend/app/runtime_profiles/release_lock.py"
PORTAL_RUNBOOK_PATH = PORTAL_ROOT / "docs/runbooks/management-readonly-release.md"

REGISTRY_PATH = ROOT / "portfolio" / "synchronized-platform.json"
SEVERANCE_FIXTURES_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "management-readonly-v1"
    / "severance-skew-recovery.json"
)
EVIDENCE_DIR = (
    ROOT
    / "docs"
    / "synchronized-platform"
    / "releases"
    / "management-readonly-v1"
    / "evidence"
)

PROFILE_ID = "management-readonly-v1"
GOVERNING_ADR = "ADR-0021"

SP60_PW0_POLICY_DIGEST = (
    "sha256:fa312387e5fa4b3980b085e20033fc8d947474c62c15dd9e3836372dea01f038"
)
SP60_PW0_POLICY_REVISION = "1.0.0"

EXPECTED_RUNTIME_COMPONENTS = ["omniscience", "barbarossa", "platform-portal"]
EXPECTED_DEFERRED_COMPONENTS = ["omnius"]
EXPECTED_SELECTED_DOMAIN_PACKS = ["reliability"]

REQUIRED_ENVIRONMENT_RECEIPT_FIELDS = (
    "environment_identity",
    "environment_owner",
    "allowed_operations",
    "observation_window",
    "rollback_target",
)


class QualificationError(Exception):
    """Raised when a required input is missing, mutable, incompatible, or unverifiable."""


def sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_hex(path.read_bytes())


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_text(path: Path) -> str:
    if not path.exists():
        raise QualificationError(f"missing required input: {path}")
    return path.read_text(encoding="utf-8")


def is_placeholder(value: Any) -> bool:
    """True for runbook templated strings like 'sha256:<sha256 of ...>' -- these
    are never real digests and must never be compared or fabricated as one."""
    return isinstance(value, str) and "<" in value and ">" in value


def extract_json_fence(text: str, heading_pattern: str, source: str) -> dict[str, Any]:
    heading_match = re.search(heading_pattern, text)
    if not heading_match:
        raise QualificationError(f"heading not found in {source}: {heading_pattern!r}")
    remainder = text[heading_match.end() :]
    fence_match = re.search(r"```json\n(.*?)\n```", remainder, re.DOTALL)
    if not fence_match:
        raise QualificationError(
            f"no fenced json block after heading in {source}: {heading_pattern!r}"
        )
    return json.loads(fence_match.group(1))


def extract_assignment_block(source_text: str, assign_name: str, source: str) -> str:
    pattern = rf"{re.escape(assign_name)}\s*=\s*\w+\(\n(.*?)\n\)\n"
    match = re.search(pattern, source_text, re.DOTALL)
    if not match:
        raise QualificationError(
            f"could not locate assignment block in {source}: {assign_name}"
        )
    return match.group(1)


def extract_field_raw(block: str, field_name: str, source: str) -> str:
    pattern = rf"^\s*{re.escape(field_name)}=(.+?),\s*$"
    match = re.search(pattern, block, re.MULTILINE)
    if not match:
        raise QualificationError(f"field {field_name!r} not found in {source}")
    return match.group(1).strip()


def resolve_string_field(raw: str, known: dict[str, str], source: str) -> str | None:
    if raw == "None":
        return None
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw in known:
        return known[raw]
    raise QualificationError(f"unresolved reference in {source}: {raw!r}")


# ---------------------------------------------------------------------------
# SP-86 (Omniscience) -- one committed, content-addressable evidence file.
# ---------------------------------------------------------------------------


def build_sp86_member() -> dict[str, Any]:
    digest = sha256_file(SP86_EVIDENCE_PATH)
    payload = json.loads(read_text(SP86_EVIDENCE_PATH))
    return {
        "owner": "omniscience",
        "source": str(SP86_EVIDENCE_PATH.relative_to(SIBLINGS_ROOT)),
        "release_lock_digest": digest,
        "profile_id": payload.get("profile_id"),
        "profile_revision": payload.get("profile_revision"),
        "git_commit": payload.get("git_commit"),
        "image_digest": payload.get("image_digest"),
        "chart_digest": payload.get("chart_digest"),
        "configuration_digest": payload.get("configuration_digest"),
        "schema_set_digest": payload.get("schema_set_digest"),
        "pii_policy_digest": payload.get("pii_policy_digest"),
        "pii_policy_revision": payload.get("pii_policy_revision"),
        "severance_fixture_digest": payload.get("severance_fixture_digest"),
        "omnius_status": payload.get("dependency_profile", {}).get("omnius_status"),
        "rollback_release_digest": payload.get("rollback_release_digest"),
        "own_declared_status": payload.get("status"),
        "own_declared_reasons": payload.get("reasons", []),
        "pending": payload.get("pending", {}),
    }


# ---------------------------------------------------------------------------
# SP-90 baseline (Barbarossa) -- transitively bound by SP-87; no single
# committed evidence file, only a runbook-published JSON block.
# ---------------------------------------------------------------------------


def build_sp90_member() -> dict[str, Any]:
    text = read_text(SP90_RUNBOOK_PATH)
    block = extract_json_fence(
        text, r"## BarbarossaGoRuntimeBaseline \(AC-SP90-7\)", str(SP90_RUNBOOK_PATH)
    )
    block_digest = sha256_hex(canonical_json_bytes(block))
    return {
        "owner": "barbarossa",
        "source": str(SP90_RUNBOOK_PATH.relative_to(SIBLINGS_ROOT)),
        "published_block_digest": block_digest,
        "git_commit": block.get("git_commit"),
        "go_toolchain_version": block.get("go_toolchain_version"),
        "go_module_graph_digest": block.get("go_module_graph_digest"),
        "binary_digest": block.get("binary_digest"),
        "image_digest": block.get("image_digest"),
        "sbom_digest": block.get("sbom_digest"),
        "configuration_schema_digest": block.get("configuration_schema_digest"),
        "raw": block,
    }


# ---------------------------------------------------------------------------
# SP-87 (Barbarossa) -- no single committed evidence file, only a runbook-
# published sample JSON block (three fields are runbook placeholder text,
# never real digests: binary_digest, image_digest, sbom_digest).
# ---------------------------------------------------------------------------


def build_sp87_member() -> dict[str, Any]:
    text = read_text(BARBAROSSA_RUNBOOK_PATH)
    block = extract_json_fence(
        text,
        r"## AC-SP87-6: release lock \(`BarbarossaManagementReadOnlyRelease`\)",
        str(BARBAROSSA_RUNBOOK_PATH),
    )
    placeholder_fields = sorted(
        field
        for field in ("binary_digest", "image_digest", "sbom_digest")
        if is_placeholder(block.get(field))
    )
    concrete_block = {k: v for k, v in block.items() if k not in placeholder_fields}
    block_digest = sha256_hex(canonical_json_bytes(concrete_block))
    return {
        "owner": "barbarossa",
        "source": str(BARBAROSSA_RUNBOOK_PATH.relative_to(SIBLINGS_ROOT)),
        "published_block_digest": block_digest,
        "placeholder_fields": placeholder_fields,
        "profile_id": block.get("profile_id"),
        "profile_revision": block.get("profile_revision"),
        "git_commit": block.get("git_commit"),
        "sp90_baseline_digest": block.get("sp90_baseline_digest"),
        "sp86_release_digest": block.get("sp86_release_digest"),
        "package_or_chart_digest": block.get("package_or_chart_digest"),
        "configuration_digest": block.get("configuration_digest"),
        "selected_domain_manifest_digest": block.get("selected_domain_manifest_digest"),
        "journey_slo_revision": block.get("journey_slo_revision"),
        "journey_slo_digest": block.get("journey_slo_digest"),
        "pii_policy_digest": block.get("pii_policy_digest"),
        "pii_policy_revision": block.get("pii_policy_revision"),
        "health_readiness_contract": block.get("health_readiness_contract"),
        "rollback_release_digest": block.get("rollback_release_digest"),
        "own_declared_status": block.get("status"),
        "own_declared_reasons": block.get("reasons", []),
        "pending": block.get("pending", {}),
        "raw": block,
    }


# ---------------------------------------------------------------------------
# SP-88 (Platform Portal) -- no single committed release-lock evidence file
# (unlike SP-86); the receipt is the source Portal itself committed: the
# frozen pins.py literal, the release_lock.py builder, the schemas.py DTO,
# and the runbook. We hash those real, committed files (never execute
# Portal's own code) and cross-check the literal pin values they copy
# against our own independently-derived SP-86/SP-87/SP-90 digests.
# ---------------------------------------------------------------------------


def build_sp88_member() -> dict[str, Any]:
    pins_text = read_text(PORTAL_PINS_PATH)
    source_files = {
        "pins.py": PORTAL_PINS_PATH,
        "schemas.py": PORTAL_SCHEMAS_PATH,
        "release_lock.py": PORTAL_RELEASE_LOCK_PATH,
        "management-readonly-release.md": PORTAL_RUNBOOK_PATH,
    }
    file_digests = {name: sha256_file(path) for name, path in source_files.items()}
    combined_lines = sorted(f"{name}:{digest}" for name, digest in file_digests.items())
    source_receipt_digest = sha256_hex("\n".join(combined_lines).encode("utf-8"))

    known: dict[str, str] = {
        "SP60_PW0_POLICY_DIGEST": SP60_PW0_POLICY_DIGEST,
        "SP60_PW0_POLICY_REVISION": SP60_PW0_POLICY_REVISION,
        "PROFILE_ID": PROFILE_ID,
    }

    sp90_digest_match = re.search(
        r'SP90_BASELINE_DIGEST\s*=\s*"(sha256:[0-9a-f]+)"', pins_text
    )
    if not sp90_digest_match:
        raise QualificationError(
            f"SP90_BASELINE_DIGEST literal not found in {PORTAL_PINS_PATH}"
        )
    known["SP90_BASELINE_DIGEST"] = sp90_digest_match.group(1)

    sp86_block = extract_assignment_block(
        pins_text, "SP86_RELEASE_PIN", str(PORTAL_PINS_PATH)
    )
    sp86_pin = {
        "git_commit": resolve_string_field(
            extract_field_raw(sp86_block, "git_commit", str(PORTAL_PINS_PATH)),
            known,
            str(PORTAL_PINS_PATH),
        ),
        "release_lock_digest": resolve_string_field(
            extract_field_raw(sp86_block, "release_lock_digest", str(PORTAL_PINS_PATH)),
            known,
            str(PORTAL_PINS_PATH),
        ),
        "pii_policy_digest": resolve_string_field(
            extract_field_raw(sp86_block, "pii_policy_digest", str(PORTAL_PINS_PATH)),
            known,
            str(PORTAL_PINS_PATH),
        ),
        "status": resolve_string_field(
            extract_field_raw(sp86_block, "status", str(PORTAL_PINS_PATH)),
            known,
            str(PORTAL_PINS_PATH),
        ),
    }
    known["SP86_RELEASE_PIN.release_lock_digest"] = (
        sp86_pin["release_lock_digest"] or ""
    )

    sp87_block = extract_assignment_block(
        pins_text, "SP87_RELEASE_PIN", str(PORTAL_PINS_PATH)
    )
    sp87_pin = {
        "git_commit": resolve_string_field(
            extract_field_raw(sp87_block, "git_commit", str(PORTAL_PINS_PATH)),
            known,
            str(PORTAL_PINS_PATH),
        ),
        "sp90_baseline_digest": resolve_string_field(
            extract_field_raw(
                sp87_block, "sp90_baseline_digest", str(PORTAL_PINS_PATH)
            ),
            known,
            str(PORTAL_PINS_PATH),
        ),
        "sp86_release_digest": resolve_string_field(
            extract_field_raw(sp87_block, "sp86_release_digest", str(PORTAL_PINS_PATH)),
            known,
            str(PORTAL_PINS_PATH),
        ),
        "pii_policy_digest": resolve_string_field(
            extract_field_raw(sp87_block, "pii_policy_digest", str(PORTAL_PINS_PATH)),
            known,
            str(PORTAL_PINS_PATH),
        ),
        "status": resolve_string_field(
            extract_field_raw(sp87_block, "status", str(PORTAL_PINS_PATH)),
            known,
            str(PORTAL_PINS_PATH),
        ),
    }

    return {
        "owner": "platform-portal",
        "sources": {
            name: str(path.relative_to(SIBLINGS_ROOT))
            for name, path in source_files.items()
        },
        "source_file_digests": file_digests,
        "source_receipt_digest": source_receipt_digest,
        "sp86_pin_copy": sp86_pin,
        "sp87_pin_copy": sp87_pin,
        "sp90_baseline_digest_copy": known["SP90_BASELINE_DIGEST"],
        "note": (
            "No single committed PortalManagementReadOnlyRelease evidence file exists "
            "at pin time (unlike SP-86's committed evidence/release-lock-*.json); "
            "source_receipt_digest hashes the real, committed source files Portal "
            "published (pins.py/schemas.py/release_lock.py/runbook), never Portal's "
            "own build_portal_release_lock() output, which this read-only cross-repo "
            "join does not execute."
        ),
    }


# ---------------------------------------------------------------------------
# AC-SP89-1: profile lock join.
# ---------------------------------------------------------------------------


def run_ac1(
    sp86: dict[str, Any],
    sp87: dict[str, Any],
    sp90: dict[str, Any],
    sp88: dict[str, Any],
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

    check(
        "sp87.sp86_release_digest == independently-derived sp86 digest",
        sp86["release_lock_digest"],
        sp87["sp86_release_digest"],
    )
    check(
        "sp88.sp86_pin_copy.release_lock_digest == independently-derived sp86 digest",
        sp86["release_lock_digest"],
        sp88["sp86_pin_copy"]["release_lock_digest"],
    )
    check(
        "sp88.sp87_pin_copy.sp86_release_digest == independently-derived sp86 digest",
        sp86["release_lock_digest"],
        sp88["sp87_pin_copy"]["sp86_release_digest"],
    )
    check(
        "sp88.sp87_pin_copy.sp90_baseline_digest == sp87.sp90_baseline_digest",
        sp87["sp90_baseline_digest"],
        sp88["sp87_pin_copy"]["sp90_baseline_digest"],
    )
    check(
        "sp88.sp90_baseline_digest_copy == sp87.sp90_baseline_digest",
        sp87["sp90_baseline_digest"],
        sp88["sp90_baseline_digest_copy"],
    )
    check(
        "sp87.git_commit == sp90.git_commit (SP-90 baseline is transitively bound by SP-87 at the same Go tree commit)",
        sp90["git_commit"],
        sp87["git_commit"],
    )
    check(
        "sp86.pii_policy_digest == SP60 PW0 policy digest",
        SP60_PW0_POLICY_DIGEST,
        sp86["pii_policy_digest"],
    )
    check(
        "sp87.pii_policy_digest == SP60 PW0 policy digest",
        SP60_PW0_POLICY_DIGEST,
        sp87["pii_policy_digest"],
    )
    check(
        "sp88.sp86_pin_copy.pii_policy_digest == SP60 PW0 policy digest",
        SP60_PW0_POLICY_DIGEST,
        sp88["sp86_pin_copy"]["pii_policy_digest"],
    )
    check(
        "sp88.sp87_pin_copy.pii_policy_digest == SP60 PW0 policy digest",
        SP60_PW0_POLICY_DIGEST,
        sp88["sp87_pin_copy"]["pii_policy_digest"],
    )
    check("sp86.omnius_status == not_deployed", "not_deployed", sp86["omnius_status"])

    completeness_gaps = [
        field
        for field in (
            "release_lock_digest",
            "image_digest",
            "chart_digest",
            "configuration_digest",
            "schema_set_digest",
            "pii_policy_digest",
            "severance_fixture_digest",
        )
        if not sp86.get(field)
    ]
    for field in (
        "sp90_baseline_digest",
        "sp86_release_digest",
        "package_or_chart_digest",
        "configuration_digest",
        "selected_domain_manifest_digest",
    ):
        if not sp87.get(field):
            completeness_gaps.append(f"sp87.{field}")

    all_pass = all(c["pass"] for c in checks) and not completeness_gaps

    return {
        "id": "AC-SP89-1",
        "status": "PASS" if all_pass else "RED",
        "cross_checks": checks,
        "completeness_gaps": completeness_gaps,
        "pending_external_gates": {
            "sp86": sp86.get("pending", {}),
            "sp87": sp87.get("pending", {}),
            "sp87_placeholder_fields": sp87.get("placeholder_fields", []),
            "sp90_binary_image_sbom_digest": {
                "binary_digest": sp90.get("binary_digest"),
                "image_digest": sp90.get("image_digest"),
                "sbom_digest": sp90.get("sbom_digest"),
                "note": "null by design in SP-90's own baseline receipt; a real value requires a release task's machine-specific build, not this implementation-baseline receipt.",
            },
        },
        "upstream_owner_declared_status": {
            "sp86": {
                "status": sp86.get("own_declared_status"),
                "reasons": sp86.get("own_declared_reasons"),
            },
            "sp87": {
                "status": sp87.get("own_declared_status"),
                "reasons": sp87.get("own_declared_reasons"),
            },
        },
        "note": (
            "PASS here means the three owner receipts join exactly, immutably, and "
            "compatibly by content-addressed digest -- it does NOT mean SP-86/SP-87's "
            "own upstream release status is GREEN (both are honestly RED, reason "
            "scoped_worktree_dirty, in the receipts they themselves published). Exact-"
            "pin verification checks identity/exactness, not the upstream task's own "
            "qualification status -- the same rule SP-87's and SP-88's own runbooks "
            "already apply to each other."
        ),
    }


# ---------------------------------------------------------------------------
# AC-SP89-2: runtime membership (Omniscience/Barbarossa/Portal only; Omnius
# and every unselected adapter absent). Buildable, static/documentary check
# against the accepted ADR-0021 registry selection plus each owner's own
# committed no-effect evidence. This is NOT a live network/DNS/workload
# inventory -- that requires the named environment AC-SP89-3/5/6 are RED for.
# ---------------------------------------------------------------------------


def run_ac2(sp86: dict[str, Any], sp87_raw: dict[str, Any]) -> dict[str, Any]:
    registry = json.loads(read_text(REGISTRY_PATH))
    profiles = [p for p in registry["runtime_profiles"] if p["id"] == PROFILE_ID]
    if not profiles:
        raise QualificationError(
            f"runtime profile {PROFILE_ID!r} not found in {REGISTRY_PATH}"
        )
    profile = profiles[0]

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

    check(
        "registry.runtime_components",
        EXPECTED_RUNTIME_COMPONENTS,
        profile.get("runtime_components"),
    )
    check(
        "registry.deferred_runtime_components",
        EXPECTED_DEFERRED_COMPONENTS,
        profile.get("deferred_runtime_components"),
    )
    check(
        "registry.selected_domain_packs",
        EXPECTED_SELECTED_DOMAIN_PACKS,
        profile.get("selected_domain_packs"),
    )
    check("registry.governing_adr", GOVERNING_ADR, profile.get("governing_adr"))
    check(
        "sp86 dependency_profile.omnius_status == not_deployed",
        "not_deployed",
        sp86["omnius_status"],
    )

    sp87_domain_manifest_present = bool(sp87_raw.get("selected_domain_manifest_digest"))
    checks.append(
        {
            "name": "sp87 publishes a selected-domain-manifest digest (SelectedDomainManifest(), Reliability-only per ADR-0003 BMR-1)",
            "expected": True,
            "actual": sp87_domain_manifest_present,
            "pass": sp87_domain_manifest_present,
        }
    )

    all_pass = all(c["pass"] for c in checks)

    return {
        "id": "AC-SP89-2",
        "status": "PASS" if all_pass else "RED",
        "cross_checks": checks,
        "evidence": {
            "registry_selection": {
                "governance_components": profile.get("governance_components"),
                "runtime_components": profile.get("runtime_components"),
                "deferred_runtime_components": profile.get(
                    "deferred_runtime_components"
                ),
                "selected_domain_packs": profile.get("selected_domain_packs"),
            },
            "sp86_no_effect_evidence": "dependency_profile.omnius_status=not_deployed (Omniscience/contracts/releases/management-readonly-v1/evidence/release-lock.c733a0d445c090187461814263be7a07d20b7af3.json)",
            "sp87_no_effect_evidence": "cmd/barbarossa/main.go registers exactly /healthz and /readyz; main_test.go's TestNoMutationOrEffectRouteIsReachable probes an explicit negative matrix of operator-mutation/action/effect/autonomy/alert-delivery-shaped paths and asserts every one 404s (Barbarossa/docs/runbooks/management-readonly-release.md AC-SP87-5).",
            "sp88_no_effect_evidence": "every CV/CMC/Privacy mutation route returns 423 release-gate-open; app/zones/{control,manage}_router.py are GET-only; app/runtime_profiles/router.py is GET-only by construction; GET .../selection renders omniusStatus=not_deployed and the closed selected/not_selected domain set (platform-portal/docs/runbooks/management-readonly-release.md AC-SP88-2, AC-SP88-5).",
        },
        "scope_boundary": (
            "This check is a static, receipt-and-registry-based membership/no-effect "
            "audit. It does NOT perform a live workload, network, DNS, route, or "
            "secret-name inventory against a running environment -- that requires the "
            "named non-production environment AC-SP89-3/AC-SP89-5/AC-SP89-6 are "
            "honestly RED for below. Do not read this PASS as a live network/DNS scan."
        ),
    }


# ---------------------------------------------------------------------------
# AC-SP89-4: severance/skew/outage/restart/rebuild fixtures.
# ---------------------------------------------------------------------------


REQUIRED_FIXTURE_FIELDS = {
    "id",
    "component",
    "scenario_family",
    "source_scenario",
    "source_ref",
    "description",
    "expected_decision",
    "must_not_validate_as",
    "preserves_unrelated_operation",
    "rejects_stale_writer",
    "rejects_stale_writer_applicable",
}
FORBIDDEN_DECISIONS = {"healthy", "empty", "cached_current", "compatible"}


def run_ac4() -> dict[str, Any]:
    matrix = json.loads(read_text(SEVERANCE_FIXTURES_PATH))
    fixtures = matrix.get("fixtures", [])

    issues: list[str] = []
    if not fixtures:
        issues.append("fixture matrix is empty")

    seen_ids: set[str] = set()
    covered: set[tuple[str, str]] = set()
    for fixture in fixtures:
        missing_fields = REQUIRED_FIXTURE_FIELDS - fixture.keys()
        if missing_fields:
            issues.append(
                f"{fixture.get('id', '<unknown>')}: missing fields {sorted(missing_fields)}"
            )
            continue
        if fixture["id"] in seen_ids:
            issues.append(f"duplicate fixture id: {fixture['id']}")
        seen_ids.add(fixture["id"])

        if fixture["scenario_family"] not in matrix.get("scenario_families", []):
            issues.append(
                f"{fixture['id']}: scenario_family {fixture['scenario_family']!r} not declared"
            )
        if fixture["component"] not in matrix.get("components", []):
            issues.append(
                f"{fixture['id']}: component {fixture['component']!r} not declared"
            )
        if fixture["expected_decision"] in FORBIDDEN_DECISIONS:
            issues.append(
                f"{fixture['id']}: expected_decision {fixture['expected_decision']!r} is a forbidden favorable outcome"
            )
        if not fixture["preserves_unrelated_operation"]:
            issues.append(
                f"{fixture['id']}: preserves_unrelated_operation must be true (unrelated state must never be hidden)"
            )
        if (
            fixture["rejects_stale_writer"]
            and not fixture["rejects_stale_writer_applicable"]
        ):
            issues.append(
                f"{fixture['id']}: rejects_stale_writer=true but rejects_stale_writer_applicable=false"
            )
        overlap = set(fixture["must_not_validate_as"]) & {fixture["expected_decision"]}
        if overlap:
            issues.append(
                f"{fixture['id']}: expected_decision also listed in must_not_validate_as: {overlap}"
            )

        covered.add((fixture["component"], fixture["scenario_family"]))

    not_evidenced = {
        (e["component"], e["scenario_family"]) for e in matrix.get("not_evidenced", [])
    }
    all_pairs = {
        (c, s)
        for c in matrix.get("components", [])
        for s in matrix.get("scenario_families", [])
    }
    uncovered = all_pairs - covered - not_evidenced
    if uncovered:
        issues.append(
            f"component/scenario_family pairs neither fixture-covered nor honestly declared not_evidenced: {sorted(uncovered)}"
        )

    restart_or_rebuild_writer_checks = [
        f
        for f in fixtures
        if f["scenario_family"] in {"restart", "rebuild"}
        and f.get("rejects_stale_writer_applicable")
    ]
    if not any(f["rejects_stale_writer"] for f in restart_or_rebuild_writer_checks):
        issues.append(
            "no restart/rebuild fixture asserts rejects_stale_writer=true (AC-SP89-4 requires 'reject stale writers' coverage)"
        )

    return {
        "id": "AC-SP89-4",
        "status": "PASS" if not issues else "RED",
        "fixture_count": len(fixtures),
        "not_evidenced_count": len(not_evidenced),
        "covered_pairs": sorted(f"{c}/{s}" for c, s in covered),
        "not_evidenced_pairs": sorted(f"{c}/{s}" for c, s in not_evidenced),
        "issues": issues,
        "fixture_matrix_digest": sha256_file(SEVERANCE_FIXTURES_PATH),
        "scope_boundary": (
            "This is a structural/typed validation of a fixture matrix that joins "
            "each owner's already-published severance evidence. It does not execute "
            "a live component and is not AC-SP89-3's real environment e2e matrix."
        ),
    }


# ---------------------------------------------------------------------------
# AC-SP89-3 / AC-SP89-5 / AC-SP89-6: environment-gated, honestly RED.
# ---------------------------------------------------------------------------


def environment_receipt_path() -> Path:
    return (
        ROOT
        / "docs"
        / "synchronized-platform"
        / "releases"
        / "management-readonly-v1"
        / "environment-receipt.json"
    )


def find_environment_receipt() -> dict[str, Any] | None:
    path = environment_receipt_path()
    if not path.exists():
        return None
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    missing = [f for f in REQUIRED_ENVIRONMENT_RECEIPT_FIELDS if not receipt.get(f)]
    if missing:
        return None
    return receipt


def run_environment_gated_ac(
    ac_id: str, requirement: str, evidence_needed: str
) -> dict[str, Any]:
    receipt = find_environment_receipt()
    if receipt is not None:
        # An authorized environment receipt exists; this task still cannot
        # perform the deployment/effect it would require -- surface it as
        # decision-required rather than silently RED.
        return {
            "id": ac_id,
            "status": "decision-required",
            "requirement": requirement,
            "environment_receipt": receipt,
            "note": (
                "A named non-production environment receipt was found, but this task's "
                "authority boundary forbids performing the deployment/observation "
                "actions this AC requires on its own. A human-authorized, separately "
                "scoped qualification pass against this named environment is required."
            ),
        }
    return {
        "id": ac_id,
        "status": "RED",
        "requirement": requirement,
        "missing_input": (
            f"one named non-production environment receipt at "
            f"{environment_receipt_path().relative_to(ROOT)} with all of "
            f"{', '.join(REQUIRED_ENVIRONMENT_RECEIPT_FIELDS)} -- none exists."
        ),
        "why_no_substitute": (
            "docs/specs/task-sp-89-management-readonly-profile-qualification.md "
            "'Authority boundary' forbids this task from creating or authorizing an "
            "environment: no Terraform/OpenTofu/Terragrunt apply or destroy, no "
            "deployment, no secret creation, no DNS change, no policy activation, no "
            "Omnius runtime enablement. A missing input produces RED/decision-"
            "required evidence, never a mock substitution or partial PASS "
            "(docs/synchronized-platform/profiles/management-readonly-v1.md "
            "'Environment and activation boundary')."
        ),
        "evidence_needed": evidence_needed,
        "decision_required": (
            "A human must authorize and supply a named non-production environment "
            "(identity, owner, allowed operations, observation window, rollback "
            "target) before this AC can be qualified."
        ),
    }


def run_ac3() -> dict[str, Any]:
    return run_environment_gated_ac(
        "AC-SP89-3",
        "The selected tenant PW0 Reliability and source-bound Portal journeys pass end to end",
        "two independently controlled tenant identities, a seeded canary/PII/active-content corpus, "
        "the human-owned SLO/source revision, and captured API/UI/telemetry evidence from a real "
        "environment running all three components together.",
    )


def run_ac5() -> dict[str, Any]:
    return run_environment_gated_ac(
        "AC-SP89-5",
        "The named non-production profile is observable, recoverable, and reversible",
        "an environment-owner receipt, external alert observation, an isolated restore result, "
        "and post-rollback conformance capture against a real deployed instance.",
    )


def run_ac6() -> dict[str, Any]:
    ac6 = run_environment_gated_ac(
        "AC-SP89-6",
        "The deployed Barbarossa workload is built only from the accepted SP-90 Go production baseline",
        "an independently captured OCI image, SBOM, filesystem, process command, and network inventory "
        "from the named environment, compared against the exact SP-90 receipt.",
    )
    if ac6["status"] == "RED":
        ac6["additional_context"] = (
            "Even the owner-level artifacts this AC would compare against are themselves "
            "pending: SP-90's own binary_digest/image_digest/sbom_digest are null by "
            "design (go-runtime-migration.md), and SP-87's runbook records the same "
            "three fields as un-computed placeholder text, never a real digest. A named "
            "environment's independently captured inventory is required regardless."
        )
    return ac6


# ---------------------------------------------------------------------------
# Assembly and CLI.
# ---------------------------------------------------------------------------


def git_head(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip()


def build_profile_lock() -> dict[str, Any]:
    sp86 = build_sp86_member()
    sp90 = build_sp90_member()
    sp87 = build_sp87_member()
    sp88 = build_sp88_member()

    ac1 = run_ac1(sp86, sp87, sp90, sp88)
    ac2 = run_ac2(sp86, sp87["raw"])
    ac3 = run_ac3()
    ac4 = run_ac4()
    ac5 = run_ac5()
    ac6 = run_ac6()

    acceptance_criteria = {ac["id"]: ac for ac in (ac1, ac2, ac3, ac4, ac5, ac6)}
    buildable = ("AC-SP89-1", "AC-SP89-2", "AC-SP89-4")
    environment_gated = ("AC-SP89-3", "AC-SP89-5", "AC-SP89-6")
    buildable_pass = all(
        acceptance_criteria[ac_id]["status"] == "PASS" for ac_id in buildable
    )

    lock: dict[str, Any] = {
        "schema": "management-readonly-v1-integrated-profile-lock-v1",
        "profile_id": PROFILE_ID,
        "profile_revision": "1.0.0",
        "governing_adr": GOVERNING_ADR,
        "genai_enablement_git_commit": git_head(ROOT),
        "members": {
            "sp86_omniscience": {k: v for k, v in sp86.items()},
            "sp87_barbarossa": {k: v for k, v in sp87.items() if k != "raw"},
            "sp90_go_baseline_transitively_via_sp87": {
                k: v for k, v in sp90.items() if k != "raw"
            },
            "sp88_platform_portal": sp88,
        },
        "sp60_pw0_policy_digest": SP60_PW0_POLICY_DIGEST,
        "sp60_pw0_policy_revision": SP60_PW0_POLICY_REVISION,
        "acceptance_criteria": acceptance_criteria,
        "buildable_acceptance_criteria": list(buildable),
        "environment_gated_acceptance_criteria": list(environment_gated),
        "status": "GREEN" if buildable_pass else "RED",
        "reasons": (
            []
            if buildable_pass
            else [
                f"{ac_id} did not PASS"
                for ac_id in buildable
                if acceptance_criteria[ac_id]["status"] != "PASS"
            ]
        ),
        "overall_note": (
            "status=GREEN here means every buildable AC (join, membership, severance-"
            "from-fixtures) passed; it does NOT mean the profile is qualified for "
            "activation. AC-SP89-3/5/6 remain honestly RED (environment-gated, no "
            "named non-production environment receipt exists) regardless of this "
            "status, and this task authorizes no deployment, infrastructure mutation, "
            "or production-readiness claim."
        ),
    }
    lock_body_digest = sha256_hex(canonical_json_bytes(lock))
    lock["profile_lock_digest"] = lock_body_digest
    return lock


def write_evidence(lock: dict[str, Any]) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    commit = lock.get("genai_enablement_git_commit") or "uncommitted"
    path = EVIDENCE_DIR / f"profile-lock.{commit}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("profile_lock_digest") != lock.get("profile_lock_digest"):
            raise QualificationError(
                f"refusing to overwrite existing immutable evidence file with different content: {path}"
            )
        return path
    path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def print_report(lock: dict[str, Any]) -> None:
    print(json.dumps(lock, indent=2, sort_keys=True))
    print("\n--- per-AC summary ---", file=sys.stderr)
    for ac_id, ac in sorted(lock["acceptance_criteria"].items()):
        print(f"{ac_id}: {ac['status']}", file=sys.stderr)
    print(f"\noverall lock status: {lock['status']}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        action="store_true",
        help="print the report only; do not write evidence",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write evidence only; suppress the stdout report",
    )
    args = parser.parse_args()

    try:
        lock = build_profile_lock()
    except QualificationError as exc:
        print(f"QUALIFICATION RED: {exc}", file=sys.stderr)
        return 1

    if args.write and not args.report:
        write_evidence(lock)
    elif args.report and not args.write:
        print_report(lock)
    else:
        path = write_evidence(lock)
        print_report(lock)
        print(f"\nevidence written to: {path.relative_to(ROOT)}", file=sys.stderr)

    buildable = lock["buildable_acceptance_criteria"]
    buildable_pass = all(
        lock["acceptance_criteria"][ac_id]["status"] == "PASS" for ac_id in buildable
    )
    return 0 if buildable_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
