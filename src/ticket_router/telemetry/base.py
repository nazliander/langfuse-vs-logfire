from contextlib import AbstractContextManager
from typing import Any, Literal, Protocol

from anthropic import Anthropic

from ticket_router.models import Cost, Usage

ObservationKind = Literal["span", "generation"]


class Observation(Protocol):
    def set_output(self, output: Any) -> None: ...

    def set_attributes(self, attributes: dict[str, str | float | int | bool]) -> None: ...

    def set_usage(self, usage: Usage, cost: Cost) -> None: ...


class Telemetry(Protocol):
    """The one seam each backend implements, so both emit the same span tree."""

    def span(self, name: str, input: Any) -> AbstractContextManager[Observation]: ...

    def generation(self, name: str, model: str, input: Any) -> AbstractContextManager[Observation]: ...

    def instrument(self, client: Anthropic) -> Anthropic:
        """Hook the tool's own LLM integration into the client in native mode, else return it unchanged."""
        ...

    def flush(self) -> None: ...
