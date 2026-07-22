from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_portfolio_drift.py"
SPEC_B1_PATH = Path("docs/specs/SPEC-B1-read-only-triage-rca.md")
SPEC_B1_TRACEABILITY_PATH = Path("solutions/sre-harness/spec-traceability/SPEC-B1.json")
SPEC_B2_PATH = Path("docs/specs/SPEC-B2-advisory-change-validation-integration.md")
SPEC_B2_TRACEABILITY_PATH = Path("solutions/sre-harness/spec-traceability/SPEC-B2.json")
SPEC_B3_PATH = Path("docs/specs/SPEC-B3-deterministic-canary-rollback.md")
SPEC_B3_TRACEABILITY_PATH = Path("solutions/sre-harness/spec-traceability/SPEC-B3.json")
SPEC_B4_PATH = Path("docs/specs/SPEC-B4-tier4-allowlisted-remediation.md")
SPEC_B4_TRACEABILITY_PATH = Path("solutions/sre-harness/spec-traceability/SPEC-B4.json")
SPEC_B5_PATH = Path("docs/specs/SPEC-B5-tier3-hitl-remediation.md")
SPEC_B5_TRACEABILITY_PATH = Path("solutions/sre-harness/spec-traceability/SPEC-B5.json")
SPEC_B6_PATH = Path("docs/specs/SPEC-B6-permanent-fix-chase.md")
SPEC_B6_TRACEABILITY_PATH = Path("solutions/sre-harness/spec-traceability/SPEC-B6.json")
SPEC_B7_PATH = Path("docs/specs/SPEC-B7-error-rate-baseline-detector.md")
SPEC_B7_TRACEABILITY_PATH = Path("solutions/sre-harness/spec-traceability/SPEC-B7.json")
SPEC_B7_CIR_PATH = Path("docs/specs/SPEC-B7-change-induced-regression-detector.md")
SPEC_B7_CIR_TRACEABILITY_PATH = Path(
    "solutions/sre-harness/spec-traceability/SPEC-B7-CIR.json"
)
SPEC_B7_DRIFT_PATH = Path("docs/specs/SPEC-B7-drift-detector.md")
SPEC_B7_DRIFT_TRACEABILITY_PATH = Path(
    "solutions/sre-harness/spec-traceability/SPEC-B7-DRIFT.json"
)
TRACK_B_SPEC_IDS = {
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
}
SPEC = importlib.util.spec_from_file_location("check_portfolio_drift", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def _expected_b1_traceability() -> dict[str, object]:
    source_digest = hashlib.sha256((ROOT / SPEC_B1_PATH).read_bytes()).hexdigest()
    return {
        "schemaVersion": "sre-harness.spec-portable-traceability/v1",
        "specId": "SPEC-B1",
        "specPath": SPEC_B1_PATH.as_posix(),
        "specSha256": f"sha256:{source_digest}",
        "evidenceScope": "local-portable-only",
        "operationalState": "incomplete",
        "authority": "non-authorizing",
        "implementationPaths": [
            "solutions/sre-harness/src/sre_harness/observability/attributes.py",
            "solutions/sre-harness/src/sre_harness/triage/contracts.py",
            "solutions/sre-harness/src/sre_harness/triage/eval.py",
            "solutions/sre-harness/src/sre_harness/triage/pipeline.py",
            "solutions/sre-harness/src/sre_harness/triage/rules.py",
            "solutions/sre-harness/src/sre_harness/triage/source.py",
        ],
        "probes": [
            {
                "id": "P-B1-1",
                "tests": [
                    "solutions/sre-harness/tests/test_triage_source.py::TestStrictJsonSnapshotSource::test_closed_schema_and_types_fail_closed",
                    "solutions/sre-harness/tests/test_triage_source.py::TestStrictJsonSnapshotSource::test_duplicate_non_finite_and_malformed_json_fail_closed",
                    "solutions/sre-harness/tests/test_triage_source.py::TestStrictJsonSnapshotSource::test_invalid_utf8_oversize_symlink_and_non_file_fail_closed",
                    "solutions/sre-harness/tests/test_triage_source.py::TestStrictJsonSnapshotSource::test_valid_v1_json_loads_exact_snapshot",
                ],
            },
            {
                "id": "P-B1-2",
                "tests": [
                    "solutions/sre-harness/tests/test_triage_pipeline.py::TestTriageContracts::test_contracts_require_timezone_aware_utc_and_bounded_values",
                    "solutions/sre-harness/tests/test_triage_pipeline.py::TestTriageContracts::test_snapshot_rejects_duplicate_or_future_evidence",
                    "solutions/sre-harness/tests/test_triage_source.py::TestSnapshotRequestAndSourceRejoin::test_foreign_incident_or_as_of_fails_closed",
                    "solutions/sre-harness/tests/test_triage_source.py::TestSnapshotRequestAndSourceRejoin::test_request_is_exact_utc_and_immutable",
                ],
            },
            {
                "id": "P-B1-3",
                "tests": [
                    "solutions/sre-harness/tests/test_triage_source.py::TestSnapshotRequestAndSourceRejoin::test_invalid_or_unavailable_source_never_becomes_an_empty_success",
                    "solutions/sre-harness/tests/test_triage_source.py::TestSnapshotRequestAndSourceRejoin::test_only_snapshot_is_called_and_exact_result_is_admitted",
                    "solutions/sre-harness/tests/test_triage_source.py::TestSnapshotRequestAndSourceRejoin::test_source_integrates_with_action_free_triage_pipeline",
                ],
            },
            {
                "id": "P-B1-4",
                "tests": [
                    "solutions/sre-harness/tests/test_triage_pipeline.py::TestGatherNode::test_gather_is_bounded_to_service_time_window_and_stable_order",
                    "solutions/sre-harness/tests/test_triage_pipeline.py::TestGatherNode::test_gather_rejects_non_positive_or_excessive_limits",
                ],
            },
            {
                "id": "P-B1-5",
                "tests": [
                    "solutions/sre-harness/tests/test_triage_pipeline.py::TestAnalyzeAndRcaNodes::test_analyzer_cannot_cite_evidence_outside_the_gathered_context",
                    "solutions/sre-harness/tests/test_triage_pipeline.py::TestAnalyzeAndRcaNodes::test_invalid_hypothesis_confidence_fails_closed",
                ],
            },
            {
                "id": "P-B1-6",
                "tests": [
                    "solutions/sre-harness/tests/test_triage_pipeline.py::TestAnalyzeAndRcaNodes::test_empty_context_stays_explicitly_unknown_instead_of_fabricating_evidence",
                    "solutions/sre-harness/tests/test_triage_pipeline.py::TestAnalyzeAndRcaNodes::test_resource_saturation_and_unknown_cases_are_calibrated",
                ],
            },
            {
                "id": "P-B1-7",
                "tests": [
                    "solutions/sre-harness/tests/test_triage_pipeline.py::TestAnalyzeAndRcaNodes::test_rca_contract_exposes_no_authority_bearing_fields",
                ],
            },
            {
                "id": "P-B1-8",
                "tests": [
                    "solutions/sre-harness/tests/test_triage_eval.py::TestTriageEval::test_seed_replays_cover_deploy_saturation_and_unknown",
                    "solutions/sre-harness/tests/test_triage_eval.py::TestTriageEval::test_wrong_root_cause_or_missing_required_citation_fails",
                    "solutions/sre-harness/tests/test_triage_eval.py::TestTriageEvalAdmission::test_absent_or_unmet_thresholds_fail_closed",
                    "solutions/sre-harness/tests/test_triage_eval.py::TestTriageEvalAdmission::test_pass_rate_duplicate_ids_and_unknown_overconfidence_are_reported",
                    "solutions/sre-harness/tests/test_triage_eval.py::TestTriageEvalAdmission::test_perfect_fixture_suite_is_threshold_conformant_but_never_production_evidence",
                    "solutions/sre-harness/tests/test_triage_eval_publication.py::TestCorpusPublicationEvalJoin::test_exact_policy_ids_and_manifest_must_rejoin",
                    "solutions/sre-harness/tests/test_triage_eval_publication.py::TestCorpusPublicationEvalJoin::test_raw_or_post_issuance_mutated_publication_cannot_enable",
                    "solutions/sre-harness/tests/test_triage_eval_publication.py::TestCorpusPublicationEvalJoin::test_verified_exact_curated_publication_can_issue_eligibility",
                    "solutions/sre-harness/tests/test_triage_eval_publication.py::TestCorpusPublicationGate::test_verifier_requires_exact_boolean_true",
                ],
            },
            {
                "id": "P-B1-9",
                "tests": [
                    "solutions/sre-harness/tests/test_observability.py::TestTriageInstrumentation::test_triage_emits_one_parent_and_three_node_spans",
                    "solutions/sre-harness/tests/test_observability.py::TestTriageInstrumentation::test_triage_parent_carries_provenance_and_read_only_result",
                ],
            },
        ],
    }


def _expected_b2_traceability() -> dict[str, object]:
    source_digest = hashlib.sha256((ROOT / SPEC_B2_PATH).read_bytes()).hexdigest()
    return {
        "schemaVersion": "sre-harness.spec-portable-traceability/v1",
        "specId": "SPEC-B2",
        "specPath": SPEC_B2_PATH.as_posix(),
        "specSha256": f"sha256:{source_digest}",
        "evidenceScope": "local-portable-only",
        "operationalState": "incomplete",
        "authority": "non-authorizing",
        "implementationPaths": [
            "solutions/sre-harness/src/sre_harness/advisory_integration.py",
            "solutions/sre-harness/src/sre_harness/change_gate.py",
            "solutions/sre-harness/src/sre_harness/cli.py",
        ],
        "probes": [
            {
                "id": "P-B2-1",
                "tests": [
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestClosedEnvelope::test_bounded_file_loader_rejects_oversize_and_symlink",
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestClosedEnvelope::test_direct_nonbytes_oversize_directory_and_invalid_shapes_fail",
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestClosedEnvelope::test_duplicate_nonfinite_invalid_utf8_or_nonobject_json_fails",
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestClosedEnvelope::test_exact_v1_envelope_loads_as_immutable_values",
                ],
            },
            {
                "id": "P-B2-2",
                "tests": [
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestClosedEnvelope::test_unknown_missing_foreign_stale_or_noncanonical_input_fails_closed",
                ],
            },
            {
                "id": "P-B2-3",
                "tests": [
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestClosedEnvelope::test_both_declared_integration_sources_are_accepted",
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestClosedEnvelope::test_future_or_more_than_five_minute_old_platform_snapshot_fails",
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestClosedEnvelope::test_unknown_missing_foreign_stale_or_noncanonical_input_fails_closed",
                ],
            },
            {
                "id": "P-B2-4",
                "tests": [
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestDeterministicAdvisoryResult::test_registered_gate_is_the_only_verdict_authority",
                ],
            },
            {
                "id": "P-B2-5",
                "tests": [
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestDeterministicAdvisoryResult::test_result_rejoins_exact_provenance_checks_and_boundary",
                ],
            },
            {
                "id": "P-B2-6",
                "tests": [
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestIntegrationCli::test_invalid_input_is_machine_distinct_and_does_not_fabricate_result",
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestIntegrationCli::test_unwritable_result_sink_is_the_same_fail_closed_integration_error",
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestIntegrationCli::test_valid_dispositions_are_distinct_and_always_write_the_result",
                ],
            },
            {
                "id": "P-B2-7",
                "tests": [
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestDeterministicAdvisoryResult::test_result_is_exactly_advisory_and_has_no_action_surface",
                ],
            },
            {
                "id": "P-B2-8",
                "tests": [
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestIntegrationTemplates::test_argocd_masks_only_the_explicit_presync_advisory_boundary",
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestIntegrationTemplates::test_gitlab_preserves_gate_status_and_retains_artifact",
                ],
            },
            {
                "id": "P-B2-9",
                "tests": [
                    "solutions/sre-harness/tests/test_advisory_integration.py::TestIntegrationTemplates::test_docs_retain_fixture_only_incomplete_boundary",
                ],
            },
        ],
    }


def _expected_b3_traceability() -> dict[str, object]:
    source_digest = hashlib.sha256((ROOT / SPEC_B3_PATH).read_bytes()).hexdigest()
    return {
        "schemaVersion": "sre-harness.spec-portable-traceability/v1",
        "specId": "SPEC-B3",
        "specPath": SPEC_B3_PATH.as_posix(),
        "specSha256": f"sha256:{source_digest}",
        "evidenceScope": "local-portable-only",
        "operationalState": "incomplete",
        "authority": "non-authorizing",
        "implementationPaths": [
            "solutions/sre-harness/src/sre_harness/rollback.py",
        ],
        "probes": [
            {
                "id": "P-B3-1",
                "tests": [
                    "solutions/sre-harness/tests/test_rollback.py::TestClosedCandidatePolicy::test_exact_fixture_policy_loads_as_immutable_values",
                    "solutions/sre-harness/tests/test_rollback.py::TestClosedCandidatePolicy::test_non_object_duplicate_nonfinite_or_non_utf8_json_fails",
                    "solutions/sre-harness/tests/test_rollback.py::TestClosedCandidatePolicy::test_oversize_policy_fails_before_json_acceptance",
                    "solutions/sre-harness/tests/test_rollback.py::TestClosedCandidatePolicy::test_regular_file_loads_but_symlink_is_rejected",
                    "solutions/sre-harness/tests/test_rollback.py::TestClosedCandidatePolicy::test_unknown_missing_unbound_mutable_or_unsafe_candidate_fails",
                ],
            },
            {
                "id": "P-B3-2",
                "tests": [
                    "solutions/sre-harness/tests/test_rollback.py::TestClosedCandidatePolicy::test_unknown_missing_unbound_mutable_or_unsafe_candidate_fails",
                ],
            },
            {
                "id": "P-B3-3",
                "tests": [
                    "solutions/sre-harness/tests/test_rollback.py::TestDeterministicOracle::test_breach_missing_error_or_nonfinite_aborts",
                    "solutions/sre-harness/tests/test_rollback.py::TestDeterministicOracle::test_extra_observations_fail_instead_of_reinterpreting_window",
                    "solutions/sre-harness/tests/test_rollback.py::TestDeterministicOracle::test_mutated_or_raw_policy_cannot_return_a_disposition",
                    "solutions/sre-harness/tests/test_rollback.py::TestDeterministicOracle::test_partial_success_observes_and_exact_success_continues",
                    "solutions/sre-harness/tests/test_rollback.py::TestDeterministicOracle::test_threshold_is_inclusive_for_success",
                ],
            },
            {
                "id": "P-B3-4",
                "tests": [
                    "solutions/sre-harness/tests/test_rollback.py::TestKubernetesBundle::test_analysis_is_finite_inline_complementary_and_fail_closed",
                ],
            },
            {
                "id": "P-B3-5",
                "tests": [
                    "solutions/sre-harness/tests/test_rollback.py::TestKubernetesBundle::test_datadog_v2_is_explicit_namespaced_and_has_no_credentials",
                ],
            },
            {
                "id": "P-B3-6",
                "tests": [
                    "solutions/sre-harness/tests/test_rollback.py::TestKubernetesBundle::test_analysis_is_finite_inline_complementary_and_fail_closed",
                    "solutions/sre-harness/tests/test_rollback.py::TestKubernetesBundle::test_bundle_is_revision_annotated_deterministic_and_fixture_only",
                    "solutions/sre-harness/tests/test_rollback.py::TestKubernetesBundle::test_rollout_and_service_encode_basic_canary_and_safe_workload",
                ],
            },
            {
                "id": "P-B3-7",
                "tests": [
                    "solutions/sre-harness/tests/test_rollback.py::TestKubernetesBundle::test_rollout_and_service_encode_basic_canary_and_safe_workload",
                ],
            },
            {
                "id": "P-B3-8",
                "tests": [
                    "solutions/sre-harness/tests/test_rollback.py::TestKubernetesBundle::test_bundle_is_revision_annotated_deterministic_and_fixture_only",
                    "solutions/sre-harness/tests/test_rollback.py::TestKubernetesBundle::test_checked_in_bundle_is_exactly_generated_from_checked_in_policy",
                    "solutions/sre-harness/tests/test_rollback.py::TestKubernetesBundle::test_renderer_rejects_mutated_policy",
                ],
            },
            {
                "id": "P-B3-9",
                "tests": [
                    "solutions/sre-harness/tests/test_rollback.py::TestEvidenceBoundary::test_docs_retain_fixture_only_incomplete_boundary",
                ],
            },
        ],
    }


def _expected_b4_traceability() -> dict[str, object]:
    source_digest = hashlib.sha256((ROOT / SPEC_B4_PATH).read_bytes()).hexdigest()
    return {
        "schemaVersion": "sre-harness.spec-portable-traceability/v1",
        "specId": "SPEC-B4",
        "specPath": SPEC_B4_PATH.as_posix(),
        "specSha256": f"sha256:{source_digest}",
        "evidenceScope": "local-portable-only",
        "operationalState": "incomplete",
        "authority": "non-authorizing",
        "implementationPaths": [
            "solutions/sre-harness/src/sre_harness/autonomy_tiers/action_table.py",
            "solutions/sre-harness/src/sre_harness/autonomy_tiers/classify.py",
            "solutions/sre-harness/src/sre_harness/remediation.py",
        ],
        "probes": [
            {
                "id": "P-B4-1",
                "tests": [
                    "solutions/sre-harness/tests/test_remediation.py::TestClosedPolicyPublication::test_exact_publication_loads_immutable_allowlist",
                    "solutions/sre-harness/tests/test_remediation.py::TestClosedPolicyPublication::test_malformed_duplicate_nonfinite_or_non_utf8_policy_fails",
                    "solutions/sre-harness/tests/test_remediation.py::TestClosedPolicyPublication::test_oversize_and_symlink_policy_fail",
                    "solutions/sre-harness/tests/test_remediation.py::TestClosedPolicyPublication::test_unknown_unbound_mutable_or_unsafe_policy_fails",
                ],
            },
            {
                "id": "P-B4-2",
                "tests": [
                    "solutions/sre-harness/tests/test_remediation.py::TestExternalPolicyAuthority::test_exact_boolean_verifier_issues_opaque_capability",
                    "solutions/sre-harness/tests/test_remediation.py::TestExternalPolicyAuthority::test_false_or_truthy_non_boolean_verification_fails",
                    "solutions/sre-harness/tests/test_remediation.py::TestExternalPolicyAuthority::test_future_or_expired_publication_fails",
                    "solutions/sre-harness/tests/test_remediation.py::TestExternalPolicyAuthority::test_untrusted_origin_verifier_or_callback_mutation_fails",
                    "solutions/sre-harness/tests/test_remediation.py::test_checked_in_policy_is_fixture_only_and_cannot_authorize_t4",
                ],
            },
            {
                "id": "P-B4-3",
                "tests": [
                    "solutions/sre-harness/tests/test_remediation.py::TestClosedPolicyPublication::test_exact_publication_loads_immutable_allowlist",
                    "solutions/sre-harness/tests/test_remediation.py::TestClosedPolicyPublication::test_unknown_unbound_mutable_or_unsafe_policy_fails",
                ],
            },
            {
                "id": "P-B4-4",
                "tests": [
                    "solutions/sre-harness/tests/test_remediation.py::TestClosedRemediationRequest::test_duplicate_nonfinite_non_utf8_or_non_object_request_fails",
                    "solutions/sre-harness/tests/test_remediation.py::TestClosedRemediationRequest::test_exact_request_loads_and_rejoins_policy",
                    "solutions/sre-harness/tests/test_remediation.py::TestClosedRemediationRequest::test_unknown_malformed_or_noncanonical_request_fails",
                ],
            },
            {
                "id": "P-B4-5",
                "tests": [
                    "solutions/sre-harness/tests/test_remediation.py::TestAuthorization::test_binding_time_or_parameter_mismatch_requires_t3",
                    "solutions/sre-harness/tests/test_remediation.py::TestAuthorization::test_exact_decimal_threshold_cannot_round_up_to_t4",
                    "solutions/sre-harness/tests/test_remediation.py::TestAuthorization::test_exact_external_candidate_authorizes_t4",
                    "solutions/sre-harness/tests/test_remediation.py::TestAuthorization::test_low_confidence_fixture_offplan_or_environment_mismatch_requires_t3",
                    "solutions/sre-harness/tests/test_remediation.py::TestAuthorization::test_raw_or_mutated_inputs_fail_before_decision",
                ],
            },
            {
                "id": "P-B4-6",
                "tests": [
                    "solutions/sre-harness/tests/test_remediation.py::TestExactStart::test_client_account_or_region_drift_prevents_start",
                    "solutions/sre-harness/tests/test_remediation.py::TestExactStart::test_document_drift_prevents_start",
                    "solutions/sre-harness/tests/test_remediation.py::TestExactStart::test_non_t4_mutated_expired_or_invalid_execution_id_fails",
                    "solutions/sre-harness/tests/test_remediation.py::TestExactStart::test_repeated_start_reuses_client_token_and_notification_key",
                    "solutions/sre-harness/tests/test_remediation.py::TestExactStart::test_start_rejoins_document_and_uses_bounded_idempotent_call",
                ],
            },
            {
                "id": "P-B4-7",
                "tests": [
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_compensation_failure_is_terminal_and_never_recursive",
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_execution_identity_drift_or_mutated_run_fails_before_action",
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_forward_failure_starts_exact_compensation_and_success_rolls_back",
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_running_is_stable_and_success_is_terminal",
                ],
            },
            {
                "id": "P-B4-8",
                "tests": [
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_approval_or_calendar_state_escalates_without_compensation",
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_execution_identity_drift_or_mutated_run_fails_before_action",
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_reconcile_rechecks_client_account_and_region",
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_rollback_document_drift_escalates_without_starting_it",
                ],
            },
            {
                "id": "P-B4-9",
                "tests": [
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_compensation_failure_is_terminal_and_never_recursive",
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_forward_failure_starts_exact_compensation_and_success_rolls_back",
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_retry_reuses_rollback_token_and_notifications_are_non_secret",
                    "solutions/sre-harness/tests/test_remediation.py::TestCompensationLifecycle::test_running_is_stable_and_success_is_terminal",
                    "solutions/sre-harness/tests/test_remediation.py::TestExactStart::test_notification_failure_retries_the_same_started_execution",
                    "solutions/sre-harness/tests/test_remediation.py::TestExactStart::test_repeated_start_reuses_client_token_and_notification_key",
                ],
            },
            {
                "id": "P-B4-10",
                "tests": [
                    "solutions/sre-harness/tests/test_remediation.py::TestEvidenceBoundary::test_docs_retain_fixture_only_incomplete_boundary",
                    "solutions/sre-harness/tests/test_remediation.py::test_checked_in_policy_is_fixture_only_and_cannot_authorize_t4",
                ],
            },
        ],
    }


def _expected_b5_traceability() -> dict[str, object]:
    source_digest = hashlib.sha256((ROOT / SPEC_B5_PATH).read_bytes()).hexdigest()
    return {
        "schemaVersion": "sre-harness.spec-portable-traceability/v1",
        "specId": "SPEC-B5",
        "specPath": SPEC_B5_PATH.as_posix(),
        "specSha256": f"sha256:{source_digest}",
        "evidenceScope": "local-portable-only",
        "operationalState": "incomplete",
        "authority": "non-authorizing",
        "implementationPaths": [
            "solutions/sre-harness/src/sre_harness/autonomy_tiers/action_table.py",
            "solutions/sre-harness/src/sre_harness/autonomy_tiers/classify.py",
            "solutions/sre-harness/src/sre_harness/hitl.py",
        ],
        "probes": [
            {
                "id": "P-B5-1",
                "tests": [
                    "solutions/sre-harness/tests/test_hitl.py::TestClosedHitlProposal::test_checked_fixture_is_parseable_but_not_an_approval",
                    "solutions/sre-harness/tests/test_hitl.py::TestClosedHitlProposal::test_closed_non_authorizing_shape_rejects_drift",
                    "solutions/sre-harness/tests/test_hitl.py::TestClosedHitlProposal::test_exact_content_addressed_provider_unions_load",
                    "solutions/sre-harness/tests/test_hitl.py::TestClosedHitlProposal::test_file_loader_rejects_symlink_and_oversize",
                    "solutions/sre-harness/tests/test_hitl.py::TestClosedHitlProposal::test_malformed_duplicate_nonfinite_or_non_utf8_fails",
                ],
            },
            {
                "id": "P-B5-2",
                "tests": [
                    "solutions/sre-harness/tests/test_hitl.py::TestTierAdmission::test_existing_classifier_is_the_only_tier_authority",
                    "solutions/sre-harness/tests/test_hitl.py::TestTierAdmission::test_future_or_expired_proposal_is_terminal_without_provider",
                    "solutions/sre-harness/tests/test_hitl.py::TestTierAdmission::test_maximum_precision_confidence_preserves_classifier_boundary",
                    "solutions/sre-harness/tests/test_hitl.py::TestTierAdmission::test_raw_or_mutated_proposal_cannot_open_case",
                    "solutions/sre-harness/tests/test_hitl.py::TestTierAdmission::test_table_revision_drift_denies_without_provider",
                ],
            },
            {
                "id": "P-B5-3",
                "tests": [
                    "solutions/sre-harness/tests/test_hitl.py::TestClosedHitlProposal::test_aws_subject_must_be_exact_first_step_approval",
                    "solutions/sre-harness/tests/test_hitl.py::TestClosedHitlProposal::test_closed_non_authorizing_shape_rejects_drift",
                    "solutions/sre-harness/tests/test_hitl.py::TestClosedHitlProposal::test_exact_content_addressed_provider_unions_load",
                    "solutions/sre-harness/tests/test_hitl.py::TestClosedHitlProposal::test_gitlab_subject_must_pin_protected_review_identity",
                ],
            },
            {
                "id": "P-B5-4",
                "tests": [
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_checked_fixture_receipt_is_fixture_only",
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_exact_boolean_verifier_issues_opaque_capability",
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_exact_content_addressed_receipt_loads",
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_false_or_truthy_nonboolean_verification_fails",
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_future_or_expired_receipt_cannot_be_verified",
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_malformed_duplicate_nonfinite_or_non_utf8_receipt_fails",
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_receipt_file_loader_rejects_symlink_and_oversize",
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_receipt_rejects_closed_shape_and_nonhuman_drift",
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_untrusted_origin_verifier_or_callback_mutation_fails",
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_verified_receipts_cannot_be_caller_constructed",
                ],
            },
            {
                "id": "P-B5-5",
                "tests": [
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_future_or_expired_receipt_cannot_be_verified",
                    "solutions/sre-harness/tests/test_hitl.py::TestReceiptRejoin::test_cross_proposal_or_subject_receipt_never_calls_provider",
                    "solutions/sre-harness/tests/test_hitl.py::TestReceiptRejoin::test_fixture_receipt_never_calls_provider",
                    "solutions/sre-harness/tests/test_hitl.py::TestReceiptRejoin::test_proposer_self_approval_never_calls_provider",
                    "solutions/sre-harness/tests/test_hitl.py::TestReceiptRejoin::test_receipt_use_after_verification_expiry_expires_without_provider",
                ],
            },
            {
                "id": "P-B5-6",
                "tests": [
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_audit_failure_returns_no_advanced_state_and_retry_reuses_keys",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_client_account_or_region_drift_fails_before_snapshot",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_conflicting_terminal_provider_state_escalates",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_document_input_or_step_drift_escalates_without_signal",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_exact_pending_snapshot_sends_one_bounded_signal",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_matching_terminal_snapshot_is_idempotent_without_signal",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_pending_provider_state_preserves_the_signalled_case",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_provider_failure_exposes_no_detail_and_retry_reuses_key",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_receipt_expiry_does_not_revoke_an_already_sent_approval",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_signal_reconciles_to_matching_terminal_state",
                ],
            },
            {
                "id": "P-B5-7",
                "tests": [
                    "solutions/sre-harness/tests/test_hitl.py::TestGitlabApprovalFlow::test_exact_protected_rule_approval_is_read_only_and_terminal",
                    "solutions/sre-harness/tests/test_hitl.py::TestGitlabApprovalFlow::test_instance_binding_drift_escalates_before_observation",
                    "solutions/sre-harness/tests/test_hitl.py::TestGitlabApprovalFlow::test_rejected_receipt_is_terminal_without_gitlab_call",
                    "solutions/sre-harness/tests/test_hitl.py::TestGitlabApprovalFlow::test_stale_empty_overridden_or_self_approval_escalates",
                ],
            },
            {
                "id": "P-B5-8",
                "tests": [
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_matching_terminal_snapshot_is_idempotent_without_signal",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_pending_provider_state_preserves_the_signalled_case",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_receipt_expiry_does_not_revoke_an_already_sent_approval",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_signal_reconciles_to_matching_terminal_state",
                    "solutions/sre-harness/tests/test_hitl.py::TestFiniteStateAndAudit::test_mutated_case_fails_before_provider",
                    "solutions/sre-harness/tests/test_hitl.py::TestFiniteStateAndAudit::test_terminal_state_is_side_effect_free_and_reject_cannot_flip",
                    "solutions/sre-harness/tests/test_hitl.py::TestGitlabApprovalFlow::test_rejected_receipt_is_terminal_without_gitlab_call",
                    "solutions/sre-harness/tests/test_hitl.py::TestReceiptRejoin::test_receipt_use_after_verification_expiry_expires_without_provider",
                ],
            },
            {
                "id": "P-B5-9",
                "tests": [
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_audit_failure_returns_no_advanced_state_and_retry_reuses_keys",
                    "solutions/sre-harness/tests/test_hitl.py::TestAwsApprovalFlow::test_provider_failure_exposes_no_detail_and_retry_reuses_key",
                    "solutions/sre-harness/tests/test_hitl.py::TestFiniteStateAndAudit::test_audit_events_are_stable_and_nonsecret",
                    "solutions/sre-harness/tests/test_hitl.py::TestGitlabApprovalFlow::test_exact_protected_rule_approval_is_read_only_and_terminal",
                    "solutions/sre-harness/tests/test_hitl.py::TestGitlabApprovalFlow::test_rejected_receipt_is_terminal_without_gitlab_call",
                    "solutions/sre-harness/tests/test_hitl.py::TestTierAdmission::test_existing_classifier_is_the_only_tier_authority",
                ],
            },
            {
                "id": "P-B5-10",
                "tests": [
                    "solutions/sre-harness/tests/test_hitl.py::TestClosedHitlProposal::test_checked_fixture_is_parseable_but_not_an_approval",
                    "solutions/sre-harness/tests/test_hitl.py::TestEvidenceBoundary::test_docs_retain_fixture_only_incomplete_boundary",
                    "solutions/sre-harness/tests/test_hitl.py::TestExternalHumanReceipt::test_checked_fixture_receipt_is_fixture_only",
                ],
            },
        ],
    }


def _expected_b6_traceability() -> dict[str, object]:
    source_digest = hashlib.sha256((ROOT / SPEC_B6_PATH).read_bytes()).hexdigest()
    test_path = "solutions/sre-harness/tests/test_permanent_fix.py"

    def node(class_name: str, test_name: str) -> str:
        return f"{test_path}::{class_name}::{test_name}"

    return {
        "schemaVersion": "sre-harness.spec-portable-traceability/v1",
        "specId": "SPEC-B6",
        "specPath": SPEC_B6_PATH.as_posix(),
        "specSha256": f"sha256:{source_digest}",
        "evidenceScope": "local-portable-only",
        "operationalState": "incomplete",
        "authority": "non-authorizing",
        "implementationPaths": [
            "solutions/sre-harness/src/sre_harness/permanent_fix.py",
        ],
        "probes": [
            {
                "id": "P-B6-1",
                "tests": sorted(
                    [
                        node(
                            "TestClosedRequest",
                            "test_canonical_request_loads_and_is_content_addressed",
                        ),
                        node(
                            "TestClosedRequest",
                            "test_checked_request_fixture_is_fixture_only",
                        ),
                        node(
                            "TestClosedRequest",
                            "test_loader_rejects_symlink_oversize_and_non_file",
                        ),
                        node(
                            "TestClosedRequest",
                            "test_malformed_duplicate_nonfinite_non_utf8_and_noncanonical_json_fail",
                        ),
                        node(
                            "TestClosedRequest",
                            "test_request_rejects_closed_shape_authority_and_invalid_values",
                        ),
                        node(
                            "TestClosedRequest",
                            "test_request_rejects_credential_bearing_or_malformed_evidence_refs",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B6-2",
                "tests": sorted(
                    [
                        node(
                            "TestIssueOpening",
                            "test_fixture_expired_or_policy_drift_never_binds_provider",
                        ),
                        node(
                            "TestIssueOpening",
                            "test_foreign_provider_binding_fails_before_search",
                        ),
                        node(
                            "TestPolicyCapability",
                            "test_exact_external_verifier_issues_opaque_capability",
                        ),
                        node(
                            "TestPolicyCapability",
                            "test_false_or_truthy_nonboolean_verification_fails",
                        ),
                        node(
                            "TestPolicyCapability",
                            "test_policy_document_rejects_malformed_duplicate_nonfinite_and_non_utf8",
                        ),
                        node(
                            "TestPolicyCapability",
                            "test_policy_is_closed_and_checked_fixture_is_inert",
                        ),
                        node(
                            "TestPolicyCapability",
                            "test_policy_requires_incident_and_permanent_fix_labels",
                        ),
                        node(
                            "TestPolicyCapability",
                            "test_untrusted_mutated_future_expired_or_fixture_policy_fails",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B6-3",
                "tests": sorted(
                    [
                        node(
                            "TestIssueOpening",
                            "test_absent_issue_creates_one_bounded_call_and_audits",
                        ),
                        node(
                            "TestIssueOpening",
                            "test_ambiguous_dedupe_search_fails_without_create",
                        ),
                        node(
                            "TestIssueOpening",
                            "test_existing_exact_issue_is_adopted_without_create",
                        ),
                        node(
                            "TestIssueOpening",
                            "test_foreign_pr_as_issue_or_closed_create_result_fails",
                        ),
                        node(
                            "TestIssueOpening",
                            "test_retry_after_audit_failure_adopts_provider_deduped_issue",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B6-4",
                "tests": sorted(
                    [
                        node(
                            "TestClosedRequest",
                            "test_request_rejects_closed_shape_authority_and_invalid_values",
                        ),
                        node(
                            "TestIssueOpening",
                            "test_absent_issue_creates_one_bounded_call_and_audits",
                        ),
                        node(
                            "TestNegativeAuthoritySurface",
                            "test_provider_protocol_and_call_surface_have_no_mutation_authority",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B6-5",
                "tests": sorted(
                    [
                        node(
                            "TestChaseLifecycle",
                            "test_ambiguous_or_foreign_change_escalates",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_exact_open_change_advances_to_change_open",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_no_change_remains_issue_open_without_audit_noise",
                        ),
                        node(
                            "TestNegativeAuthoritySurface",
                            "test_provider_protocol_and_call_surface_have_no_mutation_authority",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B6-6",
                "tests": sorted(
                    [
                        node(
                            "TestChaseLifecycle",
                            "test_foreign_failed_or_ungated_outcome_escalates",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_lifecycle_regression_and_merged_head_mismatch_escalate",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_policy_outcome_age_is_rechecked_at_reconciliation",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_produced_verified_and_gated_outcomes_advance_monotonically",
                        ),
                        node(
                            "TestFactoryOutcomeAuthority",
                            "test_exact_boolean_verifier_issues_opaque_outcome",
                        ),
                        node(
                            "TestFactoryOutcomeAuthority",
                            "test_outcome_document_rejects_malformed_duplicate_nonfinite_and_non_utf8",
                        ),
                        node(
                            "TestFactoryOutcomeAuthority",
                            "test_outcome_rejects_credential_bearing_or_malformed_evidence_manifest",
                        ),
                        node(
                            "TestFactoryOutcomeAuthority",
                            "test_outcome_rejects_mutation_origin_fixture_future_and_staleness",
                        ),
                        node(
                            "TestFactoryOutcomeAuthority",
                            "test_outcome_schema_is_closed_and_exact",
                        ),
                        node(
                            "TestFactoryOutcomeAuthority",
                            "test_truthy_nonboolean_outcome_verification_fails",
                        ),
                        node(
                            "TestNegativeAuthoritySurface",
                            "test_cases_and_verified_capabilities_are_not_caller_constructible",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B6-7",
                "tests": sorted(
                    [
                        node(
                            "TestChaseLifecycle",
                            "test_landed_requires_merged_provider_and_exact_factory_head",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_lifecycle_regression_and_merged_head_mismatch_escalate",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_provider_merge_or_outcome_alone_never_lands",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B6-8",
                "tests": sorted(
                    [
                        node(
                            "TestChaseLifecycle",
                            "test_ambiguous_or_foreign_change_escalates",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_closed_issue_before_landed_and_deadline_escalate",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_foreign_failed_or_ungated_outcome_escalates",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_lifecycle_regression_and_merged_head_mismatch_escalate",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_missing_outcome_preserves_monotonic_state",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_no_change_remains_issue_open_without_audit_noise",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_prematurely_closed_issue_never_lands_with_exact_two_source_evidence",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_produced_verified_and_gated_outcomes_advance_monotonically",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_provider_merge_observation_is_sealed_and_cannot_regress",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_terminal_states_are_stable_without_provider_calls",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_tracked_change_disappearance_escalates",
                        ),
                        node(
                            "TestNegativeAuthoritySurface",
                            "test_provider_protocol_and_call_surface_have_no_mutation_authority",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B6-9",
                "tests": sorted(
                    [
                        node(
                            "TestChaseLifecycle",
                            "test_ambiguous_or_foreign_change_escalates",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_audit_failure_does_not_return_transition",
                        ),
                        node(
                            "TestChaseLifecycle",
                            "test_no_change_remains_issue_open_without_audit_noise",
                        ),
                        node(
                            "TestIssueOpening",
                            "test_absent_issue_creates_one_bounded_call_and_audits",
                        ),
                        node(
                            "TestIssueOpening",
                            "test_retry_after_audit_failure_adopts_provider_deduped_issue",
                        ),
                        node(
                            "TestNegativeAuthoritySurface",
                            "test_audit_is_sanitized_and_has_stable_retry_key",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B6-10",
                "tests": sorted(
                    [
                        node(
                            "TestClosedRequest",
                            "test_checked_request_fixture_is_fixture_only",
                        ),
                        node(
                            "TestEvidenceBoundary",
                            "test_docs_retain_local_only_incomplete_boundary",
                        ),
                        node(
                            "TestFactoryOutcomeAuthority",
                            "test_outcome_rejects_mutation_origin_fixture_future_and_staleness",
                        ),
                        node(
                            "TestPolicyCapability",
                            "test_policy_is_closed_and_checked_fixture_is_inert",
                        ),
                    ]
                ),
            },
        ],
    }


def _expected_b7_traceability() -> dict[str, object]:
    source_digest = hashlib.sha256((ROOT / SPEC_B7_PATH).read_bytes()).hexdigest()

    def node(filename: str, *parts: str) -> str:
        return "::".join([f"solutions/sre-harness/tests/{filename}", *parts])

    return {
        "schemaVersion": "sre-harness.spec-portable-traceability/v1",
        "specId": "SPEC-B7",
        "specPath": SPEC_B7_PATH.as_posix(),
        "specSha256": f"sha256:{source_digest}",
        "evidenceScope": "local-portable-only",
        "operationalState": "incomplete",
        "authority": "non-authorizing",
        "implementationPaths": [
            "solutions/sre-harness/src/sre_harness/sentinel/detectors.py",
            "solutions/sre-harness/src/sre_harness/sentinel/eval.py",
            "solutions/sre-harness/src/sre_harness/sentinel/scenarios.py",
            "solutions/sre-harness/src/sre_harness/sentinel/serialization.py",
            "solutions/sre-harness/src/sre_harness/sentinel/state.py",
        ],
        "probes": [
            {
                "id": "P-B7-1",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_error_rate.py",
                            "TestExactErrorRateWindow",
                            "test_invalid_or_coerced_signal_is_rejected",
                        ),
                        node(
                            "test_sentinel_error_rate.py",
                            "TestExactErrorRateWindow",
                            "test_rates_are_derived_from_exact_aggregate_counts",
                        ),
                        node(
                            "test_sentinel_error_rate.py",
                            "TestExactErrorRateWindow",
                            "test_signal_and_state_are_frozen",
                        ),
                        node(
                            "test_sentinel_state.py",
                            "test_state_defaults_to_empty_signals",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7-2",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_deeply_nested_json_is_rejected_not_a_raw_recursion_error",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_directory_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_duplicate_keys_are_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_invalid_json_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_invalid_utf8_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_non_object_payload_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_nonfinite_json_numbers_are_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_open_is_nonblocking_so_special_files_cannot_stall_the_reader",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_oversized_file_is_rejected_before_decode",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_symlink_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDict",
                            "test_parses_exact_error_rate_windows",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDictErrors",
                            "test_error_rate_window_missing_or_null_field_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDictErrors",
                            "test_error_rate_window_non_mapping_row_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDictErrors",
                            "test_error_rate_window_rejects_coercion_and_nonfinite_values",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDictErrors",
                            "test_error_rate_windows_not_a_list_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDictErrors",
                            "test_error_rate_windows_over_signal_limit_is_rejected_before_row_parsing",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7-3",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_error_rate.py",
                            "TestErrorRateRule",
                            "test_exact_minimum_sample_can_qualify",
                        ),
                        node(
                            "test_sentinel_error_rate.py",
                            "TestErrorRateRule",
                            "test_insufficient_samples_stay_silent",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7-4",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_error_rate.py",
                            "TestErrorRateRule",
                            "test_current_rate_inside_declared_slo_budget_multiplier_stays_silent",
                        ),
                        node(
                            "test_sentinel_error_rate.py",
                            "TestErrorRateRule",
                            "test_exact_candidate_threshold_fires_high",
                        ),
                        node(
                            "test_sentinel_error_rate.py",
                            "TestErrorRateRule",
                            "test_just_below_complete_threshold_stays_silent",
                        ),
                        node(
                            "test_sentinel_error_rate.py",
                            "TestErrorRateRule",
                            "test_rule_constants_match_the_spec_candidate",
                        ),
                        node(
                            "test_sentinel_error_rate.py",
                            "TestErrorRateRule",
                            "test_stable_high_baseline_is_not_a_fixed_threshold_alert",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7-5",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_error_rate.py",
                            "TestErrorRateRule",
                            "test_critical_boundary_uses_stricter_relative_and_budget_rule",
                        ),
                        node(
                            "test_sentinel_error_rate.py",
                            "TestErrorRateRule",
                            "test_exact_candidate_threshold_fires_high",
                        ),
                        node(
                            "test_sentinel_error_rate.py",
                            "TestErrorRateRule",
                            "test_multiple_windows_preserve_input_order_and_silence_clean_service",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7-6",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_detectors.py",
                            "test_default_registry_contains_all_five_detectors",
                        ),
                        node(
                            "test_sentinel_error_rate.py",
                            "TestErrorRateRule",
                            "test_default_registry_contains_the_detector_without_action_surface",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7-7",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_eval.py",
                            "test_b7_error_rate_corpus_has_lead_and_three_distinct_clean_controls",
                        ),
                        node(
                            "test_sentinel_eval.py",
                            "test_runner_finds_the_earliest_fire_index",
                        ),
                        node(
                            "test_sentinel_eval.py",
                            "test_seed_suite_all_passes",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7-8",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_eval.py",
                            "test_b7_error_rate_corpus_has_lead_and_three_distinct_clean_controls",
                        ),
                        node(
                            "test_sentinel_eval.py",
                            "test_clean_scenario_that_actually_fires_is_a_false_positive",
                        ),
                        node(
                            "test_sentinel_eval.py",
                            "test_seed_suite_all_passes",
                        ),
                        node(
                            "test_sentinel_eval.py",
                            "test_seed_suite_reports_explicit_early_detection_and_false_positive_metrics",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7-9",
                "tests": [
                    node(
                        "test_sentinel_error_rate.py",
                        "TestEvidenceBoundary",
                        "test_docs_retain_fixture_only_incomplete_boundary",
                    )
                ],
            },
        ],
    }


def _expected_b7_cir_traceability() -> dict[str, object]:
    source_digest = hashlib.sha256((ROOT / SPEC_B7_CIR_PATH).read_bytes()).hexdigest()

    def node(filename: str, *parts: str) -> str:
        return "::".join([f"solutions/sre-harness/tests/{filename}", *parts])

    return {
        "schemaVersion": "sre-harness.spec-portable-traceability/v1",
        "specId": "SPEC-B7-CIR",
        "specPath": SPEC_B7_CIR_PATH.as_posix(),
        "specSha256": f"sha256:{source_digest}",
        "evidenceScope": "local-portable-only",
        "operationalState": "incomplete",
        "authority": "non-authorizing",
        "implementationPaths": [
            "solutions/sre-harness/src/sre_harness/sentinel/detectors.py",
            "solutions/sre-harness/src/sre_harness/sentinel/eval.py",
            "solutions/sre-harness/src/sre_harness/sentinel/scan.py",
            "solutions/sre-harness/src/sre_harness/sentinel/scenarios.py",
            "solutions/sre-harness/src/sre_harness/sentinel/serialization.py",
            "solutions/sre-harness/src/sre_harness/sentinel/state.py",
        ],
        "probes": [
            {
                "id": "P-B7C-1",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_change_regression.py",
                            "TestExactChangeRegressionWindow",
                            "test_derives_only_rates_and_deploy_age_from_exact_aggregates",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestExactChangeRegressionWindow",
                            "test_equal_revisions_are_rejected",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestExactChangeRegressionWindow",
                            "test_invalid_or_coerced_signal_is_rejected",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestExactChangeRegressionWindow",
                            "test_invalid_window_order_is_rejected",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestExactChangeRegressionWindow",
                            "test_signal_and_state_are_frozen",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7C-2",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_deeply_nested_json_is_rejected_not_a_raw_recursion_error",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_directory_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_duplicate_keys_are_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_file_changed_while_reading_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_invalid_json_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_invalid_utf8_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_non_object_payload_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_nonfinite_json_numbers_are_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_open_is_nonblocking_so_special_files_cannot_stall_the_reader",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_oversized_file_is_rejected_before_decode",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_symlink_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDict",
                            "test_parses_exact_change_regression_windows",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDictErrors",
                            "test_change_regression_extra_field_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDictErrors",
                            "test_change_regression_missing_or_null_field_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDictErrors",
                            "test_change_regression_non_mapping_row_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDictErrors",
                            "test_change_regression_rejects_coercion_and_nonfinite_values",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDictErrors",
                            "test_change_regression_windows_not_a_list_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestStateFromDictErrors",
                            "test_change_regression_windows_over_limit_is_rejected_before_row_parsing",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7C-3",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_exact_association_age_boundary_qualifies",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_expired_association_stays_silent",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_intervening_deployment_stays_silent",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7C-4",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_current_rate_inside_declared_slo_budget_stays_silent",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_exact_candidate_threshold_emits_honest_high_finding",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_exact_minimum_sample_can_qualify",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_insufficient_samples_stay_silent",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_just_below_complete_threshold_stays_silent",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_stable_high_baseline_is_not_a_fixed_threshold_alert",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7C-5",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_critical_boundary_uses_the_inherited_stricter_rule",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_exact_candidate_threshold_emits_honest_high_finding",
                        ),
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_multiple_windows_preserve_input_order",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7C-6",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_scan.py",
                            "test_open_specific_finding_does_not_resurrect_fresh_generic_duplicate",
                        ),
                        node(
                            "test_sentinel_scan.py",
                            "test_silent_change_detector_does_not_hide_qualifying_generic_finding",
                        ),
                        node(
                            "test_sentinel_scan.py",
                            "test_specific_change_regression_replaces_same_service_generic_finding",
                        ),
                        node(
                            "test_sentinel_scan.py",
                            "test_specificity_collapse_does_not_crash_on_custom_non_string_service",
                        ),
                        node(
                            "test_sentinel_scan.py",
                            "test_specificity_collapse_keeps_same_service_different_finding_kind",
                        ),
                        node(
                            "test_sentinel_scan.py",
                            "test_specificity_collapse_keeps_unrelated_service_generic_finding",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7C-7",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_change_regression.py",
                            "TestChangeRegressionRule",
                            "test_registry_contains_the_detector_without_action_surface",
                        ),
                        node(
                            "test_sentinel_detectors.py",
                            "test_default_registry_contains_all_five_detectors",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7C-8",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_eval.py",
                            "test_b7_change_regression_has_lead_and_five_distinct_clean_controls",
                        ),
                        node(
                            "test_sentinel_eval.py",
                            "test_seed_suite_all_passes",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7C-9",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_eval.py",
                            "test_b7_change_regression_has_lead_and_five_distinct_clean_controls",
                        ),
                        node(
                            "test_sentinel_eval.py",
                            "test_seed_suite_all_passes",
                        ),
                        node(
                            "test_sentinel_eval.py",
                            "test_seed_suite_reports_explicit_early_detection_and_false_positive_metrics",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7C-10",
                "tests": [
                    node(
                        "test_sentinel_change_regression.py",
                        "TestEvidenceBoundary",
                        "test_docs_retain_fixture_only_incomplete_boundary",
                    )
                ],
            },
        ],
    }


def _expected_b7_drift_traceability() -> dict[str, object]:
    source_digest = hashlib.sha256((ROOT / SPEC_B7_DRIFT_PATH).read_bytes()).hexdigest()

    def node(filename: str, *parts: str) -> str:
        return "::".join([f"solutions/sre-harness/tests/{filename}", *parts])

    return {
        "schemaVersion": "sre-harness.spec-portable-traceability/v1",
        "specId": "SPEC-B7-DRIFT",
        "specPath": SPEC_B7_DRIFT_PATH.as_posix(),
        "specSha256": f"sha256:{source_digest}",
        "evidenceScope": "local-portable-only",
        "operationalState": "incomplete",
        "authority": "non-authorizing",
        "implementationPaths": [
            "solutions/sre-harness/src/sre_harness/sentinel/detectors.py",
            "solutions/sre-harness/src/sre_harness/sentinel/eval.py",
            "solutions/sre-harness/src/sre_harness/sentinel/scan.py",
            "solutions/sre-harness/src/sre_harness/sentinel/scenarios.py",
            "solutions/sre-harness/src/sre_harness/sentinel/serialization.py",
            "solutions/sre-harness/src/sre_harness/sentinel/state.py",
        ],
        "probes": [
            {
                "id": "P-B7D-1",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_drift.py",
                            "TestExactDriftObservation",
                            "test_derives_only_mismatch_age_from_exact_normalized_fact",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestExactDriftObservation",
                            "test_desired_observation_order_is_exact",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestExactDriftObservation",
                            "test_invalid_or_coerced_signal_is_rejected",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestExactDriftObservation",
                            "test_matching_and_missing_observations_are_representable_without_raw_content",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestExactDriftObservation",
                            "test_matching_revision_rejects_mismatch_evidence",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestExactDriftObservation",
                            "test_mismatch_requires_consistent_persistence_evidence",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestExactDriftObservation",
                            "test_signal_and_state_are_frozen",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7D-2",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftSerialization",
                            "test_array_limit_is_checked_before_row_parsing",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftSerialization",
                            "test_array_must_be_a_list",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftSerialization",
                            "test_extra_field_is_rejected",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftSerialization",
                            "test_missing_key_is_rejected_including_nullable_fields",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftSerialization",
                            "test_non_mapping_row_is_rejected",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftSerialization",
                            "test_parses_exact_mismatch_and_nullable_matching_rows",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftSerialization",
                            "test_rejects_coercion_and_wrong_nullability",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftSerialization",
                            "test_unknown_top_level_field_rejects_the_complete_snapshot",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_deeply_nested_json_is_rejected_not_a_raw_recursion_error",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_directory_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_duplicate_keys_are_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_file_changed_while_reading_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_invalid_json_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_invalid_utf8_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_non_object_payload_is_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_nonfinite_json_numbers_are_rejected",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_open_is_nonblocking_so_special_files_cannot_stall_the_reader",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_oversized_file_is_rejected_before_decode",
                        ),
                        node(
                            "test_sentinel_serialization.py",
                            "TestReadJsonObject",
                            "test_symlink_is_rejected",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7D-3",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_299_second_mismatch_stays_silent",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_exact_persistence_boundary_emits_bounded_medium_finding",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_matching_revision_stays_silent",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_one_observation_stays_silent",
                        ),
                        node(
                            "test_sentinel_eval.py",
                            "test_b7_drift_has_lead_and_five_distinct_clean_controls",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7D-4",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_exact_persistence_boundary_emits_bounded_medium_finding",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_matching_revision_stays_silent",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_persistent_missing_observation_is_high_and_honest",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7D-5",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_exact_persistence_boundary_emits_bounded_medium_finding",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_multiple_observations_preserve_input_order",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_one_hour_persistent_digest_mismatch_is_high",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_persistent_missing_observation_is_high_and_honest",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7D-6",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftDedup",
                            "test_different_resource_remains_fresh",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftDedup",
                            "test_higher_ranked_same_key_duplicate_wins_within_scan",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftDedup",
                            "test_open_condition_stays_suppressed_when_observed_digest_changes",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7D-7",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_detectors.py",
                            "test_default_registry_contains_all_five_detectors",
                        ),
                        node(
                            "test_sentinel_drift.py",
                            "TestDriftRule",
                            "test_registry_contains_pure_action_free_detector",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7D-8",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_eval.py",
                            "test_b7_drift_has_lead_and_five_distinct_clean_controls",
                        ),
                        node("test_sentinel_eval.py", "test_seed_suite_all_passes"),
                    ]
                ),
            },
            {
                "id": "P-B7D-9",
                "tests": sorted(
                    [
                        node(
                            "test_sentinel_eval.py",
                            "test_b7_drift_has_lead_and_five_distinct_clean_controls",
                        ),
                        node("test_sentinel_eval.py", "test_seed_suite_all_passes"),
                        node(
                            "test_sentinel_eval.py",
                            "test_seed_suite_reports_explicit_early_detection_and_false_positive_metrics",
                        ),
                    ]
                ),
            },
            {
                "id": "P-B7D-10",
                "tests": [
                    node(
                        "test_sentinel_drift.py",
                        "TestEvidenceBoundary",
                        "test_docs_retain_fixture_only_incomplete_boundary",
                    )
                ],
            },
        ],
    }


class PortfolioDriftTest(unittest.TestCase):
    def setUp(self) -> None:
        errors: list[str] = []
        self.registry = CHECKER._load_json(ROOT / "portfolio/projects.json", errors)
        self.assertEqual(errors, [])

    def test_repository_is_consistent(self) -> None:
        self.assertEqual(CHECKER.check_repository(ROOT), [])

    def test_repository_rejects_malformed_registry_roots_without_crashing(self) -> None:
        cases = (
            ([], "root must be an object"),
            ([{}], "root must be an object"),
            ({}, "registry root must be a closed object"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry_path = root / "portfolio/projects.json"
            registry_path.parent.mkdir(parents=True)
            for value, expected in cases:
                with self.subTest(value=value):
                    registry_path.write_text(json.dumps(value) + "\n", encoding="utf-8")

                    errors = CHECKER.check_repository(root)

                    self.assertTrue(any(expected in error for error in errors), errors)

    def test_repository_rejects_unknown_root_registry_key(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["unexpected"] = "value"

        with mock.patch.object(CHECKER, "_load_json", return_value=registry):
            errors = CHECKER.check_repository(ROOT)

        self.assertTrue(
            any("registry root must be a closed object" in error for error in errors),
            errors,
        )

    def test_repository_loader_rejects_ambiguous_or_non_finite_json(self) -> None:
        source = (ROOT / "portfolio/projects.json").read_text(encoding="utf-8")
        cases = (
            (
                source.replace(
                    '  "schema_version": 1,',
                    '  "schema_version": 999,\n  "schema_version": 1,',
                    1,
                ),
                "duplicate JSON key: schema_version",
            ),
            (
                source.replace('"schema_version": 1', '"schema_version": NaN', 1),
                "non-finite JSON number: NaN",
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry_path = root / "portfolio/projects.json"
            registry_path.parent.mkdir(parents=True)
            for raw, expected in cases:
                with self.subTest(expected=expected):
                    registry_path.write_text(raw, encoding="utf-8")

                    errors = CHECKER.check_repository(root)

                    self.assertTrue(any(expected in error for error in errors), errors)
            registry_path.write_bytes(b"\xff\n")

            errors = CHECKER.check_repository(root)

            self.assertTrue(any("is not UTF-8" in error for error in errors), errors)

    def test_repository_rejects_non_list_decision_items_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry_path = root / "portfolio/projects.json"
            registry_path.parent.mkdir(parents=True)
            for value in (None, False, 0):
                with self.subTest(value=value):
                    registry = copy.deepcopy(self.registry)
                    registry["decision_backlog"]["items"] = value
                    registry_path.write_text(
                        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
                    )

                    errors = CHECKER.check_repository(root)

                    self.assertTrue(
                        any("items must be a list" in error for error in errors),
                        errors,
                    )

    def test_repository_rejects_malformed_project_shapes_without_crashing(self) -> None:
        cases = (
            (
                "projects null",
                lambda registry: registry.__setitem__("projects", None),
                "malformed registry shape",
            ),
            (
                "projects false",
                lambda registry: registry.__setitem__("projects", False),
                "malformed registry shape",
            ),
            (
                "projects zero",
                lambda registry: registry.__setitem__("projects", 0),
                "malformed registry shape",
            ),
            (
                "nested mcp scalar",
                lambda registry: registry["projects"][0].__setitem__("mcp", None),
                "malformed registry shape",
            ),
            (
                "nested release scalar",
                lambda registry: registry["projects"][0].__setitem__(
                    "current_release", None
                ),
                "current_release",
            ),
            (
                "authority scalar",
                lambda registry: registry["authority"].__setitem__("portfolio", None),
                "malformed registry shape",
            ),
            (
                "project name scalar",
                lambda registry: registry["projects"][0].__setitem__("name", None),
                "malformed registry shape",
            ),
            (
                "canonical documents scalar",
                lambda registry: registry["projects"][0].__setitem__(
                    "canonical_documents", None
                ),
                "malformed registry shape",
            ),
            (
                "partial release evidence",
                lambda registry: registry["projects"][0]["current_release"].__setitem__(
                    "evidence", None
                ),
                "release version/evidence must both be set or both be null",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                registry = copy.deepcopy(self.registry)
                mutate(registry)
                with mock.patch.object(CHECKER, "_load_json", return_value=registry):
                    errors = CHECKER.check_repository(ROOT)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_registry_exposes_every_proposed_portfolio_decision(self) -> None:
        backlog = self.registry.get("decision_backlog")
        self.assertIsInstance(backlog, dict)
        assert isinstance(backlog, dict)
        self.assertEqual(backlog.get("owner"), "@100rd")
        self.assertEqual(backlog.get("status"), "human-disposition-required")

        items = backlog.get("items")
        self.assertIsInstance(items, list)
        assert isinstance(items, list)
        self.assertEqual(
            [item.get("id") for item in items],
            [
                "ADR-0002",
                "ADR-0003",
                "ADR-0006",
                "ADR-0008",
                "ADR-0014",
                "ADR-0015",
                "ADR-0016",
            ],
        )
        self.assertTrue(all(item.get("status") == "proposed" for item in items))
        self.assertTrue(
            all(item.get("next_gate") == "human-disposition" for item in items)
        )

    def test_decision_backlog_rejects_missing_source_coverage(self) -> None:
        registry = copy.deepcopy(self.registry)
        backlog = registry.get("decision_backlog")
        self.assertIsInstance(backlog, dict)
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        self.assertIsInstance(items, list)
        assert isinstance(items, list)
        items.pop()
        errors: list[str] = []

        CHECKER._validate_decision_backlog(ROOT, registry, errors)

        self.assertTrue(
            any("decision backlog coverage drift" in error for error in errors)
        )

    def test_decision_backlog_rejects_status_and_dependency_drift(self) -> None:
        cases = (
            ("status", "ADR-0002", "status", "accepted", "source status drift"),
            (
                "dependency",
                "ADR-0016",
                "requires",
                ["ADR-0015", "ADR-9999"],
                "dependency",
            ),
            (
                "forward dependency",
                "ADR-0003",
                "requires",
                ["ADR-0006"],
                "missing or unordered",
            ),
            (
                "omitted source dependency",
                "ADR-0016",
                "requires",
                [],
                "source dependency drift",
            ),
            (
                "non-string dependency",
                "ADR-0016",
                "requires",
                [{"id": "ADR-0015"}],
                "dependencies must be unique sorted ADR ids",
            ),
        )
        for name, decision_id, field, value, expected in cases:
            with self.subTest(name=name):
                registry = copy.deepcopy(self.registry)
                backlog = registry.get("decision_backlog")
                self.assertIsInstance(backlog, dict)
                assert isinstance(backlog, dict)
                items = backlog.get("items")
                self.assertIsInstance(items, list)
                assert isinstance(items, list)
                item = next(entry for entry in items if entry.get("id") == decision_id)
                item[field] = value
                errors: list[str] = []

                CHECKER._validate_decision_backlog(ROOT, registry, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_decision_backlog_rejects_open_shape_and_path_alias(self) -> None:
        cases = (
            (
                "open shape",
                lambda item: item.__setitem__("accepted", True),
                "invalid closed shape",
            ),
            (
                "path alias",
                lambda item: item.__setitem__(
                    "path", "docs/decisions/0003-unified-sdlc-standard.md"
                ),
                "source path is invalid",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                registry = copy.deepcopy(self.registry)
                backlog = registry.get("decision_backlog")
                assert isinstance(backlog, dict)
                items = backlog.get("items")
                assert isinstance(items, list)
                item = next(entry for entry in items if entry.get("id") == "ADR-0002")
                mutate(item)
                errors: list[str] = []

                CHECKER._validate_decision_backlog(ROOT, registry, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_decision_backlog_rejects_non_string_review_group(self) -> None:
        registry = copy.deepcopy(self.registry)
        backlog = registry.get("decision_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        items[0]["review_group"] = {}
        errors: list[str] = []

        CHECKER._validate_decision_backlog(ROOT, registry, errors)

        self.assertTrue(any("review group is invalid" in error for error in errors))

    def test_decision_backlog_human_views_are_registry_joined(self) -> None:
        registry = copy.deepcopy(self.registry)
        backlog = registry.get("decision_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        item = next(entry for entry in items if entry.get("id") == "ADR-0008")
        item["blocks"] = ["unpublished-surface"]
        errors: list[str] = []

        CHECKER._validate_documents(ROOT, registry, errors)

        expected_paths = {
            "docs/portfolio/README.md",
            "docs/implementation-roadmap.md",
        }
        self.assertTrue(
            expected_paths.issubset({error.split(":", 1)[0] for error in errors}),
            errors,
        )

    def test_track_b_spec_backlog_covers_every_source_spec(self) -> None:
        backlog = self.registry.get("track_b_spec_backlog")
        self.assertIsInstance(backlog, dict)
        assert isinstance(backlog, dict)
        self.assertEqual(backlog.get("owner"), "genai-enablement")
        self.assertEqual(backlog.get("status"), "external-evidence-required")

        items = backlog.get("items")
        self.assertIsInstance(items, list)
        assert isinstance(items, list)
        self.assertEqual(
            [item.get("id") for item in items],
            [
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
            ],
        )
        self.assertEqual(
            [item.get("requirements") for item in items],
            [8, 9, 9, 9, 10, 10, 10, 8, 9, 8, 10, 10, 9],
        )
        self.assertEqual(
            [item.get("probes") for item in items],
            [8, 9, 9, 9, 10, 10, 10, 8, 9, 8, 10, 10, 9],
        )
        self.assertTrue(
            all(
                item.get("portable_evidence") == "local-construction-only"
                for item in items
            )
        )
        self.assertTrue(
            all(item.get("operational_state") == "incomplete" for item in items)
        )
        self.assertTrue(
            all(item.get("authority") == "non-authorizing" for item in items)
        )

    def test_b1_portable_traceability_is_exact_and_complete(self) -> None:
        backlog = self.registry.get("track_b_spec_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        b1 = next(item for item in items if item.get("id") == "SPEC-B1")
        remaining = [
            item
            for item in items
            if item.get("id") not in TRACK_B_SPEC_IDS
        ]

        self.assertEqual(
            b1.get("portable_traceability_manifest"),
            SPEC_B1_TRACEABILITY_PATH.as_posix(),
        )
        self.assertTrue(
            all(
                item.get("portable_traceability_manifest") is None for item in remaining
            )
        )

        manifest_errors: list[str] = []
        manifest = CHECKER._load_json(ROOT / SPEC_B1_TRACEABILITY_PATH, manifest_errors)
        self.assertEqual(manifest_errors, [])
        self.assertEqual(manifest, _expected_b1_traceability())

        errors: list[str] = []
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        validator(
            ROOT,
            SPEC_B1_PATH,
            (ROOT / SPEC_B1_PATH).read_text(encoding="utf-8"),
            manifest,
            errors,
        )
        self.assertEqual(errors, [])

    def test_b2_portable_traceability_is_exact_and_complete(self) -> None:
        backlog = self.registry.get("track_b_spec_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        b2 = next(item for item in items if item.get("id") == "SPEC-B2")
        remaining = [
            item
            for item in items
            if item.get("id") not in TRACK_B_SPEC_IDS
        ]

        self.assertEqual(
            b2.get("portable_traceability_manifest"),
            SPEC_B2_TRACEABILITY_PATH.as_posix(),
        )
        self.assertTrue(
            all(
                item.get("portable_traceability_manifest") is None for item in remaining
            )
        )

        manifest_errors: list[str] = []
        manifest = CHECKER._load_json(ROOT / SPEC_B2_TRACEABILITY_PATH, manifest_errors)
        self.assertEqual(manifest_errors, [])
        self.assertEqual(manifest, _expected_b2_traceability())

        errors: list[str] = []
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        validator(
            ROOT,
            SPEC_B2_PATH,
            (ROOT / SPEC_B2_PATH).read_text(encoding="utf-8"),
            manifest,
            errors,
        )
        self.assertEqual(errors, [])

    def test_b3_portable_traceability_is_exact_and_complete(self) -> None:
        backlog = self.registry.get("track_b_spec_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        b3 = next(item for item in items if item.get("id") == "SPEC-B3")
        remaining = [
            item
            for item in items
            if item.get("id") not in TRACK_B_SPEC_IDS
        ]

        self.assertEqual(
            b3.get("portable_traceability_manifest"),
            SPEC_B3_TRACEABILITY_PATH.as_posix(),
        )
        self.assertTrue(
            all(
                item.get("portable_traceability_manifest") is None for item in remaining
            )
        )

        manifest_errors: list[str] = []
        manifest = CHECKER._load_json(ROOT / SPEC_B3_TRACEABILITY_PATH, manifest_errors)
        self.assertEqual(manifest_errors, [])
        self.assertEqual(manifest, _expected_b3_traceability())

        errors: list[str] = []
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        validator(
            ROOT,
            SPEC_B3_PATH,
            (ROOT / SPEC_B3_PATH).read_text(encoding="utf-8"),
            manifest,
            errors,
        )
        self.assertEqual(errors, [])

    def test_b4_portable_traceability_is_exact_and_complete(self) -> None:
        backlog = self.registry.get("track_b_spec_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        b4 = next(item for item in items if item.get("id") == "SPEC-B4")
        remaining = [
            item
            for item in items
            if item.get("id") not in TRACK_B_SPEC_IDS
        ]

        self.assertEqual(
            b4.get("portable_traceability_manifest"),
            SPEC_B4_TRACEABILITY_PATH.as_posix(),
        )
        self.assertTrue(
            all(
                item.get("portable_traceability_manifest") is None for item in remaining
            )
        )

        manifest_errors: list[str] = []
        manifest = CHECKER._load_json(ROOT / SPEC_B4_TRACEABILITY_PATH, manifest_errors)
        self.assertEqual(manifest_errors, [])
        self.assertEqual(manifest, _expected_b4_traceability())

        errors: list[str] = []
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        validator(
            ROOT,
            SPEC_B4_PATH,
            (ROOT / SPEC_B4_PATH).read_text(encoding="utf-8"),
            manifest,
            errors,
        )
        self.assertEqual(errors, [])

    def test_b5_portable_traceability_is_exact_and_complete(self) -> None:
        backlog = self.registry.get("track_b_spec_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        b5 = next(item for item in items if item.get("id") == "SPEC-B5")
        remaining = [
            item
            for item in items
            if item.get("id") not in TRACK_B_SPEC_IDS
        ]

        self.assertEqual(
            b5.get("portable_traceability_manifest"),
            SPEC_B5_TRACEABILITY_PATH.as_posix(),
        )
        self.assertTrue(
            all(
                item.get("portable_traceability_manifest") is None for item in remaining
            )
        )

        manifest_errors: list[str] = []
        manifest = CHECKER._load_json(ROOT / SPEC_B5_TRACEABILITY_PATH, manifest_errors)
        self.assertEqual(manifest_errors, [])
        self.assertEqual(manifest, _expected_b5_traceability())

        errors: list[str] = []
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        validator(
            ROOT,
            SPEC_B5_PATH,
            (ROOT / SPEC_B5_PATH).read_text(encoding="utf-8"),
            manifest,
            errors,
        )
        self.assertEqual(errors, [])

    def test_b6_portable_traceability_is_exact_and_complete(self) -> None:
        backlog = self.registry.get("track_b_spec_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        b6 = next(item for item in items if item.get("id") == "SPEC-B6")
        remaining = [
            item
            for item in items
            if item.get("id") not in TRACK_B_SPEC_IDS
        ]

        self.assertEqual(
            b6.get("portable_traceability_manifest"),
            SPEC_B6_TRACEABILITY_PATH.as_posix(),
        )
        self.assertTrue(
            all(
                item.get("portable_traceability_manifest") is None for item in remaining
            )
        )

        manifest_errors: list[str] = []
        manifest = CHECKER._load_json(ROOT / SPEC_B6_TRACEABILITY_PATH, manifest_errors)
        self.assertEqual(manifest_errors, [])
        self.assertEqual(manifest, _expected_b6_traceability())

        errors: list[str] = []
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        validator(
            ROOT,
            SPEC_B6_PATH,
            (ROOT / SPEC_B6_PATH).read_text(encoding="utf-8"),
            manifest,
            errors,
        )
        self.assertEqual(errors, [])

    def test_b7_portable_traceability_is_exact_and_complete(self) -> None:
        backlog = self.registry.get("track_b_spec_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        b7 = next(item for item in items if item.get("id") == "SPEC-B7")
        remaining = [
            item
            for item in items
            if item.get("id") not in TRACK_B_SPEC_IDS
        ]

        self.assertEqual(
            b7.get("portable_traceability_manifest"),
            SPEC_B7_TRACEABILITY_PATH.as_posix(),
        )
        self.assertTrue(
            all(
                item.get("portable_traceability_manifest") is None for item in remaining
            )
        )

        manifest_errors: list[str] = []
        manifest = CHECKER._load_json(ROOT / SPEC_B7_TRACEABILITY_PATH, manifest_errors)
        self.assertEqual(manifest_errors, [])
        self.assertEqual(manifest, _expected_b7_traceability())

        errors: list[str] = []
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        validator(
            ROOT,
            SPEC_B7_PATH,
            (ROOT / SPEC_B7_PATH).read_text(encoding="utf-8"),
            manifest,
            errors,
        )
        self.assertEqual(errors, [])

    def test_b7_cir_portable_traceability_is_exact_and_complete(self) -> None:
        backlog = self.registry.get("track_b_spec_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        b7_cir = next(item for item in items if item.get("id") == "SPEC-B7-CIR")
        remaining = [
            item
            for item in items
            if item.get("id") not in TRACK_B_SPEC_IDS
        ]

        self.assertEqual(
            b7_cir.get("portable_traceability_manifest"),
            SPEC_B7_CIR_TRACEABILITY_PATH.as_posix(),
        )
        self.assertTrue(
            all(
                item.get("portable_traceability_manifest") is None for item in remaining
            )
        )

        manifest_errors: list[str] = []
        manifest = CHECKER._load_json(
            ROOT / SPEC_B7_CIR_TRACEABILITY_PATH, manifest_errors
        )
        self.assertEqual(manifest_errors, [])
        self.assertEqual(manifest, _expected_b7_cir_traceability())

        errors: list[str] = []
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        validator(
            ROOT,
            SPEC_B7_CIR_PATH,
            (ROOT / SPEC_B7_CIR_PATH).read_text(encoding="utf-8"),
            manifest,
            errors,
        )
        self.assertEqual(errors, [])

    def test_b7_drift_portable_traceability_is_exact_and_complete(self) -> None:
        backlog = self.registry.get("track_b_spec_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        b7_drift = next(item for item in items if item.get("id") == "SPEC-B7-DRIFT")
        remaining = [
            item
            for item in items
            if item.get("id") not in TRACK_B_SPEC_IDS
        ]

        self.assertEqual(remaining, [])
        self.assertEqual(
            b7_drift.get("portable_traceability_manifest"),
            SPEC_B7_DRIFT_TRACEABILITY_PATH.as_posix(),
        )

        manifest_errors: list[str] = []
        manifest = CHECKER._load_json(
            ROOT / SPEC_B7_DRIFT_TRACEABILITY_PATH, manifest_errors
        )
        self.assertEqual(manifest_errors, [])
        self.assertEqual(manifest, _expected_b7_drift_traceability())

        errors: list[str] = []
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        validator(
            ROOT,
            SPEC_B7_DRIFT_PATH,
            (ROOT / SPEC_B7_DRIFT_PATH).read_text(encoding="utf-8"),
            manifest,
            errors,
        )
        self.assertEqual(errors, [])

    def test_formalized_legacy_specs_have_complete_traceability(self) -> None:
        backlog = self.registry.get("track_b_spec_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None

        for spec_id in ("SPEC-B0", "SPEC-B7-CORE", "SPEC-B7-NES", "SPEC-B7-SAT"):
            with self.subTest(spec_id=spec_id):
                item = next(entry for entry in items if entry.get("id") == spec_id)
                spec_path = Path(item["path"])
                manifest_path = Path(item["portable_traceability_manifest"])
                manifest_errors: list[str] = []
                manifest = CHECKER._load_json(ROOT / manifest_path, manifest_errors)
                self.assertEqual(manifest_errors, [])
                errors: list[str] = []

                validator(
                    ROOT,
                    spec_path,
                    (ROOT / spec_path).read_text(encoding="utf-8"),
                    manifest,
                    errors,
                )

                self.assertEqual(errors, [])

    def test_b7_portable_traceability_rejects_drift_and_malformed_values(self) -> None:
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        source_text = (ROOT / SPEC_B7_PATH).read_text(encoding="utf-8")
        cases = (
            (
                "source digest",
                lambda value: value.__setitem__("specSha256", "sha256:" + "0" * 64),
                "SPEC source digest drift",
            ),
            (
                "missing probe",
                lambda value: value["probes"].pop(),
                "probe coverage drift",
            ),
            (
                "missing pytest node",
                lambda value: value["probes"][0].__setitem__(
                    "tests",
                    [
                        "solutions/sre-harness/tests/test_sentinel_error_rate.py::Missing::test_absent"
                    ],
                ),
                "pytest node does not exist",
            ),
            (
                "authority overclaim",
                lambda value: value.__setitem__("authority", "authorizing"),
                "must remain non-authorizing",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                value = _expected_b7_traceability()
                mutate(value)
                errors: list[str] = []

                validator(ROOT, SPEC_B7_PATH, source_text, value, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_b7_cir_portable_traceability_rejects_drift_and_malformed_values(
        self,
    ) -> None:
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        source_text = (ROOT / SPEC_B7_CIR_PATH).read_text(encoding="utf-8")
        cases = (
            (
                "source digest",
                lambda value: value.__setitem__("specSha256", "sha256:" + "0" * 64),
                "SPEC source digest drift",
            ),
            (
                "missing probe",
                lambda value: value["probes"].pop(),
                "probe coverage drift",
            ),
            (
                "missing pytest node",
                lambda value: value["probes"][0].__setitem__(
                    "tests",
                    [
                        "solutions/sre-harness/tests/test_sentinel_change_regression.py::Missing::test_absent"
                    ],
                ),
                "pytest node does not exist",
            ),
            (
                "authority overclaim",
                lambda value: value.__setitem__("authority", "authorizing"),
                "must remain non-authorizing",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                value = _expected_b7_cir_traceability()
                mutate(value)
                errors: list[str] = []

                validator(ROOT, SPEC_B7_CIR_PATH, source_text, value, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_b7_drift_portable_traceability_rejects_drift_and_malformed_values(
        self,
    ) -> None:
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        source_text = (ROOT / SPEC_B7_DRIFT_PATH).read_text(encoding="utf-8")
        cases = (
            (
                "source digest",
                lambda value: value.__setitem__("specSha256", "sha256:" + "0" * 64),
                "SPEC source digest drift",
            ),
            (
                "missing probe",
                lambda value: value["probes"].pop(),
                "probe coverage drift",
            ),
            (
                "missing pytest node",
                lambda value: value["probes"][0].__setitem__(
                    "tests",
                    [
                        "solutions/sre-harness/tests/test_sentinel_drift.py::Missing::test_absent"
                    ],
                ),
                "pytest node does not exist",
            ),
            (
                "authority overclaim",
                lambda value: value.__setitem__("authority", "authorizing"),
                "must remain non-authorizing",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                value = _expected_b7_drift_traceability()
                mutate(value)
                errors: list[str] = []

                validator(ROOT, SPEC_B7_DRIFT_PATH, source_text, value, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_b6_portable_traceability_rejects_drift_and_malformed_values(self) -> None:
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        source_text = (ROOT / SPEC_B6_PATH).read_text(encoding="utf-8")
        cases = (
            (
                "source digest",
                lambda value: value.__setitem__("specSha256", "sha256:" + "0" * 64),
                "SPEC source digest drift",
            ),
            (
                "missing probe",
                lambda value: value["probes"].pop(),
                "probe coverage drift",
            ),
            (
                "missing pytest node",
                lambda value: value["probes"][0].__setitem__(
                    "tests",
                    [
                        "solutions/sre-harness/tests/test_permanent_fix.py::Missing::test_absent"
                    ],
                ),
                "pytest node does not exist",
            ),
            (
                "authority overclaim",
                lambda value: value.__setitem__("authority", "authorizing"),
                "must remain non-authorizing",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                value = _expected_b6_traceability()
                mutate(value)
                errors: list[str] = []

                validator(ROOT, SPEC_B6_PATH, source_text, value, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_track_b_traceability_summary_is_registry_joined(self) -> None:
        expected = (
            "Traceability registry summary: `13` checked manifests; `0` remaining null."
        )
        documents = (
            ROOT / "PROJECT_STATUS.md",
            ROOT / "docs/implementation-roadmap.md",
            ROOT / "docs/specs/README.md",
        )
        for path in documents:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIn(expected, text)

        roadmap = (ROOT / "docs/implementation-roadmap.md").read_text(encoding="utf-8")
        self.assertNotIn("B1 through B5", roadmap)
        self.assertNotIn("remaining four", roadmap)

        original_read_text = CHECKER._read_text

        def omit_roadmap_summary(root: Path, path: Path, errors: list[str]) -> str:
            text = original_read_text(root, path, errors)
            if path == CHECKER.IMPLEMENTATION_ROADMAP_PATH:
                return text.replace(expected, "")
            return text

        with mock.patch.object(CHECKER, "_read_text", side_effect=omit_roadmap_summary):
            errors = CHECKER.check_repository(ROOT)

        self.assertTrue(
            any(
                "docs/implementation-roadmap.md" in error and expected in error
                for error in errors
            ),
            errors,
        )

    def test_b5_portable_traceability_rejects_drift_and_malformed_values(self) -> None:
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        source_text = (ROOT / SPEC_B5_PATH).read_text(encoding="utf-8")
        cases = (
            (
                "source digest",
                lambda value: value.__setitem__("specSha256", "sha256:" + "0" * 64),
                "SPEC source digest drift",
            ),
            (
                "missing probe",
                lambda value: value["probes"].pop(),
                "probe coverage drift",
            ),
            (
                "missing pytest node",
                lambda value: value["probes"][0].__setitem__(
                    "tests",
                    ["solutions/sre-harness/tests/test_hitl.py::Missing::test_absent"],
                ),
                "pytest node does not exist",
            ),
            (
                "authority overclaim",
                lambda value: value.__setitem__("authority", "authorizing"),
                "must remain non-authorizing",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                value = _expected_b5_traceability()
                mutate(value)
                errors: list[str] = []

                validator(ROOT, SPEC_B5_PATH, source_text, value, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_b4_portable_traceability_rejects_drift_and_malformed_values(self) -> None:
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        source_text = (ROOT / SPEC_B4_PATH).read_text(encoding="utf-8")
        cases = (
            (
                "source digest",
                lambda value: value.__setitem__("specSha256", "sha256:" + "0" * 64),
                "SPEC source digest drift",
            ),
            (
                "missing probe",
                lambda value: value["probes"].pop(),
                "probe coverage drift",
            ),
            (
                "missing pytest node",
                lambda value: value["probes"][0].__setitem__(
                    "tests",
                    [
                        "solutions/sre-harness/tests/test_remediation.py::Missing::test_absent"
                    ],
                ),
                "pytest node does not exist",
            ),
            (
                "authority overclaim",
                lambda value: value.__setitem__("authority", "authorizing"),
                "must remain non-authorizing",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                value = _expected_b4_traceability()
                mutate(value)
                errors: list[str] = []

                validator(ROOT, SPEC_B4_PATH, source_text, value, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_b3_portable_traceability_rejects_drift_and_malformed_values(self) -> None:
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        source_text = (ROOT / SPEC_B3_PATH).read_text(encoding="utf-8")
        cases = (
            (
                "source digest",
                lambda value: value.__setitem__("specSha256", "sha256:" + "0" * 64),
                "SPEC source digest drift",
            ),
            (
                "missing probe",
                lambda value: value["probes"].pop(),
                "probe coverage drift",
            ),
            (
                "missing pytest node",
                lambda value: value["probes"][0].__setitem__(
                    "tests",
                    [
                        "solutions/sre-harness/tests/test_rollback.py::Missing::test_absent"
                    ],
                ),
                "pytest node does not exist",
            ),
            (
                "authority overclaim",
                lambda value: value.__setitem__("authority", "authorizing"),
                "must remain non-authorizing",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                value = _expected_b3_traceability()
                mutate(value)
                errors: list[str] = []

                validator(ROOT, SPEC_B3_PATH, source_text, value, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_b2_portable_traceability_rejects_drift_and_malformed_values(self) -> None:
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        source_text = (ROOT / SPEC_B2_PATH).read_text(encoding="utf-8")
        cases = (
            (
                "source digest",
                lambda value: value.__setitem__("specSha256", "sha256:" + "0" * 64),
                "SPEC source digest drift",
            ),
            (
                "missing probe",
                lambda value: value["probes"].pop(),
                "probe coverage drift",
            ),
            (
                "missing pytest node",
                lambda value: value["probes"][0].__setitem__(
                    "tests",
                    [
                        "solutions/sre-harness/tests/test_advisory_integration.py::Missing::test_absent"
                    ],
                ),
                "pytest node does not exist",
            ),
            (
                "authority overclaim",
                lambda value: value.__setitem__("authority", "authorizing"),
                "must remain non-authorizing",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                value = _expected_b2_traceability()
                mutate(value)
                errors: list[str] = []

                validator(ROOT, SPEC_B2_PATH, source_text, value, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_b1_portable_traceability_rejects_drift_and_malformed_values(self) -> None:
        validator = getattr(CHECKER, "_validate_track_b_traceability_value", None)
        self.assertIsNotNone(validator)
        assert validator is not None
        source_text = (ROOT / SPEC_B1_PATH).read_text(encoding="utf-8")
        cases = (
            (
                "closed shape",
                lambda value: value.__setitem__("unexpected", "value"),
                "manifest must be a closed object",
            ),
            (
                "source digest",
                lambda value: value.__setitem__("specSha256", "sha256:" + "0" * 64),
                "SPEC source digest drift",
            ),
            (
                "missing probe",
                lambda value: value["probes"].pop(),
                "probe coverage drift",
            ),
            (
                "duplicate probe",
                lambda value: value["probes"].append(copy.deepcopy(value["probes"][0])),
                "probe coverage drift",
            ),
            (
                "missing pytest node",
                lambda value: value["probes"][0].__setitem__(
                    "tests",
                    sorted(
                        [
                            *value["probes"][0]["tests"],
                            "solutions/sre-harness/tests/test_triage_source.py::Missing::test_absent",
                        ]
                    ),
                ),
                "pytest node does not exist",
            ),
            (
                "test path escape",
                lambda value: value["probes"][0].__setitem__(
                    "tests", ["../test_escape.py::test_absent"]
                ),
                "pytest node path is invalid",
            ),
            (
                "implementation path escape",
                lambda value: value.__setitem__(
                    "implementationPaths", ["../implementation.py"]
                ),
                "implementation path is invalid",
            ),
            (
                "live evidence overclaim",
                lambda value: value.__setitem__("evidenceScope", "live"),
                "evidence scope must remain local-portable-only",
            ),
            (
                "operational overclaim",
                lambda value: value.__setitem__("operationalState", "complete"),
                "operational state must remain incomplete",
            ),
            (
                "authority overclaim",
                lambda value: value.__setitem__("authority", "authorizing"),
                "must remain non-authorizing",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                value = _expected_b1_traceability()
                mutate(value)
                errors: list[str] = []

                validator(ROOT, SPEC_B1_PATH, source_text, value, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_track_b_spec_backlog_rejects_source_drift(self) -> None:
        cases = (
            (
                "status",
                "SPEC-B3",
                "source_status",
                "accepted",
                "source status drift",
            ),
            (
                "roadmap gate",
                "SPEC-B5",
                "stage",
                "B6",
                "source roadmap gate drift",
            ),
            (
                "requirements",
                "SPEC-B4",
                "requirements",
                9,
                "requirement count drift",
            ),
            (
                "probes",
                "SPEC-B6",
                "probes",
                9,
                "probe count drift",
            ),
            (
                "dependency",
                "SPEC-B7-CIR",
                "requires",
                [],
                "source dependency drift",
            ),
            (
                "forward dependency",
                "SPEC-B1",
                "requires",
                ["SPEC-B6"],
                "missing or unordered",
            ),
        )
        for name, spec_id, field, value, expected in cases:
            with self.subTest(name=name):
                registry = copy.deepcopy(self.registry)
                backlog = registry.get("track_b_spec_backlog")
                assert isinstance(backlog, dict)
                items = backlog.get("items")
                assert isinstance(items, list)
                item = next(entry for entry in items if entry.get("id") == spec_id)
                item[field] = value
                errors: list[str] = []

                CHECKER._validate_track_b_spec_backlog(ROOT, registry, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_track_b_spec_backlog_rejects_coverage_path_and_malformed_data(
        self,
    ) -> None:
        cases = (
            (
                "non-list items",
                lambda backlog: backlog.__setitem__("items", None),
                "SPEC backlog items must be a list",
            ),
            (
                "missing coverage",
                lambda backlog: backlog["items"].pop(),
                "SPEC backlog coverage drift",
            ),
            (
                "path alias",
                lambda backlog: backlog["items"][0].__setitem__(
                    "path",
                    "docs/specs/SPEC-B2-advisory-change-validation-integration.md",
                ),
                "source path is invalid",
            ),
            (
                "non-string dependency",
                lambda backlog: backlog["items"][7].__setitem__("requires", [{}]),
                "dependencies must be unique sorted ids",
            ),
            (
                "boolean count",
                lambda backlog: backlog["items"][0].__setitem__("requirements", True),
                "requirement count must be a positive integer",
            ),
            (
                "non-string next gate",
                lambda backlog: backlog["items"][0].__setitem__("next_gate", {}),
                "next gate is invalid",
            ),
            (
                "missing B1 traceability",
                lambda backlog: backlog["items"][1].__setitem__(
                    "portable_traceability_manifest", None
                ),
                "portable traceability path drift",
            ),
            (
                "wrong B7-DRIFT traceability",
                lambda backlog: backlog["items"][11].__setitem__(
                    "portable_traceability_manifest",
                    SPEC_B1_TRACEABILITY_PATH.as_posix(),
                ),
                "portable traceability path drift",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                registry = copy.deepcopy(self.registry)
                backlog = registry.get("track_b_spec_backlog")
                assert isinstance(backlog, dict)
                mutate(backlog)
                errors: list[str] = []

                CHECKER._validate_track_b_spec_backlog(ROOT, registry, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_track_b_spec_human_view_is_registry_joined(self) -> None:
        registry = copy.deepcopy(self.registry)
        backlog = registry.get("track_b_spec_backlog")
        assert isinstance(backlog, dict)
        items = backlog.get("items")
        assert isinstance(items, list)
        item = next(entry for entry in items if entry.get("id") == "SPEC-B3")
        item["next_gate"] = "unpublished-gate"
        errors: list[str] = []

        CHECKER._validate_documents(ROOT, registry, errors)

        self.assertTrue(
            any(error.startswith("docs/specs/README.md:") for error in errors),
            errors,
        )

    def test_track_b_spec_source_parsers_are_closed_and_contiguous(self) -> None:
        valid = "\n".join(
            (
                "[REQ-BX-1] first",
                "[REQ-BX-2] second",
                "- **P-BX-1 first:** probe",
                "- **P-BX-2 second:** probe",
            )
        )
        self.assertEqual(CHECKER._spec_contract_count(valid, "requirement"), ("BX", 2))
        self.assertEqual(CHECKER._spec_contract_count(valid, "probe"), ("BX", 2))
        self.assertEqual(CHECKER._spec_probe_ids(valid), ("P-BX-1", "P-BX-2"))
        self.assertEqual(
            CHECKER._spec_contract_count(
                valid + "\n[REQ-BX-2] duplicate", "requirement"
            ),
            (None, None),
        )
        self.assertEqual(
            CHECKER._spec_contract_count(
                "[REQ-BX-1] first\n[REQ-BX-3] gap", "requirement"
            ),
            (None, None),
        )
        self.assertEqual(
            CHECKER._spec_probe_ids(valid + "\n- **P-BX-2 duplicate:** probe"),
            (),
        )
        dependency_block = "\n".join(
            (
                "**Depends on:** SPEC-B1, ADR-0003",
                "**Authority:** SPEC-B7",
                "",
            )
        )
        self.assertEqual(
            CHECKER._spec_dependencies(dependency_block),
            ["ADR-0003", "SPEC-B1"],
        )

    def test_tool_count_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        omniscience = CHECKER._project_by_id(registry, "omniscience")
        assert omniscience is not None
        omniscience["mcp"]["target_tool_count"] = 14
        errors: list[str] = []

        CHECKER._validate_registry(registry, errors)

        self.assertTrue(any("target_tool_count" in error for error in errors))

    def test_spec_index_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        omniscience = CHECKER._project_by_id(registry, "omniscience")
        assert omniscience is not None
        omniscience["spec_index"][-1]["status"] = "ready"
        errors: list[str] = []

        CHECKER._validate_registry(registry, errors)

        self.assertTrue(any("task SPEC index" in error for error in errors))

    def test_terminal_evidence_requires_full_commit(self) -> None:
        registry = copy.deepcopy(self.registry)
        omniscience = CHECKER._project_by_id(registry, "omniscience")
        assert omniscience is not None
        omniscience["execution_evidence"][0]["merge_commit"] = "d050eba"
        errors: list[str] = []

        CHECKER._validate_registry(registry, errors)

        self.assertTrue(any("needs a full commit" in error for error in errors))

    def test_omnius_registry_exposes_bounded_readiness_state(self) -> None:
        omnius = CHECKER._project_by_id(self.registry, "omnius")
        assert omnius is not None

        self.assertEqual(
            omnius.get("roadmap"),
            {
                "status": "control-plane-implementation",
                "page": "docs/portfolio/omnius.md",
            },
        )
        self.assertEqual(
            omnius.get("readiness", {}).get("profile"),
            {
                "id": "p0-standard-http-service-v3",
                "status": "draft",
                "assurance_profile": "P0",
                "platform_path": "standard-http-service/v3",
                "source_path": "specs/readiness/p0-standard-http-service-v3.json",
                "source_sha256": "sha256:30d81c62c67d96ee7ef46d3db2f78e97255cdfe595440412ea12910469060ede",
                "selected_capabilities": 15,
                "selected_requirements": 129,
                "selected_probes": 126,
                "readiness_blockers": 11,
                "forbidden_actions": 14,
            },
        )
        self.assertEqual(
            omnius.get("readiness", {}).get("local_verification"),
            {
                "evidence_scope": "dirty-worktree-local",
                "inspected_head": "a32fecd35588a10bd5453af4244c6fc219c7527f",
                "worktree_publication_status": "dirty-unpublished",
                "acceptance_tests_passed": 1025,
                "environment_qualified_skips": 2,
                "portable_probes_passed": 290,
                "human_waivers": 3,
                "target_profile_failures": 3,
                "contract_conformance": "conformant",
                "assurance_certification": "red",
                "activation": "blocked",
            },
        )
        self.assertTrue((ROOT / "docs/portfolio/omnius.md").is_file())

    def test_omnius_draft_or_unpublished_evidence_cannot_claim_activation(self) -> None:
        registry = copy.deepcopy(self.registry)
        omnius = CHECKER._project_by_id(registry, "omnius")
        assert omnius is not None
        omnius["readiness"] = {
            "profile": {
                "id": "p0-standard-http-service-v3",
                "status": "draft",
                "assurance_profile": "P0",
                "platform_path": "standard-http-service/v3",
                "source_path": "specs/readiness/p0-standard-http-service-v3.json",
                "source_sha256": "sha256:30d81c62c67d96ee7ef46d3db2f78e97255cdfe595440412ea12910469060ede",
                "selected_capabilities": 15,
                "selected_requirements": 129,
                "selected_probes": 126,
                "readiness_blockers": 11,
                "forbidden_actions": 14,
            },
            "local_verification": {
                "evidence_scope": "dirty-worktree-local",
                "inspected_head": "a32fecd35588a10bd5453af4244c6fc219c7527f",
                "worktree_publication_status": "dirty-unpublished",
                "acceptance_tests_passed": 1025,
                "environment_qualified_skips": 2,
                "portable_probes_passed": 290,
                "human_waivers": 3,
                "target_profile_failures": 3,
                "contract_conformance": "conformant",
                "assurance_certification": "red",
                "activation": "active",
            },
        }
        errors: list[str] = []

        CHECKER._validate_registry(registry, errors)

        self.assertTrue(
            any("Omnius activation must remain blocked" in error for error in errors)
        )

    def test_omnius_page_tracks_verification_counts(self) -> None:
        registry = copy.deepcopy(self.registry)
        omnius = CHECKER._project_by_id(registry, "omnius")
        assert omnius is not None
        omnius.setdefault("readiness", {}).setdefault("local_verification", {})[
            "acceptance_tests_passed"
        ] = 1026
        errors: list[str] = []

        CHECKER._validate_documents(ROOT, registry, errors)

        self.assertTrue(any("docs/portfolio/omnius.md" in error for error in errors))

    def test_malformed_omnius_blocker_count_fails_without_crashing(self) -> None:
        registry = copy.deepcopy(self.registry)
        omnius = CHECKER._project_by_id(registry, "omnius")
        assert omnius is not None
        omnius["readiness"]["profile"]["readiness_blockers"] = "eleven"
        errors: list[str] = []

        CHECKER._validate_registry(registry, errors)

        self.assertTrue(
            any(
                "readiness_blockers must be a positive integer" in error
                for error in errors
            )
        )

    def test_omnius_registry_rejects_malformed_state_matrix(self) -> None:
        cases = [
            (
                "missing project",
                lambda registry, _omnius: registry.__setitem__(
                    "projects",
                    [
                        item
                        for item in registry["projects"]
                        if item.get("id") != "omnius"
                    ],
                ),
                "omnius project is required",
            ),
            (
                "roadmap status",
                lambda _registry, omnius: omnius["roadmap"].__setitem__(
                    "status", "ready"
                ),
                "portfolio and roadmap statuses differ",
            ),
            (
                "roadmap page",
                lambda _registry, omnius: omnius["roadmap"].__setitem__(
                    "page", "elsewhere.md"
                ),
                "roadmap must name its portfolio page",
            ),
            (
                "document index",
                lambda _registry, omnius: omnius["canonical_documents"].pop("runbooks"),
                "canonical document index is incomplete",
            ),
            (
                "foreign document",
                lambda _registry, omnius: omnius["canonical_documents"].__setitem__(
                    "runbooks", "https://example.invalid/runbooks"
                ),
                "canonical documents must stay component-owned",
            ),
            (
                "initiative order",
                lambda _registry, omnius: omnius["initiatives"].reverse(),
                "initiative index is incomplete or unordered",
            ),
            (
                "empty blockers",
                lambda _registry, omnius: omnius.__setitem__("blockers", []),
                "must publish non-empty readiness blockers",
            ),
            (
                "profile id",
                lambda _registry, omnius: omnius["readiness"]["profile"].__setitem__(
                    "id", "p0-standard-http-service-v2"
                ),
                "profile id is not the bounded v3 slice",
            ),
            (
                "assurance profile",
                lambda _registry, omnius: omnius["readiness"]["profile"].__setitem__(
                    "assurance_profile", "P1"
                ),
                "assurance profile must be P0",
            ),
            (
                "platform path",
                lambda _registry, omnius: omnius["readiness"]["profile"].__setitem__(
                    "platform_path", "standard-http-service/v2"
                ),
                "PlatformPath must be v3",
            ),
            (
                "profile count",
                lambda _registry, omnius: omnius["readiness"]["profile"].__setitem__(
                    "selected_capabilities", False
                ),
                "selected_capabilities must be a positive integer",
            ),
            (
                "evidence scope",
                lambda _registry, omnius: omnius["readiness"][
                    "local_verification"
                ].__setitem__("evidence_scope", "caller-asserted"),
                "evidence scope is unknown",
            ),
            (
                "publication state",
                lambda _registry, omnius: omnius["readiness"][
                    "local_verification"
                ].__setitem__("worktree_publication_status", "published"),
                "worktree publication status is unknown",
            ),
            (
                "short revision",
                lambda _registry, omnius: omnius["readiness"][
                    "local_verification"
                ].__setitem__("inspected_head", "a32fecd"),
                "inspected HEAD must be a full Git commit",
            ),
            (
                "negative verification count",
                lambda _registry, omnius: omnius["readiness"][
                    "local_verification"
                ].__setitem__("portable_probes_passed", -1),
                "portable_probes_passed must be non-negative",
            ),
            (
                "boolean verification count",
                lambda _registry, omnius: omnius["readiness"][
                    "local_verification"
                ].__setitem__("human_waivers", True),
                "human_waivers must be non-negative",
            ),
            (
                "conformance decision",
                lambda _registry, omnius: omnius["readiness"][
                    "local_verification"
                ].__setitem__("contract_conformance", "unknown"),
                "contract-conformance decision is invalid",
            ),
            (
                "assurance decision",
                lambda _registry, omnius: omnius["readiness"][
                    "local_verification"
                ].__setitem__("assurance_certification", "unknown"),
                "assurance-certification decision is invalid",
            ),
            (
                "dirty release",
                lambda _registry, omnius: omnius["current_release"].__setitem__(
                    "version", "v1.0.0"
                ),
                "dirty Omnius evidence cannot claim a release",
            ),
        ]

        for label, mutate, expected in cases:
            with self.subTest(label=label):
                registry = copy.deepcopy(self.registry)
                omnius = CHECKER._project_by_id(registry, "omnius")
                assert omnius is not None
                mutate(registry, omnius)
                errors: list[str] = []

                CHECKER._validate_omnius(registry, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_base_registry_rejects_malformed_state_matrix(self) -> None:
        cases = [
            (
                "schema version",
                lambda registry, _omniscience: registry.__setitem__(
                    "schema_version", 2
                ),
                "schema_version must be 1",
            ),
            (
                "as of",
                lambda registry, _omniscience: registry.__setitem__("as_of", "today"),
                "as_of must be YYYY-MM-DD",
            ),
            (
                "authority",
                lambda registry, _omniscience: registry.__setitem__("authority", {}),
                "authority must define",
            ),
            (
                "project field",
                lambda _registry, omniscience: omniscience.pop("role"),
                "is missing role",
            ),
            (
                "repository url",
                lambda _registry, omniscience: omniscience.__setitem__(
                    "repository", "local"
                ),
                "needs a GitHub repository URL",
            ),
            (
                "owners",
                lambda _registry, omniscience: omniscience.__setitem__("owners", {}),
                "needs component/portfolio owners",
            ),
            (
                "roadmap status",
                lambda _registry, omniscience: omniscience["roadmap"].__setitem__(
                    "status", "ready"
                ),
                "Omniscience portfolio and roadmap statuses differ",
            ),
            (
                "contract semver",
                lambda _registry, omniscience: omniscience["mcp"].__setitem__(
                    "target_contract_version", "v1"
                ),
                "MCP target contract must be stable semver",
            ),
            (
                "tool registry type",
                lambda _registry, omniscience: omniscience["mcp"].__setitem__(
                    "target_tool_registry", "not-a-list"
                ),
                "target_tool_registry must contain tool names",
            ),
            (
                "tool order",
                lambda _registry, omniscience: omniscience["mcp"][
                    "target_tool_registry"
                ].reverse(),
                "target_tool_registry must be sorted",
            ),
            (
                "duplicate tool",
                lambda _registry, omniscience: omniscience["mcp"][
                    "target_tool_registry"
                ].append("search"),
                "target_tool_registry contains duplicates",
            ),
            (
                "token profile",
                lambda _registry, omniscience: omniscience["mcp"][
                    "token_profile"
                ].__setitem__("exact_scopes", ["search", "admin"]),
                "bootstrap token profile differs",
            ),
            (
                "initiative index",
                lambda _registry, omniscience: omniscience["initiatives"].reverse(),
                "initiative index must be 230, 244, 350",
            ),
            (
                "initiative progress",
                lambda _registry, omniscience: omniscience["initiatives"][
                    0
                ].__setitem__("completed_tasks", 13),
                "issue 230 must record 12/13 complete",
            ),
            (
                "capability spec",
                lambda _registry, omniscience: omniscience["spec_index"][0].__setitem__(
                    "status", "ready"
                ),
                "SPEC index must contain one valid SPEC-MCP capability",
            ),
            (
                "evidence id",
                lambda _registry, omniscience: omniscience["execution_evidence"][
                    0
                ].__setitem__("id", ""),
                "execution evidence ids must be present and unique",
            ),
            (
                "evidence PR",
                lambda _registry, omniscience: omniscience["execution_evidence"][
                    0
                ].__setitem__("pull_request", "local"),
                "needs a PR",
            ),
            (
                "evidence verification",
                lambda _registry, omniscience: omniscience["execution_evidence"][
                    0
                ].__setitem__("verification", ""),
                "needs verification authority",
            ),
        ]

        for label, mutate, expected in cases:
            with self.subTest(label=label):
                registry = copy.deepcopy(self.registry)
                omniscience = CHECKER._project_by_id(registry, "omniscience")
                assert omniscience is not None
                mutate(registry, omniscience)
                errors: list[str] = []

                CHECKER._validate_registry(registry, errors)

                self.assertTrue(any(expected in error for error in errors), errors)

    def _build_component_fixture(
        self, root: Path, registry: dict, *, dirty: bool = True
    ) -> Path:
        profile_path = root / "specs/readiness/p0-standard-http-service-v3.json"
        profile_path.parent.mkdir(parents=True)
        capabilities = []
        for index in range(15):
            requirement_count = 9 if index < 9 else 8
            probe_count = 9 if index < 6 else 8
            capabilities.append(
                {
                    "id": f"SPEC-{index}",
                    "requirements": [
                        f"REQ-{index}-{item}" for item in range(requirement_count)
                    ],
                    "probes": [f"P-{index}-{item}" for item in range(probe_count)],
                }
            )
        profile = {
            "metadata": {
                "name": "p0-standard-http-service-v3",
                "status": "draft",
            },
            "spec": {
                "assuranceProfile": "P0",
                "scope": {"platformPath": "standard-http-service/v3"},
                "capabilities": capabilities,
                "readinessBlockers": [f"blocker-{item}" for item in range(11)],
                "forbiddenActions": [f"action-{item}" for item in range(14)],
            },
        }
        profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")

        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(
            ["git", "add", str(profile_path.relative_to(root))], cwd=root, check=True
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Portfolio Test",
                "-c",
                "user.email=portfolio-test@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            cwd=root,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()

        omnius = CHECKER._project_by_id(registry, "omnius")
        assert omnius is not None
        omnius["readiness"]["profile"]["source_path"] = str(
            profile_path.relative_to(root)
        )
        omnius["readiness"]["profile"]["source_sha256"] = f"sha256:{digest}"
        omnius["readiness"]["local_verification"]["inspected_head"] = head
        if dirty:
            (root / "unpublished.txt").write_text("dirty\n", encoding="utf-8")
        else:
            omnius["readiness"]["local_verification"][
                "worktree_publication_status"
            ] = "clean-immutable"
            omnius["readiness"]["local_verification"][
                "evidence_scope"
            ] = "immutable-component"
        return profile_path

    def test_component_observation_matches_registry_snapshot(self) -> None:
        registry = copy.deepcopy(self.registry)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._build_component_fixture(root, registry)
            errors: list[str] = []

            CHECKER._validate_omnius_component(root, registry, errors)

        self.assertEqual(errors, [])

    def test_component_observation_rejects_profile_count_drift(self) -> None:
        registry = copy.deepcopy(self.registry)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = self._build_component_fixture(root, registry)
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["spec"]["readinessBlockers"].pop()
            profile_path.write_text(
                json.dumps(profile, indent=2) + "\n", encoding="utf-8"
            )
            digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
            omnius = CHECKER._project_by_id(registry, "omnius")
            assert omnius is not None
            omnius["readiness"]["profile"]["source_sha256"] = f"sha256:{digest}"
            errors: list[str] = []

            CHECKER._validate_omnius_component(root, registry, errors)

        self.assertTrue(
            any("readiness_blockers drift" in error for error in errors), errors
        )

    def test_component_profile_loader_rejects_untrusted_json_shapes(self) -> None:
        cases = [
            (b"", "empty or exceeds"),
            (b'{"value": 1, "value": 2}\n', "duplicate JSON key"),
            (b'{"value": NaN}\n', "non-finite JSON number"),
            (b"not-json\n", "not strict JSON"),
            (b"[]\n", "root must be an object"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "profile.json"
            for raw, expected in cases:
                with self.subTest(expected=expected):
                    path.write_bytes(raw)
                    errors: list[str] = []

                    result = CHECKER._load_component_profile(path, errors)

                    self.assertIsNone(result)
                    self.assertTrue(any(expected in error for error in errors), errors)

    def test_component_observation_rejects_digest_head_and_state_drift(self) -> None:
        registry = copy.deepcopy(self.registry)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._build_component_fixture(root, registry)
            omnius = CHECKER._project_by_id(registry, "omnius")
            assert omnius is not None
            profile = omnius["readiness"]["profile"]
            verification = omnius["readiness"]["local_verification"]
            profile["source_sha256"] = "sha256:" + ("0" * 64)
            verification["inspected_head"] = "1" * 40
            verification["worktree_publication_status"] = "clean-immutable"
            verification["evidence_scope"] = "immutable-component"
            errors: list[str] = []

            CHECKER._validate_omnius_component(root, registry, errors)

        for expected in (
            "source_sha256 drift",
            "inspected_head drift",
            "worktree publication status drift",
            "evidence scope drift",
        ):
            self.assertTrue(any(expected in error for error in errors), errors)

    def test_component_observation_rejects_unsafe_or_missing_roots(self) -> None:
        registry = copy.deepcopy(self.registry)
        omnius = CHECKER._project_by_id(registry, "omnius")
        assert omnius is not None
        omnius["readiness"]["profile"]["source_path"] = "../outside.json"
        with tempfile.TemporaryDirectory() as temp_dir:
            errors: list[str] = []
            CHECKER._validate_omnius_component(Path(temp_dir), registry, errors)
        self.assertTrue(
            any("canonical relative path" in error for error in errors), errors
        )

        missing_errors: list[str] = []
        CHECKER._validate_omnius_component(
            ROOT / "does-not-exist", self.registry, missing_errors
        )
        self.assertTrue(any("root does not exist" in error for error in missing_errors))

    def test_implementation_roadmap_tracks_current_spec_driven_execution(self) -> None:
        roadmap = (ROOT / "docs/implementation-roadmap.md").read_text(encoding="utf-8")
        required_facts = (
            "## Track A — Organizational Dark Factory P0",
            "## Track B — Autonomous SRE harness",
            "## Track C — Enablement pilot",
            "`p0-standard-http-service-v3`",
            "`direct-source-fallback`",
            "contract conformance is `CONFORMANT`",
            "assurance certification remains `RED`",
            "`genai-enablement`",
            "`omnius`",
            "`Omniscience`",
            "`platform-design`",
            "`platform-workflows`",
            "`platform-portal`",
            "`multiqlti`",
            "python3 scripts/check_portfolio_drift.py --omnius-root ../omnius",
        )
        for fact in required_facts:
            with self.subTest(fact=fact):
                self.assertIn(fact, roadmap)

        dependency_markers = [f"| `A{item}` |" for item in range(8)]
        positions = [roadmap.index(marker) for marker in dependency_markers]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("Phase 1: Foundation (Months 1-2)", roadmap)

    def test_b1_implementation_is_bound_to_its_component_spec(self) -> None:
        spec_path = ROOT / "docs/specs/SPEC-B1-read-only-triage-rca.md"
        spec = spec_path.read_text(encoding="utf-8")
        normalized_spec = " ".join(spec.split()).casefold()
        roadmap = (ROOT / "docs/implementation-roadmap.md").read_text(encoding="utf-8")
        status = (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")

        self.assertIn("specs/SPEC-B1-read-only-triage-rca.md", roadmap)
        self.assertIn("docs/specs/SPEC-B1-read-only-triage-rca.md", status)
        for item in range(1, 10):
            with self.subTest(requirement=item):
                self.assertIn(f"[REQ-B1-{item}]", spec)
                self.assertIn(f"**P-B1-{item} ", spec)
        for boundary in (
            "maximum authority is autonomy tier `T1`",
            "no action, remediation, credential, approval, or execution field",
            "opaque externally verified corpus publication capability",
            "No fixture, local file, test double, or agent-authored value",
        ):
            with self.subTest(boundary=boundary):
                self.assertIn(boundary.casefold(), normalized_spec)

    def test_b2_integration_is_bound_to_its_component_spec(self) -> None:
        spec_path = (
            ROOT / "docs/specs/SPEC-B2-advisory-change-validation-integration.md"
        )
        spec = spec_path.read_text(encoding="utf-8")
        normalized_spec = " ".join(spec.split()).casefold()
        roadmap = (ROOT / "docs/implementation-roadmap.md").read_text(encoding="utf-8")
        status = (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")

        self.assertIn(
            "specs/SPEC-B2-advisory-change-validation-integration.md", roadmap
        )
        self.assertIn(
            "docs/specs/SPEC-B2-advisory-change-validation-integration.md",
            status,
        )
        for item in range(1, 10):
            with self.subTest(requirement=item):
                self.assertIn(f"[REQ-B2-{item}]", spec)
                self.assertIn(f"**P-B2-{item} ", spec)
        for boundary in (
            "analysis is autonomy tier `T1`; the recommendation is `T2`",
            "`mutationAuthorized: false`",
            "no pipe such as `| tee` may overwrite the command status",
            "Fixtures and templates are not live integration evidence",
        ):
            with self.subTest(boundary=boundary):
                self.assertIn(boundary.casefold(), normalized_spec)


if __name__ == "__main__":
    unittest.main()
