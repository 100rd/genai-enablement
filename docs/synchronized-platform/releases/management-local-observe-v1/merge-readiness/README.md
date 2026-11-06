# Source merge readiness — 2026-11-06

SP-86 source work, SP-101, SP-102–SP-106 and the Control follow-up are merged in
all four repositories. [merges.json](merges.json) records the tested source heads,
actual merge commits and GitHub merge times. Each merge tree equals its tested source tree.
The original worktrees and earlier qualification receipts are preserved.

[verification.json](verification.json) separates source, CI, live local and deployment claims.
[source-ci.json](source-ci.json) contains all 17 passing PR workflows;
[main-ci.json](main-ci.json) contains the separate push workflows on the actual merge commits.
These workflow names retain their existing profile scope; a legacy HA check does not qualify
the new local profile for HA.

The lead repeated the actual two-tenant Chromium journey: 4 passed, 2 outage-only scenarios
explicitly skipped ([browser.txt](browser.txt)). Both tenants read their real Omniscience graph;
alpha reads Control and beta is refused by the configured Barbarossa allowlist. Control opens
the exact accepted analysis and its recorded Observe evidence ([fresh Control screenshot](control-analysis.png), visually inspected by the lead). The lead also repeated the
[11 signed identity checks](security.json), 28 Omniscience bootstrap/token tests, 22 Portal proxy
tests and the Barbarossa readaccess/localobserve tests. Audit-agent results and retries are
recorded without combining repeated tests into a misleading unique-test total.

An additional persistent-store replay closes AC-SP103-1 explicitly. The owner bootstrap
`python -m omniscience_server.local_observe` ran once against the existing isolated stores,
using the existing private broker credential. The coordinator bootstrap was not invoked:
no API was recreated, token mapping replaced or context refreshed. Read-only snapshots
before and after included fixed workspace/source/document/chunk IDs and content/version fields,
the entire dedicated Neo4j graph including temporal nodes and checkpoints, and paginated scoped
Qdrant payloads and vectors. Only hashes and counts are published. All full hashes matched;
see [seed-verification.json](seed-verification.json), [before](seed-before.json), and [after](seed-after.json).
There are 2 workspaces, 2 sources, 5 documents, 5 chunks, 23 graph nodes, 16 relationships and 7 points.

The [runtime snapshot](runtime-status.json) records healthy component observations and the unchanged
6 cases / 6 jobs / 4 accepted assessments / 6 reservations. No additional Codex call was made.
Original disruptive fault/recovery and restart evidence remains in its original receipt directories;
this audit does not pretend to rerun it or establish Kubernetes readiness.

The deployment agent owns charts and cluster validation. Use the
[Kubernetes handoff](../../../../runbooks/management-local-observe-kubernetes-handoff.md)
for build inputs, service identities, migrations, bootstrap, runner cutover and the new target's
acceptance checks. OCI release publication, SP-89/SP-94, AWS, image scanning, execution and HA
remain separate work.
