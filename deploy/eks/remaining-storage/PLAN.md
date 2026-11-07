# Retained storage for Barbarossa and Omniscience

Read-only preflight for EKS `nonprod-euc1`, account `120736097561`, namespace `splatform`. The operating sequence requires fresh backups of the live stores. The November 6 backup and restore receipt provide an earlier recovery point.

## Live inventory

| Store | Workload and Helm release | Current storage and runtime | Sampled state |
|---|---|---|---|
| Barbarossa PostgreSQL | `barbarossa-postgres`, release `barbarossa` v1, app chart 0.1.0 | `emptyDir` at `/bitnami/postgresql`, PostgreSQL 18.6, UID/GID/fsGroup 1001 | 12 tables, 10,065,599 bytes. 5,900 observations at sampling, 18 case observations, 10 job observations, 5 jobs, 4 cases, 4 components, one control row and one migration row |
| Omniscience PostgreSQL | `omniscience-postgres`, release `omniscience` v1, app chart 0.2.0 | `emptyDir` at `/bitnami/postgresql`, PostgreSQL 18.6, UID/GID/fsGroup 1001 | 12 tables, 8,779,455 bytes. 6 API tokens, 5 documents, 5 chunks, 2 sources, 3 workspaces and one Alembic row |
| Omniscience Neo4j | `omniscience-neo4j`, release `omniscience` v1, Neo4j chart 2026.10.1 | Community 2026.10.1, UID/GID/fsGroup 7474, `emptyDir` named `data` with separate subpaths for `/data`, backups, imports, licenses, logs and metrics | `neo4j` and `system` online. 0 nodes, 0 relationships, 0 constraints, two online default lookup indexes, one `neo4j` user with no required password change or custom home |

Both PostgreSQL databases use UTF-8 with libc `en_US.UTF-8`. Their two non-built-in roles are `postgres` and the respective owner `barbarossa_observe` or `omniscience`. The app owners have LOGIN and CREATEDB. They lack superuser, CREATEROLE and BYPASSRLS. The application and migration URLs for each release both use that release's owner. The mounted PostgreSQL admin Secrets are `barbarossa-postgres` and `omniscience-postgres`.

The Omniscience release also owns NATS 2.15.2 and Qdrant 1.20.0, whose StatefulSets already use claim templates. Require their rendered specs, claims, Services and ConfigMaps to match the installed release. Keep the Portal release and claims outside these upgrades.

## Stop writers and capture current data

1. Migrate Barbarossa in one window and Omniscience in a second. Before each window, verify EBS CSI readiness and `splatform-gp3` encryption, `WaitForFirstConsumer` and `Retain`. Prepare a distinct 8 GiB RWO PVC per selected store. Use create-only operations and check for names already in use. Match the original workload scheduling constraints in staging so its PV binds in a compatible AZ.
2. Record current deployment replica counts, source Pod and StatefulSet UIDs, Service EndpointSlice targets, Helm revision, and database image IDs. Pause scheduled jobs, CI releases, out-of-band writers and migration/bootstrap jobs for the store. No namespace CronJobs were present at preflight. The existing migration Jobs had already succeeded.
3. For Barbarossa, stop `barbarossa-observer` first to stop background observations, then stop `barbarossa-api`. For Omniscience, stop `omniscience-api`, which connects to both PostgreSQL and Neo4j and processes work from other stores. Ensure no independent ingestion or NATS consumers can write to the selected databases. Keep upstream work queued during the window. Verify old writer Pods terminated and no relevant client transactions remain. Leave source database Pods running on their current `emptyDir` through staging validation.
4. For each PostgreSQL source, capture `pg_dumpall` directly from its original Pod to a private file using the same PostgreSQL 18.6 client. Set `PGPASSWORD` inside the container from `POSTGRES_POSTGRES_PASSWORD_FILE` and connect as `postgres`. Keep stdout in a mode-0600 dump file and redact failure logs. Capture its SHA-256, source Pod UID, timestamp, database encoding and locale, role flags and ownership, exact schema/table inventory and per-table counts, and migration revision. Capture the source evidence after quiescing, then compare it immediately before rolling the source Pod. The sampled counts above are inventory and may change.
5. Take a corresponding Neo4j inventory after quiescing Omniscience. Include all databases, users, nodes and relationships, full index and constraint definitions, and the query results needed to compare authorization. Recheck immediately before the upgrade. See the Neo4j decision below.

