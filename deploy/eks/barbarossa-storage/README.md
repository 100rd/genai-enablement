# Barbarossa PostgreSQL storage cutover

Move the current Barbarossa local-profile PostgreSQL database to an encrypted 8 GiB retained EBS claim. This procedure uses the existing `barbarossa` Helm release, StatefulSet, Services, Secrets, and database name. A Frankfurt profile needs a separate database or schema and its own enrollment.

## Preflight

Use the verified `nonprod-euc1` EKS context for account `120736097561`, namespace `splatform`. The worktree must contain the private `.local-observe/eks-verification/aws_context.py` helper. Requirements are Python 3.10+, AWS CLI, kubectl, Helm and yq v4. Confirm EBS CSI is healthy. The script checks the encrypted `splatform-gp3` StorageClass uses `Retain` and `WaitForFirstConsumer`. Confirm staging and the original workload can schedule in the same AZ.

Run from the worktree root.

```sh
recovery=deploy/eks/barbarossa-storage/recover.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s deploy/eks/barbarossa-storage
python3 "$recovery" dryrun
python3 "$recovery" stage
```

Staging creates a new claim, Pod, Service, and narrowly scoped PostgreSQL probe ingress rule. The staged data volume is separate from the original. The probe image is the digest of the running Portal backend image, reused for its PostgreSQL client. The probe only receives Barbarossa URL keys. Stage before pausing writers to reduce downtime.

## Quiesce, capture, and restore

Record the current desired replica count for both `barbarossa-observer` and `barbarossa-api`. Pause releases, migrations and other writers for this database. Scale the observer to zero first and wait for it to terminate. Scale the API to zero and wait for it to terminate. Keep these writers paused through live data verification. The capture command checks both deployment replica counts and Pod selectors, active Barbarossa Jobs, and client connections to the database.

```sh
python3 "$recovery" capture
python3 "$recovery" restore
python3 "$recovery" verify-stage
```

Capture uses the running PostgreSQL 18.6 client to dump the live database to a new private directory under `.local-observe/frankfurt-activation/barbarossa-storage-current`. It records a SHA-256, source Pod, container and StatefulSet identities, and a count and sorted SHA-256 row fingerprint for each of the 12 tables. It also records schema, role verifier and sequence fingerprints, ignoring only PostgreSQL's random dump restriction markers. It checks that the source data and identity stayed stable through the dump. The observation table must contain at least the reviewed floor of 5,900 rows. Actual verification uses the final captured count and fingerprint, including observations added since preflight. The migration table is fingerprinted with the application tables.

The restore targets the isolated claim. It checks the mounted claim, running Pod and Service endpoint, owner/admin role definitions, expected bootstrap locale, and empty schema before loading. It filters four duplicate bootstrap statements and preserves the application owner flags, verifier, DDL, ACLs and table data. Verify-stage compares all table fingerprints and authenticates both URL Secret keys over the staging Service. Restore and verify receipts are private. If capture or restore fails halfway, inspect the attempt before retrying. The script refuses to overwrite a previous dump or reuse a populated restore target.

## Cutover and resume

```sh
python3 "$recovery" stop-stage
python3 "$recovery" cutover
python3 "$recovery" verify-live
python3 "$recovery" resume
```

The cutover requires the stage Pod to be gone, no other Pod to mount the claim, the original source and Helm revision to match the capture, the writers to remain paused, and the original database contents to match the capture. The server-side dry run compares the entire installed revision 1 manifest with the proposed release and permits the PostgreSQL pod image and data mount changes and the two temporary writer replica changes. It compares the generated database and application Secrets against live values in memory. No Helm hooks are expected. Revision 2 sets both writers to zero. The observer template accepts zero for maintenance and one for normal operation. Its baseline and maintenance hashes are recorded in the private receipt. The upgrade waits up to ten minutes and retains the PVC if a rollout stalls.

Verify-live checks the new Pod's digest, sole PVC use, Service endpoint, original Secret login, and exact captured row fingerprints before resuming writers. The separate `resume` command verifies the live receipt again and creates Helm revision 3 with both replica counts restored to their reviewed original value of one. Its dry run allows only those two replica changes. Confirm both deployments become ready. Check that the observer resumes recording data and that the API reports the expected local-profile state. Once the observer starts, its live data will diverge from the quiesced capture.

Keep the backup, receipts, PVC and Retain PV. Rolling back Helm to revision 1 would recreate the empty data mount. If the upgrade times out, inspect the live Helm revision, StatefulSet, claim and attachment while the writers remain paused. Repair the retained-volume rollout or restore the private backup onto a separate claim. Carry the existing-claim and image digest values forward in later Barbarossa releases.
