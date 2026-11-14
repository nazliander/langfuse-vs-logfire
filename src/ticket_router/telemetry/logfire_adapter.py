from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import logfire
from anthropic import Anthropic

from ticket_router.models import Cost, Usage


@dataclass(frozen=True)
class LogfireObservation:
    span: logfire.LogfireSpan
    record_usage: bool = True

    def set_output(self, output: Any) -> None:
        self.span.set_attribute("output", output)

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        self.span.set_attributes(attributes)

    def set_usage(self, usage: Usage, cost: Cost) -> None:
        if self.record_usage:
            self.span.set_attributes(
                {
                    "gen_ai.usage.input_tokens": usage.input_tokens,
                    "gen_ai.usage.output_tokens": usage.output_tokens,
                    "operation.cost": cost.total_usd,
                }
            )


@dataclass(frozen=True)
class LogfireTelemetry:
    instance: logfire.Logfire = field(default_factory=lambda: logfire.DEFAULT_LOGFIRE_INSTANCE)
    native: bool = False

    @contextmanager
    def _span(self, name: str, input: Any, record_usage: bool = True, **attributes: Any) -> Iterator[LogfireObservation]:
        with self.instance.span(name, _span_name=name, input=input, **attributes) as span:
            yield LogfireObservation(span, record_usage)

    def span(self, name: str, input: Any) -> Any:
        return self._span(name, input)

    def generation(self, name: str, model: str, input: Any) -> Any:
        if self.native:
            return self._span(name, input, record_usage=False)
        return self._span(
            name,
            input,
            **{"gen_ai.system": "anthropic", "gen_ai.operation.name": "chat", "gen_ai.request.model": model},
        )

    def instrument(self, client: Anthropic) -> Anthropic:
        if self.native:
            self.instance.instrument_anthropic(client)
        return client

    def flush(self) -> None:
        self.instance.force_flush()
