# ADR-0018: PII Wall is a distributed, purpose-bound data boundary

- **Status:** Proposed
- **Date:** 2026-07-18
- **Deciders:** platform owner
- **Scope:** cross-repo (`genai-enablement`, `Omniscience`, `omnius`, `platform-portal`, and every
  synchronized-platform data producer or consumer)
- **Builds on:** [ADR-0003](0003-unified-sdlc-standard.md),
  [ADR-0007](0007-platform-portal-federated-surface.md),
  [ADR-0008](0008-ai-security-domain.md),
  [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0011](0011-platform-products-and-executable-paths.md),
  [ADR-0012](0012-capability-readiness-profiles.md), and
  [ADR-0017](0017-omniscience-mcp-v1-contract-and-severance.md)

## Context

The synchronized platform already has useful but fragmented privacy controls: tenant/workspace
isolation, secret redaction, no-PII audit fields, retention and deletion requirements, source-bound
portal views, and model/data classification inputs. They do not yet form one end-to-end personal-data
boundary.

The largest current exposure is at knowledge ingestion. Omniscience can decode, parse, chunk, and embed
source content before any shared PII gate. Personal data can therefore reach the authoritative document
record, chunks, vector and graph projections, archives, caches, logs, or an external embedding provider
before a downstream consumer has a chance to redact it. A model-context scan in Omnius or a portal
display filter cannot undo that propagation.

Conversely, a single central service through which every raw value must pass would become a
cross-tenant plaintext concentration point and a platform-wide availability and trust dependency. The
platform instead needs one protocol with enforcement at every component-owned boundary, closed failure
semantics, lifecycle receipts, and a visualization surface that never becomes a new PII store.

In this ADR, **PII** is an operational shorthand for personal data governed by a pinned platform policy.
It is not a legal conclusion, a consent decision, or proof of compliance with any jurisdiction.

## Decision if accepted

### D1 - Make the wall distributed, with one signed policy bundle

`genai-enablement` owns the cross-repository taxonomy, profile semantics, minimum contract schemas, and
work-package order. A designated platform policy publisher produces an immutable, signed
`PIIPolicyBundle`; component owners independently verify the exact revision and enforce it at their own
trust boundaries.

Raw personal data does not traverse a central platform plaintext proxy. Omniscience, Omnius, and every
future producer or consumer remain responsible for enforcement before their own storage, model,
tool, display, telemetry, and external-egress sinks. An unavailable, unknown, expired, or signature-
invalid policy fails closed for new processing.

### D2 - Use a closed operational taxonomy and fail closed on `unknown`

Every in-scope data envelope carries one policy-derived class:

```text
public
internal_non_personal
personal
sensitive_personal
prohibited
unknown
```

It also carries a transformation state:

```text
raw
redacted
pseudonymized
aggregated
```

Legal or business classifications map into this closed taxonomy in the signed policy bundle. Free-form
labels cannot grant access or reduce protection. Missing, conflicting, unsupported, or stale
classification is `unknown`; it never means non-personal.

Deterministic schema rules and exact/structured detectors are the enforcement floor. Statistical or
LLM classifiers may widen protection or route for review, but cannot by themselves downgrade
`personal`, `sensitive_personal`, `prohibited`, or `unknown`.

### D3 - Deliver three cumulative PII Wall profiles

The profiles describe platform capability maturity and per-flow admission. They do not replace Omnius
assurance profiles P0-P3.

| Profile | Admission boundary | Default failure |
|---|---|---|
| `PW0 PII-free` | only `public` or `internal_non_personal`, or deterministically redacted data, may enter durable stores, embeddings, model context, tools, telemetry, portal projections, or external egress | block or quarantine before the first protected sink |
| `PW1 Pseudonymized` | PW0 plus policy-approved irreversible redaction or tenant/purpose-scoped tokenization; the receiving component has no re-identification capability | block, quarantine, or fall back to PW0 |
| `PW2 Purpose-bound raw` | PW1 plus an explicit, short-lived `PIIPermit` binding exact purpose, fields, source, sink, actor/workload, tenant/workspace, provider, retention, and expiry | deny; there is no implicit emergency or model override |

Profiles are cumulative: a PW2 flow still needs PW0 classification and PW1 transformation controls
where those controls apply. The platform starts with PW0 as the default target. This ADR does not
activate PW0, PW1, or PW2 in runtime.

### D4 - Enforce before every irreversible or external boundary

The wall has independent gates at:

1. source registration and ingestion;
2. decode/parse and before any durable raw-document write;
3. before chunking, embedding, vector/graph projection, cache, archive, or backup propagation;
4. retrieval and inter-component projection;
5. Omnius task intake, prompt/context assembly, model-provider routing, and tool input/output;
6. memory, experience, outcome, log, trace, metric, and audit persistence;
7. portal rendering, correlation, export, and delegated-control submission; and
8. every external provider, webhook, connector, download, or other egress.

