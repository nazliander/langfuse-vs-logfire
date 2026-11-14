from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Category(StrEnum):
    BILLING = "billing"
    BUG = "bug"
    ACCOUNT = "account"
    SHIPPING = "shipping"
    FEATURE_REQUEST = "feature_request"


class Urgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Ticket(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: str
    text: str = Field(min_length=3, max_length=2000)


class LlmLabel(BaseModel):
    category: Category
    urgency: Urgency
    summary: str = Field(description="One short sentence.")


class Prediction(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: str
    category: Category
    confidence: float
    source: Literal["sklearn", "llm"]
    urgency: Urgency | None = None
    summary: str | None = None
    cost_usd: float = 0.0


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Cost:
    input_usd: float
    output_usd: float

    @property
    def total_usd(self) -> float:
        return self.input_usd + self.output_usd


@dataclass(frozen=True)
class LlmResult:
    label: LlmLabel
    usage: Usage
    model: str
