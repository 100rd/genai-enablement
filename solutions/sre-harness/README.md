# sre-harness

First slice of the **Autonomous SRE Harness** (see
[`docs/autonomous-sre-harness-plan.md`](../../docs/autonomous-sre-harness-plan.md)).

The harness is the product: agents do the ops work under hard, deterministic
gates. This package contains the safety core, the first change-validation gate,
and a bounded offline read-only triage/RCA construction slice. The current
implementation is deterministic and fully unit-tested; no LLM is in the loop.

## Modules

| Module | Responsibility |
|---|---|
| `sre_harness.autonomy_tiers` | Tier model `T1 read-only → T4 autonomous`, the action-tier table, and `classify()` which **degrades down** (toward more human control) on low confidence or off-plan actions. |
| `sre_harness.advisory_integration` | **SPEC-B2 integration boundary**: a strict bounded content-addressed change/platform envelope with a five-minute snapshot freshness ceiling, deterministic gate invocation, versioned immutable result, and distinct `proceed`/`block`/`require_human`/invalid dispositions. Portable fixture conformance only; no live pipeline authority. |
| `sre_harness.rollback` | **SPEC-B3 construction boundary**: a strict content-addressed fixture-only canary policy, sealed finite `observe`/`continue`/`abort_to_stable` oracle, and deterministic Kubernetes JSON renderer for a Service, Datadog v2 AnalysisTemplate, and hardened Argo Rollout. No cluster, credential, LLM, or deployment authority. |
| `sre_harness.remediation` | **SPEC-B4 construction boundary**: strict content-addressed allowlist/request ingestion, externally verified policy capability, exact T4-to-T3 authorization, account/region/version/hash-bound SSM Automation calls, deterministic UUID idempotency, finite one-step compensation, and non-secret idempotent notifications. Explicit ports only; no credentials, AWS discovery, approval signal, or live authority. |
| `sre_harness.hitl` | **SPEC-B5 construction boundary**: strict content-addressed T3 proposals and human receipts, runtime-pinned canonical tier admission, exact external receipt verification, first-step SSM `Approve`/`Reject`, read-only protected GitLab MR approval observation, sealed finite cases, and sanitized idempotent audit. No credentials, provider discovery, automatic MR approval/merge, or fixture authority. |
| `sre_harness.permanent_fix` | **SPEC-B6 construction boundary**: strict content-addressed request/policy/factory-outcome contracts, exact external capabilities, one idempotent issue-create call, read-only factory-owned MR/PR chase, exact human-gated two-source `LANDED` join, sealed finite state, and sanitized audit. No code authoring, branch push, MR/PR creation, CI trigger, approval, merge, issue close, or incident-close authority. |
| `sre_harness.platform_graph` | `PlatformGraph` port mirroring the Omniscience MCP `list_entities` contract, an `InMemoryPlatformGraph` fake, and an `OmniscienceMcpPlatformGraph` adapter over an `McpToolClient` seam. Exposes `storageclasses_in_cluster()` and `namespaces_in_cluster()`. |
| `sre_harness.change_checks` | The three deterministic checks behind the gate, each a pure `(request, graph) -> CheckResult`: `storageclass_present`, `blast_radius` (action-tier classification), `namespace_present`. `DEFAULT_CHECKS` is the registered list. |
| `sre_harness.change_gate` | Multi-check change-validation gate: runs `DEFAULT_CHECKS` and aggregates (`block` dominates → else `require_human` → else `proceed`). `GateResult` exposes the aggregate verdict, a combined rationale, per-check `check_results`, and (back-compat) the StorageClass-specific evidence. Analysis is T1; the verdict is T2 (advisory) — the gate never executes anything. |
| `sre_harness.change_parsers` | Best-effort parsers extracting `service` / `target_cluster_ids` / `required_storageclasses` and (Stage 2) `required_namespaces` + high-blast-radius `actions` from a k8s manifest dict (`parse_k8s_manifest`) or a unified PR diff (`parse_pr_diff`). |
| `sre_harness.cli` | Legacy `sre-harness gate` plus strict `gate-integration` (SPEC-B2), which loads the closed envelope, writes an optional result artifact, and preserves machine-distinct integration exits. |
| `sre_harness.eval` | **SPEC-B0 portable baseline**: frozen incident-replay labels (`Scenario` = `{id, kind, snapshot, ground_truth}`), a target/scorer-separated `run_eval(...)`, honest implemented Pass@1/lead-time metrics, explicit unsupported metric failures, and deterministic seed suites. Pure, offline, non-authorizing — no LLM. Run with `python -m sre_harness.eval`. |
| `sre_harness.triage` | **B1 read-only triage/RCA construction slice**: strict v1 JSON ingestion and a one-method `IncidentSnapshotSource`, immutable incident snapshots, exact request rejoin, bounded service/time gather, a single `ReadOnlyAnalyzer.analyze()` seam, evidence-rejoined facts and hypotheses, calibrated confidence, a T1 RCA draft with no action surface, and three incident-replay seed labels scored through the shared eval runner. |
| `sre_harness.sentinel` | **SPEC-B7-CORE plus five detector-family SPECs** (plan Stage 7 — [ADR-0001](../../docs/decisions/0001-continuous-detection-sentinel.md)): the proactive surface to the gate's at-change one. A `Detector(state) -> [Finding]` contract, default registry, deterministic dedup/ranking, source/store/CLI seams, and all five catalog families (`saturation_expiry`, `new_error_signature`, `error_rate_vs_baseline`, `change_induced_regression`, `config_state_drift`) scored offline on lead-time and false-positive rate. Detection is T1, a finding is T2 advisory — Sentinel never executes. |
| `sre_harness.observability` | **AgentOps** (plan cross-cutting): a thin tracing facade over OpenTelemetry — `get_tracer()`, the `span(...)` context manager, the `@traced(...)` decorator, and an optional `configure_tracing(...)` for OTLP export. Defines a **stable `sre_harness.*` attribute schema** (`attributes.py`) and instruments the gate, eval runner, and triage nodes. **No-op by default** — zero behaviour change and near-zero cost when no OTel provider is configured. |

