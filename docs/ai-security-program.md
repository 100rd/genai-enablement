# AI Security — Program Definition

**Status:** Proposed working definition · 2026-07-07 · acceptance-readiness review 2026-07-16
**Companion docs:** [ADR-0008](decisions/0008-ai-security-domain.md) (AI Security as a domain over the
shared harness) · [ai-sre-program.md](ai-sre-program.md) (the sibling domain this mirrors) ·
[ADR-0001](decisions/0001-continuous-detection-sentinel.md) (Sentinel) ·
[ADR-0003](decisions/0003-unified-sdlc-standard.md) (Proposed SDLC bridge/action-tier authority) ·
[ADR-0020](decisions/0020-barbarossa-continuous-management-plane.md) (Barbarossa Security pack) ·
[platform-glossary.md](platform-glossary.md) (vocabulary)

## Mission

**AI Security owns detection coverage and the operational interpretation of security posture; source
owners own their observed facts, Barbarossa admits evidence and deterministically issues Security-pack
condition snapshots, Omniscience owns only cited knowledge/context projections, platform-design owns
policy, and humans own response decisions.** Measured on lead-time-to-detection and
mean-time-to-contain, not alerts triaged.
Two anchor facts shape everything: SOTA agents autonomously resolve only ~11% of incidents (ITBench) —
so the bet is on the machinery around agents, never on agent autonomy; and, unique to security, **an
adversary is present and a false negative is a breach, not a slow page** — which pushes the autonomy
bet even harder onto the deterministic harness.

AI Security is **the program feeding Barbarossa's isolated Security domain pack, not a second
management runtime** (ADR-0008/0020): reusable Sentinel, change-gate, eval, skill and tier assets are
populated with security detector, verifier, runbook and reasoner families. It shares mechanics with
other packs, never their policy, evidence, identity, authority or readiness.

## The two loops

