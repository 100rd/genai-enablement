# Vendored Skill — Provenance

- **Skill:** `secrets-vault-manager` (registry path `security/secrets-vault-manager`)
- **Upstream:** `alirezarezvani/claude-skills` · path `engineering/skills/secrets-vault-manager`
- **Author:** alirezarezvani
- **License:** MIT (see `LICENSE`)
- **Vendored from:** monorepo `.claude/skills/secrets-vault-manager` (originally vendored from upstream 2026-06-10)
- **Vendored into platform registry:** 2026-07-07

Carried verbatim. Only the platform extension frontmatter fields
(`version`, `tags`, `compatible_tools`, `tier`, `license`) were added to `SKILL.md`; the body,
references, and scripts are unchanged.

**Tier note:** set `tier: T3` (not the T1 default for guidance skills). The body directs
imperative, state-mutating secret operations — credential/key rotation, token revocation,
Vault seal/unseal, and `vault write` auth/policy configuration — which require explicit human
approval rather than read-only auto-execution.

**Refresh:** re-pull from upstream and re-verify the `LICENSE` body before trusting
(GitHub's license label is unreliable). Provenance authority for the wider monorepo set is
`.claude/skills/VENDORED.md`.
