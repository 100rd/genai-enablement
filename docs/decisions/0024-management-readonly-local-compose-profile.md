# ADR-0024: Compose the Management Read-Only profile locally from owner-owned fragments

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** platform owner, Omniscience owner, Barbarossa owner, and Platform Portal owner
- **Scope:** disposable local launch, cross-repository Compose ownership, and functional smoke evidence
- **Depends on:** [ADR-0018](0018-pii-wall-purpose-bound-data-boundary.md),
  [ADR-0021](0021-management-readonly-initial-runtime-profile.md),
  [ADR-0022](0022-barbarossa-go-production-runtime.md), and
  [ADR-0023](0023-barbarossa-full-go-distributed-ha-runtime.md)

## Context

Omniscience and Platform Portal already have repository-local Compose stacks, while Barbarossa has Go
API/worker roles and deployment assets but no complete local container closure. The existing stacks
cannot be started together as the synchronized platform: service names and host ports collide, each
Compose project owns a separate network, Portal is configured for selected-owner mocks, and the current
Barbarossa image does not package the HA API and worker roles.

Local launch is valuable before a named non-production environment exists. It can prove real
owner-to-owner contracts, tenant/PW0 boundaries, startup ordering, persistence, severance, read-only
negative space and the Portal experience. A single-host Compose run cannot prove failure-domain,
quorum, Kubernetes scheduling, HPA/PDB, store failover or production availability properties.

The platform needs a local profile that is useful and reproducible without being mistaken for SP-89 or
SP-94 qualification.

## Decision

### D1 — Add `management-readonly-local-v1` as a functional-smoke profile

The local profile preserves the exact runtime membership and authority of `management-readonly-v1`:

```text
Omniscience local owner services ---- read-only ----+
                                                     +--> Platform Portal
Barbarossa local API + worker -------- read-only ----+

genai-enablement -> Compose integration, inventory and smoke receipt; no runtime truth
Omnius           -> not_deployed; no service, image, route, credential, DNS name or mock
```

Reliability remains the only selected Barbarossa domain, PW0 remains selected, managed effects remain
forbidden, and Omniscience remains optional context rather than Reliability authority. Local owner
state, Portal sessions and append-only audit remain allowed under ADR-0021.

The profile emits `qualification_class=functional-smoke-only`,
`availability_class=development-single-host`, `ha_qualified=false` and
`activation_authority=none`. No local result can satisfy or replace SP-89, SP-92 or SP-94 live evidence.

### D2 — Component owners publish independently runnable Compose fragments

Each runtime owner publishes one namespaced Compose fragment, one optional source-build override and one
machine-readable local service contract in its own repository. The fragment is independently runnable
and owns its images, commands, health/readiness paths, migrations, private networks, volumes,
configuration schema and local receipt.

`genai-enablement` publishes only the cross-component composition. It uses the Compose `include`
mechanism to assemble exact owner fragments and adds integration-only networks, configuration, smoke
fixtures and receipt generation. It does not copy migrations, health semantics or component policy.

The image mode consumes explicit immutable image digests. A separate source mode may build sibling
worktrees and records exact Git revisions plus dirty flags; dirty source mode is useful for development
but is non-reproducible and cannot emit a release or qualification PASS.

### D3 — Namespace every resource and minimize host exposure

Service, network, volume, config and secret keys carry an owner prefix. The steady baseline inventory is:

```text
omniscience-api/admin/postgres/nats/neo4j/qdrant
barbarossa-api/worker/postgres/nats/migrate
portal-frontend/backend/postgres/keycloak/migrate
```

Only browser-facing Portal, Keycloak and the narrow Omniscience owner UI are published by default, bound
to `127.0.0.1`. Owner APIs may be published on non-conflicting loopback ports only by an explicit
`diagnostics` profile. Databases, brokers, Neo4j and Qdrant have no default host ports.

Portal backend alone joins the two owner-read networks. Portal never joins an owner datastore/broker
network. Omniscience and Barbarossa support networks remain mutually isolated. Canonical integration
uses Compose service DNS and never `localhost` or `host.docker.internal` for container-to-container
traffic.

### D4 — Use a deliberately non-HA Barbarossa local substrate

The default local profile runs one file-backed Barbarossa JetStream node and one durable PostgreSQL
node. It may run multiple workers for duplicate/fencing/concurrency smoke, but it never claims R3 broker,
HA store, failure-domain or autoscaling evidence. The projection and Portal label this topology
`development-single-host`; missing HA axes stay `not_qualified`, never healthy or zero.

An HA drill remains the `barbarossa-ha-v1` path in a separately authorized Kubernetes/non-production
environment. Compose is not stretched into a misleading production orchestrator.

