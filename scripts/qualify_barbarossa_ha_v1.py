#!/usr/bin/env python3
"""Join the SP-89 base-profile lock, the SP-92 Barbarossa HA owner release and
the SP-93 Portal HA experience -- plus the SP-90 Go baseline and SP-91
distributed-work substrate transitively bound by SP-92 -- into one
content-addressed `barbarossa-ha-v1` profile lock, and independently qualify
AC-SP94-1..8 (task-sp-94-barbarossa-ha-profile-qualification).

Read-only across every cross-repository input: this script never writes to
Barbarossa/ or platform-portal/, and never executes their code. It writes only
inside this repository's docs/synchronized-platform/releases/barbarossa-ha-v1/
evidence/ directory (content-addressed by this repository's HEAD commit,
append-only, never overwritten).

THE LOAD-BEARING FACT: **there is no committed SP-92 release receipt.**
Barbarossa's `HighAvailabilityRelease` (internal/runtime/api/release.go) is
computed only when a release run supplies externally measured build facts, is
registered on no HTTP route, and is committed nowhere. Barbarossa's own
committed expected verdicts (testdata/conformance/ha-runtime-v1/expected/
ac-verdicts.json) record overall_status RED with AC-SP92-1..5 RED. AC-SP94-1
therefore cannot be a PASS, however many cross-checks succeed -- and this
script says so with the exact missing input named rather than manufacturing a
digest.

AC-SP94-2 (commit/ACK/crash matrix), -3 (fencing/ordering/DLQ), -4
(failure-domain matrix), -5 (capacity/soak/rollout) and -8 (external alerts,
evidence signature, rollback) additionally require one named non-production HA
environment plus load-generation, fault-injection and alert-observer
authority. None exists. This script is forbidden from creating one (see
docs/specs/task-sp-94-barbarossa-ha-profile-qualification.md "Authority
boundary"), so those five are emitted as honest RED/decision-required
evidence. The only startable Barbarossa runtime here -- the
`management-readonly-local-v1` single-host Docker stack -- is used strictly as
a NEGATIVE CONTROL: its own committed topology declares ha_qualified=false, so
it proves those criteria cannot be qualified here. It is never presented as HA
evidence.

This script never raises. Every missing, dirty, absent or unverifiable input
becomes a typed reason inside the returned object.

`buildable_result: GREEN` on any criterion means only "this buildable check
passed". It is never profile activation, HA qualification or production
readiness.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SIBLINGS_ROOT = ROOT.parent
BARBAROSSA_ROOT = SIBLINGS_ROOT / "Barbarossa"
PORTAL_ROOT = SIBLINGS_ROOT / "platform-portal"

PROFILE_ID = "barbarossa-ha-v1"
PROFILE_REVISION = "1.0.0"
GOVERNING_ADR = "ADR-0023"
BASE_PROFILE_ID = "management-readonly-v1"

#: The exact committed SP-89 receipt this join pins. Content-addressed by the
#: genai-enablement commit that produced it; re-hashed here, never trusted
#: from a downstream copy. A locally re-run, uncommitted sibling evidence file
#: is NOT this pin and is reported separately.
SP89_EVIDENCE_FILENAME = "profile-lock.ac32c722235b435bf0632919924d8648a71653a1.json"

REGISTRY_RELPATH = "portfolio/synchronized-platform.json"
GATING_FIXTURE_RELPATH = "tests/fixtures/barbarossa-ha-v1/environment-gating.json"
SP89_EVIDENCE_RELDIR = (
    "docs/synchronized-platform/releases/management-readonly-v1/evidence"
)
RELEASE_RELDIR = "docs/synchronized-platform/releases/barbarossa-ha-v1"

# --- Barbarossa (owner, read-only) -----------------------------------------
BARB_SCHEMA_GO = "internal/runtime/projection/schema.go"
BARB_PROJECTION_GO = "internal/runtime/projection/projection.go"
BARB_SERVER_GO = "internal/runtime/api/server.go"
BARB_HEALTH_GO = "internal/runtime/health/health.go"
BARB_HA_RELEASE_GO = "internal/runtime/api/release.go"
BARB_HA_VERDICTS = "testdata/conformance/ha-runtime-v1/expected/ac-verdicts.json"
BARB_HA_MANIFEST = "testdata/conformance/ha-runtime-v1/manifest.json"
BARB_LOCAL_TOPOLOGY = "deploy/config/management-readonly-local/topology.json"
BARB_SP90_RUNBOOK = "docs/runbooks/go-runtime-migration.md"
BARB_SP91_RUNBOOK = "docs/runbooks/distributed-work.md"
BARB_HA_RUNBOOK = "docs/runbooks/high-availability.md"

#: The exact committed Barbarossa artifacts that constitute the SP-92 HA input
#: set. Hashed here to give the join a reproducible identity for the owner's
#: source even though the owner mints no receipt over them.
BARB_HA_ARTIFACTS = (
    "deploy/ha/api-deployment.json",
    "deploy/ha/api-pdb.json",
    "deploy/ha/api-service.json",
    "deploy/ha/worker-deployment.json",
    "deploy/ha/worker-hpa.json",
    "deploy/ha/worker-pdb.json",
    "deploy/ha/capacity-envelope.json",
    "deploy/ha/alerts.json",
    "deploy/jetstream/stream.json",
    "deploy/jetstream/consumer.json",
    "deploy/jetstream/account-permissions.json",
    "deploy/postgresql/ha-cluster.yaml",
    BARB_HA_RUNBOOK,
    "docs/runbooks/capacity-and-scaling.md",
    "docs/runbooks/queue-recovery.md",
)

# --- Platform Portal (owner, read-only) ------------------------------------
PORTAL_HA_PROFILE = "workflows/runtime_profiles/barbarossa-ha-v1/profile.json"
PORTAL_HA_SECTIONS = (
    "workflows/runtime_profiles/barbarossa-ha-v1/section-responses.json"
)
PORTAL_HA_PKG = "backend/app/cmc/barbarossa_ha"
PORTAL_HA_PINS = f"{PORTAL_HA_PKG}/pins.py"
PORTAL_HA_RELEASE_LOCK = f"{PORTAL_HA_PKG}/release_lock.py"
PORTAL_SP88_PINS = "backend/app/runtime_profiles/pins.py"
PORTAL_HA_RUNBOOK = "docs/runbooks/barbarossa-ha-observability.md"

PORTAL_HA_SOURCE_FILES = (
    PORTAL_HA_PROFILE,
    PORTAL_HA_SECTIONS,
    f"{PORTAL_HA_PKG}/__init__.py",
    f"{PORTAL_HA_PKG}/client.py",
    f"{PORTAL_HA_PKG}/config.py",
    PORTAL_HA_PINS,
    f"{PORTAL_HA_PKG}/read.py",
    PORTAL_HA_RELEASE_LOCK,
    f"{PORTAL_HA_PKG}/startup_checks.py",
    f"{PORTAL_HA_PKG}/states.py",
    PORTAL_HA_RUNBOOK,
)

#: Clients that would give the Portal direct broker/store/infrastructure
#: authority. Portal's own profile.json declares them forbidden; this scan
#: verifies that declaration against the real committed imports.
FORBIDDEN_PORTAL_CLIENTS = frozenset(
    {
        "nats",
        "jetstream",
        "asyncpg",
        "psycopg",
        "psycopg2",
        "sqlalchemy",
        "kubernetes",
        "boto3",
        "redis",
        "kafka",
        "confluent_kafka",
        "docker",
    }
)
FORBIDDEN_HTTP_METHOD_CALLS = frozenset({"post", "put", "patch", "delete"})

#: Any of these on the owner's published projection would let a consumer date
#: a reading. The SP-92 projection has none, which is exactly why Portal can
#: never classify this section `fresh`.
FRESHNESS_MARKER_FIELDS = frozenset(
    {
        "produced_at",
        "observed_at",
        "freshness_deadline",
        "contract_revision",
        "source_health",
        "generated_at",
        "as_of",
    }
)

EXPECTED_RUNTIME_COMPONENTS = ["omniscience", "barbarossa", "platform-portal"]
EXPECTED_DEFERRED_COMPONENTS = ["omnius"]
EXPECTED_SELECTED_DOMAIN_PACKS = ["reliability"]
EXPECTED_OWNER_ROUTES = [
    "/livez",
    "/readyz",
    "/startupz",
    "/v1/availability",
    "/v1/health",
]
EXPECTED_FORBIDDEN_CAPABILITIES = frozenset(
    {"pause", "retry", "redrive", "scale", "drain", "failover", "rollback"}
)

ENVIRONMENT_GATED_ACS = (
    "AC-SP94-2",
    "AC-SP94-3",
    "AC-SP94-4",
    "AC-SP94-5",
    "AC-SP94-8",
)
BUILDABLE_ACS = ("AC-SP94-1", "AC-SP94-6", "AC-SP94-7")

REQUIRED_ENVIRONMENT_RECEIPT_FIELDS = (
    "environment_identity",
    "environment_owner",
    "failure_domains",
    "allowed_faults",
    "load_generation_authority",
    "alert_observer",
    "observation_window",
    "rollback_target",
    "prior_release_digest",
)

AUTHORITY_BOUNDARY = (
    "docs/specs/task-sp-94-barbarossa-ha-profile-qualification.md 'Authority boundary' "
    "restricts this task to read-only inspection, load generation and only the exact "
    "failure/rollback probes listed in a named non-production authority receipt. It "
    "authorizes no Terraform/OpenTofu/Terragrunt apply or destroy, no production "
    "deployment, no secrets, no DNS, no redrive, no domain/effect activation and no "
    "production-readiness claim. A missing input produces RED/decision-required "
    "evidence, never a mock substitution and never a partial PASS."
)

NON_ACTIVATION_NOTE = (
    "buildable_result=GREEN means only that this buildable check passed. It is not "
    "profile activation, HA qualification or a production-readiness claim. "
    "activation_authority=none."
)


class QualificationError(Exception):
    """A required input is missing, mutable, incompatible or unverifiable.

    Raised only by low-level parsers. Every call site converts it into a typed
    reason inside the returned object -- `build_profile_lock` never raises.
    """


# ---------------------------------------------------------------------------
# Path resolution (indirect, so tests can repoint a whole checkout).
# ---------------------------------------------------------------------------


def barb(relpath: str) -> Path:
    return BARBAROSSA_ROOT / relpath


def portal(relpath: str) -> Path:
    return PORTAL_ROOT / relpath


def here(relpath: str) -> Path:
    return ROOT / relpath


def sp89_evidence_path() -> Path:
    return here(SP89_EVIDENCE_RELDIR) / SP89_EVIDENCE_FILENAME


def environment_receipt_path() -> Path:
    return here(RELEASE_RELDIR) / "environment-receipt.json"


def evidence_dir() -> Path:
    return here(RELEASE_RELDIR) / "evidence"


# ---------------------------------------------------------------------------
# Digest / IO helpers.
# ---------------------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise QualificationError(f"missing required input: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:  # unreadable is not the same as absent
        raise QualificationError(f"unreadable required input: {path}: {exc}") from exc


def read_text(path: Path) -> str:
    return read_bytes(path).decode("utf-8")


def read_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise QualificationError(f"unparseable json input: {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    return sha256_hex(read_bytes(path))


def file_set_digest(
    root: Path, relpaths: tuple[str, ...]
) -> tuple[str, dict[str, str]]:
    """Content digest over an explicit, ordered file set. Every member must
    exist; a silently-skipped file would make the digest meaningless."""
    if not relpaths:
        raise QualificationError("refusing to digest an empty file set")
    per_file = {rel: sha256_file(root / rel) for rel in relpaths}
    return sha256_hex(canonical_json_bytes(per_file)), per_file


def is_placeholder(value: Any) -> bool:
    """True for runbook template text like 'sha256:<sha256 of ...>'. Such a
    value is never a real digest and must never be compared or emitted as
    one."""
    return isinstance(value, str) and "<" in value and ">" in value


def _git(repo_root: Path, *args: str) -> str | None:
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


def git_head(repo_root: Path) -> str | None:
    return _git(repo_root, "rev-parse", "HEAD")


def git_tracked(repo_root: Path, path: Path) -> bool:
    try:
        rel = path.relative_to(repo_root).as_posix()
    except ValueError:
        return False
    return _git(repo_root, "ls-files", "--error-unmatch", rel) is not None


# ---------------------------------------------------------------------------
# Owner-source parsers. Nothing here executes Barbarossa or Portal code.
# ---------------------------------------------------------------------------

_GO_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
_GO_STRUCT_FIELD = re.compile(
    r'^\s*(?P<name>[A-Z]\w*)\s+(?P<type>[\w.\[\]*]+)\s+`json:"(?P<tag>[^",]+)"'
)
_SAFE_FIELD_NAME = re.compile(r"\A[a-z][a-z0-9_]*\Z")

GO_TYPE_TO_JSON = {
    "int": "integer",
    "int32": "integer",
    "int64": "integer",
    "float32": "number",
    "float64": "number",
    "bool": "boolean",
    "string": "string",
    "shared.SubjectScope": "string",
    "shared.Integrity": "object",
}


def parse_go_string_slice(text: str, var_name: str, source: str) -> list[str]:
    """Ordered string literals of `var <name> = []string{...}`."""
    match = re.search(
        rf"{re.escape(var_name)}\s*=\s*\[\]string\{{(.*?)\}}", text, re.DOTALL
    )
    if not match:
        raise QualificationError(f"go []string {var_name!r} not found in {source}")
    values = [m.group(1) for m in _GO_STRING.finditer(match.group(1))]
    if not values:
        raise QualificationError(f"go []string {var_name!r} is empty in {source}")
    return values


def parse_go_struct_json_fields(
    text: str, struct_name: str, source: str
) -> list[tuple[str, str]]:
    """Ordered (json_tag, go_type) pairs of a Go struct's tagged fields."""
    match = re.search(
        rf"type\s+{re.escape(struct_name)}\s+struct\s*\{{(.*?)\n\}}", text, re.DOTALL
    )
    if not match:
        raise QualificationError(f"go struct {struct_name!r} not found in {source}")
    fields = [
        (m.group("tag"), m.group("type"))
        for line in match.group(1).splitlines()
        if (m := _GO_STRUCT_FIELD.match(line))
    ]
    if not fields:
        raise QualificationError(
            f"go struct {struct_name!r} has no json tags in {source}"
        )
    return fields


