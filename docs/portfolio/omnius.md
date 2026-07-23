# Omnius portfolio view

**As of:** 2026-07-21
**Portfolio status:** `control-plane-implementation`

This is the program view of the current Omnius readiness slice. Capability/task contracts, readiness
profiles, probes, runbooks, and execution evidence remain authoritative in the Omnius repository. Local
worktree results below are construction evidence only: they are neither an immutable component release nor
activation evidence.

## Snapshot

| Field | Portfolio fact |
|---|---|
| Role | Governed organizational Dark Factory |
| Component owner | `@100rd` |
| Portfolio owner | `@100rd` |
| Current release | none |
| Roadmap status | `control-plane-implementation` |
| Inspected component HEAD | `a32fecd35588a10bd5453af4244c6fc219c7527f` |
| Worktree publication status | `dirty-unpublished` |
| Readiness profile | `p0-standard-http-service-v3` |
| Profile state | `draft` (non-authorizing) |
| Assurance profile | `P0` |
| PlatformPath | `standard-http-service/v3` |
| Source profile | `specs/readiness/p0-standard-http-service-v3.json` |
| Source profile digest | `sha256:30d81c62c67d96ee7ef46d3db2f78e97255cdfe595440412ea12910469060ede` |
| Selected slice | `15` capabilities, `129` requirements, `126` probes |
| Component readiness blockers | `11` |
| Preserved forbidden actions | `14` |

## Current local verification

| Decision surface | Evidence-backed local result |
|---|---|
| Evidence scope | `dirty-worktree-local` |
| Acceptance contract | `1025` passed, `2` environment-qualified skips |
| Portable conformance probes | `290` passed |
| Human waivers | `3` |
| Target-profile failures | `3` |
| Contract conformance | `conformant` |
| Assurance certification | `red` |
| Activation | `blocked` |

Contract conformance permits continued construction and review. It does not override target assurance:
the human waivers, missing target controls, dirty worktree, and draft profile keep profile activation,
production promotion, autonomy widening, and auto-merge blocked.

## Active initiatives

| Initiative | State | Next gate |
|---|---|---|
| SPEC-driven repository adoption | `implementation-evidence-uncommitted` | Human ADR/readiness review after immutable component evidence exists |
| First governed P0 vertical | `draft-non-authorizing` | Immutable external evidence plus exact human activation |

## Readiness blockers

- The implementation and current conformance evidence exist only in a dirty, unpublished worktree.
- The component-owned `p0-standard-http-service-v3` profile records eleven exact readiness blockers; this
  portfolio page summarizes their state and does not replace that list.
- Three explicit human waivers and three target-only failures keep assurance certification RED.
- Production authority identities, immutable capability/path/readiness publications, Realm admission,
  protected-path and real-path evidence, Docker P0 adapter qualification, and exact human activation are
  absent.

The next admissible technical milestone is a clean immutable component revision whose independently
observed manifests contain the selected requirement/probe ownership. The subsequent production and human
gates remain separate; an immutable revision alone cannot activate the profile.

When the Omnius sibling checkout is available, run
`python3 scripts/check_portfolio_drift.py --omnius-root ../omnius`. This optional read-only observation
verifies the source profile digest and closed counts, Git HEAD, and dirty/clean publication state. The
default command remains self-contained for CI and never silently depends on a sibling checkout.

## Canonical component links

- [Capability SPEC index](https://github.com/100rd/omnius/blob/main/specs/SPEC-INDEX.md)
- [Task SPEC and execution index](https://github.com/100rd/omnius/blob/main/docs/specs/README.md)
- [Readiness profile contract](https://github.com/100rd/omnius/blob/main/specs/readiness/README.md)
- [Component ADR index](https://github.com/100rd/omnius/blob/main/docs/adr/README.md)
- [Conformance developer contract](https://github.com/100rd/omnius/blob/main/conformance/README.md)
- [Runbooks](https://github.com/100rd/omnius/tree/main/docs/runbooks)
