"""AC-SP70-1 / AC-SP70-2 probes for task-sp-70-continuous-management-contract-release.

AC-SP70-1 (synchronized-platform-workspace-check): every SP-71..SP-85 package has an
owner-local contract or explicit blocked gate; no local-spec-required package and no
unregistered ready task remain. Ground truth is the owner-local PLATFORM/capability-index/
task-index files discovered by check_synchronized_platform.py --workspace-root.

AC-SP70-2 (synchronized-platform-dependency-and-owner-check): the registry DAG is acyclic
and no task grants sibling writes or live authority. Ground truth is ADR-0020's ownership
boundaries and each owner-local task's own scope, immutable to this registry publisher.

Both probes fail if docs/synchronized-platform/task-sp-70-continuous-management-manifest.json
drifts from portfolio/synchronized-platform.json, or if either drifts from the real sibling
workspace.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SCRIPT = ROOT / "scripts" / "check_synchronized_platform.py"
MANIFEST_PATH = (
    ROOT / "docs" / "synchronized-platform" / "task-sp-70-continuous-management-manifest.json"
)

SPEC = importlib.util.spec_from_file_location("check_synchronized_platform", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

SP70_PACKAGE_IDS = [f"SP-{n}" for n in range(71, 86)]


def _load_manifest() -> dict:
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _registry_package(registry: dict, package_id: str) -> dict:
    return next(
        package for package in registry["work_packages"] if package["id"] == package_id
    )


def _registry_component(registry: dict, component_id: str) -> dict:
    return next(
        component for component in registry["components"] if component["id"] == component_id
    )


def _scope_include_paths(text: str) -> list[str]:
    """Extract scope.include entries from a task frontmatter, in either the
    single-line `[a, b, c]` or multi-line `- item` YAML list form."""
    scope_match = re.search(r"(?ms)^scope:\s*\n(.*?)^(?:acceptanceCriteria:|rollback:)", text)
    if scope_match is None:
        return []
    block = scope_match.group(1)
    include_match = re.search(r"(?ms)include:\s*(.*?)(?:\n\s*exclude:|\Z)", block)
    if include_match is None:
        return []
    include_text = include_match.group(1)
    bracket_match = re.search(r"\[(.*?)\]", include_text, re.S)
    if bracket_match is not None:
        return [item.strip() for item in bracket_match.group(1).split(",") if item.strip()]
    return [
        line.strip()[2:].strip()
        for line in include_text.splitlines()
        if line.strip().startswith("- ")
    ]


class ManifestMatchesRegistryTests(unittest.TestCase):
    """Drift detection: the published manifest must be an exact copy of the
    registry's SP-71..SP-85 work packages, not an independently maintained guess."""

    def setUp(self) -> None:
        self.assertTrue(MANIFEST_PATH.exists(), f"manifest not found at {MANIFEST_PATH}")
        self.manifest = _load_manifest()
        self.registry = checker.load_registry()

    def test_manifest_covers_exactly_sp71_through_sp85(self) -> None:
        manifest_ids = {package["id"] for package in self.manifest["packages"]}
        self.assertEqual(manifest_ids, set(SP70_PACKAGE_IDS))

    def test_manifest_governing_adr_and_task_reference_are_correct(self) -> None:
        self.assertEqual(self.manifest["governing_adr"], "ADR-0020")
        self.assertEqual(
            self.manifest["task"], "task-sp-70-continuous-management-contract-release"
        )

    def test_every_manifest_package_matches_the_live_registry(self) -> None:
        for package_id in SP70_PACKAGE_IDS:
            with self.subTest(package_id=package_id):
                manifest_entry = next(
                    package
                    for package in self.manifest["packages"]
                    if package["id"] == package_id
                )
                registry_entry = _registry_package(self.registry, package_id)
                self.assertEqual(manifest_entry["owner"], registry_entry["owner"])
                self.assertEqual(manifest_entry["status"], registry_entry["status"])
                self.assertEqual(
                    manifest_entry["depends_on"], registry_entry["depends_on"]
                )
                manifest_contracts = {
                    (c["project"], c["kind"], c["id"]) for c in manifest_entry["contracts"]
                }
                registry_contracts = {
                    (c["project"], c["kind"], c["id"]) for c in registry_entry["contracts"]
                }
                self.assertEqual(manifest_contracts, registry_contracts)

    def test_tampering_the_registry_would_be_caught_by_this_comparison(self) -> None:
        """Prove the comparison is sensitive to drift, not vacuously true."""
        tampered = copy.deepcopy(self.registry)
        _registry_package(tampered, "SP-71")["status"] = "drifted-status"
        manifest_entry = next(
            package for package in self.manifest["packages"] if package["id"] == "SP-71"
        )
        tampered_entry = _registry_package(tampered, "SP-71")
        self.assertNotEqual(manifest_entry["status"], tampered_entry["status"])


