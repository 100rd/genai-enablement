# ADR-0016: Safe-to-reclaim decisions use an independent signed issuer

- **Status:** Proposed
- **Date:** 2026-07-14
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `omnius`, `platform-design`)
- **Builds on:** [ADR-0006](0006-unified-loop-decision-model.md),
  [ADR-0012](0012-capability-readiness-profiles.md),
  [ADR-0013](0013-platform-owned-observer-access.md), and
  [ADR-0015](0015-independent-observer-authority-attestor.md)

## Context

Observer-access cleanup deletes live Kubernetes authorization objects. Omnius already requires the
Conductor `safe_to_reclaim(workflow_id)` predicate before a normal cleanup or an orphan reaper can
act, but a caller-provided boolean or a locally constructed "verified" value would let the cleanup
executor authorize its own destructive work.

The published draft cleanup schema has a signed `safeToReclaimDecision` shape. It does not by itself
define the authoritative producer, signature payload, trust-root separation, freshness window, or
replay semantics. Those properties must be cross-repository decisions rather than adapter choices.

## Decision

### D1 - The Conductor decision plane is the sole semantic authority

The reclaim-decision issuer evaluates the Conductor-owned `safe_to_reclaim(workflow_id)` predicate.
It may emit `decision: allowed` only when the durable WorkOrder state is terminal or authoritatively
absent, no compensator or reconciliation is pending, and the WorkOrder is not `FROZEN`.

`absent` requires an authoritative nonexistence/tombstone result from the WorkOrder store and a
globally non-reusable WorkOrder ID. A cache miss, API timeout, partition, malformed record, or raw
terminal-state list is UNKNOWN and produces no positive decision.

### D2 - Issuance and execution are separate trust boundaries

The issuer is not the cleanup controller, orphan reaper, worker, planner, observer, delivery
verifier, or observer-authority attestor. It has no Kubernetes cleanup or workload mutation
authority. The cleanup and reaper identities cannot use its signing key.

Production uses a dedicated Conductor decision-plane workload identity and a dedicated asymmetric
AWS KMS Ed25519 key. That key is distinct from observer-attestation and cleanup-evidence keys. Local
kind qualification uses a per-run process-memory Ed25519 key and is never readiness-eligible.

### D3 - The signed payload is deterministic and domain-separated

The issuer computes `decisionDigest` over RFC 8785 canonical `safeToReclaimDecision` content after
removing exactly `issuer.signature` and `decisionDigest`. It signs exactly:

```text
UTF8("darkfactory.observer-access-safe-to-reclaim/v1") || 0x00 ||
hex_to_bytes(decisionDigest)
```

The decision fixes the WorkOrder ID, terminal-or-absent state, canonical state digest, issuer
profile digest, issuer subject, signing key ID, algorithm, policy, semantic verifier, and decision
time. Evidence cannot select its own trusted key or issuer profile.

### D4 - Verification is contextual, fresh, and fail-closed

The cleanup boundary verifies the exact schema revision, signature, issuer trust profile, public
key, WorkOrder ID, state, state digest, cleanup-executor separation, canonical digest, and decision
time. A decision is valid only from `decidedAt` through `decidedAt + PT5M`; a future, stale, unknown,
ECDSA-only, malformed, self-issued, foreign, or incorrectly signed decision authorizes no mutation.

The verifier returns an opaque verified capability. Cleanup APIs do not accept a raw boolean or a
caller-constructible `verified: true` record.

### D5 - Replay is bounded and cleanup remains independently constrained

A valid decision may be replayed only during its five-minute window for the same immutable
WorkOrder ID and exact state digest. This permits idempotent retry after ambiguous cleanup effects.
It cannot be replayed across WorkOrders, state epochs, trust profiles, or signature domains.

The decision proves only reclaimability. It does not select Kubernetes paths or objects. The cleanup
executor must still use the pre-registered cleanup-plan digest, WorkOrder-derived paths, independently
attested UID/resourceVersion/canonical-digest preconditions, live re-reads, shared-object preservation,
and park-on-ambiguity behavior.

### D6 - This decision does not activate readiness

Acceptance would authorize downstream contracts and implementation, not production execution.
Local signatures and kind cleanup drills remain development evidence. Production readiness still
requires protected-path enforcement, exact EKS identity and KMS qualification, negative permission
proofs, failure injection across the API/network boundary, and human activation of an exact profile.

## Consequences

**Positive**

- Cleanup cannot authorize itself or convert missing WorkOrder state into permission.
- The same signed decision supports normal cleanup and orphan reaping without duplicating reclaim
  semantics.
- Ambiguous effects can be retried idempotently without widening the delete target.

**Costs and risks**

- The Conductor decision plane and KMS availability become dependencies; their failure parks cleanup.
- WorkOrder IDs must be globally immutable and non-reusable.
- A dedicated issuer profile, signing key, protected configuration, and production qualification are
  required in addition to the cleanup verifier profile.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Cleanup executor evaluates a raw terminal-state list | It bypasses FROZEN and pending-compensator holds. |
| Cleanup executor signs its own decision | The destructive actor can self-authorize. |
| Unsigned `safe_to_reclaim: true` | A caller or compromised adapter can forge permission. |
| Reuse the observer-attestation signing key | It collapses unrelated evidence domains and blast radius. |
| Treat a WorkOrder lookup failure as `absent` | A partition becomes permission to delete. |
| Unlimited decision lifetime | Old state authority can be replayed after trust or state changes. |

## Implementation map

| Component | Responsibility |
|---|---|
| `genai-enablement` | cross-repo issuer, signature, freshness, and replay decision |
| `platform-design` | immutable issuer/trust profiles, schema pins, invalid fixtures, and bundle indexing |
| `omnius` | transport-neutral verifier, opaque capability, cleanup/reaper join, and kind qualification |
| Conductor | sole `safe_to_reclaim` semantics and authoritative WorkOrder-state digest |
| AWS platform | dedicated workload identity, KMS key, IAM boundary, and CloudTrail audit |
| Omniscience | indexes decisions and outcomes; never issues permission or supplies a trust root |

## Required verification

- forged, wrong-key, wrong-domain, wrong-profile, foreign-WorkOrder, stale, future, and changed-state
  decisions fail before lease revocation or DELETE;
- issuer and cleanup/reaper identities are distinct and cleanup identities cannot call the KMS key;
- active, FROZEN, pending-compensator, unavailable, ambiguous, and cache-miss states emit no positive
  decision;
- an allowed decision plus wrong cleanup-plan or live object preconditions still cannot delete;
- timeout-before/after-delete replay removes only the registered WorkOrder objects and preserves the
  shared role;
- kind evidence is rejected by every production readiness profile;
- KMS, WorkOrder-store, or network failure parks cleanup without unsigned or local-key fallback.
