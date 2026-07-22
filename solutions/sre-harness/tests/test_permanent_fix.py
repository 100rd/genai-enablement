from __future__ import annotations

import hashlib
import inspect
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from sre_harness.permanent_fix import (
    ChangeSnapshot,
    ChangeState,
    FactoryLifecycle,
    FactoryOutcomeGate,
    IssueCreateCall,
    IssueKind,
    IssueSnapshot,
    IssueState,
    PermanentFixCase,
    PermanentFixError,
    PermanentFixPolicyGate,
    PermanentFixState,
    ProviderKind,
    TrackerBinding,
    load_permanent_fix_policy,
    load_permanent_fix_request,
    open_permanent_fix,
    parse_factory_outcome,
    parse_permanent_fix_policy,
    parse_permanent_fix_request,
    reconcile_permanent_fix,
)

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
ORIGIN = "https://api.github.com"
REPOSITORY = "acme/payments"
INCIDENT_ID = "INC-2048"
TASK_ID = "task-inc-2048"
REQUEST_ID = "879a76dd-6296-455d-82c6-f74e54c95ced"
POLICY_ID = "0e9bb5e4-7fd8-49d7-97fc-6dcc15729b36"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
HEAD_SHA = "d" * 40
MERGE_SHA = "e" * 40
VERIFIER_REF = "verifier://platform-governance/permanent-fix/v1"
OUTCOME_VERIFIER_REF = "verifier://factory-outcome/v1"
OUTCOME_ORIGIN = "https://factory.example.invalid/outcomes/v1"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _revision(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _policy_payload(*, evidence_scope: str = "external_candidate") -> dict[str, Any]:
    policy = {
        "approvalRevision": SHA_A,
        "approvedBy": "human:platform-governance/alice",
        "evidenceScope": evidence_scope,
        "expiresAt": "2026-07-17T12:00:00Z",
        "factories": ["omnius"],
        "maxOutcomeAgeSeconds": 3600,
        "maxRequestAgeSeconds": 7200,
        "origin": ORIGIN,
        "policyId": POLICY_ID,
        "provider": "github",
        "publishedAt": "2026-07-16T11:00:00Z",
        "repository": REPOSITORY,
        "requiredLabels": ["incident", "permanent-fix"],
        "targetBranch": "main",
        "taskClasses": ["B"],
        "verifierRef": VERIFIER_REF,
    }
    return {
        "policy": policy,
        "publicationRevision": _revision(policy),
        "schemaVersion": "sre-harness.permanent-fix-policy-publication/v1",
    }


def _request_payload(
    *,
    evidence_scope: str = "external_candidate",
    policy_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy_payload = policy_payload or _policy_payload()
    request = {
        "body": (
            "The mitigation restored service. Produce the durable code fix, preserve rollback, "
            "and satisfy AC-INC-2048."
        ),
        "evidenceRefs": ["evidence://incident/INC-2048", "evidence://rca/INC-2048/v1"],
        "evidenceScope": evidence_scope,
        "expiresAt": "2026-07-16T14:00:00Z",
        "factory": "omnius",
        "incidentId": INCIDENT_ID,
        "labels": ["payments"],
        "origin": ORIGIN,
        "policyId": policy_payload["policy"]["policyId"],
        "policyRevision": policy_payload["publicationRevision"],
        "priority": "P0",
        "provider": "github",
        "repository": REPOSITORY,
        "requestId": REQUEST_ID,
        "requestedAt": "2026-07-16T11:30:00Z",
        "targetBranch": "main",
        "taskClass": "B",
        "taskId": TASK_ID,
        "title": "Permanent fix for INC-2048 payments regression",
    }
    return {
        "request": request,
        "requestRevision": _revision(request),
        "schemaVersion": "sre-harness.permanent-fix-request/v1",
    }


def _outcome_payload(
    *,
    lifecycle: str = "GATED",
    verdict: str = "pass",
    gate: str = "human",
    head_revision: str = HEAD_SHA,
    occurred_at: str = "2026-07-16T11:55:00Z",
) -> dict[str, Any]:
    outcome = {
        "changeNumber": 42,
        "evidenceManifest": f"evidence://manifest/{SHA_C}",
        "evidenceScope": "external_candidate",
        "factory": "omnius",
        "gate": gate,
        "incidentId": INCIDENT_ID,
        "lifecycle": lifecycle,
        "occurredAt": occurred_at,
        "origin": OUTCOME_ORIGIN,
        "provider": "github",
        "repository": REPOSITORY,
        "taskId": TASK_ID,
        "taskRevision": head_revision,
        "verdict": verdict,
        "verifierRef": OUTCOME_VERIFIER_REF,
    }
    return {
        "outcome": outcome,
        "outcomeRevision": _revision(outcome),
        "schemaVersion": "sre-harness.factory-outcome/v1",
    }


class FakePolicyVerifier:
    def __init__(self, result: object = True, *, mutate: bool = False) -> None:
        self.result = result
        self.mutate = mutate
        self.calls = 0

    def verify(self, publication: object) -> object:
        self.calls += 1
        if self.mutate:
            object.__setattr__(publication, "repository", "evil/repository")
        return self.result


class FakeOutcomeVerifier:
    def __init__(self, result: object = True, *, mutate: bool = False) -> None:
        self.result = result
        self.mutate = mutate
        self.calls = 0

    def verify(self, outcome: object) -> object:
        self.calls += 1
        if self.mutate:
            object.__setattr__(outcome, "task_id", "foreign-task")
        return self.result


class FakeAudit:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[object] = []

    def append(self, event: object) -> None:
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.events.append(event)


class FakeProvider:
    def __init__(
        self,
        *,
        binding: TrackerBinding | None = None,
        issue: IssueSnapshot | tuple[IssueSnapshot, ...] | None = None,
        change: ChangeSnapshot | tuple[ChangeSnapshot, ...] | None = None,
    ) -> None:
        self._binding = binding or TrackerBinding(ProviderKind.GITHUB, ORIGIN, REPOSITORY)
        self.issue = issue
        self.change = change
        self.binding_calls = 0
        self.find_issue_calls: list[str] = []
        self.create_calls: list[IssueCreateCall] = []
        self.read_issue_calls: list[int] = []
        self.find_change_calls: list[tuple[str, str]] = []

    def binding(self) -> TrackerBinding:
        self.binding_calls += 1
        return self._binding

    def find_issue(self, dedupe_key: str) -> IssueSnapshot | tuple[IssueSnapshot, ...] | None:
        self.find_issue_calls.append(dedupe_key)
        return self.issue

    def create_issue(self, call: IssueCreateCall) -> IssueSnapshot:
        self.create_calls.append(call)
        if self.issue is None:
            self.issue = IssueSnapshot(
                repository=REPOSITORY,
                number=2048,
                kind=IssueKind.ISSUE,
                state=IssueState.OPEN,
                dedupe_key=call.dedupe_key,
                incident_id=INCIDENT_ID,
                task_id=TASK_ID,
                request_revision=call.request_revision,
            )
        assert type(self.issue) is IssueSnapshot
        return self.issue

    def read_issue(self, number: int) -> IssueSnapshot:
        self.read_issue_calls.append(number)
        assert type(self.issue) is IssueSnapshot
        return self.issue

    def find_change(
        self, incident_id: str, task_id: str
    ) -> ChangeSnapshot | tuple[ChangeSnapshot, ...] | None:
        self.find_change_calls.append((incident_id, task_id))
        return self.change


def _verified_policy(
    *,
    verifier: FakePolicyVerifier | None = None,
    now: datetime = NOW,
    payload: dict[str, Any] | None = None,
):
    publication = parse_permanent_fix_policy(_canonical(payload or _policy_payload()))
    return PermanentFixPolicyGate(
        allowed_origins=frozenset({ORIGIN}),
        verifiers={VERIFIER_REF: verifier or FakePolicyVerifier()},
    ).verify(publication, now=now)


def _verified_outcome(
    *,
    lifecycle: str = "GATED",
    verifier: FakeOutcomeVerifier | None = None,
    now: datetime = NOW,
    payload: dict[str, Any] | None = None,
):
    outcome = parse_factory_outcome(_canonical(payload or _outcome_payload(lifecycle=lifecycle)))
    return FactoryOutcomeGate(
        allowed_origins=frozenset({OUTCOME_ORIGIN}),
        verifiers={OUTCOME_VERIFIER_REF: verifier or FakeOutcomeVerifier()},
        max_age_seconds=3600,
    ).verify(outcome, now=now)


def _open_case(
    *,
    provider: FakeProvider | None = None,
    audit: FakeAudit | None = None,
) -> tuple[PermanentFixCase, FakeProvider, FakeAudit]:
    provider = provider or FakeProvider()
    audit = audit or FakeAudit()
    request = parse_permanent_fix_request(_canonical(_request_payload()))
    case = open_permanent_fix(request, _verified_policy(), provider, audit, now=NOW)
    return case, provider, audit


def _change(
    *,
    state: ChangeState = ChangeState.OPEN,
    number: int = 42,
    head_revision: str = HEAD_SHA,
    merged_revision: str | None = None,
    task_id: str = TASK_ID,
    incident_id: str = INCIDENT_ID,
    repository: str = REPOSITORY,
    target_branch: str = "main",
) -> ChangeSnapshot:
    return ChangeSnapshot(
        repository=repository,
        number=number,
        state=state,
        head_revision=head_revision,
        target_branch=target_branch,
        incident_id=incident_id,
        task_id=task_id,
        merged_revision=merged_revision,
    )


@pytest.mark.unit
class TestClosedRequest:
    def test_canonical_request_loads_and_is_content_addressed(self) -> None:
        request = parse_permanent_fix_request(_canonical(_request_payload()))

        assert request.incident_id == INCIDENT_ID
        assert request.task_id == TASK_ID
        assert request.priority == "P0"
        assert request.request_revision == _request_payload()["requestRevision"]

    @pytest.mark.parametrize(
        ("mutation", "match"),
        [
            (lambda value: value.update(extra=True), "fields"),
            (lambda value: value["request"].update(autoMerge=True), "fields"),
            (lambda value: value["request"].update(closeIssue=True), "fields"),
            (lambda value: value["request"].update(priority="P1"), "priority"),
            (lambda value: value["request"].update(provider="bitbucket"), "provider"),
            (lambda value: value["request"].update(taskId=""), "task"),
            (lambda value: value["request"].update(origin="https://[::1"), "origin"),
            (lambda value: value["request"].update(requestedAt="2026-07-16"), "timestamp"),
            (lambda value: value["request"].update(expiresAt="2026-07-16T11:00:00Z"), "expiry"),
            (lambda value: value["request"].update(evidenceRefs=[]), "evidence"),
            (lambda value: value["request"].update(labels=["incident"]), "reserved"),
            (
                lambda value: value["request"].update(
                    body="token=ghp_abcdefghijklmnopqrstuvwxyz123456"
                ),
                "sensitive",
            ),
            (lambda value: value.update(requestRevision=SHA_A), "revision"),
        ],
    )
    def test_request_rejects_closed_shape_authority_and_invalid_values(
        self, mutation: Any, match: str
    ) -> None:
        payload = _request_payload()
        mutation(payload)
        if payload["requestRevision"] != SHA_A:
            payload["requestRevision"] = _revision(payload["request"])

        with pytest.raises(PermanentFixError, match=match):
            parse_permanent_fix_request(_canonical(payload))

    def test_malformed_duplicate_nonfinite_non_utf8_and_noncanonical_json_fail(
        self,
    ) -> None:
        with pytest.raises(PermanentFixError, match="invalid JSON"):
            parse_permanent_fix_request(b"{")
        with pytest.raises(PermanentFixError, match="duplicate"):
            parse_permanent_fix_request(b'{"schemaVersion":"x","schemaVersion":"x"}')
        with pytest.raises(PermanentFixError, match="finite"):
            parse_permanent_fix_request(b'{"n":NaN}')
        with pytest.raises(PermanentFixError, match="UTF-8"):
            parse_permanent_fix_request(b"\xff")
        pretty = json.dumps(_request_payload(), indent=2).encode()
        with pytest.raises(PermanentFixError, match="canonical"):
            parse_permanent_fix_request(pretty)

    def test_loader_rejects_symlink_oversize_and_non_file(self, tmp_path: Path) -> None:
        target = tmp_path / "request.json"
        target.write_bytes(_canonical(_request_payload()))
        link = tmp_path / "request-link.json"
        link.symlink_to(target)
        with pytest.raises(PermanentFixError, match="symlink"):
            load_permanent_fix_request(link)

        target.write_bytes(b"x" * (1024 * 1024 + 1))
        with pytest.raises(PermanentFixError, match="large"):
            load_permanent_fix_request(target)

        with pytest.raises(PermanentFixError, match="regular file"):
            load_permanent_fix_request(tmp_path)

    def test_checked_request_fixture_is_fixture_only(self) -> None:
        path = Path(__file__).parents[1] / "examples" / "permanent-fix-request.json"
        request = load_permanent_fix_request(path)

        assert request.evidence_scope == "fixture"

    @pytest.mark.parametrize(
        ("reference", "match"),
        [
            ("https://user:password@example.com/evidence", "credential-free"),
            ("https://example.com/evidence?access_token=fixture-secret", "credential-free"),
            ("https://:/evidence", "invalid"),
            ("evidence://:/path", "invalid"),
            ("https://[::1/evidence", "invalid"),
            ("https://example.com:bad/evidence", "invalid"),
        ],
    )
    def test_request_rejects_credential_bearing_or_malformed_evidence_refs(
        self, reference: str, match: str
    ) -> None:
        payload = _request_payload()
        payload["request"]["evidenceRefs"] = [reference]
        payload["requestRevision"] = _revision(payload["request"])

        with pytest.raises(PermanentFixError, match=match):
            parse_permanent_fix_request(_canonical(payload))


@pytest.mark.unit
class TestPolicyCapability:
    def test_exact_external_verifier_issues_opaque_capability(self) -> None:
        verifier = FakePolicyVerifier()

        policy = _verified_policy(verifier=verifier)

        assert policy.repository == REPOSITORY
        assert policy.publication_revision == _policy_payload()["publicationRevision"]
        assert verifier.calls == 1

    @pytest.mark.parametrize("result", [False, 1, "true", None])
    def test_false_or_truthy_nonboolean_verification_fails(self, result: object) -> None:
        with pytest.raises(PermanentFixError, match="verification"):
            _verified_policy(verifier=FakePolicyVerifier(result))

    def test_untrusted_mutated_future_expired_or_fixture_policy_fails(self) -> None:
        publication = parse_permanent_fix_policy(_canonical(_policy_payload()))
        with pytest.raises(PermanentFixError, match="origin"):
            PermanentFixPolicyGate(
                allowed_origins=frozenset(),
                verifiers={VERIFIER_REF: FakePolicyVerifier()},
            ).verify(publication, now=NOW)
        with pytest.raises(PermanentFixError, match="mutated"):
            _verified_policy(verifier=FakePolicyVerifier(mutate=True))
        with pytest.raises(PermanentFixError, match="future"):
            _verified_policy(now=datetime(2026, 7, 16, 10, 59, tzinfo=UTC))
        with pytest.raises(PermanentFixError, match="expired"):
            _verified_policy(now=datetime(2026, 7, 17, 12, 0, tzinfo=UTC))
        with pytest.raises(PermanentFixError, match="fixture"):
            _verified_policy(payload=_policy_payload(evidence_scope="fixture"))

    def test_policy_is_closed_and_checked_fixture_is_inert(self) -> None:
        payload = _policy_payload()
        payload["policy"]["mergeWhenPipelineSucceeds"] = True
        payload["publicationRevision"] = _revision(payload["policy"])
        with pytest.raises(PermanentFixError, match="fields"):
            parse_permanent_fix_policy(_canonical(payload))

        path = Path(__file__).parents[1] / "examples" / "permanent-fix-policy-publication.json"
        publication = load_permanent_fix_policy(path)
        assert publication.evidence_scope == "fixture"

    def test_policy_requires_incident_and_permanent_fix_labels(self) -> None:
        payload = _policy_payload()
        payload["policy"]["requiredLabels"] = ["incident"]
        payload["publicationRevision"] = _revision(payload["policy"])

        with pytest.raises(PermanentFixError, match="governance labels"):
            parse_permanent_fix_policy(_canonical(payload))

    def test_policy_document_rejects_malformed_duplicate_nonfinite_and_non_utf8(self) -> None:
        for document, match in (
            (b"{", "invalid JSON"),
            (b'{"schemaVersion":"x","schemaVersion":"x"}', "duplicate"),
            (b'{"n":NaN}', "finite"),
            (b"\xff", "UTF-8"),
        ):
            with pytest.raises(PermanentFixError, match=match):
                parse_permanent_fix_policy(document)


@pytest.mark.unit
class TestIssueOpening:
    def test_absent_issue_creates_one_bounded_call_and_audits(self) -> None:
        case, provider, audit = _open_case()

        assert case.state is PermanentFixState.ISSUE_OPEN
        assert case.issue_number == 2048
        assert len(provider.find_issue_calls) == 1
        assert len(provider.create_calls) == 1
        call = provider.create_calls[0]
        assert call.repository == REPOSITORY
        assert call.labels == ("incident", "payments", "permanent-fix")
        assert call.body.endswith(f"<!-- sre-harness-permanent-fix:{call.dedupe_key} -->")
        assert "assignee" not in repr(call).lower()
        assert "merge" not in repr(call).lower()
        assert len(audit.events) == 1

    def test_existing_exact_issue_is_adopted_without_create(self) -> None:
        request = parse_permanent_fix_request(_canonical(_request_payload()))
        policy = _verified_policy()
        bootstrap = FakeProvider()
        first = open_permanent_fix(request, policy, bootstrap, FakeAudit(), now=NOW)
        provider = FakeProvider(issue=bootstrap.issue)

        adopted = open_permanent_fix(request, policy, provider, FakeAudit(), now=NOW)

        assert adopted.issue_number == first.issue_number
        assert provider.create_calls == []

    def test_ambiguous_dedupe_search_fails_without_create(self) -> None:
        request = parse_permanent_fix_request(_canonical(_request_payload()))
        bootstrap = FakeProvider()
        open_permanent_fix(request, _verified_policy(), bootstrap, FakeAudit(), now=NOW)
        assert type(bootstrap.issue) is IssueSnapshot
        provider = FakeProvider(issue=(bootstrap.issue, bootstrap.issue))

        with pytest.raises(PermanentFixError, match="ambiguous"):
            open_permanent_fix(request, _verified_policy(), provider, FakeAudit(), now=NOW)

        assert provider.create_calls == []

    def test_retry_after_audit_failure_adopts_provider_deduped_issue(self) -> None:
        provider = FakeProvider()
        request = parse_permanent_fix_request(_canonical(_request_payload()))
        policy = _verified_policy()
        with pytest.raises(RuntimeError, match="audit"):
            open_permanent_fix(request, policy, provider, FakeAudit(fail=True), now=NOW)

        case = open_permanent_fix(request, policy, provider, FakeAudit(), now=NOW)

        assert case.issue_number == 2048
        assert len(provider.create_calls) == 1

    @pytest.mark.parametrize(
        ("binding", "match"),
        [
            (TrackerBinding(ProviderKind.GITLAB, ORIGIN, REPOSITORY), "provider"),
            (TrackerBinding(ProviderKind.GITHUB, "https://evil.example", REPOSITORY), "origin"),
            (TrackerBinding(ProviderKind.GITHUB, ORIGIN, "evil/repository"), "repository"),
        ],
    )
    def test_foreign_provider_binding_fails_before_search(
        self, binding: TrackerBinding, match: str
    ) -> None:
        provider = FakeProvider(binding=binding)
        request = parse_permanent_fix_request(_canonical(_request_payload()))

        with pytest.raises(PermanentFixError, match=match):
            open_permanent_fix(request, _verified_policy(), provider, FakeAudit(), now=NOW)

        assert provider.find_issue_calls == []

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("kind", IssueKind.CHANGE, "issue kind"),
            ("kind", "issue", "issue kind"),
            ("repository", "evil/repository", "repository"),
            ("repository", object(), "repository"),
            ("number", True, "number"),
            ("dedupe_key", object(), "dedupe"),
            ("incident_id", "INC-evil", "incident"),
            ("incident_id", object(), "incident"),
            ("task_id", "task-evil", "task"),
            ("task_id", object(), "task"),
            ("request_revision", SHA_A, "request"),
            ("request_revision", object(), "request"),
            ("state", IssueState.CLOSED, "closed"),
            ("state", "open", "state"),
        ],
    )
    def test_foreign_pr_as_issue_or_closed_create_result_fails(
        self, field: str, value: object, match: str
    ) -> None:
        provider = FakeProvider()
        request = parse_permanent_fix_request(_canonical(_request_payload()))
        baseline = open_permanent_fix(request, _verified_policy(), provider, FakeAudit(), now=NOW)
        assert provider.issue is not None
        values = vars(provider.issue).copy()
        values[field] = value
        provider.issue = IssueSnapshot(**values)
        provider.create_calls.clear()

        with pytest.raises(PermanentFixError, match=match):
            open_permanent_fix(request, _verified_policy(), provider, FakeAudit(), now=NOW)

        assert baseline.issue_number == 2048
        assert provider.create_calls == []

    def test_fixture_expired_or_policy_drift_never_binds_provider(self) -> None:
        provider = FakeProvider()
        fixture_request = parse_permanent_fix_request(
            _canonical(_request_payload(evidence_scope="fixture"))
        )
        with pytest.raises(PermanentFixError, match="fixture"):
            open_permanent_fix(fixture_request, _verified_policy(), provider, FakeAudit(), now=NOW)

        request = parse_permanent_fix_request(_canonical(_request_payload()))
        with pytest.raises(PermanentFixError, match="expired"):
            open_permanent_fix(
                request,
                _verified_policy(),
                provider,
                FakeAudit(),
                now=datetime(2026, 7, 16, 14, 0, tzinfo=UTC),
            )

        other_payload = _policy_payload()
        other_payload["policy"]["policyId"] = "c98519e4-a954-4794-854b-c7dc1bc21b55"
        other_payload["publicationRevision"] = _revision(other_payload["policy"])
        with pytest.raises(PermanentFixError, match="policy"):
            open_permanent_fix(
                request,
                _verified_policy(payload=other_payload),
                provider,
                FakeAudit(),
                now=NOW,
            )

        assert provider.binding_calls == 0


