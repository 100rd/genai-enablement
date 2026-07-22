#!/usr/bin/env python3
"""Build the content-addressed manifest for the SP-60 PII contract bundle.

Covers exactly the schemas and fixtures (SPEC-PII-POLICY AC-SP60-2: "one
canonical digest covers schemas and fixtures"). Does not cover the validator
or this tooling script itself -- those are implementation, not the published
contract surface.

Usage: python3 contracts/pii/tooling/build_manifest.py [--check]

``--check`` recomputes the digest and compares it against the file already on
disk without writing, exiting non-zero on drift (used by CI/tests as an
independent recomputation).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

CONTRACT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = CONTRACT_ROOT / "manifest" / "pii-contract-manifest.v1.json"
COVERED_ROOTS = ("schemas/v1", "fixtures/v1")
ALGORITHM_LABEL = "sha256-of-sorted-path-digest-pairs-v1"


def iter_covered_files() -> list[Path]:
    """Return every file under the covered roots, deterministically sorted."""
    files: list[Path] = []
    for root in COVERED_ROOTS:
        root_dir = CONTRACT_ROOT / root
        files.extend(path for path in root_dir.rglob("*") if path.is_file())
    return sorted(files, key=lambda path: path.relative_to(CONTRACT_ROOT).as_posix())


def build_entries() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for path in iter_covered_files():
        relative_path = path.relative_to(CONTRACT_ROOT).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({"path": relative_path, "sha256": digest})
    return entries


def canonical_digest(entries: list[dict[str, str]]) -> str:
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_manifest() -> dict[str, Any]:
    entries = build_entries()
    return {
        "contract": "SPEC-PII-POLICY",
        "workPackage": "SP-60",
        "governingAdrs": ["genai-enablement/ADR-0018"],
        "schemaMajor": 1,
        "algorithm": ALGORITHM_LABEL,
        "coveredRoots": list(COVERED_ROOTS),
        "generatedBy": "contracts/pii/tooling/build_manifest.py",
        "entryCount": len(entries),
        "entries": entries,
        "canonicalDigest": canonical_digest(entries),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="recompute and compare against the on-disk manifest without writing",
    )
    args = parser.parse_args(argv)

    manifest = build_manifest()

    if args.check:
        if not MANIFEST_PATH.exists():
            print(f"manifest missing at {MANIFEST_PATH}", file=sys.stderr)
            return 1
        on_disk = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if on_disk.get("canonicalDigest") != manifest["canonicalDigest"]:
            print(
                "manifest drift: recomputed digest "
                f"{manifest['canonicalDigest']} != on-disk digest {on_disk.get('canonicalDigest')}",
                file=sys.stderr,
            )
            return 1
        print(f"manifest OK: {manifest['canonicalDigest']}")
        return 0

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST_PATH} ({manifest['canonicalDigest']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
