---
id: task-sp-60-pii-policy-contract-v1
title: Publish the portable PII policy and receipt contract v1
status: implemented
approvedBy: "@100rd"
approvedAt: 2026-07-21
governingAdrs: [genai-enablement/ADR-0018]
capabilitySpecs: [SPEC-PII-POLICY]
repo: 100rd/genai-enablement
executionProfile: offline-contract
evidenceDestination: ci-artifact://synchronized-platform/task-sp-60-pii-policy-contract-v1/
scope:
  include: [contracts/pii/**, tests/**]
  exclude: [solutions/**, terraform/**, .github/workflows/**]
acceptanceCriteria:
  - id: AC-SP60-1
    requirement: Versioned schemas and manifest implement every SPEC-PII-POLICY contract
    probe: pii-contract-schema-and-fixtures
    expected: positive fixtures validate and downgrade, replay, raw-receipt, lifecycle-collapse and skew fixtures fail
    groundTruth: human-approved task revision and SPEC-PII-POLICY requirement/probe contract, immutable to the execution identity
  - id: AC-SP60-2
    requirement: Contract publication is content-addressed and non-activating
    probe: pii-contract-manifest
    expected: one canonical digest covers schemas and fixtures while no active policy, key or permit issuer exists
    groundTruth: accepted ADR-0018 plus the independently recomputed manifest digest and absence scan
rollback: { kind: revert-pr, probe: remove-unreleased-contract-version }
---

## Intent

Materialize the portable `SP-60` schema/fixture/validator bundle. This task may create development-only
test keys or signatures inside fixtures, but no credential, cloud key, active policy, provider call,
runtime gate, deletion or export.

## Decision returns

Return RED with the exact missing schema or semantic rule. Do not invent legal classifications,
retention periods, active publisher identity or production trust roots.