The closed local [`SPEC-B0` traceability manifest](spec-traceability/SPEC-B0.json) binds the exact
[`SPEC-B0`](../../docs/specs/SPEC-B0-offline-eval-harness.md) Draft digest and all eight eval-baseline
probes to existing implementation and pytest nodes. It remains `local-portable-only`, operationally
`incomplete`, and `non-authorizing`: seed fixtures and green tests are not a human-owned corpus,
published regression policy, model approval, runtime qualification, or production evidence.

## Read-only triage and RCA — B1 construction slice

`run_triage(snapshot)` executes three explicit nodes: bounded `gather`,
read-only `analyze`, and pure RCA `draft`. The snapshot and every evidence item
are frozen and UTC-bound; gather admits at most 128 same-service observations in
the configured lookback and sorts them deterministically. Analyzer facts and
hypotheses remain different types, confidence is bounded, and every cited ID is
rejoined to the gathered context before a report is returned. Missing evidence
produces an explicit low/zero-confidence `undetermined` result rather than a
fabricated cause.

`run_triage_from_source(request, source)` adds the SPEC-B1 ingestion boundary.
The provided `JsonFileIncidentSnapshotSource` reads a regular non-symlink UTF-8
file up to 1 MiB, rejects duplicate keys, non-finite values, unknown/missing
fields and wrong types, then rejoins the returned incident id and capture time
to the exact request. It is an offline adapter, not a live provider binding:

```python
from datetime import UTC, datetime
from pathlib import Path

from sre_harness.triage import (
    JsonFileIncidentSnapshotSource,
    SnapshotRequest,
    run_triage_from_source,
)

request = SnapshotRequest(
    incident_id="inc-payments-001",
    as_of=datetime(2026, 7, 16, 8, 20, tzinfo=UTC),
)
report = run_triage_from_source(
    request,
    JsonFileIncidentSnapshotSource(Path("examples/incident-snapshot.json")),
)
```

The default deterministic analyzer recognises only two seed regression-oracle
patterns (post-deploy error increase and resource saturation). Three curated
fixture scenarios exercise those patterns plus the honest-unknown path through
the shared `run_eval(..., scorer=triage_pass_at_1)` harness. This proves the
portable pipeline and eval seam, not production RCA quality. B1 still requires
read-only live Datadog/log/metric/deploy source adapters, an approved model or
vendor analyzer binding with token/cost telemetry, a curated real-incident
corpus and thresholds, and measured usefulness/false-positive evidence. No
current triage type exposes remediation, execution, or another write tool.

`evaluate_triage_suite(...)` prevents a local score from becoming a stronger
claim. `TriageEvalPolicy` supplies content-addressed candidate thresholds for
suite size, cause coverage, Pass@1, and unknown confidence. The report separates
`threshold_conformant` from evidence scope: current seeds are always
`fixture-only`, and their `production_evidence_eligible` result is `False`.
`TriageCorpusPublicationGate` can issue a process-local sealed capability only
after an allowlisted external verifier returns exact `True` for an unchanged
publication binding. Evaluation rejoins its exact policy revision, scenario ids,
and canonical snapshot/label manifest. Raw, fabricated, mutated, or mismatched
inputs fail closed, and even a verified publication cannot promote fixtures. The
repository configures no real external corpus publication; the positive gate
probe uses a deterministic verifier test double only.

The closed local
[`SPEC-B1` traceability manifest](spec-traceability/SPEC-B1.json) binds the exact
SPEC digest and every `P-B1-1..9` probe to existing pytest nodes and bounded
implementation paths. It stores no PASS result. In a project environment that
satisfies the declared Python 3.11+ development dependencies, its referenced
surface is exercised with:

```bash
python -m pytest -q tests/test_triage_source.py tests/test_triage_pipeline.py \
  tests/test_triage_eval.py tests/test_triage_eval_publication.py \
  tests/test_observability.py
```