def parse_go_mux_routes(server_text: str, health_text: str, source: str) -> list[str]:
    """Route paths registered on the owner's read-only mux, resolving the
    health-contract constants to their literal values."""
    contract = re.search(
        r"Contract\{LivePath:\s*\"([^\"]+)\",\s*ReadyPath:\s*\"([^\"]+)\","
        r"\s*StartupPath:\s*\"([^\"]+)\"\}",
        health_text,
    )
    if not contract:
        raise QualificationError(f"health Contract defaults not found for {source}")
    resolved = {
        "s.contract.LivePath": contract.group(1),
        "s.contract.ReadyPath": contract.group(2),
        "s.contract.StartupPath": contract.group(3),
    }
    routes: list[str] = []
    for raw in re.findall(r"mux\.HandleFunc\(\s*([^,]+),", server_text):
        token = raw.strip()
        if token.startswith('"') and token.endswith('"'):
            routes.append(token[1:-1])
        elif token in resolved:
            routes.append(resolved[token])
        else:
            raise QualificationError(
                f"unresolved mux route expression in {source}: {token!r}"
            )
    if not routes:
        raise QualificationError(f"no mux routes found in {source}")
    return sorted(routes)


def parse_python_literals(
    text: str, names: tuple[str, ...], source: str
) -> dict[str, Any]:
    """Literal module-level constants, read via `ast` -- never executed."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise QualificationError(f"unparseable python source {source}: {exc}") from exc
    found: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
            value: ast.expr | None = node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id in names:
                try:
                    found[target.id] = ast.literal_eval(value)
                except (ValueError, SyntaxError) as exc:
                    raise QualificationError(
                        f"{target.id!r} in {source} is not a literal constant: {exc}"
                    ) from exc
    missing = sorted(set(names) - found.keys())
    if missing:
        raise QualificationError(f"constants not found in {source}: {missing}")
    return found


def parse_python_dict_value(text: str, key: str, source: str) -> Any:
    """Literal value of `key` in any dict literal in a Python source file."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise QualificationError(f"unparseable python source {source}: {exc}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key_node, value_node in zip(node.keys, node.values, strict=False):
            if isinstance(key_node, ast.Constant) and key_node.value == key:
                try:
                    return ast.literal_eval(value_node)
                except (ValueError, SyntaxError) as exc:
                    raise QualificationError(
                        f"dict value for {key!r} in {source} is not a literal: {exc}"
                    ) from exc
    raise QualificationError(f"dict key {key!r} not found in {source}")


def extract_json_fence(text: str, heading_pattern: str, source: str) -> dict[str, Any]:
    heading = re.search(heading_pattern, text)
    if not heading:
        raise QualificationError(f"heading not found in {source}: {heading_pattern!r}")
    fence = re.search(r"```json\n(.*?)\n```", text[heading.end() :], re.DOTALL)
    if not fence:
        raise QualificationError(f"no fenced json block after heading in {source}")
    try:
        return json.loads(fence.group(1))
    except json.JSONDecodeError as exc:
        raise QualificationError(f"unparseable fenced json in {source}: {exc}") from exc


def parse_verdict_table(text: str, ac_prefix: str, source: str) -> dict[str, str]:
    """`| AC-SPnn-k | requirement | **GREEN** | why |` runbook rows."""
    rows = re.findall(
        rf"^\|\s*({re.escape(ac_prefix)}-\d+)\s*\|[^|]*\|\s*\*\*([^*]+)\*\*\s*\|",
        text,
        re.MULTILINE,
    )
    if not rows:
        raise QualificationError(f"no {ac_prefix} verdict rows found in {source}")
    return {
        ac_id: ("GREEN" if raw.strip().upper().startswith("GREEN") else "RED")
        for ac_id, raw in rows
    }


