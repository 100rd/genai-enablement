# Autonomous SRE Harness — Plan & Vision (v2, June 2026)

**Date**: 2026-06-16
**Supersedes (in framing, not detail)**: the SRE/AIOps workstream in `research/final-report.md` and the
"smart pager" scope of `solutions/ai-incident-agent/`.
**Grounded in**: `research/2026-agentic-sre-refresh.md` (mid-2026 landscape + engineering patterns).

---

## 1. The reframe

We started building an **AI Incident Agent** — a *smarter pager* that gathers context, drafts an RCA
hypothesis, matches a runbook, and sends an enriched notification to a human. Auto-remediation was a
"phase 6, optional" afterthought.

The target operating model (crystallized by a 2026 "AI-native SRE operator" job description, and
confirmed by where the market went) is different in kind:

> **The harness is the product.** Engineers build, operate, and maintain AI agents that *do the
> operations work* — pre-triage, change-validation gates, permanent-fix chase, RCA drafting, auto-healing
> — and write the AI + human runbooks those agents run on. They are measured on the **leverage the agent
> surface creates**, not tickets closed. Every production change goes through quality gates with a
> **tested rollback ready**, pulled the moment it goes off-plan. Every one-off solved by hand is
> generalized so an agent handles the next one.

So our product is not "an agent." It is the **harness**: the durable orchestration, the tool layer, the
retrievable runbook/skill library, the autonomy-tier gates, the eval loop, the audit trail, and the human
roles around it.

### Why this framing (the sobering anchor)
SOTA agents autonomously resolve only **~11%** of real SRE incidents end-to-end (ITBench, ICML 2025).
Betting on model autonomy is a losing bet today. Betting on the *harness* — where agents do the parts
they're good at (gather/correlate/draft) under hard gates — is the winning one.

---

## 2. The five pillars (from the operating model) -> what we build

| Pillar (job description) | What it means concretely | Build / Buy |
|---|---|---|
| **Pre-triage** | On alert, investigate *before paging* — hypotheses, targeted queries, confidence-scored draft | **Buy-first**: Datadog Bits AI / AWS DevOps Agent. **Build**: FS-specific triage + memory |
| **Change-validation gates** | Before a deploy/config sync, predict reliability/blast-radius impact -> proceed / block / require-human | **Build** (market white space). Agent advisory + deterministic policy gate |
| **Permanent-fix chase** | After mitigation, drive the *real* fix to done — open MR/ticket, track, never auto-merge | **Build**. Agent opens MRs/issues; humans review |
| **RCA drafting** | Audit-ready RCA: timeline, blast radius, contributing factors, evidence chain, confidence; fact vs inference separated | **Build on top of** Bits AI / DevOps Agent output |
| **Auto-healing** | Bounded, reversible, pre-approved remediation with tested rollback | **Build**, deterministic: GitOps PR / SSM runbook + Argo Rollouts auto-rollback. LLM proposes only |

---

## 3. The core safety primitive: autonomy tiers

Every agent action is classified into a tier. Higher tiers require more human gating. The agent
**degrades a tier down** (toward more human control) on low confidence or when an action leaves the
pre-approved set ("off-plan").

| Tier | Name | Examples | Gate |
|---|---|---|---|
| **T1** | Read-only | Pre-triage, context gathering, RCA draft, change-impact *analysis* | Auto — no approval |
| **T2** | Advised | Recommend a remediation / a rollout decision; human executes | Auto to recommend; human acts |
| **T3** | Approved (HITL) | Execute *after* explicit human approval | Single human approval (`aws:approve` / MR approval) |
| **T4** | Autonomous (HOTL) | Bounded, reversible, blast-radius-limited action; human monitors | Policy pre-approved + auto-rollback + notify; degrade->T3 off-plan |

**Action-tier table (the governance artifact auditors will ask for).** Every tool / runbook is mapped to
a tier. Initial mapping for our environment:

| Action | Tier | Rationale |
|---|---|---|
| Query logs/metrics/traces, read k8s/ArgoCD state | T1 | Read-only |
| Draft RCA / postmortem | T1 | No side effects |
| Change-validation verdict on a deploy | T1 (analysis) / T2 (recommend) | Advisory; controller decides |
| Restart a stuck stateless pod / re-trigger a stuck ArgoCD sync | T4 | Idempotent, reversible, low blast radius |
| Scale a stateless service within bounds | T4 | Reversible within SLO |
| Roll back a canary | (deterministic, not agent) | Argo Rollouts AnalysisTemplate decides |
| Config change to a prod service | T3 | Reversible but significant -> human approval |
| Anything touching **RDS** (failover/param/schema), IAM, security groups, data deletion | T3+ | High blast radius / irreversible -> human + window |

This table is the literal implementation of SR 11-7 "human-in-the-loop for high-risk."

---

## 4. Reference architecture (target)

