# ADR-0015: Observer authority is attested by a separate identity and trust root

- **Status:** Proposed
- **Date:** 2026-07-14
- **Last reviewed:** 2026-07-16
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `omnius`, `platform-design`)
- **Builds on:** [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0012](0012-capability-readiness-profiles.md), and
  [ADR-0013](0013-platform-owned-observer-access.md)

## Context

ADR-0013 gives one WorkOrder-specific observer narrowly scoped Kubernetes read authority. That
observer cannot be the authority that proves its own permissions: a compromised credential,
caller-authored authorization context, or client-side scope check could otherwise produce an
always-pass admission result.

A finite SubjectAccessReview matrix is necessary but is not by itself a complete authority proof.
The effective subject includes ServiceAccount groups; RoleBindings in any namespace and
ClusterRoleBindings can grant it authority; an aggregated ClusterRole can change after its binding;
and a non-RBAC authorizer can make a decision that is absent from the RBAC objects. Kubernetes also
documents SelfSubjectRulesReview as potentially incomplete and unsuitable as an external
authorization decision. Production evidence therefore has to bind a qualified authorizer/API
profile, complete RBAC closure, exact server decisions, and proof that relevant authority did not
change during acquisition.

As of 2026-07-16, Omnius has dirty/local candidate code under proposed ADR-0021 and draft SPEC-DO.
Its pure verifier checks a signed attestation against a supplied `ObserverAttestationContext`, while
the kind qualification reads the expected seven access objects and runs positive/negative SAR cases.
It does not establish the protected origin of that context, enumerate every applicable binding/rule,
or derive `inheritedAuthority` from the live cluster; the latter remains fixture-provided. The
Omnius ADR names platform commit `6b45293a...`, while its SPEC and verifier pin `1243d374...`.

The local `platform-design` checkout at `c606fdb...` does not materialize the observer-attestation
bundle. Candidate commits `6b45293a...` and `1243d374...` are available in the local object database
but are not ancestors of that checkout. Their proposed ADR-0059, schema, and draft profiles are useful
construction evidence; they do not supply an accepted, current-branch, immutable production binding.
The candidate schema also records only expected object projections and matrix/context digests, not
the complete acquisition and stability proof required below.

## Acceptance boundary

This ADR is non-binding while `Proposed`. Accepted ADR-0013 and the currently selected readiness
profile remain authoritative. If a draft Omnius or platform-design artifact conflicts with this
decision, it is an adoption gap rather than precedent.

Human acceptance would authorize downstream schema and implementation work against an exact revision.
It would not accept the component ADRs, publish a platform bundle, provision Kubernetes or AWS
resources, admit `standard-http-service/v3`, activate a Realm, or grant completion, promotion,
autonomous-merge, cleanup, or production-readiness authority. Those remain separate human-owned
actions with exact-revision evidence.

## Decision

### D1 - The attestor is one closed, separate platform-control workload

The production subject is exactly
`system:serviceaccount:darkfactory-attestors:observer-rbac-attestor` in the qualified cluster. Its
Pod image digest, ServiceAccount UID, namespace UID, EKS cluster identity, scheduling boundary, network
policy, platform profile revision, and execution-envelope reader are pinned by the production trust
profile. It is not the observer ServiceAccount, worker, planner, Conductor decision issuer, HTTP
producer/result signer, delivery verifier, store writer, placement controller, cleanup executor, or
orphan reaper. It runs on the protected platform-control node boundary and may not share a Pod or
node trust class with untrusted worker workloads.

Its Kubernetes API authority is closed to:

- cluster-wide `get`/`list` of Roles and RoleBindings, plus `get`/`list` of ClusterRoles and
  ClusterRoleBindings, because a foreign binding can grant the observer authority outside its intended
  Realm;
- `create` of `authorization.k8s.io/v1` SubjectAccessReview requests for the exact frozen matrix;
- exact `get` of the observer ServiceAccount, target Namespace, Argo Application, and admitted access
  objects needed for the signed lineage.

