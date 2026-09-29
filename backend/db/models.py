from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class IntentType(str, Enum):
    expense_concern = "expense_concern"
    loan_inquiry = "loan_inquiry"
    fraud_alert = "fraud_alert"
    investment_query = "investment_query"
    budget_planning = "budget_planning"
    general_question = "general_question"


class TransactionCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    category: str = Field(default="other", min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    date: datetime = Field(default_factory=utc_now)
    merchant: Optional[str] = Field(default=None, max_length=120)
    transaction_type: Literal["debit", "credit"] = "debit"
    tags: List[str] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        return value.strip().lower() or "other"


class Transaction(TransactionCreate):
    pass


class GoalCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    target_amount: float = Field(gt=0)
    current_amount: float = Field(default=0, ge=0)
    deadline: Optional[datetime] = None


class GoalProgressUpdate(BaseModel):
    current_amount: float = Field(ge=0)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return email


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=3, max_length=2000)


class Sentiment(BaseModel):
    sentiment: str
    confidence: float
    urgency: str


class ChatResponse(BaseModel):
    intent: IntentType
    confidence: float
    entities: Dict[str, Any]
    sentiment: Sentiment
    response_text: str
    chart_data: Optional[Dict[str, Any]] = None
    alerts: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
