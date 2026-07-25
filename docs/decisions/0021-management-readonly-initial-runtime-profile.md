# ADR-0021: The first synchronized-platform runtime profile is Management Read-Only

- **Status:** Accepted
- **Date:** 2026-07-25
- **Deciders:** platform owner
- **Scope:** synchronized-platform deployment sequencing and cross-repository release qualification
- **Depends on:** [ADR-0007](0007-platform-portal-federated-surface.md),
  [ADR-0012](0012-capability-readiness-profiles.md),
  [ADR-0017](0017-omniscience-mcp-v1-contract-and-severance.md),
  [ADR-0018](0018-pii-wall-purpose-bound-data-boundary.md), and
  [ADR-0020](0020-barbarossa-continuous-management-plane.md)

## Context

The target synchronized platform includes the Omnius Dark Factory, Omniscience knowledge plane,
Barbarossa Continuous Management Plane, Platform Portal, and the `genai-enablement` governance plane.
The full target closes a valuable but expensive trust chain: evidence and context lead to a management
decision, a separately authorized Omnius action, an effect receipt, and independent outcome
verification.

The first deployment does not need that entire chain to prove useful platform behavior. Omniscience,
Barbarossa, and Platform Portal can exercise tenant containment, the distributed PII Wall, immutable
contract pins, source-bound projections, deterministic Reliability evaluation, durable loop/case state,
typed severance, and detailed platform visualization without granting any managed-system effect path.

Making Omnius a mandatory dependency of the first runtime profile would also make its unfinished MCP
consumer pin, PII activation, action producer, and progressive-autonomy evidence part of the initial
critical path. Removing Omnius from the target architecture would be equally wrong: the Dark Factory
remains the intended execution owner for later action-enabled profiles.

The platform therefore needs an explicit deployment-profile decision rather than one implicit
all-components readiness state.

## Decision

### D1 — Select `management-readonly-v1` as the first runtime profile

The first deployable profile contains exactly these runtime owners:

```text
authoritative/read-only sources
        |
        v
Omniscience -- optional cited context --> Barbarossa -- released projections --> Platform Portal
     |                                       |                                  |
     +-- PW0 admission/lifecycle             +-- Reliability loop               +-- CMC/Privacy views

genai-enablement -> governance, registry and profile qualification; not a runtime truth service
Omnius           -> target architecture retained; not deployed in this profile
```

The exact machine-readable selection and gates are defined by
[`management-readonly-v1`](../synchronized-platform/profiles/management-readonly-v1.md) and the
portfolio registry. Profile membership never transfers component authority.

### D2 — Define read-only relative to operators and managed systems

The profile is stateful inside each owner. Omniscience may persist policy-admitted knowledge state;
Barbarossa may persist observations, deterministic snapshots, cases, leases, assessments and
projections; Portal may persist its session and audit records.

`management-readonly-v1` exposes no operator or agent path that changes a managed system or owner
decision state. In particular:

- no Omnius client, credential, DNS dependency, action request, permit or effect receipt is selected;
- Portal owner/component/management/privacy mutation and action routes are absent or fail closed for
  the profile; Portal-owned authentication/session and append-only audit behavior remains available;
- no Portal control changes a loop, case, policy, SLO, budget, source, evaluator or component state;
- no agent/model assessment becomes evidence, a deterministic outcome, authorization or verification;
- no task completion or deployment success is presented as a managed outcome.

Later Barbarossa-owner lifecycle controls and human dispositions require a separate assisted profile.
Managed-system effects require a separate action profile that reintroduces Omnius.

### D3 — Select one domain vertical: Reliability

The first Barbarossa domain is the read-only Reliability pack inherited from ADR-0019 and ADR-0020.
It admits source-owned observations, evaluates a human-published critical-journey/SLO revision
deterministically, persists orthogonal availability/evidence/policy/loop/case conditions, and publishes
source-bound projections.

Cost, AI effectiveness, assurance, delivery, knowledge-quality, capacity, toil, and product-outcome
packs remain compatible target capabilities but are not release prerequisites for this profile.
Readiness never transfers from Reliability to another domain.

### D4 — Defer Omnius without deleting or weakening its contracts

Omnius remains a synchronized-platform component and retains all ADRs, capability SPECs, task SPECs,
work-package status, and future ownership. Its work packages are not in the
`management-readonly-v1` required closure. In particular, SP-11, SP-20, SP-30, SP-40, SP-62 and SP-82
do not gate the first profile; SP-85 remains blocked and unselected.

Absence is rendered as `not_deployed` with the profile id and governing ADR. It is never rendered as
healthy, empty, zero, unavailable-by-accident, or successfully severed. No mock Omnius service may be
enabled in a release-candidate configuration.

The existing SP-12 full consumer-severance package remains valid for its Omnius and historical SRE
receipt set, but it is not a prerequisite of this profile. SP-90 supplies the prerequisite Barbarossa
Go baseline; SP-86 through SP-89 collect the exact Omniscience, Barbarossa, Portal and integrated
release/severance evidence selected here.

### D5 — Make Portal owner panels independently releasable

Portal release gates are evaluated per owner and per profile. A released Omniscience privacy or
component projection can become live while the Omnius panel remains `not_deployed`. A released
Barbarossa Reliability projection can become live without Cost or another domain pack.

