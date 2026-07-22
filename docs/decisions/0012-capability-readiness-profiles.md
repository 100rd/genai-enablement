# ADR-0012: Capability readiness is authorized through immutable requirement profiles

- **Status:** Accepted
- **Accepted by:** `@100rd` through approval of the P0 implementation sequence on 2026-07-13
- **Date:** 2026-07-13
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `omnius`, and every component executing task SPECs)
- **Builds on:** [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0010](0010-goal-oriented-organizational-dark-factory.md), and
  [ADR-0011](0011-platform-products-and-executable-paths.md)
- **Partially supersedes:** ADR-0009 D4 for capability readiness and D8 for the first omnius vertical

## Context

ADR-0009 gives a capability SPEC one lifecycle: `draft -> ready -> implemented -> verified`.
That is safe when a SPEC is a uniformly buildable unit. Omnius capability SPECs instead contain
cumulative P0 through P3 behavior in one document. Marking one such SPEC `ready` to implement a P0
slice also appears to authorize its unselected P1/P2/P3 mechanisms, deferred constants, and assurance
claims. Leaving it `draft` prevents a task SPEC from citing the requirements that are ready.

The first vertical exposed the ambiguity. `standard-http-service/v1` needs a bounded set of WorkOrder,
Realm, probe, intake, execution, verification, transaction, and outcome requirements. It does not need
Temporal, a hardened microVM, an independent verifier host, injected agent credentials, Jira, production
mutation, or auto-merge. A filename-level readiness flag cannot express that boundary.

The previous first class, reversible Terraform-module work, is also superseded by the later accepted
product decision in ADR-0011. Terraform remains an execution mechanism and may become another admitted
path, but the first product vertical is `standard-http-service/v1` in a `preview-*` Realm.

## Decision

Introduce a versioned **CapabilityReadinessProfile** as the only authority that makes selected
requirements from multi-profile capability SPECs executable.

### D1 - Readiness binds exact requirements, probes, and revisions

A profile contains at least:

```yaml
apiVersion: darkfactory.platform/v1alpha1
kind: CapabilityReadinessProfile
metadata:
  name: p0-standard-http-service-v1
  version: 1
  status: ready
spec:
  assuranceProfile: P0
  scope:
    platformPath: standard-http-service/v1
    realms: [preview-*]
  authority:
    approvedBy: human-codeowner
    approvedAt: RFC3339
    decisionRef: immutable-review-or-ADR-reference
  capabilities:
    - repository: 100rd/omnius
      path: specs/SPEC-WO-goal-oriented-workorders.md
      revision: immutable-git-revision
      requirements: [REQ-WO-1, REQ-WO-2]
      probes: [P-WO-1, P-WO-2]
      hardDependencies: []
  forbiddenActions: []
  evidenceTtl: ISO-8601-duration
```

The concrete schema may add fields but may not omit the immutable SPEC revision, exact REQ and probe
sets, hard dependencies, scope, assurance profile, status, or human authority. Wildcard REQ sets and
mutable branch references are invalid. A task SPEC pins the profile revision and digest as well as its
PlatformPath revision.

The profile's `pathBundle` is a requested pin, not independent observation. Compilation must also consume
an opaque platform-owner publication issued only after an allowlisted external verifier returns exact
boolean true for a closed binding of repository/root/Git revision, deterministic bundle
digest/algorithm/index, exact path and artifact digest, lifecycle/catalog state, Realm-admission evidence,
owner, CODEOWNERS path/revision, publication origin/revision, and verifier reference. Compilation rejoins
the publication to the profile's exact bundle and path. Missing, raw, copied, foreign, verifier-mismatched,
or join-mismatched publication evidence parks for both draft and ready compilation.

Compilation must join each capability entry to an independently observed immutable revision manifest.
Its closed publication binds one capability namespace, repository, SPEC path, exact Git SHA, SPEC blob
digest, REQ/probe ids, origin, publication revision, and verifier reference. An allowlisted external
verifier must return exact boolean true before an opaque verified-manifest capability is issued; intake
rejoins that capability to the profile's exact repository/path/revision. Lists copied from the profile,
raw/caller-constructed bindings, or ids discovered only in a newer worktree are not membership evidence.
An unavailable, malformed, foreign-origin/namespace, verifier-mismatched, revision/source-mismatched, or
incomplete manifest parks.

