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
| [engineering/python-dev](engineering/python-dev/SKILL.md) | 0.1.0 | T1 | in-house, new | platform | MIT | 2026-07-07 | Python conventions grounded in `solutions/sre-harness` (Poetry, ruff, mypy, pytest) + pre-PR verification loop |
| [engineering/typescript-dev](engineering/typescript-dev/SKILL.md) | 0.1.0 | T1 | in-house, new | platform | MIT | 2026-07-07 | TypeScript conventions (strict tsconfig, no `any`, explicit export return types) + eslint/prettier/tsc verification loop |
| [engineering/terraform](engineering/terraform/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/terraform-skill` | Anton Babenko / vendored | Apache-2.0 | 2026-07-07 | Diagnose-first Terraform/OpenTofu guidance with `references/` tree; upstream provenance in `VENDORED.md`/`LICENSE` |
| [engineering/terragrunt](engineering/terragrunt/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/terragrunt-skill` | Juan Reyes / vendored | Apache-2.0 | 2026-07-07 | Terragrunt catalog/live/stack scaffolding; ships own `VENDORED.md`/`VENDORED-DELTA.md`, `references/`, `assets/`, `scripts/` |
| [engineering/kubernetes](engineering/kubernetes/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/kubernetes-skill` | Lukas Niessen / vendored | MIT | 2026-07-07 | Failure-mode manifest workflow (EKS/GKE/AKS/OpenShift, GitOps, Helm/Kustomize); `references/` tree |
| [engineering/github-actions-generator](engineering/github-actions-generator/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/github-actions-generator` | akin-ozer / vendored | Apache-2.0 | 2026-07-07 | Scaffold GitHub Actions workflows + custom actions; assets/examples/references |
| [engineering/github-actions-validator](engineering/github-actions-validator/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/github-actions-validator` | akin-ozer / vendored | Apache-2.0 | 2026-07-07 | Validate/lint GitHub Actions (actionlint/act); scripts + references |
| [engineering/gitops-workflow](engineering/gitops-workflow/SKILL.md) | 0.1.0 | T3 | vendored from monorepo `.claude/skills/gitops-workflow` | wshobson / vendored | MIT | 2026-07-07 | ArgoCD + Flux GitOps; T3 — body directs state-mutating cluster ops (kubectl apply install, auto sync/prune/self-heal) |
| [engineering/terraform-style-guide](engineering/terraform-style-guide/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/terraform-style-guide` | HashiCorp / vendored | MPL-2.0 | 2026-07-07 | HashiCorp official TF style conventions; MPL terms noted in `VENDORED.md`/`LICENSE` |
| [engineering/terraform-test](engineering/terraform-test/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/terraform-test` | HashiCorp / vendored | MPL-2.0 | 2026-07-07 | Native `terraform test` (.tftest.hcl), mocks, CI; upstream `metadata` preserved; MPL terms in `VENDORED.md` |
| [engineering/terraform-search-import](engineering/terraform-search-import/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/terraform-search-import` | HashiCorp / vendored | MPL-2.0 | 2026-07-07 | Terraform Search + bulk import to state; upstream `metadata`/`compatibility` preserved; MPL terms in `VENDORED.md` |
| [sre/gpu-node-unhealthy](sre/gpu-node-unhealthy/SKILL.md) | 0.1.0 | T3 | converted from `platform-design/ai-sre/runbooks/gpu-node-unhealthy.md` | platform | MIT | 2026-07-02 | First runbook-type skill; step-level tier tags replace `auto_executable_steps`/`approval_required_steps` |
| [sre/high-pod-restart-rate](sre/high-pod-restart-rate/SKILL.md) | 0.1.0 | T3 | converted from `platform-design/ai-sre/runbooks/high-pod-restart-rate.md` | platform | MIT | 2026-07-07 | Runbook skill; steps 1–3 T1 auto, step 4 (rollback) T3 approval |
| [sre/vllm-high-latency](sre/vllm-high-latency/SKILL.md) | 0.1.0 | T3 | converted from `platform-design/ai-sre/runbooks/vllm-high-latency.md` | platform | MIT | 2026-07-07 | Runbook skill; steps 1–3 T1 auto, steps 4–5 (scale, cache config) T3 approval |
| [sre/promql-generator](sre/promql-generator/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/promql-generator` | akin-ozer / vendored | Apache-2.0 | 2026-07-07 | Author PromQL queries + recording/alerting rules; examples + references |
| [sre/promql-validator](sre/promql-validator/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/promql-validator` | akin-ozer / vendored | Apache-2.0 | 2026-07-07 | Validate/lint PromQL (syntax, semantic, anti-pattern); scripts + docs |
| [sre/slo-architect](sre/slo-architect/SKILL.md) | 2.9.0 | T1 | vendored from monorepo `.claude/skills/slo-architect` | alirezarezvani / vendored | MIT | 2026-07-07 | SLI/SLO/error-budget design + multi-window burn-rate; upstream version 2.9.0 preserved, only `tier` added |
| [sre/blast-radius](sre/blast-radius/SKILL.md) | 0.1.0 | T1 | in-house, moved from monorepo `.claude/skills/blast-radius` | platform | MIT | 2026-07-07 | Read-only Terraform change blast-radius analysis + risk thresholds + advisory approval gate (no apply); moved verbatim |
| [sre/cost-estimate](sre/cost-estimate/SKILL.md) | 0.1.0 | T1 | in-house, moved from monorepo `.claude/skills/cost-estimate` | platform | MIT | 2026-07-07 | Read-only infracost pre-apply cost estimate + threshold approval gate; one line de-coupled from PROJECT_HISTORY |
| [security/secrets-vault-manager](security/secrets-vault-manager/SKILL.md) | 0.1.0 | T3 | vendored from monorepo `.claude/skills/secrets-vault-manager` | alirezarezvani / vendored | MIT | 2026-07-07 | First `security/` member (namespace proposed by ADR-0008, PR #26 pending); Vault + cloud secret-store patterns; T3 — body directs state-mutating secret ops |
| [security/secret-leak-response](security/secret-leak-response/SKILL.md) | 0.1.0 | T3 | in-house, new; seeded from ADR-0008 (PR #26, pending) build order | platform | MIT | 2026-07-07 | Response runbook for the secret verifier/detector family (`secret_in_change` BLOCK / `secret_in_state`); confirm→scope→rotate→revoke→verify→learn; D3 fingerprint-only, NEVER-T4 no key deletion |
| [security/cve-triage](security/cve-triage/SKILL.md) | 0.1.0 | T3 | in-house, new; seeded from ADR-0008 (PR #26, pending) build order | platform | MIT | 2026-07-07 | Response runbook for the `cve_in_sbom` detector; confirm→assess→advise→land-fix→verify; durable fix flows through the factory (D9), P0 buys queue not gate skip |
| [security/iam-drift-response](security/iam-drift-response/SKILL.md) | 0.1.0 | T3 | in-house, new; seeded from ADR-0008 (PR #26, pending) build order | platform | MIT | 2026-07-07 | Response runbook for the `iam_policy_drift` detector; reproduce→classify→advise→revert-via-IaC-PR→verify; never direct console, never broaden (NEVER-T4) |

## Planned seeds

- _none currently_ — the three ADR-0008 (PR #26, pending) seed detector families now have response runbooks (`secret-leak-response`, `cve-triage`, `iam-drift-response`).
