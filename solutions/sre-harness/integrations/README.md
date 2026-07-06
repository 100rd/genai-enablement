# CI / GitOps integrations — change-validation gate (Stage 2)

These templates wire the deterministic `sre-harness gate` CLI into a delivery
pipeline so the change-validation gate runs **before** a deploy/sync. This is
Stage 2 of [`docs/autonomous-sre-harness-plan.md`](../../../docs/autonomous-sre-harness-plan.md):
*"Advisory change-validation gate — own the white space."*

## The gate is advisory (autonomy tier T2)

The CLI never executes anything. Its *analysis* is **T1** (read-only) and the
*verdict* is **T2** (advised): the gate emits `proceed` / `block` /
`require_human` and a **controller or a human acts on it**. Both templates ship
**non-blocking** so you can roll the gate out, watch its verdicts against real
changes, and only then turn it into a hard block once it has earned trust.

| Verdict | Exit code | Meaning |
|---|---|---|
| `proceed` | `0` | Every required StorageClass is present in every target cluster. |
| `block` | `1` | A required StorageClass is absent in **every** target cluster. |
| `require_human` | `2` | Gaps in **some-but-not-all** target clusters — needs a human call. |

A usage error (bad args, missing/invalid input) also exits `2` and writes to
stderr.

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

The job prints the verdict JSON and saves it as the `gate-verdict.json`
artifact. **Advisory** because `allow_failure: true` — a `block`/`require_human`
verdict warns on the pipeline but does not stop the deploy.

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

The example mounts the change manifest and the graph fixture from ConfigMaps:

```sh
kubectl create configmap sre-harness-graph \
  --from-file=platform-graph.json=solutions/sre-harness/examples/platform-graph.json
kubectl create configmap sre-harness-change \
  --from-file=manifest.json=solutions/sre-harness/examples/statefulset.json
```

## Run it locally

```sh
# structured JSON change request -> require_human (exit 2) against the example graph
sre-harness gate \
  --change examples/change-request.json \
  --graph examples/platform-graph.json
echo "exit: $?"

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
`python -m sre_harness.cli gate ...` (with `src` on `PYTHONPATH`).

## Live platform-graph adapter — TODO

Both templates point `--graph` at a **static JSON fixture** today. The CLI loads
it into the in-memory `PlatformGraph`. The production path is to feed the gate
the *live* platform state via `OmniscienceMcpPlatformGraph`
(`src/sre_harness/platform_graph.py`), which is already implemented over an
`McpToolClient` seam against the Omniscience `list_entities` MCP tool.

Remaining wiring (out of scope for this PR):

1. A concrete `McpToolClient` against a running Omniscience (real MCP client +
   workspace-scoped token).
2. A CLI flag (e.g. `--graph-source omniscience`) selecting the live adapter
   instead of `--graph <file>`, constructing `OmniscienceMcpPlatformGraph` in
   `cli._load_graph`. The rest of the CLI is unchanged — the gate already
   depends only on the `PlatformGraph` port.

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
   `ExpiryItem` / `ErrorSignatureWindow`).
2. Implement a `StateSource` adapter against that contract, unit-tested
   against a fake client (exactly like `OmniscienceMcpPlatformGraph` over
   `McpToolClient`).
3. A CLI flag (e.g. `--state-source datadog`) selecting the live adapter
   instead of `--state <file>`. The rest of the CLI is unchanged.
