# ADR-0010: Organizational Dark Factory is goal-oriented and policy-governed

- **Status:** Accepted
- **Accepted by:** `@100rd` through explicit owner decisions on 2026-07-11
- **Date:** 2026-07-11
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `omnius`, `multiqlti`, `Omniscience`,
  `platform-design`, `platform-portal`, with enforcement supplied by `platform-workflows`)
- **Extends:** [ADR-0009](0009-organizational-dark-factory-sdd.md)

## Context

ADR-0009 established the authority boundary: humans decide through ADRs, accepted SPECs make
decisions executable, and agents cannot redefine the oracle that judges their work. That boundary is
necessary, but a ready task SPEC is not the only useful entry point for an organizational factory.

Engineers receive goals, incidents, alerts, tickets, questions, and incomplete problem statements. A
factory that only executes pre-written tasks moves the hardest engineering work back to the requester:
understanding the problem, locating affected systems, deriving completion conditions, decomposing the
work, delivering it, and proving the runtime outcome.

The platform also contains two intentionally different Dark Factory products. `multiqlti` is a
personal, interactive factory that can complete work A-to-Z while allowing pauses and live changes to
research, ADRs, and SPECs. `omnius` is the organizational factory: one logical control plane per
organization, governed by policy, durable execution, independent evidence, and Realm-scoped authority.

## Decision

### D1 - Both multiqlti and omnius are full Dark Factories

`multiqlti` is the personal tier. It supports research, experimentation, interactive redirection, and
full delivery with a human participating throughout the loop. Its personal memory and lessons may be
promoted to the organization only through reviewed artifacts.

`omnius` is the organizational tier. It accepts work through chat, MCP/API, Jira, repository events,
AI SRE orders, and governed event connectors. It owns everything needed to finish an admitted goal,
including investigation, code and IaC changes, PR/MR orchestration, CI/CD, Argo CD delivery, runtime
tests, evidence, and compensation. A merge is an intermediate event unless the committed Condition of
Done explicitly ends at merge.

Patterns move in both directions through PRs to the shared skills, policy, and verifier registries.
Personal or production memory is never copied wholesale.

### D2 - Every input normalizes to a durable WorkOrder

All channels use one closed, idempotent contract. A WorkOrder records source identity, correlation,
intent, constraints, priority, candidate Realms, budget, and lifecycle. Duplicate webhooks, retries,
alerts, and semantically overlapping orders cannot create duplicate side effects.

Conversation is not execution. The operations `ask`, `investigate`, `plan`, `propose-order`, and
`commit-order` are distinct. The transition from `proposed` to `committed` is explicit and authorized by
the caller's identity plus policy. Asking through UI or MCP never grants more rights than another
channel. Status and evidence return to the originating channel.

### D3 - A SPEC is mandatory before mutation, but need not be the initial input

For a ready-SPEC intake, omnius validates the supplied contract. For a goal, alert, ticket, or dialogue
intake, omnius first runs a bounded discovery/assessment stage and produces or repairs the task SPEC.
Discovery may read authorized sources, run local experiments, and create disposable previews; it may
not mutate a persistent Realm before Realm, blast radius, policy, and completion conditions resolve.

Before mutating execution begins, omnius freezes an immutable execution contract containing:

- the goal and exact scope;
- resolved Realm and effective policies;
- task class, assurance profile, and autonomy limit;
- Condition of Done and registered probes;
- execution graph, budgets, credentials, and compensation posture;
- pinned ADR, capability SPEC, skill, tool, policy, model, prompt, and verifier revisions.

The requester may provide completion conditions. AI may derive them during assessment. The producing
identity cannot change them after execution starts. AI-authored criteria require independent validation
and the readiness authority required by task risk and Realm policy.

Low-risk policy may authorize an automatically repaired SPEC revision after complete revalidation.
Higher-risk repairs require the approval encoded by policy. Unknown, conflicting, or unmeasurable
conditions fail closed or become a bounded research WorkOrder.

### D4 - Completion is probe-defined and end-to-end

Condition of Done and its probes exist before implementation. Passing them, not a post-hoc subjective
review, completes the engineering WorkOrder. Human authority is exercised when the intent, oracle, or
high-risk policy is approved before execution.

For example, "create a Brazil production region" is not done after a Terraform PR merges. It is done
only after the infrastructure is applied through approved delivery mechanisms, the required production
applications are promoted by immutable artifact digest, security and observability controls exist, and
the declared runtime probes pass.

Research completion proves process quality - question coverage, primary evidence, citations,
reproducibility, alternatives, uncertainties, and budget - not the objective truth of every conclusion.

### D5 - AI SRE and omnius have separate ownership

