# Platform Glossary & Component Map

**Status:** Draft v0.1 · 2026-07-02
**Scope:** the five-repo AI platform — Omniscience, multiqlti, omnius, platform-design (incl. PB-SRE), genai-enablement (incl. sre-harness)

**Why this exists.** The same words mean different things across repos ("skill", "workspace",
"harness", "connection"), and several different words name the same concept (autonomy tiers
T1–T4 vs Cedar task classes A–E vs runbook auto/approval steps). Before any shared registry,
policy vocabulary, or cross-component contract can exist, the words must be fixed. This
document is the canonical vocabulary. When a repo's local term conflicts with this glossary,
the repo keeps its code identifiers but MUST use the canonical term in docs, ADRs, and
cross-repo contracts.

---

## Part 1 — What each component does

### Omniscience — the platform knowledge hub

**Mission:** know the platform. Ingest every platform source (code, IaC, K8s runtime, CI/CD,
cloud config, alerts, incident chat, docs) into one causal + bitemporal + semantic graph, and
serve it to any MCP-compatible client.

- **Does:** ingestion (~16 connectors + Go K8s operator), parsing/chunking/embedding,
  3-store persistence (Postgres = metadata, Qdrant = hybrid vectors, Neo4j = bitemporal
  graph), retrieval via 13 MCP tools (`search`, `get_entity`, `blast_radius`,
  `replay_context`, `incident_timeline`, …) and REST `/api/v1`, workspace-scoped fail-closed
  tokens.
