from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from sre_harness.hitl import (
    HITL_PROPOSAL_SCHEMA,
    HITL_RECEIPT_SCHEMA,
    AutomationApprovalSignalCall,
    AutomationApprovalSnapshot,
    AutomationApprovalStatus,
    AwsApprovalClientBinding,
    GitlabApprovalClientBinding,
    GitlabApprovalRuleSnapshot,
    GitlabApprovalSnapshot,
    HitlApprovalGate,
    HitlApprovalReceipt,
    HitlAuditEvent,
    HitlCase,
    HitlCaseState,
    HitlExecutionError,
    HitlMechanism,
    HitlPolicyError,
    HitlReceiptDecision,
    HitlRemediationProposal,
    VerifiedHitlApprovalReceipt,
    apply_hitl_receipt,
    authorize_hitl_proposal,
    hitl_action_tier_revision,
    load_hitl_proposal,
    load_hitl_receipt,
    parse_hitl_proposal,
    parse_hitl_receipt,
    reconcile_hitl_case,
)

NOW = datetime(2026, 7, 16, 10, 30, tzinfo=UTC)
PROPOSAL_ID = "bcd76f60-bec4-4caf-8eb1-80a6cdfc5ac4"
RECEIPT_ID = "b3dc5287-393d-41dd-adb8-d46c192a674e"
EXECUTION_ID = "35878d6b-2bd4-40ff-9127-7f8bd3c211b3"
ACCOUNT_ID = "123456789012"
REGION = "eu-west-1"
ORIGIN = "https://approvals.example.invalid/v1"
VERIFIER_REF = "verifier://human-approval/v1"
HUMAN_REVIEWER = "human:platform-sre/alice"
PROPOSER = "agent:sre-harness"
SHA_A = f"sha256:{'a' * 64}"
SHA_B = f"sha256:{'b' * 64}"
SHA_C = f"sha256:{'c' * 64}"
GIT_SHA = "d" * 40
ROOT = Path(__file__).resolve().parents[1]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _revision(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value)).hexdigest()}"


def _parameters() -> dict[str, list[str]]:
    return {
        "AutomationAssumeRole": [f"arn:aws:iam::{ACCOUNT_ID}:role/sre-hitl-automation"],
        "ChangeId": ["chg-2026-0716-001"],
        "Service": ["payments-api"],
    }


def _aws_subject(parameters: dict[str, list[str]]) -> dict[str, object]:
    return {
        "type": "aws_ssm",
        "awsAccountId": ACCOUNT_ID,
        "region": REGION,
        "automationExecutionId": EXECUTION_ID,
        "documentName": "SRE-ConfigChangeProd-WithApproval",
        "documentVersion": "7",
        "documentSha256": SHA_A,
        "schemaVersion": "0.3",
        "approvalStepName": "approveChange",
        "approvalFirst": True,
        "inputRevision": _revision(parameters),
    }


def _gitlab_subject() -> dict[str, object]:
    return {
        "type": "gitlab_mr",
        "instanceOrigin": "https://gitlab.example.invalid",
        "projectId": 42,
        "mergeRequestIid": 7,
        "sourceSha": GIT_SHA,
        "targetBranch": "main",
        "protectedBranchRevision": SHA_A,
        "approvalRulesRevision": SHA_B,
        "approvalSettingsRevision": SHA_C,
    }


def _proposal_payload(
    *,
    mechanism: str = "aws_ssm",
    action: str = "config_change_prod",
    confidence: str = "0.9",
    proposer: str = PROPOSER,
    created_at: str = "2026-07-16T10:00:00Z",
    expires_at: str = "2026-07-16T12:00:00Z",
) -> dict[str, object]:
    parameters = _parameters()
    subject = _aws_subject(parameters) if mechanism == "aws_ssm" else _gitlab_subject()
    proposal: dict[str, object] = {
        "proposalId": PROPOSAL_ID,
        "createdAt": created_at,
        "expiresAt": expires_at,
        "proposerPrincipal": proposer,
        "triggerId": "incident:INC-2048",
        "planRevision": SHA_B,
        "actionTierRevision": hitl_action_tier_revision(),
        "action": action,
        "confidence": confidence,
        "environment": "production",
        "parameters": parameters,
        "mechanism": mechanism,
        "subject": subject,
        "subjectRevision": _revision(
            {"action": action, "parameters": parameters, "subject": subject}
        ),
        "evidenceRefs": [
            "evidence://change/2048",
            "evidence://incident/INC-2048",
        ],
        "riskSummary": "One production configuration change scoped to payments-api.",
        "rollbackRef": "runbook://payments-api/config-rollback/v3",
        "rollbackRevision": SHA_C,
    }
    return {
        "schemaVersion": HITL_PROPOSAL_SCHEMA,
        "proposalRevision": _revision(proposal),
        "proposal": proposal,
    }


