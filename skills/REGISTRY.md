# Platform Skills Registry

Governed by [ADR-0002](../docs/decisions/0002-platform-skills-registry.md).
Vocabulary per the [platform glossary](../docs/platform-glossary.md).

**Format:** every skill is a directory with a `SKILL.md` (Agent Skills standard: YAML
frontmatter `name` + `description`, markdown body) plus the platform extension namespace
(`version`, `tags`, `compatible_tools`, `tier`, `license`). Content only — trust state
lives in each consuming runtime, never in these files (ADR-0002 D3).

**Pinning:** `skills-lock.json` records the sha256 of every `SKILL.md`. Tracking-mode
consumers (multiqlti, workstations) follow `main`; pinned-mode consumers (omnius,
production) consume only at lock-file hashes. Update the lock on every skill change.

**Changing skills:** PR only (ADR-0002 D4). Agent-authored changes must attach evidence
(runs, success-delta, models). Any body change re-quarantines the skill in every runtime
(C1). Verification criteria are never agent-editable (C2).

## Index

| Skill | Version | Tier | Origin | Author | License | Added | Notes |
|---|---|---|---|---|---|---|---|
| [engineering/golang-dev](engineering/golang-dev/SKILL.md) | 0.1.0 | T1 | in-house, new | platform | MIT | 2026-07-02 | Go development conventions + pre-PR verification loop |
| [sre/gpu-node-unhealthy](sre/gpu-node-unhealthy/SKILL.md) | 0.1.0 | T3 | converted from `platform-design/ai-sre/runbooks/gpu-node-unhealthy.md` | platform | MIT | 2026-07-02 | First runbook-type skill; step-level tier tags replace `auto_executable_steps`/`approval_required_steps` |

## Planned seeds

- `engineering/terraform` — vendor from the monorepo `.claude/skills/terraform-skill`
  (Anton Babenko, Apache-2.0) with its `references/` tree and upstream provenance.
- Remaining PB-SRE runbooks (`high-pod-restart-rate`, `vllm-high-latency`) — same
  conversion as `gpu-node-unhealthy`.