def snake_to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


def derive_projection_schema_digest(fields: list[str]) -> str:
    """Re-derive Barbarossa's `projection.SchemaDigest()` from the owner's own
    field list: `"sha256:" + sha256(canonical-JSON(fields))`, where the owner's
    canonical JSON (internal/shared/integrity.go) is separator-free and
    order-preserving. Go's encoding/json HTML-escapes `<`, `>` and `&` while
    Python's does not, so the two canonicalizations provably agree only over
    the owner's `[a-z][a-z0-9_]*` field vocabulary -- anything else fails
    closed rather than emitting a digest that might silently disagree."""
    if not fields:
        raise QualificationError("refusing to derive a schema digest from no fields")
    for field in fields:
        if not _SAFE_FIELD_NAME.match(field):
            raise QualificationError(
                f"projection field {field!r} is outside the owner's [a-z][a-z0-9_]* "
                "vocabulary; the Go and Python canonicalizations cannot be proven equal"
            )
    return sha256_hex(json.dumps(fields, separators=(",", ":")).encode("utf-8"))


def guarded(builder_name: str, fn: Any) -> dict[str, Any]:
    """Run a member builder, converting any failure into a typed error list."""
    try:
        return fn()
    except QualificationError as exc:
        return {"member": builder_name, "errors": [str(exc)]}
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        RecursionError,
    ) as exc:
        return {"member": builder_name, "errors": [f"{type(exc).__name__}: {exc}"]}


# ---------------------------------------------------------------------------
# Members.
# ---------------------------------------------------------------------------


def build_sp89_member() -> dict[str, Any]:
    """The SP-89 base-profile lock: this repository's own committed evidence,
    re-hashed here and re-derived against its own content-addressing."""
    path = sp89_evidence_path()
    payload = read_json(path)
    recorded = payload.get("profile_lock_digest")
    body = {k: v for k, v in payload.items() if k != "profile_lock_digest"}
    members = payload.get("members", {})
    return {
        "member": "sp89_base_profile",
        "source": str(path.relative_to(ROOT)),
        "committed": git_tracked(ROOT, path),
        "evidence_file_digest": sha256_file(path),
        "recorded_profile_lock_digest": recorded,
        "independently_rederived_profile_lock_digest": sha256_hex(
            canonical_json_bytes(body)
        ),
        "profile_id": payload.get("profile_id"),
        "genai_enablement_git_commit": payload.get("genai_enablement_git_commit"),
        "own_declared_status": payload.get("status"),
        "own_declared_ac_status": {
            ac_id: ac.get("status")
            for ac_id, ac in payload.get("acceptance_criteria", {}).items()
        },
        "sp86_release_lock_digest": members.get("sp86_omniscience", {}).get(
            "release_lock_digest"
        ),
        "sp87_published_block_digest": members.get("sp87_barbarossa", {}).get(
            "published_block_digest"
        ),
        "sp90_published_block_digest": members.get(
            "sp90_go_baseline_transitively_via_sp87", {}
        ).get("published_block_digest"),
        # The digest SP-87's own block DECLARES for the SP-90 baseline, i.e.
        # the owner's `runtime.Sp90BaselineDigest()` value. This is a different
        # quantity from the hash of SP-90's published runbook block above, and
        # the two are deliberately never compared to each other.
        "sp87_declared_sp90_baseline_digest": members.get("sp87_barbarossa", {}).get(
            "sp90_baseline_digest"
        ),
        "sp88_source_receipt_digest": members.get("sp88_platform_portal", {}).get(
            "source_receipt_digest"
        ),
        "sp60_pw0_policy_digest": payload.get("sp60_pw0_policy_digest"),
        "uncommitted_sibling_evidence_files": sorted(
            p.name
            for p in here(SP89_EVIDENCE_RELDIR).glob("profile-lock.*.json")
            if p.name != SP89_EVIDENCE_FILENAME
        ),
        "errors": [],
    }


def build_sp90_member() -> dict[str, Any]:
    """SP-90 Go baseline, transitively bound through SP-87/SP-92. No committed
    receipt file; the owner publishes a fenced JSON block in its runbook."""
    block = extract_json_fence(
        read_text(barb(BARB_SP90_RUNBOOK)),
        r"## BarbarossaGoRuntimeBaseline \(AC-SP90-7\)",
        BARB_SP90_RUNBOOK,
    )
    return {
        "member": "sp90_go_baseline",
        "source": f"Barbarossa/{BARB_SP90_RUNBOOK}",
        "published_block_digest": sha256_hex(canonical_json_bytes(block)),
        "git_commit": block.get("git_commit"),
        "go_toolchain_version": block.get("go_toolchain_version"),
        "go_module_graph_digest": block.get("go_module_graph_digest"),
        "binary_digest": block.get("binary_digest"),
        "image_digest": block.get("image_digest"),
        "sbom_digest": block.get("sbom_digest"),
        "errors": [],
    }


def build_sp91_member() -> dict[str, Any]:
    """SP-91 distributed-work substrate, transitively bound through SP-92. The
    owner commits no `BarbarossaDistributedWorkRelease` receipt either; its
    runbook publishes the AC verdict table -- including AC-SP91-7 ('one
    immutable substrate receipt'), which it records RED."""
    verdicts = parse_verdict_table(
        read_text(barb(BARB_SP91_RUNBOOK)), "AC-SP91", BARB_SP91_RUNBOOK
    )
    return {
        "member": "sp91_distributed_work_substrate",
        "source": f"Barbarossa/{BARB_SP91_RUNBOOK}",
        "runbook_digest": sha256_file(barb(BARB_SP91_RUNBOOK)),
        "own_declared_ac_verdicts": verdicts,
        "own_declared_red_acs": sorted(k for k, v in verdicts.items() if v != "GREEN"),
        "release_receipt_digest": None,
        "release_receipt_absent_reason": (
            "the owner commits no BarbarossaDistributedWorkRelease receipt; AC-SP91-7 is "
            "recorded RED in its own runbook"
        ),
        "errors": [],
    }


def scan_for_committed_ha_receipt() -> dict[str, Any]:
    """Search the whole Barbarossa checkout for a committed
    `HighAvailabilityRelease`-shaped JSON receipt. A scan that examined no
    files is a defect, not an absence -- it fails loudly."""
    root = BARBAROSSA_ROOT
    if not root.is_dir():
        raise QualificationError(f"Barbarossa checkout not present at {root}")
    scanned = 0
    matches: list[str] = []
    for path in sorted(root.rglob("*.json")):
        if ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        if "ha-runtime-v1" not in text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(payload, dict)
            and payload.get("profile_id") == "ha-runtime-v1"
            and (
                "sp91_substrate_digest" in payload
                or "rendered_topology_digest" in payload
            )
        ):
            matches.append(path.relative_to(root).as_posix())
    if scanned == 0:
        raise QualificationError(
            f"committed-HA-receipt scan examined 0 json files under {root}; a scan that "
            "matches nothing because it read nothing is a defect, not an absence"
        )
    return {"json_files_scanned": scanned, "matches": matches}


def build_sp92_member() -> dict[str, Any]:
    """SP-92 Barbarossa HA owner release. There is NO committed receipt; only
    the projection schema identity is stably re-derivable, and the owner's own
    committed expected verdicts record overall_status RED."""
    schema_fields = parse_go_string_slice(
        read_text(barb(BARB_SCHEMA_GO)), "projectionSchemaFields", BARB_SCHEMA_GO
    )
    struct_fields = parse_go_struct_json_fields(
        read_text(barb(BARB_PROJECTION_GO)),
        "AvailabilityProjection",
        BARB_PROJECTION_GO,
    )
    verdicts_doc = read_json(barb(BARB_HA_VERDICTS))
    routes = parse_go_mux_routes(
        read_text(barb(BARB_SERVER_GO)), read_text(barb(BARB_HEALTH_GO)), BARB_SERVER_GO
    )
    artifact_digest, per_file = file_set_digest(BARBAROSSA_ROOT, BARB_HA_ARTIFACTS)
    release_source = read_text(barb(BARB_HA_RELEASE_GO))
    return {
        "member": "sp92_barbarossa_ha_release",
        "source": f"Barbarossa/{BARB_HA_RELEASE_GO}",
        "git_commit": git_head(BARBAROSSA_ROOT),
        "release_receipt_digest": None,
        "release_receipt_absent_reason": (
            "HighAvailabilityRelease (internal/runtime/api/release.go) is computed only by a "
            "release run supplying externally measured binary/image/SBOM/chart facts, is "
            "registered on no HTTP route, and is committed nowhere in the owner repository"
        ),
        "committed_receipt_scan": scan_for_committed_ha_receipt(),
        "projection_schema_fields": schema_fields,
        "projection_schema_digest_independently_rederived": derive_projection_schema_digest(
            schema_fields
        ),
        "projection_struct_json_fields": [name for name, _ in struct_fields],
        "projection_struct_go_types": dict(struct_fields),
        "published_routes": routes,
        "own_declared_conformance_overall_status": verdicts_doc.get("overall_status"),
        "own_declared_conformance_verdicts": verdicts_doc.get("verdicts", {}),
        "conformance_verdicts_digest": sha256_file(barb(BARB_HA_VERDICTS)),
        "conformance_manifest_digest": sha256_file(barb(BARB_HA_MANIFEST)),
        "ha_artifact_content_digest": artifact_digest,
        "ha_artifact_file_digests": per_file,
        "ha_artifact_digest_note": (
            "genai-enablement-computed content digest over the owner's committed HA artifact "
            "bytes. It is NOT the owner's rendered_topology_digest / capacity_envelope_digest "
            "/ alert_runbook_digest, which only the owner's own release run can mint. It "
            "exists to give this join a reproducible identity for the owner source and to "
            "fail closed if that source drifts."
        ),
        "externally_measured_digests_absent": [
            "binary_digest",
            "image_digest",
            "sbom_digest",
            "chart_digest",
            "configuration_digest",
        ],
        "release_source_declares_live_pending_gates": sorted(
            re.findall(r'pending\["(live_[a-z_]+)"\]', release_source)
        ),
        "errors": [],
    }


