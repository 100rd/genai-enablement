# Runtime profile: `management-readonly-v1`

- **Status:** accepted-for-development
- **Governing decision:** [ADR-0021](../../decisions/0021-management-readonly-initial-runtime-profile.md)
- **Runtime decision:** [ADR-0022](../../decisions/0022-barbarossa-go-production-runtime.md)
- **Runtime owners:** `omniscience`, `barbarossa`, `platform-portal`
- **Governance owner:** `genai-enablement`
- **Deferred runtime owner:** `omnius`
- **Selected domain:** Reliability
- **Barbarossa runtime:** complete implemented Go capability surface; TypeScript is a non-deployable conformance oracle
- **PII Wall:** `PW0 PII-free`
- **Effect posture:** no operator, agent, Omnius, or managed-system effect path

## Purpose

This is the exact first deployment and qualification profile for the synchronized platform. It is a
selection over the target architecture, not a replacement architecture. An agent implements only its
owner-local task; this document fixes the cross-repository joins and negative space.

## Required work-package closure

```text
SP-00 -> SP-10, SP-50, SP-60, SP-70
SP-60 -> SP-61
SP-70 -> SP-81
SP-60 + SP-70 -> SP-71
SP-71 -> SP-72, SP-74, SP-75
SP-72 -> SP-73
SP-71 + SP-73 -> SP-76, SP-77, SP-78
SP-71 + SP-73 + SP-83 -> SP-79
SP-71 + SP-72 + SP-73 -> SP-80
SP-72 + SP-81 -> SP-83
SP-71 through SP-80 registry implementation inputs + SP-83 -> SP-90 full Go
SP-10 + SP-61 + SP-81 -> SP-86
SP-90 + SP-86 -> SP-87
SP-50 + SP-86 + SP-87 -> SP-88
SP-86 + SP-87 + SP-88 -> SP-89
```

The machine-readable dependency graph in `portfolio/synchronized-platform.json` is authoritative when
the diagram and registry differ.

## Component release contracts

| Package | Owner | Input pins | Required output |
|---|---|---|---|
| `SP-90` | Barbarossa | SP-71 through SP-80 implemented capability inputs, SP-83 context adapter, accepted ADR-0022 | immutable `BarbarossaGoRuntimeBaseline` with complete capability parity, isolation, no-implicit-activation, compiler/module/SBOM, durability, no-Node and rollback evidence |
| `SP-86` | Omniscience | SP-10 contract, SP-60 policy, SP-61 PW0, SP-81 context | immutable `OmniscienceManagementReadOnlyRelease` with Git/image/chart/schema/policy digests and producer evidence |
| `SP-87` | Barbarossa | exact SP-90 Go baseline and SP-86 release | immutable `BarbarossaManagementReadOnlyRelease` with Go provenance, durable-runtime, Reliability, severance, no-effect and rollback evidence |
| `SP-88` | Platform Portal | exact SP-86 and SP-87 releases plus SP-50 identity/shell | immutable `PortalManagementReadOnlyRelease` with live-read, tenant/PII, owner-severance, Omnius-not-deployed and no-write evidence |
| `SP-89` | genai-enablement | exact SP-86/87/88 receipts, the SP-90 baseline receipt transitively bound by SP-87, and one authorized non-production environment receipt | content-addressed profile lock and independent integrated qualification report |

## Selected and deferred behavior

| Surface | Selected behavior | Forbidden or deferred behavior |
|---|---|---|
| Omniscience | MCP/management-context reads, source evidence, PW0 admission and lifecycle receipts | management verdicts, owner actions, raw-PII profile, mandatory dependency for Reliability |
| Barbarossa | Go production runtime, durable kernel, federation state, Reliability evaluation/cases, optional context, read projection | Node.js/TypeScript production execution, SP-73 action submission, Omnius adapter, managed effects, progressive autonomy, non-Reliability packs |
| Platform Portal | registry/profile view, Omniscience detail/Privacy panel, Barbarossa Reliability CMC, typed severance, Portal-owned session/audit | owner/component/management/privacy mutation routes, generic owner commands, Omnius mock/live adapter, recomputation |
| Omnius | target-architecture metadata and `not_deployed` explanation only | runtime workload, credential, network dependency, privacy/action receipt, readiness contribution |

