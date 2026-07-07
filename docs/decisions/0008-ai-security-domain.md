# ADR-0008: AI Security as a domain over the shared harness — detector, verifier, runbook and reasoner families, not a fourth brain

- **Status:** Proposed
- **Date:** 2026-07-07
- **Deciders:** platform owner
- **Scope:** genai-enablement (this contract); consumes the platform-design security substrate; informative for PB-SRE, multiqlti, omnius
- **Vocabulary:** terms as defined in [platform-glossary.md](../platform-glossary.md) ·
  detection per [ADR-0001](0001-continuous-detection-sentinel.md) · skills per
  [ADR-0002](0002-platform-skills-registry.md) · Done/tiers per
  [ADR-0003](0003-unified-sdlc-standard.md) · memory per [ADR-0004](0004-experience-plane.md)

> ADR numbers 0006 and 0007 are held by open PRs (#19 unified loop decision model; #22 platform
> portal) and are not yet on `main`; this ADR claims **0008** and does not depend on their content.

## Context

The platform has an **AI SRE program** ([ai-sre-program.md](../ai-sre-program.md)) — a *domain* over
the shared harness, not a repo — but **no AI Security counterpart**. Security work today lives only as
two things:

1. **The security policy substrate** — platform-design's OPA/Kyverno/Checkov rules, Cedar policies,
   KMS, network policy, landing-zone design (the graph-model contract in its ADR-0055). This defines
   *what is allowed*; it does not operate agents.
2. **The factories' own SDLC security review** — a review stage *inside* a build loop (ADR-0003 I4
   producer≠verifier; omnius's `SkillContentGate` secret scan). This secures *the code a factory
   writes*; it does not watch the running platform.

Nothing operates **agents that do security operations on the running platform and on changes to it** —
the security analogue of what AI SRE is for reliability.

The harness already ships every primitive such a domain needs, deterministic and unit-tested:

- **Sentinel** ([ADR-0001](0001-continuous-detection-sentinel.md)) — a continuous-detection surface
  with a pure `Detector(SentinelState) -> Sequence[Finding]` contract, deterministic-first, dedup +
  rank by `severity × confidence`, scored offline by the eval harness on **lead-time**; detection is
  read-only (**T1**), emitting a finding is advisory (**T2**).
- **The change-validation gate** (ADR-0003 GATED / Stage 2) — a pure
  `Check(ChangeRequest, PlatformGraph) -> CheckResult` contract aggregated to a
  `PROCEED / BLOCK / REQUIRE_HUMAN` verdict.
- **The autonomy-tier engine + action-tier table** — `ACTION_TIER_TABLE` already classes
  `iam_change` and `security_group_change` as **T3** (human-approved).
- **The skills registry** ([ADR-0002](0002-platform-skills-registry.md)) — SKILL.md canon, git-backed,
  per-runtime trust, with an `sre/` namespace already precedent for a domain category.

Building a *separate* AI-Security factory or a standalone security "brain" would recreate ADR-0003's
divergence #2 (two Done/verdict semantics), fork the audit/telemetry surface (I6), duplicate the
tier/eval/registry machinery — and **double the trust surface an attacker can target**. That is the
opposite of the platform's consolidation direction.

## Decision

Adopt **AI Security as a domain over the shared harness**. It contributes *families* to the existing
surfaces; it never forks the harness core, the Sentinel engine, the gate aggregator, or the eval loop.
*One harness, two domains.*

### D1 — A domain, not a new engine
AI Security is a program that arranges the existing engines (Omniscience = state, the harness =
gates/tiers, the factories = change production, layer-④ reasoners = judgement) into a security
capability — exactly as AI SRE arranges them into an incident-resolution capability. There is **no new
factory and no fourth brain** (see *Boundaries* and *"No fourth brain"* below).

