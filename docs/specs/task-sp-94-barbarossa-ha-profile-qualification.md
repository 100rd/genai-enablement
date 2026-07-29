---
id: task-sp-94-barbarossa-ha-profile-qualification
title: Qualify the integrated barbarossa-ha-v1 runtime profile
status: ready
approvedBy: "@100rd"
approvedAt: 2026-07-26
governingAdrs: [genai-enablement/ADR-0012, genai-enablement/ADR-0018, genai-enablement/ADR-0020, genai-enablement/ADR-0022, genai-enablement/ADR-0023]
capabilitySpecs: []
repo: 100rd/genai-enablement
executionProfile: nonproduction-barbarossa-ha-profile-qualification
evidenceDestination: ci-artifact://synchronized-platform/task-sp-94-barbarossa-ha-profile-qualification/
scope:
  include:
    - docs/synchronized-platform/releases/barbarossa-ha-v1/**
    - scripts/qualify_barbarossa_ha_v1.py
    - tests/test_barbarossa_ha_v1.py
    - tests/fixtures/barbarossa-ha-v1/**
  exclude: [docs/decisions/**, docs/specs/**, portfolio/**, solutions/**, terraform/**]
acceptanceCriteria:
  - id: AC-SP94-1
    requirement: One content-addressed profile lock joins exact base profile Barbarossa HA and Portal HA receipts
    probe: barbarossa-ha-profile-release-lock
    expected: SP-89 SP-92 SP-93 and transitive SP-90 SP-91 source image chart schema policy configuration SLO capacity and evidence digests are immutable compatible and independently re-derived
    groundTruth: separately produced owner receipts registry profile revision and clean artifact registries bound to the qualification identity
  - id: AC-SP94-2
    requirement: Distributed work preserves one authoritative history across duplicate and worker-crash boundaries
    probe: barbarossa-ha-commit-ack-crash-matrix
    expected: duplicate crash-before-commit and crash-after-commit-before-ACK cases complete without lost work repeated transition or divergent receipt
    groundTruth: externally injected work broker delivery trace owner-store transaction history outbox publication and final signed receipt set
  - id: AC-SP94-3
    requirement: Fencing ordering retries and quarantine remain safe under concurrency and partitions
    probe: barbarossa-ha-fencing-ordering-dlq
    expected: stale writers fail unexpected sequence work cannot commit and poison work reaches bounded quarantine without automatic redrive or payload disclosure
    groundTruth: controlled lease partition reorder and poison timeline fencing/store rows broker state and owner projection
  - id: AC-SP94-4
    requirement: Selected service and work SLOs survive declared replica broker store and failure-domain faults
    probe: barbarossa-ha-failure-domain-matrix
    expected: API/query and queued work meet quantitative availability latency recovery and integrity objectives across pod loss broker-node loss store failover zone loss and recovery
    groundTruth: independent request/work generators fault-controller timeline external SLO observations quorum state and authoritative receipts
  - id: AC-SP94-5
    requirement: Capacity autoscaling drain rollout and rollback remain stable under sustained burst and soak load
    probe: barbarossa-ha-capacity-lifecycle
    expected: queue age and backlog recover within envelope without retry storms saturation or lost work while scale-in upgrade drain and exact rollback preserve safety
    groundTruth: immutable load model autoscaler events queue/store metrics scheduler events process traces and post-rollback conformance capture
  - id: AC-SP94-6
    requirement: Portal displays exact owner HA truth and remains severable and read-only
    probe: barbarossa-ha-portal-truth-severance
    expected: queue worker dependency capacity rollout and SLO fields preserve units freshness completeness and provenance while stale skew outage recovery and forbidden controls remain correctly typed
    groundTruth: exact SP-92 projection independent API/browser/cache/audit captures tampered fixture matrix and owner-state before-after observations
  - id: AC-SP94-7
    requirement: Tenant PW0 membership and no-effect boundaries survive every load and failure path
    probe: barbarossa-ha-isolation-no-effect
    expected: two-scope seeded PII active content and negative route tests show no disclosure favorable fallback Omnius workload hidden domain activation redrive or managed effect
    groundTruth: independent identity corpus workload DNS route secret-name dependency network broker store log trace audit and UI inventories
  - id: AC-SP94-8
    requirement: Qualification is observable reproducible reversible and non-authorizing
    probe: barbarossa-ha-qualification-integrity
    expected: external alerts runbooks evidence hashes and exact rollback pass while the report grants no production or infrastructure mutation authority
    groundTruth: named environment and fault authority receipts independent alert observer evidence manifest signature and post-rollback inventory
rollback: { kind: revert-pr, probe: remove-unqualified-ha-profile-lock-and-retain-exact-prior-qualified-component-releases }
---

## Intent

Independently join and challenge the exact Barbarossa and Portal HA owner receipts in one authorized
non-production synchronized-platform environment. The task records immutable qualification evidence;
it cannot repair a component, mint an owner receipt or deploy production.

## Required inputs

- exact accepted ADR-0023 and `barbarossa-ha-v1` registry revision;
- immutable SP-89 base-profile, SP-92 Barbarossa HA and SP-93 Portal HA receipts;
- transitive exact SP-90 and SP-91 provenance bound by SP-92;
- named non-production environment receipt with owner, identity, allowed faults and rollback target;
- independently controlled tenant identities, seeded PII/active-content corpus and source observations;
- external load/fault/alert observers and quantitative capacity/SLO targets; and
- prior known-good release digests plus backup/restore target.

Any missing, mutable, incompatible or unverifiable input produces RED/decision-required evidence. It
does not authorize infrastructure mutation, credential requests, direct broker/store repair, mock
substitution or partial PASS.

## Required output

`BarbarossaHaProfileQualification` contains at least:

```text
profile_id/revision/digest; environment/authority receipt digests;
sp89/sp92/sp93 receipt digests; transitive sp90/sp91 provenance digests;
capacity/service_slo/work_slo digests; failure_matrix_digest; load_soak_digest;
tenant/pw0/no_effect/portal_no_control evidence refs; report/evidence_manifest digests;
prior_release/rollback digests; activation_authority=none
```

## Authority boundary

This task authorizes read-only inspection, load generation and only the exact failure/rollback probes
listed in its named non-production authority receipt. It does not authorize Terraform/OpenTofu/
Terragrunt apply or destroy, production deployment, secrets, DNS, redrive, domain/effect activation or
a production-readiness claim.
