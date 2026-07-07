---
name: python-dev
description: Use when writing, reviewing, or refactoring Python on the platform — project layout, typing, dataclasses/Protocol seams, testing conventions, and the Poetry + ruff + mypy + pytest verification loop required before any PR.
version: 0.1.0
tags: [engineering, python]
compatible_tools: [claude-code, multiqlti, omnius, cursor, antigravity]
tier: T1
license: MIT
---

# Python Development

Platform conventions for Python services and tools, grounded in `solutions/sre-harness`
(Poetry, src layout, ruff + mypy + pytest). Optimize for boring, explicit, typed code:
the reader's time is worth more than the writer's.

## Project layout

- Poetry per deployable unit; `src/` layout — `packages = [{ include = "<pkg>", from = "src" }]`.
  Import the package, never a loose top-level module.
- `src/<pkg>/cli.py` exposes `main()` wired as a `[tool.poetry.scripts]` entry; keep it thin
  (parse args, build dependencies, call into the domain).
- Organize modules by domain (`change_gate.py`, `platform_graph.py`), not by layer type.
- Commit `poetry.lock`. Target Python 3.11+ (`target-version = "py311"`).

## Types & data

- `from __future__ import annotations` at the top of every module; type-hint every function —
  mypy runs with `disallow_untyped_defs = true`, so an untyped def fails the build.
- Model data with `@dataclass` — `frozen=True` value objects are pervasive in the harness;
  `slots=True` and `field(default_factory=...)` for mutable defaults are recommended additions
  (not yet used there). Never use a bare mutable default (`[]`, `{}`).
- Define seams as `typing.Protocol` (structural), defined by the consumer — e.g. the
  platform-graph *port* is a Protocol the harness depends on, not a concrete class. Keep them
  small (1–3 methods).
- Prefer `Enum` over bare strings for closed sets (grounded in the harness); `Literal` and
  `assert_never`-style exhaustiveness checks are recommended, not yet pervasive there.

## Errors

- Raise specific exceptions; never `except:` bare and never swallow — catch the narrowest type
  and re-raise with context (`raise CliError(...) from err`, the harness's own exception).
- Validate at boundaries (CLI args, parsed change files, external responses); fail fast with a
  clear message. Don't trust external data.

## Testing

- `pytest`; tests in `tests/`, `pythonpath = ["src"]`. Name tests for the behavior under test.
- Use the registered markers (`unit`, `integration`) with `--strict-markers`; keep unit tests
  free of I/O — fake Protocol seams, don't patch internals.
- Coverage via `pytest-cov` (`source = ["src/<pkg>"]`); target 80% on changed code, don't chase
  100% with assertion-free tests.

## Style & tooling

- `ruff` for lint + import order (`select = E,W,F,I,C,B,UP`); `black` owns formatting
  (`line-length = 100`), which is why ruff ignores `E501`. No manual alignment.
- Add a dependency only when it replaces meaningful code; keep it in the right Poetry group
  (runtime vs `group.dev`). Justify new direct dependencies in the PR.
- Logging via the stdlib `logging` (or the platform tracing facade); no `print` outside CLI
  scaffolding.

## Verification loop (before every PR)

Run all of it; all must pass clean — the documented `solutions/sre-harness` loop (`pytest`,
`ruff check src tests`, `mypy`) plus `black --check` and coverage, both configured in its
`pyproject.toml`:

```bash
poetry install
poetry run ruff check src tests
poetry run black --check src tests
poetry run mypy
poetry run pytest --cov
```

Include test output (or the relevant failure → fix summary) in the PR description.
