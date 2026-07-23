"""SPEC-B4 probes for externally authorized Tier-4 remediation."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from sre_harness.remediation import (
    MAX_REMEDIATION_BYTES,
    REMEDIATION_POLICY_SCHEMA,
    REMEDIATION_REQUEST_SCHEMA,
    AutomationClientBinding,
    AutomationDocumentSnapshot,
    AutomationExecutionSnapshot,
    AutomationExecutionStatus,
    DocumentBinding,
    RemediationDecision,
    RemediationDisposition,
    RemediationExecutionError,
    RemediationNotification,
    RemediationNotificationType,
    RemediationPolicyError,
    RemediationPolicyGate,
    RemediationRequest,
    RemediationRun,
    RemediationRunState,
    StartAutomationCall,
    VerifiedRemediationPolicy,
    authorize_remediation,
    load_remediation_policy,
    load_remediation_request,
    parse_remediation_policy,
    parse_remediation_request,
    reconcile_t4_remediation,
    start_t4_remediation,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 16, 10, 10, tzinfo=UTC)
ACCOUNT_ID = "000000000000"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/fixture-sre-automation"
TOPIC_ARN = f"arn:aws:sns:eu-west-1:{ACCOUNT_ID}:fixture-sre-remediation"
ORIGIN = "test://remediation-policy"
VERIFIER_REF = "test://verifier/exact-remediation-policy"


def _revision(value: object) -> str:
    canonical = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _document(name: str, digest_character: str) -> dict[str, object]:
    return {
        "documentName": name,
        "documentSha256": "sha256:" + digest_character * 64,
        "documentVersion": "1",
    }


def _entry(
    action: str,
    suffix: str,
    digest_character: str,
    parameters: dict[str, list[str]],
) -> dict[str, object]:
    return {
        "action": action,
        "environment": "development",
        "forward": _document(f"Fixture-{suffix}", digest_character),
        "parameterAllowlist": parameters,
        "rollback": _document(f"Fixture-{suffix}-Rollback", chr(ord(digest_character) + 1)),
        "rollbackExecutionIdParameter": "ForwardExecutionId",
    }


def _policy_document(scope: str = "external_candidate") -> dict[str, object]:
    common = {"AutomationAssumeRole": [ROLE_ARN]}
    entries = [
        _entry(
            "restart_stateless_pod",
            "RestartStatelessPod",
            "a",
            {
                **common,
                "Cluster": ["dev-eu-1"],
                "Namespace": ["payments"],
                "Workload": ["payments-api"],
            },
        ),
        _entry(
            "retrigger_argocd_sync",
            "RetriggerArgoCdSync",
            "c",
            {
                **common,
                "Application": ["payments"],
            },
        ),
        _entry(
            "scale_stateless_service",
            "ScaleStatelessService",
            "e",
            {
                **common,
                "Cluster": ["dev-eu-1"],
                "DesiredReplicas": ["2", "3", "4", "5"],
                "Namespace": ["payments"],
                "Workload": ["payments-api"],
            },
        ),
    ]
    return {
        "approvalRevision": "sha256:" + "b" * 64,
        "approvedBy": "team:platform-sre",
        "awsAccountId": ACCOUNT_ID,
        "confidenceThreshold": "0.9",
        "entries": entries,
        "evidenceScope": scope,
        "executionRoleArn": ROLE_ARN,
        "expiresAt": "2026-07-17T10:00:00Z",
        "maxRequestAgeSeconds": 300,
        "notificationTopicArn": TOPIC_ARN,
        "origin": ORIGIN,
        "policyId": "sre-t4-development-v1",
        "publishedAt": "2026-07-16T10:00:00Z",
        "region": "eu-west-1",
        "verifierRef": VERIFIER_REF,
    }


def _policy_payload(scope: str = "external_candidate") -> dict[str, object]:
    policy = _policy_document(scope)
    return {
        "policy": policy,
        "publicationRevision": _revision(policy),
        "schemaVersion": REMEDIATION_POLICY_SCHEMA,
    }


def _reseal_policy(payload: dict[str, object]) -> None:
    policy = payload["policy"]
    assert isinstance(policy, dict)
    payload["publicationRevision"] = _revision(policy)


def _parse_policy(scope: str = "external_candidate"):
    return parse_remediation_policy(
        json.dumps(_policy_payload(scope), allow_nan=False, sort_keys=True).encode()
    )


def _request_document(
    *,
    action: str = "restart_stateless_pod",
    confidence: str = "0.95",
    environment: str = "development",
    publication_revision: str | None = None,
) -> dict[str, object]:
    revision = publication_revision or _policy_payload()["publicationRevision"]
    return {
        "action": action,
        "confidence": confidence,
        "environment": environment,
        "parameters": {
            "AutomationAssumeRole": [ROLE_ARN],
            "Cluster": ["dev-eu-1"],
            "Namespace": ["payments"],
            "Workload": ["payments-api"],
        },
        "planRevision": "sha256:" + "c" * 64,
        "policyId": "sre-t4-development-v1",
        "policyRevision": revision,
        "requestId": "11111111-1111-4111-8111-111111111111",
        "requestedAt": "2026-07-16T10:08:00Z",
        "triggerId": "incident:payments:2026-07-16-001",
    }


def _request_payload(**kwargs: object) -> dict[str, object]:
    request = _request_document(**kwargs)  # type: ignore[arg-type]
    return {
        "request": request,
        "requestRevision": _revision(request),
        "schemaVersion": REMEDIATION_REQUEST_SCHEMA,
    }


def _reseal_request(payload: dict[str, object]) -> None:
    request = payload["request"]
    assert isinstance(request, dict)
    payload["requestRevision"] = _revision(request)


def _parse_request(**kwargs: object) -> RemediationRequest:
    return parse_remediation_request(
        json.dumps(_request_payload(**kwargs), allow_nan=False, sort_keys=True).encode()
    )


class FakeVerifier:
    def __init__(self, result: object = True, *, mutate: bool = False) -> None:
        self.result = result
        self.mutate = mutate
        self.calls = 0

    def verify(self, publication: object) -> object:
        self.calls += 1
        if self.mutate:
            object.__setattr__(publication, "policy_id", "mutated")
        return self.result


def _verified(
    scope: str = "external_candidate",
    *,
    verifier: FakeVerifier | None = None,
    now: datetime = NOW,
) -> VerifiedRemediationPolicy:
    actual_verifier = verifier or FakeVerifier()
    gate = RemediationPolicyGate(
        allowed_origins=frozenset({ORIGIN}),
        verifiers={VERIFIER_REF: actual_verifier},
    )
    return gate.verify(_parse_policy(scope), now=now)


def _decision(
    *,
    scope: str = "external_candidate",
    request: RemediationRequest | None = None,
    now: datetime = NOW,
) -> RemediationDecision:
    return authorize_remediation(request or _parse_request(), _verified(scope), now=now)


class FakeSsmClient:
    def __init__(self, decision: RemediationDecision) -> None:
        self.documents: dict[tuple[str, str], AutomationDocumentSnapshot] = {}
        self.executions: dict[str, AutomationExecutionSnapshot] = {}
        self.start_calls: list[StartAutomationCall] = []
        self.describe_calls: list[tuple[str, str]] = []
        self.execution_calls: list[str] = []
        self._ids_by_token: dict[str, str] = {}
        self.client_binding = AutomationClientBinding(
            aws_account_id=decision.aws_account_id,
            region=decision.region,
        )
        self.set_document(decision.forward_document, decision.aws_account_id)
        self.set_document(decision.rollback_document, decision.aws_account_id)

    def binding(self) -> AutomationClientBinding:
        return self.client_binding

    def set_document(self, binding: DocumentBinding, owner: str) -> None:
        name = binding.document_name
        version = binding.document_version
        sha256 = binding.document_sha256
        self.documents[(name, version)] = AutomationDocumentSnapshot(
            document_name=name,
            document_version=version,
            document_sha256=sha256,
            owner=owner,
            document_type="Automation",
            status="Active",
            schema_version="0.3",
        )

    def describe_document(self, document_name: str, document_version: str):
        self.describe_calls.append((document_name, document_version))
        return self.documents[(document_name, document_version)]

    def start_automation(self, call: StartAutomationCall) -> str:
        self.start_calls.append(call)
        if call.client_token not in self._ids_by_token:
            index = len(self._ids_by_token) + 1
            self._ids_by_token[call.client_token] = f"00000000-0000-4000-8000-{index:012d}"
        return self._ids_by_token[call.client_token]

    def get_automation_execution(self, execution_id: str):
        self.execution_calls.append(execution_id)
        return self.executions[execution_id]

    def set_status(
        self,
        execution_id: str,
        document_name: str,
        document_version: str,
        status: AutomationExecutionStatus,
    ) -> None:
        self.executions[execution_id] = AutomationExecutionSnapshot(
            execution_id=execution_id,
            document_name=document_name,
            document_version=document_version,
            status=status,
        )


class FakeNotifier:
    def __init__(self) -> None:
        self.notifications: list[RemediationNotification] = []
        self.delivered_keys: set[str] = set()

    def notify(self, notification: RemediationNotification) -> None:
        if notification.dedupe_key in self.delivered_keys:
            return
        self.delivered_keys.add(notification.dedupe_key)
        self.notifications.append(notification)


def _started() -> tuple[RemediationDecision, FakeSsmClient, FakeNotifier, RemediationRun]:
    decision = _decision()
    client = FakeSsmClient(decision)
    notifier = FakeNotifier()
    run = start_t4_remediation(decision, client, notifier, now=NOW)
    return decision, client, notifier, run


@pytest.mark.unit
class TestClosedPolicyPublication:
    def test_exact_publication_loads_immutable_allowlist(self) -> None:
        publication = _parse_policy()

        assert publication.policy_id == "sre-t4-development-v1"
        assert publication.evidence_scope == "external_candidate"
        assert publication.publication_revision == _revision(_policy_document())
        assert tuple(entry.action for entry in publication.entries) == (
            "restart_stateless_pod",
            "retrigger_argocd_sync",
            "scale_stateless_service",
        )

    @pytest.mark.parametrize(
        "mutation",
        [
            lambda value: value.update({"unknown": True}),
            lambda value: value.pop("publicationRevision"),
            lambda value: value.update({"schemaVersion": "v2"}),
            lambda value: value.update({"publicationRevision": "sha256:" + "0" * 64}),
            lambda value: value["policy"].update({"unknown": True}),
            lambda value: value["policy"].update({"evidenceScope": "production"}),
            lambda value: value["policy"].update({"expiresAt": "2026-07-16T10:00:00Z"}),
            lambda value: value["policy"].update(
                {"notificationTopicArn": "arn:aws:sns:us-east-1:111111111111:foreign"}
            ),
            lambda value: value["policy"]["entries"].reverse(),
            lambda value: value["policy"]["entries"][0].update({"action": "config_change_prod"}),
            lambda value: value["policy"]["entries"][0]["forward"].update(
                {"documentVersion": "$LATEST"}
            ),
            lambda value: value["policy"]["entries"][0].update(
                {"rollback": copy.deepcopy(value["policy"]["entries"][0]["forward"])}
            ),
            lambda value: value["policy"]["entries"][0]["parameterAllowlist"].update(
                {"AutomationAssumeRole": ["arn:aws:iam::111111111111:role/foreign"]}
            ),
            lambda value: value["policy"]["entries"][0]["parameterAllowlist"].update(
                {"Workload": ["*"]}
            ),
            lambda value: value["policy"]["entries"][0]["parameterAllowlist"].update(
                {"Cluster": ["dev-eu-1", "dev-us-1"]}
            ),
            lambda value: value["policy"]["entries"][0]["parameterAllowlist"].update(
                {"ApiToken": ["secret"]}
            ),
            lambda value: value["policy"]["entries"][2]["parameterAllowlist"].update(
                {"DesiredReplicas": ["101"]}
            ),
        ],
    )
    def test_unknown_unbound_mutable_or_unsafe_policy_fails(
        self,
        mutation: Callable[[dict[str, Any]], None],
    ) -> None:
        payload = copy.deepcopy(_policy_payload())
        mutation(payload)
        if (
            "publicationRevision" in payload
            and payload.get("publicationRevision") != "sha256:" + "0" * 64
        ):
            _reseal_policy(payload)

        with pytest.raises(RemediationPolicyError):
            parse_remediation_policy(json.dumps(payload, sort_keys=True).encode())

    @pytest.mark.parametrize(
        "raw",
        [b"[]", b'{"schemaVersion":1,"schemaVersion":2}', b'{"value":NaN}', b"\xff"],
    )
    def test_malformed_duplicate_nonfinite_or_non_utf8_policy_fails(self, raw: bytes) -> None:
        with pytest.raises(RemediationPolicyError):
            parse_remediation_policy(raw)

    def test_oversize_and_symlink_policy_fail(self, tmp_path: Path) -> None:
        with pytest.raises(RemediationPolicyError, match="exceeds maximum"):
            parse_remediation_policy(b" " * (MAX_REMEDIATION_BYTES + 1))

        source = tmp_path / "policy.json"
        source.write_text(json.dumps(_policy_payload(), sort_keys=True))
        link = tmp_path / "policy-link.json"
        link.symlink_to(source)
        assert load_remediation_policy(source).policy_id == "sre-t4-development-v1"
        with pytest.raises(RemediationPolicyError, match="symlink"):
            load_remediation_policy(link)


@pytest.mark.unit
class TestExternalPolicyAuthority:
    def test_exact_boolean_verifier_issues_opaque_capability(self) -> None:
        verifier = FakeVerifier(True)
        verified = _verified(verifier=verifier)

        assert verified.policy_id == "sre-t4-development-v1"
        assert verified.publication_revision == _policy_payload()["publicationRevision"]
        assert verifier.calls == 1

    @pytest.mark.parametrize("result", [False, 1, "true", None])
    def test_false_or_truthy_non_boolean_verification_fails(self, result: object) -> None:
        with pytest.raises(RemediationPolicyError, match="verification"):
            _verified(verifier=FakeVerifier(result))

    def test_untrusted_origin_verifier_or_callback_mutation_fails(self) -> None:
        publication = _parse_policy()
        with pytest.raises(RemediationPolicyError, match="origin"):
            RemediationPolicyGate(
                allowed_origins=frozenset(),
                verifiers={VERIFIER_REF: FakeVerifier()},
            ).verify(publication, now=NOW)
        with pytest.raises(RemediationPolicyError, match="verifier"):
            RemediationPolicyGate(
                allowed_origins=frozenset({ORIGIN}),
                verifiers={},
            ).verify(publication, now=NOW)
        with pytest.raises(RemediationPolicyError, match="mutated"):
            _verified(verifier=FakeVerifier(mutate=True))

    @pytest.mark.parametrize(
        "now",
        [datetime(2026, 7, 16, 9, 59, tzinfo=UTC), datetime(2026, 7, 17, 10, 0, 1, tzinfo=UTC)],
    )
    def test_future_or_expired_publication_fails(self, now: datetime) -> None:
        with pytest.raises(RemediationPolicyError, match="publication"):
            _verified(now=now)


@pytest.mark.unit
class TestClosedRemediationRequest:
    def test_exact_request_loads_and_rejoins_policy(self, tmp_path: Path) -> None:
        path = tmp_path / "request.json"
        path.write_text(json.dumps(_request_payload(), sort_keys=True))

        request = load_remediation_request(path)
        assert request.action == "restart_stateless_pod"
        assert request.confidence == "0.95"
        assert request.policy_revision == _policy_payload()["publicationRevision"]
        assert request.parameters[0][0] == "AutomationAssumeRole"

    @pytest.mark.parametrize(
        "raw",
        [b"[]", b'{"schemaVersion":1,"schemaVersion":2}', b'{"value":NaN}', b"\xff"],
    )
    def test_duplicate_nonfinite_non_utf8_or_non_object_request_fails(
        self,
        raw: bytes,
    ) -> None:
        with pytest.raises(RemediationPolicyError):
            parse_remediation_request(raw)

    @pytest.mark.parametrize(
        "mutation",
        [
            lambda value: value.update({"unknown": True}),
            lambda value: value.pop("requestRevision"),
            lambda value: value.update({"schemaVersion": "v2"}),
            lambda value: value.update({"requestRevision": "sha256:" + "0" * 64}),
            lambda value: value["request"].update({"unknown": True}),
            lambda value: value["request"].update({"requestId": "not-a-uuid"}),
            lambda value: value["request"].update({"requestedAt": "2026-07-16T12:08:00+02:00"}),
            lambda value: value["request"].update({"confidence": 0.95}),
            lambda value: value["request"].update({"confidence": "0.950"}),
            lambda value: value["request"]["parameters"].update(
                {"Cluster": ["dev-eu-1", "dev-eu-1"]}
            ),
        ],
    )
    def test_unknown_malformed_or_noncanonical_request_fails(
        self,
        mutation: Callable[[dict[str, Any]], None],
    ) -> None:
        payload = copy.deepcopy(_request_payload())
        mutation(payload)
        if "requestRevision" in payload and payload.get("requestRevision") != "sha256:" + "0" * 64:
            _reseal_request(payload)
        with pytest.raises(RemediationPolicyError):
            parse_remediation_request(json.dumps(payload, sort_keys=True).encode())


@pytest.mark.unit
class TestAuthorization:
    def test_exact_external_candidate_authorizes_t4(self) -> None:
        decision = _decision()

        assert decision.disposition is RemediationDisposition.EXECUTE_T4
        assert decision.action == "restart_stateless_pod"
        assert decision.request_id == "11111111-1111-4111-8111-111111111111"
        assert decision.reason == "exact-preauthorized-t4-match"

    def test_exact_decimal_threshold_cannot_round_up_to_t4(self) -> None:
        payload = _policy_payload()
        policy = payload["policy"]
        assert isinstance(policy, dict)
        policy["confidenceThreshold"] = "0.90000000000000001"
        _reseal_policy(payload)
        publication = parse_remediation_policy(
            json.dumps(payload, allow_nan=False, sort_keys=True).encode()
        )
        gate = RemediationPolicyGate(
            allowed_origins=frozenset({ORIGIN}),
            verifiers={VERIFIER_REF: FakeVerifier()},
        )
        verified = gate.verify(publication, now=NOW)
        request = _parse_request(
            confidence="0.9",
            publication_revision=payload["publicationRevision"],
        )

        decision = authorize_remediation(request, verified, now=NOW)

        assert decision.disposition is RemediationDisposition.REQUIRE_T3
        assert decision.reason == "confidence-degraded-to-t3"

    @pytest.mark.parametrize(
        ("candidate_request", "scope", "reason_fragment"),
        [
            (_parse_request(confidence="0.89"), "external_candidate", "confidence"),
            (
                _parse_request(
                    publication_revision=_policy_payload("fixture")["publicationRevision"]
                ),
                "fixture",
                "fixture",
            ),
            (_parse_request(action="delete_database"), "external_candidate", "off-plan"),
            (_parse_request(environment="production"), "external_candidate", "environment"),
        ],
    )
    def test_low_confidence_fixture_offplan_or_environment_mismatch_requires_t3(
        self,
        candidate_request: RemediationRequest,
        scope: str,
        reason_fragment: str,
    ) -> None:
        decision = _decision(scope=scope, request=candidate_request)

        assert decision.disposition is RemediationDisposition.REQUIRE_T3
        assert reason_fragment in decision.reason

    @pytest.mark.parametrize(
        "mutation",
        [
            lambda value: value.update({"policyId": "foreign-policy"}),
            lambda value: value.update({"policyRevision": "sha256:" + "d" * 64}),
            lambda value: value.update({"requestedAt": "2026-07-16T10:10:01Z"}),
            lambda value: value.update({"requestedAt": "2026-07-16T10:04:59Z"}),
            lambda value: value["parameters"].pop("AutomationAssumeRole"),
            lambda value: value["parameters"].update({"Unknown": ["value"]}),
            lambda value: value["parameters"].update({"Cluster": ["prod-eu-1"]}),
        ],
    )
    def test_binding_time_or_parameter_mismatch_requires_t3(
        self,
        mutation: Callable[[dict[str, Any]], None],
    ) -> None:
        payload = _request_payload()
        request = payload["request"]
        assert isinstance(request, dict)
        mutation(request)
        _reseal_request(payload)

        decision = _decision(
            request=parse_remediation_request(json.dumps(payload, sort_keys=True).encode())
        )
        assert decision.disposition is RemediationDisposition.REQUIRE_T3

    def test_raw_or_mutated_inputs_fail_before_decision(self) -> None:
        request = _parse_request()
        object.__setattr__(request, "action", "scale_stateless_service")
        with pytest.raises(RemediationPolicyError, match="raw or mutated"):
            authorize_remediation(request, _verified(), now=NOW)
        with pytest.raises(RemediationPolicyError, match="raw or mutated"):
            authorize_remediation(_parse_request(), object(), now=NOW)  # type: ignore[arg-type]


@pytest.mark.unit
class TestExactStart:
    def test_start_rejoins_document_and_uses_bounded_idempotent_call(self) -> None:
        decision = _decision()
        client = FakeSsmClient(decision)
        notifier = FakeNotifier()

        run = start_t4_remediation(decision, client, notifier, now=NOW)
        call = client.start_calls[0]
        assert run.state is RemediationRunState.FORWARD_RUNNING
        assert call.document_name == "Fixture-RestartStatelessPod"
        assert call.document_version == "1"
        assert call.aws_account_id == ACCOUNT_ID
        assert call.region == "eu-west-1"
        assert call.max_concurrency == "1"
        assert call.max_errors == "0"
        assert call.parameters == {name: list(values) for name, values in decision.parameters}
        assert len(call.client_token) == 36
        assert dict(call.tags) == {
            "sre-harness-action": "restart_stateless_pod",
            "sre-harness-policy": "sre-t4-development-v1",
            "sre-harness-request": "11111111-1111-4111-8111-111111111111",
        }
        assert notifier.notifications[0].event_type is RemediationNotificationType.FORWARD_STARTED

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("document_name", "Foreign"),
            ("document_version", "2"),
            ("document_sha256", "sha256:" + "f" * 64),
            ("owner", "111111111111"),
            ("document_type", "Command"),
            ("status", "Failed"),
            ("schema_version", "2.2"),
        ],
    )
    def test_document_drift_prevents_start(self, field: str, value: str) -> None:
        decision = _decision()
        client = FakeSsmClient(decision)
        key = (
            decision.forward_document.document_name,
            decision.forward_document.document_version,
        )
        client.documents[key] = replace(client.documents[key], **{field: value})

        with pytest.raises(RemediationExecutionError, match="document"):
            start_t4_remediation(decision, client, FakeNotifier(), now=NOW)
        assert client.start_calls == []

    @pytest.mark.parametrize(
        "binding",
        [
            AutomationClientBinding(aws_account_id="111111111111", region="eu-west-1"),
            AutomationClientBinding(aws_account_id=ACCOUNT_ID, region="us-east-1"),
        ],
    )
    def test_client_account_or_region_drift_prevents_start(
        self,
        binding: AutomationClientBinding,
    ) -> None:
        decision = _decision()
        client = FakeSsmClient(decision)
        client.client_binding = binding

        with pytest.raises(RemediationExecutionError, match="client binding"):
            start_t4_remediation(decision, client, FakeNotifier(), now=NOW)
        assert client.describe_calls == []
        assert client.start_calls == []

    def test_non_t4_mutated_expired_or_invalid_execution_id_fails(self) -> None:
        t3 = _decision(scope="fixture")
        with pytest.raises(RemediationExecutionError, match="T4"):
            start_t4_remediation(t3, FakeSsmClient(t3), FakeNotifier(), now=NOW)

        decision = _decision()
        client = FakeSsmClient(decision)
        object.__setattr__(decision, "reason", "mutated")
        with pytest.raises(RemediationExecutionError, match="raw or mutated"):
            start_t4_remediation(decision, client, FakeNotifier(), now=NOW)

        decision = _decision()
        with pytest.raises(RemediationExecutionError, match="expired"):
            start_t4_remediation(
                decision,
                FakeSsmClient(decision),
                FakeNotifier(),
                now=datetime(2026, 7, 17, 10, 0, 1, tzinfo=UTC),
            )

        decision = _decision()
        client = FakeSsmClient(decision)
        client.start_automation = lambda call: "not-a-uuid"  # type: ignore[method-assign]
        with pytest.raises(RemediationExecutionError, match="execution id"):
            start_t4_remediation(decision, client, FakeNotifier(), now=NOW)

    def test_repeated_start_reuses_client_token_and_notification_key(self) -> None:
        decision = _decision()
        client = FakeSsmClient(decision)
        notifier = FakeNotifier()

        first = start_t4_remediation(decision, client, notifier, now=NOW)
        second = start_t4_remediation(decision, client, notifier, now=NOW)

        assert first.forward_execution_id == second.forward_execution_id
        assert client.start_calls[0].client_token == client.start_calls[1].client_token
        assert len(notifier.notifications) == 1

    def test_notification_failure_retries_the_same_started_execution(self) -> None:
        decision = _decision()
        client = FakeSsmClient(decision)

        class FailingNotifier:
            def notify(self, notification: RemediationNotification) -> None:
                raise RuntimeError("fixture notification failure")

        with pytest.raises(RemediationExecutionError, match="notification"):
            start_t4_remediation(decision, client, FailingNotifier(), now=NOW)

        recovered = start_t4_remediation(decision, client, FakeNotifier(), now=NOW)
        assert recovered.forward_execution_id == "00000000-0000-4000-8000-000000000001"
        assert client.start_calls[0].client_token == client.start_calls[1].client_token


@pytest.mark.unit
class TestCompensationLifecycle:
    def test_running_is_stable_and_success_is_terminal(self) -> None:
        decision, client, notifier, run = _started()
        client.set_status(
            run.forward_execution_id,
            decision.forward_document.document_name,
            decision.forward_document.document_version,
            AutomationExecutionStatus.IN_PROGRESS,
        )
        assert reconcile_t4_remediation(run, client, notifier) is run
        assert len(notifier.notifications) == 1

        client.set_status(
            run.forward_execution_id,
            decision.forward_document.document_name,
            decision.forward_document.document_version,
            AutomationExecutionStatus.SUCCESS,
        )
        succeeded = reconcile_t4_remediation(run, client, notifier)
        calls = len(client.execution_calls)
        assert succeeded.state is RemediationRunState.SUCCEEDED
        assert (
            notifier.notifications[-1].event_type is RemediationNotificationType.FORWARD_SUCCEEDED
        )
        assert reconcile_t4_remediation(succeeded, client, notifier) is succeeded
        assert len(client.execution_calls) == calls

    def test_forward_failure_starts_exact_compensation_and_success_rolls_back(self) -> None:
        decision, client, notifier, run = _started()
        client.set_status(
            run.forward_execution_id,
            decision.forward_document.document_name,
            decision.forward_document.document_version,
            AutomationExecutionStatus.FAILED,
        )

        compensating = reconcile_t4_remediation(run, client, notifier)
        rollback_call = client.start_calls[-1]
        assert compensating.state is RemediationRunState.ROLLBACK_RUNNING
        assert rollback_call.document_name == "Fixture-RestartStatelessPod-Rollback"
        assert rollback_call.document_version == "1"
        assert rollback_call.parameters["ForwardExecutionId"] == [run.forward_execution_id]
        assert notifier.notifications[-1].event_type is RemediationNotificationType.ROLLBACK_STARTED

        assert compensating.rollback_execution_id is not None
        client.set_status(
            compensating.rollback_execution_id,
            decision.rollback_document.document_name,
            decision.rollback_document.document_version,
            AutomationExecutionStatus.COMPLETED_WITH_SUCCESS,
        )
        rolled_back = reconcile_t4_remediation(compensating, client, notifier)
        assert rolled_back.state is RemediationRunState.ROLLED_BACK
        assert notifier.notifications[-1].event_type is RemediationNotificationType.ROLLED_BACK

    @pytest.mark.parametrize(
        "status",
        [
            AutomationExecutionStatus.FAILED,
            AutomationExecutionStatus.TIMED_OUT,
            AutomationExecutionStatus.COMPLETED_WITH_FAILURE,
        ],
    )
    def test_compensation_failure_is_terminal_and_never_recursive(
        self,
        status: AutomationExecutionStatus,
    ) -> None:
        decision, client, notifier, run = _started()
        client.set_status(
            run.forward_execution_id,
            decision.forward_document.document_name,
            decision.forward_document.document_version,
            AutomationExecutionStatus.FAILED,
        )
        compensating = reconcile_t4_remediation(run, client, notifier)
        assert compensating.rollback_execution_id is not None
        client.set_status(
            compensating.rollback_execution_id,
            decision.rollback_document.document_name,
            decision.rollback_document.document_version,
            status,
        )

        failed = reconcile_t4_remediation(compensating, client, notifier)
        start_count = len(client.start_calls)
        assert failed.state is RemediationRunState.ROLLBACK_FAILED
        assert notifier.notifications[-1].event_type is RemediationNotificationType.ROLLBACK_FAILED
        assert reconcile_t4_remediation(failed, client, notifier) is failed
        assert len(client.start_calls) == start_count

    @pytest.mark.parametrize(
        "status",
        [
            AutomationExecutionStatus.PENDING_APPROVAL,
            AutomationExecutionStatus.APPROVED,
            AutomationExecutionStatus.REJECTED,
            AutomationExecutionStatus.PENDING_CHANGE_CALENDAR_OVERRIDE,
            AutomationExecutionStatus.CHANGE_CALENDAR_OVERRIDE_APPROVED,
            AutomationExecutionStatus.CHANGE_CALENDAR_OVERRIDE_REJECTED,
        ],
    )
    def test_approval_or_calendar_state_escalates_without_compensation(
        self,
        status: AutomationExecutionStatus,
    ) -> None:
        decision, client, notifier, run = _started()
        client.set_status(
            run.forward_execution_id,
            decision.forward_document.document_name,
            decision.forward_document.document_version,
            status,
        )

        escalated = reconcile_t4_remediation(run, client, notifier)
        assert escalated.state is RemediationRunState.ESCALATED
        assert len(client.start_calls) == 1
        assert notifier.notifications[-1].event_type is RemediationNotificationType.ESCALATED

    def test_rollback_document_drift_escalates_without_starting_it(self) -> None:
        decision, client, notifier, run = _started()
        client.set_status(
            run.forward_execution_id,
            decision.forward_document.document_name,
            decision.forward_document.document_version,
            AutomationExecutionStatus.FAILED,
        )
        key = (
            decision.rollback_document.document_name,
            decision.rollback_document.document_version,
        )
        client.documents[key] = replace(client.documents[key], status="Failed")

        escalated = reconcile_t4_remediation(run, client, notifier)
        assert escalated.state is RemediationRunState.ESCALATED
        assert len(client.start_calls) == 1
        assert "rollback-document" in notifier.notifications[-1].reason

    def test_execution_identity_drift_or_mutated_run_fails_before_action(self) -> None:
        decision, client, notifier, run = _started()
        client.set_status(
            run.forward_execution_id,
            "ForeignDocument",
            decision.forward_document.document_version,
            AutomationExecutionStatus.FAILED,
        )
        with pytest.raises(RemediationExecutionError, match="identity"):
            reconcile_t4_remediation(run, client, notifier)
        assert len(client.start_calls) == 1

        object.__setattr__(run, "action", "scale_stateless_service")
        with pytest.raises(RemediationExecutionError, match="raw or mutated"):
            reconcile_t4_remediation(run, client, notifier)

    def test_reconcile_rechecks_client_account_and_region(self) -> None:
        _, client, notifier, run = _started()
        client.client_binding = AutomationClientBinding(
            aws_account_id=ACCOUNT_ID,
            region="us-east-1",
        )

        with pytest.raises(RemediationExecutionError, match="client binding"):
            reconcile_t4_remediation(run, client, notifier)
        assert client.execution_calls == []

    def test_retry_reuses_rollback_token_and_notifications_are_non_secret(self) -> None:
        decision, client, notifier, run = _started()
        client.set_status(
            run.forward_execution_id,
            decision.forward_document.document_name,
            decision.forward_document.document_version,
            AutomationExecutionStatus.FAILED,
        )

        first = reconcile_t4_remediation(run, client, notifier)
        second = reconcile_t4_remediation(run, client, notifier)

        assert first.rollback_execution_id == second.rollback_execution_id
        assert client.start_calls[1].client_token == client.start_calls[2].client_token
        assert len(notifier.notifications) == 2
        rendered = json.dumps(
            [notification.to_document() for notification in notifier.notifications]
        )
        for secret_value in (ROLE_ARN, "dev-eu-1", "payments-api"):
            assert secret_value not in rendered


def test_checked_in_policy_is_fixture_only_and_cannot_authorize_t4() -> None:
    publication = load_remediation_policy(ROOT / "examples" / "remediation-policy-publication.json")
    gate = RemediationPolicyGate(
        allowed_origins=frozenset({publication.origin}),
        verifiers={publication.verifier_ref: FakeVerifier()},
    )
    verified = gate.verify(publication, now=NOW)
    request = _parse_request(publication_revision=publication.publication_revision)

    decision = authorize_remediation(request, verified, now=NOW)
    assert publication.evidence_scope == "fixture"
    assert decision.disposition is RemediationDisposition.REQUIRE_T3


@pytest.mark.unit
class TestEvidenceBoundary:
    def test_docs_retain_fixture_only_incomplete_boundary(self) -> None:
        repository = ROOT.parents[1]
        spec = (repository / "docs/specs/SPEC-B4-tier4-allowlisted-remediation.md").read_text(
            encoding="utf-8"
        )
        status = (repository / "PROJECT_STATUS.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        normalized_spec = " ".join(spec.split())
        normalized_status = " ".join(status.split())
        normalized_readme = " ".join(readme.split())

        assert "B4 remains incomplete" in normalized_spec
        assert "No checked-in fixture may authorize a live execution" in normalized_spec
        assert "portable fake-client conformance only" in normalized_status
        assert "B4 remains incomplete" in normalized_status
        assert "No AWS account is configured or contacted" in normalized_readme