class AcSp70_1_NoLocalSpecRequiredOrUnregisteredTaskTests(unittest.TestCase):
    """AC-SP70-1: every SP-71..SP-85 package has an owner-local contract, or an
    explicit blocked gate; no unregistered ready task remains."""

    def setUp(self) -> None:
        self.manifest = _load_manifest()
        self.registry = checker.load_registry()

    def test_every_package_is_ready_with_a_task_contract_or_explicitly_blocked(self) -> None:
        for package_id in SP70_PACKAGE_IDS:
            with self.subTest(package_id=package_id):
                entry = next(
                    package
                    for package in self.manifest["packages"]
                    if package["id"] == package_id
                )
                task_contracts = [
                    c for c in entry["contracts"] if c["kind"] == "task"
                ]
                is_blocked = "blocked" in entry["status"].lower()
                if entry["gate"] == "ready":
                    self.assertTrue(
                        task_contracts,
                        f"{package_id}: gate is 'ready' but has no owner-local task contract",
                    )
                    self.assertFalse(
                        is_blocked,
                        f"{package_id}: gate is 'ready' but registry status is blocked",
                    )
                elif entry["gate"] == "blocked":
                    self.assertFalse(
                        task_contracts,
                        f"{package_id}: gate is 'blocked' but a task contract exists "
                        "(package is not actually local-spec-required)",
                    )
                    self.assertTrue(
                        is_blocked, f"{package_id}: gate is 'blocked' but status is not"
                    )
                    self.assertTrue(
                        entry.get("blocked_reason"),
                        f"{package_id}: blocked gate requires an explicit blocked_reason",
                    )
                else:
                    self.fail(f"{package_id}: gate must be 'ready' or 'blocked'")

    def test_every_task_contract_is_registered_in_its_owner_component(self) -> None:
        for package_id in SP70_PACKAGE_IDS:
            with self.subTest(package_id=package_id):
                entry = next(
                    package
                    for package in self.manifest["packages"]
                    if package["id"] == package_id
                )
                for contract in entry["contracts"]:
                    if contract["kind"] != "task":
                        continue
                    owner_component = _registry_component(self.registry, contract["project"])
                    registered_task_ids = {
                        task["id"] for task in owner_component["task_specs"]
                    }
                    self.assertIn(
                        contract["id"],
                        registered_task_ids,
                        f"{package_id}: task {contract['id']!r} is not registered under "
                        f"owner {contract['project']!r}",
                    )

    def test_workspace_checker_finds_no_local_spec_required_or_unregistered_task(self) -> None:
        errors = checker.validate_registry(self.registry, WORKSPACE_ROOT)
        drift_errors = [
            error
            for error in errors
            if "task inventory drift" in error or "component root is missing" in error
        ]
        self.assertEqual([], drift_errors)


