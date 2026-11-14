"""Both adapters must emit the same span tree for the same ticket."""

import uuid

import pytest
from langfuse import Langfuse
from logfire.testing import CaptureLogfire
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from ticket_router.classifier import SklearnRouter
from ticket_router.llm import FlakyClassifier, StubClassifier
from ticket_router.router import Router
from ticket_router.telemetry.langfuse_adapter import LangfuseTelemetry
from ticket_router.telemetry.logfire_adapter import LogfireTelemetry

TICKETS = [
    {"ticket_id": "T-1", "text": "The app crashes when I open settings"},
    {"ticket_id": "T-2", "text": ""},
    {"ticket_id": "T-3", "text": "Where is my package"},
]


def run_all(router: Router) -> None:
    for ticket in TICKETS:
        try:
            router.route(ticket)
        except Exception:
            pass


def shape(spans: list[ReadableSpan]) -> list[tuple[str, bool]]:
    return sorted((s.name, s.status.status_code is StatusCode.ERROR) for s in spans)


@pytest.fixture
def langfuse_spans(sklearn_router: SklearnRouter) -> list[ReadableSpan]:
    exporter = InMemorySpanExporter()
    client = Langfuse(
        public_key=f"pk-lf-{uuid.uuid4()}",
        secret_key="sk-lf-test",
        base_url="http://localhost:1",
        span_exporter=exporter,
        tracer_provider=TracerProvider(),
    )
    llm = FlakyClassifier(StubClassifier(latency_s=0), fail_every=2)
    run_all(Router(sklearn_router, llm, LangfuseTelemetry(client), threshold=1.01))
    client.flush()
    return list(exporter.get_finished_spans())


def test_same_span_tree(sklearn_router: SklearnRouter, capfire: CaptureLogfire, langfuse_spans: list[ReadableSpan]) -> None:
    llm = FlakyClassifier(StubClassifier(latency_s=0), fail_every=2)
    run_all(Router(sklearn_router, llm, LogfireTelemetry(), threshold=1.01))
    logfire_spans = [s for s in capfire.exporter.exported_spans if s.attributes.get("logfire.span_type") == "span"]
    assert shape(logfire_spans) == shape(langfuse_spans)


def test_errors_are_marked(langfuse_spans: list[ReadableSpan]) -> None:
    errored = {name for name, is_error in shape(langfuse_spans) if is_error}
    assert errored == {"route_ticket", "validate_ticket", "llm.classify"}