The portfolio drift checker validates only exact local traceability; neither the
manifest nor the command is live-provider, production-quality, or authorization
evidence.

## The gate — three deterministic checks, aggregated

The gate (`change_gate.evaluate_change`) runs a registered list of pure checks
(`change_checks.DEFAULT_CHECKS`) and aggregates their verdicts. Each check is a
`(request, graph) -> CheckResult` carrying `{check_id, verdict, rationale,
evidence}`; adding a check means adding a callable to the registry, nothing else.

| Check | Question | proceed / block / require_human |
|---|---|---|
| `storageclass_present` | Is every required StorageClass present in the target clusters? | present everywhere → `proceed`; absent in **every** target → `block`; absent in some-but-not-all → `require_human`. |
| `blast_radius` | Does the change touch a high-blast-radius resource (RDS / IAM / security groups / data deletion)? | Each `action` is mapped via the action-tier table: a **T3** action — or an off-plan (unknown) one — → `require_human`; T4 (autonomous) / T2 / T1 → `proceed`. Never blocks: a high-blast-radius change is a *human decision*. |
| `namespace_present` | Is every required Namespace present in the target clusters? | Same presence semantics as StorageClass, for namespaces. |

**Aggregation:** `block` dominates → else `require_human` if any check needs a
human → else `proceed`. `GateResult.check_results` carries every per-check result
so the aggregate verdict is auditable.

## CLI — `sre-harness gate`

Makes the gate usable in a pipeline (plan Stage 2 — **advisory**). It loads a
change request and a platform-graph JSON fixture, runs `evaluate_change`, wraps
the verdict through the autonomy-tier engine (analysis T1 / verdict T2), prints
the aggregate verdict + combined rationale + per-check `check_results` as JSON,
and exits with a CI-meaningful code derived from the **aggregate** verdict:

| Exit | Verdict | Meaning |
|---|---|---|
| `0` | `proceed` | Every check is satisfied. |
| `1` | `block` | A check blocked (e.g. required StorageClass/Namespace absent in **every** target cluster). |
| `2` | `require_human` | A check needs a human: some-but-not-all coverage, or a high-blast-radius action (also: usage errors). |

```bash
# structured JSON change request (default --change-format json)
sre-harness gate --change examples/change-request.json --graph examples/platform-graph.json

# best-effort from a k8s manifest
sre-harness gate --change examples/statefulset.json --change-format k8s \
  --graph examples/platform-graph.json

# best-effort from a PR diff (service + clusters supplied by flags)
sre-harness gate --change my-diff.json --change-format pr-diff \
  --service payments --target-cluster prod-eu-1 --target-cluster prod-us-1 \
  --graph examples/platform-graph.json
```

Without `poetry install`: `python -m sre_harness.cli gate ...` (with `src` on
`PYTHONPATH`). The `--graph` fixture is the seam where the live
`OmniscienceMcpPlatformGraph` adapter plugs in later (see
[`integrations/README.md`](integrations/README.md)).

CI / GitOps templates live in [`integrations/`](integrations/) (GitLab CI stage
+ ArgoCD PreSync hook, both advisory by default with a documented switch to
blocking). Example fixtures are in [`examples/`](examples/).

## Strict advisory integration — `sre-harness gate-integration`

The SPEC-B2 surface accepts only
`sre-harness.change-advisory-request/v1`: a bounded strict UTF-8 envelope that content-addresses its
closed change and platform snapshot. The platform `asOf` cannot be future or more than five minutes
older than the request under the draft portable candidate policy; a real consumer owner must accept or
revise that ceiling. It emits `sre-harness.change-advisory-result/v1`, exactly rejoining
the invocation, input digest/revisions, every deterministic check, and the T1/T2 boundary. The result
states `advisory: true` and `mutationAuthorized: false`.

```bash
sre-harness gate-integration \
  --input examples/change-advisory-invocation.json \
  --result /tmp/change-advisory-result.json
```

Exit codes are `0=proceed`, `10=block`, `20=require_human`, and `64=invalid/unavailable integration`.
Valid non-zero results are written before exit. The committed envelope and integration templates are
fixtures; no real GitLab/Argo run or approved live platform source is configured.

## Deterministic canary rollback — B3 construction slice

`sre_harness.rollback` accepts only `sre-harness.rollback-candidate/v1`: a bounded strict JSON envelope
whose exact nested policy is SHA-256 addressed and whose `evidenceScope` is forced to `fixture`. It
rejects mutable images, approximate basic-canary pod ratios, invalid Kubernetes names, missing canary
query arguments, non-canonical thresholds, incomplete probes/resources, and a deadline shorter than the
declared pause plus analysis window.

The offline oracle mirrors the finite analysis outcome without touching a cluster. Partial finite
measurements observe, the exact configured sequence at/below the candidate ceiling continues, and a
breach, negative value, no data, provider error, NaN, or infinity aborts to stable. `continue` is an
oracle result, not deploy or promotion authorization.

