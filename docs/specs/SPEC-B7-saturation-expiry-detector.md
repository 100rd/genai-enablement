# SPEC-B7-SAT — Saturation and expiry Sentinel detector

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
**Authority:** `non-authorizing`; detection T1 and findings T2 advisory, with no remediation authority

## Goal and boundary

Formalize ADR-0001 catalog item 5: surface observed or projected resource exhaustion and already expired
or near-expiry items from explicit normalized snapshot facts. The deterministic portable candidate does
not query providers, infer capacity units or sampling cadence, renew a certificate/token, resize a
resource, schedule a scan, deliver an alert, or execute the suggested runbook.

## Requirements

[REQ-B7S-1] **Inputs are immutable normalized facts.** A saturation sample binds resource/kind, used and
positive capacity in the same unit, optional cluster, and growth per interval. An expiry item binds
name/kind and integral days remaining, including zero/negative for already expired. — **Fallback:** absent
signal collections stay silent.

[REQ-B7S-2] **The portable JSON boundary is closed and fail-closed.** The shared loader admits only exact
declared saturation/expiry arrays and fields from bounded regular UTF-8 JSON; missing/null/wrong shapes,
non-numeric values, non-integral expiry, and non-positive capacity fail. — **Fallback:** reject the
snapshot instead of fabricating a clean state.

[REQ-B7S-3] **Observed saturation bands are deterministic candidate policy.** Utilization is
`used / capacity`; at least `90%` emits `CRITICAL`, at least `75%` emits `MEDIUM`, and a lower stable
sample is silent. These constants are fixtures until a human publishes resource-specific live policy.
— **Fallback:** no global policy claim.

[REQ-B7S-4] **Projection is bounded and visibly less certain.** Positive growth that reaches capacity
within six supplied sampling intervals emits `HIGH` at confidence `0.7`; no/slow growth below the warning
band stays silent. The detector does not infer interval duration or perform an unbounded forecast.
— **Fallback:** observed facts only.

[REQ-B7S-5] **Expiry bands are deterministic candidate policy.** Already expired emits `CRITICAL`;
`1..7` days emits `HIGH`; `8..30` emits `MEDIUM`; farther expiry is silent. The signal is a remaining-days
fact, not a credential or secret value. — **Fallback:** no renewal action.

[REQ-B7S-6] **Findings are stable, bounded, and advisory.** Saturation uses cluster/resource identity when
available and includes normalized utilization/growth facts; expiry uses kind/name identity and remaining
days. Suggested `scale-or-provision-*` / `rotate-*` runbooks are references only. — **Fallback:** T2
advice with no execution.

[REQ-B7S-7] **Registry and dedup use the common Sentinel core.** One `saturation_expiry` detector is an
explicit default-registry member and may emit either saturation or expiry kinds; detector/kind/fingerprint
keeps unrelated conditions distinct while already-open conditions suppress. — **Fallback:** no hidden
runtime registration.

[REQ-B7S-8] **Evaluation covers early warning and clean silence.** Disk ramp and certificate countdown
fixtures fire before their page points; healthy disk, slow growth, and far-future expiry controls remain
silent and contribute to explicit lead-time/false-positive totals. — **Fallback:** late/missing detection
or a clean fire fails replay.

[REQ-B7S-9] **Live policy and source qualification remain external.** Operational exit requires
human-owned resource/expiry inventory, sampling cadence and units, thresholds/horizons, capacity and
expiry source freshness/coverage, read-only identity, curated real incident/clean calibration,
noise/cost budgets, delivery/ack/disable semantics, and observed operation. — **Fallback:** B7-SAT
remains operationally incomplete.

## Portable interfaces

```text
SaturationSample{resource, kind, used, capacity, cluster?, growth_per_interval}
ExpiryItem{name, kind, expires_in_days}
detect_saturation_expiry(SentinelState) -> Finding[]
```

## Verification matrix

- **P-B7S-1 normalized-input:** utilization is exact, capacity must be positive, records are immutable,
  and empty state is silent.
- **P-B7S-2 strict-json:** exact samples/items parse; missing/null/wrong/non-numeric/non-integral fields,
  wrong arrays, and malformed bounded JSON fail.
- **P-B7S-3 observed-bands:** healthy, warning, and critical utilization map to silence, `MEDIUM`, and
  `CRITICAL` at their exact boundaries.
- **P-B7S-4 projection:** bounded positive growth reaching capacity emits `HIGH/0.7`; slow growth stays
  silent.
- **P-B7S-5 expiry-bands:** expired, critical-window, warning-window, and far-future items map to exact
  severity/silence behavior.
- **P-B7S-6 finding-shape:** resource/cluster and expiry identities, evidence, confidence, and runbook
  suggestions are deterministic and action-free.
- **P-B7S-7 registry-dedup:** the five-entry default registry contains the detector and common open-set
  suppression keeps repeat conditions advisory.
- **P-B7S-8 replay-metrics:** disk and certificate incidents have positive lead, clean controls remain
  silent, and aggregate early-detection/false-positive values remain explicit.
- **P-B7S-9 evidence-boundary:** docs and status retain candidate thresholds, no live source/action,
  non-authorizing scope, and operational incompleteness.

## Exit evidence

The closed local
[`SPEC-B7-SAT` portable traceability manifest](../../solutions/sre-harness/spec-traceability/SPEC-B7-SAT.json)
binds this exact Draft digest and all nine probes to existing state, serialization, detector, scan, and
lead-time tests. It stores no PASS result and grants no source, threshold, delivery, credential, renewal,
resize, or remediation authority.

B7-SAT remains operationally incomplete until REQ-B7S-9 evidence exists.
