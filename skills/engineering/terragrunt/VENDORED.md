# Vendored: terragrunt-skill

This directory is a **vendored copy** of a community Terragrunt skill.

| Field | Value |
|-------|-------|
| Upstream | https://github.com/jfr992/terragrunt-skill |
| Path | `skills/terragrunt-skill` |
| Author | Juan Reyes (jfr992) |
| License | Apache-2.0 (see `LICENSE`; GitHub mislabels it `NOASSERTION` due to a non-standard preamble — the body is verbatim Apache-2.0) |
| Vendored on | 2026-06-10 |
| Source ref | `main` (no tagged release upstream; ~22★ at vendoring time, last push 2026-04-30) |

## ⚠️ Status: community skill, not vendor-neutral

Unlike the sibling `terraform-skill` (Anton Babenko), this skill is:

- **Third-party / community-maintained** — not from HashiCorp or Gruntwork. Re-vet on each refresh.
- **Strongly opinionated** — it encodes ONE architecture: a three-repo pattern
  (Catalog units/stacks · Live deployments · separate Module repos), the `values.xxx`
  input convention, and `terragrunt.stack.hcl` stacks (newer Terragrunt). Treat it as
  *a* well-formed approach, not the only valid Terragrunt layout. If a project already
  uses a different Terragrunt structure, follow the project, not this skill.

## Why vendored

Terragrunt is referenced across this repo (`devops-engineer`, `solution-architect`,
`infra-team`, `pipeline-team`, the `terraform-module` profile's optional tools) but no
skill covered it — `terraform-skill` mentions Terragrunt zero times. This fills that gap
and replaces dangling `TERRAGRUNT_SKILL.md` / `TERRAGRUNT_QUICK_REFERENCE.md` references.

`SKILL.md` is the navigation hub; depth lives in `references/` (12 files), with HCL/TF
templates under `assets/` and a backend bootstrap in `scripts/setup-state-backend.sh`.

## Relationship to terraform-skill

- **terraform-skill** — HCL/module/state/testing patterns for raw Terraform/OpenTofu.
- **terragrunt-skill** — the orchestration layer *on top* (DRY root config, units/stacks,
  multi-account, dependency wiring). Terragrunt calls OpenTofu/Terraform underneath, so
  both apply: use terraform-skill for the module HCL, terragrunt-skill for the wrapper.

## Refresh procedure

```bash
base="https://raw.githubusercontent.com/jfr992/terragrunt-skill/main"
dst=".claude/skills/terragrunt-skill"; sp="skills/terragrunt-skill"
curl -fsSL --create-dirs "$base/$sp/SKILL.md" -o "$dst/SKILL.md"
curl -fsSL "$base/LICENSE" -o "$dst/LICENSE"
for f in catalog-scaffolding catalog-structure cicd-pipelines dependencies \
         live-structure multi-account naming patterns performance \
         root-config stack-commands state-management; do
  curl -fsSL --create-dirs "$base/$sp/references/$f.md" -o "$dst/references/$f.md"
done
# assets/ templates and scripts/setup-state-backend.sh: re-pull as needed (see git tree)
```

On refresh, re-verify the LICENSE still resolves to Apache-2.0 and re-skim SKILL.md for
any change of architectural opinion before trusting it.