```python
from pathlib import Path

from sre_harness.rollback import load_rollback_candidate, serialize_rollback_bundle

candidate = load_rollback_candidate(Path("examples/rollback-candidate-policy.json"))
bundle = serialize_rollback_bundle(candidate)
```

The checked-in
[`integrations/argo-rollouts-deterministic-canary.json`](integrations/argo-rollouts-deterministic-canary.json)
is byte-for-byte generated from the checked-in candidate. It is Kubernetes JSON (not a claim of an
applied object): one normal Service, one namespaced Datadog v2 AnalysisTemplate, and one basic-canary
Rollout with inline finite analysis, latest ReplicaSet hash rejoin, deadline abort, immutable image,
probes/resources, and restricted pod/container security contexts. The example image uses
`registry.example.invalid` deliberately, and every resource is annotated `evidence-scope=fixture` and
`human-approval-required=true`.

The closed [`SPEC-B3` traceability manifest](spec-traceability/SPEC-B3.json) binds the exact draft digest
and `P-B3-1..9` to the bounded rollback implementation and existing pytest nodes. It stores no PASS result,
does not prove schema admission or a stable rollback, and grants no apply, sync, or deployment authority.

B3 still requires a human-owned immutable workload/policy, accepted SLO threshold and Datadog tag/query
semantics, pinned installed Argo controller/CRDs, least-privilege namespaced Secret, server-side schema
admission, observed positive promotion and forced-negative rollback to stable, plus rollback-latency and
false-positive evidence. Local rendering and tests cannot satisfy those gates.

## Tier-4 allowlisted remediation — B4 construction slice

`sre_harness.remediation` accepts only closed, bounded, content-addressed policy and request schemas. A
policy must be unchanged and receive exact boolean `True` from its preconfigured external verifier before
it can issue the opaque process-local capability used by authorization. The checked example remains
`evidenceScope: fixture`, so it always degrades to T3 and cannot authorize execution.

Authorization reuses the canonical `classify()` action-tier table. Only an exact, fresh, high-confidence
match for `restart_stateless_pod`, `retrigger_argocd_sync`, or `scale_stateless_service` can remain T4.
Each entry binds one account, region, environment, target tuple, execution role, numeric forward/rollback
document versions and SHA-256 values; replica alternatives are bounded. Low confidence, stale or off-plan
requests, binding drift, and any fixture policy return `require_t3` before a client call.

The execution core depends only on explicit SSM Automation and notification ports. It rejoins the client
account/region and exact active account-owned schema-0.3 document before each start; fixes
`MaxConcurrency="1"` and `MaxErrors="0"`; derives UUID client tokens from the request, policy, and phase;
and permits only one compensation runbook. Approval/calendar states escalate without sending an approval
signal. Transition notifications have stable dedupe keys and deliberately omit parameters, roles, tokens,
document content, and exception detail.

The closed [`SPEC-B4` traceability manifest](spec-traceability/SPEC-B4.json) binds the exact draft digest
and `P-B4-1..10` to the bounded tier-classification/remediation implementation and existing pytest nodes.
It stores no PASS result, does not prove IAM containment or a live runbook drill, and grants no AWS or
execution authority.

The fake-client tests prove only portable authorization, call-shape, state-transition, retry, and
notification contracts. B4 still needs a human-approved immutable production allowlist and runbooks,
least-privilege IAM/PassRole and target containment, durable compare-and-swap orchestration, idempotent
delivery, retained audit/CloudTrail evidence, and observed positive/negative/retry/permission drills with
blast-radius, rollback-latency, and false-positive measurements. No AWS account is configured or contacted
by this slice.

## Tier-3 HITL remediation — B5 construction slice

`sre_harness.hitl` separates a review proposal from human authority. A proposal binds the exact action,
parameters, risk/rollback references, provider subject, expiry, and a revision derived from the current
canonical action-tier table plus confidence threshold. It contains no approval field. Only an on-plan
effective T3 action opens a human case: native T3 actions can qualify directly, deterministic low-confidence
T4 actions can degrade to T3, effective T4 routes back to B4, and lower/off-plan actions cannot be promoted
by a receipt.

The separately content-addressed receipt binds one proposal and subject, human reviewer eligibility and
authentication evidence revisions, decision, evidence, and exclusive expiry. A preconfigured external
verifier must return exact boolean `True` over the unchanged receipt. Fixture, agent/bot/service,
proposer-self, stale, future, copied, mutated, or cross-subject receipts never reach a provider.

For AWS, the core requires an exact client account/region plus a fresh first-step `PendingApproval`
snapshot matching execution id, numeric document version/hash, schema `0.3`, input revision, and step name.
It emits only a bounded `Approve` or `Reject` call with a stable dedupe key; the live port must supply the
durable dedupe that `SendAutomationSignal` lacks. Receipt expiry is checked before use and does not
retroactively revoke a signal already accepted. For GitLab, the port is read-only: approval requires the
exact protected target and head SHA, reset-on-push and reauthentication, unchanged non-empty satisfied
rules, zero approvals left, and an eligible reviewer distinct from author/committers. There is no approve,
merge, push, or pipeline-mutation method.