def _portal_declared_red_reasons(
    pins: dict[str, Any], accessibility_refs: Any
) -> list[str]:
    """Re-derive, from Portal's own literal pins, the RED reasons its
    release_lock.py would emit -- without executing it."""
    reasons: list[str] = []
    if pins["SP92_RELEASE_RECEIPT_DIGEST"] is None:
        reasons.append("sp92_release_receipt_absent")
    if pins["SP92_CONFORMANCE_OVERALL_STATUS"] != "GREEN":
        reasons.append("sp92_conformance_overall_status_red")
    reasons.extend(
        f"sp92_acceptance_criterion_red:{ac_id}"
        for ac_id, verdict in sorted(pins["SP92_CONFORMANCE_VERDICTS"].items())
        if verdict != "GREEN"
    )
    if not accessibility_refs:
        reasons.append("accessibility_evidence_absent")
    return reasons


def build_sp93_member() -> dict[str, Any]:
    """SP-93 Portal HA experience: real committed Portal source and shipped
    runtime-profile artifacts, hashed here. Portal's own code is never
    executed; its literal pins are read with `ast`."""
    source_digest, per_file = file_set_digest(PORTAL_ROOT, PORTAL_HA_SOURCE_FILES)
    profile = read_json(portal(PORTAL_HA_PROFILE))
    sections = read_json(portal(PORTAL_HA_SECTIONS))
    pins = parse_python_literals(
        read_text(portal(PORTAL_HA_PINS)),
        (
            "BARBAROSSA_HA_PROFILE_ID",
            "BARBAROSSA_HA_AVAILABILITY_PATH",
            "SP92_HA_PROJECTION_FIELDS",
            "SP92_HA_PROJECTION_SCHEMA_DIGEST",
            "BARBAROSSA_HA_AVAILABILITY_CLASS",
            "BARBAROSSA_HA_QUALIFIED",
            "BARBAROSSA_HA_NOT_QUALIFIED_AXES",
            "BARBAROSSA_HA_ABSENT_AXES",
            "BARBAROSSA_HA_ABSENT_AXIS_REASON",
            "SP92_RELEASE_RECEIPT_DIGEST",
            "SP92_CONFORMANCE_OVERALL_STATUS",
            "SP92_CONFORMANCE_VERDICTS",
        ),
        PORTAL_HA_PINS,
    )
    sp88_pins = parse_python_literals(
        read_text(portal(PORTAL_SP88_PINS)), ("SP90_BASELINE_DIGEST",), PORTAL_SP88_PINS
    )
    lock_text = read_text(portal(PORTAL_HA_RELEASE_LOCK))
    lock_consts = parse_python_literals(
        lock_text, ("PROFILE_ID", "PROFILE_REVISION"), PORTAL_HA_RELEASE_LOCK
    )
    accessibility_refs = parse_python_dict_value(
        lock_text, "accessibility_evidence_refs", PORTAL_HA_RELEASE_LOCK
    )
    return {
        "member": "sp93_portal_ha_experience",
        "sources": [f"platform-portal/{rel}" for rel in PORTAL_HA_SOURCE_FILES],
        "source_file_digests": per_file,
        "source_receipt_digest": source_digest,
        "git_commit": git_head(PORTAL_ROOT),
        "runtime_profile_digest": sha256_file(portal(PORTAL_HA_PROFILE)),
        "section_responses_digest": sha256_file(portal(PORTAL_HA_SECTIONS)),
        "portal_profile_id": lock_consts["PROFILE_ID"],
        "portal_profile_revision": lock_consts["PROFILE_REVISION"],
        "declared_profile": profile,
        "pins": pins,
        "sp88_sp90_baseline_digest_copy": sp88_pins["SP90_BASELINE_DIGEST"],
        "accessibility_evidence_refs": accessibility_refs,
        "section_case_states": [
            {
                "case": case.get("case"),
                "state": (case.get("response") or {}).get("state"),
                "reason": (case.get("response") or {}).get("reason"),
                "availability_rendered": (case.get("response") or {}).get(
                    "availability"
                )
                is not None,
                "sp92_pin_status": (
                    (case.get("response") or {}).get("sp92Pin") or {}
                ).get("status"),
            }
            for case in sections.get("cases", [])
        ],
        "section_field_types": sections.get("fieldTypes", {}),
        "own_declared_release_lock_red_reasons": _portal_declared_red_reasons(
            pins, accessibility_refs
        ),
        "note": (
            "No committed PortalBarbarossaHighAvailabilityRelease evidence file exists; "
            "source_receipt_digest hashes the real committed Portal source and shipped "
            "runtime-profile artifacts. build_barbarossa_ha_release_lock() is never executed "
            "by this read-only cross-repository join."
        ),
        "errors": [],
    }


# ---------------------------------------------------------------------------
# Negative control + environment-gating matrix.
# ---------------------------------------------------------------------------


def load_gating_matrix() -> dict[str, Any]:
    return read_json(here(GATING_FIXTURE_RELPATH))


def build_negative_control() -> dict[str, Any]:
    """The `management-readonly-local-v1` single-host stack, joined against the
    gating fixture's expectations. Proof that this environment CANNOT satisfy
    AC-SP94-2/3/4/5 -- never HA evidence."""
    topology = read_json(barb(BARB_LOCAL_TOPOLOGY))
    expected = load_gating_matrix().get("negative_control", {})
    issues: list[str] = []

    def compare(field: str, expected_key: str) -> None:
        if topology.get(field) != expected.get(expected_key):
            issues.append(
                f"{field}: owner topology says {topology.get(field)!r}, fixture claims "
                f"{expected.get(expected_key)!r}"
            )

    compare("availability_class", "expected_availability_class")
    compare("ha_qualified", "expected_ha_qualified")
    compare("activation_authority", "expected_activation_authority")
    compare("queue_replicas", "expected_queue_replicas")
    compare("store_replicas", "expected_store_replicas")
    owner_axes = list(topology.get("not_qualified_axes", []))
    if owner_axes != list(expected.get("expected_not_qualified_axes", [])):
        issues.append(
            f"not_qualified_axes: owner topology says {owner_axes!r}, fixture claims "
            f"{expected.get('expected_not_qualified_axes')!r}"
        )
    if topology.get("ha_qualified") is not False:
        issues.append(
            "the local single-host stack no longer declares ha_qualified=false; it can no "
            "longer serve as the negative control and must never be read as HA evidence"
        )
    if not owner_axes:
        issues.append(
            "owner topology declares no not_qualified_axes; nothing disqualifies it"
        )
    return {
        "member": "negative_control",
        "profile_id": expected.get("profile_id"),
        "source": f"Barbarossa/{BARB_LOCAL_TOPOLOGY}",
        "topology_digest": sha256_file(barb(BARB_LOCAL_TOPOLOGY)),
        "owner_declared_topology": topology,
        "owner_not_qualified_axes": owner_axes,
        "issues": issues,
        "holds": not issues,
        "conclusion": (
            "The only Barbarossa runtime startable here declares itself "
            f"{topology.get('availability_class')!r} with ha_qualified="
            f"{topology.get('ha_qualified')!r} and activation_authority="
            f"{topology.get('activation_authority')!r}. It therefore CANNOT produce ground "
            "truth for AC-SP94-2/3/4/5 and is used only to prove that."
        ),
        "errors": [],
    }


