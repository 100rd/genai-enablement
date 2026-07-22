# ADR-0007: Platform portal — a federated tenant-facing surface, not an authority

- **Status:** Accepted
- **Date:** 2026-07-04
- **Accepted:** 2026-07-21 by the platform owner for component development
- **Last reviewed:** 2026-07-21
- **Deciders:** platform owner
- **Scope:** cross-repository compatibility proposal for `platform-portal` and the component contracts
  it consumes; binding for component contract development, but non-authorizing for live integration
- **Governed by:** accepted [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0010](0010-goal-oriented-organizational-dark-factory.md),
  [ADR-0011](0011-platform-products-and-executable-paths.md),
  [ADR-0012](0012-capability-readiness-profiles.md), and
  [ADR-0017](0017-omniscience-mcp-v1-contract-and-severance.md)
- **Compatibility references:** proposed [ADR-0002](0002-platform-skills-registry.md),
  [ADR-0003](0003-unified-sdlc-standard.md), and
  [ADR-0006](0006-unified-loop-decision-model.md); they are not binding through this proposal
- **Vocabulary:** [platform-glossary.md](../platform-glossary.md)

## Context

The platform has several owner-specific human surfaces: factory cockpits, GitHub for diffs and pull
requests, observability products for raw metrics, and Omniscience for shared knowledge. A tenant-facing
experience plane can make product/path requests and project status across those owners without turning
the portal into another factory, knowledge store, policy engine, or execution authority. Accepted
ADR-0011 already places `platform-portal` in the experience plane, and accepted ADR-0009/0010 say that it
projects state and evidence without deciding.

The original ADR described that direction as already binding and as resolving the open multi-factory
shell question in omnius SPEC-UI. That exceeds a Proposed ADR. It also treated proposed ADR-0002/0003 as
accepted constitution, assumed a live portal-side Omniscience token contract, described a smaller portal
database than the implementation now uses, and equated a portal RBAC/step-up check with authorization by
the module that owns an action.

The 2026-07-16 read-only evidence supports a proposal and an adoption plan, not activation:

- `portfolio/projects.json` records `platform-portal` as `proposed`, with no current release or release
  evidence;
- the clean `platform-portal` `main` checkout at `b346f3b...` contains backend, frontend, migrations,
  local topology, CI, tests, and seven component SPECs. Its SPEC index describes all seven segments as
  built and merged against contract mocks, while every component SPEC remains `draft` and owner
  integrations remain explicit release gates;
- every portal SPEC and its index name `ADR-0004` as the charter and link to a nonexistent
  `0004-platform-portal-federated-surface.md`. In this repository ADR-0004 is the Experience Plane and
  this portal proposal is ADR-0007, so adoption traceability is currently invalid;
- the candidate Omniscience broker calls a mock bootstrap endpoint and permits a broader read scope. The
  accepted ADR-0017 bootstrap profile is instead one server-bound workspace with exactly `search` scope;
  it does not grant `platform-portal` mint/broker authority; and
- the local omnius checkout is dirty, its SPEC-UI is draft, and its multi-factory-shell item remains
  deferred. This ADR has not resolved that component-owned item.

Construction evidence is valuable, but a clean merge, test count, mock contract, draft SPEC, or local
stack is not an accepted capability profile, a live owner contract, a release, or portfolio adoption.

## Acceptance boundary and precedence

The platform owner accepted this ADR on 2026-07-21 as the contract boundary for portal development.
Accepted ADR-0009/0010/0011/0012/0017 take precedence over portal component drafts. Proposed
ADR-0002/0003/0006 cannot become binding merely by being cited here.

Acceptance authorizes component-owned SPEC alignment and conformance work. It does not by itself:

- mark a portal SPEC or requirement ready, accept the current implementation, or resolve omnius SPEC-UI;
- publish or activate a component API, token profile, identity realm, database, secret, billing provider,
  cloud resource, deployment, release, product/path, readiness profile, or portfolio status;
- grant the portal an owner credential or make its local RBAC, step-up, cache, audit, or mock response an
  authorization decision; or