def _receipt_payload(
    proposal_payload: dict[str, object] | None = None,
    *,
    decision: str = "approved",
    evidence_scope: str = "external_candidate",
    reviewer: str = HUMAN_REVIEWER,
    decided_at: str = "2026-07-16T10:20:00Z",
    expires_at: str = "2026-07-16T11:00:00Z",
) -> dict[str, object]:
    proposal_payload = proposal_payload or _proposal_payload()
    proposal = proposal_payload["proposal"]
    assert isinstance(proposal, dict)
    receipt: dict[str, object] = {
        "receiptId": RECEIPT_ID,
        "evidenceScope": evidence_scope,
        "origin": ORIGIN,
        "verifierRef": VERIFIER_REF,
        "proposalId": proposal["proposalId"],
        "proposalRevision": proposal_payload["proposalRevision"],
        "mechanism": proposal["mechanism"],
        "subjectRevision": proposal["subjectRevision"],
        "decision": decision,
        "reviewerPrincipal": reviewer,
        "reviewerEligibilityRevision": SHA_A,
        "authenticationEvidenceRevision": SHA_B,
        "decidedAt": decided_at,
        "expiresAt": expires_at,
        "evidenceRef": "audit://human-approval/2048",
        "evidenceRevision": SHA_C,
    }
    return {
        "schemaVersion": HITL_RECEIPT_SCHEMA,
        "receiptRevision": _revision(receipt),
        "receipt": receipt,
    }


def _parse_proposal(**kwargs: object) -> HitlRemediationProposal:
    return parse_hitl_proposal(_canonical(_proposal_payload(**kwargs)))


class FakeVerifier:
    verifier_ref = VERIFIER_REF

    def __init__(self, result: object = True, *, mutate: bool = False) -> None:
        self.result = result
        self.mutate = mutate
        self.calls = 0

    def verify(self, receipt: HitlApprovalReceipt) -> object:
        self.calls += 1
        if self.mutate:
            object.__setattr__(receipt, "evidence_revision", SHA_A)
        return self.result


def _verified_receipt(
    proposal_payload: dict[str, object] | None = None,
    *,
    verifier: FakeVerifier | None = None,
    now: datetime = NOW,
    **kwargs: object,
) -> VerifiedHitlApprovalReceipt:
    receipt = parse_hitl_receipt(_canonical(_receipt_payload(proposal_payload, **kwargs)))
    return HitlApprovalGate(
        allowed_origins=frozenset({ORIGIN}),
        verifiers={VERIFIER_REF: verifier or FakeVerifier()},
    ).verify(receipt, now=now)


class FakeAudit:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[HitlAuditEvent] = []
        self.attempts: list[HitlAuditEvent] = []
        self._keys: set[str] = set()

    def record(self, event: HitlAuditEvent) -> None:
        self.attempts.append(event)
        if self.fail:
            raise RuntimeError("audit unavailable with sensitive detail")
        if event.dedupe_key not in self._keys:
            self._keys.add(event.dedupe_key)
            self.events.append(event)


def _aws_snapshot(
    *,
    status: AutomationApprovalStatus = AutomationApprovalStatus.PENDING_APPROVAL,
    **overrides: object,
) -> AutomationApprovalSnapshot:
    values: dict[str, object] = {
        "aws_account_id": ACCOUNT_ID,
        "region": REGION,
        "automation_execution_id": EXECUTION_ID,
        "document_name": "SRE-ConfigChangeProd-WithApproval",
        "document_version": "7",
        "document_sha256": SHA_A,
        "schema_version": "0.3",
        "input_revision": _revision(_parameters()),
        "approval_step_name": "approveChange",
        "approval_first": True,
        "status": status,
    }
    values.update(overrides)
    return AutomationApprovalSnapshot(**values)  # type: ignore[arg-type]


class FakeAwsProvider:
    def __init__(
        self,
        snapshot: AutomationApprovalSnapshot | None = None,
        *,
        fail_signal: bool = False,
        binding: AwsApprovalClientBinding | None = None,
    ) -> None:
        self.snapshot = snapshot or _aws_snapshot()
        self.fail_signal = fail_signal
        self.client_binding = binding or AwsApprovalClientBinding(ACCOUNT_ID, REGION)
        self.snapshot_calls = 0
        self.signal_attempts: list[AutomationApprovalSignalCall] = []
        self.signal_calls: list[AutomationApprovalSignalCall] = []
        self._keys: set[str] = set()

    def binding(self) -> AwsApprovalClientBinding:
        return self.client_binding

    def get_approval_snapshot(self, execution_id: str) -> AutomationApprovalSnapshot:
        assert execution_id == EXECUTION_ID
        self.snapshot_calls += 1
        return self.snapshot

    def send_approval_signal(self, call: AutomationApprovalSignalCall) -> None:
        self.signal_attempts.append(call)
        if self.fail_signal:
            raise RuntimeError("provider leaked secret=should-not-surface")
        if call.dedupe_key not in self._keys:
            self._keys.add(call.dedupe_key)
            self.signal_calls.append(call)


def _gitlab_rules(
    *,
    approved: bool = True,
    approved_by: tuple[str, ...] = (HUMAN_REVIEWER,),
) -> tuple[GitlabApprovalRuleSnapshot, ...]:
    return (
        GitlabApprovalRuleSnapshot(
            rule_id=11,
            name="platform-sre",
            required_approvals=1,
            approvals_left=0 if approved else 1,
            approved=approved,
            approved_by=approved_by,
        ),
    )


