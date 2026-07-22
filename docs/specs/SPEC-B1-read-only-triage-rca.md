# SPEC-B1 — Read-only incident triage and RCA drafting

**Specification type:** Capability SPEC  
**Status:** Draft / construction  
**Owner:** `genai-enablement` Autonomous SRE harness  
**Governing decisions:** [ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md) and the
[Autonomous SRE harness plan](../autonomous-sre-harness-plan.md)  
**Roadmap gate:** `B1`  
**Depends on:** SPEC-B0 offline evaluation harness  
**Evidence scope:** `local-portable-only`  
**Operational state:** `incomplete`  
**Next gate:** `approved-sources-analyzer-and-real-corpus`  
**Authority:** `non-authorizing`; maximum autonomy tier `T1`, with no action or mutation authority

## Intent and boundary

As an on-call engineer, I need a replayable incident snapshot transformed into a reviewable RCA draft so
that facts, inferences, confidence, and evidence provenance are visible before any human decides whether
to act.

SPEC-B1 owns the portable read-only snapshot, gather, analyze, draft, provenance, and evaluation
contracts. It does not own alert-provider administration, production credentials, remediation,
deployment, incident-command decisions, or approval. Its maximum authority is autonomy tier `T1`.

**Inputs:** a bounded immutable incident snapshot from an explicitly configured read-only source; an
approved analyzer implementing the one-method read-only port; curated offline ground truth.  
**Outputs:** an action-free RCA draft and AgentOps/eval evidence.  
**Out:** write/action tools, remediation recommendations/execution, mutation credentials, live provider
selection, model approval, production thresholds, paging policy, and pilot acceptance.

## Requirements

[REQ-B1-1] **Snapshot ingestion is closed, bounded, and fail-closed.** The portable JSON envelope uses
schema version `sre-harness.incident-snapshot/v1` and contains only `schemaVersion`, `alert`,
`capturedAt`, and `evidence`. Alert and evidence objects also reject unknown/missing fields. A local file
source accepts only a regular non-symlink UTF-8 file no larger than 1 MiB, rejects duplicate keys,
non-finite numbers, malformed JSON, wrong primitive types, unknown enum values, and more than 128 evidence
items. — **Fallback:** no snapshot is issued and no analyzer runs.

[REQ-B1-2] **The temporal boundary is exact UTC.** Alert start, capture time, and every observation are
timezone-aware UTC. Capture cannot precede the alert; evidence cannot follow capture. The source result
must rejoin the exact requested incident id and `as_of`; stale/foreign/copied results are rejected rather
than silently relabelled. — **Fallback:** fail closed before gather.

[REQ-B1-3] **The source port is read-only and minimal.** `IncidentSnapshotSource` exposes only
`snapshot(request) -> IncidentSnapshot`. The pipeline invokes no `write`, `update`, `ack`, `page`,
`execute`, or provider-admin method, even if a concrete object happens to expose one. Source exceptions
propagate as an unavailable read; they never fabricate an empty success. — **Fallback:** the caller keeps
the incident on its existing human path.

[REQ-B1-4] **Gather is service/time bounded and deterministic.** Gather admits only evidence for the
alerted service inside the configured lookback and capture boundary, caps the result at 128, and orders by
observation time plus evidence id. Foreign-service or out-of-window input cannot become analyzer context.
— **Fallback:** an empty admitted context produces an explicit unknown result.

[REQ-B1-5] **Facts, inferences, and confidence remain distinct.** Facts are cited claims; hypotheses are
separate typed inferences with finite confidence in `[0, 1]`. Every citation must rejoin an admitted
evidence id. The RCA primary cause and confidence equal its leading hypothesis. — **Fallback:** copied,
foreign, uncited, or structurally invalid analyzer output is rejected.

[REQ-B1-6] **Insufficient evidence is not converted into certainty.** With no supported causal pattern,
the result is `undetermined`; with no evidence its confidence is exactly zero and it carries no invented
citation. A deterministic fixture analyzer is only a regression oracle, not production intelligence.
— **Fallback:** unresolved questions are preserved for a human.

[REQ-B1-7] **The output has no mutation authority.** The RCA draft is `T1`, immutable, and exposes no
action, remediation, credential, approval, or execution field. Triage success cannot trigger or authorize
a T2–T4 transition. — **Fallback:** every operational decision remains outside SPEC-B1.

[REQ-B1-8] **Evaluation uses curated expected cause and provenance.** Incident replay uses the shared
`Scenario` contract and an explicit scorer. A pass requires both the expected primary cause and all
required citations in the primary hypothesis. Candidate thresholds are immutable content-addressed
policy input and cover minimum suite/cause counts, pass rate, and the unknown-confidence ceiling; meeting
them is reported separately from evidence eligibility. Every label declares `fixture` or
`curated_real` provenance. Any fixture makes the scope `fixture-only`; even locally labelled curated
cases remain only `candidate-curated`. `production_evidence_eligible` is issued only from an opaque
externally verified corpus publication capability. Its gate requires exact boolean success from an
allowlisted verifier and binds the publication origin/revision, corpus id/revision, approval identity and
revision, policy id/revision, exact scenario ids, and a canonical digest of every snapshot and causal
label. Evaluation rejoins that capability to the exact policy, ids, and manifest; missing, raw,
fabricated, copied, mutated, foreign, or join-mismatched input fails closed. Fixtures remain ineligible
even with a valid capability. Scores from fixture patterns cannot be reported as live usefulness,
false-positive, or production-quality evidence. — **Fallback:** absent thresholds, cause coverage,
calibrated unknowns, curated ground truth, or external publication leaves B1 incomplete.

