from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.commands import SlotValueRead
from app.schemas.dialogue import DialoguePhase
from app.schemas.users import UserRead

ActivityPhase = DialoguePhase | Literal["legacy"]


class ActivityItem(BaseModel):
    id: int
    text: str
    created_at: datetime
    user: UserRead
    intent: str
    intent_name: str
    confidence: float
    command_status: str
    phase: ActivityPhase
    clarifications: int
    slots: list[SlotValueRead]
    execution_confirmed: bool
    execution_message: str | None
    execution_recorded_at: datetime | None
    operation_id: str | None


class ActivityPage(BaseModel):
    items: list[ActivityItem]
    total: int
    limit: int
    offset: int


class IntentActivity(BaseModel):
    intent: str
    name: str
    commands: int
    executed: int


class UserActivity(BaseModel):
    user_id: int
    username: str
    name: str
    commands: int
    executed: int


class DayActivity(BaseModel):
    day: str
    commands: int
    executed: int


class ActivitySummary(BaseModel):
    total: int
    by_phase: dict[str, int]
    execution_success_rate: float | None
    avg_clarifications: float
    top_intents: list[IntentActivity]
    by_user: list[UserActivity]
    by_day: list[DayActivity]
