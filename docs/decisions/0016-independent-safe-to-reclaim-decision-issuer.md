# ADR-0016: Safe-to-reclaim decisions use an independent signed issuer

- **Status:** Proposed
- **Date:** 2026-07-14
- **Last reviewed:** 2026-07-16
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `omnius`, `platform-design`)
- **Builds on:** [ADR-0006](0006-unified-loop-decision-model.md),
  [ADR-0012](0012-capability-readiness-profiles.md),
  [ADR-0013](0013-platform-owned-observer-access.md), and
  [ADR-0015](0015-independent-observer-authority-attestor.md)

## Context

Observer-access cleanup revokes a live lease and deletes Kubernetes authorization objects. A cleanup
executor, orphan reaper, caller-provided boolean, or locally constructed `verified: true` value cannot
be allowed to authorize that destructive work. A signature is also insufficient when it covers only a
coarse `terminal` label: the same value could be replayed against another cluster, cleanup plan,
executor, or later state epoch, and a new compensation/reconciliation hold could race the delete.

The first production contract therefore needs two separate properties:

1. a Conductor-owned, strongly consistent decision over exact durable WorkOrder state and effect holds;
2. an independently verifiable signature and active reclaim reservation bound to the one cleanup target.

As of 2026-07-16, Omnius has dirty/local candidate code under proposed ADR-0022 and draft SPEC-DO.
Its pure verifier checks a signed decision against caller-supplied `SafeToReclaimContext` state and
digest. Its deterministic fixture creates a generic `terminal` digest from WorkOrder ID plus that label;
the kind cleanup test obtains the decision from this fixture, fakes lease revocation, and performs
Kubernetes cleanup with an admin kubeconfig. It does not call a durable Conductor issuer or prove a
production identity, reservation, state epoch, executor/target binding, or KMS boundary.

Two current Omnius seams disagree on absence and expiry. The legacy in-memory
`mvp_core.conductor.safe_to_reclaim()` returns true when a workflow record is missing and includes
`EXPIRED`; `DurableTaskPlane.safe_to_reclaim()` raises for a missing record and admits only `DONE` or
`ABORTED`. Draft SPEC-CD still lists `EXPIRED`. A timer-fired `EXPIRED` state is not proof that rollback
and compensation finished, so this decision selects the narrower durable behavior and records the
legacy/SPEC behavior as an adoption gap.

The local `platform-design` checkout at `c606fdb...` does not materialize the cleanup bundle. Historical
candidate commits `6b45293a...` and `1243d374...` contain a proposed cleanup schema, but no closed
production reclaim-issuer profile. That schema admits only `terminal|absent`, a caller-facing state
digest, and an issuer assertion; it does not encode the exact state projection, tombstone provenance,
target/executor binding, or reclaim reservation required below.

## Acceptance boundary

This ADR is non-binding while `Proposed`. ADR-0006 and ADR-0015 are also proposed; they cannot silently
serve as accepted authority. Accepted ADR-0013 and the currently selected readiness profile remain
authoritative until the platform owner accepts a mutually consistent exact revision set. Component
artifacts that conflict with this proposal are adoption gaps, not precedent.

Human acceptance would authorize downstream contract and implementation work. It would not accept the
Omnius component ADR/SPEC, publish a schema or platform bundle, create an issuer/profile/key, modify
Conductor state, clean Kubernetes objects, admit `standard-http-service/v3`, activate a Realm, or grant
completion, promotion, autonomous merge, or production readiness. Every such action remains separately
human-owned and exact-revision evidence-gated.

## Decision

### D1 - Conductor is the sole semantic authority and v1 admits only stable final states

The only production operation that can produce `decision: allowed` is the Conductor decision-plane
command `issue_safe_to_reclaim`. It evaluates one immutable WorkOrder/workflow binding from the
authoritative durable store; an in-memory registry, cache, replica of unknown freshness,
`terminal_workflows()` list, adapter state enum, caller state/digest, or cleanup-side query reduction is
not authority.

For a present WorkOrder, v1 allows issuance only when one serializable decision transaction proves all
of the following:

