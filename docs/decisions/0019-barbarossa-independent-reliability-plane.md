# ADR-0019: Barbarossa is the independent synchronized-platform reliability plane

- **Status:** Superseded by [ADR-0020](0020-barbarossa-continuous-management-plane.md)
- **Date:** 2026-07-19
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `Barbarossa`, `Omniscience`, `omnius`,
  `platform-portal`, and synchronized-platform observability producers)
- **Builds on:** [ADR-0001](0001-continuous-detection-sentinel.md),
  [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0010](0010-goal-oriented-organizational-dark-factory.md),
  [ADR-0011](0011-platform-products-and-executable-paths.md),
  [ADR-0012](0012-capability-readiness-profiles.md),
  [ADR-0013](0013-platform-owned-observer-access.md), and
  [ADR-0017](0017-omniscience-mcp-v1-contract-and-severance.md)
- **Related proposals:** [ADR-0007](0007-platform-portal-federated-surface.md),
  [ADR-0008](0008-ai-security-domain.md),
  [ADR-0018](0018-pii-wall-purpose-bound-data-boundary.md)

> Historical note: this decision remains the design basis for Barbarossa's Reliability domain pack.
> ADR-0020 supersedes only the product boundary by generalizing the same independent, evidence-driven
> loop mechanics across multiple management domains.

## Context

The synchronized platform has strong but separate reliability building blocks:

- the Autonomous SRE harness and deterministic Sentinel detector families in `genai-enablement`;
- component telemetry and local health surfaces;
- Omniscience topology, evidence, history, and runbook context;
- governed Omnius execution and outcome receipts; and
- Platform Portal cross-component visualization.

They do not yet define one independent owner for determining whether complete platform journeys are
available. Component readiness does not prove a user/operator outcome: a UI or asynchronous path can
fail while every participating service reports healthy. Conversely, putting availability judgment in an
observed component lets that component participate in its own certification.

The existing phrase `SRE agent` is also ambiguous. A single long-lived model would be a failure point and
an authority leak. Many agents improve investigative coverage, but their agreement is not physical
evidence and their disagreement must not make current state disappear.

The platform needs a reliability plane whose critical observation/evaluation/alert path stays useful
when Omnius, Omniscience, Portal, an individual worker, or part of the telemetry path is unavailable.

## Decision if accepted

### D1 — Add Barbarossa as a first-class synchronized-platform component

`Barbarossa` is the separately owned and deployable reliability plane. It owns platform critical-journey
measurement, reliability evidence admission, deterministic availability/error-budget snapshots,
incident state, SRE-agent work coordination, alert delivery, meta-monitoring, and component-owned read
projections.

`genai-enablement` keeps the cross-repository decisions, work-package order, reusable Autonomous SRE
harness, eval framework, and Sentinel algorithms. It does not become the live availability issuer.

### D2 — Define `SRE agent` as a role family

There may be many probe, investigator, challenger, coordinator, communications, and learning agents.
Instances are ephemeral workers. They own no durable cross-task truth and receive only exact,
scope/policy/revision-bound work through Barbarossa.

A deterministic evaluator, not an agent or agent vote, is the sole issuer of authoritative
`AvailabilitySnapshot`, `ErrorBudgetSnapshot`, and policy-derived `IncidentDeclaration`.

### D3 — Measure critical platform journeys, not component-health averages

Each active `PlatformJourneyDefinition` is human-published and binds:

- user/operator objective and exact start/success/failure semantics;
- realm/environment and product/reliability owners;
- SLI calculation and approved SLO/error-budget policy reference;
- observation windows, exclusions, maintenance and low-traffic behavior;
- required evidence source classes, independent probe vantage count, freshness and coverage; and
- schema/policy revision, activation, expiry and integrity.

Component liveness/readiness, metrics, logs, traces, controller state, and topology are evidence for
diagnosis. None alone or in aggregate defines platform availability.

### D4 — Separate evidence, deterministic judgment, and agent reasoning

Barbarossa admits source-bound `ReliabilityObservation` records into an append-only evidence ledger.
Black-box probes represent externally visible symptoms. White-box component facts help identify causes,
masked failures, capacity risk, and change correlation.

The deterministic evaluator consumes an exact journey-policy revision and immutable evidence set.
Agents publish `SREAssessment` records containing cited hypotheses, alternatives, uncertainty,
diagnostics and proposals with `authoritative=false`. An assessment cannot rewrite evidence, calculate
an authoritative health state, authorize action, or close an incident.

### D5 — Preserve three orthogonal condition axes

Every current assessment carries:

```text
ServiceCondition     = available | degraded | unavailable | unknown
ObservationCondition = complete | partial | severed
BudgetCondition      = ok | burning | exhausted | undefined
```