- permit auto-merge, production mutation, provider charge, tenant onboarding, external-client service, or
  a success/Done claim without that transition's own authority and exact evidence.

This proposal edit changes no component code or SPEC, repository revision, WorkOrder, readiness decision,
credential, provider/cloud/Kubernetes resource, deployment, release, product catalog, tenant, billing
record, or external policy.

## Decision

`platform-portal` is a tenant-facing experience surface implemented as a thin
Backend-For-Frontend (BFF). It owns the minimum portal-specific interaction and tenancy records needed to
render the product. It consumes versioned contracts from authoritative owners, presents provenance and
source health, deep-links to owner surfaces, and submits narrowly bound requests. It never becomes the
authority for domain facts, policy, readiness, gates, execution, knowledge, telemetry, or provider state.

### D1 — Keep the portal optional, thin, and product-oriented

The portal may expose the same versioned PlatformProduct/PlatformPath request contract used by CLI, chat,
MCP, API, Jira, and agent callers under ADR-0011. It may guide dialogue, collect a structured request,
display owner-produced status/evidence, and direct a human to an owner surface. It does not compile a
WorkOrder, choose a Realm, decide readiness, select a transition, verify a result, mutate infrastructure,
or declare completion.

Factory cockpits remain independently buildable, deployable, and operable. The absence or outage of the
portal cannot disable a factory, owner API, or direct authoritative source. A portal release may be
severed without migrating owner truth out of it.

The tenant model is proposed as one isolation model usable by internal teams and, after a separate
product/commercial decision, external clients. This ADR does not classify current teams as live tenants,
launch an external offering, set support/SLO/cost promises, or decide who may onboard a tenant.

### D2 — Reads are source-bound projections, never decisions

Every owner-derived panel consumes a released, versioned read contract and carries a closed envelope at
least binding:

- owner and endpoint/tool plus contract revision or digest;
- subject, tenant and workspace scope, and request/correlation identity;
- owner-produced time, portal-observed time, freshness bound, coverage, and source-health state; and
- typed result status such as `fresh`, `stale`, `unknown`, `degraded`, or `unavailable`.

The portal renders owner facts as received and does not recompute a gate, verdict, tier, policy,
classification, readiness result, lifecycle transition, finding severity, blast radius, cost, invoice,
or Done state. Unknown fields and schema skew fail closed; they are not filled from model text, labels,
defaults, another tenant, or a different owner.

Decision-class facts have a zero-authority cache: a cached value may support diagnostics but is never
rendered as current authority and never enables an action. A bounded cache is allowed only for explicitly
benign projections with a component-owned staleness policy; its source, age, coverage, and stale state
must remain visible. `stale`, `unknown`, `degraded`, and `unavailable` are distinct from an empty result,
zero incidents, zero cost, or "all clear".

### D3 — The portal submits intent; the owning module authorizes and executes

A portal-side session, RBAC lookup, CSRF check, step-up assertion, action classification, and audit intent
establish only the right to submit an exact request through the portal. They are not authority for the
domain action.

Each state-changing request binds the authenticated actor and active tenant, target workspace, exact
action and resource, owner contract revision, current owner fact revision/epoch when relevant,
idempotency key, correlation id, expiry, and the exact step-up receipt when the accepted action policy
requires one. The portal cannot widen target, credential, scope, action, tier, or lifetime and cannot
translate an unknown action into a known permissive one.

The owning module independently authenticates the caller/workload identity, authorizes the exact current
action and target, rechecks mutable state, redeems any owner-recognized approval/capability, performs the
effect, and returns an integrity-bound receipt. A portal audit row or HTTP success from the BFF is not the
owner receipt. Owner rejection remains rejection. Owner unavailability produces no effect and no success
claim. A timeout or lost response is `pending reconciliation`; the portal must query owner truth by the
same idempotency/correlation identity and must not blindly retry a possibly completed effect.

Portal-owned configuration changes, such as a tenant workspace association or source-configuration
intent, still require the portal's own exact authorization and audit contract. They do not grant access in
another module until that owner independently accepts the resulting request.

