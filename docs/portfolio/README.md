# Platform portfolio

This directory is the human-readable portfolio view. The machine-readable source for project status,
owners, releases, initiatives, blockers, and canonical links is
[`portfolio/projects.json`](../../portfolio/projects.json). Component details are linked, not copied.

## Ownership model

| Authority | Owns | Does not own |
|---|---|---|
| `genai-enablement` | Portfolio status and roadmap, canonical glossary, cross-repository ADRs, dependencies, readiness blockers, and canonical links | Component capability/task contracts, API schemas, runbooks, or implementation evidence |
| Component repository | Capability SPECs, task SPECs, MCP/REST schemas, component ADRs, runbooks, implementation documentation, and terminal execution evidence | Cross-repository decisions or a second portfolio roadmap |
| GitHub Issues | Mutable intake, triage, discussion, and progress tracking | An executable or immutable work contract |

An issue can start discovery. Mutating execution requires the component's human-ready immutable task
SPEC under [ADR-0009](../decisions/0009-organizational-dark-factory-sdd.md) and
[ADR-0012](../decisions/0012-capability-readiness-profiles.md). Terminal state is supported by the
component execution index, not inferred from an issue checkbox or a portfolio label.

## Human-owned decision backlog

`portfolio/projects.json` also carries the exhaustive machine-readable set of ADRs whose source status
is `Proposed`. The offline drift gate rejoins every item to its local ADR file and rejects a missing,
extra, accepted-by-registry-only, path-mismatched, or dependency-misordered entry. Listing a decision here
does not accept it, authorize its follow-ups, or change a component/release/readiness state. The next gate
for every item is an explicit platform-owner disposition.

| Decision | Review group | Requires | Blocks | Next gate |
|---|---|---|---|---|
| [ADR-0002](../decisions/0002-platform-skills-registry.md) | `registry-trust` | — | `skill-registry-adoption` | `human-disposition` |
| [ADR-0003](../decisions/0003-unified-sdlc-standard.md) | `cross-factory-sdlc` | — | `cross-factory-sdlc-adoption` | `human-disposition` |
| [ADR-0006](../decisions/0006-unified-loop-decision-model.md) | `cross-factory-sdlc` | `ADR-0003` | `cross-factory-loop-adoption` | `human-disposition` |
| [ADR-0007](../decisions/0007-platform-portal-federated-surface.md) | `portal-experience` | — | `platform-portal-spec-adoption` | `human-disposition` |
| [ADR-0008](../decisions/0008-ai-security-domain.md) | `ai-security` | — | `ai-security-s0-s1-spec-authorship` | `human-disposition` |
| [ADR-0014](../decisions/0014-precommitted-http-condition-evidence.md) | `delivery-evidence` | — | `http-evidence-adoption` | `human-disposition` |
| [ADR-0015](../decisions/0015-independent-observer-authority-attestor.md) | `delivery-evidence` | — | `observer-attestation-adoption` | `human-disposition` |
| [ADR-0016](../decisions/0016-independent-safe-to-reclaim-decision-issuer.md) | `delivery-evidence` | `ADR-0006`, `ADR-0015` | `safe-to-reclaim-adoption` | `human-disposition` |
| [ADR-0018](../decisions/0018-pii-wall-purpose-bound-data-boundary.md) | `privacy-boundary` | `ADR-0003`, `ADR-0007`, `ADR-0008` | `pii-wall-component-adoption` | `human-disposition` |
| [ADR-0020](../decisions/0020-barbarossa-continuous-management-plane.md) | `continuous-management-plane` | — | `barbarossa-continuous-management-adoption` | `human-disposition` |

## Portfolio views

- [Omniscience](omniscience.md) — current release, MCP v1 initiative, blockers, and authoritative links.
- [Omnius](omnius.md) — bounded readiness draft, local conformance evidence, activation blockers, and
  authoritative component links.
- Other component pages are added when a cross-repository initiative needs a maintained portfolio
  view; their baseline entries remain in the registry.

## Updating the portfolio

1. Update `portfolio/projects.json` from component-owned immutable evidence.
2. Update the corresponding page without copying component contracts.
3. Run `python3 scripts/check_portfolio_drift.py` and
   `python3 -m unittest discover -s tests -p 'test_portfolio_drift.py'`.

For a stronger local join when the Omnius sibling checkout is present, also run
`python3 scripts/check_portfolio_drift.py --omnius-root ../omnius`. The explicit option is read-only and
checks the registry snapshot against the component-owned v3 profile and Git state; CI remains independent
of sibling repositories.

The drift check is deliberately offline. It validates only committed local facts and links and never
queries the GitHub API. Release or issue changes therefore enter through an explicit reviewed registry
change rather than making CI depend on mutable network state.
