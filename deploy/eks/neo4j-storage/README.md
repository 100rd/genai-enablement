# Omniscience Neo4j retained storage

This procedure recreates the verified empty Omniscience Community graph on an encrypted 8 GiB EBS claim. It preserves the existing application-visible graph state, default lookup indexes, reviewed application schema and standard user login. A fresh store can change internal database IDs and system metadata. The verification receipt records the old and new IDs.

This workflow requires Omniscience Helm revision 3 after the PostgreSQL cutover. PostgreSQL, NATS and Qdrant keep their current StatefulSets, Pods and bound claims. If the graph has any nodes, relationships, unrecognized indexes or constraints, additional databases or nonstandard user state, residual label/type/property tokens, aliases, or custom store-side files, stop and keep the original Neo4j Pod. An offline backup plan is required for a migration of the original Neo4j stores. [Neo4j backup and restore planning](https://www.neo4j.com/docs/operations-manual/current/backup-restore/planning/)

## Preflight and stage

Use the verified EKS `nonprod-euc1` context for account `120736097561`, namespace `splatform`. The script imports the sibling Omniscience PostgreSQL recovery guards for cluster endpoint and certificate verification, Helm revision pinning, safe temporary chart reconstruction and UID-scoped deletion. Requirements are Python 3.10+, AWS CLI, kubectl, Helm, yq v4, the private AWS context helper, and healthy EBS CSI.

Run from the worktree root after PostgreSQL revision 3 is deployed.

```sh
recovery=deploy/eks/neo4j-storage/recover.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s deploy/eks/neo4j-storage
python3 "$recovery" dryrun
python3 "$recovery" stage
python3 "$recovery" prepare-stage-schema
```

Staging creates the PVC, a separate Service and a clone of the Neo4j pod template. It uses the source image digest and mounted config, Secret and subpath layout. Both original Services must target only the original Pod. The stage Service must target only the staged Pod. Temporary probe policies permit a dedicated image-pinned Pod to reach only CoreDNS and the Bolt port on those two Neo4j Pods. It uses the app's current Bolt URI, username and password references and never logs credentials.

Before pausing the API, `prepare-stage-schema` verifies authentication and exact catalogs through both source and staged Services. The source must contain exactly the app bootstrap schema and zero graph rows. The stage must have only its two default lookup indexes and no tokens. The command rechecks source release, Pod, endpoint and stage volume identities, then runs only [the reviewed schema DDL](application-schema.cypher) through the staged Pod's loopback Bolt port. The DDL comes from Omniscience commit `639c52dac220b461d286b86a6fdeb36cf89300a4` and is checked against a fixed allowlist. It includes eight RANGE indexes and four UNIQUENESS constraints with four backing indexes. It checks Community version 2026.10.1, both expected online databases, the current standard `neo4j` user, rejection of a wrong password with Neo4j's Unauthorized code, two exact default lookup index definitions, exact application index and constraint catalogs after staging, and an empty graph with the reviewed label/property tokens, zero relationship-type tokens and no database aliases. The filesystem gate checks imports, backups, licenses, plugins and dump paths and permits only the pinned image's standard plugin README. The script records only private inventory and resource identities. If staging or bootstrap fails, leave the API running and resolve the failure. Use `verify-bootstrap` to repeat validation on the already prepared stage before capture. If DDL is only partly applied, keep the source intact and investigate the staged catalog before proceeding.

## Quiesce and verify

Record the intended API replica count of one. Pause ingestion, other direct Bolt writers, release jobs and concurrent deployments. Scale `omniscience-api` to zero and wait for its Pods to terminate. Keep writers paused through live verification. The script checks zero API replicas, no matching Pods or active Omniscience Jobs, and no other Neo4j transaction during the quiesced inventory. The transaction check does not reserve a lock against a new writer, so keep external writers paused throughout.

```sh
python3 "$recovery" capture
python3 "$recovery" stop-stage
```

Capture rechecks the exact source and staged inventories, verifies the protected stores are unchanged, and writes a mode-0600 receipt. It compares source and stage logical state and records their separate internal database IDs. The original Pod stays up during these checks. Stop-stage verifies the staged inventory again and deletes only the staged Pod and Service by UID precondition. The PVC and probe policies stay in place.

## Cutover and resume

```sh
python3 "$recovery" cutover
python3 "$recovery" verify-live
python3 "$recovery" resume
```

Cutover requires the stage shutdown receipt, unchanged source state, matching retained EBS volume, and no PVC consumers. The server dry run reconstructs the installed chart with pinned dependency archives, sanitizes coalesced chart defaults before writing any temporary files, and checks all rendered Secret values against live values in memory. It compares the entire rendered manifest with release 3. Only the Neo4j image digest, data claim, and API replica count may change. The Helm override clears the inherited `emptyDir` with an explicit null. The manifest comparison treats only that exact null placeholder on the expected Neo4j claim as absent, matching the Kubernetes API's dry-run response. The live Pod must show the PVC as its sole data volume source. Storage-only upgrades suppress the previously reviewed hooks.

Revision 4 leaves the API paused. Live verification uses the existing application credentials over the original Service and requires the new Pod to mount the staged claim. The verified graph, schema, user state and staged database IDs must match. It also checks the original PostgreSQL, NATS and Qdrant Pod and claim identities. Resume rechecks the receipt, installs revision 5 with only the API replica change, then rechecks the protected stores' Pod and claim identities before deleting the probe policies by verified UID. Confirm the API becomes ready and a normal graph-backed read works.

Keep the retained claim and private receipts. Helm rollback to revision 3 would replace the retained Neo4j mount with a new empty volume. If a rollout stalls, inspect the live release, Pod, PVC and volume attachment with writers paused. Repair the retained-volume rollout and carry forward its claim and image digest in subsequent Omniscience releases.

## Recover a replaced emptyDir source after capture

Use this separate path only if the original source Pod was replaced after the quiesced capture, the API has stayed paused, and the retained staging claim is intact. The original capture and stopped-stage receipts remain authoritative. Keep them unchanged. Apply temporary Karpenter disruption protection to the current Neo4j and three protected store Pods before reopening the stage, and record the previous annotation values.

```sh
python3 "$recovery" recover-stage
python3 "$recovery" stop-recovery-stage
python3 "$recovery" cutover-recovery
python3 "$recovery" verify-live-recovery
python3 "$recovery" resume-recovery
```

The recovery guard requires the same deployed Helm revision 3 and Neo4j StatefulSet, a replacement Neo4j Pod and container created after capture, a pristine replacement graph, matching NATS and Qdrant identities, and a PostgreSQL replacement whose StatefulSet, claim, EBS volume, and database fingerprints match its verified capture. The recovered stage mounts the existing retained claim and starts Neo4j without applying DDL. Its full catalog and internal database IDs must equal the original staged inventory. Separate recovery receipts record the new source and staging identities. Create and shutdown intents are written before resource mutations. If a command is interrupted after creating the Service or while waiting for the Pod, rerun `recover-stage` to continue with resources bearing the original attempt label and pinned UIDs. If shutdown stops after the Pod is deleted, rerun `stop-recovery-stage` to finish the UID-guarded Service deletion. A foreign resource or a replaced owned UID stops either retry. Restore the previous disruption annotations after successful resume.

Run one recovery command at a time. If an interrupted command leaves the fixed-name Bolt probe Pod, the next invocation stops at the existing name. Before cleanup, verify the Pod's UID, dedicated probe label, pinned probe image and command against the interrupted attempt. Delete it only with a Kubernetes UID precondition, then retry. Leave any unidentified Pod untouched.