The profile grants no observer bearer token; `impersonate`; Secret or ConfigMap read; TokenRequest;
SelfSubjectRulesReview; discovery; workload/RBAC mutation; log, exec, attach, port-forward, or proxy;
evidence-store mutation; lease revocation; or cleanup permission. It cannot author the WorkOrder,
execution envelope, access profile, baseline, cluster profile, or cleanup plan. Any wildcard, extra
permission, credential-provider fallback, or unqualified co-tenancy makes the production profile
ineligible.

### D2 - Authority acquisition is server-originated, not caller-supplied context

One attestation run starts from a Conductor-signed execution envelope and independently protected
platform profiles. They bind the WorkOrder and observation-session IDs, one-use nonce, observer
subject derivation, intended token audience, Application/Realm, control-inventory and cleanup-plan
digests, platform bundle, cluster/authorizer profile, authority matrix, attestor profile, and maximum
five-minute acquisition interval. The attestor verifies those signatures and digests before contacting
Kubernetes.

Using only its own qualified Kubernetes credential and pinned TLS endpoint/CA, the attestor acquires
the live objects and submits every SubjectAccessReview itself. The signed evidence contains canonical
request/response projections and digests, API group/version, object UIDs/resourceVersions/rule digests,
collection snapshot digests, and acquisition times. A caller cannot supply a trusted `verified: true`,
`complete: true`, inherited-authority object, SAR response, live-object context, or signing digest.
Passing a structurally valid context to a pure verifier is not evidence of its acquisition origin.

The reviewed SAR subject fixes the exact ServiceAccount username and the canonical
`system:serviceaccounts`, namespace ServiceAccount, and `system:authenticated` groups. It also binds the
live ServiceAccount and namespace UIDs. A qualified profile cannot depend on credential-specific user
extras that the attestor cannot establish without receiving the observer token. This attestation proves
subject authority, not issuance or possession of a particular bearer token; the consumer must separately
join trusted TokenRequest issuance, audience, bound-object, expiry, and revocation evidence.

### D3 - Complete RBAC closure and exact server decisions are both required

The attestor resolves every RoleBinding and ClusterRoleBinding that can apply through the observer's
exact username or groups, every referenced Role or ClusterRole, and every rule that contributes to
effective authority. Direct `User` subjects matching the canonical ServiceAccount username count as
applicable. A missing reference, duplicate or unexpected binding, wildcard, aggregationRule,
unsettled aggregated-role output, unknown subject form, or unrepresentable rule produces UNKNOWN.

The cluster profile pins the Kubernetes/EKS version, API-resource/discovery digest obtained by the
independent cluster-qualification path, authorization mode/chain, authenticated baseline revision,
and canonical baseline rules. Only an authorizer chain whose contribution to this subject is closed
and deterministically represented may qualify. An unknown or changed webhook/authorizer, cluster
configuration, API resource, baseline, or default binding produces UNKNOWN. The attestor does not use
discovery as observation input and does not infer the baseline from its own runtime permissions.

The evidence separately records:

1. the exact authority granted by the admitted observer-access profile;
2. the independently published authenticated baseline;
3. all additional/inherited RBAC authority; and
4. the API server's response for each frozen positive and negative SAR case.

A positive case requires `allowed: true` and no `evaluationError`. A negative case requires
`allowed: false` and no `evaluationError`; the optional `denied` and `reason` fields are recorded, but
`denied: false` does not convert a final not-allowed response into an allow. Any negative allow,
positive not-allow, evaluation error, missing/malformed response, matrix drift, non-empty undeclared
residual authority, or RBAC/SAR disagreement produces UNKNOWN and no admissible attestation.

The first profile proves only its precommitted action/resource universe on its exact cluster profile.
It does not claim that a finite matrix describes future CRDs or arbitrary authorizer behavior.

### D4 - A bracketing snapshot and protected mutation continuity close the race

