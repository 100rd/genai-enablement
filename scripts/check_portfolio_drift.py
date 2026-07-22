#!/usr/bin/env python3
"""Offline consistency checks for the project portfolio and cross-repo contract facts."""

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
REGISTRY_PATH = Path("portfolio/projects.json")
PORTFOLIO_INDEX_PATH = Path("docs/portfolio/README.md")
OMNISCIENCE_PAGE_PATH = Path("docs/portfolio/omniscience.md")
OMNIUS_PAGE_PATH = Path("docs/portfolio/omnius.md")
MCP_ADR_PATH = Path("docs/decisions/0017-omniscience-mcp-v1-contract-and-severance.md")
DECISIONS_DIR = Path("docs/decisions")
PROJECT_STATUS_PATH = Path("PROJECT_STATUS.md")
IMPLEMENTATION_ROADMAP_PATH = Path("docs/implementation-roadmap.md")
TRACK_B_SPEC_INDEX_PATH = Path("docs/specs/README.md")
TRACK_B_SPECS_DIR = Path("docs/specs")
TRACK_B_TRACEABILITY_DIR = Path("solutions/sre-harness/spec-traceability")
TRACK_B_TRACEABILITY_PATHS = {
    "SPEC-B0": TRACK_B_TRACEABILITY_DIR / "SPEC-B0.json",
    "SPEC-B1": TRACK_B_TRACEABILITY_DIR / "SPEC-B1.json",
    "SPEC-B2": TRACK_B_TRACEABILITY_DIR / "SPEC-B2.json",
    "SPEC-B3": TRACK_B_TRACEABILITY_DIR / "SPEC-B3.json",
    "SPEC-B4": TRACK_B_TRACEABILITY_DIR / "SPEC-B4.json",
    "SPEC-B5": TRACK_B_TRACEABILITY_DIR / "SPEC-B5.json",
    "SPEC-B6": TRACK_B_TRACEABILITY_DIR / "SPEC-B6.json",
    "SPEC-B7-CORE": TRACK_B_TRACEABILITY_DIR / "SPEC-B7-CORE.json",
    "SPEC-B7": TRACK_B_TRACEABILITY_DIR / "SPEC-B7.json",
    "SPEC-B7-NES": TRACK_B_TRACEABILITY_DIR / "SPEC-B7-NES.json",
    "SPEC-B7-CIR": TRACK_B_TRACEABILITY_DIR / "SPEC-B7-CIR.json",
    "SPEC-B7-DRIFT": TRACK_B_TRACEABILITY_DIR / "SPEC-B7-DRIFT.json",
    "SPEC-B7-SAT": TRACK_B_TRACEABILITY_DIR / "SPEC-B7-SAT.json",
}
SRE_HARNESS_README_PATH = Path("solutions/sre-harness/README.md")
README_PATH = Path("README.md")
MAX_COMPONENT_PROFILE_BYTES = 1_048_576
DECISION_GROUPS = {
    "registry-trust",
    "cross-factory-sdlc",
    "portal-experience",
    "ai-security",
    "delivery-evidence",
    "privacy-boundary",
    "reliability-plane",
    "continuous-management-plane",
}
DECISION_ITEM_KEYS = {
    "id",
    "path",
    "status",
    "review_group",
    "requires",
    "next_gate",
    "blocks",
}
TRACK_B_SPEC_IDS = (
    "SPEC-B0",
    "SPEC-B1",
    "SPEC-B2",
    "SPEC-B3",
    "SPEC-B4",
    "SPEC-B5",
    "SPEC-B6",
    "SPEC-B7-CORE",
    "SPEC-B7",
    "SPEC-B7-NES",
    "SPEC-B7-CIR",
    "SPEC-B7-DRIFT",
    "SPEC-B7-SAT",
)
TRACK_B_SPEC_ITEM_KEYS = {
    "id",
    "path",
    "stage",
    "source_status",
    "requirements",
    "probes",
    "requires",
    "portable_evidence",
    "operational_state",
    "next_gate",
    "authority",
    "portable_traceability_manifest",
}
TRACK_B_TRACEABILITY_KEYS = {
    "schemaVersion",
    "specId",
    "specPath",
    "specSha256",
    "evidenceScope",
    "operationalState",
    "authority",
    "implementationPaths",
    "probes",
}
TRACK_B_TRACEABILITY_PROBE_KEYS = {"id", "tests"}
TRACK_B_NEXT_GATES = {
    "human-corpus-and-regression-policy-publication",
    "approved-sources-analyzer-and-real-corpus",
    "approved-consumer-and-observed-advisory-run",
    "human-policy-and-live-canary-qualification",
    "human-allowlist-and-live-provider-drills",
    "human-authority-and-live-provider-drills",
    "human-policy-and-live-provider-drills",
    "human-policy-source-and-live-calibration",
    "human-runtime-source-and-operations-policy",
}
TRACK_B_SOURCE_STATUSES = {"draft-construction", "draft-portable-construction"}
REGISTRY_ROOT_KEYS = {
    "schema_version",
    "as_of",
    "authority",
    "decision_backlog",
    "track_b_spec_backlog",
    "projects",
}
REGISTRY_OBJECT_FIELDS = {
    "authority",
    "canonical_documents",
    "current_release",
    "local_verification",
    "mcp",
    "owners",
    "profile",
    "readiness",
    "roadmap",
    "token_profile",
}
REGISTRY_OBJECT_LIST_FIELDS = {
    "execution_evidence",
    "initiatives",
    "projects",
    "slices",
    "spec_index",
}
REGISTRY_STRING_LIST_FIELDS = {
    "blockers",
    "exact_scopes",
    "remaining",
    "target_tool_registry",
}
REGISTRY_INTEGER_FIELDS = {
    "acceptance_tests_passed",
    "completed_tasks",
    "current_runtime_tool_count",
    "environment_qualified_skips",
    "forbidden_actions",
    "human_waivers",
    "max_lifetime_days",
    "portable_probes_passed",
    "readiness_blockers",
    "rotation_overlap_hours",
    "schema_version",
    "selected_capabilities",
    "selected_probes",
    "selected_requirements",
    "target_profile_failures",
    "target_tool_count",
    "total_tasks",
}
REGISTRY_NULLABLE_STRING_FIELDS = {"evidence", "version"}


def _validate_registry_shape(registry: dict[str, Any], errors: list[str]) -> None:
    def reject(path: str, expected: str) -> None:
        errors.append(
            "portfolio/projects.json: malformed registry shape at "
            f"{path}; expected {expected}"
        )

    def visit_object(value: dict[str, Any], path: str) -> None:
        for key, item in value.items():
            field_path = f"{path}.{key}" if path else key
            if not path and key in {"decision_backlog", "track_b_spec_backlog"}:
                continue
            if key in REGISTRY_OBJECT_FIELDS:
                if not isinstance(item, dict) or not item:
                    reject(field_path, "a non-empty object")
                else:
                    visit_object(item, field_path)
            elif key in REGISTRY_OBJECT_LIST_FIELDS:
                if not isinstance(item, list) or not item:
                    reject(field_path, "a non-empty object list")
                    continue
                if any(not isinstance(entry, dict) for entry in item):
                    reject(field_path, "objects only")
                    continue
                for index, entry in enumerate(item):
                    visit_object(entry, f"{field_path}.{index}")
            elif key in REGISTRY_STRING_LIST_FIELDS:
                if (
                    not isinstance(item, list)
                    or not item
                    or any(not isinstance(entry, str) or not entry for entry in item)
                ):
                    reject(field_path, "a non-empty string list")
            elif key in REGISTRY_INTEGER_FIELDS:
                if isinstance(item, bool) or not isinstance(item, int):
                    reject(field_path, "an integer")
            elif key in REGISTRY_NULLABLE_STRING_FIELDS:
                if item is not None and (not isinstance(item, str) or not item):
                    reject(field_path, "a non-empty string or null")
            elif not isinstance(item, str) or not item:
                reject(field_path, "a non-empty string")

    if set(registry) != REGISTRY_ROOT_KEYS:
        errors.append(
            "portfolio/projects.json: registry root must be a closed object with "
            f"exactly these keys: {sorted(REGISTRY_ROOT_KEYS)}"
        )

    visit_object(registry, "")


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"{path}: registry is not UTF-8: {exc}")
        return {}
    except OSError as exc:
        errors.append(f"{path}: cannot read: {exc}")
        return {}

    try:
        data = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_non_finite,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return {}

    if not isinstance(data, dict):
        errors.append(f"{path}: JSON root must be an object")
        return {}

    if (
        not raw.endswith("\n")
        or "\t" in raw
        or any(line.endswith((" ", "\t")) for line in raw.splitlines())
    ):
        errors.append(
            f"{path}: JSON must have no tabs/trailing whitespace and must end with a newline"
        )
    return data