```
 TRIGGERS                    DURABLE ORCHESTRATION (Temporal)
 Datadog/CloudWatch alerts ->  incident lifecycle = workflow (hrs/days)
 Deploy / sync events          activities = retryable, replayable steps (= AUDIT TRAIL)
 GitLab CI / ArgoCD hooks      signals/queries = human pause / resume / abort
                                         |  each activity wraps v
                              REASONING LOOP (Strands / LangGraph / Claude Agent SDK)
                              gather context -> propose -> VERIFY -> repeat
                              orchestrator + subagents (isolated context)
        +--------------------------+-----------------------------+
        v                          v                             v
 GROUNDING                  TOOL LAYER (MCP)             VERIFICATION (ranked)
 - KG: service topology     - Datadog / CloudWatch       1 rules: validate/tflint/
   + deps + owners + SLOs    - k8s (read) / ArgoCD          checkov/OPA/dry-run  (gate)
 - RAG: runbooks/postmortems - AWS (EKS/Lambda/IaC)      2 observable: SLO-burn post-canary
 - incident memory          - GitHub/GitLab              3 LLM-judge: RCA quality only (never a gate)
 - filesystem: code,        (RBAC + audit per tier)
   runbooks, past notes
        |
        v
 AUTONOMY TIERS (per action) ---------------------------> GATES (outside the model)
 T1 read-only (auto) ... T4 bounded-auto (monitor)        OPA/Kyverno policy-as-code
 degrade down on low confidence / off-plan                GitOps: PR -> ArgoCD (rollback = revert)
                                                          Argo Rollouts + Datadog analysis (auto-rollback)
        |                                                 SSM Automation runbooks (aws:approve for T3+)
        v                                                 blast-radius-scoped creds; break-glass
 AGENTOPS (OTel GenAI spans) <----> OFFLINE EVAL HARNESS
 agent/tool/model spans, cost,      replayable incident labels {ground_truth, snapshot}
 reasoning provenance               messy worlds; Pass@k; trajectory/depth scoring;
 -> WORM S3 audit (Object Lock)     weekly regression; feeds skills/rules back
```

**Key non-negotiables baked in**
- The **rollback decision is deterministic** (Argo Rollouts analysis / SSM runbook logic), never the LLM.
- **Guardrails != action authorization** — IAM scoping + the SSM/runbook allow-list are the real action
  controls; Bedrock Guardrails only filter model text.
- The **harness, not the prompt, enforces safety** (hooks / policy engine / IAM — all outside the model).

---

## 5. Revised roadmap (build order)

Driven by the research consensus: *eval first, read-only value early, write-autonomy last and
deterministic.* Each stage is independently valuable and shippable.

| Stage | Goal | Key deliverables | Risk |
|---|---|---|---|
| **0. Eval harness** | Measure before we trust | Incident-replay format `{ground_truth, snapshot}`; scorer (trajectory/depth/Pass@k); seed scenarios; port RCAEval/ITBench ideas | None (offline) |
| **1. Read-only triage + RCA** | Immediate value, zero write risk | Enable Datadog Bits AI; finish `ai-incident-agent` nodes (gather/analyze/RCA draft) against the eval harness; confidence scores | Low |
| **2. Advisory change-validation gate** | Own the white space | GitLab CI stage + ArgoCD PreSync advisory check: blast-radius analysis -> proceed/block/require-human verdict | Low (advisory) |
| **3. Deterministic rollback** | "Tested rollback ready" | Argo Rollouts + Datadog AnalysisTemplate canary auto-rollback (no LLM) | Medium (infra) |
| **4. Tier-4 auto-remediation** | Bounded auto-healing | Allow-listed SSM runbooks (restart/scale/re-sync) with auto-rollback + notify; degrade->T3 off-plan | Medium |
| **5. Tier-3 HITL remediation** | Approved actions | `aws:approve` / MR-approval flow; action-tier table enforced | Medium |
| **6. Permanent-fix chase** | Close the loop | Agent opens MRs/issues for the real fix; tracks to done; never auto-merges | Low |
| **7. Continuous Detection / Sentinel** | Catch a class before it recurs | Long-running/periodic detectors over platform state (anomaly / new-signature / change-induced-regression / drift / saturation+expiry); deterministic-first; T1 detect → T2 advise; scored by eval on lead-time. See [ADR-0001](decisions/0001-continuous-detection-sentinel.md). | Low (logic) / runtime needs cluster |
| **Cross-cutting** | Trust & audit | Autonomy-tier engine; OTel GenAI AgentOps; WORM audit trail; MRM inventory registration; ISO 42001 AIMS | — |

**Buy vs build**: buy pre-triage/RCA (Datadog Bits AI / AWS DevOps Agent — both already integrate our
Datadog/GitLab); build the **change-validation gate, the eval harness, the autonomy-tier engine, and the
deterministic remediation spine** — that's where the defensible leverage (and the market white space) is.

---

## 6. The human's role (what "measured on leverage" means)

Not closing tickets. The operator: authors AI + human runbooks; designs the gates and tiers; reviews/
approves T3 actions; monitors T4; curates the eval label set; and generalizes every one-off into an
agent/runbook/guardrail. Scoreboard = incidents pre-triaged without a human, bad changes caught by gates,
runbooks reused, MTTR delta, and how much the agent surface can carry.

---

## 7. Open decisions

1. **First dev increment** — eval harness (foundation) vs change-validation gate (white space) vs
   finishing the read-only triage nodes (existing scaffolding). See `PROJECT_STATUS.md`.
2. **Framework** — keep LangGraph (existing code) vs adopt Strands (AWS-first-party) vs Claude Agent SDK
   (filesystem-as-context). Likely: LangGraph reasoning *inside* a durable layer later.
3. **AgentCore vs self-host** — start managed (compliance + speed), keep logic portable (Strands).
4. **Scope of pilot** — which service/team is the first real engagement to measure against.
</content>
