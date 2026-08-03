"""Tests for scripts/qualify_barbarossa_ha_v1.py (task-sp-94-barbarossa-ha-
profile-qualification). Loaded the same way tests/test_management_readonly_v1.py
loads scripts/qualify_management_readonly_v1.py -- importlib against the script
file, no package installation required.

The suite covers all eight acceptance criteria, both negative controls (the
single-host local stack is proof of DISQUALIFICATION, never HA evidence; a scan
that reads nothing fails rather than reporting clean), and the never-raise
contract. Every cross-repository assertion either runs against real sibling
checkouts or SKIPS LOUDLY -- it never silently reports success.

Nothing here writes outside a temporary directory: the evidence-writing tests
repoint `evidence_dir` at a temp path, so the committed release directory is
never touched by the suite.
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
SCRIPT = ROOT / "scripts" / "qualify_barbarossa_ha_v1.py"
SPEC = importlib.util.spec_from_file_location("qualify_barbarossa_ha_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
qualify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qualify)

#: Barbarossa's own `projection.SchemaDigest()` for the SP-92 HA projection,
#: re-derived here from the owner's committed field list.
EXPECTED_SP92_SCHEMA_DIGEST = (
    "sha256:2e20878fa2679ed3681ee92ead5686ee3509efd9e7c3a58207f93f04a26589dc"
)
#: `runtime.Sp90BaselineDigest()` as SP-87 declares it and Portal's SP-88 pins
#: copy it.
EXPECTED_SP90_BASELINE_DIGEST = (
    "sha256:e72da6880f5c79ef88039eae0ccf5d818f73f71e57e6958d97beefae030f7307"
)
EXPECTED_LOCAL_NOT_QUALIFIED_AXES = [
    "failure_domain_quorum",
    "queue_replication",
    "store_replication",
    "autoscaling",
    "failover",
]
ALL_AC_IDS = {f"AC-SP94-{n}" for n in range(1, 9)}


def _siblings_present() -> bool:
    return all(
        path.exists()
        for path in (
            qualify.barb(qualify.BARB_SCHEMA_GO),
            qualify.barb(qualify.BARB_HA_VERDICTS),
            qualify.barb(qualify.BARB_LOCAL_TOPOLOGY),
            qualify.portal(qualify.PORTAL_HA_PROFILE),
            qualify.portal(qualify.PORTAL_HA_PINS),
        )
    )


SIBLINGS_PRESENT = _siblings_present()
skip_unless_siblings = unittest.skipUnless(
    SIBLINGS_PRESENT,
    "SKIPPED LOUDLY: the Barbarossa and/or platform-portal sibling checkouts are not "
    "present at ../ . These cross-repository assertions are NOT satisfied by this run.",
)


def _empty_checkout(tmp: str) -> Path:
    root = Path(tmp) / "empty-checkout"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# Helpers and parsers.
# ---------------------------------------------------------------------------


class DigestHelperTests(unittest.TestCase):
    def test_sha256_hex_is_prefixed_and_deterministic(self) -> None:
        first = qualify.sha256_hex(b"same-bytes")
        self.assertTrue(first.startswith("sha256:"))
        self.assertEqual(first, qualify.sha256_hex(b"same-bytes"))

    def test_sha256_hex_differs_for_different_bytes(self) -> None:
        self.assertNotEqual(qualify.sha256_hex(b"a"), qualify.sha256_hex(b"b"))

    def test_canonical_json_bytes_is_key_order_independent(self) -> None:
        self.assertEqual(
            qualify.canonical_json_bytes({"b": 1, "a": 2}),
            qualify.canonical_json_bytes({"a": 2, "b": 1}),
        )

    def test_is_placeholder_detects_runbook_template_text(self) -> None:
        self.assertTrue(qualify.is_placeholder("sha256:<sha256 of the built binary>"))

    def test_is_placeholder_false_for_real_digest_and_none(self) -> None:
        self.assertFalse(qualify.is_placeholder(EXPECTED_SP92_SCHEMA_DIGEST))
        self.assertFalse(qualify.is_placeholder(None))

    def test_read_bytes_raises_on_missing_file(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.read_bytes(ROOT / "does" / "not" / "exist.json")

    def test_read_json_raises_on_unparseable_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(qualify.QualificationError):
                qualify.read_json(path)

    def test_file_set_digest_refuses_an_empty_set(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.file_set_digest(ROOT, ())

    def test_file_set_digest_raises_rather_than_skipping_a_missing_member(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "present.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(qualify.QualificationError):
                qualify.file_set_digest(root, ("present.txt", "absent.txt"))

    def test_git_tracked_is_false_for_a_path_outside_the_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(qualify.git_tracked(ROOT, Path(tmp) / "x.json"))


class SchemaDigestDerivationTests(unittest.TestCase):
    def test_reproduces_the_owner_digest_for_the_committed_field_list(self) -> None:
        fields = [
            "tenant",
            "queue_depth",
            "oldest_work_age_millis",
            "inflight",
            "retry_count",
            "dlq_count",
            "worker_eligible",
            "replica_healthy",
            "replica_desired",
            "dependency_healthy",
            "capacity_max_inflight",
            "rollout_revision",
            "error_budget_remaining",
            "fencing_events",
            "integrity",
        ]
        self.assertEqual(
            qualify.derive_projection_schema_digest(fields), EXPECTED_SP92_SCHEMA_DIGEST
        )

    def test_is_order_sensitive(self) -> None:
        self.assertNotEqual(
            qualify.derive_projection_schema_digest(["a", "b"]),
            qualify.derive_projection_schema_digest(["b", "a"]),
        )

    def test_refuses_an_empty_field_list(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.derive_projection_schema_digest([])

    def test_fails_closed_outside_the_owner_field_vocabulary(self) -> None:
        # Go HTML-escapes '<' and Python does not, so a digest over such a name
        # could silently disagree with the owner's. It must never be emitted.
        with self.assertRaises(qualify.QualificationError):
            qualify.derive_projection_schema_digest(["queue<depth>"])

    def test_snake_to_camel(self) -> None:
        self.assertEqual(
            qualify.snake_to_camel("oldest_work_age_millis"), "oldestWorkAgeMillis"
        )
        self.assertEqual(qualify.snake_to_camel("tenant"), "tenant")


class GoParserTests(unittest.TestCase):
    HEALTH = 'return Contract{LivePath: "/livez", ReadyPath: "/readyz", StartupPath: "/startupz"}'

    def test_parses_a_string_slice(self) -> None:
        text = 'var fields = []string{\n\t"a", "b",\n\t"c",\n}\n'
        self.assertEqual(
            qualify.parse_go_string_slice(text, "fields", "src"), ["a", "b", "c"]
        )

    def test_raises_when_the_slice_is_absent(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.parse_go_string_slice("package x", "fields", "src")

    def test_raises_when_the_slice_is_empty(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.parse_go_string_slice("var fields = []string{}", "fields", "src")

    def test_parses_struct_json_tags_with_types(self) -> None:
        text = (
            "type P struct {\n"
            '\tTenant shared.SubjectScope `json:"tenant"`\n'
            '\tDepth  int                 `json:"queue_depth"`\n'
            "}\n"
        )
        self.assertEqual(
            qualify.parse_go_struct_json_fields(text, "P", "src"),
            [("tenant", "shared.SubjectScope"), ("queue_depth", "int")],
        )

    def test_raises_when_the_struct_is_absent(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.parse_go_struct_json_fields("package x", "P", "src")

    def test_resolves_mux_routes_including_contract_constants(self) -> None:
        server = 'mux.HandleFunc(s.contract.LivePath, h)\nmux.HandleFunc("/v1/availability", h)\n'
        self.assertEqual(
            qualify.parse_go_mux_routes(server, self.HEALTH, "src"),
            ["/livez", "/v1/availability"],
        )

    def test_raises_on_an_unresolved_route_expression(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.parse_go_mux_routes(
                "mux.HandleFunc(someUnknownVar, h)", self.HEALTH, "src"
            )

    def test_raises_when_no_route_is_registered(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.parse_go_mux_routes("package api", self.HEALTH, "src")


class PythonParserTests(unittest.TestCase):
    def test_reads_plain_and_annotated_literal_constants(self) -> None:
        text = 'A = "x"\nB: tuple[str, ...] = ("p", "q")\nC: str | None = None\n'
        self.assertEqual(
            qualify.parse_python_literals(text, ("A", "B", "C"), "src"),
            {"A": "x", "B": ("p", "q"), "C": None},
        )

    def test_raises_when_a_constant_is_missing(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.parse_python_literals('A = "x"\n', ("A", "MISSING"), "src")

    def test_raises_when_a_constant_is_not_a_literal(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.parse_python_literals("A = compute()\n", ("A",), "src")

    def test_reads_a_dict_value_without_executing_the_module(self) -> None:
        text = 'def f():\n    return {"refs": [], "other": 1}\n'
        self.assertEqual(qualify.parse_python_dict_value(text, "refs", "src"), [])

    def test_raises_when_the_dict_key_is_absent(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.parse_python_dict_value("x = {}", "refs", "src")


class MarkdownParserTests(unittest.TestCase):
    def test_extracts_a_fenced_json_block(self) -> None:
        self.assertEqual(
            qualify.extract_json_fence(
                '## H\n\n```json\n{"a": 1}\n```\n', r"## H", "src"
            ),
            {"a": 1},
        )

    def test_raises_on_missing_heading_or_fence(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.extract_json_fence("nothing", r"## H", "src")
        with self.assertRaises(qualify.QualificationError):
            qualify.extract_json_fence("## H\nno fence", r"## H", "src")

    def test_parses_a_verdict_table_and_normalizes_live_red(self) -> None:
        text = (
            "| AC | Requirement | Verdict | Why |\n"
            "| AC-SP91-1 | a | **RED (live)** | x |\n"
            "| AC-SP91-3 | b | **GREEN** | y |\n"
        )
        self.assertEqual(
            qualify.parse_verdict_table(text, "AC-SP91", "src"),
            {"AC-SP91-1": "RED", "AC-SP91-3": "GREEN"},
        )

    def test_raises_when_no_verdict_row_matches(self) -> None:
        with self.assertRaises(qualify.QualificationError):
            qualify.parse_verdict_table("no table here", "AC-SP91", "src")


class GuardedTests(unittest.TestCase):
    def test_converts_a_qualification_error_into_a_typed_member_error(self) -> None:
        def boom() -> dict[str, object]:
            raise qualify.QualificationError("missing thing")

        self.assertEqual(qualify.guarded("m", boom)["errors"], ["missing thing"])

    def test_converts_an_unexpected_error_into_a_typed_member_error(self) -> None:
        def boom() -> dict[str, object]:
            raise KeyError("nope")

        self.assertIn("KeyError", qualify.guarded("m", boom)["errors"][0])


# ---------------------------------------------------------------------------
# Loud-failure scans (a scan that reads nothing must never report clean).
# ---------------------------------------------------------------------------


class LoudScanTests(unittest.TestCase):
    def test_committed_receipt_scan_raises_when_it_reads_no_files(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(qualify, "BARBAROSSA_ROOT", _empty_checkout(tmp)),
            self.assertRaises(qualify.QualificationError) as ctx,
        ):
            qualify.scan_for_committed_ha_receipt()
        self.assertIn("examined 0 json files", str(ctx.exception))

    def test_committed_receipt_scan_raises_when_the_checkout_is_absent(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(qualify, "BARBAROSSA_ROOT", Path(tmp) / "gone"),
            self.assertRaises(qualify.QualificationError),
        ):
            qualify.scan_for_committed_ha_receipt()

    def test_committed_receipt_scan_finds_a_receipt_when_one_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _empty_checkout(tmp)
            (root / "receipt.json").write_text(
                json.dumps(
                    {"profile_id": "ha-runtime-v1", "sp91_substrate_digest": "sha256:x"}
                ),
                encoding="utf-8",
            )
            with mock.patch.object(qualify, "BARBAROSSA_ROOT", root):
                result = qualify.scan_for_committed_ha_receipt()
        self.assertEqual(result["matches"], ["receipt.json"])
        self.assertGreater(result["json_files_scanned"], 0)

    def test_no_control_scan_raises_when_the_package_is_absent(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(qualify, "PORTAL_ROOT", _empty_checkout(tmp)),
            self.assertRaises(qualify.QualificationError),
        ):
            qualify.scan_portal_no_control()

    def test_no_control_scan_raises_rather_than_calling_an_empty_package_clean(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _empty_checkout(tmp)
            (root / qualify.PORTAL_HA_PKG).mkdir(parents=True)
            with (
                mock.patch.object(qualify, "PORTAL_ROOT", root),
                self.assertRaises(qualify.QualificationError) as ctx,
            ):
                qualify.scan_portal_no_control()
        self.assertIn("refusing to report clean", str(ctx.exception))

    def test_no_control_scan_detects_a_forbidden_client_and_a_mutating_call(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _empty_checkout(tmp)
            pkg = root / qualify.PORTAL_HA_PKG
            pkg.mkdir(parents=True)
            (pkg / "bad.py").write_text(
                "import nats\n\n\ndef f(c):\n    c.post('/x')\n", encoding="utf-8"
            )
            with mock.patch.object(qualify, "PORTAL_ROOT", root):
                scan = qualify.scan_portal_no_control()
        self.assertEqual(scan["forbidden_imports"], ["nats"])
        self.assertEqual(len(scan["mutating_calls"]), 1)


# ---------------------------------------------------------------------------
# Members (cross-repository; skipped loudly without siblings).
# ---------------------------------------------------------------------------


class Sp89MemberTests(unittest.TestCase):
    def test_pinned_receipt_is_committed_and_self_consistent(self) -> None:
        sp89 = qualify.build_sp89_member()
        self.assertEqual(sp89["errors"], [])
        self.assertTrue(
            sp89["committed"], "the pinned SP-89 receipt must be git-tracked"
        )
        self.assertEqual(
            sp89["recorded_profile_lock_digest"],
            sp89["independently_rederived_profile_lock_digest"],
        )

    def test_carries_sp89s_own_red_criteria_verbatim(self) -> None:
        sp89 = qualify.build_sp89_member()
        for ac_id in ("AC-SP89-3", "AC-SP89-5", "AC-SP89-6"):
            self.assertEqual(sp89["own_declared_ac_status"][ac_id], "RED")

    def test_reports_uncommitted_sibling_evidence_separately_from_the_pin(self) -> None:
        sp89 = qualify.build_sp89_member()
        self.assertIsInstance(sp89["uncommitted_sibling_evidence_files"], list)
        self.assertNotIn(
            qualify.SP89_EVIDENCE_FILENAME, sp89["uncommitted_sibling_evidence_files"]
        )


@skip_unless_siblings
class Sp92MemberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sp92 = qualify.build_sp92_member()

    def test_builds_without_error(self) -> None:
        self.assertEqual(self.sp92["errors"], [])

    def test_schema_digest_is_independently_rederived_to_the_owner_value(self) -> None:
        self.assertEqual(
            self.sp92["projection_schema_digest_independently_rederived"],
            EXPECTED_SP92_SCHEMA_DIGEST,
        )

    def test_owner_struct_tags_and_schema_field_list_stay_in_lockstep(self) -> None:
        self.assertEqual(
            self.sp92["projection_schema_fields"],
            self.sp92["projection_struct_json_fields"],
        )

    def test_release_receipt_is_absent_and_never_fabricated(self) -> None:
        self.assertIsNone(self.sp92["release_receipt_digest"])
        self.assertEqual(self.sp92["committed_receipt_scan"]["matches"], [])
        self.assertGreater(self.sp92["committed_receipt_scan"]["json_files_scanned"], 0)

    def test_owner_declared_conformance_is_carried_verbatim_and_is_red(self) -> None:
        self.assertEqual(self.sp92["own_declared_conformance_overall_status"], "RED")
        verdicts = self.sp92["own_declared_conformance_verdicts"]
        for ac_id in ("AC-SP92-1", "AC-SP92-2", "AC-SP92-3", "AC-SP92-4", "AC-SP92-5"):
            self.assertEqual(verdicts[ac_id], "RED")
        self.assertEqual(verdicts["AC-SP92-6"], "GREEN")
        self.assertEqual(verdicts["AC-SP92-7"], "GREEN")

    def test_owner_publishes_only_read_only_routes(self) -> None:
        self.assertEqual(self.sp92["published_routes"], qualify.EXPECTED_OWNER_ROUTES)

    def test_externally_measured_digests_are_named_as_absent(self) -> None:
        self.assertIn("image_digest", self.sp92["externally_measured_digests_absent"])
        self.assertIn("sbom_digest", self.sp92["externally_measured_digests_absent"])


@skip_unless_siblings
class Sp93MemberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sp93 = qualify.build_sp93_member()

    def test_builds_without_error(self) -> None:
        self.assertEqual(self.sp93["errors"], [])

    def test_portal_pins_the_absent_sp92_receipt_as_none(self) -> None:
        self.assertIsNone(self.sp93["pins"]["SP92_RELEASE_RECEIPT_DIGEST"])

    def test_portal_pins_the_owner_schema_digest_exactly(self) -> None:
        self.assertEqual(
            self.sp93["pins"]["SP92_HA_PROJECTION_SCHEMA_DIGEST"],
            EXPECTED_SP92_SCHEMA_DIGEST,
        )

    def test_portal_sp88_pins_carry_the_owner_sp90_baseline_digest(self) -> None:
        self.assertEqual(
            self.sp93["sp88_sp90_baseline_digest_copy"], EXPECTED_SP90_BASELINE_DIGEST
        )

    def test_portal_declares_its_own_red_reasons_including_the_absent_receipt(
        self,
    ) -> None:
        reasons = self.sp93["own_declared_release_lock_red_reasons"]
        self.assertIn("sp92_release_receipt_absent", reasons)
        self.assertIn("sp92_conformance_overall_status_red", reasons)
        self.assertIn("accessibility_evidence_absent", reasons)

    def test_no_captured_section_state_is_fresh(self) -> None:
        self.assertNotIn(
            "fresh", {c["state"] for c in self.sp93["section_case_states"]}
        )


@skip_unless_siblings
class Sp90AndSp91MemberTests(unittest.TestCase):
    def test_sp90_binary_image_sbom_digests_are_null_by_design(self) -> None:
        sp90 = qualify.build_sp90_member()
        self.assertEqual(sp90["errors"], [])
        self.assertIsNone(sp90["binary_digest"])
        self.assertIsNone(sp90["image_digest"])
        self.assertIsNone(sp90["sbom_digest"])

    def test_sp90_block_digest_is_reproducible(self) -> None:
        self.assertEqual(
            qualify.build_sp90_member()["published_block_digest"],
            qualify.build_sp90_member()["published_block_digest"],
        )

    def test_sp91_has_no_committed_receipt_and_declares_ac7_red(self) -> None:
        sp91 = qualify.build_sp91_member()
        self.assertEqual(sp91["errors"], [])
        self.assertIsNone(sp91["release_receipt_digest"])
        self.assertEqual(sp91["own_declared_ac_verdicts"]["AC-SP91-7"], "RED")
        self.assertIn("AC-SP91-7", sp91["own_declared_red_acs"])


# ---------------------------------------------------------------------------
# Negative control and environment-gating matrix.
# ---------------------------------------------------------------------------


@skip_unless_siblings
class NegativeControlTests(unittest.TestCase):
    def test_local_stack_declares_itself_non_ha_and_the_fixture_agrees(self) -> None:
        control = qualify.build_negative_control()
        self.assertEqual(control["errors"], [])
        self.assertTrue(control["holds"], control["issues"])
        self.assertIs(control["owner_declared_topology"]["ha_qualified"], False)
        self.assertEqual(
            control["owner_not_qualified_axes"], EXPECTED_LOCAL_NOT_QUALIFIED_AXES
        )
        self.assertEqual(
            control["owner_declared_topology"]["activation_authority"], "none"
        )

    def test_fails_closed_when_the_fixture_claims_something_the_owner_does_not(
        self,
    ) -> None:
        matrix = copy.deepcopy(qualify.load_gating_matrix())
        matrix["negative_control"]["expected_availability_class"] = (
            "production-multi-zone"
        )
        with mock.patch.object(qualify, "load_gating_matrix", return_value=matrix):
            control = qualify.build_negative_control()
        self.assertFalse(control["holds"])
        self.assertTrue(
            any("availability_class" in issue for issue in control["issues"])
        )

    def test_fails_closed_if_the_local_stack_ever_claims_to_be_ha_qualified(
        self,
    ) -> None:
        # The teeth of the negative control: if the single-host stack started
        # declaring itself HA, it must be rejected as a control rather than
        # quietly accepted as HA evidence.
        with tempfile.TemporaryDirectory() as tmp:
            root = _empty_checkout(tmp)
            topology_path = root / qualify.BARB_LOCAL_TOPOLOGY
            topology_path.parent.mkdir(parents=True)
            topology_path.write_text(
                json.dumps(
                    {
                        "availability_class": "development-single-host",
                        "queue_replicas": 1,
                        "store_replicas": 1,
                        "ha_qualified": True,
                        "activation_authority": "none",
                        "not_qualified_axes": EXPECTED_LOCAL_NOT_QUALIFIED_AXES,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(qualify, "BARBAROSSA_ROOT", root):
                control = qualify.build_negative_control()
        self.assertFalse(control["holds"])
        self.assertTrue(
            any(
                "must never be read as HA evidence" in issue
                for issue in control["issues"]
            ),
            control["issues"],
        )


@skip_unless_siblings
class GatingMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.control = qualify.build_negative_control()

    def test_real_fixture_is_valid_and_covers_every_disqualifying_axis(self) -> None:
        gating = qualify.validate_gating_matrix(self.control)
        self.assertTrue(gating["valid"], gating["issues"])
        self.assertEqual(
            sorted(gating["axes_covered"]), sorted(EXPECTED_LOCAL_NOT_QUALIFIED_AXES)
        )
        self.assertEqual(gating["criteria_count"], len(qualify.ENVIRONMENT_GATED_ACS))

    def test_rejects_an_empty_matrix(self) -> None:
        with mock.patch.object(
            qualify,
            "load_gating_matrix",
            return_value={"environment_gated_criteria": []},
        ):
            gating = qualify.validate_gating_matrix(self.control)
        self.assertFalse(gating["valid"])
        self.assertIn("environment_gated_criteria is empty", gating["issues"])

    def test_rejects_a_criterion_with_no_required_inputs(self) -> None:
        matrix = copy.deepcopy(qualify.load_gating_matrix())
        matrix["environment_gated_criteria"][0]["required_inputs"] = []
        with mock.patch.object(qualify, "load_gating_matrix", return_value=matrix):
            gating = qualify.validate_gating_matrix(self.control)
        self.assertFalse(gating["valid"])
        self.assertTrue(any("required_inputs is empty" in i for i in gating["issues"]))

    def test_rejects_a_criterion_with_no_forbidden_substitutes(self) -> None:
        matrix = copy.deepcopy(qualify.load_gating_matrix())
        matrix["environment_gated_criteria"][0]["forbidden_substitutes"] = []
        with mock.patch.object(qualify, "load_gating_matrix", return_value=matrix):
            gating = qualify.validate_gating_matrix(self.control)
        self.assertFalse(gating["valid"])

    def test_rejects_an_axis_the_owner_does_not_actually_declare(self) -> None:
        matrix = copy.deepcopy(qualify.load_gating_matrix())
        matrix["environment_gated_criteria"][0]["disqualifying_local_axes"] = [
            "invented_axis"
        ]
        with mock.patch.object(qualify, "load_gating_matrix", return_value=matrix):
            gating = qualify.validate_gating_matrix(self.control)
        self.assertFalse(gating["valid"])
        self.assertTrue(any("invented_axis" in i for i in gating["issues"]))

    def test_rejects_a_matrix_that_leaves_a_disqualifying_axis_unmapped(self) -> None:
        matrix = copy.deepcopy(qualify.load_gating_matrix())
        for entry in matrix["environment_gated_criteria"]:
            entry["disqualifying_local_axes"] = []
        with mock.patch.object(qualify, "load_gating_matrix", return_value=matrix):
            gating = qualify.validate_gating_matrix(self.control)
        self.assertFalse(gating["valid"])
        self.assertTrue(any("not mapped to any" in i for i in gating["issues"]))

    def test_refuses_to_validate_against_an_unread_negative_control(self) -> None:
        # A vacuous pass would be the worst failure mode here.
        gating = qualify.validate_gating_matrix(
            {"member": "negative_control", "errors": ["gone"]}
        )
        self.assertFalse(gating["valid"])
        self.assertTrue(any("unread negative control" in i for i in gating["issues"]))

    def test_rejects_a_matrix_that_declares_a_different_criterion_set(self) -> None:
        matrix = copy.deepcopy(qualify.load_gating_matrix())
        matrix["environment_gated_criteria"].pop()
        with mock.patch.object(qualify, "load_gating_matrix", return_value=matrix):
            gating = qualify.validate_gating_matrix(self.control)
        self.assertFalse(gating["valid"])


# ---------------------------------------------------------------------------
# Acceptance criteria.
# ---------------------------------------------------------------------------


@skip_unless_siblings
class Ac1JoinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sp89 = qualify.build_sp89_member()
        cls.sp90 = qualify.build_sp90_member()
        cls.sp91 = qualify.build_sp91_member()
        cls.sp92 = qualify.build_sp92_member()
        cls.sp93 = qualify.build_sp93_member()
        cls.reg = qualify.registry_profile()

    def _run(self, **overrides: object) -> dict:
        members: dict[str, object] = {
            "sp89": self.sp89,
            "sp90": self.sp90,
            "sp91": self.sp91,
            "sp92": self.sp92,
            "sp93": self.sp93,
        }
        members.update(overrides)
        return qualify.run_ac1(
            members["sp89"],
            members["sp90"],
            members["sp91"],
            members["sp92"],
            members["sp93"],
            self.reg,
        )

    def test_every_buildable_cross_check_passes(self) -> None:
        ac1 = self._run()
        self.assertEqual(
            ac1["buildable_result"], "GREEN", ac1["failed_buildable_checks"]
        )
        self.assertGreater(len(ac1["buildable_checks"]), 10)

    def test_status_is_red_because_the_sp92_receipt_is_absent(self) -> None:
        ac1 = self._run()
        self.assertEqual(ac1["status"], "RED")
        self.assertEqual(ac1["red_cause"], "missing_upstream_owner_receipt")
        inputs = [entry["input"] for entry in ac1["missing_ground_truth"]]
        self.assertTrue(
            any("SP-92 BarbarossaHighAvailabilityRelease receipt" in i for i in inputs),
            inputs,
        )
        self.assertTrue(
            any("SP-91 BarbarossaDistributedWorkRelease" in i for i in inputs), inputs
        )

    def test_fails_closed_on_a_single_digit_schema_digest_drift(self) -> None:
        drifted = copy.deepcopy(self.sp93)
        pinned = drifted["pins"]["SP92_HA_PROJECTION_SCHEMA_DIGEST"]
        drifted["pins"]["SP92_HA_PROJECTION_SCHEMA_DIGEST"] = pinned[:-1] + (
            "0" if pinned[-1] != "0" else "1"
        )
        ac1 = self._run(sp93=drifted)
        self.assertEqual(ac1["buildable_result"], "RED")
        self.assertEqual(ac1["red_cause"], "cross_check_failed")

    def test_fails_closed_when_the_sp89_receipt_is_not_committed(self) -> None:
        drifted = copy.deepcopy(self.sp89)
        drifted["committed"] = False
        self.assertEqual(self._run(sp89=drifted)["buildable_result"], "RED")

    def test_fails_closed_when_a_placeholder_digest_appears(self) -> None:
        drifted = copy.deepcopy(self.sp90)
        drifted["image_digest"] = "sha256:<sha256 of the built image>"
        ac1 = self._run(sp90=drifted)
        self.assertEqual(ac1["buildable_result"], "RED")
        self.assertIn(
            "no placeholder template text is carried as an sp90 binary/image/sbom digest",
            ac1["failed_buildable_checks"],
        )

    def test_fails_closed_when_a_member_could_not_be_read(self) -> None:
        ac1 = self._run(
            sp92={"member": "sp92_barbarossa_ha_release", "errors": ["gone"]}
        )
        self.assertEqual(ac1["status"], "RED")
        self.assertEqual(ac1["buildable_result"], "RED")


@skip_unless_siblings
class Ac6PortalTruthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sp92 = qualify.build_sp92_member()
        cls.sp93 = qualify.build_sp93_member()

    def test_every_structural_check_passes_but_status_stays_red(self) -> None:
        ac6 = qualify.run_ac6(self.sp92, self.sp93)
        self.assertEqual(
            ac6["buildable_result"], "GREEN", ac6["failed_buildable_checks"]
        )
        self.assertEqual(ac6["status"], "RED")
        self.assertTrue(ac6["missing_ground_truth"])

    def test_fresh_is_structurally_unreachable_for_this_owner(self) -> None:
        names = {
            c["name"]: c
            for c in qualify.run_ac6(self.sp92, self.sp93)["buildable_checks"]
        }
        self.assertTrue(
            names["owner projection carries no freshness marker field"]["pass"]
        )
        self.assertTrue(names["no captured portal section response is 'fresh'"]["pass"])

    def test_fails_closed_when_a_fresh_capture_appears(self) -> None:
        drifted = copy.deepcopy(self.sp93)
        drifted["section_case_states"].append(
            {
                "case": "invented",
                "state": "fresh",
                "reason": None,
                "availability_rendered": True,
                "sp92_pin_status": "compatible",
            }
        )
        self.assertEqual(qualify.run_ac6(self.sp92, drifted)["buildable_result"], "RED")

    def test_fails_closed_on_an_owner_wire_type_drift(self) -> None:
        drifted = copy.deepcopy(self.sp93)
        drifted["section_field_types"]["availability"]["workerEligible"] = [
            "boolean",
            "null",
        ]
        ac6 = qualify.run_ac6(self.sp92, drifted)
        self.assertEqual(ac6["buildable_result"], "RED")
        self.assertIn(
            "every owner payload field keeps its owner wire type in portal",
            ac6["failed_buildable_checks"],
        )

    def test_fails_closed_when_portal_misreports_the_owner_qualification(self) -> None:
        drifted = copy.deepcopy(self.sp93)
        drifted["declared_profile"]["owner_qualification"]["ha_qualified"] = True
        self.assertEqual(qualify.run_ac6(self.sp92, drifted)["buildable_result"], "RED")

    def test_fails_closed_when_portal_renders_a_payload_in_an_unavailable_state(
        self,
    ) -> None:
        drifted = copy.deepcopy(self.sp93)
        for case in drifted["section_case_states"]:
            if case["state"] == "unavailable":
                case["availability_rendered"] = True
                break
        self.assertEqual(qualify.run_ac6(self.sp92, drifted)["buildable_result"], "RED")

    def test_fails_closed_when_portal_derives_headroom(self) -> None:
        drifted = copy.deepcopy(self.sp93)
        drifted["section_field_types"]["availability"]["headroom"] = ["integer", "null"]
        self.assertEqual(qualify.run_ac6(self.sp92, drifted)["buildable_result"], "RED")

    def test_names_the_missing_live_and_accessibility_evidence(self) -> None:
        inputs = " ".join(
            entry["input"]
            for entry in qualify.run_ac6(self.sp92, self.sp93)["missing_ground_truth"]
        )
        self.assertIn("browser", inputs)
        self.assertIn("accessibility", inputs)


@skip_unless_siblings
class Ac7IsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sp92 = qualify.build_sp92_member()
        cls.sp93 = qualify.build_sp93_member()
        cls.reg = qualify.registry_profile()

    def test_membership_and_no_effect_checks_pass_but_status_stays_red(self) -> None:
        ac7 = qualify.run_ac7(self.sp92, self.sp93, self.reg)
        self.assertEqual(
            ac7["buildable_result"], "GREEN", ac7["failed_buildable_checks"]
        )
        self.assertEqual(ac7["status"], "RED")
        self.assertGreater(ac7["no_effect_scan"]["files_scanned"], 0)

    def test_fails_closed_when_the_registry_widens_the_effect_posture(self) -> None:
        drifted = copy.deepcopy(self.reg)
        drifted["effect_posture"] = "allowed"
        self.assertEqual(
            qualify.run_ac7(self.sp92, self.sp93, drifted)["buildable_result"], "RED"
        )

    def test_fails_closed_when_omnius_stops_being_deferred(self) -> None:
        drifted = copy.deepcopy(self.reg)
        drifted["deferred_runtime_components"] = []
        self.assertEqual(
            qualify.run_ac7(self.sp92, self.sp93, drifted)["buildable_result"], "RED"
        )

    def test_fails_closed_when_the_owner_publishes_a_redrive_route(self) -> None:
        drifted = copy.deepcopy(self.sp92)
        drifted["published_routes"] = [*drifted["published_routes"], "/v1/redrive"]
        self.assertEqual(
            qualify.run_ac7(drifted, self.sp93, self.reg)["buildable_result"], "RED"
        )

    def test_fails_closed_when_portal_stops_forbidding_a_control_capability(
        self,
    ) -> None:
        drifted = copy.deepcopy(self.sp93)
        drifted["declared_profile"]["no_control"]["forbidden_capabilities"] = ["pause"]
        self.assertEqual(
            qualify.run_ac7(self.sp92, drifted, self.reg)["buildable_result"], "RED"
        )

    def test_fails_closed_when_the_registry_entry_is_absent(self) -> None:
        self.assertEqual(
            qualify.run_ac7(self.sp92, self.sp93, None)["buildable_result"], "RED"
        )


@skip_unless_siblings
class EnvironmentGatedAcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.control = qualify.build_negative_control()
        cls.gating = qualify.validate_gating_matrix(cls.control)

    def test_every_environment_gated_criterion_is_red_with_named_inputs(self) -> None:
        for ac_id in qualify.ENVIRONMENT_GATED_ACS:
            with self.subTest(ac_id=ac_id):
                with mock.patch.object(
                    qualify, "find_environment_receipt", return_value=None
                ):
                    ac = qualify.run_environment_gated_ac(
                        ac_id, self.gating, self.control
                    )
                self.assertEqual(ac["status"], "RED")
                self.assertEqual(
                    ac["buildable_result"], "GREEN", ac["failed_buildable_checks"]
                )
                self.assertTrue(ac["missing_ground_truth"])
                self.assertTrue(ac["forbidden_substitutes"])
                self.assertIn(
                    "environment-receipt.json", ac["missing_environment_receipt"]
                )

    def test_the_local_stack_is_named_as_a_negative_control_never_as_evidence(
        self,
    ) -> None:
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            ac4 = qualify.run_environment_gated_ac(
                "AC-SP94-4", self.gating, self.control
            )
        self.assertIn("NEGATIVE control", ac4["negative_control"])
        self.assertIn("management-readonly-local-v1", ac4["negative_control"])
        self.assertIn("failure_domain_quorum", ac4["negative_control"])

    def test_the_local_stack_is_a_forbidden_substitute_for_the_load_criteria(
        self,
    ) -> None:
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            ac5 = qualify.run_environment_gated_ac(
                "AC-SP94-5", self.gating, self.control
            )
        self.assertTrue(
            any(
                "management-readonly-local-v1" in s
                for s in ac5["forbidden_substitutes"]
            )
        )

    def test_ac8_names_the_alert_observer_and_signature_authority(self) -> None:
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            ac8 = qualify.run_environment_gated_ac(
                "AC-SP94-8", self.gating, self.control
            )
        inputs = " ".join(entry["input"] for entry in ac8["missing_ground_truth"])
        self.assertIn("alert-observer receipt", inputs)
        self.assertIn("signing authority", inputs)
        self.assertIn("post-rollback inventory", inputs)

    def test_becomes_decision_required_when_a_full_receipt_exists(self) -> None:
        receipt = {
            field: "present" for field in qualify.REQUIRED_ENVIRONMENT_RECEIPT_FIELDS
        }
        with mock.patch.object(
            qualify, "find_environment_receipt", return_value=receipt
        ):
            ac2 = qualify.run_environment_gated_ac(
                "AC-SP94-2", self.gating, self.control
            )
        self.assertEqual(ac2["status"], "decision-required")
        self.assertTrue(ac2["environment_receipt_present"])

    def test_fails_closed_when_the_negative_control_no_longer_holds(self) -> None:
        broken = copy.deepcopy(self.control)
        broken["issues"] = ["the local stack now claims ha_qualified=true"]
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            ac3 = qualify.run_environment_gated_ac("AC-SP94-3", self.gating, broken)
        self.assertEqual(ac3["buildable_result"], "RED")

    def test_fails_closed_when_the_gating_matrix_is_invalid(self) -> None:
        broken = copy.deepcopy(self.gating)
        broken["issues"] = ["environment_gated_criteria is empty"]
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            ac4 = qualify.run_environment_gated_ac("AC-SP94-4", broken, self.control)
        self.assertEqual(ac4["buildable_result"], "RED")


class EnvironmentReceiptDiscoveryTests(unittest.TestCase):
    def test_no_receipt_exists_for_this_profile(self) -> None:
        self.assertIsNone(qualify.find_environment_receipt())

    def test_rejects_a_partial_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "environment-receipt.json"
            path.write_text(
                json.dumps({"environment_identity": "only-one"}), encoding="utf-8"
            )
            with mock.patch.object(
                qualify, "environment_receipt_path", return_value=path
            ):
                self.assertIsNone(qualify.find_environment_receipt())

    def test_accepts_a_complete_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "environment-receipt.json"
            path.write_text(
                json.dumps(
                    {f: "x" for f in qualify.REQUIRED_ENVIRONMENT_RECEIPT_FIELDS}
                ),
                encoding="utf-8",
            )
            with mock.patch.object(
                qualify, "environment_receipt_path", return_value=path
            ):
                self.assertIsNotNone(qualify.find_environment_receipt())


# ---------------------------------------------------------------------------
# Never-raise contract and end-to-end assembly.
# ---------------------------------------------------------------------------


class NeverRaiseTests(unittest.TestCase):
    def test_returns_a_red_object_when_both_sibling_checkouts_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "not-a-checkout"
            with (
                mock.patch.object(qualify, "BARBAROSSA_ROOT", missing),
                mock.patch.object(qualify, "PORTAL_ROOT", missing),
            ):
                lock = qualify.build_profile_lock()
        self.assertEqual(lock["status"], "RED")
        self.assertEqual(lock["buildable_checks_result"], "RED")
        # The absence must surface as a named failure, never as a quiet PASS.
        for ac_id in qualify.BUILDABLE_ACS:
            self.assertEqual(lock["acceptance_criteria"][ac_id]["status"], "RED")
        self.assertTrue(lock["reasons"])

    def test_returns_a_red_object_when_the_gating_fixture_is_unreadable(self) -> None:
        with mock.patch.object(
            qualify,
            "load_gating_matrix",
            side_effect=qualify.QualificationError("fixture gone"),
        ):
            lock = qualify.build_profile_lock()
        self.assertEqual(lock["status"], "RED")
        self.assertIn("fixture gone", json.dumps(lock))

    def test_returns_a_red_object_on_an_unexpected_internal_error(self) -> None:
        with mock.patch.object(
            qualify, "registry_profile", side_effect=RuntimeError("unexpected boom")
        ):
            lock = qualify.build_profile_lock()
        self.assertEqual(lock["status"], "RED")
        self.assertTrue(
            any("qualifier_internal_error" in reason for reason in lock["reasons"]),
            lock["reasons"],
        )
        self.assertIn("profile_lock_digest", lock)


@skip_unless_siblings
class ProfileLockIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            cls.lock = qualify.build_profile_lock()

    def test_all_eight_acceptance_criteria_are_reported(self) -> None:
        self.assertEqual(set(self.lock["acceptance_criteria"]), ALL_AC_IDS)

    def test_every_criterion_is_red_and_none_is_a_partial_pass(self) -> None:
        for ac_id, ac in sorted(self.lock["acceptance_criteria"].items()):
            with self.subTest(ac_id=ac_id):
                self.assertEqual(ac["status"], "RED")
                self.assertTrue(ac["missing_ground_truth"])

    def test_every_buildable_check_passes(self) -> None:
        failed = {
            ac_id: ac["failed_buildable_checks"]
            for ac_id, ac in self.lock["acceptance_criteria"].items()
            if ac["buildable_result"] != "GREEN"
        }
        self.assertEqual(failed, {})
        self.assertEqual(self.lock["buildable_checks_result"], "GREEN")

    def test_overall_status_is_red_and_grants_no_activation_authority(self) -> None:
        self.assertEqual(self.lock["status"], "RED")
        self.assertEqual(self.lock["activation_authority"], "none")
        self.assertIn("not HA qualification", self.lock["overall_note"])

    def test_no_owner_receipt_digest_is_fabricated(self) -> None:
        self.assertIsNone(
            self.lock["members"]["sp92_barbarossa_ha"]["release_receipt_digest"]
        )
        self.assertIsNone(
            self.lock["members"]["sp91_distributed_work_transitively_via_sp92"][
                "release_receipt_digest"
            ]
        )

    def test_digest_is_reproducible_across_two_builds(self) -> None:
        with mock.patch.object(qualify, "find_environment_receipt", return_value=None):
            second = qualify.build_profile_lock()
        self.assertEqual(
            self.lock["profile_lock_digest"], second["profile_lock_digest"]
        )

    def test_write_evidence_is_idempotent_and_carries_an_unsigned_manifest(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(qualify, "evidence_dir", return_value=Path(tmp)),
        ):
            first = qualify.write_evidence(self.lock)
            second = qualify.write_evidence(self.lock)
            self.assertEqual(first, second)
            payload = json.loads(first.read_text(encoding="utf-8"))
        self.assertIsNone(payload["evidence_manifest"]["signature"])
        self.assertEqual(
            payload["evidence_manifest"]["profile_lock_digest"],
            self.lock["profile_lock_digest"],
        )

    def test_write_evidence_refuses_to_overwrite_diverging_content(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(qualify, "evidence_dir", return_value=Path(tmp)),
        ):
            qualify.write_evidence(self.lock)
            drifted = copy.deepcopy(self.lock)
            drifted["profile_lock_digest"] = "sha256:" + "0" * 64
            with self.assertRaises(qualify.QualificationError):
                qualify.write_evidence(drifted)


if __name__ == "__main__":
    unittest.main()