def _read_text(root: Path, relative_path: Path, errors: list[str]) -> str:
    path = root / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{relative_path}: cannot read: {exc}")
        return ""


def _require(text: str, expected: str, path: Path, errors: list[str]) -> None:
    if expected not in text:
        errors.append(f"{path}: missing registry fact {expected!r}")


def _adr_status(text: str) -> str | None:
    patterns = (
        r"^\s*-\s+\*\*Status:\*\*\s*([A-Za-z]+)",
        r"^\s*\*\*Status\*\*:\s*([A-Za-z]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return match.group(1).casefold()
    return None


def _adr_build_dependencies(text: str, proposed_ids: set[str]) -> list[str]:
    match = re.search(
        r"^-\s+\*\*Builds on:\*\*(.*?)(?=^-\s+\*\*|^\s*$)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        return []
    referenced = {
        f"ADR-{number}" for number in re.findall(r"\[ADR-(\d{4})\]\(", match.group(1))
    }
    return sorted(referenced & proposed_ids)


def _spec_id(text: str) -> str | None:
    match = re.search(r"^#\s+(SPEC-B\d+(?:-[A-Z]+)?)\s+—", text, re.MULTILINE)
    return match.group(1) if match else None


def _spec_status(text: str) -> str | None:
    match = re.search(r"^\*\*Status:\*\*\s*(.*?)\s*$", text, re.MULTILINE)
    if match is None:
        return None
    return re.sub(r"[^a-z0-9]+", "-", match.group(1).casefold()).strip("-")


def _spec_roadmap_gate(text: str) -> str | None:
    match = re.search(r"^\*\*Roadmap gate:\*\*\s*`(B[0-7])`", text, re.MULTILINE)
    return match.group(1) if match else None


def _spec_code_field(text: str, field: str) -> str | None:
    match = re.search(
        rf"^\*\*{re.escape(field)}:\*\*\s*`([^`]+)`\s*(?:;.*)?$",
        text,
        re.MULTILINE,
    )
    return match.group(1) if match else None


def _spec_dependencies(text: str) -> list[str]:
    match = re.search(
        r"^\*\*Depends on:\*\*(.*?)(?=^\*\*[^\n]+:\*\*|^\s*$)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        return []
    dependencies = set(
        re.findall(r"\b(?:ADR-\d{4}|SPEC-B\d+(?:-[A-Z]+)?)\b", match.group(1))
    )
    return sorted(dependencies)


def _spec_contract_count(text: str, kind: str) -> tuple[str | None, int | None]:
    if kind == "requirement":
        matches = re.findall(r"^\[REQ-([A-Z0-9]+)-(\d+)\]", text, re.MULTILINE)
    else:
        matches = re.findall(r"^\s*-\s+\*\*P-([A-Z0-9]+)-(\d+)\b", text, re.MULTILINE)
    prefixes = {prefix for prefix, _number in matches}
    numbers = {int(number) for _prefix, number in matches}
    if (
        len(matches) != len(set(matches))
        or len(prefixes) != 1
        or numbers != set(range(1, len(numbers) + 1))
    ):
        return None, None
    return prefixes.pop(), len(numbers)


def _spec_probe_ids(text: str) -> tuple[str, ...]:
    matches = re.findall(r"^\s*-\s+\*\*(P-([A-Z0-9]+)-(\d+))\b", text, re.MULTILINE)
    if not matches:
        return ()
    ids = tuple(probe_id for probe_id, _prefix, _number in matches)
    prefixes = {prefix for _probe_id, prefix, _number in matches}
    numbers = tuple(int(number) for _probe_id, _prefix, number in matches)
    if (
        len(ids) != len(set(ids))
        or len(prefixes) != 1
        or numbers != tuple(range(1, len(numbers) + 1))
    ):
        return ()
    return ids


def _python_test_nodes(path: Path, relative: str, errors: list[str]) -> set[str]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        errors.append(f"{relative}: cannot inspect pytest nodes: {exc}")
        return set()

    nodes: set[str] = set()
    for item in tree.body:
        if isinstance(
            item, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and item.name.startswith("test_"):
            nodes.add(f"{relative}::{item.name}")
        elif isinstance(item, ast.ClassDef):
            for child in item.body:
                if isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and child.name.startswith("test_"):
                    nodes.add(f"{relative}::{item.name}::{child.name}")
    return nodes


def _validate_track_b_traceability_value(
    root: Path,
    source_path: Path,
    source_text: str,
    manifest: dict[str, Any],
    errors: list[str],
) -> None:
    spec_id = _spec_id(source_text)
    traceability_path = TRACK_B_TRACEABILITY_PATHS.get(
        spec_id or "", TRACK_B_TRACEABILITY_DIR / "UNKNOWN.json"
    )
    label = f"{spec_id or 'Track-B SPEC'} portable traceability"
    if set(manifest) != TRACK_B_TRACEABILITY_KEYS:
        errors.append(f"{traceability_path}: manifest must be a closed object")
        return

    if manifest.get("schemaVersion") != "sre-harness.spec-portable-traceability/v1":
        errors.append(f"{traceability_path}: traceability schema is invalid")
    if spec_id not in TRACK_B_TRACEABILITY_PATHS or manifest.get("specId") != spec_id:
        errors.append(f"{traceability_path}: SPEC id drift")
    if manifest.get("specPath") != source_path.as_posix():
        errors.append(f"{traceability_path}: SPEC path drift")
    expected_digest = (
        f"sha256:{hashlib.sha256(source_text.encode('utf-8')).hexdigest()}"
    )
    if manifest.get("specSha256") != expected_digest:
        errors.append(f"{traceability_path}: SPEC source digest drift")
    if manifest.get("evidenceScope") != "local-portable-only":
        errors.append(
            f"{traceability_path}: evidence scope must remain local-portable-only"
        )
    if manifest.get("operationalState") != "incomplete":
        errors.append(f"{traceability_path}: operational state must remain incomplete")
    if manifest.get("authority") != "non-authorizing":
        errors.append(f"{traceability_path}: {label} must remain non-authorizing")

    implementation_paths = manifest.get("implementationPaths")
    implementation_root = root / "solutions/sre-harness/src/sre_harness"
    try:
        resolved_implementation_root = implementation_root.resolve(strict=True)
    except OSError:
        errors.append(f"{traceability_path}: implementation root is missing")
        resolved_implementation_root = implementation_root
    if (
        not isinstance(implementation_paths, list)
        or not implementation_paths
        or any(not isinstance(value, str) for value in implementation_paths)
        or implementation_paths != sorted(set(implementation_paths))
    ):
        errors.append(
            f"{traceability_path}: implementation paths must be a non-empty sorted string list"
        )
    else:
        for value in implementation_paths:
            relative_path = Path(value)
            full_path = root / relative_path
            try:
                full_path.resolve(strict=True).relative_to(resolved_implementation_root)
                inside_root = True
            except (OSError, ValueError):
                inside_root = False
            if (
                relative_path.is_absolute()
                or ".." in relative_path.parts
                or relative_path.as_posix() != value
                or relative_path.suffix != ".py"
                or full_path.is_symlink()
                or not full_path.is_file()
                or not inside_root
            ):
                errors.append(
                    f"{traceability_path}: implementation path is invalid: {value!r}"
                )

    probes = manifest.get("probes")
    expected_probe_ids = _spec_probe_ids(source_text)
    if not isinstance(probes, list):
        errors.append(f"{traceability_path}: probes must be a list")
        return

    observed_probe_ids: list[str] = []
    test_node_cache: dict[str, set[str]] = {}
    tests_root = root / "solutions/sre-harness/tests"
    try:
        resolved_tests_root = tests_root.resolve(strict=True)
    except OSError:
        errors.append(f"{traceability_path}: pytest root is missing")
        resolved_tests_root = tests_root
    for index, probe in enumerate(probes):
        if not isinstance(probe, dict) or set(probe) != TRACK_B_TRACEABILITY_PROBE_KEYS:
            errors.append(
                f"{traceability_path}: probe {index} has an invalid closed shape"
            )
            continue
        probe_id = probe.get("id")
        tests = probe.get("tests")
        if not isinstance(probe_id, str):
            errors.append(f"{traceability_path}: probe {index} id is invalid")
            continue
        observed_probe_ids.append(probe_id)
        if (
            not isinstance(tests, list)
            or not tests
            or any(not isinstance(value, str) or not value for value in tests)
            or tests != sorted(set(tests))
        ):
            errors.append(
                f"{traceability_path}: {probe_id} tests must be a non-empty sorted string list"
            )
            continue
        for node_id in tests:
            parts = node_id.split("::")
            relative_value = parts[0]
            relative_path = Path(relative_value)
            full_path = root / relative_path
            try:
                full_path.resolve(strict=True).relative_to(resolved_tests_root)
                inside_root = True
            except (OSError, ValueError):
                inside_root = False
            if (
                len(parts) not in {2, 3}
                or relative_path.is_absolute()
                or ".." in relative_path.parts
                or relative_path.as_posix() != relative_value
                or relative_path.suffix != ".py"
                or full_path.is_symlink()
                or not full_path.is_file()
                or not inside_root
            ):
                errors.append(
                    f"{traceability_path}: pytest node path is invalid: {node_id!r}"
                )
                continue
            if relative_value not in test_node_cache:
                test_node_cache[relative_value] = _python_test_nodes(
                    full_path, relative_value, errors
                )
            if node_id not in test_node_cache[relative_value]:
                errors.append(
                    f"{traceability_path}: pytest node does not exist: {node_id!r}"
                )

    if tuple(observed_probe_ids) != expected_probe_ids:
        errors.append(f"{traceability_path}: probe coverage drift against {spec_id}")


def _validate_decision_backlog(
    root: Path, registry: dict[str, Any], errors: list[str]
) -> None:
    backlog = registry.get("decision_backlog")
    if not isinstance(backlog, dict) or set(backlog) != {"owner", "status", "items"}:
        errors.append(
            "portfolio/projects.json: decision_backlog must be a closed owner/status/items object"
        )
        return
    if backlog.get("owner") != "@100rd":
        errors.append(
            "portfolio/projects.json: decision backlog needs the human owner @100rd"
        )
    if backlog.get("status") != "human-disposition-required":
        errors.append(
            "portfolio/projects.json: decision backlog must remain human-disposition-required"
        )

    items = backlog.get("items")
    if not isinstance(items, list):
        errors.append("portfolio/projects.json: decision backlog items must be a list")
        return

    observed: dict[str, str] = {}
    source_texts: dict[str, str] = {}
    decisions_root = root / DECISIONS_DIR
    try:
        resolved_root = root.resolve(strict=True)
        resolved_decisions = decisions_root.resolve(strict=True)
        resolved_decisions.relative_to(resolved_root)
    except (OSError, ValueError):
        errors.append(
            f"{DECISIONS_DIR}: decisions directory is missing or outside the repository"
        )
        return
    try:
        decision_paths = sorted(decisions_root.glob("[0-9][0-9][0-9][0-9]-*.md"))
    except OSError as exc:
        errors.append(f"{DECISIONS_DIR}: cannot enumerate ADRs: {exc}")
        return
    for source_path in decision_paths:
        relative = source_path.relative_to(root).as_posix()
        if source_path.is_symlink() or not source_path.is_file():
            errors.append(f"{relative}: ADR source must be a regular non-symlink file")
            continue
        try:
            text = source_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{relative}: cannot read ADR status: {exc}")
            continue
        status = _adr_status(text)
        if status is None:
            errors.append(f"{relative}: ADR status is missing or malformed")
            continue
        if status == "proposed":
            decision_id = f"ADR-{source_path.name[:4]}"
            if decision_id in observed:
                errors.append(f"{DECISIONS_DIR}: duplicate proposed id {decision_id}")
            observed[decision_id] = relative
            source_texts[decision_id] = text

    ids: list[str] = []
    registry_paths: dict[str, str] = {}
    for index, item in enumerate(items):
        label = f"decision backlog item {index}"
        if not isinstance(item, dict) or set(item) != DECISION_ITEM_KEYS:
            errors.append(
                f"portfolio/projects.json: {label} has an invalid closed shape"
            )
            continue
        decision_id = item.get("id")
        path_value = item.get("path")
        if not isinstance(decision_id, str) or not re.fullmatch(
            r"ADR-\d{4}", decision_id
        ):
            errors.append(f"portfolio/projects.json: {label} needs a canonical ADR id")
            continue
        ids.append(decision_id)
        if decision_id in registry_paths:
            errors.append(
                f"portfolio/projects.json: duplicate decision backlog id {decision_id}"
            )
        if not isinstance(path_value, str):
            errors.append(
                f"portfolio/projects.json: {decision_id} needs a canonical source path"
            )
            continue
        source_path = Path(path_value)
        if (
            source_path.is_absolute()
            or ".." in source_path.parts
            or source_path.parent != DECISIONS_DIR
            or source_path.as_posix() != path_value
            or not source_path.name.startswith(decision_id.removeprefix("ADR-") + "-")
        ):
            errors.append(
                f"portfolio/projects.json: {decision_id} source path is invalid"
            )
        registry_paths[decision_id] = path_value

        full_source = root / source_path
        if full_source.is_symlink() or not full_source.is_file():
            errors.append(
                f"{path_value}: backlog ADR must be a regular non-symlink file"
            )
            continue
        try:
            full_source.resolve(strict=True).relative_to(resolved_decisions)
        except (OSError, ValueError):
            errors.append(
                f"{path_value}: backlog ADR resolves outside the decisions directory"
            )
            continue
        try:
            source_text = full_source.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{path_value}: cannot read backlog ADR: {exc}")
        else:
            source_status = _adr_status(source_text)
            if item.get("status") != source_status:
                errors.append(
                    f"portfolio/projects.json: {decision_id} source status drift"
                )
        if item.get("status") != "proposed":
            errors.append(
                f"portfolio/projects.json: {decision_id} source status drift; "
                "backlog may contain only Proposed ADRs"
            )
        review_group = item.get("review_group")
        if not isinstance(review_group, str) or review_group not in DECISION_GROUPS:
            errors.append(
                f"portfolio/projects.json: {decision_id} review group is invalid"
            )
        if item.get("next_gate") != "human-disposition":
            errors.append(
                f"portfolio/projects.json: {decision_id} next gate must be human-disposition"
            )
        requires = item.get("requires")
        if (
            not isinstance(requires, list)
            or any(not isinstance(value, str) for value in requires)
            or requires != sorted(set(requires))
        ):
            errors.append(
                f"portfolio/projects.json: {decision_id} dependencies must be unique sorted ADR ids"
            )
        elif requires != _adr_build_dependencies(
            source_texts.get(decision_id, ""), set(observed)
        ):
            errors.append(
                f"portfolio/projects.json: {decision_id} source dependency drift"
            )
        blocks = item.get("blocks")
        if (
            not isinstance(blocks, list)
            or not blocks
            or any(not isinstance(value, str) or not value for value in blocks)
            or len(blocks) != len(set(blocks))
        ):
            errors.append(
                f"portfolio/projects.json: {decision_id} must name unique blocked adoption surfaces"
            )

    expected_ids = sorted(observed)
    if ids != expected_ids or registry_paths != observed:
        errors.append(
            "portfolio/projects.json: decision backlog coverage drift against Proposed ADR sources"
        )

    positions = {decision_id: index for index, decision_id in enumerate(ids)}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        decision_id = item["id"]
        requires = item.get("requires")
        if not isinstance(requires, list):
            continue
        for dependency in requires:
            if not isinstance(dependency, str):
                continue
            if dependency not in positions or positions[dependency] >= positions.get(
                decision_id, -1
            ):
                errors.append(
                    f"portfolio/projects.json: {decision_id} dependency "
                    f"{dependency!r} is missing or unordered"
                )


def _validate_track_b_spec_backlog(
    root: Path, registry: dict[str, Any], errors: list[str]
) -> None:
    backlog = registry.get("track_b_spec_backlog")
    if not isinstance(backlog, dict) or set(backlog) != {"owner", "status", "items"}:
        errors.append(
            "portfolio/projects.json: track_b_spec_backlog must be a closed "
            "owner/status/items object"
        )
        return
    if backlog.get("owner") != "genai-enablement":
        errors.append(
            "portfolio/projects.json: Track-B SPEC backlog owner must be genai-enablement"
        )
    if backlog.get("status") != "external-evidence-required":
        errors.append(
            "portfolio/projects.json: Track-B SPEC backlog must remain "
            "external-evidence-required"
        )

    items = backlog.get("items")
    if not isinstance(items, list):
        errors.append(
            "portfolio/projects.json: Track-B SPEC backlog items must be a list"
        )
        return

    specs_root = root / TRACK_B_SPECS_DIR
    try:
        resolved_root = root.resolve(strict=True)
        resolved_specs = specs_root.resolve(strict=True)
        resolved_specs.relative_to(resolved_root)
    except (OSError, ValueError):
        errors.append(
            f"{TRACK_B_SPECS_DIR}: SPEC directory is missing or outside the repository"
        )
        return

    observed: dict[str, dict[str, Any]] = {}
    try:
        spec_paths = sorted(specs_root.glob("SPEC-B*.md"))
    except OSError as exc:
        errors.append(f"{TRACK_B_SPECS_DIR}: cannot enumerate Track-B SPECs: {exc}")
        return
    for source_path in spec_paths:
        relative = source_path.relative_to(root).as_posix()
        if source_path.is_symlink() or not source_path.is_file():
            errors.append(
                f"{relative}: Track-B SPEC must be a regular non-symlink file"
            )
            continue
        try:
            source_path.resolve(strict=True).relative_to(resolved_specs)
            text = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            errors.append(f"{relative}: cannot read Track-B SPEC: {exc}")
            continue
        source_id = _spec_id(text)
        if source_id is None:
            errors.append(f"{relative}: Track-B SPEC id is missing or malformed")
            continue
        if source_id in observed:
            errors.append(f"{TRACK_B_SPECS_DIR}: duplicate Track-B SPEC id {source_id}")
            continue
        requirement_prefix, requirement_count = _spec_contract_count(
            text, "requirement"
        )
        probe_prefix, probe_count = _spec_contract_count(text, "probe")
        if requirement_prefix is None or requirement_count is None:
            errors.append(f"{relative}: requirement ids must be one contiguous family")
        if probe_prefix is None or probe_count is None:
            errors.append(f"{relative}: probe ids must be one contiguous family")
        if requirement_prefix != probe_prefix:
            errors.append(f"{relative}: requirement and probe id families must match")
        source_status = _spec_status(text)
        if source_status not in TRACK_B_SOURCE_STATUSES:
            errors.append(
                f"{relative}: Track-B SPEC must remain a Draft construction artifact"
            )
        if "**Specification type:** Capability SPEC" not in text:
            errors.append(f"{relative}: Track-B SPEC type metadata is missing")
        if re.search(
            r"^\*\*Owner:\*\*\s*`genai-enablement` Autonomous SRE harness\s*$",
            text,
            re.MULTILINE,
        ) is None:
            errors.append(f"{relative}: Track-B SPEC owner metadata is missing")
        if (
            "**Governing decisions:**" not in text
            or "ADR-0009" not in text.split("##", 1)[0]
        ):
            errors.append(f"{relative}: Track-B governing decisions are incomplete")
        if _spec_code_field(text, "Evidence scope") != "local-portable-only":
            errors.append(f"{relative}: Track-B evidence-scope metadata drift")
        if _spec_code_field(text, "Operational state") != "incomplete":
            errors.append(f"{relative}: Track-B operational-state metadata drift")
        if _spec_code_field(text, "Authority") != "non-authorizing":
            errors.append(f"{relative}: Track-B authority metadata drift")
        source_next_gate = _spec_code_field(text, "Next gate")
        if source_next_gate not in TRACK_B_NEXT_GATES:
            errors.append(f"{relative}: Track-B next-gate metadata is invalid")
        observed[source_id] = {
            "path": relative,
            "text": text,
            "stage": _spec_roadmap_gate(text),
            "source_status": source_status,
            "requirements": requirement_count,
            "probes": probe_count,
            "requires": _spec_dependencies(text),
            "next_gate": source_next_gate,
        }

    if set(observed) != set(TRACK_B_SPEC_IDS):
        errors.append(
            "portfolio/projects.json: Track-B SPEC source set drift against the planned catalog"
        )

    ids: list[str] = []
    registry_paths: dict[str, str] = {}
    decision_backlog = registry.get("decision_backlog")
    decision_items = (
        decision_backlog.get("items", []) if isinstance(decision_backlog, dict) else []
    )
    decision_ids = {
        item.get("id")
        for item in decision_items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for index, item in enumerate(items):
        label = f"Track-B SPEC backlog item {index}"
        if not isinstance(item, dict) or set(item) != TRACK_B_SPEC_ITEM_KEYS:
            errors.append(
                f"portfolio/projects.json: {label} has an invalid closed shape"
            )
            continue
        spec_id = item.get("id")
        path_value = item.get("path")
        if not isinstance(spec_id, str) or spec_id not in TRACK_B_SPEC_IDS:
            errors.append(f"portfolio/projects.json: {label} needs a planned SPEC id")
            continue
        ids.append(spec_id)
        if spec_id in registry_paths:
            errors.append(
                f"portfolio/projects.json: duplicate Track-B SPEC id {spec_id}"
            )
        if not isinstance(path_value, str):
            errors.append(
                f"portfolio/projects.json: {spec_id} needs a canonical source path"
            )
            continue
        source_path = Path(path_value)
        source_fact = observed.get(spec_id, {})
        if (
            source_path.is_absolute()
            or ".." in source_path.parts
            or source_path.parent != TRACK_B_SPECS_DIR
            or source_path.as_posix() != path_value
            or source_fact.get("path") != path_value
        ):
            errors.append(f"portfolio/projects.json: {spec_id} source path is invalid")
        registry_paths[spec_id] = path_value

        if item.get("source_status") != source_fact.get("source_status"):
            errors.append(f"portfolio/projects.json: {spec_id} source status drift")
        if item.get("source_status") not in TRACK_B_SOURCE_STATUSES:
            errors.append(
                f"portfolio/projects.json: {spec_id} must remain a Draft construction artifact"
            )
        if item.get("stage") != source_fact.get("stage"):
            errors.append(
                f"portfolio/projects.json: {spec_id} source roadmap gate drift"
            )
        requirements = item.get("requirements")
        if (
            isinstance(requirements, bool)
            or not isinstance(requirements, int)
            or requirements < 1
        ):
            errors.append(
                f"portfolio/projects.json: {spec_id} requirement count must be a positive integer"
            )
        elif requirements != source_fact.get("requirements"):
            errors.append(f"portfolio/projects.json: {spec_id} requirement count drift")
        probes = item.get("probes")
        if isinstance(probes, bool) or not isinstance(probes, int) or probes < 1:
            errors.append(
                f"portfolio/projects.json: {spec_id} probe count must be a positive integer"
            )
        elif probes != source_fact.get("probes"):
            errors.append(f"portfolio/projects.json: {spec_id} probe count drift")

        requires = item.get("requires")
        if (
            not isinstance(requires, list)
            or any(not isinstance(value, str) for value in requires)
            or requires != sorted(set(requires))
        ):
            errors.append(
                f"portfolio/projects.json: {spec_id} dependencies must be unique sorted ids"
            )
        elif requires != source_fact.get("requires"):
            errors.append(f"portfolio/projects.json: {spec_id} source dependency drift")

        next_gate = item.get("next_gate")
        if not isinstance(next_gate, str) or next_gate not in TRACK_B_NEXT_GATES:
            errors.append(f"portfolio/projects.json: {spec_id} next gate is invalid")
        elif next_gate != source_fact.get("next_gate"):
            errors.append(f"portfolio/projects.json: {spec_id} source next-gate drift")
        if item.get("portable_evidence") != "local-construction-only":
            errors.append(
                f"portfolio/projects.json: {spec_id} portable evidence must remain local-only"
            )
        if item.get("operational_state") != "incomplete":
            errors.append(
                f"portfolio/projects.json: {spec_id} operational state must remain incomplete"
            )
        if item.get("authority") != "non-authorizing":
            errors.append(
                f"portfolio/projects.json: {spec_id} must remain non-authorizing"
            )

        traceability_path = item.get("portable_traceability_manifest")
        expected_traceability_path = TRACK_B_TRACEABILITY_PATHS.get(spec_id)
        if expected_traceability_path is not None:
            expected_traceability_value = expected_traceability_path.as_posix()
            if traceability_path != expected_traceability_value:
                errors.append(
                    f"portfolio/projects.json: {spec_id} portable traceability path drift"
                )
            else:
                assert isinstance(traceability_path, str)
                relative_traceability_path = Path(traceability_path)
                full_traceability_path = root / relative_traceability_path
                try:
                    resolved_traceability_root = (
                        root / TRACK_B_TRACEABILITY_DIR
                    ).resolve(strict=True)
                    full_traceability_path.resolve(strict=True).relative_to(
                        resolved_traceability_root
                    )
                    inside_traceability_root = True
                except (OSError, ValueError):
                    inside_traceability_root = False
                if (
                    relative_traceability_path.is_absolute()
                    or ".." in relative_traceability_path.parts
                    or relative_traceability_path.as_posix() != traceability_path
                    or full_traceability_path.is_symlink()
                    or not full_traceability_path.is_file()
                    or not inside_traceability_root
                ):
                    errors.append(
                        f"portfolio/projects.json: {spec_id} portable traceability file is invalid"
                    )
                else:
                    manifest_error_count = len(errors)
                    manifest = _load_json(full_traceability_path, errors)
                    if len(errors) == manifest_error_count:
                        _validate_track_b_traceability_value(
                            root,
                            Path(path_value),
                            str(source_fact.get("text", "")),
                            manifest,
                            errors,
                        )
        elif traceability_path is not None:
            errors.append(
                f"portfolio/projects.json: {spec_id} has an unreviewed portable traceability claim"
            )

    expected_paths = {
        spec_id: observed.get(spec_id, {}).get("path") for spec_id in TRACK_B_SPEC_IDS
    }
    if ids != list(TRACK_B_SPEC_IDS) or registry_paths != expected_paths:
        errors.append(
            "portfolio/projects.json: Track-B SPEC backlog coverage drift against source SPECs"
        )

    positions = {spec_id: index for index, spec_id in enumerate(ids)}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        spec_id = item["id"]
        requires = item.get("requires")
        if not isinstance(requires, list):
            continue
        for dependency in requires:
            if not isinstance(dependency, str):
                continue
            if dependency.startswith("ADR-"):
                if dependency not in decision_ids:
                    errors.append(
                        f"portfolio/projects.json: {spec_id} dependency {dependency!r} "
                        "is absent from the decision backlog"
                    )
            elif dependency not in positions or positions[dependency] >= positions.get(
                spec_id, -1
            ):
                errors.append(
                    f"portfolio/projects.json: {spec_id} dependency "
                    f"{dependency!r} is missing or unordered"
                )


def _project_by_id(registry: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    for project in registry.get("projects", []):
        if isinstance(project, dict) and project.get("id") == project_id:
            return project
    return None


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _load_component_profile(
    path: Path, errors: list[str]
) -> tuple[dict[str, Any], str] | None:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        errors.append(f"Omnius component profile cannot be read: {exc}")
        return None
    if not raw or len(raw) > MAX_COMPONENT_PROFILE_BYTES:
        errors.append("Omnius component profile is empty or exceeds the one-MiB bound")
        return None
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_non_finite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"Omnius component profile is not strict JSON: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append("Omnius component profile root must be an object")
        return None
    return value, hashlib.sha256(raw).hexdigest()


def _git_output(root: Path, args: list[str], errors: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        errors.append(f"Omnius component Git observation failed for {' '.join(args)}")
        return None
    if result.returncode != 0 or len(result.stdout) > MAX_COMPONENT_PROFILE_BYTES:
        errors.append(f"Omnius component Git observation failed for {' '.join(args)}")
        return None
    return result.stdout.strip()


def _validate_omnius_component(
    component_root: Path, registry: dict[str, Any], errors: list[str]
) -> None:
    omnius = _project_by_id(registry, "omnius")
    if omnius is None:
        errors.append("Omnius component observation requires the portfolio project")
        return

    try:
        root = component_root.resolve(strict=True)
    except OSError:
        errors.append("Omnius component root does not exist")
        return
    if not root.is_dir():
        errors.append("Omnius component root must be a directory")
        return

    readiness = omnius.get("readiness", {})
    profile_binding = readiness.get("profile", {})
    source_path_value = profile_binding.get("source_path")
    if not isinstance(source_path_value, str):
        errors.append("Omnius component source_path must be a relative path")
        return
    source_path = Path(source_path_value)
    if (
        source_path.is_absolute()
        or not source_path.parts
        or ".." in source_path.parts
        or source_path.as_posix() != source_path_value
    ):
        errors.append("Omnius component source_path must be a canonical relative path")
        return

    candidate = root / source_path
    cursor = root
    for part in source_path.parts:
        cursor /= part
        if cursor.is_symlink():
            errors.append("Omnius component source profile must not traverse a symlink")
            return
    try:
        candidate.resolve(strict=True).relative_to(root)
    except (OSError, ValueError):
        errors.append(
            "Omnius component source profile is missing or outside the repository"
        )
        return
    if not candidate.is_file():
        errors.append("Omnius component source profile must be a regular file")
        return

    loaded = _load_component_profile(candidate, errors)
    if loaded is None:
        return
    component_profile, digest = loaded
    if profile_binding.get("source_sha256") != f"sha256:{digest}":
        errors.append("Omnius component source_sha256 drift")

    metadata = component_profile.get("metadata")
    spec = component_profile.get("spec")
    if not isinstance(metadata, dict) or not isinstance(spec, dict):
        errors.append("Omnius component profile metadata/spec must be objects")
        return
    scope = spec.get("scope")
    capabilities = spec.get("capabilities")
    blockers = spec.get("readinessBlockers")
    forbidden = spec.get("forbiddenActions")
    if (
        not isinstance(scope, dict)
        or not isinstance(capabilities, list)
        or not isinstance(blockers, list)
        or not isinstance(forbidden, list)
        or any(
            not isinstance(capability, dict)
            or not isinstance(capability.get("requirements"), list)
            or not isinstance(capability.get("probes"), list)
            for capability in capabilities
        )
    ):
        errors.append("Omnius component profile has an invalid closed readiness shape")
        return

    observed = {
        "id": metadata.get("name"),
        "status": metadata.get("status"),
        "assurance_profile": spec.get("assuranceProfile"),
        "platform_path": scope.get("platformPath"),
        "selected_capabilities": len(capabilities),
        "selected_requirements": sum(
            len(item["requirements"]) for item in capabilities
        ),
        "selected_probes": sum(len(item["probes"]) for item in capabilities),
        "readiness_blockers": len(blockers),
        "forbidden_actions": len(forbidden),
    }
    for field, value in observed.items():
        if profile_binding.get(field) != value:
            errors.append(f"Omnius component profile {field} drift")

    top_level = _git_output(root, ["rev-parse", "--show-toplevel"], errors)
    if top_level is None:
        return
    try:
        if Path(top_level).resolve(strict=True) != root:
            errors.append("Omnius component root is not the observed Git toplevel")
            return
    except OSError:
        errors.append("Omnius component Git toplevel cannot be resolved")
        return

    head = _git_output(root, ["rev-parse", "HEAD"], errors)
    status = _git_output(
        root, ["status", "--porcelain=v1", "--untracked-files=normal"], errors
    )
    if head is None or status is None:
        return
    verification = readiness.get("local_verification", {})
    if verification.get("inspected_head") != head:
        errors.append("Omnius component inspected_head drift")
    observed_publication = "dirty-unpublished" if status else "clean-immutable"
    if verification.get("worktree_publication_status") != observed_publication:
        errors.append("Omnius component worktree publication status drift")
    observed_scope = "dirty-worktree-local" if status else "immutable-component"
    if verification.get("evidence_scope") != observed_scope:
        errors.append("Omnius component evidence scope drift")


def _validate_omnius(registry: dict[str, Any], errors: list[str]) -> None:
    omnius = _project_by_id(registry, "omnius")
    if omnius is None:
        errors.append("portfolio/projects.json: omnius project is required")
        return

    roadmap = omnius.get("roadmap", {})
    if omnius.get("portfolio_status") != roadmap.get("status"):
        errors.append(
            "portfolio/projects.json: Omnius portfolio and roadmap statuses differ"
        )
    if roadmap.get("page") != str(OMNIUS_PAGE_PATH):
        errors.append(
            "portfolio/projects.json: Omnius roadmap must name its portfolio page"
        )

    documents = omnius.get("canonical_documents", {})
    required_document_keys = {
        "capability_specs",
        "task_specs",
        "readiness_profiles",
        "adrs",
        "conformance",
        "runbooks",
    }
    if not isinstance(documents, dict) or set(documents) != required_document_keys:
        errors.append(
            "portfolio/projects.json: Omnius canonical document index is incomplete"
        )
    elif any(
        not str(url).startswith("https://github.com/100rd/omnius/")
        for url in documents.values()
    ):
        errors.append(
            "portfolio/projects.json: Omnius canonical documents must stay component-owned"
        )

    initiatives = omnius.get("initiatives", [])
    initiative_ids = [item.get("id") for item in initiatives if isinstance(item, dict)]
    if initiative_ids != ["repository-adoption", "p0-standard-http-service-v3"]:
        errors.append(
            "portfolio/projects.json: Omnius initiative index is incomplete or unordered"
        )

    blockers = omnius.get("blockers")
    if (
        not isinstance(blockers, list)
        or not blockers
        or any(not str(item).strip() for item in blockers)
    ):
        errors.append(
            "portfolio/projects.json: Omnius must publish non-empty readiness blockers"
        )

    readiness = omnius.get("readiness", {})
    profile = readiness.get("profile", {})
    if profile.get("id") != "p0-standard-http-service-v3":
        errors.append(
            "portfolio/projects.json: Omnius readiness profile id is not the bounded v3 slice"
        )
    if profile.get("assurance_profile") != "P0":
        errors.append(
            "portfolio/projects.json: Omnius readiness assurance profile must be P0"
        )
    if profile.get("platform_path") != "standard-http-service/v3":
        errors.append(
            "portfolio/projects.json: Omnius readiness PlatformPath must be v3"
        )
    if profile.get("source_path") != "specs/readiness/p0-standard-http-service-v3.json":
        errors.append(
            "portfolio/projects.json: Omnius readiness source path must name the v3 profile"
        )
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(profile.get("source_sha256", ""))):
        errors.append(
            "portfolio/projects.json: Omnius readiness source digest must be canonical sha256"
        )
    for field in (
        "selected_capabilities",
        "selected_requirements",
        "selected_probes",
        "readiness_blockers",
        "forbidden_actions",
    ):
        value = profile.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            errors.append(
                f"portfolio/projects.json: Omnius profile {field} must be a positive integer"
            )

    verification = readiness.get("local_verification", {})
    if verification.get("evidence_scope") not in {
        "dirty-worktree-local",
        "immutable-component",
    }:
        errors.append("portfolio/projects.json: Omnius evidence scope is unknown")
    if verification.get("worktree_publication_status") not in {
        "dirty-unpublished",
        "clean-immutable",
    }:
        errors.append(
            "portfolio/projects.json: Omnius worktree publication status is unknown"
        )
    if not re.fullmatch(r"[0-9a-f]{40}", str(verification.get("inspected_head", ""))):
        errors.append(
            "portfolio/projects.json: Omnius inspected HEAD must be a full Git commit"
        )
    for field in (
        "acceptance_tests_passed",
        "portable_probes_passed",
        "environment_qualified_skips",
        "human_waivers",
        "target_profile_failures",
    ):
        value = verification.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(
                f"portfolio/projects.json: Omnius verification {field} must be non-negative"
            )

    if verification.get("contract_conformance") not in {"conformant", "nonconformant"}:
        errors.append(
            "portfolio/projects.json: Omnius contract-conformance decision is invalid"
        )
    if verification.get("assurance_certification") not in {"green", "amber", "red"}:
        errors.append(
            "portfolio/projects.json: Omnius assurance-certification decision is invalid"
        )

    unpublished = (
        profile.get("status") != "ready"
        or profile.get("readiness_blockers", 0) > 0
        or verification.get("evidence_scope") != "immutable-component"
        or verification.get("worktree_publication_status") != "clean-immutable"
        or verification.get("assurance_certification") != "green"
        or verification.get("human_waivers", 0) > 0
        or verification.get("target_profile_failures", 0) > 0
    )
    if unpublished and verification.get("activation") != "blocked":
        errors.append("portfolio/projects.json: Omnius activation must remain blocked")

    if verification.get("evidence_scope") == "dirty-worktree-local":
        release = omnius.get("current_release", {})
        if release.get("version") is not None or release.get("evidence") is not None:
            errors.append(
                "portfolio/projects.json: dirty Omnius evidence cannot claim a release"
            )


def _validate_registry(registry: dict[str, Any], errors: list[str]) -> None:
    if registry.get("schema_version") != 1:
        errors.append("portfolio/projects.json: schema_version must be 1")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(registry.get("as_of", ""))):
        errors.append("portfolio/projects.json: as_of must be YYYY-MM-DD")

    authority = registry.get("authority")
    if not isinstance(authority, dict) or set(authority) != {
        "portfolio",
        "components",
        "intake",
    }:
        errors.append(
            "portfolio/projects.json: authority must define portfolio, components, and intake"
        )

    projects = registry.get("projects")
    if not isinstance(projects, list) or not projects:
        errors.append("portfolio/projects.json: projects must be a non-empty list")
        return

    ids = [project.get("id") for project in projects if isinstance(project, dict)]
    if len(ids) != len(projects) or any(
        not isinstance(project_id, str) for project_id in ids
    ):
        errors.append("portfolio/projects.json: every project needs a string id")
    if len(ids) != len(set(ids)):
        errors.append("portfolio/projects.json: project ids must be unique")

    for project in projects:
        if not isinstance(project, dict):
            continue
        project_id = project.get("id", "<unknown>")
        for key in (
            "name",
            "repository",
            "role",
            "portfolio_status",
            "owners",
            "current_release",
        ):
            if key not in project:
                errors.append(
                    f"portfolio/projects.json: project {project_id!r} is missing {key}"
                )
        if not str(project.get("repository", "")).startswith("https://github.com/"):
            errors.append(
                f"portfolio/projects.json: project {project_id!r} needs a GitHub repository URL"
            )
        owners = project.get("owners", {})
        if (
            not isinstance(owners, dict)
            or not owners.get("component")
            or not owners.get("portfolio")
        ):
            errors.append(
                f"portfolio/projects.json: project {project_id!r} needs component/portfolio owners"
            )
        current_release = project.get("current_release")
        if (
            not isinstance(current_release, dict)
            or not {"version", "evidence"}.issubset(current_release)
            or any(
                value is not None and not isinstance(value, str)
                for value in (
                    current_release.get("version"),
                    current_release.get("evidence"),
                )
            )
        ):
            errors.append(
                "portfolio/projects.json: project "
                f"{project_id!r} current_release must define nullable version/evidence"
            )
        elif (current_release.get("version") is None) != (
            current_release.get("evidence") is None
        ):
            errors.append(
                "portfolio/projects.json: project "
                f"{project_id!r} release version/evidence must both be set or both be null"
            )

    omniscience = _project_by_id(registry, "omniscience")
    if omniscience is None:
        errors.append("portfolio/projects.json: omniscience project is required")
        return

    if omniscience.get("portfolio_status") != omniscience.get("roadmap", {}).get(
        "status"
    ):
        errors.append(
            "portfolio/projects.json: Omniscience portfolio and roadmap statuses differ"
        )

    mcp = omniscience.get("mcp", {})
    target_version = str(mcp.get("target_contract_version", ""))
    if not re.fullmatch(r"[1-9]\d*\.\d+\.\d+", target_version):
        errors.append(
            "portfolio/projects.json: MCP target contract must be stable semver"
        )

    registry_tools = mcp.get("target_tool_registry", [])
    if not isinstance(registry_tools, list) or any(
        not isinstance(tool, str) for tool in registry_tools
    ):
        errors.append(
            "portfolio/projects.json: target_tool_registry must contain tool names"
        )
        registry_tools = []
    if registry_tools != sorted(registry_tools):
        errors.append("portfolio/projects.json: target_tool_registry must be sorted")
    if len(registry_tools) != len(set(registry_tools)):
        errors.append(
            "portfolio/projects.json: target_tool_registry contains duplicates"
        )
    if mcp.get("target_tool_count") != len(registry_tools):
        errors.append(
            "portfolio/projects.json: target_tool_count does not match target_tool_registry"
        )
    if "contract_info" not in registry_tools:
        errors.append(
            "portfolio/projects.json: MCP v1 registry must include contract_info"
        )
    if mcp.get("target_tool_count") != mcp.get("current_runtime_tool_count", -1) + 1:
        errors.append(
            "portfolio/projects.json: MCP v1 must add exactly contract_info to the current registry"
        )

    token = mcp.get("token_profile", {})
    expected_token_facts = {
        "id": "omniscience-mcp-read-v1",
        "issuer": "Omniscience admin token API",
        "exact_scopes": ["search"],
        "max_lifetime_days": 30,
        "rotation_overlap_hours": 24,
        "workspace_binding": "required",
    }
    if token != expected_token_facts:
        errors.append(
            "portfolio/projects.json: bootstrap token profile differs from ADR-0017"
        )

    initiatives = omniscience.get("initiatives", [])
    initiative_ids = [item.get("id") for item in initiatives if isinstance(item, dict)]
    if initiative_ids != ["230", "244", "350"]:
        errors.append(
            "portfolio/projects.json: Omniscience initiative index must be 230, 244, 350"
        )
    initiative_230 = next((item for item in initiatives if item.get("id") == "230"), {})
    if (
        initiative_230.get("completed_tasks") != 12
        or initiative_230.get("total_tasks") != 13
        or initiative_230.get("remaining") != ["242"]
    ):
        errors.append(
            "portfolio/projects.json: issue 230 must record 12/13 complete with only 242 remaining"
        )

    slices = next(
        (item.get("slices", []) for item in initiatives if item.get("id") == "350"), []
    )
    specs = omniscience.get("spec_index", [])
    task_specs = [
        {"id": entry.get("id"), "status": entry.get("status")}
        for entry in specs
        if entry.get("kind") == "task"
    ]
    if task_specs != slices:
        errors.append(
            "portfolio/projects.json: issue 350 slices and task SPEC index differ"
        )
    capability_specs = [entry for entry in specs if entry.get("kind") == "capability"]
    if (
        len(capability_specs) != 1
        or capability_specs[0].get("id") != "SPEC-MCP"
        or capability_specs[0].get("status")
        not in {"planned-component-contract", "implemented-component-contract"}
    ):
        errors.append(
            "portfolio/projects.json: SPEC index must contain one valid SPEC-MCP capability"
        )

    evidence = omniscience.get("execution_evidence", [])
    evidence_ids: set[str] = set()
    for entry in evidence:
        evidence_id = entry.get("id")
        if not evidence_id or evidence_id in evidence_ids:
            errors.append(
                "portfolio/projects.json: execution evidence ids must be present and unique"
            )
        evidence_ids.add(evidence_id)
        if entry.get("status") in {"implemented", "verified", "superseded"}:
            if not str(entry.get("pull_request", "")).startswith("https://github.com/"):
                errors.append(
                    f"portfolio/projects.json: terminal evidence {evidence_id!r} needs a PR"
                )
            if not re.fullmatch(r"[0-9a-f]{40}", str(entry.get("merge_commit", ""))):
                errors.append(
                    f"portfolio/projects.json: terminal evidence {evidence_id!r} needs a full commit"
                )
            if not entry.get("verification"):
                errors.append(
                    f"portfolio/projects.json: terminal evidence {evidence_id!r} needs verification authority"
                )

    _validate_omnius(registry, errors)


def _validate_documents(
    root: Path, registry: dict[str, Any], errors: list[str]
) -> None:
    omniscience = _project_by_id(registry, "omniscience")
    if omniscience is None:
        return

    page = _read_text(root, OMNISCIENCE_PAGE_PATH, errors)
    index = _read_text(root, PORTFOLIO_INDEX_PATH, errors)
    adr = _read_text(root, MCP_ADR_PATH, errors)
    readme = _read_text(root, README_PATH, errors)
    omnius_page = _read_text(root, OMNIUS_PAGE_PATH, errors)
    project_status = _read_text(root, PROJECT_STATUS_PATH, errors)
    implementation_roadmap = _read_text(root, IMPLEMENTATION_ROADMAP_PATH, errors)
    track_b_spec_index = _read_text(root, TRACK_B_SPEC_INDEX_PATH, errors)
    sre_harness_readme = _read_text(root, SRE_HARNESS_README_PATH, errors)
    mcp = omniscience["mcp"]

    page_facts = [
        f"**As of:** {registry['as_of']}",
        f"**Portfolio status:** `{omniscience['portfolio_status']}`",
        f"| Current release | `{omniscience['current_release']['version']}`",
        f"| Roadmap status | `{omniscience['roadmap']['status']}` |",
        f"| Current MCP contract | `{mcp['current_contract_version']}` |",
        f"| Target MCP contract | `{mcp['target_contract_version']}` |",
        f"| Runtime tools now | `{mcp['current_runtime_tool_count']}` |",
        f"| Target v1 tools | `{mcp['target_tool_count']}`",
        f"| Bootstrap token profile | `{mcp['token_profile']['id']}` |",
    ]
    for fact in page_facts:
        _require(page, fact, OMNISCIENCE_PAGE_PATH, errors)

    for entry in omniscience["spec_index"]:
        _require(
            page,
            f"| `{entry['id']}` | {entry['kind']} | `{entry['status']}` |",
            OMNISCIENCE_PAGE_PATH,
            errors,
        )

    for entry in omniscience["execution_evidence"]:
        for fact in (
            entry["id"],
            entry["status"],
            entry["pull_request"],
            entry["merge_commit"],
        ):
            _require(page, str(fact), OMNISCIENCE_PAGE_PATH, errors)

    adr_facts = [
        "- **Status:** Accepted",
        f"- **Contract version:** `{mcp['target_contract_version']}`",
        f"- **Target tool registry count:** `{mcp['target_tool_count']}`",
        f"- **Bootstrap token profile:** `{mcp['token_profile']['id']}`",
    ]
    for fact in adr_facts:
        _require(adr, fact, MCP_ADR_PATH, errors)
    for tool in mcp["target_tool_registry"]:
        if not re.search(rf"(?<![a-z_]){re.escape(tool)}(?![a-z_])", adr):
            errors.append(f"{MCP_ADR_PATH}: target tool {tool!r} is absent")

    for phrase in (
        "`genai-enablement` | Portfolio status and roadmap",
        "Component repository | Capability SPECs, task SPECs",
        "GitHub Issues | Mutable intake",
        "## Human-owned decision backlog",
        "never\nqueries the GitHub API",
    ):
        _require(index, phrase, PORTFOLIO_INDEX_PATH, errors)

    backlog = registry.get("decision_backlog", {})
    items = backlog.get("items", []) if isinstance(backlog, dict) else []
    if not isinstance(items, list):
        items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        decision_id = item.get("id")
        path_value = item.get("path")
        requires = item.get("requires")
        blocks = item.get("blocks")
        if (
            not isinstance(decision_id, str)
            or not isinstance(path_value, str)
            or not isinstance(requires, list)
            or not isinstance(blocks, list)
        ):
            continue
        filename = Path(path_value).name
        requires_text = (
            ", ".join(f"`{dependency}`" for dependency in requires) if requires else "—"
        )
        blocks_text = ", ".join(f"`{blocked}`" for blocked in blocks)
        index_row = (
            f"| [{decision_id}](../decisions/{filename}) | `{item.get('review_group')}` | "
            f"{requires_text} | {blocks_text} | `{item.get('next_gate')}` |"
        )
        roadmap_row = (
            f"| [{decision_id}](decisions/{filename}) | `{item.get('review_group')}` | "
            f"{requires_text} | {blocks_text} | `{item.get('next_gate')}` |"
        )
        _require(index, index_row, PORTFOLIO_INDEX_PATH, errors)
        _require(
            implementation_roadmap,
            roadmap_row,
            IMPLEMENTATION_ROADMAP_PATH,
            errors,
        )
        _require(
            project_status,
            f"[{decision_id}](docs/decisions/{filename})",
            PROJECT_STATUS_PATH,
            errors,
        )
    for text, path in (
        (implementation_roadmap, IMPLEMENTATION_ROADMAP_PATH),
        (project_status, PROJECT_STATUS_PATH),
    ):
        _require(text, "human-disposition", path, errors)
        _require(text, "does not accept", path, errors)

    spec_backlog = registry.get("track_b_spec_backlog", {})
    spec_items = spec_backlog.get("items", []) if isinstance(spec_backlog, dict) else []
    if not isinstance(spec_items, list):
        spec_items = []
    for item in spec_items:
        if not isinstance(item, dict):
            continue
        spec_id = item.get("id")
        path_value = item.get("path")
        requires = item.get("requires")
        requirements = item.get("requirements")
        probes = item.get("probes")
        if (
            not isinstance(spec_id, str)
            or not isinstance(path_value, str)
            or not isinstance(requires, list)
            or any(not isinstance(value, str) for value in requires)
            or isinstance(requirements, bool)
            or not isinstance(requirements, int)
            or isinstance(probes, bool)
            or not isinstance(probes, int)
        ):
            continue
        filename = Path(path_value).name
        requires_text = (
            ", ".join(f"`{dependency}`" for dependency in requires) if requires else "—"
        )
        spec_row = (
            f"| [{spec_id}]({filename}) | `{item.get('stage')}` | "
            f"`{item.get('source_status')}` | `{requirements}` / `{probes}` | "
            f"{requires_text} | `{item.get('portable_evidence')}` | "
            f"`{item.get('operational_state')}` | `{item.get('next_gate')}` |"
        )
        _require(track_b_spec_index, spec_row, TRACK_B_SPEC_INDEX_PATH, errors)
        _require(
            implementation_roadmap,
            f"specs/{filename}",
            IMPLEMENTATION_ROADMAP_PATH,
            errors,
        )
        _require(
            project_status,
            f"docs/specs/{filename}",
            PROJECT_STATUS_PATH,
            errors,
        )
        traceability_path = item.get("portable_traceability_manifest")
        if isinstance(traceability_path, str):
            source_spec = _read_text(root, Path(path_value), errors)
            for text, path in (
                (track_b_spec_index, TRACK_B_SPEC_INDEX_PATH),
                (implementation_roadmap, IMPLEMENTATION_ROADMAP_PATH),
                (project_status, PROJECT_STATUS_PATH),
                (source_spec, Path(path_value)),
            ):
                _require(text, traceability_path, path, errors)
            _require(
                sre_harness_readme,
                f"spec-traceability/{Path(traceability_path).name}",
                SRE_HARNESS_README_PATH,
                errors,
            )
    checked_traceability = sum(
        isinstance(item.get("portable_traceability_manifest"), str)
        for item in spec_items
        if isinstance(item, dict)
    )
    remaining_traceability = sum(
        item.get("portable_traceability_manifest") is None
        for item in spec_items
        if isinstance(item, dict)
    )
    traceability_summary = (
        "Traceability registry summary: "
        f"`{checked_traceability}` checked manifests; "
        f"`{remaining_traceability}` remaining null."
    )
    for text, path in (
        (track_b_spec_index, TRACK_B_SPEC_INDEX_PATH),
        (implementation_roadmap, IMPLEMENTATION_ROADMAP_PATH),
        (project_status, PROJECT_STATUS_PATH),
    ):
        _require(text, traceability_summary, path, errors)
        _require(text, "track_b_spec_backlog", path, errors)
        _require(text, "external-evidence-required", path, errors)
        _require(text, "does not authorize", path, errors)

    for link in (
        "portfolio/projects.json",
        "docs/portfolio/README.md",
        "docs/portfolio/omniscience.md",
        "docs/specs/README.md",
    ):
        _require(readme, link, README_PATH, errors)
    if "MCP (13 tools)" in readme:
        errors.append("README.md: stale Omniscience 13-tool claim remains")

    omnius = _project_by_id(registry, "omnius")
    if omnius is None:
        return
    profile = omnius.get("readiness", {}).get("profile", {})
    verification = omnius.get("readiness", {}).get("local_verification", {})
    omnius_facts = [
        f"**As of:** {registry['as_of']}",
        f"**Portfolio status:** `{omnius['portfolio_status']}`",
        f"| Roadmap status | `{omnius['roadmap']['status']}` |",
        f"| Inspected component HEAD | `{verification['inspected_head']}` |",
        f"| Worktree publication status | `{verification['worktree_publication_status']}` |",
        f"| Readiness profile | `{profile['id']}` |",
        f"| Profile state | `{profile['status']}` (non-authorizing) |",
        f"| Assurance profile | `{profile['assurance_profile']}` |",
        f"| PlatformPath | `{profile['platform_path']}` |",
        f"| Source profile | `{profile['source_path']}` |",
        f"| Source profile digest | `{profile['source_sha256']}` |",
        (
            f"| Selected slice | `{profile['selected_capabilities']}` capabilities, "
            f"`{profile['selected_requirements']}` requirements, "
            f"`{profile['selected_probes']}` probes |"
        ),
        f"| Component readiness blockers | `{profile['readiness_blockers']}` |",
        f"| Preserved forbidden actions | `{profile['forbidden_actions']}` |",
        f"| Evidence scope | `{verification['evidence_scope']}` |",
        (
            f"| Acceptance contract | `{verification['acceptance_tests_passed']}` passed, "
            f"`{verification['environment_qualified_skips']}` environment-qualified skips |"
        ),
        f"| Portable conformance probes | `{verification['portable_probes_passed']}` passed |",
        f"| Human waivers | `{verification['human_waivers']}` |",
        f"| Target-profile failures | `{verification['target_profile_failures']}` |",
        f"| Contract conformance | `{verification['contract_conformance']}` |",
        f"| Assurance certification | `{verification['assurance_certification']}` |",
        f"| Activation | `{verification['activation']}` |",
    ]
    for fact in omnius_facts:
        _require(omnius_page, fact, OMNIUS_PAGE_PATH, errors)
    for url in omnius.get("canonical_documents", {}).values():
        _require(omnius_page, str(url), OMNIUS_PAGE_PATH, errors)
    for link in ("docs/portfolio/omnius.md",):
        _require(readme, link, README_PATH, errors)


def check_repository(
    root: Path = ROOT, *, omnius_root: Path | None = None
) -> list[str]:
    errors: list[str] = []
    registry = _load_json(root / REGISTRY_PATH, errors)
    shape_error_count = len(errors)
    _validate_registry_shape(registry, errors)
    if len(errors) != shape_error_count:
        return errors

    base_error_count = len(errors)
    try:
        _validate_registry(registry, errors)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        errors.append(
            "portfolio/projects.json: malformed registry shape rejected during "
            f"base validation ({type(exc).__name__})"
        )
        return errors
    if len(errors) != base_error_count:
        return errors

    backlog_error_count = len(errors)
    try:
        _validate_decision_backlog(root, registry, errors)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        errors.append(
            "portfolio/projects.json: malformed registry shape rejected during "
            f"decision-backlog validation ({type(exc).__name__})"
        )
        return errors
    if len(errors) != backlog_error_count:
        return errors

    spec_error_count = len(errors)
    try:
        _validate_track_b_spec_backlog(root, registry, errors)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        errors.append(
            "portfolio/projects.json: malformed registry shape rejected during "
            f"Track-B SPEC validation ({type(exc).__name__})"
        )
        return errors
    if len(errors) != spec_error_count:
        return errors

    _validate_documents(root, registry, errors)
    if omnius_root is not None:
        _validate_omnius_component(omnius_root, registry, errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--omnius-root",
        type=Path,
        help="optionally verify the Omnius snapshot against a read-only sibling checkout",
    )
    args = parser.parse_args(argv)
    errors = check_repository(omnius_root=args.omnius_root)
    if errors:
        print("Portfolio drift check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "Portfolio drift check passed (offline; registry, roadmap, SPEC index, contract, evidence)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
