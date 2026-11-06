---
id: task-sp-102-local-observe-contract
title: Record the approved local observation composition and interfaces
status: ready
approvedBy: platform-owner-via-implementation-request
approvedAt: 2026-11-06
repo: 100rd/genai-enablement
governingAdrs: [ADR-0025]
evidenceDestination: docs/synchronized-platform/releases/management-local-observe-v1/
scope:
  include: [deploy/local/management-local-observe-v1/**, scripts/local_observe.py, tests/test_local_observe.py]
  exclude: [contracts/pii/**, solutions/**]
acceptanceCriteria:
  - {id: AC-SP102-1, requirement: Compose isolated owner artifacts without widening older profiles, probe: local-observe-composition, expected: exact three owners and private distinct volumes with loopback bindings, groundTruth: rendered Compose model and original project inventory}
  - {id: AC-SP102-2, requirement: Preserve configuration and data on repeat launch and stop, probe: local-observe-lifecycle, expected: no credential replacement or volume removal, groundTruth: independently hashed files and before-after volume inventory}
rollback: {kind: stop-new-profile, probe: retained-local-observe-volumes}
---

The approved plan is ADR-0025. This task owns integration glue only. The source registry and this
acceptance contract are maintained by the Lead separately from implementation.
