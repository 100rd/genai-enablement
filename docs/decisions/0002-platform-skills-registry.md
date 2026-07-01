# ADR-0002: Platform skills registry — SKILL.md canon, git-backed distribution, per-runtime trust

- **Status:** Proposed
- **Date:** 2026-07-02
- **Deciders:** platform owner
- **Scope:** cross-repo (multiqlti, omnius, Omniscience, platform-design/PB-SRE, genai-enablement, engineer workstations)
- **Vocabulary:** terms as defined in [platform-glossary.md](../platform-glossary.md) (PR #9)

## Context

The platform goal is that a skill — e.g. "how we develop in Go" — is **the same artifact**
whether it is used by an engineer in Claude Code, by a multiqlti pipeline stage, or by an
omnius Worker. Today there are three skill systems and ~10 skill-like formats across the
estate, with no shared source of truth:

1. **multiqlti** (live): skill = Postgres record whose payload is `systemPromptOverride` +
   `tools[]`; interchange format is a bespoke `multiqlti/v1 Kind: Skill` YAML. Notably this
   *diverged from multiqlti's own PLAN decision #13*, which had selected "Markdown with
   frontmatter". A git ingestion path already exists (`git-skill-sync` walks a repo and
   parses YAML/JSON skill files).
2. **omnius** (design + mock): has already adopted **SKILL.md as a cross-vendor open
   standard** (MASTER-ARCHITECTURE: "agent = model-agnostic prompt + SKILL.md runbooks +
   MCP tools"). Its `SkillModel` is a trust envelope around a SKILL.md-style body:
   provenance, quarantine, `approved_body_hash`, success-delta lifecycle
   (`unverified → verified → deprecated`), CODEOWNERS-gated git-backed store —
   explicitly *"a Controller + git-backed store, not an HTTP API an agent can call to
   mutate skills"* (SPEC-SK).
3. **Monorepo tooling** (live): 40+ canonical Agent Skills `SKILL.md` files
   (`.claude/skills/`, `.gemini/skills/`), a provenance index (`VENDORED.md`), and a
   sha256 lock-file (`skills-lock.json` with `computedHash`) — a working reference
   implementation of pinned skill distribution.

Additionally, PB-SRE runbooks are skill-shaped markdown with step-level autonomy tags
(`auto_executable_steps` / `approval_required_steps`), and both factories want agents to
**improve skills from their own experience** (multiqlti "lessons" memory layer; omnius
`accumulated-lesson` skill type).

Two hard requirements emerged from design discussion:

- **R1 — one content artifact, many runtimes.** The Go skill must be a single file with a
  single change history, consumable by Claude Code natively, by multiqlti pipelines, and by
  omnius task classes.
- **R2 — agents may modify skills, and runtimes may trust proven skills** — without
  reward-hacking or silent corruption of a working asset.

## Decision

### D1. Canonical format: Agent Skills `SKILL.md`

A skill is a directory containing `SKILL.md` (YAML frontmatter + markdown body), optionally
`references/`, `scripts/`, `examples/`, `LICENSE`. Frontmatter:

```yaml
---
name: golang-dev                # required (Agent Skills standard)
description: Use when ...       # required (Agent Skills standard)
# platform extension namespace (all optional):
version: 1.2.0                  # semver, bumped on body change
tags: [engineering, golang]
compatible_tools: [claude-code, multiqlti, omnius, cursor, antigravity]
tier: T1                        # max autonomy tier the skill's instructions assume
license: MIT
---
```

Rationale: omnius has already standardized on it; the monorepo already has 40+ instances;
Claude Code / Cursor / agy consume it natively; and for multiqlti this is a *return to its
own decision #13*, not an external imposition. Runbooks converge to skills of type runbook
with step-level tier tags (T1–T4 per the glossary ruling), replacing the bespoke
PB-SRE frontmatter over time.

**The file contains content only.** Trust state, success statistics, and validation
metadata never live in the file (see D3).

### D2. Distribution: one git repo, lock-file pinning, two consumption modes

A single git repository — working name **`platform-skills`** — is the source of truth:

```
platform-skills/
├── engineering/golang-dev/SKILL.md
├── engineering/terraform/SKILL.md        # seeded from vendored .claude/skills
├── sre/gpu-node-unhealthy/SKILL.md       # converted PB-SRE runbook, tier-tagged steps
├── REGISTRY.md                           # provenance index (VENDORED.md pattern)
└── skills-lock.json                      # sha256 per skill (computedHash pattern)
```

- **CODEOWNERS-gated:** skill paths cannot be pushed to by agent/worker tokens; changes
  arrive only via PR (aligns with omnius REQ-SK-4).
- **Tracking mode** (multiqlti, personal instances, workstations): follow `main`; updates
  propagate quickly. Appropriate where the cost of a bad skill is low.
- **Pinned mode** (omnius, anything production-adjacent): consume only at lock-file SHAs.
  Auditability requires it — `replay_context` must be able to answer *which exact skill
  body was in context for task X* (bitemporal replay).

### D3. Trust separation: content is shared, trust is local, evidence travels

- **Content** (SKILL.md) — portable, one per skill, lives in the registry.
- **Trust status** (`unverified/verified/deprecated`, `validated_on_model`,
  `validated_env`, success counters) — **per-runtime, non-transferable.** A skill verified
  in multiqlti is *not* thereby verified in omnius: different models, stakes, and
  environments. Each runtime keeps its own trust index (omnius: `SkillStore`; multiqlti:
  new columns on its existing skill record; workstations: none needed).
- **Evidence (dossier)** — portable: run counts, success-delta, model families, source
  runtime. It accompanies a skill into another runtime's admission gate so the human (or
  future auto-gate) decides with data. This implements the **graduation path**:
  multiqlti is the proving ground; skills graduate into omnius with a track record.

