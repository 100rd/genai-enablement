# ADR-0008: AI Security as a domain over the shared harness — detector, verifier, runbook and reasoner families, not a fourth brain

- **Status:** Proposed
- **Date:** 2026-07-07
- **Last reviewed:** 2026-07-16 (acceptance-readiness hardening; status unchanged)
- **Deciders:** platform owner
- **Scope:** genai-enablement (this contract); consumes the platform-design security substrate; informative for PB-SRE, multiqlti, omnius
- **Vocabulary:** terms as defined in [platform-glossary.md](../platform-glossary.md) ·
  detection per [ADR-0001](0001-continuous-detection-sentinel.md) · skills per
  [ADR-0002](0002-platform-skills-registry.md) · Done/tiers per
  [ADR-0003](0003-unified-sdlc-standard.md) · memory per [ADR-0004](0004-experience-plane.md) ·
  Continuous Management placement per proposed
  [ADR-0020](0020-barbarossa-continuous-management-plane.md)

> ADR numbers 0006 (unified loop decision model, PR #19) and 0007 (platform portal, PR #22)
> landed alongside this ADR; it claims **0008** and does not depend on their content.

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

The harness already defines every primitive such a domain needs. The change-gate, the tier engine +
action-tier table, and the skills registry are merged and unit-tested on `main`; **Sentinel is
landed on `main` via PRs #18/#24**:

- **Sentinel** ([ADR-0001](0001-continuous-detection-sentinel.md)) — a continuous-detection surface
  with a pure `Detector(SentinelState) -> Sequence[Finding]` contract, deterministic-first, dedup +
  rank by `severity × confidence`, scored offline by the eval harness on **lead-time**; detection is
  read-only (**T1**), emitting a finding is advisory (**T2**).
- **The change-validation gate** (the harness Stage-2 multi-check gate; ADR-0003 contributes the GATED
  lifecycle phase) — a pure `Check(ChangeRequest, PlatformGraph) -> CheckResult` contract aggregated to
  a `PROCEED / BLOCK / REQUIRE_HUMAN` verdict.
- **The autonomy-tier engine + action-tier table** — `ACTION_TIER_TABLE` already classes
  `iam_change` and `security_group_change` as **T3** (human-approved).
- **The skills registry** ([ADR-0002](0002-platform-skills-registry.md)) — SKILL.md canon, git-backed,
  per-runtime trust, with an `sre/` namespace already precedent for a domain category.

Building a *separate* AI-Security factory or a standalone security "brain" would recreate ADR-0003's
divergence #2 (two Done/verdict semantics), fork the audit/telemetry surface (I6), duplicate the
tier/eval/registry machinery — and **double the trust surface an attacker can target**. That is the
opposite of the platform's consolidation direction.

## Acceptance boundary and prerequisite authority

This document is a proposed cross-repository decision, not implementation or activation authority.
Acceptance would authorize authorship and review of the bounded S0/S1 task SPECs under accepted
[ADR-0001](0001-continuous-detection-sentinel.md); it would not approve a live source, a production
baseline, a security policy, a write credential, a response action, or a deployment.

ADR-0002 and ADR-0003 are still **Proposed**. References to their vocabulary and candidate mechanisms
do not accept them transitively and cannot make their dependent surfaces ready. The staged authority is:

- **S0/S1** depend on this ADR being accepted and on accepted ADR-0001. They remain offline,
  deterministic, fixture-scoped construction until separate external publications and live evidence
  exist.
- **S2** cannot activate a security change-gate until the gate/SDLC authority in ADR-0003 is accepted
  or replaced by another accepted decision with the same producer/verifier and fail-closed invariants.
- **S3** cannot publish or activate `security/` skills until ADR-0002's trust-root, revision pinning,
  C1/C2, and CODEOWNERS authority are accepted and materially bound.
- **S4-S6** cannot gain response or factory authority from this ADR. Each needs its own accepted SPEC,
  existing tier authority, exact human/policy bindings, and the external/live evidence named below.

The platform owner must accept or revise this dependency split explicitly. An agent must not change
this ADR's status, infer acceptance from code or tests, or begin S0/S1 because the proposal is detailed.

## Decision

Adopt **AI Security as a domain over the shared harness**. It contributes *families* to the existing
surfaces; it never forks the harness core, the Sentinel engine, the gate aggregator, or the eval loop.
One reusable harness may serve multiple isolated domains. If ADR-0020 is also accepted, Barbarossa's
Security pack owns the continuous exposure/control/outcome loop; this ADR remains the domain-specific
detector, verifier, runbook and reasoner-family decision and grants no Barbarossa or Omnius authority.

### D1 — A domain, not a new engine
AI Security is a program that arranges the existing engines (Omniscience = state, the harness =
gates/tiers, the factories = change production, layer-④ reasoners = judgement) into a security
capability — exactly as AI SRE arranges them into an incident-resolution capability. There is **no new
factory and no fourth brain** (see *Boundaries* and *"No fourth brain"* below).

### D2 — Detection: a security detector family in Sentinel (inherits ADR-0001)
Security detectors are pure `Detector(SentinelState) -> Sequence[Finding]` callables registered in a
new `DEFAULT_SECURITY_DETECTORS` family constant, run by the **same** `run_sentinel` primitive under a
thin family dispatcher and scored by the **same** lead-time eval. `SentinelState` grows new *optional*
typed signal fields so existing SRE callers and state files remain behavior-compatible. A selected
security scan is stricter:
the dispatcher requires an exact health/coverage/freshness record for every enabled security source
before invoking the pure detectors. Missing, stale, partial, or revision-mismatched input is an explicit
incomplete/liveness result, never a clean posture result and never a clean eval scenario.

Detection stays **T1**; emitting a finding stays **T2**. One Sentinel registry serves both domains.
The CLI selector is `--family sre|security|all`; its compatibility default is and remains `sre`.
Changing that default is a separate versioned breaking decision even after security admission;
`security` and `all` are explicit opt-ins. The existing `DEFAULT_DETECTORS` remains the ordered SRE
family for existing callers;
`DEFAULT_SECURITY_DETECTORS` is separate; `all` is their deterministic concatenation and fails closed
on duplicate detector ids. Family selection changes membership only, never tier, rank, dedup, storage,
or finding semantics.

Each S1 detector consumes only a closed, bounded, immutable **normalized fact** plus exact policy/source
revision, observation time, freshness ceiling, coverage, and evidence scope. Raw IAM policy documents,
raw SBOMs, manifests, vulnerability-feed bodies, credentials, secret values, provider errors, and live
client objects never enter `SentinelState`, a finding, audit storage, or a prompt. Source and fallback
adapters normalize outside the detector and publish the same typed contract. Fixture inputs are marked
fixture-only and cannot support a live or production claim.

### D3 — Prevention: a security verifier family in the change-gate (harness Stage 2; ADR-0003 contributes the GATED phase + action-tier extension)
Security verifiers are pure `Check` callables added to the gate registry (e.g. `secret_in_change`,
`iac_security_regression`, `image_cve_gate`, `privileged_workload`). ADR-0001's own taxonomy already
places "secret / ExternalSecret declared" and "deployment-strategy fits workload role" as **gate**
checks — security verifiers extend that Stage-2 multi-check gate; they are **not** Sentinel detectors.
**Secret detection is primarily a gate verifier** (`secret_in_change`, BLOCK on a secret added in a
diff); a Sentinel `secret_in_state` detector is defense-in-depth only (secrets already live in
ConfigMaps/env that bypassed the gate). **Secret material never leaves as a value:** a secret-bearing
finding stores only a fingerprint and location (repo / path / line, ConfigMap / key), never the secret
value — values are redacted before the finding is persisted, before it enters the WORM audit trail or
any at-rest store, and before any layer-④ prompt. This extends ADR-0001's *names / keys, never values*
rule to the security domain.

### D4 — Capability: a staged `security/` namespace in the skills registry
A new top-level `skills/security/` sits beside `engineering/` and `sre/`, holding runbook-type SKILL.md
with step-level tier tags (seed: `security/leaked-credential-response`,
`security/exposed-endpoint-response`, `security/critical-cve-response`). REGISTRY.md index +
`skills-lock.json` + CODEOWNERS-gate + PR-only mechanics are identical to the existing registry.

### D5 — Reasoning: security specialists live only in harness layer ④
Security-domain reasoners draft T1 triage of a finding and T2 response advice, exactly as PB-SRE's nine
SRE specialists do in layer ④. **The LLM lives only in layer ④** — the same platform invariant. Every
"allowed / not-allowed" decision and every response remains deterministic (tiers + gates). Secret
material never enters a layer-④ prompt — reasoners receive redacted findings (fingerprint + location),
never secret values (D3).

### D6 — Response is staged through the same action-tier table
Security containment starts **T3-only (human-in-the-loop, approval within a window)**. Revoking even an
already-leaked ephemeral token is irreversible and therefore remains T3 under the current T4 contract;
"safe direction" and natural expiry do not manufacture reversibility. A future, separately accepted
action SPEC may propose a deliberately narrow T4 quarantine action only when it has a deterministic
predicate, exact bounded target, forensic preservation, idempotence, automatic rollback, notification,
kill-switch, and retained positive/negative/severance drills. It ships default-OFF and degrades to T3
off-plan. **The predicate gating any future T4 action must itself be a deterministic gate / graph fact,
never a layer-④ LLM inference**; otherwise an LLM judgement would drive an autonomous action, which D5
forbids.

The **NEVER-T4 list** is enumerated and marked **non-amendable by agents** (the C2 asymmetry applied to
the action table):
credential / key *deletion* (vs rotation), disabling MFA or security controls, modifying or disabling
audit logging, IAM policy *broadening*, security-group / firewall *widening*, data deletion, mass or
production quarantine, any change to the platform-design security substrate (Cedar / OPA / Kyverno /
KMS), disabling the gate or a detector itself, mutating the skills-registry trust store
(`skills-lock.json` / CODEOWNERS / a skill's success criteria), and tampering with the eval harness or
its golden sets. This is the target security contract, not a claim about the current table: today's broad
`iam_change` and `security_group_change` T3 classifier entries do not distinguish tightening from
broadening and therefore cannot authorize any S5 provider call. Before S5, an accepted action SPEC must
replace or refine broad security labels with exact direction-specific action ids, keep every NEVER-T4
action out of the executable agent registry, and route it to a protected human-only process. An ambiguous
`T3+` label is not an executable tier. The full target mapping is the security action-tier table in
[ai-security-program.md](../ai-security-program.md).

### D7 — Security gates fail closed under severance; security detection degrades open
The security-specific inversion of AI SRE's degraded mode:

- **Gate under severance fails CLOSED** — a verifier that cannot obtain its baseline (IAM / SBOM /
  exposure source down) returns **REQUIRE_HUMAN**, never PROCEED.
- **Detection under severance degrades OPEN at the source-adapter boundary** — a detector never performs
  I/O. An admitted adapter that loses Omniscience may obtain the same normalized fact contract from a
  direct source (AWS / registry / Kubernetes) using a separately bound, least-privilege fallback
  credential scoped no wider than the hub path. If that cannot produce complete, fresh, revision-bound
  facts, the family dispatcher reports incomplete/liveness state; detector silence is not satisfaction.
- Any auto-response **preserves forensic evidence first**.

### D8 — Trust and severance rules are mandatory, and matter more here
If/when the ADR-0002 skill surface is accepted, any body change to a security runbook must
auto-re-quarantine it in every runtime (**C1**); an agent may refine a runbook *body* but **never** its
success criteria (**C2**). This ADR repeats those requirements but does not activate ADR-0002. A
tampered security runbook is an attack vector, so these defenses are load-bearing, not incidental.
Security lessons enter the
Experience plane ([ADR-0004](0004-experience-plane.md)) as **verification-grounded** items: a
containment counts `verified` only from independent confirmation, never self-report.

### D9 — Permanent fixes flow through the factory as committed specs
Accepted ADR-0005 supplies the committed-SPEC and optional **Security Standing Role** shape. A patch,
policy hardening, or IAM tightening becomes a task with a `task_id`; once an accepted SDLC/tier contract
exists, its class, tier, gates, and terminal evidence are bound there. A P0 lane buys queue position,
never gate skips. Containment (runtime state) never waits for the factory; the durable fix never bypasses
it. This decision does not activate a role or accept ADR-0003 by reference.

## Consequences

**Positive**
- One eval harness and one audit surface across SRE and Security now; once ADR-0003 or a replacement is
  accepted, its single OutcomeEvent and Done semantics also apply without a domain fork. Security
  inherits the harness's maturity; only families are net-new.
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
| **The harness core** — tiers, gates, the Sentinel engine, eval, registry mechanics | **genai-enablement / sre-harness** | Domain-neutral machinery. AI Security extends stable typed extension points (family dispatch, normalized state, detectors and scenarios) through accepted SPECs; it neither forks the core nor changes its authority semantics. **This is the "no fourth brain".** |

### "No fourth brain" — rationale
The platform's engines are Omniscience (knowing), the harness (gating/safety), the factories
(producing changes), and the layer-④ reasoners (judgement). AI SRE is not a new engine — it arranges
these into incident resolution. AI Security is the identical move for security: **detector + verifier +
runbook + reasoner families on the one harness.** A standalone security brain would fork Done-semantics,
telemetry, tiers, eval, and the registry — and enlarge the very attack surface it exists to shrink.

## Build order (future work — no code in this ADR)

Mirrors the AI SRE roadmap: *eval first, read-only value early, write-autonomy last and deterministic.*

1. **S0 — security lead-time eval scenarios** (offline, reuse `run_sentinel_eval`). The corpus has
   detector-specific positive and complete clean controls plus missing, stale, partial, foreign-revision,
   malformed and secret-leakage negative controls. A clean scenario is eligible for the false-positive
   denominator only when all required source-health records say complete and fresh.
2. **S1 — three deterministic security detectors, offline** (the first increment), against the Sentinel
   contract (landed via PRs #18/#24), registered in
   `DEFAULT_SECURITY_DETECTORS`:
   - `iam_policy_drift` — a set difference over normalized evaluated-grant facts and an independently
     published baseline revision. It must not claim effective access when SCPs, boundaries, resource
     policies, session policies, conditions, or evaluator coverage are unknown. Severity follows the
     bounded action/resource sensitivity policy; confidence describes exact drift detection, not attack
     likelihood.
   - `cve_in_sbom` — an exact running-workload/SBOM revision joined to a normalized package identity,
     advisory/feed revision, version-range matcher revision, applicability result, and versioned CVSS
     vector. A package-version string match alone cannot claim applicability; CVSS Base alone cannot
     stand in for threat/environment context. Built offline against a **fixture feed**; a live
     OSV/Trivy/Grype adapter lands later and remains outside the pure detector.
   - `exposed_surface_vs_policy` — a normalized, coverage-complete reachability fact (Service / Ingress /
     security-group composition) absent from an independently published exposure allow-list. Severity
     follows the versioned public-reachability × service-sensitivity policy, not detector-authored values.
   - *Deferred, distinct from the above:* `credential_rotation_overdue` (age-since-rotation beyond
     policy) — **not** a duplicate of the `saturation_expiry` detector (on PRs #18/#24), whose expiry
     branch is the *availability* framing (days-to-expiry). The two must not be merged.
3. **S2 — security gate verifiers** wired advisory (`secret_in_change` BLOCK primary; `secret_in_state`
   Sentinel defense-in-depth; `iac_security_regression`; `image_cve_gate`; `privileged_workload`).
4. **S3 — seed `security/` runbook skills** (D4).
5. **S4 — layer-④ security triage** (T1 triage / T2 advice).
6. **S5 — T3 bounded containment** (HITL); no initial T4 authority.
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

- [ ] Platform owner accepts or revises the prerequisite/staged-authority split in this proposal.
- [ ] Author S0–S1 as committed specs (ADR-0005) once this ADR is accepted.
- [ ] Add `DEFAULT_SECURITY_DETECTORS` + the `--family` CLI selector to the Sentinel package.
- [ ] Before S5, replace/refine broad `iam_change` / `security_group_change` classification with exact
  direction-specific security action ids and a non-executable NEVER-T4/human-only boundary (D6).
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
- Sentinel contract: `solutions/sre-harness/src/sre_harness/sentinel/` (landed via PRs #18/#24)
  · gate: `solutions/sre-harness/src/sre_harness/change_gate.py`, `change_checks.py`
  · action-tier table: `solutions/sre-harness/src/sre_harness/autonomy_tiers/action_table.py`
- `research/sections/compliance-framework.md`, `research/comparisons/vendor-compliance-matrix.md` — the
  governance-of-AI-tools scope this domain is bounded *against*
- [NIST SP 800-61 Rev. 3](https://doi.org/10.6028/NIST.SP.800-61r3) — current incident-response
  recommendations integrated with CSF 2.0; the program lifecycle is a local operational state machine,
  not a claim to reproduce NIST's lifecycle verbatim
- [CVSS v4.0 specification](https://www.first.org/cvss/v4.0/specification-document) — versioned Base,
  Threat, Environmental and Supplemental metric semantics used by future vulnerability facts
