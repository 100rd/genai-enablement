# ADR-0025: Local observation and bounded Codex analysis

- **Status:** Accepted
- **Date:** 2026-11-06
- **Deciders:** platform owner, by explicit approval of the implementation plan in the coordinating chat
- **Scope:** local Omniscience, Barbarossa and Portal only
- **Depends on:** ADR-0018, ADR-0020, ADR-0024

## Decision

Introduce `management-local-observe-v1`, a separate development profile. It selects local Reliability
reachability and Security access-boundary observations. It does not widen `management-readonly-v1`,
`management-readonly-local-v1`, or `barbarossa-ha-v1`, and does not reuse their receipts.

Barbarossa owns the observer, PostgreSQL observation/case/analysis ledger, protected read API,
separate internal analysis listener, and a host-side Go Codex runner. These are roles of one component.
Omniscience owns isolated safe workspace seeds, knowledge contracts and scoped token issuance. Portal
owns authenticated sessions, delegated read identity and views. genai-enablement owns composition,
cross-component acceptance, progress and this decision. Omnius remains not deployed.

The observer reads only the three fixed owner endpoints. Poll interval is 30 seconds, timeout 3 seconds,
two failures open a case, two successes recover it, and evidence older than 90 seconds is stale. Each
observation identifies its single shared-host vantage. Observer loss is unknown coverage, never an
invented owner failure or healthy result. No external availability or HA claim follows from these probes.

Security observations test absent and foreign identity on read routes. Mutation-negative tests run only
in an isolated disposable qualification environment. No runtime scanner, remediation or owner mutation
is admitted. Existing user data, volumes and AWS inventories are preserved.

Portal delegates its server-validated effective tenant in an Ed25519 token with issuer
`platform-portal-local`, audience `barbarossa-read`, role `read`, and a maximum 60-second lifetime.
Barbarossa verifies the pinned public key, temporal claims and allowed tenant. Invalid identity is 401;
forbidden scope is 403. A query parameter cannot supply identity. Runner credentials are separate and
permit only claim, heartbeat and assessment submission on an independently bound listener.

The host runner invokes `codex exec` with existing host authentication, a pinned analysis-only profile,
read-only sandbox, ephemeral sessions and strict output schema. No shell, MCP, apps, plugins, hooks,
web, nested agents, project instructions or user configuration may become an execution surface.
Only sanitized observation/context references enter the prompt; database/broker credentials do not.
The runtime validates result shape, evidence references and lease fencing before sealing a
non-authoritative assessment. Model output cannot change domain truth or execute a proposal.

Default model: `gpt-6-luna`. One concurrent process, six attempts per rolling hour, 120 seconds per
attempt, at most two attempts per job. Attempts are reserved durably before launch. Fingerprints exclude
timestamps; only new/material problem changes schedule analysis. Unsupported CLI constraints, login or
model failure produce a visible failed/unavailable analysis, never an unrestricted fallback.

## Qualification and rollback

Qualification requires real owner reads, two-tenant isolation, dynamic timestamps, an induced failure
through case/analysis/UI/recovery, persistence after restart, bounded/deduplicated model calls, stale
lease rejection, and no-effect negative controls. Mock tests alone do not close live acceptance.
Source builds remain explicitly non-reproducible. OCI publication, production, HA, AWS and autonomy
promotion remain separate work. Normal stop preserves volumes; rollback stops the new roles without
deleting history. No automatic reset is provided.

## Work order

SP-102 records the integration contract; SP-103 implements the knowledge boundary; SP-104 implements
the local observer/identity/analysis runtime; SP-105 integrates Portal; SP-106 independently qualifies
the assembled profile. Component task SPECs own code scope and independent acceptance.
