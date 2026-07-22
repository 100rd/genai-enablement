# SPEC-B3 — Deterministic canary rollback

**Specification type:** Capability SPEC  
**Status:** Draft / construction  
**Owner:** `genai-enablement` Autonomous SRE harness  
**Governing decisions:** [ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md) and the
[Autonomous SRE harness plan](../autonomous-sre-harness-plan.md)  
**Roadmap gate:** `B3`  
**Depends on:** —  
**Evidence scope:** `local-portable-only`  
**Operational state:** `incomplete`  
**Next gate:** `human-policy-and-live-canary-qualification`  
**Authority:** `non-authorizing`; deterministic rendering/oracle only, with no apply or deployment authority

## Intent and boundary

As a delivery-system owner, I need an explicitly reviewed canary policy rendered into an Argo Rollouts
basic-canary plus a Datadog `AnalysisTemplate` so that a bounded metric decision can stop the candidate
and return traffic to the stable ReplicaSet without an LLM, agent, prompt, or runtime judgment in the
rollback path.

SPEC-B3 owns a portable fixture-only policy envelope, an offline decision oracle, and deterministic
Kubernetes JSON rendering. It does not own a production error-rate threshold, Datadog tag convention,
credential, cluster, controller installation, traffic router, image, service SLO, or rollout approval.
The generated resources are construction candidates and confer no deployment authority.

**Assumed compatibility floor:** Argo Rollouts `v1.7.0` or newer because Datadog v2 `queries` and
`formula` were introduced in that line. The Kubernetes version/distribution, namespace, Pod Security
Admission mode, CNI, GitOps controller, and installed CRD revision are unbound until live acceptance.

**Inputs:** one bounded, content-addressed, `fixture`-scoped candidate policy and zero or more offline
metric observations.  
**Outputs:** one deterministic observation/continue/abort disposition and one Kubernetes JSON `List`
containing a `Service`, `AnalysisTemplate`, and `Rollout`.  
**Out:** cluster apply/sync, credential material, production threshold selection, LLM/model calls,
traffic-router invention, manual promotion, rollback execution by the Python module, and claims of a
live or tested rollback.

## Requirements

[REQ-B3-1] **The candidate policy is closed, bounded, content-addressed, and fixture-only.** The only
accepted schema is `sre-harness.rollback-candidate/v1`; strict UTF-8 JSON is capped at 1 MiB and rejects
duplicate keys, non-finite JSON numbers, symlinks, non-files, unknown/missing fields, wrong primitives,
and a `policyRevision` that is not the canonical SHA-256 of the exact nested policy. `evidenceScope` must
be `fixture`; this interface cannot label itself production evidence. — **Fallback:** reject before
decision or rendering.

[REQ-B3-2] **Human-owned rollout inputs are explicit and constrained, never inferred.** Namespace and
resource names must be Kubernetes DNS labels; the image must be pinned by `sha256` digest; replicas,
basic-canary weight, pause, deadline, probe paths/port, and resource requests/limits are exact policy
fields. Replica count and weight must yield an integral basic-canary pod ratio. Metric queries must
reference both the exact service and latest ReplicaSet hash arguments. The error-rate ceiling is a
canonical decimal candidate string in `(0, 1)`. — **Fallback:** reject an approximate, mutable, or
under-specified candidate.

[REQ-B3-3] **The offline oracle has three non-authorizing dispositions.** Fewer than the configured
number of successful samples returns `observe`; exactly the configured count of finite values at or
below the ceiling returns `continue`; any value above the ceiling, missing data, provider error, NaN, or
infinity returns `abort_to_stable`. Extra samples and raw/mutated policies are invalid. The oracle is a
test mirror, not a cluster actuator. — **Fallback:** invalid input never returns `continue`.

[REQ-B3-4] **Analysis is inline, finite, complementary, and fail closed.** The rendered rollout sets an
explicit canary weight, waits a finite pause, then invokes one inline namespaced `AnalysisTemplate`.
The metric has a finite positive `count`; `failureLimit`, `inconclusiveLimit`, and
`consecutiveErrorLimit` are all zero. Success and failure expressions are complementary for finite
values, use `default()` so Datadog `nil` is failure, and explicitly fail NaN/Inf. There is no `dryRun`.
— **Fallback:** the candidate cannot advance on an unknown metric result.

[REQ-B3-5] **Datadog configuration is explicit and credential-free.** The provider is Datadog v2 with
explicit `queries`, exact `formula: errors / requests`, explicit `sum` aggregator, polling interval and
provider window. The template references a namespaced Secret by name only; it contains no Secret
resource, address, API key, application key, token, environment fallback, or embedded credential.
— **Fallback:** a consumer must provision and authorize the Secret separately.

