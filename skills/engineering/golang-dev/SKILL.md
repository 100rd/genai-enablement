---
name: golang-dev
description: Use when writing, reviewing, or refactoring Go code on the platform — project layout, error handling, concurrency, testing conventions, and the verification loop required before any PR.
version: 0.1.0
tags: [engineering, golang]
compatible_tools: [claude-code, multiqlti, omnius, cursor, antigravity]
tier: T1
license: MIT
---

# Go Development

Platform conventions for Go services and tools. Optimize for boring, explicit, reviewable
code: the reader's time is worth more than the writer's.

## Project layout

- `cmd/<binary>/main.go` — thin entrypoints: parse config, wire dependencies, call `run(ctx)`.
- `internal/<domain>/` — business logic, organized by domain, not by layer type.
- `pkg/` only for code deliberately importable by other repos; default to `internal/`.
- One `go.mod` per deployable unit; commit `go.sum`.

## Errors

- Return errors; never panic in library code. `panic` is acceptable only in `main` wiring
  for impossible states.
- Wrap with context: `fmt.Errorf("loading tenant %s: %w", id, err)`. Use `%w` so callers
  can `errors.Is`/`errors.As`.
- Sentinel errors (`var ErrNotFound = errors.New(...)`) for conditions callers branch on;
  typed errors when callers need fields.
- Handle every error explicitly. `_ =` requires a comment explaining why discarding is safe.
- Error messages: lowercase, no trailing punctuation, no "failed to" prefix stacking.

## Context & concurrency

- `context.Context` is the first parameter of anything that blocks, does I/O, or can be
  cancelled. Never store contexts in structs.
- No naked goroutines: every goroutine has a defined owner, a way to stop (ctx), and a way
  to surface its error. Prefer `golang.org/x/sync/errgroup` over hand-rolled WaitGroups.
- Channels: the writer closes; prefer passing data over sharing memory; buffered channels
  need a stated reason for the chosen capacity.
- Guard shared state with the race detector, not with hope: `go test -race` is part of the
  verification loop, always.

## Testing

- Table-driven tests with named cases; `t.Run(name, ...)` for subtests; `t.Parallel()`
  where cases are independent.
- Test behavior through exported APIs; reach into internals only when there is no
  observable behavior to assert.
- Use interfaces at consumption points to fake dependencies; keep interfaces small
  (1–3 methods) and defined by the consumer, not the provider.
- Golden files for large outputs (`testdata/`, update via a `-update` flag).
- Coverage target: 80% on changed packages; do not chase 100% through assertion-free tests.

## Style & dependencies

- `gofmt`/`goimports` formatting is non-negotiable; no manual alignment.
- Follow standard naming: short receiver names, `New<T>` constructors, no `Get` prefixes,
  acronyms capitalized (`ServeHTTP`, `userID`).
- Add a dependency only when it replaces meaningful code; prefer stdlib. Justify any new
  direct dependency in the PR description.
- Logging: `log/slog` with structured key-value pairs; no `fmt.Println` outside `main`
  scaffolding.

## Verification loop (before every PR)

Run all of it; all must pass clean:

```bash
gofmt -l . && go vet ./...
golangci-lint run
go test -race -cover ./...
go mod tidy && git diff --exit-code go.mod go.sum
```

Include test output (or the relevant failure → fix summary) in the PR description.
