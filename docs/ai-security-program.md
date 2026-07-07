# AI Security — Program Definition

**Status:** Proposed working definition · 2026-07-07
**Companion docs:** [ADR-0008](decisions/0008-ai-security-domain.md) (AI Security as a domain over the
shared harness) · [ai-sre-program.md](ai-sre-program.md) (the sibling domain this mirrors) ·
[ADR-0001](decisions/0001-continuous-detection-sentinel.md) (Sentinel) ·
[ADR-0003](decisions/0003-unified-sdlc-standard.md) (SDLC bridge, action-tier table) ·
[platform-glossary.md](platform-glossary.md) (vocabulary)

## Mission

**AI Security owns the complete knowledge of the platform's security posture and exposure; humans own
response decisions.** Measured on lead-time-to-detection and mean-time-to-contain, not alerts triaged.
Two anchor facts shape everything: SOTA agents autonomously resolve only ~11% of incidents (ITBench) —
so the bet is on the machinery around agents, never on agent autonomy; and, unique to security, **an
adversary is present and a false negative is a breach, not a slow page** — which pushes the autonomy
bet even harder onto the deterministic harness.

AI Security is **a domain over the shared harness, not a second product** (ADR-0008): the same Sentinel
engine, the same change-gate, the same skills registry, the same tiers — populated with security
detector, verifier, runbook and reasoner *families*. One harness, two domains.

## The two loops

AI Security runs the **Security Incident Response Loop (SIRL)** — a lifecycle distinct from the SDLC,
mapped to NIST SP 800-61:

```
SIRL:  DETECTED → TRIAGED → CONTAINED → ERADICATED → RECOVERED → LEARNED   (seconds–minutes)
                               │                          ▲
                               └────────── bridge ────────┘
SDLC:  TRIGGERED → … → VERIFIED → GATED → LANDED                            (hours–days, factory)
```

- **Containment never waits for the factory**: isolating a compromised workload, revoking a leaked
  credential, or restricting an exposed surface is runtime-state work under the harness — no queue.
- **The permanent fix never bypasses the factory**: the durable change (patch, policy hardening, IAM
  tightening, closing the injection vector) goes through the SDLC standard (ADR-0003) as an
  incident-spawned task (P0 lane, same gates — priority buys queue position, never gate skips).
- **Two speeds, two causes**: containment needs only the *operational* fact ("this key is public",
  "this port is open to `0.0.0.0/0`") — fast, from the graph; the *root cause* (how it got committed,
  how to close the class) is the factory's job later.
- **Adversary-aware, evidence-first**: containment buys the human a decision window; it does not
  destroy state. **Forensic evidence is preserved before any auto-response.**
- **Permanent-fix chase**: the incident is not closed until the fix has LANDED; `incident_id` joins
  `task_id`.

## The seven layers

The same seven harness layers AI SRE runs on, populated with security families. **LLM lives only in
layer ④.** Everything that decides "allowed / not allowed" and everything that responds is deterministic.

