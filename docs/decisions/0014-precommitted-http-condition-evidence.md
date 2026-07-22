# ADR-0014: HTTP Conditions of Done are precommitted, externally executed evidence

- **Status:** Proposed
- **Date:** 2026-07-14
- **Last reviewed:** 2026-07-16
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `omnius`, `platform-design`)
- **Builds on:** [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0010](0010-goal-oriented-organizational-dark-factory.md),
  [ADR-0011](0011-platform-products-and-executable-paths.md), and
  [ADR-0012](0012-capability-readiness-profiles.md)

## Context

The draft `standard-http-service/v3` path names three runtime Conditions of Done: `/healthz`,
`/readyz`, and one to five request-contract paths. The request contract already limits acceptance to
`GET`, HTTP 200, and either exact text or a shallow JSON subset. It does not yet define a reusable
probe profile, target-resolution boundary, four-state result schema, trusted verifier identity, or
the evidence binding that proves three consecutive passes came from the deployed revision.

Without those contracts, an implementation could accept a worker self-report, probe a caller-chosen
URL, follow a redirect outside the Realm, reinterpret timeout as success, or run a different expected
response after implementation. That would make Condition of Done a prompt convention rather than an
execution gate.

As of 2026-07-16, `platform-design` has no published closed v1 probe-profile/result bundle for this
path. Omnius has extensive dirty/local candidate mechanics under proposed ADR-0023 and draft SPEC-DO,
including a local producer, verifier, store, and kind lifecycle probe. Those artifacts are useful
construction evidence, not cross-repository conformance, immutable publication, or readiness.

## Acceptance boundary

This ADR is non-binding while `Proposed`. Acceptance would authorize the named owners to publish and
qualify the exact contracts below; it would not accept Omnius candidate code, publish a platform bundle,
admit `standard-http-service/v3`, create cloud identities or stores, or activate a readiness profile.
ADR-0009, ADR-0010, ADR-0011, ADR-0012, and accepted ADR-0013 remain authoritative where this proposal
is incomplete. Only the human platform owner may accept, revise, reject, or supersede this decision.

## Decision

### D1 - Freeze conditions before mutating execution

Assessment resolves every load-bearing condition to a versioned probe profile before the first
mutating action. The signed execution envelope binds the request acceptance digest, PlatformPath and
probe-profile revisions, expected responses, consecutive-pass requirement, evidence TTL, Realm,
subject-issuer, producer-workload/credential-issuer, result-signer, result-verifier, evidence-store and
receipt-store profiles, their protected trust-chain binding digest, and compensation. Each profile pins
its exact revision and immutable identity; a worker may implement the endpoint but cannot modify the
frozen probe, expected value, producer image/identity, signer/verifier key binding, or stores. An adapter
reference is a lookup location, not authority: every resolved immutable profile and public-key/KMS/store
identity must join the signed envelope before authoring or network execution.

Expected exact-text and JSON-subset values are durable subject material. The initial profile therefore
admits only bounded fields whose owner-published PlatformPath schema classifies them as public and binds
that classification provenance. It rejects credentials, tokens, secrets, personal data, tenant data,
unclassified free-form values, and opaque caller blobs before freezing. Hashing an expected secret would
not make the execution contract safe because the producer still needs the plaintext oracle.

If assessment cannot define an observable condition, the WorkOrder remains assessing or becomes
bounded research. It cannot enter mutating execution with a post-hoc definition of done.

### D2 - Targets are derived from delivery identity, never supplied as URLs

The initial preview profile resolves one logical Service target from fresh, independently verified
delivery evidence: exact WorkOrder, cluster identity, Realm and namespace UID, Service name/UID, port
8080, merge commit, and image digest. The delivery observation has a bounded maximum age and its
digest is part of the execution envelope. The verifier re-reads Namespace and Service identity at
session start and before and after every attempt. It binds the Service resourceVersion and a canonical
digest of its type, selector, declared port, targetPort, and cluster address; deletion, recreation,
resource-version change, routing-spec mismatch, or other identity drift is `probe-error`.

