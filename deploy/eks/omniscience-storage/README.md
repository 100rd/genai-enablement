# Omniscience PostgreSQL storage cutover

Move the current Omniscience PostgreSQL database to an encrypted 8 GiB retained EBS claim. The procedure keeps the existing database, credentials, workspaces, sources, client Services, and Helm release. NATS, Qdrant and Neo4j are outside the data move. Plan the Neo4j storage change separately.

## Preflight

Use EKS `nonprod-euc1` in account `120736097561`, namespace `splatform`. The recovery script validates the kubeconfig endpoint and certificate against AWS and uses the private `.local-observe/eks-verification/aws_context.py` helper. Requirements are Python 3.10+, AWS CLI, kubectl, Helm and yq v4. Verify EBS CSI readiness. Confirm staging and the original workload can schedule in the same AZ.

Run from the worktree root.

```sh
recovery=deploy/eks/omniscience-storage/recover.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s deploy/eks/omniscience-storage
python3 "$recovery" dryrun
python3 "$recovery" stage
```

The dry run renders both proposed Helm transitions and checks entire manifests. Staging checks names are free and creates the retained claim, Pod, Service and staging-only probe ingress policy. It reuses the source scheduling constraints and pinned PostgreSQL 18.6 image. It verifies the original PostgreSQL Service does not select the staging Pod. The bootstrap probe runs before the API pauses. It authenticates both URL Secret keys to the fresh owner database, checks role and database identity, and executes `SELECT 1`. The probe uses a digest-pinned Portal backend image and a dedicated label outside the broad Omniscience API policy. Its egress policy permits only CoreDNS and port 5432 to the original and staged Omniscience PostgreSQL Pods. Stop before pausing the API if staging or bootstrap authentication fails. Once the existing stage is ready and any network issue is resolved, `verify-bootstrap` can repeat the check without recreating staging resources.

## Quiesce, capture, and restore

Pause releases, ingestion, NATS consumers that write to this database, and other writers. Record the reviewed original replica count of one for `omniscience-api`. Scale it to zero and wait for its Pods to terminate. The API must stay paused through verification of the retained volume on the original Service. Capture verifies zero API replicas, no matching API Pods, no active Omniscience Jobs, and no remaining PostgreSQL client sessions.

```sh
python3 "$recovery" capture
python3 "$recovery" restore
python3 "$recovery" verify-stage
```

Capture creates a fresh `pg_dumpall` in a private directory under `.local-observe/frankfurt-activation/omniscience-storage-current` and records the dump SHA-256. It checks the pinned source Helm revision and Pod identity, and compares database table counts and row fingerprints, schema, owner and cluster role fingerprints, and sequence state before and after the dump. Schema fingerprints ignore the random PostgreSQL dump restriction tokens. The Alembic table is part of the fingerprint.

Restore verifies the staged Pod and Service, sole PVC consumer, exact role/database definitions, expected locale and empty schema. It removes four duplicate bootstrap statements and keeps the application owner, roles and grants, data and sequence state. Verify-stage compares the restored state with the fresh capture and tests both URL Secret keys through the staging Service, including a read of Alembic revision `0015`. The probe normalizes the installed SQLAlchemy `postgresql+asyncpg://` scheme for its libpq client. The operator should inspect a partial attempt before retrying. The script refuses to overwrite a previous dump or restore over a populated schema.

## Cutover and resume

```sh
python3 "$recovery" stop-stage
python3 "$recovery" cutover
python3 "$recovery" verify-live
python3 "$recovery" resume
```

The script deletes only the verified staging resources by UID precondition. It checks the stopped receipt, source fingerprints, no remaining PVC consumer, and the bound PV and encrypted EBS volume identity before cutover. The Helm upgrade reconstructs the installed root chart and downloads the exact archive hashes for PostgreSQL 18.12.18, NATS 2.15.2, Neo4j 2026.10.1 and Qdrant 1.20.0. It uses the current release values without exporting them and compares every rendered Secret with its live value in memory. The manifest comparison allows only the PostgreSQL image digest and external data mount, and the Omniscience API replica count of zero in revision 2. The existing Qdrant test hooks and Omniscience bootstrap hook are suppressed for both upgrades.

Verify-live checks that the original PostgreSQL Service reaches the replacement Pod alone, validates the same EBS claim and image, rechecks all fingerprints and authenticates both current database URLs. Resume requires that live verification receipt and revalidates the data with the API still paused. It creates revision 3 with `replicaCount=1`; its server dry run permits only the API replica change. After resume, the script removes the retained probe egress policy by its verified UID. Confirm API readiness and a workspace or source read through its normal entry point after resuming.

Keep the dump, private receipts, PVC and Retain PV. If Helm times out, inspect the deployed revision and volume attachment while the API remains paused. A rollback to the pre-persistence revision recreates an empty data mount. Fix the retained-volume rollout or restore the fresh backup onto a separate claim. Carry the existing-claim values and image digest forward in future releases.