### D4 — Tenant isolation is an end-to-end contract, not an architectural label

Portal identity must pin the OIDC issuer, audience/client, algorithms, subject, tenant-membership source,
client-scoped roles, expiry, session regeneration rules, CSRF posture, and step-up semantics. Missing,
ambiguous, unknown, or conflicting identity/tenant claims deny. A platform operator starts with no tenant
visibility and enters at most one tenant through an explicit, authorized, audited switch; there is no
implicit see-all path.

Every portal-owned tenant row is isolated by an exact database policy. Candidate Postgres RLS must be
proved with a non-owner, non-`BYPASSRLS` runtime role, forced/default-deny policies, transaction-local
tenant context, separate migration authority, pooled-connection reset/reuse tests, and startup/runtime
checks. Application `WHERE tenant_id = ...`, ORM filters, or the presence of `ENABLE/FORCE RLS` text is
not sufficient evidence by itself.

Downstream access must preserve set containment: the requested workspace is a member of the tenant's
owned set; an empty set means no workspace; and a missing, foreign, wildcard, expired, over-wide, or
unverifiable token denies without disclosing existence. Token issue/exchange/broker authority, audience,
scope, TTL, rotation, revocation, and audit are owned by the downstream component contract. In particular,
ADR-0017's `omniscience-mcp-read-v1` profile governs its accepted consumer and does not authorize the
portal's current mock broker or broader scope list. A live portal integration needs a separately accepted,
compatible owner contract or an accepted revision of the existing one.

### D5 — Store only closed portal-owned state and labeled projections

The portal database has an explicit ownership matrix; table presence does not establish authority.

| Data class | Portal posture | External authority/boundary |
|---|---|---|
| portal sessions, CSRF state, OIDC attempts, portal step-up assertions | portal-owned, short-lived | identity and MFA claims still come from the accepted IdP contract |
| tenant/user references, memberships, roles, workspace associations | portal-owned only where an accepted onboarding contract assigns ownership | cannot mint downstream access or override an owner's tenant/workspace mapping |
| source-configuration intent, secret handles, re-ingest requests | portal-owned request/config ledger | secret values stay in the secret owner; ingestion and indexed knowledge stay with Omniscience |
| portal action intent/outcome audit | portal-owned append-only evidence of portal behavior | not an owner action receipt, OutcomeEvent, provider fact, or authorization |
| product/path requests and status | immutable request reference plus labeled projection | contract, WorkOrder, Realm, execution, verification, and Done remain with their owners |
| runs, lifecycle, gates, tiers, findings, graph/topology, metrics | read-only source-labeled projection | factory, harness/policy, Omniscience, and observability owners remain authoritative |
| plans, subscriptions, usage, invoices, payment references | portal may own its commercial catalog/request records | provider charge, payment instrument, metering, settlement, and invoice status require their accepted owners and reconciliation |

Secret values, provider credentials, payment-card data, owner signing keys, unrestricted service tokens,
and owner decision records are not portal storage. Projection/cache rows are namespaced by exact tenant,
workspace, owner, resource, contract revision, and observation epoch; they cannot be queried or presented
as canonical state.

### D6 — Component SPECs and releases adopt the ADR explicitly

Portal behavior is specified in English with stable `SPEC-XX` and `[REQ-XX-n]` identifiers, typed
interfaces, an explicit failure posture, deterministic positive and negative probes, dependency/release
gates, and pinned constants. Under ADR-0012, readiness binds exact repository revisions, requirement and
probe sets, dependencies, Realm/path scope, evidence TTL, and human authority; a document-level status or
merged implementation is not enough.

Current `SPEC-IT`, `SPEC-PS`, `SPEC-KV`, `SPEC-CP`, `SPEC-CN`, `SPEC-AU`, `SPEC-BL`, `SPEC-PM`, and
`SPEC-CV` are candidate component decomposition, not accepted by this ADR. Their headers now identify
this accepted ADR, but the seven historical specs still require semantic D/PI traceability
reconciliation. Before adoption, the index and each selected requirement/probe must bind the accepted
ADR-0007 revision, reconcile incompatible token, ownership, action, cache, visualization, and product
claims, and enter readiness through the accepted lifecycle. Existing mock-backed code at `b346f3b...`
is construction evidence that may be retained; `SPEC-PM` and `SPEC-CV` currently have documentation
only. None is grandfathered past those gates.

