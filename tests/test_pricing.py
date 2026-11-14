import pytest

from ticket_router.models import Usage
from ticket_router.pricing import cost_of


def test_haiku_cost_per_token() -> None:
    cost = cost_of("claude-haiku-5-5", Usage(input_tokens=1_000, output_tokens=200))
    assert cost.input_usd == pytest.approx(0.0001)
    assert cost.output_usd == pytest.approx(0.0001)
    assert cost.total_usd == pytest.approx(0.0002)


def test_unknown_model_raises() -> None:
    with pytest.raises(KeyError):
        cost_of("gpt-unknown", Usage(input_tokens=1, output_tokens=1))