| # | Layer | What it does (security) | LLM | Built from |
|---|---|---|---|---|
| ① | **Prevention** | security **verifier family** in the change-gate: `secret_in_change` (BLOCK), `iac_security_regression`, `image_cve_gate`, `privileged_workload` — catch an insecure change *before* it lands | no | sre-harness change-gate + gate CLI (harness Stage 2; ADR-0003 GATED phase) |
| ② | **Detection** | security **detector family** in Sentinel: IAM drift vs baseline, CVE-in-SBOM, exposed-surface-vs-policy, secret-in-state (defense-in-depth) — anomaly / new-class / risk over the running system; secret-bearing findings store fingerprint/location only — values are redacted, never persisted, audited, or sent to a model | no | Sentinel (ADR-0001), `DEFAULT_SECURITY_DETECTORS` family |
| ③ | **Knowledge** | Omniscience facts the detectors compare against: IAM inventory, SBOMs, exposure surfaces, deploy events; threat context | no | Omniscience v0.2 + new security connectors/operators |
| ④ | **Reasoning** | T1 triage of a finding (what is it, blast radius, confidence); T2 response advice (rotate / patch / restrict / quarantine). The only LLM layer | **yes** | security specialists in harness tiers, beside PB-SRE's SRE specialists |
| ⑤ | **Safety** | autonomy tiers T1–T4 with degradation; the **security action-tier table** (below); verdicts PROCEED/BLOCK/REQUIRE_HUMAN; **response is deterministic, never LLM** | no | sre-harness core (merged) |
| ⑥ | **Action** | bounded containment: **T3 by default** (rotate/quarantine/restrict with a human window); a narrow **T4 allow-list ships default-OFF**; durable changes — factory PR only | no | action-tier table + `security/` runbooks + SSM `aws:approve` |
| ⑦ | **Learning** | post-incident: machine drafts, human finalizes (forensics-aware); each hand-solved issue becomes a new **detector** *and* a **`security/` runbook skill** (tier-tagged) → next occurrence is faster; eval cases grow from real incident replays | partly | skills registry `security/` namespace + eval lead-time scenarios |

The loop gets faster through layer ⑦ — learning — never by cutting gates.

## The security action-tier table

Extends the harness `ACTION_TIER_TABLE` (which already classes `iam_change` / `security_group_change`
as T3). This is the SR 11-7 governance artifact for the security domain.

