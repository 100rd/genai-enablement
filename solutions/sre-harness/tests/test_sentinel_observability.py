"""Unit tests for AgentOps instrumentation of the Sentinel scan.

Mirrors ``test_observability.py``'s strategy: install an in-memory SDK provider,
run a scan, then assert the ``sentinel.*`` spans and stable attribute
names/values — plus the no-op default when no provider is wired.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from sre_harness.observability import attributes as attrs
from sre_harness.sentinel.scan import run_sentinel
from sre_harness.sentinel.state import (
    ErrorSignatureWindow,
    ExpiryItem,
    SaturationSample,
    SentinelState,
)


@pytest.fixture
def exporter() -> Iterator[InMemorySpanExporter]:
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))

    original = trace._TRACER_PROVIDER
    trace._TRACER_PROVIDER = provider
    try:
        yield memory
    finally:
        trace._TRACER_PROVIDER = original
        memory.clear()


def _by_name(spans: tuple[ReadableSpan, ...], name: str) -> list[ReadableSpan]:
    return [s for s in spans if s.name == name]


def _busy_state() -> SentinelState:
    return SentinelState(
        saturation_samples=(
            SaturationSample(resource="pvc", kind="disk", used=95.0, capacity=100.0),
        ),
        expiry_items=(ExpiryItem(name="api-tls", kind="cert", expires_in_days=3),),
        error_windows=(
            ErrorSignatureWindow(
                service="payments", baseline=frozenset({"E1"}), current=frozenset({"E1", "E_NEW"})
            ),
        ),
    )


@pytest.mark.unit
class TestSentinelInstrumentation:
    def test_scan_emits_parent_and_per_detector_spans(self, exporter: InMemorySpanExporter) -> None:
        run_sentinel(_busy_state())
        spans = exporter.get_finished_spans()

        assert len(_by_name(spans, "sentinel.scan")) == 1
        # One child span per default detector (saturation_expiry, new_error_signature).
        assert len(_by_name(spans, "sentinel.detector")) == 2

    def test_scan_span_carries_aggregate_attributes(self, exporter: InMemorySpanExporter) -> None:
        run_sentinel(_busy_state())
        (scan,) = _by_name(exporter.get_finished_spans(), "sentinel.scan")
        a = scan.attributes or {}

        assert a[attrs.SENTINEL_DETECTOR_COUNT] == 2
        assert a[attrs.SENTINEL_FINDING_COUNT] == 3
        assert a[attrs.SENTINEL_SUPPRESSED_COUNT] == 0
        assert a[attrs.SENTINEL_DETECTION_TIER] == "T1"
        assert a[attrs.SENTINEL_RECOMMENDATION_TIER] == "T2"
        assert a[attrs.SERVICE] == "sre-harness"

    def test_detector_spans_carry_id_and_count(self, exporter: InMemorySpanExporter) -> None:
        run_sentinel(_busy_state())
        detectors = _by_name(exporter.get_finished_spans(), "sentinel.detector")

        ids = {(s.attributes or {})[attrs.SENTINEL_DETECTOR_ID] for s in detectors}
        assert ids == {"detect_saturation_expiry", "detect_new_error_signature"}
        for s in detectors:
            assert attrs.SENTINEL_DETECTOR_FINDING_COUNT in (s.attributes or {})

    def test_detector_spans_are_children_of_the_scan_span(
        self, exporter: InMemorySpanExporter
    ) -> None:
        run_sentinel(_busy_state())
        spans = exporter.get_finished_spans()
        (scan,) = _by_name(spans, "sentinel.scan")
        detectors = _by_name(spans, "sentinel.detector")

        scan_span_id = scan.context.span_id
        for child in detectors:
            assert child.parent is not None
            assert child.parent.span_id == scan_span_id


@pytest.mark.unit
class TestSentinelNoOpDefault:
    def test_scan_runs_unchanged_with_no_provider(self) -> None:
        # No `exporter` fixture: tracing is the no-op default.
        report = run_sentinel(_busy_state())
        assert len(report.findings) == 3

    def test_scan_does_not_route_to_an_unwired_exporter(
        self, exporter: InMemorySpanExporter
    ) -> None:
        unwired = InMemorySpanExporter()
        run_sentinel(_busy_state())
        assert unwired.get_finished_spans() == ()