### D2 — Detection: a security detector family in Sentinel (inherits ADR-0001)
Security detectors are pure `Detector(SentinelState) -> Sequence[Finding]` callables registered in a
new `DEFAULT_SECURITY_DETECTORS` family constant, run by the **same** `run_sentinel` / scan / CLI and
scored by the **same** lead-time eval. `SentinelState` grows new *optional* signal fields — exactly as
the state module already anticipates ("later detectors add their own signal fields here without
changing the detector contract"). Detection stays **T1**; emitting a finding stays **T2**. One
Sentinel registry serves both domains; a CLI `--family sre|security|all` selector picks which family
runs.

### D3 — Prevention: a security verifier family in the change-gate (inherits ADR-0003 GATED / Stage 2)
Security verifiers are pure `Check` callables added to the gate registry (e.g. `secret_in_change`,
`iac_security_regression`, `image_cve_gate`, `privileged_workload`). ADR-0001's own taxonomy already
places "secret / ExternalSecret declared" and "deployment-strategy fits workload role" as **gate**
checks — security verifiers extend that Stage-2 multi-check gate; they are **not** Sentinel detectors.
**Secret detection is primarily a gate verifier** (`secret_in_change`, BLOCK on a secret added in a
diff); a Sentinel `secret_in_state` detector is defense-in-depth only (secrets already live in
ConfigMaps/env that bypassed the gate).

### D4 — Capability: a `security/` namespace in the skills registry (inherits ADR-0002)
A new top-level `skills/security/` sits beside `engineering/` and `sre/`, holding runbook-type SKILL.md
with step-level tier tags (seed: `security/leaked-credential-response`,
`security/exposed-endpoint-response`, `security/critical-cve-response`). REGISTRY.md index +
`skills-lock.json` + CODEOWNERS-gate + PR-only mechanics are identical to the existing registry.

### D5 — Reasoning: security specialists live only in harness layer ④
Security-domain reasoners draft T1 triage of a finding and T2 response advice, exactly as PB-SRE's nine
SRE specialists do in layer ④. **The LLM lives only in layer ④** — the same platform invariant. Every
"allowed / not-allowed" decision and every response remains deterministic (tiers + gates).

### D6 — Response is tiered by the same action-tier table, extended with security actions (inherits I5)
Security containment defaults to **T3 (human-in-the-loop, approval within a window)**. A deliberately
narrow **T4 allow-list** (bounded, reversible, safe-direction — e.g. revoke an *already-leaked
ephemeral* token; quarantine to an isolated namespace with auto-rollback + notify) exists in the table
but **ships default-OFF**, degrading to T3 off-plan. The **NEVER-T4 list** is enumerated and marked
**non-amendable by agents** (the C2 asymmetry applied to the action table): credential/key *deletion*
(vs rotation), disabling MFA or security controls, modifying or disabling audit logging, IAM policy
*broadening*, security-group / firewall *widening*, data deletion, mass or production quarantine, any
change to the platform-design security substrate (Cedar / OPA / Kyverno / KMS), and disabling the gate
or a detector itself. The full mapping is the security action-tier table in
[ai-security-program.md](../ai-security-program.md).

### D7 — Security gates fail closed under severance; security detection degrades open
The security-specific inversion of AI SRE's degraded mode:

- **Gate under severance fails CLOSED** — a verifier that cannot obtain its baseline (IAM / SBOM /
  exposure source down) returns **REQUIRE_HUMAN**, never PROCEED.
- **Detection under severance degrades OPEN** — a detector that loses Omniscience falls back to direct
  sources (AWS / registry / kubectl), slower but functional — **and detector liveness is monitored**,
  because a detector that suddenly reports nothing may have been disabled by an adversary, not
  satisfied.
- Any auto-response **preserves forensic evidence first**.

### D8 — Trust and severance rules apply verbatim, and matter more here (inherits ADR-0002 C1/C2, ADR-0004)
Any body change to a security runbook auto-re-quarantines it in every runtime (**C1**); an agent may
refine a runbook *body* but **never** its success criteria (**C2**). A tampered security runbook is an
attack vector, so these defenses are load-bearing, not incidental. Security lessons enter the
Experience plane ([ADR-0004](0004-experience-plane.md)) as **verification-grounded** items: a
containment counts `verified` only from independent confirmation, never self-report.

### D9 — Permanent fixes flow through the factory as committed specs (inherits ADR-0003, ADR-0005)
A patch, a policy hardening, or an IAM tightening is a task with a `task_id`, a class, and a tier; a P0
lane buys queue position, never gate skips. An optional **Security Standing Role** (ADR-0005) watches
security concerns and spawns human-merge-gated loops. Containment (runtime state) never waits for the
factory; the durable fix never bypasses it.

## Consequences

**Positive**
- One measuring stick (I6 OutcomeEvent), one Done semantics (I3), one audit trail, one eval harness
  across SRE and Security. Security inherits the harness's maturity for free; only families are net-new.
- "Catch the class before it recurs" (ADR-0001) becomes the security scoreboard: each hand-solved
  security issue becomes a new detector **and** a runbook skill.
- The four knowledge planes compose unchanged — state (Omniscience), capability (Skills), experience
  (ADR-0004), repo-facts — now serving a security domain too.

**Negative / costs**
- `SentinelState` and the gate registry grow; a family selector (`--family`) is needed to keep SRE and
  security scans separable.
- Security detectors that need external feeds (CVE, IAM baseline) are offline-buildable now, but
  live-wiring is deferred exactly like Sentinel's Datadog/Loki adapters.

**Risks**
- Cross-domain human-role overlap (SRE on-call vs SecOps) — mitigated by starting SecOps-on-call as an
  extension of the SRE curator/on-call role and splitting only when volume justifies it.
- A security detector or runbook is itself an attack target — mitigated by C1/C2 (D8), fail-closed
  gates and detector-liveness monitoring (D7), and the non-amendable NEVER-T4 list (D6).

## Boundaries

| Concern | Owner | This domain's relationship |
|---|---|---|
| **Security policy substrate** — OPA/Kyverno/Checkov rules, Cedar policies, KMS, network policy, landing-zone security design, ADR-0055 graph contract | **platform-design** | AI Security **consumes** these as its detectors' baselines and its gate allow-lists. It **never authors** the substrate. |
| **Governance / compliance OF AI tools** — SR 11-7 model risk, ISO 42001 AIMS, EU AI Act, vendor compliance, MRM validation | **Model Risk Management + the AI Governance Committee** (compliance-framework §4.5 / Phase 1; "validation function must be separate from model development") | **OUT of scope.** Those controls govern the AI tools *themselves*. This domain is **AI performing security operations** on the platform — the other side of the boundary. |
| **Factory SDLC security review** — I4 producer≠verifier, code_review / fact_check stages, omnius `SkillContentGate` | **the factories (multiqlti / omnius)** | Boundary: SDLC review asks "is the code we are *writing* safe?"; AI Security asks "is the *running platform*, and this *change* to it, secure?" They **meet at the change-gate** — a factory PR passes the same security verifiers (D3). |
| **SRE reliability reasoning** — PB-SRE's nine specialists, the IRL | **the AI SRE program** | A parallel domain on the same harness. Security adds layer-④ security reasoners beside the SRE ones; no overlap. |
| **The harness core** — tiers, gates, the Sentinel engine, eval, registry mechanics | **genai-enablement / sre-harness** | Domain-neutral machinery. AI Security *populates* it; it does not modify it. **This is the "no fourth brain".** |

### "No fourth brain" — rationale
The platform's engines are Omniscience (knowing), the harness (gating/safety), the factories
(producing changes), and the layer-④ reasoners (judgement). AI SRE is not a new engine — it arranges
these into incident resolution. AI Security is the identical move for security: **detector + verifier +
runbook + reasoner families on the one harness.** A standalone security brain would fork Done-semantics,
telemetry, tiers, eval, and the registry — and enlarge the very attack surface it exists to shrink.

## Build order (future work — no code in this ADR)

Mirrors the AI SRE roadmap: *eval first, read-only value early, write-autonomy last and deterministic.*

1. **S0 — security lead-time eval scenarios** (offline, reuse `run_sentinel_eval`).
2. **S1 — three deterministic security detectors, offline** (the first increment), against the shipped
   Sentinel contract, registered in `DEFAULT_SECURITY_DETECTORS`:
   - `iam_policy_drift` — live IAM grants minus an approved baseline (a set-difference, structurally
     identical to `new_error_signature`); severity by action/resource sensitivity (wildcard /
     privilege-escalation → CRITICAL); confidence 1.0.
   - `cve_in_sbom` — each running workload's SBOM component matched against a known-vuln feed; severity
     by CVSS band; confidence 1.0 on exact version match. Built offline against a **fixture feed**; a
     live OSV/Trivy/Grype adapter lands later (documented TODO, no stub code — the Stage-2
     live-adapter precedent).
   - `exposed_surface_vs_policy` — each exposed surface (Service LB / Ingress / SG rule) not permitted
     by a declared exposure allow-list; severity by public × sensitive-port; confidence 1.0.
   - *Deferred, distinct from the above:* `credential_rotation_overdue` (age-since-rotation beyond
     policy) — **not** a duplicate of the shipped `saturation_expiry` detector, whose expiry branch is
     the *availability* framing (days-to-expiry). The two must not be merged.
3. **S2 — security gate verifiers** wired advisory (`secret_in_change` BLOCK primary; `secret_in_state`
   Sentinel defense-in-depth; `iac_security_regression`; `image_cve_gate`; `privileged_workload`).
4. **S3 — seed `security/` runbook skills** (D4).
5. **S4 — layer-④ security triage** (T1 triage / T2 advice).
6. **S5 — T3 bounded containment** (HITL); T4 allow-list default-OFF.
7. **S6 — permanent-fix chase** (patch / policy PR through the factory).

## Alternatives considered

1. **A separate AI-Security factory / brain** — rejected: recreates ADR-0003 divergence #2 (two Done
   semantics), forks telemetry / tiers / eval / registry, and doubles the attack surface.
