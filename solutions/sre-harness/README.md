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
| `sre_harness.platform_graph` | `PlatformGraph` port mirroring the Omniscience MCP `list_entities` contract, an `InMemoryPlatformGraph` fake, and an `OmniscienceMcpPlatformGraph` adapter over an `McpToolClient` seam. |
| `sre_harness.change_gate` | Change-validation gate (check #1): is every required StorageClass present in the target clusters? Verdict `proceed` / `block` / `require_human`. The analysis is T1; the verdict is T2 (advisory) — the gate never executes anything. |
| `sre_harness.change_parsers` | Best-effort parsers extracting `service` / `target_cluster_ids` / `required_storageclasses` from a k8s manifest dict (`parse_k8s_manifest`) or a unified PR diff (`parse_pr_diff`). |
| `sre_harness.cli` | `sre-harness gate` command (Stage 2): loads a change request + a `PlatformGraph` fixture, runs the gate, prints the verdict JSON, and sets a CI-meaningful exit code. |

## CLI — `sre-harness gate`

Makes the gate usable in a pipeline (plan Stage 2 — **advisory**). It loads a
change request and a platform-graph JSON fixture, runs `evaluate_change`, wraps
the verdict through the autonomy-tier engine (analysis T1 / verdict T2), prints
the verdict + rationale as JSON, and exits with a CI-meaningful code:

| Exit | Verdict | Meaning |
|---|---|---|
| `0` | `proceed` | Every required StorageClass present in every target cluster. |
| `1` | `block` | A required StorageClass absent in **every** target cluster. |
| `2` | `require_human` | Gaps in **some-but-not-all** target clusters (also: usage errors). |

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

## Status

- Autonomy-tier engine — done, unit-tested.
- Change-validation gate (StorageClass check) — done, unit-tested against the fake.
- `OmniscienceMcpPlatformGraph` — implemented over an `McpToolClient` seam and
  unit-tested with a fake client; maps the `list_entities` response to `Entity`.
  Remaining: a concrete `McpToolClient` against a running Omniscience (real MCP
  client + workspace-scoped token) for end-to-end use.
- PR-diff / k8s-manifest parsing into `ChangeRequest` — best-effort parsers
  shipped (`change_parsers.parse_k8s_manifest` / `parse_pr_diff`), in addition
  to the structured `parse_change_request`.
- `sre-harness gate` CLI + GitLab CI / ArgoCD PreSync integration templates
  (Stage 2, advisory) — done, unit-tested (exit codes, parser paths, errors).
  Remaining: a `--graph-source omniscience` flag selecting the live
  `OmniscienceMcpPlatformGraph` adapter instead of a static `--graph` fixture.
</content>
