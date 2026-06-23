"""Unit tests for AgentOps — OpenTelemetry instrumentation of gate + eval.

Strategy: install an SDK ``TracerProvider`` with a ``SimpleSpanProcessor`` and an
``InMemorySpanExporter`` for the duration of a test, run the gate / eval, then
assert the emitted spans and our stable ``sre_harness.*`` attribute names/values.
A separate test asserts the **no-op default**: with no provider configured, the
same calls emit no spans and raise nothing.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from sre_harness.change_gate import ChangeRequest, Verdict, evaluate_change
from sre_harness.eval import change_gate_target, load_seed_scenarios, run_eval
from sre_harness.observability import attributes as attrs
from sre_harness.observability import configure_tracing, get_tracer, span, traced
from sre_harness.platform_graph import Entity, InMemoryPlatformGraph


@pytest.fixture
def exporter() -> Iterator[InMemorySpanExporter]:
    """Install an in-memory tracer provider; restore the no-op default after.

    OTel's global provider can only be set once per process, so we swap the
    module-global directly (and put the original back) instead of going through
    ``set_tracer_provider`` (which warns on override).
    """
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


def _gate_graph() -> InMemoryPlatformGraph:
    return InMemoryPlatformGraph(
        entities=[
            Entity(kind="StorageClass", name="gp3", cluster="prod-1"),
            Entity(kind="Namespace", name="payments", cluster="prod-1"),
        ]
    )


def _proceed_request() -> ChangeRequest:
    return ChangeRequest(
        service="payments-api",
        target_cluster_ids=["prod-1"],
        required_storageclasses={"gp3"},
    )


@pytest.mark.unit
class TestGateInstrumentation:
    def test_gate_emits_parent_and_per_check_spans(self, exporter: InMemorySpanExporter) -> None:
        evaluate_change(_proceed_request(), _gate_graph())
        spans = exporter.get_finished_spans()

        parents = _by_name(spans, "gate.evaluate")
        checks = _by_name(spans, "gate.check")
        assert len(parents) == 1
        # One child span per default check (storageclass, blast_radius, namespace).
        assert len(checks) == 3

    def test_gate_parent_span_carries_aggregate_attributes(
        self, exporter: InMemorySpanExporter
    ) -> None:
        evaluate_change(_proceed_request(), _gate_graph())
        (parent,) = _by_name(exporter.get_finished_spans(), "gate.evaluate")
        a = parent.attributes or {}

        assert a[attrs.GATE_VERDICT] == Verdict.PROCEED.value
        assert a[attrs.GATE_SERVICE] == "payments-api"
        assert a[attrs.GATE_TARGET_CLUSTER_COUNT] == 1
        assert a[attrs.GATE_CHECK_COUNT] == 3
        assert a[attrs.GATE_ANALYSIS_TIER] == "T1"
        assert a[attrs.GATE_RECOMMENDATION_TIER] == "T2"
        assert a[attrs.SERVICE] == "sre-harness"

    def test_gate_check_spans_carry_check_id_and_verdict(
        self, exporter: InMemorySpanExporter
    ) -> None:
        evaluate_change(_proceed_request(), _gate_graph())
        checks = _by_name(exporter.get_finished_spans(), "gate.check")

        check_ids = {(s.attributes or {})[attrs.GATE_CHECK_ID] for s in checks}
        assert check_ids == {"storageclass_present", "blast_radius", "namespace_present"}
        for s in checks:
            assert (s.attributes or {})[attrs.GATE_CHECK_VERDICT] == Verdict.PROCEED.value

    def test_check_spans_are_children_of_the_gate_span(
        self, exporter: InMemorySpanExporter
    ) -> None:
        evaluate_change(_proceed_request(), _gate_graph())
        spans = exporter.get_finished_spans()
        (parent,) = _by_name(spans, "gate.evaluate")
        checks = _by_name(spans, "gate.check")

        parent_span_id = parent.context.span_id
        for child in checks:
            assert child.parent is not None
            assert child.parent.span_id == parent_span_id


@pytest.mark.unit
class TestEvalInstrumentation:
    def test_eval_emits_suite_and_per_scenario_spans(self, exporter: InMemorySpanExporter) -> None:
        scenarios = load_seed_scenarios()
        run_eval(scenarios, change_gate_target)
        spans = exporter.get_finished_spans()

        suites = _by_name(spans, "eval.suite")
        scenario_spans = _by_name(spans, "eval.scenario")
        assert len(suites) == 1
        assert len(scenario_spans) == len(scenarios)

    def test_suite_span_carries_aggregate_attributes(self, exporter: InMemorySpanExporter) -> None:
        scenarios = load_seed_scenarios()
        summary = run_eval(scenarios, change_gate_target)
        (suite,) = _by_name(exporter.get_finished_spans(), "eval.suite")
        a = suite.attributes or {}

        assert a[attrs.EVAL_SCENARIO_COUNT] == len(scenarios)
        assert a[attrs.EVAL_PASSED_COUNT] == summary.passed
        assert a[attrs.EVAL_PASS_RATE] == summary.pass_rate

    def test_scenario_spans_carry_id_kind_and_score(self, exporter: InMemorySpanExporter) -> None:
        scenarios = load_seed_scenarios()
        run_eval(scenarios, change_gate_target)
        scenario_spans = _by_name(exporter.get_finished_spans(), "eval.scenario")

        ids = {(s.attributes or {})[attrs.EVAL_SCENARIO_ID] for s in scenario_spans}
        assert ids == {s.id for s in scenarios}
        for s in scenario_spans:
            a = s.attributes or {}
            assert attrs.EVAL_SCENARIO_KIND in a
            assert a[attrs.EVAL_SCORE_PASSED] is True  # the perfect seed target
            assert a[attrs.EVAL_SCORE] == 1.0


@pytest.mark.unit
class TestNoOpDefault:
    def test_gate_does_not_route_to_an_unwired_exporter(
        self, exporter: InMemorySpanExporter
    ) -> None:
        # Sanity on isolation: an exporter we never wire receives nothing.
        unwired = InMemorySpanExporter()
        evaluate_change(_proceed_request(), _gate_graph())
        assert unwired.get_finished_spans() == ()

    def test_facade_calls_are_safe_with_no_provider(self) -> None:
        # No provider installed in this test (no `exporter` fixture). The proxy
        # tracer is a no-op: opening spans and decorating must neither raise nor
        # produce real spans.
        tracer = get_tracer()
        assert tracer is not None

        with span("noop.parent", {attrs.GATE_VERDICT: "proceed"}) as s:
            # A non-recording span has an all-zero span context.
            assert s.get_span_context().span_id == 0

        @traced("noop.fn", {attrs.EVAL_SCENARIO_ID: "x"})
        def work() -> int:
            return 42

        assert work() == 42

    def test_gate_runs_unchanged_with_no_provider(self) -> None:
        # No `exporter` fixture: tracing is the no-op default. Behaviour must be
        # identical to an untraced run.
        result = evaluate_change(_proceed_request(), _gate_graph())
        assert result.verdict is Verdict.PROCEED
        assert len(result.check_results) == 3

    def test_configure_tracing_no_endpoint_is_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SRE_HARNESS_OTLP_ENDPOINT", raising=False)
        # No endpoint anywhere -> stays no-op, returns False, touches nothing.
        assert configure_tracing() is False


@pytest.mark.unit
class TestGenAiAliasMapping:
    def test_llm_token_attrs_mirror_to_genai_convention_names(
        self, exporter: InMemorySpanExporter
    ) -> None:
        # The token/cost scaffold: our stable names are kept AND additively
        # mirrored onto the (experimental) gen_ai.* convention names.
        with span(
            "llm.step",
            {
                attrs.LLM_INPUT_TOKENS: 100,
                attrs.LLM_OUTPUT_TOKENS: 20,
                attrs.LLM_COST_USD: 0.0012,
                attrs.LLM_MODEL: "claude-sonnet",
            },
        ):
            pass

        (s,) = _by_name(exporter.get_finished_spans(), "llm.step")
        a = s.attributes or {}
        # Stable names preserved.
        assert a[attrs.LLM_INPUT_TOKENS] == 100
        assert a[attrs.LLM_OUTPUT_TOKENS] == 20
        assert a[attrs.LLM_COST_USD] == pytest.approx(0.0012)
        # Safe GenAI aliases added.
        assert a["gen_ai.usage.input_tokens"] == 100
        assert a["gen_ai.usage.output_tokens"] == 20
        assert a["gen_ai.request.model"] == "claude-sonnet"
        # cost has no standardised gen_ai.* name -> not aliased.
        assert "gen_ai.usage.cost" not in a