Service identity alone does not attribute a response to a revision. The verifier therefore resolves
the complete bounded ready backend set through independently read EndpointSlices. Every address must
equal the admitted Pod's numeric `status.podIP`, join that exact Pod through the EndpointSlice
`targetRef` name/UID, be non-loopback/non-link-local/non-multicast/non-unspecified, and have a running
container whose `imageID` equals the frozen digest; external,
unowned, unready, excess, or mixed-image endpoints are `probe-error`. The closed ready-set cardinality
is one through three; an empty set is target unavailability and `probe-error`, never a vacuous pass.
One attempt probes every ready backend directly in deterministic Pod-UID order. The verifier snapshots
`EndpointSlice -> Pod UID -> imageID` immediately before and after the attempt and rejects any set,
resource-version, UID, address, readiness, or image drift. The signed snapshot digests are the
revision-attribution evidence; Service routing correctness remains part of delivery evidence rather
than being inferred from one load-balanced response.

The delivery-to-HTTP projection is normative. `service.routingSpecDigest` is RFC 8785 SHA-256 over
the live Service projection `{type, clusterIP, clusterIPs, ipFamilies, ipFamilyPolicy, selector,
ports[name, protocol, port, targetPort]}` with absent optional fields represented exactly as the
versioned projection schema defines. `renderedPodTemplateDigest` is the delivery verifier's canonical
digest of the admitted Deployment `spec.template`; `networkPolicySetDigest` is the canonical digest of
the complete sorted admitted NetworkPolicy set from the same stable delivery snapshot. The subject
copies those signed delivery values; the runtime producer re-reads and compares them but cannot invent
or replace their projection rules.

The caller supplies only a bounded ASCII origin-form path. It has exactly one leading `/`, contains
only non-empty unreserved-character segments, and has no `.` or `..` segment, repeated slash,
percent encoding, backslash, query, fragment, or control character. It cannot supply scheme, host,
port, DNS name, IP address, headers, credentials, proxy, or redirect target. In particular,
`//host/path` is invalid rather than a network-path reference.

The verifier transport derives each fixed backend authority from that trusted snapshot and has
no environment-proxy behavior, redirects, DNS rebinding fallback, arbitrary methods, or credential
injection. It passes the already-validated origin path separately to that fixed authority and never
uses URL joining or reparses the path as a URL. Production TLS and authenticated probes require a
later profile; they are not inferred from this preview contract.

### D3 - The initial HTTP profile is deterministic and bounded

The initial reusable profile runs:

- `GET /healthz`, requiring HTTP 200;
- `GET /readyz`, requiring HTTP 200;
- every request acceptance path, requiring HTTP 200 and its frozen exact-text or shallow-JSON subset;
- one through three ready backends and a pass only when every backend passes the condition; backend
  requests may execute concurrently, but inputs and retained results remain in deterministic Pod-UID order;
- three consecutive all-backend passes per condition in deterministic order;
- at most five attempt batches per condition with one second between completed batches;
- a five-second per-backend request deadline, a 30-second batch deadline, a 64-KiB response limit per
  backend, and a four-minute overall run deadline.

The published profile pins the exact supported Kubernetes server/EKS versions and required feature
states. Passing against an unrecorded newer or older control plane is not portable production evidence.

Each target snapshot uses complete paginated reads with no more than five pages, 100 objects across
the Realm runtime collections, and 1 MiB per Kubernetes response. The session reads the exact Namespace
and Service identities plus Deployment, ReplicaSet, EndpointSlice, NetworkPolicy, and Pod collections;
it has no discovery, watch, Secret/ConfigMap, log/exec/proxy, TokenRequest, foreign-Realm, or mutation
operation. An incomplete page, 101st object, repeated continuation, resource-version drift, oversized
response, or deadline crossing is unavailable evidence, never a partial target.