def _gitlab_snapshot(**overrides: object) -> GitlabApprovalSnapshot:
    values: dict[str, object] = {
        "instance_origin": "https://gitlab.example.invalid",
        "project_id": 42,
        "merge_request_iid": 7,
        "state": "opened",
        "source_sha": GIT_SHA,
        "target_branch": "main",
        "protected_target": True,
        "reset_approvals_on_push": True,
        "require_reauthentication": True,
        "approval_rules_overwritten": False,
        "protected_branch_revision": SHA_A,
        "approval_rules_revision": SHA_B,
        "approval_settings_revision": SHA_C,
        "approvals_left": 0,
        "approved": True,
        "rules": _gitlab_rules(),
        "author_principal": "human:developer/bob",
        "committer_principals": ("human:developer/bob",),
    }
    values.update(overrides)
    return GitlabApprovalSnapshot(**values)  # type: ignore[arg-type]


class FakeGitlabProvider:
    def __init__(
        self,
        snapshot: GitlabApprovalSnapshot | None = None,
        *,
        binding: GitlabApprovalClientBinding | None = None,
    ) -> None:
        self.snapshot = snapshot or _gitlab_snapshot()
        self.client_binding = binding or GitlabApprovalClientBinding(
            "https://gitlab.example.invalid"
        )
        self.snapshot_calls = 0

    def binding(self) -> GitlabApprovalClientBinding:
        return self.client_binding

    def get_approval_snapshot(
        self, project_id: int, merge_request_iid: int
    ) -> GitlabApprovalSnapshot:
        assert (project_id, merge_request_iid) == (42, 7)
        self.snapshot_calls += 1
        return self.snapshot


def _awaiting_case(
    *,
    mechanism: str = "aws_ssm",
    action: str = "config_change_prod",
    confidence: str = "0.9",
    audit: FakeAudit | None = None,
) -> tuple[HitlRemediationProposal, HitlCase, FakeAudit]:
    proposal = _parse_proposal(
        mechanism=mechanism,
        action=action,
        confidence=confidence,
    )
    sink = audit or FakeAudit()
    case = authorize_hitl_proposal(proposal, sink, now=NOW)
    assert case.state is HitlCaseState.AWAITING_HUMAN
    return proposal, case, sink


@pytest.mark.unit
class TestClosedHitlProposal:
    @pytest.mark.parametrize(
        ("mechanism", "expected"),
        [("aws_ssm", HitlMechanism.AWS_SSM), ("gitlab_mr", HitlMechanism.GITLAB_MR)],
    )
    def test_exact_content_addressed_provider_unions_load(
        self, mechanism: str, expected: HitlMechanism
    ) -> None:
        proposal = _parse_proposal(mechanism=mechanism)

        assert proposal.mechanism is expected
        assert proposal.proposal_id == PROPOSAL_ID
        assert proposal.action_tier_revision == hitl_action_tier_revision()

    @pytest.mark.parametrize(
        ("mutation", "match"),
        [
            (lambda payload: payload.update(extra=True), "fields"),
            (lambda payload: payload.update(proposalRevision=SHA_A), "revision"),
            (lambda payload: payload.update(schemaVersion="v0"), "schema"),
            (lambda payload: payload["proposal"].update(approved=True), "fields"),
            (lambda payload: payload["proposal"].update(confidence="0.90"), "confidence"),
            (lambda payload: payload["proposal"].update(evidenceRefs=[]), "evidence"),
            (
                lambda payload: payload["proposal"].update(
                    evidenceRefs=list(reversed(payload["proposal"]["evidenceRefs"]))
                ),
                "evidence",
            ),
            (
                lambda payload: payload["proposal"]["parameters"].update(Password=["do-not-store"]),
                "parameter",
            ),
        ],
    )
    def test_closed_non_authorizing_shape_rejects_drift(self, mutation: Any, match: str) -> None:
        payload = _proposal_payload()
        mutation(payload)

        with pytest.raises(HitlPolicyError, match=match):
            parse_hitl_proposal(_canonical(payload))

    @pytest.mark.parametrize(
        ("raw", "match"),
        [
            (b'{"schemaVersion":"x","schemaVersion":"y"}', "duplicate"),
            (b'{"schemaVersion":NaN}', "finite"),
            (b"\xff", "UTF-8"),
            (b"[]", "object"),
        ],
    )
    def test_malformed_duplicate_nonfinite_or_non_utf8_fails(self, raw: bytes, match: str) -> None:
        with pytest.raises(HitlPolicyError, match=match):
            parse_hitl_proposal(raw)

    def test_file_loader_rejects_symlink_and_oversize(self, tmp_path: Path) -> None:
        target = tmp_path / "proposal.json"
        target.write_bytes(_canonical(_proposal_payload()))
        link = tmp_path / "proposal-link.json"
        link.symlink_to(target)
        with pytest.raises(HitlPolicyError, match="symlink"):
            load_hitl_proposal(link)

        target.write_bytes(b"x" * (1024 * 1024 + 1))
        with pytest.raises(HitlPolicyError, match="large"):
            load_hitl_proposal(target)

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("documentVersion", "$LATEST", "version"),
            ("approvalFirst", False, "first"),
            ("schemaVersion", "0.2", "schema"),
            ("inputRevision", SHA_A, "input"),
            ("documentName", "*", "document"),
        ],
    )
    def test_aws_subject_must_be_exact_first_step_approval(
        self, field: str, value: object, match: str
    ) -> None:
        payload = _proposal_payload()
        subject = payload["proposal"]["subject"]
        assert isinstance(subject, dict)
        subject[field] = value
        payload["proposal"]["subjectRevision"] = _revision(
            {
                "action": payload["proposal"]["action"],
                "parameters": payload["proposal"]["parameters"],
                "subject": subject,
            }
        )
        payload["proposalRevision"] = _revision(payload["proposal"])

        with pytest.raises(HitlPolicyError, match=match):
            parse_hitl_proposal(_canonical(payload))

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("instanceOrigin", "http://gitlab.example.invalid", "HTTPS"),
            ("sourceSha", "main", "source"),
            ("projectId", 0, "project"),
            ("targetBranch", "*", "branch"),
        ],
    )
    def test_gitlab_subject_must_pin_protected_review_identity(
        self, field: str, value: object, match: str
    ) -> None:
        payload = _proposal_payload(mechanism="gitlab_mr")
        subject = payload["proposal"]["subject"]
        assert isinstance(subject, dict)
        subject[field] = value
        payload["proposal"]["subjectRevision"] = _revision(
            {
                "action": payload["proposal"]["action"],
                "parameters": payload["proposal"]["parameters"],
                "subject": subject,
            }
        )
        payload["proposalRevision"] = _revision(payload["proposal"])

        with pytest.raises(HitlPolicyError, match=match):
            parse_hitl_proposal(_canonical(payload))

    def test_checked_fixture_is_parseable_but_not_an_approval(self) -> None:
        path = Path(__file__).parents[1] / "examples" / "hitl-remediation-proposal.json"
        proposal = load_hitl_proposal(path)

        assert proposal.action == "config_change_prod"
        assert not hasattr(proposal, "approved")


