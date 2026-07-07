# Vendored Skill — Provenance

- **Skill:** `gitops-workflow` (registry path `engineering/gitops-workflow`)
- **Upstream:** `wshobson/agents` · path `plugins/kubernetes-operations/skills/gitops-workflow`
- **Author:** wshobson
- **License:** MIT (see `LICENSE`)
- **Vendored from:** monorepo `.claude/skills/gitops-workflow` (originally vendored from upstream 2026-06-10)
- **Vendored into platform registry:** 2026-07-07

Carried verbatim. Only the platform extension frontmatter fields
(`version`, `tags`, `compatible_tools`, `tier`, `license`) were added to `SKILL.md`; the body
and references are unchanged.

**Tier note:** set `tier: T3` (not the T1 default for guidance skills). The body directs
state-mutating cluster operations — `kubectl apply` to install ArgoCD and automated
sync/prune/self-heal policies that continuously reconcile the cluster to Git — which require
explicit human approval rather than read-only auto-execution.

**Refresh:** re-pull from upstream and re-verify the `LICENSE` body before trusting
(GitHub's license label is unreliable). Provenance authority for the wider monorepo set is
`.claude/skills/VENDORED.md`.
