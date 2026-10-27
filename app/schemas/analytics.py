from pydantic import BaseModel


class TopIntent(BaseModel):
    intent: str
    name: str
    commands: int
    completed: int
    success_rate: float


class StatusSummary(BaseModel):
    total: int
    by_status: dict[str, int]
    success_rate: float
    avg_clarifications: float


class DayCount(BaseModel):
    day: str
    commands: int


class ScenarioCount(BaseModel):
    scenario: str
    name: str
    utterances: int


class TrainResult(BaseModel):
    trained_on: int
    dev_accuracy: float
