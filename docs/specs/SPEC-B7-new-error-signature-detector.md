# SPEC-B7-NES — New-error-signature Sentinel detector

**Specification type:** Capability SPEC
**Status:** Draft / portable construction
**Owner:** `genai-enablement` Autonomous SRE harness
**Governing decisions:** [ADR-0001](../decisions/0001-continuous-detection-sentinel.md),
[ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md), and the
[Autonomous SRE harness plan](../autonomous-sre-harness-plan.md)
**Roadmap gate:** `B7`
**Depends on:** SPEC-B0 offline evaluation harness, SPEC-B7-CORE Sentinel portable core
**Evidence scope:** `local-portable-only`
**Operational state:** `incomplete`
**Next gate:** `human-policy-source-and-live-calibration`
**Authority:** `non-authorizing`; detection T1 and finding T2 advisory, with no remediation authority

## Goal and boundary

Formalize ADR-0001 catalog item 2: surface an already normalized error signature that is present in the
current window and absent from the same service's baseline window. The deterministic core compares
identities only. It does not ingest raw logs, derive or cluster signatures, name an incident class,
choose a baseline, schedule a scan, deliver an alert, or execute a response.

## Requirements

[REQ-B7N-1] **Input is an immutable normalized per-service window.** Each signal contains one service plus
baseline and current sets of precomputed signature identities. Raw log lines, stack traces, request
bodies, user data, credentials, and model output do not belong in this contract. — **Fallback:** absent
signals stay silent.

[REQ-B7N-2] **The portable JSON boundary is closed and fail-closed.** The shared Sentinel loader admits
only the declared `error_windows` array and exact service/baseline/current fields, with bounded regular
UTF-8 JSON, unique set members, and no unknown or malformed shapes. — **Fallback:** reject the snapshot
instead of treating malformed evidence as clean.

[REQ-B7N-3] **Novelty is exact set difference, never volume.** The candidate rule is
`current - baseline`; a signature already in the service baseline is silent regardless of occurrence
count, while every distinct newly present identity is eligible. — **Fallback:** no baseline-independent
global ERROR threshold.

[REQ-B7N-4] **Identity, ordering, and service scope are deterministic.** Findings are emitted in sorted
signature order and fingerprinted by exact service plus signature, so the same identity on another
service does not inherit baseline or dedup state. — **Fallback:** ambiguous service/signature identity is
not emitted.

[REQ-B7N-5] **Output is bounded advisory evidence.** Each novel identity emits one `HIGH`,
confidence-`1.0` finding with detector `new_error_signature`, kind `new_error_signature`, bounded counts
and signature identity, and the `triage-new-error-signature` suggestion. It contains no raw content or
action field. — **Fallback:** T2 advice only.

[REQ-B7N-6] **Registry and dedup use the common Sentinel core.** The detector is an explicit member of
`DEFAULT_DETECTORS`; common scan ranking and open-finding suppression apply without detector-specific
write behavior. — **Fallback:** an unregistered detector cannot appear in default scans.

[REQ-B7N-7] **Evaluation proves early surfacing and clean silence on fixtures.** The seed incident first
introduces a novel identity before the page; clean windows with only baseline-known identities remain
silent and contribute to explicit false-positive metrics. — **Fallback:** late/missing detection or a
clean fire fails the replay.

[REQ-B7N-8] **Normalization and model clustering remain externally gated.** Live exit requires a
human-owned signature normalization/version policy, immutable source/baseline windows, privacy and
retention rules, curated real incident/clean labels, accepted noise/cost thresholds, read-only identity,
and observed calibration. The ADR's optional cheap-model clustering/naming step requires its own governed
SPEC and evidence; this deterministic SPEC cannot silently enable it. — **Fallback:** B7-NES remains
operationally incomplete.

## Portable interfaces

```text
ErrorSignatureWindow{service, baseline, current}
detect_new_error_signature(SentinelState) -> Finding[]
```

## Verification matrix

- **P-B7N-1 normalized-input:** state holds immutable per-service signature sets and defaults the signal
  collection empty.
- **P-B7N-2 strict-json:** exact windows parse; missing/null/wrong collections, non-object rows, and
  malformed bounded JSON fail.
- **P-B7N-3 set-difference:** baseline-known identities remain silent and new identities surface.
- **P-B7N-4 stable-identity:** multiple novel identities sort and the same identity remains
  service-scoped.
- **P-B7N-5 advisory-finding:** detector/kind/severity/confidence/fingerprint/evidence/runbook fields are
  exact and contain no execution surface.
- **P-B7N-6 registry-dedup:** the five-entry default registry contains the detector and common dedup keys
  keep detector families distinct.
- **P-B7N-7 replay-metrics:** the new-signature incident has positive lead and clean scenarios remain
  included in explicit early-detection/false-positive totals.
- **P-B7N-8 evidence-boundary:** docs and status retain the deterministic-fixture, no-clustering,
  non-authorizing, operationally incomplete boundary.

## Exit evidence

The closed local
[`SPEC-B7-NES` portable traceability manifest](../../solutions/sre-harness/spec-traceability/SPEC-B7-NES.json)
binds this exact Draft digest and all eight probes to existing state, serialization, detector, scan, and
lead-time tests. It stores no PASS result and grants no source, normalization, model, delivery, or action
authority.

B7-NES remains operationally incomplete until REQ-B7N-8 evidence exists.
