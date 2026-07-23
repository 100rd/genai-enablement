"""AC-SP60-1 probe: pii-contract-schema-and-fixtures.

Ground truth: task-sp-60-pii-policy-contract-v1 (human-approved) and the
SPEC-PII-POLICY requirement/probe contract.

Expected: every positive fixture under contracts/pii/fixtures/v1/positive
validates (and, where applicable, resolves an allowed profile downgrade
correctly); every negative fixture under
contracts/pii/fixtures/v1/negative -- one per required category
(downgrade-violation, replay, raw-receipt, lifecycle-collapse, skew) -- is
rejected by the validator.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "contracts" / "pii"
FIXTURES_ROOT = CONTRACT_ROOT / "fixtures" / "v1"

if str(CONTRACT_ROOT) not in sys.path:
    sys.path.append(str(CONTRACT_ROOT))

from validator import pii_contract_validator as pcv  # noqa: E402  (path set above)

REQUIRED_NEGATIVE_CATEGORIES = {
    "downgrade-violation",
    "replay",
    "raw-receipt",
    "lifecycle-collapse",
    "skew",
}


def _load_cases(kind: str) -> list[tuple[Path, dict]]:
    directory = FIXTURES_ROOT / kind
    cases = []
    for path in sorted(directory.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            cases.append((path, json.load(handle)))
    return cases


class PositiveFixturesValidateTests(unittest.TestCase):
    """Every positive fixture must validate cleanly."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = _load_cases("positive")

    def test_positive_fixtures_exist(self) -> None:
        self.assertGreater(len(self.cases), 0, "expected at least one positive fixture")

    def test_each_positive_fixture_is_admissible(self) -> None:
        for path, case in self.cases:
            with self.subTest(fixture=path.name):
                errors = pcv.evaluate_case(case)
                self.assertEqual(
                    [],
                    errors,
                    f"positive fixture {path.name} was rejected: {errors}",
                )

    def test_profile_downgrade_case_actually_resolves_stricter_profile(self) -> None:
        """Not a tautology: prove the case both parses AND the strictness math holds."""
        matches = [case for _, case in self.cases if case.get("category") == "profile-downgrade-allowed"]
        self.assertTrue(matches, "expected at least one profile-downgrade-allowed positive fixture")
        for case in matches:
            resolved = pcv.resolve_effective_profile(
                case["policyMinimumProfile"], case["consumerRequestedProfile"]
            )
            self.assertEqual(resolved, case["consumerRequestedProfile"])
            self.assertLessEqual(
                pcv.PROFILE_ORDER[case["consumerRequestedProfile"]],
                pcv.PROFILE_ORDER[case["policyMinimumProfile"]],
            )