[REQ-B1-9] **AgentOps records the pipeline without inventing model usage.** One `triage.run` span parents
bounded gather/analyze/draft spans and records incident, service, admitted-evidence count, primary cause,
confidence, and T1. Token/model/cost attributes appear only when an approved model adapter supplies real
usage. — **Fallback:** deterministic analysis emits no model telemetry.

## Portable interfaces

```text
IncidentSnapshotSource.snapshot(SnapshotRequest) -> IncidentSnapshot
gather_context(IncidentSnapshot, lookback, max_items) -> GatheredContext
ReadOnlyAnalyzer.analyze(GatheredContext) -> AnalysisDraft
draft_rca(GatheredContext, AnalysisDraft) -> RcaDraft
run_triage_from_source(SnapshotRequest, IncidentSnapshotSource, ReadOnlyAnalyzer?) -> RcaDraft
evaluate_triage_suite(Scenario[], Target, TriageEvalPolicy?) -> TriageEvalReport
TriageCorpusPublicationGate.evaluate() -> TriageCorpusPublicationDecision
```

## Verification / acceptance probes

- **P-B1-1 closed-json:** valid v1 JSON loads; unknown/missing fields, duplicates, non-finite values,
  invalid UTF-8, oversize content, symlinks, non-files, wrong types/enums, and 129 evidence items fail.
- **P-B1-2 exact-time:** naive/non-UTC, capture-before-alert, future evidence, wrong incident, or wrong
  `as_of` fails before analysis.
- **P-B1-3 read-only-source:** a source exposing a trap `write/execute` method proves that only
  `snapshot()` is called; an exception or non-exact result fails rather than degrading to fabricated data.
- **P-B1-4 bounded-gather:** foreign/out-of-window evidence is excluded; stable ordering and the cap hold.
- **P-B1-5 citation-rejoin:** analyzer citation outside gathered evidence and invalid confidence fail.
- **P-B1-6 honest-unknown:** empty/unsupported context produces `undetermined`, zero/low confidence, and
  unresolved questions without invented evidence.
- **P-B1-7 no-action-surface:** the report is T1 and has no action/remediation/execution field.
- **P-B1-8 replay-score:** deployment, saturation, and unknown fixtures require exact cause and citations;
  a perfect fixture suite may be threshold-conformant but remains `fixture-only` and production-ineligible.
  Missing/unmet thresholds, duplicate ids, incomplete cause coverage, low pass rate, or overconfident
  unknowns fail conformance. Raw/fabricated/mutated publications, truthy verifier substitutes, foreign
  origins/verifiers, and policy/id/manifest mismatches cannot issue eligibility. A hypothetical exact
  allowlisted verifier can issue the opaque capability for an exactly rejoined `curated_real` corpus,
  while the same capability still cannot promote fixture labels.
- **P-B1-9 tracing:** parent/child spans contain real provenance and deterministic paths contain no
  fabricated LLM usage.

## Current evidence and blockers

The portable gather/analyze/draft, citation, honest-unknown, replay scoring/admission, tracing, and closed
JSON/source mechanisms exist in the dirty local worktree. The source accepts only the exact v1 bounded
file envelope, and the orchestrator rejoins incident id plus `as_of` while invoking only `snapshot()`.
The candidate eval policy separates threshold conformance from evidence scope. The portable publication
gate, process-local sealed capability, canonical corpus manifest, and exact policy/scenario rejoin exist;
their positive probe uses only a deterministic verifier test double. The current worktree configures no
external publication, and the committed example and seed corpus remain local fixtures, so current
production eligibility is false. None of this is live-provider or externally verified corpus evidence.

The closed local
[`SPEC-B1` portable traceability manifest](../../solutions/sre-harness/spec-traceability/SPEC-B1.json)
binds this exact SPEC digest and all nine probe ids to existing pytest nodes plus bounded implementation
paths. The portfolio checker parses those test files with the Python AST and rejects a stale source
digest, missing/extra probe, missing test node, path escape, symlink, malformed shape, or authority/evidence
overclaim. The manifest is a static local traceability index, not a stored test result, external
publication, live evidence receipt, or authority grant; its referenced tests must still pass in the
declared Python 3.11+ environment.

B1 remains incomplete until humans select and approve the provider/source set and analyzer, provision
read-only credentials outside the model, curate a representative real-incident corpus, publish regression
and stop thresholds, measure usefulness/false positives, and select a pilot under Track C. No fixture,
local file, test double, or agent-authored value may clear those gates.
