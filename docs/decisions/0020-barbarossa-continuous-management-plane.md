# ADR-0020: Barbarossa is the synchronized-platform Continuous Management Plane

- **Status:** Proposed
- **Date:** 2026-07-19
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `Barbarossa`, `Omniscience`, `omnius`,
  `platform-portal`, the PII Wall, and synchronized-platform evidence producers)
- **Supersedes:** [ADR-0019](0019-barbarossa-independent-reliability-plane.md) as the Barbarossa product
  boundary; ADR-0019 remains the Reliability domain design history
- **Builds on:** [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0010](0010-goal-oriented-organizational-dark-factory.md),
  [ADR-0011](0011-platform-products-and-executable-paths.md),
  [ADR-0012](0012-capability-readiness-profiles.md),
  [ADR-0013](0013-platform-owned-observer-access.md),
  [ADR-0017](0017-omniscience-mcp-v1-contract-and-severance.md), and
  [ADR-0019](0019-barbarossa-independent-reliability-plane.md)
- **Related proposals:** [ADR-0007](0007-platform-portal-federated-surface.md),
  [ADR-0008](0008-ai-security-domain.md), and
  [ADR-0018](0018-pii-wall-purpose-bound-data-boundary.md)

## Context

ADR-0019 established the correct architecture for an AI SRE capability: current journey availability
comes from independent evidence and deterministic policy, not an agent, component self-report or UI.
Agents may investigate and propose, Omniscience supplies severable context, Omnius owns execution, and
Barbarossa verifies the outcome independently.

Reliability is one instance of a broader class. Cost and value, AI-system assurance, security,
privacy, compliance, software supply-chain integrity, delivery effectiveness, knowledge quality,
capacity/performance/sustainability, toil and product outcomes also have no finite “done” state. Each
continuously observes a changing system, evaluates it against human-owned policy, opens findings or
opportunities, proposes bounded changes, verifies realized outcomes and learns. Building an unrelated
agent platform for each would duplicate ledgers, orchestration, evidence semantics, action control,
verification and visualization. Combining their meaning into one optimizer would be worse: a saving
could offset an outage, an engagement metric could offset privacy harm, or a model score could become
authorization.

The synchronized platform therefore needs a common continuous-management runtime with domain-specific
truth and authority kept rigorously separate.

## Decision if accepted

### D1 — Generalize Barbarossa into the Continuous Management Plane

Barbarossa is a separately owned and deployable component for running continuous management loops. It
owns common loop lifecycle, evidence admission, deterministic evaluation runtime, case ledger,
multi-agent work coordination, cross-loop constraint resolution, governed action request protocol,
independent outcome verification, source-bound projections and progressive-autonomy gates.

`genai-enablement` owns this cross-repository decision, the synchronized work-package DAG, portfolio
facts, reusable harness/evaluation assets and the common PII Wall governance contract. It does not
become the live issuer for any Barbarossa domain.

### D2 — Split shared kernel mechanics from domain packs

The kernel defines mechanics only:

```text
define -> observe -> evaluate -> case -> assess/plan
       -> authorize -> act -> verify -> learn -> repeat
```

Each domain pack owns its manifest, namespace, objective and condition vocabulary, policy and owners,
evidence schemas, evaluator, case and action classes, imported/exported constraints, verification
profiles, PII/retention policy and qualification corpus. Kernel success and another pack's readiness
cannot qualify a domain.

Domain packs have separate workload identity, policy authority, ledgers/partitions, quotas and released
projections to the degree required by their isolation profile. They exchange only typed, versioned
facts and constraints. They do not read one another's private records or borrow identity/permission.

### D3 — Establish twelve v1 domain packs

| Pack | Managed outcome and boundary |
|---|---|
| Reliability | critical journeys, availability/error budgets, incidents and alert path; retains ADR-0019 architecture |
| Cost & Value | attributable cost, allocation, unit economics, opportunities and independently realized value; never blind cost cutting |
| AI & Agent Effectiveness | exact model/prompt/harness/tool/policy system capability, risk, drift and qualification; no self-grading authority |
| Security | asset exposure, threat relevance and control effectiveness; risk acceptance remains human |
| Privacy | purpose, authorized data use, minimization, retention and deletion; legal interpretation remains human |
| Continuous Compliance | scoped applicability, controls, evidence, assessment, findings and POA&M; no universal compliant badge or audit opinion |
| Supply-Chain Integrity | source/build provenance, artifact verification, admission and revocation; producer cannot self-authorize |
| Delivery Effectiveness | canonical DORA flow/stability/rework outcomes; no person/team ranking |
| Knowledge Quality | impact of Omniscience-published provenance/freshness/conformance/coverage/conflict state; Omniscience keeps semantic source truth |
| Capacity, Performance & Sustainability | demand/supply feasibility, headroom, performance and method-bound environmental condition |
| Toil | aggregate workflow friction, interrupt load and durable relief; no workforce surveillance |
| Product Outcomes | human-owned outcomes and valid experiments under hard guardrails; no autonomous KPI optimizer |

