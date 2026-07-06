# ADR-0007: Platform portal — a federated multi-tenant surface (thin BFF), not a factory

- **Status:** Proposed
- **Date:** 2026-07-04
- **Deciders:** platform owner
- **Scope:** binding for the new **platform-portal** component; **resolves omnius SPEC-UI
  REQ-UI-9's open "multi-factory shell" question**; inherits (never weakens) ADR-0003 I1–I8,
  ADR-0002 (skills registry), ADR-0001 (Sentinel), the autonomy tiers T1–T4, and the
  sre-harness action-tier table. Informative for the per-factory cockpits (multiqlti / omnius)
  and Omniscience (whose read-only MCP contract the portal consumes).
- **Vocabulary:** [platform-glossary.md](../platform-glossary.md) — esp. *tenant workspace*
  (2.4), *knowledge plane*, *severance*, *autonomy tier*, *gate vs guardrail*. Skills per
  [ADR-0002](0002-platform-skills-registry.md); SDLC invariants per
  [ADR-0003](0003-unified-sdlc-standard.md); Sentinel per
  [ADR-0001](0001-continuous-detection-sentinel.md).

## Context

The platform is five components with **five different human surfaces** and no federated one:
per-factory cockpits (multiqlti's UI, omnius's `console/`), Omniscience's own MCP-first
surface, Grafana/Langfuse for metrics, GitHub for diffs/PRs. Each is correct for its owner and
its single audience. **None of them onboards a tenant, federates the five components into one
control-plane + observability view, or provides a commercial surface.** The product goal —
*genai-enablement **as a service** first (internal engineering teams = tenants), **as a
platform** later (external clients: devops teams, startups)* — needs exactly those three things,
and needs them multi-tenant from the first row of the first table.

This forces a decision omnius explicitly parked. **SPEC-UI REQ-UI-9** established that each
factory keeps its **own** cockpit + local memory + curation queue, that **Omniscience is a
shared read-only knowledge layer, not a shared UI shell**, and that one factory's UI must not
depend on another — and then left open (SPEC-UI *Open questions*, last bullet):

> **[defer] Multi-factory shell** — whether a thin federated shell lists each factory's
> cockpit, or each factory's UI is fully standalone with Omniscience as the only shared surface
> (per REQ-UI-9 the default is standalone).

The product answer is "yes, there is a federated shell" — but the *shape* of that shell is
where the platform can hurt itself. Two failure modes are live correctness hazards, not
aesthetics:

