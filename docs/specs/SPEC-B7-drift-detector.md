# SPEC-B7-DRIFT — Config↔state drift Sentinel detector

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
**Authority:** `non-authorizing`; detection T1 and finding T2, with no reconciliation or action authority

## Goal and boundary

Add the remaining deterministic ADR-0001 catalog family, `drift`, only with an exact normalized
config↔observed-state fact, a convergence grace period, persistent-mismatch evidence, positive replay
lead-time, and deliberately messy clean worlds. The detector evaluates digests and metadata supplied in a
snapshot; it never reads, stores, compares, or emits raw manifests, configuration values, Secret data, or
diff content.

This slice owns one immutable fixture signal, deterministic rule, strict JSON ingestion, stable dedup
identity, registry admission, and replay labels. It does not own Omniscience drift materialization, desired
state authority, controller reconciliation semantics, source freshness/completeness, runtime scheduling,
delivery, acknowledgement, reconciliation, rollback, remediation, or deployment.

## User journey

**As the on-call owner**, I want Sentinel to surface a tracked resource that remains different from its
declared desired revision after a bounded convergence window, while ignoring normal rollout convergence
and one-off observation noise, so I receive an early advisory without exposing configuration contents or
creating a second reconciler.

## Candidate rule

For one exact tracked resource observation:

```text
is_mismatch = observed_revision is absent or observed_revision != desired_revision
drift_age   = observed_at - mismatch_started_at

candidate = is_mismatch
            and consecutive_mismatches >= 2
            and drift_age >= 300 seconds
```

A qualifying digest mismatch is MEDIUM severity. It becomes HIGH when the observed resource is absent or
the mismatch has persisted for at least 3,600 seconds. Matching desired/observed revisions must carry no
mismatch start and a zero mismatch count. These constants are construction candidates protected by
fixture replay, not accepted production policy.

## Requirements

[REQ-B7D-1] **The normalized drift signal is exact, immutable, bounded, and internally consistent.**
`DriftObservation` binds safe bounded resource kind/id text, canonical lowercase SHA-256 tracking-policy
and desired revisions, an optional canonical observed revision, exact bounded desired-recorded/observed
UTC epoch seconds, an optional mismatch-start epoch, and an exact bounded consecutive-mismatch count.
Matching revisions require `mismatch_started_at is None` and count zero. A differing or absent observed
revision requires `desired_recorded_at <= mismatch_started_at <= observed_at` and count at least one.
Booleans, coercion, malformed revisions/text/times/counts, impossible state, overflow, and mutation fail
before detector execution. — **Fallback:** reject invalid state; emit nothing.

[REQ-B7D-2] **JSON ingestion is typed, closed, and bounded.** `drift_observations` accepts at most 1,000
rows through exact field extraction, including explicit nullable `observed_revision` and
`mismatch_started_at`; it never uses `**kwargs` or string/numeric coercion. It inherits the shared regular
non-symlink, non-blocking, stable-read, strict UTF-8 JSON-object boundary of at most 1 MiB, including
duplicate-key and non-finite-number rejection. Missing keys, wrong nullability/type, extra fields,
over-limit arrays, and malformed rows reject the complete snapshot. — **Fallback:** no partial state or
finding.

[REQ-B7D-3] **Detection requires persistence beyond normal convergence.** A mismatch qualifies only at
two or more consecutive observations and age at least 300 seconds. One observation, a 299-second mismatch,
a resource that converges before the boundary, or a desired-revision change whose mismatch evidence has
reset stays silent. The detector reads no clock and infers no history beyond the supplied exact fact. —
**Fallback:** await a later normalized snapshot.

[REQ-B7D-4] **Detection compares exact desired and observed state without raw content.** Equal revisions
stay silent. A qualifying unequal revision emits a digest-mismatch advisory; a qualifying absent observed
revision emits a missing-resource advisory. The rule does not compare text manifests, perform fuzzy
matching, infer semantic equivalence, or treat controller status strings as authority. — **Fallback:** an
ambiguous/unmaterialized state is not represented as a valid signal.

[REQ-B7D-5] **Output is deterministic, bounded, non-sensitive, and epistemically honest.** One qualifying
observation emits one `config_state_drift` finding with detector id `config_state_drift`, stable
`resource_kind:resource_id` fingerprint, MEDIUM/HIGH candidate severity, fixed confidence, exact bounded
revision/time/count evidence, and `triage-config-state-drift` suggestion. Rationale says “differs from” or
“is absent from observed state”; it never claims cause or remediation. Evidence excludes manifests,
configuration/diff values, Secret data, credentials, URLs, user identities, model text, and provider
errors. Input order controls output order. — **Fallback:** invalid input cannot construct a finding.

