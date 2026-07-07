# terraform-skill — Local Delta (newer than upstream)

The vendored `terraform-skill` is upstream **v1.17.1** (latest as of 2026-06-10), but its
feature coverage **caps at Terraform ~1.11**. This delta records TF/OpenTofu changes through
**Terraform 1.15.6 (2026-06-10)** and **OpenTofu 1.12.0 (2026-05-14)** that the skill does
not yet cover. Apply these on top of `SKILL.md`. Re-check on the next upstream refresh and
delete rows the skill absorbs.

> **Detect the tool + version first.** Terraform 1.15 and OpenTofu 1.12 have **diverged** —
> several features exist in only one. The Response Contract's "version floor" step must name
> `terraform` vs `tofu` and the exact version before emitting anything below.

## Version floors to add to the skill's Feature Guard Table

| Feature | Floor | Tool | Notes |
|---|---|---|---|
| `import { identity = … }` (import by provider identity, mutually exclusive with `id`) | **1.12** | TF + OT | precise imports for composite-identity resources |
| ephemeral values/resources GA + refinements | 1.11→1.12 | TF + OT | skill already knows ephemeral 1.10; GA hardening landed later |
| `list`/query resources, `terraform query` cmd, **`.tfquery.hcl`** files, **`action` blocks** (non-CRUD provider ops) | **1.14** | TF only | new file type + new top-level blocks; build floor Go 1.25 / macOS 12+ |
| **`convert()`** builtin (inline type conversion) | **1.15** | TF only | gate on `required_version >= 1.15` |
| **variables/locals allowed in module `source` and `version`** | **1.15** | TF only | previously had to be static literals — big authoring change |
| explicit `type = …` on `output` blocks; functions allowed in `mock` blocks | **1.15** | TF only | |
| `deprecated` attribute on `variable`/`output` (emits warnings) | **1.15** | TF only | module authors mark inputs/outputs deprecated |
| `import` blocks usable **inside modules** | 1.16 (dev) | TF | **do NOT emit for stable targets yet** |

## OpenTofu-only — will BREAK in Terraform (do not emit in `terraform` repos)

| Feature | Floor (OT) | Note |
|---|---|---|
| `enabled` meta-argument (0/1 alternative to `count`/`for_each`) | 1.11 | invalid in TF |
| `destroy = false` lifecycle (drop from state without destroying) | 1.12 | TF has no equivalent; use `state rm` there |
| dynamic `prevent_destroy` (can reference variables) | 1.12 | TF requires a literal |
| `-exclude` / `-exclude-file` / `-target-file` on plan/apply | 1.10 | TF has no `-exclude` |
| `oci:` provider/module **source** scheme + OCI mirror | 1.10 | not valid in TF |
| cross-type `moved` blocks (move between resource types) | 1.10 | TF `moved` is same-type only |
| `const = true` variables (static eval) | 1.12 | OT-only |
| local backend writes pretty-printed JSON state | 1.12 | cosmetic; changes committed local-state diffs |

## Backend / fmt notes (sharpen the skill)
- New S3 backends: `use_lockfile = true`, **omit `dynamodb_table`** (DynamoDB locking deprecated, TF 1.11 / OT 1.10). The skill is correct here — just stop emitting `dynamodb_table` for new code.
- The `backend` block is now validated by **`terraform validate`** (TF 1.15) — backend errors surface before `init`.
- S3 backend auth can use **AWS IAM Identity Center / `aws login`** sessions (TF 1.15 / OT 1.12) — no static keys in backend config.
- **`fmt` is version-coupled.** No canonical-format overhaul happened; the only in-window scope change is `fmt` now formatting `.tfquery.hcl` (TF 1.15). Always run the **repo's pinned binary** and re-run `fmt` after any version bump — code formatted by an older binary can fail `fmt -check` on a newer one.

## Deprecations / breaking (recent)
- DynamoDB state locking deprecated → `use_lockfile` (TF 1.11 / OT 1.10).
- WinRM provisioner connection deprecated (OT 1.12) → removed OT 1.13; TF still supports it.
- S3 backend `AWS_USE_FIPS_ENDPOINT` / `AWS_USE_DUALSTACK_ENDPOINT` now accept only `"true"`/`"false"` (TF 1.15).
- Runtime floors raised (Go 1.25, macOS 12+) — affects CI runner images, not generated HCL.

Sources: hashicorp/terraform & opentofu/opentofu CHANGELOGs and release blogs (TF v1.11–1.15, OT 1.10–1.12), verified 2026-06-11.
