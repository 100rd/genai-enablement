"""Unit tests for the Sentinel ``FindingStore`` port (Stage 7, step 2).

``run_sentinel`` dedupes against a caller-supplied ``open_findings`` sequence
but has no memory of its own (see ``sre_harness.sentinel.scan``). A
``FindingStore`` gives a periodic runner that memory across scans. Mirrors the
``PlatformGraph`` port test style: an in-memory fake plus a file-backed
adapter, exercised the same way.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from sre_harness.sentinel.finding import Finding, Severity
from sre_harness.sentinel.store import (
    FindingStore,
    InMemoryFindingStore,
    JsonFileFindingStore,
)


def _finding(fingerprint: str = "pvc-payments") -> Finding:
    return Finding(
        detector_id="saturation_expiry",
        kind="saturation",
        severity=Severity.HIGH,
        confidence=0.9,
        fingerprint=fingerprint,
        rationale="disk at 95% of capacity",
    )


@pytest.mark.unit
class TestProtocolConformance:
    def test_in_memory_is_a_finding_store(self) -> None:
        assert isinstance(InMemoryFindingStore(), FindingStore)

    def test_json_file_is_a_finding_store(self, tmp_path: Path) -> None:
        assert isinstance(JsonFileFindingStore(tmp_path / "open.json"), FindingStore)


@pytest.mark.unit
class TestInMemoryFindingStore:
    def test_defaults_to_empty(self) -> None:
        assert InMemoryFindingStore().load_open() == ()

    def test_constructor_seeds_open_findings(self) -> None:
        store = InMemoryFindingStore([_finding()])

        assert store.load_open() == (_finding(),)

    def test_save_replaces_the_open_set(self) -> None:
        store = InMemoryFindingStore([_finding("a")])

        store.save_open([_finding("b")])

        assert store.load_open() == (_finding("b"),)

    def test_save_empty_clears_the_open_set(self) -> None:
        store = InMemoryFindingStore([_finding()])

        store.save_open([])

        assert store.load_open() == ()


@pytest.mark.unit
class TestJsonFileFindingStoreRoundTrip:
    def test_missing_file_loads_as_empty(self, tmp_path: Path) -> None:
        store = JsonFileFindingStore(tmp_path / "does-not-exist.json")

        assert store.load_open() == ()

    def test_save_then_load_round_trips(self, tmp_path: Path) -> None:
        store = JsonFileFindingStore(tmp_path / "open.json")
        findings = (_finding("a"), _finding("b"))

        store.save_open(findings)

        assert store.load_open() == findings

    def test_save_overwrites_rather_than_appends(self, tmp_path: Path) -> None:
        store = JsonFileFindingStore(tmp_path / "open.json")

        store.save_open([_finding("a")])
        store.save_open([_finding("b")])

        assert store.load_open() == (_finding("b"),)

    def test_save_empty_writes_a_readable_empty_set(self, tmp_path: Path) -> None:
        store = JsonFileFindingStore(tmp_path / "open.json")

        store.save_open([])

        assert store.load_open() == ()

    def test_save_creates_the_file_with_restrictive_permissions(self, tmp_path: Path) -> None:
        # Contents are operator-controlled monitoring metadata, not secrets,
        # but there is no reason for it to be world-readable either — the
        # atomic temp-file write (tempfile.mkstemp) already yields 0600.
        path = tmp_path / "open.json"
        JsonFileFindingStore(path).save_open([_finding()])

        assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.unit
class TestJsonFileFindingStoreErrors:
    def test_invalid_json_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "open.json"
        path.write_text("{not json", encoding="utf-8")

        with pytest.raises(ValueError, match="not valid JSON"):
            JsonFileFindingStore(path).load_open()

    def test_non_object_payload_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "open.json"
        path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

        with pytest.raises(ValueError, match="object"):
            JsonFileFindingStore(path).load_open()

    def test_open_findings_not_a_list_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "open.json"
        path.write_text(json.dumps({"open_findings": "nope"}), encoding="utf-8")

        with pytest.raises(ValueError, match="open_findings"):
            JsonFileFindingStore(path).load_open()

    def test_directory_path_is_rejected_on_load(self, tmp_path: Path) -> None:
        directory = tmp_path / "open-as-dir"
        directory.mkdir()

        with pytest.raises(ValueError, match="not a file"):
            JsonFileFindingStore(directory).load_open()

    def test_directory_path_is_rejected_on_save(self, tmp_path: Path) -> None:
        directory = tmp_path / "open-as-dir"
        directory.mkdir()

        with pytest.raises(ValueError, match="not a file"):
            JsonFileFindingStore(directory).save_open([_finding()])

    def test_missing_parent_directory_is_rejected_on_save(self, tmp_path: Path) -> None:
        path = tmp_path / "does-not-exist" / "open.json"

        with pytest.raises(OSError):
            JsonFileFindingStore(path).save_open([_finding()])


@pytest.mark.unit
class TestJsonFileFindingStoreAtomicity:
    def test_failed_write_does_not_corrupt_the_existing_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "open.json"
        store = JsonFileFindingStore(path)
        store.save_open([_finding("a")])
        original = path.read_text(encoding="utf-8")

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("simulated crash mid-write")

        monkeypatch.setattr("sre_harness.sentinel.store.os.replace", _boom)

        with pytest.raises(OSError, match="simulated crash mid-write"):
            store.save_open([_finding("b")])

        assert path.read_text(encoding="utf-8") == original

    def test_failed_write_leaves_no_temp_file_behind(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "open.json"

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("simulated crash mid-write")

        monkeypatch.setattr("sre_harness.sentinel.store.os.replace", _boom)

        with pytest.raises(OSError):
            JsonFileFindingStore(path).save_open([_finding()])

        assert list(tmp_path.iterdir()) == []
