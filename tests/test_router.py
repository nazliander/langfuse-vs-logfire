import pytest
from pydantic import ValidationError

from ticket_router.classifier import SklearnRouter
from ticket_router.llm import FlakyClassifier, LlmTimeout, StubClassifier
from ticket_router.router import Router
from ticket_router.telemetry.recording import RecordingTelemetry

TICKET = {"ticket_id": "T-1", "text": "The app crashes when I open settings"}


def make_router(sklearn_router: SklearnRouter, threshold: float, llm=None) -> tuple[Router, RecordingTelemetry]:
    telemetry = RecordingTelemetry()
    router = Router(sklearn_router, llm or StubClassifier(latency_s=0), telemetry, threshold)
    return router, telemetry


def test_confident_ticket_skips_llm(sklearn_router: SklearnRouter) -> None:
    router, telemetry = make_router(sklearn_router, threshold=0.0)
    prediction = router.route(TICKET)
    assert prediction.source == "sklearn"
    assert prediction.cost_usd == 0
    root = telemetry.only_root()
    assert root.name == "route_ticket"
    assert [c.name for c in root.children] == ["validate_ticket", "featurize", "sklearn.predict"]
    assert root.output["source"] == "sklearn"


def test_unsure_ticket_falls_back_to_llm(sklearn_router: SklearnRouter) -> None:
    router, telemetry = make_router(sklearn_router, threshold=1.01)
    prediction = router.route(TICKET)
    assert prediction.source == "llm"
    assert prediction.cost_usd > 0
    generation = telemetry.only_root().children[-1]
    assert (generation.name, generation.kind) == ("llm.classify", "generation")
    assert generation.usage is not None and generation.usage.input_tokens > 0
    assert generation.cost is not None and generation.cost.total_usd == prediction.cost_usd


def test_invalid_ticket_records_error(sklearn_router: SklearnRouter) -> None:
    router, telemetry = make_router(sklearn_router, threshold=0.0)
    with pytest.raises(ValidationError):
        router.route({"ticket_id": "T-2", "text": ""})
    root = telemetry.only_root()
    assert root.error is not None
    assert [c.name for c in root.children] == ["validate_ticket"]
    assert root.children[0].error is not None


def test_llm_failure_records_error(sklearn_router: SklearnRouter) -> None:
    llm = FlakyClassifier(StubClassifier(latency_s=0), fail_every=1)
    router, telemetry = make_router(sklearn_router, threshold=1.01, llm=llm)
    with pytest.raises(LlmTimeout):
        router.route(TICKET)
    generation = telemetry.only_root().children[-1]
    assert generation.name == "llm.classify"
    assert generation.error is not None and "LlmTimeout" in generation.error
