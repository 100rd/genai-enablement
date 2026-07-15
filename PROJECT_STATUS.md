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
  drafted for separate human acceptance/readiness review
- [ ] **Platform skill-registry trust root** — ADR-0002 defines git-backed pinned consumption,
  but the current `skills-lock.json` carries only content hashes: select a human-owned signing
  mechanism/key owner and publish exact immutable git revisions before Omnius P1 REG activation.
  Until then Omnius must reject the live lock as unsigned/unpinned; executable `scripts/` remain
  disabled for the first governed vertical.
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
2. Review/accept or revise the omnius ADR-0015/0016 + SPEC draft bundle
3. Complete AI Incident Agent implementation
4. Identify and assess first pilot team
5. Create first CI/CD playbook from real workflow
6. Set up metrics dashboard
