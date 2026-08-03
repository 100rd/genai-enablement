# `barbarossa-ha-v1` integrated profile lock (task-sp-94-barbarossa-ha-profile-qualification)

**Status: RED. The profile is NOT qualified, NOT activated, and NOT production-ready.**
`activation_authority: none`.

This directory holds an independent, read-only qualification join over the SP-89 base-profile
lock, the SP-92 Barbarossa HA owner release and the SP-93 Portal HA experience, plus the SP-90
Go baseline and SP-91 distributed-work substrate transitively bound by SP-92. It does not repair
a component, mint a sibling receipt, edit the ADR-0023 selection, deploy anything, or replace
missing environment evidence with a mock. See
[ADR-0023](../../../decisions/0023-barbarossa-full-go-distributed-ha-runtime.md) and
[the profile definition](../../profiles/barbarossa-ha-v1.md).

```text
docs/synchronized-platform/releases/barbarossa-ha-v1/
  README.md                  this file
  evidence/                  qualify_barbarossa_ha_v1.py default-run output
                              (content-addressed by this repository's HEAD commit;
                              never overwritten, only appended to)
  environment-receipt.json   NOT present. If a human later authorizes a named
                              non-production HA environment for SP-94, its receipt
                              belongs here -- see "Five criteria are environment-gated"
                              below for the exact required fields.
```

## Regenerating the profile lock

```bash
python3 scripts/qualify_barbarossa_ha_v1.py --report   # stdout only, no write
python3 scripts/qualify_barbarossa_ha_v1.py --write    # write evidence only
python3 scripts/qualify_barbarossa_ha_v1.py            # both (the verify command)
```

The exit code reports the **buildable** checks only: `0` when every check that can be performed
from committed artifacts passed, `1` otherwise. **Exit 0 is not qualification.** The overall
`status` in the emitted lock is `RED`, and stays RED for the reasons below.

## Result

| AC | What it requires | Buildable checks | Status | Why |
|---|---|---|---|---|
| AC-SP94-1 | One content-addressed lock joins the exact SP-89/SP-92/SP-93 and transitive SP-90/SP-91 digests, immutable, compatible and independently re-derived | **GREEN** (17/17) | **RED** | no committed SP-92 receipt exists at all; SP-91 has none either; SP-90's binary/image/SBOM are null; SP-93's own release lock is RED |
| AC-SP94-2 | Commit / ACK / crash matrix preserves one authoritative history | GREEN (gating declaration + negative control) | **RED** | environment-gated |
| AC-SP94-3 | Fencing, ordering, retries and quarantine under concurrency and partitions | GREEN (gating declaration + negative control) | **RED** | environment-gated |
| AC-SP94-4 | Service and work SLOs survive replica / broker / store / failure-domain faults | GREEN (gating declaration + negative control) | **RED** | environment-gated |
| AC-SP94-5 | Capacity, autoscaling, drain, rollout and rollback under burst and soak load | GREEN (gating declaration + negative control) | **RED** | environment-gated |
| AC-SP94-6 | Portal displays exact owner HA truth and stays severable and read-only | **GREEN** (20/20) | **RED** | no independent API/browser/cache/audit capture against a running pair; no live tampered-fixture run; SP-93 accessibility evidence absent |
| AC-SP94-7 | Tenant PW0 membership and no-effect boundaries survive every load and failure path | **GREEN** (13/13) | **RED** | no live two-scope corpus under load; no live workload/DNS/route/secret/network/broker/store/log/trace/audit/UI inventory |
| AC-SP94-8 | Qualification is observable, reproducible, reversible and non-authorizing | GREEN (gating declaration + negative control) | **RED** | environment-gated: no external alert observer, no evidence-manifest signing authority, no executed rollback |

`buildable_result: GREEN` on a criterion means only that the checks that *can* be performed from
committed artifacts passed. It is never profile activation, HA qualification or production
readiness. No criterion is reported as a partial PASS.

## What "independently re-derived" means here

Nothing below trusts a downstream copy, and nothing executes owner code.

