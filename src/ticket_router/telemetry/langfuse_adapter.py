from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic
from langfuse import Langfuse, LangfuseGeneration, LangfuseSpan
from opentelemetry.sdk.trace import TracerProvider

from ticket_router.models import Cost, Usage
from ticket_router.telemetry.base import ObservationKind


@dataclass(frozen=True)
class LangfuseObservation:
    observation: LangfuseSpan | LangfuseGeneration
    record_usage: bool = True

    def set_output(self, output: Any) -> None:
        self.observation.update(output=output)

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        self.observation.update(metadata=attributes)

    def set_usage(self, usage: Usage, cost: Cost) -> None:
        if self.record_usage:
            self.observation.update(
                usage_details={"input": usage.input_tokens, "output": usage.output_tokens},
                cost_details={"input": cost.input_usd, "output": cost.output_usd},
            )


@dataclass(frozen=True)
class LangfuseTelemetry:
    client: Langfuse
    native: bool = False
    tracer_provider: TracerProvider | None = None

    def __post_init__(self) -> None:
        if self.native and self.tracer_provider is None:
            raise ValueError("native mode needs the TracerProvider given to Langfuse")

    @contextmanager
    def _observe(self, name: str, kind: ObservationKind, input: Any, model: str | None = None) -> Iterator[LangfuseObservation]:
        with self.client.start_as_current_observation(name=name, as_type=kind, input=input, model=model) as observation:
            yield LangfuseObservation(observation, record_usage=not self.native)

    def span(self, name: str, input: Any) -> Any:
        return self._observe(name, "span", input)

    def generation(self, name: str, model: str, input: Any) -> Any:
        if self.native:
            return self._observe(name, "span", input)
        return self._observe(name, "generation", input, model)

    def instrument(self, client: Anthropic) -> Anthropic:
        if not self.native:
            return client
        return client.with_options(
            open_telemetry={
                "tracer_provider": self.tracer_provider,
                "traces": {"enabled": True, "content_mode": "content"},
            }
        )

    def flush(self) -> None:
        self.client.flush()
