# Synchronized platform ADR/SPEC plan

**Canonical owner:** `genai-enablement`

**Target component scope:** `genai-enablement`, `Barbarossa`, `omnius`, `Omniscience`, `platform-portal`

**Initial runtime profile:** [`management-readonly-v1`](profiles/management-readonly-v1.md) selects
`Omniscience`, `Barbarossa`, and `platform-portal`; `omnius` is retained but deferred from this profile.

**Machine-readable source:** [`portfolio/synchronized-platform.json`](../../portfolio/synchronized-platform.json)

This is the complete navigation and dependency plan for the synchronized platform. It answers two
different questions without merging their authority:

1. **What should be built, and in what cross-repository order?** This plan and the cross-repository ADRs
   answer that question.
2. **What may an agent implement in one repository?** The owning component's ready capability/task SPEC,
   readiness profile, and local evidence rules answer that question.

The plan is not an execution oracle and does not copy component requirements. An agent can take one
local SPEC without a writable `genai-enablement` checkout; the local `PLATFORM.md` provides the stable
link back here for wider context.

## Authority and discovery

```text
genai-enablement cross-repo ADR
              |
              +--> component adoption ADR
                         |
                         +--> component capability SPEC
                                      |
                                      +--> component task SPEC
                                                   |
                                                   +--> immutable evidence
```

Every synchronized-platform repository uses the same discovery convention:

1. open root `PLATFORM.md`;
2. follow the local ADR and capability/task SPEC indexes;
3. claim one owning-repository task SPEC or one bounded capability-SPEC slice;
4. treat this plan as dependency/navigation context, never as permission to edit another repository;
5. return a versioned interface artifact or evidence receipt for the next work package.

For a cross-repository result, create or claim separate task SPECs in dependency order. One task SPEC has
one owning repository and cannot grant write authority in a sibling.

## Initial deployment profile

[ADR-0021](../decisions/0021-management-readonly-initial-runtime-profile.md) accepts
`management-readonly-v1` as the first deployment/qualification target. It is a selection over the full
architecture, not a redefinition of component ownership:

```text
Omniscience -> optional cited context -> Barbarossa Reliability -> source-bound Platform Portal views
      |                                      |                              |
      +-- PW0 gate                           +-- durable owner state         +-- no write/action routes

Omnius: target component retained; explicit not_deployed; no workload, credential, route or mock
```

The profile is read-only relative to managed systems and owner/component management controls. Selected
owners still persist their own admitted knowledge, observations, snapshots, cases, projections,
sessions and append-only audit records. ADR-0022 fixes Go as the only Barbarossa production runtime;
the TypeScript baseline is a non-deployable conformance oracle. SP-90 is the Go prerequisite and
SP-86 through SP-89 are the release chain; exact membership, negative space, evidence and handoff order are in the
[profile contract](profiles/management-readonly-v1.md).

## Component ownership

