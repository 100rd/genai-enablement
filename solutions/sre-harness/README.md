# sre-harness

First slice of the **Autonomous SRE Harness** (see
[`docs/autonomous-sre-harness-plan.md`](../../docs/autonomous-sre-harness-plan.md)).

The harness is the product: agents do the ops work under hard, deterministic
gates. This package contains the safety core and the first change-validation
gate — pure, deterministic, fully unit-tested. No LLM in the loop here.

## Modules

| Module | Responsibility |
|---|---|
| `sre_harness.autonomy_tiers` | Tier model `T1 read-only → T4 autonomous`, the action-tier table, and `classify()` which **degrades down** (toward more human control) on low confidence or off-plan actions. |
| `sre_harness.platform_graph` | `PlatformGraph` port mirroring the Omniscience MCP `list_entities` contract, an `InMemoryPlatformGraph` fake, and an `OmniscienceMcpPlatformGraph` adapter over an `McpToolClient` seam. Exposes `storageclasses_in_cluster()` and `namespaces_in_cluster()`. |
| `sre_harness.change_checks` | The three deterministic checks behind the gate, each a pure `(request, graph) -> CheckResult`: `storageclass_present`, `blast_radius` (action-tier classification), `namespace_present`. `DEFAULT_CHECKS` is the registered list. |
| `sre_harness.change_gate` | Multi-check change-validation gate: runs `DEFAULT_CHECKS` and aggregates (`block` dominates → else `require_human` → else `proceed`). `GateResult` exposes the aggregate verdict, a combined rationale, per-check `check_results`, and (back-compat) the StorageClass-specific evidence. Analysis is T1; the verdict is T2 (advisory) — the gate never executes anything. |
| `sre_harness.change_parsers` | Best-effort parsers extracting `service` / `target_cluster_ids` / `required_storageclasses` and (Stage 2) `required_namespaces` + high-blast-radius `actions` from a k8s manifest dict (`parse_k8s_manifest`) or a unified PR diff (`parse_pr_diff`). |
| `sre_harness.cli` | `sre-harness gate` command (Stage 2): loads a change request + a `PlatformGraph` fixture, runs the gate, prints the verdict JSON, and sets a CI-meaningful exit code. |
| `sre_harness.eval` | Offline eval harness (plan Stage 0): frozen incident-replay labels (`Scenario` = `{id, kind, snapshot, ground_truth}`), a `run_eval(scenarios, target)` runner, **Pass@1** scoring, and a 10-scenario seed suite covering all three checks' verdict space. Pure, offline, deterministic — no LLM. Run with `python -m sre_harness.eval`. |
| `sre_harness.sentinel` | **Continuous detection / Sentinel** (plan Stage 7 — [ADR-0001](../../docs/decisions/0001-continuous-detection-sentinel.md)): the *proactive* surface to the gate's *at-change* one. A `Detector(state) -> [Finding]` contract, a `DEFAULT_DETECTORS` registry, and `run_sentinel()` which dedupes findings against the open set and ranks them by `severity × confidence`. Two deterministic seed detectors (`saturation_expiry`, `new_error_signature`), scored offline by the eval harness on **lead-time**. Detection is T1, a finding is T2 (advisory) — Sentinel never executes. Run with `python -m sre_harness.sentinel`. |
| `sre_harness.observability` | **AgentOps** (plan cross-cutting): a thin tracing facade over OpenTelemetry — `get_tracer()`, the `span(...)` context manager, the `@traced(...)` decorator, and an optional `configure_tracing(...)` for OTLP export. Defines a **stable `sre_harness.*` attribute schema** (`attributes.py`) and instruments the gate and the eval runner. **No-op by default** — zero behaviour change and near-zero cost when no OTel provider is configured. |

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

**Lead-time eval.** Detectors are scored offline by the eval harness on
**lead-time** (ADR measurement): replay a timeline of state snapshots and verify
the detector fires *before* the incident paged, with a clean-timeline
false-positive control. Run with:

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
- Offline eval harness (Stage 0) — done, unit-tested. Scenario/label format,
  `run_eval` runner, **Pass@1** verdict scoring, and a 10-scenario seed suite
  covering all three checks (StorageClass / blast-radius / namespace) and their
  combinations across `proceed` / `block` / `require_human`. Scored now: Pass@1
  only. Stubbed extension points (typed, raise rather than fake a number):
  `Pass@k` / `trajectory` / `depth` / `signal-surfacing` — wire real scorers
  once there is a stochastic, multi-step agent target (Stage 1+).
- `OmniscienceMcpPlatformGraph` — implemented over an `McpToolClient` seam and
  unit-tested with a fake client; maps the `list_entities` response to `Entity`.
  Remaining: a concrete `McpToolClient` against a running Omniscience (real MCP
  client + workspace-scoped token) for end-to-end use.
- PR-diff / k8s-manifest parsing into `ChangeRequest` — best-effort parsers
  shipped (`change_parsers.parse_k8s_manifest` / `parse_pr_diff`), in addition
  to the structured `parse_change_request`. Stage 2 also extracts
  `required_namespaces` (k8s `metadata.namespace`) and high-blast-radius
  `actions` (high-risk k8s kinds / added diff lines) for the new checks.
- `sre-harness gate` CLI + GitLab CI / ArgoCD PreSync integration templates
  (Stage 2, advisory) — done, unit-tested (exit codes, parser paths, errors).
  Remaining: a `--graph-source omniscience` flag selecting the live
  `OmniscienceMcpPlatformGraph` adapter instead of a static `--graph` fixture.
- Continuous detection / Sentinel (Stage 7, build-order step 1) — done,
  unit-tested. Detector contract + `DEFAULT_DETECTORS` registry + dedup +
  `severity × confidence` ranking (`sentinel.scan`), two deterministic detectors
  (`saturation_expiry`, `new_error_signature`), and a **lead-time** eval
  (`run_sentinel_eval` + a 4-scenario seed suite, `python -m sre_harness.sentinel`)
  scoring how early a detector surfaces a problem, with a clean-timeline
  false-positive control. AgentOps spans emitted; still advisory/deterministic,
  no LLM. Remaining (build-order steps 2–3): the `monitor`/`CronJob` runtime +
  live observability adapters (needs cluster), and the cheap-model novelty
  clustering / expensive-model finding draft for `new_error_signature`.
</content>
