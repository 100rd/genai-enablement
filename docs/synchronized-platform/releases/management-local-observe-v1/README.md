# Local source qualification — management-local-observe-v1

Qualified on 2026-11-06 on macOS ARM64 / Docker Desktop. All three components and the host runner
are running. This is the new local advisory profile; it grants no remediation or production authority.

[Machine-readable receipt](qualification.json), [source snapshot](source-snapshot.json),
[execution ledger](../../../../portfolio/local-observe-progress.json),
[operations runbook](../../../runbooks/management-local-observe-v1.md).

## Accepted behavior

| Check | Observed result | Evidence |
|---|---|---|
| Real tenant knowledge and login | Both Keycloak users read their own real Omniscience MCP data; foreign workspace access refused; beta cannot read alpha's platform observations | [Chromium](browser-tests.txt) |
| Identity boundary | Own read 200; absent identity, bad signature, expiry, audience or role 401; wrong scope, foreign tenant and selectors 403 | [11 live checks](security-final.json) |
| Omniscience failure | Two negative probes open one case, real Codex produces an assessment, two positive probes resolve it; additional negative timestamps do not create another job | [Accepted](omniscience-second-accepted.json), [recovered](omniscience-second-recovered.json) |
| Portal backend failure | Case and real assessment persisted while Portal was down, visible after recovery | [Accepted](portal-drill-accepted.json), [recovered](portal-drill-recovered.json) |
| Barbarossa API failure | Independent observer persists case directly to the owner store while API is down; pending work is visible after API return and processed when runner returns | [Case during outage](barbarossa-outage-case.json), [pending runner](barbarossa-pending-runner.json), [recovered](barbarossa-drill-recovered.json) |
| Observer and runner loss | After 96 seconds stopped, freshness becomes stale and does not render healthy | [Stale projection](observer-runner-stale.json) |
| PostgreSQL failure | Owner returns 503; Portal shows unavailable with no healthy projection; history readable after DB recovery | [Unavailable](database-unavailable.json), [browser drill](database-browser-drill.txt), [recovered](database-recovered.json) |
| Full launcher stop/start | Five cases, three assessments, five launch reservations, job states/epochs, private files and nine volume creation times unchanged; no duplicate call | [Restart comparison](restart.json) |
| Final UI | Evidence, supplied historic Omniscience context, non-authoritative recommendations and prior runner error are visible as text | [Screenshot](portal-qualified.png), [final owner status](final-status.json) |

The three accepted cases are:

- Omniscience: `case-63f3a808540611a83a04032d5c35a061304e5cd2981ae2d389feabed07c15024` — opened 15:18:39Z, assessment 15:18:48Z, resolved 15:20:39Z.
- Portal: `case-29357c89381f46f4f55cf9be64910538989818b099b99523460f4ff8f605de6b` — opened 15:22:39Z, assessment 15:22:46Z, resolved 15:23:39Z.
- Barbarossa: `case-f4bda5c69dbeea87c1c93179cbd160b7522f8e6afc10a8538f75803383c4b080` — opened 15:28:12Z, assessment 15:28:22Z, resolved 15:29:12Z.

All three assessments use real `gpt-6-luna` through host Codex CLI 0.159.2. Each was accepted on its
first attempt after the final result contract was installed. An earlier Omniscience drill produced
two rejected responses. Their exact rejection subtype was not retained by the earlier diagnostic
format; no assessment was accepted. The schema was then constrained to the job's exact citations,
bounded single-line text and small lists, and tested against the actual CLI wire protocol before
repeating the drill. The failed job and its two reservations remain in history. This accounts for
five model launches, three accepted assessments, one historical failed job and zero duplicate
accepted results. A separate initial startup case recovered before a model attempt and was cancelled.

The final browser run passed three tests with the outage-only fourth test skipped because the store
was healthy. That fourth test passed separately while the local PostgreSQL service was stopped.
The displayed runner error is historical; the final runner is online with no queued or active job.

## Code and negative checks

| Owner | Verification |
|---|---|
| genai-enablement | [246 tests, 91 explicit skips, 306 subtests](genai-tests.txt); synchronized workspace ADR/SPEC/owner check passed |
| Omniscience | [86 focused Python tests](omniscience-tests.txt); 12 Go consumer-kit tests including independent digest/receipt binding and relative checkout roots; broader focused checks were run during implementation |
| Barbarossa | [Root Go regression with race detector](barbarossa-go-tests.txt); nested API Go tests; [seven PostgreSQL 18 integration tests](barbarossa-postgres-tests.txt) in a disposable test container |
| Portal | [407 backend tests, four explicit skips](portal-backend-tests.txt); frontend unit regressions, direct ESLint and TypeScript checks; actual Chromium checks above |
| Codex process boundary | Installed CLI loopback fixture confirmed zero tools, structured output, inherited lock and process-group behavior without a paid model call; parent/supervisor death and timeout tests passed |

