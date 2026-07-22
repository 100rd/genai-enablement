# Implementation roadmap

**As of:** 2026-07-19
**Operating model:** evidence-gated build order, not a calendar forecast

This roadmap replaces the original month-based enablement outline. The program now has four distinct
tracks with different authorities and completion evidence:

- the Organizational Dark Factory P0 vertical implements accepted cross-repository decisions through
  exact component SPEC/readiness slices;
- the Autonomous SRE harness develops read-only and advisory safety capabilities independently of Dark
  Factory activation; and
- the Continuous Management Plane runs independently qualified, never-ending management domain loops
  through Barbarossa; and
- the enablement pilot starts only after a human selects a team and baseline.

Passing tests or finishing code never advances a human or production gate by implication. Current truth is
maintained in [PROJECT_STATUS](../PROJECT_STATUS.md); machine-readable project and blocker facts live in
[`portfolio/projects.json`](../portfolio/projects.json).

## Authority and transition rules

The accepted authority chain is:

1. [ADR-0009](decisions/0009-organizational-dark-factory-sdd.md): humans decide in ADRs; agents execute
   bounded SPECs and cannot redefine their oracle.
2. [ADR-0010](decisions/0010-goal-oriented-organizational-dark-factory.md): discovery may begin from a
   goal, but mutation requires a governed WorkOrder and SPEC.
3. [ADR-0012](decisions/0012-capability-readiness-profiles.md): readiness is an immutable exact
   requirement/probe/revision profile, not whole-document optimism.
4. [ADR-0017](decisions/0017-omniscience-mcp-v1-contract-and-severance.md): Omniscience MCP v1 is
   content-addressed, workspace-bound, freshness-aware, and severable.

Three decision surfaces remain independent:

| Surface | Current Track-A result | What it permits | What it cannot permit |
|---|---|---|---|
| Contract conformance | Local contract conformance is `CONFORMANT` | Continued construction and review | Target activation, production promotion, or autonomy widening |
| Assurance certification | Target assurance certification remains `RED` | Nothing beyond reporting missing controls | Treating waivers or portable probes as real-path evidence |
| Capability readiness | `p0-standard-http-service-v3` is `draft` | Non-authorizing planning and deterministic fixtures | Realm admission, execution, merge, or self-approval |

No stage may infer a stronger decision from a weaker surface. Every transition below names its own
evidence and owner.

## Human-owned decision backlog

The acceptance-readiness audit is complete for the currently Proposed portfolio ADRs, but
their status has not changed. The authoritative machine set is `portfolio/projects.json`; the drift gate
joins it to every source ADR and the human portfolio view. `Requires` orders only dispositions that build
on another Proposed decision. The backlog does not accept any decision and grants no execution, component
adoption, readiness, release, or provider authority.

| Decision | Review group | Requires | Blocks | Next gate |
|---|---|---|---|---|
| [ADR-0002](decisions/0002-platform-skills-registry.md) | `registry-trust` | — | `skill-registry-adoption` | `human-disposition` |
| [ADR-0003](decisions/0003-unified-sdlc-standard.md) | `cross-factory-sdlc` | — | `cross-factory-sdlc-adoption` | `human-disposition` |
| [ADR-0006](decisions/0006-unified-loop-decision-model.md) | `cross-factory-sdlc` | `ADR-0003` | `cross-factory-loop-adoption` | `human-disposition` |
| [ADR-0007](decisions/0007-platform-portal-federated-surface.md) | `portal-experience` | — | `platform-portal-spec-adoption` | `human-disposition` |
| [ADR-0008](decisions/0008-ai-security-domain.md) | `ai-security` | — | `ai-security-s0-s1-spec-authorship` | `human-disposition` |
| [ADR-0014](decisions/0014-precommitted-http-condition-evidence.md) | `delivery-evidence` | — | `http-evidence-adoption` | `human-disposition` |
| [ADR-0015](decisions/0015-independent-observer-authority-attestor.md) | `delivery-evidence` | — | `observer-attestation-adoption` | `human-disposition` |
| [ADR-0016](decisions/0016-independent-safe-to-reclaim-decision-issuer.md) | `delivery-evidence` | `ADR-0006`, `ADR-0015` | `safe-to-reclaim-adoption` | `human-disposition` |
| [ADR-0018](decisions/0018-pii-wall-purpose-bound-data-boundary.md) | `privacy-boundary` | `ADR-0003`, `ADR-0007`, `ADR-0008` | `pii-wall-component-adoption` | `human-disposition` |
| [ADR-0020](decisions/0020-barbarossa-continuous-management-plane.md) | `continuous-management-plane` | — | `barbarossa-continuous-management-adoption` | `human-disposition` |

