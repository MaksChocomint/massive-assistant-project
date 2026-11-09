from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.activity import ActivityPage, ActivityPhase, ActivitySummary
from app.services import activity

router = APIRouter(tags=["История и аналитика"])
DB = Annotated[Session, Depends(get_db)]
UserFilter = Annotated[int | None, Query(gt=0)]
DaysFilter = Annotated[int | None, Query(ge=1, le=365)]


@router.get("/activity", summary="Журнал команд, пользователей и квитанций")
def history(
    db: DB,
    user_id: UserFilter = None,
    days: DaysFilter = None,
    phase: ActivityPhase | None = None,
    search: Annotated[str | None, Query(max_length=300)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ActivityPage:
    return activity.history(db, user_id, days, phase, search, limit, offset)


@router.get("/analytics/activity", summary="Сводка по подтверждённому исполнению и пользователям")
def summary(db: DB, user_id: UserFilter = None, days: DaysFilter = None) -> ActivitySummary:
    return activity.summary(db, user_id, days)
