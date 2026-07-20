# ADR-0017: Omniscience MCP v1 is pinned, freshness-aware, and severable

- **Status:** Accepted
- **Accepted by:** platform owner through the explicit implementation instruction on 2026-07-15
- **Date:** 2026-07-15
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `Omniscience`, `omnius`, and every
  Omniscience MCP consumer)
- **Builds on:** [ADR-0007](0007-platform-portal-federated-surface.md),
  [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0010](0010-goal-oriented-organizational-dark-factory.md), and
  [ADR-0012](0012-capability-readiness-profiles.md)
- **Contract version:** `1.0.0`
- **Target tool registry count:** `15`
- **Bootstrap token profile:** `omniscience-mcp-read-v1`

## Context

Omniscience is a severable knowledge dependency for omnius, the SRE harness, and other platform
consumers. Its current MCP documentation still calls the wire contract v0, allows breaking changes,
and does not publish a content-addressed schema/tool registry that a consumer can pin. Current
responses also expose freshness and projection health inconsistently. A syntactically successful
response can therefore be stale, lack source lineage, or come from divergent projections without a
consumer receiving one portable signal that direct-source fallback is required.

Omnius already fails closed when the contract, token, or workspace boundary is not independently
verified. It cannot activate its knowledge-plane integration until the producer publishes a stable
contract and the platform fixes the bootstrap token profile. Copying Omniscience's component schemas
or runbooks into this repository would create a second authority and make the skew worse.

This ADR fixes the cross-repository boundary. Omniscience remains the authority for the capability
SPEC, task SPEC, schemas, tool implementation, API documentation, and operational evidence.

## Decision

### D1 - Publish one content-addressed MCP v1 contract

Omniscience publishes MCP contract `1.0.0` as an immutable manifest. The manifest contains:

- the exact Omniscience Git commit;
- the canonical SHA-256 digest of every committed input/output schema;
- the complete, sorted tool registry and its canonical SHA-256 digest;
- supported authentication, freshness, consistency, and fallback capabilities; and
- the token-profile id required for the consumer class.

Canonical JSON uses UTF-8, sorted object keys, no insignificant whitespace, and a terminal newline
before hashing. The manifest itself is content-addressed. A schema addition or compatible optional
field follows semver; a breaking wire change, removal, rename, or changed meaning requires a new major
contract version. Updating a branch or mutable documentation page never updates an already published
contract.

The v1 registry contains the existing fourteen runtime tools plus `contract_info`, for fifteen tools
in total:

```text
blast_radius, contract_info, find_similar_incidents, generate_postmortem,
get_document, get_entity, get_related_entities, incident_timeline, list_entities,
list_sources, replay_context, resolve_incident, search, source_stats, suggest_runbook
```

Omniscience's component-owned manifest and schemas are authoritative. The portfolio registry records
only the selected version, tool count, readiness state, and canonical links.

### D2 - Make the contract self-describing through an authenticated tool

MCP v1 adds `contract_info`. It requires a valid authenticated token, is callable by the
`omniscience-mcp-read-v1` profile, and returns at least:

- contract version and exact Git commit;
- manifest digest;
- per-schema digests and the aggregate schema-set digest;
- complete tool-registry digest;
- token-profile id; and
- supported auth, freshness, consistency, and fallback capabilities.

A consumer compares this response with its pinned manifest before treating Omniscience as usable.
Missing fields, an unavailable handshake, an unknown capability, or any version/commit/schema/registry
digest mismatch requires direct-source fallback. A consumer must not negotiate down to v0 silently.

### D3 - Add one metadata envelope without renaming successful payloads

Existing successful top-level payload fields retain their v0 names and meanings. V1 adds or extends a
top-level `meta` object on every successful response:

```json
{
  "meta": {
    "contract": {
      "version": "1.0.0",
      "commit": "<git-sha>",
      "schema_sha256": "<sha256>"
    },
    "workspace_id": "<token-derived-uuid>",
    "generated_at": "<utc>",
    "effective_as_of": "<utc>",
    "freshness": {
      "status": "fresh|stale|unknown|degraded",
      "evaluated_at": "<utc>",
      "oldest_source_age_seconds": 0,
      "stale_source_ids": []
    },
    "consistency": {
      "status": "converged|degraded|unknown",
      "degraded_subsystems": [],
      "projection_lag_versions": 0
    },
    "fallback": {
      "required": false,
      "reason": null
    }
  }
}
```

`workspace_id` is derived from the authenticated server principal, never request input.
`generated_at` is response production time. `effective_as_of` is the actual temporal boundary used,
including an explicit caller `as_of` when supplied. Timestamps are UTC RFC 3339 values.

The `schema_sha256` in a response identifies that tool's exact output schema. `contract_info` also
returns the aggregate schema-set digest and per-schema map so the consumer can prove the complete pin.

### D4 - Evaluate freshness only over evidence used by the answer

Freshness is computed from the source lineage actually used to form the returned answer. Unrelated
workspace sources do not make an answer stale. `oldest_source_age_seconds` is the maximum evaluated age
among used sources, and `stale_source_ids` names only used sources that violate their freshness bound.

When the implementation cannot determine complete used-source lineage, it returns `unknown`; it must
not infer `fresh`. A never-synced source is also `unknown` unless a more specific component contract
defines it as degraded. A mixed-source answer is stale when any used source is stale. An explicit
historical `as_of` is assessed against the sources/evidence selected for that boundary and is never
presented as current merely because the request was intentional.

