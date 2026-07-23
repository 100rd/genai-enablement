# SP-70 Continuous Management compatibility and package manifest

**Publishing task:** [`task-sp-70-continuous-management-contract-release`](../specs/task-sp-70-continuous-management-contract-release.md)
**Governing ADR:** [ADR-0020](../decisions/0020-barbarossa-continuous-management-plane.md) (accepted)
**Machine artifact:** [`task-sp-70-continuous-management-manifest.json`](task-sp-70-continuous-management-manifest.json)
**Source of truth:** [`portfolio/synchronized-platform.json`](../../portfolio/synchronized-platform.json) `work_packages`

This is a navigation and compatibility publication only. It does not implement Barbarossa, select a
live domain, activate a management action, or authorize a deployment. Every field in the JSON artifact
is copied from the machine registry, which remains the single source of truth; `tests/test_sp70_continuous_management_manifest.py`
fails if the two drift apart.

## What this closes

Before this publication, `SP-71` through `SP-85` depended on `SP-70` without a single place that
confirmed, package by package, that each one already has an owner-local contract to build against (or,
for the one package that intentionally has none, an explicit blocked gate). This manifest is that place.

## AC-SP70-1 — no local-spec-required package, no unregistered ready task

For every package `SP-71`..`SP-85` the manifest records either:

- a `gate: "ready"` entry whose `contracts` list includes at least one owner-local `task` contract, and
  that task id is registered in the owner component's `task_specs` in the registry (checked by
  `synchronized-platform-workspace-check`, i.e. `check_synchronized_platform.py --workspace-root ..`); or
- a `gate: "blocked"` entry with an explicit `blocked_reason` (only `SP-85`, whose capability `SPEC-AUT`
  is `complete-for-planning-blocked` and has no task contract by design).

No package in the range is left without one of these two states, so none is "local-spec-required" and
none references an unregistered ready task.

| Package | Owner | Registry status | Owner-local contract | Gate |
|---|---|---|---|---|
| SP-71 | barbarossa | ready-for-development-non-live | task-sp-71-kernel-runtime | ready |
| SP-72 | barbarossa | ready-for-development-non-live | task-sp-72-federation-constraints | ready |
| SP-73 | barbarossa | ready-for-development-non-live | task-sp-73-actions-verification | ready |
| SP-74 | barbarossa | ready-for-development-non-live | task-sp-74-projection-cockpit | ready |
| SP-75 | barbarossa | ready-for-development-non-live | task-sp-75-reliability-readonly | ready |
| SP-76 | barbarossa | ready-for-development-non-live | task-sp-76-cost-value-readonly | ready |
| SP-77 | barbarossa | ready-for-development-non-live | task-sp-77-ai-effectiveness-readonly | ready |
| SP-78 | barbarossa | ready-for-development-non-live | task-sp-78-assurance-packs-readonly | ready |
| SP-79 | barbarossa | ready-for-development-non-live | task-sp-79-delivery-knowledge-readonly | ready |
| SP-80 | barbarossa | ready-for-development-non-live | task-sp-80-capacity-toil-product-readonly | ready |
| SP-81 | omniscience | ready-for-development | task-sp-81-management-context-v1 | ready |
| SP-82 | omnius | ready-for-development-no-effect | task-sp-82-management-action-v1 | ready |
| SP-83 | barbarossa | ready-for-development-producer-gated | task-sp-83-context-consumer | ready |
| SP-84 | platform-portal | ready-for-development-source-gated | task-sp-84-continuous-management-center | ready |
| SP-85 | barbarossa | blocked-on-live-evidence | — (capability SPEC-AUT only) | blocked |

## AC-SP70-2 — package order preserves owner authority and severance

Ground truth is ADR-0020's ownership boundaries (D1, D8, D9, D12) plus each owner-local task's own
declared scope, immutable to this registry-publishing task.

- **Acyclic DAG:** `check_synchronized_platform.py` walks the full `depends_on` graph (not only this
  package range) and fails with `"work-package dependency graph contains a cycle"` if one exists.
  `tests/test_sp70_continuous_management_manifest.py` re-asserts this against the live registry and the
  real sibling workspace.
- **No sibling writes:** every task contract listed above was read from its owner's own repository
  (`Barbarossa/docs/specs/*.md`, `Omniscience/docs/specs/task-sp-81-management-context-v1.md`,
  `omnius/docs/specs/task-sp-82-management-action-v1.md`,
  `platform-portal/docs/specs/task-sp-84-continuous-management-center.md`). Each task's `scope.include`
  paths are confined to that same repository (e.g. `src/kernel/**`, `src/domains/**`,
  `mvp_core/management_actions/**`, `backend/app/cmc/**`) and each task's `repo:` frontmatter field names
  only its own repository (`100rd/Barbarossa`, `100rd/Omniscience`, `100rd/omnius`,
  `100rd/platform-portal`). None references another component's directory, and none includes
  `docs/specs/**` (its own task-SPEC oracle) or the synchronized registry lock.
- **No live authority:** `SP-71`..`SP-84` are all explicitly `non-live`, `no-effect`, `producer-gated`,
  or `source-gated` in the registry; `SP-85` is `blocked-on-live-evidence` and carries no task contract
  at all. Acceptance of ADR-0020 authorizes planning and fixture-backed construction only (D12,
  acceptance record item 6); this manifest changes none of that.

## Non-authorization statement

This manifest is publication evidence for the `registry-contract` execution profile only. It grants no
live provider, credential, deployment, remediation, PII activation, or management action authority in
any component, and it does not change any other package's implementation status.