Caller-owned probe status maps are not a compiler input or readiness evidence. `ready` compilation also
requires one externally verified closed evidence publication bound to the exact profile
name/version/path/revision/digest, platform path and bundle revision/digest, assurance profile, concrete
in-scope Realm, declared evidence TTL, canonical observation and expiry, real-path/readiness eligibility,
complete selected probe set, each exact probe revision and immutable evidence reference/digest, the evidence
manifest digest, publication origin/revision, and verifier reference. Only exact boolean true from an
allowlisted external verifier issues the integrity-sealed opaque evidence capability. Missing, raw, copied,
foreign, stale-at-or-after-expiry, future-dated, partial/extra/non-pass, revision-mismatched, or
post-verification-modified evidence parks. Draft status observations remain non-authorizing.

Every external authority capability consumed by compilation—the platform-contract publication,
capability-revision manifests, human readiness-profile publication, probe-evidence publication, and the
delivery trust-chain capability—must remain byte-equivalent to the binding its gate verified. Each gate
snapshots and revalidates its closed binding across the external verifier callback and issues an opaque
process-local integrity seal. The readiness compiler rejects an absent/invalid seal or any post-issuance
field/nested-model mutation; delivery trust-anchor/store materializers enforce the same check before use.
Frozen caller objects or an exact Python type alone are not immutability evidence.

### D2 - Unselected capability content remains draft and non-executable

A profile changes no source SPEC text or whole-document state. Requirements absent from the profile
remain draft even when another requirement in the same file is ready. A task cannot infer permission
from adjacency, dependency prose, a higher target profile, or an installed technology.

The whole-SPEC `ready` state from ADR-0009 remains valid only for a capability SPEC whose complete
requirement set is approved as one buildable unit. Multi-profile SPECs use readiness profiles.

### D3 - Profiles are human-owned, immutable, and fail closed

Only the component CODEOWNER may set a profile to `ready`. Agents may author a draft proposal and its
fixtures, but cannot approve it or change its authority, REQ set, probe set, scope, forbidden actions,
or assurance profile during the execution it governs.

The transition is not established by the profile's own `approvedBy` field. A closed publication binds
the profile name/version, repository/path, exact Git revision, canonical document digest, ready status,
authority fields, CODEOWNERS path/revision, approval revision, publication origin/revision, and verifier
reference. Only an allowlisted external verifier returning exact boolean true may issue the opaque
publication capability accepted by compilation. Compilation rejoins that capability to the independently
observed path/revision and exact document digest/identity/authority; missing, raw, copied-invalid,
foreign-origin, verifier-mismatched, or join-mismatched publication evidence parks. Draft proposals remain
inactive and need no publication capability.

Changing a cited SPEC or probe invalidates the pin; it does not update the profile silently. The owner
issues a new profile version after review. Missing revisions, revision manifests, references, probes,
dependencies, expiry, or authority make intake park before mutation.

Realm scope may use an exact Realm ID or one bounded terminal `-*` prefix pattern needed for a
WorkOrder-derived disposable Realm. Blanket, leading, interior, repeated, or suffix-bearing wildcards are
invalid. Intake matches this pattern against the independently derived effective Realm, not task
frontmatter. The signed envelope retains the exact path, Realm scope, evidence TTL, and forbidden actions;
the execution compiler verifies the envelope signature and exact profile binding before adapter
resolution, so it cannot replace profile-owned forbidden actions with a caller-selected set.

Profile lifecycle is:

```text
draft -> ready -> superseded
             \-> expired
```

`implemented` and `verified` remain evidence states of capability requirements, not profile states.

### D4 - Profiles cannot manufacture assurance