The producer credential lifecycle follows the Kubernetes TokenRequest floor rather than inventing a
shorter unsupported requested TTL. The protected issuer outside the producer requests exactly 600
seconds, binds the token to the exact producer Pod UID in production, and supplies it only after subject
validation. Kubernetes rejects a requested duration below 600 seconds, but the TokenRequest issuer may
return a different actual expiration. The profile therefore accepts a positive actual lifetime no greater
than 600 seconds only when at least 245 seconds remain at producer start; it does not require actual TTL
equality with the request. Issuance evidence binds the exact request, response expiration, audience,
ServiceAccount, Pod name/UID, and bound-object claims as validated online by the API server. A
caller-authored credential wrapper is not issuance evidence. The producer still has a non-extendable
four-minute execution deadline. It cannot call TokenRequest,
refresh or reuse the token, or turn token lifetime into execution budget; result persistence is followed
by producer-Pod/access cleanup. A token that is unbound, longer-lived, reused from delivery observation,
issued for another Pod/ServiceAccount/audience, or not invalidated by the qualified cleanup path is not
production evidence. An unbound admin-issued token is permitted only in explicitly development-local
transport tests and qualifies neither credential lifecycle nor readiness. Kubernetes requires requested
service account token lifetimes to be at least 600 seconds, so the previous five-minute local assumption
was not implementable on a conforming cluster.

Credential cleanup deletes the exact namespace/name with a UID precondition for the bound producer Pod,
then proves revocation rather than
assuming it from the delete response or token expiry. For at most 60 seconds it performs a bounded
authenticated read of a fixed permitted object, or an equivalent online TokenReview, using the same
token and audience. Only an explicit unauthenticated result proves invalidation; authorization denial,
transport failure, or continued authentication at the deadline remains unresolved and parks
completion. The token stays process-local and is never written to cleanup evidence. This window follows
the Kubernetes bound-token deletion semantics and accommodates authenticator cache propagation without
turning the ten-minute token lifetime into a cleanup wait.

The two status-only probes accept a bounded HTTP 200 response without requiring or decoding a media
type. An exact-text assertion requires its declared text media type and compares strictly decoded
UTF-8 bytes after no normalization. A JSON-subset assertion requires its declared JSON media type;
comparison is typed, non-recursive for v1, rejects duplicate keys/non-finite numbers, and never treats
missing keys as null.

### D4 - Results have four states and only pass completes work

Each backend result, attempt-batch result, and aggregate condition result is exactly one of `pass`,
`fail`, `inconclusive`, or `probe-error`:

- a backend `pass` means one complete response satisfies status and, when declared, media and body
  assertions;
- `fail` means a received response violates status, redirect, size, media, UTF-8, JSON, exact-text, or
  subset requirements;
- `inconclusive` means the overall run budget expires before enough attempts can be started or
  completed, without a more specific completed failure;
- `probe-error` means connection, DNS, per-attempt timeout, target-identity, verifier, schema,
  signature, or evidence failure prevents a trusted application assertion.

An attempt batch is `pass` only when every backend in the unchanged snapshot returns `pass`. Any
backend or snapshot `probe-error` makes the batch `probe-error`; otherwise any backend `fail` makes
the batch `fail`; otherwise any missing or `inconclusive` backend makes the batch `inconclusive`.
Only three consecutive `pass` batches satisfy a condition. Otherwise, at attempt/deadline exhaustion,
aggregate precedence is `probe-error`, then `fail`, then `inconclusive`; no missing response or other
state is coerced to pass. A non-pass resets the consecutive-pass counter but remains in evidence.

When the producer has a valid pre-snapshot but the post-snapshot detects drift, it emits the closed
`target-drift` attempt and discards backend observations. When Kubernetes state cannot produce the
schema-required pre/post snapshot, signing or persistence fails, or the producer disappears, no
synthetic target/result is constructed. The CompletionGate deterministically reduces missing or
unverifiable required evidence to `probe-error`; lack of a signed result is never a pass.

### D5 - Evidence binds subject, oracle, time, and trust

The signed result binds WorkOrder, execution-envelope digest, PlatformPath and probe IDs/revisions,
request acceptance digest, cluster and Realm identity, fresh delivery-observation digest, logical
target plus Service/Namespace UIDs, pre/post backend snapshot digests and resource versions, ordered
Pod UIDs and image IDs, pre/post Service resourceVersions and canonical routing-spec digests, merge
commit, image digest, unique run ID, unique ordered attempt IDs/ordinals, attempt timestamps and
durations, per-backend status/content digests, aggregate state, verifier profile digest/signing key,
and expiry. A verifier rejects duplicate, missing, reordered, stale, or cross-run attempts and any
result older than its delivery observation permits.