The attestor takes a complete pre-snapshot of all relevant RBAC collections and exact lineage objects,
runs the entire SAR matrix, then takes the same complete post-snapshot. Collection completeness,
pagination, resourceVersion behavior, object UID/resourceVersion, canonical rule/binding digests, and
resolved closure must match. It signs only after the post-snapshot passes.

Matching scans alone do not exclude a grant inserted and removed between them. The production profile
therefore selects one independently enforced mechanism that proves no relevant RBAC, authorizer,
baseline, API-resource, or bound-object mutation occurred from the pre-snapshot through signing: either
an exact protected mutation-fence/epoch receipt or an independently protected append-only audit
continuity proof. The mechanism, issuer, interval, event classes, completeness rule, and digest are
pinned in the execution envelope and evidence. Absence, gaps, clock ambiguity, mutation, or an
unqualified mechanism produces UNKNOWN. The attestor cannot issue or modify this continuity proof.

The evidence binds `observedAt`, acquisition start/end, signature time, and `expiresAt`. Its lifetime is
positive and no greater than five minutes; verification must occur within the interval and within the
enclosing observation session. Reuse is limited to the same immutable WorkOrder, session, nonce,
cluster/profile revisions, and subject snapshot. Cross-session, cross-cluster, post-expiry, or changed-
epoch replay fails.

### D5 - Production signing uses an exact asymmetric AWS KMS trust anchor

The attestor obtains AWS credentials only through one EKS Pod Identity association bound to the exact
cluster, namespace, and ServiceAccount. The profile pins the association ARN/ID, IAM role ARN and
account, session-tag conditions, association/session policy, role trust policy, KMS key policy, region,
and the negative proof that no other runtime identity can sign with the key. Node-instance metadata,
ambient AWS credentials, IRSA, static credentials, and another association are forbidden fallbacks.

The dedicated customer-managed asymmetric key is pinned by exact region-qualified key ARN and has
`KeySpec: ECC_NIST_EDWARDS25519`, `KeyUsage: SIGN_VERIFY`, enabled state, and signing algorithm
`ED25519_SHA_512`. The `GetPublicKey` qualification record pins the returned key ARN, DER-encoded SPKI
public-key bytes and SHA-256 digest, KeySpec, KeyUsage, and signing-algorithm set. A mutable alias, key ARN
without the pinned public key, public key without its exact key ARN/account/region, multi-Region
substitution, or unexpected algorithm is not a trust anchor.

The runtime IAM role can call only `kms:Sign` on that key, and the KMS/key and IAM policies restrict it
to the exact admitted Pod Identity session. Key administrators do not receive signing authority. The
observer, worker, producer, result signer, cleanup/reaper, planner, verifier, and store identities cannot
call the key. Rotation creates a new immutable trust-profile revision; old evidence remains verifiable
only for its already bounded lifetime. The private key never enters Kubernetes, an image, filesystem,
environment variable, or evidence artifact.

### D6 - The payload is deterministic, domain-separated, and signed only after semantic validation

The attestor validates the closed schema and every envelope/profile/object/SAR/continuity join from its
own acquired data. It then computes `evidenceSha256` over RFC 8785 canonical evidence after removing
exactly `evidenceSha256` and `signature.value`, and submits exactly this message to KMS with
`SigningAlgorithm: ED25519_SHA_512` and `MessageType: RAW`:

```text
UTF8("darkfactory.observer-access-attestation/v1") || 0x00 ||
hex_to_bytes(evidenceSha256)
```

The attestor rejects a caller-supplied digest and validates that the KMS response reports the exact key
ARN and signing algorithm. The verifier independently repeats schema validation, canonicalization,
digest calculation, standard Ed25519 verification over the same domain-separated message, exact
public-key/profile resolution, lineage, closure, matrix, continuity, freshness, and replay checks. The
evidence itself cannot nominate a trusted key, profile, cluster, baseline, or verifier.

### D7 - Verification yields one narrow, opaque authority capability

