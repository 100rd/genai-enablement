# `management-readonly-v1` integrated profile lock (task-sp-89-management-readonly-profile-qualification)

**Status:** independent, read-only qualification join over three already-published owner
release receipts (SP-86 Omniscience, SP-87 Barbarossa, SP-88 Platform Portal) plus the
SP-90 Go baseline transitively bound by SP-87. It does not repair a component, mint a
sibling receipt, edit the ADR-0021 selection, deploy anything, or replace missing
environment evidence with a mock. See
[ADR-0021](../../../decisions/0021-management-readonly-initial-runtime-profile.md) and
[the profile definition](../../profiles/management-readonly-v1.md).

```text
docs/synchronized-platform/releases/management-readonly-v1/
  README.md                  this file
  evidence/                  qualify_management_readonly_v1.py default-run output
                              (content-addressed by the joined lock's own digest;
                              never overwritten, only appended to)
  environment-receipt.json   NOT present. If a human later authorizes a named
                              non-production environment for SP-89, its receipt
                              (environment_identity, environment_owner,
                              allowed_operations, observation_window,
                              rollback_target) belongs here -- see "AC-SP89-3/5/6"
                              below for what changes when it exists.
```

## Regenerating the profile lock

```bash
python3 scripts/qualify_management_readonly_v1.py --report   # stdout only, no write
python3 scripts/qualify_management_readonly_v1.py --write     # write evidence only
python3 scripts/qualify_management_readonly_v1.py             # both (the verify command)
```

## What this join checks (AC-SP89-1..6)

| AC | What | Buildable without an environment? |
|---|---|---|
| AC-SP89-1 | One content-addressed lock joins the exact SP-86/SP-87/SP-88 owner digests and the SP-90 baseline (transitively via SP-87); every Git/image/chart/schema/policy/config/evidence digest is complete, immutable, compatible, and independently re-derived. | Yes -- PASS |
| AC-SP89-2 | Runtime membership is exactly Omniscience/Barbarossa/Portal; Omnius and every unselected adapter are absent, checked against the accepted ADR-0021 registry selection plus each owner's own committed no-effect evidence. | Yes -- PASS (static/documentary; not a live network/DNS/workload scan) |
| AC-SP89-3 | The selected tenant PW0 Reliability and source-bound Portal journeys pass end to end. | No -- requires a real environment |
| AC-SP89-4 | Every selected component/source can be severed without fabricated truth (stale/skew/outage/restart/rebuild). | Yes -- PASS (structural/typed fixture matrix joining each owner's already-published severance evidence) |
| AC-SP89-5 | The named non-production profile is observable, recoverable, and reversible. | No -- requires a real environment |
| AC-SP89-6 | The deployed Barbarossa workload is built only from the accepted SP-90 Go baseline (image/SBOM/process inventory). | No -- requires a real environment |

## What "independently re-derived" means here

- **SP-86**: this script re-hashes Omniscience's committed
  `evidence/release-lock.c733a0d445c090187461814263be7a07d20b7af3.json` bytes itself
  (`sha256:bdd2368427f7...`) rather than trusting any downstream copy.
- **SP-87 / SP-90**: neither has a single committed evidence file (only a runbook-
  published sample JSON block each); this script parses the fenced block, canonicalizes
  it, and hashes it itself for reproducibility tracking, and cross-checks the digests
  the block *declares* (`sp86_release_digest`, `sp90_baseline_digest`) against the
  independently-derived SP-86 digest and against every other place that same value is
  cited (Portal's `pins.py`). Placeholder runbook text (`sha256:<sha256 of ...>`) is
  detected and excluded from digest comparisons -- never treated as a real digest.
- **SP-88**: no single committed `PortalManagementReadOnlyRelease` evidence file exists
  at pin time (unlike SP-86's); this script hashes the real, committed source Portal
  published (`pins.py`, `schemas.py`, `release_lock.py`, its runbook) and cross-checks
  the literal pin values those files copy against the independently-derived SP-86/SP-87/
  SP-90 digests. It never executes Portal's own `build_portal_release_lock()`.

Re-running the script against unchanged sibling checkouts always reproduces
byte-identical digests; a changed source at either end fails the corresponding
cross-check closed (RED), never a silent match.

## AC-SP89-3 / AC-SP89-5 / AC-SP89-6: honest RED, not a runner failure

These three ACs each require one named non-production environment receipt --
environment identity, owner, allowed operations, observation window, and rollback
target -- that does not exist. This task's authority boundary forbids creating one
(no Terraform/OpenTofu/Terragrunt apply or destroy, no deployment, no secret, no DNS
change, no policy activation, no Omnius enablement; see the task spec's "Authority
boundary" and the profile's "Environment and activation boundary"). The runner detects
this and emits typed RED/decision-required evidence naming the exact missing input --
never a mock substitution, never a partial PASS. If a human later authorizes a named
environment and records its receipt at `environment-receipt.json` in this directory,
re-running the script surfaces these three ACs as `decision-required` instead of `RED`
(a human-authorized, separately scoped qualification pass against that named
environment is still required -- this script does not perform deployment or
observation actions on its own even when a receipt exists).

## Non-activation boundary

- No credential, cloud key, live consumer pin, provider/model call, deployment, or
  production-readiness claim.
- This directory does not change `Omniscience/**`, `Barbarossa/**`, or
  `platform-portal/**` -- every cross-repository read in `scripts/
  qualify_management_readonly_v1.py` is read-only.
- `status=GREEN` on the joined lock means every *buildable* AC passed; it is not a
  profile-activation or production-readiness claim.