Global package status is retained. SP-11, SP-20, SP-30, SP-40, SP-62, SP-82 and SP-85 are explicitly
deferred. SP-12, SP-B0-B7, SP-51, SP-52, SP-63, SP-84 and SP-91 through SP-94 are
`non_gating_work_packages`: their historical/full-architecture construction or conformance may remain
useful, but none can close or widen this profile. The registry requires every package to be classified
as required, deferred or non-gating.

SP-73 and SP-76 through SP-80 are full-Go migration inputs through SP-90. They are not selected runtime
releases and grant no action or domain activation; their presence in required closure proves only that
the approved language move is complete.

## Configuration invariants

The release-candidate configuration MUST:

1. select `management-readonly-v1` by immutable id and revision;
2. allow network traffic only among the selected runtime owners, declared owner-local support services,
   and explicit read-only managed-system sources;
3. contain no Omnius endpoint, credential, service discovery, retry queue or fallback mock;
4. select only the Reliability domain pack;
5. pin exact SP-60 policy, SP-10/SP-81 producer, and all component release digests;
6. pin the SP-90 Go compiler/module/SBOM/parity receipt and contain no Node.js runtime, package manager,
   transpiler, JavaScript sidecar or TypeScript fallback in the Barbarossa artifact;
7. disable every Portal owner/component/management/privacy mutation route and every Barbarossa
   owner-executor adapter;
8. expose owner-local health/readiness and non-identifying metrics without treating them as domain truth;
9. emit `not_deployed` for Omnius and `not_selected` for other Barbarossa domain packs; and
10. fail closed when a required pin, identity, PW0 receipt, source, clock or integrity check is absent.

## Integrated qualification matrix

| Gate | Required evidence | Failure result |
|---|---|---|
| Membership | runtime inventory, network/DNS/config scan, process/workload inventory | RED if Omnius or an unselected adapter is reachable |
| Contract pin | exact registry, producer, consumer, schema and configuration digests | RED on mutable/latest, missing, dirty or incompatible input |
| Barbarossa runtime | SP-90 compiler/module/SBOM/parity receipt plus image/process/filesystem inventory | RED on missing Go pin or any production Node.js/TypeScript execution path |
| Tenant isolation | two-tenant positive/negative API and UI matrix with timing/non-disclosure checks | RED on cross-scope list/read/inference |
| PW0 | seeded PII and active content at ingest, evidence, context, projection, UI, logs, telemetry and export | RED on persistence, echo, model/provider propagation or favorable fallback |
| Reliability | deterministic replay plus one bounded authorized environment observation window | RED on nondeterminism, missing SLO/source authority or false available/all-clear |
| Severance | remove Omniscience, Barbarossa and Portal independently; induce stale/skew/source loss | RED when unrelated state is hidden or a missing source becomes favorable |
| No effect | route/config/dependency/network audit plus negative POST/permit/action probes | RED on any Omnius/action/effect reachability |
| Durability | restart, duplicate, lease/fencing, projection rebuild and backup/restore evidence | RED on lost/duplicated authoritative state or stale-writer acceptance |
| Operations | health/readiness, SLO/alerts for the platform profile, logs/metrics/traces and runbooks | RED when failure is not externally detectable or diagnosable |
| Rollback | exact prior digests, rollback procedure and post-rollback conformance | RED when rollback widens access, loses required state or enables a mock |

## Environment and activation boundary

SP-90 and SP-86 through SP-88 may build and qualify repository-local artifacts and disposable
environments. SP-89 may qualify a named non-production environment only when its environment identity,
owner, allowed operations and rollback are supplied independently.

No task here creates or approves cloud infrastructure, production credentials, DNS, secrets, alert
destinations or a production rollout. Qualification produces evidence; a separate human activation
decision selects an environment and deployment mutation.

## Handoff order

1. Assign SP-90 in Barbarossa to publish the Go production-runtime baseline.
2. Assign SP-86 in Omniscience independently; it may run concurrently with SP-90.
3. Assign SP-87 in Barbarossa after exact SP-90 and SP-86 receipts exist.
4. Assign SP-88 in Platform Portal after exact SP-86 and SP-87 receipts exist.
5. Assign SP-89 in `genai-enablement` after all three component receipts exist and a named
   non-production environment is authorized.

An agent that lacks an input returns the task's typed RED/decision-required evidence. It does not
substitute a mock, widen the profile, edit a sibling, or claim partial qualification as success.