- the exact durable state is `DONE` or `ABORTED`;
- the record is not `FROZEN`, parked for human disposition, or releasable only by a human;
- no compensation, reconciliation, outbox, provider-effect, or state-transition hold is pending or
  ambiguous, except the exact registered observer-access cleanup effect being authorized;
- that cleanup effect, identity binding, cleanup plan, execution envelope, cluster/Realm target, and
  consumer identity are already registered and immutable; and
- the state/effect projection is complete under the pinned policy revision.

`EXPIRED` is a timer/rollback trigger, not a reclaimable result. It may authorize nothing until the
rollback reaches durable `ABORTED` with all non-target holds resolved. `FROZEN` remains non-reclaimable
regardless of age. Human release of FROZEN creates a new `ABORTED` state epoch and requires a new
decision; it never revives an earlier signature. Unknown state, missing fields, partial persistence,
conflicting terminal labels, or semantic-verifier failure produces no positive decision.

### D2 - Absence requires an immutable tombstone, never a failed lookup

`absent` is admissible only for a previously allocated, globally non-reusable WorkOrder ID whose
authoritative ID/WorkOrder ledger retains an immutable terminal tombstone. The tombstone binds tenant/ID
namespace, WorkOrder and internal workflow IDs, their one-to-one binding digest, last exact state and
state epoch, deletion/retention event, registered observer-access effect, identity/cleanup-plan/target
digests, and store commit index. Tombstone retention must outlive every possible observer-access object,
reaper, audit, and decision replay window.

A not-found response, cache miss, absent in-memory map entry, empty list, replica lag, timeout, partition,
store error, malformed record, purged tombstone, unknown ID namespace, or observed Kubernetes label is not
proof of absence. A never-allocated ID has no registered cleanup plan and is not auto-deleted. These cases
park and alert for human reconciliation. WorkOrder IDs and their workflow bindings cannot be reused after
tombstoning.

### D3 - Issuance atomically creates one bounded reclaim reservation

The same serializable transaction that evaluates D1 or D2 creates a unique reclaim reservation. It
binds a decision ID, unique idempotency nonce, reservation/lease ID and revision, exact
WorkOrder/workflow and state epoch, registered cleanup effect, identity-binding and cleanup-plan digests,
execution-envelope and platform-profile digests, cluster/Realm target digest, authorized cleanup/reaper
and cleanup-actuator subjects and profiles, issuer profile, `decidedAt`, and `expiresAt`. The positive
lifetime is profile-bounded and no greater than five minutes.

The reservation first commits as pending and non-authorizing under a unique
`(WorkOrder, effect, state epoch, consumer, idempotency nonce)` key. From that commit, pending and active
reservations are exclusive durable fences over the complete signed state/effect/hold/tombstone,
WorkOrder/workflow binding, cleanup-plan, target, consumer, and actuator projection. A state transition,
new compensator/effect/hold, FROZEN disposition, workflow-ID rebinding, or protected projection change
conflicts and waits; it cannot commit by revoking the reservation underneath an external mutation.
Explicit cancellation is allowed only when no cleanup step is `in_flight`, `executing`, `ambiguous`, or
otherwise unresolved, after which the state mutation must retry against a new epoch. Consumption ends
the fence only after every step is conclusive. Cancellation or reservation expiry releases the fence
only when no non-conclusive step exists; otherwise expiry merely forbids new claims and the fence remains
until the exact reconciliation rules below produce a conclusive state.

The issuer signs only the frozen pending record. In the same serializable compare-and-set transaction
that activates it, Conductor re-reads and recomputes the complete authoritative WorkOrder or tombstone,
state/effect/hold projection, state epoch, plan, target, consumer, and actuator binding. Activation
requires byte-for-byte equality with the frozen signed projection, an unchanged pending reservation, and
an unexpired decision; the transaction then persists the exact canonical decision/signature and marks
that reservation active. A mismatch cancels the pending record and makes the signature unusable. This
second authoritative join is defense in depth against an attempted concurrent change, stale or faulty
snapshot assembly, and storage/projection faults. A correct pending fence prevents a protected change
from committing during the KMS call, but never permits the activation join to be omitted.

