from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Intent
from app.schemas.catalog import IntentCreate, IntentRead, IntentUpdate, ScenarioRead, SlotTypeRead
from app.schemas.common import ErrorResponse, Page
from app.schemas.users import UserCreate, UserRead
from app.services import catalog as service

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Не найдено"}}


def intent_read(intent: Intent, utterances: int = 0) -> IntentRead:
    return IntentRead(
        id=intent.id,
        code=intent.code,
        name=intent.name,
        scenario_id=intent.scenario_id,
        is_active=intent.is_active,
        utterances=utterances,
    )


@router.get("/intents", tags=["Намерения"], summary="Список намерений")
def list_intents(
    db: DB,
    scenario_id: int | None = None,
    search: Annotated[str | None, Query(description="Поиск по названию или коду")] = None,
    active: bool | None = None,
    sort: Annotated[
        Literal["id", "-id", "code", "-code", "name", "-name"],
        Query(description="id, code, name; «-» — по убыванию"),
    ] = "id",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[IntentRead]:
    rows, total = service.list_intents(db, scenario_id, search, active, sort, limit, offset)
    return Page(items=[intent_read(i, n) for i, n in rows], total=total, limit=limit, offset=offset)


@router.get("/intents/{intent_id}", tags=["Намерения"], responses=NOT_FOUND)
def get_intent(intent_id: int, db: DB) -> IntentRead:
    return intent_read(service.get_intent(db, intent_id))


@router.post(
    "/intents",
    tags=["Намерения"],
    status_code=status.HTTP_201_CREATED,
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "Код уже занят"}},
)
def create_intent(data: IntentCreate, db: DB) -> IntentRead:
    return intent_read(service.create_intent(db, data))


@router.patch("/intents/{intent_id}", tags=["Намерения"], responses=NOT_FOUND)
def update_intent(intent_id: int, data: IntentUpdate, db: DB) -> IntentRead:
    return intent_read(service.update_intent(db, intent_id, data))


@router.delete(
    "/intents/{intent_id}",
    tags=["Намерения"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "Есть команды или фразы"}},
)
def delete_intent(intent_id: int, db: DB) -> Response:
    service.delete_intent(db, intent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/scenarios", tags=["Справочники"], summary="Сценарии с числом намерений")
def list_scenarios(db: DB) -> list[ScenarioRead]:
    return [
        ScenarioRead(id=s.id, code=s.code, name=s.name, intents=n)
        for s, n in service.list_scenarios(db)
    ]


@router.get("/slot-types", tags=["Справочники"], summary="Типы параметров")
def list_slot_types(db: DB) -> list[SlotTypeRead]:
    return [SlotTypeRead.model_validate(s) for s in service.list_slot_types(db)]


@router.post(
    "/users",
    tags=["Пользователи"],
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "Логин занят"}},
)
def create_user(data: UserCreate, db: DB) -> UserRead:
    return UserRead.model_validate(service.create_user(db, data))


@router.get("/users", tags=["Пользователи"])
def list_users(db: DB) -> list[UserRead]:
    return [UserRead.model_validate(u) for u in service.list_users(db)]


@router.get("/users/{user_id}", tags=["Пользователи"], responses=NOT_FOUND)
def get_user(user_id: int, db: DB) -> UserRead:
    return UserRead.model_validate(service.get_user(db, user_id))
