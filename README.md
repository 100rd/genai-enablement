# AI Platform — Coordination Hub

This repository is the coordination point for our AI platform: the canonical vocabulary,
cross-repo decisions (ADRs), the shared skills registry, and the platform vision. If you
work on any subproject, the words, rules, and skills here are binding.

## The platform

Goal: platform-level AI enablement — accelerate engineering 30–50% on selected work
classes, make AI SRE own the full knowledge of platform problems, give engineers extra
hands, and unload the backlog. Humans own decisions; agents do the work under
deterministic gates (L4, never L5).

| Project | Role | Status |
|---|---|---|
| [**Omniscience**](https://github.com/100rd/Omniscience) | Knowledge hub — ingests platform sources (code, IaC, K8s, CI, alerts, chat) into a bitemporal graph; serves it to any client via MCP (13 tools) | v0.2 shipped, stabilizing |
| [**multiqlti**](https://github.com/100rd/multiqlti) | Personal dark factory — multi-model SDLC pipelines for one engineer; the platform's proving ground | live |
| [**omnius**](https://github.com/100rd/omnius) | Centralized dark factory — org-scale governed SDLC (deterministic core, untrusted agents, human-owned merges) | design + tested mockup |
| [**platform-design**](https://github.com/100rd/platform-design) | Infra substrate (AWS/EKS/GitOps/policy) + PB-SRE advisory diagnostics | design estate |
| [**genai-enablement**](https://github.com/100rd/genai-enablement) (this repo) | Program frame, shared artifacts, autonomous SRE harness (safety core: autonomy tiers, change gates) | active |

> Some component repositories are private — ask the platform owner for access if a link
> returns 404.

## How they connect

```
        engineers (Claude Code / IDE)          sources: git · k8s · CI · alerts · chat
                    │                                        │
                    ▼                                        ▼
   multiqlti ──MCP──►┌──────────────┐◄──connectors── platform runtime
                     │  Omniscience  │                 (defined by platform-design)
   omnius ────MCP──► │  (the graph)  │
                     └──────────────┘
   sre-harness ─MCP──────┘   ▲
   (this repo)               └── PB-SRE (platform-design) pushes topology, reads subgraphs
```

- Omniscience is the hub: everything reads platform knowledge from it, severably —
  removing it degrades consumers, never kills them.
- multiqlti → omnius is the **graduation path**: patterns and skills proven in the
  personal tier move into the governed tier with an evidence dossier.
- The **AI SRE program** = Sentinel detection (ADR-0001) + Omniscience knowledge +
  harness gates (this repo) + PB-SRE reasoning.

Detailed as-is map with per-link status and contract risks:
[`docs/diagrams/ai-platform-connections.excalidraw`](docs/diagrams/ai-platform-connections.excalidraw).

## Start here

| Artifact | What it gives you |
|---|---|
| [`docs/platform-glossary.md`](docs/platform-glossary.md) | Canonical terms, component boundaries (what each project does and does NOT), term-collision rulings |
| [`docs/decisions/`](docs/decisions/) | ADRs binding across repos (0001 Sentinel, 0002 skills registry) |
| [`skills/`](skills/) | Shared skills registry — SKILL.md format, sha256 lock, PR-only changes ([rules](skills/REGISTRY.md)) |
| [`docs/autonomous-sre-harness-plan.md`](docs/autonomous-sre-harness-plan.md) | AI SRE direction: autonomy tiers, action tiers, gates |
| [`research/`](research/) | Market and architecture research (40+ solutions, 2026 agentic-SRE refresh) |
| [`docs/role-definition.md`](docs/role-definition.md), [`docs/implementation-roadmap.md`](docs/implementation-roadmap.md), [`docs/success-metrics.md`](docs/success-metrics.md) | The enablement program: role, roadmap, DORA-based metrics |

## Rules for subproject engineers

1. **A change touching two or more components starts with an ADR here.**
2. **Terms per the glossary** — in docs, ADRs, and cross-repo contracts. Code identifiers
   may stay local.
3. **How-tos become skills** in [`skills/`](skills/) (PR-only, evidence attached for
   agent-authored changes) — not wiki pages.
4. API/MCP contracts live with their component (e.g. the Omniscience MCP contract lives in
   the Omniscience repo); this repo records the *decisions* about them.

## The harness (code in this repo)

`solutions/sre-harness/` — the deterministic safety core for SRE agents: autonomy-tier
engine (T1–T4 with degradation), action-tier table, change-validation gate
(PROCEED / BLOCK / REQUIRE_HUMAN — no LLM inside), platform-graph port with an Omniscience
MCP adapter, offline eval harness, gate CLI with CI integrations. See the
[plan](docs/autonomous-sre-harness-plan.md) and [ADR-0001](docs/decisions/0001-continuous-detection-sentinel.md).