The closed [`SPEC-B5` traceability manifest](spec-traceability/SPEC-B5.json) binds the exact draft digest
and every source probe id to existing AST-discovered pytest nodes and the bounded classifier/HITL
implementation paths. It remains `local-portable-only`, operationally `incomplete`, and
`non-authorizing`; it stores no test result, verified human approval, provider observation, or live signal
authority.

The checked
[`examples/hitl-remediation-proposal.json`](examples/hitl-remediation-proposal.json) and
[`examples/hitl-approval-receipt.json`](examples/hitl-approval-receipt.json) are review fixtures; the
receipt is explicitly `evidenceScope: fixture` and cannot signal. Local tests prove parsing,
classification, joins, call shape, state, retry, and audit contracts only. B5 still needs human-owned
identity/MFA and reviewer eligibility, immutable runbook/MR policies, separate principals, durable
CAS/outbox orchestration, provider/audit adapters and retained approve/reject/expiry/drift/concurrency/
permission/recovery drills. No AWS or GitLab service is configured or contacted by this slice.

## Permanent-fix chase — B6 construction slice

`sre_harness.permanent_fix` bridges a mitigated incident into the normal factory without bypassing its
gates. A strict request binds one `incidentId` to one `taskId`, factory, exact provider/repository, P0
class, target branch, bounded sanitized issue content, immutable evidence references, and one externally
verified policy revision. Only a non-fixture policy capability can reach the provider. The sole write call
creates or adopts one issue through a stable opaque dedupe key; the provider adapter must back that key
with a durable ledger because issue-create APIs do not supply a portable idempotency token.

After intake, the port is read-only. It observes one exact factory-created MR/PR and rejects ambiguity,
GitHub PR-as-issue confusion, cross-repository/task/incident joins, target/head drift, premature closure,
and closed-unmerged changes. A separately verified canonical factory outcome is the only source of
`VERIFIED`, `GATED`, and `LANDED`; provider CI/approval/mergeability summaries never become authority.
`LANDED` requires both a human-gated passing factory outcome and a provider merged snapshot for the same
40-hex head. The module exposes no code, branch, MR/PR-create, pipeline, approval, merge, comment, issue
close, or incident-close method.

The closed [`SPEC-B6` traceability manifest](spec-traceability/SPEC-B6.json) binds the exact Draft digest
and `P-B6-1..10` to existing AST-discovered pytest nodes and the bounded
`sre_harness.permanent_fix` implementation. It remains `local-portable-only`, operationally `incomplete`,
and `non-authorizing`; it stores no PASS result, durable dedupe proof, provider/factory observation, human
gate, merge evidence, or incident-close authority.

[`examples/permanent-fix-policy-publication.json`](examples/permanent-fix-policy-publication.json) and
[`examples/permanent-fix-request.json`](examples/permanent-fix-request.json) are canonical review fixtures
with `evidenceScope: fixture`; neither can contact a provider. Local tests prove parser, capability,
dedupe, call-shape, join, lifecycle, timeout, and audit behavior only. B6 still needs human-owned immutable
provider/factory policy, separate principals, durable CAS/outbox and dedupe ledger, retained provider and
factory evidence, failure/race/recovery drills, and an observed exact incident-to-landed-revision chain.
No GitHub, GitLab, factory, CI, or incident system is configured or contacted by this slice.

## Sentinel — continuous detection (Stage 7)

Where the gate is *point-in-time* (validate **this change** at the PR/sync),
Sentinel is *continuous / periodic* (watch the **running system** for emerging
risk and **new problem classes**). Same deterministic-first shape as the gate:
detectors are pure `(state) -> [Finding]` rules over a `SentinelState` snapshot,
so the whole surface is unit-/eval-testable offline while the live sources
(Datadog / Loki / CloudWatch / Omniscience) are wired up separately (ADR-0001,
build order step 3). The `CronJob` runtime + a file-backed state/findings seam
(build order step 2) are below.

`run_sentinel(state, detectors=DEFAULT_DETECTORS, open_findings=())`:

1. runs every registered detector,
2. **dedupes** findings against the caller's already-open set (never re-alert a
   known finding) — suppressed ones are kept on the report for audit, and
3. **ranks** the survivors most-urgent-first by `severity × confidence`.

Detection is **T1** (read-only); a finding is **T2** (advisory) — Sentinel feeds
the gate → runbook → permanent-fix loop and never executes remediation.