@pytest.mark.unit
class TestTierAdmission:
    @pytest.mark.parametrize(
        ("action", "confidence", "state"),
        [
            ("config_change_prod", "0.9", HitlCaseState.AWAITING_HUMAN),
            ("restart_stateless_pod", "0.6", HitlCaseState.AWAITING_HUMAN),
            ("restart_stateless_pod", "0.9", HitlCaseState.ROUTE_T4),
            ("config_change_prod", "0.6", HitlCaseState.REQUIRE_T2),
            ("recommend_remediation", "0.9", HitlCaseState.REQUIRE_T2),
            ("unknown_root_shell", "0.9", HitlCaseState.DENIED),
        ],
    )
    def test_existing_classifier_is_the_only_tier_authority(
        self, action: str, confidence: str, state: HitlCaseState
    ) -> None:
        proposal = _parse_proposal(action=action, confidence=confidence)
        audit = FakeAudit()

        case = authorize_hitl_proposal(proposal, audit, now=NOW)

        assert case.state is state
        assert len(audit.events) == 1

    @pytest.mark.parametrize(
        ("confidence", "state"),
        [
            ("0.69999999999999", HitlCaseState.AWAITING_HUMAN),
            ("0.7", HitlCaseState.ROUTE_T4),
            ("0.70000000000001", HitlCaseState.ROUTE_T4),
        ],
    )
    def test_maximum_precision_confidence_preserves_classifier_boundary(
        self, confidence: str, state: HitlCaseState
    ) -> None:
        proposal = _parse_proposal(
            action="restart_stateless_pod",
            confidence=confidence,
        )

        case = authorize_hitl_proposal(proposal, FakeAudit(), now=NOW)

        assert case.state is state

    def test_table_revision_drift_denies_without_provider(self) -> None:
        payload = _proposal_payload()
        payload["proposal"]["actionTierRevision"] = SHA_A
        payload["proposalRevision"] = _revision(payload["proposal"])
        proposal = parse_hitl_proposal(_canonical(payload))

        case = authorize_hitl_proposal(proposal, FakeAudit(), now=NOW)

        assert case.state is HitlCaseState.DENIED
        assert case.reason == "action-tier-revision-mismatch"

    @pytest.mark.parametrize(
        "now",
        [
            datetime(2026, 7, 16, 9, 59, 59, tzinfo=UTC),
            datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
        ],
    )
    def test_future_or_expired_proposal_is_terminal_without_provider(self, now: datetime) -> None:
        proposal = _parse_proposal()

        case = authorize_hitl_proposal(proposal, FakeAudit(), now=now)

        assert case.state is HitlCaseState.EXPIRED

    def test_raw_or_mutated_proposal_cannot_open_case(self) -> None:
        proposal = _parse_proposal()
        object.__setattr__(proposal, "action", "iam_change")

        with pytest.raises(HitlPolicyError, match="integrity"):
            authorize_hitl_proposal(proposal, FakeAudit(), now=NOW)

    def test_cases_are_opaque_and_sealed(self) -> None:
        with pytest.raises(TypeError, match="authorization"):
            HitlCase()  # type: ignore[call-arg]


