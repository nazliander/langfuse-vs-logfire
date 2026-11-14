from collections.abc import Mapping
from dataclasses import dataclass

from ticket_router.classifier import SklearnRouter
from ticket_router.llm import LlmClassifier
from ticket_router.models import Category, Prediction, Ticket
from ticket_router.pricing import cost_of
from ticket_router.telemetry.base import Telemetry


@dataclass(frozen=True)
class Router:
    sklearn: SklearnRouter
    llm: LlmClassifier
    telemetry: Telemetry
    threshold: float = 0.7

    def route(self, raw: Mapping[str, str]) -> Prediction:
        with self.telemetry.span("route_ticket", input=dict(raw)) as root:
            ticket = self._validate(raw)
            category, confidence = self._predict(ticket)
            prediction = (
                Prediction(ticket_id=ticket.ticket_id, category=category, confidence=confidence, source="sklearn")
                if confidence >= self.threshold
                else self._ask_llm(ticket, confidence)
            )
            root.set_output(prediction.model_dump(mode="json"))
            root.set_attributes({"route.source": prediction.source, "route.confidence": confidence})
            return prediction

    def _validate(self, raw: Mapping[str, str]) -> Ticket:
        with self.telemetry.span("validate_ticket", input=dict(raw)) as span:
            ticket = Ticket.model_validate(raw)
            span.set_output({"ticket_id": ticket.ticket_id, "chars": len(ticket.text)})
            return ticket

    def _predict(self, ticket: Ticket) -> tuple[Category, float]:
        with self.telemetry.span("featurize", input={"text": ticket.text}) as span:
            features = self.sklearn.featurize(ticket.text)
            span.set_output({"non_zero_features": int(features.nnz)})
        with self.telemetry.span("sklearn.predict", input={"non_zero_features": int(features.nnz)}) as span:
            category, confidence = self.sklearn.predict(features)
            span.set_output({"category": str(category), "confidence": confidence})
            span.set_attributes({"model.threshold": self.threshold})
            return category, confidence

    def _ask_llm(self, ticket: Ticket, sklearn_confidence: float) -> Prediction:
        with self.telemetry.generation("llm.classify", model=self.llm.model, input={"text": ticket.text}) as generation:
            result = self.llm.classify(ticket.text)
            cost = cost_of(result.model, result.usage)
            generation.set_output(result.label.model_dump(mode="json"))
            generation.set_usage(result.usage, cost)
            return Prediction(
                ticket_id=ticket.ticket_id,
                category=result.label.category,
                confidence=sklearn_confidence,
                source="llm",
                urgency=result.label.urgency,
                summary=result.label.summary,
                cost_usd=cost.total_usd,
            )
