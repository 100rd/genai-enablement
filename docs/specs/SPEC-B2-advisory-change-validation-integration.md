# SPEC-B2 — Advisory change-validation CI / PreSync integration

**Specification type:** Capability SPEC  
**Status:** Draft / construction  
**Owner:** `genai-enablement` Autonomous SRE harness  
**Governing decisions:** [ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md) and the
[Autonomous SRE harness plan](../autonomous-sre-harness-plan.md)  
**Roadmap gate:** `B2`  
**Depends on:** SPEC-B0 offline evaluation harness  
**Evidence scope:** `local-portable-only`  
**Operational state:** `incomplete`  
**Next gate:** `approved-consumer-and-observed-advisory-run`  
**Authority:** `non-authorizing`; analysis `T1` and recommendation `T2`, with no delivery action authority

## Intent and boundary

As a delivery-system owner, I need one proposed change and one exact platform snapshot evaluated before
deploy or sync so that deterministic `proceed`, `block`, or `require_human` advice is recorded without
giving the harness execution authority.

SPEC-B2 owns the portable integration envelope, deterministic gate invocation, versioned result artifact,
machine-distinct disposition, and advisory GitLab CI / Argo CD PreSync templates. It does not own a live
platform-graph provider, deployment credentials, pipeline protection rules, production blocking policy,
override approval, or the deploy/sync action. Analysis is autonomy tier `T1`; the recommendation is `T2`.

**Inputs:** one bounded content-addressed change plus platform snapshot from an explicit CI or PreSync
source.  
**Outputs:** one immutable JSON advisory result and a machine-distinct exit disposition.  
**Out:** mutation tools, deploy/sync execution, model verdicts, implicit fixture promotion, production
credentials, and changing a consumer pipeline from advisory to blocking.

## Requirements

[REQ-B2-1] **The integration envelope is closed, bounded, and versioned.** The only accepted schema is
`sre-harness.change-advisory-request/v1`. UTF-8 JSON is capped at 1 MiB and rejects duplicate keys,
non-finite numbers, symlinks, non-files, unknown/missing fields, wrong primitives, and malformed values.
— **Fallback:** return the integration-input error disposition; do not run any check.

[REQ-B2-2] **The exact evaluated content is content-addressed.** `changeRevision` equals the canonical
SHA-256 of the closed change object and `platformRevision` equals the canonical SHA-256 of the closed
platform snapshot, including its canonical UTC `asOf`. Lists are sorted and unique, and platform entities
are exact immutable values.
Copied, reordered, stale, or digest-mismatched content is rejected rather than relabelled. — **Fallback:**
no advisory result is issued.

[REQ-B2-3] **Invocation provenance is explicit but not self-authorizing.** Every request carries a bounded
invocation id, exact source (`gitlab_ci` or `argocd_presync`), and canonical UTC request time. The platform
`asOf` cannot be in the future and, under this draft portable candidate policy, cannot be more than five
minutes older than the request. The consuming delivery-system owner must accept or revise that policy
before a real run can become B2 exit evidence. These fields
identify the claimed integration context; they do not prove that a real pipeline, cluster, or protected
revision produced it. — **Fallback:** invalid, future, stale, or unknown context fails before evaluation.

[REQ-B2-4] **The existing deterministic gate remains the only verdict authority.** The adapter reconstructs
one `ChangeRequest`, one read-only platform snapshot, and invokes `evaluate_change` with the registered
deterministic checks. It does not add an LLM, prompt, parser guess, or source-specific verdict override.
The aggregate order remains `block` over `require_human` over `proceed`. — **Fallback:** check exceptions
are integration failures, not fabricated advice.

[REQ-B2-5] **The result artifact is closed, versioned, and exactly rejoined.** The result schema is
`sre-harness.change-advisory-result/v1` and repeats the invocation id/source/time, exact platform `asOf`,
input digest, change/platform revisions, aggregate verdict/rationale, all check results/evidence, and T1/T2 boundary.
It states `advisory: true` and `mutationAuthorized: false`; it contains no deploy, sync, approval,
credential, or execution command. — **Fallback:** output-write failure is an integration error.

[REQ-B2-6] **Disposition and input failure are machine-distinct.** The integration command returns `0` for
`proceed`, `10` for `block`, `20` for `require_human`, and `64` for an invalid/unavailable envelope or
result sink. A valid `require_human` result can never be confused with malformed input. The legacy `gate`
CLI remains backward compatible and is not B2 integration evidence. — **Fallback:** unknown state is `64`,
never `0`.

