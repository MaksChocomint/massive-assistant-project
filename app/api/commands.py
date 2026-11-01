from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Command, Intent
from app.schemas.commands import ClarifyRequest, CommandCreate, CommandRead, SlotValueRead
from app.schemas.common import ErrorResponse, Page
from app.services import commands as service

router = APIRouter(prefix="/commands", tags=["Команды"])
CommandStatus = Literal["needs_clarification", "completed", "cancelled", "failed"]
DB = Annotated[Session, Depends(get_db)]
ERRORS = {
    400: {"model": ErrorResponse, "description": "Команда не распознана или ответ не подходит"},
    404: {"model": ErrorResponse, "description": "Команда или пользователь не найдены"},
    409: {"model": ErrorResponse, "description": "Действие недоступно в текущем статусе"},
    503: {"model": ErrorResponse, "description": "Недостаточно обучающих данных"},
}


def to_read(db: Session, command: Command) -> CommandRead:
    intent = db.get(Intent, command.intent_id)
    assert intent is not None
    return CommandRead(
        id=command.id,
        user_id=command.user_id,
        text=command.text,
        intent=intent.code,
        intent_name=intent.name,
        confidence=command.confidence,
        status=command.status,
        clarifications=command.clarifications,
        slots=[
            SlotValueRead(slot=s.slot_type.code, name=s.slot_type.name, value=s.value)
            for s in command.slots
        ],
        question=service.next_question(db, command),
        created_at=command.created_at,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Отправить команду ассистенту",
    description="Определяет намерение и параметры. Если параметров не хватает, "
    "команда получает статус needs_clarification и вопрос в поле question.",
    responses=ERRORS,
)
def create_command(data: CommandCreate, db: DB) -> CommandRead:
    return to_read(db, service.create_command(db, data.user_id, data.text))


@router.get("", summary="Список команд с фильтрами и пагинацией")
def list_commands(
    db: DB,
    status_filter: Annotated[CommandStatus | None, Query(alias="status")] = None,
    user_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[CommandRead]:
    items, total = service.list_commands(db, status_filter, user_id, limit, offset)
    return Page(items=[to_read(db, c) for c in items], total=total, limit=limit, offset=offset)


@router.get("/{command_id}", summary="Получить команду", responses=ERRORS)
def get_command(command_id: int, db: DB) -> CommandRead:
    return to_read(db, service.get_command(db, command_id))


@router.post(
    "/{command_id}/clarify",
    summary="Ответить на уточняющий вопрос",
    description="Заполняет первый недостающий параметр. Для времени и даты ответ "
    "проверяется на формат (иначе 400). После 3 неудачных попыток — статус failed.",
    responses={**ERRORS, 400: {"model": ErrorResponse, "description": "Ответ не подходит"}},
)
def clarify_command(command_id: int, data: ClarifyRequest, db: DB) -> CommandRead:
    return to_read(db, service.clarify_command(db, command_id, data.answer))


@router.post("/{command_id}/cancel", summary="Отменить команду", responses=ERRORS)
def cancel_command(command_id: int, db: DB) -> CommandRead:
    return to_read(db, service.cancel_command(db, command_id))
