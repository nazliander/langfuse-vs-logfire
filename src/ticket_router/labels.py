from collections import defaultdict
from dataclasses import dataclass

Correct = int
Total = int


@dataclass(frozen=True)
class LabeledPrediction:
    ticket_id: str
    source: str
    predicted: str
    true_category: str

    @property
    def correct(self) -> bool:
        return self.predicted == self.true_category


def traceparent(trace_id: str, span_id: str) -> str:
    return f"00-{trace_id}-{span_id}-01"


def accuracy_by_source(rows: list[LabeledPrediction]) -> dict[str, tuple[Correct, Total]]:
    if not rows:
        raise ValueError("no labeled predictions")
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        for key in (row.source, "all"):
            counts[key][0] += row.correct
            counts[key][1] += 1
    return {key: (c, t) for key, (c, t) in counts.items()}
