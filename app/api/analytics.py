from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.analytics import DayCount, ScenarioCount, StatusSummary, TopIntent, TrainResult
from app.schemas.common import ErrorResponse
from app.services import analytics
from app.services.nlu import train_nlu

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]


@router.get("/analytics/top-intents", tags=["Аналитика"], summary="Топ-N намерений по командам")
def top_intents(db: DB, limit: Annotated[int, Query(ge=1, le=50)] = 5) -> list[TopIntent]:
    return [TopIntent.model_validate(row) for row in analytics.top_intents(db, limit)]


@router.get("/analytics/status-summary", tags=["Аналитика"], summary="Команды по статусам")
def status_summary(db: DB) -> StatusSummary:
    return StatusSummary.model_validate(analytics.status_summary(db))


@router.get("/analytics/commands-by-day", tags=["Аналитика"], summary="Число команд по дням")
def commands_by_day(db: DB, days: Annotated[int, Query(ge=1, le=90)] = 7) -> list[DayCount]:
    return [DayCount.model_validate(row) for row in analytics.commands_by_day(db, days)]


@router.get("/analytics/dataset", tags=["Аналитика"], summary="Фразы датасета по сценариям")
def dataset(db: DB) -> list[ScenarioCount]:
    return [ScenarioCount.model_validate(row) for row in analytics.dataset_by_scenario(db)]


@router.post(
    "/nlu/train",
    tags=["Распознавание"],
    summary="Переобучить распознавание по БД",
    responses={503: {"model": ErrorResponse, "description": "Недостаточно данных для обучения"}},
)
def train(db: DB) -> TrainResult:
    nlu = train_nlu(db)
    return TrainResult(trained_on=nlu.trained_on, dev_accuracy=nlu.dev_accuracy(db))