def validate_gating_matrix(negative_control: dict[str, Any]) -> dict[str, Any]:
    """Structural validation of the environment-gating fixture. An empty or
    axis-incomplete matrix is RED, never a silent pass."""
    matrix = load_gating_matrix()
    criteria = matrix.get("environment_gated_criteria", [])
    owner_axes = set(negative_control.get("owner_not_qualified_axes", []))
    issues: list[str] = []
    if not criteria:
        issues.append("environment_gated_criteria is empty")
    declared_ids = sorted(entry.get("id") for entry in criteria if entry.get("id"))
    if declared_ids != sorted(ENVIRONMENT_GATED_ACS):
        issues.append(
            f"declared criteria {declared_ids} != environment-gated set "
            f"{sorted(ENVIRONMENT_GATED_ACS)}"
        )
    if not owner_axes:
        issues.append(
            "no owner not_qualified axes were available to validate the matrix against; "
            "refusing to report a valid gating matrix from an unread negative control"
        )
    covered: set[str] = set()
    for entry in criteria:
        ac_id = entry.get("id", "<unknown>")
        if not entry.get("requirement"):
            issues.append(f"{ac_id}: missing requirement")
        if not entry.get("required_inputs"):
            issues.append(f"{ac_id}: required_inputs is empty")
        if not entry.get("forbidden_substitutes"):
            issues.append(f"{ac_id}: forbidden_substitutes is empty")
        for axis in entry.get("disqualifying_local_axes", []):
            if axis not in owner_axes:
                issues.append(
                    f"{ac_id}: disqualifying axis {axis!r} is not one the owner's own topology "
                    f"declares not_qualified ({sorted(owner_axes)})"
                )
            covered.add(axis)
    uncovered = owner_axes - covered
    if uncovered:
        issues.append(
            "owner not_qualified axes not mapped to any environment-gated criterion: "
            f"{sorted(uncovered)}"
        )
    return {
        "member": "environment_gating_matrix",
        "fixture": GATING_FIXTURE_RELPATH,
        "fixture_digest": sha256_file(here(GATING_FIXTURE_RELPATH)),
        "criteria_count": len(criteria),
        "axes_covered": sorted(covered),
        "issues": issues,
        "valid": not issues,
        "criteria": {entry["id"]: entry for entry in criteria if entry.get("id")},
        "errors": [],
    }


def find_environment_receipt() -> dict[str, Any] | None:
    path = environment_receipt_path()
    if not path.is_file():
        return None
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(receipt, dict):
        return None
    if [f for f in REQUIRED_ENVIRONMENT_RECEIPT_FIELDS if not receipt.get(f)]:
        return None
    return receipt


# ---------------------------------------------------------------------------
# Acceptance criteria.
# ---------------------------------------------------------------------------


def _ac(
    ac_id: str,
    requirement: str,
    checks: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    scope_boundary: str,
) -> dict[str, Any]:
    buildable_green = bool(checks) and all(c["pass"] for c in checks)
    return {
        "id": ac_id,
        "requirement": requirement,
        "status": "PASS" if buildable_green and not missing else "RED",
        "buildable_result": "GREEN" if buildable_green else "RED",
        "buildable_checks": checks,
        "failed_buildable_checks": [c["name"] for c in checks if not c["pass"]],
        "missing_ground_truth": missing,
        "scope_boundary": scope_boundary,
        "non_activation": NON_ACTIVATION_NOTE,
    }


def _check(checks: list[dict[str, Any]], name: str, expected: Any, actual: Any) -> None:
    checks.append(
        {
            "name": name,
            "expected": expected,
            "actual": actual,
            "pass": expected == actual,
        }
    )


def _members_failed(*members: dict[str, Any]) -> list[str]:
    return [
        f"{member.get('member', '<unknown>')}: {error}"
        for member in members
        for error in member.get("errors", [])
    ]


def _unreadable_ac(
    ac_id: str, requirement: str, scope: str, failures: list[str]
) -> dict[str, Any]:
    return _ac(
        ac_id,
        requirement,
        [
            {
                "name": "every required committed artifact is readable",
                "expected": [],
                "actual": failures,
                "pass": False,
            }
        ],
        [
            {
                "input": "readable committed owner artifacts for every joined member",
                "why_no_substitute": "an unreadable input cannot be independently re-derived",
                "decision_required": "restore the missing sibling checkout or artifact",
                "detail": failures,
            }
        ],
        scope,
    )


def run_ac1(
    sp89: dict[str, Any],
    sp90: dict[str, Any],
    sp91: dict[str, Any],
    sp92: dict[str, Any],
    sp93: dict[str, Any],
    registry_profile_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    requirement = (
        "One content-addressed profile lock joins exact base profile, Barbarossa HA and "
        "Portal HA receipts"
    )
    scope = (
        "A content-addressed join over already-published, committed owner artifacts. It does "
        "not mint an owner receipt, execute owner code, or observe a running system."
    )
    failures = _members_failed(sp89, sp90, sp91, sp92, sp93)
    if failures:
        return _unreadable_ac("AC-SP94-1", requirement, scope, failures)

    checks: list[dict[str, Any]] = []
    schema_digest = sp92["projection_schema_digest_independently_rederived"]
    pins = sp93["pins"]
    profile = sp93["declared_profile"]
    reg = registry_profile_entry or {}

    _check(
        checks, "sp89 receipt is committed (git-tracked) here", True, sp89["committed"]
    )
    _check(
        checks,
        "sp89 profile_lock_digest re-derives from its own committed body",
        sp89["recorded_profile_lock_digest"],
        sp89["independently_rederived_profile_lock_digest"],
    )
    _check(
        checks,
        "sp89 receipt filename commit == the commit it records",
        SP89_EVIDENCE_FILENAME,
        f"profile-lock.{sp89['genai_enablement_git_commit']}.json",
    )
    _check(
        checks, "sp89 profile_id == base profile", BASE_PROFILE_ID, sp89["profile_id"]
    )
    _check(
        checks,
        "sp90 runbook block independently re-hashed == the block digest sp89 recorded",
        sp89["sp90_published_block_digest"],
        sp90["published_block_digest"],
    )
    _check(
        checks,
        "portal sp88 pins' SP90_BASELINE_DIGEST == the owner Sp90BaselineDigest() sp89 recorded "
        "via sp87",
        sp89["sp87_declared_sp90_baseline_digest"],
        sp93["sp88_sp90_baseline_digest_copy"],
    )
    _check(
        checks,
        "sp92 projection struct json tags == projectionSchemaFields (owner lockstep re-verified)",
        sp92["projection_schema_fields"],
        sp92["projection_struct_json_fields"],
    )
    _check(
        checks,
        "portal pins SP92_HA_PROJECTION_FIELDS == owner projectionSchemaFields",
        sp92["projection_schema_fields"],
        list(pins["SP92_HA_PROJECTION_FIELDS"]),
    )
    _check(
        checks,
        "portal pins SP92_HA_PROJECTION_SCHEMA_DIGEST == independently re-derived owner digest",
        schema_digest,
        pins["SP92_HA_PROJECTION_SCHEMA_DIGEST"],
    )
    _check(
        checks,
        "portal profile.json schema_digest == independently re-derived owner digest",
        schema_digest,
        profile.get("consumed_contract", {}).get("schema_digest"),
    )
    _check(
        checks,
        "portal profile.json consumed_contract.fields == owner projectionSchemaFields",
        sp92["projection_schema_fields"],
        profile.get("consumed_contract", {}).get("fields"),
    )
    _check(
        checks,
        "portal pins SP92_CONFORMANCE_VERDICTS == owner committed ac-verdicts.json",
        sp92["own_declared_conformance_verdicts"],
        dict(pins["SP92_CONFORMANCE_VERDICTS"]),
    )
    _check(
        checks,
        "portal pins SP92_CONFORMANCE_OVERALL_STATUS == owner committed overall_status",
        sp92["own_declared_conformance_overall_status"],
        pins["SP92_CONFORMANCE_OVERALL_STATUS"],
    )
    _check(
        checks,
        "portal pins SP92_RELEASE_RECEIPT_DIGEST is None (absent, never fabricated)",
        None,
        pins["SP92_RELEASE_RECEIPT_DIGEST"],
    )
    _check(
        checks,
        "no placeholder template text is carried as an sp90 binary/image/sbom digest",
        [],
        sorted(
            field
            for field in ("binary_digest", "image_digest", "sbom_digest")
            if is_placeholder(sp90.get(field))
        ),
    )
    _check(
        checks,
        "registry runtime_components for barbarossa-ha-v1",
        EXPECTED_RUNTIME_COMPONENTS,
        reg.get("runtime_components"),
    )
    _check(
        checks,
        "registry governing_adr for barbarossa-ha-v1",
        GOVERNING_ADR,
        reg.get("governing_adr"),
    )

    red_sp92_acs = sorted(
        ac_id
        for ac_id, verdict in sp92["own_declared_conformance_verdicts"].items()
        if verdict != "GREEN"
    )
    missing: list[dict[str, Any]] = [
        {
            "input": "an immutable committed SP-92 BarbarossaHighAvailabilityRelease receipt",
            "why_no_substitute": sp92["release_receipt_absent_reason"],
            "decision_required": (
                "the Barbarossa owner must run its own release pipeline with the externally "
                "measured binary/image/SBOM/chart facts and commit the resulting receipt"
            ),
            "detail": {
                "committed_receipt_scan": sp92["committed_receipt_scan"],
                "externally_measured_digests_absent": sp92[
                    "externally_measured_digests_absent"
                ],
            },
        },
        {
            "input": "an SP-92 receipt whose own status is not RED",
            "why_no_substitute": (
                "the owner's own committed expected verdicts record overall_status "
                f"{sp92['own_declared_conformance_overall_status']!r} with {red_sp92_acs} RED; "
                "a downstream join cannot upgrade an owner's honest RED"
            ),
            "decision_required": (
                "a live HA qualification environment must close AC-SP92-1..5 before SP-94 can "
                "join a non-RED owner receipt"
            ),
        },
        {
            "input": "an immutable committed SP-91 BarbarossaDistributedWorkRelease receipt",
            "why_no_substitute": sp91["release_receipt_absent_reason"],
            "decision_required": (
                "SP-91 must publish its substrate receipt; its own runbook records AC-SP91-7 RED"
            ),
            "detail": {"own_declared_red_acs": sp91["own_declared_red_acs"]},
        },
        {
            "input": "SP-90 binary / image / SBOM digests",
            "why_no_substitute": (
                "null by design in the owner's own implementation-baseline receipt; a real "
                "value requires a release pipeline's machine-specific build"
            ),
            "decision_required": "a Barbarossa release build must publish them",
            "detail": {
                "binary_digest": sp90["binary_digest"],
                "image_digest": sp90["image_digest"],
                "sbom_digest": sp90["sbom_digest"],
            },
        },
        {
            "input": "a non-RED SP-93 PortalBarbarossaHighAvailabilityRelease",
            "why_no_substitute": (
                "Portal's own release lock is RED for reasons it cannot close from inside its "
                "own repository"
            ),
            "decision_required": (
                "the upstream SP-92 receipt plus Portal's own accessibility evidence must exist"
            ),
            "detail": {
                "portal_declared_red_reasons": sp93[
                    "own_declared_release_lock_red_reasons"
                ]
            },
        },
        {
            "input": (
                "owner image / chart / SBOM / configuration / capacity / SLO receipt digests for "
                "the HA release"
            ),
            "why_no_substitute": (
                "only the owner's own release run can mint them; this join computes a content "
                "digest over the owner's committed artifact bytes "
                f"({sp92['ha_artifact_content_digest']}) and labels it as exactly that, never "
                "as the owner's rendered_topology / capacity_envelope / alert_runbook digests"
            ),
            "decision_required": "the Barbarossa owner must publish the release receipt",
        },
    ]

    result = _ac("AC-SP94-1", requirement, checks, missing, scope)
    result["upstream_owner_declared_status"] = {
        "sp89": {
            "status": sp89["own_declared_status"],
            "acceptance_criteria": sp89["own_declared_ac_status"],
        },
        "sp91": sp91["own_declared_ac_verdicts"],
        "sp92": {
            "overall_status": sp92["own_declared_conformance_overall_status"],
            "verdicts": sp92["own_declared_conformance_verdicts"],
        },
        "sp93": {"red_reasons": sp93["own_declared_release_lock_red_reasons"]},
    }
    result["red_cause"] = (
        "missing_upstream_owner_receipt"
        if result["buildable_result"] == "GREEN"
        else "cross_check_failed"
    )
    return result


def scan_portal_no_control() -> dict[str, Any]:
    """Read every Python file in Portal's HA package and collect imported
    top-level modules plus mutating HTTP method calls. A scan that read no
    files raises rather than reporting a clean result."""
    pkg = portal(PORTAL_HA_PKG)
    if not pkg.is_dir():
        raise QualificationError(f"portal HA package not present at {pkg}")
    files = sorted(pkg.glob("*.py"))
    if not files:
        raise QualificationError(
            f"no python files found under {pkg}; refusing to report clean"
        )
    imports: set[str] = set()
    mutating: list[str] = []
    for path in files:
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError as exc:
            raise QualificationError(
                f"unparseable portal source {path}: {exc}"
            ) from exc
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in FORBIDDEN_HTTP_METHOD_CALLS
            ):
                mutating.append(f"{path.name}:{node.lineno}:{node.func.attr}")
    return {
        "package": f"platform-portal/{PORTAL_HA_PKG}",
        "files_scanned": len(files),
        "imported_top_level_modules": sorted(imports),
        "forbidden_imports": sorted(imports & FORBIDDEN_PORTAL_CLIENTS),
        "mutating_calls": sorted(mutating),
    }


