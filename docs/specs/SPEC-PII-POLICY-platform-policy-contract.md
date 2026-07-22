# SPEC-PII-POLICY — Platform PII policy, profile, and receipt contract

**Specification type:** Capability SPEC  
**Status:** Ready  
**Owner:** `genai-enablement` platform governance  
**Governing decisions:** [ADR-0018](../decisions/0018-pii-wall-purpose-bound-data-boundary.md),
[ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md), and
[ADR-0012](../decisions/0012-capability-readiness-profiles.md)  
**Work package:** `SP-60`  
**Authority:** development and conformance only; no profile activation, permit issuance, provider use,
deletion, export, or production policy publication

## Goal and boundary

Define the minimum content-addressed protocol that lets every component enforce the same PII taxonomy
without sending raw values through a central proxy. This SPEC owns schemas and compatibility semantics;
each data owner remains responsible for enforcement and evidence at its own boundary.

## Requirements

[REQ-PII-POL-1] A `PIIPolicyBundle` has one immutable revision and binds taxonomy, PW0/PW1/PW2 profile
rules, detector manifests, transformations, purposes, source/sink classes, field rules, retention,
permit constraints, compatibility, issue/expiry times, signer and integrity. Unknown fields may widen
protection but cannot relax a known rule. **Fallback:** invalid, expired, future, unsigned, incompatible,
or partially loaded bundles are unavailable and block new protected processing.

[REQ-PII-POL-2] The closed data classes are `public`, `internal_non_personal`, `personal`,
`sensitive_personal`, `prohibited`, and `unknown`; transformation states are `raw`, `redacted`,
`pseudonymized`, and `aggregated`. Free-form labels never grant admission. **Fallback:** unmapped,
conflicting, or unsupported classification becomes `unknown`.

[REQ-PII-POL-3] `PW0`, `PW1`, and `PW2` are cumulative profiles. A consumer may enforce a stricter
profile but cannot downgrade the effective profile selected by human/owner policy. **Fallback:** no
valid selection admits only independently proven non-personal read-only operation.

[REQ-PII-POL-4] A `DataEnvelope` binds tenant/workspace, subject/source, purpose, data class,
transformation, allowed fields and sinks, policy revision, lineage, issue/expiry, coverage and integrity.
The value and the policy metadata cannot be separated during propagation. **Fallback:** an incomplete or
foreign-scope envelope is rejected before the next sink.

[REQ-PII-POL-5] A `PIIPermit` is short-lived, single-purpose and exact: issuer, subject, fields, source,
sink/provider/tool, actor/workload, tenant/workspace, retention, policy revision, issue/expiry and nonce
are mandatory. It cannot be widened, refreshed by a consumer, or reused for another sink. **Fallback:**
deny raw processing; there is no ambient administrator or model override.

[REQ-PII-POL-6] `SanitizationReceipt`, `BoundaryDecisionReceipt`, and `DeletionReceipt` are
non-identifying, content-addressed and scope/revision/time/coverage bound. They record disposition and
store/boundary identifiers but contain no raw value, reversible token, stable cross-purpose fingerprint,
prompt excerpt, or provider payload. **Fallback:** an unsafe receipt is rejected and cannot prove
coverage.

[REQ-PII-POL-7] Lifecycle evidence is per store and projection class. `complete`, `pending`, `excluded`,
`immutable_retention`, `backup_pending`, `failed`, and `unavailable` remain distinct; aggregation cannot
turn partial coverage into `deleted` or `clean`. **Fallback:** missing required receipts keep the parent
operation partial.

[REQ-PII-POL-8] Policy publication is producer/consumer severable. Components pin an exact schema major,
policy revision and signer trust profile; skew, outage, revocation and recovery have deterministic
fixtures. **Fallback:** last-known policy may describe historical records but cannot authorize new
processing past its freshness/expiry boundary.

[REQ-PII-POL-9] The contract contains no raw-data API and grants no central enforcement authority.
Platform Portal receives policy metadata and owner receipts only; Omniscience and Omnius enforce locally;
Barbarossa admits management evidence under the same boundary. **Fallback:** a consumer asking the policy
publisher to classify or proxy a raw value is non-conformant.

[REQ-PII-POL-10] Publication is a separate human-controlled transition. A repository schema, fixture,
signature test, or ready task cannot make a policy active. **Fallback:** absent immutable publication and
owner adoption receipts leave every runtime profile inactive.

## Interfaces

```text
PIIPolicyBundle
DataEnvelope
PIIPermit
BoundaryDecisionReceipt
SanitizationReceipt
DeletionReceipt
PrivacyCoverageEnvelope
```

The development task publishes versioned JSON Schemas, canonical fixtures, a deterministic validator,
compatibility rules and a manifest. Signing-key provisioning and an active policy publication are
outside this SPEC's development authority.

## Verification

- **P-PII-POL-1 schema closure:** unknown class/profile/disposition values and missing scope, time,
  coverage or integrity fields fail.
- **P-PII-POL-2 widen-only:** every attempted downgrade, field/sink widening, expiry extension and
  cross-purpose/tenant replay is rejected.
- **P-PII-POL-3 no-raw receipts:** seeded PII, reversible tokens and fingerprints never survive any
  receipt or coverage projection.
- **P-PII-POL-4 lifecycle aggregation:** mixed store states remain partial and cannot become deleted.
- **P-PII-POL-5 skew/severance:** unknown major, stale/revoked policy and publisher outage block new
  processing without erasing historical provenance.
- **P-PII-POL-6 non-activation:** fixtures and validator success do not expose an active policy or permit
  issuer.

## Development exit

Exit requires the schema bundle, manifest, canonical positive/negative fixtures, deterministic validator,
compatibility matrix, generated digest, and passing offline probes. Live policy publication, trust-key
provisioning, component activation and privacy claims remain separately approved owner transitions.