| Component | Owns | Does not own | Local plan |
|---|---|---|---|
| `genai-enablement` | cross-repository ADRs, synchronized work-package order, portfolio facts, PII Wall taxonomy/profile contracts, reusable Autonomous SRE harness and eval SPECs | component implementation details, live availability/incident truth, component schemas, runtime evidence | [`PLATFORM.md`](../../PLATFORM.md) |
| `Barbarossa` | shared continuous-management kernel, isolated domain packs, independent evidence/evaluation, cases, agent federation, cross-loop constraints, governed action requests, outcome verification, and source-bound projections | human objectives/policy/risk acceptance, component source truth, Omniscience semantic truth, Omnius execution, Portal composition, or PII policy | [local workspace](../../../Barbarossa/PLATFORM.md) · planned [repository](https://github.com/100rd/Barbarossa/blob/main/PLATFORM.md) |
| `omnius` | governed factory execution, readiness compilation, context/model/tool/egress PII enforcement, capability/task contracts, deterministic probes and evidence admission; target action-profile owner | Omniscience internals or cross-repository decision authority | [local workspace](../../../omnius/PLATFORM.md) · [repository](https://github.com/100rd/omnius/blob/main/PLATFORM.md) |
| `Omniscience` | knowledge-plane ledger/projections, pre-storage/pre-embedding PII enforcement, MCP producer contract, tenant boundary, release/canary and task evidence | Omnius planning/execution authority or the portfolio roadmap | [local workspace](../../../Omniscience/PLATFORM.md) · [repository](https://github.com/100rd/Omniscience/blob/main/PLATFORM.md) |
| `platform-portal` | cross-component visualization, component detail, Privacy Center composition, portal identity/tenancy/audit, and owner-delegated intent submission | component truth, privacy classification/compliance, gates, readiness, lifecycle, maintenance, or effect authority | [local workspace](../../../platform-portal/PLATFORM.md) · [repository](https://github.com/100rd/platform-portal/blob/main/PLATFORM.md) |

## UI composition boundary

Component-local UI keeps its owner independently operable. Omnius owns a narrow execution cockpit for
queues, one WorkOrder/task, local evidence, and local operator controls. Omniscience owns a narrow
operational UI for sources, ingestion/indexing, storage, freshness, MCP health, and maintenance.
Barbarossa owns a narrow management cockpit for source/evaluator/loop health, active cases, one case
detail, domain/constraint state, and management-agent queue/fleet/lease/dead-letter state.

Platform Portal is the detailed cross-component surface and Continuous Management Center: portfolio
and synchronized-work maps, loop/domain posture, evidence coverage, cross-loop constraints/conflicts,
cases, assessments, actions/receipts, independently verified outcomes, component pages, and thin
owner-authorized controls. It may render deep released projections, but every field remains
source-bound and every action is re-authorized and receipted by its component owner. Portal loss cannot
block component operation; component loss becomes an explicit unavailable projection.

For `management-readonly-v1`, Omnius is `not_deployed`, all Portal write/action routes are absent or
fail closed, and only released Omniscience and Barbarossa owner panels may be live. A deferred owner is
not an unavailable, empty, zero or healthy owner. Local/component control remains out of the selected
profile even when contract mocks exist.

## Barbarossa Continuous Management boundary

[ADR-0020](../decisions/0020-barbarossa-continuous-management-plane.md) accepts Barbarossa as the
separate Continuous Management Plane for development. The Reliability design in superseded
[ADR-0019](../decisions/0019-barbarossa-independent-reliability-plane.md) becomes the first domain
pack. `management agent` is a role family with many ephemeral workers; it is not one authoritative
model. Every domain uses the same mechanics without sharing truth or authority:

```text
human policy + independent/source-owned evidence
  -> admit -> deterministic domain evaluation -> immutable snapshot
     -> case -> multi-agent assess/plan -> constraint resolution
        -> separate authorization -> Omnius effect receipt
           -> fresh independent outcome verification -> learn/repeat

Omniscience -> severable management context; knowledge-quality source truth
Portal       -> Continuous Management Center projection, never authority
```

The v1 packs are Reliability, Cost & Value, AI & Agent Effectiveness, Security, Privacy, Continuous
Compliance, Supply-Chain Integrity, Delivery Effectiveness, Knowledge Quality, Capacity/Performance/
Sustainability, Toil, and Product Outcomes. Domain outcome, evidence, policy, loop health, action effect
and verification remain orthogonal. Missing/stale/incompatible coverage is typed, never favorable.
Hard reliability/security/privacy/compliance constraints cannot be offset by cost, speed or product
gain. Omniscience, Omnius and Portal remain severable; every domain boundary follows the PII Wall.

The first profile selects only Reliability plus the shared kernel/context/projection path. SP-73,
SP-76 through SP-80, SP-82 and SP-85 are not release prerequisites for that profile.

## PII Wall boundary

[ADR-0018](../decisions/0018-pii-wall-purpose-bound-data-boundary.md) accepts a distributed PII Wall,
not a central plaintext proxy. `genai-enablement` owns the common taxonomy, profile and receipt
semantics. Enforcement stays with the data owner:

```text
source
  -> Omniscience pre-ingest / pre-store / pre-chunk / pre-embedding gate
     -> released safe knowledge projection
        -> Omnius pre-context / model / tool / output / persistence gate
           -> non-identifying owner receipts
              -> Platform Portal Privacy Center
```

The maturity profiles are `PW0 PII-free`, `PW1 Pseudonymized`, and `PW2 Purpose-bound raw`. PW0 is the
default target; all three remain non-active until exact local slices, policy publications and
owner-boundary evidence exist. The portal displays coverage and submits
owner-delegated privacy intents, but never receives raw PII, mints a raw-data permit, or declares a
sibling clean/deleted. Barbarossa independently applies the same boundary before any management
evidence persistence, agent/model context, alert/case, action adapter, local view, or Portal projection;
telemetry, billing, security, audit, delivery, workforce and experiment data are not presumed
non-personal.

`management-readonly-v1` selects SP-60/SP-61 PW0 plus independent Barbarossa and Portal enforcement.
SP-62 is not a gate because the profile contains no Omnius data path. Portal releases privacy panels per
owner and renders the Omnius panel `not_deployed`; it does not infer platform-wide PII-free status.

## Cross-repository ADR inventory

Statuses below are decision states, not implementation states.

| ADR | Status | Primary synchronized-platform concern |
|---|---|---|
| [ADR-0001](../decisions/0001-continuous-detection-sentinel.md) | Accepted | Track-B Sentinel detector catalog |
| [ADR-0002](../decisions/0002-platform-skills-registry.md) | Proposed | shared skill distribution and local trust roots |
| [ADR-0003](../decisions/0003-unified-sdlc-standard.md) | Proposed | compatible SDLC event/evidence shape |
| [ADR-0004](../decisions/0004-experience-plane.md) | Accepted | verified cross-repository Experience plane |
| [ADR-0005](../decisions/0005-autonomous-factory-intake.md) | Accepted | committed-spec intake and standing roles |
| [ADR-0006](../decisions/0006-unified-loop-decision-model.md) | Proposed | loop decision compatibility |
| [ADR-0007](../decisions/0007-platform-portal-federated-surface.md) | Accepted | federated view, never authority |
| [ADR-0008](../decisions/0008-ai-security-domain.md) | Proposed | AI-security domain over the shared harness |
| [ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md) | Accepted | ADR → capability SPEC → task SPEC → evidence |
| [ADR-0010](../decisions/0010-goal-oriented-organizational-dark-factory.md) | Accepted | goal-oriented WorkOrders and Realm policy |
| [ADR-0011](../decisions/0011-platform-products-and-executable-paths.md) | Accepted | PlatformProducts and versioned executable paths |
| [ADR-0012](../decisions/0012-capability-readiness-profiles.md) | Accepted | immutable, selected REQ/probe readiness |
| [ADR-0013](../decisions/0013-platform-owned-observer-access.md) | Accepted | observer/workload authority separation |
| [ADR-0014](../decisions/0014-precommitted-http-condition-evidence.md) | Proposed | precommitted external HTTP completion evidence |
| [ADR-0015](../decisions/0015-independent-observer-authority-attestor.md) | Proposed | independent observer-authority attestation |
| [ADR-0016](../decisions/0016-independent-safe-to-reclaim-decision-issuer.md) | Proposed | independent signed reclaim authority |
| [ADR-0017](../decisions/0017-omniscience-mcp-v1-contract-and-severance.md) | Accepted | pinned, freshness-aware, severable MCP v1 |
| [ADR-0018](../decisions/0018-pii-wall-purpose-bound-data-boundary.md) | Accepted | distributed PII Wall and PW0/PW1/PW2 data boundary |
| [ADR-0019](../decisions/0019-barbarossa-independent-reliability-plane.md) | Superseded | historical Reliability domain architecture retained by Barbarossa |
| [ADR-0020](../decisions/0020-barbarossa-continuous-management-plane.md) | Accepted | shared Continuous Management kernel, isolated domain packs and cross-loop governance |
| [ADR-0021](../decisions/0021-management-readonly-initial-runtime-profile.md) | Accepted | first Omniscience/Barbarossa/Portal runtime profile with Omnius deferred and effects disabled |
| [ADR-0022](../decisions/0022-barbarossa-go-production-runtime.md) | Accepted | Go-only Barbarossa production runtime, TypeScript conformance-oracle boundary and SP-90 migration gate |

## Component SPEC inventory

### `genai-enablement`

The Autonomous SRE catalog remains a separate, non-authorizing construction track. The same local
[SPEC index](../specs/README.md) now also owns the ready PII policy contract and governance handoffs.

| Build order | Capability SPECs |
|---|---|
| B0 | `SPEC-B0` |
| B1–B2 | `SPEC-B1`, `SPEC-B2` |
| B3–B6 | `SPEC-B3`, `SPEC-B4`, `SPEC-B5`, `SPEC-B6` |
| B7 core | `SPEC-B7-CORE` |
| B7 detectors | `SPEC-B7`, `SPEC-B7-NES`, `SPEC-B7-CIR`, `SPEC-B7-DRIFT`, `SPEC-B7-SAT` |
| PII policy | `SPEC-PII-POLICY` |

The thirteen Track-B contracts remain `draft` and operationally incomplete. `SPEC-PII-POLICY` is
`ready` for a versioned non-active policy publication. The independently claimable governance tasks are
`task-sp-60-pii-policy-contract-v1` and
`task-sp-70-continuous-management-contract-release`. The separately ready
`task-sp-89-management-readonly-profile-qualification` joins exact SP-86/SP-87/SP-88 releases in one
named non-production environment; it cannot mint missing owner evidence. None authorizes a live
provider, credential, production deployment, remediation, PII activation, management action or
production claim.

### `Barbarossa`

The authoritative [local capability index](../../../Barbarossa/specs/SPEC-INDEX.md) contains 29
independently claimable planning-complete contracts:

```text
Kernel
  SPEC-LOOP -> SPEC-DOM -> SPEC-OBS -> SPEC-EVAL -> SPEC-CASE
  SPEC-FED  SPEC-CTX  SPEC-CFL  SPEC-ACT  SPEC-VRF  SPEC-VIEW  SPEC-AUT

Reliability       SPEC-JR  SPEC-AVL  SPEC-INC  SPEC-ALT
Cost & Value      SPEC-COST-POL  SPEC-COST-EVAL  SPEC-COST-ACT
AI assurance      SPEC-AIE
Security          SPEC-SEC
Privacy           SPEC-PRV
Compliance        SPEC-CMP
Supply chain      SPEC-SCI
Delivery          SPEC-DEL
Knowledge         SPEC-KNW
Capacity          SPEC-CAP
Toil              SPEC-TOIL
Product outcomes  SPEC-PROD
```

Twenty-eight are `complete-for-planning`; `SPEC-AUT` is `complete-for-planning-blocked`. These states
mean each capability has requirements, interfaces, degraded semantics, probes and explicit gates
sufficient for independent task planning. Accepted local ADR-0002 and cross-repository ADR-0020 now
permit these bounded, ready, non-live tasks from the
[local task queue](../../../Barbarossa/docs/specs/README.md):

| Ready task SPEC | Work package |
|---|---|
| `task-sp-71-kernel-runtime` | SP-71 |
| `task-sp-72-federation-constraints` | SP-72 |
| `task-sp-73-actions-verification` | SP-73 |
| `task-sp-74-projection-cockpit` | SP-74 |
| `task-sp-75-reliability-readonly` | SP-75 |
| `task-sp-76-cost-value-readonly` | SP-76 |
| `task-sp-77-ai-effectiveness-readonly` | SP-77 |
| `task-sp-78-assurance-packs-readonly` | SP-78 |
| `task-sp-79-delivery-knowledge-readonly` | SP-79 |
| `task-sp-80-capacity-toil-product-readonly` | SP-80 |
| `task-sp-83-context-consumer` | SP-83 |
| `task-sp-90-golang-runtime-migration` | SP-90 |
| `task-sp-87-management-readonly-reliability-release` | SP-87 |

They authorize fixture-backed contract/runtime construction only: no live source, credential,
deployment, alert route, domain activation, model/provider call, owner effect, autonomy promotion,
audit/risk decision, or production claim. `SPEC-AUT`/SP-85 deliberately has no ready task.

### `omnius`

The authoritative [capability index](https://github.com/100rd/omnius/blob/main/specs/SPEC-INDEX.md)
defines hard and signal-only dependencies. The original capability set remains `draft`; `SPEC-PII` and
`SPEC-MACT` are now `ready` for their exact non-active/non-effect task slices.

| Tier | Capability SPECs |
|---|---|
| T0 | `SPEC-CC`, `SPEC-TM` |
| T1 | `SPEC-PP`, `SPEC-WO`, `SPEC-RLM`, `SPEC-PRB`, `SPEC-EF`, `SPEC-IP`, `SPEC-SE`, `SPEC-PII`, `SPEC-VC`, `SPEC-IN` |
| T2 | `SPEC-TX` |
| T3 | `SPEC-DO`, `SPEC-CD`, `SPEC-RP`, `SPEC-MR`, `SPEC-MEM`, `SPEC-REG`, `SPEC-MACT` |
| T4 | `SPEC-EI`, `SPEC-EXP`, `SPEC-OT` |
| T5 | `SPEC-KP`, `SPEC-OS`, `SPEC-SK`, `SPEC-ROLE` |
| T6–T8 | `SPEC-FO`, `SPEC-HB`, `SPEC-UI` |
| cross-cutting | `SPEC-BM` |

The current `p0-standard-http-service-v3` profile is a non-authorizing draft. It is planning evidence,
not an activation. Its exact selected capability set is `SPEC-CC`, `SPEC-TM`, `SPEC-RLM`,
`SPEC-OS`, `SPEC-EF`, `SPEC-VC`, `SPEC-PRB`, `SPEC-PP`, `SPEC-WO`, `SPEC-IN`, `SPEC-TX`, `SPEC-CD`,
`SPEC-OT`, `SPEC-IP`, and `SPEC-DO`. The ready repository-local queue is:

| Ready task SPEC | Work package |
|---|---|
| `task-sp-11-mcp-consumer-pin` | SP-11 |
| `task-sp-20-p0-vertical-readiness` | SP-20 |
| `task-sp-30-experience-placement` | SP-30 |
| `task-sp-40-governance-publications` | SP-40 |
| `task-sp-62-pii-wall-pw0` | SP-62 |
| `task-sp-82-management-action-v1` | SP-82 |

Each task preserves the explicit producer, human, external-source and live-effect gates in its own
acceptance/rollback contract.

### `Omniscience`

All nine capability contracts are `ready` under the component-local decisions; PII and management
context readiness is limited to their exact task slices:

```text
SPEC-IN
SPEC-SOT --> SPEC-EV --> SPEC-KP
SPEC-ACL --------^       |
SPEC-OPS <---------------+
SPEC-EV + SPEC-KP + SPEC-ACL + SPEC-OPS --> SPEC-MCP
SPEC-ACL + SPEC-SOT + SPEC-EV + SPEC-OPS --> SPEC-PII
SPEC-SOT + SPEC-EV + SPEC-KP + SPEC-ACL + SPEC-OPS --> SPEC-MCTX
```

The [task queue](https://github.com/100rd/Omniscience/blob/main/docs/specs/README.md) has nine
independent ready slices:

| Task SPEC | Dependency position |
|---|---|
| `gh-issue-350-mcp-v1` | first; producer contract and release materialization |
| `gh-issue-350-consumer-severance` | after MCP v1 |
| `gh-issue-350-production-ha` | after MCP v1 |
| `gh-issue-350-backup-restore` | after production HA |
| `gh-issue-350-read-scaling-priority` | after production HA |
| `gh-issue-355` | independently fixes token-derived source tenancy |
| `task-sp-61-pii-wall-pw0` | after SP-60 policy publication |
| `task-sp-81-management-context-v1` | after SP-70 contract release |
| `task-sp-86-management-readonly-release` | after exact SP-10/SP-60/SP-61/SP-70/SP-81 inputs; publishes the selected runtime release |

Ready authorizes only the bounded repository-local work and disposable qualification written in each task.
It is not production/deployment/destructive authority.

### `platform-portal`

The [local capability index](https://github.com/100rd/platform-portal/blob/main/specs/SPEC-INDEX.md)
contains eleven capability contracts:

```text
SPEC-IT --> SPEC-PS --> SPEC-KV
               |
               +--> SPEC-PM --> SPEC-CV
               |
               +--> SPEC-PII
               |
               +--> SPEC-CP --> SPEC-CN --> SPEC-AU --> SPEC-BL
               |
               +--> SPEC-CMC
```

Nine contracts — `SPEC-IT`, `SPEC-PS`, `SPEC-KV`, `SPEC-CP`, `SPEC-CN`, `SPEC-AU`, `SPEC-BL`,
`SPEC-PM`, and `SPEC-CV` — are built against contract mocks. `SPEC-PII` and `SPEC-CMC` are ready for
bounded non-live development. The independently claimable
[local task queue](https://github.com/100rd/platform-portal/blob/main/docs/specs/README.md) is:

| Ready task SPEC | Work package |
|---|---|
| `task-sp-50-adoption-alignment` | SP-50 |
| `task-sp-51-registry-live-read` | SP-51 registry |
| `task-sp-51-omniscience-read-adapter` | SP-51 Omniscience |
| `task-sp-51-omnius-read-adapter` | SP-51 Omnius |
| `task-sp-52-delegated-control` | SP-52 |
| `task-sp-63-privacy-center` | SP-63 |
| `task-sp-84-continuous-management-center` | SP-84 |
| `task-sp-88-management-readonly-portal-release` | SP-88 |

No portal task authorizes a live integration, uncited component truth, component effect, deployment,
billing event or production claim; source release gates remain explicit.

## Independently claimable synchronized work packages

The `Depends on packages` and `Registry status` columns below are exact machine values checked against the
registry. External and human inputs remain prose in `Current gate` and are not fabricated as package edges.

| Package | Owner | Governing ADRs | Local execution contract | Depends on packages | Registry status | Current gate |
|---|---|---|---|---|---|---|
| `SP-00` governance/discovery | `genai-enablement` | ADR-0009, ADR-0012 | this plan + registry/drift checks | — | `maintained` | maintain catalogs; no runtime authority |
| `SP-10` MCP v1 producer | `omniscience` | ADR-0017 | `SPEC-MCP` + `gh-issue-350-mcp-v1` + `gh-issue-355` | `SP-00` | `implemented-verification-pending` | immutable release/canary and final verification evidence absent |
| `SP-11` Omnius MCP consumer | `omnius` | ADR-0017 | `SPEC-KP` + `task-sp-11-mcp-consumer-pin` | `SP-10` | `ready-for-development-producer-pin-gated` | develop against exact pin; direct-source fallback remains until verification |
| `SP-12` severance conformance | `omniscience` | ADR-0017 | `gh-issue-350-consumer-severance` | `SP-10`, `SP-11` | `implemented-evidence-pending` | exact consumer receipts and live safe-severance evidence absent |
| `SP-20` first governed P0 vertical | `omnius` | ADR-0009–0016 | `p0-standard-http-service-v3` + `task-sp-20-p0-vertical-readiness` | `SP-12` | `ready-for-development-external-gated` | external pins and human activation remain outside the task |
| `SP-30` verified Experience placement | `omnius` | ADR-0004 | `SPEC-EXP`, `SPEC-OT`, `SPEC-KP` + `task-sp-30-experience-placement` | — | `implemented-local` | PostgreSQL placement and human curation boundary fixed by local ADR-0025 |
| `SP-40` registry/roles/human boundary | `omnius` | ADR-0002, ADR-0005 | `SPEC-REG`, `SPEC-ROLE`, `SPEC-HB`, `SPEC-SK` + `task-sp-40-governance-publications` | — | `implemented-local` | signer injection and protected publication remain explicit release inputs |
| `SP-B0-B7` Autonomous SRE | `genai-enablement` | ADR-0001, ADR-0009 | thirteen local Track-B capability SPECs | — | `portable-construction` | portable construction only; external/live gates remain |
| `SP-50` portal foundation | `platform-portal` | ADR-0007, ADR-0011 | `SPEC-IT`, `SPEC-PS` + `task-sp-50-adoption-alignment` | `SP-00` | `implemented-local-mock-backed` | semantic traceability alignment; no live activation |
| `SP-51` platform visualization | `platform-portal` | ADR-0007, ADR-0011, ADR-0017 | `SPEC-PM`, `SPEC-CV`, `SPEC-KV`, `SPEC-AU` + three SP-51 task specs | `SP-50` | `implemented-local-source-gated` | released owner reads and per-component severance evidence absent |
| `SP-52` delegated component control | `platform-portal` | ADR-0007, ADR-0011 | `SPEC-CP`, `SPEC-CN` + `task-sp-52-delegated-control` | `SP-50` | `implemented-local-no-effect` | only intent/receipt/reconciliation construction; owner effect remains disabled |
| `SP-60` PII Wall governance | `genai-enablement` | ADR-0018 | `SPEC-PII-POLICY` + `task-sp-60-pii-policy-contract-v1` | `SP-00` | `implemented-local-non-active` | publish versioned taxonomy/profile/receipt contract; no profile activation |
| `SP-61` knowledge-plane PII boundary | `omniscience` | ADR-0012, ADR-0018 | `SPEC-PII` + `task-sp-61-pii-wall-pw0` | `SP-60` | `implemented-local-non-active` | fixture-backed PW0; real-store/lifecycle evidence remains release-gated |
| `SP-62` factory PII boundary | `omnius` | ADR-0012, ADR-0018 | `SPEC-PII` + `task-sp-62-pii-wall-pw0` | `SP-60` | `implemented-local-non-active` | fixture-backed PW0; provider/tool/egress activation remains release-gated |
| `SP-63` Privacy Center | `platform-portal` | ADR-0007, ADR-0011, ADR-0018 | `SPEC-PII` + `task-sp-63-privacy-center` | `SP-50`, `SP-61`, `SP-62` | `implemented-local-source-gated` | build safe projection against fixtures; owner releases remain absent |
| `SP-70` Continuous Management governance | `genai-enablement` | ADR-0020 | `task-sp-70-continuous-management-contract-release` | `SP-00` | `implemented-local-non-authorizing` | publish contract inventory/dependency release; no runtime authority |
| `SP-71` management-kernel foundation | `barbarossa` | ADR-0012, ADR-0013, ADR-0018, ADR-0020 | kernel capability set + `task-sp-71-kernel-runtime` | `SP-60`, `SP-70` | `implemented-local-non-live` | fixture stores/clock/identity/isolation with pinned PII policy; live sources remain disabled |
| `SP-72` federation and cross-loop constraints | `barbarossa` | ADR-0009, ADR-0012, ADR-0020 | `SPEC-FED`, `SPEC-CFL` + `task-sp-72-federation-constraints` | `SP-71` | `implemented-local-non-live` | deterministic federation/constraint fixtures; no live agents or budgets |
| `SP-73` governed actions and independent verification | `barbarossa` | ADR-0009, ADR-0010, ADR-0012, ADR-0020 | `SPEC-ACT`, `SPEC-VRF` + `task-sp-73-actions-verification` | `SP-72` | `implemented-local-non-live` | action requests/verification only; owner adapters and effects absent |
| `SP-74` management projections and local cockpit | `barbarossa` | ADR-0007, ADR-0011, ADR-0020 | `SPEC-VIEW` + `task-sp-74-projection-cockpit` | `SP-71` | `implemented-local-non-live` | fixture projection and narrow local cockpit; no copied owner truth |
| `SP-75` Reliability domain pack | `barbarossa` | ADR-0001, ADR-0012, ADR-0019, ADR-0020 | reliability capability set + `task-sp-75-reliability-readonly` | `SP-71` | `implemented-local-non-live` | read-only fixture vertical; real SLO/probe/incident/alert owners absent |
| `SP-76` Cost & Value domain pack | `barbarossa` | ADR-0012, ADR-0020 | cost capability set + `task-sp-76-cost-value-readonly` | `SP-71`, `SP-73` | `implemented-local-non-live` | read-only fixture vertical; finance/product policy inputs absent |
| `SP-77` AI & Agent Effectiveness pack | `barbarossa` | ADR-0012, ADR-0020 | `SPEC-AIE` + `task-sp-77-ai-effectiveness-readonly` | `SP-71`, `SP-73` | `implemented-local-non-live` | read-only fixture vertical; system fingerprint/graders/outcome slices absent |
| `SP-78` security, privacy, compliance and supply-chain packs | `barbarossa` | ADR-0008, ADR-0012, ADR-0018, ADR-0020 | assurance capability set + `task-sp-78-assurance-packs-readonly` | `SP-71`, `SP-73` | `implemented-local-non-live` | read-only fixture vertical; owner policies and independent retests absent |
| `SP-79` delivery and knowledge-quality packs | `barbarossa` | ADR-0017, ADR-0020 | `SPEC-DEL`, `SPEC-KNW` + `task-sp-79-delivery-knowledge-readonly` | `SP-71`, `SP-73`, `SP-83` | `implemented-local-non-live` | read-only fixtures; canonical delivery and released knowledge inputs absent |
| `SP-80` capacity, toil and product-outcome packs | `barbarossa` | ADR-0012, ADR-0020 | outcome capability set + `task-sp-80-capacity-toil-product-readonly` | `SP-71`, `SP-72`, `SP-73` | `implemented-local-non-live` | read-only fixtures; capacity/workflow/product owners absent |
| `SP-81` Omniscience management-context producer | `omniscience` | ADR-0017, ADR-0020 | `SPEC-MCTX` + `task-sp-81-management-context-v1` | `SP-70` | `implemented-local-release-gated` | versioned cited context/quality projection; release and severance evidence pending |
| `SP-82` Omnius management-action producer | `omnius` | ADR-0009, ADR-0010, ADR-0012, ADR-0020 | `SPEC-MACT` + `task-sp-82-management-action-v1` | `SP-70` | `implemented-local-no-effect` | owner authorization/receipt/reconciliation fixtures; effects disabled |
| `SP-83` Barbarossa context consumer | `barbarossa` | ADR-0017, ADR-0020 | `SPEC-CTX` + `task-sp-83-context-consumer` | `SP-72`, `SP-81` | `implemented-local-producer-gated` | build severable adapter against fixture; live use waits for SP-81 release |
| `SP-84` Portal Continuous Management Center | `platform-portal` | ADR-0007, ADR-0011, ADR-0020 | `SPEC-CMC` + `task-sp-84-continuous-management-center` | `SP-50`, `SP-74`, `SP-75`, `SP-76`, `SP-77`, `SP-78`, `SP-79`, `SP-80` | `implemented-local-source-gated` | mock vertical ready; released Barbarossa/SP-81/SP-82 sources absent |
| `SP-85` progressive domain autonomy | `barbarossa` | ADR-0009, ADR-0012, ADR-0020 | `SPEC-AUT` | `SP-B0-B7`, `SP-73`, `SP-82` | `blocked-on-live-evidence` | no selected domain/action live qualification, identities, constraints, rollback or forced-negative drills |
| `SP-86` Omniscience management-readonly release | `omniscience` | ADR-0012, ADR-0017, ADR-0018, ADR-0020, ADR-0021, ADR-0022 | `SPEC-MCP`, `SPEC-PII`, `SPEC-MCTX` + `task-sp-86-management-readonly-release` | `SP-10`, `SP-61`, `SP-81` | `ready-for-development-input-release-gated` | publish an exact language-neutral image/chart/contract/PW0 release and producer evidence independently of SP-90; no deployment activation |
| `SP-87` Barbarossa management-readonly Reliability release | `barbarossa` | ADR-0012, ADR-0017, ADR-0018, ADR-0020, ADR-0021, ADR-0022 | selected kernel/Reliability/context/view capabilities + `task-sp-87-management-readonly-reliability-release` | `SP-86`, `SP-90` | `ready-for-development-producer-gated` | package exact Go baseline and SP-86 consumer/severance receipt; no Node or action/effect route |
| `SP-88` Portal management-readonly release | `platform-portal` | ADR-0007, ADR-0011, ADR-0018, ADR-0020, ADR-0021, ADR-0022 | `SPEC-IT`, `SPEC-PS`, `SPEC-PM`, `SPEC-CV`, `SPEC-PII`, `SPEC-CMC` + `task-sp-88-management-readonly-portal-release` | `SP-50`, `SP-86`, `SP-87` | `ready-for-development-owner-release-gated` | exact live reads and Go provenance display, owner-scoped panels, Omnius not_deployed and all write/action routes disabled |
| `SP-89` integrated management-readonly qualification | `genai-enablement` | ADR-0012, ADR-0018, ADR-0020, ADR-0021, ADR-0022 | `task-sp-89-management-readonly-profile-qualification` | `SP-86`, `SP-87`, `SP-88` | `ready-for-development-component-release-gated` | independently join exact releases and transitive SP-90 Go evidence in one authorized non-production target; no activation or infra mutation |
| `SP-90` Barbarossa Go runtime migration | `barbarossa` | ADR-0018, ADR-0020, ADR-0021, ADR-0022 | selected kernel/Reliability/context/view capabilities + `task-sp-90-golang-runtime-migration` | `SP-71`, `SP-72`, `SP-74`, `SP-75`, `SP-83` | `ready-for-development-contract-migration-gated` | immutable Go baseline with parity, durability, PW0, no-effect and no-Node evidence; not a component release |

`SP-10`, `SP-11`, and `SP-12` deliberately remain three tasks. No producer task may edit the consumer,
and no consumer receipt may rewrite the producer contract.

`SP-50`, `SP-51`, and `SP-52` keep portal foundation, visualization, and owner-delegated controls
independently claimable. A portal task never grants write authority in an owner repository.

`SP-61` and `SP-62` can be implemented independently after the shared governance artifact is published;
neither requires writable access to the other component. `SP-63` composes their released receipts only
after each owner has separately qualified its projection/action contract.

`SP-71` through `SP-74` form the independently implementable management kernel and projection surface.
`SP-75` through `SP-80` are separate domain-pack slices; readiness never transfers between them.
`SP-81` and `SP-82` are producer-owned work and grant no Barbarossa task sibling write access.
`SP-83` consumes only an exact Omniscience release with typed severance. `SP-84` composes released
Barbarossa truth without copying authority. `SP-85` remains blocked even if kernel and portable harness
tests pass; promotion is per exact domain/action profile.

`SP-90` is the required Barbarossa Go baseline but is not a component release. `SP-86` through `SP-89`
are the only release packages selected by `management-readonly-v1`. SP-86 and SP-90 may execute
independently; SP-87 requires both, SP-88 returns its own pinned consumer evidence, and SP-89 only joins
exact receipts and verifies the transitive Go binding. Existing Omnius packages retain their global
status but are not in this profile's required closure. Existing broad mock/construction packages remain
evidence inputs, not automatic live gates.

## Development handoff queue

The unit of dispatch is one ready task SPEC in its owning repository. A wave expresses dependency order,
not shared write access; tasks inside a wave can be claimed independently when their own inputs exist.

The current deployment-focused queue is:

1. **SP-90 — Barbarossa Go baseline:** assign `task-sp-90-golang-runtime-migration` and obtain one
   immutable compiler/module/binary/image/SBOM/parity/no-Node receipt.
2. **SP-86 — Omniscience:** independently assign `task-sp-86-management-readonly-release` and obtain
   one immutable producer/image/chart/PW0 receipt; it may run concurrently with SP-90.
3. **SP-87 — Barbarossa release:** after exact SP-90 and SP-86 receipts, assign
   `task-sp-87-management-readonly-reliability-release`; obtain the Go-only durable Reliability,
   context-severance, projection and no-effect evidence.
4. **SP-88 — Platform Portal:** after exact SP-86/SP-87 releases, assign
   `task-sp-88-management-readonly-portal-release`; obtain live-read, tenant/PW0, owner-severance,
   Omnius-`not_deployed` and no-write evidence.
5. **SP-89 — integration:** after all three owner receipts and a separately authorized named
   non-production environment exist, assign `task-sp-89-management-readonly-profile-qualification`.
6. **Do not dispatch Omnius or SP-85 for this profile:** their contracts remain discoverable future
   work and cannot be replaced by a mock or partial receipt.

The earlier construction queue remains historical dependency context for capabilities outside the
selected deployment profile:

1. **Publish the two shared contracts and close local adoption choices:**
   `task-sp-60-pii-policy-contract-v1`,
   `task-sp-70-continuous-management-contract-release`,
   `task-sp-30-experience-placement`,
   `task-sp-40-governance-publications`, and
   `task-sp-50-adoption-alignment`.
2. **Build owner boundaries and the management kernel:**
   `task-sp-61-pii-wall-pw0` and `task-sp-62-pii-wall-pw0` after the SP-60 artifact;
   `task-sp-71-kernel-runtime` after both SP-60 and SP-70; `task-sp-81-management-context-v1` and
   `task-sp-82-management-action-v1` after the SP-70 release; the three SP-51 read tasks and
   `task-sp-52-delegated-control` after SP-50. `task-sp-11-mcp-consumer-pin` waits for the immutable
   SP-10 producer pin, and `task-sp-20-p0-vertical-readiness` waits for SP-12 evidence.
3. **Compose independent loops and read-only domains:**
   `task-sp-72-federation-constraints`, then `task-sp-73-actions-verification`;
   `task-sp-74-projection-cockpit` and `task-sp-75-reliability-readonly` after SP-71;
   `task-sp-83-context-consumer` after SP-72/SP-81; then the SP-76 through SP-80 domain tasks at their
   exact package dependencies. `task-sp-63-privacy-center` follows SP-50/SP-61/SP-62.
4. **Compose the detailed portal view:**
   `task-sp-84-continuous-management-center` after the SP-74 through SP-80 read projections. Its mock
   vertical may ship without effects; live context/actions remain gated by SP-81/SP-82 releases.
5. **Do not dispatch SP-85:** progressive autonomy remains blocked until one exact domain/action profile
   has live qualification, owner identities, constraints, rollback and forced-negative evidence.

The existing Omniscience issue-350/355 queue remains independently dispatchable in its documented
dependency order. SP-10 and SP-12 need verification evidence, not another speculative design pass.

## Handoff contract for one SPEC

An agent receiving one component SPEC must be given:

- owning repository and exact writable paths;
- the local `PLATFORM.md`;
- capability SPEC and, when work is being executed, one ready task SPEC or exact readiness-profile slice;
- accepted governing ADR ids, plus any still-proposed cross-repository ADRs explicitly retained as
  non-authorizing constraints;
- required external input artifact digests or typed RED/park behavior when absent;
- acceptance probes and evidence destination;
- forbidden sibling writes and external actions.

The agent returns:

- changed component-owned artifacts only;
- exact verification commands/results;
- an immutable interface artifact, release bundle, or evidence receipt named by the SPEC;
- unresolved external/human gates without converting them into fixture success.

This handoff is sufficient for independent component work. Reading the full plan is required for
navigation and dependency awareness, not for inventing missing local requirements.

## Verification

From `genai-enablement`:

```bash
python3 scripts/check_synchronized_platform.py
python3 scripts/check_synchronized_platform.py --workspace-root ..
python3 -m unittest discover -s tests -p 'test_synchronized_platform.py' -v
```

The hermetic check validates this repository's registry and plan. The explicit workspace check also opens
the sibling projects and validates their `PLATFORM.md`, indexes, and registered SPEC/task inventories. It
never discovers or edits siblings implicitly.
