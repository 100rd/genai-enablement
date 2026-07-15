# GenAI Enablement - Project Status

**Last Updated**: 2026-07-15
**Phase**: Autonomous SRE Harness development — Stages 0 & 2 shipped, Stage 7 (Sentinel) step 1 shipped
**Overall Health**: On Track

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
- [x] Implementation roadmap document
- [x] Success metrics framework
- [x] Engagement templates (kickoff, assessment, playbook, ROI tracker)
- [x] **Agentic SRE landscape refresh (June 2026)** — 3 parallel research threads (market, architecture, AWS-native)
- [x] **Autonomous SRE Harness plan v2** — autonomy-tier model, action-tier governance, revised roadmap
- [x] **Sentinel (Stage 7, build-order step 1)** — continuous-detection detector contract + registry + dedup + `severity × confidence` ranking, two deterministic detectors (`saturation_expiry`, `new_error_signature`), and a **lead-time** eval (seed suite + false-positive control). Deterministic, offline, unit-tested; no LLM.
- [x] **Organizational Dark Factory SDD governance** — ADR-0009 accepted with graded SDD,
  progressive assurance, and distinct conformance/certification gates

## In Progress
- [ ] **Repository adoption** — omnius ADR-0015/0016 and SPEC-IN/ROLE/EXP/REG/OT/TM remain
  drafted for separate human acceptance/readiness review. Omnius now has a non-authorizing
  `standard-http-service/v3` readiness draft and a deterministic compiler that fails closed on schema,
  immutable revision/path-bundle pin, dependency, registered-probe, blocker, and probe-result drift;
  this implementation evidence does not accept the ADRs or activate the profile.
- [ ] **Platform skill-registry trust root** — ADR-0002 defines git-backed pinned consumption,
  but the current `skills-lock.json` carries only content hashes: select a human-owned signing
  mechanism/key owner and publish exact immutable git revisions before Omnius P1 REG activation.
  Until then Omnius must reject the live lock as unsigned/unpinned; executable `scripts/` remain
  disabled for the first governed vertical.
- [ ] **Omniscience MCP contract and workspace-token seam** — select the immutable contract-version
  pin/CI-skew mechanism and name the human-owned workspace read-token issuer, rotation cadence, and
  closed read scopes before Omnius KP activation. Omnius may implement and test the fail-closed client
  contract, but must use direct-source severance and reject an unpinned contract or any write/admin
  token until the platform binding exists.
- [ ] **Cross-stack Experience store placement** — select the physical store and operational owner for
  verified Experience beside, but not inside, Omniscience. The store must preserve the state/capability/
  experience authority split, tenant isolation, immutable evidence joins, and cold-start severance;
  Omnius may implement the portable contract but cannot claim P3 Experience activation before binding it.
- [ ] **Terraform Maintainer Standing Role activation inputs** — name the human CODEOWNERS group that
  owns the first role definition and pin its cost/wall-clock breaker values from measured curation-pilot
  evidence. Until both owner and threshold provenance are human-approved immutable revisions, Omnius may
  implement the ROLE contract but must keep autonomous activation disabled and route unmatched,
  production, irreversible, apply, direct-state, and unpinned-skill work to a human.
- [ ] **Human Boundary governance inputs** — ratify the auth/MFA production-migration Class-2
  (human-forever) disposition; pin game-day cadence/pass thresholds, the `awaiting_human` target and
  benign-reject allowance, and the deterministic Mode-B discarded-candidate degeneracy rule; publish
  the complete human-owned gate-config path manifest. Until these versioned inputs and accountable
  owners exist, Omnius must use the stricter human-gated/default-deny branches and cannot claim HB
  activation, rehearsed removability, or an autonomy increase.
- [ ] **Delivery observation and HTTP evidence trust chain** — review and accept or revise proposed
  ADR-0014/0015/0016, then publish the exact production identities and immutable trust profiles for
  the HTTP subject issuer/result signer, observer-authority attestor, and safe-to-reclaim issuer. Pin
  their distinct EKS Pod Identity/IAM boundaries and asymmetric KMS keys, the create-only S3 evidence
  profile and receipt store, and the human-owned readiness revision. Until those protected bindings
  and real-path negative/failure evidence exist, `standard-http-service/v3` remains catalog-only with
  only a `draft` readiness profile; the candidate record remains `admitted: false` with
  `readinessProfile: null`. Local process-memory signatures, PVC storage, kind qualification, and the
  draft compiler cannot activate a Realm, production path, or autonomous merge.
- [ ] AI Incident Agent — complete implementation and testing
- [ ] Detailed implementation roadmap refinement per team

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
| AI Incident Agent scope | In Progress | LangGraph-based, see solutions/ |
| ADR-to-SPEC governance | Accepted | ADR-0009; graded SDD, progressive assurance, and distinct conformance/certification gates |

## Next Actions
1. Select the platform skill-registry lock signing mechanism/key owner and exact-revision schema
2. Select the Omniscience MCP contract pin/skew check and workspace read-token issuer/rotation/scopes
3. Select and assign the cross-stack verified Experience store outside Omniscience
4. Name the Terraform Maintainer CODEOWNERS group and pin measured cost/wall-clock breaker inputs
5. Ratify and pin the Human Boundary governance inputs and complete gate-config path manifest
6. Review/accept or revise ADR-0014/0015/0016 and provision the delivery-observation production trust chain
7. Review/accept or revise the omnius ADR-0015/0016 + SPEC draft bundle
8. Complete AI Incident Agent implementation
9. Identify and assess first pilot team
10. Create first CI/CD playbook from real workflow
11. Set up metrics dashboard