@pytest.mark.unit
class TestExternalHumanReceipt:
    def test_exact_content_addressed_receipt_loads(self) -> None:
        receipt = parse_hitl_receipt(_canonical(_receipt_payload()))

        assert receipt.decision is HitlReceiptDecision.APPROVED
        assert receipt.reviewer_principal == HUMAN_REVIEWER

    @pytest.mark.parametrize(
        ("mutation", "match"),
        [
            (lambda payload: payload.update(extra=True), "fields"),
            (lambda payload: payload.update(receiptRevision=SHA_A), "revision"),
            (lambda payload: payload["receipt"].update(approved=True), "fields"),
            (lambda payload: payload["receipt"].update(decision="allow"), "decision"),
            (
                lambda payload: payload["receipt"].update(reviewerPrincipal="agent:planner"),
                "human",
            ),
            (
                lambda payload: payload["receipt"].update(reviewerPrincipal="bot:release"),
                "human",
            ),
        ],
    )
    def test_receipt_rejects_closed_shape_and_nonhuman_drift(
        self, mutation: Any, match: str
    ) -> None:
        payload = _receipt_payload()
        mutation(payload)

        with pytest.raises(HitlPolicyError, match=match):
            parse_hitl_receipt(_canonical(payload))

    @pytest.mark.parametrize(
        ("raw", "match"),
        [
            (b'{"schemaVersion":"x","schemaVersion":"y"}', "duplicate"),
            (b'{"schemaVersion":NaN}', "finite"),
            (b"\xff", "UTF-8"),
            (b"[]", "object"),
        ],
    )
    def test_malformed_duplicate_nonfinite_or_non_utf8_receipt_fails(
        self, raw: bytes, match: str
    ) -> None:
        with pytest.raises(HitlPolicyError, match=match):
            parse_hitl_receipt(raw)

    def test_receipt_file_loader_rejects_symlink_and_oversize(self, tmp_path: Path) -> None:
        target = tmp_path / "receipt.json"
        target.write_bytes(_canonical(_receipt_payload()))
        link = tmp_path / "receipt-link.json"
        link.symlink_to(target)
        with pytest.raises(HitlPolicyError, match="symlink"):
            load_hitl_receipt(link)

        target.write_bytes(b"x" * (1024 * 1024 + 1))
        with pytest.raises(HitlPolicyError, match="large"):
            load_hitl_receipt(target)

    def test_exact_boolean_verifier_issues_opaque_capability(self) -> None:
        verifier = FakeVerifier()

        verified = _verified_receipt(verifier=verifier)

        assert verified.receipt_revision == _receipt_payload()["receiptRevision"]
        assert verifier.calls == 1

    @pytest.mark.parametrize("result", [False, 1, "true", None])
    def test_false_or_truthy_nonboolean_verification_fails(self, result: object) -> None:
        with pytest.raises(HitlPolicyError, match="verification"):
            _verified_receipt(verifier=FakeVerifier(result))

    def test_untrusted_origin_verifier_or_callback_mutation_fails(self) -> None:
        receipt = parse_hitl_receipt(_canonical(_receipt_payload()))
        with pytest.raises(HitlPolicyError, match="origin"):
            HitlApprovalGate(
                allowed_origins=frozenset(),
                verifiers={VERIFIER_REF: FakeVerifier()},
            ).verify(receipt, now=NOW)
        with pytest.raises(HitlPolicyError, match="verifier"):
            HitlApprovalGate(
                allowed_origins=frozenset({ORIGIN}),
                verifiers={},
            ).verify(receipt, now=NOW)
        with pytest.raises(HitlPolicyError, match="mutated"):
            _verified_receipt(verifier=FakeVerifier(mutate=True))

    def test_future_or_expired_receipt_cannot_be_verified(self) -> None:
        with pytest.raises(HitlPolicyError, match="future"):
            _verified_receipt(now=datetime(2026, 7, 16, 10, 19, tzinfo=UTC))
        with pytest.raises(HitlPolicyError, match="expired"):
            _verified_receipt(now=datetime(2026, 7, 16, 11, 0, tzinfo=UTC))

    def test_verified_receipts_cannot_be_caller_constructed(self) -> None:
        receipt = parse_hitl_receipt(_canonical(_receipt_payload()))
        with pytest.raises(TypeError, match="gate"):
            VerifiedHitlApprovalReceipt(receipt)  # type: ignore[call-arg]

    def test_checked_fixture_receipt_is_fixture_only(self) -> None:
        path = Path(__file__).parents[1] / "examples" / "hitl-approval-receipt.json"
        receipt = load_hitl_receipt(path)

        assert receipt.evidence_scope == "fixture"