| Detector | Surfaces | Findings |
|---|---|---|
| `saturation_expiry` | resources trending to exhaustion + near-expiry certs/tokens | `saturation` (observed critical / projected exhaustion / warn) and `expiry` (expired / critical / warn), by `Severity` |
| `new_error_signature` | error signatures present now but absent from the baseline window (novel *class*, not raw volume) | one `HIGH` finding per novel signature; naming/clustering is a future model step |
| `error_rate_vs_baseline` | exact aggregate current error rate meeting the maximum of rolling-baseline relative/absolute and declared SLO-budget thresholds, with at least 100 requests in both windows | one deterministic `HIGH`/`CRITICAL` advisory finding per qualifying service; candidate fixture thresholds, not accepted production policy |
| `change_induced_regression` | the same complete pre/post regression rule bound to distinct immutable revisions, ordered windows, a deploy no older than one hour, and zero intervening deploys | one `HIGH`/`CRITICAL` association finding per qualifying service/revision; explicitly correlation, not causation; replaces the same-service generic error-rate duplicate in one scan |
| `config_state_drift` | exact normalized tracking-policy/desired/observed digests that remain different for at least two observations and five minutes | one stable-resource `MEDIUM` advisory, elevated to `HIGH` for a missing observed resource or one-hour persistence; no raw config/diff and no reconciliation authority |

**Lead-time eval.** Detectors are scored offline by the eval harness on
**lead-time** (ADR measurement): replay timelines of state snapshots and verify
the detector fires *before* the incident page. The B7 corpus adds explicit
incident/early-detection and clean/false-positive metrics. Error-rate contributes
three clean controls; change regression contributes five: stable-high baseline,
low-volume spike, inside-SLO rate, expired association, and intervening deploy.
Config-state drift contributes five more: converged state, one observation,
inside-grace mismatch, inside-grace missing state, and desired-revision reset.
The 20-scenario portable corpus reports 6/6 early detections and 0/14 false
positives with mean lead 1.83 snapshots. This is fixture conformance, not
production calibration, source-completeness, causal, or reconciliation evidence. Run with:

The closed local
[`SPEC-B7-CORE`](spec-traceability/SPEC-B7-CORE.json) manifest binds the exact
[`Sentinel core SPEC`](../../docs/specs/SPEC-B7-core-sentinel-runtime-contract.md) Draft digest and all
eight common finding/source/scan/store/CLI/telemetry probes. It remains `local-portable-only`,
operationally `incomplete`, and `non-authorizing`; it grants no live source, runtime, delivery,
acknowledgement, credential, or action authority.

The closed local
[`SPEC-B7-NES`](spec-traceability/SPEC-B7-NES.json) manifest binds the exact
[`new-error-signature SPEC`](../../docs/specs/SPEC-B7-new-error-signature-detector.md) Draft digest and
all eight normalized-input, novelty, identity, registry, and replay probes. It grants no raw-log source,
signature-normalization policy, model clustering/naming, delivery, or remediation authority.

The closed local [`SPEC-B7`](spec-traceability/SPEC-B7.json) manifest binds the exact Draft digest and all
nine error-rate probes to existing pytest nodes and the bounded detector/state/serialization/eval
implementation. It remains `local-portable-only`, operationally `incomplete`, and `non-authorizing`; it
stores no PASS result and supplies no live source, accepted threshold, production calibration, runtime,
delivery, or remediation authority.

The closed local [`SPEC-B7-CIR`](spec-traceability/SPEC-B7-CIR.json) manifest similarly binds the exact
change-regression Draft digest and all ten probes to existing detector/state/serialization/scan/eval
paths. It remains `local-portable-only`, operationally `incomplete`, and `non-authorizing`: portable
association is correlation, not causation, and the manifest stores no PASS result or live authority.

The closed local [`SPEC-B7-DRIFT`](spec-traceability/SPEC-B7-DRIFT.json) manifest binds the exact
normalized-drift Draft digest and all ten probes to existing detector/state/serialization/scan/eval paths.
It remains `local-portable-only`, operationally `incomplete`, and `non-authorizing`; digest fixtures supply
no reconciliation authority, live Omniscience/source coverage, runtime, delivery, or remediation power.

The closed local
[`SPEC-B7-SAT`](spec-traceability/SPEC-B7-SAT.json) manifest binds the exact
[`saturation/expiry SPEC`](../../docs/specs/SPEC-B7-saturation-expiry-detector.md) Draft digest and all
nine normalized-input, candidate-band/projection, registry, and replay probes. Candidate fixture
thresholds grant no inventory/source policy, live calibration, renewal/resize, delivery, or remediation
authority.

```bash
python -m sre_harness.sentinel            # summary (pass rate + mean lead-time)
python -m sre_harness.sentinel --verbose  # also prints per-scenario lead-time
```

Exits non-zero if any scenario fails (fired too late, or a false positive on a
clean timeline), so it can gate CI alongside the Pass@1 suite.

### CLI — `sre-harness sentinel scan` (build order step 2)

Makes Sentinel runnable periodically (a `CronJob`, see
[`integrations/sentinel-cronjob.yaml`](integrations/sentinel-cronjob.yaml)):
loads a `SentinelState` snapshot, optionally loads + persists an open-findings
set so repeat scans dedupe against history, and prints the report as JSON.

