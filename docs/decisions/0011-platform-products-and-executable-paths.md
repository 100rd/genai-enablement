# ADR-0011: Platform products are delivered through versioned executable paths

- **Status:** Accepted
- **Accepted by:** `@100rd` through explicit owner decision on 2026-07-13
- **Date:** 2026-07-13
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `omnius`, `Omniscience`, `platform-design`,
  `platform-portal`, `platform-workflows`; `multiqlti` may consume and prove candidate paths)
- **Extends:** [ADR-0010](0010-goal-oriented-organizational-dark-factory.md)

## Context

Current platform-engineering work is converging on two related directions: AI-powered platforms and
platforms for AI workloads. Agentic Development Platform proposals further separate existing IDP
tooling, executable path specifications, and the agent infrastructure/harness that dispatches them.
These are useful directional signals, but not proof that one monolithic product should own the portal,
catalog, observability, incident response, infrastructure, and agent runtime.

The platform already has the necessary ownership boundaries. What is missing is an explicit product
contract between a user's desired outcome and omnius's goal-oriented WorkOrder. `EntityClass` describes
typed platform entities, but does not by itself describe the complete delivery/operations path that
turns a request into a running, verified product.

## Decision

### D1 - Treat the platform as a product portfolio

The platform exposes outcome-oriented **PlatformProducts**, not raw cloud resources. Initial product
families include environments, standard services, data access, and later inference workloads. A product
has an owner, consumers, support boundary, version, documentation, SLO, cost model, adoption metrics,
and retirement lifecycle.

Platform engineers own primitives, contracts, policies, and paths. Application/ML engineers and AI
agents consume the same products through typed requests. Consumer simplicity must not move safety or
operational complexity into an undocumented backend.

### D2 - Separate PlatformProduct, EntityClass, and PlatformPath

| Artifact | Owns | Example |
|---|---|---|
| **PlatformProduct** | user-visible supported outcome and service promise | Standard HTTP Service |
| **EntityClass** | versioned schema/lifecycle for a typed building block or instance | Service, Environment, InferenceRuntime |
| **PlatformPath** | executable A-to-Z contract that realizes/operates a product | `standard-http-service/v1` |

A PlatformProduct composes EntityClasses and one or more PlatformPaths. An EntityClass is not a
workflow. A PlatformPath is not a microservice or agent prompt. It is a versioned contract compiled
into an omnius WorkOrder execution graph.

### D3 - Human and agent consumers use the same contract

Portal, CLI, chat, MCP, API, Jira, and agent callers submit the same versioned product/path request.
Identity, Realm, policy, budget, and approval may produce different authorization outcomes, but the
schema and Condition of Done do not fork into human and agent variants.

Natural language may discover or populate a contract. It never replaces the committed structured
request or grants apply authority.

### D4 - Keep the five architectural planes separate

```text
Experience plane
  platform-portal / CLI / chat / MCP / Jira

Decision and contract plane
  genai-enablement ADRs / local ADRs and SPECs / product and path schemas

Organizational factory plane
  omnius assessment / WorkOrders / policy / verification / durable orchestration

Knowledge and operations plane
  Omniscience platform state / omnius execution memory / AI SRE incidents

Execution plane
  Git / platform-workflows / Terraform / Argo CD / Kubernetes and cloud controllers
```

These are ownership planes, not a mandate for five deployments. Existing products own their facts and
mechanisms. omnius coordinates them through contracts; it does not reimplement a service catalog,
observability backend, incident manager, GitOps controller, or inference platform.

### D5 - PlatformPath is closed, versioned, and executable

A path contract declares at least:

```yaml
schemaVersion: platform/path/v1
kind: PlatformPath
metadata:
  name: standard-http-service
  version: v1
  owner: platform-team
product: standard-service
inputs: {}
entityClasses: []
supportedRealms: []
workflow: []
policies: []
conditionsOfDone: []
compensation: {}
evidence: {}
```

Inputs are bounded and machine-validatable. The workflow references approved delivery mechanisms and
skills rather than embedding unrestricted shell commands. Conditions of Done use registered probes.
Unknown fields, unresolved versions, missing owners, and unsupported Realms fail closed.

Path definitions originate in the owning platform repository, are reviewed through Git, and are
indexed into Omniscience. `genai-enablement` owns the cross-repo decision/schema vocabulary and portfolio
map, not copies of each executable path.

### D6 - Paths earn promotion and never mutate consumers silently

