# AI SRE — Program Definition

**Status:** Adopted working definition · 2026-07-02
**Companion docs:** [autonomous-sre-harness-plan.md](autonomous-sre-harness-plan.md) (the
safety-core component plan) · [ADR-0001](decisions/0001-continuous-detection-sentinel.md)
(Sentinel) · [ADR-0003](decisions/0003-unified-sdlc-standard.md) (SDLC bridge) ·
[ADR-0020](decisions/0020-barbarossa-continuous-management-plane.md)
(Continuous Management placement; ADR-0019 retained as Reliability history) ·
[platform-glossary.md](platform-glossary.md) (vocabulary)

## Mission

**AI SRE is Barbarossa's Reliability domain program: it builds the reliability machinery; Barbarossa
independently measures current platform-journey availability; humans own policy, command, and high-risk
decisions.**
Measured on MTTR and leverage, not tickets closed. The anchor fact that shapes everything:
SOTA agents autonomously resolve ~11% of incidents (ITBench) — so the bet is on the
machinery around agents, never on agent autonomy itself.

`SRE agent` is a Reliability-pack role family, not a singleton or an authority. The reusable harness,
eval, and Sentinel algorithms remain in `genai-enablement`; the proposed Barbarossa Continuous
Management Plane owns common durable loop mechanics and the isolated Reliability pack owns
journey/incident meaning. Omniscience remains severable context, Omnius owns governed execution, and
Platform Portal remains a view. Other domain packs share mechanics but never inherit SRE policy,
evidence or readiness.

## The two loops

AI SRE runs the **Incident Resolution Loop (IRL)** — a lifecycle distinct from the SDLC:

```
IRL:   DETECTED → TRIAGED → MITIGATED → RESOLVED → LEARNED      (seconds–minutes)
                                │             ▲
                                └── bridge ───┘
SDLC:  TRIGGERED → … → VERIFIED → GATED → LANDED                (hours–days, factory)
```

- **Mitigation does not wait for the durable SDLC**: restoring service is runtime-state work such as
  restart, rollback or scale. Barbarossa may request it only after current policy, constraints and
  authority join; Omnius re-authorizes and executes it, and fresh independent evidence determines
  recovery. A priority operational path does not bypass safety or owner authority.
- **The permanent fix never bypasses the factory**: durable code/IaC changes go through
  the SDLC standard (ADR-0003) as an incident-spawned task (P0 lane, same gates —
  priority buys queue position, never gate skips).
- **Permanent-fix chase is linked follow-up, not closure authority**: `incident_id` joins `task_id`, but
  a landed fix is factory evidence, not an incident verdict. Current independent recovery evidence and
  human-owned incident policy govern incident closure; unresolved permanent work remains an explicit
  linked case or risk item.
- Two root causes, two speeds: mitigation needs only the **operational** cause ("release N
  makes the disk hurt" — minutes, from the graph); the **code-level** cause is the
  factory's job later. Unfound root cause → a factory research task (omnius Mode B:
  read-only, outputs ranked hypotheses to a human).

## The seven layers

LLM lives **only in layer 4**. Everything that decides "allowed / not allowed" and
everything that rolls back is deterministic.

| # | Layer | What it does | LLM | Built from |
|---|---|---|---|---|
| ① | **Prevention** | change-gate in CI blocks dangerous changes *before* deploy (blast-radius, resource presence, namespace checks); the cheapest incident is the one that never happened — the market white space | no | sre-harness change-gate + gate CLI + GitLab CI / ArgoCD PreSync (merged) |
| ② | **Detection** | thresholds, evictions, canary metrics + **Sentinel**: trend-slope changes, drift, degradation | no | Prometheus/Datadog + Sentinel (ADR-0001; offline core shipped: detectors + lead-time eval + `sentinel scan` CLI with finding persistence; runtime wiring pending) |
| ③ | **Knowledge** | bitemporal platform graph: `incident_timeline`, `blast_radius`, `find_similar_incidents`, `suggest_runbook`, `as_of` replay | no | Omniscience v0.5.0 released; MCP v1 plus HA/freshness evidence remain in progress under Omniscience#350 |
| ④ | **Reasoning** | T1 pre-triage: operational RCA draft + confidence + proposed actions; T2 advisory remediation; deep root-cause hunt → factory research | **yes** | donors: ai-incident-agent nodes (gather_context, analyze, match_runbooks — see History below) + PB-SRE's 9 specialists (gpu-health, scaling, incident, …). The least-built layer |
| ⑤ | **Safety** | autonomy tiers T1–T4 with degradation on low confidence; action-tier table (SR 11-7 artifact); verdicts PROCEED/BLOCK/REQUIRE_HUMAN; **rollback is deterministic, never LLM** | no | sre-harness core (merged, unit-tested) |
| ⑥ | **Action** | Barbarossa proposes and independently verifies; Omnius owns separately authorized execution. Future T4 bounded reversible actions are monitored and haltable; T3 requires on-call approval; durable changes use governed factory delivery | no | harness action contracts + Omnius owner receipts |
| ⑦ | **Learning** | postmortem: machine drafts (`generate_postmortem`), human finalizes; mitigation → runbook **skill** in the registry (PR + quarantine, tier-tagged steps) → next occurrence is T4-auto in seconds; eval cases grow from real incident replays | partly | skills registry (seeded: `sre/gpu-node-unhealthy`) + eval Stage 0 (merged) |