- **Does NOT:** synthesize answers (no embedded LLM — the calling client's model does),
  execute actions ("Insight Mode" only; Action Mode is a future v2), store agent
  experience/lessons (explicitly out of scope per its ADR-0015).
- **Maturity:** most mature component. v0.2 shipped, v0.3/v0.4 in flight. Deployable
  (docker-compose.prod, Helm). Still stabilizing (June-2026 hardening review).
- **Consumed by:** multiqlti (memory backend), omnius (knowledge plane), sre-harness
  (platform graph), PB-SRE (topology), IDE/agent clients.

### multiqlti — the personal dark factory

**Mission:** give one engineer a multi-model SDLC pipeline: describe a feature, a chain of
specialized agent stages plans → architects → codes → tests → reviews → deploys, with any
model per stage.

- **Does:** pipeline orchestration (linear/DAG/swarm), 8 stage classes ("teams"), execution
  strategies (Debate/MoA/Voting), multi-provider gateway (Claude/Gemini/Grok/local + CLI
  subscriptions), own RAG (migrating to Omniscience), workspace code indexing, skills
  marketplace, guardrails, sandbox, federation, triggers; exposes itself as an MCP server.
- **Does NOT:** org-level governance (no trust lifecycle on skills, no autonomy-tier
  enforcement, human approval is per-pipeline config, not policy); production change
  management.
- **Maturity:** live, self-hosted, all planned phases shipped; Omniscience integration built
  but behind a feature flag against a mock.
- **Role in the platform:** the proving ground / innovation edge. Patterns and skills are
  iterated here cheaply, then graduate into omnius.

### omnius — the centralized dark factory

**Mission:** run engineering tasks end-to-end (plan → code in sandbox → verify → PR → merge)
at org scale, with humans owning approval, not syntax review. Target autonomy L4, never L5.

- **Does (by design):** deterministic core outside the LLM — Conductor FSM (Temporal),
  Gate Engine (Cedar policy), dual-sandbox Verifier with distinct model families
  (worker ≠ evaluator), transactional wrapper, Curator Console (human PARKED queue),
  skill-store with a trust lifecycle, knowledge-plane client to Omniscience (read-only,
  severable).
- **Does NOT:** trust its own agents (they are ephemeral, swappable, untrusted by
  architecture); auto-merge by default (opt-in, fail-closed, per-class, earned); replace
  multiqlti (peer of a different tier).
- **Maturity:** Phase 0 — the full logic exists as a tested Python mockup (81 green tests),
  but every security/infra guarantee is simulated ("security posture 0%"). Phase 1
  (Firecracker/Temporal/OpenBao/SPIRE swaps) not started.
- **First real task class (planned):** reversible Terraform-module changes in
  platform-design.

### platform-design — the platform substrate (infra + security)

**Mission:** define the ground truth the rest of the platform runs on and reasons about:
AWS landing zone, EKS + Karpenter, GitOps (ArgoCD + Kargo), Cilium, policy-as-code
(OPA/Kyverno/Checkov), 55 ADRs.

- **Does:** authoritative IaC estate (22 Terraform modules + Terragrunt), cluster and
  network design, security policy, observability stack definitions; hosts **PB-SRE** (below);
  provides the graph model contract for change gating (ADR-0055).
- **Does NOT:** run anything yet — design estate; "no live AWS resources have been applied."
- **Maturity:** designed and CI-checked, not deployed.

#### PB-SRE ("Platform Brain", `ai-sre/`) — advisory SRE diagnostics

- **Does (by design):** multi-agent incident diagnostics — orchestrator + 9 specialists on a
  blackboard, read-only guardrails in 4 layers, remediation only as GitOps PRs, Slack
  approval flow; syncs platform topology into Omniscience.
- **Does NOT:** act autonomously (advisory-only is its security model); own the safety
  gates (that is the sre-harness's job).
- **Maturity:** v0.1 prototype — FastAPI service and k8s manifests are real, agent
  invocations are simulated, Omniscience sync is dry-run.

### genai-enablement — the program frame + the autonomous SRE harness

**Mission (program):** the org-level GenAI adoption vision — "Enable, Don't Own", prove on
real workloads, measure everything (DORA), reusable playbooks, safe & auditable
(SR 11-7 / ISO 42001).

**Mission (sre-harness):** "the harness is the product" — deterministic safety machinery
under which SRE agents operate: autonomy tiers, action-tier policy, change-validation gates,
deterministic rollback. Anchor fact: SOTA agents autonomously resolve only ~11% of incidents
(ITBench) — so bet on the harness, not on model autonomy.

- **Does:** vision/research docs; harness code — autonomy-tier engine (T1–T4 with
  degradation), action-tier table, change gate (PROCEED/BLOCK/REQUIRE_HUMAN, no LLM),
  PlatformGraph port + Omniscience MCP adapter, offline eval harness, gate CLI + CI
  integrations, multi-check gate, OTel instrumentation, Sentinel continuous-detection ADR
  (all merged to main as of July 2026).
- **Does NOT:** reason (no LLM in the safety core by design); execute remediation
  (recommendation tier T2 max in current code).
- **Maturity:** research-heavy with a growing code core; deterministic safety core + eval +
  gate CLI unit-tested and merged; no live LLM/agent layer and no live Omniscience client yet.

### Cross-component roles at a glance

| Component | One-line role | Depends on | Depended on by |
|---|---|---|---|
| Omniscience | knows the platform | sources (git/k8s/…) | everyone |
| multiqlti | personal factory / proving ground | Omniscience (optional) | nobody (by design) |
| omnius | governed org factory | Omniscience (severable), platform-design (task target) | nobody yet |
| platform-design | ground truth substrate + PB-SRE | — | Omniscience (as source), omnius, harness |
| genai-enablement | program frame + SRE safety core | Omniscience, platform-design | AI SRE program |

---

## Part 2 — Canonical glossary

Legend for the per-system columns: the local term and, where it differs, its local meaning.
"—" = concept absent in that system.

### 2.1 Skills & knowledge units

| Canonical term | Definition | multiqlti | omnius | Elsewhere |
|---|---|---|---|---|
| **Skill** | A reusable, portable instruction unit in Agent Skills format (`SKILL.md`: YAML frontmatter `name`+`description`, markdown body, optional `references/`, `scripts/`). Content only — trust lives outside the file. | `skills` DB record whose payload is `systemPromptOverride`+`tools[]`; interchange YAML `multiqlti/v1 Kind: Skill`. *Divergence from its own PLAN decision #13 (markdown+frontmatter).* | `SkillModel` = trust envelope around a SKILL.md body (`instruction-skill`); SKILL.md adopted as cross-vendor standard in MASTER-ARCHITECTURE | `.claude/skills/`, `.gemini/skills/` — canonical format, 40+ instances |
| **Skill type** | instruction (how-to runbook) / executable (code) / accumulated-lesson (agent-derived) | not typed | `SkillType` enum — exactly these three | — |
| **Lesson** | Agent-derived experience distilled into a skill draft; always enters quarantine | "agent-experience" memory layer | `accumulated-lesson` skill type; body auto-refined, success-criteria human-gated | — |
| **Runbook** | Operational skill with step-level autonomy tags (which steps run auto vs need approval) | — | "their runbook = the Meta-Loop" (mainplan) | PB-SRE `runbooks/*.md` with `auto_executable_steps`/`approval_required_steps` frontmatter; Omniscience `suggest_runbook` tool; AWS SSM Automation runbooks in harness plan |
| **Capability token** | A permission mode granted to a task (`read`/`write`/`execute`/`iac_deploy`). **NOT a skill** — naming collision inside omnius (`CedarPDP.permitted_skill_set` returns these). | `tools[]` allowlist | Cedar `permitted_skill_set` ⚠ misnamed | PB-SRE `ToolPermission` (server, tools, read_only) |
| **Knowledge base** | Unstructured reference content a skill or agent may consult | knowledge bases feature (#79) | knowledge plane (see 2.4) | PB-SRE `knowledge/*.md`; Omniscience is the platform-wide KB |

### 2.2 Agents & execution

| Canonical term | Definition | multiqlti | omnius | Elsewhere |
|---|---|---|---|---|
| **Agent** | A model + system prompt + tool allowlist + guardrails, executing one role. Ephemeral; owns no cross-task state. | "team" (`TeamConfig`: stage class like planning/development; 8 registered) | Planner / Worker / Evaluator — roles bound via SPIFFE SVID to model pools + harness | `.claude/agents/*.md` (frontmatter subagent defs); PB-SRE `AgentDefinition` dataclass (role, model, system_prompt, tool_permissions) |
| **Orchestrator** | The component that owns control flow across agents; deterministic, outside the LLM | `PipelineController` | Conductor (FSM, → Temporal) | PB-SRE orchestrator (blackboard); harness = the deterministic gates around any orchestrator |
| **Pipeline** | A declared sequence/DAG of agent stages | pipeline (linear/DAG/swarm) | task lifecycle FSM (`TRIGGERED→PLANNING→…→MERGED`) | harness roadmap stages |
| **Run / Task** | One execution instance through a pipeline/lifecycle | run (`run_pipeline`, `get_run`) | task (`task_id`, joined to incident plane for escape tracking) | PB-SRE investigation |
| **Execution strategy** | How multiple models combine on one stage | Single / Debate / MoA / Voting / parallel-split | worker≠evaluator family split (adversarial pair, not consensus) | — |
| **Sandbox** | Isolated execution environment for agent-written code | Docker sandbox (#82) | Execution Fabric: Firecracker/Kata microVMs (design; Docker in mock), dual-mount | — |
| **Trigger** | Event that starts a run | triggers: schedule/webhook/github_event/file_change | `TRIGGERED` FSM entry | PB-SRE alert ingestion (route by label prefix) |
| **Federation** | Multiple instances of the same product sharing state/skills/agents | peer mesh over WebSocket + A2A remote agents + config-sync | — (single central instance by design) | — |

### 2.3 Trust & governance

| Canonical term | Definition | multiqlti | omnius | Elsewhere |
|---|---|---|---|---|
| **Autonomy tier** | How much the AI may do on its own. Canonical scale **T1 read-only → T2 advised → T3 human-approved (HITL) → T4 bounded-autonomous (HOTL)**; degrade one tier on low confidence or off-plan. | approval gates per pipeline (#91), not a formal scale | Cedar task classes: A (dev+reversible, execute) / B (dev, read-write) / C (prod+reversible, read+execute) / E (prod non-reversible, human-gated) — env × reversibility projection of the same idea | genai-enablement T1–T4 + action-tier table (the canonical source); PB-SRE: everything T1/T2 + runbook steps tagged auto (≈T4) / approval (≈T3) |
| **Action tier** | Per-action-kind mapping to the minimum autonomy tier (e.g. restart-stateless-pod=T4, prod-config-change=T3, IAM/data-deletion=T3+) | — | Cedar policy per class | harness `ACTION_TIER_TABLE` (SR 11-7 governance artifact) |
| **Gate** | A deterministic, out-of-LLM check that permits/blocks a transition. Guardrails filter text; **gates authorize actions** — never conflate. | governance/approval gates | Gate Engine (Cedar PDP + VAP/Kyverno); conformance meta-gate (`can_auto_merge`) | harness change-gate; platform-design OPA/Kyverno/Checkov; CI quality gates |
| **Verdict** | A gate's output | approve/reject in approval flow | `can_auto_merge` breakdown | harness `Verdict`: PROCEED / BLOCK / REQUIRE_HUMAN |
| **Trust lifecycle** | Skill/artifact states: **unverified → verified → deprecated**; admission human-gated; any body change re-quarantines (hash drift) | absent (only `isBuiltin`, `sharing`) | SPEC-SK: content gate (secret scan), quarantine, `approved_body_hash`, success-delta retirement | skills-lock.json sha256 pinning = same integrity primitive |
| **Evidence (dossier)** | Portable track record of a skill/agent (runs, success-delta, models, env). Travels between runtimes; **trust status does not.** | usage stats (usageCount) | `replay_count`/`success_count`/`validated_on_model`/`validated_env` | — |
| **Provenance** | Where an artifact came from: human / system-derived / external. External ⇒ quarantine + human gate. | `sourceType: manual\|git`, `forkedFrom` | SPEC-SK provenance stage | `VENDORED.md` (upstream, author, license) |
| **Curator / Human gate** | The human approval surface | approval gates UI | Curator Console (PARKED queue, per-class auto-merge toggle) | harness REQUIRE_HUMAN / T3; PB-SRE Slack approve; SSM `aws:approve` |
| **Guardrail** | Runtime filter on agent I/O (tool allowlists, write-verb blocking, secret scanning). Defense-in-depth; **not** an authorization mechanism (see Gate). | guardrail-runner | SkillContentGate; read-only MCP clamp | PB-SRE `guardrails/` 4 layers; Bedrock Guardrails caveat in harness plan |
| **Severance** | The property that removing a dependency degrades a system instead of killing it | pgvector fallback behind memory feature flag | symmetric severance (REQ-KP-4): Planner falls back to direct source queries | canonical platform principle |

### 2.4 Knowledge & data

| Canonical term | Definition | multiqlti | omnius | Elsewhere |
|---|---|---|---|---|
| **Platform graph** | The typed entity/edge graph of platform state (services, clusters, deps, owners), bitemporal | consumed via Omniscience provider | Knowledge Plane = Omniscience read-only MCP contract | harness `PlatformGraph` port; PB-SRE topology store; lives in Omniscience Neo4j |
| **Knowledge plane** | A consumer's name for its read-only view of the platform graph | "world-knowledge" memory layer | `knowledge_plane.py` (MCPClientWrapper, read-only token guard) | — |
| **Memory (3 layers)** | world-knowledge (platform-wide, → Omniscience) / agent-experience (lessons, stays local) / working (per-run) | exactly this split (memory-architecture ADR) | truth stores split: operational-reality (Omniscience) + others | Omniscience explicitly refuses the lessons layer |
| **Connector (source)** | An **ingestion** adapter feeding data INTO Omniscience (git, k8s operator, Slack, Datadog…) | its workspaces become connectors (ADR-0015) | — | Omniscience `sources` + connectors pkg |
| **Connection** | An **outbound** credentialed link FROM an agent runtime to an external tool (MCP client, GitLab, Jira…). ⚠ Do not confuse with Connector. | External Connections (AES-GCM secrets) | MCP Gateway routes | PB-SRE `mcp_registry` |
| **Workspace** | ⚠ Collision. (a) multiqlti: an indexed code repo an agent works on; (b) Omniscience: a **tenancy unit** (`workspace_id` on tokens, fail-closed filter). Canonical ruling: qualify — *code workspace* vs *tenant workspace*. | code workspace | — | Omniscience tenant workspace |
| **Blast radius** | The set of entities affected by a change/incident, computed from the platform graph. **Scope-surfacing only — never itself a gate input** (omnius rule, v0.1). | news board cross-linking | KP tool, scope surfacing | Omniscience MCP tool; harness gate check (multicheck branch); ADR-0055 |
| **as_of / bitemporal** | Point-in-time graph queries (`valid_from/valid_to/recorded_at`) — "what did the platform look like when X happened" | — | `replay_context` for auditability | Omniscience ADR-0008; harness adapter passes `as_of` |
| **Incident** | An operational problem with a timeline, resolution, and postmortem | run/incident history (future Omniscience source) | escape-rate return signal (incident plane joins `task_id`) | Omniscience `resolve_incident`/`incident_timeline`/`find_similar_incidents`/`generate_postmortem`; PB-SRE investigation; harness pre-triage |

### 2.5 Distribution & interfaces

| Canonical term | Definition | multiqlti | omnius | Elsewhere |
|---|---|---|---|---|
| **MCP** | The platform's universal bus. Every cross-component integration is an MCP contract. | client (external connections) + server (self, `run_pipeline`…) | client (KP) + Gateway (all agent actions routed/authorized) | Omniscience: MCP-first server (13 tools); harness: MCP client seam |
| **MCP Gateway** | A policy-enforcing chokepoint all agent tool calls route through | — (per-connection scoping) | Marketplace design: gateway verifies permissions | future shared candidate |
| **Registry (skills)** | The git-backed single source of truth for skills + lock-file pinning + provenance index. Proposed shared artifact: `platform-skills`. | Skill Market (external adapters: MCP Registry, CrewAI-GitHub, Composio) + internal marketplace (private/team/public, fork, semver) | git-backed skill store (Controller, not HTTP API), CODEOWNERS-gated | `.claude/skills` + `skills-lock.json` + `VENDORED.md` — the working reference implementation |
| **Marketplace** | The sharing/discovery UX on top of a registry (fork, publish, install, update) | Phase 6.16 internal + Phase 9 external | Agentic Marketplace (design: engineers publish micro-agents, adversarial certification) | — |
| **Lock-file / pinning** | sha256-pinned artifact set a runtime consumes; tracking mode (follow main) vs pinned mode (explicit SHAs) | config-sync `skill-state` lock entity | `approved_body_hash` per skill | `skills-lock.json` (`computedHash`) |
| **Eval harness** | Offline replay of golden cases to score an agent/skill/gate before it touches reality | fact_check team (in-pipeline) | conformance probes + golden-set attestation | genai-enablement Stage-0 eval (incident replay, RCAEval/ITBench-inspired) |
| **Telemetry (GenAI conventions)** | OTel GenAI semantic conventions for traces + cost accounting; independently chosen by three repos — de facto canonical | OpenTelemetry (#94) | SPEC-FO (OpenLLMetry→Langfuse) | harness agentops branch |
| **Model catalog** | Registry of model slugs → family, cost, allowed roles. Family attestation: worker family ≠ evaluator family. | model slugs + per-stage assignment | LiteLLM tag routing (`role:worker` family A ≠ `role:evaluator` family B) | PB-SRE hardcoded model IDs (to migrate) |

### 2.6 Product-level terms

| Canonical term | Definition |
|---|---|
| **Dark factory** | An SDLC system where agents do the production work and humans own approval. Two tiers: **personal** (multiqlti — exploration, low governance) and **centralized** (omnius — org-governed, gated). |
| **ADR-to-SPEC governance / SDD** | The authority split accepted by ADR-0009: humans decide intent, boundaries, ownership, and consequences in ADRs; agents execute only human-ready capability/task SPECs with deterministic acceptance probes. |
| **Capability SPEC** | A reusable, component-owned executable contract: requirements, interfaces, fallbacks, probes, and evidence obligations implementing one or more accepted ADRs. It is not one task instance. |
| **Task SPEC** | One immutable execution contract in a component's `docs/specs/` queue. It cites governing ADRs/capability SPECs and carries scope, class/tier request, role, pinned skills, acceptance criteria, rollback, and provenance. Tickets are inbox; task SPECs are work. |
| **SDD mode** | The decision-risk-weighted document depth from ADR-0009: **Quick** for R0/reversible work inside an existing boundary, **Standard** for routine work inside an accepted capability, and **Full** for new boundaries, side effects, or Class B/C/E work. A deterministic classifier may only widen the mode. |
| **Assurance profile** | A cumulative, threat-model-selected claim about enforced controls: **P0 Control-plane MVP**, **P1 Governed**, **P2 High Assurance**, or **P3 Scale & Autonomy**. A profile is certified by evidence; it is not inferred from installed products. |
| **Contract conformance** | Required merge result for implemented contracts, active-profile obligations, schemas, and regression probes. It is distinct from certification of a higher future profile. |
| **Assurance certification** | RED/AMBER/GREEN evidence result for a target assurance profile. It gates profile activation, production promotion, autonomy widening, and auto-merge without making every development PR depend on future controls. |
| **Standing Role** | A human-owned persistent definition (purpose, concerns, loop template, pinned skills, capability ceiling, experience scope) that spawns isolated ephemeral loops. It is not a running privileged agent. |
| **Graduation path** | The pipeline by which a pattern/skill proven in the personal tier (with evidence) is admitted into the centralized tier (through its trust lifecycle). |
| **Harness** | ⚠ Collision-prone. Canonical platform meaning: the deterministic safety machinery around agents (gates, tiers, verification) — "the harness is the product". Avoid using it for (a) agent runtime SDKs (say *agent harness/SDK*: Claude Agent SDK, PydanticAI) and (b) Claude Code's own tool environment. |
| **Insight Mode / Action Mode** | Omniscience v1 (read-only retrieval with citations) vs future v2 (write/execute). The platform-wide analogue: T1/T2 vs T3/T4. |
| **AI SRE** | The program (not one repo): Sentinel continuous detection + Omniscience knowledge + harness gates + PB-SRE diagnostic reasoning. Owns "full knowledge of platform problems"; humans own decisions. |
| **Enable, Don't Own** | genai-enablement operating principle: build capability in teams, hand off, don't become the bottleneck. |
| **L4 / never L5** | Autonomy ceiling: bounded autonomy with human ownership of correctness; full unattended autonomy is explicitly out of scope. |

---

## Part 3 — Term collisions and rulings

| Word | Collision | Ruling |
|---|---|---|
| **skill** | multiqlti DB agent-config vs omnius trust-wrapped SKILL.md vs Cedar capability tokens vs Claude Code SKILL.md | Canonical = Agent Skills SKILL.md content unit. multiqlti's record is a *skill binding/materialization*; Cedar's `permitted_skill_set` should be renamed **capability set** (it contains capability tokens, not skills) |
| **workspace** | multiqlti indexed code repo vs Omniscience tenancy unit | Always qualify: **code workspace** / **tenant workspace** |
| **harness** | safety core vs agent SDK vs Claude Code environment | Unqualified "harness" = the safety core. Otherwise say "agent SDK" / "Claude Code" |
| **connection vs connector** | multiqlti outbound tool links vs Omniscience ingestion adapters | **Connector** = data INTO the hub; **Connection** = agent's outbound credentialed link. Never interchangeable |
| **team** | multiqlti pipeline stage class vs human org team vs `.claude/agents/teams/` launchers | In cross-repo docs say **stage class** for multiqlti's meaning |
| **runbook** | PB-SRE procedural markdown vs SSM Automation documents vs Omniscience `suggest_runbook` payloads | All converge to: **skill of type runbook** with step-level tier tags (target state) |
| **verified** | omnius lifecycle state vs colloquial "tested" | Reserve **verified** for the lifecycle state; use "tested/validated" informally |
| **agent** | runtime worker vs `.claude/agents` persona defs vs A2A remote agents | Default = runtime worker. Say **agent definition** for persona files, **remote agent** for A2A |
| **T-tiers vs classes A–E vs auto/approval steps** | three encodings of autonomy | T1–T4 is the canonical scale (it's the governance-facing one, SR 11-7-mapped). Cedar classes and runbook step tags MUST document their T-mapping |
| **spec** | reusable capability contract vs one task's committed execution contract | Always qualify **capability SPEC** or **task SPEC**. An ADR is neither: it records the human decision that governs both. |

---

## Appendix — where each system's terms live (evidence anchors)

- multiqlti: `shared/schema.ts` (skills:598, model_skill_bindings:1459), `shared/types.ts` (TeamConfig:69, SkillYaml:1737), `server/controller/pipeline-controller.ts:1465` (applySkill), `docs/decisions/memory-architecture.md`, `docs/config-sync/schemas.md`
- omnius: `phase_3/skill_lifecycle.py` (SkillModel/lifecycle), `mvp_core/pool/__init__.py` (CedarPDP, ReasoningPool, FamilyAttestation), `specs/SPEC-SK-skill-lifecycle.md`, `specs/SPEC-KP-knowledge-plane.md`, `architecture/MASTER-ARCHITECTURE.md` §0/§6.2/§7.5
- Omniscience: `apps/server/src/omniscience_server/mcp/server.py` (13 tools), `packages/core/.../auth/{scopes,workspace}.py`, `docs/decisions/0015-multiqlti-as-mcp-consumer-and-source.md`, `docs/decisions/` ADR-0008 (bitemporal)
- platform-design: `ai-sre/agents/orchestrator/config.py` (AgentDefinition), `ai-sre/runbooks/*.md` (step tags), `ai-sre/guardrails/read_only.py`, `docs/adrs/0055-*.md`
- genai-enablement: `docs/autonomous-sre-harness-plan.md` §3 (tiers), `docs/decisions/0009-organizational-dark-factory-sdd.md` (ADR-to-SPEC authority), `solutions/sre-harness/src/sre_harness/{autonomy_tiers,change_gate,platform_graph}.py`
- monorepo: `.claude/skills/` + `VENDORED.md`, `skills-lock.json`, `.claude/agents/**`
