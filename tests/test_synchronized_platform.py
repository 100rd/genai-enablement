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
        self.assertEqual(
            "complete-implemented-capability-surface",
            profile["barbarossa_go_scope"],
        )
        self.assertIn("SP-90", profile["required_work_packages"])
        self.assertNotIn("SP-90", profile["release_work_packages"])
        self.assertIn("SP-73", profile["required_work_packages"])
        self.assertNotIn("SP-73", profile["release_work_packages"])
        self.assertEqual([], checker.validate_registry(registry, ROOT.parent))

    def test_barbarossa_ha_profile_pins_transport_state_and_release_chain(self) -> None:
        registry = checker.load_registry()
        profile = next(
            item
            for item in registry["runtime_profiles"]
            if item["id"] == "barbarossa-ha-v1"
        )
        self.assertEqual("nats-jetstream", profile["barbarossa_work_transport"])
        self.assertEqual(3, profile["barbarossa_stream_replicas"])
        self.assertEqual("postgresql-ha", profile["barbarossa_state_store"])
        self.assertEqual("at-least-once", profile["delivery_semantics"])
        self.assertEqual("forbidden", profile["portal_ha_controls"])
        self.assertTrue(
            {"SP-91", "SP-92", "SP-93", "SP-94"}.issubset(
                profile["required_work_packages"]
            )
        )
        self.assertEqual([], checker.validate_registry(registry, ROOT.parent))

    def test_local_profile_pins_real_owner_functional_smoke_without_ha(self) -> None:
        registry = checker.load_registry()
        profile = next(
            item
            for item in registry["runtime_profiles"]
            if item["id"] == "management-readonly-local-v1"
        )
        self.assertEqual("docker-compose", profile["orchestrator"])
        self.assertEqual("2.24.4", profile["minimum_compose_version"])
        self.assertEqual("functional-smoke-only", profile["qualification_class"])
        self.assertEqual("development-single-host", profile["availability_class"])
        self.assertEqual("nats-jetstream", profile["barbarossa_work_transport"])
        self.assertEqual(1, profile["barbarossa_stream_replicas"])
        self.assertEqual("postgresql-single-node", profile["barbarossa_state_store"])
        self.assertFalse(profile["ha_qualified"])
        self.assertEqual("forbidden", profile["selected_owner_mocks"])
        self.assertEqual("loopback-only", profile["host_binding_posture"])
        self.assertEqual(
            {
                "vcpu": 4,
                "memory_bytes": 8_000_000_000,
                "free_disk_bytes": 25_000_000_000,
            },
            profile["minimum_image_mode_host"],
        )
        self.assertEqual(12 * 1024**3, profile["recommended_source_build_memory_bytes"])
        self.assertEqual("sequential", profile["source_build_parallelism_at_minimum"])
        self.assertEqual(
            {"SP-95", "SP-96", "SP-97", "SP-98"},
            set(profile["release_work_packages"]),
        )
        self.assertTrue(
            {"SP-86", "SP-88", "SP-90", "SP-91", "SP-92", "SP-93"}.issubset(
                profile["required_work_packages"]
            )
        )
        self.assertNotIn("SP-89", profile["required_work_packages"])
        self.assertNotIn("SP-94", profile["required_work_packages"])
        self.assertEqual([], checker.validate_registry(registry, ROOT.parent))

    def test_local_handoff_dependency_chain_is_guarded(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        self._package(registry, "SP-97")["depends_on"].remove("SP-96")
        self._package(registry, "SP-98")["depends_on"].remove("SP-97")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("SP-97" in error and "dependency" in error for error in errors))
        self.assertTrue(any("SP-98" in error and "dependency" in error for error in errors))

    def test_local_profile_rejects_ha_or_mock_promotion(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        profile = next(
            item
            for item in registry["runtime_profiles"]
            if item["id"] == "management-readonly-local-v1"
        )
        profile["ha_qualified"] = True
        profile["selected_owner_mocks"] = "allowed"
        errors = checker.validate_registry(registry)
        self.assertTrue(any("ha_qualified must match" in error for error in errors))
        self.assertTrue(any("selected_owner_mocks must match" in error for error in errors))

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

    def test_sp90_requires_complete_go_input_closure(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        sp90 = next(item for item in registry["work_packages"] if item["id"] == "SP-90")
        sp90["depends_on"].remove("SP-76")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("accepted dependency edges" in error for error in errors))

    def test_sp90_requires_action_and_non_reliability_contracts(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        barbarossa = self._component(registry, "barbarossa")
        expected_full_go = {
            item["id"]
            for item in barbarossa["capability_specs"]
            if item["id"] != "SPEC-AUT"
        }
        self.assertEqual(expected_full_go, set(checker.BARBAROSSA_FULL_GO_CAPABILITY_IDS))
        sp90 = next(item for item in registry["work_packages"] if item["id"] == "SP-90")
        sp90["contracts"] = [
            item for item in sp90["contracts"] if item.get("id") != "SPEC-COST-EVAL"
        ]
        errors = checker.validate_registry(registry)
        self.assertTrue(any("accepted contract closure" in error for error in errors))

    def test_ha_dependency_chain_is_guarded(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        sp91 = next(item for item in registry["work_packages"] if item["id"] == "SP-91")
        sp91["depends_on"].remove("SP-87")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("accepted dependency edges" in error for error in errors))

    def test_ha_substrate_to_runtime_dependency_is_guarded(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        sp92 = next(item for item in registry["work_packages"] if item["id"] == "SP-92")
        sp92["depends_on"].remove("SP-91")
        errors = checker.validate_registry(registry)
        self.assertTrue(any("accepted dependency edges" in error for error in errors))

    @unittest.skipUnless(ROOT.parent.joinpath("Barbarossa").is_dir(), "sibling workspace required")
    def test_ha_task_scopes_include_required_integration_seams(self) -> None:
        barbarossa_task = ROOT.parent / "Barbarossa/docs/specs/task-sp-91-distributed-work-substrate.md"
        portal_task = ROOT.parent / "platform-portal/docs/specs/task-sp-93-barbarossa-ha-observability.md"
        barbarossa_text = barbarossa_task.read_text(encoding="utf-8")
        portal_text = portal_task.read_text(encoding="utf-8")
        self.assertIn("    - go.mod\n", barbarossa_text)
        self.assertIn("    - go.sum\n", barbarossa_text)
        self.assertIn("    - deploy/jetstream/**\n", barbarossa_text)
        self.assertIn("    - backend/app/cmc/router.py\n", portal_text)
        self.assertIn("    - backend/app/main.py\n", portal_text)
        self.assertIn(
            "    - frontend/app/(shell)/manage/continuous/page.tsx\n", portal_text
        )

    def test_ha_profile_rejects_single_replica_stream(self) -> None:
        registry = copy.deepcopy(checker.load_registry())
        profile = next(
            item
            for item in registry["runtime_profiles"]
            if item["id"] == "barbarossa-ha-v1"
        )
        profile["barbarossa_stream_replicas"] = 1
        errors = checker.validate_registry(registry)
        self.assertTrue(
            any("barbarossa_stream_replicas must match" in error for error in errors)
        )

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
        profile["non_gating_work_packages"].remove("SP-84")
        profile["required_work_packages"].append("SP-84")
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