class NegativeFixturesFailTests(unittest.TestCase):
    """Every negative fixture must be rejected, and every required category covered."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = _load_cases("negative")

    def test_negative_fixtures_exist(self) -> None:
        self.assertGreater(len(self.cases), 0, "expected at least one negative fixture")

    def test_each_negative_fixture_is_rejected(self) -> None:
        for path, case in self.cases:
            with self.subTest(fixture=path.name):
                errors = pcv.evaluate_case(case)
                self.assertNotEqual(
                    [],
                    errors,
                    f"negative fixture {path.name} was WRONGLY accepted (expected rejection)",
                )

    def test_all_five_required_negative_categories_are_present_and_fail(self) -> None:
        categories_seen = {case.get("category") for _, case in self.cases}
        missing = REQUIRED_NEGATIVE_CATEGORIES - categories_seen
        self.assertEqual(
            set(),
            missing,
            f"missing required negative fixture categories: {sorted(missing)}",
        )
        for category in REQUIRED_NEGATIVE_CATEGORIES:
            with self.subTest(category=category):
                category_cases = [case for _, case in self.cases if case.get("category") == category]
                self.assertTrue(category_cases, f"no fixture found for category {category!r}")
                for case in category_cases:
                    self.assertNotEqual([], pcv.evaluate_case(case))


class SchemaStructuralTests(unittest.TestCase):
    """Direct unit coverage of the structural (schema) validator, independent of fixtures."""

    def test_unknown_data_class_is_rejected(self) -> None:
        errors = pcv.validate_against_schema("not_a_real_class", "data-class.schema.json")
        self.assertTrue(errors)

    def test_known_data_class_is_accepted(self) -> None:
        errors = pcv.validate_against_schema("sensitive_personal", "data-class.schema.json")
        self.assertEqual([], errors)

    def test_missing_required_field_is_rejected(self) -> None:
        errors = pcv.validate_against_schema({}, "data-envelope.schema.json")
        self.assertTrue(any("missing required field" in e for e in errors))

    def test_malformed_integrity_digest_is_rejected(self) -> None:
        instance = {"algorithm": "sha256", "digest": "not-hex"}
        errors = pcv.validate_against_schema(instance, "integrity.schema.json")
        self.assertTrue(errors)


class SemanticValidatorUnitTests(unittest.TestCase):
    """Direct unit coverage of each semantic rule, independent of the fixture files,
    so a fixture-authoring mistake cannot mask a broken rule (or vice versa)."""

    def test_check_no_widening_passes_identical_scope(self) -> None:
        envelope = {
            "allowed_fields": ["a"],
            "allowed_sinks": ["s"],
            "policy_revision": "1.0.0",
            "tenant_id": "t1",
            "expires_at": "2026-01-01T00:00:00Z",
        }
        self.assertEqual([], pcv.check_no_widening(envelope, dict(envelope)))

    def test_check_no_widening_flags_extra_field(self) -> None:
        parent = {"allowed_fields": ["a"], "allowed_sinks": ["s"], "policy_revision": "1.0.0", "tenant_id": "t1"}
        child = {"allowed_fields": ["a", "b"], "allowed_sinks": ["s"], "policy_revision": "1.0.0", "tenant_id": "t1"}
        errors = pcv.check_no_widening(parent, child)
        self.assertTrue(any("field widening" in e for e in errors))

    def test_check_permit_replay_flags_duplicate_nonce(self) -> None:
        permit = {"nonce": "n1", "allowed_sinks": ["s"], "tenant_id": "t1", "purpose_id": "p1"}
        usage = [
            {"nonce": "n1", "sink": "s", "tenant_id": "t1", "purpose_id": "p1"},
            {"nonce": "n1", "sink": "s", "tenant_id": "t1", "purpose_id": "p1"},
        ]
        errors = pcv.check_permit_replay(permit, usage)
        self.assertTrue(any("reused" in e for e in errors))

    def test_scan_receipt_for_raw_leakage_flags_forbidden_key(self) -> None:
        receipt = {"raw_value": "should not exist"}
        errors = pcv.scan_receipt_for_raw_leakage(receipt)
        self.assertTrue(any("forbidden field name" in e for e in errors))

    def test_scan_receipt_for_raw_leakage_accepts_clean_receipt(self) -> None:
        receipt = {
            "receipt_id": "r1",
            "input_digest": "sha256:" + "a" * 64,
            "disposition": "complete",
        }
        self.assertEqual([], pcv.scan_receipt_for_raw_leakage(receipt))

    def test_aggregate_lifecycle_all_complete(self) -> None:
        states = [{"disposition": "complete"}, {"disposition": "excluded"}]
        self.assertEqual("complete", pcv.aggregate_lifecycle(states))

    def test_aggregate_lifecycle_reports_most_severe_blocking_state(self) -> None:
        states = [{"disposition": "complete"}, {"disposition": "pending"}, {"disposition": "unavailable"}]
        self.assertEqual("unavailable", pcv.aggregate_lifecycle(states))

    def test_check_policy_skew_passes_when_fully_pinned(self) -> None:
        consumer_pin = {"schema_major": 1, "policy_revision_pin": "1.0.0", "signer_trust_profile": "k1"}
        bundle = {
            "policy_revision": "1.0.0",
            "compatibility": {"schema_major": 1, "min_supported_major": 1, "max_supported_major": 1},
            "issued_at": "2026-01-01T00:00:00Z",
            "expires_at": "2027-01-01T00:00:00Z",
            "signer": {"key_id": "k1"},
        }
        errors = pcv.check_policy_skew(consumer_pin, bundle, reference_now="2026-06-01T00:00:00Z")
        self.assertEqual([], errors)

    def test_resolve_effective_profile_rejects_looser_request(self) -> None:
        with self.assertRaises(ValueError):
            pcv.resolve_effective_profile("PW0", "PW2")


if __name__ == "__main__":
    unittest.main()
