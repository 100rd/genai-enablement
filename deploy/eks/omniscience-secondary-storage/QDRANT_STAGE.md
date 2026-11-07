# Isolated Qdrant restore rehearsal

The coordinator uses the completed Qdrant 1.20.0 native capture from `capture-nmq_o7wh`. It rehashes the pinned receipt and all seven artifacts, checks the source Helm revision and captured identities, and restores the seven captured points to an encrypted, retained 10 GiB gp3 claim in `splatform`. Run the rehearsal after independent review. The Omniscience API can stay online while the stage reads the off-node capture. The receipt proves recovery of the capture time state.

From this worktree root, check the capture offline and run the tests.

```sh
python3 deploy/eks/omniscience-secondary-storage/qdrant_stage.py check-backup
python3 -m unittest discover -s deploy/eks/omniscience-secondary-storage -p test_qdrant_stage.py
```

After review, run the rehearsal and verify the resulting stage.

```sh
python3 deploy/eks/omniscience-secondary-storage/qdrant_stage.py run
python3 deploy/eks/omniscience-secondary-storage/qdrant_stage.py verify
```

The stage has unique Pod and policy selectors, with Kubernetes and Cilium deny policies created before either Pod. It exposes REST and P2P on Pod loopback. The coordinator uses a local-only port-forward to the exact staged Pod and reads the captured authentication Secret reference into memory. The Pod starts with no bootstrap peer and advertises `http://127.0.0.1:6335/`. It loads the captured snapshot using the authenticated multipart upload route with the server-side SHA-256 check. The reviewed capture contains an empty alias set. The acceptance checks cover the exact collection configuration, payload index schema, aliases, seven vectors and payloads, and one Active local shard.

The first staged Pod is deleted with a UID precondition and replaced by a differently named Pod on the same EBS volume. The replacement must retain the staged peer ID and loopback URI, come up healthy, and return the same logical inventory. The staged peer has its own Raft state. A later replacement under the original StatefulSet name must use the same advertised URI and P2P loopback bind, with client listener settings reviewed separately for the original Services.

The private journal under `.local-observe/frankfurt-activation/qdrant-stage/` records creation intents, admitted spec hashes, resource UIDs, EBS identity and the rehearsal phase. Re-run `run` to resume the same intent after a transport interruption. A recorded in-flight upload resumes by inspecting the staged collection. If the expected state is absent or partial, the coordinator stops with the claim and Pods available for review. Preserve the journal and original capture. The accepted stage remains running with its deny policies. A staged shutdown and the original StatefulSet handoff require their own reviewed procedure.

[Qdrant 1.20.0 snapshot upload implementation](https://github.com/qdrant/qdrant/blob/v1.20.0/src/actix/api/snapshot_api.rs) · [Qdrant 1.20.0 P2P bind configuration](https://github.com/qdrant/qdrant/blob/v1.20.0/src/settings.rs) · [Qdrant snapshots](https://qdrant.tech/documentation/snapshots/)

## Spot interruption recovery rehearsal

On November 7, 2026, the capture node was terminated after a Spot interruption, and the first staged Pod was evicted before upload. The original StatefulSet recreated Qdrant on a different node with an empty collection inventory. The incident command checks the pinned capture and original Helm release, Secret, StatefulSet and host-path binding identities. It also checks that the capture node is absent and that the observed replacement Pod and Node have their reviewed UIDs. It restores from the off-node capture. The replacement's data is outside the rehearsal.

After reviewing the incident pins, start a fresh rehearsal and then verify it.

```sh
python3 deploy/eks/omniscience-secondary-storage/qdrant_stage.py recover-spot-stage
python3 deploy/eks/omniscience-secondary-storage/qdrant_stage.py verify-spot-stage
```

Both incident Pods require the observed EKS managed on-demand capacity class, `eks.amazonaws.com/capacityType=ON_DEMAND`. The fresh claim follows the first scheduled consumer's AZ. The incident journal is `.local-observe/frankfurt-activation/qdrant-stage-spot-20261107/`. The original journal and its retained claim are evidence from the interrupted rehearsal.
