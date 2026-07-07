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
| [engineering/terraform](engineering/terraform/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/terraform-skill` | Anton Babenko / vendored | Apache-2.0 | 2026-07-07 | Diagnose-first Terraform/OpenTofu guidance with `references/` tree; upstream provenance in `VENDORED.md`/`LICENSE` |
| [engineering/terragrunt](engineering/terragrunt/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/terragrunt-skill` | Juan Reyes / vendored | Apache-2.0 | 2026-07-07 | Terragrunt catalog/live/stack scaffolding; ships own `VENDORED.md`/`VENDORED-DELTA.md`, `references/`, `assets/`, `scripts/` |
| [engineering/kubernetes](engineering/kubernetes/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/kubernetes-skill` | Lukas Niessen / vendored | MIT | 2026-07-07 | Failure-mode manifest workflow (EKS/GKE/AKS/OpenShift, GitOps, Helm/Kustomize); `references/` tree |
| [sre/gpu-node-unhealthy](sre/gpu-node-unhealthy/SKILL.md) | 0.1.0 | T3 | converted from `platform-design/ai-sre/runbooks/gpu-node-unhealthy.md` | platform | MIT | 2026-07-02 | First runbook-type skill; step-level tier tags replace `auto_executable_steps`/`approval_required_steps` |
| [sre/high-pod-restart-rate](sre/high-pod-restart-rate/SKILL.md) | 0.1.0 | T3 | converted from `platform-design/ai-sre/runbooks/high-pod-restart-rate.md` | platform | MIT | 2026-07-07 | Runbook skill; steps 1–3 T1 auto, step 4 (rollback) T3 approval |
| [sre/vllm-high-latency](sre/vllm-high-latency/SKILL.md) | 0.1.0 | T3 | converted from `platform-design/ai-sre/runbooks/vllm-high-latency.md` | platform | MIT | 2026-07-07 | Runbook skill; steps 1–3 T1 auto, steps 4–5 (scale, cache config) T3 approval |
| [sre/promql-generator](sre/promql-generator/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/promql-generator` | akin-ozer / vendored | Apache-2.0 | 2026-07-07 | Author PromQL queries + recording/alerting rules; examples + references |
| [sre/promql-validator](sre/promql-validator/SKILL.md) | 0.1.0 | T1 | vendored from monorepo `.claude/skills/promql-validator` | akin-ozer / vendored | Apache-2.0 | 2026-07-07 | Validate/lint PromQL (syntax, semantic, anti-pattern); scripts + docs |
| [sre/slo-architect](sre/slo-architect/SKILL.md) | 2.9.0 | T1 | vendored from monorepo `.claude/skills/slo-architect` | alirezarezvani / vendored | MIT | 2026-07-07 | SLI/SLO/error-budget design + multi-window burn-rate; upstream version 2.9.0 preserved, only `tier` added |
| [security/secrets-vault-manager](security/secrets-vault-manager/SKILL.md) | 0.1.0 | T3 | vendored from monorepo `.claude/skills/secrets-vault-manager` | alirezarezvani / vendored | MIT | 2026-07-07 | First `security/` member (namespace proposed by ADR-0008, PR #26 pending); Vault + cloud secret-store patterns; T3 — body directs state-mutating secret ops |

## Planned seeds

- _none currently_
