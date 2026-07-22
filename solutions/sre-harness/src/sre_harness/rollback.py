"""Closed SPEC-B3 policy, oracle, and Kubernetes JSON renderer.

The module constructs fixture-scoped candidates only.  It never contacts a
cluster, Datadog, an LLM, or another execution surface.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import secrets
import stat
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

ROLLBACK_POLICY_SCHEMA = "sre-harness.rollback-candidate/v1"
MAX_ROLLBACK_POLICY_BYTES = 1024 * 1024
ARGO_ROLLOUTS_CONTROLLER_FLOOR = "1.7.0"

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?$")
_IMAGE_DIGEST = re.compile(r"^[a-z0-9](?:[a-z0-9._:/-]{0,253})@sha256:[0-9a-f]{64}$")
_ERROR_RATE = re.compile(r"^0\.\d*[1-9]$")
_HTTP_PATH = re.compile(r"^/[A-Za-z0-9._~/-]{0,127}$")
_CPU_QUANTITY = re.compile(r"^(?:[1-9][0-9]*m|[1-9][0-9]*)$")
_MEMORY_QUANTITY = re.compile(r"^(?:[1-9][0-9]*)(?:Ki|Mi|Gi)$")
_QUERY_ARGUMENTS = ("{{args.service-name}}", "{{args.canary-hash}}")
_SUSPICIOUS_QUERY_TERMS = ("api-key", "api_key", "app-key", "app_key", "password=")
_CONSTRUCTION_TOKEN = object()
_INTEGRITY_KEY = secrets.token_bytes(32)

_TOP_LEVEL_FIELDS = frozenset({"schemaVersion", "evidenceScope", "policyRevision", "policy"})
_POLICY_FIELDS = frozenset(
    {
        "analysisTemplateName",
        "canaryWeight",
        "container",
        "controllerFloor",
        "datadogSecretName",
        "image",
        "metric",
        "namespace",
        "pauseSeconds",
        "progressDeadlineSeconds",
        "replicas",
        "rolloutName",
        "serviceName",
    }
)
_METRIC_FIELDS = frozenset(
    {
        "formula",
        "initialDelaySeconds",
        "maximumErrorRate",
        "measurementCount",
        "measurementIntervalSeconds",
        "name",
        "providerWindowSeconds",
        "queries",
    }
)
_QUERY_FIELDS = frozenset({"errors", "requests"})
_CONTAINER_FIELDS = frozenset(
    {
        "limitCpu",
        "limitMemory",
        "livenessPath",
        "port",
        "readinessPath",
        "requestCpu",
        "requestMemory",
        "startupPath",
        "terminationGraceSeconds",
    }
)


class RollbackPolicyError(ValueError):
    """A candidate policy, observation sequence, or renderer input is invalid."""


class RollbackDisposition(Enum):
    """Offline mirror states; none grants deployment or cluster authority."""

    OBSERVE = "observe"
    CONTINUE = "continue"
    ABORT_TO_STABLE = "abort_to_stable"


class MetricObservationState(Enum):
    """Exact offline observation states mirrored by the fail-closed template."""

    VALUE = "value"
    NO_DATA = "no_data"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True)
class MetricObservation:
    """One offline metric observation used only by the deterministic oracle."""

    state: MetricObservationState
    metric_value: float | int | None

    @classmethod
    def value(cls, value: float | int) -> MetricObservation:
        return cls(state=MetricObservationState.VALUE, metric_value=value)

    @classmethod
    def no_data(cls) -> MetricObservation:
        return cls(state=MetricObservationState.NO_DATA, metric_value=None)

    @classmethod
    def provider_error(cls) -> MetricObservation:
        return cls(state=MetricObservationState.PROVIDER_ERROR, metric_value=None)


@dataclass(frozen=True, init=False)
class RollbackCandidatePolicy:
    """Opaque immutable candidate issued only by the strict v1 parser."""

    policy_revision: str
    evidence_scope: str
    controller_floor: str
    namespace: str
    rollout_name: str
    service_name: str
    analysis_template_name: str
    datadog_secret_name: str
    image: str
    replicas: int
    canary_weight: int
    pause_seconds: int
    progress_deadline_seconds: int
    metric_name: str
    measurement_interval_seconds: int
    provider_window_seconds: int
    initial_delay_seconds: int
    measurement_count: int
    maximum_error_rate: str
    errors_query: str
    requests_query: str
    formula: str
    container_port: int
    startup_path: str
    readiness_path: str
    liveness_path: str
    request_cpu: str
    request_memory: str
    limit_cpu: str
    limit_memory: str
    termination_grace_seconds: int
    _integrity_seal: str = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        policy_revision: str,
        evidence_scope: str,
        controller_floor: str,
        namespace: str,
        rollout_name: str,
        service_name: str,
        analysis_template_name: str,
        datadog_secret_name: str,
        image: str,
        replicas: int,
        canary_weight: int,
        pause_seconds: int,
        progress_deadline_seconds: int,
        metric_name: str,
        measurement_interval_seconds: int,
        provider_window_seconds: int,
        initial_delay_seconds: int,
        measurement_count: int,
        maximum_error_rate: str,
        errors_query: str,
        requests_query: str,
        formula: str,
        container_port: int,
        startup_path: str,
        readiness_path: str,
        liveness_path: str,
        request_cpu: str,
        request_memory: str,
        limit_cpu: str,
        limit_memory: str,
        termination_grace_seconds: int,
        _construction_token: object | None = None,
    ) -> None:
        if _construction_token is not _CONSTRUCTION_TOKEN:
            raise TypeError("rollback candidates must come from the strict parser")
        values = locals().copy()
        values.pop("self")
        values.pop("_construction_token")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_integrity_seal", _policy_seal(self))

    def _is_intact(self) -> bool:
        return type(self) is RollbackCandidatePolicy and hmac.compare_digest(
            self._integrity_seal,
            _policy_seal(self),
        )


def parse_rollback_candidate(raw: bytes) -> RollbackCandidatePolicy:
    """Parse one exact fixture-only v1 policy from bounded strict JSON bytes."""
    if type(raw) is not bytes:
        raise RollbackPolicyError("rollback candidate must be exact bytes")
    if len(raw) > MAX_ROLLBACK_POLICY_BYTES:
        raise RollbackPolicyError(
            f"rollback candidate exceeds maximum {MAX_ROLLBACK_POLICY_BYTES} bytes"
        )
    try:
        text = raw.decode("utf-8", errors="strict")
        payload = json.loads(
            text,
            object_pairs_hook=_closed_object,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RollbackPolicyError("rollback candidate is not strict UTF-8 JSON") from exc
    if type(payload) is not dict:
        raise RollbackPolicyError("rollback candidate must be a JSON object")
    _exact_fields(payload, _TOP_LEVEL_FIELDS, "rollback candidate")
    if payload["schemaVersion"] != ROLLBACK_POLICY_SCHEMA:
        raise RollbackPolicyError("unsupported rollback candidate schemaVersion")
    if payload["evidenceScope"] != "fixture":
        raise RollbackPolicyError("rollback candidate evidenceScope must be fixture")

    policy_revision = _exact_sha256(payload["policyRevision"], "policyRevision")
    policy = _exact_object(payload["policy"], "policy")
    _exact_fields(policy, _POLICY_FIELDS, "policy")
    if policy_revision != _canonical_digest(policy):
        raise RollbackPolicyError("policyRevision does not match the exact policy content")

    controller_floor = _exact_text(policy["controllerFloor"], "policy.controllerFloor")
    if controller_floor != ARGO_ROLLOUTS_CONTROLLER_FLOOR:
        raise RollbackPolicyError(
            f"policy.controllerFloor must be {ARGO_ROLLOUTS_CONTROLLER_FLOOR} for v1"
        )
    namespace = _dns_label(policy["namespace"], "policy.namespace")
    rollout_name = _dns_label(policy["rolloutName"], "policy.rolloutName")
    service_name = _dns_label(policy["serviceName"], "policy.serviceName")
    analysis_template_name = _dns_label(
        policy["analysisTemplateName"],
        "policy.analysisTemplateName",
    )
    datadog_secret_name = _dns_label(
        policy["datadogSecretName"],
        "policy.datadogSecretName",
    )
    image = _exact_text(policy["image"], "policy.image", maximum=320)
    if not _IMAGE_DIGEST.fullmatch(image):
        raise RollbackPolicyError("policy.image must be a lowercase sha256-pinned image reference")

    replicas = _exact_int(policy["replicas"], "policy.replicas", minimum=2, maximum=1000)
    canary_weight = _exact_int(
        policy["canaryWeight"],
        "policy.canaryWeight",
        minimum=1,
        maximum=49,
    )
    if replicas * canary_weight % 100 != 0:
        raise RollbackPolicyError(
            "policy replicas and canaryWeight must yield an integral basic-canary pod ratio"
        )
    pause_seconds = _exact_int(
        policy["pauseSeconds"],
        "policy.pauseSeconds",
        minimum=1,
        maximum=86400,
    )
    progress_deadline_seconds = _exact_int(
        policy["progressDeadlineSeconds"],
        "policy.progressDeadlineSeconds",
        minimum=1,
        maximum=604800,
    )

    metric = _exact_object(policy["metric"], "policy.metric")
    _exact_fields(metric, _METRIC_FIELDS, "policy.metric")
    metric_name = _dns_label(metric["name"], "policy.metric.name")
    measurement_interval_seconds = _exact_int(
        metric["measurementIntervalSeconds"],
        "policy.metric.measurementIntervalSeconds",
        minimum=1,
        maximum=3600,
    )
    provider_window_seconds = _exact_int(
        metric["providerWindowSeconds"],
        "policy.metric.providerWindowSeconds",
        minimum=1,
        maximum=86400,
    )
    if provider_window_seconds < measurement_interval_seconds:
        raise RollbackPolicyError(
            "policy.metric.providerWindowSeconds must cover the measurement interval"
        )
    initial_delay_seconds = _exact_int(
        metric["initialDelaySeconds"],
        "policy.metric.initialDelaySeconds",
        minimum=0,
        maximum=3600,
    )
    measurement_count = _exact_int(
        metric["measurementCount"],
        "policy.metric.measurementCount",
        minimum=1,
        maximum=100,
    )
    maximum_error_rate = _exact_text(
        metric["maximumErrorRate"],
        "policy.metric.maximumErrorRate",
        maximum=32,
    )
    if not _ERROR_RATE.fullmatch(maximum_error_rate):
        raise RollbackPolicyError(
            "policy.metric.maximumErrorRate must be a canonical decimal in (0, 1)"
        )
    threshold = Decimal(maximum_error_rate)
    if threshold <= 0 or threshold >= 1:
        raise RollbackPolicyError(
            "policy.metric.maximumErrorRate must be a canonical decimal in (0, 1)"
        )
    formula = _exact_text(metric["formula"], "policy.metric.formula", maximum=64)
    if formula != "errors / requests":
        raise RollbackPolicyError("policy.metric.formula must be exactly errors / requests")
    queries = _exact_object(metric["queries"], "policy.metric.queries")
    _exact_fields(queries, _QUERY_FIELDS, "policy.metric.queries")
    errors_query = _metric_query(queries["errors"], "policy.metric.queries.errors")
    requests_query = _metric_query(queries["requests"], "policy.metric.queries.requests")

    container = _exact_object(policy["container"], "policy.container")
    _exact_fields(container, _CONTAINER_FIELDS, "policy.container")
    container_port = _exact_int(
        container["port"],
        "policy.container.port",
        minimum=1,
        maximum=65535,
    )
    startup_path = _http_path(container["startupPath"], "policy.container.startupPath")
    readiness_path = _http_path(
        container["readinessPath"],
        "policy.container.readinessPath",
    )
    liveness_path = _http_path(
        container["livenessPath"],
        "policy.container.livenessPath",
    )
    request_cpu = _cpu_quantity(container["requestCpu"], "policy.container.requestCpu")
    limit_cpu = _cpu_quantity(container["limitCpu"], "policy.container.limitCpu")
    if _cpu_millicores(request_cpu) > _cpu_millicores(limit_cpu):
        raise RollbackPolicyError("policy.container requestCpu must not exceed limitCpu")
    request_memory = _memory_quantity(
        container["requestMemory"],
        "policy.container.requestMemory",
    )
    limit_memory = _memory_quantity(
        container["limitMemory"],
        "policy.container.limitMemory",
    )
    if _memory_kibibytes(request_memory) > _memory_kibibytes(limit_memory):
        raise RollbackPolicyError("policy.container requestMemory must not exceed limitMemory")
    termination_grace_seconds = _exact_int(
        container["terminationGraceSeconds"],
        "policy.container.terminationGraceSeconds",
        minimum=1,
        maximum=300,
    )

    minimum_deadline = (
        pause_seconds + initial_delay_seconds + measurement_count * measurement_interval_seconds
    )
    if progress_deadline_seconds <= minimum_deadline:
        raise RollbackPolicyError(
            "policy.progressDeadlineSeconds must exceed pause plus the analysis window"
        )

    return RollbackCandidatePolicy(
        policy_revision=policy_revision,
        evidence_scope="fixture",
        controller_floor=controller_floor,
        namespace=namespace,
        rollout_name=rollout_name,
        service_name=service_name,
        analysis_template_name=analysis_template_name,
        datadog_secret_name=datadog_secret_name,
        image=image,
        replicas=replicas,
        canary_weight=canary_weight,
        pause_seconds=pause_seconds,
        progress_deadline_seconds=progress_deadline_seconds,
        metric_name=metric_name,
        measurement_interval_seconds=measurement_interval_seconds,
        provider_window_seconds=provider_window_seconds,
        initial_delay_seconds=initial_delay_seconds,
        measurement_count=measurement_count,
        maximum_error_rate=maximum_error_rate,
        errors_query=errors_query,
        requests_query=requests_query,
        formula=formula,
        container_port=container_port,
        startup_path=startup_path,
        readiness_path=readiness_path,
        liveness_path=liveness_path,
        request_cpu=request_cpu,
        request_memory=request_memory,
        limit_cpu=limit_cpu,
        limit_memory=limit_memory,
        termination_grace_seconds=termination_grace_seconds,
        _construction_token=_CONSTRUCTION_TOKEN,
    )


def load_rollback_candidate(path: Path) -> RollbackCandidatePolicy:
    """Read one regular non-symlink bounded policy file and parse it strictly."""
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RollbackPolicyError(f"rollback candidate file unavailable: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise RollbackPolicyError("rollback candidate file must not be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise RollbackPolicyError("rollback candidate file must be a regular file")
    if metadata.st_size > MAX_ROLLBACK_POLICY_BYTES:
        raise RollbackPolicyError(
            f"rollback candidate exceeds maximum {MAX_ROLLBACK_POLICY_BYTES} bytes"
        )

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise RollbackPolicyError("rollback candidate must remain a regular file")
            raw = handle.read(MAX_ROLLBACK_POLICY_BYTES + 1)
    except RollbackPolicyError:
        raise
    except OSError as exc:
        raise RollbackPolicyError(f"rollback candidate file unavailable: {path}") from exc
    return parse_rollback_candidate(raw)


def evaluate_rollback(
    policy: RollbackCandidatePolicy,
    observations: Sequence[MetricObservation],
) -> RollbackDisposition:
    """Mirror the finite v1 metric decision without performing a rollback."""
    _require_intact(policy)
    if len(observations) > policy.measurement_count:
        raise RollbackPolicyError("received more observations than the candidate measurementCount")

    threshold = Decimal(policy.maximum_error_rate)
    for observation in observations:
        if type(observation) is not MetricObservation:
            raise RollbackPolicyError("metric observation must be an exact MetricObservation")
        if observation.state is MetricObservationState.VALUE:
            value = observation.metric_value
            if type(value) not in (int, float):
                raise RollbackPolicyError("value observation must contain an exact number")
            assert isinstance(value, int | float)
            if not math.isfinite(value):
                return RollbackDisposition.ABORT_TO_STABLE
            decimal_value = Decimal(str(value))
            if decimal_value < 0 or decimal_value > threshold:
                return RollbackDisposition.ABORT_TO_STABLE
        elif observation.state in (
            MetricObservationState.NO_DATA,
            MetricObservationState.PROVIDER_ERROR,
        ):
            if observation.metric_value is not None:
                raise RollbackPolicyError("non-value observation must not contain a metric value")
            return RollbackDisposition.ABORT_TO_STABLE
        else:
            raise RollbackPolicyError("metric observation has an unknown state")

    if len(observations) < policy.measurement_count:
        return RollbackDisposition.OBSERVE
    return RollbackDisposition.CONTINUE


def render_rollback_bundle(policy: RollbackCandidatePolicy) -> dict[str, Any]:
    """Render a deterministic fixture-only Kubernetes JSON List."""
    _require_intact(policy)
    annotations = _annotations(policy)
    selector = {"app.kubernetes.io/name": policy.rollout_name}
    pod_labels = {
        **selector,
        "app.kubernetes.io/managed-by": "sre-harness",
    }
    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "annotations": annotations.copy(),
            "name": policy.service_name,
            "namespace": policy.namespace,
        },
        "spec": {
            "ports": [
                {
                    "name": "http",
                    "port": 80,
                    "protocol": "TCP",
                    "targetPort": "http",
                }
            ],
            "selector": selector.copy(),
            "type": "ClusterIP",
        },
    }
    safe_result = "default(result, 1)"
    success_condition = (
        f"!isNaN({safe_result}) && !isInf({safe_result}) && "
        f"{safe_result} >= 0 && {safe_result} <= {policy.maximum_error_rate}"
    )
    failure_condition = (
        f"isNaN({safe_result}) || isInf({safe_result}) || "
        f"{safe_result} < 0 || {safe_result} > {policy.maximum_error_rate}"
    )
    analysis_template = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "AnalysisTemplate",
        "metadata": {
            "annotations": annotations.copy(),
            "name": policy.analysis_template_name,
            "namespace": policy.namespace,
        },
        "spec": {
            "args": [{"name": "service-name"}, {"name": "canary-hash"}],
            "metrics": [
                {
                    "consecutiveErrorLimit": 0,
                    "count": policy.measurement_count,
                    "failureCondition": failure_condition,
                    "failureLimit": 0,
                    "inconclusiveLimit": 0,
                    "initialDelay": f"{policy.initial_delay_seconds}s",
                    "interval": f"{policy.measurement_interval_seconds}s",
                    "name": policy.metric_name,
                    "provider": {
                        "datadog": {
                            "aggregator": "sum",
                            "apiVersion": "v2",
                            "formula": policy.formula,
                            "interval": f"{policy.provider_window_seconds}s",
                            "queries": {
                                "errors": policy.errors_query,
                                "requests": policy.requests_query,
                            },
                            "secretRef": {
                                "name": policy.datadog_secret_name,
                                "namespaced": True,
                            },
                        }
                    },
                    "successCondition": success_condition,
                }
            ],
        },
    }
    service_fqdn = f"{policy.service_name}.{policy.namespace}.svc.cluster.local"
    rollout = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Rollout",
        "metadata": {
            "annotations": annotations.copy(),
            "name": policy.rollout_name,
            "namespace": policy.namespace,
        },
        "spec": {
            "minReadySeconds": 10,
            "progressDeadlineAbort": True,
            "progressDeadlineSeconds": policy.progress_deadline_seconds,
            "replicas": policy.replicas,
            "revisionHistoryLimit": 5,
            "rollbackWindow": {"revisions": 3},
            "selector": {"matchLabels": selector.copy()},
            "strategy": {
                "canary": {
                    "maxSurge": 1,
                    "maxUnavailable": 0,
                    "steps": [
                        {"setWeight": policy.canary_weight},
                        {"pause": {"duration": f"{policy.pause_seconds}s"}},
                        {
                            "analysis": {
                                "args": [
                                    {"name": "service-name", "value": service_fqdn},
                                    {
                                        "name": "canary-hash",
                                        "valueFrom": {"podTemplateHashValue": "Latest"},
                                    },
                                ],
                                "templates": [{"templateName": policy.analysis_template_name}],
                            }
                        },
                    ],
                }
            },
            "template": {
                "metadata": {
                    "annotations": annotations.copy(),
                    "labels": pod_labels,
                },
                "spec": {
                    "automountServiceAccountToken": False,
                    "containers": [
                        {
                            "image": policy.image,
                            "imagePullPolicy": "IfNotPresent",
                            "livenessProbe": _http_probe(
                                policy.liveness_path,
                                failure_threshold=3,
                                period_seconds=10,
                            ),
                            "name": policy.rollout_name,
                            "ports": [
                                {
                                    "containerPort": policy.container_port,
                                    "name": "http",
                                    "protocol": "TCP",
                                }
                            ],
                            "readinessProbe": _http_probe(
                                policy.readiness_path,
                                failure_threshold=3,
                                period_seconds=5,
                            ),
                            "resources": {
                                "limits": {
                                    "cpu": policy.limit_cpu,
                                    "memory": policy.limit_memory,
                                },
                                "requests": {
                                    "cpu": policy.request_cpu,
                                    "memory": policy.request_memory,
                                },
                            },
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "capabilities": {"drop": ["ALL"]},
                                "readOnlyRootFilesystem": True,
                                "runAsNonRoot": True,
                            },
                            "startupProbe": _http_probe(
                                policy.startup_path,
                                failure_threshold=30,
                                period_seconds=2,
                            ),
                        }
                    ],
                    "enableServiceLinks": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "terminationGracePeriodSeconds": policy.termination_grace_seconds,
                },
            },
        },
    }
    return {
        "apiVersion": "v1",
        "items": [service, analysis_template, rollout],
        "kind": "List",
    }


def serialize_rollback_bundle(policy: RollbackCandidatePolicy) -> bytes:
    """Return stable, human-readable UTF-8 JSON for the rendered resource list."""
    bundle = render_rollback_bundle(policy)
    return (
        json.dumps(
            bundle,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _require_intact(policy: RollbackCandidatePolicy) -> None:
    if type(policy) is not RollbackCandidatePolicy or not policy._is_intact():
        raise RollbackPolicyError("rollback candidate policy is raw or mutated")


def _annotations(policy: RollbackCandidatePolicy) -> dict[str, str]:
    return {
        "sre-harness.genai-enablement/controller-floor": policy.controller_floor,
        "sre-harness.genai-enablement/evidence-scope": policy.evidence_scope,
        "sre-harness.genai-enablement/human-approval-required": "true",
        "sre-harness.genai-enablement/policy-revision": policy.policy_revision,
    }


def _http_probe(path: str, *, failure_threshold: int, period_seconds: int) -> dict[str, Any]:
    return {
        "failureThreshold": failure_threshold,
        "httpGet": {"path": path, "port": "http", "scheme": "HTTP"},
        "periodSeconds": period_seconds,
        "timeoutSeconds": 1,
    }


def _policy_document(policy: RollbackCandidatePolicy) -> dict[str, object]:
    return {
        "analysisTemplateName": policy.analysis_template_name,
        "canaryWeight": policy.canary_weight,
        "container": {
            "limitCpu": policy.limit_cpu,
            "limitMemory": policy.limit_memory,
            "livenessPath": policy.liveness_path,
            "port": policy.container_port,
            "readinessPath": policy.readiness_path,
            "requestCpu": policy.request_cpu,
            "requestMemory": policy.request_memory,
            "startupPath": policy.startup_path,
            "terminationGraceSeconds": policy.termination_grace_seconds,
        },
        "controllerFloor": policy.controller_floor,
        "datadogSecretName": policy.datadog_secret_name,
        "image": policy.image,
        "metric": {
            "formula": policy.formula,
            "initialDelaySeconds": policy.initial_delay_seconds,
            "maximumErrorRate": policy.maximum_error_rate,
            "measurementCount": policy.measurement_count,
            "measurementIntervalSeconds": policy.measurement_interval_seconds,
            "name": policy.metric_name,
            "providerWindowSeconds": policy.provider_window_seconds,
            "queries": {
                "errors": policy.errors_query,
                "requests": policy.requests_query,
            },
        },
        "namespace": policy.namespace,
        "pauseSeconds": policy.pause_seconds,
        "progressDeadlineSeconds": policy.progress_deadline_seconds,
        "replicas": policy.replicas,
        "rolloutName": policy.rollout_name,
        "serviceName": policy.service_name,
    }


def _policy_seal(policy: RollbackCandidatePolicy) -> str:
    envelope = {
        "schemaVersion": ROLLBACK_POLICY_SCHEMA,
        "evidenceScope": policy.evidence_scope,
        "policyRevision": policy.policy_revision,
        "policy": _policy_document(policy),
    }
    canonical = _canonical_json(envelope)
    return hmac.new(_INTEGRITY_KEY, canonical, hashlib.sha256).hexdigest()


def _canonical_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise RollbackPolicyError("value is not canonical JSON") from exc


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RollbackPolicyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> object:
    raise RollbackPolicyError(f"non-finite JSON number is not allowed: {value}")


def _exact_object(value: object, field_name: str) -> dict[str, object]:
    if type(value) is not dict:
        raise RollbackPolicyError(f"{field_name} must be an exact object")
    return value


def _exact_fields(value: dict[str, object], expected: frozenset[str], field_name: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise RollbackPolicyError(
            f"{field_name} fields are not closed (missing={missing}, unknown={unknown})"
        )


def _exact_text(value: object, field_name: str, *, maximum: int = 253) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise RollbackPolicyError(f"{field_name} must be a non-blank exact string")
    if len(value) > maximum or any(ord(character) < 32 for character in value):
        raise RollbackPolicyError(f"{field_name} is not a bounded printable string")
    return value


def _exact_sha256(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name)
    if not _SHA256.fullmatch(text):
        raise RollbackPolicyError(f"{field_name} must be an exact SHA-256")
    return text


def _exact_int(
    value: object,
    field_name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int:
        raise RollbackPolicyError(f"{field_name} must be an exact integer")
    assert isinstance(value, int)
    if value < minimum or value > maximum:
        raise RollbackPolicyError(f"{field_name} must be between {minimum} and {maximum}")
    return value


def _dns_label(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name, maximum=63)
    if not _DNS_LABEL.fullmatch(text):
        raise RollbackPolicyError(f"{field_name} must be a Kubernetes DNS label")
    return text


def _metric_query(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name, maximum=4096)
    for argument in _QUERY_ARGUMENTS:
        if argument not in text:
            raise RollbackPolicyError(f"{field_name} must reference {argument}")
    lowered = text.lower()
    if any(term in lowered for term in _SUSPICIOUS_QUERY_TERMS):
        raise RollbackPolicyError(f"{field_name} must not contain credential-like material")
    return text


def _http_path(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name, maximum=128)
    if not _HTTP_PATH.fullmatch(text) or "//" in text or "/../" in f"{text}/":
        raise RollbackPolicyError(f"{field_name} must be a bounded absolute HTTP path")
    return text


def _cpu_quantity(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name, maximum=16)
    if not _CPU_QUANTITY.fullmatch(text):
        raise RollbackPolicyError(f"{field_name} must be an exact positive CPU quantity")
    return text


def _cpu_millicores(value: str) -> int:
    if value.endswith("m"):
        return int(value[:-1])
    return int(value) * 1000


def _memory_quantity(value: object, field_name: str) -> str:
    text = _exact_text(value, field_name, maximum=16)
    if not _MEMORY_QUANTITY.fullmatch(text):
        raise RollbackPolicyError(f"{field_name} must be an exact positive binary memory quantity")
    return text


def _memory_kibibytes(value: str) -> int:
    units = {"Ki": 1, "Mi": 1024, "Gi": 1024 * 1024}
    unit = value[-2:]
    return int(value[:-2]) * units[unit]


__all__ = [
    "ARGO_ROLLOUTS_CONTROLLER_FLOOR",
    "MAX_ROLLBACK_POLICY_BYTES",
    "ROLLBACK_POLICY_SCHEMA",
    "MetricObservation",
    "MetricObservationState",
    "RollbackCandidatePolicy",
    "RollbackDisposition",
    "RollbackPolicyError",
    "evaluate_rollback",
    "load_rollback_candidate",
    "parse_rollback_candidate",
    "render_rollback_bundle",
    "serialize_rollback_bundle",
]