[REQ-B2-7] **The adapter is advisory and action-free.** Evaluation may read only its supplied immutable
envelope and write only its declared local result artifact/stdout. It cannot deploy, sync, page, approve,
mutate platform state, or invoke a write-capable client. A consumer or human owns any later action.
— **Fallback:** no action follows automatically.

[REQ-B2-8] **Templates preserve the real disposition before explicitly degrading to advisory.** GitLab CI
runs the integration command directly, always retains the result artifact, and uses `allow_failure: true`;
no pipe such as `| tee` may overwrite the command status. Argo CD runs it as `PreSync`, records stdout,
and masks non-zero status only at the explicit outer advisory boundary. Changing either template to
blocking is a separate human-owned policy change. — **Fallback:** remain non-blocking.

[REQ-B2-9] **Fixtures and templates are not live integration evidence.** A real B2 exit requires an
observed GitLab or Argo CD run bound to an immutable harness revision, an approved read-only platform
source and freshness policy, an exact proposed change, a retained result artifact, and measured
latency/catch/false-positive evidence. Local examples, ConfigMaps, fake clients, and green tests prove only portable conformance.
— **Fallback:** B2 remains incomplete.

## Portable interfaces

```text
load_change_advisory_invocation(path) -> ChangeAdvisoryInvocation
evaluate_change_advisory(ChangeAdvisoryInvocation) -> ChangeAdvisoryResult
ChangeAdvisoryResult.to_document() -> sre-harness.change-advisory-result/v1
sre-harness gate-integration --input <envelope> [--result <artifact>]
```

## Verification / acceptance probes

- **P-B2-1 closed-envelope:** a valid v1 envelope loads; oversize, symlink, duplicate/non-finite,
  malformed, unknown/missing, and wrong-type input fails before checks.
- **P-B2-2 content-rejoin:** exact canonical revisions load; change/platform mutation, unsorted or duplicate
  lists/entities, and digest mismatch fail closed.
- **P-B2-3 source-context:** only bounded invocation ids, the two explicit sources, canonical UTC, and a
  non-future platform snapshot no more than five minutes old are accepted; none proves a real run.
- **P-B2-4 deterministic-authority:** the same snapshot worlds produce exact registered-check `proceed`,
  `block`, and `require_human` results with unchanged aggregation.
- **P-B2-5 result-rejoin:** the v1 result repeats exact invocation/as-of/digest/revisions, every check result,
  T1/T2, `advisory: true`, and `mutationAuthorized: false` with no action surface.
- **P-B2-6 distinct-exits:** valid worlds return `0`/`10`/`20`; missing, invalid, or unwritable input/output
  returns `64`, and valid non-zero results are still written before exit.
- **P-B2-7 no-action-surface:** trap deploy/sync/write methods are absent and never invoked.
- **P-B2-8 template-status:** GitLab has no status-masking pipe and retains the result with
  `allow_failure: true`; Argo CD masks only after the direct integration command at `PreSync`.
- **P-B2-9 evidence-scope:** docs and status retain the fixture/template boundary until an observed,
  immutable real integration artifact and measurements exist.

## Current evidence and blockers

The deterministic multi-check gate, legacy CLI, strict v1 integration envelope/result, content revision
rejoin, immutable invocation/result contracts, distinct dispositions, bounded file/result handling, and
non-blocking GitLab/Argo template probes exist in the dirty local worktree. The templates consume the
committed static envelope fixture; no approved live platform adapter, immutable harness publication, or
observed consumer run is bound.

The closed local
[`SPEC-B2` portable traceability manifest](../../solutions/sre-harness/spec-traceability/SPEC-B2.json)
binds this exact SPEC digest and all nine probe ids to existing pytest nodes plus bounded implementation
paths. The portfolio checker parses those test files with the Python AST and rejects a stale source
digest, missing/extra probe, missing test node, path escape, symlink, malformed shape, or authority/evidence
overclaim. The manifest is a static local traceability index, not a stored test result, observed consumer
artifact, live evidence receipt, or authority grant; its referenced tests must still pass in the declared
Python 3.11+ environment.

B2 remains incomplete until a human-selected consumer wires one approved read-only platform source and
exact change producer, accepts or revises the candidate freshness ceiling, retains an immutable real-run result, and measures latency, catches, false
positives, and override behavior. No local artifact may clear that gate.