`consistency` describes agreement between the authoritative Postgres ledger and the Neo4j/Qdrant
projections actually used. Projection distance is a version delta named `projection_lag_versions`, not
seconds. The legacy `staleness_seconds` field may remain temporarily for byte-compatible consumers but
is deprecated and cannot substitute for v1 consistency metadata.

### D5 - Make degradation and severance machine-actionable

`fallback.required` is true when any of the following can affect the answer:

- a used source is stale;
- used-source lineage is missing or incomplete;
- a required store is divergent, unavailable, or behind the authoritative ledger;
- freshness or consistency is degraded or unknown in a way that prevents the consumer's use; or
- the pinned contract handshake is missing or mismatched.

The reason is a stable machine-readable code defined in the component schema. Consumer policy may be
stricter and fall back for every `stale`, `unknown`, or `degraded` result. It may never override
`fallback.required=true` based on an LLM judgment.

Severance means that a consumer switches to its direct authoritative sources and continues already
materialized work when Omniscience is unavailable or unsuitable. Omniscience output is context and
evidence, never the sole authorization oracle for a merge, infrastructure mutation, incident action,
or terminal WorkOrder decision.

### D6 - Fix the workspace-bound bootstrap token profile

The v1 bootstrap consumer profile is exactly `omniscience-mcp-read-v1`:

- issuer: the human-administered Omniscience admin token API;
- tenant boundary: one mandatory server-bound `workspace_id` carried by the token;
- scope set: exactly `search` and no additional scope;
- expiry: mandatory and no more than 30 days after issue;
- rotation: replacement tokens overlap their predecessor for at most 24 hours;
- audit: create, rotate, and revoke events are written to the Omniscience audit trail; and
- consumer clamp: omnius rejects legacy tokens, missing workspace/expiry, a lifetime over 30 days,
  and tokens containing any extra scope, including read/admin scopes.

The overlap permits controlled rotation; it does not extend either token's own expiry. Revocation
terminates acceptance independently of the overlap. `contract_info` and all tools admitted to this
consumer use the token-derived workspace and preserve cross-workspace non-disclosure.

This opaque-token profile is a bounded bootstrap decision. OAuth 2.1, passport propagation, and a
general policy engine remain separate discovery work and do not block v1.

### D7 - Keep ownership and execution evidence in their authoritative repositories

`genai-enablement` owns this ADR, the portfolio roadmap, dependency/readiness blockers, glossary, and
links. Omniscience owns `SPEC-MCP`, the Full-mode v1 task SPEC, schemas, manifest, API docs, contract
tests, runbooks, and terminal execution index. GitHub issues are mutable intake and progress views, not
executable contracts.

The Omniscience v0 documentation is marked superseded when v1 is published. V1 becomes the stable
public contract only after the component-owned task SPEC is human-ready, implementation and skew tests
pass, and the execution index records immutable evidence. This accepted ADR does not itself activate a
consumer or certify the implementation.

### D8 - Roll out through a pinned canary and a severance drill

Delivery order is:

1. publish the component capability and human-ready task contracts;
2. publish schemas, manifest, `contract_info`, metadata, and token enforcement in a canary;
3. verify runtime registry, schemas, manifest, docs, and handshake are byte-consistent;
4. pin the exact manifest in omnius;
5. exercise stale, unknown, degraded, digest-mismatch, cross-workspace, rotation, and revoke paths;
6. run a live severance drill proving direct-source fallback and continued materialized work; and
7. record human verification evidence before moving the task SPEC to a terminal state.

Contract mismatch or missing evidence keeps the integration inactive and selects fallback. It does not
permit a best-effort v0 call.

## Deferred work

This decision does not implement or approve:

- production HA, EKS topology, PDBs, autoscaling, or priority classes;
- Neo4j Enterprise/Aura licensing or Qdrant distributed topology;
- backup/restore infrastructure or destructive restore drills;
- a shared admission/rate-limit backend; or
- OAuth 2.1, passport propagation, or the v0.6 policy engine.

Those are separately reviewable task SPECs under the Omniscience production-readiness initiative.

## Consequences

- Consumers get a deterministic compatibility and freshness boundary rather than interpreting ad hoc
  payload fields.
- Workspace identity and least privilege are enforced at both producer and consumer edges.
- Omniscience can degrade without becoming a platform-wide single point of correctness or progress.
- Every successful response grows by a metadata envelope, and the producer must maintain lineage and
  projection-health instrumentation for every tool.
- Supporting a stable public v1 contract raises the cost of breaking changes; new major versions and a
  deliberate consumer migration become mandatory.

## Required conformance evidence

- every v1 tool preserves legacy top-level successful payload fields and validates the v1 `meta`;
- fresh, stale, never-synced, mixed-source, missing-lineage, projection-lag, and explicit-`as_of`
  scenarios produce the required states and fallback decisions;
- workspace is token-derived and foreign/nonexistent resources are non-disclosing;
- legacy/extra-scope/non-expiring/overlong/revoked tokens fail closed and the 24-hour rotation overlap
  is bounded;
- runtime registry, committed schemas, manifest digests, docs, and `contract_info` agree; and
- omnius accepts the exact pin and demonstrably switches to direct sources for every unusable contract
  or freshness state.