Observability sends normalized actionable alerts, not the raw telemetry firehose, to AI SRE. AI SRE
correlates and diagnoses the operational case, retrieves supporting logs/metrics/traces as needed, and
owns incident state:

```text
detected -> investigating -> mitigated -> remediated -> verified -> closed
```

AI SRE may execute pre-authorized runtime runbooks and emergency mitigation under the same policy model
as an engineer. A known rollback can precede the full SDD path, followed by retrospective evidence.
Changes to Git, application code, IaC, delivery configuration, detectors, or runbooks become omnius
WorkOrders. omnius performs the engineering work; AI SRE verifies the external runtime outcome and
closes the incident. A self-resolved capacity event need not manufacture a patch.

### D6 - Memories and platform state are different systems

Each factory owns durable intra-loop state, task history, and cross-task learning. `multiqlti` memory is
personal; `omnius` memory is organizational execution experience. Active loop state is an evented,
recoverable control-plane record, not an LLM conversation buffer.

Omniscience is the read-only state-of-platform knowledge plane: declared and observed code,
infrastructure, topology, deployments, incidents, and evidence provenance. Authoritative declarations
remain in Git, service catalogs, delivery systems, and runtime sources; Omniscience ingests and relates
them. omnius publishes outcomes through those authoritative event/source paths rather than directly
rewriting the graph.

Memory access is isolated by Realm, team, and sensitivity. Platform facts and task memories use ABAC
independently. Omniscience loss permits a policy-declared degraded path for low risk; production changes
that require unavailable topology or Realm evidence fail closed.

### D7 - One logical omnius per organization, partitioned by Realm

One organizational control plane prevents independent factories from making conflicting decisions.
It is highly available on Kubernetes, backed by a durable event store, and uses distributed execution
cells. A process, node, cluster, or model failure must not lose or duplicate a step.

A Realm is the policy boundary for an environment or resource class. Realms determine task classes,
autonomy, credentials, networks, gates, budgets, allowed SPEC repair, approvals, and blast-radius
limits. omnius resolves Realm from authoritative declarations, code/IaC, delivery topology, runtime
metadata, and Omniscience. Conflict or insufficient confidence yields `realm_resolution_failed`.

Policy precedence is:

```text
global invariant > Realm deny > authorized emergency grant > resource policy
> task policy > agent request
```

`preview-*` may allow broad autonomous mutation, but cannot override global prohibitions on cross-Realm
access, production credentials, shared-state deletion, or data exfiltration.

### D8 - EntityClass makes organizational standards executable

Applications, environments, datastores, and infrastructure resources declare metadata including owner,
Realm, criticality, dependencies, SLO, data class, deployment mechanism, and rollback capability.
Definitions and instances originate in Git/catalogs and are indexed into Omniscience.

An EntityClass has a versioned lifecycle:

```text
draft -> experimental -> validated -> approved -> deprecated
```

New classes may be proposed automatically. They gain evidence through preview, development, and staging
before policy admits them to production. Existing instances do not silently adopt a new lifecycle
version; migration is a separate WorkOrder. Runtime/declaration drift creates a policy-classified
reconciliation order.

### D9 - Probe reliability is explicit and learns from escapes

Every probe declares the condition it proves, oracle, method, environment, expected result, independence,
failure semantics, and evidence. Reliability considers relevance, coverage, authoritative ground truth,
repeatability, environment fidelity, tamper resistance, freshness, statistical power, and provenance.
Required assurance derives from Realm, risk, blast radius, reversibility, and data impact.

Probabilistic probes declare threshold, observation window, minimum sample size, comparison baseline,
and missing-data behavior. Their result is `pass`, `fail`, `inconclusive`, or `probe-error`; only `pass`
satisfies the condition.

When a post-delivery escape proves a probe gap, the exact probe version becomes contextual
`under-review`, `degraded`, or `quarantined`. omnius creates a regression fixture and a PR to strengthen
the verifier. The replacement must fail on the escaped defect and pass on the corrected implementation.
Mere correlation or an alert cannot poison a probe without independent causal confirmation.

### D10 - Skills guide execution; deterministic controls enforce safety

Shared skills encode best practice for both factories and are pinned by content hash. They may help AI
construct an execution graph, but they are not a security boundary. IAM, policy engines, admission,
CI/CD, Git protection, and external verifiers enforce restrictions.

Changes to shared skills, policy, verifier logic, and safety registries always use PRs with independent
evidence. omnius may propose improvements from its memory but cannot silently self-modify its oracle or
authority.

### D11 - Work execution is durable, concurrent, and compensating

