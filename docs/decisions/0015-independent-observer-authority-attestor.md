# ADR-0015: Observer authority is attested by a separate identity and trust root

- **Status:** Proposed
- **Date:** 2026-07-14
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `omnius`, `platform-design`)
- **Builds on:** [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0012](0012-capability-readiness-profiles.md), and
  [ADR-0013](0013-platform-owned-observer-access.md)

## Context

ADR-0013 gives one WorkOrder-specific observer narrowly scoped Kubernetes read authority. That
observer cannot be the authority that proves its own permissions: a compromised credential or a
client-side scope check could otherwise produce an always-pass admission result.

The draft platform contract therefore requires an independently signed observer-access
attestation. It does not yet select the attestor workload identity, Kubernetes read surface,
production signing root, signature payload, or the boundary between disposable local-kind evidence
and readiness evidence. Those choices are security properties, not adapter implementation details.

## Decision

### D1 - The attestor is a separate platform-control workload

Production uses one dedicated ServiceAccount, `observer-rbac-attestor`, in the
`darkfactory-attestors` namespace. It is not the observer ServiceAccount, Omnius worker, verifier,
placement controller, or cleanup/reaper identity. It runs on the platform-control node pool and may
not be co-located with an untrusted worker workload.

Its Kubernetes API surface is closed to:

- `get`/`list` of ServiceAccounts, Roles, RoleBindings, ClusterRoles, and ClusterRoleBindings needed
  to resolve all bindings that can apply to the observer subject;
- `create` of `authorization.k8s.io/v1` SubjectAccessReview requests for the frozen positive and
  negative matrix;
- exact reads of the Application, Namespace, and admitted access objects whose identity is bound into
  the attestation.

It receives no observer bearer token, `impersonate`, Secret/ConfigMap read, TokenRequest, workload
mutation, RBAC mutation, exec/log/proxy, or cleanup permission. SubjectAccessReview names the subject
being evaluated and therefore does not require impersonation. Any wildcard or extra permission makes
the attestor profile unqualified.

WorkOrder identity and cleanup-plan digests come from the Conductor-signed execution envelope the
attestor cannot author. This decision does not require WorkOrder to become a Kubernetes CRD or make
cluster state the task source of truth.

### D2 - Attestation combines object provenance, rule resolution, and server decisions

One attestation freezes a bounded Kubernetes snapshot and includes every access object UID,
resourceVersion, canonical rule digest, subject binding, and profile digest. The attestor resolves
all RBAC bindings that can apply to the observer subject, including ServiceAccount groups and
cluster-wide bindings. It separately asks the API server for every frozen positive and negative
SubjectAccessReview case.

An allow in the negative matrix, a deny in the positive matrix, `evaluationError`, missing decision,
snapshot drift, unresolved aggregated role, unknown authorizer in the qualified cluster profile, or
RBAC/SAR disagreement produces UNKNOWN and no signed attestation. The first profile proves the closed
observer action universe and its declared authenticated baseline; it does not claim that a finite
matrix describes arbitrary future CRDs or a different authorizer chain.

### D3 - Production signing uses an asymmetric AWS KMS key

The production attestor obtains AWS credentials through an EKS Pod Identity association bound to
its exact namespace and ServiceAccount. Its IAM role can call only `kms:Sign` on one versioned
asymmetric `ECC_NIST_EDWARDS25519` signing key with signing algorithm `ED25519_SHA_512`. The private
key never enters Kubernetes, a container image, environment variable, or evidence artifact. The
observer, worker, cleanup controller, and Omnius planner have no KMS signing permission.

The verifier trust profile pins the KMS key ARN, public-key digest, algorithm, attestor Kubernetes
subject, cluster identity, and profile revision. Key rotation creates a new trust-profile revision;
old evidence remains verifiable until its bounded expiry but a mutable alias is never sufficient
authority.

### D4 - The signed payload is small, domain-separated, and deterministic

The attestor first computes `evidenceSha256` over RFC 8785 canonical evidence excluding
`evidenceSha256` and `signature.value`. It signs exactly:

