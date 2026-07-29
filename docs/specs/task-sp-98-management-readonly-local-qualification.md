---
id: task-sp-98-management-readonly-local-qualification
title: Compose and qualify the local Management Read-Only synchronized platform
status: ready
approvedBy: "@100rd"
approvedAt: 2026-07-29
governingAdrs: [genai-enablement/ADR-0012, genai-enablement/ADR-0018, genai-enablement/ADR-0021, genai-enablement/ADR-0022, genai-enablement/ADR-0023, genai-enablement/ADR-0024]
capabilitySpecs: []
repo: 100rd/genai-enablement
executionProfile: management-readonly-local-v1-functional-smoke
evidenceDestination: ci-artifact://synchronized-platform/task-sp-98-management-readonly-local-qualification/
scope:
  include:
    - deploy/local/management-readonly-v1/**
    - scripts/generate_management_readonly_local_env.py
    - scripts/qualify_management_readonly_local.py
    - tests/test_management_readonly_local.py
    - tests/fixtures/management-readonly-local-v1/**
    - docs/synchronized-platform/releases/management-readonly-local-v1/**
    - .github/workflows/management-readonly-local.yml
  exclude: [docs/decisions/**, docs/specs/**, portfolio/**, solutions/**, terraform/**]
acceptanceCriteria:
  - id: AC-SP98-1
    requirement: One Compose application assembles only exact owner-published local fragments and receipts
    probe: synchronized-local-compose-lock
    expected: SP-95 SP-96 SP-97 fragment service contract image or source configuration and rollback digests re-derive while mutable missing dirty-as-reproducible or copied owner configuration is RED
    groundTruth: separately produced owner receipts exact Git or OCI identities and the fully rendered Compose model
  - id: AC-SP98-2
    requirement: Rendered membership networking ports and credentials preserve owner and profile boundaries
    probe: synchronized-local-topology-containment
    expected: namespaced exact service network volume and loopback binding inventory passes with Portal read-only owner reachability and no Omnius mock public support port shared store broker owner-write credential or port collision
    groundTruth: rendered Compose JSON container network socket DNS environment-key secret-name and route inventories
  - id: AC-SP98-3
    requirement: The stack starts and stops through one documented bounded lifecycle without races or implicit data deletion
    probe: synchronized-local-lifecycle
    expected: config preflight migration bootstrap health-gated up warm restart down and explicit reset separation pass within the reference envelope while ordinary down preserves all named volumes
    groundTruth: direct Compose events health transitions one-shot exit records volume identities startup measurements and before-after persistence reads
  - id: AC-SP98-4
    requirement: Portal uses real Omniscience and Barbarossa owner contracts with truthful local availability semantics
    probe: synchronized-local-real-owner-experience
    expected: exact owner revisions freshness provenance and development-single-host state render while selected-owner mock URLs fixtures and services are absent and missing HA axes remain not_qualified
    groundTruth: owner API captures Portal API browser accessibility tree rendered configuration and process/network inventory
  - id: AC-SP98-5
    requirement: Tenant PW0 and no-effect boundaries hold across every local owner and Portal sink
    probe: synchronized-local-tenant-pw0-no-effect
    expected: two-scope positive and negative reads plus seeded PII reversible token and active content tests show no cross-scope disclosure sink residue echo Omnius route owner write action effect or favorable fallback
    groundTruth: independent identities seeded corpus owner stores broker captures UI cache logs traces metrics audit export and before-after owner-state inventories
  - id: AC-SP98-6
    requirement: Owner severance restart and recovery remain independently diagnosable
    probe: synchronized-local-severance-recovery
    expected: Omniscience and Barbarossa stop restart and contract-skew scenarios affect only their source-bound panels preserve unrelated truth and recover to fresh projections without duplicate authoritative transitions
    groundTruth: controlled Compose service lifecycle owner/store histories Portal timeline and fresh post-recovery reads
  - id: AC-SP98-7
    requirement: Local execution remains within a measured portable host envelope
    probe: synchronized-local-resource-envelope
    expected: amd64 and arm64 reference runs publish image sizes per-service limits peak and steady CPU memory disk container counts and cold/warm startup timing within the declared 4-vCPU 8-GB 25-GB image-mode envelope with sequential source builds or return typed host_capacity_insufficient
    groundTruth: named host and Docker versions independent resource capture image inventory and bounded startup timeline
  - id: AC-SP98-8
    requirement: The local receipt is reproducible reversible and cannot be promoted into HA or deployment evidence
    probe: synchronized-local-receipt-integrity
    expected: exact redacted evidence manifest and rollback pass while source dirtiness forces non-reproducible development status and availability_class ha_qualified activation_authority remain fixed to development-single-host false none
    groundTruth: content-addressed receipt schema evidence hashes prior owner digests rollback capture and negative SP-89 SP-92 SP-94 claim validation
  - id: AC-SP98-9
    requirement: Local secret material and destructive reset remain explicit non-leaking operator actions
    probe: synchronized-local-secret-reset-safety
    expected: committed configuration contains no secret value the checked-in env example covers every required variable the high-entropy generator neither prints values nor overwrites an existing env file and reset without the exact confirmation gate leaves every named volume unchanged
    groundTruth: committed-value and required-variable scans generator entropy stdout stderr overwrite-negative captures reset command contract and before-after volume identities
rollback: { kind: disposable, probe: stop-local-profile-preserve-volumes-and-restore-exact-prior-owner-fragment-digests }
---

## Intent

Publish the cross-repository Compose application and independently exercise the complete
`management-readonly-local-v1` functional-smoke matrix. This task consumes owner artifacts; it cannot
repair a component, copy an owner migration/configuration, mint a sibling receipt or claim deployment
or HA qualification.

## Required inputs

- exact accepted ADR-0024 and local profile revision;
- immutable SP-95 `OmniscienceLocalRuntimeReceipt`;
- immutable SP-96 `BarbarossaLocalRuntimeReceipt`;
- immutable SP-97 `PortalLocalRuntimeReceipt`;
- a reference host identity with Docker/Compose versions and declared resources;
- two local tenant/workspace identities and deterministic safe plus negative PW0 fixture corpus; and
- exact prior local receipt/owner artifact digests and a non-destructive stop/rollback target.

Missing, mutable, incompatible or unverifiable input produces RED/decision-required evidence. It does
not authorize a mock substitution, sibling edit, secret request, public exposure, infrastructure
mutation, volume deletion or partial PASS.

## Required output

`SynchronizedPlatformLocalLaunchReceipt` contains the fields fixed by the profile plus a
content-addressed report for every acceptance probe. Owner receipts remain separately verifiable and
are referenced, never reissued.

## Authority boundary

This task authorizes local file changes in the listed `genai-enablement` paths and disposable Docker
resources on the developer host when implementation is later assigned. It does not authorize
production deployment, cloud/Kubernetes mutation, external secrets or data, destructive volume reset,
Omnius, managed effects, owner control, HA qualification, SP-89/SP-94 completion or a
production-readiness claim.
