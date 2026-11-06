# `management-readonly-local-v1` — assembled local launch (task-sp-98)

This directory assembles the first synchronized-platform profile from three
owner-published local fragments (ADR-0024 D2). It uses Compose `include` to
combine the owners' services, images, migrations, and health checks and
reconciles the shared read networks.

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
| `compose.portal-read.yaml` | Authenticated source assembly for the same legacy project. Includes the owner source and Portal read-auth fragments. |
| `.env.example` | Every variable the three fragments read (committed; no real secret). |
| `.env` | Disposable, generated, git-ignored (never committed). |

## Prerequisites

- Docker Compose `2.24.4+` (uses the `include` mechanism).
- The three owner repositories checked out as siblings of `genai-enablement/`
  (`../Omniscience`, `../barbarossa`, `../platform-portal`) — the `include`
  paths are relative to those.
- Prebuilt Omniscience source images available locally
  (`omniscience-local/omniscience-{server,admin}:source`). The targeted build
  below builds only the Barbarossa and Portal images.

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

## Launch with authenticated Barbarossa reads

Use the authenticated source assembly with owner revisions that provide the
Barbarossa verifier and the Portal session-bound signer. The canonical model
and prior evidence remain available for historical qualification and replay.
The protected Barbarossa routes require a signed read identity.

Generate a fresh Ed25519 pair once in an isolated, ignored directory. Pick the
Portal tenant UUID to bind to this Barbarossa owner. The example uses the
legacy local realm's seeded tenant.

```bash
legacy_dir="$PWD/deploy/local/management-readonly-v1"
legacy_auth_dir="$legacy_dir/.legacy-auth"
(umask 077
 mkdir "$legacy_auth_dir" &&
 openssl genpkey -algorithm ED25519 -out "$legacy_auth_dir/portal-private.pem" &&
 openssl pkey -in "$legacy_auth_dir/portal-private.pem" -pubout -out "$legacy_auth_dir/portal-public.pem" &&
 chmod 0644 "$legacy_auth_dir/portal-public.pem")

export BARBAROSSA_LEGACY_PORTAL_TENANT_ID=00000000-0000-0000-0000-000000000001
export PORTAL_LEGACY_READ_TENANT_ID="$BARBAROSSA_LEGACY_PORTAL_TENANT_ID"
export BARBAROSSA_LEGACY_PORTAL_PUBLIC_KEY_FILE="$legacy_auth_dir/portal-public.pem"
export PORTAL_LEGACY_READ_PRIVATE_KEY_FILE="$legacy_auth_dir/portal-private.pem"
```

Set `SP98_OMNISCIENCE_FRAGMENT_DIR`, `SP98_BARBAROSSA_FRAGMENT_DIR`, and
`SP98_PORTAL_FRAGMENT_DIR` to the absolute directories containing the owner
Compose fragments when using separate worktrees. The defaults select the
standard sibling checkouts. Build the changed owner images once if needed, then
start the health-gated project with the existing environment and volumes.

```bash
docker compose \
  -f "$legacy_dir/compose.portal-read.yaml" --env-file "$legacy_dir/.env" \
  build barbarossa-api barbarossa-worker portal-backend portal-migrate portal-frontend
docker compose \
  -f "$legacy_dir/compose.portal-read.yaml" --env-file "$legacy_dir/.env" \
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

The live capture runs a fixed local availability probe inside the Portal
backend using its mounted signer. Expect 401 for a request without identity,
200 with the legacy availability shape for the bound tenant, 403 for a
foreign signed tenant, and 409 for a conflicting legacy scope assertion.
The capture includes status codes and the shape check. Live acceptance
criteria still require their own observations.

The standalone Barbarossa owner qualifier has a separate credential input,
`BARBAROSSA_LEGACY_PORTAL_TOKEN_FILE`. The verifier accepts JWTs for at most
60 seconds. Supply a mode-0600 token file and refresh it atomically throughout
the owner qualifier's builds and live checks, using the matching signing key
and tenant. An expired token fails the protected read checks. The integrated
probe above signs during the probe and needs no host token file.

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