Response-loss retry reads the same stored decision and signature bytes; it cannot create a second
reservation or silently change a time, nonce, target, or signature payload. Signing failure,
compare-and-set conflict, or an abandoned pending record leaves no usable capability and explicitly
cancels or expires the reservation. There is never an active unsigned reservation or a usable signature
for an inactive reservation. Issuance and reservation audit records are append-only. The issuer may
create/cancel only this typed reservation and cannot arbitrarily edit WorkOrder state or effect records.

### D4 - The signed decision binds state provenance and the exact cleanup authority

The closed decision contains at least:

- schema, policy, semantic-verifier, platform-bundle, and issuer-profile revisions;
- tenant/ID namespace, WorkOrder ID, internal workflow ID, and their immutable binding digest;
- execution-envelope, registered-effect, identity-binding, cleanup-plan, cluster/Realm target,
  authorized-consumer, and cleanup-actuator profile/subject digests;
- exact `DONE`, `ABORTED`, or tombstoned-absent state; state epoch, record/store revision, frozen flag,
  compensator/reconciliation/outbox/provider-effect projections and digests, plus tombstone fields when
  absent;
- canonical state-projection digest computed by the decision plane, not accepted from a caller;
- decision ID, nonce, reservation ID/revision, decision and expiry times; and
- issuer subject, signing key, algorithm, and signature metadata.

The signed state projection excludes secrets, credentials, raw provider payloads, and mutable display
labels. Generic `terminal` without the exact final state/epoch/holds, a state digest computed only from
WorkOrder ID plus a label, or an `independentFromCleanupExecutor: true` assertion without the exact
consumer binding is invalid.

The decision does not choose Kubernetes URLs or objects. It authorizes only the independently registered
cleanup-plan digest and target. The protected cleanup plan remains the source of exact paths, delete order,
UID/resourceVersion/canonical-digest preconditions, shared-object preservation, and live re-read rules.

### D5 - Issuance, signing, verification, and destructive execution are distinct identities

The production issuer subject is exactly
`system:serviceaccount:darkfactory-decision-plane:safe-to-reclaim-issuer` in the qualified cluster. Its
Pod image digest, ServiceAccount/namespace UIDs, EKS cluster identity, scheduling/network boundary,
Conductor API client identity, and profile revision are pinned. It is not the cleanup controller, orphan
reaper, worker, planner, observer, observer-authority attestor, HTTP subject/result signer, cleanup-evidence
signer, store writer, or pure verifier.

The issuer has only the typed Conductor decision/reservation API authority and append-only issuance audit
write described in D1-D3. It has no Kubernetes API credential, cleanup plan authoring, lease-revocation,
DELETE, workload/RBAC mutation, general WorkOrder-state mutation, evidence-store mutation, or human-release
authority. Cleanup and reaper identities cannot issue/reserve decisions or use the issuer signing key.

The sole production identity permitted to revoke the observer lease or mutate the registered Kubernetes
objects is exactly
`system:serviceaccount:darkfactory-cleanup:observer-access-cleanup-actuator` in the qualified target
cluster. Its image digest, ServiceAccount/namespace UIDs, cluster identity, network boundary, admitted
object kinds, fixed-path resolver, narrow RBAC, and actuator profile revision are pinned. It is a small
protected mutation gateway, distinct from the issuer, cleanup coordinator, and orphan reaper. It cannot
issue or sign a decision, author a cleanup plan, choose a target or path, create a reservation, or change
general WorkOrder state. Its only Conductor write is the typed compare-and-set result for a claimed step.

Cleanup coordinator and reaper subjects have no Kubernetes credential or RBAC that can directly revoke
the lease or DELETE protected cleanup objects. They can present a verified capability to the typed
Conductor step-claim API and send the returned opaque permit to the actuator. Conversely, the actuator
cannot claim its own step. This split makes the actuator the enforced mutation boundary rather than a
library check that a compromised coordinator can bypass.