A successful verifier returns an integrity-protected, caller-unconstructible capability bound to the
exact WorkOrder, observation session, nonce, subject, cluster, authority/profile digests, evidence
digest, and expiry. Consumers revalidate that binding and expiry at use. Raw evidence, a copied verdict,
a truthy value, or a mutable `verified` field is not accepted.

The capability proves only that the observer subject matched the admitted authority profile during the
bounded stable interval. It does not prove token issuance/possession, delivery state, HTTP Conditions of
Done, WorkOrder completion, safe-to-reclaim, cleanup success, Realm admission, or readiness. Missing,
unavailable, malformed, stale, unverifiable, or non-matching evidence reduces to UNKNOWN and authorizes
nothing; there is no unsigned, cached, caller-context, local-key, or alternate-key production fallback.

### D8 - Local kind qualification remains a separate non-admissible trust class

Local development runs a separate attestor identity with a per-run process-memory Ed25519 signing key.
Its Kubernetes client credential, admin-assisted CSR/bootstrap, loopback API endpoint, workstation,
kind cluster, profiles, and evidence are development-only. Evidence is marked with the exact
`kind-development/v1` profile, ephemeral public key, cluster identity, run/session nonce, and short
expiry. The signing private key is not stored in a Kubernetes Secret or reused across runs.

Local evidence may test schema, acquisition, failure injection, signature, replay, and cleanup joins.
No production or readiness profile may trust its key, kubeconfig/client certificate, cluster identity,
fixture context, or admin bootstrap. It cannot activate a Realm, production path, completion,
promotion, cleanup, autonomous merge, or readiness.

### D9 - Publication and acceptance do not activate observer readiness

`platform-design` must publish a new immutable candidate bundle that encodes D1-D8 rather than treating
the historical draft schema as sufficient. Omnius must rejoin one exact platform revision and replace
caller-provided acquisition context with a protected origin/capability boundary. Its component ADR/SPEC,
schema pins, verifier, producer, and kind harness must agree on the same revisions before adoption can be
claimed.

Production identity/key provisioning, protected-path enforcement, real-EKS positive/negative probes,
RBAC mutation-continuity drills, credential and cleanup/reaper qualification, cross-repository
conformance, and a human-owned readiness revision remain mandatory. No document-status change, schema
publication, cloud mutation, or component implementation is performed by this decision edit.

## Consequences

**Positive**

- Observer compromise cannot self-assert a narrower authority than the qualified API server granted.
- Caller-created contexts and finite SAR-only checks cannot masquerade as complete authority evidence.
- The signing key is outside Kubernetes storage and unavailable to worker, observer, and destructive
  identities.
- Development qualification and production verification share semantics without sharing trust roots.

**Costs and risks**

- The attestor has broad read access to RBAC metadata and requires isolation, audit, and bounded output.
- A qualified cluster/authorizer baseline and protected mutation-continuity mechanism become critical
  dependencies.
- EKS Pod Identity, KMS, Kubernetes API, and continuity-proof availability are fail-closed production
  dependencies.
- The historical platform schema and current Omnius context/verifier seam require incompatible hardening
  before adoption.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Observer signs its own authority | Collapses producer and verifier into one compromised identity. |
| Caller supplies trusted live context | Signature verification would not prove how objects, rules, or SAR decisions were acquired. |
| SelfSubjectRulesReview as authority oracle | Kubernetes documents it as potentially incomplete and unsuitable for external authorization decisions. |
| Positive/negative SAR matrix alone | It cannot enumerate foreign grants, future resources, or unqualified authorizer behavior. |
| Matching pre/post scans without continuity proof | A temporary grant can be inserted and removed between scans. |
| Admin kubeconfig as production attestor | Unbounded credential and no admitted workload-identity provenance. |
| `kubectl auth can-i --as` only | Requires impersonation and does not bind exact live RBAC objects or acquisition provenance. |
| Kubernetes Secret stores the production key | Cluster Secret readers could forge external authority. |
| Mutable KMS alias or ARN-only trust | Rotation/substitution can change the verifying public key without a profile revision. |
| One trust profile for kind and EKS | Development evidence could be replayed as readiness evidence. |

