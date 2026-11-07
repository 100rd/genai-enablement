# Frankfurt PostgreSQL network policy preparation

This command prepares a policy-only change in `splatform` on the verified
`nonprod-euc1` EKS cluster. It requires the private verified AWS context
helper used by Omniscience storage recovery and PyYAML. It reads the three
owner Helm charts from their activation worktrees.

```sh
rtk proxy python3 deploy/eks/postgres-network-boundaries/prepare.py
rtk proxy python3 -m pytest -q deploy/eks/postgres-network-boundaries/test_prepare.py
```

The command captures policy specs, database Service and StatefulSet selectors,
pod identities, and workload template labels. It requires one canonical running
primary per owner and accepts the Omniscience API deployment at zero replicas
during maintenance. Cilium must match the supported clusterwide baseline and
any namespace Cilium rehearsal deny rules must be disjoint from the checked
endpoints.

The proposed policy set scopes the three database policies to explicit owner
runtime, migration, and bootstrap labels. The owner egress policies bind
TCP/5432 to the corresponding primary. Narrowing the overlapping private-store
policies removes their database access while retaining the intended Omni NATS,
Qdrant, and Neo4j paths and Portal's separate Keycloak policy. DNS and the
caller policies' other existing ingress and egress rules are retained. The
plan requires canonical bundled primaries and a separate review for topology
changes, including read replicas or database backup CronJobs.

Four creates stage grants for authorized callers and Qdrant before nine
patches narrow existing policies. Each patch tests the current UID, resource
version, and entire spec before replacing the spec. The command checks that
each prefix of the proposed order preserves the required ordinary pod paths.
It sends all operations with server dry-run and compares the admitted
identities and specs. Only after a second identical inventory and source
check does it write a private directory with the snapshot, ordered operations,
proposed specs, and aggregate receipt. The receipt records source hashes
alongside the historical review hashes so source drift stays visible. The
source check compares the chart values for database ingress and checks for
the owner egress policy in each template. Full Helm rendering is covered by
the separate owner chart regression in `tests/test_postgres_network_boundaries.py`.

The prepared receipt describes admission and policy semantics at capture
time. Any later execution requires a fresh identity and union check immediately
before authorization and revalidation after each operation. The sequence is
not atomic across policies. Record applied prefixes and stop if a CAS test
fails or any intervening policy, workload, or Service changes. Reconcile the
current prefix before resuming. An automatic rollback could restore broad
database access and requires separate review. Helm owns the patched policies
and can overwrite the live specs on a later upgrade. Before a later Helm
upgrade, reconcile the owner chart policies, including the live Omni
NATS/Qdrant split and additional Qdrant policy. Keep the Omniscience storage
handoff and Helm revision changes separate from policy activation.

Traffic verification requires approved owner and negative test probes from
the relevant pod identities after an authorized rollout. Host and control
plane carve-outs are outside the ordinary pod-traffic check.