@pytest.mark.unit
class TestFactoryOutcomeAuthority:
    def test_exact_boolean_verifier_issues_opaque_outcome(self) -> None:
        verifier = FakeOutcomeVerifier()

        outcome = _verified_outcome(verifier=verifier)

        assert outcome.task_id == TASK_ID
        assert outcome.lifecycle is FactoryLifecycle.GATED
        assert verifier.calls == 1

    @pytest.mark.parametrize("result", [False, 1, "true", None])
    def test_truthy_nonboolean_outcome_verification_fails(self, result: object) -> None:
        with pytest.raises(PermanentFixError, match="verification"):
            _verified_outcome(verifier=FakeOutcomeVerifier(result))

    def test_outcome_rejects_mutation_origin_fixture_future_and_staleness(self) -> None:
        with pytest.raises(PermanentFixError, match="mutated"):
            _verified_outcome(verifier=FakeOutcomeVerifier(mutate=True))

        outcome = parse_factory_outcome(_canonical(_outcome_payload()))
        with pytest.raises(PermanentFixError, match="origin"):
            FactoryOutcomeGate(
                allowed_origins=frozenset(),
                verifiers={OUTCOME_VERIFIER_REF: FakeOutcomeVerifier()},
                max_age_seconds=3600,
            ).verify(outcome, now=NOW)

        fixture = _outcome_payload()
        fixture["outcome"]["evidenceScope"] = "fixture"
        fixture["outcomeRevision"] = _revision(fixture["outcome"])
        with pytest.raises(PermanentFixError, match="fixture"):
            _verified_outcome(payload=fixture)

        with pytest.raises(PermanentFixError, match="future"):
            _verified_outcome(payload=_outcome_payload(occurred_at="2026-07-16T12:01:00Z"))
        with pytest.raises(PermanentFixError, match="stale"):
            _verified_outcome(payload=_outcome_payload(occurred_at="2026-07-16T10:59:59Z"))

    @pytest.mark.parametrize(
        ("mutation", "match"),
        [
            (lambda value: value.update(extra=True), "fields"),
            (lambda value: value["outcome"].update(lifecycle="DONE"), "lifecycle"),
            (lambda value: value["outcome"].update(taskRevision=SHA_A), "head"),
            (lambda value: value["outcome"].update(origin="https://[::1"), "origin"),
            (lambda value: value["outcome"].update(gate="agent"), "gate"),
            (lambda value: value["outcome"].update(verdict="green"), "verdict"),
            (lambda value: value.update(outcomeRevision=SHA_A), "revision"),
        ],
    )
    def test_outcome_schema_is_closed_and_exact(self, mutation: Any, match: str) -> None:
        payload = _outcome_payload()
        mutation(payload)
        if payload["outcomeRevision"] != SHA_A:
            payload["outcomeRevision"] = _revision(payload["outcome"])

        with pytest.raises(PermanentFixError, match=match):
            parse_factory_outcome(_canonical(payload))

    def test_outcome_document_rejects_malformed_duplicate_nonfinite_and_non_utf8(self) -> None:
        for document, match in (
            (b"{", "invalid JSON"),
            (b'{"schemaVersion":"x","schemaVersion":"x"}', "duplicate"),
            (b'{"n":NaN}', "finite"),
            (b"\xff", "UTF-8"),
        ):
            with pytest.raises(PermanentFixError, match=match):
                parse_factory_outcome(document)

    @pytest.mark.parametrize(
        ("reference", "match"),
        [
            ("https://user:password@example.com/manifest", "credential-free"),
            ("https://example.com/manifest?access_token=fixture-secret", "credential-free"),
            ("https://:/manifest", "invalid"),
            ("evidence://:/manifest", "invalid"),
            ("https://[::1/manifest", "invalid"),
            ("https://example.com:bad/manifest", "invalid"),
        ],
    )
    def test_outcome_rejects_credential_bearing_or_malformed_evidence_manifest(
        self, reference: str, match: str
    ) -> None:
        payload = _outcome_payload()
        payload["outcome"]["evidenceManifest"] = reference
        payload["outcomeRevision"] = _revision(payload["outcome"])

        with pytest.raises(PermanentFixError, match=match):
            parse_factory_outcome(_canonical(payload))


