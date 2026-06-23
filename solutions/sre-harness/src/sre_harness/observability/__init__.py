"""AgentOps — OpenTelemetry instrumentation for the SRE harness (cross-cutting).

A thin tracing facade over OpenTelemetry plus a stable attribute schema, so the
gate and the eval harness emit spans without the rest of the codebase touching
OTel directly. **No-op by default**: with no provider configured, every span is
a cheap no-op (zero behaviour change).

Public surface:

- :func:`span` / :func:`traced` / :func:`get_tracer` / :func:`set_attributes` —
  the facade (:mod:`.tracer`).
- :func:`configure_tracing` — optional OTLP-export wiring from the environment.
- The ``sre_harness.*`` attribute-name constants (:mod:`.attributes`).

See ``docs/autonomous-sre-harness-plan.md`` (AGENTOPS / cross-cutting row) and
the README "Observability / AgentOps" section.
"""

from sre_harness.observability import attributes
from sre_harness.observability.tracer import (
    DEFAULT_SERVICE,
    ENV_OTLP_ENDPOINT,
    INSTRUMENTATION_NAME,
    configure_tracing,
    get_tracer,
    set_attributes,
    span,
    traced,
)

__all__ = [
    "DEFAULT_SERVICE",
    "ENV_OTLP_ENDPOINT",
    "INSTRUMENTATION_NAME",
    "attributes",
    "configure_tracing",
    "get_tracer",
    "set_attributes",
    "span",
    "traced",
]
