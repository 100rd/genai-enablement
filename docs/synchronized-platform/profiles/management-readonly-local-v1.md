# Runtime profile: `management-readonly-local-v1`

- **Status:** accepted-for-local-development
- **Governing ADR:** [ADR-0024](../../decisions/0024-management-readonly-local-compose-profile.md)
- **Base runtime membership:** [`management-readonly-v1`](management-readonly-v1.md)
- **Orchestrator:** Docker Compose `2.24.4+`
- **Qualification class:** functional smoke only
- **Activation authority:** none

## Purpose

Provide a disposable, laptop-runnable realization of the first synchronized-platform profile using
real Omniscience, Barbarossa and Platform Portal owner services. It exists to shorten integration
feedback and produce source-bound local evidence. It is not a deployment environment, HA proof or
production-readiness gate.

## Exact selection

| Axis | Selected value |
|---|---|
| Runtime owners | `omniscience`, `barbarossa`, `platform-portal` |
| Governance owner | `genai-enablement` (composition/receipt only) |
| Deferred owner | `omnius` as `not_deployed` |
| Barbarossa domain | `reliability` only |
| PII profile | `PW0` |
| Managed effects | forbidden |
| Barbarossa runtime | Go only |
| Omniscience embeddings | local/in-process; no provider call |
| Barbarossa work transport | owner-local NATS JetStream R1 |
| Barbarossa authoritative store | owner-local single PostgreSQL |
| Availability class | `development-single-host` |
| HA qualification | false |
| Portal selected-owner data | real owner endpoints only; no mocks |

## Owner fragments and handoff contracts

| Package | Owner | Required input | Output |
|---|---|---|---|
| `SP-95` | Omniscience | exact SP-86 release | `OmniscienceLocalRuntimeReceipt` plus namespaced image/source Compose fragments |
| `SP-96` | Barbarossa | exact SP-90/SP-91/SP-92 artifacts | `BarbarossaLocalRuntimeReceipt` plus API/worker images and local R1/single-store fragment |
| `SP-97` | Platform Portal | exact SP-88/SP-93 and SP-95/SP-96 contracts | `PortalLocalRuntimeReceipt` with real-owner reads and selected-owner mocks absent |
| `SP-98` | genai-enablement | exact SP-95/SP-96/SP-97 receipts | `SynchronizedPlatformLocalLaunchReceipt` and integrated smoke report |

Dependency order is `SP-95 || SP-96 -> SP-97 -> SP-98`. No task writes a sibling repository or
substitutes a missing receipt.

## Steady-state service inventory

```text
omniscience-api
omniscience-admin
omniscience-postgres
omniscience-nats
omniscience-neo4j
omniscience-qdrant
barbarossa-api
barbarossa-worker
barbarossa-postgres
barbarossa-nats
portal-frontend
portal-backend
portal-postgres
portal-keycloak
```

`omniscience-migrate`, `barbarossa-migrate`, `portal-migrate`, bootstrap and smoke-probe jobs may exist
only as bounded one-shot services. A completed one-shot is not a healthy runtime owner.

Service/resource keys are owner-prefixed. No `mock-*`, `omnius-*`, generic `app`, generic `postgres` or
shared broker/store resource may appear in the rendered model.

## Network contract

```text
host browser -> 127.0.0.1:3000 portal-frontend
host browser -> 127.0.0.1:8081 portal-keycloak
host browser -> 127.0.0.1:3001 omniscience-admin

portal-frontend -> portal-backend
portal-backend  -> omniscience-api (read only)
portal-backend  -> barbarossa-api  (read only)

omniscience-api -> omniscience private stores/broker
barbarossa-api/worker -> barbarossa private store/broker
```

Support services have no default host binding. Diagnostic API bindings are optional, loopback-only and
collision-free. Portal does not join either owner-private network; an owner never joins its sibling's
private network.

## Launch modes

### Image mode

Consumes exact OCI digests published by SP-95/SP-96/SP-97. Mutable tags and `latest` are rejected. This
is the only mode eligible for `reproducible=true` in the local receipt.

### Source mode

Includes owner-published source-build overrides resolved relative to each owner repository. The receipt
records every Git commit and dirty flag. Dirty worktrees are allowed for developer feedback but force
`reproducible=false` and `qualification_status=development-only`.

Both modes use the same service, network, health, identity, PII, no-write and smoke contracts.

## Reference host envelope

The implementation must publish measured results for macOS Docker Desktop and Linux Docker Engine on
`amd64` and `arm64`. The minimum image-mode acceptance target is at least 4 vCPU, 8 GB memory reported
available to Docker and 25 GB free disk; 12 GiB memory is the recommended source-build envelope. Source
builds must be schedulable sequentially at the minimum target rather than compiling every owner image in
parallel. Warm start from existing images/volumes must reach all health gates within 5 minutes; cold
pull/build/model-cache population has a 15-minute bound and must distinguish network download time from
service readiness.

An implementation may publish a smaller measured envelope, but cannot silently require a larger one.
The rendered application declares per-service memory limits, and the integrated receipt records peak
and steady aggregate use. Resource exhaustion is typed `host_capacity_insufficient`, never owner
unavailable or healthy.

## Required functional-smoke matrix

| Gate | Required observation |
|---|---|
| Render | `docker compose config` passes; exact service/network/volume inventory contains no mock/Omnius/collision |
| Start | migrations/bootstrap complete once; every steady service reaches dependency-aware health within the bound |
| Identity | Portal login issues one tenant/workspace-bound local session; owner reads use least-privilege read credentials |
| Real owners | Portal renders exact Omniscience and Barbarossa owner revisions, freshness and local availability class |
| Tenant | tenant A positive and tenant B negative reads show no field donation, timing disclosure or cache bleed |
| PW0 | seeded PII, reversible tokens and active content reach no store, projection, UI, log, trace, metric, archive or backup |
| No effect | Omnius, action/control routes, owner-write credentials and managed-state changes remain absent |
| Severance | stopping either owner makes only its panels typed unavailable/stale; recovery restores fresh truth |
| Persistence | owner state survives normal restart and projections converge without duplicate authoritative transitions |
| Shutdown | normal down preserves volumes; reset requires a separate explicit destructive command |

## Receipt

`SynchronizedPlatformLocalLaunchReceipt` contains at least:

```text
profile_id/revision/digest; base_profile_revision; compose_version;
mode/reproducible; owner receipt and image/git/configuration digests;
rendered_compose_digest; service/network/volume/host_binding inventory digests;
reference_host/resource/startup measurements; tenant/pw0/no_effect evidence refs;
real_owner/severance/restart/persistence evidence refs;
availability_class=development-single-host; ha_qualified=false;
activation_authority=none; reset_performed=false
```

## Negative space

The profile contains no Omnius runtime/mock, shared owner database/broker, external model/provider,
production secret, public datastore port, Portal owner-write credential, queue administration, redrive,
scale/failover/rollback control, infrastructure apply, DNS mutation, HA claim or production activation.
