# CI / GitOps integrations — change-validation gate (Stage 2)

These templates wire the deterministic `sre-harness gate-integration` command into a delivery
pipeline so the change-validation gate runs **before** a deploy/sync. This is
Stage 2 of [`docs/autonomous-sre-harness-plan.md`](../../../docs/autonomous-sre-harness-plan.md):
*"Advisory change-validation gate — own the white space."*

The command implements
[`SPEC-B2`](../../../docs/specs/SPEC-B2-advisory-change-validation-integration.md): it accepts one closed,
content-addressed v1 envelope containing the exact change and platform snapshot and emits one versioned,
exactly rejoined result. A future or more-than-five-minute-old platform snapshot fails before evaluation.
The committed envelope and both templates are portable fixtures, not evidence of an observed consumer
integration.

## The gate is advisory (autonomy tier T2)

The CLI never executes anything. Its *analysis* is **T1** (read-only) and the
*verdict* is **T2** (advised): the gate emits `proceed` / `block` /
`require_human` and a **controller or a human acts on it**. Both templates ship
**non-blocking** so you can roll the gate out, watch its verdicts against real
changes, and only then turn it into a hard block once it has earned trust.

| Verdict | Exit code | Meaning |
|---|---|---|
| `proceed` | `0` | Every required StorageClass is present in every target cluster. |
| `block` | `10` | A deterministic check blocks. |
| `require_human` | `20` | A deterministic check needs a human decision. |
| integration error | `64` | The envelope/result sink is invalid or unavailable; no verdict is fabricated. |

The legacy `sre-harness gate` command retains its original `0`/`1`/`2` behavior for local compatibility;
it is not the strict SPEC-B2 integration surface.

## Files

| File | Use |
|---|---|
| [`gitlab-ci.gate.yml`](gitlab-ci.gate.yml) | A GitLab CI `change-validation` stage that runs the CLI on merge requests, advisory via `allow_failure: true`. |
| [`argocd-presync-gate.yaml`](argocd-presync-gate.yaml) | An ArgoCD PreSync hook Job that runs the CLI before a sync, advisory via `\|\| true` + `hook-delete-policy: HookSucceeded`. |

## GitLab CI

Include the snippet and add the stage before your deploy:

```yaml
include:
  - local: solutions/sre-harness/integrations/gitlab-ci.gate.yml
```

The job prints the versioned verdict JSON and atomically saves it as the `gate-verdict.json`
artifact. **Advisory** because `allow_failure: true` — a `block`/`require_human`
verdict warns on the pipeline but does not stop the deploy. The command is not piped through `tee`, so
its real disposition reaches GitLab before `allow_failure` explicitly degrades it to a warning.

**Make it blocking** (once trusted): delete the `allow_failure: true` line. The
job's non-zero exit code then fails the pipeline.

## ArgoCD PreSync

Apply `argocd-presync-gate.yaml` as part of the application (or render it from
your chart). It runs as a `PreSync` hook, logs the verdict, and — because the
command ends with `|| true` and the hook is deleted on success — never aborts
the sync.

**Make it blocking** (once trusted): remove `|| true` from the container command
so it exits non-zero on `block`/`require_human`. A failed PreSync hook aborts
the sync.

The example mounts the closed fixture envelope from one ConfigMap:

```sh
kubectl create configmap sre-harness-change-advisory \
  --from-file=change-advisory-invocation.json=solutions/sre-harness/examples/change-advisory-invocation.json
```

## Run it locally

```sh
# strict fixture envelope -> require_human (exit 20), with a retained result
sre-harness gate-integration \
  --input examples/change-advisory-invocation.json \
  --result /tmp/change-advisory-result.json
echo "exit: $?"
```

The older local parser paths remain available outside the SPEC-B2 integration contract:

```sh
# best-effort from a k8s manifest (service + clusters + storageclasses extracted)
sre-harness gate \
  --change examples/statefulset.json --change-format k8s \
  --graph examples/platform-graph.json

# best-effort from a PR diff (service + clusters must be supplied)
sre-harness gate \
  --change my-diff.json --change-format pr-diff \
  --service payments --target-cluster prod-eu-1 --target-cluster prod-us-1 \
  --graph examples/platform-graph.json
```

Without `poetry install`, run the same thing as a module:
`python -m sre_harness.cli gate-integration ...` (with `src` on `PYTHONPATH`).

## Live platform-graph adapter — TODO

Both templates consume a **static closed fixture envelope** today. The adapter loads its embedded
snapshot into the in-memory `PlatformGraph`. The production path is to construct that envelope from the
exact proposed change and *live* platform state via `OmniscienceMcpPlatformGraph`
(`src/sre_harness/platform_graph.py`), which is already implemented over an
`McpToolClient` seam against the Omniscience `list_entities` MCP tool.

Remaining wiring (out of scope for this PR):