### D5 — Remove selected-owner mocks from the local runtime closure

Portal's local profile mounts only selected read surfaces plus Portal-owned authentication, session and
append-only audit behavior. Omniscience and Barbarossa panels consume real owner endpoints and exact
local receipts. Mock service names, mock base URLs, selected-owner fixture servers and test-injection
routes are absent from the rendered runtime model.

One-shot bootstrap and negative-test jobs may use deterministic non-PII fixtures on isolated setup
networks. They terminate before the steady-state inventory is accepted, have no browser route, and can
never be represented as an owner runtime.

### D6 — Make startup, secrets, persistence and reset behavior explicit

Every long-running service has a dependency-aware health check. Migrations and bootstrap jobs are
one-shot dependencies with `service_completed_successfully`; consumers wait for
`service_healthy`. The supported launch path uses `docker compose up --wait` and has a bounded timeout.

Committed files contain no secret value. A checked-in `.env.example` documents every variable, and a
local generator creates high-entropy disposable values without overwriting an existing `.env` or
printing secrets. All persistent stores use owner-namespaced volumes. Normal `down` preserves data;
volume deletion is an explicit, confirmed reset command and is never part of ordinary stop/rollback.

### D7 — Qualify observable behavior, not container existence

The local smoke receipt binds the profile/ADR revisions, exact owner receipt and image/source identities,
the fully rendered redacted Compose configuration digest, service/network/volume inventory, reference
host envelope and probe evidence. Acceptance covers:

- bounded cold/warm start and every selected service becoming healthy;
- exact real-owner Portal reads and owner-published provenance;
- two-tenant containment plus seeded PII/active-content rejection without sink residue or echo;
- Omniscience and Barbarossa severance/recovery independently, with unrelated panels retained;
- restart/persistence and owner projection convergence;
- absent Omnius, mocks, action/effect routes and write-capable owner credentials; and
- normal stop/restart plus explicit destructive-reset separation.

Container count, `docker compose config`, or all-green health checks alone are insufficient.

### D8 — Deliver through four independently assignable work packages

```text
SP-86 -> SP-95 Omniscience local owner fragment -------+
                                                       |
SP-90/SP-91/SP-92 -> SP-96 Barbarossa local runtime ---+--> SP-97 Portal real-owner local wiring
SP-88/SP-93 -------------------------------------------+             |
                                                                    v
                                                        SP-98 integrated local qualification
```

SP-95 and SP-96 may run concurrently. SP-97 starts only from their immutable local service contracts
and the exact Portal owner-read releases. SP-98 consumes all three owner receipts and cannot repair or
mint a component receipt.

## Cross-repository invariants

- **MLC-1:** local membership equals `management-readonly-v1`; Omnius and unselected domains are absent.
- **MLC-2:** selected-owner mocks and mock URLs are absent from the rendered steady-state model.
- **MLC-3:** every owner fragment is independently runnable and owned by exactly one repository.
- **MLC-4:** parent composition never copies component migrations, policy or health semantics.
- **MLC-5:** Portal has read-network access only and no owner datastore, broker or mutation credential.
- **MLC-6:** local R1/single-store topology is visibly non-HA and cannot satisfy SP-92/SP-94.
- **MLC-7:** PW0 and tenant checks precede durable, model, UI, log, telemetry, archive and backup sinks.
- **MLC-8:** all host bindings are loopback, configurable and collision-free; support stores are private.
- **MLC-9:** dirty source mode and mutable image tags cannot produce reproducible PASS evidence.
- **MLC-10:** normal stop preserves volumes; reset is separate, explicit and destructive.
- **MLC-11:** a local receipt grants no production, infrastructure, action, effect or profile activation authority.

## Consequences

The platform gains a one-command, real-owner development loop while preserving repository ownership and
the staged release model. Agents can implement and verify each component locally before the integrated
SP-98 handoff. The cost is a larger laptop stack, explicit namespacing, local configuration contracts
and a second non-HA topology that must remain visibly distinct from production-shaped qualification.

## References

- Docker Compose include: <https://docs.docker.com/reference/compose-file/include/>
- Docker Compose startup order and health conditions:
  <https://docs.docker.com/compose/how-tos/startup-order/>
- Docker Compose file merge and override rules:
  <https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/>
- Docker Compose profiles: <https://docs.docker.com/compose/how-tos/profiles/>

## Acceptance record

The platform owner requested on 2026-07-29 that local-launch requirements be formed under the standard
cross-repository ADR/SPEC model. This decision authorizes SP-95 through SP-98 development and disposable
local qualification only. It authorizes no production deployment, infrastructure mutation, external
credential, personal data, provider/model call, managed-system effect or HA claim.