## Team and repository ownership

| Repository/team | Owns in this roadmap | Explicitly does not own |
|---|---|---|
| `genai-enablement` | Portfolio order, cross-repository ADRs, readiness blockers, reusable Autonomous SRE harness, pilot metrics | Component SPEC/API schemas, live availability/incident state, or execution truth |
| `Barbarossa` | Shared management-loop kernel, isolated domain packs, independent evaluation/verification, constraints, cases, agent federation and projections | Human objectives/policy/risk acceptance, Omniscience semantic truth, Omnius execution, Portal composition, or PII policy |
| `omnius` | Dark Factory capability/task SPECs, readiness compiler, Conductor, deterministic probes, P0 evidence admission | Omniscience internals, platform infrastructure, or human approval |
| `Omniscience` | MCP v1 producer contract, manifest/schemas, token lifecycle, release materialization, canary and producer evidence | Omnius planning decisions or platform-wide readiness |
| `platform-design` | Platform contract bundles, identity/security/policy substrate, Realm and infrastructure design evidence | Factory orchestration or portfolio decisions |
| `platform-workflows` | Shared delivery enforcement and append-only workflow/evidence mechanics | Product correctness or readiness approval |
| `platform-portal` | Federated tenant-facing view and Continuous Management Center after contracts are ready | Decision logic, execution authority, or a second source of truth |
| `multiqlti` | Personal Dark Factory and bounded proving-ground observations | Shared production Experience authority or organizational readiness |

## Track A — Organizational Dark Factory P0

The active vertical is `standard-http-service/v3` under draft profile
`p0-standard-http-service-v3`. Its component profile currently selects 15 capabilities, 129 requirements,
126 probes, 11 readiness blockers, and 14 forbidden actions. Omniscience remains
`direct-source-fallback` until its exact MCP release and consumer evidence exist.

### Dependency-ordered gates

| Gate | Owner(s) | Current state | Required exit evidence |
|---|---|---|---|
| `A0` | `genai-enablement` + human platform owner | Complete for ADR-0009/0010/0012/0017 | Accepted decisions remain linked to their component adoption ADR/SPEC surfaces |
| `A1` | `omnius` | Implementation evidence is extensive but dirty/unpublished | Clean immutable component revision; exact capability manifests containing every selected REQ/probe owner; full conformance rerun; no claim of readiness |
| `A2` | `Omniscience` + `omnius` | MCP v1 mechanisms exist only in a dirty producer worktree; consumer is severed | Immutable producer release bundle and `contract_info`; exact verifier references; workspace token create/rotate/revoke audit; deployed canary receipt; consumer pin and severance drill |
| `A3` | Human owner + `platform-design` + `platform-workflows` | Blocked on decisions and production bindings | Accepted/revised delivery ADRs; distinct workload/control identities and asymmetric keys; create-only evidence/receipt stores; protected-path and failure evidence |
| `A4` | `omnius` + `platform-design` + `platform-workflows` | Portable mechanisms only | Exact P0 worker/verifier adapter qualification, Docker/real-cluster positive and negative matrices, complete exact-revision real-path probe publication |
| `A5` | Human profile CODEOWNER + `omnius` | Blocked; profile remains draft | Externally verified platform bundle/path publication, Realm admission, capability manifests, unexpired probe evidence, delivery-trust capability, and exact human profile publication |
| `A6` | `omnius` + component owners | Not admitted | One bounded preview Realm executes the exact profile; no production, shared-state, direct-deploy, data, secret, multi-repository, policy/probe, self-approval, or auto-merge mutation |
| `A7` | `genai-enablement` + selected Experience owner | Blocked on store placement and pilot evidence | Verified outcome/return joins, assigned cross-stack Experience store, approved curation policy, measured pilot baseline and escape feedback without authority leakage |

`A1` and `A2` may continue as separately reviewable construction work. `A3` requires explicit human and
production choices. `A4` cannot substitute portable fixtures for `A3`; `A5` cannot start from a dirty
revision; `A6` cannot widen beyond its exact profile; and `A7` cannot place shared state inside
Omniscience or promote a proving-ground store by convention.