def run_ac6(sp92: dict[str, Any], sp93: dict[str, Any]) -> dict[str, Any]:
    requirement = (
        "Portal displays exact owner HA truth and remains severable and read-only"
    )
    scope = (
        "Structural verification of Portal's shipped artifacts against Barbarossa's actual "
        "committed contract. It is not an independent API/browser/cache/audit capture against "
        "a running pair, and it does not execute the tampered-fixture matrix live."
    )
    failures = _members_failed(sp92, sp93)
    if failures:
        return _unreadable_ac("AC-SP94-6", requirement, scope, failures)

    checks: list[dict[str, Any]] = []
    profile = sp93["declared_profile"]
    pins = sp93["pins"]
    owner_fields = sp92["projection_schema_fields"]
    owner_types = sp92["projection_struct_go_types"]

    try:
        topology = read_json(barb(BARB_LOCAL_TOPOLOGY))
        scan = scan_portal_no_control()
    except QualificationError as exc:
        return _unreadable_ac("AC-SP94-6", requirement, scope, [str(exc)])

    _check(
        checks,
        "portal read-edge path is an owner-published route",
        True,
        pins["BARBAROSSA_HA_AVAILABILITY_PATH"] in sp92["published_routes"],
    )
    _check(
        checks,
        "owner published route set == the read-only set portal declares",
        EXPECTED_OWNER_ROUTES,
        sp92["published_routes"],
    )
    _check(
        checks,
        "portal owner_qualification == owner committed topology.json",
        [
            topology.get("availability_class"),
            topology.get("ha_qualified"),
            list(topology.get("not_qualified_axes", [])),
        ],
        [
            profile.get("owner_qualification", {}).get("availability_class"),
            profile.get("owner_qualification", {}).get("ha_qualified"),
            list(profile.get("owner_qualification", {}).get("not_qualified_axes", [])),
        ],
    )
    _check(
        checks,
        "portal pins HA qualification == owner committed topology.json",
        [
            topology.get("availability_class"),
            topology.get("ha_qualified"),
            list(topology.get("not_qualified_axes", [])),
        ],
        [
            pins["BARBAROSSA_HA_AVAILABILITY_CLASS"],
            pins["BARBAROSSA_HA_QUALIFIED"],
            list(pins["BARBAROSSA_HA_NOT_QUALIFIED_AXES"]),
        ],
    )

    # Freshness: the owner publishes no marker, so `fresh` is unreachable.
    _check(
        checks,
        "owner projection carries no freshness marker field",
        [],
        sorted(set(owner_fields) & FRESHNESS_MARKER_FIELDS),
    )
    _check(
        checks,
        "portal declares owner_publishes_marker=false, best state unknown, with the owner reason",
        [False, "unknown", "owner-publishes-no-freshness-marker"],
        [
            profile.get("freshness", {}).get("owner_publishes_marker"),
            profile.get("freshness", {}).get("best_achievable_state"),
            profile.get("freshness", {}).get("reason"),
        ],
    )
    states = [case["state"] for case in sp93["section_case_states"]]
    _check(
        checks,
        "no captured portal section response is 'fresh'",
        [],
        [s for s in states if s == "fresh"],
    )
    _check(
        checks,
        "the contract-exact live capture is 'unknown' with the owner-marker reason",
        [("unknown", "owner-publishes-no-freshness-marker")],
        [
            (case["state"], case["reason"])
            for case in sp93["section_case_states"]
            if case["case"] == "live-contract-exact"
        ],
    )
    _check(
        checks,
        "portal renders no availability payload in any unavailable/incompatible state",
        [],
        [
            case["case"]
            for case in sp93["section_case_states"]
            if case["state"] in {"unavailable", "incompatible"}
            and case["availability_rendered"]
        ],
    )
    _check(
        checks,
        "portal captures cover severance, skew and outage states",
        True,
        {"unavailable", "incompatible", "unknown"}.issubset(set(states)),
    )

    # Units: the owner's Go wire types must survive into Portal's declared types.
    availability_types = sp93["section_field_types"].get("availability", {})
    unit_mismatches: list[str] = []
    for field in owner_fields:
        if field == "integrity":
            continue  # the seal is deliberately not re-published
        camel = snake_to_camel(field)
        declared = availability_types.get(camel)
        expected_json_type = GO_TYPE_TO_JSON.get(owner_types.get(field, ""))
        if declared is None:
            unit_mismatches.append(f"{field}: portal declares no type for {camel!r}")
        elif expected_json_type is None:
            unit_mismatches.append(
                f"{field}: unmapped owner go type {owner_types.get(field)!r}"
            )
        elif expected_json_type not in declared:
            unit_mismatches.append(
                f"{field}: owner go type {owner_types.get(field)!r} -> {expected_json_type!r}, "
                f"portal declares {declared!r}"
            )
    _check(
        checks,
        "every owner payload field keeps its owner wire type in portal",
        [],
        unit_mismatches,
    )
    _check(
        checks,
        "the owner integrity seal is not re-published as an availability field",
        False,
        "integrity" in availability_types,
    )

    # Completeness: absent axes are a closed typed list, never zero or false.
    _check(
        checks,
        "portal profile.json absent_axes == portal pins absent axes",
        sorted(pins["BARBAROSSA_HA_ABSENT_AXES"]),
        sorted(entry["axis"] for entry in profile.get("absent_axes", [])),
    )
    _check(
        checks,
        "every absent axis carries the single fixed portal-owned reason",
        [pins["BARBAROSSA_HA_ABSENT_AXIS_REASON"]],
        sorted({entry["reason"] for entry in profile.get("absent_axes", [])}),
    )
    _check(
        checks,
        "no absent axis is silently satisfied by an owner-published field",
        [],
        sorted(
            axis
            for axis in pins["BARBAROSSA_HA_ABSENT_AXES"]
            if snake_to_camel(axis) in availability_types
        ),
    )
    _check(
        checks,
        "portal never derives headroom from the owner's capacity ceiling",
        False,
        "headroom" in availability_types,
    )

    # No control: declared, then verified against the real committed source.
    _check(
        checks,
        "portal profile.json declares GET-only",
        ["GET"],
        profile.get("no_control", {}).get("http_methods"),
    )
    _check(
        checks,
        "portal HA package imports no broker/store/infrastructure client",
        [],
        scan["forbidden_imports"],
    )
    _check(
        checks,
        "portal HA package makes no mutating HTTP call",
        [],
        scan["mutating_calls"],
    )
    _check(
        checks,
        "the no-control scan actually read files",
        True,
        scan["files_scanned"] > 0,
    )

    missing = [
        {
            "input": (
                "independent API, browser, cache and audit captures taken against a running "
                "Portal and Barbarossa HA pair, plus owner-state before/after observations"
            ),
            "why_no_substitute": (
                "Portal's committed section-responses.json is a generated capture of Portal's "
                "own read path over a fixture; it proves the shape Portal renders, not what a "
                "browser and an independent observer see against the real owner under skew, "
                "outage and recovery"
            ),
            "decision_required": (
                "a named non-production environment running both components, plus an "
                "independent observer with browser and cache capture authority"
            ),
        },
        {
            "input": "the tampered-fixture matrix executed against the live read path",
            "why_no_substitute": (
                "a structural comparison of committed artifacts cannot show that a tampered "
                "owner response is rejected at runtime"
            ),
            "decision_required": "a live Portal instance pointed at a controllable owner double",
        },
        {
            "input": "SP-93 accessibility evidence",
            "why_no_substitute": (
                "Portal's own release lock records accessibility_evidence_refs=[] and the "
                "reason accessibility_evidence_absent"
            ),
            "decision_required": "the SP-93 frontend scope must produce and commit it",
        },
    ]
    result = _ac("AC-SP94-6", requirement, checks, missing, scope)
    result["no_control_scan"] = scan
    return result