- **SP-89**: this repository's own committed
  `management-readonly-v1/evidence/profile-lock.ac32c722….json` is re-hashed here, its
  `profile_lock_digest` is **re-derived from its own body** (strip the digest field,
  canonicalize, hash) and compared with the value it records, and it is asserted to be
  git-tracked. A locally re-run, uncommitted sibling evidence file is reported separately and is
  never mistaken for the pin.
- **SP-92**: the *only* stable, re-derivable owner identity is `projection.SchemaDigest()`. This
  script parses Barbarossa's own `internal/runtime/projection/schema.go` field list, re-derives
  the digest under the owner's documented canonicalization (`sha256(canonical-JSON(fields))`,
  `internal/shared/integrity.go`), and independently re-checks the owner's own lockstep
  invariant by parsing the `AvailabilityProjection` struct tags out of `projection.go`. Because
  Go's `encoding/json` HTML-escapes `<`, `>` and `&` and Python's does not, the derivation
  **fails closed** for any field name outside the owner's `[a-z][a-z0-9_]*` vocabulary rather
  than emitting a digest that might silently disagree. Every other SP-92 quantity (rendered
  topology, capacity envelope, SLO, metric schema, alert/runbook, image, SBOM, binary, chart) is
  *not* re-derived: only the owner's own release run can mint those. What this join computes
  instead is a clearly labelled `ha_artifact_content_digest` over the owner's committed HA
  artifact bytes, which exists to give the join a reproducible identity and to fail closed if
  that source drifts.
- **SP-90 / SP-91**: neither has a committed receipt file. SP-90's runbook block is parsed,
  canonicalized and hashed here, and compared with the block digest SP-89 recorded; the separate
  owner value `runtime.Sp90BaselineDigest()` that SP-87 declares is compared with Portal's SP-88
  `SP90_BASELINE_DIGEST` literal. Those two are different quantities and are never compared with
  each other. SP-91's verdict table is parsed from its runbook; it records AC-SP91-7 (*one
  immutable substrate receipt*) RED.
- **SP-93**: the real committed Portal source and shipped runtime-profile artifacts are hashed
  here. Portal's literal pins are read with `ast` (parsed, never executed), and its release
  lock's RED reasons are re-derived from those pins rather than taken from its own output.
  Portal's claims are then checked against **Barbarossa's actual committed contract**, not
  against Portal's summary of it: the schema digest, the field list, the wire types (an owner
  `int` must not become a Portal boolean), the owner-published route set, and the local
  topology's `availability_class` / `ha_qualified` / `not_qualified_axes`.
- **Placeholder text** (`sha256:<sha256 of …>`) is detected and never treated as, or compared
  with, a real digest. Values the owner records as uncomputed stay `null`.

Re-running against unchanged sibling checkouts reproduces byte-identical digests; a changed
source at either end fails the corresponding cross-check closed (RED), never a silent match.

## Why AC-SP94-1 cannot be a PASS

**There is no committed SP-92 release receipt anywhere in Barbarossa.**
`HighAvailabilityRelease` (`internal/runtime/api/release.go`) is computed only by a release run
supplying externally measured binary/image/SBOM/chart facts, is registered on no HTTP route, and
is committed nowhere. This script *scans* the whole Barbarossa checkout for one rather than
asserting its absence — and the scan fails loudly if it reads zero files, so "found nothing" can
never mean "looked at nothing".

Even if a receipt existed, Barbarossa's own committed expected verdicts
(`testdata/conformance/ha-runtime-v1/expected/ac-verdicts.json`) record `overall_status: RED`
with AC-SP92-1..5 RED. A downstream join cannot upgrade an owner's honest RED. The same holds
one layer down: SP-91 records AC-SP91-7 RED, SP-90's binary/image/SBOM digests are null by
design, and SP-93's own release lock is RED for `sp92_release_receipt_absent`,
`sp92_conformance_overall_status_red`, `accessibility_evidence_absent` and
`sp88_portal_baseline_red`.

