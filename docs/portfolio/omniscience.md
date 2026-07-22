# Omniscience portfolio view

**As of:** 2026-07-21
**Portfolio status:** `issue-350-all-slices-implemented` (verification human/cross-repo gated)

This page is the program view for Omniscience. Capability and task contracts, schemas, runbooks, and
execution evidence remain canonical in the Omniscience repository.

## Snapshot

| Field | Portfolio fact |
|---|---|
| Role | Platform knowledge hub and read-only evidence surface |
| Component owner | `@100rd` |
| Portfolio owner | `@100rd` |
| Current release | `v0.5.0` ([annotated tag evidence](https://github.com/100rd/Omniscience/tree/v0.5.0)) |
| Roadmap status | `issue-350-all-slices-implemented` |
| Current MCP contract | `v0` |
| Target MCP contract | `1.0.0` |
| Runtime tools now | `14` |
| Target v1 tools | `15` (the existing registry plus authenticated `contract_info`) |
| Bootstrap token profile | `omniscience-mcp-read-v1` |

## Open initiatives

| Initiative | State | Bounded next outcome |
|---|---|---|
| [#230 — v0.5 SRE and MCP distribution](https://github.com/100rd/Omniscience/issues/230) | `open-pm-only`; 12/13 tasks complete | Leave only PM task [#242](https://github.com/100rd/Omniscience/issues/242) open; do not close the epic yet |
| [#244 — v0.6 Agentic Data Platform](https://github.com/100rd/Omniscience/issues/244) | `pre-plan` | Run a separate competing-hypothesis discovery before planning |
| [#350 — production readiness and stable consumer contract](https://github.com/100rd/Omniscience/issues/350) | `all-slices-implemented` | All five slices merged (PRs #361–#365); each slice's verification is human/cross-repo gated |

The #350 execution slices are indexed as follows:

| SPEC/index id | Kind | Portfolio state |
|---|---|---|
| `SPEC-MCP` | capability | `implemented-component-contract` |
| `mcp-v1` | task | `implemented` |
| `consumer-severance` | task | `implemented` |
| `production-ha` | task | `implemented` |
| `backup-restore` | task | `implemented` |
| `read-scaling-priority` | task | `implemented` |

All five #350 slices are now implemented and merged to main (PRs #361–#365), and the component
`execution-index.json` records each as `implemented` (PR [#366](https://github.com/100rd/Omniscience/pull/366)).
No slice is terminal/`verified`: every one retains explicit decision-return acceptance criteria an agent
cannot self-grant — a live severance/canary drill and omnius pin (mcp-v1, AC-MCP-5); real Omnius/SRE
immutable receipts and a live severance drill (consumer-severance, AC-SEV-2/3); a disposable 3-AZ cluster
and Neo4j/Qdrant entitlements (production-ha, AC-HA-4); an isolated recovery environment and a one-shot
human approval bound to the command digest (backup-restore); and live 2+-replica measurement plus
acceptance of a shared backend (read-scaling-priority, AC-SCALE-5). Verification and the `verified` state
remain human/cross-repo gated.

## MCP v1 boundary

[ADR-0017](../decisions/0017-omniscience-mcp-v1-contract-and-severance.md) fixes contract `1.0.0`,
the 15-tool registry, content-addressed schema and registry pins, additive freshness/consistency/fallback
metadata, direct-source severance, and the exact `omniscience-mcp-read-v1` bootstrap profile.

The stable target registry is:

```text
blast_radius, contract_info, find_similar_incidents, generate_postmortem,
get_document, get_entity, get_related_entities, incident_timeline, list_entities,
list_sources, replay_context, resolve_incident, search, source_stats, suggest_runbook
```

The accepted ADR is a cross-repository decision, not implementation evidence. V1 becomes consumable
only after Omniscience publishes its human-ready component contracts, content-addressed manifest and
schemas, matching `contract_info`, contract/security/skew tests, and terminal execution evidence.

## Readiness blockers

- MCP v1 manifest, schemas, `contract_info` handshake, and the consumer pin are not yet published.
- A portable bundle/Streamable-HTTP canary verifier exists only in the dirty Omniscience worktree; no
  immutable bundle, deployed canary receipt, or consumer activation exists.
- Omnius direct-source severance and human verification drills are not yet recorded.
- Production HA needs a separate Neo4j Enterprise/Aura licensing and Qdrant topology decision.
- OAuth 2.1, passport propagation, and the policy engine remain in #244 discovery.

## Recent terminal evidence

| Task | State | Immutable delivery evidence | Verification authority |
|---|---|---|---|
| `gh-issue-355` | `implemented` | [PR #359](https://github.com/100rd/Omniscience/pull/359), merge `d050eba8ffe6d025cc0db75ebc4dfc5a60dba937` | [Omniscience task SPEC index](https://github.com/100rd/Omniscience/blob/main/docs/specs/README.md) |

The component execution index owns the exact verification command and result. This portfolio row records
the immutable delivery join and must not promote the task beyond the component's evidence-backed state.

## Canonical component links

- [Capability SPEC index](https://github.com/100rd/Omniscience/blob/main/specs/SPEC-INDEX.md)
- [Task SPEC and execution index](https://github.com/100rd/Omniscience/blob/main/docs/specs/README.md)
- [MCP contract](https://github.com/100rd/Omniscience/blob/main/docs/api/mcp.md)
- [REST contract](https://github.com/100rd/Omniscience/blob/main/docs/api/rest.md)
- [Component ADR index](https://github.com/100rd/Omniscience/blob/main/docs/decisions/README.md)
- [Runbooks](https://github.com/100rd/Omniscience/tree/main/docs/runbooks)
- [GitHub milestones](https://github.com/100rd/Omniscience/milestones)
