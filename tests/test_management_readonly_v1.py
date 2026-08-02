"""Tests for scripts/qualify_management_readonly_v1.py (task-sp-89-management-
readonly-profile-qualification). Loaded the same way tests/test_synchronized_
platform.py loads scripts/check_synchronized_platform.py -- importlib against
the script file, no package installation required.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qualify_management_readonly_v1.py"
SPEC = importlib.util.spec_from_file_location("qualify_management_readonly_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
qualify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qualify)

EXPECTED_SP86_DIGEST = (
    "sha256:bdd2368427f7f4f7ccdcc8a1302cb3dcedd06a474f6281f393706030423bc7ee"
)
EXPECTED_SP90_BASELINE_DIGEST = (
    "sha256:e72da6880f5c79ef88039eae0ccf5d818f73f71e57e6958d97beefae030f7307"
)
EXPECTED_SP60_PW0_DIGEST = (
    "sha256:fa312387e5fa4b3980b085e20033fc8d947474c62c15dd9e3836372dea01f038"
)


def _siblings_present() -> bool:
    return (
        qualify.SP86_EVIDENCE_PATH.exists()
        and qualify.BARBAROSSA_RUNBOOK_PATH.exists()
        and qualify.SP90_RUNBOOK_PATH.exists()
        and qualify.PORTAL_PINS_PATH.exists()
    )


SIBLINGS_PRESENT = _siblings_present()
skip_unless_siblings = unittest.skipUnless(
    SIBLINGS_PRESENT,
    "Omniscience/Barbarossa/platform-portal sibling checkouts are not present at ../",
)


class HelperFunctionTests(unittest.TestCase):
    def test_sha256_hex_is_prefixed_and_deterministic(self) -> None:
        first = qualify.sha256_hex(b"same-bytes")
        second = qualify.sha256_hex(b"same-bytes")
        self.assertTrue(first.startswith("sha256:"))
        self.assertEqual(first, second)

    def test_sha256_hex_differs_for_different_bytes(self) -> None:
        self.assertNotEqual(qualify.sha256_hex(b"a"), qualify.sha256_hex(b"b"))

    def test_canonical_json_bytes_is_key_order_independent(self) -> None:
        a = qualify.canonical_json_bytes({"b": 1, "a": 2})
        b = qualify.canonical_json_bytes({"a": 2, "b": 1})
        self.assertEqual(a, b)

    def test_is_placeholder_detects_runbook_template_text(self) -> None:
        self.assertTrue(
            qualify.is_placeholder("sha256:<sha256 of the built cmd/barbarossa binary>")
        )

    def test_is_placeholder_false_for_real_digest(self) -> None:
        self.assertFalse(qualify.is_placeholder(EXPECTED_SP86_DIGEST))

    def test_is_placeholder_false_for_none(self) -> None:
        self.assertFalse(qualify.is_placeholder(None))

    def test_read_text_raises_on_missing_file(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.read_text(ROOT / "does" / "not" / "exist.json")

    def test_extract_json_fence_raises_on_missing_heading(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.extract_json_fence(
                "no heading here", r"## Missing Heading", "test-source"
            )

    def test_extract_json_fence_raises_on_missing_fence(self) -> None:
        text = "## Heading\nno fenced block follows"
        with self.assertRaises(qualify.QualificationError):
            qualify.extract_json_fence(text, r"## Heading", "test-source")

    def test_extract_json_fence_parses_real_block(self) -> None:
        text = '## Heading\n\n```json\n{"a": 1}\n```\n'
        result = qualify.extract_json_fence(text, r"## Heading", "test-source")
        self.assertEqual(result, {"a": 1})

    def test_resolve_string_field_literal(self) -> None:
        self.assertEqual(
            qualify.resolve_string_field('"sha256:abc"', {}, "src"), "sha256:abc"
        )

    def test_resolve_string_field_reference(self) -> None:
        self.assertEqual(
            qualify.resolve_string_field("FOO", {"FOO": "bar"}, "src"), "bar"
        )

    def test_resolve_string_field_none(self) -> None:
        self.assertIsNone(qualify.resolve_string_field("None", {}, "src"))

    def test_resolve_string_field_unresolved_raises(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.resolve_string_field("UNKNOWN_NAME", {}, "src")


@skip_unless_siblings
class Sp86MemberTests(unittest.TestCase):
    def test_release_lock_digest_matches_known_pin(self) -> None:
        sp86 = qualify.build_sp86_member()
        self.assertEqual(sp86["release_lock_digest"], EXPECTED_SP86_DIGEST)

    def test_omnius_status_is_not_deployed(self) -> None:
        sp86 = qualify.build_sp86_member()
        self.assertEqual(sp86["omnius_status"], "not_deployed")

    def test_own_declared_status_is_carried_verbatim(self) -> None:
        sp86 = qualify.build_sp86_member()
        self.assertIn(sp86["own_declared_status"], {"RED", "GREEN"})

    def test_pii_policy_digest_matches_sp60_pin(self) -> None:
        sp86 = qualify.build_sp86_member()
        self.assertEqual(sp86["pii_policy_digest"], EXPECTED_SP60_PW0_DIGEST)


@skip_unless_siblings
class Sp90MemberTests(unittest.TestCase):
    def test_binary_image_sbom_digests_are_null_by_design(self) -> None:
        sp90 = qualify.build_sp90_member()
        self.assertIsNone(sp90["binary_digest"])
        self.assertIsNone(sp90["image_digest"])
        self.assertIsNone(sp90["sbom_digest"])

    def test_published_block_digest_is_reproducible(self) -> None:
        first = qualify.build_sp90_member()["published_block_digest"]
        second = qualify.build_sp90_member()["published_block_digest"]
        self.assertEqual(first, second)


@skip_unless_siblings
class Sp87MemberTests(unittest.TestCase):
    def test_sp86_release_digest_cross_check(self) -> None:
        sp87 = qualify.build_sp87_member()
        self.assertEqual(sp87["sp86_release_digest"], EXPECTED_SP86_DIGEST)

    def test_sp90_baseline_digest_cross_check(self) -> None:
        sp87 = qualify.build_sp87_member()
        self.assertEqual(sp87["sp90_baseline_digest"], EXPECTED_SP90_BASELINE_DIGEST)

    def test_placeholder_fields_are_flagged_not_treated_as_real_digests(self) -> None:
        sp87 = qualify.build_sp87_member()
        self.assertEqual(
            sp87["placeholder_fields"], ["binary_digest", "image_digest", "sbom_digest"]
        )

    def test_own_declared_status_carried_verbatim(self) -> None:
        sp87 = qualify.build_sp87_member()
        self.assertIn(sp87["own_declared_status"], {"RED", "GREEN"})


@skip_unless_siblings
class Sp88MemberTests(unittest.TestCase):
    def test_sp86_pin_copy_matches_independently_derived_sp86_digest(self) -> None:
        sp88 = qualify.build_sp88_member()
        self.assertEqual(
            sp88["sp86_pin_copy"]["release_lock_digest"], EXPECTED_SP86_DIGEST
        )

    def test_sp90_baseline_digest_copy_matches_pin(self) -> None:
        sp88 = qualify.build_sp88_member()
        self.assertEqual(
            sp88["sp90_baseline_digest_copy"], EXPECTED_SP90_BASELINE_DIGEST
        )

    def test_sp87_pin_copy_cross_references_sp86_digest(self) -> None:
        sp88 = qualify.build_sp88_member()
        self.assertEqual(
            sp88["sp87_pin_copy"]["sp86_release_digest"], EXPECTED_SP86_DIGEST
        )


@skip_unless_siblings
class AcceptanceCriteriaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sp86 = qualify.build_sp86_member()
        cls.sp90 = qualify.build_sp90_member()
        cls.sp87 = qualify.build_sp87_member()
        cls.sp88 = qualify.build_sp88_member()

    def test_ac1_passes_on_real_exact_pins(self) -> None:
        ac1 = qualify.run_ac1(self.sp86, self.sp87, self.sp90, self.sp88)
        self.assertEqual(ac1["status"], "PASS", ac1)
        self.assertTrue(all(c["pass"] for c in ac1["cross_checks"]))
        self.assertEqual(ac1["completeness_gaps"], [])

    def test_ac1_fails_closed_on_a_single_digit_digest_drift(self) -> None:
        drifted_sp87 = copy.deepcopy(self.sp87)
        drifted_sp87["sp86_release_digest"] = drifted_sp87["sp86_release_digest"][
            :-1
        ] + ("0" if drifted_sp87["sp86_release_digest"][-1] != "0" else "1")
        ac1 = qualify.run_ac1(self.sp86, drifted_sp87, self.sp90, self.sp88)
        self.assertEqual(ac1["status"], "RED")

    def test_ac1_fails_closed_on_missing_field(self) -> None:
        incomplete_sp86 = copy.deepcopy(self.sp86)
        incomplete_sp86["severance_fixture_digest"] = None
        ac1 = qualify.run_ac1(incomplete_sp86, self.sp87, self.sp90, self.sp88)
        self.assertEqual(ac1["status"], "RED")
        self.assertIn("severance_fixture_digest", ac1["completeness_gaps"])

    def test_ac2_passes_membership_check(self) -> None:
        ac2 = qualify.run_ac2(self.sp86, self.sp87["raw"])
        self.assertEqual(ac2["status"], "PASS", ac2)
        self.assertEqual(
            ac2["evidence"]["registry_selection"]["runtime_components"],
            qualify.EXPECTED_RUNTIME_COMPONENTS,
        )
        self.assertEqual(
            ac2["evidence"]["registry_selection"]["deferred_runtime_components"],
            qualify.EXPECTED_DEFERRED_COMPONENTS,
        )

    def test_ac2_fails_closed_when_omnius_status_drifts(self) -> None:
        drifted_sp86 = copy.deepcopy(self.sp86)
        drifted_sp86["omnius_status"] = "deployed"
        ac2 = qualify.run_ac2(drifted_sp86, self.sp87["raw"])
        self.assertEqual(ac2["status"], "RED")


class Ac4SeveranceFixtureTests(unittest.TestCase):
    def test_real_fixture_matrix_passes(self) -> None:
        ac4 = qualify.run_ac4()
        self.assertEqual(ac4["status"], "PASS", ac4["issues"])
        self.assertGreater(ac4["fixture_count"], 0)

    def test_every_scenario_family_is_covered_or_honestly_not_evidenced(self) -> None:
        ac4 = qualify.run_ac4()
        matrix = json.loads(qualify.SEVERANCE_FIXTURES_PATH.read_text(encoding="utf-8"))
        all_pairs = {
            f"{c}/{s}"
            for c in matrix["components"]
            for s in matrix["scenario_families"]
        }
        seen = set(ac4["covered_pairs"]) | set(ac4["not_evidenced_pairs"])
        self.assertEqual(all_pairs, seen)

    def test_restart_or_rebuild_family_asserts_stale_writer_rejection(self) -> None:
        matrix = json.loads(qualify.SEVERANCE_FIXTURES_PATH.read_text(encoding="utf-8"))
        writer_rejections = [
            f
            for f in matrix["fixtures"]
            if f["scenario_family"] in {"restart", "rebuild"}
            and f["rejects_stale_writer"]
        ]
        self.assertTrue(writer_rejections)

    def test_detects_forbidden_favorable_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_matrix = {
                "schema": "test",
                "components": ["omniscience"],
                "scenario_families": ["stale"],
                "fixtures": [
                    {
                        "id": "bad-001",
                        "component": "omniscience",
                        "scenario_family": "stale",
                        "source_scenario": "x",
                        "source_ref": "x",
                        "description": "x",
                        "expected_decision": "healthy",
                        "must_not_validate_as": ["empty"],
                        "preserves_unrelated_operation": True,
                        "rejects_stale_writer": False,
                        "rejects_stale_writer_applicable": False,
                    }
                ],
                "not_evidenced": [],
            }
            bad_path = Path(tmp) / "bad.json"
            bad_path.write_text(json.dumps(bad_matrix), encoding="utf-8")
            with mock.patch.object(qualify, "SEVERANCE_FIXTURES_PATH", bad_path):
                ac4 = qualify.run_ac4()
            self.assertEqual(ac4["status"], "RED")
            self.assertTrue(
                any("forbidden favorable outcome" in issue for issue in ac4["issues"])
            )

    def test_detects_hidden_unrelated_operation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_matrix = {
                "schema": "test",
                "components": ["omniscience"],
                "scenario_families": ["stale"],
                "fixtures": [
                    {
                        "id": "bad-002",
                        "component": "omniscience",
                        "scenario_family": "stale",
                        "source_scenario": "x",
                        "source_ref": "x",
                        "description": "x",
                        "expected_decision": "fallback_required",
                        "must_not_validate_as": ["healthy"],
                        "preserves_unrelated_operation": False,
                        "rejects_stale_writer": False,
                        "rejects_stale_writer_applicable": False,
                    }
                ],
                "not_evidenced": [],
            }
            bad_path = Path(tmp) / "bad.json"
            bad_path.write_text(json.dumps(bad_matrix), encoding="utf-8")
            with mock.patch.object(qualify, "SEVERANCE_FIXTURES_PATH", bad_path):
                ac4 = qualify.run_ac4()
            self.assertEqual(ac4["status"], "RED")

    def test_detects_uncovered_component_scenario_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_matrix = {
                "schema": "test",
                "components": ["omniscience"],
                "scenario_families": ["stale", "skew"],
                "fixtures": [
                    {
                        "id": "only-stale",
                        "component": "omniscience",
                        "scenario_family": "stale",
                        "source_scenario": "x",
                        "source_ref": "x",
                        "description": "x",
                        "expected_decision": "fallback_required",
                        "must_not_validate_as": ["healthy"],
                        "preserves_unrelated_operation": True,
                        "rejects_stale_writer": False,
                        "rejects_stale_writer_applicable": False,
                    }
                ],
                "not_evidenced": [],
            }
            bad_path = Path(tmp) / "bad.json"
            bad_path.write_text(json.dumps(bad_matrix), encoding="utf-8")
            with mock.patch.object(qualify, "SEVERANCE_FIXTURES_PATH", bad_path):
                ac4 = qualify.run_ac4()
            self.assertEqual(ac4["status"], "RED")
            self.assertTrue(
                any("neither fixture-covered" in issue for issue in ac4["issues"])
            )


class EnvironmentGatedAcTests(unittest.TestCase):
    def test_ac3_is_red_when_no_environment_receipt_exists(self) -> None:
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            ac3 = qualify.run_ac3()
        self.assertEqual(ac3["status"], "RED")
        self.assertIn("environment-receipt.json", ac3["missing_input"])
        self.assertIn("Authority boundary", ac3["why_no_substitute"])

    def test_ac5_is_red_when_no_environment_receipt_exists(self) -> None:
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            ac5 = qualify.run_ac5()
        self.assertEqual(ac5["status"], "RED")

    def test_ac6_is_red_and_names_sp90_sp87_pending_context(self) -> None:
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            ac6 = qualify.run_ac6()
        self.assertEqual(ac6["status"], "RED")
        self.assertIn("additional_context", ac6)

    def test_environment_gated_ac_becomes_decision_required_when_receipt_present(
        self,
    ) -> None:
        fake_receipt = {
            field: "present" for field in qualify.REQUIRED_ENVIRONMENT_RECEIPT_FIELDS
        }
        with mock.patch.object(
            qualify, "find_environment_receipt", return_value=fake_receipt
        ):
            ac3 = qualify.run_ac3()
        self.assertEqual(ac3["status"], "decision-required")

    def test_find_environment_receipt_returns_none_when_file_absent(self) -> None:
        self.assertIsNone(qualify.find_environment_receipt())

    def test_find_environment_receipt_rejects_partial_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            partial = {"environment_identity": "only-one-field"}
            path = Path(tmp) / "environment-receipt.json"
            path.write_text(json.dumps(partial), encoding="utf-8")
            with mock.patch.object(
                qualify, "environment_receipt_path", return_value=path
            ):
                self.assertIsNone(qualify.find_environment_receipt())


@skip_unless_siblings
class ProfileLockIntegrationTests(unittest.TestCase):
    def test_build_profile_lock_end_to_end(self) -> None:
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            lock = qualify.build_profile_lock()
        self.assertEqual(lock["acceptance_criteria"]["AC-SP89-1"]["status"], "PASS")
        self.assertEqual(lock["acceptance_criteria"]["AC-SP89-2"]["status"], "PASS")
        self.assertEqual(lock["acceptance_criteria"]["AC-SP89-3"]["status"], "RED")
        self.assertEqual(lock["acceptance_criteria"]["AC-SP89-4"]["status"], "PASS")
        self.assertEqual(lock["acceptance_criteria"]["AC-SP89-5"]["status"], "RED")
        self.assertEqual(lock["acceptance_criteria"]["AC-SP89-6"]["status"], "RED")
        self.assertEqual(lock["status"], "GREEN")

    def test_profile_lock_digest_is_reproducible_across_two_builds(self) -> None:
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            first = qualify.build_profile_lock()
            second = qualify.build_profile_lock()
        self.assertEqual(first["profile_lock_digest"], second["profile_lock_digest"])

    def test_write_evidence_is_idempotent_for_identical_content(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(qualify, "find_environment_receipt", return_value=None),
            mock.patch.object(qualify, "EVIDENCE_DIR", Path(tmp)),
        ):
            lock = qualify.build_profile_lock()
            first_path = qualify.write_evidence(lock)
            second_path = qualify.write_evidence(lock)
            self.assertEqual(first_path, second_path)
            self.assertTrue(first_path.exists())

    def test_write_evidence_refuses_to_overwrite_diverging_content(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(qualify, "find_environment_receipt", return_value=None),
            mock.patch.object(qualify, "EVIDENCE_DIR", Path(tmp)),
        ):
            lock = qualify.build_profile_lock()
            qualify.write_evidence(lock)
            drifted = copy.deepcopy(lock)
            drifted["profile_lock_digest"] = "sha256:" + "0" * 64
            with self.assertRaises(qualify.QualificationError):
                qualify.write_evidence(drifted)


if __name__ == "__main__":
    unittest.main()
