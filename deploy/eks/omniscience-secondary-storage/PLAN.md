# Retained storage for Omniscience NATS and Qdrant

Read-only inventory for account `120736097561`, EKS `nonprod-euc1`, namespace `splatform`, while the API was paused for the separate Neo4j cutover. Snapshot capture and restore remain unexecuted.

## Source inventory

| Store | StatefulSet UID | Pod UID | PVC and PV |
|---|---|---|---|
| `omniscience-nats` | `2e4356df-c974-431d-855b-0f1a43f1d53d` | `ae111a93-448b-453f-8953-93d9e9e523da` | `omniscience-nats-js-omniscience-nats-0` (`18b96c9a-a4c2-40ce-869e-d68758cac553`) → `pv-splatform-nats-noniac` (`7406b00b-6788-4065-bc92-d2d8496a0845`) |
| `omniscience-qdrant` | `a7aab595-2ad1-42cd-b87b-73e9fd483b4a` | `e9f94ffc-2064-41fc-96ed-8b426bc901c1` | `qdrant-storage-omniscience-qdrant-0` (`db4ff201-cc89-4406-a0ef-3a7d3215a090`) → `pv-splatform-qdrant-noniac` (`f09888d2-f417-465b-84b7-8d67fa416fb4`) |

Both claims request 10 GiB. Both PVs have Retain but use `hostPath` with `DirectoryOrCreate` and no node affinity. Their current data directories live on `ip-10-1-14-115.eu-central-1.compute.internal` under `/tmp/splatform-nats-noniac` and `/tmp/splatform-qdrant-noniac`. Rescheduling onto another node could silently create fresh directories. Leave both temporary Pod disruption annotations in place and record their previous values until backup and staged restore are verified. Before either final source Pod is removed, review adding temporary UID-guarded disruption protection to the original Node to keep both host paths available through handoff. Remove temporary annotations after the reviewed recovery window. The node annotation covers voluntary disruption. The private off-node snapshot is the recovery copy if the node disappears. [Karpenter disruption controls](https://karpenter.sh/docs/concepts/disruption/#node-level-controls)

### NATS JetStream

- NATS chart and server 2.15.2. Container digest `docker.io/library/nats@sha256:afae2fdbe2e326c65e1246cb83b9d05d319188734f3bd577ac8072daae78a10f`. Reloader digest `docker.io/natsio/nats-server-config-reloader@sha256:d758a82a9c20337e46c2f7356a413faa52cf4d6b02497c3ad81f72f1ba106464`.
- The server has one JetStream account, no routes or leaf nodes and no active client connections at sampling. Client Service is `omniscience-nats:4222`; governing Service is `omniscience-nats-headless`. Loopback port 8222 serves read-only monitoring. Data volume mounts at `/data` and consumed 84 KiB.
- Three file-backed, single-replica streams have zero messages, bytes and first/last sequences. Four durable consumers have zero pending, ack-pending and redelivery counts.

| Stream | Durable consumers |
|---|---|
| `INGEST_CHANGES` | `omniscience-ingestion-worker` |
| `INGEST_DLQ` | None |
| `OUTBOX` | `omniscience-outbox-entity-consumer`, `omniscience-outbox-edge-consumer`, `omniscience-outbox-merge-consumer` |

Zero messages does not imply zero persisted state. Preserve streams, consumer configuration and cursors.

### Qdrant

- Chart and server 1.20.0. Container digest `docker.io/qdrant/qdrant@sha256:9bfc89f9914fc14876a88c05270685921a55b8877b254a98bcc1cc2f0a424cd2`. The ownership init container uses the same image version. The storage mount is `/qdrant/storage` and consumed 85,284 KiB. Preserve the current fsGroup 3000 and ownership init behavior. Client Service is `omniscience-qdrant`; governing Service is `omniscience-qdrant-headless`.
- Distributed mode is enabled. The cluster has **one peer**, zero pending Raft operations, one collection, zero aliases and no shard transfers. Collection `omniscience__all-MiniLM-L6-v2__d384` is green. It has one local Active shard 0 containing all seven points, zero remote shards, replication factor one, write consistency factor one, on-disk payloads, two segments and five indexed vectors.
- The sampled canonical SHA-256 of seven ID-sorted scroll records including vectors and payloads is `0b33b2866404b1bd204cd49b0f52c0b9976efaff5b3ab05b744060e4c09804d4`. Recompute with the writers paused. Segment count and index progress are operational metrics. Collection configuration, payload indexes, aliases, point content and shard placement are the restore equivalence gates.

## First execution slice after review

Capture both native snapshots off the node before changing either StatefulSet. Recheck current Omniscience release and the four store identities after Neo4j handoff, then pause the Omniscience API and any separate NATS publishers, consumer workers, Qdrant writers and release hooks. Verify clients have drained, and collect stable inventories immediately before and after capture. Do not reuse today's sampled counts as a capture receipt.

Create a mode-0700 directory under ignored `.local-observe/frankfurt-activation/secondary-storage-backups/` for the capture, with mode-0600 files and SHA-256 manifests. Record source release and Pod/PVC/PV UIDs, UTC capture time, source node and image digests. Keep snapshot payloads, API keys and detailed API responses out of terminal output and source control.

### Capture and verify JetStream

Use NATS CLI 0.4.0, pinned to a verified upstream binary or archive. Bind a loopback-only kubectl port-forward to the exact source Pod's port 4222 using the verified EKS context. The running app uses an unauthenticated NATS Service URI. Confirm the expected account over the private tunnel and keep the server's config and policies as deployed. Capture configurations and cursor metadata privately with `nats stream info --json` and `nats consumer info --json`. Compare the inventories with the source monitoring endpoint `GET /jsz?accounts=true&streams=true&consumers=true&config=true`.

```sh
umask 077
nats --server "$SOURCE_NATS" --timeout 2m account backup --check --consumers --force --critical-warnings "$PRIVATE_BACKUP/nats"
nats --server "$STAGE_NATS" --timeout 2m account restore "$PRIVATE_BACKUP/nats"
```

The account backup must contain all three stream snapshots and four consumer records. For a per-stream restore rehearsal, `nats stream backup <stream> <directory> --check --consumers` and `nats stream restore <directory>` use the native JetStream snapshot and restore APIs. Restore only into an isolated, empty staging server with the same NATS version and file store settings. No stage routes, gateway, leaf connections, production endpoints or publishers may reach the target. Compare exact normalized stream and consumer configuration, message counts and sequence state, pending and delivered cursors, redelivery counters, durable names and health. The staged server can have a different server ID. Retain any backup warnings privately and stop on missing consumer state. [NATS CLI account backup flags](https://github.com/nats-io/natscli/blob/v0.4.0/cli/account_command.go) [NATS CLI stream backup flags](https://github.com/nats-io/natscli/blob/v0.4.0/cli/stream_command.go) [JetStream API reference](https://docs.nats.io/reference/jetstream/api/)

### Capture and verify Qdrant

Bind a separate loopback-only port-forward to the exact source Pod's HTTP port 6333. Obtain the existing API key from its Secret into the authenticated HTTP client's memory. Keep it out of command-line arguments and output. Use the following routes.

| Operation | Endpoint |
|---|---|
| Verify peer, shard placement and collections | `GET /cluster`, `GET /collections`, `GET /collections/{collection}`, `GET /collections/{collection}/cluster` |
| Capture aliases | `GET /aliases` |
| Capture count and canonical record digest | `POST /collections/{collection}/points/count` with `{"exact":true}`, then paginated `POST /collections/{collection}/points/scroll` with `with_payload:true` and `with_vector:true` |
| Create the local collection snapshot | `POST /collections/{collection}/snapshots?wait=true` |
| Download and checksum snapshot | `GET /collections/{collection}/snapshots/{snapshot_name}` |
| Restore the snapshot into the isolated target | Multipart `POST /collections/{collection}/snapshots/upload?priority=snapshot&wait=true` with the archive in field `snapshot` |
| Reapply aliases, if the captured set is nonempty | `POST /collections/aliases` using captured create-alias actions |

Distributed-mode collection snapshots contain only the shards on the node that took them. The one current peer holds the only shard and all seven points, so one collection snapshot covers the observed data. If peer or shard placement changes, stop and redesign the capture per node. Full-storage snapshots are unsupported for distributed mode. Collection snapshots include the collection's data and configuration, and aliases require a separate capture. [Qdrant snapshot documentation](https://qdrant.tech/documentation/snapshots/) [Create collection snapshot API](https://api.qdrant.tech/api-reference/snapshots/create-snapshot) [Upload collection snapshot API](https://api.qdrant.tech/master/api-reference/snapshots/recover-from-uploaded-snapshot) [Qdrant node recovery](https://qdrant.tech/documentation/scaling/node-failure-recovery/)

Start a fresh Qdrant 1.20.0 peer on the staged EBS claim with equivalent one-peer settings and ownership. Isolate its P2P port and bootstrap configuration so it cannot join the source cluster. The staged Raft state and peer ID are new. Pin a peer URI strategy that works after restart under the original StatefulSet name, and test the restart before accepting the stage. Compare green readiness, exact collection configuration and payload index definitions, alias set, count and canonical point digest, and one local Active shard with no transfers or pending operations. Perform a normal read through the staged HTTP API. No source writes beyond creation of its documented snapshot files are needed. Leave original host-path data intact.

## EBS handoff after both restore rehearsals pass

Use separate 10 GiB RWO PVCs on the encrypted Retain `splatform-gp3` class and independently prove EBS identity and AZ. Maintain a private stage shutdown receipt before reattaching each claim to its original service identity. Pin the live Helm revision and rebuild from the exact package set already used by the [Omniscience PostgreSQL workflow](../omniscience-storage/README.md). Keep the API at zero during cutover. Suppress Omniscience bootstrap and chart test hooks.

Both live StatefulSets have immutable `volumeClaimTemplates`. NATS chart 2.15.2 exposes StatefulSet merge/patch and file-store PVC settings. Qdrant chart 1.20.0 hardcodes the `qdrant-storage` claim template and its corresponding mount. A reviewed replacement render is required to reference externally staged claims while preserving both original Service names, selectors and governing Services. The preferred handoff is explicit UID-scoped replacement of the affected StatefulSet after its source is stopped, followed by the normal Helm upgrade with the exact replacement manifests. Keep the old PVCs, PVs and host paths as rollback evidence. Avoid blanket Helm force replacement and in-place rebinding of the old claim names. Before this operation, prove the full proposed manifests contain only intended store changes and temporary API replica changes, and leave PostgreSQL and Neo4j untouched.

After each replacement, prove the original Service points solely to the new Pod, the original hostPath claim remains untouched, the intended EBS volume is the sole data mount, and the captured logical inventories and authentication still match. Keep the API paused until both verify. Resume through a separately checked Helm revision. Snapshot capture, staged restore and the replacement dry run are independent gates. This inventory does not authorize a source deletion.
