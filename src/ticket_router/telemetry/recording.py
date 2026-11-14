from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic

from ticket_router.models import Cost, Usage
from ticket_router.telemetry.base import ObservationKind


@dataclass
class RecordedObservation:
    name: str
    kind: ObservationKind
    input: Any
    output: Any = None
    attributes: dict[str, Any] = field(default_factory=dict)
    usage: Usage | None = None
    cost: Cost | None = None
    error: str | None = None
    children: list["RecordedObservation"] = field(default_factory=list)

    def set_output(self, output: Any) -> None:
        self.output = output

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        self.attributes.update(attributes)

    def set_usage(self, usage: Usage, cost: Cost) -> None:
        self.usage, self.cost = usage, cost


@dataclass
class RecordingTelemetry:
    roots: list[RecordedObservation] = field(default_factory=list)
    _stack: list[RecordedObservation] = field(default_factory=list)

    def only_root(self) -> RecordedObservation:
        (root,) = self.roots
        return root

    @contextmanager
    def _observe(self, name: str, kind: ObservationKind, input: Any) -> Iterator[RecordedObservation]:
        observation = RecordedObservation(name, kind, input)
        (self._stack[-1].children if self._stack else self.roots).append(observation)
        self._stack.append(observation)
        try:
            yield observation
        except Exception as error:
            observation.error = f"{type(error).__name__}: {error}"
            raise
        finally:
            self._stack.pop()

    def span(self, name: str, input: Any) -> Any:
        return self._observe(name, "span", input)

    def generation(self, name: str, model: str, input: Any) -> Any:
        return self._observe(name, "generation", input)

    def instrument(self, client: Anthropic) -> Anthropic:
        return client

    def flush(self) -> None: ...
