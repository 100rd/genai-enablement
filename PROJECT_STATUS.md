# GenAI Enablement - Project Status

**Last Updated**: 2026-11-07
**Phase**: Autonomous SRE Harness development — Stages 0 & 2 shipped; Stage 3 portable construction and Stage 7 (Sentinel) portable detector expansion in progress
**Overall Health (broader harness)**: On Track — platform-state activation remains unqualified

## Platform-state activation — acceptance not passed, 2026-11-07

**Portal recovered on retained storage:** the failed `emptyDir` database was preserved,
and the verified 2026-11-06 22:55 UTC backup restored to an encrypted 8 GiB EBS PVC.
Helm release `platform-portal` revision 2 is deployed; PostgreSQL and backend are Ready.
Staging table counts, migration revision, role flags and both current credential logins
passed; live Service authentication and backend rollout passed after cutover. A fresh
browser reaches SSO. Changes after the backup are not claimed recovered. Other stores
and the authenticated browser journey still require verification. See the
[recovery evidence](docs/synchronized-platform/releases/management-platform-frankfurt-v1/source-checks/eks-portal-storage-recovery.json).


**Barbarossa retained storage verified:** Helm revision 3 resumed both API and observer
after exact staged/live checks of 6,072 observations, four cases, five jobs, schema and
role state. Observations resumed (6,084 at the post-resume check). Existing profile
history is preserved; its EKS store still has no accepted AI assessments.
[Evidence](docs/synchronized-platform/releases/management-platform-frankfurt-v1/source-checks/eks-barbarossa-storage.json).
**Omniscience PostgreSQL retained storage verified:** Helm revision 3 preserved all
12 tables, three workspaces, two sources and five documents on retained EBS.
[Evidence](docs/synchronized-platform/releases/management-platform-frankfurt-v1/source-checks/eks-omniscience-postgres-storage.json).
**Neo4j retained storage verified:** Helm revision 5 is deployed; API replicas and
ready replicas are one, and `/ready` returns 200. After Karpenter replaced the old
emptyDir Pod during maintenance, guarded recovery reused the verified EBS stage.
The exact empty graph, 14 indexes, four constraints, auth and staged database IDs
matched. Original receipts remain preserved; PostgreSQL fingerprints remained intact.
[Recovery evidence](docs/synchronized-platform/releases/management-platform-frankfurt-v1/source-checks/eks-neo4j-storage.json).
**Secondary storage recovery:** AWS interrupted the original Spot node at 12:49 UTC.
Replacement Qdrant had zero points instead of the seven in the verified off-node backup.
Both isolated EBS restore rehearsals now pass: Qdrant's exact seven-point state survives
Pod replacement, and NATS preserves three streams/four durables using the reviewed native
empty-store equivalence check. Production still uses hostPath; the guarded StatefulSet
handoff is in progress: the API is deliberately paused, schema-2 preparation and quiesced source checks passed; AWS session expired during staged writer shutdown. Production switch and API resume remain unverified; credential renewal is required to continue or safely cancel. Managed on-demand desired capacity increased from two to three within
the existing maximum; Terragrunt reconciliation remains required.
[Incident](docs/synchronized-platform/releases/management-platform-frankfurt-v1/source-checks/eks-secondary-storage-spot-interruption.json),
[Qdrant restore](docs/synchronized-platform/releases/management-platform-frankfurt-v1/source-checks/eks-qdrant-retained-rehearsal.json),
[NATS restore](docs/synchronized-platform/releases/management-platform-frankfurt-v1/source-checks/eks-nats-retained-rehearsal.json).

**Deployment wiring, source only:** the scheduled Omniscience collector and separate
Barbarossa Frankfurt API/intake/migration profile passed independent review and lead Helm
tests. Frankfurt migration renders require both runtime roles at zero replicas. Neither
profile wiring change is deployed; persistent state collection and live AI remain open.
[Capture evidence](docs/synchronized-platform/releases/management-platform-frankfurt-v1/source-checks/eks-secondary-storage-capture.json).
**Network isolation source ready, not deployed:** all three owner charts now constrain
PostgreSQL access and Service ownership, including umbrella releases and optional
Keycloak. Independent review and five real Helm render regressions passed. Existing
live permissive policies still require reconciliation and traffic checks.
[Source evidence](docs/synchronized-platform/releases/management-platform-frankfurt-v1/source-checks/postgres-network-boundaries.json).
Full acceptance is not passed.


The user confirmed account `120736097561`, `eu-central-1`, and every namespace of
`nonprod-euc1`. Collection must be cloud agnostic and must not depend on AWS Config.
The additive [Frankfurt profile](docs/synchronized-platform/profiles/management-platform-frankfurt-v1.md)
keeps the earlier local qualification separate. Current work covers direct cloud and
Kubernetes collection into Omniscience, advisory AI SRE/Security in Barbarossa, and
closure of the EKS acceptance findings. This expanded profile is not yet activated.

The direct AWS connector read 19 actual resources within the confirmed account.
Its 144 focused tests passed. Portal logout, loopback runner targeting and Barbarossa
profile/provenance isolation have source fixes with review; final deployment remains
pending. Bounded Kubernetes lifecycle fixes are reviewed source changes; complete state
admission and reconciliation coverage remain unfinished.
The lead reproduced 122 focused tests against disposable NATS, PostgreSQL, Neo4j and
Qdrant plus configuration/admission tests (3 skipped), and 311 Go operator tests.
Go identity, vector generation and bounded graph lifecycle changes passed independent
review. Periodic reconciliation now covers 26 core Kubernetes kinds. Source/cluster
binding, publisher permissions and owner evidence intake still block activation; these
results do not qualify EKS. See
the [activation register](portfolio/platform-activation-progress.json) for open findings.
All three existing PostgreSQL databases were privately backed up and each backup
restored successfully into its own disposable PostgreSQL 18 container. Those initial restore checks were disposable. Portal was subsequently restored and
cut over as recorded above; the remaining stores are not yet qualified.

The [rebased platform-state plan](docs/synchronized-platform/platform-state-plan.md)
chooses a hybrid: pull baselines/reconciliation plus watches/events, durable collector
push into Omniscience, and pinned evidence reads by Barbarossa. Desired state, observed
resources, runtime signals, relationships and evidence quality remain separate layers.
Reuse the existing Go operator and AI queue. Next: authorized complete state generations,
then a self-platform vertical slice, deterministic SRE/Security analysis and finally
all-namespace/Frankfurt coverage. A limited vertical slice cannot qualify the full scope.
PS-01/PS-02 now include a strict v2 contract, source-target enrollment with epoch
fencing, immutable transactional batch persistence and authorized revision reads.
The lead reproduced 201 tests, including real PostgreSQL and token-auth HTTP reads.
The Go collector read 81 actual Deployments across EKS namespaces; this is a collection
proof, not live owner ingestion. The Barbarossa parser, deterministic workload availability evaluation, and atomic
revision → case → analysis queue intake passed source review and 17 PostgreSQL race
tests. Delivery scheduling and deployment remain pending. The dedicated HTTP publish endpoint passed security review, including revocation
during streamed upload.
AWS/EKS access is restored using process-local credentials; the original credentials
file is unchanged. No platform acceptance claim changed.