Activation follows dependency readiness, not the historical build sequence. Identity/tenancy and shell
mechanisms alone do not make the knowledge, control, connector, audit/metrics, or billing paths live. Each
owner integration remains disabled or visibly unavailable until its released contract, credential,
negative isolation/authorization evidence, and operational release gate are satisfied.

### D7 — Reuse owner depth without sharing authority or credentials

Diff and pull-request depth link to GitHub; raw metrics link to their observability owner; topology and
knowledge come from Omniscience; component maintenance stays in the component cockpit. The portal may
render detailed component projections through D2's released source-bound read contracts and correlate
them through published identities. It does not import owner state or maintenance logic.

Deep links are preferred. Embedding an owner UI requires a separate accepted browser/security contract
covering frame policy, origin, session and logout, CSRF, clickjacking, tenant context, accessibility, and
failure behavior. Credentials, bearer tokens, approval receipts, and unrestricted target URLs are never
placed in query strings, fragments, frames, client bundles, or portal-generated deep links. If the owner
surface is unavailable, the portal reports that condition and may present a safe canonical link; it does
not rebuild or fabricate the owner workflow.

### D8 — Keep local cockpits narrow; make the portal the cross-component detail surface

Each component remains independently operable without the portal and may own a small local cockpit for
its own state:

- Omnius may render its execution queue, one WorkOrder/task detail, local evidence, and component-local
  operator controls.
- Omniscience may render its sources, ingestion/indexing, storage, freshness, MCP health, and
  component-local maintenance.

Platform Portal owns the platform-wide composition: portfolio and synchronized-work maps, component
detail pages, cross-component dependencies and timelines, evidence correlation, and thin delegated
controls. A portal component page may be more detailed than a local cockpit because it composes several
released owner projections. Every projected field retains owner, revision, scope, freshness, coverage,
and source health; every action still follows D3.

The portal uses a stable common detail skeleton (overview, activity, dependencies, evidence, controls,
and local-depth links) with versioned component-owned payloads. It accepts no arbitrary owner HTML,
JavaScript, CSS, iframe, query, chart expression, template, or credential. Cross-component joins require
owner-published correlation identities; names, similar labels, timestamps, or model inference cannot
create a relation.

Local UI and portal detail are deliberately asymmetric:

- loss of the portal must not block component operation or recovery;
- loss of a component makes its portal projection unavailable and disables its controls;
- the portal may not turn its correlated view into a new component health, readiness, gate, lifecycle,
  or completion decision; and
- raw metrics, raw graph exploration, diffs, and deep maintenance remain with their owners, while the
  portal owns the curated cross-platform narrative and navigation.

## Portal invariants

| Id | Invariant | Required posture |
|---|---|---|
| **PI-1** | View, never authority | owner facts render with provenance; portal code cannot issue domain decisions |
| **PI-2** | Intent, never owner authorization | portal admission is only right-to-call; owner independently authorizes and receipts the exact effect |
| **PI-3** | No second source of truth | portal-owned records use a closed matrix; every other datum is a labeled projection |
| **PI-4** | Honest degradation | stale/unknown/degraded/unavailable never becomes empty, all-clear, approved, free, or Done |
| **PI-5** | End-to-end tenant containment | identity, DB, cache, owner request, workspace, token, logs, and deep links preserve the same tenant boundary |
| **PI-6** | Optional and severable experience plane | factories and direct owner surfaces operate without the portal; severance creates no fabricated fallback |
| **PI-7** | No-reinvent browser boundary | owner depth stays in owner surfaces; embedding and credential propagation require separate authority |
| **PI-8** | Local cockpit / platform detail separation | local UIs keep components operable; the portal owns detailed cross-component composition without copying owner authority |

## Current component adoption map

This is a 2026-07-16 observation, not a readiness, conformance, release, or production result.