@pytest.mark.unit
class TestChaseLifecycle:
    def test_no_change_remains_issue_open_without_audit_noise(self) -> None:
        case, provider, audit = _open_case()

        same = reconcile_permanent_fix(case, provider, None, audit, now=NOW)

        assert same is case
        assert len(audit.events) == 1

    def test_exact_open_change_advances_to_change_open(self) -> None:
        case, provider, audit = _open_case()
        provider.change = _change()

        changed = reconcile_permanent_fix(case, provider, None, audit, now=NOW)

        assert changed.state is PermanentFixState.CHANGE_OPEN
        assert changed.change_number == 42
        assert changed.head_revision == HEAD_SHA

    def test_produced_verified_and_gated_outcomes_advance_monotonically(self) -> None:
        case, provider, audit = _open_case()
        provider.change = _change()

        produced = reconcile_permanent_fix(
            case, provider, _verified_outcome(lifecycle="PRODUCED"), audit, now=NOW
        )
        verified = reconcile_permanent_fix(
            produced, provider, _verified_outcome(lifecycle="VERIFIED"), audit, now=NOW
        )
        gated = reconcile_permanent_fix(
            verified, provider, _verified_outcome(lifecycle="GATED"), audit, now=NOW
        )

        assert produced.state is PermanentFixState.VERIFYING
        assert verified.state is PermanentFixState.VERIFYING
        assert gated.state is PermanentFixState.AWAITING_HUMAN_MERGE
        assert len(audit.events) == 4

    def test_policy_outcome_age_is_rechecked_at_reconciliation(self) -> None:
        policy_payload = _policy_payload()
        policy_payload["policy"]["maxOutcomeAgeSeconds"] = 60
        policy_payload["publicationRevision"] = _revision(policy_payload["policy"])
        request_payload = _request_payload(policy_payload=policy_payload)
        request = parse_permanent_fix_request(_canonical(request_payload))
        policy = _verified_policy(payload=policy_payload)
        provider = FakeProvider()
        audit = FakeAudit()
        case = open_permanent_fix(request, policy, provider, audit, now=NOW)
        provider.change = _change()

        result = reconcile_permanent_fix(
            case, provider, _verified_outcome(lifecycle="GATED"), audit, now=NOW
        )

        assert result.state is PermanentFixState.ESCALATED
        assert "policy age" in result.reason

    def test_landed_requires_merged_provider_and_exact_factory_head(self) -> None:
        case, provider, audit = _open_case()
        provider.change = _change(state=ChangeState.MERGED, merged_revision=MERGE_SHA)

        landed = reconcile_permanent_fix(
            case, provider, _verified_outcome(lifecycle="LANDED"), audit, now=NOW
        )

        assert landed.state is PermanentFixState.LANDED
        assert landed.merged_revision == MERGE_SHA

    def test_provider_merge_or_outcome_alone_never_lands(self) -> None:
        case, provider, audit = _open_case()
        provider.change = _change(state=ChangeState.MERGED, merged_revision=MERGE_SHA)

        provider_only = reconcile_permanent_fix(case, provider, None, audit, now=NOW)
        assert provider_only.state is PermanentFixState.CHANGE_OPEN
        assert provider_only.reason == "provider reports merge; exact factory outcome is pending"
        assert provider_only.merged_revision == MERGE_SHA

        case2, provider2, audit2 = _open_case()
        provider2.change = _change(state=ChangeState.OPEN)
        outcome_only = reconcile_permanent_fix(
            case2,
            provider2,
            _verified_outcome(lifecycle="LANDED"),
            audit2,
            now=NOW,
        )
        assert outcome_only.state is PermanentFixState.AWAITING_HUMAN_MERGE

    @pytest.mark.parametrize(
        ("lifecycle", "provider_state", "expected_state"),
        [
            ("PRODUCED", ChangeState.OPEN, PermanentFixState.VERIFYING),
            ("VERIFIED", ChangeState.OPEN, PermanentFixState.VERIFYING),
            ("GATED", ChangeState.OPEN, PermanentFixState.AWAITING_HUMAN_MERGE),
            ("GATED", ChangeState.MERGED, PermanentFixState.AWAITING_HUMAN_MERGE),
        ],
    )
    def test_missing_outcome_preserves_monotonic_state(
        self,
        lifecycle: str,
        provider_state: ChangeState,
        expected_state: PermanentFixState,
    ) -> None:
        case, provider, audit = _open_case()
        provider.change = _change()
        advanced = reconcile_permanent_fix(
            case, provider, _verified_outcome(lifecycle=lifecycle), audit, now=NOW
        )
        provider.change = _change(
            state=provider_state,
            merged_revision=MERGE_SHA if provider_state is ChangeState.MERGED else None,
        )

        observed = reconcile_permanent_fix(advanced, provider, None, audit, now=NOW)

        assert observed.state is expected_state
        assert observed.lifecycle_rank == advanced.lifecycle_rank
        if provider_state is ChangeState.MERGED:
            assert observed.merged_revision == MERGE_SHA
            assert "factory LANDED outcome" in observed.reason
            assert "human merge gate is pending" not in observed.reason
        else:
            assert observed is advanced

    @pytest.mark.parametrize("lifecycle", [None, "GATED"])
    def test_tracked_change_disappearance_escalates(self, lifecycle: str | None) -> None:
        case, provider, audit = _open_case()
        provider.change = _change()
        tracked = reconcile_permanent_fix(
            case,
            provider,
            _verified_outcome(lifecycle=lifecycle) if lifecycle is not None else None,
            audit,
            now=NOW,
        )
        provider.change = None

        result = reconcile_permanent_fix(tracked, provider, None, audit, now=NOW)

        assert result.state is PermanentFixState.ESCALATED
        assert "missing" in result.reason

    @pytest.mark.parametrize(
        ("next_change", "match"),
        [
            (_change(state=ChangeState.OPEN), "regressed"),
            (
                _change(state=ChangeState.MERGED, merged_revision="f" * 40),
                "merge revision",
            ),
        ],
    )
    def test_provider_merge_observation_is_sealed_and_cannot_regress(
        self, next_change: ChangeSnapshot, match: str
    ) -> None:
        case, provider, audit = _open_case()
        provider.change = _change(state=ChangeState.MERGED, merged_revision=MERGE_SHA)
        merged = reconcile_permanent_fix(case, provider, None, audit, now=NOW)
        assert merged.merged_revision == MERGE_SHA
        provider.change = next_change

        result = reconcile_permanent_fix(merged, provider, None, audit, now=NOW)

        assert result.state is PermanentFixState.ESCALATED
        assert match in result.reason

    def test_prematurely_closed_issue_never_lands_with_exact_two_source_evidence(
        self,
    ) -> None:
        case, provider, audit = _open_case()
        assert type(provider.issue) is IssueSnapshot
        provider.issue = IssueSnapshot(**{**vars(provider.issue), "state": IssueState.CLOSED})
        provider.change = _change(state=ChangeState.MERGED, merged_revision=MERGE_SHA)

        result = reconcile_permanent_fix(
            case, provider, _verified_outcome(lifecycle="LANDED"), audit, now=NOW
        )

        assert result.state is PermanentFixState.ESCALATED
        assert "closed" in result.reason

    @pytest.mark.parametrize(
        ("change", "match"),
        [
            ((_change(), _change()), "multiple"),
            (_change(repository="evil/repository"), "repository"),
            (_change(repository=object()), "repository"),  # type: ignore[arg-type]
            (_change(number=True), "number"),
            (_change(task_id="task-evil"), "task"),
            (_change(task_id=object()), "task"),  # type: ignore[arg-type]
            (_change(incident_id="INC-evil"), "incident"),
            (_change(incident_id=object()), "incident"),  # type: ignore[arg-type]
            (_change(target_branch="release"), "target"),
            (_change(target_branch=object()), "target"),  # type: ignore[arg-type]
            (_change(state="open"), "state"),  # type: ignore[arg-type]
            (_change(head_revision=SHA_A), "head"),
            (_change(head_revision=123), "head"),  # type: ignore[arg-type]
            (_change(head_revision=[]), "head"),  # type: ignore[arg-type]
            (_change(head_revision="password=provider-secret"), "head"),
            (_change(head_revision=float("nan")), "head"),  # type: ignore[arg-type]
            (_change(head_revision=object()), "head"),  # type: ignore[arg-type]
            (
                _change(
                    state=ChangeState.MERGED,
                    merged_revision=123,  # type: ignore[arg-type]
                ),
                "merge revision",
            ),
            (
                _change(
                    state=ChangeState.MERGED,
                    merged_revision="access_token=provider-secret",
                ),
                "merge revision",
            ),
            (_change(state=ChangeState.CLOSED), "closed"),
        ],
    )
    def test_ambiguous_or_foreign_change_escalates(
        self, change: ChangeSnapshot | tuple[ChangeSnapshot, ...], match: str
    ) -> None:
        case, provider, audit = _open_case()
        provider.change = change

        result = reconcile_permanent_fix(case, provider, None, audit, now=NOW)

        assert result.state is PermanentFixState.ESCALATED
        assert match in result.reason
        assert result.change_number is None
        assert result.head_revision is None
        assert result.merged_revision is None
        assert len(audit.events) == 2
        assert "provider-secret" not in f"{result!r}{audit.events[-1]!r}"

    @pytest.mark.parametrize(
        ("payload_change", "match"),
        [
            ({"taskId": "task-evil"}, "task"),
            ({"incidentId": "INC-evil"}, "incident"),
            ({"repository": "evil/repository"}, "repository"),
            ({"changeNumber": 99}, "change"),
            ({"taskRevision": "f" * 40}, "head"),
            ({"verdict": "fail"}, "verdict"),
            ({"gate": "auto", "lifecycle": "GATED"}, "human"),
            ({"lifecycle": "REJECTED", "verdict": "fail", "gate": "rejected"}, "terminal"),
        ],
    )
    def test_foreign_failed_or_ungated_outcome_escalates(
        self, payload_change: dict[str, object], match: str
    ) -> None:
        case, provider, audit = _open_case()
        provider.change = _change()
        payload = _outcome_payload()
        payload["outcome"].update(payload_change)
        payload["outcomeRevision"] = _revision(payload["outcome"])

        result = reconcile_permanent_fix(
            case, provider, _verified_outcome(payload=payload), audit, now=NOW
        )

        assert result.state is PermanentFixState.ESCALATED
        assert match in result.reason

    def test_lifecycle_regression_and_merged_head_mismatch_escalate(self) -> None:
        case, provider, audit = _open_case()
        provider.change = _change()
        gated = reconcile_permanent_fix(
            case, provider, _verified_outcome(lifecycle="GATED"), audit, now=NOW
        )

        regressed = reconcile_permanent_fix(
            gated, provider, _verified_outcome(lifecycle="VERIFIED"), audit, now=NOW
        )
        assert regressed.state is PermanentFixState.ESCALATED
        assert "regressed" in regressed.reason

        case2, provider2, audit2 = _open_case()
        provider2.change = _change(
            state=ChangeState.MERGED,
            head_revision="f" * 40,
            merged_revision=MERGE_SHA,
        )
        mismatch = reconcile_permanent_fix(
            case2, provider2, _verified_outcome(lifecycle="LANDED"), audit2, now=NOW
        )
        assert mismatch.state is PermanentFixState.ESCALATED
        assert "head" in mismatch.reason

    def test_closed_issue_before_landed_and_deadline_escalate(self) -> None:
        case, provider, audit = _open_case()
        assert provider.issue is not None
        provider.issue = IssueSnapshot(**{**vars(provider.issue), "state": IssueState.CLOSED})

        closed = reconcile_permanent_fix(case, provider, None, audit, now=NOW)
        assert closed.state is PermanentFixState.ESCALATED
        assert "closed" in closed.reason

        case2, provider2, audit2 = _open_case()
        expired = reconcile_permanent_fix(
            case2,
            provider2,
            None,
            audit2,
            now=datetime(2026, 7, 16, 14, 0, tzinfo=UTC),
        )
        assert expired.state is PermanentFixState.ESCALATED
        assert "deadline" in expired.reason

    def test_terminal_states_are_stable_without_provider_calls(self) -> None:
        case, provider, audit = _open_case()
        provider.change = _change(state=ChangeState.MERGED, merged_revision=MERGE_SHA)
        landed = reconcile_permanent_fix(
            case, provider, _verified_outcome(lifecycle="LANDED"), audit, now=NOW
        )
        reads = (len(provider.read_issue_calls), len(provider.find_change_calls))

        same = reconcile_permanent_fix(landed, provider, None, audit, now=NOW + timedelta(days=1))

        assert same is landed
        assert reads == (len(provider.read_issue_calls), len(provider.find_change_calls))

    def test_audit_failure_does_not_return_transition(self) -> None:
        case, provider, _ = _open_case()
        provider.change = _change()
        with pytest.raises(RuntimeError, match="audit"):
            reconcile_permanent_fix(case, provider, None, FakeAudit(fail=True), now=NOW)

        assert case.state is PermanentFixState.ISSUE_OPEN