## PostgreSQL restore and Helm handoff

Use the proven [Portal recovery sequence](../portal-recovery/README.md) with store-specific identities and a fresh backup. The Portal script embeds Portal-specific guards and backup assertions.

- Claims are `barbarossa-postgres-data-retained` and `omniscience-postgres-data-retained`. Use separate staging Pod and Service names and labels. Clone the source pod template, mount its new claim in place of the data `emptyDir`, and pin `registry-1.docker.io/bitnami/postgresql@sha256:b418fd5f001c272aad93ac1febf783f543ee45d8e359d58bd5afc3d2a9b62290`. Keep source auth mounts, owner/database bootstrap, and pod security context. Verify the staging EndpointSlice points exclusively to the intended ready Pod UID.
- Confirm each fresh target has only its expected owner and admin roles, the matching empty owner database, and the matching encoding and locale. Filter exactly four checked top-level bootstrap lines from the validated dump before piping into `psql -X -q -v ON_ERROR_STOP=1 -U postgres -d postgres`. Omit the duplicate CREATE statements for the owner and postgres, the ALTER ROLE for postgres, and the CREATE DATABASE for the initialized app database. Keep owner role options and verifier, database ownership, data, ACLs, sequences and other DDL. Keep the SQL and its diagnostic output private. Compare source and target schema, exact counts, migration revision, ownership and role flags before recording a private receipt tied to dump hash, source identity and target claim/PV identity.
- Test runtime and migration Secret keys from an isolated in-namespace probe, replacing the host in memory with the staging Service. Barbarossa uses `barbarossa-observe-secret` keys `RUNTIME_DATABASE_URL` and `MIGRATION_DATABASE_URL` with `postgres://`. Omniscience uses `omniscience-api-secret` keys `DATABASE_URL` and `MIGRATION_DATABASE_URL` with `postgresql+asyncpg://`. Use the corresponding driver or normalize the scheme for a PostgreSQL client. Check current user/database and a read allowed to the app role. The generic Omniscience store policy can permit an Omniscience-labeled probe. Barbarossa's store policy selects the original instance, so give the distinct staging Pod an explicit narrow ingress policy for its probe. Use disposable probe labels that avoid app Service selectors and verify DNS/TCP allowances.
- Apply only the following Helm overrides to each existing release after staging has stopped and no Pod references the target claim. Set `postgresql.primary.persistence.enabled=true`, `postgresql.primary.persistence.existingClaim` to that store's claim and `postgresql.image.digest` to the image digest above. Both releases use PostgreSQL dependency 18.12.18. The existing-claim branch puts the claim in the pod template and does not add `volumeClaimTemplates`. Original StatefulSet name, selectors, governing Service and client Services stay in place.
- Reconstruct the installed parent chart from private release metadata, re-fetch exact dependency versions, and reuse installed values in memory. Barbarossa depends only on PostgreSQL 18.12.18. Omniscience also needs NATS 2.15.2, Neo4j 2026.10.1 and Qdrant 1.20.0. Record artifact hashes and validate the entire server dry-run manifest against the installed revision, allowing only intended store pod image and data-volume changes. Check generated Secret data against live Secret data in memory. Verify no storage change to NATS or Qdrant. Barbarossa has no installed Helm hooks. Omniscience has Qdrant test hooks and `omniscience-api-bootstrap` on post-install/post-upgrade. Use `--no-hooks` for storage-only upgrades. Keep previously completed migrations in place and compare the live app migration revision before resuming writers.
- Roll with `--wait --timeout 10m` without automatic rollback. Verify the original Service now targets the ready replacement Pod, expected claim and digest, and persistent state through both original Secret URLs. If a replacement Pod schedules onto another node, wait for the EBS attachment to move within the bound AZ. After successful database verification, restore original app replicas and validate readiness and a store-backed read. For Barbarossa, resume the API first and the observer second.

## Neo4j decision and handoff