class AcSp70_2_OwnerAuthorityAndSeveranceTests(unittest.TestCase):
    """AC-SP70-2: the registry DAG is acyclic and no task grants sibling writes
    or live authority."""

    def setUp(self) -> None:
        self.manifest = _load_manifest()
        self.registry = checker.load_registry()

    def test_full_registry_is_free_of_cycles_and_reference_errors(self) -> None:
        errors = checker.validate_registry(self.registry, WORKSPACE_ROOT)
        self.assertEqual([], errors)

    def test_sp71_through_sp85_subgraph_has_no_cycle(self) -> None:
        subgraph = {
            package_id: set(_registry_package(self.registry, package_id)["depends_on"])
            & set(SP70_PACKAGE_IDS)
            for package_id in SP70_PACKAGE_IDS
        }
        pending = set(subgraph)
        while pending:
            ready = {pid for pid in pending if not (subgraph[pid] & pending)}
            self.assertTrue(
                ready, f"SP-71..SP-85 dependency subgraph contains a cycle: {sorted(pending)}"
            )
            pending -= ready

    def test_a_real_cycle_would_be_detected(self) -> None:
        """Prove the cycle check is sensitive, not vacuously true."""
        tampered = copy.deepcopy(self.registry)
        _registry_package(tampered, "SP-71")["depends_on"] = ["SP-83"]
        errors = checker.validate_registry(tampered)
        self.assertTrue(any("contains a cycle" in error for error in errors))

    def test_no_owner_local_task_scope_reaches_into_a_sibling_component(self) -> None:
        sibling_directories = set(checker.EXPECTED_COMPONENTS.values())
        checked_any = False
        for package_id in SP70_PACKAGE_IDS:
            entry = _registry_package(self.registry, package_id)
            owner = entry["owner"]
            component = _registry_component(self.registry, owner)
            owner_directory = component["directory"]
            owner_root = WORKSPACE_ROOT / owner_directory
            if not owner_root.is_dir():
                continue
            for contract in entry["contracts"]:
                if contract["kind"] != "task":
                    continue
                task_meta = next(
                    task
                    for task in component["task_specs"]
                    if task["id"] == contract["id"]
                )
                task_path = owner_root / task_meta["path"]
                if not task_path.is_file():
                    continue
                checked_any = True
                text = task_path.read_text(encoding="utf-8")
                include_paths = _scope_include_paths(text)
                with self.subTest(task=contract["id"]):
                    self.assertTrue(include_paths, f"{contract['id']}: scope.include is empty")
                    for path in include_paths:
                        first_segment = path.split("/", 1)[0]
                        self.assertNotIn(
                            first_segment,
                            sibling_directories,
                            f"{contract['id']}: scope path {path!r} appears to reach into "
                            "a sibling component directory",
                        )
                    repo_match = re.search(r"(?m)^repo:\s*(\S+)\s*$", text)
                    self.assertIsNotNone(repo_match, f"{contract['id']}: repo field is missing")
                    self.assertEqual(
                        repo_match.group(1),
                        f"100rd/{owner_directory}",
                        f"{contract['id']}: repo field does not name its own owner repository",
                    )
        self.assertTrue(checked_any, "no owner-local task file was actually checked")

    def test_no_sp70_range_package_grants_live_or_effect_authority(self) -> None:
        for package_id in SP70_PACKAGE_IDS:
            with self.subTest(package_id=package_id):
                entry = _registry_package(self.registry, package_id)
                status = entry["status"].lower()
                if package_id == "SP-85":
                    self.assertIn("blocked", status)
                    continue
                self.assertTrue(
                    "non-live" in status
                    or "no-effect" in status
                    or "gated" in status
                    or status == "ready-for-development",
                    f"{package_id}: status {entry['status']!r} does not read as "
                    "non-live/no-effect/gated",
                )
                self.assertNotIn("-live", status.replace("non-live", ""))
                self.assertNotIn("-effect", status.replace("no-effect", ""))


if __name__ == "__main__":
    unittest.main()
