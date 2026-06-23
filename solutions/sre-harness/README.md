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

## The Omniscience contract

The gate reasons over an authoritative platform-state graph behind the
`PlatformGraph` port, so it is built and tested against the in-memory fake while
the real adapter is wired up in the Omniscience repo in parallel. The adapter
targets the MCP tool:

```
list_entities(kind: str, cluster: str | null, name: str | null,
              as_of: ISO-8601 | null) -> [entity]
```

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
</content>
