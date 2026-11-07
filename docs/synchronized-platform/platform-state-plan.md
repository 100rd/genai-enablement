# Platform state → AI SRE and AI Security

Rebased: 2026-11-07. Owner of overall progress: genai-enablement.
Status: architecture and delivery plan; implementation incomplete; EKS acceptance not passed.

Scope: account `120736097561`, region `eu-central-1`, cluster `nonprod-euc1`, all namespaces.
AWS Config is excluded. Existing local-profile qualification keeps its original scope.

## Outcome and state model

Omniscience must answer, with evidence: what should exist, what exists, how it behaves,
what depends on it, what changed, and what is currently unknown. Its platform state is
an evidence-backed representation; the originating systems remain authoritative for
intent and observations. A resource inventory alone cannot establish service health.

Keep these layers distinct:

1. Desired: Git revision, rendered manifests/Helm inputs, declared policy and SLOs.
   Terraform configuration, successful apply state and Argo target/sync revisions are
   separate claims, not interchangeable desired-state authorities.
2. Observed: resource identity/incarnation, configuration, placement, status and access.
3. Operational signals: request success/latency, workload availability, saturation,
   relevant events and bounded log/trace evidence over an explicit time window.
4. Relationships: service → release → workload → Pod → Node → cloud instance;
   Service → load balancer, PVC → PV → volume, application → database.
5. Provenance and history: source, collection scope, observation/ingestion time,
   source checkpoint, completeness, freshness, changes, conflicts and evidence links.

AI hypotheses and recommendations remain separately attributed assessments. They do
not overwrite facts, resolve a case or establish that a service is healthy.

Stable service/environment/tenant identity must join these layers. Resource UID or
provider-native identity is distinct from a reusable name. Relationships carry their
source; inferred associations remain marked inferred. Missing ownership remains
unknown. A snapshot across sources is a version vector with observation windows,
not a claim of one atomic cloud-wide instant.

## Audited foundation and gaps

Audited selected worktrees, not stale main checkouts. This is a source audit, not a
new live EKS qualification. Dirty work is not merged or deployed by this plan.

| Component | Existing foundation | Missing for platform state |
|---|---|---|
| Omniscience, base `2272deca` | Go Kubernetes operator; NATS ingestion/outbox; PostgreSQL documents; Neo4j topology and temporal history; Qdrant search; tenant REST/MCP; Git/Terraform/tfstate/Kubernetes YAML parsing; source freshness | Parsers do not establish service-centric desired/runtime linkage. Need canonical evidence persistence/read API, generation/partition coverage, desired/observed/signal joins and explicit projection lag |
| Omniscience, reviewed working changes | Direct AWS EC2/VPC/security-group/EKS/ELB/RDS reads; operator identity and UID lifecycle fixes; 26 core kinds periodically reconciled; cloud-neutral evidence v1 wire contract | Source↔cluster authorization, source-scoped publisher credentials, optional CRD parity, obsolete relationship replacement/owner references, full collection receipts, API/publication. Historical cutoff for an already-superseded edge remains unverified |
| Barbarossa, base `c7131b3` plus working fixes | Durable cases/jobs/leases, bounded runner, validated evidence references, advisory assessments; profile/provenance isolation changes | Dynamic platform evidence intake, deterministic SRE/Security policies, resource/service projections, pinned state revisions and material-change deduplication |
| Portal, base `480c5ba` plus logout fix | Observe observations/evidence; Control cases, queue/history, runner and exact accepted results; tenant delegation | New profile/schema support, live service graph/default selection, desired-vs-observed and coverage/freshness views. Existing contracts are tied to the local profile |

Relevant owner code: Omniscience `operator/`,
`packages/core/src/omniscience_core/platform_evidence/`, `contracts/platform-evidence/v1/`;
Barbarossa `internal/localobserve/`, `internal/codexrunner/`;
Portal `backend/app/local_observe/`, `frontend/lib/runtime-profile.ts`,
`frontend/app/(shell)/control/LocalAnalysis.tsx`.
The narrow v1 evidence contract has six fixed baseline partitions; it is not a full
platform-state ontology. Extend through an explicit compatible/versioned contract,
without broadening existing receipts or weakening validation.

[Source verification](releases/management-platform-frankfurt-v1/source-checks/verification.json)
and the [progress register](../../portfolio/platform-activation-progress.json) retain
prior test/review evidence and unresolved findings. Existing generic document parsing
is useful input, not proof that desired-state reconciliation already works.

## Collection decision: hybrid, at three boundaries

