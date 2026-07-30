#!/usr/bin/env python3
"""Generate a disposable, high-entropy `.env` for the assembled
management-readonly-local-v1 synchronized-platform stack (task-sp-98, ADR-0024).

Safety contract (AC-SP98-9 / ADR-0024 D6):

  * NEVER prints a secret value on stdout or stderr — only variable NAMES and a
    count/entropy summary.
  * NEVER overwrites an existing `.env`. A running store keeps the password set
    at its first init, so regenerating would lock the stack out of its own
    volume; a real reset is the separate, explicit `docker compose down -v`
    followed by removing `.env` by hand. `--force` still requires the explicit
    `--i-am-resetting-local-secrets` confirmation token.
  * Reads only the committed `.env.example` template and copies every non-secret
    line verbatim; only the SECRET block is randomized. Config-coupled values
    (ports, DB names/roles, the owner-baked Keycloak client secret, TTLs) are
    copied, never randomized — randomizing them would desynchronize a baked
    owner artifact.

This script writes only inside this repository's
deploy/local/management-readonly-v1/ directory. It performs no Docker, network,
or cross-repository action.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_DIR = ROOT / "deploy" / "local" / "management-readonly-v1"
DEFAULT_TEMPLATE = ENV_DIR / ".env.example"
DEFAULT_ENV_FILE = ENV_DIR / ".env"

# The variables the generator randomizes with fresh high-entropy values. Every
# one is a store/broker credential whose value the assembled Compose model is
# free to choose and wires consistently into both the store and its consumers.
# Anything NOT in this set (ports, DB names/roles, the owner-baked Keycloak
# client secret, TTLs, model identity) is copied verbatim from the template.
SECRET_VARS: tuple[str, ...] = (
    "OMNISCIENCE_POSTGRES_PASSWORD",
    "OMNISCIENCE_NEO4J_PASSWORD",
    "OMNISCIENCE_QDRANT_API_KEY",
    "POSTGRES_PASSWORD",
    "PORTAL_DB_PASSWORD",
    "PORTAL_APP_DB_PASSWORD",
    "PORTAL_KEYCLOAK_ADMIN_PASSWORD",
)

# 32 url-safe bytes -> 256 bits of entropy per secret.
SECRET_ENTROPY_BYTES = 32
CONFIRM_TOKEN = "--i-am-resetting-local-secrets"


class EnvGenerationError(Exception):
    """Raised when the template is missing or a destructive overwrite is refused."""


def new_secret() -> str:
    """Return a fresh high-entropy, url-safe secret (no leading dash, no '=')."""
    return secrets.token_urlsafe(SECRET_ENTROPY_BYTES)


def _split_assignment(line: str) -> tuple[str, str] | None:
    """Return (KEY, VALUE) for a `KEY=VALUE` line, else None (comment/blank)."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if "=" not in line:
        return None
    key, _, value = line.partition("=")
    key = key.strip()
    if not key or any(ch.isspace() for ch in key):
        return None
    return key, value


def render_env(template_text: str, secret_factory=new_secret) -> tuple[str, list[str]]:
    """Render the .env body from the template.

    Every SECRET_VARS assignment gets a fresh secret; every other line (comments,
    blanks, config assignments) is copied verbatim. Returns the rendered text and
    the sorted list of secret variable NAMES that were assigned (never values).
    """
    out_lines: list[str] = []
    assigned: set[str] = set()
    for line in template_text.splitlines():
        parsed = _split_assignment(line)
        if parsed is not None and parsed[0] in SECRET_VARS:
            key = parsed[0]
            out_lines.append(f"{key}={secret_factory()}")
            assigned.add(key)
        else:
            out_lines.append(line)
    return "\n".join(out_lines) + "\n", sorted(assigned)


def write_env_file(env_file: Path, text: str) -> None:
    """Write the env file with owner-only permissions (0600)."""
    env_file.write_text(text, encoding="utf-8")
    os.chmod(env_file, 0o600)


def generate(
    template: Path = DEFAULT_TEMPLATE,
    env_file: Path = DEFAULT_ENV_FILE,
    force: bool = False,
    confirmed: bool = False,
) -> list[str]:
    """Generate env_file from template. Returns the list of secret var NAMES set.

    Raises EnvGenerationError if the template is missing, if env_file exists and
    force is not set, or if force is set without the explicit confirmation token.
    """
    if not template.exists():
        raise EnvGenerationError(f"missing template: {template}")
    if env_file.exists():
        if not force:
            raise EnvGenerationError(
                f"refusing to overwrite existing env file: {env_file}\n"
                f"a running store keeps its first-init password; to reset, run "
                f"`docker compose ... down -v`, remove {env_file.name}, then re-run "
                f"with {CONFIRM_TOKEN}."
            )
        if not confirmed:
            raise EnvGenerationError(
                f"--force requires the explicit confirmation token {CONFIRM_TOKEN} "
                f"(overwriting {env_file.name} invalidates the secrets a running "
                f"stack already committed to its volumes)."
            )
    text, assigned = render_env(template.read_text(encoding="utf-8"))
    # Every secret var declared in the template must have been assigned.
    missing = [v for v in SECRET_VARS if v not in assigned]
    if missing:
        raise EnvGenerationError(
            f"template does not declare required secret variables: {', '.join(missing)}"
        )
    write_env_file(env_file, text)
    return assigned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument(
        "--env-file", type=Path, default=DEFAULT_ENV_FILE, dest="env_file"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing env file (DESTRUCTIVE; also requires the confirmation token)",
    )
    parser.add_argument(
        CONFIRM_TOKEN,
        action="store_true",
        dest="confirmed",
        help="explicit confirmation that overwriting local secrets is intended",
    )
    args = parser.parse_args()

    try:
        assigned = generate(
            template=args.template,
            env_file=args.env_file,
            force=args.force,
            confirmed=args.confirmed,
        )
    except EnvGenerationError as exc:
        print(f"env generation refused: {exc}", file=sys.stderr)
        return 3

    # Report NAMES and a count/entropy summary only — never a value.
    try:
        shown_path = args.env_file.resolve().relative_to(ROOT)
    except ValueError:
        shown_path = args.env_file
    print(f"wrote {shown_path} (mode 0600)")
    print(
        f"generated {len(assigned)} high-entropy secrets ({SECRET_ENTROPY_BYTES * 8} bits each):"
    )
    for name in assigned:
        print(f"  - {name}")
    print(
        "config-coupled and non-secret values were copied verbatim from the template."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