The current bounded A1 readiness/conformance Python surface is static-clean across all 14 new files and
passes its focused contract/coverage checks. That local result does not conceal the repository-wide legacy
baseline: full-tree Ruff still reports 119 findings and the formatter reports 144 files outside its
baseline. Retiring that debt is construction work; neither the bounded green surface nor a future bulk
cleanup can substitute for A1's immutable revision and exact publication evidence.

### Current Track-A blockers requiring human or external state

- select the platform skill-registry signing mechanism, key owner, and exact-revision lock schema;
- publish the immutable Omniscience MCP v1 producer revision and provision concrete verifier/token/canary
  evidence;
- select the shared Experience store and operational/curation owners;
- name the Terraform Maintainer CODEOWNERS group and approve measured breaker inputs;
- ratify Human Boundary governance inputs and the complete protected gate-config manifest;
- accept or revise the delivery-observation/trust-chain ADR set and provision its production identities;
- accept or revise the Omnius adoption/readiness bundle and publish its exact CODEOWNER authority; and
- select the pilot team and Realm only after the vertical is evidence-ready.

None of these inputs may be invented from fixtures, test constants, existing cloud credentials, or an
agent-authored approval field.

## Track B — Autonomous SRE harness

This track follows the build order in the
[Autonomous SRE harness plan](autonomous-sre-harness-plan.md). It remains useful while Track A is blocked,
but it receives no Dark Factory authority from that independence.

The machine-readable `track_b_spec_backlog` in `portfolio/projects.json` binds every current Track-B
source SPEC to its exact Draft status, roadmap gate, dependency ids, contiguous REQ/probe counts, and
external next gate. Its aggregate state is `external-evidence-required`. The thirteen-SPEC catalog now
covers `B0..B7`, the common Sentinel core, and all five accepted ADR-0001 detector families. This planning
join explicitly does not authorize live sources, provider calls, credentials, deployment, remediation, a
pilot, or any production claim; each row remains `local-construction-only` and operationally
`incomplete`.

All thirteen Track-B rows now point to closed
`solutions/sre-harness/spec-traceability/SPEC-B0.json` and
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
`solutions/sre-harness/spec-traceability/SPEC-B7-SAT.json` local manifests. The offline checker rejoins
each exact SPEC digest, every source probe id, existing pytest nodes, implementation paths, and
non-authorizing state. No `portable_traceability_manifest` field remains null; the manifests store no PASS
result and do not advance any external next gate.
Traceability registry summary: `13` checked manifests; `0` remaining null.