Readiness authorizes implementation; assurance certification proves that the selected controls work on
the real path. A ready P0 profile does not make P0 GREEN. Contract conformance verifies the profile and
implemented obligations, while assurance certification continues to gate activation, promotion,
autonomy widening, and auto-merge.

Mechanism-specific P1/P2 requirements cannot be pulled into P0 merely because the mechanism is already
installed. Conversely, a P0 adapter is admissible only if it satisfies the selected P0 property probes.

### D5 - Experimental paths may gather evidence under a ready profile

The first revision of a PlatformPath cannot already have the operational evidence required for
`validated` or `approved`. A readiness profile may admit an `experimental` path only when all of the
following hold:

- the Realm is non-production and disposable;
- human landing is mandatory and auto-merge is off;
- the action and probe catalogs are closed and pinned;
- every external side effect has an idempotency claim and registered compensation;
- the profile states the reuse-factor hypothesis and promotion evidence to collect;
- production, shared-state, data, secret-bearing, and irreversible mutations are forbidden.

For mutation admission, `Realm-admitted pinned path revision` replaces a blanket requirement for an
`approved` path. The admission claim must come from the exact verified platform-owner publication, with a
non-catalog-only path in `experimental`, `validated`, or `approved` state and an exact Realm-admission
evidence digest. A caller/profile boolean or catalog projection is not authority. `validated` and
`approved` remain mandatory where Realm policy says so.

### D6 - First implementation profile

The first profile is `p0-standard-http-service-v1`:

- input through authenticated in-cluster MCP/API;
- one existing source repository and one service;
- effective Realm `preview-<work-order-id>`;
- immutable SPEC, PlatformPath, policy, action, probe, and model/tool bundle pins;
- isolated/default-deny worker;
- deterministic verification outside the worker;
- Omnius idempotently opens a Draft PR, a human merges it, and CI/GitOps deploys from `main`;
- runtime Conditions of Done and compensation evidence determine completion;
- no Jira, runtime secrets, data migration, multi-repository mutation, production mutation, direct
  apply, direct deploy, push to `main`, or auto-merge.

Omniscience is optional planning enrichment; direct authoritative source queries are the severance
fallback. The initial deterministic HTTP path requires no LLM evaluator verdict.

## Consequences

**Positive**

- Agents receive the smallest exact executable contract rather than implicit permission over a large SPEC.
- P0 work can start without weakening future P1/P2/P3 requirements or overstating assurance.
- Readiness, implementation, and certification become separately auditable transitions.
- Experimental product paths can collect the evidence needed for validation without pretending to be approved.

**Costs and risks**

- Profiles add a governed artifact and compatibility validator.
- Every selected requirement and probe needs a stable identifier.
- SPEC changes require explicit profile supersession instead of silently flowing into active work.
- Over-fragmented profiles would recreate task planning at the capability layer; CODEOWNERS must keep profiles
  centered on reusable verticals.

## Implementation map

| Component | Responsibility |
|---|---|
| `genai-enablement` | canonical term and cross-repo authority contract |
| `omnius` | profile schema/validator, first local profile, intake pinning, conformance probes |
| `platform-design` | authoritative product/path/entity contracts and preview execution mechanisms |
| `Omniscience` | indexes profiles and observed state; never grants readiness |
| `multiqlti` | may consume ready profiles or propose drafts; cannot promote omnius readiness |

## Verification

Conformance fixtures must prove:

- a task cannot execute a REQ absent from its pinned readiness profile;
- a changed SPEC/probe revision invalidates the profile;
- blanket/interior-wildcard, missing, expired, dependency-incomplete, self-declared agent-approved, or
  unverified/profile-mismatched publication inputs park before mutation;
- a caller-owned all-pass map cannot replace the exact externally verified profile/path/Realm-bound probe
  result set; stale, future, partial, non-pass, wrong-revision, raw, or modified evidence parks;
- a ready P0 profile leaves P1/P2/P3 requirements unauthorized and their certification unchanged;
- an experimental path is admitted only in a matching disposable Realm with human landing and compensation;
- a profile cannot enable auto-merge or production by omitting explicit forbidden actions.