These axes do not collapse into one inferred green value. Missing, stale, conflicting, future-dated,
foreign-scope, incompatible, or insufficiently covered evidence cannot produce current `available`.
After expiry, last-known-good is historical evidence only.

### D6 — Keep the critical path independently operable

The critical `probe -> admit -> evaluate -> persist -> alert` path:

1. has separate workload identity and least-privilege credentials;
2. uses at least one probe/failure domain outside the observed platform for critical journeys;
3. does not require Omniscience, Omnius, or Platform Portal;
4. uses durable, replayable evidence and incident state;
5. reports collector/queue/drop/freshness/coverage health independently from service condition; and
6. has an external watchdog that proves the complete alert path.

Omniscience loss degrades diagnostic context. Omnius loss removes governed execution. Portal loss removes
the composed UI. None suppresses deterministic detection or critical alerting.

### D7 — Coordinate many agents with durable at-least-once work

Work partitions by realm, journey, incident and role. Each immutable `SREWorkItem` binds exact input
snapshot/evidence references, allowed sources/tools, policy/model profile, budget, deadline,
idempotency key, priority and retry limit.

Claim/renew/takeover uses leases with monotonically increasing fencing epochs. A stale worker cannot
publish or continue tools after losing its lease. Redelivery is expected; result publication is
idempotent and a reused key with changed intent is a conflict.

There is no global agent leader. One active incident coordinator lease serializes incident workflow;
many investigators/challengers may operate concurrently.

### D8 — Keep incident command and mutation authority explicit

Incident state separates observations, deterministic impact, agent inference, human decision, external
effect, and post-action verification. Current Incident Commander, Operations, Communications, and
Planning roles are explicit, expiring, auditable assignments.

An automated coordinator may advance allowed workflow and assign read-only work. It cannot self-grant
human command or production mutation authority.

### D9 — Keep Omniscience severable and source-bound

Omniscience may publish a versioned `ReliabilityContextBundle` with topology, changes, history,
runbooks, similar incidents, citations, coverage, source health, and freshness. Barbarossa pins the
producer contract/release and revalidates scope and PII class.

Context can support or contradict a hypothesis. It cannot create an observation, availability snapshot,
incident transition, approval, effect receipt, or closure. Missing context reduces diagnosis coverage
and never means healthy.

### D10 — Delegate execution to Omnius and verify independently

Barbarossa may convert a non-authoritative proposal into a bounded `MitigationRequest` only after exact
policy and human/owner authority joins. Omnius re-authorizes current intent, owns planning/execution and
returns an integrity-bound receipt. Timeout is pending reconciliation and retries reuse one idempotency
identity.

Owner-reported success is not recovery. Barbarossa observes the journey through its independent path and
issues a fresh snapshot before incident closure policy can be satisfied.

### D11 — Make Platform Portal the Reliability Center, not the reliability authority

Barbarossa keeps a narrow local cockpit for probe/source/evaluator/alert health, active incidents, one
incident detail, agent fleet/queue/lease/dead-letter state, and safe component-local maintenance.

Platform Portal composes the detailed cross-platform Reliability Center from Barbarossa read
projections: journey conditions, SLO/error-budget burn, observation coverage, incidents, evidence
freshness, agent work, alerts, actions and receipts. It cannot recompute availability, reinterpret
assessments as facts, extend snapshot freshness, or make Barbarossa availability part of another
component's correctness.

### D12 — Start assisted and gate progressive autonomy separately

The initial profile is read-only/assisted:

- deterministic policy may declare an incident;
- agents investigate and propose;
- humans retain command and high-risk approval;
- Omnius performs exact authorized actions; and
- Barbarossa independently verifies outcomes.

Bounded autonomous mitigation is a separate Barbarossa SPEC and work package. Promotion requires
human-published scenario/action policy, immutable live evaluation with uncertainty, distinct identities,
deterministic preconditions, exclusive fenced permit, dry-run/canary where possible, blast-radius/rate/
cost limits, rollback and kill switch, forced-negative drills, continuous observation, and automatic
downgrade on drift or evidence loss.

### D13 — Apply the PII Wall to operational evidence

Telemetry, logs, traces, exception text, incident chat, prompts, documents, alerts, assessments and
receipts are not implicitly PII-free. Barbarossa enforces the pinned PII policy before its ledger,
agent/model context, alert, local UI, portal projection, external provider, archive or backup.

Cross-component contracts prefer safe references, digests, counts and scoped pseudonyms. Unknown or
unsafe content is blocked or quarantined without echoing raw values into errors or telemetry.

### D14 — Require local SPECs, task selection, and real-path evidence

