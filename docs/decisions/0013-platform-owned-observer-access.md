# ADR-0013: Platform observer access is separate from workload authority

- **Status:** Proposed
- **Date:** 2026-07-14
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `omnius`, `platform-design`)
- **Builds on:** [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0011](0011-platform-products-and-executable-paths.md), and
  [ADR-0012](0012-capability-readiness-profiles.md)

## Context

The `standard-http-service/v2` path closes its workload resource envelope to six kinds and
requires proof that its preview Realm contains no workload-owned RBAC. Omnius now has a
read-only Kubernetes transport that must list the complete admitted and forbidden inventory in
one exact Realm. Native Kubernetes RBAC cannot restrict an ordinary `list` verb with
`resourceNames`, and runtime Pod and ReplicaSet names are not known before the list.

The narrow native-RBAC shape therefore requires a `RoleBinding` inside the target namespace. It
binds a fixed read-only `ClusterRole` to a WorkOrder-specific observer ServiceAccount outside the
Realm. The current contract rejects every RoleBinding in the Realm, so it cannot simultaneously
require least-privilege namespace-scoped observation and prove that observation through native
Kubernetes authorization.

Replacing the RoleBinding with a ClusterRoleBinding would make list authority cluster-wide. Giving
the observer an admin credential and relying only on client-side namespace checks would turn a
transport defect into cross-Realm read access. Both alternatives violate the Dark Factory boundary.

## Decision

### D1 - Separate workload inventory from platform control inventory

A PlatformPath keeps a closed **workload desired inventory**. Platform-owned access, policy, and
reconciliation objects belong to a separate **platform control inventory**. Control objects do not
become workload-authorable merely because they exist in the Realm.

The first path continues to admit exactly its six workload kinds. It additionally declares one
observer access binding in its delivery profile. The binding is created only by the trusted
platform control plane and is absent from the source repository path authored by the worker.

### D2 - Native observer RBAC has one exact shape

For one WorkOrder, the admitted shape is:

- one dedicated ServiceAccount in the platform observer namespace, named from the WorkOrder;
- one Role in `argocd` granting `get` on the exact WorkOrder-derived Application, plus its exact
  RoleBinding to that ServiceAccount;
- one per-WorkOrder ClusterRole granting `get` on the exact derived Namespace, plus its exact
  ClusterRoleBinding;
- one versioned shared ClusterRole granting only `list` on the closed observer kind set;
- one RoleBinding in the preview Realm binding that shared ClusterRole to the exact observer
  ServiceAccount.

No platform-owned rule grants Secrets, ConfigMaps, AppProjects, non-resource discovery URLs, watch,
logs, exec, port-forward, proxy, impersonation, token minting, or any mutation verb. A workload Role
remains forbidden. Any extra RoleBinding, subject, verb, API group, resource, or namespace fails
closed.

Kubernetes commonly grants `/api` and `/apis` discovery to every authenticated principal through the
built-in `system:discovery` binding. The native profile does not claim that inherited permission can be
denied portably. Instead, the observer transport exposes no discovery operation, recordings prove that
it was not invoked, and attestation proves that the platform-owned access bundle adds no
`nonResourceURLs` rule. Any inherited authority is recorded separately from the authority granted by
the bundle.

### D3 - Credential scope and server-side authority are both required

The observer uses a WorkOrder-specific TokenRequest credential with a single API audience and a
maximum ten-minute lifetime. Its client-side scope binds the API server, CA digest, Application,
Namespace, kind set, operation set, and absolute observation deadline.

Client-side scope does not prove bearer-token authority. Independent admission evidence must bind
the live ServiceAccount, Role/ClusterRole rules, RoleBindings/ClusterRoleBinding, token audience,
the platform-granted negative authorization matrix, and any inherited effective authority. Missing or
stale server-side evidence produces UNKNOWN and no delivery evidence. A forbidden resource or verb
being allowed fails closed; inherited Kubernetes discovery is the sole declared portability exception
and is safe only while the transport cannot invoke it.

