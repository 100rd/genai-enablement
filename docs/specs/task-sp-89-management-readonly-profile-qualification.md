---
id: task-sp-89-management-readonly-profile-qualification
title: Qualify the integrated management-readonly-v1 runtime profile
status: ready
approvedBy: "@100rd"
approvedAt: 2026-07-25
governingAdrs: [genai-enablement/ADR-0012, genai-enablement/ADR-0018, genai-enablement/ADR-0020, genai-enablement/ADR-0021, genai-enablement/ADR-0022]
capabilitySpecs: []
repo: 100rd/genai-enablement
executionProfile: nonproduction-profile-qualification
evidenceDestination: ci-artifact://synchronized-platform/task-sp-89-management-readonly-profile-qualification/
scope:
  include:
    - docs/synchronized-platform/releases/management-readonly-v1/**
    - scripts/qualify_management_readonly_v1.py
    - tests/test_management_readonly_v1.py
    - tests/fixtures/management-readonly-v1/**
  exclude: [docs/decisions/**, docs/specs/**, portfolio/**, solutions/**, terraform/**]
acceptanceCriteria:
  - id: AC-SP89-1
    requirement: One content-addressed profile lock joins exact SP-86 SP-87 and SP-88 owner releases and the SP-90 Go baseline transitively bound by SP-87
    probe: management-readonly-release-lock
    expected: Git image chart schema policy configuration and evidence digests are complete immutable compatible and independently re-derived
    groundTruth: separately produced SP-90 and owner release receipts plus registry profile revision immutable to the qualification identity
  - id: AC-SP89-2
    requirement: Runtime membership contains only Omniscience Barbarossa and Platform Portal
    probe: management-readonly-membership-and-no-effect
    expected: Omnius and every unselected action effect autonomy and domain adapter are absent from workloads DNS configuration credentials routes and observed traffic
    groundTruth: independent environment workload network DNS route and secret-name inventory joined to the accepted ADR-0021 selection
  - id: AC-SP89-3
    requirement: The selected tenant PW0 Reliability and source-bound Portal journeys pass end to end
    probe: management-readonly-e2e-matrix
    expected: two-tenant containment seeded-PII rejection deterministic Reliability and exact owner projections pass without mocks or favorable unknowns
    groundTruth: independent tenant identities seeded canary corpus human-owned SLO/source revision and captured API/UI/telemetry evidence
  - id: AC-SP89-4
    requirement: Every selected component and optional source can be severed without fabricated truth
    probe: management-readonly-severance-skew-recovery
    expected: stale skew outage restart and projection rebuild remain typed preserve unrelated operation and reject stale writers
    groundTruth: independently induced failure timeline component source observations and durable-store revision history
  - id: AC-SP89-5
    requirement: The named non-production profile is observable recoverable and reversible
    probe: management-readonly-operations-rollback
    expected: health SLO alert backup restore and exact-digest rollback evidence pass and no activation or production claim is emitted
    groundTruth: environment-owner receipt external alert observation isolated restore result and post-rollback conformance capture
  - id: AC-SP89-6
    requirement: The deployed Barbarossa workload is built only from the accepted SP-90 Go production baseline
    probe: management-readonly-barbarossa-go-runtime
    expected: exact compiler module SBOM binary image and process evidence match SP-90 and no Node.js package manager transpiler JavaScript sidecar or TypeScript fallback exists
    groundTruth: independently captured SP-90 receipt OCI SBOM image filesystem process command and network inventory from the named environment
rollback: { kind: revert-pr, probe: remove-unqualified-profile-lock-and-retain-last-qualified-owner-releases }
---

## Intent

Join and independently validate the three owner-produced release receipts for
`management-readonly-v1`. The task creates a qualification runner, fixtures, one content-addressed
release lock and a report. It cannot repair a component, mint a sibling receipt, edit the portfolio
selection, or replace missing environment evidence with mocks.

## Required inputs

- exact accepted ADR-0021 and profile revision;
- immutable SP-90 baseline receipt carried and transitively bound by SP-87, plus exact SP-86, SP-87 and
  SP-88 owner release receipts;
- one named non-production environment receipt with owner, identity, allowed operations, observation
  window and rollback target;
- independently controlled tenant identities, seeded PII/active-content corpus, Reliability source/SLO
  revision, failure-injection authority and alert observer; and
- prior known-good release digests and backup/restore target.

Any missing, mutable, incompatible or unverifiable input produces RED/decision-required evidence. It
does not authorize an infrastructure mutation, credential request, mock substitution or partial PASS.

## Authority boundary

This task authorizes read-only inspection and explicitly approved failure/rollback qualification only
inside the named non-production target. It does not authorize Terraform/OpenTofu/Terragrunt apply or
destroy, production deployment, secret creation, DNS change, policy activation, external effect,
Omnius runtime enablement, or a production-readiness claim.
