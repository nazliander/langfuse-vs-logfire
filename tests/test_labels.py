import pytest

from ticket_router.labels import LabeledPrediction, accuracy_by_source, traceparent


def test_traceparent_is_w3c_format() -> None:
    assert traceparent("0af7651916cd43dd8448eb211c80319c", "b7ad6b7169203331") == (
        "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    )


def test_accuracy_by_source() -> None:
    rows = [
        LabeledPrediction("T-1", "sklearn", "billing", "billing"),
        LabeledPrediction("T-2", "sklearn", "bug", "account"),
        LabeledPrediction("T-3", "llm", "bug", "bug"),
    ]
    result = accuracy_by_source(rows)
    assert result["sklearn"] == (1, 2)
    assert result["llm"] == (1, 1)
    assert result["all"] == (2, 3)


def test_accuracy_needs_rows() -> None:
    with pytest.raises(ValueError):
        accuracy_by_source([])
