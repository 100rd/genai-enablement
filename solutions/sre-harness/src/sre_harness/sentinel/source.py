"""Where a Sentinel scan gets its state snapshot (Stage 7, step 2).

Mirrors the :class:`~sre_harness.platform_graph.PlatformGraph` port: detectors
depend on the :class:`StateSource` *protocol*, not a concrete source, so the
CLI and tests run against a fixture/static source today while the live
observability adapters (Datadog / Loki / CloudWatch / Omniscience) are wired
up separately, once their query contracts are specified (see
``integrations/README.md``'s Sentinel section — deliberately not stubbed here
to avoid untested, speculative adapter code).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from sre_harness.sentinel.serialization import read_json_object, state_from_dict
from sre_harness.sentinel.state import SentinelState


@runtime_checkable
class StateSource(Protocol):
    """Read-only source of one :class:`~sre_harness.sentinel.state.SentinelState` snapshot."""

    def snapshot(self) -> SentinelState:
        """Return the current state snapshot."""
        ...


class StaticStateSource:
    """``StateSource`` wrapping an already-built ``SentinelState`` (tests, ad-hoc runs)."""

    def __init__(self, state: SentinelState) -> None:
        self._state = state

    def snapshot(self) -> SentinelState:
        return self._state


class JsonFileStateSource:
    """``StateSource`` backed by a JSON fixture/ConfigMap-mounted file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def snapshot(self) -> SentinelState:
        if not self._path.exists():
            raise ValueError(f"state file not found: {self._path}")
        payload = read_json_object(self._path)
        return state_from_dict(payload)


__all__ = [
    "JsonFileStateSource",
    "StateSource",
    "StaticStateSource",
]