Negative tests cover malformed/oversized/duplicate JSON, invented citations, wrong context identity,
wrong workspace, stale leases, duplicate accepted delivery, maximum attempts, one active lease,
durable six-per-hour reservations, process timeout and orphan exclusion. Mutating-operation negative
checks use disposable HTTP test handlers and isolated PostgreSQL test schemas; the live security
observer performs reads only. Prior ManagementWorkItem tool requirements remain unchanged.

Independent integration, Python, Go, TypeScript, SQL and security reviews were followed by root diff
review and repeated key checks. Findings were fixed before dependent integration. The final narrow
Go review also passed `go vet`; installed `staticcheck` cannot read Go 1.27.1 export data and is not
claimed as a passing check. Full per-agent token/time/retry metrics were not exposed or recorded by
the collaboration API; the ledger explicitly leaves unavailable measurements null rather than
inventing them. Recorded durations are estimates where marked.

## Source and release boundaries

All implementation lives in `codex/local-observe-v1` worktrees beneath the four repositories.
At the time of this qualification, no commit, push, registry publication or production deployment
had been performed. Subsequent source commits and pull requests are tracked in the
[publication record](../../../../portfolio/local-observe-publication.json); the historical snapshot
and live qualification results remain unchanged. The source snapshot
pins each base Git HEAD plus every changed/new nonignored file hash (including deleted paths), with
this evidence directory excluded to avoid a self-reference. This identifies uncommitted source;
it is not a clean release revision. The local image IDs are in the qualification receipt. Omniscience's
final development image was assembled by overlaying current application/contracts on its local
source-built base; no release OCI digest or reproducible publication claim is made.

Original dirty checkouts and their Git HEADs were preserved, including SP-86/SP-101 WIP; see
[original preservation audit](original-preservation.json). Existing volumes and unrelated Docker
projects were retained. The new profile owns eight runtime volumes plus a persistent state-binding
guard. Keycloak now has a retained data volume; both users logged in after the complete stop/start.

SP-99/SP-100 are merged baseline deliveries. SP-86 source changes and SP-101 Knowledge View passed
local verification. SP-86 publication is still gated by clean source/producer release evidence and
OCI publication. Earlier profiles retain their own selections and receipts. Legacy source tests
passed, including protected CMC reads and their signed Portal integration; this run does not assert
a fresh live qualification of older profiles or replace their receipts.

Remaining queue: SP-89, SP-94, published images, AWS integration, execution of recommendations,
image vulnerability scanning and HA. Native Linux bind permissions have not been qualified. The
observer is one synthetic source sharing the host's failure domain; healthy here is not external
availability. The prepared Omniscience context is an immutable historic snapshot, with timestamps
shown to the model and Portal. Model text cannot alter component state or execute commands.

## Repeating checks

Use the exact owner worktrees and persistent state paths in the runbook. From this coordinator
worktree run:

```sh
PYTHONDONTWRITEBYTECODE=1 .local-observe/venv/bin/python -m pytest tests -q
PYTHONDONTWRITEBYTECODE=1 .local-observe/venv/bin/python scripts/check_synchronized_platform.py --workspace-root ..
.local-observe/venv/bin/python scripts/local_observe.py status
```

In the Barbarossa owner, run root `go test -race ./...`, the nested `cmd/barbarossa-api` tests, and
`cmd/barbarossa-observe` with `BARBAROSSA_OBSERVE_TEST_DATABASE_URL` pointing to a disposable test DB.
The actual-CLI fixture is `TestPinnedCodexSendsNoTools` with `BARBAROSSA_TEST_CODEX_BINARY` set to the
absolute pinned CLI path. It uses synthetic loopback authentication and does not consume a real turn.

Portal's `frontend/playwright.local-observe.config.ts` runs the browser tests against port 13000.
Supply the two generated passwords through the test environment, never command arguments or logs.
Set `LOCAL_OBSERVE_EXPECT_INCIDENT=1` for recorded incident history. The outage assertion requires
`LOCAL_OBSERVE_EXPECT_OWNER_UNAVAILABLE=1` and a deliberately unavailable profile-local owner store.
Only stop services in the generated profile; restore them after the exercise. A new material failure
can consume the persistent model budget. Stop/start uses the launcher and retains volumes; never
use `down -v` or replace the state directory against existing profile volumes.
