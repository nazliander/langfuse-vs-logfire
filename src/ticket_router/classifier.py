from dataclasses import dataclass
from typing import Self

from scipy.sparse import spmatrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from ticket_router.models import Category


@dataclass(frozen=True)
class SklearnRouter:
    vectorizer: TfidfVectorizer
    model: LogisticRegression

    @classmethod
    def train(cls, texts: list[str], labels: list[Category]) -> Self:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        model = LogisticRegression(max_iter=1000, C=10.0)
        model.fit(vectorizer.fit_transform(texts), [str(label) for label in labels])
        return cls(vectorizer, model)

    def featurize(self, text: str) -> spmatrix:
        return self.vectorizer.transform([text])

    def predict(self, features: spmatrix) -> tuple[Category, float]:
        probabilities = self.model.predict_proba(features)[0]
        best = int(probabilities.argmax())
        return Category(self.model.classes_[best]), float(probabilities[best])