The exact Neo4j 2026.10.1 dependency rendered successfully with these leaf settings. The Omniscience parent chart adds the outer `neo4j` key.

```yaml
neo4j:
  image:
    customImage: docker.io/library/neo4j@sha256:7dbd307cc8f35d6a061cf71659d3d8f783c3db9e8c2f5bb9d54f77921931952a
  volumes:
    data:
      mode: volume
      volume:
        persistentVolumeClaim:
          claimName: omniscience-neo4j-data-retained
```

This renders the existing `data` pod volume as the external PVC without claim templates. Preserve the chart's mounted subpaths, config, UID/GID and existing `omniscience-neo4j-auth` Secret. Stage with labels distinct from both `app=omniscience-neo4j` and the original Helm instance selector. Use a separate Service and a narrow staged Bolt ingress rule from the probe. Verify using the app's existing `omniscience-api-secret/NEO4J_PASSWORD` with its configured username and the staging Bolt host. Validate system authentication, index definitions and graph counts on the staged Pod, then verify the same through the original Bolt Service after handoff.

There is no supported online Neo4j backup command in this Community installation. The documented migration path that preserves both database stores uses offline `neo4j-admin database dump` of both `neo4j` and `system`, then `load` into the stopped staging target. The current StatefulSet replacement destroys its `emptyDir`, including if a Helm maintenance-mode change replaces the Pod. No in-place method to hold this original Kubernetes Pod offline long enough to obtain supported dumps was verified. Treat preserving the current internal Neo4j store, including database identities and system metadata, as a separate gate before replacing it. [Neo4j backup and restore planning](https://www.neo4j.com/docs/operations-manual/current/backup-restore/planning/)

If the operator accepts preserving the application-visible state of the empty graph and standard login, stage a fresh Neo4j store with the current Secret and configuration. Recheck that the quiesced original still has zero nodes and relationships, the two default lookup indexes, no constraints and only the default user. Compare the staged user, indexes and Secret-based application authentication to that evidence. A fresh store generates new internal database identities and system metadata. If any graph or custom authorization state appears, keep the original running and leave Neo4j out of the Helm change until a supported backup path is proven.

Omniscience PostgreSQL can migrate in its own release revision while Neo4j remains on its original volume. Carry the PostgreSQL overrides forward when applying any later Neo4j change. If both stores have separately validated staged claims and the Neo4j decision is accepted before the release window, they can cut over in one Omniscience upgrade with one writer pause.

## Management workspace enrollment

Live Omniscience has three workspaces and two filesystem sources. Portal has two tenant-workspace mappings, both marked non-production.

| Workspace | Workspace ID | Source | Portal mapping |
|---|---|---|---|
| Default Workspace | `00000000-0000-0000-0000-000000000001` | None | None |
| Local Observe alpha | `a34f0802-8321-5c7c-8a6b-dea95391faf5` | `local-observe-alpha`, `b6effa47-a802-5d47-8d09-48fe432d7721` | Observe Alpha, tenant ID equals workspace ID |
| Local Observe beta | `beac9cbb-b8e1-52da-9fe7-5c5e591825f5` | `local-observe-beta`, `f6a79cc9-db87-5504-be6b-1dcbab0340ef` | Observe Beta, tenant ID equals workspace ID |

Enroll the cluster management target in a dedicated `platform-state` workspace and source, with an explicit Portal mapping to a designated management tenant. Verify that the intended management principal can read it and that both Local Observe tenants are denied. Keep this enrollment separate from the storage cutover so backup inventories and post-cutover verification refer to the same data.

## Execution gates still open

The live checks sampled counts and verified chart capabilities. The installed-parent server dry runs, fresh post-quiescence dumps and restore checks, staged network probes, and Neo4j system-store decision remain execution gates. The exact current writer set must be rechecked against active workloads and release jobs immediately before the maintenance window.

## Failure handling

Keep the source Pods available until the staged checks pass. Keep dump hashes, restore receipts, and the Retain PVs after handoff. A Helm rollback to a pre-persistence revision points the workloads at newly created empty volumes. Repair the retained-volume release or restore the captured backup onto a separate claim while writers remain paused. Validate the final live stores and record the resulting release revision, PVC/PV identity, and application readiness.