### D4 - Observation verifies its own access binding

The Realm observer may ignore no arbitrary RBAC. It must read the RoleBinding collection and accept
exactly the deterministic platform-owned observer binding. It verifies name, namespace, ownership
labels, immutable role reference, and the single expected ServiceAccount subject. Every other Role
or RoleBinding remains a containment failure.

The final evidence manifest binds the verified access-policy digest and collection snapshot. Two
complete inventory passes must agree on security-relevant state before evidence is emitted.

### D5 - Lifecycle and compensation own observer-access cleanup

Access objects are created before observation only after repository authorization, admission, and
compensation registration. Token expiry is not cleanup. Completion, cancellation, failure, and
expiry revoke the observation lease and remove the WorkOrder-specific bindings. A separate reaper
compares live bindings with terminal WorkOrders and removes or parks orphans through the same
audited control path.

### D6 - This decision does not activate readiness

ADR acceptance authorizes downstream contract design, not execution. A new Omnius requirement
slice and a new immutable platform delivery-profile revision must encode the exact shape. The P0
readiness profile remains draft until real-cluster positive and negative RBAC probes, independent
admission evidence, cleanup/recovery probes, protected-path enforcement, and human activation all
pass.

## Consequences

**Positive**

- Native Kubernetes RBAC limits list authority to one Realm without granting cluster-wide reads.
- The worker still cannot author RBAC or expand its workload resource envelope.
- The observer proves both workload containment and the narrow control that lets it observe.
- Credential compromise is bounded by Realm, kind, verb, audience, deadline, and server-side RBAC.

**Costs and risks**

- Platform control inventory becomes a first-class contract surface with its own schemas and probes.
- A RoleBinding exists inside an otherwise workload-RBAC-free Realm and must be distinguished by
  exact provenance rather than a broad label exclusion.
- Native bearer tokens are not proof-of-possession credentials. Short TTL, private CA pinning,
  external placement, egress controls, and independent authorization evidence remain mandatory.
- Per-WorkOrder control objects and cleanup add lifecycle load; orphan detection is required before
  readiness.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Cluster-wide list through a ClusterRoleBinding | A stolen observer token reads every Realm. |
| Admin kubeconfig plus client-side namespace checks | Client defects become authority escalation. |
| Permit arbitrary platform-labeled RoleBindings | A forged label could hide privilege expansion. |
| Omit Roles/RoleBindings from observation | The observer could not prove absence of workload RBAC. |
| Authorization webhook in the first vertical | Valid later, but adds a new critical service before the native path is qualified. |

## Implementation map

| Component | Responsibility |
|---|---|
| `genai-enablement` | cross-repo authority decision and terminology |
| `omnius` | draft requirement slice, exact binding verifier, credential/session checks, lifecycle and evidence probes |
| `platform-design` | versioned observer-access contract, RBAC templates, admission policy, and negative authorization fixtures |
| Omniscience | indexes observed control state and outcomes; never grants or widens access |

## Required verification

- exact Application and Namespace reads succeed; foreign identities fail;
- all declared Realm list operations succeed and complete pagination under one deadline;
- Secret, ConfigMap, AppProject, watch, log, exec, port-forward, proxy, impersonation, TokenRequest,
  create, update, patch, and delete authorization all fail;
- transport recordings contain no discovery request, the platform-owned rules contain no
  `nonResourceURLs`, and inherited discovery authority is reported rather than misclassified as a
  portable denial;
- a changed role reference, extra subject, second RoleBinding, workload Role, stale token, wrong audience,
  foreign Realm, changed CA, or incomplete cleanup produces no evidence;
- cancellation and timeout revoke/remove access, and the orphan reaper detects a deliberately stranded binding;
- the workload desired inventory remains exactly the canonical six-kind envelope.
