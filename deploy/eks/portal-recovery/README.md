# Portal PostgreSQL recovery

This procedure restores the November 6 backup onto an 8 GiB retained EBS volume in `splatform` on `nonprod-euc1`. The final Helm upgrade keeps the existing StatefulSet, Services, app URL secrets, and release ownership. It replaces the data mount in the existing StatefulSet's pod template with an externally provisioned PVC.

## Preconditions

- Confirm the operator has the verified account `120736097561` context and the local `.local-observe/eks-verification/aws_context.py` helper. The script needs Python 3.10+, Helm, kubectl, yq v4, and AWS CLI.
- Confirm EBS CSI is ready and the encrypted `splatform-gp3` StorageClass uses `WaitForFirstConsumer` and `Retain`. The recovery pod and original StatefulSet use the same scheduling constraints. Confirm compatible node capacity in the PV's selected AZ before stopping staging.
- Confirm the failed source pod and its backup are accounted for. Preserve a fresh logical dump and checksum of the old pod before the final rollout. The old `emptyDir` lasts only as long as that pod.
- Confirm this is the first recovery attempt or inspect the current PVC and staging pod before resuming. A partial SQL restore requires inspecting the staged PVC and reinitializing a fresh, empty target with explicit operator approval. The filter checks a fixed backup hash and the restore checks a fresh database, so repeating the restore over partially restored tables fails.
- Coordinate a pause on any concurrent Portal release, migrations, or application writes until staging validation and cutover complete.

## Stage and verify

Run these commands from the worktree root. The script keeps SQL and Helm output in process memory and only prints step results.

```sh
recovery=deploy/eks/portal-recovery/recover.py
backup=.local-observe/frankfurt-activation/backups/20261106T225549Z/portal-postgres.sql

python3 "$recovery" dryrun
python3 "$recovery" stage
python3 "$recovery" restore "$backup"
python3 "$recovery" verify-stage
```

Staging checks that its PVC, Service, and pod names are free and creates them without adopting existing resources. The staging pod clones the live PostgreSQL container and scheduling configuration, uses the pinned image, and has labels separate from the original PostgreSQL Service. The restore checks the backup SHA-256, confirms the bootstrap locale and empty schema, and removes four duplicate bootstrap statements. The existing admin role remains usable with the mounted Secret. The owner and runtime role definitions, ACLs, and data come from the backup.

Verification matches private restore and verification receipts to the source release, backup SHA-256, image, PVC UID, and PV. Verification compares all 17 public table names and row counts, Alembic revision `0009_kv_owner_entitlement`, and role privileges. A short-lived pod connects through the staging Service with both current Portal URL Secret keys and checks its role, database, and ability to read `tenants`. The runtime probe sets a synthetic tenant context for row-level security. The migration URL uses the `postgres` role. If either credential fails, stop before cutover and reconcile the restored role credential against the existing Secret through an authorized in-cluster procedure.

## Cut over

After verification passes, record the Portal backend's desired replica count. Scale it to zero and wait for its pods to terminate. Capture and checksum the original pod's final logical dump while the backend is paused. Terminate the staging writer and confirm it is gone before starting Helm. Check the retained PVC stays bound, and allow the EBS attachment to detach if the rollout schedules a different node.

```sh
python3 "$recovery" stop-stage
python3 "$recovery" cutover
# Restore the recorded Portal backend replica count in the verified context.
python3 "$recovery" verify-live
```

Cutover reconstructs the installed release's chart and pulls the pinned PostgreSQL chart package. It reuses the live Helm values in memory and applies `helm-values.yaml`. The server dry run compares all rendered resources against the installed release, allowing the PostgreSQL pod template's image and data volume changes. It compares both credential Secrets against live data in memory. The known bootstrap mappings hook is skipped for the storage-only upgrade. The upgrade waits up to ten minutes. The live checks validate the restored schema and both role logins through the original Service, then wait for the backend to become ready. Live row counts can increase when the app resumes.

If rollout or application verification fails, inspect the Helm release status, Pod and PVC events, volume attachment, and backend readiness. Keep the recovered PVC and its Retain PV. Avoid a Helm rollback to revision 1 because it recreates an empty data mount. If Helm times out, check whether it already applied the intended pod template before attempting the upgrade again. Carry the retained claim and digest values forward in subsequent Portal Helm releases.

## Execution receipt — 2026-11-07

Stage, restore, verify-stage, stop-stage, cutover and verify-live passed. The staging
probe was corrected to supply a transaction-local tenant context for runtime RLS and
to verify the actual migration role (`postgres`); credential values were unchanged.
The backend was paused and its original empty database dumped before cutover. The
installed release is now revision 2, with the original Service identities and the
retained PVC. Source and final-empty backups remain private. Unknown writes after
the restored backup timestamp cannot be claimed recovered. See the coordinator
recovery evidence; full platform acceptance remains open.
