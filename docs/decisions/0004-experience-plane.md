# ADR-0004: The Experience plane — a verification-grounded, cross-repo memory of how we solved things

- **Status:** Accepted
- **Date:** 2026-07-06
- **Deciders:** platform owner
- **Scope:** cross-repo (multiqlti = proving ground, omnius = consumer, Omniscience = the adjacent state plane, genai-enablement = this contract)
- **Vocabulary:** terms as defined in [platform-glossary.md](../platform-glossary.md)

## Context

The estate now has four kinds of knowledge, and three of them already have a home:

- **State** — "what is true now" — lives in **Omniscience** (the bitemporal state graph). Per the
  Omniscience-excludes-experience decision (ADR-0015), Omniscience deliberately does **not** store
  *how we solved things* — only what is.
- **Capability** — "how we do X in general" — lives in **Skills** (SKILL.md artifacts), governed by
  [ADR-0002](0002-platform-skills-registry.md): one artifact, a trust envelope
  (`unverified → verified → deprecated`), success-delta graduation, CODEOWNERS-gated.
- **Repo facts** — "this repo uses uv" — are static per-repo profile data.
- **Experience** — "*how we solved X here, and whether it actually worked*" — had **no home and no
  mechanism**. This is the plane a factory needs to stop starting cold: the distilled, outcome-bearing
  memory of its own runs.

multiqlti has built and shipped that mechanism end-to-end (the "Dream", DREAM-1..4): a background
distiller writes Experience items from terminal loops; the planner reads the top-K at plan time; a
scheduled pass consolidates (dedup/decay/successDelta); and repeatedly-verified patterns propose
SKILL.md patches into the ADR-0002 envelope. It works as a proving ground, but the plane's **shape,
its grounding rule, and its boundaries** are cross-repo concerns — omnius will need the same plane at
org scale, and it must compose cleanly with Omniscience (state) and ADR-0002 (skills). This ADR
graduates the proving-ground design into a platform contract.

## Decision

Adopt the **Experience plane** as a distinct, fourth knowledge plane with the following contract.

1. **It is a separate plane, adjacent to Omniscience — not inside it.** Experience items reference
   Omniscience entity ids (`relatedComponents`) so "why did X happen" (state) and "how we solved X,
   verified" (experience) are one query apart but two stores. This preserves ADR-0015 (Omniscience =
   state only) while giving experience a home beside it.

2. **An item earns trust ONLY from independent verification — never self-report.** This is the
   load-bearing rule and the deliberate divergence from prior "the agent said it got better" memory
   systems. An item's `confidence` is:
   - `verified` ⇐ an independent check confirmed the underlying result — a test-run pass, a fresh
     single-verifier marking the criterion closed, or a merged/converged loop;
   - `refuted` ⇐ independent verification refuted it (a negative lesson, equally stored);
   - `observed` ⇐ neither (e.g. a judge opinion) — shown but weighted down.
   A pattern an agent *believes* worked but that verification refuted is `refuted`, not `verified`.
   This is the same ground truth that keeps the SDLC honest (ADR-0003) applied to memory.

3. **Item shape (the interchange contract).** An Experience item carries:
   `scope { repo, archetype, criterionClass, role?, concern? }`, a single distilled `claim`,
   `evidence[]` (loop/round/diff pointers — auditable), `verification { method, outcome,
   groundingRatioAtTime }`, `confidence`, `successDelta`, `provenance`, `freshness
   { lastConfirmedAt, decayPolicy }`, `relatedComponents[]` (into Omniscience state).

4. **Freshness and self-correction are mandatory (anti-Goodhart).** A `verified` item unconfirmed for
   N reuses / T time decays to `observed`; reuse re-grounds it (a later loop's independent
   verification refreshes `lastConfirmedAt` and updates `successDelta`, or demotes it). Contradictions
   on the same scope keep both items and let the fresher-verified lead — never a silent overwrite. The
   plane self-corrects from **outcomes**, not from age alone.

5. **The read discipline: every write has a read.** An Experience store without a reader is a dead
   `lessons` table. The canonical read point is the **planner**, at loop entry, alongside skill
   selection and repo facts — fenced and byte-bounded like any other injected context, biasing the
   plan without dictating it. Off ⇒ loops run cold, byte-identical.

6. **Boundaries — Experience ≠ State ≠ Skill ≠ Repo-fact.** The plane writes ONLY experience items. It
   links to Omniscience but never mutates the state graph (ADR-0015). It may **propose** a SKILL.md
   patch when a pattern is repeatedly `verified` (DREAM-4) — but the patch enters the ADR-0002 trust
   envelope as `unverified` and graduates only on measured success-delta, CODEOWNERS-gated; the
   Experience plane never edits a skill in place. Repo facts stay static profile data.

7. **Proving ground → canon.** multiqlti is the proving ground (DREAM-1..4 shipped, kill-switched,
   default-off). omnius consumes this contract for org-scale governed memory. The physical store may
   start multiqlti-local and graduate to a store beside Omniscience; this ADR fixes the **shape and
   rules**, not the deployment.

## Consequences

- **Positive:** the factory stops re-solving solved problems and starts warm; lessons are auditable
  (evidence + verification), self-correcting (freshness), and honest (verification-grounded). The
  four planes compose: State (Omniscience) + Capability (Skills, ADR-0002) + Experience (this ADR) +
  Repo-facts, assembled per run. Experience feeds Skills through a governed, human-gated path.
- **Costs / risks:** a second knowledge store to operate beside Omniscience; the grounding rule is
  only as good as the independent verification behind it (weak verification ⇒ weak `verified`); a
  stale-memory failure mode that §4's decay + reuse-re-grounding must actively counter.
- **Rejected alternatives:** *(a)* put Experience inside Omniscience — rejected, violates ADR-0015 and
  conflates state with outcomes; *(b)* self-reported confidence (roll back when it "got worse") —
  rejected as the Goodhart/reward-hacking failure mode; *(c)* fold Experience into Skills — rejected,
  a skill is generic capability, an experience item is a scoped outcome with freshness (§6 boundary).

## References

- multiqlti design notes: `docs/design/experience-plane-dream.md` (the Dream mechanism),
  `knowledge-planes.md` (the four planes), `standing-role.md` (role-scoped experience).
- [ADR-0002](0002-platform-skills-registry.md) (skills trust envelope — the graduation target),
  [ADR-0003](0003-unified-sdlc-standard.md) (quality-gated Done — the same ground truth),
  ADR-0015 (Omniscience excludes experience — the boundary this plane respects).
- Shipped proving-ground stages: DREAM-1 (distiller write), DREAM-2 (planner read), DREAM-3
  (consolidate), DREAM-4 (skill-feedback proposals) — all in `100rd/multiqlti`, kill-switched.
