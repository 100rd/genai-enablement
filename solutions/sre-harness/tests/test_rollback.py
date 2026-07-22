"""SPEC-B3 probes for deterministic fixture-only canary rollback construction."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from sre_harness.rollback import (
    MAX_ROLLBACK_POLICY_BYTES,
    ROLLBACK_POLICY_SCHEMA,
    MetricObservation,
    RollbackCandidatePolicy,
    RollbackDisposition,
    RollbackPolicyError,
    evaluate_rollback,
    load_rollback_candidate,
    parse_rollback_candidate,
    render_rollback_bundle,
    serialize_rollback_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


def _revision(value: object) -> str:
    canonical = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _policy_document() -> dict[str, object]:
    return {
        "analysisTemplateName": "payments-api-error-rate",
        "canaryWeight": 10,
        "container": {
            "limitCpu": "1000m",
            "limitMemory": "512Mi",
            "livenessPath": "/healthz",
            "port": 8080,
            "readinessPath": "/readyz",
            "requestCpu": "250m",
            "requestMemory": "256Mi",
            "startupPath": "/startupz",
            "terminationGraceSeconds": 30,
        },
        "controllerFloor": "1.7.0",
        "datadogSecretName": "datadog-rollouts-readonly",
        "image": "registry.example.invalid/payments@sha256:" + "a" * 64,
        "metric": {
            "formula": "errors / requests",
            "initialDelaySeconds": 60,
            "maximumErrorRate": "0.01",
            "measurementCount": 5,
            "measurementIntervalSeconds": 30,
            "name": "error-rate",
            "providerWindowSeconds": 300,
            "queries": {
                "errors": "sum:trace.http.request.errors{service:{{args.service-name}},rollouts_pod_template_hash:{{args.canary-hash}}}.as_count()",
                "requests": "sum:trace.http.request.hits{service:{{args.service-name}},rollouts_pod_template_hash:{{args.canary-hash}}}.as_count()",
            },
        },
        "namespace": "payments-canary",
        "pauseSeconds": 120,
        "progressDeadlineSeconds": 900,
        "replicas": 10,
        "rolloutName": "payments-api",
        "serviceName": "payments-api",
    }


def _payload() -> dict[str, object]:
    policy = _policy_document()
    return {
        "schemaVersion": ROLLBACK_POLICY_SCHEMA,
        "evidenceScope": "fixture",
        "policyRevision": _revision(policy),
        "policy": policy,
    }


def _reseal(payload: dict[str, object]) -> None:
    policy = payload["policy"]
    assert isinstance(policy, dict)
    payload["policyRevision"] = _revision(policy)


def _parse(payload: dict[str, object]) -> RollbackCandidatePolicy:
    return parse_rollback_candidate(json.dumps(payload).encode())


def _resource(bundle: dict[str, Any], kind: str) -> dict[str, Any]:
    resources = [item for item in bundle["items"] if item["kind"] == kind]
    assert len(resources) == 1
    return resources[0]


@pytest.mark.unit
class TestClosedCandidatePolicy:
    def test_exact_fixture_policy_loads_as_immutable_values(self) -> None:
        candidate = _parse(_payload())

        assert candidate.namespace == "payments-canary"
        assert candidate.replicas == 10
        assert candidate.maximum_error_rate == "0.01"
        assert candidate.policy_revision == _revision(_policy_document())
        assert candidate.evidence_scope == "fixture"

    @pytest.mark.parametrize(
        "mutation",
        [
            lambda value: value.update({"unknown": True}),
            lambda value: value.pop("evidenceScope"),
            lambda value: value.update({"schemaVersion": "v2"}),
            lambda value: value.update({"evidenceScope": "production"}),
            lambda value: value.update({"policyRevision": "sha256:" + "0" * 64}),
            lambda value: value["policy"].update({"unknown": True}),
            lambda value: value["policy"].update({"controllerFloor": "1.6.0"}),
            lambda value: value["policy"].update({"namespace": "Payments"}),
            lambda value: value["policy"].update({"image": "payments:latest"}),
            lambda value: value["policy"].update({"replicas": True}),
            lambda value: value["policy"].update({"replicas": 9}),
            lambda value: value["policy"].update({"canaryWeight": 50}),
            lambda value: value["policy"].update({"pauseSeconds": 0}),
            lambda value: value["policy"]["metric"].update({"maximumErrorRate": "0.010"}),
            lambda value: value["policy"]["metric"].update({"formula": "errors/requests"}),
            lambda value: value["policy"]["metric"]["queries"].update(
                {"errors": "sum:errors{service:{{args.service-name}}}"}
            ),
            lambda value: value["policy"]["container"].update({"startupPath": "startupz"}),
            lambda value: value["policy"]["container"].update({"requestCpu": "2000m"}),
        ],
    )
    def test_unknown_missing_unbound_mutable_or_unsafe_candidate_fails(
        self,
        mutation: Callable[[dict[str, Any]], None],
    ) -> None:
        payload = copy.deepcopy(_payload())
        mutation(payload)
        if payload.get("policyRevision") != "sha256:" + "0" * 64:
            _reseal(payload)

        with pytest.raises(RollbackPolicyError):
            _parse(payload)

    @pytest.mark.parametrize(
        "raw",
        [
            b"[]",
            b'{"schemaVersion":1,"schemaVersion":2}',
            b'{"replicas":NaN}',
            b"\xff",
        ],
    )
    def test_non_object_duplicate_nonfinite_or_non_utf8_json_fails(self, raw: bytes) -> None:
        with pytest.raises(RollbackPolicyError):
            parse_rollback_candidate(raw)

    def test_oversize_policy_fails_before_json_acceptance(self) -> None:
        with pytest.raises(RollbackPolicyError, match="exceeds maximum"):
            parse_rollback_candidate(b" " * (MAX_ROLLBACK_POLICY_BYTES + 1))

    def test_regular_file_loads_but_symlink_is_rejected(
        self,
        tmp_path: Path,
    ) -> None:
        source = tmp_path / "policy.json"
        source.write_text(json.dumps(_payload()))
        link = tmp_path / "policy-link.json"
        link.symlink_to(source)

        assert load_rollback_candidate(source).rollout_name == "payments-api"
        with pytest.raises(RollbackPolicyError, match="symlink"):
            load_rollback_candidate(link)


@pytest.mark.unit
class TestDeterministicOracle:
    def test_partial_success_observes_and_exact_success_continues(self) -> None:
        candidate = _parse(_payload())
        successes = [MetricObservation.value(0.005) for _ in range(5)]

        assert evaluate_rollback(candidate, successes[:4]) is RollbackDisposition.OBSERVE
        assert evaluate_rollback(candidate, successes) is RollbackDisposition.CONTINUE

    def test_threshold_is_inclusive_for_success(self) -> None:
        candidate = _parse(_payload())
        observations = [MetricObservation.value(0.01)] + [
            MetricObservation.value(0.001) for _ in range(4)
        ]

        assert evaluate_rollback(candidate, observations) is RollbackDisposition.CONTINUE

    @pytest.mark.parametrize(
        "observation",
        [
            MetricObservation.value(0.0100001),
            MetricObservation.value(-0.001),
            MetricObservation.no_data(),
            MetricObservation.provider_error(),
            MetricObservation.value(float("nan")),
            MetricObservation.value(float("inf")),
            MetricObservation.value(float("-inf")),
        ],
    )
    def test_breach_missing_error_or_nonfinite_aborts(
        self,
        observation: MetricObservation,
    ) -> None:
        assert (
            evaluate_rollback(_parse(_payload()), [observation])
            is RollbackDisposition.ABORT_TO_STABLE
        )

    def test_extra_observations_fail_instead_of_reinterpreting_window(self) -> None:
        observations = [MetricObservation.value(0.001) for _ in range(6)]

        with pytest.raises(RollbackPolicyError, match="more observations"):
            evaluate_rollback(_parse(_payload()), observations)

    def test_mutated_or_raw_policy_cannot_return_a_disposition(self) -> None:
        candidate = _parse(_payload())
        object.__setattr__(candidate, "maximum_error_rate", "0.9")

        with pytest.raises(RollbackPolicyError, match="raw or mutated"):
            evaluate_rollback(candidate, [])
        with pytest.raises(RollbackPolicyError, match="raw or mutated"):
            evaluate_rollback(object(), [])  # type: ignore[arg-type]


@pytest.mark.unit
class TestKubernetesBundle:
    def test_analysis_is_finite_inline_complementary_and_fail_closed(self) -> None:
        bundle = render_rollback_bundle(_parse(_payload()))
        template = _resource(bundle, "AnalysisTemplate")
        metric = template["spec"]["metrics"][0]

        assert template["apiVersion"] == "argoproj.io/v1alpha1"
        assert template["spec"]["args"] == [
            {"name": "service-name"},
            {"name": "canary-hash"},
        ]
        assert metric["count"] == 5
        assert metric["interval"] == "30s"
        assert metric["initialDelay"] == "60s"
        assert metric["failureLimit"] == 0
        assert metric["inconclusiveLimit"] == 0
        assert metric["consecutiveErrorLimit"] == 0
        assert "default(result, 1)" in metric["successCondition"]
        assert "!isNaN" in metric["successCondition"]
        assert "!isInf" in metric["successCondition"]
        assert "<= 0.01" in metric["successCondition"]
        assert "default(result, 1)" in metric["failureCondition"]
        assert "isNaN" in metric["failureCondition"]
        assert "isInf" in metric["failureCondition"]
        assert "> 0.01" in metric["failureCondition"]
        assert "dryRun" not in template["spec"]

        rollout = _resource(bundle, "Rollout")
        steps = rollout["spec"]["strategy"]["canary"]["steps"]
        assert steps == [
            {"setWeight": 10},
            {"pause": {"duration": "120s"}},
            {
                "analysis": {
                    "args": [
                        {
                            "name": "service-name",
                            "value": "payments-api.payments-canary.svc.cluster.local",
                        },
                        {
                            "name": "canary-hash",
                            "valueFrom": {"podTemplateHashValue": "Latest"},
                        },
                    ],
                    "templates": [{"templateName": "payments-api-error-rate"}],
                }
            },
        ]

    def test_datadog_v2_is_explicit_namespaced_and_has_no_credentials(self) -> None:
        bundle = render_rollback_bundle(_parse(_payload()))
        template = _resource(bundle, "AnalysisTemplate")
        datadog = template["spec"]["metrics"][0]["provider"]["datadog"]

        assert datadog == {
            "aggregator": "sum",
            "apiVersion": "v2",
            "formula": "errors / requests",
            "interval": "300s",
            "queries": _policy_document()["metric"]["queries"],  # type: ignore[index]
            "secretRef": {"name": "datadog-rollouts-readonly", "namespaced": True},
        }
        assert all(item["kind"] != "Secret" for item in bundle["items"])
        lowered = serialize_rollback_bundle(_parse(_payload())).lower()
        assert b"api-key" not in lowered
        assert b"app-key" not in lowered
        assert b'"address"' not in lowered

    def test_rollout_and_service_encode_basic_canary_and_safe_workload(self) -> None:
        bundle = render_rollback_bundle(_parse(_payload()))
        service = _resource(bundle, "Service")
        rollout = _resource(bundle, "Rollout")
        spec = rollout["spec"]
        pod = spec["template"]["spec"]
        container = pod["containers"][0]

        assert service["spec"]["selector"] == spec["selector"]["matchLabels"]
        assert spec["replicas"] == 10
        assert spec["progressDeadlineSeconds"] == 900
        assert spec["progressDeadlineAbort"] is True
        assert spec["rollbackWindow"] == {"revisions": 3}
        assert "trafficRouting" not in spec["strategy"]["canary"]
        assert pod["automountServiceAccountToken"] is False
        assert pod["securityContext"] == {
            "runAsNonRoot": True,
            "seccompProfile": {"type": "RuntimeDefault"},
        }
        assert container["image"].endswith("@sha256:" + "a" * 64)
        assert container["securityContext"] == {
            "allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
            "readOnlyRootFilesystem": True,
            "runAsNonRoot": True,
        }
        assert container["resources"] == {
            "limits": {"cpu": "1000m", "memory": "512Mi"},
            "requests": {"cpu": "250m", "memory": "256Mi"},
        }
        assert container["startupProbe"]["httpGet"]["path"] == "/startupz"
        assert container["readinessProbe"]["httpGet"]["path"] == "/readyz"
        assert container["livenessProbe"]["httpGet"]["path"] == "/healthz"

    def test_bundle_is_revision_annotated_deterministic_and_fixture_only(self) -> None:
        candidate = _parse(_payload())
        first = render_rollback_bundle(candidate)
        second = render_rollback_bundle(candidate)

        assert first == second
        assert serialize_rollback_bundle(candidate) == serialize_rollback_bundle(candidate)
        for resource in first["items"]:
            annotations = resource["metadata"]["annotations"]
            assert annotations == {
                "sre-harness.genai-enablement/controller-floor": "1.7.0",
                "sre-harness.genai-enablement/evidence-scope": "fixture",
                "sre-harness.genai-enablement/human-approval-required": "true",
                "sre-harness.genai-enablement/policy-revision": candidate.policy_revision,
            }
            assert resource["metadata"]["namespace"] == "payments-canary"

        serialized = serialize_rollback_bundle(candidate).lower()
        assert b'"status"' not in serialized
        assert b'"llm"' not in serialized
        assert b'"plugin"' not in serialized
        assert b'"web"' not in serialized
        assert b'"job"' not in serialized

    def test_renderer_rejects_mutated_policy(self) -> None:
        candidate = _parse(_payload())
        object.__setattr__(candidate, "canary_weight", 40)

        with pytest.raises(RollbackPolicyError, match="raw or mutated"):
            render_rollback_bundle(candidate)

    def test_checked_in_bundle_is_exactly_generated_from_checked_in_policy(self) -> None:
        candidate = load_rollback_candidate(ROOT / "examples" / "rollback-candidate-policy.json")

        assert (
            serialize_rollback_bundle(candidate)
            == (ROOT / "integrations" / "argo-rollouts-deterministic-canary.json").read_bytes()
        )


@pytest.mark.unit
class TestEvidenceBoundary:
    def test_docs_retain_fixture_only_incomplete_boundary(self) -> None:
        repository = ROOT.parents[1]
        spec = (repository / "docs/specs/SPEC-B3-deterministic-canary-rollback.md").read_text(
            encoding="utf-8"
        )
        status = (repository / "PROJECT_STATUS.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        assert "B3 remains incomplete" in spec
        assert "No local artifact may" in spec
        assert "portable fixture conformance only" in status
        assert "B3 remains incomplete" in status
        assert "Local rendering and tests cannot satisfy those gates" in readme
