import time
from dataclasses import dataclass, field
from typing import Protocol

from anthropic import Anthropic

from ticket_router.models import Category, LlmLabel, LlmResult, Urgency, Usage

SYSTEM_PROMPT = (
    "You route customer support tickets. Pick exactly one category, "
    "rate the urgency, and summarize the ticket in one short sentence."
)


class LlmError(RuntimeError): ...


class LlmTimeout(LlmError): ...


class LlmClassifier(Protocol):
    @property
    def model(self) -> str: ...

    def classify(self, text: str) -> LlmResult: ...


@dataclass(frozen=True)
class AnthropicClassifier:
    client: Anthropic
    model: str = "claude-haiku-5-5"

    def classify(self, text: str) -> LlmResult:
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
            output_format=LlmLabel,
            output_config={"effort": "low"},
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise LlmError(f"no label, stop_reason={response.stop_reason}")
        usage = Usage(response.usage.input_tokens, response.usage.output_tokens)
        return LlmResult(response.parsed_output, usage, self.model)


KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.BILLING: ("charge", "bill", "invoice", "price", "refund", "renew", "plan"),
    Category.BUG: ("crash", "error", "broken", "freez", "stuck"),
    Category.ACCOUNT: ("log in", "password", "email", "account", "profile"),
    Category.SHIPPING: ("parcel", "package", "deliver", "order", "box", "tracking"),
}


@dataclass(frozen=True)
class StubClassifier:
    """Deterministic offline stand-in. Token counts approximate a real Haiku call."""

    model: str = "stub-haiku"
    latency_s: float = 0.3

    def classify(self, text: str) -> LlmResult:
        time.sleep(self.latency_s)
        lowered = text.lower()
        category = next(
            (c for c, words in KEYWORDS.items() if any(w in lowered for w in words)),
            Category.FEATURE_REQUEST,
        )
        label = LlmLabel(category=category, urgency=Urgency.MEDIUM, summary=text[:80])
        return LlmResult(label, Usage(input_tokens=180 + len(text) // 4, output_tokens=45), self.model)


@dataclass
class FlakyClassifier:
    """Raises LlmTimeout on every n-th call, to put errors in the traces."""

    inner: LlmClassifier
    fail_every: int
    _calls: int = field(default=0, init=False)

    @property
    def model(self) -> str:
        return self.inner.model

    def classify(self, text: str) -> LlmResult:
        self._calls += 1
        if self._calls % self.fail_every == 0:
            raise LlmTimeout(f"injected timeout on call {self._calls}")
        return self.inner.classify(text)