## Implementation map

| Component | Responsibility |
|---|---|
| `genai-enablement` | cross-repo identity, acquisition, stability, trust-root, and authority-capability decision |
| `platform-design` | immutable cluster/baseline/attestor profiles, RBAC, schemas, continuity mechanism, invalid fixtures, and bundle publication |
| `omnius` | protected acquisition adapter, deterministic pure verifier, opaque capability consumer, and local-kind qualification |
| AWS platform | EKS Pod Identity association, IAM/session boundaries, asymmetric KMS key, public-key record, and CloudTrail evidence |
| Kubernetes platform | qualified authorizer/API profile, mutation continuity, exact SAR responses, and bounded RBAC reads |
| Omniscience | indexes attestation outcomes; never supplies context, signing, verification, or authorization authority |

## Required verification

- observer, worker, producer/result signer, verifier, store, cleanup/reaper, and planner identities cannot
  call the attestor KMS key; attestor is the sole runtime signer;
- attestor cannot read Secrets/ConfigMaps, mint tokens, impersonate, discover APIs, mutate RBAC/workloads,
  access evidence storage, revoke leases, or clean resources;
- forged caller context, `verified: true`, copied capability, supplied digest, alternate credential
  provider, wrong Pod Identity association/session tag, and post-verification mutation fail;
- all ServiceAccount username/group bindings and every applicable RoleBinding/ClusterRoleBinding and
  referenced rule are resolved; direct-User, foreign, wildcard, aggregate, extra-subject, and residual
  grants fail;
- exact positive SAR cases allow and negative cases do not allow; missing result, `evaluationError`,
  matrix drift, unknown authorizer, API/baseline drift, and RBAC/SAR disagreement fail;
- temporary grant insertion/removal, continuity gap, incomplete pagination, object replacement, or
  mutation between pre-snapshot and signing produces no capability;
- wrong WorkOrder/session/nonce, cluster, subject/group set, envelope, profile, key ARN, public key,
  algorithm, signature domain, canonical digest, time interval, or replay epoch fails;
- KMS uses exact `ECC_NIST_EDWARDS25519`, `SIGN_VERIFY`, `ED25519_SHA_512`, `MessageType: RAW`, and the
  pinned DER SPKI public key; KMS or Pod Identity failure yields UNKNOWN without fallback;
- a valid authority capability still cannot satisfy token issuance, delivery/HTTP evidence, completion,
  safe-to-reclaim, cleanup, Realm admission, or readiness;
- kind evidence and historical fixture-derived context are rejected by every production readiness trust
  profile;
- cross-repository conformance pins one exact accepted ADR set and immutable platform/Omnius revisions;
  no acceptance or readiness claim is inferred from local dirty tests.

## References

- Kubernetes SubjectAccessReview API:
  `https://kubernetes.io/docs/reference/kubernetes-api/authorization-resources/subject-access-review-v1/`
- Kubernetes authorization checks and SelfSubjectRulesReview limitations:
  `https://kubernetes.io/docs/reference/access-authn-authz/authorization/#checking-api-access`
- Kubernetes RBAC and aggregated ClusterRoles:
  `https://kubernetes.io/docs/reference/access-authn-authz/rbac/`
- AWS KMS Sign API: `https://docs.aws.amazon.com/kms/latest/APIReference/API_Sign.html`
- AWS KMS GetPublicKey API:
  `https://docs.aws.amazon.com/kms/latest/APIReference/API_GetPublicKey.html`
- AWS KMS asymmetric key specifications:
  `https://docs.aws.amazon.com/kms/latest/developerguide/symm-asymm-choose-key-spec.html`
- EKS Pod Identity association:
  `https://docs.aws.amazon.com/eks/latest/userguide/pod-id-association.html`
