"""A thin tracing facade over OpenTelemetry (AgentOps).

Design goals (from ``docs/autonomous-sre-harness-plan.md`` cross-cutting row):

- **No-op by default.** When no ``TracerProvider`` is configured, the OTel API
  hands back a proxy that delegates to a no-op tracer: every span here becomes a
  cheap, side-effect-free object. Instrumentation is therefore zero
  behaviour-change and near-zero cost when tracing is off — nothing to import,
  configure, or run (no collector required).
- **Stable attribute names only at call sites.** Call sites pass our own
  ``sre_harness.*`` names (see :mod:`.attributes`); :func:`span` additionally
  mirrors a *small, safe* subset onto the experimental OTel GenAI names so an
  OTel-native backend still sees them — but the unstable ``gen_ai.*`` strings
  never appear in harness code.
- **Tiny surface.** :func:`get_tracer`, the :func:`span` context manager, and
  the :func:`traced` decorator are all the harness needs. :func:`configure_tracing`
  is an *optional* convenience for wiring an OTLP exporter from the environment;
  it is never required and is safe to skip.

The hot path imports only ``opentelemetry-api``: the SDK (``opentelemetry-sdk``)
and the OTLP exporter are imported lazily inside :func:`configure_tracing`, so
the no-op default never touches them even though they are installed.
"""

from __future__ import annotations

import functools
import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import Any, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Span, Tracer
from opentelemetry.util.types import AttributeValue

from sre_harness.observability.attributes import _GEN_AI_CONVENTION_ALIASES, SERVICE

#: Instrumentation-scope name for every tracer the harness creates.
INSTRUMENTATION_NAME = "sre_harness"

#: Default logical service value stamped on root spans.
DEFAULT_SERVICE = "sre-harness"

#: Env var that opts into OTLP export via :func:`configure_tracing`.
ENV_OTLP_ENDPOINT = "SRE_HARNESS_OTLP_ENDPOINT"

F = TypeVar("F", bound=Callable[..., Any])


def get_tracer() -> Tracer:
    """Return the harness tracer.

    Resolves through the global OTel API, so with no provider configured this is
    the no-op tracer (zero behaviour change, cheap). Versioned with the package
    so spans carry the instrumentation-scope version.
    """
    from sre_harness import __version__

    return trace.get_tracer(INSTRUMENTATION_NAME, __version__)


@contextmanager
def span(
    name: str,
    attributes: Mapping[str, AttributeValue] | None = None,
    *,
    service: str | None = None,
) -> Iterator[Span]:
    """Start a span as the current span, yielding it for the ``with`` block.

    ``attributes`` are our stable ``sre_harness.*`` names; a small safe subset is
    additionally mirrored onto the OTel GenAI convention names. When tracing is
    not configured the underlying span is a no-op and this is essentially free.
    """
    merged = _with_genai_aliases(attributes)
    if service is not None:
        merged[SERVICE] = service
    with get_tracer().start_as_current_span(name, attributes=merged or None) as current:
        yield current


def traced(
    name: str,
    attributes: Mapping[str, AttributeValue] | None = None,
    *,
    service: str | None = None,
) -> Callable[[F], F]:
    """Decorator wrapping a function call in a :func:`span`.

    Equivalent to opening ``span(name, attributes, service=service)`` around each
    call. No-op-cheap when tracing is off, like :func:`span`.
    """

    def decorate(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with span(name, attributes, service=service):
                return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorate


def set_attributes(current: Span, attributes: Mapping[str, AttributeValue]) -> None:
    """Set our stable attributes (plus safe GenAI aliases) on an existing span.

    Useful when values are only known partway through a span's lifetime (e.g. the
    aggregate verdict computed inside the gate span). A no-op span ignores these.
    """
    for key, value in _with_genai_aliases(attributes).items():
        current.set_attribute(key, value)


def configure_tracing(
    *,
    service: str = DEFAULT_SERVICE,
    endpoint: str | None = None,
) -> bool:
    """Optionally wire a real OTel SDK provider with an OTLP exporter.

    Reads ``endpoint`` (or :data:`ENV_OTLP_ENDPOINT`); if neither is set, tracing
    stays in its no-op default and this returns ``False`` without touching global
    state. When an endpoint is present it installs an SDK ``TracerProvider`` with
    a batch OTLP/HTTP span exporter and returns ``True``.

    Importing this module never requires the SDK or the OTLP exporter package;
    they are imported here, only on the opt-in path. A running collector is not
    required for the no-op default — only for actual export.
    """
    target = endpoint or os.environ.get(ENV_OTLP_ENDPOINT)
    if not target:
        return False

    # Lazy SDK imports: keep the hot path API-only. The OTLP exporter is an
    # optional extra (``opentelemetry-exporter-otlp-proto-http``); it is not a
    # declared dependency, so a clear error beats a raw ImportError if it is
    # absent. The no-op default never needs it.
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found]
            OTLPSpanExporter,
        )
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "OTLP export requires the optional dependency "
            "'opentelemetry-exporter-otlp-proto-http'; install it to enable export, "
            "or leave tracing unconfigured for the no-op default."
        ) from exc

    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=target)))
    trace.set_tracer_provider(provider)
    return True


def _with_genai_aliases(
    attributes: Mapping[str, AttributeValue] | None,
) -> dict[str, AttributeValue]:
    """Copy ``attributes`` and additively mirror the safe GenAI-convention names.

    The original stable keys are always kept; aliases are *added*, never
    substituted, so an OTel-native backend sees both. Returns a fresh dict
    (immutable-friendly: never mutates the caller's mapping).
    """
    if not attributes:
        return {}
    merged: dict[str, AttributeValue] = dict(attributes)
    for stable_key, genai_key in _GEN_AI_CONVENTION_ALIASES.items():
        if stable_key in merged:
            merged[genai_key] = merged[stable_key]
    return merged


__all__ = [
    "DEFAULT_SERVICE",
    "ENV_OTLP_ENDPOINT",
    "INSTRUMENTATION_NAME",
    "configure_tracing",
    "get_tracer",
    "set_attributes",
    "span",
    "traced",
]
