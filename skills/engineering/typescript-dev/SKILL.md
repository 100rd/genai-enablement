---
name: typescript-dev
description: Use when writing, reviewing, or refactoring TypeScript on the platform — project layout, strict typing, error/async handling, testing conventions, and the ESLint + Prettier + tsc verification loop required before any PR.
version: 0.1.0
tags: [engineering, typescript]
compatible_tools: [claude-code, multiqlti, omnius, cursor, antigravity]
tier: T1
license: MIT
---

# TypeScript Development

Platform conventions for TypeScript components and services. Optimize for boring, explicit,
strictly-typed code: the reader's time is worth more than the writer's.

## Project layout

- Organize by feature/domain, not by file type. Barrel (`index.ts`) only at real module
  boundaries; avoid deep re-export chains.
- One `tsconfig.json` per package with `"strict": true`; extend a shared base rather than
  copying compiler flags. Prefer ESM (`"type": "module"`), `"moduleResolution": "bundler"` or
  `"node16"` per runtime.
- Commit the lockfile (`pnpm-lock.yaml` / `package-lock.json`). Keep `package.json` scripts as
  the single source of truth for lint/format/typecheck/test.

## Types

- `strict: true` is non-negotiable; also enable `noUncheckedIndexedAccess` and
  `exactOptionalPropertyTypes`. Treat compiler errors as build failures.
- **No `any`.** Use `unknown` at boundaries and narrow; reach for generics or discriminated
  unions instead of casting. `as` casts need a comment justifying why they're sound.
- Explicit return types on every exported function and public method — inference is fine for
  locals, never for the module's public surface.
- Model closed sets with union literals or `as const`; use discriminated unions + exhaustive
  `switch` with a `never` default to force handling of new cases.

## Errors & async

- Prefer `async/await` over raw `.then()` chains; every `await` that can reject is handled or
  deliberately propagated. No floating promises (`@typescript-eslint/no-floating-promises`).
- Throw `Error` subclasses with context; never throw strings. Validate external input at the
  boundary (e.g. `zod`) and treat parsed data as the typed source of truth.
- Never swallow errors silently; surface user-facing messages in UI code, log structured
  context on the server.

## Testing

- `vitest` (or `jest`) with tests colocated or under `test/`; name tests for the behavior under
  test. Prefer testing exported behavior over implementation details.
- Fake dependencies at seams (interfaces/injected deps), not deep module internals; keep unit
  tests free of network/filesystem. Target 80% on changed code.

## Style & tooling

- ESLint (flat config, `@typescript-eslint`) for correctness; Prettier owns formatting — don't
  fight it with lint rules. Fix, don't disable; an `eslint-disable` needs a reason.
- Add a dependency only when it replaces meaningful code; prefer the platform's existing
  libraries. Justify new direct dependencies in the PR.

## Verification loop (before every PR)

Run all of it; all must pass clean:

```bash
pnpm install
pnpm eslint .
pnpm prettier --check .
pnpm tsc --noEmit
pnpm test
```

Include test output (or the relevant failure → fix summary) in the PR description.
