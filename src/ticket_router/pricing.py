from dataclasses import dataclass

from ticket_router.models import Cost, Usage


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float


HAIKU = Price(input_per_mtok=0.10, output_per_mtok=0.50)
PRICES: dict[str, Price] = {"claude-haiku-5-5": HAIKU, "stub-haiku": HAIKU}


def cost_of(model: str, usage: Usage) -> Cost:
    price = PRICES[model]
    return Cost(
        input_usd=usage.input_tokens * price.input_per_mtok / 1_000_000,
        output_usd=usage.output_tokens * price.output_per_mtok / 1_000_000,
    )