AI Security runs the **Security Incident Response Loop (SIRL)** — a lifecycle distinct from the SDLC.
It is a local operational state machine aligned with the detection, response, recovery, and continuous-
improvement concerns in [NIST SP 800-61 Rev. 3](https://doi.org/10.6028/NIST.SP.800-61r3); it is not a
literal mapping of NIST's CSF 2.0 lifecycle model:

```
SIRL:  DETECTED → TRIAGED → CONTAINED → ERADICATED → RECOVERED → LEARNED   (seconds–minutes)
                               │                          ▲
                               └────────── bridge ────────┘
SDLC:  TRIGGERED → … → VERIFIED → GATED → LANDED                            (hours–days, factory)
```

- **Containment does not wait for the durable SDLC**: isolating a compromised workload, revoking a
  leaked credential, or restricting an exposed surface is runtime-state work. Barbarossa may request
  it only after current security policy, constraints and human/owner authority join; Omnius
  re-authorizes and executes it, and fresh independent security evidence verifies containment.
- **The permanent fix never bypasses the factory**: the durable change (patch, policy hardening, IAM
  tightening, closing the injection vector) becomes a committed SPEC under accepted ADR-0005. Its
  executable SDLC bridge waits until proposed ADR-0003 is accepted or replaced (P0 priority will buy
  queue position, never gate skips).
- **Two speeds, two causes**: containment needs only the *operational* fact ("this key is public",
  "this port is open to `0.0.0.0/0`") — fast, from the graph; the *root cause* (how it got committed,
  how to close the class) is the factory's job later.
- **Adversary-aware, evidence-first**: containment buys the human a decision window; it does not
  destroy state. **Forensic evidence is preserved before any auto-response.**
- **Permanent-fix chase is linked follow-up, not closure authority**: `incident_id` joins `task_id`, but
  a landed fix is factory evidence rather than a security-incident verdict. Independent containment/
  recovery evidence and human-owned incident policy govern closure; unresolved durable work remains a
  linked case or accepted-risk item.

## The seven layers

The same seven harness layers AI SRE runs on, populated with security families. **LLM lives only in
layer ④.** Everything that decides "allowed / not allowed" and everything that responds is deterministic.

| # | Layer | What it does (security) | LLM | Built from |
|---|---|---|---|---|
| ① | **Prevention** | security **verifier family** in the change-gate: `secret_in_change` (BLOCK), `iac_security_regression`, `image_cve_gate`, `privileged_workload` — catch an insecure change *before* it lands; activation waits for accepted gate/SDLC authority | no | sre-harness change-gate + gate CLI (harness Stage 2; proposed ADR-0003 GATED phase) |
| ② | **Detection** | security **detector family** in Sentinel: IAM drift vs baseline, CVE-in-SBOM, exposed-surface-vs-policy, secret-in-state (defense-in-depth) — pure rules over normalized, revision-bound facts; missing/stale/partial source coverage is explicit liveness failure, never a clean posture; secret-bearing findings store fingerprint/location only — values are redacted, never persisted, audited, or sent to a model | no | Sentinel (ADR-0001), `DEFAULT_SECURITY_DETECTORS` family |
| ③ | **Knowledge** | source-owner facts admitted directly or through exact cited Omniscience projections: IAM inventory, SBOMs, exposure surfaces and deploy events; plus severable threat context | no | Omniscience v0.5.0 released; MCP v1 plus required security sources/severance evidence remain in progress |
| ④ | **Reasoning** | T1 triage of a finding (what is it, blast radius, confidence); T2 response advice (rotate / patch / restrict / quarantine). The only LLM layer | **yes** | security specialists in harness tiers, beside PB-SRE's SRE specialists |
| ⑤ | **Safety** | autonomy tiers T1–T4 with degradation; the **security action-tier table** (below); verdicts PROCEED/BLOCK/REQUIRE_HUMAN; **response is deterministic, never LLM** | no | sre-harness core (merged) |
| ⑥ | **Action** | bounded containment starts **T3-only** (rotate/quarantine/restrict with a human window) through an Omnius owner adapter; any future T4 quarantine requires a separate accepted action profile and ships default-OFF; Barbarossa independently verifies outcome; durable changes use the factory | no | Barbarossa Security/action contracts + Omnius owner receipts + action-tier table and `security/` runbooks |
| ⑦ | **Learning** | post-incident: machine drafts, human finalizes (forensics-aware); each hand-solved issue becomes a new **detector** *and* a **`security/` runbook skill** (tier-tagged) → next occurrence is faster; eval cases grow from real incident replays | partly | skills registry `security/` namespace + eval lead-time scenarios |

The loop gets faster through layer ⑦ — learning — never by cutting gates.

## Normalized security-signal boundary

The first detector increment is deliberately a contract over normalized facts, not an adapter project.
Every enabled security signal carries an exact policy revision, source-manifest revision, observation
time, freshness ceiling, coverage result, and evidence scope. Live/provider payloads are normalized and
redacted before the immutable `SentinelState` boundary. Raw IAM policy documents, SBOM/feed bodies,
manifests, credentials, secret values, provider exceptions, and client objects never enter detector
state, findings, audit storage, or prompts.

Family selection is explicit: existing callers retain the ordered SRE `DEFAULT_DETECTORS`; the future
`DEFAULT_SECURITY_DETECTORS` is separate; `all` is a duplicate-id-rejecting deterministic concatenation.
The CLI default is and remains `sre`; changing it requires a separate versioned breaking decision even
after admission. Selecting `security` or `all` requires complete, fresh source-health records for every
enabled detector. Missing,
stale, partial, foreign-revision, or malformed coverage produces an incomplete/liveness disposition and
cannot enter the clean-scenario false-positive denominator.

Detector-specific facts also avoid overclaiming:

- IAM drift consumes normalized evaluated-grant facts and reports declared/effective scope only to the
  level proved by SCP, boundary, resource-policy, session-policy, condition, and evaluator coverage.
- CVE-in-SBOM binds the running workload revision, SBOM digest, normalized package identity, advisory
  and matcher revisions, applicability, and a versioned CVSS vector. Exact package text is not by itself
  applicability, and [CVSS v4.0](https://www.first.org/cvss/v4.0/specification-document) Base severity
  is not a substitute for Threat and Environmental context.
- Exposure drift consumes a coverage-complete normalized reachability fact and an independently
  published allow-list/sensitivity policy; the detector does not derive policy from the observed world.

## The security action-tier table

This is the target extension/refinement of the harness `ACTION_TIER_TABLE`, not current executable
state. The table today classes broad `iam_change` / `security_group_change` labels as T3 but does not
distinguish tightening from broadening. Those labels remain conservative classification inputs only and
cannot authorize an S5 provider call. Before S5, an accepted action SPEC must introduce exact
direction-specific action ids, keep the NEVER-T4 set out of the executable agent registry, and bind the
protected human-only path. The resulting table is the SR 11-7 governance artifact for the security domain.

| Action | Tier | Rationale |
|---|---|---|
| Scan a diff/SBOM for secrets/CVEs; read IAM/CloudTrail; diff IAM vs baseline; read exposed surfaces | **T1** | Read-only detection |
| Draft a security finding / triage note; **recommend** rotate-key / patch / block-merge / quarantine | **T2** | Advisory; a human acts |
| Rotate a credential/secret; quarantine a workload to an isolated namespace; disable a suspicious IAM principal; add a deny network-policy; block an egress | **T3 (HITL, human window)** | State-changing, security-sensitive, reversible-with-effort → single human approval within a window |
| Revoke an **already-leaked ephemeral** token | **T3** | Revocation is irreversible under the current T4 contract; safe direction and natural expiry do not manufacture reversibility |
| *(future candidate; narrow, opt-in, default-OFF)* quarantine-to-isolated-namespace with **auto-rollback + notify** | **No T4 authority yet** | Requires a separate accepted action SPEC, deterministic predicate, exact bounded target, forensic preservation, idempotence, rollback, kill-switch, notification, and retained drills; otherwise T3 |
| Roll back a canary on a security regression | *(deterministic, not agent)* | Argo Rollouts analysis decides |
| **NEVER-T4** (non-amendable by agents): delete a credential/key (vs rotate) · disable MFA / security controls · modify or disable audit logging · IAM policy *broadening* · security-group / firewall *widening* · data deletion · mass or production quarantine · touch the platform-design security substrate (Cedar/OPA/Kyverno/KMS) · disable the gate or a detector itself · mutate the skills-registry trust store (`skills-lock.json` / CODEOWNERS / a skill's success criteria) · tamper with the eval harness or its golden sets | **Target: DENY / protected human-only path** | Not implemented by today's broad T3 labels; the pre-S5 action SPEC must keep exact NEVER-T4 actions out of the executable registry; an ambiguous `T3+` label is not an executable tier |

## Degraded mode (deliberate design property — the security inversion)

Omniscience is the default source for IAM baselines, SBOMs, and exposure inventory. The security
domain **inverts** AI SRE's degraded mode by surface:

- **The gate fails CLOSED.** A security verifier that cannot obtain its baseline returns
  **REQUIRE_HUMAN**, never PROCEED — an unverifiable change is a human decision.
- **Detection degrades OPEN at the adapter boundary.** A pure detector never performs I/O. An admitted
  source adapter that loses the hub may produce the same normalized contract from direct sources (AWS /
  registry / Kubernetes) using a separately bound **least-privilege fallback credential no wider than
  the hub path**. If complete fresh facts cannot be produced, the family reports incomplete/liveness
  state rather than silence; a detector that suddenly reports nothing may have been *disabled by an
  adversary*, not satisfied.
- **Evidence is preserved before any auto-response.**

Severance is mandatory for every hub consumer (glossary: *Severance*).

## Humans

| Role | Owns |
|---|---|
| **SecOps on-call** | receives an assembled security case (not a raw alert); approves T3 containment; can halt any future admitted T4 action |
| **Security curator** | owns the security action-tier table (incl. the non-amendable NEVER-T4 list); admits `security/` runbook skills into the registry; finalizes forensics-aware post-incident reports |

SecOps on-call **starts as an extension of the SRE curator/on-call role**, splitting into a distinct
rota only when security volume justifies it. The inversion is the same as AI SRE's: humans move from
*reading dashboards* to *making decisions and curating correctness*. If the proposed ADR-0002 skill
surface is accepted, agents never edit their own success criteria (its C2 invariant).

## Metrics (local now; future OutcomeEvent mapping awaits ADR-0003 acceptance)

- **Lead-time-to-detection** — how early a security detector surfaces the risk before exploit/page
  (reuse Sentinel's lead-time eval verbatim).
- **Mean-time-to-contain (MTTC)** — the security analogue of MTTR (DETECTED → CONTAINED).
- **Escaped-findings** — a secret / CVE / misconfiguration that reached production uncaught; the return
  signal MUST be independent of the verifier that passed it. This locally restates the proposed
  ADR-0003 I8 invariant without treating that ADR as accepted.
- **Share of findings auto-contained at T4 without a human** — exactly 0 while no T4 authority exists;
  if a later action SPEC is accepted, its measured target remains near zero by design.
- **Share of PRs with a security verdict ready at merge** — prevention coverage.
- **Coverage / class-conversion** — how many security problem classes have become detectors (the
  leverage scoreboard).
- **Source-health coverage** — complete/fresh/partial/unavailable scans by detector and Realm; an
  unavailable source is excluded from clean-world false-positive claims, not counted as zero findings.
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
**Missing (in unblocking order):** ⓪ human acceptance or revision of ADR-0008 and its staged dependency
boundary → ① the three deterministic security detectors, offline
(`iam_policy_drift`, `cve_in_sbom`, `exposed_surface_vs_policy`) → ② the security gate verifiers,
advisory → ③ the `security/` skills namespace + seed runbooks → ④ the layer-④ security reasoners → ⑤
live IAM / SBOM / exposure sources → ⑥ the escaped-findings join.

## Roadmap

Human accept/revise ADR-0008 → S0 security lead-time eval scenarios → **S1 the three deterministic
detectors, offline ← first implementation increment** → S2 security gate verifiers wired advisory only
after accepted gate/SDLC authority → S3 seed `security/` runbook skills only after accepted registry trust
authority → S4 layer-④ security triage (T1/T2) → S5 T3 bounded containment (HITL; no initial T4
authority) → S6 permanent-fix chase (patch / policy PR through the factory).

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