1. **A portal that re-implements decision logic.** If the portal caches or recomputes a gate
   verdict, an autonomy tier, or a `can_auto_merge` result, then a **portal bug can bypass a
   real gate** — a cached "approve" shown after the owning module would have said BLOCK. This is
   precisely what omnius **REQ-UI-1 / REQ-CC-5** forbid ("the UI is a view, never an authority;
   it computes no gate; reads fail to *unavailable*, never a stale-cached *approved*; writes
   fail closed").
2. **A portal that becomes a second source of truth.** If the portal grows its own graph, its
   own runs store, or its own decision cache, it **duplicates and can silently contradict** the
   owning module. The glossary's *severance* principle and REQ-CC-9 require the opposite: shared
   knowledge is read *from Omniscience by contract*, and removing a dependency **degrades, never
   fabricates**.

The portal must therefore be defined by what it is **not** as sharply as by what it is: not a
factory, not a source of truth, not a re-implementation of any cockpit. It is the *federating,
multi-tenant, commercial* surface **on top of** surfaces that already own their decisions.

## Decision

The platform-portal is a **federated multi-tenant surface implemented as a thin
Backend-For-Frontend (BFF)**. It federates the five components via a **shared read-layer +
deep-links** and holds **no decision logic and no new source of truth**. Seven decisions
(D1–D7) below encode this; the portal invariants table (PI-1…PI-6) makes them the reference the
specs cite.

### D1 — The portal is a federated multi-factory *surface* (thin BFF), NOT a factory

**Context.** The temptation is to grow the shell into "the place work happens." That would make
it a sixth factory with all the governance obligations of one, competing with the two that
already exist. The measured platform shape is hub-and-spoke around Omniscience with peer
factories; the portal is a *seventh kind of thing* — a presentation + tenancy layer, not a peer
factory.

**Decision.** The portal is a thin BFF that **federates**: it reads each owning module through
that module's stable contract, renders a unified per-tenant view, and links or proxies every
action back to the owner. **Per-factory cockpits (multiqlti, omnius `console/`) stay
standalone**; the portal **federates via a shared read-layer + deep-links and never
re-implements a per-factory cockpit**. This is the faithful resolution of REQ-UI-9's open
question: a federated shell *exists*, but it is additive and non-coupling — **a factory's
cockpit never depends on the portal** (REQ-UI-9's "one factory's UI does not depend on another"
is preserved, extended to "nor on the shell"), and Omniscience remains the shared read-only
knowledge layer, not a shared UI shell.

**Consequences.** The portal owns only *platform-tier* surfaces (tenant onboarding, cross-factory
rollup, the federation itself). When a user needs the depth of a cockpit, the portal **deep-links
into the standalone cockpit** rather than mirroring it. A cockpit can be developed, deployed, and
operated with the portal entirely absent.

### D2 — View-never-authority: the portal holds no decision logic (inherits REQ-UI-1 / REQ-CC-5)

**Context.** Every datum the portal shows — a gate `Verdict`, an autonomy tier, a `can_auto_merge`
breakdown, a Sentinel finding's severity, a run's state — is *owned and decided elsewhere*. The
only safe portal is one that cannot fabricate any of them.

**Decision.** The portal process holds **no gate / verdict / tier / classification decision
function**. Every datum is **read from its owning module and rendered as-is**; every action
(trigger a run, approve a gate, change a source config, admit a skill) **calls the real owning
module**, which performs and authorizes it. **Reads fail to "unavailable"** (a rendered read
error) — **never a stale-cached "approved."** **Writes fail closed** (the human cannot approve
through a portal that cannot confirm the real state). A portal bug can therefore never bypass a
gate, flip a tier, or mark work done.

**Consequences.** This is REQ-UI-1 applied across *federation and tenancy*, not one factory: the
same invariant must hold for every module the portal federates and every tenant it serves. It is
the hardest single constraint on the build and the reason the portal DB (D4) may hold no decision
state.

### D3 — Multi-tenant from day one: RLS + tenant-scoped OIDC + per-tenant Omniscience workspace tokens

**Context.** "Internal teams now, external clients later" is a **tenancy** statement, and tenancy
touches identity and *every query*. Retrofitting it later is a rewrite (see Alternative 4). The
Omniscience *tenant workspace* (`workspace_id` on fail-closed tokens, glossary 2.4) already gives
the platform a per-tenant isolation primitive to align with.

**Decision.** Multi-tenancy is a **day-one** property: **Postgres Row-Level Security (RLS)**
keyed on a session `tenant_id`, **tenant-scoped OIDC tokens** (a principal is bound to exactly one
tenant, save an explicit platform-operator principal), and **per-tenant Omniscience access via
per-tenant workspace-scoped read tokens, fail-closed**. Internal engineering teams are tenants
*now*; external clients later are the **same model, no schema fork**.

**Consequences.** Isolation is enforced at the database (RLS), not by application `WHERE` clauses
alone — an ORM bug cannot cross tenants. The per-tenant Omniscience workspace-token contract is a
**hard dependency** on the Omniscience owner and is the ADR's foremost must-resolve follow-up.

### D4 — No new source of truth: the portal DB holds only platform-tenancy state

**Context.** Anything the portal stores that another module owns is a divergence waiting to
happen and, if it is a decision datum, a gate-bypass waiting to happen (D2).

**Decision.** The portal DB holds **ONLY**: tenants, users, roles, source-configs, audit, and
(later) billing. Everything else is **read from its owner by contract**: the **graph ←
Omniscience** (read-only MCP), **gates / autonomy tiers ← sre-harness**, **runs / factory
lifecycle ← the factories** (multiqlti / omnius). Any read cache the BFF keeps is **explicitly
non-authoritative** and **severance-aware (REQ-CC-9)**: on module severance or staleness beyond a
pinned bound the panel renders **"unavailable"** — the portal never serves a cached gate / verdict
/ tier as if it were live.

**Consequences.** The portal cannot answer "what is the platform state" from its own store; it is
structurally a projector. This is what makes D2 enforceable and severance honest.

### D5 — Spec-first, in the omnius house style; artifacts in English

**Context.** These surfaces interlock with omnius's specs and this repo's ADRs; drifting from the
house style would fracture the shared review discipline.

**Decision.** The portal is specified **spec-first in the omnius house style** — `SPEC-XX` ids,
each `[REQ-XX-n]` carrying a deterministic **Fallback**, per-REQ deterministic **acceptance
probes**, a dependency graph / build order, and a deferred-constants table (typed, fail-closed if
unset). **All artifacts are in English.**

**Consequences.** Engineers implement against accepted specs; the constitution-conformance
discipline (deterministic probe per REQ) extends to the presentation + tenancy layer.

### D6 — Inherits the platform constitution; surfaces it, never weakens it

**Context.** The portal is where a human *sees* the platform's safety machinery. The risk is that
a convenience surface quietly relaxes an invariant (e.g. a one-click "approve all" that skips a
step-up).

**Decision.** The portal **inherits and surfaces, never weakens**: **ADR-0003 I1–I8** (task
envelope, canonical lifecycle, quality-gated DoD, producer≠verifier, side-effect boundary,
OutcomeEvent telemetry, registry-only skills, escape tracking); the **autonomy tiers T1–T4, never
L5**; the **sre-harness action-tier table**; and **ADR-0002** (skills registry). Irreversible /
boundary-expanding actions require **Class-2 step-up** (SPEC-HB / SPEC-IP) and are performed by the
owning module, never by the portal.

**Consequences.** The portal renders these as first-class, legible facts (why a run is gated, which
tier applies, which action needs step-up). It can make an invariant *visible*; it can never make one
*optional*.

### D7 — No-reinvent boundary (inherits REQ-UI-7)

**Context.** Commodity surfaces already have excellent owners. Rebuilding them creates drift from
the owner's truth and burns the build on solved problems.

**Decision.** Commodity surfaces are **embedded or linked from their owner, never rebuilt**:
**diff / PR → GitHub**; **raw metrics → Grafana / Langfuse**; **topology / incidents →
Omniscience**; **per-factory cockpits → embed / deep-link**. The **custom build is only the
platform-tier surfaces** the portal alone owns: tenant onboarding + management, cross-factory
federation/rollup, the multi-tenant knowledge view, and (later) the commercial surface.

**Consequences.** A down embedded surface **links out** to the owner; it is never replaced by a
fabricated local copy (a local copy would drift from the owner's truth — REQ-UI-7's rule).

### Portal invariants (inherited — the reference the specs cite)

The portal creates **no new constitution**. It renders the existing one. The specs' *Invariants
honored* sections cite these by id; each id is a portal-local name for an inherited invariant.

| Id | Portal invariant | Inherited from | One-line statement |
|---|---|---|---|
| **PI-1** | View-never-authority | omnius REQ-UI-1 / REQ-CC-5 (D2) | portal holds no decision logic; reads render as-is; every action calls the owning module |
| **PI-2** | No new source of truth | D4 | portal DB holds only tenants/users/roles/source-configs/audit/billing; all else read by contract; caches non-authoritative |
| **PI-3** | Fail-closed + severance-aware | omnius REQ-CC-9 / REQ-UI-1 (D2/D4) | reads fail to "unavailable" (never stale); writes fail closed; a severed module degrades context, not the shell |
| **PI-4** | Tenant isolation | D3 | RLS + tenant-scoped OIDC + per-tenant workspace tokens; a cross-tenant read is impossible; an absent/mismatched tenant token fails closed |
| **PI-5** | No-reinvent boundary | omnius REQ-UI-7 (D7) | diff→GitHub, metrics→Grafana/Langfuse, topology→Omniscience, cockpits→deep-link; custom build = platform-tier only |
| **PI-6** | Autonomy ceiling preserved | ADR-0003 I1–I8, tiers T1–T4/never-L5, action-tier table, ADR-0002 (D6) | portal surfaces gates/tiers/skills as-is; irreversible actions need Class-2 step-up; never weakens a bound |

## Component decomposition

Seven `SPEC-XX` segments, one coherent buildable unit each. **MVP = SPEC-IT + SPEC-PS + SPEC-KV**
(the thin vertical: a tenant logs in, sees a federated shell, reads its own knowledge view — all
view-never-authority, all tenant-isolated). CP/CN/AU/BL are later.

| ID | Segment | One-line scope | MVP? |
|---|---|---|---|
| **SPEC-IT** | Identity & Tenancy | OIDC login, tenant model, RBAC, Postgres RLS isolation, tenant-scoped tokens, Class-2 step-up for irreversible actions | **MVP** |
| **SPEC-PS** | Portal Shell | 3 zones (Control / Observe / Manage), navigation, view-never-authority, the no-reinvent boundary as an enforced invariant | **MVP** |
| **SPEC-KV** | Knowledge View | read-only per-tenant projection of the Omniscience graph + Sentinel findings, severance-aware | **MVP** |
| **SPEC-CP** | Control Plane | federated factory-run / harness-gate / autonomy-tier *action* surface, each proxied to its owner; cockpit deep-links | later |
| **SPEC-CN** | Connectors & Source Config | per-tenant source registration (git/k8s/CI/…) that feeds Omniscience ingestion; config only, never ingestion | later |
| **SPEC-AU** | Audit & Outcome Metrics | portal audit trail aligned with ADR-0003 I6 OutcomeEvent; DORA-based metrics surfaced from SPEC-FO / harness | later |
| **SPEC-BL** | Billing & Commercial Metering | tenant billing / usage metering — the external-client commercial surface | later |

**Build order:** `ADR-0007 → SPEC-IT → SPEC-PS → SPEC-KV → SPEC-CP → SPEC-CN → SPEC-AU →
SPEC-BL`. IT is the foundation (identity + tenancy gate every query and every downstream token);
PS consumes the IT principal to render the shell; KV needs both the IT tenant/workspace token and
the PS shell to project the knowledge view. The MVP thin vertical stops after KV.

## Consequences

**Positive.** One federated, multi-tenant surface exists without any factory depending on it or on
another. The commercial path (external clients) is a token/role/billing extension of the same model,
not a rewrite. Every decision datum stays owned by its module, so a portal bug cannot bypass a gate.

**Negative / costs.** The BFF must be disciplined to stay thin — every "just cache the verdict"
shortcut is a latent gate-bypass and is barred by D2/D4. The per-tenant Omniscience workspace-token
contract is an external dependency that must be pinned before SPEC-KV builds. RLS + tenant-scoped
tokens add real complexity to day one — accepted deliberately (Alternative 4).

**Risks.** (a) BFF cache drift presenting a stale decision as live → mitigated by non-authoritative,
severance-aware caches (D4) and the view-not-authority probe (SPEC-PS). (b) Cross-tenant leakage →
mitigated by RLS-at-the-database + the tenant-isolation conformance probe (SPEC-IT). (c) Coupling to
Omniscience internals → mitigated by contract-version pinning (SPEC-KV, inherits KP REQ-KP-1).

## Alternatives considered

1. **Extend omnius SPEC-UI into a shared shell.** Rejected: it **couples the factories** through a
   shared UI and **regresses REQ-UI-9's standalone default** — a factory's cockpit would come to
   depend on the shell, exactly the dependency REQ-UI-9 forbids. The portal must be additive and
   non-coupling, not an expansion of one factory's UI.
2. **A thick aggregator with its own graph + decision cache.** Rejected: it **duplicates the source
   of truth** (its graph diverges from Omniscience's) and — worse — **a cached gate result can bypass
   a real gate** (a stale "approve" served after the owner would BLOCK), violating REQ-UI-1 /
   REQ-CC-5. D2/D4 exist to make this alternative structurally impossible.
3. **No portal — cockpits + Omniscience only.** Rejected: there is then **no multi-tenant onboarding
   and no commercial surface**. The product goal (as-a-service, then as-a-platform) is unreachable
   without a federating tenancy layer; the cockpits are single-audience by design.
4. **Single-tenant now, add tenancy later.** Rejected: **tenancy touches identity and every query**;
   retrofitting RLS + tenant-scoped tokens + per-tenant workspace tokens across an already-built
   surface is a rewrite, not an increment. Day-one tenancy (D3) is cheaper than the retrofit.

## Follow-ups

- [ ] **Pin the per-tenant Omniscience workspace-token contract** with the Omniscience owner: who
      mints the per-tenant workspace-scoped **read** token, its scope set (read-only, exactly one
      `workspace_id`), TTL, and rotation. This is a **hard, must-resolve-before-SPEC-KV-build**
      dependency (SPEC-KV REQ-KV-6 / SPEC-IT REQ-IT-5).
- [ ] **Align the portal audit / OutcomeEvent with ADR-0003 I6** — the portal's human-decision event
      stream (approve, trigger, config change, step-up) reuses the versioned OutcomeEvent schema so
      cross-factory yield/escape stays one query (SPEC-AU, later; SPEC-IT/PS emit the MVP subset).
- [ ] **Flip omnius SPEC-UI REQ-UI-9's open "multi-factory shell" item to resolved-by-ADR-0007** (the
      federated shell exists, additive + non-coupling, cockpits standalone, Omniscience the shared
      read layer).
- [ ] **Add a "platform portal" row to the glossary Part 2** (Product-level terms): the federated
      multi-tenant surface / thin BFF; view-never-authority; no new source of truth.
- [ ] Pin the deferred constants (session TTL, tenant-scoped + workspace-token TTLs, Class-2 step-up
      freshness window, read-cache staleness bound, Omniscience MCP contract-version) from a security
      review before the consuming spec builds (SPEC-INDEX §5).

## References

- [platform-glossary.md](../platform-glossary.md) — *tenant workspace*, *knowledge plane*,
  *severance*, *autonomy tier*, *gate vs guardrail*, *L4 / never L5*.
- [ADR-0001](0001-continuous-detection-sentinel.md) — Sentinel findings (SPEC-KV projects them).
- [ADR-0002](0002-platform-skills-registry.md) — skills registry (portal surfaces, never mutates).
- [ADR-0003](0003-unified-sdlc-standard.md) — SDLC invariants I1–I8, the action-tier table, the
  OutcomeEvent schema (I6).
- omnius `specs/SPEC-UI-human-interface.md` (REQ-UI-1 view-never-authority, REQ-UI-7 no-reinvent,
  REQ-UI-9 per-factory federation — the open question this ADR resolves),
  `specs/SPEC-KP-knowledge-plane.md` (REQ-KP-1 contract-only coupling, REQ-KP-3 blast_radius
  surfacing-only, REQ-KP-4 symmetric severance), `specs/SPEC-IP-identity-policy.md` &
  `specs/SPEC-HB-human-boundary.md` (Class-2 step-up, the human boundary).
- `project/platform-portal/specs/` — SPEC-INDEX + SPEC-IT / SPEC-PS / SPEC-KV (MVP), authored
  against this ADR as their source of truth.
</content>
