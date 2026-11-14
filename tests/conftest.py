from pathlib import Path

import pytest

from ticket_router.classifier import SklearnRouter
from ticket_router.data import load_training_set

DATA = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="session")
def sklearn_router() -> SklearnRouter:
    texts, labels = load_training_set(DATA / "train.csv")
    return SklearnRouter.train(texts, labels)