1. A concrete `McpToolClient` against a running Omniscience (real MCP client +
   workspace-scoped token).
2. A consumer-owned envelope producer that queries the approved adapter, canonicalizes the exact change
   and platform snapshot, computes both content revisions, and retains the source artifact.
3. An observed GitLab or Argo CD run bound to an immutable harness revision, with retained result,
   latency, catch, false-positive, and override evidence.

---

# Deterministic canary rollback (Stage 3 portable construction)

[`argo-rollouts-deterministic-canary.json`](argo-rollouts-deterministic-canary.json) is a Kubernetes JSON
`List` generated from
[`../examples/rollback-candidate-policy.json`](../examples/rollback-candidate-policy.json) under
[`SPEC-B3`](../../../docs/specs/SPEC-B3-deterministic-canary-rollback.md). It contains a normal Service,
a namespaced Datadog v2 AnalysisTemplate, and a basic-canary Rollout. The rollout sets an integral
candidate pod weight, pauses, and runs a finite inline analysis over the latest ReplicaSet hash. Any
breach, Datadog nil, NaN/Inf, inconclusive result, or provider error is configured to prevent promotion;
an unsuccessful analysis aborts the canary toward the stable ReplicaSet without an LLM decision.

This file is deliberately **not deployable evidence**. Its image points at `example.invalid`; its 1%
error ceiling, Datadog metric/tag names, timing, namespace, Secret reference, resources, and controller
floor are unapproved fixture candidates. No Secret or credential is included. Every resource carries
the exact policy revision plus `evidence-scope=fixture` and `human-approval-required=true` annotations.

Before any apply/sync, the consumer owner must replace and review those candidates, publish the exact
immutable policy/workload revision, pin the installed controller and CRDs, provision the least-privilege
namespaced Datadog Secret, and pass server-side admission. B3 exit additionally needs retained positive
promotion and forced-negative rollback observations, stable-traffic verification, rollback latency,
false-positive measurements, and an approved recovery/override procedure.

The repository checks reproducibility rather than applying the bundle:

```sh
PYTHONPATH=src uv run --with pytest pytest tests/test_rollback.py
```

---

# Tier-4 allowlisted remediation (Stage 4 portable construction)

[`SPEC-B4`](../../../docs/specs/SPEC-B4-tier4-allowlisted-remediation.md) deliberately has no deployable
integration manifest in this directory. Its portable core exposes explicit SSM Automation and notification
ports, while the checked
[`../examples/remediation-policy-publication.json`](../examples/remediation-policy-publication.json) is
forced to `evidenceScope: fixture` and therefore always requires T3. A consumer must separately own and
review the immutable runbooks, external policy publication, account/region binding, IAM/PassRole and target
containment, durable workflow/ledger, notification delivery, audit retention, and live drills before any
runtime adapter or deployment artifact is admitted here.

Local verification exercises fakes only and makes no AWS call:

```sh
PYTHONPATH=src uv run --with pytest pytest tests/test_remediation.py
```

---

# Tier-3 HITL remediation (Stage 5 portable construction)

[`SPEC-B5`](../../../docs/specs/SPEC-B5-tier3-hitl-remediation.md) adds no deployable webhook, AWS client,
GitLab token, or merge controller here. The checked proposal and `evidenceScope: fixture` receipt exercise
only the strict portable contracts. A future consumer-owned adapter must expose exact read bindings,
deduplicate AWS approval signals durably, keep GitLab observation read-only, and retain sanitized audit;
human identity/MFA, reviewer eligibility, runbook/MR policy, credentials, CAS/outbox recovery, and live
drills remain outside the repository fixture.

```sh
PYTHONPATH=src uv run --with pytest pytest tests/test_hitl.py
```

---

# Permanent-fix chase (Stage 6 portable construction)

[`SPEC-B6`](../../../docs/specs/SPEC-B6-permanent-fix-chase.md) adds no GitHub App, GitLab token, webhook,
factory client, branch worker, MR/PR controller, pipeline trigger, or merge/close integration here. The
checked policy and request are `evidenceScope: fixture`; they exercise only the strict portable contracts.
A future consumer-owned adapter must durably deduplicate the one allowed issue-create call, use a separate
read-only principal for issue/MR/PR observation, verify canonical factory outcomes independently, retain a
transactional audit/outbox, and expose no automatic merge, issue-close, or incident-close operation.

```sh
PYTHONPATH=src uv run --with pytest pytest tests/test_permanent_fix.py
```

---

# Sentinel continuous detection (Stage 7, build-order step 2)

Wires the deterministic `sre-harness sentinel scan` CLI into a periodic
`CronJob` so Sentinel actually runs continuously, per
[`docs/decisions/0001-continuous-detection-sentinel.md`](../../../docs/decisions/0001-continuous-detection-sentinel.md)'s
build order: *"2. Runtime: `monitor`/`CronJob` wiring + observability source
adapters (needs cluster)."*

