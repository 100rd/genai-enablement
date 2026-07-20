# Synchronized platform ADR/SPEC plan

**Canonical owner:** `genai-enablement`

**Component scope:** `genai-enablement`, `Barbarossa`, `omnius`, `Omniscience`, `platform-portal`

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

## Component ownership

| Component | Owns | Does not own | Local plan |
|---|---|---|---|
| `genai-enablement` | cross-repository ADRs, synchronized work-package order, portfolio facts, and PII Wall taxonomy/profile contracts | component implementation details, live availability/incident truth, component schemas, runtime evidence | [`PLATFORM.md`](../../PLATFORM.md) |
| `Barbarossa` | shared continuous-management kernel, isolated domain packs, independent evidence/evaluation, cases, agent federation, cross-loop constraints, governed action requests, outcome verification, and source-bound projections | human objectives/policy/risk acceptance, component source truth, Omniscience semantic truth, Omnius execution, Portal composition, or PII policy | [local workspace](../../../Barbarossa/PLATFORM.md) · planned [repository](https://github.com/100rd/Barbarossa/blob/main/PLATFORM.md) |
| `omnius` | governed factory execution, readiness compilation, context/model/tool/egress PII enforcement, capability/task contracts, deterministic probes and evidence admission | Omniscience internals or cross-repository decision authority | [local workspace](../../../omnius/PLATFORM.md) · [repository](https://github.com/100rd/omnius/blob/main/PLATFORM.md) |
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

## Barbarossa Continuous Management boundary

[ADR-0020](../decisions/0020-barbarossa-continuous-management-plane.md) proposes Barbarossa as the
separate Continuous Management Plane. The Reliability design in superseded
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

## PII Wall boundary

[ADR-0018](../decisions/0018-pii-wall-purpose-bound-data-boundary.md) proposes a distributed PII Wall,
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
default target; all three remain non-active until the proposed ADR is accepted, exact local slices are
human-ready, and owner-boundary evidence exists. The portal displays coverage and submits
owner-delegated privacy intents, but never receives raw PII, mints a raw-data permit, or declares a
sibling clean/deleted. Barbarossa independently applies the same boundary before any management
evidence persistence, agent/model context, alert/case, action adapter, local view, or Portal projection;
telemetry, billing, security, audit, delivery, workforce and experiment data are not presumed
non-personal.

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
| [ADR-0007](../decisions/0007-platform-portal-federated-surface.md) | Proposed | federated view, never authority |
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
| [ADR-0018](../decisions/0018-pii-wall-purpose-bound-data-boundary.md) | Proposed | distributed PII Wall and PW0/PW1/PW2 data boundary |
| [ADR-0019](../decisions/0019-barbarossa-independent-reliability-plane.md) | Superseded | historical Reliability domain architecture retained by Barbarossa |
| [ADR-0020](../decisions/0020-barbarossa-continuous-management-plane.md) | Proposed | shared Continuous Management kernel, isolated domain packs and cross-loop governance |

## Component SPEC inventory

### `genai-enablement`

This repository owns the shared plan, cross-repository ADRs, machine registry and validation. It has no
component-local runtime capability SPEC in this synchronized catalog. Reusable harness construction
remains a separate program asset and cannot qualify a Barbarossa domain or action profile by itself.

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
sufficient for independent task planning. The [local task queue](../../../Barbarossa/docs/specs/README.md)
contains no human-ready live task. Local ADR-0002 and cross-repository ADR-0020 remain Proposed, so the
catalog authorizes documentation/mock contract work only: no live source, credential, probe,
deployment, alert, domain declaration, model/provider call, action, readiness, audit/risk decision, or
production claim.

### `omnius`

The authoritative [capability index](https://github.com/100rd/omnius/blob/main/specs/SPEC-INDEX.md)
defines hard and signal-only dependencies. All component documents remain `draft`; only exact selections
inside a human-ready readiness profile become executable.

| Tier | Capability SPECs |
|---|---|
| T0 | `SPEC-CC`, `SPEC-TM` |
| T1 | `SPEC-PP`, `SPEC-WO`, `SPEC-RLM`, `SPEC-PRB`, `SPEC-EF`, `SPEC-IP`, `SPEC-SE`, `SPEC-PII`, `SPEC-VC`, `SPEC-IN` |
| T2 | `SPEC-TX` |
| T3 | `SPEC-DO`, `SPEC-CD`, `SPEC-RP`, `SPEC-MR`, `SPEC-MEM`, `SPEC-REG` |
| T4 | `SPEC-EI`, `SPEC-EXP`, `SPEC-OT` |
| T5 | `SPEC-KP`, `SPEC-OS`, `SPEC-SK`, `SPEC-ROLE` |
| T6–T8 | `SPEC-FO`, `SPEC-HB`, `SPEC-UI` |
| cross-cutting | `SPEC-BM` |

The current `p0-standard-http-service-v3` profile is a non-authorizing draft. It is planning evidence,
not a task queue or activation. Its exact selected capability set is `SPEC-CC`, `SPEC-TM`, `SPEC-RLM`,
`SPEC-OS`, `SPEC-EF`, `SPEC-VC`, `SPEC-PRB`, `SPEC-PP`, `SPEC-WO`, `SPEC-IN`, `SPEC-TX`, `SPEC-CD`,
`SPEC-OT`, `SPEC-IP`, and `SPEC-DO`.

### `Omniscience`

The initial seven capability contracts are `ready` under Omniscience's component-local accepted ADR-0019.
`SPEC-PII` is a separate `draft` contract and does not inherit that readiness:

```text
SPEC-IN
SPEC-SOT --> SPEC-EV --> SPEC-KP
SPEC-ACL --------^       |
SPEC-OPS <---------------+
SPEC-EV + SPEC-KP + SPEC-ACL + SPEC-OPS --> SPEC-MCP
SPEC-ACL + SPEC-SOT + SPEC-EV + SPEC-OPS --> SPEC-PII
```

The [task queue](https://github.com/100rd/Omniscience/blob/main/docs/specs/README.md) has five independent,
human-ready issue-350 slices:

| Task SPEC | Dependency position |
|---|---|
| `gh-issue-350-mcp-v1` | first; producer contract and release materialization |
| `gh-issue-350-consumer-severance` | after MCP v1 |
| `gh-issue-350-production-ha` | after MCP v1 |
| `gh-issue-350-backup-restore` | after production HA |
| `gh-issue-350-read-scaling-priority` | after production HA |

Ready authorizes only the bounded repository-local work and disposable qualification written in each task.
It is not production/deployment/destructive authority.

### `platform-portal`

The [local capability index](https://github.com/100rd/platform-portal/blob/main/specs/SPEC-INDEX.md)
contains ten `draft` capability contracts:

```text
SPEC-IT --> SPEC-PS --> SPEC-KV
               |
               +--> SPEC-PM --> SPEC-CV
               |
               +--> SPEC-PII
               |
               +--> SPEC-CP --> SPEC-CN --> SPEC-AU --> SPEC-BL
```

`SPEC-IT`, `SPEC-PS`, `SPEC-KV`, `SPEC-CP`, `SPEC-CN`, `SPEC-AU`, and `SPEC-BL` have mock-backed
construction on `main`, but remain non-live and require ADR-0007 adoption alignment plus exact owner
release gates. `SPEC-PM`, `SPEC-CV`, and `SPEC-PII` are documentation-only drafts for the two-layer
platform map, detailed component projections, and the Privacy Center. The
[local task queue](https://github.com/100rd/platform-portal/blob/main/docs/specs/README.md)
contains no human-ready task yet. No portal SPEC currently authorizes a live integration, component
action, deployment, billing event, or production claim.

## Independently claimable synchronized work packages

The `Depends on packages` and `Registry status` columns below are exact machine values checked against the
registry. External and human inputs remain prose in `Current gate` and are not fabricated as package edges.

| Package | Owner | Governing ADRs | Local execution contract | Depends on packages | Registry status | Current gate |
|---|---|---|---|---|---|---|
| `SP-00` governance/discovery | `genai-enablement` | ADR-0009, ADR-0012 | this plan + registry/drift checks | — | `maintained` | maintain catalogs; no runtime authority |
| `SP-10` MCP v1 producer | `omniscience` | ADR-0017 | `SPEC-MCP` + `gh-issue-350-mcp-v1` | `SP-00` | `in-progress` | dirty construction; immutable release/canary evidence absent |
| `SP-11` Omnius MCP consumer | `omnius` | ADR-0017 | `SPEC-KP` selected slice | `SP-10` | `blocked-on-producer-pin` | direct-source fallback until exact producer pin is verified |
| `SP-12` severance conformance | `omniscience` | ADR-0017 | `gh-issue-350-consumer-severance` | `SP-10`, `SP-11` | `ready-spec-evidence-pending` | exact consumer receipts and live safe-severance evidence absent |
| `SP-20` first governed P0 vertical | `omnius` | ADR-0009–0016 | `p0-standard-http-service-v3` exact 15-capability selection | `SP-12` | `draft-non-authorizing` | draft, 11 blockers, human activation absent |
| `SP-30` verified Experience placement | `omnius` | ADR-0004 | `SPEC-EXP`, `SPEC-OT`, `SPEC-KP` | — | `decision-required` | production store and curation authority undecided |
| `SP-40` registry/roles/human boundary | `omnius` | ADR-0002, ADR-0005 | `SPEC-REG`, `SPEC-ROLE`, `SPEC-HB`, `SPEC-SK` | — | `decision-required` | decision/publication required |
| `SP-50` portal foundation | `platform-portal` | ADR-0007, ADR-0011 | `SPEC-IT`, `SPEC-PS` | `SP-00` | `draft-non-authorizing` | ADR-0007 disposition and legacy traceability alignment required |
| `SP-51` platform visualization | `platform-portal` | ADR-0007, ADR-0011, ADR-0017 | `SPEC-PM`, `SPEC-CV`, `SPEC-KV`, `SPEC-AU` | `SP-50` | `draft-contract-gated` | released owner read contracts and per-component severance evidence absent |
| `SP-52` delegated component control | `platform-portal` | ADR-0007, ADR-0011 | `SPEC-CP`, `SPEC-CN` | `SP-50` | `mock-backed-non-authorizing` | owner action authorization, receipts, reconciliation, and live negative evidence absent |
| `SP-60` PII Wall governance | `genai-enablement` | ADR-0018 | ADR + registry + drift checks | `SP-00` | `proposed-non-authorizing` | ADR-0018 acceptance, policy publisher/trust root, and minimum schema pins absent |
| `SP-61` knowledge-plane PII boundary | `omniscience` | ADR-0012, ADR-0018 | `SPEC-PII` | `SP-60` | `draft-contract-gated` | pre-propagation implementation, lifecycle coverage, and real-store evidence absent |
| `SP-62` factory PII boundary | `omnius` | ADR-0012, ADR-0018 | `SPEC-PII` | `SP-60` | `draft-contract-gated` | context/model/tool/provider contracts and real-boundary evidence absent |
| `SP-63` Privacy Center | `platform-portal` | ADR-0007, ADR-0011, ADR-0018 | `SPEC-PII` | `SP-50`, `SP-61`, `SP-62` | `draft-source-gated` | accepted portal/privacy decisions and released owner privacy projections/actions absent |
| `SP-70` Continuous Management governance | `genai-enablement` | ADR-0020 | ADR + registry + drift checks | `SP-00` | `proposed-non-authorizing` | ADR-0020 human disposition and local Barbarossa adoption remain absent |
| `SP-71` management-kernel foundation | `barbarossa` | ADR-0012, ADR-0013, ADR-0018, ADR-0020 | `SPEC-LOOP`, `SPEC-DOM`, `SPEC-OBS`, `SPEC-EVAL`, `SPEC-CASE` | `SP-70` | `planning-complete-runtime-gated` | store/clock/identity/isolation, PII policy and real evidence corpus absent |
| `SP-72` federation and cross-loop constraints | `barbarossa` | ADR-0009, ADR-0012, ADR-0020 | `SPEC-FED`, `SPEC-CFL` | `SP-71` | `planning-complete-runtime-gated` | durable engine, fencing, budgets and human conflict policy absent |
| `SP-73` governed actions and independent verification | `barbarossa` | ADR-0009, ADR-0010, ADR-0012, ADR-0020 | `SPEC-ACT`, `SPEC-VRF` | `SP-72` | `planning-complete-producer-gated` | owner action adapters, verification sources, rollback and reconciliation absent |
| `SP-74` management projections and local cockpit | `barbarossa` | ADR-0007, ADR-0011, ADR-0020 | `SPEC-VIEW` | `SP-71` | `planning-complete-contract-gated` | projection auth/scope/schema/freshness and local operator policy undecided |
| `SP-75` Reliability domain pack | `barbarossa` | ADR-0001, ADR-0012, ADR-0019, ADR-0020 | `SPEC-JR`, `SPEC-AVL`, `SPEC-INC`, `SPEC-ALT` | `SP-71` | `planning-complete-domain-gated` | journey/SLO owners, real probes, incident policy, alert routes and watchdog absent |
| `SP-76` Cost & Value domain pack | `barbarossa` | ADR-0012, ADR-0020 | `SPEC-COST-POL`, `SPEC-COST-EVAL`, `SPEC-COST-ACT` | `SP-71`, `SP-73` | `planning-complete-domain-gated` | finance/product owners, functional units, FOCUS mapping, allocation and action classes absent |
| `SP-77` AI & Agent Effectiveness pack | `barbarossa` | ADR-0012, ADR-0020 | `SPEC-AIE` | `SP-71`, `SP-73` | `planning-complete-domain-gated` | exact system fingerprint, suites/graders, production outcome slices and risk owner absent |
| `SP-78` security, privacy, compliance and supply-chain packs | `barbarossa` | ADR-0008, ADR-0012, ADR-0018, ADR-0020 | `SPEC-SEC`, `SPEC-PRV`, `SPEC-CMP`, `SPEC-SCI` | `SP-71`, `SP-73` | `planning-complete-domain-gated` | owner policies, source/assessment coverage, trust/admission and independent retests absent |
| `SP-79` delivery and knowledge-quality packs | `barbarossa` | ADR-0017, ADR-0020 | `SPEC-DEL`, `SPEC-KNW` | `SP-71`, `SP-73`, `SP-83` | `planning-complete-domain-gated` | canonical delivery linkage and released Omniscience quality contract absent |
| `SP-80` capacity, toil and product-outcome packs | `barbarossa` | ADR-0012, ADR-0020 | `SPEC-CAP`, `SPEC-TOIL`, `SPEC-PROD` | `SP-71`, `SP-72`, `SP-73` | `planning-complete-domain-gated` | capacity models, privacy-safe workflow evidence, product outcome/experiment owners absent |
| `SP-81` Omniscience management-context producer | `omniscience` | ADR-0017, ADR-0020 | owner-local context and knowledge-quality contracts required | `SP-70` | `local-spec-required` | no generic context/quality schema, auth, freshness, citation and severance contract |
| `SP-82` Omnius management-action producer | `omnius` | ADR-0009, ADR-0010, ADR-0012, ADR-0020 | owner-local management action/receipt contract required | `SP-70` | `local-spec-required` | no owner action, authorization, idempotency, receipt or reconciliation contract |
| `SP-83` Barbarossa context consumer | `barbarossa` | ADR-0017, ADR-0020 | `SPEC-CTX` | `SP-72`, `SP-81` | `planning-complete-producer-gated` | waits for immutable Omniscience producer release and severance evidence |
| `SP-84` Portal Continuous Management Center | `platform-portal` | ADR-0007, ADR-0011, ADR-0020 | owner-local Continuous Management Center contract required | `SP-50`, `SP-74`, `SP-75`, `SP-76`, `SP-77`, `SP-78`, `SP-79`, `SP-80` | `local-spec-required` | Portal SPEC plus released Barbarossa/domain projection and severance fixtures absent |
| `SP-85` progressive domain autonomy | `barbarossa` | ADR-0009, ADR-0012, ADR-0020 | `SPEC-AUT` | `SP-73`, `SP-82` | `blocked-on-live-evidence` | no selected domain/action live qualification, identities, constraints, rollback or forced-negative drills |

`SP-10`, `SP-11`, and `SP-12` deliberately remain three tasks. No producer task may edit the consumer,
and no consumer receipt may rewrite the producer contract.

`SP-50`, `SP-51`, and `SP-52` keep portal foundation, visualization, and owner-delegated controls
independently claimable. A portal task never grants write authority in an owner repository.

`SP-61` and `SP-62` can be implemented independently after the shared governance contract is accepted;
neither requires writable access to the other component. `SP-63` composes their released receipts only
after each owner has separately qualified its projection/action contract.

`SP-71` through `SP-74` form the independently implementable management kernel and projection surface.
`SP-75` through `SP-80` are separate domain-pack slices; readiness never transfers between them.
`SP-81` and `SP-82` are producer-owned work and grant no Barbarossa task sibling write access.
`SP-83` consumes only an exact Omniscience release with typed severance. `SP-84` composes released
Barbarossa truth without copying authority. `SP-85` remains blocked even if kernel tests pass;
promotion is per exact domain/action profile.

## Handoff contract for one SPEC

An agent receiving one component SPEC must be given:

- owning repository and exact writable paths;
- the local `PLATFORM.md`;
- capability SPEC and, when work is being executed, one ready task SPEC or exact readiness-profile slice;
- accepted governing ADR ids;
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
