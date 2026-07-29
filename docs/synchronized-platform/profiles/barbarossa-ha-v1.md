# Runtime profile: `barbarossa-ha-v1`

- **Status:** accepted-for-development
- **Governing decision:** [ADR-0023](../../decisions/0023-barbarossa-full-go-distributed-ha-runtime.md)
- **Base profile:** [`management-readonly-v1`](management-readonly-v1.md)
- **Runtime owners:** `omniscience`, `barbarossa`, `platform-portal`
- **Governance owner:** `genai-enablement`
- **Deferred runtime owner:** `omnius`
- **Selected domain:** Reliability
- **Barbarossa runtime:** complete Go implementation; TypeScript is a non-deployable oracle
- **Distributed work:** Barbarossa-owned NATS JetStream R3 plus HA PostgreSQL state/fencing
- **PII Wall:** `PW0 PII-free`
- **Effect posture:** no operator, agent, Omnius, redrive, or managed-system effect path

## Purpose

This profile adds production-shaped distributed work and component high availability to the already
selected read-only synchronized-platform composition. It does not widen business/domain authority:
only Reliability is active, Omnius remains `not_deployed`, effects remain forbidden and Portal is
read-only.

The full Go SP-90 inventory contains all implemented domain packs and inert action/verification
contracts. Inventory is not selection. The exact runtime configuration must still register only the
Reliability closure inherited from `management-readonly-v1`.

## Required work-package closure

```text
management-readonly-v1 closure through SP-89

SP-86 + SP-90 -> SP-87
SP-87 -> SP-91
SP-91 -> SP-92
SP-88 + SP-92 -> SP-93
SP-89 + SP-92 + SP-93 -> SP-94
```

The machine-readable dependency graph in `portfolio/synchronized-platform.json` is authoritative when
the diagram and registry differ.

## HA release contracts

| Package | Owner | Input pins | Required output |
|---|---|---|---|
| `SP-90` | Barbarossa | complete accepted capability inventory and frozen TypeScript oracle | immutable `BarbarossaGoRuntimeBaseline` with full-surface manifest, all-capability parity, isolation, no-implicit-activation and no-Node evidence |
| `SP-91` | Barbarossa | exact SP-87 release binding SP-90, R3 JetStream and HA-store qualification fixtures | immutable `BarbarossaDistributedWorkRelease` with stream/store schemas, idempotency, fencing, ordering, retry/DLQ, severance and PW0 evidence |
| `SP-92` | Barbarossa | exact SP-87 and SP-91 receipts, capacity envelope, SLOs and failure target | immutable `BarbarossaHighAvailabilityRelease` with topology, load/soak/failover/drain/upgrade and owner-projection evidence |
| `SP-93` | Platform Portal | exact SP-88 and SP-92 receipts | immutable read-only `PortalBarbarossaHighAvailabilityRelease` with truthful owner-pinned detail and no-control evidence |
| `SP-94` | genai-enablement | exact SP-89, SP-92 and SP-93 receipts plus authorized non-production environment | content-addressed profile lock and independent HA/failure/tenant/no-effect qualification report |

## Runtime topology invariants

The release-candidate configuration MUST:

1. run only Go Barbarossa binaries from exact SP-90 provenance;
2. separate API/query and worker roles and spread at least three API replicas across declared failure
   domains;
3. keep at least two eligible workers per critical durable consumer within the declared capacity
   envelope;
4. use Barbarossa-owned file-backed R3 JetStream streams, durable pull consumers and explicit ACK;
5. use an HA owner state store for transactional inbox/idempotency, work/result/outbox state and
   monotonic fencing;
6. ACK only after authoritative commit and reject stale-worker or unexpected-sequence writes;
7. bound pending, concurrency, retries, backoff and DLQ behavior; prohibit automatic redrive;
8. define requests/limits, disruption budgets, topology spread, rolling strategy, dependency-aware
   readiness, startup/liveness and graceful drain;
9. scale workers primarily from queue lag/oldest age with CPU/memory guardrails and stable scale-down;
10. expose non-identifying service/work lifecycle, queue, worker, dependency, capacity, rollout and
    SLO/error-budget signals plus one versioned Portal projection;
11. contain no direct Portal broker/store/Kubernetes credential or distributed-work mutation route;
12. select PW0 and Reliability only, emit Omnius `not_deployed`, and keep every managed effect closed.

## Qualification matrix

| Gate | Required evidence | Failure result |
|---|---|---|
| Full Go | complete SP-90 capability manifest, compiler/module/SBOM/parity and process inventory | RED on partial capability closure, production Node/TypeScript or implicit domain selection |
| Delivery | R3 stream/consumer permissions, explicit ACK, retry/backoff/DLQ and broker quorum | RED on R1, shared owner stream, ACK-before-commit, unbounded retry or automatic redrive |
| State safety | transactional inbox/result/outbox, duplicate and monotonic fencing traces | RED on duplicate authoritative transition, lost receipt or accepted stale writer |
| Ordering | partition/sequence fixtures, concurrent consumers and out-of-order delivery | RED on causally invalid commit or global-order assumption |
| Availability | pod and failure-domain loss with external API/work observations | RED when committed reads disappear or work misses declared recovery objectives |
| Capacity | immutable load model, sustained/burst/soak results and queue-age autoscaling | RED without numeric envelope/targets or under retry/saturation instability |
| Dependencies | broker-node loss, broker outage/recovery and store failover | RED on data loss, fabricated success, unsafe readiness or unrecoverable backlog |
| Lifecycle | drain, scale-in, rolling upgrade, projection rebuild and rollback | RED on lost work, stale commit, unsafe eviction or widened authority |
| Portal | exact owner projection, freshness/skew/severance/PW0/no-control browser matrix | RED on recomputation, direct infrastructure access, unsafe display or mutation route |
| Isolation/effects | two-scope seeded PW0 plus route/config/permission/network inventory | RED on cross-scope disclosure, Omnius/action/effect reachability or favorable unknown |

## Work-package classification

The required work packages are SP-00, SP-10, SP-50, SP-60, SP-61, SP-70 through SP-81, SP-83, and
SP-86 through SP-94. SP-11, SP-20, SP-30, SP-40,
SP-62, SP-82 and SP-85 remain deferred. SP-12, SP-B0-B7, SP-51, SP-52, SP-63 and SP-84 remain
non-gating. Every registry work package is classified exactly once.

SP-73 and SP-76 through SP-80 are required only as inputs to full-Go SP-90. This does not select their
actions or domains in `barbarossa-ha-v1`.

## Environment and activation boundary

SP-91 through SP-93 may build artifacts and use disposable or explicitly authorized non-production
targets. SP-94 may inject failures only in the exact named non-production environment and authority
receipt supplied to it.

Nothing in this profile provisions production infrastructure, creates credentials, changes DNS,
deploys production, activates a domain/effect, redrives operator work or approves a rollout. A later
human deployment decision must bind an immutable qualified SP-94 receipt to an exact environment and
mutation plan.

## Handoff order

1. Complete SP-90 in Barbarossa; SP-86 may proceed independently.
2. Complete SP-87 after exact SP-90 and SP-86.
3. Run SP-91 after exact SP-87, then run SP-92 after exact SP-91.
4. Complete SP-88 and SP-89 baseline qualification; run SP-93 after exact SP-88 and SP-92.
5. Run SP-94 after exact SP-89, SP-92 and SP-93 plus a named non-production environment receipt.

Missing input returns typed RED/decision-required evidence. An agent never substitutes mocks, edits a
sibling, weakens replication, widens authority or treats partial qualification as success.
