# ADR-0022: Barbarossa production runtime is Go

- **Status:** Accepted
- **Date:** 2026-07-25
- **Deciders:** platform owner and Barbarossa owner
- **Scope:** Barbarossa implementation language, migration sequencing, and synchronized-platform release evidence
- **Depends on:** [ADR-0020](0020-barbarossa-continuous-management-plane.md) and
  [ADR-0021](0021-management-readonly-initial-runtime-profile.md)

## Context

Barbarossa was designed as an independently operable Continuous Management Plane. Its accepted
capability ADRs and SPECs describe authority, deterministic evaluation, durable evidence, isolation,
severance, and effect boundaries; they did not select an implementation language.

The first contract/mock implementation introduced TypeScript strict ESM, Zod, and Vitest without a
language ADR. Later tasks inherited that repository shape and repeated `Barbarossa = TypeScript` as if
it were an accepted architecture decision. That implementation is valuable as an executable contract
and regression corpus, but it is not evidence that Node.js was selected for the production control
plane.

The platform owner has reaffirmed the intended decision: Barbarossa's production runtime is Go. The
initial `management-readonly-v1` release must not make the accidental prototype stack permanent.

## Decision

### D1 — Go is the sole Barbarossa production runtime

Every deployable Barbarossa server, worker, scheduler, evaluator, persistence adapter, projection
publisher, health endpoint, migration tool, and production container selected by a synchronized-platform
runtime profile MUST be implemented and built as Go.

An exact Go compiler/toolchain version and module graph are pinned by each release. Mutable tags such as
`latest` are not release evidence. Production images and SBOMs contain no Node.js runtime, npm/pnpm/yarn,
TypeScript transpiler, Vitest runner, or JavaScript sidecar.

### D2 — TypeScript becomes a read-only conformance oracle during migration

The existing TypeScript implementation remains temporarily available as:

- executable examples of the accepted language-neutral contracts;
- deterministic fixtures and negative cases;
- a parity corpus for the Go migration; and
- regression evidence for behavior that has not yet been ported.

It is not a production runtime, fallback service, sidecar, release artifact, source of authority, or
permission to reinterpret a SPEC. Migration work cannot edit the TypeScript oracle merely to make Go
parity pass. Any intentional contract change starts in the governing ADR/SPEC and updates both
implementations from that accepted revision.

### D3 — Complete the whole implemented Go surface before SP-87

`SP-90` is the owner-local Barbarossa Go migration package for the complete implemented contract
surface, not only the `management-readonly-v1` slice. It ports and qualifies:

- shared fail-closed, identity, integrity, clock, tenant and PW0 primitives;
- every implemented kernel module, including cross-loop constraints, governed-action contracts and
  independent verification;
- every implemented domain pack in the accepted Barbarossa capability inventory; and
- runtime, package, health, telemetry, durability, backup/restore and rollback seams.

SP-90 excludes progressive autonomy because `SPEC-AUT` has no accepted implementation, live owner
adapters, Omnius integration, credentials, deployment activation and managed effects. Ported code does
not become selected code: each runtime profile still declares an exact domain and authority allowlist.
`management-readonly-v1` continues to activate Reliability only and forbids effects.

SP-86 remains an independent Omniscience producer task and may run in parallel with SP-90. SP-87 cannot
start release qualification until exact SP-90 and SP-86 receipts exist:

```text
SP-71..80 + SP-83  -> SP-90 (complete implemented Barbarossa Go baseline)
SP-10/61/81       -> SP-86 (Omniscience release)
SP-90 + SP-86     -> SP-87 -> SP-88 -> SP-89
```

### D4 — Parity is contract-based, not line-by-line translation

Go acceptance is evaluated against the accepted ADR/SPEC semantics and an immutable, independently
reviewed fixture manifest. Equivalent external envelopes, reason codes, state transitions, ordering,
deduplication, replay, freshness, severance, PW0 and failure behavior are required. Internal package
layout and implementation technique may differ.

A favorable TypeScript result cannot overrule a stricter accepted contract, and a Go implementation
cannot claim parity from compile success, test count, or fixture-only happy paths.

### D5 — TypeScript retirement is a separate, evidence-gated cleanup

SP-90 and SP-87 do not delete the oracle. Retirement requires a later owner-local task proving that all
selected and retained contract cases have moved to language-neutral fixtures or Go tests, repository CI
no longer needs Node.js, and rollback no longer depends on the TypeScript baseline. Until then, the
oracle is explicitly non-deployable and excluded from release artifacts.

## Cross-repository invariants

- **GO-1:** every implemented Barbarossa capability except blocked `SPEC-AUT` resolves to the exact
  full-surface SP-90 Go baseline; each workload activates only its profile-selected closure.
- **GO-2:** SP-86 is language-independent and has no dependency on SP-90.
- **GO-3:** SP-87 is RED when the SP-90 receipt, compiler pin, module graph, SBOM, parity manifest or
  no-Node evidence is absent or mutable.
- **GO-4:** Portal consumes owner contracts, never Go internals, but displays the owner-published runtime
  implementation and release provenance without recomputation.
- **GO-5:** SP-89 independently confirms that no Node.js/TypeScript execution path exists in the
  Barbarossa production artifact or deployed workload.
- **GO-6:** the migration grants no infrastructure, source, policy, incident, alert, action, effect,
  autonomy or production-activation authority.

## Consequences

### Positive

- The intended production language is explicit and cannot be inferred from a prototype.
- The first deployed Barbarossa slice validates the production runtime rather than a disposable mock.
- Contract parity preserves existing test investment without shipping Node.js.
- Later runtime profiles can select already ported domain packs without reopening the language move.

### Costs and trade-offs

- SP-87 now waits for a complete Go migration receipt rather than a Reliability-only subset.
- The repository temporarily carries two implementations of part of the contract surface.
- CI must keep oracle and Go evidence separate until retirement.
- A direct translation is insufficient; durable/restart and production packaging evidence are required.

## Alternatives rejected

- **Ship the TypeScript baseline first and migrate later:** turns an accidental prototype choice into a
  deployed compatibility obligation.
- **Delete TypeScript before parity:** discards the only executable regression corpus and makes silent
  semantic loss harder to detect.
- **Run Go and Node.js together:** widens the trust, supply-chain, operations and failure surface and
  obscures the authoritative runtime.
- **Let each domain choose a language:** fragments deterministic kernel behavior and complicates
  isolation, replay and release qualification.

## Acceptance record

The platform owner confirmed on 2026-07-25 that the Go transition belongs to the current planning
iteration and must complete before the previously accepted SP-87 release handoff. This decision
authorizes only the bounded ADR/SPEC and SP-90 development contract. It does not authorize deployment,
production activation, infrastructure mutation, credentials, live sources or managed-system effects.
