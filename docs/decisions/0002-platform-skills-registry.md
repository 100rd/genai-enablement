# ADR-0002: Platform skills registry — SKILL.md canon, git-backed distribution, per-runtime trust

- **Status:** Proposed — human disposition required; non-authorizing
- **Date:** 2026-07-02
- **Last reviewed:** 2026-07-16
- **Deciders:** platform owner
- **Scope:** cross-repo (multiqlti, omnius, Omniscience, platform-design/PB-SRE, genai-enablement, engineer workstations)
- **Governed by:** accepted [ADR-0009](0009-organizational-dark-factory-sdd.md),
  [ADR-0010](0010-goal-oriented-organizational-dark-factory.md), and
  [ADR-0012](0012-capability-readiness-profiles.md)
- **Vocabulary:** terms as defined in [platform-glossary.md](../platform-glossary.md) (PR #9)

## Context

The platform goal is that a skill — e.g. "how we develop in Go" — is **the same
content-addressed artifact** whether it is used by an engineer, by a multiqlti pipeline
stage, or by an omnius Worker. Consumers may materialize that artifact differently, but
the source bytes, transformation/profile revision, and artifact identity must remain
replayable. The estate still has distinct content, binding, and trust surfaces:

1. **genai-enablement registry (committed bootstrap):** `skills/` contains 24 `SKILL.md`
   files and provenance material. The v1 `skills-lock.json` hashes each `SKILL.md`, and all
   24 hashes matched on 2026-07-16. It does not bind an exact Git commit, a full directory
   tree, an Agent Skills/profile revision, an independent verifier, or a signature. No
   committed registry CODEOWNERS or registry CI gate exists. It is inventory and local
   drift evidence, not a production release.
2. **multiqlti (committed proving-ground consumer):** commit `21bbabb` added a bounded
   `SKILL.md` parser and local registry sync. It confines paths, checks the v1 raw
   `SKILL.md`-file hash,
   filters `compatible_tools`, and materializes a `sourceType: git` database row without
   overwriting manual or foreign-team rows. It does not authenticate a registry release,
   bind an exact Git revision or full directory tree, import organizational trust, or
   grant organizational execution authority.
3. **omnius (dirty/local candidate plus legacy seam):** draft `SPEC-REG` and
   `mvp_core/registry/contracts.py` define a fail-closed signed-lock/readiness candidate and
   explicitly reject the live v1 lock. These files are unpublished worktree evidence, not
   an accepted capability or immutable release. The older `phase_3/skill_lifecycle.py`
   still uses a mutable local store and hard-coded replay thresholds; it is not the
   organizational adoption authority and cannot prove conformance.
4. **Agent Skills upstream:** the current official format requires `name` and
   `description` and defines optional `license`, `compatibility`, `metadata`, and
   experimental `allowed-tools`. The registry's top-level `version`, `tags`,
   `compatible_tools`, and `tier` fields are a local consumer profile, not fields whose
   upstream meaning may be assumed. The exact upstream specification and local profile
   must therefore be pinned rather than resolved from a mutable web page or client
   convention.

Additionally, PB-SRE runbooks are skill-shaped markdown with step-level autonomy tags
(`auto_executable_steps` / `approval_required_steps`), and both factories want agents to
**improve skills from their own experience** (multiqlti "lessons" memory layer; omnius
`accumulated-lesson` skill type).

Two hard requirements emerged from design discussion:

- **R1 — one content artifact, many runtimes.** The Go skill must be one exact
  content-addressed tree with one change history, materializable by engineer clients,
  multiqlti pipelines, and omnius task classes without changing its identity.
- **R2 — agents may modify skills, and runtimes may trust proven skills** — without
  reward-hacking or silent corruption of a working asset.

## Acceptance boundary and precedence

This ADR is a cross-repository compatibility **proposal**. It does not publish a registry
release, make the current v1 lock admissible, accept an Omnius capability SPEC, mark a
CapabilityReadinessProfile ready, grant a consumer filesystem or tool capability, or
authorize production use. Only the human platform owner may accept, revise, or reject it.

Accepted ADR-0009/0010/0012 take precedence. In particular:

- an accepted ADR and ready exact component SPEC/profile are required before an
  organizational consumer may activate this boundary;
- a skill is instruction content, never a capability, policy, verifier, Condition of Done,
  or approval receipt;
- artifact conformance, local trust, task admission, result verification, landing, and
  assurance are separate decisions; and
- no fixture, local hash match, dirty worktree module, self-reported success rate, or
  agent-authored approval can cross a human or production gate.

Human acceptance must disposition the exact upstream format/profile pin, registry owner and
protected paths, signed release schema, signature algorithm and key owner, independent
verifier identities, executable-file policy, consumer modes, and revocation owner. Until
then, every organizational consumer fails closed and multiqlti remains a personal
proving-ground consumer only.

## Decision

### D1. Canonical content uses an exact Agent Skills core plus a pinned platform profile

A skill is a directory containing `SKILL.md` (YAML frontmatter + Markdown body), optionally
with `references/`, `scripts/`, `assets/`, examples, license, and provenance files. The
accepted release must pin an exact upstream Agent Skills specification revision or blob
digest and an exact platform profile revision. A mutable URL or "whatever this client
accepts" is not a format pin.

The upstream core is represented as:

```yaml
---
name: golang-dev
description: Go development conventions. Use when implementing or reviewing Go code.
license: MIT
compatibility: Requires a Go toolchain.
metadata:
  platform-profile: platform-skill/v1
---
```

The platform profile must define how the current `version`, `tags`, `compatible_tools`, and
`tier` data migrate into upstream fields, namespaced string metadata, or a companion
content-addressed manifest. Until that profile is accepted and validated, the current
top-level extensions remain bootstrap input for existing consumers and are not evidence of
upstream conformance. `allowed-tools`, `compatible_tools`, and `tier` are descriptive
compatibility inputs only: the WorkOrder/Realm policy and capability gateway independently
authorize every action.

The entire allowed directory is the content artifact. Trust state, success statistics,
admission decisions, approvals, and verifier results never live in `SKILL.md` or its
frontmatter. Executable `scripts/` are disabled for the first governed vertical; their mere
presence never grants execution permission.

### D2. Distribution uses a clean Git release and a signed full-tree lock envelope

A single git-backed registry is the source of truth. **Initial home: the `skills/`
directory of this repo (genai-enablement).** Extraction into a dedicated `platform-skills`
repository happens later, when consumer count or access-control needs justify it — the
layout below is designed to survive that move unchanged (consumers reference the directory
subtree, not the repo root):

```
skills/
├── engineering/golang-dev/SKILL.md
├── engineering/terraform/SKILL.md        # seeded from vendored .claude/skills
├── sre/gpu-node-unhealthy/SKILL.md       # converted PB-SRE runbook, tier-tagged steps
├── REGISTRY.md                           # provenance index (VENDORED.md pattern)
└── skills-lock.json                      # current unsigned SKILL.md-only bootstrap inventory
```

- **Protected publication:** registry content, profile/schema, lock, CODEOWNERS, release
  workflow, trust policy, and verification criteria are protected paths. Worker, evaluator,
  and proposal-bot identities have no direct-push, approval, release, key, or policy-write
  credential. Changes arrive as inert proposals and require the configured human landing
  path.
- **Tracking mode** (multiqlti personal/proving-ground instances and explicitly local
  workstations): may follow a reviewed branch or local checkout, but the resolved bytes are
  untrusted local materialization. Tracking mode cannot authorize an organizational task,
  feed a pinned WorkOrder, publish runtime trust, or silently graduate into pinned mode.
- **Pinned mode** (omnius and anything organizational or production-adjacent): consumes only
  an independently verified signed release envelope from one clean exact Git commit. Mutable
  branches, tags without a resolved commit, semver ranges, `latest`, and working-tree bytes
  are prohibited.

The current v1 `skills-lock.json` is a bootstrap inventory containing only
`computedHash` values for `SKILL.md`. It is useful for local body-drift detection, but it is
not a production trust root and it does not cover references, scripts, assets, licenses, or
provenance. Pinned consumers must reject it.

The future release envelope must bind, under one canonical signed payload:

1. closed schema version, exact upstream Agent Skills pin, exact platform-profile pin, digest
   algorithms, registry origin, clean Git commit, release revision, and manifest digest;
2. a duplicate-free sorted skill set with exact skill id, registry-relative directory,
   complete allowed-file manifest, per-file digest, full-tree digest, license/provenance
   references, and executable-file disposition;
3. signature algorithm, human-owned key id, signing identity, issuance/expiry or explicit
   non-expiry policy, verifier reference, and revocation reference; and
4. canonicalization, size/count/depth bounds, collision behavior, path/symlink rules, and
   fail-closed handling for unknown fields, duplicate JSON/YAML keys, non-finite data,
   missing bytes, and unavailable verification.

The verifier is preconfigured and independent from the producer and consumer. It returns
exact boolean success over a snapshotted envelope and exact clean Git materialization; the
gate revalidates both after the callback and issues an opaque integrity-bound readiness
capability. Every resolution rejoins that capability to the exact release, origin, verifier,
skill id, path, commit, and tree digest. A raw signed model, caller-fabricated decision,
truthy non-boolean, copied-invalid object, callback mutation, or post-issuance mutation has
no authority. Omnius's HMAC signer is only a deterministic test double and selects neither
the production algorithm nor key owner.

### D3. Release validity, local trust, capability, and evidence are independent

- **Content** (complete skill tree) — portable, content-addressed, and released by the
  registry.
- **Release validity** — proves exact origin, revision, bytes, and publication authority; it
  does not prove the instructions are safe or effective.
- **Trust status** (`unverified/verified/deprecated`, `validated_on_model`,
  `validated_env`, success counters) — **per-runtime, non-transferable.** A skill verified
  in multiqlti is *not* thereby verified in omnius. Trust binds the exact tree digest,
  local model/tool/environment/profile revisions, human-owned criteria, and independent
  oracle. A new tree identity starts `unverified`; it does not mutate or silently demote a
  different revision already pinned to active work.
- **Capability and authorization** — remain in the WorkOrder, Realm, task policy, and tool
  gateway. A skill name, tier, body instruction, frontmatter field, registry signature, or
  verified status cannot grant a tool, credential, scope, network route, landing right, or
  autonomy tier.
- **Evidence dossier** — may travel only as signal. It binds the exact artifact/release,
  task and criteria revision, producer and independently administered oracle, model/tool and
  environment revisions, run population and exclusions, outcome/return evidence, timestamps,
  signature, and source-health/coverage state. Missing, stale, producer-only, ambiguous, or
  `inconclusive` evidence cannot set local trust or become a silent zero.

This preserves the graduation path: multiqlti may produce attributed proving-ground
evidence; Omnius independently admits or rejects the exact artifact under its own accepted
SPEC/profile. Neither a success counter nor model consensus is an admission oracle.

### D4. Agent modification is proposal-only and cannot redefine correctness

```
agent works → distills a bounded lesson → emits an inert patch + dossier
  → proposal branch/PR (no protected-path, policy, key, or approval credential)
  → CI: exact core/profile validation · closed tree/lock reproduction
       · secret/content/license/provenance scan · independent eval where defined
  → human/CODEOWNER disposition and signed clean-revision publication
  → each runtime resolves its permitted mode and independently admits the new tree identity
```

- **C1 — modification creates a new identity.** Any body, reference, script, asset,
  license, or provenance change produces a new full-tree digest. The new identity enters
  each runtime as `unverified`; existing tasks remain pinned to the old identity unless an
  exact human/security revocation policy halts or parks them.
- **C2 — agents never edit their own success criteria.** The machine may refine a skill
  body only through the proposal path. A verification procedure, oracle, threshold,
  protected path, release policy, trust transition, or definition of success is a separate
  human-owned revision and cannot land in the same authority transaction by implication.
- **C3 — no current auto-landing.** The first governed vertical requires human landing and
  has auto-merge off under ADR-0012. A future per-class auto-landing path requires its own
  accepted SPEC/profile and certified target assurance under ADR-0009; success statistics
  or a skill's own instruction cannot earn it alone.
- **Churn control:** lessons accumulate in a staging area and are periodically distilled
  into one PR (batch), never one PR per run.

### D5. Adoption is component-owned and cannot be inferred from file presence

| Consumer | Current evidence | Required adoption boundary |
|---|---|---|
| `genai-enablement` registry | 24 committed skill files; v1 SKILL.md-only hashes; no committed registry CODEOWNERS/CI or signed release | accepted core/profile mapping, protected publication paths, reproducible closed full-tree manifest, human-owned signature/revocation authority, independent verifier, immutable release |
| multiqlti | committed parser/sync at `21bbabb`; local v1 hash/path checks; `sourceType: git` materialization | explicitly tracking/proving-ground mode unless a later accepted adapter verifies the signed release; no imported organizational trust or tool authority; exact transformation/replay evidence |
| Omnius | dirty/local draft SPEC-REG and candidate fail-closed contracts; live v1 rejected; incompatible legacy lifecycle remains | accepted component ADR/SPEC and exact readiness profile, clean immutable implementation and manifest, configured external verifier, local admission/oracle evidence, legacy bypass removal, negative severance/revocation drills |
| engineer clients | filesystem discovery differs by product; support for the local top-level extension profile is not proven by the upstream core | client/version compatibility recorded per release; local/tracking use only unless the same signed release and organizational policy are enforced |
| PB-SRE / runbook consumers | converted runbook-shaped seeds exist in the bootstrap registry | accepted profile mapping for step metadata plus independent action-tier authorization; conversion cannot grant execution |
| Omniscience | no accepted registry connector/publication evidence in this ADR | optional read-only indexing of exact released artifacts and lineage; no admission, trust, policy, or availability authority |

### D6. Omniscience indexes the registry

After an independently released registry exists, `platform-skills` may be registered as a
read-only git connector in Omniscience. The index may relate exact release/tree identities to
tasks, consumers, incidents, model changes, and attributed outcome/return evidence. It is a
signal-only projection: Omniscience cannot sign a release, set local trust, authorize a
skill/tool, supply an oracle, or become required for pinned active-task replay. On severance,
consumers use their exact verified local materialization for already admitted work and block
new uncached resolution; they do not follow a stale graph or branch.

## Required conformance and activation evidence

Acceptance of this ADR is necessary but not sufficient for activation. Component owners must
publish immutable evidence for all of the following before any organizational use:

1. an accepted ADR revision plus accepted component adoption ADR/SPEC and an exact ready
   CapabilityReadinessProfile selecting the relevant requirements/probes;
2. one clean exact registry Git revision with independently reproduced core/profile
   validation, canonical signed release envelope, closed full-tree manifest, and verified
   origin/commit/release/profile/manifest joins;
3. human-owned protected-path, CODEOWNERS, signing, verifier, revocation, and key-rotation
   bindings, with worker/evaluator/proposal identities denied every direct mutation path;
4. malformed, oversized, duplicate-key, unknown-field, non-finite, path traversal, symlink,
   case/Unicode collision, missing/extra file, dirty-revision, mutable-ref, expired/revoked,
   wrong-origin, wrong-profile, wrong-commit, wrong-verifier, truthy-verifier, callback-
   mutation, copied-invalid, fabricated-capability, and post-issuance-mutation negatives;
5. body, reference, script, asset, license, and provenance mutations each changing the full
   tree identity and re-entering quarantine; script presence must grant no execution;
6. hostile `allowed-tools`, `compatible_tools`, `tier`, trust, success, or approval fields
   proving unable to widen WorkOrder/Realm/tool policy or set local trust;
7. exact local admission with independently administered criteria/oracle, explicit
   `inconclusive` fail-closed behavior, dossier attribution/source-health checks, and proof
   that foreign trust remains signal-only;
8. deterministic collision, idempotency, cache, revocation, active-task enumeration,
   severance, retry, concurrency, and recovery drills with immutable non-secret receipts;
9. multiqlti tracking-mode proof that current local sync cannot publish organizational
   trust or silently become a pinned consumer, plus exact parser/transformation replay; and
10. Omnius evidence from one clean immutable component release showing that raw v1 lock,
    legacy lifecycle, caller-built decisions, and missing external verifier all park before
    task execution, followed by exact signed-release resolution on the admitted path.

No checklist item may be satisfied by this proposal, a fixture key, the current HMAC test
double, a local hash match, a dirty worktree, or a human receipt that merely copies producer
claims.

## Consequences

**Positive**
- If accepted and adopted, one exact skill tree can retain one replayable history across
  consumers while local bindings and trust remain independent (R1).
- The proposal path allows agent-authored improvements without agent-owned correctness or
  publication authority (R2).
- Existing bootstrap content, multiqlti ingestion, and Omnius candidate contracts provide
  implementation evidence without being misrepresented as an active trust root.

**Negative / costs**
- One more governed registry/release surface and additional CODEOWNERS review load
  (mitigated by batching, D4).
- multiqlti's internal marketplace (fork/share/semver) must reconcile local forks with the
  registry (forks become branches or divergent local skills — needs a follow-up design
  note).
- Trust re-earning after every body change adds latency between "improved" and "trusted"
  (accepted deliberately — that latency is the safety margin).

**Risks**
- Skill flapping if agents propose edits too eagerly → batch distillation + PR rate limits.
- Cross-runtime contamination if a runtime mistakenly imports another's trust status →
  trust indexes are structurally local (D3); conformance test to enforce.
- Format drift between upstream core and local extensions → both exact pins and their
  mapping are versioned and validated in registry CI.

## Alternatives considered

1. **`multiqlti/v1 Kind: Skill` YAML as the canon** — rejected: it couples shared content to
   one runtime's binding schema and recreates N×M conversion.
2. **Central skill service (DB + HTTP API)** — rejected: omnius SPEC-SK explicitly forbids
   a mutable skill API as an attack surface; git provides provenance, review gates, and
   rollback for free; an API can later be layered read-only on top if needed.
3. **Keep per-runtime formats + N×M converters** — rejected: converter drift recreates
   today's problem with extra steps; no single change history per skill.
4. **Store trust status in the SKILL.md frontmatter** — rejected: trust is
   runtime-measured and non-transferable (D3); embedding it would make a skill "verified"
   everywhere after one runtime's validation — precisely the unsafe shortcut.
5. **Treat the current v1 `computedHash` lock as production pinning** — rejected: it omits
   exact Git/profile/release authority and ignores non-`SKILL.md` bytes.
6. **Treat local extension fields or client acceptance as the format standard** — rejected:
   the upstream core and the platform profile must be independently pinned and validated;
   permissive parsing is not a compatibility contract.

## Follow-ups

- [x] Create the bootstrap `skills/` registry and seed it. It now contains 24 committed
      `SKILL.md` files; this completion does not publish a production release.
- [x] multiqlti: committed SKILL.md parser and v1 local sync at `21bbabb`. It remains a
      tracking/proving-ground adapter, not a signed organizational consumer.
- [ ] Human acceptance: pin the exact upstream Agent Skills revision and disposition the
      platform profile/migration for current extension fields.
- [ ] Registry CI and protection: exact core/profile validator, closed full-tree manifest
      builder, secret/content/license/provenance scans, lock reproduction, protected
      CODEOWNERS/release paths, and negative fixtures.
- [ ] Registry trust root: select the production signing algorithm and human key owner,
      approve the closed release schema, publish one exact clean signed revision, configure
      independent verifier/revocation/key-rotation bindings, and retain external receipts.
- [ ] Omnius: accept the component adoption SPEC/profile, publish the implementation from a
      clean immutable revision, configure the external verifier, and remove every legacy or
      raw-lock bypass before P1 REG activation.
- [ ] omnius: issue to rename Cedar `permitted_skill_set` → `capability set`
      (glossary Part 3 ruling; avoids the internal name collision).
- [ ] Omniscience: register only an immutable released registry as a read-only source and
      prove consumer severance (D6).
- [ ] Follow-up design note: multiqlti marketplace forks vs registry reconciliation.

## References

- [platform-glossary.md](../platform-glossary.md) — canonical vocabulary (skill, trust
  lifecycle, evidence, graduation path, lock-file/pinning)
- [Agent Skills specification](https://agentskills.io/specification) — upstream core format;
  a production release must pin an immutable revision/blob rather than this mutable URL
- [bootstrap registry](../../skills/REGISTRY.md) and
  [v1 lock inventory](../../skills/skills-lock.json) — current non-authorizing local evidence
- omnius: `specs/SPEC-SK-skill-lifecycle.md`, `phase_3/skill_lifecycle.py`,
  `specs/SPEC-REG-platform-skills-registry-adapter.md`,
  `mvp_core/registry/contracts.py`, `architecture/MASTER-ARCHITECTURE.md` §6.2
- multiqlti: commit `21bbabb`, `server/skills/skill-md-service.ts`,
  `server/skills/registry-sync.ts`, `shared/types.ts` (`SkillYaml`)
- Omniscience: `docs/decisions/0015-multiqlti-as-mcp-consumer-and-source.md`
- monorepo: `.claude/skills/` + `VENDORED.md`, `skills-lock.json`
