# Runtime profile: `management-local-observe-v1`

- **Status:** locally-qualified-source
- **Governing decision:** [ADR-0025](../../decisions/0025-management-local-observe-v1.md)
- **Runtime components:** Omniscience, Barbarossa, Platform Portal
- **Domains:** local Reliability reachability; local Security access boundaries
- **Availability class:** development-single-host; HA not qualified
- **Effects:** forbidden; assessments are advisory

## Assembly

The source-mode launcher accepts exact owner project roots, uses the owners' build/migration artifacts,
and generates one isolated Compose project. All newly created volumes and networks carry the profile
prefix. Public host bindings are loopback-only. The original profile's volumes and unrelated Docker
projects are never reset or stopped.

Default host ports: Portal 13000, Omniscience Admin 13001, Keycloak 18081; qualification-only owner reads
18000 (Omniscience), 18001 (Portal), 18080 (Barbarossa); runner listener 18082. The host Codex runner
belongs to Barbarossa and receives no store/broker credentials. Its credential is distinct from the
Portal signing key. Generated configuration is private, ignored, never overwritten implicitly, and
never printed by the launcher.

## Read and analysis contracts

The owner public API exposes `GET /v1/observe/status`, `/v1/observe/cases`, and
`/v1/observe/cases/{id}` using `schema_version: 1`. It carries observation provenance, freshness,
components, cases, assessments and runner status. Protected reads require the exact ADR-0025 delegated
identity. Minimal liveness/readiness remains separate from tenant data.

The internal listener accepts authenticated JSON POSTs to `/internal/analysis/claim` and
`/internal/analysis/{work_id}/{heartbeat,submit,fail}`. Claims bind runner id, work/case id, lease epoch,
opaque lease token, expiry, hard deadline and immutable observation refs. Submission cannot choose
tenant, case identity, authoritative status or accepted evidence outside the claim.

`AnalysisOnly` is a separate work contract: no capability to run tools is granted. The existing
federation contract's non-empty tool requirement is not weakened. Model response fields are
`model_revision`, `facts_cited`, `hypotheses`, `alternatives`, `uncertainty`, and `proposals`.
The owner seals the final assessment and supplies all trusted identifiers and timestamps.

## Acceptance

1. Real MCP reads, context and Knowledge View distinguish empty, denied, stale, incompatible and offline.
2. Two independent tenants read their own seeded workspace and cannot infer another tenant's data.
3. Readiness observations change with the running services; fixed replay cannot satisfy this profile.
4. A controlled owner failure opens one case and one analysis; recovery is recorded without history loss.
5. Missing observer/runner/owner/store evidence cannot become a favorable state.
6. Invalid auth, signatures, claims, model output, references and stale leases are rejected.
7. Restart preserves rate limits, attempts, observations, cases and exactly one accepted result per job.
8. Portal renders safe recommendations as text; no command execution or managed write is possible.
9. Prior profiles keep their independent receipts; this profile cannot claim SP-89/SP-94 or production.

## Local operation

Use the source launcher [scripts/local_observe.py](../../../scripts/local_observe.py) only on a
trusted host with the host Codex CLI already authorized for ChatGPT. The currently exercised host is
macOS with Docker Desktop on ARM64. Native Linux with a non-root Docker daemon and mode-0600 bind
mounts has not been qualified. The runner uses the host Codex CLI in analysis-only mode; the current
host authorization and CLI session are shared by that single trusted-host loopback HTTP workflow.
No API key, additional Codex authorization, or tool-enabled analysis is part of this profile.

See the [local operation runbook](../../runbooks/management-local-observe-v1.md) for prerequisites,
exact owner checkout paths, commands, state handling, and qualification boundaries. Portal is at
`http://localhost:13000`; Omniscience Admin is at `http://localhost:13001`. Portal-to-Barbarossa read tokens
expire after 60 seconds; Omniscience workspace read tokens have a 900-second ceiling. The launcher creates
eight isolated persistent runtime volumes, including Keycloak, and a state-binding guard volume that
prevents the fixed profile/volume names from being used with a different credential directory.
Normal stop retains all of them. Never use `down -v`, reset the profile, or delete its credential or
binding state. After stopping this profile, restore an older profile using that profile's own config
and volume names.

Local source qualification passed all three component faults with real Codex analysis and recovery,
two-tenant browser/MCP checks, observer/runner staleness, database failure and full restart persistence.
See the [qualification report](../releases/management-local-observe-v1/README.md). This source run does not close SP-89/SP-94,
qualify a release OCI image, or change receipts from prior profiles. The optional
`--retain-failed-result` flag is for qualification only: it may retain one bounded rejected raw model
response in private state, which may not be valid JSON. It is off by default. Keep usernames
`observe-alpha` and `observe-beta` and all generated passwords/private state credentials private;
never print or share them.

Current execution evidence and independent review are recorded in
[`local-observe-progress.json`](../../../portfolio/local-observe-progress.json).

Committed source and coordinated pull requests are tracked in
[the publication record](../../../portfolio/local-observe-publication.json). Local qualification does
not imply PR merge, published OCI release or production activation.