@pytest.mark.unit
class TestReceiptRejoin:
    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("proposalId", "2101778f-3631-4f91-96d1-e56683c44a65", "proposal"),
            ("proposalRevision", SHA_A, "proposal"),
            ("subjectRevision", SHA_A, "subject"),
            ("mechanism", "gitlab_mr", "mechanism"),
        ],
    )
    def test_cross_proposal_or_subject_receipt_never_calls_provider(
        self, field: str, value: object, match: str
    ) -> None:
        proposal_payload = _proposal_payload()
        payload = _receipt_payload(proposal_payload)
        payload["receipt"][field] = value
        payload["receiptRevision"] = _revision(payload["receipt"])
        receipt = parse_hitl_receipt(_canonical(payload))
        verified = HitlApprovalGate(
            allowed_origins=frozenset({ORIGIN}),
            verifiers={VERIFIER_REF: FakeVerifier()},
        ).verify(receipt, now=NOW)
        _, case, audit = _awaiting_case()
        provider = FakeAwsProvider()

        with pytest.raises(HitlPolicyError, match=match):
            apply_hitl_receipt(case, verified, provider, audit, now=NOW)

        assert provider.snapshot_calls == 0
        assert provider.signal_calls == []

    def test_proposer_self_approval_never_calls_provider(self) -> None:
        proposal_payload = _proposal_payload(proposer=HUMAN_REVIEWER)
        proposal = parse_hitl_proposal(_canonical(proposal_payload))
        audit = FakeAudit()
        case = authorize_hitl_proposal(proposal, audit, now=NOW)
        verified = _verified_receipt(proposal_payload)
        provider = FakeAwsProvider()

        with pytest.raises(HitlPolicyError, match="self"):
            apply_hitl_receipt(case, verified, provider, audit, now=NOW)

        assert provider.snapshot_calls == 0

    def test_fixture_receipt_never_calls_provider(self) -> None:
        _, case, audit = _awaiting_case()
        verified = _verified_receipt(evidence_scope="fixture")
        provider = FakeAwsProvider()

        with pytest.raises(HitlPolicyError, match="fixture"):
            apply_hitl_receipt(case, verified, provider, audit, now=NOW)

        assert provider.snapshot_calls == 0

    def test_receipt_use_after_verification_expiry_expires_without_provider(self) -> None:
        _, case, audit = _awaiting_case()
        verified = _verified_receipt(now=NOW)
        provider = FakeAwsProvider()

        result = apply_hitl_receipt(
            case,
            verified,
            provider,
            audit,
            now=datetime(2026, 7, 16, 11, 0, tzinfo=UTC),
        )

        assert result.state is HitlCaseState.EXPIRED
        assert provider.snapshot_calls == 0


