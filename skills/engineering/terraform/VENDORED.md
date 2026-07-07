# Vendored: terraform-skill

This directory is a **vendored copy** of the upstream Terraform/OpenTofu skill.

| Field | Value |
|-------|-------|
| Upstream | https://github.com/antonbabenko/terraform-skill |
| Path | `skills/terraform-skill` |
| Author | Anton Babenko |
| License | Apache-2.0 (see `LICENSE`) |
| Vendored version | **1.17.1** |
| Vendored on | 2026-06-10 |
| Source ref | `master` |

## Why vendored

Agents in this repo (notably `.claude/agents/engineering/terraform-engineer.md`)
defer to this skill as their source of truth for Terraform/OpenTofu patterns,
state management, testing, security, CI/CD, and code intelligence. Vendoring
keeps that knowledge base available offline and pinned to a known version,
instead of duplicating ~500 lines of guidance inside the agent persona.

`SKILL.md` is the diagnose-first workflow router; depth lives in `references/`
and is loaded on demand.

## Refresh procedure

```bash
base="https://raw.githubusercontent.com/antonbabenko/terraform-skill/master"
dst=".claude/skills/terraform-skill"
curl -fsSL "$base/skills/terraform-skill/SKILL.md" -o "$dst/SKILL.md"
curl -fsSL "$base/LICENSE" -o "$dst/LICENSE"
for f in ci-cd-workflows code-intelligence-lsp code-patterns module-patterns \
         quick-reference security-compliance state-management testing-frameworks; do
  curl -fsSL "$base/skills/terraform-skill/references/${f}.md" -o "$dst/references/${f}.md"
done
# then bump the "Vendored version" / "Vendored on" rows above from version.json
```

Local additions that are **NOT** part of upstream and must be preserved on
refresh (they live elsewhere in the repo, not in this directory):

- Verification Loop + `VERIFICATION_COMPLETE` report format (in the agent)
- SDLC profile `.claude/profiles/infra/terraform-module.yaml`
- CFN→Terraform migration set (`terraform-migration-engineer`, command, hook)
- Startup/shutdown history protocols and inter-agent escalation rules
