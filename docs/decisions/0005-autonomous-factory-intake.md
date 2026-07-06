# ADR-0005: The autonomous factory — committed spec as the unit of work, tracker intake, standing roles

- **Status:** Proposed
- **Date:** 2026-07-06
- **Deciders:** platform owner
- **Scope:** cross-repo (multiqlti = proving ground, omnius = governed consumer, genai-enablement = this contract)
- **Vocabulary:** terms as defined in [platform-glossary.md](../platform-glossary.md)

## Context

multiqlti has built and proven, end-to-end, an autonomous engineering factory: a task enters, a
consilium loop reviews → plans → develops → verifies → opens a PR, and a human merges. This ADR
graduates the **intake and execution shape** of that factory into a cross-repo contract, so omnius
can adopt the same model at governed org scale. It is the companion to
[ADR-0004](0004-experience-plane.md) (the Experience plane — the factory's memory) and builds on
[ADR-0002](0002-platform-skills-registry.md) (skills) and
[ADR-0003](0003-unified-sdlc-standard.md) (quality-gated Done).

The proving-ground design is captured in multiqlti's design notes (`docs/design/`: `spec-as-task.md`,
`task-tracker-triggers.md`, `standing-role.md`, `loop-consolidation.md`) and shipped as SPEC-1..4,
TRACK-1..6, ROLE-1..4. This ADR fixes the **contract**, not the implementation.

## Decision

Adopt the following factory contract.

1. **The unit of work is a committed spec, not a chat message or a raw ticket.** A committed spec
   (`docs/specs/<slug>.md`) or ADR (`docs/adr/`) — YAML frontmatter (`title, status
   draft|ready|in-progress|done, source, repo, role?, skills?, acceptanceCriteria`) + body — is the
   durable, version-controlled, reviewable intent. `acceptanceCriteria` **are** the loop's
   verification criteria (ADR-0003 Done made per-task). Only a `ready` spec executes.

2. **One execution route: a committed spec fires a loop.** A default per-repo watch on
   `docs/specs`/`docs/adr` fires a consilium loop when a `ready` spec/ADR lands. Humans and every
   intake source produce specs into the same place — there is exactly one path from intent to work.

3. **Two human gates, cleanly separated.** A human approves the **spec** (the *what*, via the spec
   PR / a ready-transition) and later merges the **code PR** (the *ship*). The factory automates only
   the work between them. This is L4, never L5 — the same discipline as ADR-0010 (auto-merge opt-in).

4. **Trackers are spec producers, not loop launchers.** A ticket in any tracker
   (GitHub / GitLab / Bitbucket / Jira / Linear / Azure DevOps / ClickUp) is normalised or
   synthesised into a **committed spec** (with `source: {kind, ref, url}` provenance) and the ticket
   receives mandatory **write-back** at every transition (picked-up → PR → terminal → close). All
   trackers reduce to one uniform connector interface (watch / read / write-back) over one watch
   spine + one spec-writer; adding a tracker is one adapter. The tracker is the inbox; the committed
   spec is the crystallised task; the loop is the work.

5. **A Standing Role is a persistent named identity that spawns ephemeral loops.** A Role bundles a
   persona + skills (ADR-0002 SKILL.md set) + a loop template + concerns (what it watches, via
   triggers/trackers) + role-scoped experience (ADR-0004). Its triggers wake it; each wake spawns an
   ephemeral loop; it accumulates experience keyed by `(role, concern)` so it starts warm. A Role is
   a *definition*, not a running privileged process — its only runtime footprint is the ephemeral,
   isolated, human-merge-gated loops it spawns. Creating/enabling a Role and merging its loops' PRs
   are human/CODEOWNERS acts.

6. **Everything is verification-grounded and default-off.** A loop verifies against the spec's
   `acceptanceCriteria` (ADR-0003); experience earns `verified` only from independent verification
   (ADR-0004); every new capability ships behind a kill-switch, byte-identical when off. Untrusted
   inputs (ticket/spec text) are fenced before any prompt.

## Consequences

- **Positive:** intent is crystallised and reviewed before expensive execution; the task queue is
  the repo history (auditable, permanent); intake is pluggable (7 trackers, humans, ADRs) over one
  execution route; roles turn the factory into named digital employees; the whole thing composes
  with Skills (ADR-0002), Done (ADR-0003), and Experience (ADR-0004).
- **Costs / risks:** the spec-first gate adds a step (a spec PR) between ticket and work — deliberate,
  it is the intent-review gate; the connector surface (7 trackers) is maintenance; the human-merge
  gate is a throughput ceiling by design (L4).
- **Rejected alternatives:** *(a)* fire a loop directly from a ticket — rejected, loses the durable
  reviewable intent and the uniform loop input; *(b)* a chat message as the unit of work — rejected,
  ephemeral and unauditable; *(c)* auto-merge the code PR — rejected, that is L5 (ADR-0010 keeps
  auto-merge opt-in/default-off).

## References

- multiqlti design notes: `spec-as-task.md`, `task-tracker-triggers.md`, `standing-role.md`,
  `loop-consolidation.md`. Shipped: SPEC-1..4, TRACK-1..6, ROLE-1..4 (all in `100rd/multiqlti`,
  kill-switched).
- [ADR-0002](0002-platform-skills-registry.md) (skills), [ADR-0003](0003-unified-sdlc-standard.md)
  (quality-gated Done), [ADR-0004](0004-experience-plane.md) (the factory's memory), and omnius
  ADR-0010 (auto-merge opt-in) which this L4 posture matches. omnius is the governed consumer of
  this contract (see the omnius adoption ADR).