| Action | Tier | Rationale |
|---|---|---|
| Scan a diff/SBOM for secrets/CVEs; read IAM/CloudTrail; diff IAM vs baseline; read exposed surfaces | **T1** | Read-only detection |
| Draft a security finding / triage note; **recommend** rotate-key / patch / block-merge / quarantine | **T2** | Advisory; a human acts |
| Rotate a credential/secret; quarantine a workload to an isolated namespace; disable a suspicious IAM principal; add a deny network-policy; block an egress | **T3 (HITL, human window)** | State-changing, security-sensitive, reversible-with-effort → single human approval within a window |
| *(narrow, opt-in, **default-OFF**)* revoke an **already-leaked ephemeral** token; quarantine-to-isolated-namespace with **auto-rollback + notify** | **T4 (bounded)** | Safe-direction + time-bounded blast (the token expires regardless); the leaked+ephemeral predicate must be a deterministic gate/graph fact, never a layer-④ inference; degrade → T3 off-plan |
| Roll back a canary on a security regression | *(deterministic, not agent)* | Argo Rollouts analysis decides |
| **NEVER-T4** (human-gated always; non-amendable by agents): delete a credential/key (vs rotate) · disable MFA / security controls · modify or disable audit logging · IAM policy *broadening* · security-group / firewall *widening* · data deletion · mass or production quarantine · touch the platform-design security substrate (Cedar/OPA/Kyverno/KMS) · disable the gate or a detector itself · mutate the skills-registry trust store (`skills-lock.json` / CODEOWNERS / a skill's success criteria) · tamper with the eval harness or its golden sets | **T3+ / human** | Irreversible, control-weakening, adversary-exploitable, or self-referential — SR 11-7 "human-in-the-loop for high-risk" |

## Degraded mode (deliberate design property — the security inversion)

Omniscience is the default source for IAM baselines, SBOMs, and exposure inventory. The security
domain **inverts** AI SRE's degraded mode by surface:

- **The gate fails CLOSED.** A security verifier that cannot obtain its baseline returns
  **REQUIRE_HUMAN**, never PROCEED — an unverifiable change is a human decision.
- **Detection degrades OPEN.** A Sentinel security detector that loses the hub falls back to direct
  sources (AWS / registry / kubectl) — on a **least-privilege fallback credential no wider than the hub
  path**, so open-degradation never silently widens what a compromised detector can reach — slower,
  still functional — **and detector liveness is monitored**, because a detector that suddenly reports
  nothing may have been *disabled by an adversary*, not satisfied.
- **Evidence is preserved before any auto-response.**

Severance is mandatory for every hub consumer (glossary: *Severance*).

## Humans

| Role | Owns |
|---|---|
| **SecOps on-call** | receives an assembled security case (not a raw alert); approves T3 containment; can halt any T4 action |
| **Security curator** | owns the security action-tier table (incl. the non-amendable NEVER-T4 list); admits `security/` runbook skills into the registry; finalizes forensics-aware post-incident reports |

SecOps on-call **starts as an extension of the SRE curator/on-call role**, splitting into a distinct
rota only when security volume justifies it. The inversion is the same as AI SRE's: humans move from
*reading dashboards* to *making decisions and curating correctness*. Agents never edit their own
success criteria (C2, ADR-0002).

## Metrics (via OutcomeEvent, ADR-0003 I6/I8)

- **Lead-time-to-detection** — how early a security detector surfaces the risk before exploit/page
  (reuse Sentinel's lead-time eval verbatim).
- **Mean-time-to-contain (MTTC)** — the security analogue of MTTR (DETECTED → CONTAINED).
- **Escaped-findings** — a secret / CVE / misconfiguration that reached production uncaught; the return
  signal MUST be independent of the verifier that passed it (I8).
- **Share of findings auto-contained at T4 without a human** — ≈0 by design initially (the honest
  number, like AI SRE's T4 share).
- **Share of PRs with a security verdict ready at merge** — prevention coverage.
- **Coverage / class-conversion** — how many security problem classes have become detectors (the
  leverage scoreboard).
- **MTTR-permanent** — time to the durable fix LANDED (join `incident_id` → `task_id`).

## Boundary vs governance / compliance (what this program is NOT)

Governance and compliance **of the AI tools themselves** — SR 11-7 model risk, ISO 42001 AIMS, the EU
AI Act, the vendor compliance matrix, MRM validation — is owned by **Model Risk Management and the AI
Governance Committee** (under the CRO/risk function, separate from model development). That is out of
scope here. This program is the other side of the boundary: **AI performing security operations** on
the platform (detecting secrets, IAM drift, CVEs, exposure; responding to security incidents). See
ADR-0008 *Boundaries*.

## Maturity map (honest, 2026-07)

**Built (reused as-is):** the harness deterministic core + eval + gate CLI, the action-tier table, and
the skills registry mechanics (on `main`); the Sentinel engine, detector contract, dedup/rank, and
lead-time eval **landed on `main` via PRs #18/#24**. None of this is security-specific yet, and none needs re-building.
**Missing (in unblocking order):** ① the three deterministic security detectors, offline
(`iam_policy_drift`, `cve_in_sbom`, `exposed_surface_vs_policy`) → ② the security gate verifiers,
advisory → ③ the `security/` skills namespace + seed runbooks → ④ the layer-④ security reasoners → ⑤
live IAM / SBOM / exposure sources → ⑥ the escaped-findings join.

## Roadmap

S0 security lead-time eval scenarios → **S1 the three deterministic detectors, offline ← first
increment** → S2 security gate verifiers wired advisory → S3 seed `security/` runbook skills → S4
layer-④ security triage (T1/T2) → S5 T3 bounded containment (HITL; T4 allow-list default-OFF) → S6
permanent-fix chase (patch / policy PR through the factory).

## Relationship to prior art

Unlike AI SRE — which superseded the `ai-incident-agent` "smart pager" and absorbed PB-SRE's advisory
prototype — AI Security has **no superseded predecessor**; it is net-new families on proven machinery.
Its donors, carried forward (not replaced):

- **platform-design's security substrate** (OPA/Kyverno/Checkov, Cedar, KMS, network policy, 55 ADRs) —
  the *policy* this program's detectors and gates compare against; platform-design remains its owner.
- **omnius's `SkillContentGate`** (secret scan, content gate) — the factory-side precedent for
  content-level security checks; the change-gate is where the two surfaces meet.
- **PB-SRE's read-only guardrails** — the defense-in-depth discipline (guardrails filter, gates
  authorize) carried into the security verifier and reasoner families.