The loop gets faster through layer ⑦ — learning — never by cutting gates.

## Degraded mode (deliberate design property)

Omniscience is the default context source for layer ④ (`MCP: timeline / blast_radius /
similar incidents`). When the hub is unavailable **or holds no signal linking the
problem**, T1 falls back to direct sources — kubectl, PromQL, git log — and finds the
operational cause itself. Slower, still functional. Severance is mandatory for every hub
consumer (glossary: *Severance*; Omniscience#350). Under ADR-0020 this fallback belongs to Barbarossa's
Reliability pack;
loss of context cannot suppress its deterministic probe/evaluate/alert path.

## Humans

| Role | Owns |
|---|---|
| **On-call** | receives an assembled case (not a raw alert); approves T3 actions; can halt any T4 action |
| **Curator** | finalizes postmortems, owns the action-tier table, admits runbook skills into the registry |

The inversion: humans move from *reading dashboards* to *making decisions and curating
correctness*. Agents never edit their own success criteria (C2, ADR-0002).

## Metrics (via OutcomeEvent, ADR-0003 I6/I8)

MTTR · share of incidents mitigated at T4 without a human · escape rate (return signal
independent of the verifier) · share of alerts with an RCA draft ready when on-call opens
them · offline eval score on incident replays (ITBench-style) · toil hours.

## Maturity map (honest, 2026-07)

**Built:** harness deterministic core + eval + gate CLI (main), Sentinel offline core
(detectors + lead-time eval + `sentinel scan` CLI with finding persistence, main),
Omniscience v0.5.0 with 14 current MCP tools (MCP v1 targets 15), action-tier table, skills registry (24 skills incl.
runbook and security response families), ADR-0001/0003/0008.
**Missing (in unblocking order):** ① immutable Omniscience MCP v1 release, consumer pin and severance
evidence → ② the T1 reasoning layer (harness plan Stage 1) → ③ a
live cluster to observe (platform-design agent-cluster IaC landed) → ④ Sentinel runtime
wiring (CronJob on a live cluster + live observability-source adapters; offline core
landed) → ⑤ escape join → ⑥ Omniscience HA profile (#350).

**Interim mode that works today:** on-call opens Claude Code with the Omniscience MCP and
performs layer ④ manually with the same tools.

## Roadmap

Stage 0 eval ✅ → **Stage 1 T1 read-only triage/RCA ← current** → Stage 2 advisory
change-gate wired into live CI → Stage 3 deterministic rollback → Stage 4 T4
auto-remediation → Stage 5 T3 HITL → Stage 6 permanent-fix chase.

## History — superseded iterations

- **ai-incident-agent** (Dec 2025, LangGraph "smart pager") — removed from `solutions/` in
  July 2026; its node design (gather_context → validate_alert → analyze_incident →
  match_runbooks → enrich_notification → send_notifications) remains in git history as the
  donor specification for layer ④ T1. Its self-made `decision_nodes` are the one part
  deliberately discarded — decisions belong to the harness gates, not to the reasoning
  agent.
- **PB-SRE** (platform-design `ai-sre/`) — advisory multi-agent prototype; its 9
  specialists become layer-④ reasoners inside harness tiers; its read-only guardrails and
  GitOps-PR remediation pattern carry into layers ⑤–⑥.