The issuer's production AWS credentials come only from one EKS Pod Identity association bound to the exact cluster,
namespace, and ServiceAccount. The immutable profile pins association ARN/ID, IAM role ARN/account,
session-tag conditions, association/session policy, role trust policy, KMS key policy, region, and negative
proof that no other runtime identity can sign. Ambient/static credentials, node metadata, IRSA, another
association, cross-account target-role substitution, or cached credentials from an older association
revision are forbidden. Pod/credential rotation and the provider's association-cache behavior must be
qualified before a policy/association change becomes ready.

### D6 - Production KMS signing is exact and domain-separated

The dedicated customer-managed asymmetric key is distinct from every observer-attestation, HTTP,
cleanup-evidence, and other decision key. The trust profile pins the exact region-qualified KMS key ARN,
account/region, `KeySpec: ECC_NIST_EDWARDS25519`, `KeyUsage: SIGN_VERIFY`, enabled state,
`ED25519_SHA_512`, and the exact DER-encoded SPKI public-key bytes and SHA-256 digest returned by the
qualified `GetPublicKey` record. A mutable alias, ARN without the pinned public key, public key without its
exact ARN/account/region, multi-Region substitution, or ECDSA profile is invalid.

The issuer validates every D1-D4 semantic join, then computes `decisionDigest` over RFC 8785 canonical
decision content after removing exactly `issuer.signature` and `decisionDigest`. It submits exactly this
message to KMS with `SigningAlgorithm: ED25519_SHA_512` and `MessageType: RAW`:

```text
UTF8("darkfactory.observer-access-safe-to-reclaim/v1") || 0x00 ||
hex_to_bytes(decisionDigest)
```

It rejects caller-provided digests and validates that the KMS response reports the exact key ARN and
algorithm. Runtime IAM allows only `kms:Sign` on that key for the exact admitted Pod Identity session;
key administrators have no signing authority. Rotation creates a new immutable trust-profile revision.
The private key never enters Kubernetes, an image, filesystem, environment variable, or evidence.

### D7 - Verification yields an opaque capability only after an active exact join

The verifier resolves schema, policy, issuer profile, exact KMS ARN/public key, consumer profile, platform
target, and cleanup envelope from independently protected configuration. Evidence cannot nominate its own
trusted key, state context, consumer, target, or verifier. The verifier independently repeats closed-schema
validation, RFC 8785 digest calculation, standard Ed25519 verification, exact WorkOrder/workflow/state/
effect/plan/target/consumer/actuator joins, time checks, and authenticated active-reservation validation.

It returns an integrity-protected, caller-unconstructible `VerifiedSafeToReclaim` capability bound to all
of those fields and the exact expiry. The capability permits only a call to the typed step-claim API; it
is not a Kubernetes mutation credential. Cleanup APIs reject booleans, raw/copyable verdicts, duck-typed
objects, mutable `verified` fields, and a capability for another consumer, actuator, target, effect, plan,
state epoch, or reservation. A pure verifier that trusts caller-supplied `SafeToReclaimContext`
state/digest does not satisfy the production origin boundary.

Missing, denied, unavailable, malformed, stale, future, unverifiable, unreserved, or mismatched decisions
reduce to UNKNOWN and authorize no lease revocation or DELETE. There is no unsigned, cached-state,
caller-context, local-key, alternate-key, or alternate-consumer production fallback.

### D8 - Every mutation crosses an atomic, fenced step boundary

A valid capability may be retried only before its expiry while the exact reservation remains active and
the WorkOrder/workflow state epoch, registered effect, cleanup plan, cluster/Realm target, consumer, and
actuator subjects remain unchanged. It cannot be replayed across WorkOrders, workflow bindings, tenants,
states, epochs, plans, clusters, Realms, consumers, actuators, profiles, reservations, keys, or signature
domains.