A downstream scan is defense in depth, not evidence that an upstream gate can be omitted. If a gate
cannot determine the effective policy, scope, or classification, it blocks or quarantines before its
sink and emits a non-identifying receipt.

### D5 - Standardize data, permit, and evidence contracts

The minimum cross-repository contracts are:

```text
DataEnvelope {
  envelope_id, tenant_id, workspace_id?, source_ref, subject_ref?,
  data_class, transform_state, field_manifest, policy_revision,
  purpose_id?, permit_id?, produced_at, expires_at?, integrity
}

PIIPermit {
  permit_id, tenant_id, workspace_id?, purpose_id, actor_or_workload,
  source_constraints, allowed_fields, allowed_sinks, provider_constraints,
  transform_requirements, retention_deadline, issued_at, expires_at,
  issuer, policy_revision, integrity
}

SanitizationReceipt {
  receipt_id, input_digest, output_digest?, policy_revision, profile,
  detector_revisions, transformations, disposition, coverage,
  produced_at, producer, integrity
}

PrivacyCoverage {
  component_id, tenant_id, workspace_id?, policy_revision, profile,
  boundary_set, covered_stores, uncovered_or_unknown, observed_at,
  freshness_deadline, source_health, integrity
}

DeletionReceipt {
  request_id, tenant_id, workspace_id?, subject_ref?, policy_revision,
  store_class, covered_artifacts, excluded_or_pending, disposition,
  produced_at, producer, integrity
}
```

Receipts contain digests, counts, stable pseudonymous references, and failure reasons, never the raw
value they prove was handled. Cross-component correlation uses explicit published ids only.

### D6 - Keep pseudonymization scoped and re-identification separate

PW1 tokenization is tenant-scoped and, where a workflow needs correlation, purpose- or WorkOrder-scoped.
The same input must not create a globally linkable platform identity. A component that consumes a
pseudonymized envelope does not receive the re-identification key or service capability.

If reversible tokenization is later required, the mapping lives in a separately authorized,
tenant-scoped vault with independent identity, audit, expiry, and deletion. Neither Omnius agents,
Omniscience retrieval, nor Platform Portal receives a general reveal operation.

### D7 - Bind raw processing to purpose, fields, sink, provider, and lifetime

PW2 is admitted only with a valid `PIIPermit` minted outside the agent and outside the content being
processed. The permit is exact and widen-never: a caller cannot add fields, sinks, providers, purposes,
tenants, or time. A permit for deterministic processing does not permit model context; model use must be
named as an allowed sink and separately supported by the selected provider policy.

PW2 output cannot enter learning, Experience, shared memory, prompt caches, general search, or portal
detail unless a new policy evaluation produces a PW0/PW1-safe envelope. Permit expiry stops new reads
and processing and begins the owner-defined cleanup/retention path.

### D8 - Make lifecycle coverage explicit across every store class

Classification, retention, export, correction, and deletion obligations propagate through raw
documents, parsed structures, chunks, Postgres, Neo4j, Qdrant, object storage, caches, outboxes,
checkpoints, prompts, model/provider logs, task artifacts, memory, telemetry, archives, and backups.

An owner may report completion only for the exact store set named in its `DeletionReceipt`. Partial,
unavailable, immutable-retention, or backup-pending states remain explicit. Immutable audit may retain
non-identifying proof that an operation occurred, but not the deleted PII value. Backup expiry and
restore-time re-deletion are part of coverage, not silently omitted.

### D9 - Keep component ownership explicit

| Owner | PII Wall responsibility |
|---|---|
| `genai-enablement` | ADR, taxonomy/profile semantics, minimum schemas, policy-publication contract, dependency plan, drift checks |
| `Omniscience` | pre-ingest classification, quarantine, transformation before persistence/chunk/embed, projection labels, retrieval/egress revalidation, knowledge-store lifecycle receipts |
| `omnius` | task/context classification, prompt and provider admission, tool input/output and result scanning, safe memory/experience/telemetry persistence, purpose-bound execution |
| `platform-portal` | Privacy Center composition, coverage and receipt visualization, owner-delegated privacy intents, reconciliation and portal audit |

No component can declare a sibling compliant, clean, deleted, or safe. It can verify a signed sibling
receipt against its own admission contract.

### D10 - Make Platform Portal the Privacy Center, not the privacy authority

Platform Portal visualizes policy revision, active profile, boundary/store coverage, quarantine counts,
sanitization evidence, incidents, and export/deletion progress from owner-produced projections. It does
not ingest or reveal raw PII, re-run classification to produce an authoritative result, or infer a
green state from an absent event.