| Stage | Current state | Next evidence-gated outcome |
|---|---|---|
| [`B0`](specs/SPEC-B0-offline-eval-harness.md) Eval harness | Shipped portable baseline: immutable scenario/target/scorer seam, honest Pass@1 and lead-time metrics, deterministic seed suites, explicit unsupported metric failures, and closed `SPEC-B0.json` traceability; current labels remain fixtures | Human-own and immutably publish a representative corpus, labels/provenance, metric applicability, regression/stop thresholds, retention, and observed runs bound to an immutable harness revision |
| [`B1`](specs/SPEC-B1-read-only-triage-rca.md) Read-only triage and RCA | The bounded offline slice now includes strict v1 source ingestion, gather/analyze/RCA, exact request/citation rejoin, fixture-ineligible thresholds, and a fail-closed external corpus-publication capability with exact policy/scenario-manifest rejoin; three seed replays pass locally but no live source/model/corpus publication exists | Bind approved Datadog/log/metric/deploy sources and analyzer through the SPEC-B1 ports, curate and externally publish real incident ground truth/thresholds through the publication gate, and measure usefulness/false positives; retain no write tools |
| [`B2`](specs/SPEC-B2-advisory-change-validation-integration.md) Advisory change-validation gate | Shipped deterministic core plus a dirty/local strict content-addressed CI/PreSync envelope/result and status-preserving non-blocking templates; no observed real consumer run exists | Wire one approved live platform/change producer into a real CI/PreSync advisory run, retain its immutable result and measurements, while deterministic policy remains the final proceed/block/require-human authority |
| [`B3`](specs/SPEC-B3-deterministic-canary-rollback.md) Deterministic rollback | Dirty/local portable construction slice: a closed content-addressed fixture candidate, offline three-state decision oracle, and deterministic hardened Service/Datadog v2 AnalysisTemplate/basic-canary Rollout JSON bundle; no cluster, credential, accepted threshold, or observed rollback is bound | Human-select and immutably publish the workload, threshold, Datadog queries/tags, Secret owner, and controller/CRD versions; pass server-side admission plus observed positive promotion and forced-negative stable rollback, then measure rollback latency and false positives; no LLM in the decision path |
| [`B4`](specs/SPEC-B4-tier4-allowlisted-remediation.md) Tier-4 allowlisted remediation | Dirty/local portable construction slice: a closed content-addressed policy/request contract, externally verified capability gate, existing-tier-table authorization, exact account/region/version/hash-bound SSM calls, deterministic idempotence, one-step compensation, and non-secret transition notifications; the checked policy is fixture-only and no AWS account was contacted | Human-approve and immutably publish the exact production allowlist/runbooks, IAM/PassRole and target boundaries; bind durable compare-and-swap orchestration plus idempotent delivery; then retain positive, retry, off-plan, forced-failure, rollback-failure, notification-failure, expiry, and permission-denial drills with blast-radius/latency/false-positive measurements |
| [`B5`](specs/SPEC-B5-tier3-hitl-remediation.md) Tier-3 HITL remediation | Dirty/local portable construction slice: closed content-addressed proposals/receipts, runtime-revision-pinned canonical T3 classification, exact-boolean external human authority, first-step SSM `Approve`/`Reject` signaling through a deduping port, read-only protected GitLab MR approval observation, finite expiry/reject/escalation state, and sanitized audit; checked artifacts are fixtures and no provider was contacted | Human-select and immutably publish identity/MFA/reviewer eligibility, exact runbook/MR policies and separate principals; bind durable CAS/outbox plus provider/audit adapters; retain approve/reject/expiry/stale-head/rule-drift/duplicate/concurrency/permission/recovery drills before claiming live HITL execution |
| [`B6`](specs/SPEC-B6-permanent-fix-chase.md) Permanent-fix chase | Dirty/local portable construction slice: closed content-addressed request/policy/outcome contracts, exact-boolean external capabilities, one idempotent bounded issue-create port, read-only issue plus factory-created MR/PR observation, monotonic verified/gated/landed joins, exact merged-head two-source agreement, finite escalation, sanitized audit, and closed local `solutions/sre-harness/spec-traceability/SPEC-B6.json`; checked request/policy artifacts are fixtures and no provider or factory was contacted | Human-select and immutably publish repository/label/branch plus factory-outcome policies; bind separate least-privilege issue-write and read-only chase principals, durable CAS/outbox and create-dedupe ledger; retain create/race/ambiguity/stale-head/verification/gate/merge/timeout/permission/audit/recovery drills and exact `incidentId`→`taskId`→landed-revision evidence before closing an incident |
| [`B7-CORE`](specs/SPEC-B7-core-sentinel-runtime-contract.md) / [`B7`](specs/SPEC-B7-error-rate-baseline-detector.md) / [`B7-NES`](specs/SPEC-B7-new-error-signature-detector.md) / [`B7-CIR`](specs/SPEC-B7-change-induced-regression-detector.md) / [`B7-DRIFT`](specs/SPEC-B7-drift-detector.md) / [`B7-SAT`](specs/SPEC-B7-saturation-expiry-detector.md) Sentinel continuous detection | Deterministic common core and all five ADR-0001 detector families now have source SPECs plus closed traceability: saturation/expiry, new signature, error-rate, deploy-correlation, and config↔state drift. Portable fixtures cover exact common scan/store/CLI contracts, detector rules, six positive-lead incidents, fourteen clean controls, and explicit early-detection/false-positive metrics; no live source, accepted production threshold/policy, clustering, causation, reconciliation, delivery, or runtime claim | Human-own and version runtime/source/ordering/freshness/coverage policy; saturation/expiry sampling and thresholds; signature normalization; deploy/window/baseline/SLO and tracked-resource/desired-state policies; immutable config/revision-to-workload binding and exact Omniscience schema; calibrate on a curated real incident/clean corpus; retain observed confidence intervals, noise/cost budgets, read-only identity, delivery/dedup, acknowledgement, and disable evidence |

Cross-cutting requirements are autonomy-tier degradation, deterministic gates outside prompts, immutable
audit, cost/wall-clock budgets, evidence provenance, and no model-supplied authorization.

## Track M — Barbarossa Continuous Management Plane