A large WorkOrder is a parent durable DAG of linked capability/task SPECs and cross-repository PRs/MRs,
all joined by one work-order id. Resource and dependency leases serialize conflicting Terraform state,
resources, or contracts while allowing independent streams to run concurrently.

Incident priority may preempt ordinary work at a safe checkpoint. `pause` stops scheduling new steps,
`cancel` invokes policy-defined compensation, and `emergency-stop` revokes leases/credentials and stops
execution cells. Partial success prefers safe roll-forward; full rollback is required only by the
effective safety/integrity policy. Every order has time, model, compute, and cloud-cost budgets; budget
exhaustion pauses or replans rather than fabricating completion.

Execution cells receive short-lived, step-specific, Realm-scoped credentials. Models never receive
standing production secrets. Approved gates may merge without a human when policy permits.

### D12 - Model routing is policy-constrained and engine-independent

omnius uses an in-cluster LiteLLM gateway with provider-supported primary endpoints and Amazon Bedrock
as fallback. Private in-cluster/AWS models are a planned capability, not a current rollout requirement.

AI may request a model for a step; a deterministic router enforces Realm/data policy, capability,
producer/verifier separation, availability, cost, and residency. High-risk verification uses a different
model family/provider where possible. A fallback must satisfy the minimum capability profile or the loop
durably pauses.

Every execution freezes the model identity, prompt, skills, tools, policy, and verifier bundle. Provider
alias drift triggers regression evaluation and restricts high-risk roles until re-certified. LiteLLM is
one logical gateway with Realm-separated credential pools, budgets, routes, and egress policy.

### D13 - Data and destructive operations have global invariants

Schema/data changes use expand-and-contract, compatibility probes, backup/restore evidence, and explicit
data blast radius. Production deletion is two-phase by default:

```text
detach/quarantine -> observation window -> destroy
```

Direct destruction is limited to declared ephemeral classes or an authorized emergency policy. Agent
data access uses audited tools with filtering, masking, query budgets, and step-scoped write authority.

### D14 - Platform learning is bidirectional and evidence-gated

Work outcomes join orders, SPEC revisions, commits, CI/CD runs, deployments, probes, incidents, and
runtime verification in Omniscience. Factory experience records how work was performed and whether it
escaped. Confirmed lessons may change planning within current policy; widening a shared capability
requires a PR.

Lessons and skills may be promoted `multiqlti -> shared -> omnius` and generalized production lessons
may flow `omnius -> shared -> multiqlti`. Promotion strips sensitive task context and requires evidence.

### D15 - Rollout is vertical and measured

The rollout order is:

1. chat/MCP order -> application change -> PR -> immutable preview deployment -> probes;
2. AI SRE engineering order -> omnius patch -> AI SRE runtime verification;
3. multi-repository non-production infrastructure delivery.

Each slice advances through `observe-only -> plan-only -> preview execution -> wider Realm`. Metrics
include probe-defined completion, escapes, verifier false-pass/false-fail, lead/recovery time, human
interventions, compensation, cost per completed order, policy stops, and skill reuse/improvement.

## Consequences

**Positive**

- omnius performs engineering rather than merely executing pre-authored tickets.
- Safety authority remains deterministic even when AI creates or repairs a SPEC.
- AI SRE, omnius, and Omniscience have explicit non-overlapping ownership.
- The platform can learn from outcomes without allowing silent self-modification.

**Costs and risks**

- WorkOrder assessment, Realm resolution, probe curation, and durable orchestration are substantial
  control-plane capabilities.
- One logical organizational factory requires high availability and strict partitioning.
- A broad A-to-Z claim is valid only for certified EntityClasses, Realms, and delivery mechanisms.
- Incomplete metadata or unreliable probes deliberately reduce autonomy and throughput.

## Relationship to ADR-0009

ADR-0009 remains authoritative. This ADR changes the interpretation of "agents execute ready SPECs": a
SPEC is required at the mutation boundary, not necessarily at initial intake. Humans retain authority
over organizational decisions and high-risk readiness. Policy may authorize low-risk readiness and SPEC
repair only inside an accepted human-defined boundary. The producer still cannot redefine its oracle
during execution.

## Implementation map

| Component | Required local adoption |
|---|---|
| `omnius` | WorkOrder, Realm/EntityClass, probe reliability, memory, model routing, durable delivery |
| `multiqlti` | interactive A-to-Z loops, mutable pre-commit artifacts, bidirectional skill promotion |
| `Omniscience` | platform-state/entity/evidence projection with provenance and ABAC |
| `platform-design` | Realm enforcement, execution cells, delivery and destructive-operation controls |
| `platform-portal` | dialogue/order/status/evidence surfaces without decision authority |
| `platform-workflows` | reusable validators, evidence, artifact-promotion, and delivery gates |