**Current source regression:** Omniscience full Python suite passes (4,423 passed, 78 skipped); mypy, Ruff, operator race, governance and MCP contract checks pass. Portal backend (1,469 passed, 4 skipped), frontend (702 passed), typecheck, lint and production build pass. These checks do not qualify the deployed EKS profile.

**Source publication:** [Portal #25](https://github.com/100rd/platform-portal/pull/25), [Barbarossa #15](https://github.com/100rd/Barbarossa/pull/15) and [coordinator #63](https://github.com/100rd/genai-enablement/pull/63) merged after successful PR CI. [Omniscience #376](https://github.com/100rd/Omniscience/pull/376) is awaiting final CI after reviewed Go lint corrections. [Portal #26](https://github.com/100rd/platform-portal/pull/26) fixes unlocked production dependencies and merged after all four PR workflows passed. Six isolated Linux/amd64 images are built locally, with offline smoke checks; no new images are published or deployed.

## EKS activation audit — 2026-11-06

**Deployed; acceptance failed.** Read-only inspection of `nonprod-euc1` / `splatform`
and actual browser sessions verified both tenant logins, real Omniscience graphs, fresh
Barbarossa observations, cases/evidence in Control and all 11 signed-identity checks.
Seven Deployments and six StatefulSets are ready; all three migration Jobs completed.
These are EKS observations, separate from the successful local qualification below.

Acceptance blockers: three PostgreSQL stores and Neo4j use `emptyDir` data volumes;
the EKS runner has never reported a heartbeat; the Portal frontend can connect to all
three database ports; and `shared-host` observation provenance contradicts multi-node
placement. Startup also raced migrations, and Portal logout redirects to
`https://localhost:3000/login`. The EKS snapshot has two resolved startup cases,
three cancelled jobs and no accepted assessment visible in Control. It does not
inherit the local installation's six cases or four assessments.

See the [audit, evidence and owner follow-up queue](docs/synchronized-platform/releases/management-local-observe-v1/eks-audit/README.md).
No workload, chart, source code, secret or network policy was changed by this audit.
Fault injection, database Pod replacement and the complete Codex recovery drill remain
unperformed on EKS. Source merges and earlier local receipts retain their scope.

## Current local activation — 2026-11-06

**Source delivery merged; Kubernetes handoff prepared.** The current queue (SP-86 source work,
SP-101, SP-102–SP-106 and the Control follow-up) is merged into all four repositories.
All 17 source-head CI workflows and all 17 push workflows on the merge commits passed. Fresh real Chromium checks passed for both tenants,
Control/results/evidence and automatic connection refresh (4 passed; 2 outage-only checks skipped).
The 11 live signed-identity checks passed. Repeating the Omniscience seed preserved the recorded
PostgreSQL, Neo4j and Qdrant hashes, including IDs, document versions, graph temporal state and vectors.
See [merge verification](docs/synchronized-platform/releases/management-local-observe-v1/merge-readiness/verification.json)
and the [Kubernetes handoff](docs/runbooks/management-local-observe-kubernetes-handoff.md).
Charts and deployment belong to the deployment agent; the EKS audit above now records
the deployed installation and its failed acceptance, separately from this local evidence.
The local profile still has one observer and a host Codex runner; a cluster install does not qualify HA.

**Barbarossa work is now in Control:** Portal `1389aae` shows cases, real analysis queue/history,
runner diagnostics, exact job results and text recommendations. Observe retains component/domain
observations, knowledge and recorded case evidence. Barbarossa `1c63356` provides protected,
bounded job reads. Four real Chromium scenarios passed for both tenant sessions and the complete
Control → result → Observe evidence → Control path, including manual refresh and access denial.
[Control evidence and screenshots](docs/synchronized-platform/releases/management-local-observe-v1/control-work/README.md).

During backend recreation the observer detected a real outage and Codex completed one more analysis.
Current totals are **6 cases, 4 accepted assessments and 6 durable reservations**; the queue is empty,
runner online and all three component observations healthy. The five-reservation qualification below
is historical. Runtime volumes were preserved; no recommendation was executed. All five CI workflows passed
for both current component revisions; publication remains separate from local activation.

**Home connection cards running:** Portal `ae74ebc` now shows Barbarossa and Omniscience
connection, observed readiness and last-check time above the graph. Authenticated status refreshes
every 30 seconds and on demand. Cards stream independently of knowledge loading; unavailable,
denied, checking and stale observations remain distinct. [Browser and test evidence](docs/synchronized-platform/releases/management-local-observe-v1/home-connections/README.md).

**Default Portal journey corrected after user report.** Previous browser checks used explicit
entity/deep links and missed the normal landing. Portal `7526fb1` now opens `/observe` and loads
its tenant's owner-served seeded graph. Both fresh login journeys, foreign-workspace refusal,
Control's unselected-factory state, an actual Omniscience outage and recovery passed in Chromium.
See the [corrective receipt](docs/synchronized-platform/releases/management-local-observe-v1/default-journey/README.md).
The graph is prepared test topology. Current observations are in Observe; cases and recommendations
are now in Control. The older unselected-factory receipt remains historical.
Historical drill receipts below retain their original scope.

The **management-local-observe-v1** profile is implemented and running from
isolated `codex/local-observe-v1` worktrees. Omniscience serves real two-tenant knowledge, Barbarossa
records live Reliability/Security observations and durable cases, and Portal displays evidence and
non-authoritative Codex recommendations. Controlled outages of all three APIs completed the full
observation → case → real Codex analysis → Portal → recovery path.

In the original qualification, three assessments were accepted from five reserved `gpt-6-luna` calls. The first two invalid responses
were rejected and remain visible as one historical failed job; subsequent faults passed on the first
attempt. Stop/start preserved all five cases, three assessments, five reservations, lease epochs,
credentials and nine persistent volumes. Observer/runner loss and database failure were checked
separately. Both tenants passed real browser login/MCP isolation; all eleven signed-identity checks passed.

SP-99 and SP-100 are merged. SP-86 source work and SP-101 Knowledge View are implemented and tested;
SP-86 publication remains release-gated. Original dirty checkouts and earlier qualification receipts
are preserved. Changes in all four repositories are committed, pushed and merged. The coordinator delivery record
tracks source commits, review status and the separate local/production boundaries.

- [Qualification and evidence](docs/synchronized-platform/releases/management-local-observe-v1/README.md)
- [Runtime profile](docs/synchronized-platform/profiles/management-local-observe-v1.md)
- [Execution progress](portfolio/local-observe-progress.json) and [local runbook](docs/runbooks/management-local-observe-v1.md)
- [Commit and PR publication record](portfolio/local-observe-publication.json)
- Merged PRs: [Omniscience #374](https://github.com/100rd/Omniscience/pull/374) (`3831fb7`), [Barbarossa #13](https://github.com/100rd/Barbarossa/pull/13) (`c7f78d3`), [Portal #23](https://github.com/100rd/platform-portal/pull/23) (`adcddeb`), [genai-enablement #60](https://github.com/100rd/genai-enablement/pull/60) (`4cbf5c0`). Barbarossa tenant-boundary [issue #12](https://github.com/100rd/Barbarossa/issues/12) is closed.
- CI follow-ups fixed import/format/type/governance checks and legacy signed-read qualification. Exact source and merge revisions, CI results and tree equality are recorded in the additive merge receipt. Historical qualification receipts retain their original scope.
- Portal: http://localhost:13000; this qualification is macOS/Docker Desktop, single-host and advisory only.
- Published OCI releases, SP-89/SP-94, AWS, image vulnerability scanning, autonomous effects and HA remain separate gates.

The older sections below retain their historical scope.

## Direction shift (2026-06-16)
The SRE workstream is reframed from a "smart pager" (enriched notifications) to an
**Autonomous SRE Harness** — *"the harness is the product"*: agents do pre-triage,
change-validation gates, permanent-fix chase, RCA drafting, and bounded auto-healing under
tiered autonomy, measured on leverage not tickets closed.
- Landscape refresh: [`research/2026-agentic-sre-refresh.md`](research/2026-agentic-sre-refresh.md)
- Plan & vision: [`docs/autonomous-sre-harness-plan.md`](docs/autonomous-sre-harness-plan.md)
- Anchor fact: SOTA agents autonomously resolve ~11% of SRE incidents (ITBench) → bet on the harness.

## Completed
- [x] Market research — 40+ GenAI DevOps/SRE solutions analyzed across 7 categories
- [x] Quick reference table — decision guide for tool selection
- [x] AI Incident Agent — LangGraph solution prototype (architecture + source code)
- [x] Project structure — docs, templates, case-studies directories created
- [x] Project registered in orchestration system (PROJECT.md)
- [x] Role definition document
- [x] **Spec-driven implementation roadmap by track/team** — the obsolete month-based outline is now
  an evidence-gated dependency order for Organizational Dark Factory P0 (`A0..A7`), the Autonomous SRE
  harness (`B0..B7`), and the later enablement pilot (`C0..C4`), with exact repository owners, independent
  conformance/certification/readiness surfaces, transition evidence, and human/production boundaries.
- [x] Success metrics framework
- [x] Engagement templates (kickoff, assessment, playbook, ROI tracker)
- [x] **Agentic SRE landscape refresh (June 2026)** — 3 parallel research threads (market, architecture, AWS-native)
- [x] **Autonomous SRE Harness plan v2** — autonomy-tier model, action-tier governance, revised roadmap
- [x] **Offline eval baseline (Stage 0)** — [SPEC-B0](docs/specs/SPEC-B0-offline-eval-harness.md)
  formalizes the immutable scenario/target/scorer seam, honest Pass@1/lead-time metrics, deterministic
  seed coverage, explicit unsupported-metric failure, and local traceability. The code baseline is
  shipped, but B0 remains operationally incomplete until a human-owned real corpus and regression policy
  are immutably published.
- [x] **Sentinel portable core (Stage 7)** —
  [SPEC-B7-CORE](docs/specs/SPEC-B7-core-sentinel-runtime-contract.md) formalizes immutable
  state/findings, read-only sources, deterministic registry/dedup/ranking, atomic open-finding state,
  advisory CLI exits, and AgentOps. It remains a local construction contract with no live runtime,
  delivery, credential, or action authority.
- [x] **Sentinel ADR catalog foundations** —
  [SPEC-B7-SAT](docs/specs/SPEC-B7-saturation-expiry-detector.md) and
  [SPEC-B7-NES](docs/specs/SPEC-B7-new-error-signature-detector.md) formalize the original deterministic
  `saturation_expiry` and `new_error_signature` families, including candidate rules, lead-time/clean
  controls, no-action boundaries, and the external policy/calibration gates. No LLM or provider is bound.
- [x] **Sentinel B7 portable detector increment** — [SPEC-B7](docs/specs/SPEC-B7-error-rate-baseline-detector.md) adds exact aggregate `error_rate_vs_baseline` input/rule/registry admission, one incident replay with positive lead, three targeted clean controls, and explicit early-detection/false-positive metrics. Fixture-only candidate thresholds; no live source, runtime deployment, or production calibration.
- [x] **Sentinel B7 change-regression portable increment** — [SPEC-B7-CIR](docs/specs/SPEC-B7-change-induced-regression-detector.md) adds exact immutable deploy/pre-post binding, ordered one-hour/zero-intervening association, shared complete regression thresholds, specific-over-generic collapse, one positive-lead incident replay, and five attribution/regression clean controls. It reports correlation only; no live deploy source, causation, or runtime authority.
- [x] **Sentinel B7 config-state drift portable increment** — [SPEC-B7-DRIFT](docs/specs/SPEC-B7-drift-detector.md) completes the deterministic ADR catalog with an exact normalized tracking-policy/desired/observed digest fact, two-observation/five-minute persistence gate, stable resource dedup, one positive-lead replay, and five convergence/noise/reset clean controls. It observes only; no raw config, live Omniscience source, reconciliation authority, or accepted policy.
- [x] **Organizational Dark Factory SDD governance** — ADR-0009 accepted with graded SDD,
  progressive assurance, and distinct conformance/certification gates
- [x] **Barbarossa Continuous Management planning corpus** — proposed
  [ADR-0020](docs/decisions/0020-barbarossa-continuous-management-plane.md) supersedes the
  reliability-only product boundary while retaining ADR-0019 as Reliability design history. The
  synchronized registry now joins 12 kernel capabilities, 12 isolated domain packs and 29
  independently assignable Barbarossa SPECs to an acyclic `SP-70…SP-85` work-package plan. All
  contracts remain non-authorizing; `SPEC-AUT` is explicitly blocked on per-domain live evidence.
- [x] **Local P0 qualification refresh (2026-07-15)** — Docker Engine 29.2.1 qualified the
  worker/verifier isolation and reclaim boundary (`293 pass`, `3 waived`, `0 fail`: AMBER, not
  GREEN). Kind v1.32.5 plus Cilium 1.19.5 passed observer authority/RBAC, preconditioned cleanup and
  reaper failures, Pod-bound credential invalidation, direct Pod-IP policy, and the complete HTTP
  evidence lifecycle. The signed kind report remains explicitly `admissible: false` and
  `readinessEligible: false`.

## In Progress
- [ ] **Human-owned portfolio decision backlog** — all ten ADRs in this repository whose current source status is
  `Proposed` are now joined into the machine-readable portfolio, roadmap, and human portfolio view. The
  drift gate rejects missing/extra entries, source status/path mismatch, and an unknown or forward
  dependency. This records review order only: it does not accept a decision, authorize a follow-up SPEC,
  adopt component code, activate readiness, or change a release.
  - [ADR-0002](docs/decisions/0002-platform-skills-registry.md): `registry-trust` → `human-disposition`; blocks `skill-registry-adoption`.
  - [ADR-0003](docs/decisions/0003-unified-sdlc-standard.md): `cross-factory-sdlc` → `human-disposition`; blocks `cross-factory-sdlc-adoption`.
  - [ADR-0006](docs/decisions/0006-unified-loop-decision-model.md): requires `ADR-0003`; `cross-factory-sdlc` → `human-disposition`; blocks `cross-factory-loop-adoption`.
  - [ADR-0007](docs/decisions/0007-platform-portal-federated-surface.md): `portal-experience` → `human-disposition`; blocks `platform-portal-spec-adoption`.
  - [ADR-0008](docs/decisions/0008-ai-security-domain.md): `ai-security` → `human-disposition`; blocks `ai-security-s0-s1-spec-authorship`.
  - [ADR-0014](docs/decisions/0014-precommitted-http-condition-evidence.md): `delivery-evidence` → `human-disposition`; blocks `http-evidence-adoption`.
  - [ADR-0015](docs/decisions/0015-independent-observer-authority-attestor.md): `delivery-evidence` → `human-disposition`; blocks `observer-attestation-adoption`.
  - [ADR-0016](docs/decisions/0016-independent-safe-to-reclaim-decision-issuer.md): requires `ADR-0006`, `ADR-0015`; `delivery-evidence` → `human-disposition`; blocks `safe-to-reclaim-adoption`.
  - [ADR-0018](docs/decisions/0018-pii-wall-purpose-bound-data-boundary.md): requires `ADR-0003`, `ADR-0007`, `ADR-0008`; `privacy-boundary` → `human-disposition`; blocks `pii-wall-component-adoption`.
  - [ADR-0020](docs/decisions/0020-barbarossa-continuous-management-plane.md): `continuous-management-plane` → `human-disposition`; blocks `barbarossa-continuous-management-adoption`.
- [ ] **Track-B SPEC external-evidence backlog** — the machine-readable `track_b_spec_backlog` now
  covers all and only the thirteen [Autonomous SRE harness SPECs](docs/specs/README.md), including the
  previously implicit B0 baseline, Sentinel core, and first two detector families. It rejoins their source
  ids, paths, Draft statuses, roadmap gates, dependencies, and contiguous REQ/probe counts, and records
  the exact next human/external gate. Its state is `external-evidence-required`; every row remains
  `local-construction-only`, operationally `incomplete`, and `non-authorizing`. This planning index does
  not replace any SPEC's own acceptance oracle and explicitly does not authorize a live source, provider
  call, credential, deployment, remediation, pilot, or production claim.
  All thirteen Track-B SPECs now have closed local manifests at
  `solutions/sre-harness/spec-traceability/SPEC-B0.json`,
  `solutions/sre-harness/spec-traceability/SPEC-B1.json` and
  `solutions/sre-harness/spec-traceability/SPEC-B2.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B3.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B4.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B5.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B6.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B7-CORE.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B7.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B7-NES.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B7-CIR.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B7-DRIFT.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B7-SAT.json`: each binds the exact SPEC digest and every
  source probe id to existing pytest nodes and implementation paths. The checker rejects
  source/node/path/scope drift. No `portable_traceability_manifest` value remains null; these static
  indexes store no PASS result and do not change any external gate.
  Traceability registry summary: `13` checked manifests; `0` remaining null.
- [ ] **Repository adoption** — omnius ADR-0015/0016 and SPEC-IN/ROLE/EXP/REG/OT/TM remain
  drafted for separate human acceptance/readiness review. Omnius now has a non-authorizing
  `standard-http-service/v3` readiness draft and a deterministic compiler that fails closed on schema,
  immutable revision/path-bundle pin, independently observed capability-revision membership, dependency,
  registered-probe, bidirectional runtime-owned requirement/probe traceability, blocker, probe-result,
  bounded-Realm, PlatformPath, evidence-TTL, and forbidden-action drift. Capability manifests are
  closed repository/path/revision/blob-digest publications with namespace-owned unique ids, immutable
  publication revisions, allowlisted origins, and exact verifier references. Only exact boolean external
  verification issues an opaque capability; raw/caller-constructed bindings and profile lists cannot
  claim an id absent from the pinned revision, and the compiler rejoins exact source and revision. The
  profile-authored path-bundle pin is no longer treated as independent observation: compilation now
  requires an opaque externally verified platform-owner publication that pins the exact bundle/path
  materialization, lifecycle/catalog state, Realm-admission digest, CODEOWNERS revision, and
  origin/verifier. Draft planning may use the verified catalog-only fixture, while `ready` requires an
  admitted `experimental`, `validated`, or `approved` path. Raw/copied bindings, truthy verifier output,
  and inconsistent lifecycle/admission state fail closed. Human readiness authority is also separated
  from profile-authored claims: `ready` compilation now
  requires an opaque externally verified CODEOWNER publication that exactly rejoins the profile
  repository/path/revision/digest/name/version/authority. A raw `approvedBy` field, copied binding, foreign
  origin/verifier, or mismatched publication cannot promote a draft. Profile scope and prohibitions remain
  signed through intake and execution; execution verifies the envelope signature and exact readiness binding before
  adapter resolution. The compiler now exposes no caller probe-state parameter: `ready` requires an
  integrity-sealed opaque publication from an allowlisted exact-boolean external verifier. It
  rejoins the exact profile, bundle, path, assurance profile, concrete Realm and `PT24H` window, then requires
  a complete exact-revision pass result set with immutable evidence refs/digests and a manifest digest.
  Missing/raw/copied, stale/future, partial/extra/non-pass, wrong-revision, or post-issuance-modified evidence
  fails closed. The adjacent platform-contract, capability-manifest, readiness-profile, and delivery-trust
  opaque authorities now use the same issuance-integrity boundary: gates snapshot and revalidate across
  verifier callbacks, process-local seals bind every issued field/nested model, and compiler/materializer
  consumers reject post-issuance mutation. The v3 selection now includes the complete `REQ-TM-1..11` / `P-TM-1..11`
  contract, so exact model/evidence expiry is part of readiness rather than an unselected adjacent
  assurance check. The v3 PRB selection also includes the HTTP-specific provenance, bounded state
  machine, replay/admission, and digest-signature contract (`REQ-PRB-8`, `REQ-PRB-13..16` /
  `P-PRB-7..11`),
  including both registered owners of `REQ-PRB-15`. The selected RLM/PRB/PP/WO/IN slices now have
  explicit ownership coverage, including multi-requirement probes, and reject omitted ownership,
  duplicate/compound requirement metadata, and probes that carry requirements outside the selected
  slice. The HTTP PRB contract is pinned to immutable Omnius revision `a32fecd`, while newer ownership
  probes that exist only in the current worktree remain an explicit activation blocker until a later
  immutable capability revision and externally observed manifest contain every selected REQ/probe id and
  replace the provisional pins. Current manifests are deterministic conformance fixtures, not production
  publication/verifier evidence; the production platform-contract, capability-manifest,
  readiness-profile, and readiness-probe-evidence origins/verifiers, CODEOWNERS/approval publication paths,
  Realm-admission evidence, immutable real-path evidence manifest/results, and blob observations remain
  unselected. The documented host bootstrap now uses Python 3.14 plus the same fully pinned requirements
  as the conformance image instead of an absent repository-local virtual environment. Legacy Phase 2/3
  timestamp seams now emit timezone-aware UTC for secret leases, evaluator freshness/measurements,
  outcome/return observability, conductor outcomes, and human drill cadence while treating persisted
  naive values as UTC; the Python 3.14 `utcnow()` deprecation path is gone. On the current worktree it
  passes the 1,025-test acceptance contract and 290 portable probes; three explicit human
  waivers and three target-profile controls keep assurance certification RED without blocking contract
  conformance. The bounded new readiness/conformance Python surface is now Ruff-clean and formatter-clean
  across all 14 files; its 92 focused tests pass, and 78 focused tests cover the five production modules at
  90% branch coverage. This is not a repository-wide static-clean claim: the full legacy tree still reports
  119 Ruff findings and 144 files outside formatter baseline, deliberately left as explicit A1 construction
  debt instead of receiving a mass rewrite. The GenAI machine-readable portfolio now carries this bounded
  Omnius readiness snapshot,
  its 11 component-owned blockers, dirty/unpublished evidence scope, and separate conformance/certification/
  activation decisions; the offline drift gate rejects any active claim while the profile is draft or
  evidence remains unpublished/RED and keeps the human page synchronized with exact counts and the source
  profile digest. An explicit read-only sibling observer additionally rejoins those facts to the actual
  Omnius v3 JSON, Git HEAD, and dirty/clean publication state when `--omnius-root` is supplied; the default
  CI check remains self-contained and never discovers sibling repositories implicitly. The standalone E2E
  runner passes 47 tests and the console dependency set imports cleanly.
  This implementation evidence does not accept the ADRs or activate the profile.
- [ ] **Platform skill-registry trust root** — ADR-0002 defines git-backed pinned consumption,
  but the current `skills-lock.json` carries only content hashes: select a human-owned signing
  mechanism/key owner and publish exact immutable git revisions before Omnius P1 REG activation.
  Omnius now inspects bounded duplicate-safe raw lock JSON and the actual live v1 file is deterministically
  rejected as legacy content-hash-only, missing its signed envelope/exact commit and with no trusted verifier
  configured. Its portable consumer contract now binds a signed verifier reference to an allowlisted
  preconfigured verifier, accepts only exact-boolean verification over a stable revalidated snapshot, and
  issues an opaque integrity-sealed readiness capability required by the resolver. Raw signed-lock bypass,
  copied-invalid input, verifier mutation/identity drift, fabricated readiness, and post-issuance mutation
  fail closed on every resolution. This enforcement and its deterministic HMAC test double do not select the
  production algorithm or key owner and do not activate P1 REG. Executable `scripts/` remain disabled for the
  first governed vertical.
- [ ] **Omniscience MCP contract and workspace-token seam** — implement and publish accepted
  [ADR-0017](docs/decisions/0017-omniscience-mcp-v1-contract-and-severance.md) before Omnius KP
  activation. The decision now fixes MCP `1.0.0`, a content-addressed fifteen-tool manifest plus
  authenticated `contract_info`, additive freshness/consistency/fallback capabilities, and bootstrap
  profile `omniscience-mcp-read-v1`: human-administered Omniscience admin-token API, server-bound
  workspace, exact `search` scope, mandatory expiry up to 30 days, and replacement overlap up to 24
  hours. Omnius now pins the full registry/commit/manifest/schema/profile/capability handshake while
  exposing only its closed five-tool planning subset. Publication, token-profile, and claims verifiers
  have distinct disjoint allowlists; only exact-boolean verification over stable strict snapshots can issue
  the opaque integrity-sealed readiness receipt rechecked on every operation. Truthy non-booleans,
  copied-invalid input, verifier drift/mutation, raw-gate substitution, fabricated/mutated readiness,
  legacy profiles, extra scopes, and excessive lifetime fail closed. The consumer now also validates
  every ADR-0017 response envelope against the invoked operation's schema pin, exact contract commit,
  token workspace, UTC production/effective/freshness times, and requested `as_of`. Only a strictly
  revalidated stable `fresh` + `converged` response with no producer fallback may become Planner
  context; malformed/copied-invalid metadata, time/contract/schema/workspace skew, every
  stale/unknown/degraded state, or `fallback.required=true` emits a typed direct-source-fallback
  selection that no LLM can override. Omnius has also removed the legacy runtime-v0 bypass:
  its phase-2 transport now requires one complete stable sealed-consumer/claims/private-bearer/endpoint
  binding before any network request, authorizes the exact five-operation surface before bearer use,
  bounds request/response JSON, and rejects redirects, duplicate or non-finite JSON, malformed JSON-RPC,
  oversized responses, and response-metadata skew with stable non-secret fallback reasons. The default
  Conductor is deliberately unconfigured, performs no MCP request, and uses the maintained direct Git
  source without fabricating a confidence value. The Omniscience working tree now implements the
  human-ready SPEC-MCP slice: the fifteen-tool content-addressed registry, authenticated handshake,
  answer-scoped freshness/consistency/fallback envelope, exact admin-issued token profile, bounded
  single-successor rotation/revoke path, and offline drift tests. Hardening makes non-finite/non-JSON or
  oversized output a stable tool error, refuses to reinterpret legacy `staleness_seconds` as version lag,
  treats post-`as_of` snapshots as missing historical lineage, aligns integer metadata with the Omnius
  consumer, and pins the Python MCP SDK to stable v1. P-MCP-9 offline probes now directly assert the
  predecessor row lock, unique single-successor constraint, and exact structured create/rotate/revoke
  audit records; these probes are mechanism evidence, not a live rotation drill. The single offline drift
  gate now verifies both the direct server requirements and resolved SDK lock, while mutation probes cover
  the canary docs, every MCP catalog, and the capability/task/execution indexes. The worktree now also has
  a fail-closed release materializer: it reads schemas/registry/template only from one clean exact Git
  `HEAD`, publishes below the manifest digest, and release runtime rejects env-only, non-canonical,
  commit-mismatched, symlinked, or package-mismatched provenance. A portable fail-closed canary verifier
  now independently validates
  that bundle, the official Streamable HTTP initialization, exact fifteen-tool input-schema surface,
  authenticated workspace handshake, and all manifest/schema/registry/profile/capability pins. It reads
  the bearer only from the environment, rejects redirects and non-canonical `/mcp` URLs, and emits only a
  non-secret receipt or stable error code; a real in-process FastMCP lifecycle qualifies in the focused
  suite. The CI-equivalent Ruff/format, strict mypy, governance, lock, and offline drift gates now pass;
  full local collection passed 3,539 tests and had only 13 Docker-socket setup errors in three pre-existing
  Neo4j testcontainer files, while the exact non-Docker rerun passed 3,536 tests. This is verifier mechanism
  only, not an activated environment. However inspected HEAD
  `d050eba8ffe6d025cc0db75ebc4dfc5a60dba937` contains none of this worktree publication; because the tree
  is dirty, it is intentionally ineligible for materialization. No immutable release bundle, deployed
  canary/receipt, exact verifier references, live token, durable audit,
  rotation/revoke drill, consumer pin, severance drill, or human execution evidence exists. Readiness
  therefore remains direct-source fallback and no activation is claimed.
- [ ] **Cross-stack Experience store placement** — select the physical store and operational owner for
  verified Experience beside, but not inside, Omniscience. The store must preserve the state/capability/
  experience authority split, tenant isolation, immutable evidence joins, and cold-start severance;
  Omnius now implements the portable contract: an absent/unverified binding denies writes and starts
  planner reads cold; an admissible binding pins a human owner, origin, deployment/schema/tenant/join
  revisions, separate publication-binding and access-grant verifier references, durability, and the
  no-state/no-capability/no-cross-tenant boundary. The gate now revalidates an exact stable snapshot,
  rejects non-boolean success and verifier-callback mutation, and issues an opaque integrity-sealed
  readiness receipt; boundary and store consumers independently validate it before every positive
  operation. Copied-invalid, fabricated, modified, drifted, or untrusted inputs remain cold/denied.
  Store operations require exact-boolean verified single-scope grants and immutable evidence joins, with
  tenant/repo/role/sensitivity isolation and duplicate-safe exact replay. Its in-memory adapter remains
  explicitly non-production. Caller-owned `human_approved` no longer authorizes Experience decay or skill-
  proposal thresholds: a separate externally verified binding now joins exact policy values/revisions to
  a human CODEOWNERS owner, approval, curation-pilot evidence, and allowlisted verifier. It is revalidated
  as a stable snapshot and issued as an opaque integrity-sealed receipt; consolidator and proposal gate
  recheck it on every call, while absent, truthy-verified, copied-invalid, fabricated, or modified policy
  authority demotes verified guidance to cold/observed and blocks skill PRs. Current values remain fixtures,
  not ratified production governance. The inspected multiqlti table remains a project-local, nullable-project,
  default-off proving-ground store, not the assigned shared backend; no P3 activation is claimed.
- [ ] **Terraform Maintainer Standing Role activation inputs** — name the human CODEOWNERS group that
  owns the first role definition and pin its cost/wall-clock breaker values from measured curation-pilot
  evidence. Omnius now rejects the previous caller-owned `owner_verified` / `human_approved` /
  `activation_inputs_bound` flags and requires an allowlisted externally verified activation binding.
  That binding joins the exact role/signature/path, human CODEOWNERS and approval revisions, breaker
  policy/provenance/values plus curation-pilot evidence, trusted verifier, and exact Class A /
  non-production P3 GREEN certification. The gate now revalidates an exact snapshot, rejects verifier-
  callback mutation, and issues an opaque integrity-sealed activation decision; matcher and spawner
  independently validate it before creating authority. An absent, copied-invalid, fabricated, modified,
  drifted, AMBER/RED, or untrusted binding/decision cannot wake a loop. The existing `45 min / USD 20 /
  3 retries` values remain fixtures, no authoritative CODEOWNERS group or measured binding was found,
  and no autonomous activation is claimed. Unmatched, production, irreversible, apply, direct-state,
  and unpinned-skill work continues to route to a human.
- [ ] **Human Boundary governance inputs** — ratify the auth/MFA production-migration Class-2
  (human-forever) disposition; pin game-day cadence/pass thresholds, the `awaiting_human` target and
  benign-reject allowance, and the deterministic Mode-B discarded-candidate degeneracy rule; publish
  the complete human-owned gate-config path manifest. Omnius now rejects caller-owned approval,
  CODEOWNERS, and ratification flags and requires an allowlisted, externally verified exact-revision
  governance binding. The binding joins every policy/approval/owner revision, evidence-backed threshold,
  Class-2 disposition, and all twelve protected gate surfaces; exact-boolean verifier failure, drift,
  an incomplete/unprotected manifest, or an unconfigured live binding produces one portable readiness
  result that makes all matrix rows human, disables CI apply/promotion, rejects queue/registry admission,
  fails removability readiness, denies agent config writes, and human-routes every diff. The verifier operates
  on a validated snapshot and callback mutation fails closed; the issued decision is opaque and integrity-sealed
  over the full policy, binding, and protected paths, and every positive consumer rejects fabrication or
  post-issuance mutation. Directory-prefix paths are matched as prefixes and traversal paths fail closed.
  Current bindings, owners, and numeric values exist only in deterministic test/probe fixtures, so no HB
  activation, rehearsed removability, or autonomy increase is claimed until the human publishes the production
  inputs.
- [ ] **Delivery observation and HTTP evidence trust chain** — review and accept or revise proposed
  ADR-0014/0015/0016, then publish the exact production identities and immutable trust profiles for
  the HTTP subject issuer/result signer, observer-authority attestor, and safe-to-reclaim issuer. Pin
  their distinct EKS Pod Identity/IAM boundaries and asymmetric KMS keys, the create-only S3 evidence
  profile and receipt store, and the human-owned readiness revision. Until those protected bindings
  and real-path negative/failure evidence exist, `standard-http-service/v3` remains catalog-only with
  only a `draft` readiness profile; the candidate record remains `admitted: false` with
  `readinessProfile: null`. Local process-memory signatures, PVC storage, kind qualification, and the
  draft compiler cannot activate a Realm, production path, or autonomous merge. Its deterministic
  platform-contract publication is explicitly catalog-only and unadmitted; no production owner origin,
  external verifier, CODEOWNERS revision, or Realm-admission digest has been selected. Omnius now implements
  the portable `REQ-DO-18` enforcement boundary: an allowlisted external verifier must return exact
  boolean success for one closed binding that accepts ADR-0014/0015/0016, pins four distinct KMS
  Ed25519 signer/attestor identities plus separate producer, credential-issuer, and evidence-store
  identities, binds the create-only S3/Object Lock and immutable receipt profiles, and carries the
  protected-path, real-path, negative-permission, failure-drill, and human-activation revisions. The
  resulting opaque capability materializes the existing HTTP subject/result, observer-attestor,
  safe-to-reclaim, and evidence-store contracts; the v3 readiness compiler additionally requires its
  exact profile Git revision and canonical profile digest. All current values and verifier output are
  deterministic non-production fixtures: no AWS resource, production identity, accepted decision,
  protected-path evidence, exact-revision real-path probe publication, or readiness activation has been
  published. The local GitHub class-3
  path now also retains one create attempt across worker disappearance and accepts only an append-only,
  exact Ed25519 human-fence receipt after lease expiry before independent absence reconciliation; its protected
  production public-key/control endpoint and failure drills remain unbound.
- [ ] AI Incident Agent — complete implementation and testing. The governing
  [SPEC-B1](docs/specs/SPEC-B1-read-only-triage-rca.md) now fixes the read-only snapshot, source,
  gather/analyze/draft, citation, eval, and AgentOps oracle. A bounded B1 offline construction slice
  now implements a strict 1 MiB UTF-8 v1 JSON file source with duplicate/non-finite/symlink and closed
  schema rejection, exact incident/`as_of` source rejoin, immutable UTC incident/evidence snapshots,
  service/time-bounded gather, a single
  read-only `analyze()` seam, exact fact/hypothesis citation rejoin, calibrated confidence with an
  honest zero-confidence unknown path, action-free T1 RCA drafting, AgentOps node spans, and three
  incident-replay labels scored through the shared eval runner. Candidate content-addressed thresholds
  now report metric conformance separately from evidence scope. An exact corpus-publication gate issues
  an opaque process-local capability only after allowlisted exact-boolean verification and rejoins the
  exact policy, scenario ids, and canonical snapshot/label manifest; raw, fabricated, mutated, foreign,
  and mismatched inputs fail closed. The positive verifier is a test double, the perfect seed suite
  remains `fixture-only`, and the current unconfigured publication path leaves
  `production_evidence_eligible` false. It remains incomplete: no live
  Datadog/log/metric/deploy source, approved model/vendor analyzer, curated real-incident corpus,
  externally verified corpus/policy publication, or measured production usefulness/false-positive
  evidence exists.
- [ ] Advisory change-validation integration — the governing
  [SPEC-B2](docs/specs/SPEC-B2-advisory-change-validation-integration.md) now fixes the closed integration
  envelope/result and T1/T2 boundary. The dirty local SRE harness implements strict bounded v1 UTF-8 JSON,
  duplicate/non-finite/symlink and closed-field rejection, canonical change/platform SHA-256 rejoin,
  a fail-closed draft candidate five-minute platform-snapshot freshness ceiling, opaque immutable invocation/result
  contracts, the unchanged deterministic three-check gate, exact result provenance, distinct
  `0/10/20/64` dispositions, and atomic non-symlink result output. GitLab now
  preserves the command status instead of masking it through `tee`; GitLab and Argo CD remain explicitly
  non-blocking templates. This is portable fixture conformance only: no human-accepted freshness policy,
  approved live platform/change
  producer, immutable harness release, observed GitLab/Argo run, retained external artifact, or measured
  latency/catch/false-positive/override evidence exists, so B2 remains incomplete.
- [ ] Deterministic canary rollback — the governing
  [SPEC-B3](docs/specs/SPEC-B3-deterministic-canary-rollback.md) now fixes the fixture-only policy,
  fail-closed decision oracle, and Argo Rollouts/Datadog rendering boundary. The dirty local SRE harness
  implements bounded duplicate-safe content-addressed policy ingestion; immutable SHA-256 image and
  exact integral basic-canary weight checks; explicit candidate timings, resources, probes, and metric
  inputs; an offline `observe` / `continue` / `abort_to_stable` mirror; and deterministic Kubernetes JSON
  for a Service, namespaced Datadog v2 AnalysisTemplate, and hardened inline-analysis Rollout. The
  analysis has finite count, complementary nil/NaN/Inf-safe conditions, zero failure/inconclusive/error
  tolerance, an exact latest-ReplicaSet hash join, deadline abort, no dry-run, and no LLM/plugin/job/web
  decision surface. This is portable fixture conformance only: Kubernetes/distribution/namespace and
  Argo controller/CRD versions are not pinned by a consumer, the sample image is intentionally invalid,
  the threshold/query/tag/Secret are not human accepted or provisioned, no resource was server-side
  admitted or applied, and no positive promotion, forced-negative rollback, stable-traffic, latency, or
  false-positive evidence exists. B3 remains incomplete.
- [ ] Tier-4 allowlisted remediation — the governing
  [SPEC-B4](docs/specs/SPEC-B4-tier4-allowlisted-remediation.md) now fixes the exact externally authorized
  SSM allowlist, T4-to-T3 degradation, finite compensation state machine, and notification boundary. The
  dirty local SRE harness implements bounded duplicate-safe content-addressed policy/request ingestion;
  an exact-boolean external publication capability; canonical action-tier classification for restart,
  Argo CD re-trigger, and bounded stateless scaling; exact account/region, numeric document version,
  owner/hash/schema, target tuple, concurrency-one, zero-error, and UUID idempotency joins; and sealed
  `forward_running` / `rollback_running` / terminal states with no recursive compensation. Approval and
  calendar states escalate without an Automation signal, while notifications use stable dedupe keys and
  omit parameters, roles, tokens, document content, and exception detail. This is portable fake-client
  conformance only: the checked publication is forced to `fixture`, no production runbook/policy, IAM or
  PassRole boundary, durable workflow/ledger, delivery proof, CloudTrail retention, drill, or operational
  measurement exists, and no AWS account was contacted. B4 remains incomplete.
- [ ] Tier-3 HITL remediation — the governing
  [SPEC-B5](docs/specs/SPEC-B5-tier3-hitl-remediation.md) now fixes the closed proposal/receipt,
  canonical action-tier, explicit human authority, AWS approval signal, GitLab approval observation,
  finite state, and sanitized audit boundary. The dirty local SRE harness implements strict bounded
  duplicate-safe content-addressed proposal and receipt readers; a runtime-derived revision over the
  canonical action table and threshold; exact T3 admission for native T3 or deterministic T4→T3 cases;
  allowlisted exact-boolean external receipt verification; proposer/non-human/fixture/self-approval,
  cross-subject, future, and expiry denial; and integrity-sealed cases. The AWS path rejoins client,
  account/region, execution, numeric document version/hash/schema, exact input revision, and first
  approval step before sending only `Approve` or `Reject` through a stable-dedupe port. The GitLab path
  is read-only and requires the exact opened protected target/head, reset-on-push and reauthentication,
  non-overridden non-empty satisfied rules, exact policy revisions, and an independent eligible reviewer;
  it exposes no approve or merge operation. Audit events exclude parameters, reviewer/MFA identity,
  risk/rollback text, comments, content, tokens, and provider exceptions. This is portable fake-provider
  conformance only: checked proposal/receipt artifacts are non-authorizing fixtures, no production
  identity or policy, durable CAS/outbox, provider/audit delivery, retained provider audit, drill, or
  operational measurement exists, and neither AWS nor GitLab was contacted. B5 remains incomplete.
- [ ] Permanent-fix chase — the governing
  [SPEC-B6](docs/specs/SPEC-B6-permanent-fix-chase.md) now fixes the strict incident-to-task intake,
  externally authorized issue-create, factory-owned change, canonical outcome, exact landing, finite state,
  and negative merge/close-authority boundary. The dirty local SRE harness implements bounded
  duplicate-safe canonical content-addressed request, policy, and factory-outcome readers; exact-boolean
  external policy/outcome capabilities with mutation, origin, fixture, freshness, and policy-age denial;
  exact provider/repository/factory/class/label/branch joins; one bounded idempotent issue-create call with
  opaque dedupe; PR-as-issue and ambiguous-search rejection; read-only exact issue and factory-created
  MR/PR tracking; monotonic `PRODUCED`/`VERIFIED`/human-`GATED` chase; and `LANDED` only when a passing
  human-gated factory outcome and provider merge agree on the same head. Premature close, closed-unmerged,
  stale/drifted/failed/foreign outcome, lifecycle regression, and timeout escalate. Audit excludes issue
  body/title, evidence content, identities, diffs, logs, tokens, and provider exceptions. This is portable
  fake-provider conformance only. The closed local
  `solutions/sre-harness/spec-traceability/SPEC-B6.json` binds the exact Draft digest and all ten probes to
  existing pytest nodes and the bounded implementation path; it stores no PASS result or provider/factory
  authority. Checked policy/request artifacts are inert fixtures, no human-owned live
  provider/factory policy, separate principal, durable CAS/outbox or dedupe ledger, retained provider/factory
  evidence, drill, or incident-to-landed operational measurement exists. No GitHub, GitLab, factory, CI, or
  incident service was contacted, and B6 remains incomplete.
- [ ] Sentinel B7 live admission — the portable core plus `saturation_expiry`, `new_error_signature`,
  `error_rate_vs_baseline`, `change_induced_regression`, and `config_state_drift` constructions are
  present, but human-owned versioned runtime/source/ordering/freshness/coverage policy,
  saturation/expiry sampling and thresholds, signature normalization, deploy/window/baseline/SLO and
  tracked-resource/desired-state policies, immutable config/revision-to-workload binding, an exact Omniscience schema,
  a curated real incident/clean calibration corpus, source ordering/freshness/coverage/liveness and
  read-only identity, controller convergence/deletion and clock-skew semantics, observed lead-time and
  false-positive confidence intervals, noise/cost budgets, delivery/dedup retention, deployed runtime,
  and a disable owner are absent. The 6/6 early and 0/14 false-positive values are deterministic fixture
  results only and do not prove causation, source completeness, or reconciliation; B7 remains
  operationally incomplete. The closed local
  `solutions/sre-harness/spec-traceability/SPEC-B7-CORE.json`,
  `solutions/sre-harness/spec-traceability/SPEC-B7.json`,
  `solutions/sre-harness/spec-traceability/SPEC-B7-NES.json`,
  `solutions/sre-harness/spec-traceability/SPEC-B7-CIR.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B7-DRIFT.json`, and
  `solutions/sre-harness/spec-traceability/SPEC-B7-SAT.json` manifests bind the common core and all five
  detector-family Drafts and probes to existing local tests/implementation.
  They store no PASS result, make no causation or reconciliation claim, and do not authorize a live source,
  runtime, delivery, or action.

## Not Started
- [ ] First pilot engagement
- [ ] Baseline metrics collection
- [ ] Workshop/training materials
- [ ] Populate case studies from real engagements
- [ ] CI/CD integration playbooks
- [ ] IaC assistance playbooks
- [ ] Observability playbooks

## Key Decisions
| Decision | Status | Notes |
|----------|--------|-------|
| Tool stack for pilot | Pending | See research/quick-reference-table.md |
| First pilot team | Pending | Need team assessment |
| AI Incident Agent scope | In Progress | Offline T1 pipeline/eval seam exists; live sources, analyzer and real-incident evaluation remain, see solutions/sre-harness/ |
| ADR-to-SPEC governance | Accepted | ADR-0009; graded SDD, progressive assurance, and distinct conformance/certification gates |

## Next Actions
1. Human-disposition ADR-0002 before selecting the production registry signing/key-owner profile
2. Human-disposition ADR-0003, then its dependent ADR-0006 compatibility proposal
3. Human-disposition ADR-0007 before any platform-portal SPEC adoption or release claim
4. Human-disposition ADR-0008 before authoring the gated AI Security S0/S1 component SPECs
5. Human-disposition ADR-0014 and ADR-0015, then ADR-0016 after its ADR-0006/0015 dependencies
6. Finish and publish the current ADR-0017/SPEC-MCP v1 Omniscience worktree, materialize its immutable source-commit manifest/`contract_info`, provision exact verifier refs, and record canary, token rotation/revoke, consumer-pin, severance, and human evidence
7. Select and assign the cross-stack verified Experience store outside Omniscience; ratify its curation-policy owner, evidence, verifier, and thresholds
8. Name the Terraform Maintainer CODEOWNERS group and pin measured cost/wall-clock breaker inputs
9. Ratify and pin the Human Boundary governance inputs and complete gate-config path manifest
10. Provision the delivery-observation production trust chain only after the ADR-0014/0015/0016 dispositions
11. Review/accept or revise the omnius ADR-0015/0016 + SPEC draft bundle and publish the exact
   CODEOWNER readiness-profile binding, origin, approval revision, and verifier
12. Bind approved read-only incident sources/analyzer and curate real-incident B1 eval thresholds
13. Identify and assess first pilot team
14. Create the first CI/CD playbook and metrics dashboard only from an observed pilot workflow

### 2026-11-07: secondary-store Spot interruption

At 12:49:07 UTC AWS interrupted the node hosting NATS, Qdrant and the isolated Qdrant restore Pod. The original node is gone. Replacement source Pods are Ready, but logical data equivalence is unverified; normal restore guards stopped on changed identities. The seven-artifact off-node native capture remains available, and the isolated Qdrant EBS volume survived unattached. Explicit recovery rehearsal is in progress; full acceptance remains **not passed**. [Incident evidence](docs/synchronized-platform/releases/management-platform-frankfurt-v1/source-checks/eks-secondary-storage-spot-interruption.json).

Follow-up live read confirmed Qdrant has **0 points versus 7 in the verified backup**. NATS recreated its three empty streams and four durables, but exact inventory differs. Restoration has not yet passed.

Qdrant isolated EBS recovery passed exact seven-point comparison and Pod replacement on managed on-demand capacity. NATS native restore completed, but its acceptance gate remains closed while native restore metadata differences are checked. The managed on-demand node group increased desired capacity 2 → 3 within its existing maximum; Terragrunt reconciliation remains required. Production storage cutover is not yet complete.

Both isolated native restore rehearsals are now verified: Qdrant preserves all 7 points across Pod replacement; NATS preserves 3 streams and 4 durables with a reviewed native empty-store equivalence check. Production StatefulSet handoff is still pending. Omniscience collector and separate Barbarossa Frankfurt Helm support passed source tests and review but are not deployed.
