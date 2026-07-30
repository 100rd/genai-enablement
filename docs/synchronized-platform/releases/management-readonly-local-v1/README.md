# Release: `management-readonly-local-v1` integrated local launch (task-sp-98)

The genai-enablement integrator artifact for the first synchronized-platform
profile's disposable local launch (ADR-0024). It assembles the three owner
fragments (SP-95 Omniscience, SP-96 Barbarossa, SP-97 Platform Portal) into one
Compose application and independently qualifies AC-SP98-1..9, emitting a
content-addressed `SynchronizedPlatformLocalLaunchReceipt`.

## Artifacts

| Path | What |
|------|------|
| `../../../../deploy/local/management-readonly-v1/` | the assembled Compose application + env template |
| `../../../../scripts/qualify_management_readonly_local.py` | the integrator qualifier → receipt |
| `../../../../scripts/generate_management_readonly_local_env.py` | high-entropy env generator (no leak / no overwrite) |
| `evidence/synchronized-platform-local-launch-receipt.*.json` | the content-addressed launch receipt |
| `evidence/live-capture.arm64.json` | the honest arm64 live-smoke capture folded into the live ACs |

## Acceptance summary (this run, arm64)

| AC | Probe | Class | Status |
|----|-------|-------|--------|
| AC-SP98-1 | synchronized-local-compose-lock | deterministic | **PASS** |
| AC-SP98-2 | synchronized-local-topology-containment | deterministic | **PASS** |
| AC-SP98-8 | synchronized-local-receipt-integrity | deterministic | **PASS** |
| AC-SP98-9 | synchronized-local-secret-reset-safety | deterministic | **PASS** |
| AC-SP98-7 | synchronized-local-resource-envelope | live | **PASS** (within 8 GB envelope; amd64 pending) |
| AC-SP98-3 | synchronized-local-lifecycle | live | partial (owner portal-backend /readyz 404 skew) |
| AC-SP98-4 | synchronized-local-real-owner-experience | live | partial (real owner reads live; browser blocked by the same skew) |
| AC-SP98-5 | synchronized-local-tenant-pw0-no-effect | live | partial (live boundary negatives; full UI corpus needs the frontend) |
| AC-SP98-6 | synchronized-local-severance-recovery | live | partial (severance observed at API level) |

`deterministic_status = GREEN`. `mode = source`, `reproducible = false`,
`qualification_status = development-only`, `availability_class =
development-single-host`, `ha_qualified = false`, `activation_authority = none`.

## Honest live findings

- **Capacity was sufficient**, not `host_capacity_insufficient`: the near-full
  stack (13/14 steady services incl. the torch Omniscience API) ran healthy at
  ~2.1 GiB steady on a shared 7.65 GiB-to-Docker arm64 host.
- **Real dual-owner reads are live**: Portal backend → Omniscience `/ready`
  (full dependency + PW0 privacy closure healthy, v0.2.0) and → Barbarossa
  `/v1/local/availability` (development-single-host, ha_qualified=false,
  not_qualified axes). No mock in the running model. Portal is not on any
  owner-private network (owner store unreachable — verified live).
- **Two owner-artifact defects surfaced, not repaired** (sibling repos are
  read-only to SP-98): (1) `portal-backend` `/readyz` → 404 on the prebuilt
  `platform-portal-backend:latest` image, blocking `portal-frontend`; (2)
  preserved owner store volumes initialized by earlier standalone runs skew the
  credentials until reset.

## Uncommitted prior-wave dependencies (flagged, not silently consumed)

- SP-96 Barbarossa and SP-97 Portal local runtime receipts are computed at
  runtime (Go / Python) with no committed JSON to content-address; the receipt
  pins their committed service contracts and flags `sp96/sp97_runtime_receipt_digest`
  as pending.
- SP-95 Omniscience's committed receipt is itself self-declared RED
  (`scoped_worktree_dirty`, `sp86_image_registry_digest_pending`); its honest
  status is surfaced, never upgraded.

## Cannot claim

No production deployment, no HA (SP-92/SP-94), no SP-89 qualification, no Omnius,
no managed effect, no activation authority. A local receipt grants none of these.