Adding a pack requires a local domain SPEC and manifest review. It is not a generic runtime plugin or an
unreviewed prompt.

### D4 — Preserve orthogonal state and typed degradation

Every loop keeps at least:

```text
DomainOutcomeCondition
EvidenceCondition
PolicyCondition
LoopHealthCondition
ActionEffectCondition
VerificationCondition
```

Missing, stale, partial, severed, foreign, incompatible, conflicting or insufficient evidence never
becomes zero, false, healthy, efficient, compliant or successful. Last-known-good after expiry is
historical. Domain packs expose granular conditions and reasons; there is no global management score.

### D5 — Make constraints directional and non-compensating

Packs publish typed facts or `allow | deny | unknown` constraints with scope, policy/evidence revision,
reason, freshness and expiry. Hard reliability, security, privacy, compliance and safety requirements
are vetoes. Cost, speed, utilization or product gain cannot compensate for a hard denial or unknown.
Contradictions open an explicit conflict case owned by human policy authorities; agent consensus does
not resolve policy.

### D6 — Treat agents as an ephemeral role family

There may be many investigator, challenger, planner, verifier-support and learning agents per domain.
They receive exact, budgeted, scope/revision-bound work through leases and fencing, cite evidence, and
publish non-authoritative assessments. They own no durable truth, policy, risk acceptance, action
permission or outcome verdict. A model vote cannot turn an inference into fact.

### D7 — Keep evidence, evaluation, authorization, effect and verification separate

Barbarossa admits immutable source-bound evidence and evaluates it with a domain-owned deterministic
artifact against exact policy. A case can coordinate assessments and proposals. Human or owner policy
joins separately before any action request. Omnius re-authorizes and owns execution, returning an
integrity-bound effect receipt. Barbarossa then uses new, precommitted, sufficiently independent
observations to verify the managed outcome and required guards. Executor success cannot close a case.

### D8 — Keep Omniscience and Omnius severable

Omniscience may publish versioned, cited `ManagementContextBundle` records and, for Knowledge Quality,
the authoritative `KnowledgeQualitySnapshot`. Context supports reasoning; it does not create a domain
fact, verdict, authorization, receipt or closure. Its loss reduces context/knowledge coverage and
cannot suppress other loops.

Omnius owns action planning/execution, identities, idempotency, receipts and reconciliation. Its loss
removes governed execution, not observation/evaluation/case/alert capability. Producer work must be
specified and released in its owning repository before a Barbarossa live adapter can activate.

### D9 — Make Platform Portal the Continuous Management Center

Barbarossa owns a narrow local cockpit for loop/evaluator/source health, active cases, one case detail,
agent queues/leases/dead letters and safe local maintenance. It stays useful when Portal is unavailable.

Platform Portal composes the fleet-wide Continuous Management Center: loop and domain posture, evidence
coverage/freshness, cross-loop constraints and conflicts, cases, assessments, actions/receipts,
verification and realized outcomes. Portal may submit owner-delegated intents but cannot recompute
domain truth, extend freshness, grant authority or make its availability part of loop correctness.

### D10 — Apply the PII Wall to every management boundary

Telemetry, billing/allocation, security findings, personal data use, audit evidence, delivery events,
work observations, experiments, prompts, context, cases, alerts, receipts and projections are not
implicitly safe. Every admission, durable store, model/tool context, owner adapter, external provider
and view uses a pinned purpose/recipient/classification/transformation policy and non-identifying
receipt. Unknown classification or purpose blocks release and reports reduced coverage.

### D11 — Gate autonomy per domain and action class

Initial packs are observe/evaluate/assist. Progressive autonomy never promotes Barbarossa globally.
Each exact domain/action profile needs human-published objectives and constraints, live positive and
forced-negative evaluation, independent observation, distinct identities, deterministic preconditions,
exclusive fenced permit, blast-radius/rate/cost limits, dry-run/canary where possible, rollback and
kill switch, outcome verification and automatic downgrade on drift or evidence loss.

### D12 — Keep local SPECs independently assignable

Barbarossa owns the 29-capability kernel/domain catalog and task queue referenced by the synchronized
registry. A component agent can implement one contract/mock slice using local files and a stable link
to this plan; it never needs writable access to `genai-enablement` or a sibling. Omniscience, Omnius and
Platform Portal must publish their own producer/action/view SPECs. Acceptance of this ADR authorizes
adoption and planning, not live operation.

## Cross-repository invariants