[REQ-B3-6] **The basic canary returns to the stable ReplicaSet without model authority.** No traffic
router is fabricated. A normal `Service` selects both stable and candidate pods; the exact integral pod
ratio supplies the bounded weight. An unsuccessful inline analysis aborts the rollout, and Argo
Rollouts' basic-canary controller behavior rolls back toward the stable ReplicaSet. The bundle sets
`progressDeadlineAbort: true`; no LLM, web hook, job, plugin, or Python callback participates in the
decision path. — **Fallback:** controller/analysis failure is not promotion authority.

[REQ-B3-7] **The workload candidate includes portable safety defaults.** Selector and pod labels match;
the image is immutable; startup/readiness/liveness probes, CPU/memory requests and limits, termination
grace, non-root execution, runtime-default seccomp, dropped capabilities, read-only root filesystem,
disabled privilege escalation, and disabled service-account-token automount are explicit. — **Fallback:**
reject policies that cannot render these fields completely.

[REQ-B3-8] **The renderer is deterministic and carries its evidence boundary.** Identical intact policy
bytes produce identical JSON resources and serialized bytes. Every resource is namespaced and annotated
with the exact policy revision, `evidence-scope=fixture`, `human-approval-required=true`, and controller
floor. The bundle contains no status, applied UID, cluster name, observed timestamp, approval, or live
result. — **Fallback:** local rendering remains a candidate artifact.

[REQ-B3-9] **Portable conformance is not live rollback evidence.** B3 exit requires a human-selected and
immutable workload/policy revision; accepted threshold and Datadog query/tag semantics; installed pinned
Argo Rollouts CRDs/controller; server-side schema admission; a provisioned least-privilege namespaced
Secret; positive promotion and forced-negative rollback observations; stable-service verification;
controller/AnalysisRun evidence; rollback latency and false-positive measurements; and an approved
recovery/override procedure. — **Fallback:** B3 remains incomplete.

## Portable interfaces

```text
load_rollback_candidate(path) -> RollbackCandidatePolicy
evaluate_rollback(policy, observations) -> RollbackDisposition
render_rollback_bundle(policy) -> Kubernetes JSON List
serialize_rollback_bundle(policy) -> deterministic UTF-8 JSON bytes
```

## Verification / acceptance probes

- **P-B3-1 closed-policy:** valid exact fixture policy loads; oversize, symlink, duplicate/non-finite,
  malformed, unknown/missing, wrong-type, non-fixture, and revision-mismatched input fails closed.
- **P-B3-2 explicit-candidate:** mutable images, invalid names/quantities/paths/ranges, approximate pod
  weights, non-canonical thresholds, foreign formulas, and queries missing required arguments fail.
- **P-B3-3 oracle:** partial successes observe; the exact bounded success sequence continues; breach,
  no-data, provider-error, NaN, and Inf abort; extra samples and raw/mutated policies fail.
- **P-B3-4 analysis:** one inline finite analysis has complementary no-data/non-finite-safe conditions,
  zero failure/inconclusive/error tolerance, no dry-run, and exact policy timings.
- **P-B3-5 Datadog:** v2 queries/formula/sum/window and a namespaced Secret reference render without
  credential fields or a Secret resource.
- **P-B3-6 rollback-path:** basic-canary exact weight/pause/analysis, latest-hash rejoin, deadline abort,
  and stable Service selection render with no LLM/agent/plugin/web/job decision surface.
- **P-B3-7 workload-safety:** immutable image, probes, resources, selector equality, token disablement,
  and restricted pod/container security contexts are structurally present.
- **P-B3-8 reproducibility:** repeated rendering is byte-identical and the checked-in example bundle is
  exactly generated from the checked-in candidate policy with fixture annotations.
- **P-B3-9 evidence-scope:** docs/status retain the construction boundary until immutable live positive
  and negative runs plus measured rollback evidence exist.

## Current evidence and blockers

The strict fixture-only policy reader, integrity-sealed policy, finite offline oracle, deterministic
renderer, and checked-in byte-exact Kubernetes JSON bundle exist in the dirty local worktree. Local
parsing, rendering, and green tests prove only the closed portable contract; they cannot prove that a
cluster admits the CRDs, Datadog returns the intended canary signal, the Secret is provisioned, or stable
traffic is restored.

The closed local
[`SPEC-B3` portable traceability manifest](../../solutions/sre-harness/spec-traceability/SPEC-B3.json)
binds this exact SPEC digest and all nine probe ids to existing pytest nodes plus the bounded implementation
path. The portfolio checker parses the test file with the Python AST and rejects a stale source digest,
missing/extra probe, missing test node, path escape, symlink, malformed shape, or authority/evidence
overclaim. The manifest is a static local traceability index, not a stored test result, admitted resource,
observed rollback artifact, live evidence receipt, or authority grant; its referenced tests must still
pass in the declared Python 3.11+ environment.

B3 remains incomplete until the live acceptance evidence in REQ-B3-9 exists. No local artifact may
select production thresholds, authorize an apply/sync, or clear that gate.
