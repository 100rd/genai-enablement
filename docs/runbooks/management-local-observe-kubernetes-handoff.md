# Kubernetes handoff: management-local-observe-v1

**Status:** the source delivery is tested and merged. Charts and cluster deployment belong to the deployment agent. Kubernetes behavior, placement and rollout acceptance still require evidence from that target; the current qualification is local and single-host.

## Merged source inputs

| Repository | Merge revision | Tested source revision |
|---|---|---|
| [100rd/Omniscience](https://github.com/100rd/Omniscience/pull/374) | `3831fb7f581ac747a679513dd221231eb083581d` | `639c52dac220b461d286b86a6fdeb36cf89300a4` |
| [100rd/Barbarossa](https://github.com/100rd/Barbarossa/pull/13) | `c7f78d3ac37b6d0b933fee91292bf9c5c7ff1233` | `1c6335656b348dbd9025aa82d0cb730b442604dd` |
| [100rd/platform-portal](https://github.com/100rd/platform-portal/pull/23) | `adcddeb2338991f0780d7abb40a050c224efb392` | `1389aae9112ba03696fb3bc99560e970887d3241` |
| [100rd/genai-enablement](https://github.com/100rd/genai-enablement/pull/60) | `4cbf5c0603869fdf24cb486ad76e32a608970d82` | `2f9d654445ba3aa10f21e938c860d8b9e765d2e1` |

All four merge trees equal the tested source trees. [Merge evidence](../synchronized-platform/releases/management-local-observe-v1/merge-readiness/README.md) records exact CI and local checks.

## Image/build inputs

Build immutable images from the revisions above and load them into the target cluster or publish them to its deployment registry. Pin the resulting artifacts in the chart. This experiment does not itself complete the separate OCI release qualification.

| Component | Source and build detail |
|---|---|
| Portal backend and migration job | `platform-portal/backend/Dockerfile`, context `backend/`. The same backend image runs `alembic upgrade head` in the migration Job and `uvicorn app.main:app --host 0.0.0.0 --port 8000` in the API deployment. |
| Portal frontend | `platform-portal/frontend/Dockerfile`, context `frontend/`, final stage `runner`. Supply `BACKEND_INTERNAL_URL` as a build argument: the Next.js rewrite destination is baked at build time. This is an **internal** backend Service origin such as `http://portal-backend:8000`; it is distinct from the public user-facing `FRONTEND_ORIGIN` runtime setting. |
| Barbarossa local Observe | `barbarossa/Dockerfile`, `--target barbarossa-observe`; source entry point `cmd/barbarossa-observe/main.go`. This dedicated binary has `serve`, `observe`, `migrate`, and `healthcheck` commands and contains the SP-104 SQL migration. Use this image for migration Job, API (`barbarossa-observe serve`), and observer (`barbarossa-observe observe`); there is no separate `barbarossa-api serve` binary in this target. |
| Omniscience local Observe | API/migration image: root `Dockerfile`, repository-root context, `INSTALL_LOCAL_EMBEDDINGS=true`; admin image: `apps/admin/Dockerfile` with `apps/admin/` context. Build configuration is recorded in `Omniscience/deploy/compose/management-readonly-local/compose.source.yaml` and layer `Omniscience/deploy/compose/management-local-observe-v1/compose.yaml`. The overlay names the source-built images `omniscience-local/omniscience-server:observe-source` and `omniscience-local/omniscience-admin:observe-source`; build configuration is inherited from the base source fragment. No published OCI image for this selected local Observe owner profile is available in the reviewed source, so build and load or publish these source artifacts at the exact reviewed commit for the cluster experiment. This is not a production image release. |

Portal images are not built from the root repository directory. Keep frontend and backend artifacts aligned to the same Portal revision. The frontend rewrite must remain same-origin to browsers; only the server-side Next.js proxy talks to the backend Service.

Set `OMNISCIENCE_MCP_SOURCE_COMMIT` to the exact Omniscience source revision used for the image,
as the local coordinator does. Preserve the served contract pin and source provenance when
building the cluster artifacts; replacing a tag does not establish that provenance.

## Required dependency and migration order

1. Build Omniscience from its source Compose build fragment and layer its `management-local-observe-v1/compose.yaml` overlay for the selected configuration. Provision stores and secrets, apply its schema migration and wait for `/ready` before the owner bootstrap in step 2. Bootstrap is deliberately restricted to `ENVIRONMENT=development`, PostgreSQL database `omniscience`, and the exact store hostnames below. It requires `HF_HUB_OFFLINE=1`. The owner expects service destinations `omniscience-api:8000`, `omniscience-postgres`, `omniscience-neo4j`, and `omniscience-qdrant`. The overlay sets `LOCAL_OBSERVE_ENABLED=true` and `GRAPH_BITEMPORAL=enabled`; the local source fragment uses offline local embeddings (`EMBEDDING_PROVIDER=local`, model `all-MiniLM-L6-v2`, CPU, offline flags). Keep discovery, reconcile, scheduler, and retention disabled for this selected local closure.
2. Run the owner seed with `python -m omniscience_server.local_observe`, supplying its existing broker secret only to that process. Its output lists workspaces; it is not itself proof of scoped reads. Follow the read-verification sequence in `genai-enablement/scripts/local_observe.py:bootstrap`: mint restricted per-workspace tokens, verify the expected own topology, reject foreign topology with 404, then hash the stable verified bindings into the mapping receipt. The fixed workspaces are alpha `a34f0802-8321-5c7c-8a6b-dea95391faf5` and beta `beac9cbb-b8e1-52da-9fe7-5c5e591825f5`. Tenant IDs are configured separately. Do not infer authorization from matching IDs or publish the tokens. The coordinator launcher itself targets local Compose/loopback, so the deployment agent must perform these ordered operations through the cluster's private paths rather than running `activate` against Kubernetes.
3. Provision dedicated Barbarossa Observe PostgreSQL 18 and its persistent volume. Run the one-shot `barbarossa-observe migrate` Job to successful completion before `barbarossa-observe serve` or `barbarossa-observe observe` starts. The local profile uses a separate `barbarossa_observe` database/store; do not point it at the unrelated SP-96 runtime database. Preserve its volume during ordinary rollout and rollback.
4. Provision Portal PostgreSQL and identity/issuer configuration. Run the Portal migration Job (`alembic upgrade head`, then create the two fixed profile tenants) before starting the backend. After validating the owner receipt, run the Portal's existing `python -m app.local_observe.bootstrap mappings` command against the migration database role with only the receipt JSON on stdin. The bootstrap is idempotent for the same mapping and receipt and rejects conflicting rows. Do not grant the viewer DB role mapping-write authority.
5. Start Portal backend, frontend, and Barbarossa observer after their migrations and required owner services are ready. Do not overlap separate writers/observer instances during cutover; this selected profile is single-observer and its source contract is explicitly `development-single-host`.

The coordinator bootstrap also prepares a bounded, content-addressed Omniscience context file
from the verified alpha runbook read. Follow that preparation when setting
`BARBAROSSA_OBSERVE_CONTEXT_FILE`; the API validates/imports it at startup. It is a prepared
snapshot with its own observation time, not a fresh knowledge query on every analysis.
Omitting the environment variable does not erase already persisted context; an explicit `[]`
clears the active context. Preserve case evidence and accepted history across this operation.

## DNS, network, and listener constraints

Preserve the following service destinations, or change the owning source contracts together with an explicit review and new qualification:

- Portal backend → Omniscience: `http://omniscience-api:8000`.
- Portal backend → Barbarossa read API: `http://barbarossa-api:8080`.
- Barbarossa observer → Omniscience readiness: `http://omniscience-api:8000/ready`.
- Barbarossa observer → Barbarossa readiness: `http://barbarossa-api:8080/readyz`.
- Barbarossa observer → Portal readiness: `http://portal-backend:8000/readyz`.
- Frontend server-side rewrite → the backend Service on port `8000` (baked into the frontend image via internal `BACKEND_INTERNAL_URL`, independent of public `FRONTEND_ORIGIN`).

Use NetworkPolicies to preserve the local trust boundaries: Portal backend may call owner read APIs, but must not reach owner stores, migrations, or runner mutation routes. The observer needs documented readiness and owner read paths, its Portal probe-token exchange, and **read/write access to its own observation database** to persist health samples/cases. Keep app runtime DB credentials separate from migration/admin credentials; grant schema migration permissions only to the one-shot migration Job. Do not expose Postgres, Neo4j, Qdrant, NATS, or the Barbarossa runner protocol through Ingress or public Services.

The Barbarossa Observe process listens on `:8080` for read API and `:8082` for the internal runner protocol (both bind all Pod interfaces). Allow `8080` only for the intended Portal, observer and probe paths. **Do not create a Kubernetes Service or Ingress for `8082`.** Restrict Pod-network access to that listener and use a loopback-only host port-forward for the host runner, e.g. bind host `127.0.0.1:18082` to the API Pod's `8082`. The runner client is fixed to `http://127.0.0.1:18082`; it rejects non-loopback/non-numeric IPv4 origins. The existing local Observe Compose stack already binds that host port. Coordinate a cutover (stop the local runner and observer before its API, retaining all volumes) or use another trusted host; do not silently leave the runner connected to the old queue. Never bind `18082` to `0.0.0.0`.

The observer calls the Portal's internal credential exchange at `/api/internal/local-observe/probe-tokens` using its separate probe secret. The endpoint returns the configured synthetic alpha/beta read identities and is outside the frontend rewrite. Keep it internal, secret-protected, and unavailable outside the selected runtime profile.

## Identity and secret wiring

Set `PORTAL_RUNTIME_PROFILE=management-local-observe-v1` on Portal backend and frontend. Configure the public user-facing URL as `FRONTEND_ORIGIN` and register the exact callback `{FRONTEND_ORIGIN}/api/v1/auth/callback` with the OIDC provider. Separately, build the frontend's `BACKEND_INTERNAL_URL` to the in-cluster backend Service; it is not the public origin. Configure `KEYCLOAK_ISSUER_URL` to the issuer URL actually advertised to the browser and backend; the local `keycloak.localtest.me` issuer and localhost origins are development-only. Preserve same-origin session/API behavior and the backend's same-origin post-login redirect validation.

Mount the Ed25519 private key (`PORTAL_BARBAROSSA_READ_PRIVATE_KEY_FILE`) only in Portal backend. Share the separate probe secret between Portal (`PORTAL_LOCAL_OBSERVE_PROBE_TOKEN_FILE`) and observer (`BARBAROSSA_PROBE_TOKEN_FILE`). Mount the matching public key only into Barbarossa Observe (`BARBAROSSA_PORTAL_READ_PUBLIC_KEY_FILE`). Do not duplicate private signing material into the frontend, observer, runner, or Omniscience. JWT claims are fixed in source: issuer `platform-portal-local`, audience `barbarossa-read`, effective tenant and user, `role=read`, `scope=observe:read`, and 60-second expiration. In the selected local Observer/Barbarossa profile, `BARBAROSSA_PORTAL_TENANT_IDS` is **alpha-only**; beta's own Omniscience graph access is allowed, while beta's Barbarossa Control requests must remain denied (403). Preserve this deliberate scope asymmetry. Configure the owner-published pin and credentials as secrets/config according to their sensitivity:

- `KV_OMNISCIENCE_BASE_URL=http://omniscience-api:8000`
- `KV_OMNISCIENCE_ALLOWED_HOSTS=omniscience-api` (exact hostname, no wildcard)
- `KV_OMNISCIENCE_PINNED_CONTRACT_VERSION` equal to the live MCP manifest version; the source local default `1.0.0` must be checked against the owner before rollout.
- `KV_OMNISCIENCE_BROKER_ADMIN_CREDENTIAL` equal to the owner bootstrap credential (`OMNISCIENCE_LOCAL_OBSERVE_BROKER_TOKEN`). Its `local-observe:mint-read` authority only mints the restricted read profile for the two designated workspaces; it is not a broad owner admin token. Keep it backend/bootstrap-only.
- `OMNISCIENCE_WORKSPACE_TOKEN_TTL_CEILING_SECONDS=900` (verify the selected config preserves the existing ceiling).
- `PORTAL_BARBAROSSA_OBSERVE_BASE_URL=http://barbarossa-api:8080` and `PORTAL_BARBAROSSA_READ_PRIVATE_KEY_FILE`.
- `BARBAROSSA_OBSERVE_DATABASE_URL` with runtime read/write access to the observer's own observation tables; reserve migration/admin permissions for the migration Job. `BARBAROSSA_PROBE_TOKEN_FILE`, `BARBAROSSA_RUNNER_TOKEN_FILE`, `BARBAROSSA_OBSERVE_CONTEXT_FILE`, and alpha-only `BARBAROSSA_PORTAL_TENANT_IDS` belong only in their owning Barbarossa roles.
- Portal database application and migration URLs as separate credentials; the mapping bootstrap must use the migration/owner database role.

No credential values belong in this document, chart defaults, logs, image layers, or public environment/config output.

`BARBAROSSA_PORTAL_TENANT_IDS` is a nonempty JSON array of allowed tenant IDs. The runner bearer
is shared only between the owner API and the authorized host runner; the probe bearer is shared
only between Portal backend and observer. Neither is a public read token.

## Probes and readiness semantics

- Portal backend: `/healthz` is the process health endpoint; `/readyz` returns `{"status":"ready"}` without checking the DB or contacting owners. This is an intentional “can serve traffic” contract. Do not convert Omniscience/Barbarossa degradation into a backend liveness failure or claim `/readyz` proves datastore/owner readiness. Ensure DB migrations complete before rollout; monitor DB/owner dependencies separately.
- Barbarossa Observe: the container `healthcheck` command probes `http://127.0.0.1:8080/readyz`. Use the image's `healthcheck` command (distroless image has no shell/curl/wget); readiness and liveness must not probe internal `8082` from a Service. Confirm probe timing with the selected chart and local owner readiness contract.
- Omniscience: the local profile's readiness path is `/ready`; it represents selected dependency/migration/policy closure. Confirm the deployed owner chart's readiness contract rather than reusing Portal `/readyz` semantics.
- Migration Jobs are completion gates, not long-running readiness targets. API/observer/runner start only after their required migration job succeeds.

The Barbarossa local Observe model records `FailureDomain: shared-host` and `SharedFateWithSubject: true`. That provenance is not accurate for arbitrary multi-node Kubernetes placement. Either constrain the selected profile to a genuinely single-node-equivalent failure domain and verify the recorded provenance, or revise the contract and requalify before deployment. Do not claim HA or infer a failure-domain boundary from a namespace or node label.

## Post-deploy acceptance gate

Do not call the rollout complete until the deployment owner records evidence for each item against the exact image digests and chart/config revision:

1. All migrations are successful and ordered; the two profile tenants and both receipt-verified Omniscience workspace mappings exist exactly once. A conflicting receipt/mapping fails closed.
2. Both real Keycloak users can start at `/`, land at `/observe`, and see only their own owner-backed graph/workspace provenance. A foreign workspace is refused; missing, expired, invalid, or incorrectly signed Portal tokens fail closed. Alpha can read Barbarossa Control; beta is denied that surface with 403 by the alpha-only Barbarossa tenant allowlist.
3. The live MCP manifest matches the configured pin; severance, expiry, incompatible contract, empty healthy response, degraded and stale responses remain visibly distinct.
4. `/control` independently reads cases/status, queue, and history; pagination cursors stay independent; selecting work displays that exact accepted result; manual refresh updates the work view. Recommendations remain non-authoritative and no execution/mutation routes are exposed.
5. Observe cards appear without waiting for a graph read, carry component timestamps, refresh, clear stale healthy state on failure, and restore it after recovery.
6. Exercise the full controlled lifecycle: induce a bounded test fault, verify the observer persists the expected case and readiness evidence without secrets/raw response bodies, allow the analysis-only Codex runner to consume eligible work, and verify Control shows the exact accepted result as non-authoritative. Then restore the dependency and verify recovery appears in Observe/Control, history and results persist across Pod restarts, queue leases/attempt limits and rate limits remain enforced, and stale evidence never stays green. Do not use this workflow to execute remediation.
7. The runner reaches only the loopback `127.0.0.1:18082` port-forward, accepts its credential only on the internal API, and cannot be reached through a Service/Ingress. Coordinate the existing local Docker port owner before cutover; run only one observer and one host runner.
8. Probe `/healthz`, `/readyz`, Barbarossa `/readyz`, and Omniscience `/ready` according to the contracts above. Owner outages must not be misreported as Portal process failure or as healthy owner data.
9. Record explicitly that this remains a local, single-observer, single-host-equivalent profile unless separate HA qualification exists. Kubernetes scheduling or replica counts alone do not upgrade its availability claim.

**Known boundary:** the source profile and acceptance spec provide a local qualification recipe (`frontend`: `npx playwright test -c playwright.local-observe.config.ts`). That test plus local backend tests are not Kubernetes qualification. Deployment is assigned to the separate deployment agent; this handoff records source constraints and does not claim Kubernetes qualification.

## Source references checked

- Portal: `backend/Dockerfile`, `frontend/Dockerfile`, `infra/compose/management-local-observe-v1/compose.yaml`, `backend/app/local_observe/{delegation.py,router.py,probes.py,bootstrap.py}`, `backend/app/kv/config.py`, `backend/app/main.py`, `scripts/local_observe_realm.py`, `docs/specs/task-sp-105-local-observe-portal.md`, and `infra/compose/management-local-observe-v1/README.md`.
- Barbarossa local Observe branch/source: `Dockerfile` target `barbarossa-observe`, `cmd/barbarossa-observe/main.go`, `internal/localobserve/{observer.go,model.go}`, `internal/codexrunner/client.go`, `deploy/compose/management-local-observe-v1/compose.yaml`, `docs/runbooks/management-local-codex-runner.md`, and `docs/specs/task-sp-104-local-observe-runtime.md`.
- Omniscience local Observe owner: `deploy/compose/management-readonly-local/compose.source.yaml`, `deploy/compose/management-readonly-local/compose.yaml`, and overlay `deploy/compose/management-local-observe-v1/{compose.yaml,README.md}`. The overlay is the source-cluster-experiment reference; an OCI owner release image is not published for this selected profile in the reviewed source.

Host Codex authorization remains on the trusted host. Build/configure the host runner using the [Barbarossa runner runbook](https://github.com/100rd/Barbarossa/blob/c7f78d3ac37b6d0b933fee91292bf9c5c7ff1233/docs/runbooks/management-local-codex-runner.md), including its installed-CLI support check. Do not place ChatGPT credentials in Pods. The runner requires its own queue bearer, isolated analysis-only CLI configuration and a working loopback port-forward; a cluster API deployment alone cannot perform AI analysis.