2. **Security detection as a second, security-only Sentinel** — rejected: two engines to maintain and
   two eval loops; a `DEFAULT_SECURITY_DETECTORS` family under one engine (D2) gives the same
   separation for free.
3. **Secret detection as a Sentinel detector** — rejected as the *primary* placement: a secret in a
   diff is point-in-time, which is a gate concern per ADR-0001's own taxonomy; Sentinel keeps only the
   defense-in-depth `secret_in_state` (D3).
4. **Fold security governance (SR 11-7 / ISO 42001) into this domain** — rejected: that is governance
   *of* AI tools, owned by MRM and the AI Governance Committee (*Boundaries*); conflating it would blur
   "AI doing security" with "is our AI compliant".

## Follow-ups

- [ ] Author S0–S1 as committed specs (ADR-0005) once this ADR is accepted.
- [ ] Add `DEFAULT_SECURITY_DETECTORS` + the `--family` CLI selector to the Sentinel package.
- [ ] Extend `ACTION_TIER_TABLE` with the security actions and the non-amendable NEVER-T4 list (D6).
- [ ] Create `skills/security/` and seed the three response runbooks (D4).
- [ ] Document the live IAM-baseline / SBOM / exposure source contracts (deferred adapters, D2/S1).
- [ ] Add an "AI Security domain" row to the glossary's Part 2 after acceptance.

## References

- [ai-security-program.md](../ai-security-program.md) — the program definition this ADR anchors
- [ai-sre-program.md](../ai-sre-program.md) — the sibling domain whose shape this mirrors
- [ADR-0001](0001-continuous-detection-sentinel.md) (Sentinel detector contract),
  [ADR-0002](0002-platform-skills-registry.md) (skills registry + C1/C2 trust),
  [ADR-0003](0003-unified-sdlc-standard.md) (quality-gated Done, action-tier table, I6/I8),
  [ADR-0004](0004-experience-plane.md) (verification-grounded memory),
  [ADR-0005](0005-autonomous-factory-intake.md) (committed-spec intake, standing roles)
- [platform-glossary.md](../platform-glossary.md) — autonomy tiers, gate vs guardrail, severance
- Sentinel contract: `solutions/sre-harness/src/sre_harness/sentinel/` ·
  gate: `solutions/sre-harness/src/sre_harness/change_gate.py`, `change_checks.py` ·
  action-tier table: `solutions/sre-harness/src/sre_harness/autonomy_tiers/action_table.py`
- `research/sections/compliance-framework.md`, `research/comparisons/vendor-compliance-matrix.md` — the
  governance-of-AI-tools scope this domain is bounded *against*
