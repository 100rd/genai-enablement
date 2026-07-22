# SPEC-B7-CORE — Sentinel portable core

**Specification type:** Capability SPEC  
**Status:** Draft / portable construction  
**Owner:** `genai-enablement` Autonomous SRE harness  
**Governing decisions:** [ADR-0001](../decisions/0001-continuous-detection-sentinel.md),
[ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md), and the
[Autonomous SRE harness plan](../autonomous-sre-harness-plan.md)  
**Roadmap gate:** `B7`  
**Depends on:** SPEC-B0 offline evaluation harness  
**Evidence scope:** `local-portable-only`  
**Operational state:** `incomplete`  
**Next gate:** `human-runtime-source-and-operations-policy`  
**Authority:** `non-authorizing`; detection T1 and findings T2 advisory, with no execution authority

## Goal and boundary

Define the common portable contract used by every Sentinel detector: immutable state and findings, a
pure detector registry, deterministic deduplication/ranking, explicit read-only sources, bounded JSON
serialization, optional durable open-finding state, advisory CLI behavior, and AgentOps telemetry.

The core does not select production sources, schedule a runtime, define detector-family policy, deliver
alerts, acknowledge incidents, execute remediation, or authorize a downstream action.

## Requirements

[REQ-B7CORE-1] **Findings are immutable, bounded advisory facts.** A finding carries detector id, kind,
severity, confidence in `[0, 1]`, a non-blank fingerprint, rationale, bounded evidence, and an optional
runbook suggestion. Its dedup key is detector/kind/fingerprint and its rank is deterministic
`severity × confidence`. — **Fallback:** malformed findings fail before reporting.

[REQ-B7CORE-2] **State enters through one read-only snapshot port.** `StateSource` exposes only
`snapshot() -> SentinelState`; static and strict JSON-file adapters implement the same port. An absent,
invalid, non-object, or structurally invalid snapshot is an error, not an empty success. — **Fallback:**
the existing human/monitoring path remains authoritative.

[REQ-B7CORE-3] **Scanning is pure, deterministic, deduplicated, and ranked.** `run_sentinel` evaluates the
registered detector sequence over one immutable snapshot, collapses duplicate keys to the higher-ranked
finding, suppresses already-open findings, and sorts fresh and suppressed findings by rank. A custom
detector list is explicit input. — **Fallback:** no detector output is reinterpreted as an action.

[REQ-B7CORE-4] **Open-finding state is explicit and retry-safe.** A store loads and atomically replaces one
closed open-finding set; an absent file means no prior findings, while malformed state fails. Successful
scans persist the currently reproduced set so repeated findings suppress and resolved findings drop.
File permissions are restrictive and failed replacement does not corrupt the prior file. — **Fallback:**
store failure returns an integration error without claiming persistence.

[REQ-B7CORE-5] **JSON and CLI boundaries fail closed and preserve advisory meaning.** Regular bounded
UTF-8 JSON rejects symlinks, special files, duplicate keys, non-finite values, deep/oversize content,
concurrent mutation, unknown fields, and wrong types. `sentinel scan` emits a closed JSON report; exit
`0` means no fresh findings, `1` means fresh advisory findings, and input/store errors are distinct.
Neither exit is a remediation command or deployment gate. — **Fallback:** invalid input never becomes a
clean scan.

[REQ-B7CORE-6] **Telemetry is descriptive and optional.** One `sentinel.scan` span parents one
`sentinel.detector` span per registered detector and records detector/finding/suppression counts and the
T1/T2 boundary. With no provider, scanning is behaviorally unchanged and no exporter is invented.
— **Fallback:** no-op tracing.

[REQ-B7CORE-7] **The core exposes no operational action surface.** Source, detector, scan, store, and CLI
contracts contain no deploy, reconcile, acknowledge, silence, rollback, approve, credential, or execute
operation. Suggested runbooks are text references only. — **Fallback:** a human or separately governed
capability owns every action.

[REQ-B7CORE-8] **Portable conformance is not runtime qualification.** Exit requires human-owned source
schemas and freshness/coverage/order policy, read-only identity, schedule/HA and cost budgets, delivery
and acknowledgement semantics, durable-store ownership/retention, disable/rollback procedure, and
observed clean/incident operation bound to an immutable release. — **Fallback:** B7 runtime remains
operationally incomplete.

## Portable interfaces

```text
StateSource.snapshot() -> SentinelState
Detector(SentinelState) -> Finding[]
run_sentinel(state, detectors, open_findings) -> SentinelReport
FindingStore.load() -> Finding[]
FindingStore.save(Finding[]) -> None
sre-harness sentinel scan --state <snapshot> [--open-findings <state>] [--verbose]
```

## Verification matrix

- **P-B7CORE-1 finding-contract:** severity ordering, rank, dedup identity, confidence, fingerprint,
  optional runbook, and immutability are exact.
- **P-B7CORE-2 read-only-source:** static/file sources satisfy the one-method protocol; valid snapshots
  load and missing/malformed/invalid snapshots fail.
- **P-B7CORE-3 scan:** empty, ranked, suppressed, duplicate, custom-detector, and specificity cases are
  deterministic.
- **P-B7CORE-4 store:** memory/file stores replace, clear, round-trip, restrict permissions, reject bad
  state, and preserve the prior file on failed atomic write.
- **P-B7CORE-5 CLI-boundary:** clean/fresh findings have distinct advisory exits and stable report
  fields; source/store errors are clean failures without tracebacks.
- **P-B7CORE-6 tracing:** scan/detector parentage and counts are recorded; the no-provider path is inert.
- **P-B7CORE-7 no-action-surface:** report tiers remain T1/T2 and persisted findings remain observations,
  not execution commands.
- **P-B7CORE-8 evidence-boundary:** docs and status retain the local-only, non-authorizing,
  operationally incomplete runtime boundary.

## Exit evidence

The closed local
[`SPEC-B7-CORE` portable traceability manifest](../../solutions/sre-harness/spec-traceability/SPEC-B7-CORE.json)
binds this exact Draft digest and all eight probes to existing Sentinel core tests and implementation
paths. It stores no scan PASS and supplies no source, schedule, delivery, credential, or action authority.

B7 core remains operationally incomplete until REQ-B7CORE-8 evidence exists.
