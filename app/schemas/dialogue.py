from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.commands import SlotValueRead

DialoguePhase = Literal[
    "clarifying",
    "awaiting_confirmation",
    "ready",
    "executed",
    "execution_failed",
    "cancelled",
    "failed",
]


class DialogueCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=300, examples=["поставь будильник"])


class DialogueAnswer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    answer: str = Field(min_length=1, max_length=200, examples=["на семь утра"])


class ExecutionReceipt(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    operation_id: str = Field(min_length=1, max_length=100, examples=["alarm-42"])
    success: bool
    message: str = Field(min_length=1, max_length=500, examples=["Будильник установлен на 07:00"])


class DialogueRead(BaseModel):
    id: int
    text: str
    phase: DialoguePhase
    intent: str
    intent_name: str
    confidence: float
    slots: list[SlotValueRead]
    question: str | None
    spoken_text: str
    ready_for_execution: bool
    execution_confirmed: bool
    operation_id: str | None
    execution_message: str | None