Evidence also contains a bounded canonical oracle projection. Exact text records expected and
observed canonical byte digests. JSON subset records, for each frozen top-level key, its presence,
expected and observed type, and canonical-value digests. This is sufficient to re-evaluate the
comparison represented by the signed assertion without retaining the full response. Raw response
bodies, credentials, and Secret values do not enter durable evidence.

The verifier runs outside the worker identity and writable workspace. Its profile and signing key are
resolved from an adapter-owned trust anchor. Self-declared verifier identity or worker-authored
evidence is invalid even when structurally well formed.

Subject issuance and result signing are separate roles and trust profiles. The subject issuer signs
the frozen run authority before network execution and has no Kubernetes/HTTP producer authority. The
result signer signs only the bounded producer output. Both trust profiles pin role, profile digest,
algorithm, provider, and readiness eligibility. A development profile pins its signing-key identity and
public-key bytes/digest; a production KMS profile pins the exact key ARN, account/region, and the exact
exported public-key bytes/digest together. A mutable KMS alias or ARN without the pinned public key is not
a production trust anchor. The producer workload, credential
issuer, subject issuer, result signer, pure verifier, store writer, worker, and cleanup executor are
distinct roles with closed permissions; structural separation labels without distinct admitted workload
identities do not qualify.
The producer cannot supply the public key used to judge itself; verification context is assembled
independently from the protected envelope/profile store. Local process-memory keys use distinct
development-only profiles and cannot satisfy a production readiness profile.

The result signer first computes `evidenceSha256` over RFC 8785 canonical result bytes excluding
exactly `evidenceSha256` and `verifier.signature`. It signs exactly:

```text
UTF8("darkfactory.http-probe-result/v1") || 0x00 || hex_to_bytes(evidenceSha256)
```

Before invoking KMS, the signer independently validates the closed result schema, frozen signed subject,
execution-envelope/run/profile/time joins, and allowed signer-owned fields, then recomputes the digest
from canonical bytes. It never signs a caller-supplied digest or uses signature success as an HTTP
verdict. The pure result verifier separately repeats schema, digest, signature, trust, and reduction
checks before issuing any completion capability.

This keeps the provider message below the AWS KMS `Sign` request limit, prevents cross-evidence-type
signature replay, and makes canonicalization independently reproducible. Production uses a dedicated
region-qualified asymmetric `ECC_NIST_EDWARDS25519` KMS key with `KeyUsage: SIGN_VERIFY`,
`ED25519_SHA_512`, `MessageType: RAW`, and only
`kms:Sign` permission for the exact result-signer workload identity. It does not sign the potentially
large canonical result directly and does not use the prehash Ed25519 variant under an `Ed25519` label.

The protected evidence-store profile pins provider, exact bucket/resource identity, prefix, create-only
policy, checksum, versioning, retention mode, and receipt schema in the execution envelope. The initial
production profile stores the canonical signed bytes at the derived key
`http-probe-result/v1/<workOrderId>/<runId>.json`. S3 writes use Signature V4 and `If-None-Match: *`,
enforced by bucket policy. Versioning plus Object Lock COMPLIANCE retention at least through the profile's
audit-retention deadline protects the committed version; Object Lock alone is insufficient because it
does not prevent a new version at the same key.

In a versioned bucket, `If-None-Match: *` applies to the current version and permits a write when that
current version is a delete marker. The qualified profile therefore denies `DeleteObject`,
`DeleteObjectVersion`, unversioned/copy writes, and store-policy/versioning/Object-Lock mutation to every
runtime identity, proves that no delete marker exists at the derived key, and invalidates readiness on
protected store-policy drift. The writer has no list, delete, policy, retention, or bypass-governance
authority. Human break-glass administration is outside runtime authority and must leave separately
audited evidence; it cannot preserve readiness silently.