@pytest.mark.unit
class TestNegativeAuthoritySurface:
    def test_provider_protocol_and_call_surface_have_no_mutation_authority(self) -> None:
        from sre_harness import permanent_fix

        source = inspect.getsource(permanent_fix.PermanentFixProvider)
        methods = {
            name
            for name, value in vars(permanent_fix.PermanentFixProvider).items()
            if callable(value) and not name.startswith("_")
        }

        assert methods == {"binding", "find_issue", "create_issue", "read_issue", "find_change"}
        for forbidden in ("merge", "close", "approve", "comment", "push", "pipeline"):
            assert f"def {forbidden}" not in source.lower()

    def test_audit_is_sanitized_and_has_stable_retry_key(self) -> None:
        case, provider, audit = _open_case()
        event = audit.events[0]
        rendered = repr(event)

        assert case.request_id in rendered
        assert case.incident_id in rendered
        assert case.task_id in rendered
        assert "The mitigation restored service" not in rendered
        assert "evidence://" not in rendered
        assert "alice" not in rendered
        assert len(event.retry_key) == 71

    def test_cases_and_verified_capabilities_are_not_caller_constructible(self) -> None:
        from sre_harness import permanent_fix

        with pytest.raises(TypeError, match="open"):
            PermanentFixCase()  # type: ignore[call-arg]
        publication = parse_permanent_fix_policy(_canonical(_policy_payload()))
        with pytest.raises(TypeError, match="gate"):
            permanent_fix.VerifiedPermanentFixPolicy(publication)  # type: ignore[call-arg]
        outcome = parse_factory_outcome(_canonical(_outcome_payload()))
        with pytest.raises(TypeError, match="gate"):
            permanent_fix.VerifiedFactoryOutcome(outcome)  # type: ignore[call-arg]


@pytest.mark.unit
class TestEvidenceBoundary:
    def test_docs_retain_local_only_incomplete_boundary(self) -> None:
        harness_root = Path(__file__).parents[1]
        repository = harness_root.parents[1]
        spec = (repository / "docs/specs/SPEC-B6-permanent-fix-chase.md").read_text(
            encoding="utf-8"
        )
        status = (repository / "PROJECT_STATUS.md").read_text(encoding="utf-8")
        readme = (harness_root / "README.md").read_text(encoding="utf-8")
        normalized_spec = " ".join(spec.split())
        normalized_status = " ".join(status.split())
        normalized_readme = " ".join(readme.split())

        assert "SPEC-B6.json" in normalized_spec
        assert "B6 remains incomplete" in normalized_spec
        assert "construction evidence only" in normalized_spec
        assert "SPEC-B6.json" in normalized_status
        assert "B6 remains incomplete" in normalized_status
        assert "SPEC-B6.json" in normalized_readme
        assert "No GitHub, GitLab, factory, CI, or incident system" in normalized_readme
