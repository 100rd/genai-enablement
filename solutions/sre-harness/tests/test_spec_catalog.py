"""Documentation-boundary probes for legacy Track-B surfaces formalized as SPECs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _assert_documented(spec_name: str, manifest_name: str, incomplete_phrase: str) -> None:
    spec_path = ROOT / "docs/specs" / spec_name
    spec = spec_path.read_text(encoding="utf-8")
    status = (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/implementation-roadmap.md").read_text(encoding="utf-8")
    harness_readme = (ROOT / "solutions/sre-harness/README.md").read_text(encoding="utf-8")

    assert "**Specification type:** Capability SPEC" in spec
    assert "**Evidence scope:** `local-portable-only`" in spec
    assert "**Operational state:** `incomplete`" in spec
    assert "**Authority:** `non-authorizing`" in spec
    assert f"spec-traceability/{manifest_name}" in spec
    assert f"solutions/sre-harness/spec-traceability/{manifest_name}" in status
    assert f"specs/{spec_name}" in roadmap
    assert f"spec-traceability/{manifest_name}" in harness_readme
    assert incomplete_phrase in spec


def test_b0_spec_is_discoverable_and_non_authorizing() -> None:
    _assert_documented(
        "SPEC-B0-offline-eval-harness.md",
        "SPEC-B0.json",
        "B0 remains operationally incomplete",
    )


def test_b7_core_spec_is_discoverable_and_non_authorizing() -> None:
    _assert_documented(
        "SPEC-B7-core-sentinel-runtime-contract.md",
        "SPEC-B7-CORE.json",
        "B7 core remains operationally incomplete",
    )


def test_b7_new_signature_spec_is_discoverable_and_non_authorizing() -> None:
    _assert_documented(
        "SPEC-B7-new-error-signature-detector.md",
        "SPEC-B7-NES.json",
        "B7-NES remains operationally incomplete",
    )


def test_b7_saturation_spec_is_discoverable_and_non_authorizing() -> None:
    _assert_documented(
        "SPEC-B7-saturation-expiry-detector.md",
        "SPEC-B7-SAT.json",
        "B7-SAT remains operationally incomplete",
    )
