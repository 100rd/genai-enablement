# ADR-0023: Barbarossa uses fenced distributed work for high availability

- **Status:** Accepted
- **Date:** 2026-07-26
- **Deciders:** platform owner, Barbarossa owner, and Platform Portal owner
- **Scope:** full-Go prerequisite, distributed work, Barbarossa HA and Portal visibility
- **Depends on:** [ADR-0018](0018-pii-wall-purpose-bound-data-boundary.md),
  [ADR-0020](0020-barbarossa-continuous-management-plane.md), and
  [ADR-0022](0022-barbarossa-go-production-runtime.md)

## Context

Barbarossa runs continuous evaluation, replay, projection and reconciliation. High availability cannot
be inferred from a stateless health endpoint or a Deployment replica count: distributed workers must
survive duplicates, restarts, stale leases, broker/store failure and rescheduling while preserving one
authoritative history. The separately approved Go move must also finish across the whole implemented
Barbarossa surface rather than stop at the original Reliability-only slice.

The synchronized platform already operates NATS JetStream patterns in Omniscience, but component
ownership and durability settings must remain explicit. Sharing a broker technology does not transfer
stream, acknowledgement or work-state authority between components.

## Decision

### D1 — Full Go precedes distributed and HA releases

SP-90 publishes the complete implemented Go baseline. Runtime selection remains independent: porting a
domain/action contract never activates it. The HA chain is:

```text
SP-86 + SP-90 -> SP-87 Barbarossa functional release
SP-87 -> SP-91 distributed work
SP-91 -> SP-92 Barbarossa HA owner release
SP-88 + SP-92 -> SP-93 Portal HA observability
SP-89 + SP-92 + SP-93 -> SP-94 integrated HA qualification
```

Each package is independently assignable in its owning repository and consumes exact immutable
receipts. SP-91 is serialized after SP-87 because both legitimately change Barbarossa runtime paths;
they must not be assigned concurrently. SP-91/SP-92 do not depend on Portal availability; SP-93 does
not write Barbarossa state.

### D2 — Queue delivery and authoritative state are separate

Barbarossa initially uses owner-scoped NATS JetStream file-backed R3 streams and durable pull consumers
for horizontal distribution. Explicit ACK, bounded pending work, bounded delivery attempts, retry
backoff and quarantine/DLQ are mandatory. Omniscience application streams are not reused as Barbarossa
work streams and an R1 stream cannot qualify this profile.

Delivery is at-least-once. Barbarossa's HA PostgreSQL store transactionally owns inbox/idempotency,
work state, attempt, monotonic fencing epoch, result/receipt and outbox state. ACK occurs only after the
authoritative commit. Broker deduplication may reduce duplicates but cannot justify an end-to-end
exactly-once claim.

### D3 — Fencing, ordering and backpressure are correctness boundaries

Every work item carries identity, tenant/realm/environment, aggregate/partition key, causal sequence,
contract revision and payload digest. Every claim receives a monotonic fencing epoch; stale writes fail
compare-and-set. Causally ordered work rejects or parks unexpected sequences. Poison work is bounded
and quarantined; redrive is never automatic. Dependency loss creates typed backpressure/unreadiness and
never a fabricated success.

### D4 — Barbarossa is a multi-role measurable service

API/query and worker roles scale independently. Production-shaped qualification requires failure-domain
spread, disruption budgets, requests/limits, safe rolling updates, dependency-aware health, graceful
drain and queue-pressure autoscaling. Queue lag and oldest-work age are primary worker signals with
CPU/memory/concurrency guardrails.

Availability is accepted only against declared service/work SLOs and a quantitative capacity envelope.
Load, soak, duplicate, crash-before-commit, crash-after-commit-before-ACK, stale-worker, poison/DLQ,
broker-node loss, store failover, failure-domain loss, scale and upgrade scenarios are evidence gates.

### D5 — Portal gets detailed owner truth without infrastructure authority

Barbarossa publishes a versioned, sanitized HA projection. Platform Portal displays service/work SLOs,
queue depth/age/inflight, throughput/ACK latency, retries/redelivery/DLQ, replicas/workers, lease/fencing,
dependencies, capacity/autoscaling, rollout and exact release provenance.

Portal has no broker administration, Barbarossa database or Kubernetes mutation credential. The first
surface is read-only. Pause, retry, redrive, scale, drain, failover and rollback require a later
owner-delegated control ADR/SPEC and are explicitly forbidden here.

### D6 — `barbarossa-ha-v1` is a qualification profile, not activation authority

The new profile layers SP-91 through SP-94 over the existing management-readonly component closure.
It keeps Omnius deferred, PW0 selected, managed effects forbidden and Reliability as the only active
domain. Full Go inventory does not widen the runtime profile.

## Cross-repository invariants

- **BHA-1:** SP-91 is RED without the exact full-surface SP-90 receipt.
- **BHA-2:** SP-92 is RED without R3 broker and HA-store receipts, a capacity envelope, SLOs and
  failure evidence; replica count or health checks alone are insufficient.
- **BHA-3:** ACK-before-commit, unbounded retry, unfenced leases, automatic redrive and favorable
  dependency fallbacks are forbidden.
- **BHA-4:** Omniscience remains a severable context producer and cannot own Barbarossa work state.
- **BHA-5:** SP-93 consumes only the exact SP-92 projection and cannot inspect or control underlying
  infrastructure.
- **BHA-6:** SP-94 independently replays failure/scale/tenant/no-effect scenarios in one authorized
  non-production environment and cannot mint component receipts.
- **BHA-7:** no package authorizes infrastructure apply, production deployment or activation.

## Consequences

Barbarossa can distribute long-running work and remain independently available without sacrificing
determinism or owner authority. This adds a quorum broker, HA state store, schema/queue operations,
capacity planning, DLQ handling and recurring resilience qualification. Operational complexity is an
explicit cost of the availability objective.

## References

- NATS JetStream consumers: <https://docs.nats.io/nats-concepts/jetstream/consumers>
- NATS JetStream clustering: <https://docs.nats.io/running-a-nats-service/configuration/clustering/jetstream_clustering>
- NATS JetStream monitoring: <https://docs.nats.io/running-a-nats-service/nats_admin/monitoring/monitoring_jetstream>
- Kubernetes disruption budgets: <https://kubernetes.io/docs/concepts/workloads/pods/disruptions/>
- Kubernetes topology spread: <https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/>
- Kubernetes autoscaling: <https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/>

## Acceptance record

The platform owner confirmed on 2026-07-26 that the full Barbarossa Go move is separately approved and
that the HA/distributed-work requirements must be added to the component specifications. This decision
authorizes bounded development and non-production qualification only; it does not authorize deployment,
production mutation, credentials, redrive, domain activation or managed-system effects.