**Advisory, never a gate**: exit `0` = no fresh findings, `1` = fresh findings
(informational — act on the JSON, do not treat as a failure), `2` = usage
error. A `CronJob` must never fail on exit `1` (see the integrations doc).

```bash
sre-harness sentinel scan --state examples/sentinel-state.json --verbose

# with persistence: a second run against the same state suppresses the repeat
sre-harness sentinel scan --state examples/sentinel-state.json \
  --open-findings /tmp/sentinel-open-findings.json
```

Without `poetry install`: `python -m sre_harness.cli sentinel scan ...` (with
`src` on `PYTHONPATH`). See
[`integrations/README.md`](integrations/README.md#sentinel-continuous-detection-stage-7-build-order-step-2)
for the full CronJob wiring, the open-findings persistence contract, and the
live observability source adapter TODO.

## The Omniscience contract

The gate reasons over an authoritative platform-state graph behind the
`PlatformGraph` port, so it is built and tested against the in-memory fake while
the real adapter is wired up in the Omniscience repo in parallel. The adapter
targets the MCP tool:

```
list_entities(kind: str, cluster: str | null, name: str | null,
              as_of: ISO-8601 | null) -> [entity]
```

## Observability / AgentOps

The harness emits OpenTelemetry spans for the gate and the eval runner so a run is
auditable end to end (plan cross-cutting row: *AgentOps — OTel GenAI spans, cost,
reasoning provenance*). The instrumentation lives behind a thin facade
(`sre_harness.observability`) and is **no-op by default**: with no OTel
`TracerProvider` configured, the API hands back a no-op tracer, every span is a
cheap side-effect-free object, and behaviour is unchanged. Nothing to run, no
collector required.

**What's traced**

| Span | Parent | Key attributes |
|---|---|---|
| `gate.evaluate` | (root) | `gate.verdict`, `gate.service`, `gate.target_cluster_count`, `gate.check_count`, `gate.analysis_tier`, `gate.recommendation_tier`, `service` |
| `gate.check` | `gate.evaluate` | `gate.check_id`, `gate.check_verdict` (one child span per check) |
| `eval.suite` | (root) | `eval.scenario_count`, `eval.passed_count`, `eval.pass_rate`, `service` |
| `eval.scenario` | `eval.suite` | `eval.scenario_id`, `eval.scenario_kind`, `eval.score`, `eval.passed` (one per scenario) |
| `triage.run` | (root) | `triage.incident_id`, `triage.service`, `triage.evidence_count`, `triage.root_cause`, `triage.confidence`, `triage.analysis_tier`, `service` |
| `triage.gather` / `triage.analyze` / `triage.draft` | `triage.run` | One child span for each bounded B1 node; the deterministic analyzer emits no LLM token/cost fields |
| `sentinel.scan` | (root) | `sentinel.detector_count`, `sentinel.finding_count`, `sentinel.suppressed_count`, `sentinel.detection_tier`, `sentinel.recommendation_tier`, `service` |
| `sentinel.detector` | `sentinel.scan` | `sentinel.detector_id`, `sentinel.detector_finding_count` (one child span per detector) |

**The attribute schema (why our own names).** The OTel GenAI semantic conventions
(`gen_ai.*`) are still *experimental* and have churned across releases. AgentOps is
a cross-cutting concern meant to outlive that churn, so the harness defines its own
**stable** attribute names under the `sre_harness.*` namespace
(`sre_harness/observability/attributes.py`) and sets those at every call site. A
small, safe subset of the token/cost scaffold is *additively* mirrored onto the
standardised GenAI names internally (e.g. `sre_harness.llm.input_tokens` →
`gen_ai.usage.input_tokens`) so an OTel-native backend still sees them — but the
unstable `gen_ai.*` strings never appear in harness code.

A token/cost scaffold (`sre_harness.llm.input_tokens` / `...output_tokens` /
`...cost_usd` / `...model`) is defined for the future read-only triage / RCA LLM
steps (plan Stage 1); no LLM runs today, so those attributes are declared but not
yet emitted.

**Enabling an exporter.** Tracing stays no-op until you wire a provider. The
convenience helper reads an endpoint from the environment:

```bash
export SRE_HARNESS_OTLP_ENDPOINT="http://localhost:4318/v1/traces"
```

```python
from sre_harness.observability import configure_tracing
configure_tracing()  # returns False (and stays no-op) if no endpoint is set
```

`configure_tracing()` installs an SDK `TracerProvider` with a batch OTLP/HTTP
exporter. It requires the optional `opentelemetry-exporter-otlp-proto-http`
package (not a declared dependency); without it, `configure_tracing()` raises a
clear error. You can also bring your own provider via the standard OTel SDK —
the facade resolves through the global API either way.

## Develop

```bash
poetry install
poetry run pytest          # or: python -m pytest
poetry run ruff check src tests
poetry run mypy
```

## Run the eval suite

```bash
python -m sre_harness.eval            # summary (pass rate + per-kind breakdown)
python -m sre_harness.eval --verbose  # also prints per-scenario verdicts
```

Exits non-zero if any scenario fails, so it can gate CI later.

## Status

- Autonomy-tier engine — done, unit-tested.
- Change-validation gate — multi-check (plan Stage 2), unit-tested against the
  fake. Three deterministic checks (`storageclass_present`, `blast_radius`,
  `namespace_present`) behind a check abstraction, aggregated `block` >
  `require_human` > `proceed`. Still advisory/deterministic, no LLM.
- Offline eval harness (Stage 0,
  [SPEC-B0](../../docs/specs/SPEC-B0-offline-eval-harness.md)) — portable baseline done and unit-tested.
  Scenario/label format,
  `run_eval` runner with an explicit scenario-specific scorer seam, **Pass@1**
  verdict scoring, and a 10-scenario seed suite
  covering all three checks (StorageClass / blast-radius / namespace) and their
  combinations across `proceed` / `block` / `require_human`. Scored now: Pass@1
  only. Stubbed extension points (typed, raise rather than fake a number):
  `Pass@k` / `trajectory` / `depth` / `signal-surfacing` — wire real scorers
  once there is a stochastic, multi-step agent target (Stage 1+).
- Read-only triage/RCA (Stage 1/B1) — bounded offline construction slice
  implemented and unit-tested: the draft SPEC-B1 contract, strict bounded v1
  JSON ingestion, a `snapshot()`-only source port with exact incident/time
  rejoin, immutable UTC incident/evidence contracts, service/time-bounded
  gather, one `analyze()`-only port, fact/inference
  separation, exact citation rejoin, confidence and honest-unknown behavior,
  T1 action-free RCA drafting, AgentOps node spans, three shared-harness
  incident replays, and fixture-ineligible threshold admission. Remaining: live read-only source adapters, approved
  model/vendor analyzer binding, curated real-incident labels and thresholds,
  an externally verified corpus/policy publication, and measured production
  usefulness. B1 is not complete or deployed.
- `OmniscienceMcpPlatformGraph` — implemented over an `McpToolClient` seam and
  unit-tested with a fake client; maps the `list_entities` response to `Entity`.
  Remaining: a concrete `McpToolClient` against a running Omniscience (real MCP
  client + workspace-scoped token) for end-to-end use.
- PR-diff / k8s-manifest parsing into `ChangeRequest` — best-effort parsers
  shipped (`change_parsers.parse_k8s_manifest` / `parse_pr_diff`), in addition
  to the structured `parse_change_request`. Stage 2 also extracts
  `required_namespaces` (k8s `metadata.namespace`) and high-blast-radius
  `actions` (high-risk k8s kinds / added diff lines) for the new checks.
- Advisory change validation (Stage 2/B2) — the deterministic core, legacy local CLI, and templates
  exist. The draft SPEC-B2 construction now adds a strict bounded v1 integration envelope/result,
  exact content revision and five-minute freshness rejoin, opaque immutable invocation/result contracts,
  distinct `0/10/20/64` exits, atomic non-symlink artifact output, and template status-preservation probes. Remaining: a
  consumer-owned producer backed by an approved live platform source and one observed immutable
  GitLab/Argo run with retained latency/catch/false-positive/override evidence. B2 is not complete.
  The closed [`SPEC-B2` traceability manifest](spec-traceability/SPEC-B2.json) binds the exact draft
  digest and `P-B2-1..9` to bounded implementation paths and existing pytest nodes; it stores no PASS
  result and grants no pipeline, deploy, or sync authority.
- Continuous detection / Sentinel (Stage 7,
  [SPEC-B7-CORE](../../docs/specs/SPEC-B7-core-sentinel-runtime-contract.md) plus
  [SPEC-B7-SAT](../../docs/specs/SPEC-B7-saturation-expiry-detector.md),
  [SPEC-B7-NES](../../docs/specs/SPEC-B7-new-error-signature-detector.md),
  [SPEC-B7](../../docs/specs/SPEC-B7-error-rate-baseline-detector.md),
  [SPEC-B7-CIR](../../docs/specs/SPEC-B7-change-induced-regression-detector.md), and
  [SPEC-B7-DRIFT](../../docs/specs/SPEC-B7-drift-detector.md))
  — unit-tested. Detector contract + five-entry
  `DEFAULT_DETECTORS` registry + dedup/specificity collapse +
  `severity × confidence` ranking (`sentinel.scan`) and a 20-scenario
  lead-time/false-positive eval. The three increments add three incident replays,
  each with two snapshots of lead, and thirteen targeted clean controls; the
  aggregate portable result is 6/6 early and 0/14 false positives. AgentOps spans
  emitted; still advisory/deterministic, no LLM, causation, or reconciliation claim.
  Remaining: human-owned deploy/window/baseline/SLO and tracked-resource/desired-state
  policies, normalization and immutable config/revision-to-workload binding,
  calibration, live observability/Omniscience adapters and deployed runtime evidence,
  plus the cheap-model novelty clustering /
  expensive-model finding draft for `new_error_signature`.
</content>