Missing, deferred, stale, incompatible, or severed owners retain distinct states. One owner cannot
donate fields, coverage, actions, receipts, or favorable status to another. Portal never recomputes
component truth.

### D6 — Keep Omniscience optional to authoritative Reliability judgment

Barbarossa consumes an exact SP-81 management-context release only as cited context. Direct
authoritative observations and deterministic evaluation remain independently operable. Omniscience
loss removes context and knowledge-quality detail; it cannot stop an already admitted Reliability
evaluation or turn state favorable.

Portal can consume released Omniscience and Barbarossa projections independently. Source loss affects
only its owning panels and produces explicit stale, incompatible, severed, or unavailable state.

### D7 — Select PII Wall profile PW0

Only `PW0 PII-free` is eligible for `management-readonly-v1`. The SP-60 policy revision and SP-61
Omniscience receipt must be pinned. Barbarossa independently applies the same policy before durable
evidence, agent/model context, cases, alerts, projections, telemetry, archives or backups. Portal
accepts only non-identifying owner projections and rejects seeded PII and active content without echo.

Omnius SP-62 is not required because no Omnius data path exists in this profile. This does not qualify
or activate Omnius PW0 for a later profile.

### D8 — Release through one runtime prerequisite and four owner-scoped work packages

The profile is delivered in dependency order:

1. **SP-90 / Barbarossa:** publish the Go-only production-runtime baseline and TypeScript-oracle parity
   receipt required by [ADR-0022](0022-barbarossa-go-production-runtime.md);
2. **SP-86 / Omniscience:** independently publish one immutable MCP/context/PW0 runtime release and
   producer receipt; SP-86 may execute in parallel with SP-90;
3. **SP-87 / Barbarossa:** publish one durable Go read-only Reliability runtime release and consumer
   severance receipt against exact SP-90 and SP-86 inputs;
4. **SP-88 / Platform Portal:** publish one read-only Portal release pinned to SP-86/SP-87 with Omnius
   explicitly not deployed; and
5. **SP-89 / genai-enablement:** join exact release receipts and independently qualify the complete
   profile.

Each task is executable only in its owning repository. A producer cannot create a sibling receipt.
SP-89 may validate immutable supplied artifacts but cannot repair a component or write its release
evidence.

### D9 — Separate build, qualification, and activation

An implementation or container/chart build does not activate the profile. Integrated qualification
requires exact Git, image, chart, schema, policy and configuration digests plus tenant-isolation, PII,
contract-skew, source-severance, restart/recovery, observability and rollback evidence from one named
non-production environment.

The deployment substrate and environment authorization are explicit inputs. This ADR creates no
cluster, cloud resource, credential, DNS record or secret. Any production activation or infrastructure
mutation retains its separate human approval and repository-local task/plan.

## Cross-repository invariants

- **MR-1:** runtime membership is exact; an unselected component cannot appear through a mock or ambient
  dependency.
- **MR-2:** read-only permits owner-local derived state, never managed-system or operator-triggered
  owner-state mutation.
- **MR-3:** Omnius absence is `not_deployed`, never a health assertion.
- **MR-4:** Reliability is the only selected domain and grants no readiness to another pack.
- **MR-5:** Omniscience context is optional to deterministic Reliability truth.
- **MR-6:** every live Portal panel is bound to one exact released owner contract and release receipt.
- **MR-7:** owner release gates are independent; an absent owner does not block or validate another.
- **MR-8:** PW0 rejection occurs before every durable, model, UI, telemetry, archive and backup boundary.
- **MR-9:** no Omnius/action/effect/autonomy path is reachable in the profile network or UI.
- **MR-10:** only SP-89 can claim integrated qualification, and only a later human decision can activate
  a named environment.
- **MR-11:** the Barbarossa production artifact is built from the exact SP-90 Go baseline; TypeScript is
  a non-deployable conformance oracle and no Node.js execution path exists in the profile.

## Consequences

### Positive

- The first deployment validates useful platform behavior with a materially smaller trust and release
  closure.
- Barbarossa's independence and Omniscience severability are tested in a real component composition.
- Portal can go live incrementally by owner instead of waiting for an all-components release.
- Omnius can mature independently and later join through an explicit action profile.

### Costs and trade-offs

- The first release cannot execute remediation or prove realized effects.
- Portal controls remain disabled even when a local mock demonstrates them.
- A separate deployment/qualification pass is still required after component implementation.
- Owner-independent Portal gates and explicit `not_deployed` semantics add contract and UI states.

## Alternatives rejected

- **Wait for every synchronized-platform component:** delays evidence about the management plane and
  couples initial deployment to the highest-risk effect path.
- **Remove Omnius from the target architecture:** loses the governed execution owner and turns a staged
  decision into an architectural deletion.
- **Keep an Omnius mock in the live profile:** creates false confidence and lets mock receipts look like
  real owner evidence.
- **Let Portal call components generically:** collapses owner authorization and severance boundaries.
- **Make Omniscience mandatory for Reliability:** lets an optional context plane suppress independent
  availability judgment.

## Acceptance record

The platform owner selected the Omniscience/Barbarossa/Platform Portal focus on 2026-07-25 and asked
for the usual `genai-enablement` ADR/SPEC decomposition before independent implementation handoff. This
acceptance, together with ADR-0022, authorizes the five bounded development task contracts only. It
authorizes no deployment,
credential, live source, model/provider call, managed-system effect, infrastructure mutation or
production claim.
