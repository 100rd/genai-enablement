# Runbook: management-local-observe-v1

This runbook operates the isolated, source-built local management observation profile. It is a
single-host development qualification, not a production deployment. First source builds and
qualification exercises take longer than starting already built images.

## Prerequisites

- macOS with Docker Desktop on ARM64, running and using a local Unix-socket Docker context. This is
  the exercised host configuration. Native Linux bind-mount permissions have not been qualified.
- Python 3 and a virtual environment with `PyYAML` and `cryptography` installed. `cryptography` is
  used by the launcher; PyYAML is needed by the source/render tooling.
- Docker Compose and Buildx, plus Go for building the host runner.
- Codex CLI 0.159.2 already authorized through ChatGPT on this trusted host. The runner uses that
  existing authorization for analysis-only work. Do not supply store or broker credentials to it.
- The three owner source worktrees at the defaults below, or explicit paths passed with all three
  owner flags.

From the `genai-enablement` checkout, create the Python environment:

```sh
python3 -m venv .local-observe/venv
. .local-observe/venv/bin/activate
python -m pip install PyYAML cryptography
```

The launcher resolves these owner checkout defaults from the common Git checkout:

```text
/Users/lo/Develop/multi-team-agentic/project/Omniscience/.worktrees/local-observe-v1
/Users/lo/Develop/multi-team-agentic/project/Barbarossa/.worktrees/local-observe-v1
/Users/lo/Develop/multi-team-agentic/project/platform-portal/.worktrees/local-observe-v1
```

If the source worktrees are elsewhere, provide **all three** flags on every command that needs owner
paths (`render`, `build`, `up`, or `activate`). When restarting only the runner, pass
`--barbarossa` to `start-runner` with that same explicit owner checkout. Full owner path flags:

```sh
--omniscience /absolute/path/to/Omniscience \
--barbarossa /absolute/path/to/Barbarossa \
--portal /absolute/path/to/platform-portal
```

The paths must point at the corresponding owner repositories and source worktrees, not deployment
artifacts copied elsewhere.

## Initialize, render, and build

Initialize private runtime state once. The default is `.local-observe/runtime`; use the same state
directory for every later command:

```sh
python scripts/local_observe.py init
python scripts/local_observe.py render
python scripts/local_observe.py build
```

`render` validates the isolated combined Compose configuration and materializes it in private local
state. `build` builds the services from the three checked-out source trees. For a targeted rebuild,
repeat `--service SERVICE_NAME`, for example:

```sh
python scripts/local_observe.py build --service omniscience-api
```

The optional owner path flags can be appended to each applicable command. The normal `build` path
builds all selected source services; it does not activate the stack.

## Activate and inspect

Start the services, seed and verify both tenant workspaces, then start the host analysis-only runner:

```sh
python scripts/local_observe.py activate
python scripts/local_observe.py status
```

Append all three owner path flags to `activate` when using non-default checkout locations. Activation
waits for Compose health checks before bootstrapping owner reads. Portal is served at
`http://localhost:13000`; Omniscience Admin is at `http://localhost:13001`. The local owner-read
qualification endpoints and runner listener use the loopback-only ports described in the runtime
profile. Portal-to-Barbarossa signed read tokens expire after 60 seconds. Broker-minted Omniscience
workspace read tokens have a 900-second TTL ceiling. The separate persistent broker credential can
only mint that restricted profile for the two prepared workspaces.

`status` reports the profile's Compose services. Runner diagnostics stay in the private state
directory (`runner.log`); inspect that file locally if startup or queue contact fails. The launcher
does not print credential values. Usernames `observe-alpha` and `observe-beta`, generated passwords,
signing keys, and all other private state credentials must remain private.

In Portal, open **Control** for Barbarossa cases, the analysis queue and history, runner heartbeat,
and accepted results/recommendations. Select a job to see that job's exact accepted result, then
use **Open recorded evidence** to inspect its case observations in **Observe**. **Refresh work**
requests a new read; the work view shows snapshot times and does not poll automatically.
An empty confirmed queue means no jobs on that page, while denied or failed reads show a separate
message. Recommendations remain text. The **Observe** landing page retains connection checks and
tenant knowledge; **Local Observations** contains domain/component state and case evidence.

The internal queue uses authenticated HTTP on fixed loopback under a single trusted host assumption.
Protection against another privileged local process impersonating that listener is outside this
profile. Codex manages refresh of the existing host ChatGPT login; credentials never enter containers.

During qualification only, `activate --retain-failed-result` or `start-runner
--retain-failed-result` enables retention of the first bounded rejected raw model response. It may not
be valid JSON and is sensitive evidence. Do not enable this option in normal use; it is off by
default.

## Stop and preserve state

Stop the runner and Compose services while retaining all named volumes and local credentials:

```sh
python scripts/local_observe.py stop
```

The profile has eight persistent runtime volumes, including Keycloak, plus a state-binding guard
volume. The guard ties the fixed project and volume names to the credential directory. Keep the
original `.local-observe/runtime` directory and Docker volumes together. Never run `docker compose
down -v`, remove profile volumes, or initialize a replacement state directory against existing
volumes. To resume, use the same state directory and owner paths. To restore an older management
profile, first stop this profile and use that older profile's own configuration and volume names.

If only the host runner must be stopped, use `python scripts/local_observe.py stop-runner`; normal
profile stop handles it automatically. To see Compose state before stopping, use `status`.

## Qualification boundary

The exercised local source qualification passed controlled faults of all three components, real
Codex analysis, browser evidence/recommendations, tenant isolation, observer/runner staleness, database
unavailability and a complete stop/start with preserved history and budgets. See the
[qualification report](../synchronized-platform/releases/management-local-observe-v1/README.md). This source-built run does not
close SP-89/SP-94, qualify a release OCI image, or update earlier profile receipts. The current
progress record is [local-observe-progress.json](../../portfolio/local-observe-progress.json).