## Sentinel is advisory (autonomy tiers T1 / T2) — never a gate

Detection is **Tier 1** (read-only); emitting a finding is **Tier 2**
(advisory). Unlike the change-validation gate, Sentinel has no "block" verdict
at all — it never executes anything and it never fails a pipeline. The CLI's
exit code is **informational**, not pass/fail:

| Exit | Meaning |
|---|---|
| `0` | No fresh findings this scan. |
| `1` | Fresh findings emitted this scan — **look at the JSON output**, do not treat this as a failure. |
| `2` | Usage error (bad args, missing/invalid input). |

**A CronJob wiring this command must never fail the Job on exit `1`** — see
the `|| true` in [`sentinel-cronjob.yaml`](sentinel-cronjob.yaml), the same
advisory pattern as the gate templates above.

[`SPEC-B7`](../../../docs/specs/SPEC-B7-error-rate-baseline-detector.md) and
[`SPEC-B7-CIR`](../../../docs/specs/SPEC-B7-change-induced-regression-detector.md), and
[`SPEC-B7-DRIFT`](../../../docs/specs/SPEC-B7-drift-detector.md) add
`error_rate_windows`, `change_regression_windows`, and `drift_observations`
fixture signals plus deterministic detectors to this existing scan boundary.
They do not activate a live metric/deploy/Omniscience query, publish a production
baseline/SLO/association/tracked-resource policy or normalization algorithm,
deploy the CronJob, prove source completeness or causation, reconcile state, or
authorize alert/remediation delivery. The checked example is portable fixture
evidence only: production admission requires separately owned source ordering/
completeness, immutable config/revision-to-workload binding, controller
convergence/deletion semantics, calibration, runtime, noise, and disable evidence.

## Files

| File | Use |
|---|---|
| [`sentinel-cronjob.yaml`](sentinel-cronjob.yaml) | A periodic `CronJob` running `sre-harness sentinel scan` against a mounted state fixture, persisting the open-findings set to a PVC so repeat scans dedupe against history. |

## Open-findings persistence (dedup across scans)

`sre-harness sentinel scan --open-findings <path>` reads that path's JSON at
the start of a scan and **overwrites** it at the end with the fresh +
suppressed union, so the next scan knows what's already open (per the ADR's
"never re-alert a known/open finding"). The path must survive across CronJob
runs — the template mounts a PVC; a shared object store/DB is future work.

**Findings auto-drop by omission, not by tracked history**: `save_open` only
ever persists what *this* scan's detectors actually produced (fresh +
suppressed) — a previously-open finding whose condition has resolved (or a
flapping metric currently under threshold) silently disappears from the next
save, with no record that it was ever "closed". To force-clear a finding a
detector still reproduces every scan, an operator edits the open-findings file
directly. A more deliberate finding-lifecycle mechanism (explicit
acknowledge/resolve, an audit trail of closures) is future work.

## Run it locally

```sh
# a hot disk sample -> one saturation_expiry finding, exit 1
sre-harness sentinel scan --state examples/sentinel-state.json --verbose
echo "exit: $?"

# with persistence: the second run against the same state suppresses the repeat (exit 0)
sre-harness sentinel scan --state examples/sentinel-state.json \
  --open-findings /tmp/sentinel-open-findings.json --verbose
sre-harness sentinel scan --state examples/sentinel-state.json \
  --open-findings /tmp/sentinel-open-findings.json --verbose
```

Without `poetry install`, run the same thing as a module:
`python -m sre_harness.cli sentinel scan ...` (with `src` on `PYTHONPATH`).

## Live observability source adapter — TODO

`--state` points at a **static JSON fixture** today. The CLI loads it via
`JsonFileStateSource` into a `SentinelState`. Detectors depend only on the
`StateSource` protocol (`src/sre_harness/sentinel/source.py`), mirroring the
gate's `PlatformGraph` seam — but unlike Omniscience's `list_entities` (already
a pinned contract), no live source's query contract (Datadog / Loki /
CloudWatch / Omniscience) is specified yet, so no live adapter class is
implemented here (that would be speculative, untestable-offline code).

Remaining wiring (out of scope for this PR, needs a cluster + a specified
source contract):

1. Pin a query contract for at least one live source (Datadog metrics/logs
   query, or an Omniscience signal, mapping to `SaturationSample` /
   `ExpiryItem` / `ErrorSignatureWindow` / `ErrorRateWindow` /
   `ChangeRegressionWindow`).
2. Implement a `StateSource` adapter against that contract, unit-tested
   against a fake client (exactly like `OmniscienceMcpPlatformGraph` over
   `McpToolClient`).
3. A CLI flag (e.g. `--state-source datadog`) selecting the live adapter
   instead of `--state <file>`. The rest of the CLI is unchanged.
