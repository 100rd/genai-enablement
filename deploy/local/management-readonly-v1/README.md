# `management-readonly-local-v1` — assembled local launch (task-sp-98)

The ONE assembled Docker Compose application for the first synchronized-platform
profile, composed from the three owner-published local fragments (ADR-0024 D2).
This directory owns only the **composition**: it declares no owner service,
image, migration or health semantic itself — it `include`s the exact owner
fragments and adds the cross-component network reconciliation and the launch
receipt.

```
Omniscience (SP-95) ── read ──▶
                                Platform Portal (SP-97) ──▶ browser (127.0.0.1)
Barbarossa  (SP-96) ── read ──▶
genai-enablement (SP-98) → composition + SynchronizedPlatformLocalLaunchReceipt
Omnius → not_deployed (no service / image / route / mock)
```

| File | Purpose |
|------|---------|
| `compose.yaml` | Assembled, include-only, image-mode/canonical model. Renders the full 14-service steady inventory + 3 one-shot migrations, every key owner-prefixed, no mock/omnius/collision. Reproducible-eligible (needs published owner OCI digests). |
| `compose.source.yaml` | Source overlay: makes the stack runnable from the owners' locally-built images (reuse, no rebuild). Forces `reproducible=false`. |
| `.env.example` | Every variable the three fragments read (committed; no real secret). |
| `.env` | Disposable, generated, git-ignored (never committed). |

## Prerequisites

- Docker Compose `2.24.4+` (uses the `include` mechanism).
- The three owner repositories checked out as siblings of `genai-enablement/`
  (`../Omniscience`, `../barbarossa`, `../platform-portal`) — the `include`
  paths are relative to those.
- Prebuilt owner images present locally (no rebuild needed): reuse
  `omniscience-local/omniscience-server:source`, `barbarossa-{api,worker}:mrl-v1`,
  `platform-portal-{backend,frontend}:latest`. A full source build (`--build`)
  recompiles the heavy Omniscience image — avoid unless you mean it.

## Generate the environment

```bash
python scripts/generate_management_readonly_local_env.py   # writes .env (0600), no secret printed
```

The generator fills the SECRET block with fresh high-entropy values and copies
every config-coupled line verbatim. It NEVER overwrites an existing `.env`
(a running store keeps its first-init password) — see **Reset** below.

> **Preserved-volume note.** Owner named volumes (`barbarossa-postgres-data`,
> `omniscience-pgdata`, `portal-mrl-pgdata`, …) are global and survive `down`.
> PostgreSQL only applies a password on first init, so a freshly-generated
> `.env` will not authenticate against a volume initialized by an earlier
> standalone owner run. For a clean run either reset those volumes (below) or
> use the owner-default credentials that match the existing volumes.

## Launch (one health-gated project)

```bash
docker compose \
  -f deploy/local/management-readonly-v1/compose.yaml \
  -f deploy/local/management-readonly-v1/compose.source.yaml \
  --env-file deploy/local/management-readonly-v1/.env \
  up -d --wait --wait-timeout 600
```

Browser surfaces (loopback only): Portal `http://127.0.0.1:3000`, Keycloak
`http://127.0.0.1:8081`, Omniscience admin `http://127.0.0.1:3001`.

## Qualify → receipt

```bash
# deterministic ACs (no running stack needed):
python scripts/qualify_management_readonly_local.py --report

# fold a live capture from a running stack and write content-addressed evidence:
python scripts/qualify_management_readonly_local.py --probe-live > /tmp/live.json   # observe only
python scripts/qualify_management_readonly_local.py --live-capture /tmp/live.json --write
```

## Persistence, shutdown, reset

- **Normal stop** preserves every named volume:
  `docker compose -p management-readonly-local-v1 down`
- **Reset** is the separate, explicit, destructive command (deletes data):
  `docker compose -p management-readonly-local-v1 down -v`
  Regenerating `.env` after a reset needs the confirmation token:
  `python scripts/generate_management_readonly_local_env.py --force --i-am-resetting-local-secrets`

## Boundaries (ADR-0024)

`availability_class=development-single-host`, `ha_qualified=false`,
`activation_authority=none`, `qualification_class=functional-smoke-only`.
No Omnius, no mock, no owner-write credential, no HA/SP-89/SP-92/SP-94 claim,
no production activation. The Portal backend joins only the two owner-read
edges (`omniscience-readnet`, `barbarossa-edge`) — never an owner-private
store/broker network.

## Known owner-artifact caveats (surfaced, not repaired — sibling repos are read-only)

- **portal-backend `/readyz` → 404** on the prebuilt `platform-portal-backend:latest`
  image (fragment healthcheck ↔ image skew); it cascades to `portal-frontend`
  not reaching healthy. The backend process still serves and performs the real
  owner reads. Fix belongs to the Portal owner (SP-97).
- **Preserved-volume credential skew**: an owner store volume initialized by an
  earlier standalone run with different credentials fails migration auth until
  reset. See the preserved-volume note above.