Privacy controls are owner-advertised intent contracts such as request quarantine, reprocess, export,
correction, or deletion. The portal authenticates, scopes, step-ups, audits, and submits; the owner
re-authorizes, performs or rejects, and returns the receipt. Timeout is `pending_reconciliation`, never
success. There is no generic portal override or reveal control.

### D11 - Require local adoption, readiness, and real-boundary evidence

Acceptance of this ADR would authorize component owners to adopt the boundary, not activate it.
Implementation requires:

1. an accepted local adoption ADR where project policy requires one;
2. a human-ready exact capability/task slice;
3. pinned taxonomy, detector, policy, schema, and provider revisions;
4. deterministic negative and adversarial probes at the real enforcement point;
5. lifecycle and severance evidence; and
6. owner-produced release receipts consumed independently by downstream components.

Fixture success, a portal badge, a classifier model result, or a document status cannot activate a
profile or prove PII absence.

## Invariants

- **PII-1 — classify before propagation:** unknown or unadmitted data cannot reach a protected sink.
- **PII-2 — raw is purpose-bound:** raw personal data requires an exact, expiring external permit.
- **PII-3 — least disclosure:** components receive only allowed fields and transformation state.
- **PII-4 — no agent self-authorization:** content, prompt, tool, or agent output cannot lower policy.
- **PII-5 — tenant and purpose isolation:** tokens, caches, correlation ids, and receipts do not create
  cross-tenant or unintended cross-purpose linkage.
- **PII-6 — lifecycle completeness is scoped evidence:** partial coverage never becomes “deleted” or
  “clean”.
- **PII-7 — telemetry is not an escape path:** logs, traces, metrics, audit, and errors contain no raw
  PII.
- **PII-8 — egress is a first-class sink:** external providers and exports require explicit admission.
- **PII-9 — portal is view/proxy only:** visualization and intent submission never become privacy
  authority.
- **PII-10 — failure is visible and closed:** unavailable, stale, unknown, incompatible, and partial
  never collapse to safe, empty, or complete.

## Consequences

- The first useful delivery can be PW0 and does not wait for a token vault or raw-data workflow.
- Omniscience must move enforcement ahead of its current decode/parse/chunk/embed propagation path.
- Omnius gets a distinct personal-data boundary; `SPEC-SE` remains the credential/secret boundary.
- The portal becomes the detailed privacy operations surface without accumulating raw personal data.
- Components must carry more provenance and lifecycle metadata and retain non-identifying receipts.
- False positives may quarantine work. That operational cost is preferred to silent propagation and is
  measured before any policy is relaxed.

## Non-goals

- Declaring legal compliance, lawful basis, consent, data-controller/processor roles, or jurisdictional
  retention rules.
- Building a universal enterprise DLP product or guaranteeing detection of every personal datum.
- Creating a central raw-data lake, cross-tenant identity graph, or general re-identification service.
- Replacing component tenant isolation, secrets management, authorization, or owner retention policy.
- Activating runtime gates, external providers, deletion, exports, or production changes through this
  proposed ADR.

## Alternatives considered

- **Portal-only masking:** rejected because data has already propagated before display.
- **Omnius-only prompt scanning:** rejected because it cannot protect Omniscience storage and embedding.
- **One central plaintext proxy:** rejected as a concentration point and hard platform dependency.
- **Best-effort tags without receipts:** rejected because downstream consumers cannot distinguish
  coverage, freshness, or failure.
- **LLM-only classification:** rejected as non-deterministic authority; it may only widen or advise.

## Required evidence before any profile is active

- seeded and structured PII fixtures are blocked or transformed before every selected real sink;
- `unknown`, policy outage/skew, detector failure, forged scope, expired permit, field/sink widening,
  and provider mismatch fail closed;
- raw values are absent from persisted documents/chunks/vectors/graph, model context, tool transcripts,
  memory, logs, traces, metrics, audit, portal DTOs, and receipts for PW0;
- cross-tenant and cross-purpose pseudonym correlation fails;
- retrieval and restore cannot resurrect deleted or disallowed data outside declared pending coverage;
- owner outage and partial lifecycle coverage render unavailable/partial, never safe or complete; and
- removing Platform Portal does not disable owner enforcement or privacy operations.

## Adoption map

- Omniscience: `SPEC-PII` owns ingestion, knowledge-store, projection, retrieval, and lifecycle
  enforcement.
- Omnius: `SPEC-PII` owns task/context/model/tool/egress and learning/telemetry enforcement.
- Platform Portal: `SPEC-PII` owns the Privacy Center and owner-delegated privacy-intent experience.
- `genai-enablement`: `SP-60` through `SP-63` order governance, component delivery, and portal
  composition without granting sibling write authority.