Barbarossa is a separate synchronized-platform project under proposed
[ADR-0020](decisions/0020-barbarossa-continuous-management-plane.md). Superseded
[ADR-0019](decisions/0019-barbarossa-independent-reliability-plane.md) remains the Reliability domain's
design history. Track B supplies reusable harness/evaluation/detector construction; Track M owns the
shared loop runtime and domain qualification. Neither track inherits live authority from the other.

| Gate | Owner | Current state | Required exit evidence |
|---|---|---|---|
| `M0` governance | `genai-enablement` + human platform owner | ADR-0020 Proposed; registry/plan planning-complete | ADR disposition, local adoption and exact task/readiness selections |
| `M1` kernel foundation | `Barbarossa` | `SPEC-LOOP/DOM/OBS/EVAL/CASE` complete-for-planning | durable store/clock/identity/isolation, PII policy, real corpus and failure recovery |
| `M2` coordination and constraints | `Barbarossa` | `SPEC-FED/CFL` complete-for-planning | leases/fencing/budgets plus human-owned hard/soft constraint and conflict policy |
| `M3` actions and verification | `Barbarossa`, `omnius` | consumer contracts complete; producer SPEC absent | owner action/receipt/reconciliation release, independent sources, rollback and drills |
| `M4` domain packs | domain policy owners + `Barbarossa` | 12 packs complete-for-planning | separate policy, sources, evaluator corpus, owners and qualification for each selected pack |
| `M5` knowledge/context integration | `Omniscience`, `Barbarossa` | consumer contract complete; producer SPEC absent | released context/knowledge-quality schema, auth/freshness/citations and severance evidence |
| `M6` Continuous Management Center | `Barbarossa`, `platform-portal` | projection contract complete; Portal SPEC absent | released projections plus Portal view-never-authority and per-source severance evidence |
| `M7` progressive autonomy | human policy owner + `Barbarossa` + `omnius` | planning-complete-blocked | one exact domain/action live profile, identities, hard constraints, fencing, rollback, kill switch and forced-negative drills |

Reliability preserves an independently operable `probe -> admit -> evaluate -> persist -> alert` path.
Other domains reuse the kernel but never borrow Reliability truth, policy or readiness. Omniscience,
Omnius and Portal remain severable. The complete 29-SPEC and `SP-70…SP-85` mapping is in the
[synchronized-platform plan](synchronized-platform/README.md).

## Track C — Enablement pilot

This track is intentionally not started. A real pilot is an observed program, not a synthetic success
claim.

| Gate | Human/technical owner | Required evidence |
|---|---|---|
| `C0` Select pilot | Human enablement owner + participating team | Named team/service, consent, scope, exclusions, owners, support window |
| `C1` Baseline | Team + `genai-enablement` | DORA/operational baseline, incident/change sample, data-access assessment, success and stop thresholds |
| `C2` Read-only pilot | Team + Track-B owners | Bounded triage/advisory workflow, audit and severance, no mutation authority, measured usefulness and false positives |
| `C3` Advisory delivery gate | Team + `platform-workflows` | One real CI/CD path, deterministic verdict authority, override/rollback procedure, measured latency and catch rate |
| `C4` Replicate or stop | Human portfolio owner | Evidence-backed ROI/quality review; case study only from real results; explicit decision to expand, revise, or stop |

Training material, playbooks, dashboards, and case studies follow `C0`–`C4`; they are not completion evidence
before a pilot exists.

## Verification and planning handoff

From `project/genai-enablement`:

```bash
python3 scripts/check_portfolio_drift.py
python3 scripts/check_portfolio_drift.py --omnius-root ../omnius
python3 -m unittest discover -s tests -p 'test_portfolio_drift.py'
```

The default portfolio check is hermetic. The explicit sibling command is read-only and rejoins the current
Omnius source-profile digest/counts, Git HEAD, and dirty/clean state; it does not make dirty evidence
immutable.

For every completed gate:

1. update component-owned SPEC/task/execution evidence in the owning repository;
2. update [`PROJECT_STATUS.md`](../PROJECT_STATUS.md) and the machine-readable portfolio without copying
   component contracts;
3. record the exact decision surface and verification result in `project/PROJECT_HISTORY.md`; and
4. leave every downstream gate unchanged until its own required evidence is observed.

## Definition of roadmap completion

This roadmap is complete as a planning artifact when every active stream has an owner, dependency order,
entry/exit evidence, and explicit non-authority boundary. It is not a claim that Tracks A, B, M, or C
are complete. Product completion still requires the component evidence and human/external gates named
above.