**Source → collector:** pull establishes a baseline and repairs gaps; watch/events
accelerate changes. **Collector → Omniscience:** authenticated durable push of normalized
facts and complete collection manifests. The first deployment-generation path uses the
source-scoped HTTP admission endpoint with a retained collector outbox; HTTP success
follows the PostgreSQL transaction. The existing operator/NATS document path remains
separate and does not establish complete-generation admission. **Omniscience → Barbarossa:**
version-pinned reads of admitted evidence; notifications only wake up the reader.

Pure pull adds latency and repeated scanning. Pure push cannot prove an initial
inventory or reliably recover missed changes. Reuse the Go operator and direct AWS
adapters; do not create a second Kubernetes inventory collector. Cloud-specific
adapters translate native data into the same neutral contract.

The intervals below are initial engineering targets, subject to measured API budgets,
not statements about currently running collectors.

| Source and data | Baseline / repair | Fast path | Initial target |
|---|---|---|---|
| Git, IaC, Helm inputs | Fetch pinned revisions and allowlisted rendered desired objects | Authenticated webhook triggers revision fetch | Webhook plus 5-minute reconciliation |
| Argo desired revision and sync state | Authorized API read, linked to Git/release | Watch/event triggers refresh | Changes within 30 seconds; 5-minute reconciliation |
| Kubernetes all namespaces | Complete paginated LIST per registered kind/scope; periodic reconciliation | LIST→WATCH, recovery by relist on expired checkpoint | Watch changes within 30 seconds; core full reconciliation every 5 minutes; optional kinds initially 15 minutes |
| AWS resources/configuration | Direct paginated SDK inventory by account/region/service; targeted GET for uncertain absence | Optional native events trigger GET; never required for correctness | Critical configuration 3–5 minutes; remaining registered inventory 15–30 minutes |
| Runtime metrics | Bounded queries against existing Prometheus/CloudWatch or equivalent backend | Alerts trigger refreshed measurement-window query | 30–60 seconds for service health, 1–5 minutes for slower cloud signals |
| Audit/security events | Source configuration and delivery/checkpoint verification | Durable event ingestion | Source-specific latency and explicit delivery gaps |