Before lease revocation and each Kubernetes DELETE, the cleanup coordinator calls
`claim_safe_to_reclaim_step`. One serializable Conductor transaction revalidates the active reservation,
unexpired decision, complete unchanged signed projection and state epoch, fixed plan order, consumer, and
actuator. It records exactly one step as in flight, binding step ID/order, mutation kind, fixed object
path, plan entry digest, UID/resourceVersion/canonical-digest preconditions when applicable, coordinator
subject, actuator subject, single-use nonce, and deadline. It returns an integrity-protected opaque step
permit. No step may be claimed after decision expiry, out of order, concurrently for the same effect, or
for caller-supplied paths or preconditions.

The exact lifecycle is:

- `in_flight -> {executing, cancelled_unredeemed}`;
- `executing -> {confirmed_effect, confirmed_absent, precondition_conflict, ambiguous}`; and
- `ambiguous -> {confirmed_effect, confirmed_absent, precondition_conflict}`.

The states `in_flight`, `executing`, and `ambiguous` are non-conclusive. An `in_flight` step reaches
conclusive `cancelled_unredeemed` only through a serializable compare-and-set that proves the claim
deadline passed and the permit was never redeemed. An `executing` step reaches a conclusive result when
the exact external outcome is known, or `ambiguous` when it is not. `Ambiguous` reaches a conclusive
result only through the exact actuator or separately authorized human reconciliation below. No next step
may be claimed while any step is non-conclusive.

The separately protected actuator is the only identity with lease-revocation and Kubernetes DELETE
authority. It accepts the step only over mutually authenticated transport from the permit-bound
coordinator/reaper subject; possession of copied permit bytes by another subject conveys no authority. At
the actual mutation boundary the actuator redeems the exact permit once through its own authenticated,
strongly consistent Conductor endpoint. That atomic compare-and-set rechecks the fence and changes only
the matching step from in flight to executing; an expired, already-used, wrong-consumer, wrong-actuator,
wrong-order, wrong-object, or altered permit cannot be redeemed. The actuator then derives the operation
and path from that protected step rather than request input. Kubernetes DELETE uses the attested UID and
resourceVersion preconditions; lease revocation uses the registered lease ID, holder, and version. A
same-name replacement, changed digest, foreign object, or missing shared-role proof never reaches DELETE.
The coordinator and reaper cannot bypass this check because their identities are denied direct mutation
authority. Permit or decision expiry forbids a new redemption, but does not release the fence around an
already executing external call.

The actuator durably compare-and-sets the `executing` step to `confirmed_effect`, `confirmed_absent`,
`precondition_conflict`, or `ambiguous` before another step can be claimed. Confirmed absence is adopted
only under the same plan/reservation and exact post-read. Timeout, lost response, or uncertain
lease/DELETE outcome leaves the step in its current non-conclusive state or moves `executing` to
`ambiguous`; the exclusive state fence remains parked until the actuator or a separately authorized
human reconciliation proves the exact outcome. Neither cancellation, wall-clock reservation, nor
decision expiry releases an `in_flight`, `executing`, or `ambiguous` fence. Expiry during partial cleanup
forbids the next step; a fresh decision may resume only after the prior step is conclusively reconciled
and a new durable-state, reservation, plan-order, and live-object join succeeds.

Successful completion consumes/closes the reservation only after every registered step has ordered
`confirmed_effect` or `confirmed_absent` and records an append-only cleanup receipt. A conclusive
`precondition_conflict` or `cancelled_unredeemed` closes or parks the failed attempt without claiming
cleanup success. A decision proves only reclaimability of the registered observer-access effect. It does
not prove deletion, cleanup completion, delivery/HTTP Conditions of Done, WorkOrder success, Realm
admission, promotion, autonomous merge, or readiness.

### D9 - Local qualification and publication remain non-admissible

Local kind qualification uses a separate issuer identity and a per-run process-memory Ed25519 key with a
development-only profile. Fixture-created state/digests, admin kubeconfig cleanup, fake lease revocation,
in-memory Conductor maps, workstation credentials, loopback API endpoints, and kind cluster identity are
never trusted by a production/readiness profile. The signing key is not stored in a Kubernetes Secret or
reused across runs.

