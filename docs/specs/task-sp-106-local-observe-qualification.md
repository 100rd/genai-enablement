---
id: task-sp-106-local-observe-qualification
title: Independently qualify local observations Codex analysis and Portal recovery
status: ready
approvedBy: platform-owner-via-implementation-request
approvedAt: 2026-11-06
repo: 100rd/genai-enablement
governingAdrs: [ADR-0025]
evidenceDestination: docs/synchronized-platform/releases/management-local-observe-v1/
scope:
  include: [scripts/qualify_local_observe.py, tests/test_local_observe_qualification.py, docs/synchronized-platform/releases/management-local-observe-v1/**]
  exclude: [contracts/pii/**, solutions/**]
acceptanceCriteria:
  - {id: AC-SP106-1, requirement: Exercise the real failure-case-analysis-UI-recovery chain, probe: live-local-observe, expected: correlated source observations case assessment and recovery with bounded model calls, groundTruth: independently induced disposable-service outage plus owner API and browser captures}
  - {id: AC-SP106-2, requirement: Isolate tenants and reject invalid results and stale leases, probe: local-observe-negative-matrix, expected: no cross-tenant read accepted forgery duplicate result or managed effect, groundTruth: independent identities signed-invalid inputs and captured owner ledger rows}
  - {id: AC-SP106-3, requirement: Retain durable history and budgets across restart, probe: local-observe-restart, expected: attempts and results survive without duplicate accepted analysis, groundTruth: before-after database queries and process termination timeline}
rollback: {kind: stop-new-profile, probe: preserve-observation-history}
---

No fixture-only pass replaces live or browser acceptance. The receipt records exact source content
digests, dirty flags, host architecture and unverified gates. No production or HA authority is issued.
