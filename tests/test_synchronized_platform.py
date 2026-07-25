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

    def test_runtime_profile_membership_and_dependency_closure(self) -> None:
        registry = checker.load_registry()
        profile = registry["runtime_profiles"][0]
        self.assertEqual("management-readonly-v1", profile["id"])
        self.assertEqual(
            {"omniscience", "barbarossa", "platform-portal"},
            set(profile["runtime_components"]),
        )
        self.assertEqual({"omnius"}, set(profile["deferred_runtime_components"]))
        self.assertEqual("forbidden", profile["effect_posture"])
        self.assertEqual("go", profile["barbarossa_runtime"])
        self.assertEqual(
            "conformance-oracle-only", profile["barbarossa_typescript_role"]
        )
        self.assertIn("SP-90", profile["required_work_packages"])
        self.assertNotIn("SP-90", profile["release_work_packages"])
        self.assertIn("SP-73", profile["non_gating_work_packages"])
        self.assertEqual([], checker.validate_registry(registry, ROOT.parent))

    def test_runtime_profile_rejects_barbarossa_runtime_drift(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        registry["runtime_profiles"][0]["barbarossa_runtime"] = "typescript"
        errors = checker.validate_registry(registry)
        self.assertTrue(any("barbarossa_runtime must match" in error for error in errors))

    def test_runtime_profile_rejects_typescript_role_drift(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        registry["runtime_profiles"][0]["barbarossa_typescript_role"] = "production"
        errors = checker.validate_registry(registry)
        self.assertTrue(
            any("barbarossa_typescript_role must match" in error for error in errors)
        )

    def test_sp87_requires_go_baseline_dependency(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        sp87 = next(item for item in registry["work_packages"] if item["id"] == "SP-87")
        sp87["depends_on"].remove("SP-90")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("accepted dependency edges" in error for error in errors))

    def test_sp86_requires_go_decision_for_language_neutral_handoff(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        sp86 = next(item for item in registry["work_packages"] if item["id"] == "SP-86")
        sp86["governing_adrs"].remove("ADR-0022")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("accepted governing ADRs" in error for error in errors))

    def test_sp87_requires_domain_registry_contract(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        sp87 = next(item for item in registry["work_packages"] if item["id"] == "SP-87")
        sp87["contracts"] = [
            item for item in sp87["contracts"] if item.get("id") != "SPEC-DOM"
        ]
        errors = checker.validate_registry(registry)
        self.assertTrue(any("accepted contract closure" in error for error in errors))

    def test_runtime_profile_missing_dependency_fails(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        registry["runtime_profiles"][0]["required_work_packages"].remove("SP-60")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("closure is missing dependencies" in error for error in errors))

    def test_runtime_profile_required_deferred_overlap_fails(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        registry["runtime_profiles"][0]["deferred_work_packages"].append("SP-86")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("both required and deferred" in error for error in errors))

    def test_runtime_profile_unclassified_package_fails(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        registry["runtime_profiles"][0]["non_gating_work_packages"].remove("SP-12")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("classification must cover" in error for error in errors))

    def test_runtime_profile_rejects_required_package_from_deferred_owner(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        profile = registry["runtime_profiles"][0]
        profile["deferred_work_packages"].remove("SP-11")
        profile["required_work_packages"].append("SP-11")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("unselected owners" in error for error in errors))

    def test_runtime_profile_rejects_domain_pin_drift(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        registry["runtime_profiles"][0]["selected_domain_packs"] = ["cost-value"]
        errors = checker.validate_registry(registry)
        self.assertTrue(any("selected_domain_packs must match" in error for error in errors))

    def test_runtime_profile_rejects_pii_pin_drift(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        registry["runtime_profiles"][0]["pii_profile"] = "PW2"
        errors = checker.validate_registry(registry)
        self.assertTrue(any("pii_profile must match" in error for error in errors))

    def test_runtime_profile_rejects_release_chain_drift(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        registry["runtime_profiles"][0]["release_work_packages"].remove("SP-87")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("release_work_packages must match" in error for error in errors))

    def test_runtime_profile_rejects_non_gating_scope_expansion(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        profile = registry["runtime_profiles"][0]
        profile["non_gating_work_packages"].remove("SP-73")
        profile["required_work_packages"].append("SP-73")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("required_work_packages must match" in error for error in errors))

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
