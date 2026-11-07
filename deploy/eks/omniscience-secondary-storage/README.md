# Native snapshot capture for Omniscience secondary stores

This slice captures JetStream and Qdrant snapshots from the reviewed node-local source stores. It neither restores snapshots nor changes Kubernetes workloads, storage bindings, or the Omniscience API replica count. Qdrant creates a documented collection snapshot file on the source Pod before the script downloads it. Read the [migration plan](PLAN.md) for topology and later handoff.

## Read-only preflight

Run from the GenAI worktree root. The script uses the verified EKS context helper and the reviewed Omniscience release 5 and source store identities.

```sh
workflow=deploy/eks/omniscience-secondary-storage/capture.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s deploy/eks/omniscience-secondary-storage
python3 "$workflow" inventory
```

Inventory reads JetStream monitoring and Qdrant count/scroll data over a private loopback port-forward. It prints aggregate counts. Qdrant records and Secret values stay in process memory. If the Helm release, source Pod, StatefulSet, PVC, PV, image digest or node has changed, review the new source before modifying the identity pins.

## Capture in a maintenance window

Download the pinned NATS CLI 0.4.0 archive from upstream. For this ARM64 macOS host, use `nats-0.4.0-darwin-arm64.zip`. The script also accepts the upstream macOS AMD64 archive and checks the exact SHA-256 before executing the binary. It disables the local NATS context and inherits no `NATS_*` variables. [Pinned NATS CLI release](https://github.com/nats-io/natscli/releases/tag/v0.4.0)

```sh
umask 077
tool_dir="$(mktemp -d .local-observe/nats-cli-download.XXXXXXXX)"
archive="$tool_dir/nats-0.4.0-darwin-arm64.zip"
curl -fsSL https://github.com/nats-io/natscli/releases/download/v0.4.0/nats-0.4.0-darwin-arm64.zip -o "$archive"
```

Keep the temporary disruption protection on both store Pods. Pause the API, wait for all of its Pods to terminate, and pause other JetStream and Qdrant writers. Capture requires explicit acknowledgment of those writer controls, a live API replica count of zero, no matching API Pods or active Omniscience Jobs, and no NATS client connections immediately before and after capture. Qdrant must still be a single-peer distributed cluster with one active local shard holding all points and no transfers or pending Raft operations.

```sh
python3 "$workflow" capture --writers-paused --nats-archive "$archive"
```

Each attempt uses a new mode-0700 directory under `.local-observe/frankfurt-activation/secondary-storage-backups/`. The receipt starts as `incomplete`. The account backup requests all three stream snapshots with consumer configuration and state. Qdrant uses the collection snapshot API because this server runs in distributed mode. The receipt stores Qdrant aliases, collection and payload-index config, and a digest of all vectors and payloads separately from the archive.

The script changes the receipt to `complete` only when all seven private artifacts have expected names, positive lengths and recorded hashes, the Qdrant download matches the snapshot's advertised size and the required server-provided SHA-256, and the before-and-after source identities and logical inventories are equal. The incomplete receipt records the Qdrant source snapshot name, size and checksum before download. The script syncs every artifact and containing directory before atomically completing the receipt and syncing the attempt directory. Failures leave the original data and an incomplete attempt for inspection. After resolving the failure, retry into a new directory. Use only a complete receipt and separately rehearse restoration of all streams, durables, aliases, and points before moving either source.

## Isolated NATS EBS restore rehearsal

The rehearsal uses the pinned complete native capture `capture-nmq_o7wh`. It verifies the receipt SHA-256, all seven artifact hashes and lengths, and private file modes before each command. The live API can remain running. The rehearsal never addresses the production NATS Service or writes to its host path.

```sh
nats_rehearsal=deploy/eks/omniscience-secondary-storage/nats_stage.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s deploy/eks/omniscience-secondary-storage
python3 "$nats_rehearsal" preflight
python3 "$nats_rehearsal" stage
# Set attempt to the private rehearsal directory printed by stage.
python3 "$nats_rehearsal" restore --attempt "$attempt" --nats-archive "$archive"
python3 "$nats_rehearsal" verify --attempt "$attempt"
```

Stage creates a separate 10 GiB encrypted Retain EBS claim and a Pod with pinned NATS and reloader images. The source StatefulSet pod template must match the reviewed digest before any stage resources are created. The API-admitted Pod spec must match the derived stage spec before its UID is recorded. An immutable clone of the source NATS configuration changes only the client and monitoring listeners to loopback. No Service is created. The unique Pod labels exclude existing Service selectors and workload allow policies. The known clusterwide host and DNS allowances are covered by a stage-only Cilium deny policy, in addition to a Kubernetes ingress/egress deny policy. The script checks both policies, the bound EBS identity, absence of Service endpoints, the loopback binds, no server routes or clients, and the correct empty JetStream account. It tests the Kubernetes loopback port-forward before restore. Stop if any isolation or forwarding check fails.

The native NATS CLI account restore uses the same pinned archive as capture. It connects only to the staged Pod through that private tunnel. The restore intent is recorded before importing anything. Verification compares the captured stream definitions and sequence state and the four durable consumers' configuration and cursors. A server ID can change. The receipt ignores only the same per-observation consumer timestamp omitted at capture.

A failed stage command can be retried with `stage --attempt "$attempt"`. The attempt lock, resource labels, and UID receipts guard creation and retries. If restore stops after submitting the native operation, run `verify` to check whether the exact capture was recovered. If it was partial, stop that attempt and start a new one. The script does not restore over a nonempty account or clear a partial claim.

When the rehearsal no longer needs to run, stop its ephemeral resources while retaining the claim and all evidence.

```sh
python3 "$nats_rehearsal" stop --attempt "$attempt"
```

Shutdown checks every remaining ephemeral resource against its recorded UID before writing the stop intent. It then removes only that attempt's Pod, ConfigMap and policies with UID preconditions. Cleanup uses the attempt receipt and does not depend on the backup files still being readable. It retains the claim, source host path and snapshot files. If a hard interruption happened before a created resource UID was saved, rerun the stage command with the same attempt to reconcile it before shutdown. This rehearsal does not validate the final StatefulSet replacement or a fresh production data capture. Final handoff needs a separately reviewed immutable-claim-template replacement, a fresh quiesced source comparison and post-handoff verification.

### Rehearse the pinned capture after source-node loss

Use incident mode for the reviewed replacement Pod on the new node after the original node disappears. This mode verifies the recorded replacement identity, original storage bindings, release 5, authentication Secret metadata and pinned snapshot files. It rehearses the historical capture in a new retained claim. The current host-path contents require a separate assessment. The incident stage schedules only on EKS On-Demand nodes and verifies the assigned node before restore.

```sh
python3 "$nats_rehearsal" preflight --incident
python3 "$nats_rehearsal" stage --incident
# Use the new nats-incident-* directory printed by stage.
python3 "$nats_rehearsal" restore --incident --attempt "$attempt" --nats-archive "$archive"
python3 "$nats_rehearsal" verify --incident --attempt "$attempt"
python3 "$nats_rehearsal" stop --incident --attempt "$attempt"
```

Use the same `--incident` flag and attempt directory when retrying. Incident mode uses a separate namespace of attempt names and refuses normal rehearsal directories. It retains each rehearsal claim when stopping its ephemeral resources.

Incident verification retains the raw inventory and its digest. For pristine empty
NATS 2.15.2 file streams only, native restore may change `first_seq` from zero to one
and recreate idle durables with a later creation timestamp. The comparator permits
only those differences and requires all configuration, messages and cursor state to
match. See the pinned [stream restore implementation](https://github.com/nats-io/nats-server/blob/v2.15.2/server/stream_backup.go#L414-L475),
[empty file-store sequence handling](https://github.com/nats-io/nats-server/blob/v2.15.2/server/filestore.go#L10768-L10780)
and [consumer creation](https://github.com/nats-io/nats-server/blob/v2.15.2/server/consumer.go#L1237-L1242).

## Journaled production handoff

The handoff is specific to the reviewed Helm revision 5, captured source identities
and accepted incident rehearsals. `prepare` reads the live cluster, renders the
exact proposed changes and records a private schema-2 journal. It changes no workload.
Renamed StatefulSet CREATE dry-runs check schema and admission without starting a
controller; they do not establish admission under the production names.

Run each subsequent phase only after the preceding command succeeds and its evidence
is checked. These commands intentionally pause the API and replace source StatefulSets.
All old and new claims, off-node backups and original rehearsal receipts are retained.

```sh
handoff=deploy/eks/omniscience-secondary-storage/secondary_handoff.py
python3 "$handoff" prepare --nats-attempt "$attempt"
python3 "$handoff" pause-api
python3 "$handoff" stop-stage-writers
python3 "$handoff" stop-sources
python3 "$handoff" install
python3 "$handoff" verify-live
python3 "$handoff" resume-api
```

Exclude concurrent Helm/GitOps writers. Before source shutdown, the coordinator
checks the freshly rendered manifest and admission again, quiesced inventories,
UIDs, retention, detached EBS claims and protected PostgreSQL/Neo4j identities.
Helm 6 starts the stores with API replicas zero. Exact live data, runtime layout,
authentication, Qdrant peer, EBS bindings and Service endpoints gate Helm 7 API resume.
The Qdrant post-renderer is required for this stored chart on every later upgrade;
an upgrade without it would attempt to restore the old claim template and peer URI.
Do not apply the new owner chart until its retained-store configuration is reconciled.

Before source shutdown starts, `cancel` can resume the original API after checking
its pinned sources. This restores the pre-handoff service state; it does not recover
the data lost with the Spot node. Once source shutdown starts, recover forward using
the retained claims. An interrupted deployed Helm revision can be reconciled by
repeating its command when the marker, manifest and hooks match. A pending or failed
revision requires inspection and reviewed forward repair, with the journal and
release history preserved. Helm 7 may already have set API replicas to one before
recording failure: inspect actual replicas and use a UID/spec/resource-version guarded
pause if repair needs quiescence. Never blindly roll back to the hostPath templates,
delete claims or resume an unverified store.