`platform-design` must publish a new immutable schema/profile bundle encoding D1-D8. Omnius must reconcile
ADR-0022, SPEC-CD/SPEC-DO, both `safe_to_reclaim` seams, the pure verifier/context, cleanup capability,
issuer/reservation and step-claim adapters, protected cleanup actuator, and kind harness to one exact
revision. In particular, missing in-memory state must stop being safe, `EXPIRED` must not authorize
reclaim before durable rollback completion, and coordinator/reaper code must not hold a direct DELETE
credential.

Production readiness still requires protected-path enforcement, exact EKS/IAM/KMS provisioning, durable
store consistency and tombstone qualification, reservation race/failure drills, negative permission
proofs, real-cluster cleanup/reaper tests, cross-repository conformance, and human activation of an exact
profile. No status, schema, component code, Conductor state, Kubernetes/AWS resource, credential, policy,
or external system is changed by this decision edit.

## Consequences

**Positive**

- Cleanup cannot authorize itself, treat a missing map entry as absence, or replay a coarse terminal
  signature against another effect or target.
- State changes and new holds cannot silently race a still-valid five-minute signature.
- An atomic single-use step permit closes the client-check-to-DELETE race at the enforced actuator.
- Ambiguous cleanup effects park one exact reservation, state fence, and plan until reconciled.
- Signer, semantic authority, verifier, coordinator, and destructive actuator have explicit, disjoint
  trust surfaces.

**Costs and risks**

- Conductor needs a strongly consistent decision/reservation API, immutable ID/tombstone ledger, and
  append-only issuance/step/consumption audit.
- The platform needs a separately protected cleanup actuator and must keep an in-flight state fence
  parked through ambiguous external outcomes.
- A genuine orphan without a retained tombstone and registered plan requires human reconciliation rather
  than automatic deletion.
- Conductor, durable store, EKS Pod Identity, KMS, reservation validation, and Kubernetes availability are
  fail-closed dependencies.
- The historical schema and current Omnius predicate/verifier/kind seams require incompatible hardening.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Missing workflow record means safe | Cache loss, replica lag, or state loss becomes permission to delete. |
| Generic `terminal` or `EXPIRED` label | It does not prove rollback/compensation completion or the exact state epoch. |
| Caller supplies trusted state/digest context | Signature verification would not prove durable state provenance. |
| Five-minute signature without reservation | A new hold or target change can race and invalidate reclaimability. |
| Client-side reservation recheck immediately before DELETE | State can change after the check and before the external mutation. |
| Coordinator owns DELETE credentials and validates its own permit | A compromised destructive caller can bypass the library check. |
| Decision omits plan, target, or executor | It can be replayed for another cleanup effect, cluster, or identity. |
| Cleanup executor evaluates/signs the predicate | The destructive actor can self-authorize. |
| Unsigned `safe_to_reclaim: true` | A caller or compromised adapter can forge permission. |
| Reuse observer/HTTP/cleanup evidence key | It collapses evidence domains and blast radius. |
| Mutable KMS alias or ARN-only trust | Rotation/substitution can change the public key without a profile revision. |
| Admin kubeconfig or kind fixture as production issuer | It lacks durable Conductor provenance and admitted workload identity. |
| Unlimited or cross-executor replay | Old state authority can be reused after trust, state, or target changes. |

## Implementation map

| Component | Responsibility |
|---|---|
| `genai-enablement` | cross-repo semantic predicate, absence, reservation, identity, signature, capability, and replay decision |
| Conductor | authoritative state/effect/tombstone transaction, exclusive reservation fence, atomic step claims, and append-only audit |
| `platform-design` | immutable issuer/consumer/target profiles, schema, IAM/KMS bindings, invalid fixtures, and bundle publication |
| `omnius` | issuer adapter, transport-neutral verifier, opaque capability, exact coordinator/reaper step claims, actuator adapter, and kind qualification |
| AWS platform | EKS Pod Identity association, IAM/session boundary, dedicated KMS key/public-key record, and CloudTrail evidence |
| Kubernetes platform | actuator-only exact preconditioned cleanup and live absence/replacement evidence; never reclaim semantics |
| Omniscience | indexes decisions/outcomes; never supplies state, absence, signing, reservation, or cleanup authority |