def run_ac7(
    sp92: dict[str, Any],
    sp93: dict[str, Any],
    registry_profile_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    requirement = "Tenant PW0 membership and no-effect boundaries survive every load and failure path"
    scope = (
        "A static membership and no-effect audit against the accepted ADR-0023 registry "
        "selection and each owner's committed inventories. It is NOT a live workload, network, "
        "DNS, route, secret-name, broker, store, log, trace or UI inventory."
    )
    failures = _members_failed(sp92, sp93)
    if failures:
        return _unreadable_ac("AC-SP94-7", requirement, scope, failures)

    try:
        scan = scan_portal_no_control()
    except QualificationError as exc:
        return _unreadable_ac("AC-SP94-7", requirement, scope, [str(exc)])

    checks: list[dict[str, Any]] = []
    reg = registry_profile_entry or {}
    profile = sp93["declared_profile"]
    _check(
        checks,
        "registry runtime_components",
        EXPECTED_RUNTIME_COMPONENTS,
        reg.get("runtime_components"),
    )
    _check(
        checks,
        "registry deferred_runtime_components (omnius stays deferred)",
        EXPECTED_DEFERRED_COMPONENTS,
        reg.get("deferred_runtime_components"),
    )
    _check(
        checks,
        "registry selected_domain_packs (reliability only)",
        EXPECTED_SELECTED_DOMAIN_PACKS,
        reg.get("selected_domain_packs"),
    )
    _check(checks, "registry pii_profile", "PW0", reg.get("pii_profile"))
    _check(checks, "registry effect_posture", "forbidden", reg.get("effect_posture"))
    _check(
        checks,
        "registry portal_ha_controls",
        "forbidden",
        reg.get("portal_ha_controls"),
    )
    _check(
        checks,
        "registry barbarossa_stream_replicas",
        3,
        reg.get("barbarossa_stream_replicas"),
    )
    _check(
        checks,
        "registry barbarossa_state_store",
        "postgresql-ha",
        reg.get("barbarossa_state_store"),
    )
    _check(
        checks,
        "registry required_work_packages contain the whole HA chain",
        [],
        sorted(
            {"SP-89", "SP-90", "SP-91", "SP-92", "SP-93", "SP-94"}
            - set(reg.get("required_work_packages", []))
        ),
    )
    _check(
        checks,
        "owner publishes no mutation, redrive, action, effect or Omnius route",
        [],
        [
            route
            for route in sp92["published_routes"]
            if route not in EXPECTED_OWNER_ROUTES
            or any(
                token in route
                for token in (
                    "redrive",
                    "pause",
                    "action",
                    "effect",
                    "omnius",
                    "scale",
                    "drain",
                )
            )
        ],
    )
    _check(
        checks,
        "portal declares every HA control capability forbidden",
        [],
        sorted(
            EXPECTED_FORBIDDEN_CAPABILITIES
            - set(profile.get("no_control", {}).get("forbidden_capabilities", []))
        ),
    )
    _check(
        checks,
        "portal HA package imports no broker/store/infrastructure client",
        [],
        scan["forbidden_imports"],
    )
    _check(
        checks,
        "the no-effect scan actually read files",
        True,
        scan["files_scanned"] > 0,
    )

    missing = [
        {
            "input": (
                "an independently controlled two-scope identity corpus with seeded PII and "
                "active content, exercised through every load and failure path"
            ),
            "why_no_substitute": (
                "a registry and source audit cannot show that no cross-scope disclosure, "
                "favorable fallback or hidden domain activation occurs under load, partition "
                "or recovery"
            ),
            "decision_required": (
                "a named non-production environment with tenant-provisioning and load authority"
            ),
        },
        {
            "input": (
                "live workload, DNS, route, secret-name, dependency, network, broker, store, "
                "log, trace, audit and UI inventories from that environment"
            ),
            "why_no_substitute": (
                "committed manifests declare intent; only a running environment can prove no "
                "unselected workload, domain, effect path or managed side effect exists"
            ),
            "decision_required": "read-only inventory access to the named environment",
        },
    ]
    result = _ac("AC-SP94-7", requirement, checks, missing, scope)
    result["no_effect_scan"] = scan
    return result


def run_environment_gated_ac(
    ac_id: str, gating: dict[str, Any], negative_control: dict[str, Any]
) -> dict[str, Any]:
    entry = gating.get("criteria", {}).get(ac_id, {})
    requirement = entry.get("requirement") or f"{ac_id} (requirement unavailable)"
    scope = (
        "Environment-gated. No buildable substitute exists: this criterion's ground truth is "
        "an observation of a running HA deployment under externally injected faults and load."
    )
    checks: list[dict[str, Any]] = []
    _check(
        checks,
        "environment-gating matrix is structurally valid",
        [],
        gating.get("issues", _members_failed(gating)),
    )
    _check(
        checks,
        "negative control holds (the local stack declares itself non-HA)",
        [],
        negative_control.get("issues", _members_failed(negative_control)),
    )
    _check(
        checks,
        f"{ac_id} declares its required inputs",
        True,
        bool(entry.get("required_inputs")),
    )
    _check(
        checks,
        f"{ac_id} declares its forbidden substitutes",
        True,
        bool(entry.get("forbidden_substitutes")),
    )

    axes = entry.get("disqualifying_local_axes", [])
    declared_ha = negative_control.get("owner_declared_topology", {}).get(
        "ha_qualified"
    )
    if axes:
        negative_control_note = (
            f"The only startable Barbarossa runtime here is "
            f"{negative_control.get('profile_id')!r}, whose own committed topology declares "
            f"ha_qualified={declared_ha!r} and lists {axes} among its not_qualified axes. It is "
            f"a NEGATIVE control for {ac_id}: proof that this environment cannot produce the "
            "ground truth, never evidence that it can."
        )
    else:
        negative_control_note = (
            f"The only startable Barbarossa runtime here is "
            f"{negative_control.get('profile_id')!r}, declared ha_qualified={declared_ha!r} with "
            f"activation_authority=none. It carries no alert-observer, signing or rollback "
            f"authority for {ac_id} either."
        )

    missing = [
        {
            "input": required_input,
            "why_no_substitute": AUTHORITY_BOUNDARY,
            "decision_required": (
                "a human must authorize and supply a named non-production HA environment "
                f"receipt at {environment_receipt_path().relative_to(ROOT)} with all of "
                f"{', '.join(REQUIRED_ENVIRONMENT_RECEIPT_FIELDS)}"
            ),
        }
        for required_input in entry.get("required_inputs", [])
    ] or [
        {
            "input": f"the environment-gating declaration for {ac_id}",
            "why_no_substitute": (
                "the gating fixture declares no required inputs for this criterion, so the "
                "criterion cannot be reported as gated on anything specific"
            ),
            "decision_required": f"repair {GATING_FIXTURE_RELPATH}",
        }
    ]

    result = _ac(ac_id, requirement, checks, missing, scope)
    result["forbidden_substitutes"] = entry.get("forbidden_substitutes", [])
    result["negative_control"] = negative_control_note
    receipt = find_environment_receipt()
    result["environment_receipt_present"] = receipt is not None
    if receipt is not None:
        result["status"] = "decision-required"
        result["environment_receipt"] = receipt
        result["note"] = (
            "A named non-production environment receipt was found, but this task's authority "
            "boundary forbids performing the fault-injection, load-generation and rollback "
            "observations this criterion requires on its own. A human-authorized, separately "
            "scoped qualification pass against that named environment is required."
        )
    else:
        result["missing_environment_receipt"] = (
            f"no receipt at {environment_receipt_path().relative_to(ROOT)} with all of "
            f"{', '.join(REQUIRED_ENVIRONMENT_RECEIPT_FIELDS)}"
        )
    return result


# ---------------------------------------------------------------------------
# Assembly and CLI.
# ---------------------------------------------------------------------------


def registry_profile() -> dict[str, Any] | None:
    try:
        registry = read_json(here(REGISTRY_RELPATH))
    except QualificationError:
        return None
    for profile in registry.get("runtime_profiles", []):
        if profile.get("id") == PROFILE_ID:
            return profile
    return None


def build_evidence_manifest(lock: dict[str, Any]) -> dict[str, Any]:
    """An unsigned manifest of what this run bound. AC-SP94-8 additionally
    requires a signature over it, which no authority here can produce."""
    return {
        "profile_lock_digest": lock.get("profile_lock_digest"),
        "genai_enablement_git_commit": lock.get("genai_enablement_git_commit"),
        "signature": None,
        "signature_absent_reason": (
            "no evidence-manifest signing authority exists for this task; an unsigned manifest "
            "is never presented as a signed attestation (AC-SP94-8)"
        ),
    }


def build_profile_lock() -> dict[str, Any]:
    """Assemble the qualification. Never raises: every failure -- including an
    unexpected one -- becomes a typed reason inside the returned object."""
    try:
        return _build_profile_lock()
    except Exception as exc:  # noqa: BLE001 -- the never-raise contract
        lock = {
            "schema": "barbarossa-ha-v1-integrated-profile-lock-v1",
            "profile_id": PROFILE_ID,
            "profile_revision": PROFILE_REVISION,
            "governing_adr": GOVERNING_ADR,
            "genai_enablement_git_commit": git_head(ROOT),
            "acceptance_criteria": {},
            "buildable_checks_result": "RED",
            "status": "RED",
            "activation_authority": "none",
            "reasons": [f"qualifier_internal_error:{type(exc).__name__}: {exc}"],
        }
        lock["profile_lock_digest"] = sha256_hex(canonical_json_bytes(lock))
        return lock


def _build_profile_lock() -> dict[str, Any]:
    sp89 = guarded("sp89_base_profile", build_sp89_member)
    sp90 = guarded("sp90_go_baseline", build_sp90_member)
    sp91 = guarded("sp91_distributed_work_substrate", build_sp91_member)
    sp92 = guarded("sp92_barbarossa_ha_release", build_sp92_member)
    sp93 = guarded("sp93_portal_ha_experience", build_sp93_member)
    negative_control = guarded("negative_control", build_negative_control)
    gating = guarded(
        "environment_gating_matrix", lambda: validate_gating_matrix(negative_control)
    )
    reg = registry_profile()

    acs = [
        run_ac1(sp89, sp90, sp91, sp92, sp93, reg),
        run_ac6(sp92, sp93),
        run_ac7(sp92, sp93, reg),
        *(
            run_environment_gated_ac(ac_id, gating, negative_control)
            for ac_id in ENVIRONMENT_GATED_ACS
        ),
    ]
    acceptance_criteria = {ac["id"]: ac for ac in acs}

    buildable_green = all(ac["buildable_result"] == "GREEN" for ac in acs)
    qualified = all(ac["status"] == "PASS" for ac in acs)
    reasons = [f"{ac['id']}: {ac['status']}" for ac in acs if ac["status"] != "PASS"]
    reasons.extend(
        _members_failed(sp89, sp90, sp91, sp92, sp93, negative_control, gating)
    )

    lock: dict[str, Any] = {
        "schema": "barbarossa-ha-v1-integrated-profile-lock-v1",
        "profile_id": PROFILE_ID,
        "profile_revision": PROFILE_REVISION,
        "governing_adr": GOVERNING_ADR,
        "base_profile_id": BASE_PROFILE_ID,
        "genai_enablement_git_commit": git_head(ROOT),
        "registry_selection": reg,
        "members": {
            "sp89_base_profile": sp89,
            "sp90_go_baseline_transitively_via_sp92": sp90,
            "sp91_distributed_work_transitively_via_sp92": sp91,
            "sp92_barbarossa_ha": sp92,
            "sp93_platform_portal_ha": sp93,
        },
        "negative_control": negative_control,
        "environment_gating": gating,
        "acceptance_criteria": acceptance_criteria,
        "buildable_acceptance_criteria": list(BUILDABLE_ACS),
        "environment_gated_acceptance_criteria": list(ENVIRONMENT_GATED_ACS),
        "buildable_checks_result": "GREEN" if buildable_green else "RED",
        "status": "GREEN" if qualified else "RED",
        "activation_authority": "none",
        "reasons": reasons,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "overall_note": (
            "status is RED and cannot be otherwise while no committed SP-92 owner receipt "
            "exists and no named non-production HA environment receipt exists. "
            "buildable_checks_result=GREEN means every check that CAN be performed from "
            "committed artifacts passed -- it is not HA qualification, profile activation or "
            "production readiness, and it grants no infrastructure-mutation authority."
        ),
    }
    lock["profile_lock_digest"] = sha256_hex(canonical_json_bytes(lock))
    return lock


def write_evidence(lock: dict[str, Any]) -> Path:
    directory = evidence_dir()
    directory.mkdir(parents=True, exist_ok=True)
    commit = lock.get("genai_enablement_git_commit") or "uncommitted"
    path = directory / f"profile-lock.{commit}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("profile_lock_digest") != lock.get("profile_lock_digest"):
            raise QualificationError(
                "refusing to overwrite existing immutable evidence file with different "
                f"content: {path}"
            )
        return path
    payload = dict(lock)
    payload["evidence_manifest"] = build_evidence_manifest(lock)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def print_report(lock: dict[str, Any]) -> None:
    print(json.dumps(lock, indent=2, sort_keys=True))
    print("\n--- per-AC summary ---", file=sys.stderr)
    for ac_id, ac in sorted(lock.get("acceptance_criteria", {}).items()):
        print(
            f"{ac_id}: status={ac['status']} buildable={ac['buildable_result']} "
            f"missing_ground_truth={len(ac['missing_ground_truth'])}",
            file=sys.stderr,
        )
    print(f"\nbuildable checks: {lock.get('buildable_checks_result')}", file=sys.stderr)
    print(f"overall qualification status: {lock.get('status')}", file=sys.stderr)
    print(f"activation authority: {lock.get('activation_authority')}", file=sys.stderr)


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

    lock = build_profile_lock()

    try:
        if args.write and not args.report:
            write_evidence(lock)
        elif args.report and not args.write:
            print_report(lock)
        else:
            path = write_evidence(lock)
            print_report(lock)
            print(f"\nevidence written to: {path.relative_to(ROOT)}", file=sys.stderr)
    except QualificationError as exc:
        print(f"EVIDENCE WRITE REFUSED: {exc}", file=sys.stderr)
        return 1

    return 0 if lock.get("buildable_checks_result") == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
