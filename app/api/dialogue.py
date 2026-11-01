from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import ErrorResponse
from app.schemas.dialogue import DialogueAnswer, DialogueCreate, DialogueRead, ExecutionReceipt
from app.services import dialogue

router = APIRouter(prefix="/dialogues", tags=["Ассистивный диалог"])
DB = Annotated[Session, Depends(get_db)]
ERRORS = {code: {"model": ErrorResponse} for code in (400, 404, 409, 422, 503)}


@router.post("", status_code=201, summary="Начать диалог без выбора пользователя", responses=ERRORS)
def create(data: DialogueCreate, db: DB) -> DialogueRead:
    return dialogue.create(db, data.text)


@router.get("/{session_id}", summary="Состояние и текст для озвучивания", responses=ERRORS)
def read(session_id: int, db: DB) -> DialogueRead:
    return dialogue.read(db, session_id)


@router.post(
    "/{session_id}/answer", summary="Уточнение или подтверждение команды", responses=ERRORS
)
def answer(session_id: int, data: DialogueAnswer, db: DB) -> DialogueRead:
    return dialogue.answer(db, session_id, data.answer)


@router.post("/{session_id}/cancel", summary="Отменить до передачи исполнителю", responses=ERRORS)
def cancel(session_id: int, db: DB) -> DialogueRead:
    return dialogue.cancel(db, session_id)


@router.post(
    "/{session_id}/execution",
    summary="Квитанция внешнего исполнителя",
    description="Не выполняет действие. Принимает фактический результат от интеграции. "
    "Повтор одинаковой квитанции безопасен; подмена уже принятого результата запрещена.",
    responses=ERRORS,
)
def execution(session_id: int, data: ExecutionReceipt, db: DB) -> DialogueRead:
    return dialogue.acknowledge(db, session_id, data)