A normally acknowledged write is committed only after read-back of the exact `versionId` returned by
the conditional write matches the canonical bytes and `evidenceSha256`,
and the execution store durably records an immutable receipt containing the store profile, bucket/key,
version ID, checksum, evidence digest, and commit time. Retry of the same key and identical bytes is
idempotent; a different existing byte sequence is a conflict. A timeout or other ambiguous write is
reconciled by a bounded current-key metadata read that must return one non-delete-marker `versionId`,
followed by an exact-version read: identical means committed, confirmed absence may retry, and unavailable,
marker-bearing, multi-version-ambiguous, or different remains parked. No mutable pointer, list result,
caller key, overwrite, delete, or last-writer-wins rule can establish completion authority.

Credential and producer-Pod cleanup is fail-safe, not held hostage by storage availability. The normal
ordered path is sign, persist/read-back/receipt, revoke, then attest cleanup. On signing, persistence, or
receipt failure, no persisted-evidence capability exists and completion is `probe-error`, but the
credential, producer Pod, and registered observer access are still driven toward revocation by the
session finalizer and external reaper. Such emergency cleanup cannot manufacture a result or an ordered
success receipt; ambiguity parks the WorkOrder and alerts. A crash at any boundary must therefore result
in either an exact persisted result plus cleanup evidence, or missing/uncommitted result plus cleanup and
non-completion, never retained authority merely to preserve evidence ordering.

### D6 - Publication does not grant readiness

`platform-design` owns the closed reusable schemas and draft profile revision. Omnius may implement
and qualify a runner only against an exact pinned draft. Realm admission, readiness activation, and
production use require later human-owned revisions and real-path evidence. This ADR does not admit the
current v3 path or change the existing v2 readiness pin.

Before an acceptance decision, the Omnius candidate must be treated as an adoption gap where it requires
`actual_ttl_seconds == 600`: the cross-repository contract accepts a shorter issuer-returned lifetime when
the verified remaining budget is at least 245 seconds. Its local filesystem store and kind/admin cleanup
remain development evidence and do not prove the production S3 delete-marker/version boundary or
UID-preconditioned cleanup identity.

## Consequences

**Positive**

- Completion is auditable from a frozen expectation, bounded oracle projection, and external evidence.
- Caller-controlled URL/redirect/proxy behavior cannot turn probes into an SSRF or credential channel.
- Timeout and missing evidence stay distinct from an application assertion failure.
- The same machine contract serves human-authored and AI-assessed requests.

**Costs and risks**

- The preview profile proves only bounded HTTP behavior, not SLO, data correctness, or production
  readiness.
- Three passes reduce transient false positives but are not a statistical reliability claim.
- Service/namespace identity and network placement must be independently verified before probing.
- Future authenticated/TLS, streaming, deep JSON, write-method, Terraform, and SLO probes need new
  profiles rather than widening v1.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Let the worker run its own smoke test | Producer self-report is not external ground truth. |
| Accept a request URL | Creates SSRF, DNS, redirect, credential, and cross-Realm ambiguity. |
| Treat timeout as retry-until-pass | Hides bounded failure and makes completion non-deterministic. |
| Store response bodies as evidence | Expands sensitive-data retention; the bounded oracle projection is sufficient to audit the signed comparison. |
| Use an LLM to judge response correctness | The initial contract is deterministically comparable. |

## Implementation map

| Component | Responsibility |
|---|---|
| `genai-enablement` | cross-repo decision and shared terminology |
| `platform-design` | closed probe profile/result schemas, draft path binding, invalid fixtures |
| `omnius` | exact contract ingestion, bounded transport/runner, signing, create-only persistence, lifecycle and evidence verification |
| Application repository | owns its relative request paths and expected domain responses |
| Omniscience | indexes outcomes and later escapes; never supplies completion authority |

## Required verification

- expectation, probe revision, target binding, and verifier identity mutations fail;
- a caller host, scheme, header, credential, proxy, redirect, non-GET method, `//host` path, dot
  segment, percent encoding, query, or fragment is rejected;