| Area | Current candidate evidence | Required adoption boundary |
|---|---|---|
| portfolio | `platform-portal` is `proposed`; release and evidence are null | human ADR disposition, exact component release evidence, then a separately authorized portfolio update |
| component traceability | nine draft portal SPECs and an index exist; PM/CV capture platform map and component detail | reconcile legacy D/PI mappings; pin accepted ADR revision and exact ready requirement/probe sets |
| implementation | clean `platform-portal` `main` at `b346f3b...`; backend/frontend/CI/tests/local topology | immutable release, build/provenance evidence, accepted runtime profile, deploy and operational probes |
| integrations | contract mocks plus explicit RG-KV/RG-CP/RG-CN/RG-AU/RG-BL release gates | released owner APIs/schemas, credentials, failure semantics, compatibility and live-path negative tests |
| identity/tenancy | OIDC, session, RLS, operator switch, workspace-set and step-up candidates | accepted IdP/onboarding ownership, runtime-role/RLS/pool evidence, two-tenant and operator isolation |
| knowledge | mock broker/client with capability check and unavailable state | owner-approved portal token/consumer contract compatible with ADR-0017 or a separately accepted revision |
| actions | portal RBAC, intent/outcome audit, handlers and mock clients | independent owner authorization, exact receipts, idempotency, ambiguity reconciliation, outage evidence |
| commercial | plans/subscription/usage/invoice candidates and Stripe release gate | accepted product/commercial ownership, provider contract, metering/reconciliation, secret and compliance boundary |
| omnius UI | dirty local checkout; draft SPEC-UI still defers multi-factory-shell choice | component owner decides and pins its own compatible SPEC revision after ADR disposition |
| component UI boundary | portal vision and SPEC-CV define narrow local cockpits plus detailed portal projections | Omnius and Omniscience publish compatible local-UI/read-projection boundaries and severance evidence |

## Required conformance and release evidence

Acceptance-readiness review must reject missing, stale, mutable, caller-authored, mock-only, or
revision-mismatched evidence. Adoption requires at least:

1. **Human disposition and traceability:** immutable acceptance/supersession evidence; portal SPEC/index
   references corrected to the exact ADR-0007 revision; exact ready REQ/probe/profile bindings.
2. **Ownership and schema:** a closed field/table/API ownership matrix; schemas bind tenant/workspace,
   owner, subject, revision, freshness, coverage, source health, and typed unavailable states.
3. **Tenant isolation:** two-tenant, foreign-workspace, empty-set, unknown-claim, operator-no-tenant,
   single-tenant switch, cache/log/deep-link, and pooled-connection reuse negatives using the real runtime
   DB role and policy.
4. **Read integrity:** schema-skew, stale, partial, unknown, owner-timeout, severance, and recovery probes;
   decision-class cache cannot enable an action or display current authority.
5. **Action authority:** owner reject, revoked/expired step-up, changed epoch, wrong target/tenant, unknown
   action, duplicate request, timeout after possible effect, reconciliation, audit outage, and lost-response
   probes on the real owner path.
6. **No-decision boundary:** static and runtime evidence that the portal cannot construct or sign owner
   verdict/tier/readiness/Done records, bypass an owner, or convert unavailable into success.
7. **Credential and data boundary:** no secret readback, cross-tenant handle/token use, payment-card storage,
   client-bundle credential, token-in-link, unrestricted owner credential, or mock endpoint in a live
   configuration.
8. **Live integration gates:** released and pinned Omniscience, factory/harness, ingestion/secret,
   OutcomeEvent/metrics, and billing/metering contracts with compatibility, outage, recovery, rotation,
   revocation, and reconciliation evidence for each enabled panel/action.
9. **Severance:** portal removal does not block owners; owner severance produces exact unavailable states
   and no false zero/all-clear/success; recovery never replays a state-changing intent accidentally.
10. **Release and operations:** immutable source/build/image provenance, dependency and vulnerability
    policy, migration/rollback, backup/restore, SLO/alert/runbook, deploy/rollback, and post-deploy probes;
    portfolio status changes only after retained release evidence exists.
