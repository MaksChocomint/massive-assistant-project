from datetime import datetime

from pydantic import BaseModel, Field


class CommandCreate(BaseModel):
    user_id: int = Field(gt=0, examples=[1])
    text: str = Field(min_length=1, max_length=300, examples=["поставь будильник"])


class ClarifyRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=200, examples=["на семь утра"])


class SlotValueRead(BaseModel):
    slot: str
    name: str
    value: str


class CommandRead(BaseModel):
    id: int
    user_id: int
    text: str
    intent: str
    intent_name: str
    confidence: float
    status: str
    clarifications: int
    slots: list[SlotValueRead]
    question: str | None = Field(
        description="Что спросить у пользователя, если не хватает параметров"
    )
    created_at: datetime
