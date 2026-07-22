#!/usr/bin/env python3
"""Validate synchronized-platform discovery, inventories, and work-package references."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "portfolio" / "synchronized-platform.json"
EXPECTED_COMPONENTS = {
    "barbarossa": "Barbarossa",
    "genai-enablement": "genai-enablement",
    "omnius": "omnius",
    "omniscience": "Omniscience",
    "platform-portal": "platform-portal",
}
COMPONENT_PLAN_HEADINGS = {
    "barbarossa": "Barbarossa",
    "genai-enablement": "genai-enablement",
    "omnius": "omnius",
    "omniscience": "Omniscience",
    "platform-portal": "platform-portal",
}
ADR_ID_PATTERN = re.compile(r"\bADR-\d{4}\b")
CAPABILITY_ID_PATTERN = re.compile(r"\bSPEC-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
TASK_ID_PATTERN = re.compile(
    r"\b(?:gh-issue-\d+|task-sp-[a-z0-9]+)(?:-[a-z0-9]+)*\b"
)
PACKAGE_ID_PATTERN = re.compile(r"\bSP-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
SOURCE_STATUS_PATTERN = re.compile(
    r"(?im)^\s*(?:-\s*)?"
    r"(?:\*{0,2}status\*{0,2}\s*:|\*{0,2}status\s*:\*{0,2})"
    r"\s*\*{0,2}([a-z][a-z-]*)"
)


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("synchronized-platform registry must be a JSON object")
    return data


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_file(root: Path, value: Any) -> Path | None:
    if not _non_empty_string(value):
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _source_status(text: str) -> str | None:
    match = SOURCE_STATUS_PATTERN.search(text[:2400])
    return match.group(1).lower() if match else None


def _task_handoff_findings(text: str) -> list[str]:
    """Return missing immutable-handoff fields from one task SPEC frontmatter."""
    if not text.startswith("---\n"):
        return ["task frontmatter is missing"]
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ["task frontmatter is unterminated"]
    frontmatter = parts[1]
    findings: list[str] = []
    task_id_match = re.search(r"(?m)^id:\s*(\S+)\s*$", frontmatter)
    task_id = task_id_match.group(1) if task_id_match else ""
    if re.search(r"(?m)^evidenceDestination:\s*\S+\s*$", frontmatter) is None:
        findings.append("evidenceDestination is missing")

    acceptance_match = re.search(
        r"(?ms)^acceptanceCriteria:\s*\n(.*?)^rollback:\s*", frontmatter
    )
    if acceptance_match is None:
        findings.append("acceptanceCriteria or rollback boundary is missing")
    else:
        acceptance = acceptance_match.group(1)
        criteria_count = len(re.findall(r"\bid:\s*AC-[A-Z0-9-]+", acceptance))
        ground_truth_count = len(re.findall(r"\bgroundTruth:\s*", acceptance))
        if criteria_count == 0:
            findings.append("acceptanceCriteria contains no AC-* entries")
        elif ground_truth_count != criteria_count:
            findings.append(
                "every acceptance criterion requires exactly one external groundTruth"
            )

    scope_match = re.search(r"(?ms)^scope:\s*\n(.*?)^acceptanceCriteria:", frontmatter)
    if scope_match is not None:
        include_scope = scope_match.group(1).split("exclude:", 1)[0]
        if "docs/specs/**" in include_scope:
            findings.append("writable scope includes the task-SPEC oracle docs/specs/**")
        if (
            "portfolio/synchronized-platform.json" in include_scope
            and task_id != "task-sp-70-continuous-management-contract-release"
        ):
            findings.append("writable scope includes the synchronized registry lock")
    return findings


def _table_rows(text: str, pattern: re.Pattern[str]) -> tuple[dict[str, list[str]], set[str]]:
    rows: dict[str, list[str]] = {}
    duplicates: set[str] = set()
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells:
            continue
        match = pattern.search(cells[0])
        if match is None:
            continue
        item_id = match.group(0)
        if item_id in rows:
            duplicates.add(item_id)
        rows[item_id] = cells
    return rows, duplicates


def _component_plan_section(plan_text: str, component_id: str) -> str:
    heading = COMPONENT_PLAN_HEADINGS[component_id]
    match = re.search(rf"(?m)^### `{re.escape(heading)}`\s*$", plan_text)
    if match is None:
        return ""
    remainder = plan_text[match.end() :]
    next_heading = re.search(r"(?m)^#{2,3}\s+", remainder)
    return remainder[: next_heading.start()] if next_heading else remainder


def _component_roots(workspace_root: Path | None) -> dict[str, Path]:
    roots = {"genai-enablement": ROOT}
    if workspace_root is not None:
        resolved_workspace = workspace_root.resolve()
        for component_id, directory in EXPECTED_COMPONENTS.items():
            candidate = (resolved_workspace / directory).resolve()
            if candidate.parent == resolved_workspace:
                roots[component_id] = candidate
    return roots


def _registered_paths(component: dict[str, Any], key: str) -> set[str]:
    items = component.get(key, [])
    if not isinstance(items, list):
        return set()
    return {
        item["path"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def _discovered_capability_paths(component_id: str, root: Path) -> set[str]:
    if component_id == "genai-enablement":
        return {
            path.relative_to(root).as_posix()
            for path in (root / "docs" / "specs").glob("SPEC-*.md")
        }
    return {
        path.relative_to(root).as_posix()
        for path in (root / "specs").glob("SPEC-*.md")
        if path.name != "SPEC-INDEX.md"
    }


def _discovered_task_paths(component_id: str, root: Path) -> set[str]:
    task_root = root / "docs" / "specs"
    if not task_root.is_dir():
        return set()
    return {
        path.relative_to(root).as_posix()
        for path in task_root.glob("*.md")
        if TASK_ID_PATTERN.fullmatch(path.stem)
    }


def validate_registry(
    registry: dict[str, Any], workspace_root: Path | None = None
) -> list[str]:
    errors: list[str] = []
    if registry.get("schema_version") != 1:
        errors.append("registry schema_version must be 1")

    canonical = registry.get("canonical_plan")
    if not isinstance(canonical, dict):
        errors.append("canonical_plan must be an object")
        canonical = {}
    plan_path = canonical.get("path")
    plan_url = canonical.get("url")
    resolved_plan = _safe_file(ROOT, plan_path)
    if resolved_plan is None:
        errors.append("canonical plan path is missing")
        plan_text = ""
    else:
        plan_text = resolved_plan.read_text(encoding="utf-8")
    if not isinstance(plan_url, str) or not plan_url.startswith("https://github.com/"):
        errors.append("canonical plan URL must be an absolute GitHub URL")

    entrypoint = canonical.get("entrypoint")
    if _safe_file(ROOT, entrypoint) is None:
        errors.append("canonical root entrypoint is missing")

    adrs = registry.get("cross_repo_adrs")
    if not isinstance(adrs, list):
        errors.append("cross_repo_adrs must be a list")
        adrs = []
    adr_ids = [item.get("id") for item in adrs if isinstance(item, dict)]
    valid_adr_ids = [
        item_id
        for item_id in adr_ids
        if isinstance(item_id, str) and ADR_ID_PATTERN.fullmatch(item_id)
    ]
    if len(valid_adr_ids) != len(adr_ids):
        errors.append("every cross-repo ADR requires an ADR-NNNN id")
    duplicate_adrs = _duplicates(valid_adr_ids)
    if duplicate_adrs:
        errors.append(f"duplicate cross-repo ADR ids: {sorted(duplicate_adrs)}")
    adr_plan_rows, duplicate_plan_adrs = _table_rows(plan_text, ADR_ID_PATTERN)
    if duplicate_plan_adrs:
        errors.append(f"duplicate ADR rows in canonical plan: {sorted(duplicate_plan_adrs)}")
    if set(valid_adr_ids) != set(adr_plan_rows):
        errors.append(
            "ADR inventory drift between registry and canonical plan "
            f"(missing={sorted(set(valid_adr_ids) - set(adr_plan_rows))}, "
            f"extra={sorted(set(adr_plan_rows) - set(valid_adr_ids))})"
        )
    for adr in adrs:
        if not isinstance(adr, dict):
            errors.append("cross-repo ADR entries must be objects")
            continue
        adr_id = adr.get("id")
        path_value = adr.get("path")
        status = adr.get("status")
        source_path = _safe_file(ROOT, path_value)
        if source_path is None:
            errors.append(f"{adr_id}: ADR path is missing")
            continue
        text = source_path.read_text(encoding="utf-8")
        if not _non_empty_string(status) or _source_status(text) != status.lower():
            errors.append(f"{adr_id}: ADR status does not match source")
        plan_row = adr_plan_rows.get(adr_id) if isinstance(adr_id, str) else None
        if plan_row is not None and (
            len(plan_row) < 2
            or not _non_empty_string(status)
            or plan_row[1].strip("`").lower() != status.lower()
        ):
            errors.append(f"{adr_id}: ADR status drift between registry and canonical plan")

    components = registry.get("components")
    if not isinstance(components, list):
        errors.append("components must be a list")
        components = []
    component_ids = [
        item.get("id") for item in components if isinstance(item, dict)
    ]
    if set(component_ids) != set(EXPECTED_COMPONENTS):
        errors.append(
            f"component ids must be exactly {sorted(EXPECTED_COMPONENTS)}, "
            f"found {sorted(str(item_id) for item_id in component_ids)}"
        )
    duplicate_components = _duplicates(
        [item_id for item_id in component_ids if isinstance(item_id, str)]
    )
    if duplicate_components:
        errors.append(f"duplicate component ids: {sorted(duplicate_components)}")

    roots = _component_roots(workspace_root)
    catalogs: dict[tuple[str, str], set[str]] = {}
    readiness_selections: dict[tuple[str, str], set[str]] = {}
    for component in components:
        if not isinstance(component, dict):
            errors.append("component entries must be objects")
            continue
        component_id = component.get("id")
        if not isinstance(component_id, str):
            errors.append("component id must be a string")
            continue
        expected_directory = EXPECTED_COMPONENTS.get(component_id)
        if component.get("directory") != expected_directory:
            errors.append(
                f"{component_id}: directory must be {expected_directory!r}, "
                f"found {component.get('directory')!r}"
            )

        for kind, key in (
            ("capability", "capability_specs"),
            ("task", "task_specs"),
            ("readiness", "readiness_profiles"),
        ):
            items = component.get(key)
            if not isinstance(items, list):
                errors.append(f"{component_id}: {key} must be a list")
                items = []
            ids = [
                item.get("id") for item in items if isinstance(item, dict)
            ]
            if any(not _non_empty_string(item_id) for item_id in ids):
                errors.append(f"{component_id}: every {kind} requires a non-empty id")
            duplicates = _duplicates(
                [item_id for item_id in ids if _non_empty_string(item_id)]
            )
            if duplicates:
                errors.append(
                    f"{component_id}: duplicate {kind} ids: {sorted(duplicates)}"
                )
            catalogs[(component_id, kind)] = {
                item_id for item_id in ids if _non_empty_string(item_id)
            }

        root = roots.get(component_id)
        if root is None:
            continue
        if not root.is_dir():
            errors.append(f"{component_id}: component root is missing: {root}")
            continue
        entry = component.get("entrypoint")
        entry_path = _safe_file(root, entry)
        if entry_path is None:
            errors.append(f"{component_id}: PLATFORM entrypoint is missing")
            entry_text = ""
        else:
            entry_text = entry_path.read_text(encoding="utf-8")
        if isinstance(plan_url, str) and plan_url not in entry_text:
            errors.append(f"{component_id}: PLATFORM entrypoint lacks canonical plan URL")

        readme = component.get("readme")
        readme_path = _safe_file(root, readme)
        if readme_path is None:
            errors.append(f"{component_id}: root readme is missing")
        elif "PLATFORM.md" not in readme_path.read_text(encoding="utf-8"):
            errors.append(f"{component_id}: root readme does not link PLATFORM.md")

        for index_key in ("capability_index", "task_index"):
            index_path = component.get(index_key)
            if index_path is None:
                continue
            resolved_index = _safe_file(root, index_path)
            if resolved_index is None:
                errors.append(f"{component_id}: {index_key} is missing")
            elif "PLATFORM.md" not in resolved_index.read_text(encoding="utf-8"):
                errors.append(f"{component_id}: {index_key} does not link PLATFORM.md")

        for key in ("capability_specs", "task_specs", "readiness_profiles"):
            items = component.get(key, [])
            for item in items:
                if not isinstance(item, dict):
                    errors.append(f"{component_id}: {key} entries must be objects")
                    continue
                item_id = item.get("id")
                path_value = item.get("path")
                status = item.get("status")
                source_path = _safe_file(root, path_value)
                if source_path is None:
                    errors.append(f"{component_id}/{item_id}: source path is missing")
                    continue
                if key == "readiness_profiles":
                    try:
                        source = json.loads(source_path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        errors.append(f"{component_id}/{item_id}: readiness source is invalid JSON")
                        continue
                    source_id = source.get("metadata", {}).get("name")
                    source_status = source.get("metadata", {}).get("status")
                    source_capabilities = {
                        capability.get("id")
                        for capability in source.get("spec", {}).get("capabilities", [])
                        if isinstance(capability, dict)
                        and _non_empty_string(capability.get("id"))
                    }
                    selected = item.get("selected_capabilities")
                    selected_set = (
                        {value for value in selected if _non_empty_string(value)}
                        if isinstance(selected, list)
                        else set()
                    )
                    if item_id != source_id:
                        errors.append(
                            f"{component_id}/{item_id}: readiness id does not match source"
                        )
                    if not _non_empty_string(status) or status != source_status:
                        errors.append(
                            f"{component_id}/{item_id}: readiness status does not match source"
                        )
                    if not isinstance(selected, list) or selected_set != source_capabilities:
                        errors.append(
                            f"{component_id}/{item_id}: readiness selection does not match source"
                        )
                    if _non_empty_string(item_id):
                        readiness_selections[(component_id, item_id)] = selected_set
                    continue

                text = source_path.read_text(encoding="utf-8")
                if not _non_empty_string(item_id) or item_id not in text[:2400]:
                    errors.append(f"{component_id}/{item_id}: id does not match source")
                if not _non_empty_string(status) or _source_status(text) != status.lower():
                    errors.append(f"{component_id}/{item_id}: status does not match source")
                if key == "task_specs":
                    for finding in _task_handoff_findings(text):
                        errors.append(f"{component_id}/{item_id}: {finding}")

        plan_section = _component_plan_section(plan_text, component_id)
        if not plan_section:
            errors.append(f"{component_id}: component section is missing from canonical plan")
        else:
            plan_capabilities = set(CAPABILITY_ID_PATTERN.findall(plan_section))
            plan_capabilities.discard("SPEC-INDEX")
            registered_capability_ids = catalogs[(component_id, "capability")]
            if plan_capabilities != registered_capability_ids:
                errors.append(
                    f"{component_id}: capability inventory drift in canonical plan "
                    f"(missing={sorted(registered_capability_ids - plan_capabilities)}, "
                    f"extra={sorted(plan_capabilities - registered_capability_ids)})"
                )
            plan_tasks = set(TASK_ID_PATTERN.findall(plan_section))
            registered_task_ids = catalogs[(component_id, "task")]
            if plan_tasks != registered_task_ids:
                errors.append(
                    f"{component_id}: task inventory drift in canonical plan "
                    f"(missing={sorted(registered_task_ids - plan_tasks)}, "
                    f"extra={sorted(plan_tasks - registered_task_ids)})"
                )
            for readiness_id in catalogs[(component_id, "readiness")]:
                if readiness_id not in plan_section:
                    errors.append(
                        f"{component_id}/{readiness_id}: readiness profile is missing "
                        "from canonical plan"
                    )

        registered_capabilities = _registered_paths(component, "capability_specs")
        discovered_capabilities = _discovered_capability_paths(component_id, root)
        if registered_capabilities != discovered_capabilities:
            errors.append(
                f"{component_id}: capability inventory drift "
                f"(missing={sorted(discovered_capabilities - registered_capabilities)}, "
                f"extra={sorted(registered_capabilities - discovered_capabilities)})"
            )
        registered_tasks = _registered_paths(component, "task_specs")
        discovered_tasks = _discovered_task_paths(component_id, root)
        if registered_tasks != discovered_tasks:
            errors.append(
                f"{component_id}: task inventory drift "
                f"(missing={sorted(discovered_tasks - registered_tasks)}, "
                f"extra={sorted(registered_tasks - discovered_tasks)})"
            )

    packages = registry.get("work_packages")
    if not isinstance(packages, list):
        errors.append("work_packages must be a list")
        packages = []
    package_ids = [
        item.get("id") for item in packages if isinstance(item, dict)
    ]
    valid_package_ids = [
        item_id
        for item_id in package_ids
        if isinstance(item_id, str) and PACKAGE_ID_PATTERN.fullmatch(item_id)
    ]
    if len(valid_package_ids) != len(package_ids):
        errors.append("every work package requires a non-empty SP-* id")
    duplicate_packages = _duplicates(valid_package_ids)
    if duplicate_packages:
        errors.append(f"duplicate work-package ids: {sorted(duplicate_packages)}")
    known_packages = set(valid_package_ids)
    known_adrs = set(valid_adr_ids)
    package_plan_rows, duplicate_plan_packages = _table_rows(
        plan_text, PACKAGE_ID_PATTERN
    )
    if duplicate_plan_packages:
        errors.append(
            f"duplicate work-package rows in canonical plan: {sorted(duplicate_plan_packages)}"
        )
    if known_packages != set(package_plan_rows):
        errors.append(
            "work-package inventory drift between registry and canonical plan "
            f"(missing={sorted(known_packages - set(package_plan_rows))}, "
            f"extra={sorted(set(package_plan_rows) - known_packages)})"
        )
    dependency_graph: dict[str, set[str]] = {}
    for package in packages:
        if not isinstance(package, dict):
            errors.append("work-package entries must be objects")
            continue
        package_id = package.get("id")
        if not (
            isinstance(package_id, str) and PACKAGE_ID_PATTERN.fullmatch(package_id)
        ):
            continue
        owner = package.get("owner")
        if owner not in EXPECTED_COMPONENTS:
            errors.append(f"{package_id}: unknown owner {owner!r}")
        status = package.get("status")
        if not _non_empty_string(status):
            errors.append(f"{package_id}: status must be a non-empty string")

        dependencies = package.get("depends_on")
        if not isinstance(dependencies, list) or any(
            not _non_empty_string(dependency) for dependency in dependencies
        ):
            errors.append(f"{package_id}: depends_on must be a list of non-empty ids")
            dependencies = []
        dependency_graph[package_id] = {
            dependency for dependency in dependencies if dependency in known_packages
        }
        for dependency in dependencies:
            if dependency not in known_packages:
                errors.append(f"{package_id}: unknown dependency {dependency!r}")

        governing_adrs = package.get("governing_adrs")
        if not isinstance(governing_adrs, list):
            errors.append(f"{package_id}: governing_adrs must be a list")
            governing_adrs = []
        for adr_id in governing_adrs:
            if adr_id not in known_adrs:
                errors.append(f"{package_id}: unknown governing ADR {adr_id!r}")

        contracts = package.get("contracts")
        if not isinstance(contracts, list):
            errors.append(f"{package_id}: contracts must be a list")
            contracts = []
        contract_keys: list[tuple[Any, Any, Any]] = []
        for contract in contracts:
            if not isinstance(contract, dict):
                errors.append(f"{package_id}: contract references must be objects")
                continue
            project = contract.get("project")
            kind = contract.get("kind")
            contract_id = contract.get("id")
            contract_keys.append((project, kind, contract_id))
            if contract_id not in catalogs.get((project, kind), set()):
                errors.append(
                    f"{package_id}: unknown {project}/{kind} contract {contract_id!r}"
                )
        if len(contract_keys) != len(set(contract_keys)):
            errors.append(f"{package_id}: duplicate contract references")

        readiness_contracts = [
            contract
            for contract in contracts
            if isinstance(contract, dict) and contract.get("kind") == "readiness"
        ]
        for readiness_contract in readiness_contracts:
            project = readiness_contract.get("project")
            readiness_id = readiness_contract.get("id")
            selected_capabilities = readiness_selections.get((project, readiness_id))
            if selected_capabilities is None:
                continue
            package_capabilities = {
                contract.get("id")
                for contract in contracts
                if isinstance(contract, dict)
                and contract.get("project") == project
                and contract.get("kind") == "capability"
                and _non_empty_string(contract.get("id"))
            }
            if package_capabilities != selected_capabilities:
                errors.append(
                    f"{package_id}: capability contracts do not match readiness "
                    f"{project}/{readiness_id} "
                    f"(missing={sorted(selected_capabilities - package_capabilities)}, "
                    f"extra={sorted(package_capabilities - selected_capabilities)})"
                )

        plan_row = package_plan_rows.get(package_id)
        if plan_row is not None:
            if len(plan_row) < 7:
                errors.append(
                    f"{package_id}: canonical plan row must contain seven columns"
                )
            else:
                plan_owner = plan_row[1].strip("`")
                if plan_owner != owner:
                    errors.append(
                        f"{package_id}: owner drift between registry and canonical plan"
                    )
                plan_dependencies = set(
                    PACKAGE_ID_PATTERN.findall(plan_row[4])
                )
                if plan_dependencies != set(dependencies):
                    errors.append(
                        f"{package_id}: dependency drift between registry and canonical plan"
                    )
                plan_status = plan_row[5].strip("`")
                if not _non_empty_string(status) or plan_status != status:
                    errors.append(
                        f"{package_id}: status drift between registry and canonical plan"
                    )

    pending = set(dependency_graph)
    while pending:
        ready = {
            package_id
            for package_id in pending
            if not (dependency_graph[package_id] & pending)
        }
        if not ready:
            errors.append(
                "work-package dependency graph contains a cycle: "
                f"{sorted(pending)}"
            )
            break
        pending -= ready
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help=(
            "Explicit parent containing Barbarossa, genai-enablement, omnius, "
            "Omniscience, and platform-portal"
        ),
    )
    args = parser.parse_args()
    registry = load_registry()
    errors = validate_registry(
        registry,
        args.workspace_root.resolve() if args.workspace_root is not None else None,
    )
    if errors:
        print("Synchronized platform check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    scope = "workspace" if args.workspace_root is not None else "hermetic"
    print(f"Synchronized platform check passed ({scope}; ADR/SPEC discovery and references).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
