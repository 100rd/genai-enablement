# Agentic SRE Landscape Refresh — June 2026

**Date**: 2026-06-16
**Purpose**: Refresh the December-2025 research (`research/final-report.md`, `solutions/ai-incident-agent/`)
against the state of the autonomous-SRE / "AI SRE" market and engineering practice as of mid-2026.
**Trigger**: A 2026 job description for an "AI-native SRE operator" crystallized the target operating
model — *"the harness is the product"*: engineers build/operate agents that do the ops work (pre-triage,
change-validation gates, permanent-fix chase, RCA drafting, auto-healing) and are measured on the
**leverage the agent surface creates**, not tickets closed.

> **How to read this**: nearly every MTTR/accuracy percentage in vendor material is self-reported and
> unaudited. Treat all such numbers as directional marketing. Claims below are flagged where the source
> is secondary. Load-bearing primary sources are listed at the end.

---

## 0. The one fact that reframes everything

**ITBench (IBM Research, ICML 2025 oral, [arXiv:2502.05352](https://arxiv.org/abs/2502.05352)) —
SOTA agents autonomously resolve only ~11% of real SRE incident scenarios end-to-end**
(102+ reproducible scenarios on live Kubernetes + observability stacks; CISO 25%, FinOps 26%).

Implication for us: **do not bet on model autonomy.** Bet on the *harness* — pre-triage,
evidence-gathering, correlation, RCA drafting (all of which agents are already good at), gated hard
on *acting*. The leverage is in scaffolding, gates, memory, and the eval loop. This is the literal
meaning of "the harness is the product."

---

## 1. What changed since our December-2025 research

| Dimension | Dec 2025 (our plan) | June 2026 (now) |
|---|---|---|
| Category | "AIOps platforms", emerging | Named **"AI SRE"** category; Gartner Cool Vendors; arms race |
| Our solution framing | "AI Incident Agent" = enriched notifications (smart pager) | Target = **autonomous SRE harness** with tiered autonomy + change gates |
| Cloud-native agents | Datadog Bits AI (mentioned), DevOps Guru | **Azure SRE Agent (GA)**, **AWS DevOps Agent (GA)**, **Google Gemini Cloud Assist**, Datadog **Bits AI SRE (GA)** |
| Remediation posture | "auto-remediation = optional, phase 6" | **Tiered autonomy** is the canonical model; deterministic rollback (Argo Rollouts) is the safety primitive; AWS itself ships **read-only** |
| Eval | not addressed | **Offline incident replay** is the reference discipline (build it first) |
| Orchestration | LangGraph only | **Temporal (durable) + LangGraph/Claude Agent SDK (reasoning)** two-layer |
| AWS substrate | Bedrock + SageMaker + ECS | **Bedrock AgentCore (GA)** + **Strands Agents SDK (1.0)** + SSM Automation spine |
| Governance | SR 11-7 for ML models | SR 11-7 **re-interpreted for LLM agents** (register agent + each action in MRM inventory); ISO 42001 AIMS; **guardrails != action authorization** |

---

## 2. Commercial landscape (who does what, mid-2026)

### Cloud-provider agents (the heavyweights)
- **Azure SRE Agent** — *GA; strongest disclosed architecture.* Multilayer investigation, hypothesis
  testing, **adjustable autonomy** (recommend mode for low-sev, autonomous mode for P1), **Incident
  Response Plans** routing to the right agent at the right autonomy level, **verified-recovery loops**
  (alert -> fix -> confirm recovered), dual OpenAI + **Claude** models, native control-plane execution,
  memory. All write actions gated by RBAC + explicit approval; safety enforced via **hooks**
  (Stop / PostToolUse / global) — i.e. in the harness, not the prompt. OSS: `microsoft/sre-agent`.
- **AWS DevOps Agent** — *GA 2026-03-31, on Bedrock AgentCore.* Sub-agents for Triage / Investigation-RCA
  / prevention. Integrates CloudWatch, **Datadog**, Dynatrace, New Relic, Splunk, Grafana, PagerDuty,
  ServiceNow, **GitHub/GitLab**, EventBridge. **Crucial:** in its EKS reference it is **read-only — no
  shell on the node; every interaction mediated by SSM Automation; diagnoses but does not remediate.**
  That is AWS's own signal for "safe to ship in 2026."
- **Google Gemini Cloud Assist** — RCA with parallel hypothesis exploration; background agent
  auto-initiates investigations; mines past incidents via embeddings + vector DB (institutional memory).

### Observability / incident incumbents
- **Datadog Bits AI SRE** (*we already pay for Datadog*) — 24/7 on-call agent, branching/recursive
  hypothesis testing against live telemetry, self-validation, audit-ready RCA delivered before responders
  log in. Built a rigorous **LLM-judge eval platform** over thousands of labeled real incidents.
  -> **Fastest path to value for us: enable Bits AI, no procurement.**
- **incident.io AI SRE** — Slack-native multi-agent; parallel search across PRs/Slack/history/telemetry;
  pinpoints **the breaking PR and drafts the fix as a PR**. Honest scope: "first 80%", human approves.
- **PagerDuty Advance** — SRE/Scribe/Shift agents; betting on the **agent-to-agent (MCP) orchestration
  layer** across AWS/Azure agents rather than owning every agent.
- **Dynatrace** (causal/topology, but reasons only over its own data — lock-in), **New Relic**
  (interop/partnership strategy), **Cisco/Splunk AgenticOps** (claims it *applies fixes*),
  **ServiceNow** (ITSM workflow-triggered remediation).

### Standalone startups
- **Resolve AI** — broadest scope ("maintain software" across prod lifecycle), prod-context-into-IDE
  loop. **$125M Series A @ $1B**, Feb 2026 (Coinbase, DoorDash, Salesforce, MongoDB customers).
- **Traversal** — **causal-ML-first RCA** (founders are causal-inference researchers); **American
  Express** deployment + Amex Ventures investment. The most technically distinctive RCA bet.
- **Cleric** — self-learning AI SRE, per-finding **confidence scores**, operational memory; Gartner Cool
  Vendor. **Parity** — deepest **Kubernetes**-native (cluster introspection + runbook automation).
  **Deductive** — RL-trained. **NeuBird HawkEye** — loud auto-remediate claims, marketplace distribution.

### Open source
- **HolmesGPT** (Robusta + Microsoft, CNCF Sandbox Oct 2025) — agentic troubleshooter that decides what
  data to fetch and iterates; broad (k8s/VM/cloud/DB/SaaS). **K8sGPT** — narrower k8s diagnosis baseline.

### Out of category (correcting our earlier list)
- **Wren AI** = agentic BI / text-to-SQL (not SRE). **Wayfound** = "guardian agent" supervising other
  agents (adjacent governance, not ops). **Tetrate** = service mesh / AI gateway (no confirmed AI-SRE
  product).

---

## 3. State-of-the-art capabilities (the bar to clear)

1. **Hypothesis-driven investigation** — form hypotheses, run *targeted* queries, validate/reject,
   iterate; parallel/branching search is now table stakes.
2. **Cross-signal correlation incl. code** — fuse logs/metrics/traces *and* the breaking PR / deploy.
   "Which deploy broke it + here's the fix" is the freshest 2026 capability.
3. **Audit-ready RCA drafting** into the human's surface (Slack/Teams), with **confidence scores** and
   linked evidence, separating observed fact from inferred cause.
4. **Tiered / adjustable autonomy** — explicit recommend-vs-act per severity, permissioned execution.
5. **Runbook ingestion + bounded remediation** under guardrails.
6. **Operational memory** — learning per incident (feedback / RL / incident-corpus embeddings).
7. **Verified-recovery loops** — confirm the system actually recovered after acting.
8. **Agent-to-agent interoperability via MCP.**

---

## 4. Engineering patterns to adopt

- **Two-layer orchestration**: **Temporal** owns the durable, replayable incident lifecycle (= audit
  trail + crash-resilience + human pause/resume/abort via signals); **LangGraph / Claude Agent SDK** owns
  the reasoning loop *inside each Temporal activity*. LLM/tool calls must live in activities (replay
  determinism).
- **Autonomy tiers** (the core safety primitive): **T1 Read-only -> T2 Advised -> T3 Approved (HITL) ->
  T4 Autonomous (HOTL)**, mapped to risk x reversibility; **degrade T4->T3 on low confidence / off-plan**.
- **Safe remediation = deterministic, not LLM**:
  - GitOps — agent never `kubectl apply`s; it opens a **PR**, ArgoCD/Flux reconciles, **rollback = git
    revert**.
  - **Argo Rollouts + Datadog `AnalysisTemplate`** = automatic canary analysis + **auto-rollback with no
    LLM in the loop** (this is the "tested rollback"). Keep the rollback decision deterministic.
  - **Policy-as-code (OPA/Kyverno)** as the hard gate enforced *outside* the agent (admission/CI layer).
  - On AWS: mutations only via **pre-approved SSM Automation runbooks** (versioned, IAM-scoped, with
    `aws:approve` for high tiers, full CloudTrail), triggered by EventBridge. Agent = proposer.
- **RCA techniques** ranked: topology/dependency-graph-aware (workhorse) -> **good-deploy vs bad-deploy
  diff** (highest leverage, since most incidents are change-induced) -> causal inference (frontier) ->
  log/metric/trace correlation (table stakes). Offline harnesses to port: **RCAEval**, **ITBench**.
- **Context/grounding**: compose **RAG (runbooks/postmortems) + knowledge graph (service topology/deps)
  + incident memory**; **filesystem-as-context** (expose runbooks/code/notes as files; agentic search via
  grep/read before semantic search). Azure moved 100+ tools -> filesystem and it outperformed.
- **Verification** ranked (Anthropic): **rules-based (best)** -> observable -> LLM-judge (weakest, never
  as an action gate). For ops, a proposed change must pass `validate / tflint / checkov / OPA / dry-run`
  before it is *eligible* to act.
- **Eval-driven development**: build an **offline incident-replay harness first**. Labels =
  `{ground_truth_root_cause, world_snapshot}`; store *relationships across signals* (raw telemetry
  expires); make simulated worlds **messy**; score **trajectory / depth / signal-surfacing / Pass@k**,
  not pass/fail; weekly regression sweeps.
- **AgentOps**: OpenTelemetry **GenAI semantic conventions** (v1.41: agent/workflow/tool/model spans) —
  but `gen_ai.*` attrs are still unstable; wrap behind our own schema.

---

## 5. AWS-native reference stack (for our environment)

EKS/RDS/Lambda, GitLab CI + ArgoCD, Datadog, SOC 2 / ISO 27001 / SR 11-7 / HITL-for-high-risk.

| Layer | Choice | Why |
|---|---|---|
| Agent framework | **Strands Agents SDK** (pinned) | First-party, OTEL-native, portable AgentCore<->self-host |
| Runtime | **Bedrock AgentCore Runtime** (VPC + PrivateLink) | Isolation, 8h jobs, inherited compliance; async for >15min gates |
| Tools | **AgentCore Gateway** fronting AWS MCP (CloudWatch App Signals / EKS / Lambda Tool / IaC) + vetted **ArgoCD MCP** + read-only **k8s MCP** | One governed tool surface |
| Identity | **AgentCore Identity** + per-tier scoped IAM | Least privilege per action tier |
| Safety (model) | **Bedrock Guardrails** (denied topics, grounding, PII redaction) | Constrain reasoning/output |
| Safety (actions) | **Action-tier table**; mutations only via pre-approved **SSM Automation** runbooks (`aws:approve` for T2+) via EventBridge | Deterministic, reversible, auditable writes |
| Change gates | Agent as **GitLab CI stage + ArgoCD PreSync advisory gate**; **Argo Rollouts + Datadog AnalysisTemplate** = deterministic auto-rollback | LLM proposes; controller decides -> SOC 2 CC8.1 |
| Pre-triage / RCA | **Datadog Bits AI** + **CloudWatch Investigations** / **AWS DevOps Agent** | First-party, human-validated; no custom code to start |
| Observability / audit | AgentCore Observability (ADOT->CloudWatch) + **Bedrock Model Invocation Logs** + **CloudTrail** -> **WORM S3 (Object Lock + KMS)** in a separate logging account | Immutable multi-layer trail for SR 11-7 / ISO 42001 |
| Governance | Register agent + model versions + each action in **MRM inventory**; build **ISO 42001 AIMS**; verify attestations in **AWS Artifact** | Direct SR 11-7 / SOC 2 / ISO mapping |

**Watch-outs**: AWS DevOps Agent **does not remediate** (the autonomous-action half is DIY). Guardrails
filter model text, **not tool side-effects** (IAM + SSM allow-list are the real controls). AgentCore
15-min synchronous timeout -> long gates must be async. No first-party ArgoCD MCP (fork/vet community one).
Q Developer brand churn (May-2026 EOS notice) — don't anchor on Q. DevOps Guru is legacy-by-momentum.
SR 11-7 #1 exam finding = un-inventoried LLMs — register before prod. **Vendor MTTR/accuracy stats are
unverified.**

---

## 6. Opportunities (white space we can own)

1. **Pre-incident change-validation gates** — agent predicts reliability impact of a deploy/config change
   and approves/blocks. Barely productized anywhere; it's a literal pillar of the target operating model.
2. **A neutral offline eval harness** ("SWE-bench for incidents") — there is no trustworthy third-party
   benchmark; building ours is both a quality engine and a differentiator.
3. **Safe auto-remediation with rollback guarantees** for a *regulated FS* context — most vendors stop at
   recommend; deterministic GitOps/SSM rollback + tiered autonomy + full audit is defensible under SR 11-7.
4. **Cross-vendor, no-lock-in telemetry reasoning** — incumbents reason best only over their own data.

---

## 7. Load-bearing primary sources

- ITBench — [arXiv:2502.05352](https://arxiv.org/abs/2502.05352) · [OSS](https://github.com/itbench-hub/ITBench)
- Datadog Bits AI eval platform — https://www.datadoghq.com/blog/engineering/bits-ai-eval-platform/
- RCAEval — https://github.com/phamquiluan/RCAEval
- Anthropic, Building agents with the Claude Agent SDK — https://claude.com/blog/building-agents-with-the-claude-agent-sdk
- Azure SRE Agent GA — https://techcommunity.microsoft.com/blog/appsonazureblog/announcing-general-availability-for-the-azure-sre-agent/4500682 · [OSS](https://github.com/microsoft/sre-agent)
- AWS DevOps Agent GA — https://aws.amazon.com/blogs/mt/announcing-general-availability-of-aws-devops-agent/ · [EKS+MCP](https://aws.amazon.com/blogs/devops/diagnose-eks-node-issues-faster-with-aws-devops-agent-and-custom-mcp/)
- Bedrock AgentCore GA — https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-agentcore-available
- Strands Agents 1.0 — https://aws.amazon.com/blogs/opensource/introducing-strands-agents-1-0-production-ready-multi-agent-orchestration-made-simple/
- Argo Rollouts analysis — https://argo-rollouts.readthedocs.io/en/stable/features/analysis/
- OTel GenAI agent spans — https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/
</content>
