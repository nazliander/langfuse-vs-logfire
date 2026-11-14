import csv
from pathlib import Path

from ticket_router.models import Category


def load_training_set(path: Path) -> tuple[list[str], list[Category]]:
    with path.open() as f:
        rows = list(csv.DictReader(f))
    return [r["text"] for r in rows], [Category(r["category"]) for r in rows]


def load_tickets(path: Path) -> list[dict[str, str]]:
    with path.open() as f:
        return list(csv.DictReader(f))
