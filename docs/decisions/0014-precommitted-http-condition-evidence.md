# ADR-0014: HTTP Conditions of Done are precommitted, externally executed evidence

- **Status:** Proposed
- **Date:** 2026-07-14
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

## Decision

### D1 - Freeze conditions before mutating execution

Assessment resolves every load-bearing condition to a versioned probe profile before the first
mutating action. The signed execution envelope binds the request acceptance digest, PlatformPath and
probe-profile revisions, expected responses, consecutive-pass requirement, evidence TTL, Realm,
subject-issuer profile, result-verifier profile, their protected trust-anchor binding digest, and
compensation. A worker may implement the endpoint but cannot modify the frozen probe, expected value,
signer profile/key binding, or evidence store. An adapter reference is a lookup location, not authority:
the resolved immutable profile and public-key/KMS identity must join the signed envelope before authoring.

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
target an admitted Pod UID whose running container `imageID` equals the frozen digest; external,
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
- one through three ready backends and a pass only when every backend passes the condition;
- three consecutive all-backend passes per condition in deterministic order;
- at most five attempt batches per condition with one second between completed batches;
- a five-second per-backend request deadline, a 30-second batch deadline, a 64-KiB response limit per
  backend, and a four-minute overall run deadline.

Each target snapshot uses complete paginated reads with no more than five pages, 100 objects across
the Realm runtime collections, and 1 MiB per Kubernetes response. The session reads the exact Namespace
and Service identities plus Deployment, ReplicaSet, EndpointSlice, NetworkPolicy, and Pod collections;
it has no discovery, watch, Secret/ConfigMap, log/exec/proxy, TokenRequest, foreign-Realm, or mutation
operation. An incomplete page, 101st object, repeated continuation, resource-version drift, oversized
response, or deadline crossing is unavailable evidence, never a partial target.

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
algorithm, signing key ID/public-key digest or exact KMS key, provider, and readiness eligibility.
The producer cannot supply the public key used to judge itself; verification context is assembled
independently from the protected envelope/profile store. Local process-memory keys use distinct
development-only profiles and cannot satisfy a production readiness profile.

### D6 - Publication does not grant readiness

`platform-design` owns the closed reusable schemas and draft profile revision. Omnius may implement
and qualify a runner only against an exact pinned draft. Realm admission, readiness activation, and
production use require later human-owned revisions and real-path evidence. This ADR does not admit the
current v3 path or change the existing v2 readiness pin.

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
| `omnius` | exact contract ingestion, bounded transport/runner, signature and evidence verification |
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
- post-freeze subject/result trust-anchor substitution, equal issuer/verifier roles, or a profile/key
  not joined to the protected execution envelope fails before network execution or completion;
- delivery projection mutation for Service routing, pod template, or NetworkPolicy set fails even when
  the mutated subject/result is internally re-signed;
- incomplete pagination, 101st runtime object, repeated continuation, Kubernetes read failure, signing
  failure, or missing evidence becomes `probe-error` at the CompletionGate and never a synthetic pass;
- draft publication and runner qualification do not create Realm admission or readiness.
