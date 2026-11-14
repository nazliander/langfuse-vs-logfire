"""In native mode the adapters leave tokens and cost to each tool's own LLM integration."""

import uuid

from anthropic import Anthropic
from langfuse import Langfuse
from logfire.testing import CaptureLogfire
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ticket_router.models import Cost, Usage
from ticket_router.telemetry.langfuse_adapter import LangfuseTelemetry
from ticket_router.telemetry.logfire_adapter import LogfireTelemetry

USAGE, COST = Usage(10, 5), Cost(0.1, 0.2)


def test_logfire_native_generation_has_no_manual_usage(capfire: CaptureLogfire) -> None:
    with LogfireTelemetry(native=True).generation("llm.classify", "claude-haiku-5-5", {"text": "x"}) as generation:
        generation.set_usage(USAGE, COST)
    (span,) = [s for s in capfire.exporter.exported_spans if s.attributes.get("logfire.span_type") == "span"]
    assert not any(key.startswith("gen_ai.") or key == "operation.cost" for key in span.attributes)


def test_langfuse_native_routes_anthropic_spans_to_langfuse() -> None:
    provider = TracerProvider()
    client = Langfuse(
        public_key=f"pk-lf-{uuid.uuid4()}",
        secret_key="sk-lf-test",
        base_url="http://localhost:1",
        span_exporter=InMemorySpanExporter(),
        tracer_provider=provider,
    )
    telemetry = LangfuseTelemetry(client, native=True, tracer_provider=provider)
    instrumented = telemetry.instrument(Anthropic(api_key="test", open_telemetry=False))
    assert instrumented.open_telemetry["tracer_provider"] is provider
    assert instrumented.open_telemetry["traces"]["enabled"] is True
    assert instrumented.open_telemetry["traces"]["content_mode"] == "content"


def test_manual_mode_keeps_client_unchanged() -> None:
    anthropic = Anthropic(api_key="test", open_telemetry=False)
    assert LogfireTelemetry().instrument(anthropic) is anthropic