```text
UTF8("darkfactory.observer-access-attestation/v1") || 0x00 || hex_to_bytes(evidenceSha256)
```

The verifier recomputes the canonical digest before verifying the Ed25519 signature. This avoids
provider message-size ambiguity, prevents a signature from being replayed as another evidence type,
and keeps canonicalization outside the KMS API boundary.

### D5 - Local kind qualification has a separate non-admissible trust profile

Local development runs the attestor outside the observer identity with a process-memory Ed25519 key
generated for that qualification run. The private key is not stored in a Kubernetes Secret. Evidence
is marked with the `kind-development/v1` attestor profile, cluster identity, and short expiry.

No readiness profile may trust the development key, local kubeconfig, loopback API server, or kind
cluster identity. Local evidence validates contract behavior and failure injection only; it cannot
activate a Realm, production path, or autonomous merge.

### D6 - This decision does not activate observer readiness

Acceptance would authorize component contracts and implementation, not execution readiness. The
draft path remains catalog-only until production identity and key provisioning, protected-path
enforcement, real-cluster positive/negative probes, cleanup/reaper qualification, and a separate
human-owned readiness profile all pass against exact revisions.

## Consequences

**Positive**

- Observer compromise cannot self-assert a narrower authority than the API server grants.
- The signing key is outside Kubernetes storage and unavailable to worker and observer identities.
- The same closed evidence contract supports local failure injection and production verification
  without treating their trust roots as equivalent.

**Costs and risks**

- The attestor has broad read access to RBAC metadata and must be isolated and audited accordingly.
- SubjectAccessReview is necessary but not sufficient; deterministic binding/rule resolution remains
  required to expose foreign grants and provenance drift.
- EKS Pod Identity and KMS availability become production dependencies; failure produces UNKNOWN,
  never an unsigned fallback.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Observer signs its own authority | Collapses producer and verifier into one compromised identity. |
| Admin kubeconfig as production attestor | Unbounded credential and no workload-identity provenance. |
| `kubectl auth can-i --as` only | Requires impersonation and does not bind exact live RBAC objects. |
| Kubernetes Secret stores the production key | Cluster Secret readers could forge external authority. |
| One trust profile for kind and EKS | Development evidence could be replayed as readiness evidence. |

## Implementation map

| Component | Responsibility |
|---|---|
| `genai-enablement` | cross-repo identity and trust-root decision |
| `platform-design` | versioned attestor/trust profiles, RBAC, signature contract, invalid fixtures |
| `omnius` | deterministic evidence verifier and local-kind qualification harness |
| AWS platform | EKS Pod Identity association, IAM role, asymmetric KMS key, CloudTrail audit |
| Omniscience | indexes attestation outcomes; never supplies signing or authorization authority |

## Required verification

- observer/worker/cleanup identities cannot call the KMS signing key;
- attestor cannot read Secrets, mint tokens, impersonate, mutate RBAC/workloads, or clean resources;
- exact positive reads pass and every frozen negative case denies through SubjectAccessReview;
- foreign RoleBinding/ClusterRoleBinding, wildcard, aggregated-role drift, or extra subject fails;
- object mutation between rule resolution and signing produces no evidence;
- wrong key, profile, cluster, subject, signature domain, canonical digest, or expired evidence fails;
- KMS or Pod Identity failure produces UNKNOWN without local-key fallback;
- kind evidence is rejected by every production readiness trust profile.

## References

- Kubernetes SubjectAccessReview API:
  `https://kubernetes.io/docs/reference/kubernetes-api/definitions/subject-access-review-v1-authorization/`
- Kubernetes authorization checks:
  `https://kubernetes.io/docs/reference/access-authn-authz/authorization/#checking-api-access`
- AWS KMS asymmetric key specifications:
  `https://docs.aws.amazon.com/kms/latest/developerguide/symm-asymm-choose-key-spec.html`
- AWS KMS Sign API: `https://docs.aws.amazon.com/kms/latest/APIReference/API_Sign.html`
- EKS Pod Identity:
  `https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html`