[REQ-B7D-6] **Repeat scans use stable existing dedup semantics.** The fingerprint excludes current time and
observed revision so the same tracked-resource condition is suppressed while open, even if the observed
digest changes. A different resource remains independent. Within-scan duplicate keys retain only the
higher-ranked finding under the existing scan contract. — **Fallback:** do not create an alert stream for
one persistent resource.

[REQ-B7D-7] **The detector remains T1/T2 and action-free.** It is a pure registered function with no
network, filesystem, clock read, model, acknowledgement, send, controller refresh/sync, patch/apply,
runbook execution, rollback, remediation, issue, pipeline, merge, or close surface. Supplied revisions and
epochs are facts, not fetched or inferred by the detector. — **Fallback:** humans and separately authorized
deterministic gates decide any response.

[REQ-B7D-8] **Registry admission requires positive replay lead-time.** A fixture timeline begins converged,
introduces one desired revision while observed state remains on the prior revision, crosses the exact
persistence boundary at least one snapshot before the labelled page, and expects the exact detector/kind.
The eval records first fire and positive lead. — **Fallback:** late or missing detection fails the suite.

[REQ-B7D-9] **False-positive evidence covers convergence and incomplete persistence.** The fixture corpus
contains at least five detector-specific clean timelines: exact convergence, a single mismatch
observation, a repeated mismatch still inside grace, an absent observation inside grace, and a desired
revision update that resets mismatch evidence. All remain silent; aggregate eval reports explicit clean
count and zero false positives/rate. — **Fallback:** any clean fire blocks registry admission.

[REQ-B7D-10] **Portable digest comparison is not live drift evidence.** Live exit additionally requires a
human-owned versioned tracked-resource/desired-state policy, immutable config-to-runtime identity, an
approved normalization/digest algorithm, exact Omniscience schema and source binding, source
ordering/freshness/coverage/liveness, controller convergence and deletion semantics, clock-skew policy,
real incident/clean calibration, observed lead-time and false-positive confidence intervals, noise/cost
budgets, read-only source identity, delivery/dedup retention, and a disable owner. — **Fallback:** label
constants and results fixture-only; make no live coverage, reconciliation, or usefulness claim.

## Portable interfaces

```text
DriftObservation(resource_kind, resource_id, tracking_policy_revision,
                 desired_revision, observed_revision, desired_recorded_at,
                 mismatch_started_at, observed_at, consecutive_mismatches)
detect_config_state_drift(state) -> list[Finding]
state_from_dict({"drift_observations": [...]}) -> SentinelState
run_sentinel_eval(scenarios, detectors) -> SentinelEvalSummary
```

## Verification matrix

- **P-B7D-1 exact-signal:** valid converged/mismatch/missing frozen states construct; unsafe/coerced text,
  malformed revisions, invalid nullable combinations, time/count bounds, impossible ordering, and
  mutation reject.
- **P-B7D-2 input-boundary:** typed round trip; missing/extra/wrong-nullability/wrong-type/over-1,000 rows
  and inherited shared file attacks reject the whole state.
- **P-B7D-3 persistence:** exact two-observation/300-second boundary fires; one observation and 299 seconds
  stay silent; convergence/reset timelines remain silent.
- **P-B7D-4 comparison:** equal revisions stay silent; persistent unequal and absent observations fire
  their exact honest rationale branch.
- **P-B7D-5 finding:** MEDIUM/HIGH boundaries, confidence, stable fingerprint, bounded evidence, runbook,
  wording, ordering, and absence of raw/sensitive fields are exact.
- **P-B7D-6 dedup:** repeat open condition suppresses despite observed-revision drift; another resource
  remains fresh; higher-ranked same-key duplicate wins.
- **P-B7D-7 authority:** registry includes the pure detector; source contains no action capability.
- **P-B7D-8 lead-time:** labelled persistent drift first fires before the page with expected detector/kind.
- **P-B7D-9 false-positive:** five named clean controls stay silent and aggregate false-positive rate is
  exactly zero.
- **P-B7D-10 evidence-scope:** docs/status distinguish normalized fixtures from live Omniscience/source/
  policy/runtime evidence and never claim reconciliation authority.

The closed local `solutions/sre-harness/spec-traceability/SPEC-B7-DRIFT.json` manifest binds this exact
Draft digest and P-B7D-1..10 to existing pytest nodes and the bounded Sentinel implementation paths. It
is static `local-portable-only`, operationally `incomplete`, and `non-authorizing`; it stores no PASS
result and grants no reconciliation, live Omniscience/source, runtime, delivery, or remediation authority.

## Exit evidence

The portable increment is conformant only when P-B7D-1..10 pass with at least 80% branch coverage for the
affected Sentinel surface and the complete harness remains green. Live operation remains incomplete until
REQ-B7D-10 is satisfied. Fixture inputs cannot publish desired-state authority, prove source completeness,
schedule a runtime, deliver alerts, reconcile resources, or authorize actions.
