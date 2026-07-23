"""SPEC-B2 probes for the strict advisory CI / PreSync integration contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from sre_harness.advisory_integration import (
    ADVISORY_REQUEST_SCHEMA,
    ADVISORY_RESULT_SCHEMA,
    MAX_ADVISORY_ENVELOPE_BYTES,
    AdvisoryIntegrationError,
    AdvisorySource,
    ChangeAdvisoryInvocation,
    ChangeAdvisoryResult,
    canonical_digest,
    evaluate_change_advisory,
    load_change_advisory_invocation,
    parse_change_advisory_invocation,
    write_change_advisory_result,
)
from sre_harness.change_gate import Verdict
from sre_harness.cli import (
    EXIT_INTEGRATION_BLOCK,
    EXIT_INTEGRATION_INVALID,
    EXIT_INTEGRATION_PROCEED,
    EXIT_INTEGRATION_REQUIRE_HUMAN,
    main,
)

ROOT = Path(__file__).resolve().parents[1]


def _change(required: tuple[str, ...] = ("silver",)) -> dict[str, object]:
    return {
        "actions": [],
        "requiredNamespaces": ["payments"],
        "requiredStorageClasses": list(required),
        "service": "payments",
        "targetClusterIds": ["prod-eu-1", "prod-us-1"],
    }


def _platform() -> dict[str, object]:
    return {
        "asOf": "2026-07-16T09:38:00Z",
        "entities": [
            {"cluster": "prod-eu-1", "kind": "Namespace", "name": "payments"},
            {"cluster": "prod-us-1", "kind": "Namespace", "name": "payments"},
            {"cluster": "prod-eu-1", "kind": "StorageClass", "name": "gold"},
            {"cluster": "prod-eu-1", "kind": "StorageClass", "name": "silver"},
            {"cluster": "prod-us-1", "kind": "StorageClass", "name": "silver"},
        ],
    }


def _payload(required: tuple[str, ...] = ("silver",)) -> dict[str, object]:
    change = _change(required)
    platform = _platform()
    return {
        "schemaVersion": ADVISORY_REQUEST_SCHEMA,
        "invocationId": "gitlab-payments-4242",
        "source": "gitlab_ci",
        "requestedAt": "2026-07-16T09:40:00Z",
        "changeRevision": canonical_digest(change),
        "platformRevision": canonical_digest(platform),
        "change": change,
        "platformSnapshot": platform,
    }


def _parse(payload: dict[str, object]):
    return parse_change_advisory_invocation(json.dumps(payload).encode())


@pytest.mark.unit
class TestClosedEnvelope:
    def test_exact_v1_envelope_loads_as_immutable_values(self) -> None:
        invocation = _parse(_payload())

        assert invocation.invocation_id == "gitlab-payments-4242"
        assert invocation.source is AdvisorySource.GITLAB_CI
        assert invocation.platform_as_of.isoformat() == "2026-07-16T09:38:00+00:00"
        assert invocation.target_cluster_ids == ("prod-eu-1", "prod-us-1")
        assert invocation.required_storageclasses == ("silver",)
        assert invocation.invocation_digest.startswith("sha256:")

    def test_both_declared_integration_sources_are_accepted(self) -> None:
        payload = _payload()
        payload["source"] = "argocd_presync"

        assert _parse(payload).source is AdvisorySource.ARGOCD_PRESYNC

    @pytest.mark.parametrize(
        "as_of",
        ["2026-07-16T09:40:01Z", "2026-07-16T09:34:59Z"],
    )
    def test_future_or_more_than_five_minute_old_platform_snapshot_fails(
        self,
        as_of: str,
    ) -> None:
        payload = _payload()
        platform = payload["platformSnapshot"]
        assert isinstance(platform, dict)
        platform["asOf"] = as_of
        payload["platformRevision"] = canonical_digest(platform)

        with pytest.raises(AdvisoryIntegrationError, match="platform snapshot"):
            _parse(payload)

    @pytest.mark.parametrize(
        "mutation",
        [
            lambda value: value.update({"unknown": True}),
            lambda value: value.pop("invocationId"),
            lambda value: value.update({"schemaVersion": "v2"}),
            lambda value: value.update({"source": "local"}),
            lambda value: value.update({"requestedAt": "2026-07-16T11:40:00+02:00"}),
            lambda value: value.update({"changeRevision": "sha256:" + "0" * 64}),
            lambda value: value.update({"platformRevision": "sha256:" + "0" * 64}),
            lambda value: value["change"].update({"unknown": True}),
            lambda value: value["platformSnapshot"].update({"unknown": True}),
            lambda value: value["platformSnapshot"]["entities"][0].update({"unknown": True}),
            lambda value: value["change"].update({"targetClusterIds": ["prod-eu-1", "prod-eu-1"]}),
            lambda value: value["platformSnapshot"]["entities"].reverse(),
        ],
    )
    def test_unknown_missing_foreign_stale_or_noncanonical_input_fails_closed(
        self,
        mutation,
    ) -> None:
        payload = copy.deepcopy(_payload())
        mutation(payload)

        with pytest.raises(AdvisoryIntegrationError):
            _parse(payload)

    @pytest.mark.parametrize(
        "raw",
        [
            b'{"schemaVersion":"x","schemaVersion":"y"}',
            b'{"value":NaN}',
            b"\xff",
            b"[]",
        ],
    )
    def test_duplicate_nonfinite_invalid_utf8_or_nonobject_json_fails(self, raw: bytes) -> None:
        with pytest.raises(AdvisoryIntegrationError):
            parse_change_advisory_invocation(raw)

    def test_bounded_file_loader_rejects_oversize_and_symlink(self, tmp_path: Path) -> None:
        oversized = tmp_path / "oversized.json"
        oversized.write_bytes(b" " * (MAX_ADVISORY_ENVELOPE_BYTES + 1))
        valid = tmp_path / "valid.json"
        valid.write_text(json.dumps(_payload()), encoding="utf-8")
        link = tmp_path / "link.json"
        link.symlink_to(valid)

        with pytest.raises(AdvisoryIntegrationError, match="maximum"):
            load_change_advisory_invocation(oversized)
        with pytest.raises(AdvisoryIntegrationError, match="symlink"):
            load_change_advisory_invocation(link)

    def test_committed_example_is_valid_but_explicitly_a_fixture(self) -> None:
        invocation = load_change_advisory_invocation(
            ROOT / "examples/change-advisory-invocation.json"
        )

        assert invocation.source is AdvisorySource.GITLAB_CI
        assert invocation.invocation_id == "fixture-gitlab-payments-1"

    def test_invocation_cannot_be_constructed_by_a_caller(self) -> None:
        parsed = _parse(_payload())

        with pytest.raises(TypeError, match="strict parser"):
            ChangeAdvisoryInvocation(
                invocation_id=parsed.invocation_id,
                source=parsed.source,
                requested_at=parsed.requested_at,
                platform_as_of=parsed.platform_as_of,
                change_revision=parsed.change_revision,
                platform_revision=parsed.platform_revision,
                service=parsed.service,
                target_cluster_ids=parsed.target_cluster_ids,
                required_storageclasses=parsed.required_storageclasses,
                actions=parsed.actions,
                required_namespaces=parsed.required_namespaces,
                platform_entities=parsed.platform_entities,
                invocation_digest=parsed.invocation_digest,
            )

    def test_direct_nonbytes_oversize_directory_and_invalid_shapes_fail(
        self,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(AdvisoryIntegrationError, match="exact bytes"):
            parse_change_advisory_invocation("{}")  # type: ignore[arg-type]
        with pytest.raises(AdvisoryIntegrationError, match="maximum"):
            parse_change_advisory_invocation(b" " * (MAX_ADVISORY_ENVELOPE_BYTES + 1))
        with pytest.raises(AdvisoryIntegrationError, match="regular file"):
            load_change_advisory_invocation(tmp_path)

        for path, value in (
            (("invocationId",), "not allowed"),
            (("changeRevision",), "main"),
            (("change",), []),
            (("change", "service"), ""),
            (("change", "targetClusterIds"), []),
            (("change", "actions"), "read"),
            (("platformSnapshot", "entities"), {}),
            (("platformSnapshot", "entities", 0, "cluster"), 1),
            (("platformSnapshot", "entities", 0, "cluster"), ""),
        ):
            payload = copy.deepcopy(_payload())
            current: Any = payload
            for component in path[:-1]:
                current = current[component]
            current[path[-1]] = value
            with pytest.raises(AdvisoryIntegrationError):
                _parse(payload)

        with pytest.raises(AdvisoryIntegrationError, match="canonical JSON"):
            canonical_digest({"bad": object()})


@pytest.mark.unit
class TestDeterministicAdvisoryResult:
    @pytest.mark.parametrize(
        ("required", "verdict"),
        [
            (("silver",), "proceed"),
            (("platinum",), "block"),
            (("gold",), "require_human"),
        ],
    )
    def test_registered_gate_is_the_only_verdict_authority(
        self,
        required: tuple[str, ...],
        verdict: str,
    ) -> None:
        invocation = _parse(_payload(required))

        result = evaluate_change_advisory(invocation)
        document = result.to_document()

        assert document["schemaVersion"] == ADVISORY_RESULT_SCHEMA
        assert document["invocationId"] == invocation.invocation_id
        assert document["invocationDigest"] == invocation.invocation_digest
        assert document["changeRevision"] == invocation.change_revision
        assert document["platformRevision"] == invocation.platform_revision
        assert document["platformAsOf"] == "2026-07-16T09:38:00Z"
        assert document["verdict"] == verdict
        assert {row["checkId"] for row in document["checkResults"]} == {
            "storageclass_present",
            "blast_radius",
            "namespace_present",
        }

    def test_result_is_exactly_advisory_and_has_no_action_surface(self) -> None:
        invocation = _parse(_payload())
        result = evaluate_change_advisory(invocation)
        document = result.to_document()

        assert document["analysisTier"] == "T1"
        assert document["recommendationTier"] == "T2"
        assert document["advisory"] is True
        assert document["mutationAuthorized"] is False
        forbidden = {"deploy", "sync", "execute", "approve", "credentials", "remediation"}
        assert forbidden.isdisjoint(document)
        for value in (invocation, result):
            assert all(not hasattr(value, action) for action in forbidden)

    def test_result_rejoins_exact_provenance_checks_and_boundary(self) -> None:
        invocation = _parse(_payload())

        document = evaluate_change_advisory(invocation).to_document()

        assert set(document) == {
            "schemaVersion",
            "invocationId",
            "source",
            "requestedAt",
            "platformAsOf",
            "invocationDigest",
            "changeRevision",
            "platformRevision",
            "subject",
            "verdict",
            "rationale",
            "analysisTier",
            "recommendationTier",
            "advisory",
            "mutationAuthorized",
            "checkResults",
        }
        assert document["invocationId"] == invocation.invocation_id
        assert document["source"] == invocation.source.value
        assert document["requestedAt"] == "2026-07-16T09:40:00Z"
        assert document["platformAsOf"] == "2026-07-16T09:38:00Z"
        assert document["invocationDigest"] == invocation.invocation_digest
        assert document["changeRevision"] == invocation.change_revision
        assert document["platformRevision"] == invocation.platform_revision
        assert document["subject"] == {
            "service": "payments",
            "targetClusterIds": ["prod-eu-1", "prod-us-1"],
        }
        assert document["verdict"] == "proceed"
        assert isinstance(document["rationale"], str) and document["rationale"]
        assert document["analysisTier"] == "T1"
        assert document["recommendationTier"] == "T2"
        assert document["advisory"] is True
        assert document["mutationAuthorized"] is False
        checks = document["checkResults"]
        assert isinstance(checks, list) and len(checks) == 3
        assert all(
            set(check) == {"checkId", "verdict", "rationale", "evidence"} for check in checks
        )
        assert all(isinstance(check["evidence"], dict) for check in checks)

    def test_result_writer_rejects_a_symlink_sink(self, tmp_path: Path) -> None:
        result = evaluate_change_advisory(_parse(_payload()))
        target = tmp_path / "target.json"
        target.write_text("unchanged", encoding="utf-8")
        link = tmp_path / "result.json"
        link.symlink_to(target)

        with pytest.raises(AdvisoryIntegrationError, match="symlink"):
            write_change_advisory_result(result, link)
        assert target.read_text(encoding="utf-8") == "unchanged"

    def test_raw_or_mutated_invocation_and_fabricated_result_fail_closed(self) -> None:
        invocation = _parse(_payload())
        object.__setattr__(invocation, "service", "tampered")

        with pytest.raises(AdvisoryIntegrationError, match="raw or mutated"):
            evaluate_change_advisory(invocation)
        with pytest.raises(TypeError, match="deterministic evaluation"):
            ChangeAdvisoryResult(verdict=Verdict.PROCEED, document={})

    def test_post_issuance_result_mutation_is_detected_before_read_or_write(
        self,
        tmp_path: Path,
    ) -> None:
        result = evaluate_change_advisory(_parse(_payload()))
        object.__setattr__(result, "_document_json", b'{"verdict":"proceed"}')

        with pytest.raises(AdvisoryIntegrationError, match="result is mutated"):
            result.to_document()
        with pytest.raises(AdvisoryIntegrationError, match="result is mutated"):
            write_change_advisory_result(result, tmp_path / "result.json")

    def test_result_writer_rejects_raw_directory_or_missing_parent_sinks(
        self,
        tmp_path: Path,
    ) -> None:
        result = evaluate_change_advisory(_parse(_payload()))

        with pytest.raises(AdvisoryIntegrationError, match="deterministic"):
            write_change_advisory_result(object(), tmp_path / "raw.json")  # type: ignore[arg-type]
        with pytest.raises(AdvisoryIntegrationError, match="regular file"):
            write_change_advisory_result(result, tmp_path)
        with pytest.raises(AdvisoryIntegrationError, match="real directory"):
            write_change_advisory_result(result, tmp_path / "missing" / "result.json")


@pytest.mark.unit
class TestIntegrationCli:
    @pytest.mark.parametrize(
        ("required", "exit_code"),
        [
            (("silver",), EXIT_INTEGRATION_PROCEED),
            (("platinum",), EXIT_INTEGRATION_BLOCK),
            (("gold",), EXIT_INTEGRATION_REQUIRE_HUMAN),
        ],
    )
    def test_valid_dispositions_are_distinct_and_always_write_the_result(
        self,
        required: tuple[str, ...],
        exit_code: int,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        request = tmp_path / "request.json"
        request.write_text(json.dumps(_payload(required)), encoding="utf-8")
        result = tmp_path / "result.json"

        actual = main(["gate-integration", "--input", str(request), "--result", str(result)])

        stdout_document = json.loads(capsys.readouterr().out)
        assert actual == exit_code
        assert json.loads(result.read_text(encoding="utf-8")) == stdout_document

    def test_invalid_input_is_machine_distinct_and_does_not_fabricate_result(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        result = tmp_path / "result.json"

        code = main(
            ["gate-integration", "--input", str(tmp_path / "missing.json"), "--result", str(result)]
        )

        assert code == EXIT_INTEGRATION_INVALID == 64
        assert not result.exists()
        assert "error" in capsys.readouterr().err.lower()

    def test_unwritable_result_sink_is_the_same_fail_closed_integration_error(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        request = tmp_path / "request.json"
        request.write_text(json.dumps(_payload()), encoding="utf-8")

        code = main(
            [
                "gate-integration",
                "--input",
                str(request),
                "--result",
                str(tmp_path / "missing" / "result.json"),
            ]
        )

        assert code == EXIT_INTEGRATION_INVALID
        assert "result parent" in capsys.readouterr().err.lower()


@pytest.mark.unit
class TestIntegrationTemplates:
    def test_docs_retain_fixture_only_incomplete_boundary(self) -> None:
        repository = ROOT.parents[1]
        spec = (
            repository / "docs/specs/SPEC-B2-advisory-change-validation-integration.md"
        ).read_text(encoding="utf-8")
        status = (repository / "PROJECT_STATUS.md").read_text(encoding="utf-8")

        assert "Fixtures and templates are not live integration evidence" in spec
        assert "B2 remains incomplete" in spec
        assert "portable fixture conformance only" in status
        assert "B2 remains incomplete" in status

    def test_gitlab_preserves_gate_status_and_retains_artifact(self) -> None:
        template = (ROOT / "integrations/gitlab-ci.gate.yml").read_text(encoding="utf-8")

        assert "gate-integration" in template
        assert "--result gate-verdict.json" in template
        assert "allow_failure: true" in template
        assert "| tee" not in template

    def test_argocd_masks_only_the_explicit_presync_advisory_boundary(self) -> None:
        template = (ROOT / "integrations/argocd-presync-gate.yaml").read_text(encoding="utf-8")

        assert "argocd.argoproj.io/hook: PreSync" in template
        assert "gate-integration" in template
        assert "|| true" in template