## Required verification

- absent in-memory/cache/replica state, unknown ID, missing/purged tombstone, lookup timeout/partition, and
  malformed/partial durable records issue no capability and perform no mutation;
- `ACTIVE`, `EXPIRED`, `FROZEN`, human-parked, pending/ambiguous compensator, reconciliation, outbox,
  provider-effect, and state-transition states issue no positive decision; only exact stable `DONE`,
  `ABORTED`, or qualified tombstone states do;
- human FROZEN release and state/hold/effect/plan/target/consumer/actuator changes conflict with pending or
  active reservation fences; they cannot commit while a step is `in_flight`, `executing`, `ambiguous`, or
  otherwise unresolved, and explicit cancellation only after every step is conclusive forces a new epoch
  and decision;
- forged caller state/context/boolean/capability/digest, generic terminal digest, duck type, alternate
  consumer, and post-verification mutation fail;
- wrong tenant, WorkOrder/workflow binding, state/epoch/store revision, tombstone, registered effect,
  envelope, plan, cluster/Realm target, executor, reservation, time, profile, key, public key, algorithm,
  signature domain, or canonical digest fails;
- decision issuance and state/reservation commit are crash-safe: failure before/after commit or KMS response
  yields either one exact signed active reservation or no usable capability, never an unsigned/duplicate
  authorization; pending-to-active CAS re-reads the complete signed state projection and rejects every
  KMS-call race;
- new-hold-versus-pending/signing/activation/step-in-flight, expiry-mid-cleanup,
  revoke-before/after-timeout, delete-before/after-timeout, same-name replacement, partition, and replay
  drills stop or resume only the exact registered effect; `in_flight`, `executing`, and `ambiguous` steps
  retain the fence through cancellation and expiry until conclusive reconciliation;
- issuer, cleanup coordinator, reaper, actuator, observer, worker, planner, verifier,
  HTTP/attestor/cleanup-evidence, and store identities are distinct; only the issuer can reserve/sign, only
  the actuator can perform the narrow mutations, and neither can mutate general WorkOrder state;
- KMS uses exact `ECC_NIST_EDWARDS25519`, `SIGN_VERIFY`, `ED25519_SHA_512`, `MessageType: RAW`, exact
  region-qualified ARN and DER SPKI public key; KMS/Pod Identity/cache failure yields UNKNOWN without
  fallback;
- coordinator/reaper direct lease revocation and DELETE are RBAC-denied; the actuator rejects forged,
  foreign-subject copies, reused, expired, wrong-consumer/actuator, wrong-order/path/object, or altered
  step permits at the mutation boundary;
- every lease revocation and DELETE has one atomic in-flight step claim; every DELETE uses fixed
  WorkOrder-derived path/order plus live canonical digest and UID/resourceVersion preconditions, preserves
  the shared role, and records a conclusive outcome before reservation completion;
- a valid reclaim capability still cannot prove cleanup completion, delivery/HTTP success, WorkOrder
  success, Realm admission, promotion, autonomous merge, or readiness;
- kind fixture decisions, fake lease revocation, admin kubeconfig cleanup, legacy absent-is-safe behavior,
  and local keys are rejected by every production trust profile;
- cross-repository conformance pins one accepted ADR set and immutable platform/Omnius revisions; no
  acceptance/readiness claim is inferred from dirty local tests.

## References

- AWS KMS Sign API: `https://docs.aws.amazon.com/kms/latest/APIReference/API_Sign.html`
- AWS KMS GetPublicKey API:
  `https://docs.aws.amazon.com/kms/latest/APIReference/API_GetPublicKey.html`
- AWS KMS asymmetric key specifications:
  `https://docs.aws.amazon.com/kms/latest/developerguide/symm-asymm-choose-key-spec.html`
- EKS Pod Identity association:
  `https://docs.aws.amazon.com/eks/latest/userguide/pod-id-association.html`
- Kubernetes DeleteOptions preconditions:
  `https://kubernetes.io/docs/reference/kubernetes-api/common-definitions/delete-options/`