Acceptance of this ADR would authorize component adoption and contract work, not live operation.
Barbarossa owns its capability index and independently claimable task SPECs. Omniscience, Omnius, and
Platform Portal must author their own producer/consumer/action/view SPECs before live integration.

The first live Barbarossa profile requires:

1. one human-published journey/SLO/error-budget policy;
2. independent black-box and owner evidence with PII-safe admission;
3. deterministic positive, negative, partial, severed, stale, conflict and low-traffic calibration;
4. durable ledger/queue/incident recovery with lease/fencing drills;
5. external end-to-end alert watchdog;
6. read-only identities and severance drills for all optional components; and
7. an immutable exact capability/task/readiness selection and owner evidence.

## Cross-repository invariants

- **BAR-1:** component self-report is evidence, never its own platform availability verdict.
- **BAR-2:** current green requires fresh required evidence; blindness is unknown/severed.
- **BAR-3:** LLM output never supplies SLO policy, availability, incident closure, or authorization.
- **BAR-4:** agent plurality improves coverage but does not create consensus authority.
- **BAR-5:** a stale lease holder cannot publish or mutate after fenced takeover.
- **BAR-6:** duplicate critical alert is preferable to a silently missed alert; duplicate mutation is
  forbidden.
- **BAR-7:** Omniscience, Omnius, and Portal are severable from critical detection/alerting.
- **BAR-8:** effect receipt and independently observed recovery are different facts.
- **BAR-9:** every cross-component record is scope/revision/time/coverage/integrity bound.
- **BAR-10:** operational evidence crosses the PII Wall before durable/model/external propagation.
- **BAR-11:** Portal composes Barbarossa truth and never recalculates it.
- **BAR-12:** no draft, fixture, mock, test pass, or agent approval activates live authority.

## Consequences

### Positive

- One component has clear accountability for whole-platform journey availability.
- Detection remains available during failure of knowledge, execution, or visualization components.
- Many agents can scale independently without distributing authoritative truth into prompts.
- Unknown and observation failure become visible rather than false green.
- Actions retain owner authorization and independent post-effect verification.

### Costs and trade-offs

- A new component, trust boundary, durable state, on-call surface, and self-SLO must be operated.
- Critical-journey and end-to-end evidence are more expensive than component checks.
- At-least-once work/alert delivery requires deduplication, reconciliation and fencing.
- Separate failure domains and external watchdogs increase infrastructure and operational cost.
- Product owners must explicitly decide journeys, targets, exclusions and error-budget consequences.

## Alternatives rejected

- **One global SRE agent:** nondeterministic singleton and combined authority/failure point.
- **Agent majority vote:** measures correlated reasoning, not observed behavior.
- **Host SRE inside Omnius:** execution failure could suppress detection of itself.
- **Host availability inside Omniscience:** severable context becomes correctness authority.
- **Compute health in Platform Portal:** view availability becomes part of platform correctness.
- **Average component health:** misses cross-component, UI and asynchronous user outcomes.
- **Centralize all raw telemetry in Barbarossa:** duplicates observability systems and creates a PII/
  availability concentration point; Barbarossa stores normalized evidence or safe references.

## Primary engineering references

- Google SRE, [Product-Focused Reliability for SRE](https://sre.google/resources/practices-and-processes/product-focused-reliability-for-sre/)
  — product journeys and end-to-end outcomes exceed service health.
- Google SRE, [Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
  — black-box symptoms, white-box causes, simple actionable paging.
- Google SRE Workbook, [Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)
  — multi-window/multi-burn-rate alerts and low-traffic strategies.
- Google SRE, [Distributed Periodic Scheduling](https://sre.google/sre-book/distributed-periodic-scheduling/)
  — durable coordination, partial failures, idempotency and state lookup.
- AWS Builders' Library,
  [Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
  — caller intent/idempotency identity and semantically equivalent retry.
- Prometheus, [Alertmanager high availability](https://prometheus.io/docs/alerting/latest/high_availability/)
  — fail-open, at-least-once critical notification delivery.
- OpenTelemetry, [Collector internal telemetry](https://opentelemetry.io/docs/collector/internal-telemetry/)
  — queue, refusal, failure and data-flow meta-monitoring.
- Google, [How Google SRE is using agentic AI](https://cloud.google.com/blog/products/devops-sre/how-google-sre-is-using-agentic-ai-to-improve-operations/)
  — strong identities, SLOs, backup paths, transparency and continuous evaluation for SRE agents.

## Status and authority

This ADR is Proposed. The user's decision to create a separate project named Barbarossa fixes the project
direction and name; it does not by itself accept every policy and interface in this proposal. No
component ADR/SPEC status, runtime identity, source, credential, SLO target, alert route, deployment,
incident authority, action, readiness profile, or production state changes until separately approved.