Kubernetes list/watch and expired-version recovery follow the
[official API model](https://kubernetes.io/docs/reference/using-api/api-concepts/).
Resource versions are opaque checkpoints, not wall-clock freshness. A watch connection
alone does not prove all kinds were collected. AWS event delivery guarantees vary by
source, so events cannot substitute for inventory reconciliation
([AWS delivery documentation](https://docs.aws.amazon.com/eventbridge/latest/ref/event-delivery-level.html)).

Use existing telemetry backends: Omniscience stores bounded signal summaries and
references, not every raw log/metric/trace. Secret values, credentials and complete
Terraform state files do not enter the graph or model context. Extract allowlisted
attributes. Provider-neutral collection still needs provider-specific adapters.

### Admission, persistence and recovery

- Register workspace, tenant, source, cluster/account scope and collector identity.
  Authorize the actual publisher against that binding; a workspace subject alone is
  insufficient. Fence competing collectors by active source/scope epoch or lease.
- Persist immutable observations and collection receipts in PostgreSQL, alongside
  explicit current-state materialization. Neo4j and Qdrant are derived projections;
  expose their watermarks/lag rather than making their availability proof of state.
- Each collection generation records partitions, item count/digest, checkpoints and
  completion. Publish a complete receipt only after all its items are durably admitted.
  Transport ACK follows durable admission; projections may follow asynchronously.
  Advance a source checkpoint only after its complete generation commits, independently
  of broker ACKs. Reject an existing event ID with a different digest. Test lost ACK,
  receipt-before-items, and crashes between spooling, admission and checkpoint commit.
- Merge LIST generations and watches at the snapshot checkpoint, buffering/replaying
  subsequent events so a slow baseline cannot overwrite a newer update or tombstone.
  For AWS without a universal version, serialize/reconcile reads per resource using
  adapter-defined precedence and re-verification; receipt time alone is insufficient.
  Test stale scans versus newer same-incarnation updates and deletions.
- Replays are idempotent. Fence old resource incarnations and source epochs. Retire
  obsolete relationships as well as nodes. Do not compare Kubernetes versions as integers.
- Failed pagination, forbidden reads and timeouts produce partial/denied/failed coverage,
  never an empty successful scope. Infer deletion only from authoritative deletion or
  a complete relevant collection; use targeted verification/grace for eventually
  consistent cloud absence. An inaccessible resource does not disappear.
- Use bounded retry/spooling, backpressure and an explicit failed-delivery path. A
  dropped interval invalidates completeness until repaired. Do not claim exactly-once
  transport; prove one admitted effect through idempotency and fencing.
- Freshness is per source/partition and signal window, initially a configurable multiple
  of its interval. Show last complete reconciliation, latest event, watch liveness and
  projection lag separately. Partial/stale/unknown is not healthy. Preserve conflicting
  claims with field-specific authority rather than universal latest-timestamp-wins.

## Delivery sequence and acceptance

PS identifiers below are internal planning IDs, not new external SP tickets. Each row
is an epic decomposed into roughly 15-minute, single-owner verifiable implementation
slices before coding. Baseline failure and expected behavior precede each slice.

| ID / owner | Deliverable and dependencies | Observable done condition |
|---|---|---|
| PS-01 Omniscience + genai | Versioned state contract, service/resource identity, authority and coverage catalogue. Reuse narrow v1 appropriately | Desired/observed/signal examples validate; denied/partial/conflicting and stale examples stay distinguishable; exact API and compatibility contract agreed |
| PS-02 Omniscience | Durable evidence admission, source authorization, complete generations and pinned read API; depends PS-01. Close existing lifecycle findings | Actual collector → authenticated admission → PostgreSQL → owner API round trip; transport-specific operator/NATS compatibility, replay, missing batch, watch gap, UID recreation and cross-source/tenant refusal tests pass |
| PS-02D deployment owner + component owners | In parallel: retained storage/data migration, database network boundaries, ordered migrations, public logout, cluster provenance and runner connectivity | Verified restore and Pod replacement preserve data; frontend cannot reach DBs; migrations precede serving. EBS prerequisites and write/read smoke passed; staged Portal restore verified; cutover in progress |
| PS-03 Omniscience → Portal | First complete vertical slice for Omniscience, Barbarossa and Portal services: pinned Git/Argo intent, K8s facts, runtime signals and real dependency links; depends PS-02 | Observe answers what should run, what runs, whether requests succeed, dependencies and evidence age; missing sources visibly unknown; no seeded default substituted for live state |
| PS-04 Barbarossa → Portal | Deterministic Reliability/Security evaluation and pinned evidence → existing durable AI queue/runner → Control; depends PS-03 and deployment prerequisites before fault drill | One material deviation creates one case/analysis; accepted citations resolve to exact facts/policy revisions; Control shows queue/runner/results and advisory recommendation; recovery closes deterministic case while retaining history |
| PS-05 Omniscience + Barbarossa | Expand registered partitions to every namespace and discovered Frankfurt resource family; PS-03 foundation, incremental policies after PS-04 | Coverage catalogue accounts for present, absent, unsupported and denied families; relationships join services to cloud dependencies; no unsupported family silently excluded from completion |
| PS-06 all owners, genai records | Exact-image EKS qualification, source reviews/CI/merges and receipts; depends all applicable above | SRE and Security journeys, browser tenancy, failure/recovery, restart, deduplication and limits pass against final revisions; remaining exclusions explicitly reported |

PS-03/04 prove a **limited self-platform vertical slice**. They do not pass the user's
full Frankfurt scope. Full acceptance requires an independently compared discovery
baseline: each served/listable Kubernetes GVR and namespace/cluster scope (including
new namespaces/CRDs), and each AWS service/resource family with regional/global scope,
collection status and freshness. Unsupported or denied required coverage blocks full
acceptance unless the user explicitly changes scope. Reporting a gap does not waive it.
Excluded sensitive payloads and AWS Config are distinct from missing resource coverage.
PS-05 discovers and tracks compute, networking, ingress/DNS/TLS,
storage, databases, queues/streams, IAM/access, Kubernetes workloads/policies and
operational sources. Applicable global dependencies (for example IAM and hosted DNS)
are labelled global, associated with the regional platform and read only as needed;
this does not expand to other accounts. Unimplemented families remain explicit gaps.

Before deployed PS-03 evidence, PS-02D must establish durable storage, restore/rollback,
ordered startup and tenant/source boundaries. The authorized storage prerequisite draft
is only one subtask; it is not evidence of completed database migration or network
isolation. Coordinate the full operator/outbox fleet cutover, retire old publisher
credentials and prevent legacy consumers from acknowledging incompatible records.
PS-04 additionally requires a live heartbeat from the correctly targeted host runner;
local preflight is insufficient.

### AI SRE and AI Security behavior

Reuse Barbarossa's queue, leases, reservation limits and host Codex runner; do not build
a second analysis engine. Pin owner snapshot/facts, desired revision, policy version,
signal window and evidence references into each job. Model context is bounded and
credential-free. Persist an intake cursor and periodically catch up owner revisions;
a lost notification must not lose a finding. Retain immutable evidence through queue
retries and the configured case/audit retention period. A missing pinned revision
blocks/retries analysis explicitly; never substitute the latest state. Intake is
idempotent across restart. Findings use material state/policy/evidence fingerprints; timestamp
refreshes alone do not trigger another analysis. Invalid/incomplete evidence yields
unknown, not recovery. Queue capacity/fairness and deferred work remain visible.

First SRE policies: desired/available workload mismatch, sustained request failure,
restart/crash conditions and declared service dependency failure. SLO-based findings
require an actual declared SLO; inventory readiness alone is insufficient.
First Security policies: verified identity boundary, excessive access against a
versioned policy, public exposure and workload privilege. Honour explicit exceptions;
privileged infrastructure Pods are not automatically vulnerabilities. Configuration
checks are not a vulnerability scan or proof of compliance.

Use safe fixtures in an isolated test namespace/tenant for Security. Do not grant real
broad permissions to manufacture a finding. Controlled service faults require retained
storage and a recovery path. Keep analysis-only mode, one concurrent run, six hourly
reservations, 120-second attempts, at most two attempts, fenced leases and schema/
citation validation. A runner failure is distinct from a platform finding.

## Final evidence requirements and execution discipline

Qualify missed events/relist, partial/denied collection, stale collector, projection lag,
source conflict, desired drift, resource recreation, tenant/source isolation and durable
restart. Demonstrate fault → observation → case → real Codex result → Control → observed
recovery for both domains; history and call budgets survive restart. Verify invalid
JSON/citations/oversize/timeout/old lease rejection. Capture browser default journeys,
not only deep links. Preserve prior profiles and receipts; use exact image/revision and
coverage references for this profile. No passing claim derives from fixtures or source
unit tests alone.

Simple narrow tasks use gpt-6-luna; state/auth/integration use gpt-6.1-sol. Lead owns
architecture, reads full diffs including new files, reproduces key tests and resolves
independent specialist review findings before dependent work. Record model, measured
usage or labelled estimate, time, retries and outcome. No fabricated usage figures.

Current next delivery is PS-01/PS-02: make a real, complete, authorized state generation
readable from Omniscience. PS-02D proceeds in parallel with restored AWS access and Portal retained-volume recovery.
Existing reviewed changes are retained inputs, not abandoned or declared deployed.

### HTTP bootstrap transport — 2026-11-07

The outside-cluster bootstrap collector may publish a whole partition attempt through
`POST /api/v1/platform-state/targets/{target}/sources/{source}/batches` with a dedicated
`platform-state:publish` token and explicit enrollment. Workspace and publisher are
derived from that token; admission locks current token authority and source epoch
through commit. The 8 MiB bounded receipt returns only after persistence. This additive
transport does not qualify the planned in-cluster NATS delivery, durable collector
outbox, watch recovery or full-generation materialization. Those remain PS-02 work.

### Execution status — 2026-11-07

Portal, Barbarossa and Omniscience PostgreSQL have completed retained EBS cutover
with staged/live verification. The Barbarossa store retains its existing local-profile
history; Frankfurt still requires a separate bound store.

Neo4j's application graph was empty, with the exact reviewed application schema.
After schema-preserving staging and capture, Karpenter replaced the original emptyDir
Pod. The normal guard prevented cutover. Explicit recovery reopened the retained
staging claim and verified its catalog and internal database IDs. UID-guarded stage shutdown, retained-volume cutover and live verification completed.
Helm revision 5 resumed the API with one Ready replica and HTTP 200 from `/ready`.
Original receipts are preserved; recovery has separate intent and evidence records.
NATS and Qdrant still use node-local hostPath PVCs and require native backup plus
verified EBS restoration; their temporary disruption protection remains. This storage
milestone does not establish full platform-state acceptance.

The deployments collector now has a durable single-pending-generation outbox, bounded
HTTP publication and a CLI with actual cluster-UID checks. Lead race tests and independent
review passed. This scheduled collector is not yet deployed. Owner reads are scoped by
source; a real local HTTP/PostgreSQL roundtrip imported interleaved revisions 1, 3 and 4,
excluding sibling source revision 2. Timestamp refresh did not create a second case/job;
recovery resolved the same case. These are synthetic local integration results.

All Frankfurt read projections now carry the bound workspace/target/source/cluster;
Portal checks them before rendering. Refresh errors clear old facts, and no component
readiness is inferred from a projection read timestamp. Actual EKS enrollment, publisher
activation, complete desired/runtime/dependency joins, Security rules, Codex execution,
network boundaries, full coverage and authenticated browser acceptance remain open.