@pytest.mark.unit
class TestAwsApprovalFlow:
    @pytest.mark.parametrize(
        ("decision", "signal", "state"),
        [
            ("approved", "Approve", HitlCaseState.APPROVAL_SIGNAL_SENT),
            ("rejected", "Reject", HitlCaseState.REJECTION_SIGNAL_SENT),
        ],
    )
    def test_exact_pending_snapshot_sends_one_bounded_signal(
        self, decision: str, signal: str, state: HitlCaseState
    ) -> None:
        _, case, audit = _awaiting_case()
        receipt = _verified_receipt(decision=decision)
        provider = FakeAwsProvider()

        result = apply_hitl_receipt(case, receipt, provider, audit, now=NOW)

        assert result.state is state
        assert len(provider.signal_calls) == 1
        call = provider.signal_calls[0]
        assert call.aws_account_id == ACCOUNT_ID
        assert call.region == REGION
        assert call.automation_execution_id == EXECUTION_ID
        assert call.signal_type == signal
        assert call.payload == {"Comment": [f"sre-harness-receipt:{RECEIPT_ID}"]}
        assert "ChangeId" not in repr(call)
        assert len(call.dedupe_key) == 71

    @pytest.mark.parametrize(
        ("status", "state"),
        [
            (AutomationApprovalStatus.APPROVED, HitlCaseState.APPROVED),
            (AutomationApprovalStatus.REJECTED, HitlCaseState.REJECTED),
        ],
    )
    def test_signal_reconciles_to_matching_terminal_state(
        self, status: AutomationApprovalStatus, state: HitlCaseState
    ) -> None:
        decision = "approved" if status is AutomationApprovalStatus.APPROVED else "rejected"
        _, case, audit = _awaiting_case()
        receipt = _verified_receipt(decision=decision)
        provider = FakeAwsProvider()
        signalled = apply_hitl_receipt(case, receipt, provider, audit, now=NOW)
        provider.snapshot = _aws_snapshot(status=status)

        result = reconcile_hitl_case(signalled, provider, audit, now=NOW)

        assert result.state is state
        assert len(provider.signal_calls) == 1
        terminal = reconcile_hitl_case(result, provider, audit, now=NOW)
        assert terminal is result

    def test_pending_provider_state_preserves_the_signalled_case(self) -> None:
        _, case, audit = _awaiting_case()
        provider = FakeAwsProvider()
        signalled = apply_hitl_receipt(case, _verified_receipt(), provider, audit, now=NOW)

        pending = reconcile_hitl_case(signalled, provider, audit, now=NOW)

        assert pending is signalled
        assert len(provider.signal_calls) == 1

    def test_matching_terminal_snapshot_is_idempotent_without_signal(self) -> None:
        _, case, audit = _awaiting_case()
        receipt = _verified_receipt()
        provider = FakeAwsProvider(_aws_snapshot(status=AutomationApprovalStatus.APPROVED))

        result = apply_hitl_receipt(case, receipt, provider, audit, now=NOW)

        assert result.state is HitlCaseState.APPROVED
        assert provider.signal_calls == []

    def test_receipt_expiry_does_not_revoke_an_already_sent_approval(self) -> None:
        _, case, audit = _awaiting_case()
        provider = FakeAwsProvider()
        signalled = apply_hitl_receipt(case, _verified_receipt(), provider, audit, now=NOW)
        provider.snapshot = _aws_snapshot(status=AutomationApprovalStatus.APPROVED)

        result = reconcile_hitl_case(
            signalled,
            provider,
            audit,
            now=datetime(2026, 7, 16, 11, 30, tzinfo=UTC),
        )

        assert result.state is HitlCaseState.APPROVED

    @pytest.mark.parametrize(
        ("snapshot", "reason"),
        [
            (_aws_snapshot(document_version="8"), "provider-subject-drift"),
            (_aws_snapshot(document_sha256=SHA_B), "provider-subject-drift"),
            (_aws_snapshot(input_revision=SHA_B), "provider-subject-drift"),
            (_aws_snapshot(approval_step_name="laterApproval"), "provider-subject-drift"),
            (_aws_snapshot(approval_first=False), "provider-subject-drift"),
            (_aws_snapshot(schema_version="0.2"), "provider-subject-drift"),
        ],
    )
    def test_document_input_or_step_drift_escalates_without_signal(
        self, snapshot: AutomationApprovalSnapshot, reason: str
    ) -> None:
        _, case, audit = _awaiting_case()
        provider = FakeAwsProvider(snapshot)

        result = apply_hitl_receipt(case, _verified_receipt(), provider, audit, now=NOW)

        assert result.state is HitlCaseState.ESCALATED
        assert result.reason == reason
        assert provider.signal_calls == []

    def test_client_account_or_region_drift_fails_before_snapshot(self) -> None:
        _, case, audit = _awaiting_case()
        provider = FakeAwsProvider(binding=AwsApprovalClientBinding("999999999999", REGION))

        result = apply_hitl_receipt(case, _verified_receipt(), provider, audit, now=NOW)

        assert result.state is HitlCaseState.ESCALATED
        assert provider.snapshot_calls == 0

    def test_conflicting_terminal_provider_state_escalates(self) -> None:
        _, case, audit = _awaiting_case()
        provider = FakeAwsProvider(_aws_snapshot(status=AutomationApprovalStatus.REJECTED))

        result = apply_hitl_receipt(
            case, _verified_receipt(decision="approved"), provider, audit, now=NOW
        )

        assert result.state is HitlCaseState.ESCALATED
        assert provider.signal_calls == []

    def test_provider_failure_exposes_no_detail_and_retry_reuses_key(self) -> None:
        _, case, audit = _awaiting_case()
        provider = FakeAwsProvider(fail_signal=True)
        receipt = _verified_receipt()

        with pytest.raises(HitlExecutionError, match="approval signal failed") as exc:
            apply_hitl_receipt(case, receipt, provider, audit, now=NOW)
        assert "secret" not in str(exc.value)

        provider.fail_signal = False
        result = apply_hitl_receipt(case, receipt, provider, audit, now=NOW)

        assert result.state is HitlCaseState.APPROVAL_SIGNAL_SENT
        assert len(provider.signal_attempts) == 2
        assert provider.signal_attempts[0].dedupe_key == provider.signal_attempts[1].dedupe_key

    def test_audit_failure_returns_no_advanced_state_and_retry_reuses_keys(self) -> None:
        _, case, _ = _awaiting_case()
        provider = FakeAwsProvider()
        audit = FakeAudit(fail=True)
        receipt = _verified_receipt()

        with pytest.raises(HitlExecutionError, match="audit"):
            apply_hitl_receipt(case, receipt, provider, audit, now=NOW)

        audit.fail = False
        result = apply_hitl_receipt(case, receipt, provider, audit, now=NOW)

        assert result.state is HitlCaseState.APPROVAL_SIGNAL_SENT
        assert len(provider.signal_attempts) == 2
        assert len(provider.signal_calls) == 1
        assert audit.attempts[0].dedupe_key == audit.attempts[1].dedupe_key