- **CMP-1:** no component, model, executor or UI certifies its own managed outcome.
- **CMP-2:** no favorable current state exists without fresh required evidence and active policy.
- **CMP-3:** facts, deterministic verdicts, agent assessments, human decisions, authorizations, effects
  and independent verification remain distinct records.
- **CMP-4:** no global efficiency score or weighted average can override a hard domain constraint.
- **CMP-5:** every exchanged fact/constraint is scope, producer, contract, policy, time, coverage and
  integrity bound.
- **CMP-6:** domain packs share kernel mechanics but not truth, policy, credentials or readiness.
- **CMP-7:** stale agents are fenced; duplicate work is safe; duplicate external mutation is forbidden.
- **CMP-8:** Omniscience, Omnius and Portal are severable and their loss is typed, never hidden.
- **CMP-9:** raw or purpose-unknown protected data does not reach ledgers, agents, models or projections.
- **CMP-10:** an effect receipt is not a verified outcome or realized benefit.
- **CMP-11:** product, legal, risk, finance and policy trade-offs remain human-owned.
- **CMP-12:** no draft, fixture, mock, test pass, document status or agent approval activates live authority.

## Consequences

### Positive

- One reusable management kernel replaces repeated orchestration and evidence plumbing.
- Domain policy and authority remain independently reviewable and deployable.
- Reliability constraints prevent efficiency optimizers from silently increasing systemic risk.
- Many specialized agents can scale without distributing durable truth into prompts.
- Platform Portal receives one coherent, source-bound management model without becoming authority.
- Realized outcomes are distinguished from proposals, action receipts and forecast benefits.

### Costs and trade-offs

- Barbarossa becomes a larger platform product with strong isolation and its own reliability surface.
- Every domain still requires expert owners, explicit semantics, sources, evaluator and qualification.
- Cross-loop constraint conflicts require human governance and may intentionally block optimization.
- Independent observations, durable evidence and verification increase infrastructure and operating cost.
- Generic kernel evolution must preserve compatibility without flattening domain meaning.

## Alternatives rejected

- **Keep Barbarossa reliability-only:** duplicates the same safe loop mechanics in multiple systems.
- **One omnipotent optimization agent:** combines nondeterminism, truth and mutation authority.
- **One global efficiency score:** permits compensation across incomparable or protected outcomes.
- **Make Omnius the management plane:** execution failure or incentives could suppress independent judgment.
- **Make Omniscience the management plane:** contextual knowledge would become operational authority.
- **Compute outcomes in Platform Portal:** UI availability and interpretation would become correctness.
- **Centralize every raw signal:** creates PII, availability and governance concentration without need.

## Primary engineering references

- Google SRE, [Site Reliability Engineering](https://sre.google/sre-book/table-of-contents/) and
  [The Site Reliability Workbook](https://sre.google/workbook/table-of-contents/) — reliability loops,
  SLOs, load, toil and safe operations.
- FinOps Foundation, [FinOps Framework](https://www.finops.org/framework/) and
  [FOCUS](https://focus.finops.org/focus-specification/) — cost/value practice, unit economics and
  interoperable billing semantics.
- NIST, [AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework),
  [SP 800-137](https://csrc.nist.gov/pubs/sp/800/137/final), and
  [Privacy Framework](https://www.nist.gov/privacy-framework) — continuous AI, security and privacy
  governance.
- NIST, [OSCAL](https://pages.nist.gov/OSCAL/) and
  [SP 800-53A](https://csrc.nist.gov/pubs/sp/800/53/a/r5/final) — machine-readable control and
  assessment evidence.
- SLSA, [Specification v1.2](https://slsa.dev/spec/v1.2/) and NIST,
  [SSDF](https://csrc.nist.gov/pubs/sp/800/218/final) — software supply-chain integrity.
- DORA, [Research](https://dora.dev/research/) — delivery performance and improvement.
- W3C, [PROV-O](https://www.w3.org/TR/prov-o/), [SHACL](https://www.w3.org/TR/shacl/) and
  [DQV](https://www.w3.org/TR/vocab-dqv/) — provenance, conformance and data-quality vocabulary.
- Green Software Foundation,
  [Software Carbon Intensity](https://sci.greensoftware.foundation/) — method-bound software carbon
  condition.

## Acceptance gate

Before acceptance:

1. human owner reviews the 12-domain boundary and non-compensating constraint rule;
2. Barbarossa local ADR-0002 and its 29-spec registry remain aligned with this decision;
3. synchronized registry/plan checks pass against all available sibling projects;
4. Omniscience, Omnius and Platform Portal producer/action/view gaps remain explicit work packages;
5. the PII Wall boundary applies to every domain class; and
6. no wording implies that planning completeness or ADR acceptance grants live authorization.