### D4. Agent modification loop (R2), with two non-negotiable constraints

```
agent works → distills lesson → edits/creates SKILL.md
  → PR to platform-skills (bot branch; direct push blocked by CODEOWNERS)
  → CI: frontmatter schema lint · secret/content scan (SkillContentGate rules)
       · eval replay where golden cases exist
  → evidence attached to the PR (runs, success-delta, models)
  → human merge (auto-merge may later be earned per skill class,
    mirroring omnius's per-class auto-merge model)
  → each runtime pulls per its mode and re-earns trust locally
```

- **C1 — modification auto-demotes trust.** Any body change re-quarantines the skill in
  every runtime (hash mismatch vs `approved_body_hash` / lock-file `computedHash`). An
  improved skill must re-earn `verified`. This is the structural defense against silent
  corruption of working assets.
- **C2 — agents never edit their own success criteria.** The machine may refine a skill
  **body**; the verification procedure / definition of success is only ever *proposed* and
  requires a human gate (omnius SPEC-SK asymmetry, adopted platform-wide). This is the
  structural defense against reward hacking.
- **Churn control:** lessons accumulate in a staging area and are periodically distilled
  into one PR (batch), never one PR per run.

### D5. Per-runtime adapters (all small, none blocking the others)

| Runtime | Adapter | Effort basis |
|---|---|---|
| multiqlti | extend `git-skill-sync` to parse `SKILL.md` (frontmatter → name/description/tags/version; body → `systemPromptOverride`); `sourceType: 'git'` already exists | extension of an existing parser |
| omnius | `SkillStore.admit(body)` ingests the SKILL.md body into its trust envelope — already designed this way; Worker on Claude Agent SDK also consumes SKILL.md natively | designed-for |
| Claude Code / Cursor / agy | native — it is their format | none |
| PB-SRE | convert `runbooks/*.md` frontmatter to SKILL.md + tier tags | mechanical conversion |

### D6. Omniscience indexes the registry

`platform-skills` is registered as a git **connector** (source) in Omniscience. Skill
history becomes part of the platform graph: which skill version was active when incident X
happened; `blast_radius` of a skill (which pipelines/task classes consume it); correlation
of success-delta degradation with model upgrades.

## Consequences

**Positive**
- One Go skill, one change history, three-plus consumers (R1 satisfied).
- Agents improve skills safely (R2 satisfied via C1/C2).
- multiqlti gains a trust vocabulary it lacks today; omnius gains a proving ground and
  evidence-informed admissions; engineers get the same skills locally.
- The registry mechanics (lock-file, provenance index) already exist in the monorepo as a
  working pattern — low invention risk.

**Negative / costs**
- One more repo to govern; CODEOWNERS review load (mitigated by batching, D4).
- multiqlti's internal marketplace (fork/share/semver) must reconcile local forks with the
  registry (forks become branches or divergent local skills — needs a follow-up design
  note).
- Trust re-earning after every body change adds latency between "improved" and "trusted"
  (accepted deliberately — that latency is the safety margin).

**Risks**
- Skill flapping if agents propose edits too eagerly → batch distillation + PR rate limits.
- Cross-runtime contamination if a runtime mistakenly imports another's trust status →
  trust indexes are structurally local (D3); conformance test to enforce.
- Format drift in the extension namespace → frontmatter schema is versioned and linted in
  registry CI.

## Alternatives considered

1. **`multiqlti/v1 Kind: Skill` YAML as the canon** — rejected: proprietary where a
   cross-vendor open standard exists; omnius already committed to SKILL.md; loses native
   consumption by Claude Code/Cursor/agy; and multiqlti itself originally chose
   markdown+frontmatter (decision #13).
2. **Central skill service (DB + HTTP API)** — rejected: omnius SPEC-SK explicitly forbids
   a mutable skill API as an attack surface; git provides provenance, review gates, and
   rollback for free; an API can later be layered read-only on top if needed.
3. **Keep per-runtime formats + N×M converters** — rejected: converter drift recreates
   today's problem with extra steps; no single change history per skill.
4. **Store trust status in the SKILL.md frontmatter** — rejected: trust is
   runtime-measured and non-transferable (D3); embedding it would make a skill "verified"
   everywhere after one runtime's validation — precisely the unsafe shortcut.

## Follow-ups

- [ ] Create `platform-skills` repo; seed with 2–3 skills (`golang-dev` new;
      `terraform` from vendored set; one converted PB-SRE runbook).
- [ ] Registry CI: frontmatter schema lint, secret scan, lock-file update job.
- [ ] multiqlti: SKILL.md parser in `git-skill-sync` (PoC target — first live consumer).
- [ ] omnius: issue to rename Cedar `permitted_skill_set` → `capability set`
      (glossary Part 3 ruling; avoids the internal name collision).
- [ ] Omniscience: register the registry as a git source (D6).
- [ ] Follow-up design note: multiqlti marketplace forks vs registry reconciliation.

## References

- [platform-glossary.md](../platform-glossary.md) — canonical vocabulary (skill, trust
  lifecycle, evidence, graduation path, lock-file/pinning)
- omnius: `specs/SPEC-SK-skill-lifecycle.md`, `phase_3/skill_lifecycle.py`,
  `architecture/MASTER-ARCHITECTURE.md` §6.2
- multiqlti: `PLAN.md` decision #13, `server/services/git-skill-sync.ts`,
  `shared/types.ts` (`SkillYaml`)
- Omniscience: `docs/decisions/0015-multiqlti-as-mcp-consumer-and-source.md`
- monorepo: `.claude/skills/` + `VENDORED.md`, `skills-lock.json`
- Agent Skills open standard (SKILL.md), Linux Foundation AAIF