@pytest.mark.unit
class TestGitlabApprovalFlow:
    def test_exact_protected_rule_approval_is_read_only_and_terminal(self) -> None:
        proposal_payload = _proposal_payload(mechanism="gitlab_mr")
        proposal = parse_hitl_proposal(_canonical(proposal_payload))
        audit = FakeAudit()
        case = authorize_hitl_proposal(proposal, audit, now=NOW)
        receipt = _verified_receipt(proposal_payload)
        provider = FakeGitlabProvider()

        result = apply_hitl_receipt(case, receipt, provider, audit, now=NOW)

        assert result.state is HitlCaseState.APPROVED
        assert provider.snapshot_calls == 1
        assert not hasattr(provider, "approve")
        assert not hasattr(provider, "merge")

    def test_rejected_receipt_is_terminal_without_gitlab_call(self) -> None:
        proposal_payload = _proposal_payload(mechanism="gitlab_mr")
        proposal = parse_hitl_proposal(_canonical(proposal_payload))
        audit = FakeAudit()
        case = authorize_hitl_proposal(proposal, audit, now=NOW)
        receipt = _verified_receipt(proposal_payload, decision="rejected")
        provider = FakeGitlabProvider()

        result = apply_hitl_receipt(case, receipt, provider, audit, now=NOW)

        assert result.state is HitlCaseState.REJECTED
        assert provider.snapshot_calls == 0

    @pytest.mark.parametrize(
        "snapshot",
        [
            _gitlab_snapshot(source_sha="e" * 40),
            _gitlab_snapshot(protected_target=False),
            _gitlab_snapshot(reset_approvals_on_push=False),
            _gitlab_snapshot(require_reauthentication=False),
            _gitlab_snapshot(approval_rules_overwritten=True),
            _gitlab_snapshot(approval_rules_revision=SHA_A),
            _gitlab_snapshot(approval_settings_revision=SHA_A),
            _gitlab_snapshot(approvals_left=1),
            _gitlab_snapshot(approved=False),
            _gitlab_snapshot(rules=()),
            _gitlab_snapshot(rules=_gitlab_rules(approved=False)),
            _gitlab_snapshot(author_principal=HUMAN_REVIEWER),
            _gitlab_snapshot(committer_principals=(HUMAN_REVIEWER,)),
            _gitlab_snapshot(rules=_gitlab_rules(approved_by=("human:other",))),
        ],
    )
    def test_stale_empty_overridden_or_self_approval_escalates(
        self, snapshot: GitlabApprovalSnapshot
    ) -> None:
        proposal_payload = _proposal_payload(mechanism="gitlab_mr")
        proposal = parse_hitl_proposal(_canonical(proposal_payload))
        audit = FakeAudit()
        case = authorize_hitl_proposal(proposal, audit, now=NOW)
        provider = FakeGitlabProvider(snapshot)

        result = apply_hitl_receipt(
            case,
            _verified_receipt(proposal_payload),
            provider,
            audit,
            now=NOW,
        )

        assert result.state is HitlCaseState.ESCALATED

    def test_instance_binding_drift_escalates_before_observation(self) -> None:
        proposal_payload = _proposal_payload(mechanism="gitlab_mr")
        proposal = parse_hitl_proposal(_canonical(proposal_payload))
        audit = FakeAudit()
        case = authorize_hitl_proposal(proposal, audit, now=NOW)
        provider = FakeGitlabProvider(
            binding=GitlabApprovalClientBinding("https://other.example.invalid")
        )

        result = apply_hitl_receipt(
            case,
            _verified_receipt(proposal_payload),
            provider,
            audit,
            now=NOW,
        )

        assert result.state is HitlCaseState.ESCALATED
        assert provider.snapshot_calls == 0


@pytest.mark.unit
class TestFiniteStateAndAudit:
    def test_audit_events_are_stable_and_nonsecret(self) -> None:
        _, case, audit = _awaiting_case()
        provider = FakeAwsProvider()
        result = apply_hitl_receipt(case, _verified_receipt(), provider, audit, now=NOW)

        assert result.state is HitlCaseState.APPROVAL_SIGNAL_SENT
        assert len({event.dedupe_key for event in audit.events}) == len(audit.events)
        serialized = repr(audit.events)
        for forbidden in (
            "ChangeId",
            "payments-api",
            HUMAN_REVIEWER,
            "authenticationEvidenceRevision",
            "riskSummary",
            "rollbackRef",
        ):
            assert forbidden not in serialized

    def test_terminal_state_is_side_effect_free_and_reject_cannot_flip(self) -> None:
        _, case, audit = _awaiting_case()
        provider = FakeAwsProvider()
        rejected = apply_hitl_receipt(
            case,
            _verified_receipt(decision="rejected"),
            provider,
            audit,
            now=NOW,
        )
        provider.snapshot = _aws_snapshot(status=AutomationApprovalStatus.REJECTED)
        terminal = reconcile_hitl_case(rejected, provider, audit, now=NOW)
        calls = len(provider.signal_calls)

        assert reconcile_hitl_case(terminal, provider, audit, now=NOW) is terminal
        assert len(provider.signal_calls) == calls
        with pytest.raises(HitlPolicyError, match="terminal"):
            apply_hitl_receipt(
                terminal, _verified_receipt(decision="approved"), provider, audit, now=NOW
            )

    def test_mutated_case_fails_before_provider(self) -> None:
        _, case, audit = _awaiting_case()
        object.__setattr__(case, "state", HitlCaseState.APPROVED)
        provider = FakeAwsProvider()

        with pytest.raises(HitlPolicyError, match="integrity"):
            apply_hitl_receipt(case, _verified_receipt(), provider, audit, now=NOW)

        assert provider.snapshot_calls == 0


@pytest.mark.unit
class TestEvidenceBoundary:
    def test_docs_retain_fixture_only_incomplete_boundary(self) -> None:
        repository = ROOT.parents[1]
        spec = (repository / "docs/specs/SPEC-B5-tier3-hitl-remediation.md").read_text(
            encoding="utf-8"
        )
        status = (repository / "PROJECT_STATUS.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        normalized_spec = " ".join(spec.split())
        normalized_status = " ".join(status.split())
        normalized_readme = " ".join(readme.split())

        assert "SPEC-B5.json" in normalized_spec
        assert "B5 remains incomplete" in normalized_spec
        assert "No checked-in fixture may authorize a provider signal" in normalized_spec
        assert "SPEC-B5.json" in normalized_status
        assert "B5 remains incomplete" in normalized_status
        assert "No AWS or GitLab service is configured or contacted" in normalized_readme
