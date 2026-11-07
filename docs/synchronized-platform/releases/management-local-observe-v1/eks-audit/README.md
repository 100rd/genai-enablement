# EKS deployment audit — 2026-11-06

**Result: deployed, acceptance failed.** This is an additive observation of the
`management-local-observe-v1` installation in context `nonprod-euc1`, namespace
`splatform`, inspected around 22:24–22:36 UTC. It is not a new successful qualification
and does not reuse local Docker receipts as cluster evidence.

## What passed

- Kubernetes: 7/7 Deployments, 6/6 StatefulSets ready; 3/3 migration Jobs complete.
- Actual Portal browser login for alpha and beta; each loaded its own real Omniscience
  graph with 3 entities and 2 edges. Alpha's request for beta's workspace returned
  `NEEDS MAPPING` without foreign graph/provenance. MCP contract shown: `1.0.0`.
- Alpha's Barbarossa and Omniscience connection cards were connected/healthy with fresh
  timestamps. Repeated owner reads advanced persisted observation timestamps on the
  30-second cadence. The signed snapshot has all three components healthy.
- Control displayed two resolved startup cases, recorded evidence links, an empty
  pending queue and three cancelled jobs with zero claim attempts. The case-to-Observe
  evidence path showed unhealthy/healthy history. No accepted assessment was visible.
- Beta's Control access was denied by the configured alpha-only Barbarossa allowlist.
  Both connection cards also denied status through that projection; beta's own
  Omniscience knowledge still worked.
- Eleven live signed-identity checks passed: own read `200`; absent/invalid signature,
  expiry, audience and role `401`; wrong scope, foreign tenant and tenant substitution
  through query/header `403`. Signing material stayed inside the existing backend Pod.

See [verification.json](verification.json), [signed checks and owner status](identity-and-status.json),
[Control screenshot](control-alpha.png) and [beta knowledge screenshot](observe-beta.png).
Screenshots are actual browser captures, not fixture renders. The graph is seeded test
topology; it is not a discovery of all EKS resources.

## Findings and owner queue

| ID | Owner | Observed problem | Required verification after correction |
| --- | --- | --- | --- |
| EKS-01 | Deployment | All three PostgreSQL data volumes and Neo4j `/data` use `emptyDir`, without PVC templates. Pod replacement discards these volumes. Only NATS and Qdrant have Bound PVCs. | Preserve current data before migration to persistent volumes; then demonstrate controlled Pod replacement retains identities, knowledge, cases, jobs, leases and reservations. Pin PostgreSQL instead of mutable `latest` (logs report 18.6). |
| EKS-02 | Deployment / Barbarossa | Runner state is `unknown`, `last_seen_at=null`; Control says `Awaiting first heartbeat`. No AI attempts/results were observed. Host port `127.0.0.1:18082` is occupied by the local Docker installation. | Choose an unambiguous cluster runner connection, confirm heartbeat and execute one controlled fault → case → Codex → Portal → recovery drill. Verify deduplication, leases and durable call limits. Do not assume the local runner serves EKS. |
| EKS-03 | Deployment | PostgreSQL ingress policies allow 5432 without a source selector. The broad Portal egress policy also selects frontend/Keycloak. A TCP probe from the existing frontend Pod connected to all three PostgreSQL services. | Restrict source/destination by component role and demonstrate intended callers succeed while frontend/cross-component callers are denied. The probe sent no DB credentials or SQL; it proves network reachability, not authenticated data access. |
| EKS-04 | Barbarossa / Deployment | Live observations claim `failure_domain=shared-host`, `shared_fate_with_subject=true`. Observer/Barbarossa/Omniscience API are on one node; Portal and Neo4j are on another. | Make the observation profile/provenance describe actual placement, then requalify it. Same availability zone does not establish a shared host or HA. |
| EKS-05 | Deployment | Observer started before migration completion and logged three persistence errors. Barbarossa API previously exited because prepared knowledge context could not be persisted. Portal frontend preceded its migration and backend restarted twice. Current workloads have recovered. | Add an explicit migration/startup completion barrier; verify a rollout without these persistence failures and verify context is available to analysis. |
| EKS-06 | Portal | `POST /api/auth/logout` returns `307 Location: https://localhost:3000/login`. Browser sign-out invalidated the session but did not complete navigation to the deployed login. | Build redirects from the configured public origin and verify real browser logout/login behind the Gateway. The existing login route already uses `FRONTEND_ORIGIN`. |

Direct receipts: [storage and data mounts](storage.json),
[frontend TCP connectivity](frontend-db-network.json), [logout response](logout-routing.json),
and [sanitized placement, startup errors and local listener](deployment-details.json).
The first four findings prevent accepting the current EKS installation; the rollout and
logout defects must also be closed before recording the complete user-journey acceptance.
Startup errors are historical observations, not a claim of an ongoing outage.

## Revision and evidence boundaries

The deployed image tags and Helm app versions select these tested source revisions:

| Component | Source revision |
| --- | --- |
| Barbarossa | `1c6335656b348dbd9025aa82d0cb730b442604dd` |
| Omniscience | `639c52dac220b461d286b86a6fdeb36cf89300a4` |
| Portal | `1389aae9112ba03696fb3bc99560e970887d3241` |

This confirms observed deployment configuration, not a reproducible image-build attestation.
The source merge/CI record remains in [merge-readiness](../merge-readiness/verification.json).
All Services are ClusterIP; no Service/HTTPRoute exposes the runner listener on 8082.
No claim about access from networks outside the current connected environment is made.

No cluster resource, chart, application source, secret or network policy was modified.
Existing test accounts were used for login; both created SSO sessions were logged out.
Temporary local credential material was removed. The access-audit agent retrieved Secret
JSON for a metadata/key-name projection; values were not decoded or emitted by that agent.
The lead extracted only the existing test credentials needed for the browser checks;
credentials/tokens/keys are not included in this receipt.

No deliberate fault, DB Pod replacement, schema write, AI invocation or recommendation
execution was performed. Persistent restart behavior, complete AI recovery, effective DB
grants, default-ServiceAccount RBAC and HA are not qualified by this audit. The case UI
also reported no published workspace evidence; the cause was not diagnosed here.

The original local installation's 6 cases / 4 assessments / 6 reservations remain a
separate historical result. They are not the EKS counters. Raw audit notes and additional
browser captures remain under the ignored `.local-observe/eks-verification/` directory.
[Artifact hashes](artifacts.json) cover the portable evidence attached here.

## Agent review

Runtime inspection used `gpt-6.1-sol` (about 3 minutes / 4,000 generated tokens estimated,
zero command retries). Access inspection used `gpt-6-luna` (about 7 minutes / 4,300 tokens
estimated, one local projection-query correction). These are estimates, not billing data.
The lead reviewed both complete reports, independently checked the data mounts and policy
rules, ran the frontend TCP probe and signed-identity matrix, and performed the actual
two-tenant browser journeys. The lead corrected the access report's inaccurate distinction
between retrieving Secret JSON and reading values; no secret values were published.

The audit updates coordinator status only. Application fixes and deployment changes remain
with their owners; the successful local qualification has not been overwritten.

Independent evidence review by `gpt-6-luna` found three missing portable supporting
receipts (placement, startup errors, local listener). These are now attached in
`deployment-details.json`; no runtime findings were withdrawn. Estimated review cost:
6 minutes / 2,200 tokens, not measured billing. Both coordinator drift checks passed;
54 portfolio tests passed and the synchronized-platform suite completed 37 tests with
one skip. These checks validate the tracking changes, not EKS runtime acceptance.
See [coordinator validation](coordinator-validation.json).