- exact text and typed JSON subset positive/negative vectors are deterministic;
- timeout, oversize, invalid media/UTF-8/JSON, duplicate keys, non-finite numbers, and missing keys
  produce the specified non-pass state;
- one or two passes followed by failure do not satisfy three consecutive passes;
- mixed backend pass/fail, pass/probe-error, and missing-response batches reduce to the specified
  non-pass state;
- a zero-backend snapshot is `probe-error` and cannot satisfy a condition;
- duplicate or reordered attempts, a stale delivery observation, and cross-cluster or cross-run
  replay fail;
- Service selector, EndpointSlice membership/readiness, Pod UID/address, or container image mutation
  before or during an attempt produces `probe-error`;
- evidence from another WorkOrder, Service/Namespace UID, commit, image, or expired window fails;
- worker-authored/self-signed evidence cannot satisfy a Condition of Done;
- a sensitive or opaque expected value is rejected before subject issuance and never reaches durable
  evidence;
- post-freeze subject/result trust-anchor substitution, equal issuer/verifier roles, or a profile/key
  not joined to the protected execution envelope fails before network execution or completion;
- delivery projection mutation for Service routing, pod template, or NetworkPolicy set fails even when
  the mutated subject/result is internally re-signed;
- incomplete pagination, 101st runtime object, repeated continuation, Kubernetes read failure, signing
  failure, or missing evidence becomes `probe-error` at the CompletionGate and never a synthetic pass;
- the matrix passes on the exact pinned Kubernetes/EKS revisions and an unrecorded control-plane version
  cannot qualify by compatibility assumption;
- caller-supplied digest signing and signer-side subject/schema/join bypass fail before KMS invocation;
- signature-domain, evidence digest, exact KMS ARN/account/region/public-key digest/key-usage/algorithm/message-type, store
  profile, derived object key, conditional-write, delete-marker absence, exact-version checksum/read-back,
  receipt, or retained bytes mutation fails closed;
- crash or timeout before write, after ambiguous write, after read-back, after receipt, and during revoke
  yields exactly one immutable result or no committed result; a different same-key object conflicts;
- signer/store/receipt failure still attempts credential, producer-Pod, and registered-access cleanup,
  while missing ordered persistence remains `probe-error` and cannot be repaired by unsigned evidence;
- a requested 599-second TokenRequest is rejected by Kubernetes; a requested 600-second Pod-bound token
  with verified actual lifetime at most 600 seconds and at least 245 seconds remaining covers the run;
  a shorter still-sufficient returned lifetime is accepted, while an overlong/insufficient, claim/status-
  mismatched, wrong-bound-Pod, refreshed/reused, or still-authenticated token 60 seconds after
  UID-preconditioned exact-Pod deletion is rejected without completion evidence;
- cleanup invalidation is observed before the token's natural expiry; unauthenticated only after natural
  expiry is not deletion proof, authorization denial or transport/TokenReview failure parks, and a
  same-name replacement makes the UID-preconditioned DELETE fail while preserving the replacement;
- draft publication and runner qualification do not create Realm admission or readiness.

Kubernetes references: [TokenRequest validation requires at least 600 seconds](https://github.com/kubernetes/kubernetes/blob/master/pkg/apis/authentication/validation/validation.go),
[TokenRequest expiration is issuer-returned](https://github.com/kubernetes/api/blob/master/authentication/v1/types.go),
[the API server controls maximum issued lifetime](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-apiserver/#options),
and [bound tokens fail when the object is absent or has been deleting for 60 seconds](https://kubernetes.io/docs/reference/access-authn-authz/service-accounts-admin/#bound-service-account-tokens).

AWS references: [KMS `Sign` limits and Ed25519 message types](https://docs.aws.amazon.com/kms/latest/APIReference/API_Sign.html),
[KMS Ed25519 key specifications](https://docs.aws.amazon.com/kms/latest/developerguide/symm-asymm-choose-key-spec.html),
[S3 conditional create-only writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html),
[S3 bucket-policy enforcement of conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html),
and [S3 Object Lock version semantics](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html).
