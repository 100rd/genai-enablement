from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_synchronized_platform.py"
SPEC = importlib.util.spec_from_file_location("check_synchronized_platform", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class SynchronizedPlatformContractTests(unittest.TestCase):
    @staticmethod
    def _package(registry: dict, package_id: str) -> dict:
        return next(
            package
            for package in registry["work_packages"]
            if package["id"] == package_id
        )

    @staticmethod
    def _component(registry: dict, component_id: str) -> dict:
        return next(
            component
            for component in registry["components"]
            if component["id"] == component_id
        )

    def test_real_workspace_is_closed_and_discoverable(self) -> None:
        registry = checker.load_registry()
        self.assertEqual([], checker.validate_registry(registry, ROOT.parent))

    def test_unknown_contract_reference_fails(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        registry["work_packages"][0]["contracts"].append(
            {
                "project": "omniscience",
                "kind": "capability",
                "id": "SPEC-NOT-REAL",
            }
        )
        errors = checker.validate_registry(registry)
        self.assertTrue(any("SPEC-NOT-REAL" in error for error in errors))

    def test_duplicate_component_fails(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        registry["components"].append(copy.deepcopy(registry["components"][0]))
        errors = checker.validate_registry(registry)
        self.assertTrue(any("duplicate component ids" in error for error in errors))

    def test_work_package_dependency_plan_drift_fails(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        self._package(registry, "SP-10")["depends_on"] = ["SP-B0-B7"]
        errors = checker.validate_registry(registry)
        self.assertTrue(any("dependency drift" in error for error in errors))

    def test_work_package_status_plan_drift_fails(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        self._package(registry, "SP-10")["status"] = "semantic-drift"
        errors = checker.validate_registry(registry)
        self.assertTrue(any("status drift" in error for error in errors))

    def test_empty_required_semantics_fail(self) -> None:
        mutations = {
            "adr status": lambda registry: registry["cross_repo_adrs"][0].update(
                status=""
            ),
            "capability status": lambda registry: self._component(
                registry, "genai-enablement"
            )["capability_specs"][0].update(status=""),
            "package status": lambda registry: self._package(
                registry, "SP-10"
            ).update(status=""),
            "package id": lambda registry: self._package(
                registry, "SP-10"
            ).update(id=""),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                registry = copy.deepcopy(checker.load_registry())
                mutate(registry)
                self.assertNotEqual([], checker.validate_registry(registry))

    def test_work_package_cycle_fails(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        self._package(registry, "SP-00")["depends_on"] = ["SP-10"]
        errors = checker.validate_registry(registry)
        self.assertTrue(any("contains a cycle" in error for error in errors))

    def test_readiness_selection_contract_drift_fails(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        package = self._package(registry, "SP-20")
        package["contracts"] = [
            contract
            for contract in package["contracts"]
            if contract.get("id") != "SPEC-IP"
        ]
        errors = checker.validate_registry(registry, ROOT.parent)
        self.assertTrue(
            any("do not match readiness" in error for error in errors)
        )

    def test_component_directory_escape_fails(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        self._component(registry, "omnius")["directory"] = "../omnius"
        errors = checker.validate_registry(registry)
        self.assertTrue(any("directory must be" in error for error in errors))

    def test_registry_path_escape_fails(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        registry["canonical_plan"]["path"] = "../omnius/PLATFORM.md"
        errors = checker.validate_registry(registry)
        self.assertTrue(any("canonical plan path is missing" in error for error in errors))

    def test_unregistered_ready_task_fails_workspace_discovery(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        portal = self._component(registry, "platform-portal")
        removed = portal["task_specs"].pop()
        errors = checker.validate_registry(registry, ROOT.parent)
        self.assertTrue(
            any(
                "task inventory drift" in error and removed["path"] in error
                for error in errors
            )
        )

    def test_task_handoff_requires_evidence_and_per_ac_ground_truth(self) -> None:
        task = """---
id: task-sp-test
status: ready
scope:
  include: [src/**]
acceptanceCriteria:
  - { id: AC-TEST-1, probe: test, expected: pass }
rollback: { kind: revert-pr }
---
"""
        findings = checker._task_handoff_findings(task)
        self.assertTrue(any("evidenceDestination" in item for item in findings))
        self.assertTrue(any("groundTruth" in item for item in findings))

    def test_task_handoff_rejects_writable_oracle_and_registry(self) -> None:
        task = """---
id: task-sp-test
status: ready
evidenceDestination: ci-artifact://task/test/
scope:
  include: [src/**, docs/specs/**, portfolio/synchronized-platform.json]
acceptanceCriteria:
  - { id: AC-TEST-1, probe: test, expected: pass, groundTruth: external receipt }
rollback: { kind: revert-pr }
---
"""
        findings = checker._task_handoff_findings(task)
        self.assertTrue(any("task-SPEC oracle" in item for item in findings))
        self.assertTrue(any("registry lock" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