11. **Component-detail contracts:** typed Omnius, Omniscience, coordination-hub, and portal-self
    projections; common-envelope conformance; no active owner content; correlation-id semantics; local
    cockpit severance; and owner-action reconciliation.

## Consequences

**Positive.** A tenant gets one product-oriented entry point while authority remains with the component
that owns each fact or effect. The portal can evolve or disappear without migrating factory, knowledge,
policy, execution, telemetry, or provider truth.

**Costs.** Every panel and action needs a released owner contract, provenance/freshness envelope, exact
tenant propagation, negative failure evidence, and honest unavailable state. Live integrations therefore
advance more slowly than mock-backed UI construction.

**Risks.** Portal convenience can still become de facto authority through stale display, permissive retry,
over-wide credentials, identity/tenant drift, or commercial-state ambiguity. D2-D5 and the required
negative evidence make those failures release-blocking rather than presentation details.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| make the portal a factory/control plane | duplicates orchestration and lets presentation state influence execution authority |
| cache or recompute owner decisions | a stale or divergent projection can bypass the current owner gate |
| authorize an owner action with portal RBAC/step-up alone | right-to-call is not current target authorization or an effect receipt |
| use one cross-tenant service credential | a portal compromise becomes a workspace/tenant bypass and violates set containment |
| treat merged mock-backed code as adopted | construction evidence omits accepted specs, live contracts, credentials, operations, and release evidence |
| embed every owner cockpit | expands browser/session/clickjacking coupling and duplicates navigation without a security contract |
| make the portal only a shallow link directory | leaves cross-component dependencies, evidence, and control context fragmented; D8 permits detailed released projections without copying authority |
| single-tenant schema first, isolation later | identity, storage, cache, logs, tokens, links, and every owner request would need a risky retrofit |
| no portal | remains a valid deployment choice, but does not provide the proposed common tenant-facing experience product |

## Follow-ups

- [x] Obtain explicit platform-owner disposition of this proposal (accepted 2026-07-21 for development;
      no live authority).
- [ ] In `platform-portal`, reconcile the historical D/PI references against the accepted ADR-0007
      revision and bind selected PM/CV requirements with D1-D8.
- [ ] Publish exact readiness profiles for selected portal requirements and their deterministic probes.
- [ ] Pin the IdP/onboarding, tenant/workspace, downstream token, owner action/receipt, projection/freshness,
      and browser/deep-link contracts.
- [ ] Close each real-owner release gate and retain live-path negative and recovery evidence.
- [ ] Produce an immutable portal release and operational evidence before proposing a portfolio status or
      current-release update.
- [ ] Let the omnius owner decide the deferred SPEC-UI multi-factory-shell item against an accepted,
      immutable ADR revision; do not mark it resolved from this proposal.
- [ ] Publish component detail/read/action contracts and prove that Omnius and Omniscience local
      cockpits remain independently operable when the portal is severed.

## References

- [platform-glossary.md](../platform-glossary.md) — tenant workspace, knowledge plane, severance,
  autonomy tier, and gate/guardrail vocabulary.
- [ADR-0009](0009-organizational-dark-factory-sdd.md) — human ADR/SPEC authority and portal projection.
- [ADR-0010](0010-goal-oriented-organizational-dark-factory.md) — dialogue/order/status/evidence surfaces
  without decision authority.
- [ADR-0011](0011-platform-products-and-executable-paths.md) — common product/path request and separated
  architectural planes.
- [ADR-0012](0012-capability-readiness-profiles.md) — exact human-owned readiness profiles.
- [ADR-0017](0017-omniscience-mcp-v1-contract-and-severance.md) — pinned Omniscience v1 contract,
  freshness, severance, and bootstrap token profile.
- omnius `specs/SPEC-UI-human-interface.md` — draft REQ-UI-1, REQ-UI-7, REQ-UI-9 and the deferred
  multi-factory-shell item; component-owned and non-binding here.
- `project/platform-portal/specs/` — current draft portal SPECs and release-gated mock implementation;
  component-owned and not adopted by this proposal.
