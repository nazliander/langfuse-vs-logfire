from ticket_router.classifier import SklearnRouter
from ticket_router.models import Category


def test_clear_billing_ticket(sklearn_router: SklearnRouter) -> None:
    features = sklearn_router.featurize("I was charged twice, please refund me")
    category, confidence = sklearn_router.predict(features)
    assert category is Category.BILLING
    assert 0.0 < confidence <= 1.0