**What would change this:** the Barbarossa owner runs its own release pipeline with the
externally measured binary/image/SBOM/chart facts, commits the resulting
`BarbarossaHighAvailabilityRelease` receipt, and a live HA qualification environment closes
AC-SP92-1..5 so that receipt is no longer RED. SP-91 must likewise publish its substrate
receipt, and SP-93 must commit its accessibility evidence.

## Five criteria are environment-gated RED

AC-SP94-2, -3, -4, -5 and -8 each require one **named non-production HA environment receipt**
that does not exist, at `environment-receipt.json` in this directory, carrying all of:

```text
environment_identity, environment_owner, failure_domains, allowed_faults,
load_generation_authority, alert_observer, observation_window, rollback_target,
prior_release_digest
```

They additionally require authority this task does not hold: an external fault controller, an
external load generator, an independent alert observer, an evidence-manifest signing authority
and a rollback target. The task spec's *Authority boundary* forbids creating any of them (no
Terraform/OpenTofu/Terragrunt apply or destroy, no deployment, no secrets, no DNS, no redrive,
no domain/effect activation, no production-readiness claim). The runner therefore emits typed
RED evidence naming, per criterion, the exact required inputs and the exact forbidden
substitutes — never a mock, never a partial PASS.

That declaration lives in `tests/fixtures/barbarossa-ha-v1/environment-gating.json` and is
itself validated: an empty matrix, a criterion with no required inputs or no forbidden
substitutes, a criterion set that differs from the environment-gated set, an invented
disqualifying axis, or a disqualifying axis left unmapped all make the matrix invalid and the
criteria RED.

**What would change this:** a human authorizes a named non-production HA environment with at
least three failure domains running the SP-92 rendered topology, records its receipt here, and a
separately scoped qualification pass produces the broker delivery and owner-store transaction
traces (AC-SP94-2), the lease-partition and poison timelines with fencing/store rows
(AC-SP94-3), the fault-controller timeline plus external SLO observations and quorum state
(AC-SP94-4), the immutable load model with autoscaler, scheduler and post-rollback conformance
captures (AC-SP94-5), and the independent alert-observer receipt, manifest signature and
post-rollback inventory (AC-SP94-8). With a receipt present but no such pass performed, this
runner reports those criteria as `decision-required` instead of `RED` — still never PASS.

## The local Docker stack is a NEGATIVE control, never HA evidence

The only Barbarossa runtime that can be started here is the `management-readonly-local-v1`
single-host Compose fragment. Its **own committed topology**
(`Barbarossa/deploy/config/management-readonly-local/topology.json`) declares:

```text
availability_class = "development-single-host"
queue_replicas = 1, store_replicas = 1
ha_qualified = false, activation_authority = "none"
not_qualified_axes = [failure_domain_quorum, queue_replication,
                      store_replication, autoscaling, failover]
```

This qualifier asserts that declaration explicitly and uses it **only** as proof that AC-SP94-2,
-3, -4 and -5 cannot be qualified in this environment — each of those criteria names the exact
axes that disqualify it and lists the local stack among its forbidden substitutes. If that
topology ever stopped declaring `ha_qualified: false`, the negative control would be reported as
broken rather than quietly accepted as HA evidence (`tests/test_barbarossa_ha_v1.py`,
`NegativeControlTests::test_fails_closed_if_the_local_stack_ever_claims_to_be_ha_qualified`).

## Non-activation boundary

- No credential, cloud key, live consumer pin, provider/model call, deployment, fault injection,
  load generation, redrive, domain/effect activation or production-readiness claim.
- This directory does not change `Barbarossa/**` or `platform-portal/**` — every
  cross-repository read in `scripts/qualify_barbarossa_ha_v1.py` is read-only, and no owner code
  is ever executed.
- The emitted evidence manifest is **unsigned** (`signature: null`) with the reason recorded. An
  unsigned manifest is never presented as a signed attestation.
- The qualifier never raises: a missing, dirty, absent or unverifiable input becomes a typed
  reason inside the returned object, so a broken input can never masquerade as a passing check.
- `status: RED` and `activation_authority: none` are the honest result of this pass. A later
  human deployment decision must bind an immutable *qualified* SP-94 receipt to an exact
  environment and mutation plan; this one is not that.
