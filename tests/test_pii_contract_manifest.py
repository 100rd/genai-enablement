"""AC-SP60-2 probe: pii-contract-manifest.

Ground truth: accepted ADR-0018 plus an independently recomputed manifest
digest and an absence scan.

Expected: the recomputed manifest digest is stable/canonical over schemas +
fixtures, AND an absence scan confirms no active policy, key, or permit
issuer exists anywhere in the published SP-60 contract bundle.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "contracts" / "pii"
MANIFEST_PATH = CONTRACT_ROOT / "manifest" / "pii-contract-manifest.v1.json"
COVERED_ROOTS = ("schemas/v1", "fixtures/v1")

if str(CONTRACT_ROOT) not in sys.path:
    sys.path.append(str(CONTRACT_ROOT))

from validator import pii_contract_validator as pcv  # noqa: E402
from validator import schema_check  # noqa: E402

_PEM_MARKERS = (
    "-----BEGIN PRIVATE KEY",
    "-----BEGIN RSA PRIVATE KEY",
    "-----BEGIN EC PRIVATE KEY",
    "-----BEGIN OPENSSH PRIVATE KEY",
    "-----BEGIN ENCRYPTED PRIVATE KEY",
)
_NETWORK_CALL_PATTERN = re.compile(
    r"\b(requests\.(get|post|put|delete|patch)|urllib\.request|http\.client|"
    r"socket\.socket|aiohttp\.|httpx\.(get|post))\s*\("
)
_SERVER_PATTERN = re.compile(r"\b(Flask\(|FastAPI\(|app\.run\(|uvicorn\.run\(|http\.server\.HTTPServer\()")
_FORBIDDEN_CALLABLE_PREFIXES = ("issue_", "publish_", "activate_", "grant_", "mint_", "provision_")
_FORBIDDEN_STATUS_VALUES = {"active", "published", "live", "production"}


def _independent_manifest_recompute() -> tuple[list[dict[str, str]], str]:
    """Recompute the manifest from scratch, without importing build_manifest.py,
    to genuinely serve as an independent check on the published tool's output.
    """
    entries: list[dict[str, str]] = []
    for root in COVERED_ROOTS:
        root_dir = CONTRACT_ROOT / root
        for path in root_dir.rglob("*"):
            if path.is_file():
                relative_path = path.relative_to(CONTRACT_ROOT).as_posix()
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                entries.append({"path": relative_path, "sha256": digest})
    entries.sort(key=lambda entry: entry["path"])
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    canonical_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    return entries, canonical_digest


class ManifestDigestIsCanonicalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(MANIFEST_PATH.exists(), f"manifest not found at {MANIFEST_PATH}")
        with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
            self.on_disk_manifest = json.load(handle)
        self.recomputed_entries, self.recomputed_digest = _independent_manifest_recompute()

    def test_recomputed_digest_matches_on_disk_manifest(self) -> None:
        self.assertEqual(self.recomputed_digest, self.on_disk_manifest["canonicalDigest"])

    def test_digest_is_stable_across_repeated_recomputation(self) -> None:
        _, second_digest = _independent_manifest_recompute()
        self.assertEqual(self.recomputed_digest, second_digest)

    def test_every_on_disk_schema_and_fixture_file_is_covered_by_the_manifest(self) -> None:
        manifest_paths = {entry["path"] for entry in self.on_disk_manifest["entries"]}
        actual_paths = {entry["path"] for entry in self.recomputed_entries}
        self.assertEqual(actual_paths, manifest_paths)

    def test_every_manifest_entry_sha256_matches_the_file_on_disk_right_now(self) -> None:
        recomputed_by_path = {entry["path"]: entry["sha256"] for entry in self.recomputed_entries}
        for entry in self.on_disk_manifest["entries"]:
            with self.subTest(path=entry["path"]):
                self.assertEqual(recomputed_by_path[entry["path"]], entry["sha256"])

    def test_manifest_entry_count_matches(self) -> None:
        self.assertEqual(len(self.recomputed_entries), self.on_disk_manifest["entryCount"])

    def test_tampering_a_covered_file_changes_the_digest(self) -> None:
        """Prove the digest is actually sensitive to content, not a constant."""
        sample_schema = CONTRACT_ROOT / "schemas" / "v1" / "profile.schema.json"
        original_bytes = sample_schema.read_bytes()
        try:
            sample_schema.write_bytes(original_bytes + b" ")
            _, tampered_digest = _independent_manifest_recompute()
            self.assertNotEqual(tampered_digest, self.recomputed_digest)
        finally:
            sample_schema.write_bytes(original_bytes)


class AbsenceScanTests(unittest.TestCase):
    """Confirm the published bundle activates nothing: no live policy, key, or issuer."""

    def _all_source_files(self) -> list[Path]:
        return [path for path in CONTRACT_ROOT.rglob("*") if path.is_file()]

    def test_no_pem_private_key_material_anywhere_in_the_bundle(self) -> None:
        for path in self._all_source_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in _PEM_MARKERS:
                self.assertNotIn(
                    marker, text, f"{path.relative_to(CONTRACT_ROOT)} contains PEM key marker {marker!r}"
                )

    def test_no_outbound_network_calls_in_python_sources(self) -> None:
        for path in CONTRACT_ROOT.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            match = _NETWORK_CALL_PATTERN.search(text)
            self.assertIsNone(
                match, f"{path.relative_to(CONTRACT_ROOT)} appears to make an outbound network call: {match}"
            )

    def test_no_web_server_or_service_entrypoint_in_python_sources(self) -> None:
        for path in CONTRACT_ROOT.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            match = _SERVER_PATTERN.search(text)
            self.assertIsNone(
                match, f"{path.relative_to(CONTRACT_ROOT)} appears to start a server: {match}"
            )

    def test_validator_module_exposes_no_issuing_or_publishing_callable(self) -> None:
        for module in (pcv, schema_check):
            for name, member in inspect.getmembers(module):
                if name.startswith("_") or not callable(member):
                    continue
                if inspect.getmodule(member) is not module:
                    continue  # skip re-exported stdlib/other-module symbols
                for prefix in _FORBIDDEN_CALLABLE_PREFIXES:
                    self.assertFalse(
                        name.startswith(prefix),
                        f"{module.__name__}.{name} looks like an activation/issuance callable "
                        f"(forbidden prefix {prefix!r}) -- SP-60 is development/conformance only",
                    )

    def test_no_fixture_declares_an_active_or_published_status(self) -> None:
        for kind in ("positive", "negative"):
            for path in sorted((CONTRACT_ROOT / "fixtures" / "v1" / kind).glob("*.json")):
                with path.open("r", encoding="utf-8") as handle:
                    text = handle.read()
                lowered = text.lower()
                for forbidden in _FORBIDDEN_STATUS_VALUES:
                    pattern = re.compile(r'"(status|publication_status)"\s*:\s*"' + forbidden + r'"')
                    self.assertIsNone(
                        pattern.search(lowered),
                        f"{path.relative_to(CONTRACT_ROOT)} declares a forbidden status {forbidden!r}",
                    )

    def test_policy_bundle_fixture_is_explicitly_marked_unpublished(self) -> None:
        bundle_fixture = CONTRACT_ROOT / "fixtures" / "v1" / "positive" / "pii-policy-bundle.valid.json"
        with bundle_fixture.open("r", encoding="utf-8") as handle:
            case = json.load(handle)
        status = case["instance"].get("publication_status")
        self.assertIsNotNone(status)
        self.assertNotIn(status, _FORBIDDEN_STATUS_VALUES)

    def test_no_real_looking_cloud_credential_env_reference(self) -> None:
        credential_pattern = re.compile(
            r"(AWS_SECRET_ACCESS_KEY|AKIA[0-9A-Z]{16}|-----BEGIN CERTIFICATE-----)"
        )
        for path in self._all_source_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertIsNone(
                credential_pattern.search(text),
                f"{path.relative_to(CONTRACT_ROOT)} appears to contain cloud credential material",
            )


if __name__ == "__main__":
    unittest.main()