PlatformPath lifecycle is:

```text
draft -> experimental -> validated -> approved -> deprecated
```

Evidence is accumulated through preview/development/staging before broader Realm admission. An existing
WorkOrder pins an exact path revision. A new path version does not alter existing products/instances or
active WorkOrders; migration is its own WorkOrder with compatibility and compensation evidence.

### D7 - AI/inference is a first-class product family, not Dark Factory internals

Inference endpoints, embedding services, batch inference, model-runtime profiles, scaling, quotas, data
classification, and cost envelopes may be modeled as PlatformProducts/EntityClasses/Paths. Their
runtime implementation belongs to the platform execution plane. omnius delivers and operates them like
other governed products; LiteLLM used by omnius's reasoning pool is not the customer inference platform.

The first verified vertical remains a standard application in `preview-*`. An inference product/path is
the second product vertical, admitted only after the common contract, policy, artifact-promotion, and
runtime-probe path works.

### D8 - Logical capabilities do not imply a microservice inventory

Request gateway, catalog projection, contract validation, policy, orchestration, agent runtime,
execution adapters, observability, and recommendations are useful capability labels. They are not nine
services to build for v1. A component is split only for independent scaling, security boundary,
availability, ownership, or lifecycle reasons supported by evidence.

### D9 - Self-architecture means governed proposals

Feedback may cause omnius to propose a new PlatformProduct, EntityClass, PlatformPath, default, skill,
policy, or verifier. It must create a traceable ADR/SPEC/PR with outcome evidence. It cannot silently
promote the proposal, redefine its oracle, or modify organizational authority. Low-risk path-body
changes may follow explicitly accepted policy; boundary and policy changes remain human-owned.

### D10 - Product and factory metrics are both required

Platform product metrics include request-to-ready lead time, successful self-service share, path/template
reuse, adoption, support load, cost per product instance, policy rejection reasons, and consumer
experience. Factory trust metrics remain probe-defined completion, escapes, false-pass/false-fail,
human intervention, compensation, and cost per verified WorkOrder.

No single adoption or speed metric may authorize autonomy. A faster path with worse delivery stability,
cost, or escape rate is not successful.

### D11 - Rollout proves one path before product breadth

1. Define the minimal product taxonomy and `standard-http-service/v1` path.
2. Deliver it from chat/MCP request through immutable preview artifact and runtime probes.
3. Measure reuse, lead time, interventions, cost, and escapes.
4. Add `inference-service/v1` using the same product/path contract and AI-specific quota/data/cost
   policy.
5. Admit optimization proposals only after outcome and attribution quality are proven.

## Consequences

**Positive**

- Product thinking becomes an executable contract rather than portal branding.
- Humans and agents consume the same supported platform surface.
- AI workload support can grow without coupling customer inference to omnius internals.
- Existing platform products remain owners of runtime truth and execution mechanisms.

**Costs and risks**

- The organization must curate a small portfolio rather than accept arbitrary product/path growth.
- Path/version compatibility and retirement become governed lifecycle work.
- Product metrics require reliable joins from request through deployment and runtime outcome.
- A poorly designed path can scale a bad default; staged promotion and escape learning are mandatory.

## Evidence quality

The Platform Engineering reports and Agentic Development Platform material are directional industry
evidence, not normative standards. Survey results and vendor/community reference architectures support
the problem framing and path-layer concept. Unverified promotional numbers are not used as acceptance
thresholds or economic assumptions.

## Implementation map

| Component | Responsibility |
|---|---|
| `genai-enablement` | product/path vocabulary, cross-repo ADRs, portfolio implementation map |
| `omnius` | path binding, assessment, WorkOrder compilation/execution, policy and evidence |
| `platform-design` | authoritative path implementations, EntityClasses, execution mechanisms |
| `platform-workflows` | reusable validation, build, promotion, and evidence workflows |
| `platform-portal` | common product/path request and status projection; no decision authority |
| `Omniscience` | indexed products/entities/paths and observed platform/outcome state |
| `multiqlti` | interactive path research/prototyping and evidence-backed promotion proposals |

## References

- [State of AI in Platform Engineering 2025](https://platformengineering.org/reports/state-of-ai-in-platform-engineering-2025)
- [Architecting Agentic Development Platforms](https://platformcon.com/sessions/architecting-agentic-development-platforms)
- [The rise of agentic platforms](https://platformengineering.org/blog/the-rise-of-agentic-platforms-scaling-beyond-automation)

