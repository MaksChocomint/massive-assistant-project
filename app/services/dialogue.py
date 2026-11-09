"""Невизуальный сценарий: уточнение → проговаривание → подтверждение → квитанция.

Этот слой не управляет устройствами. Успех внешнего действия сообщается только
после отдельной квитанции исполнителя, а не после заполнения параметров.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, BusinessError, ConflictError, NotFoundError
from app.models import Command, DialogueSession
from app.schemas.commands import SlotValueRead
from app.schemas.dialogue import DialogueRead, ExecutionReceipt
from app.schemas.users import UserRead
from app.services import commands
from app.services.nlu import normalize
from app.services.profiles import ensure_owner

YES = {"да", "подтверждаю", "верно", "правильно", "все верно", "все правильно", "согласен", "ага"}
NO = {"нет", "неверно", "неправильно", "не то", "ошибка", "отмена", "отмени"}


def _get(db: Session, session_id: int) -> DialogueSession:
    session = db.get(DialogueSession, session_id)
    if session is None:
        raise NotFoundError(f"Диалог {session_id} не найден")
    return session


def _advance(session: DialogueSession, command: Command) -> None:
    if session.phase == "clarifying":
        session.phase = {
            "completed": "awaiting_confirmation",
            "failed": "failed",
            "cancelled": "cancelled",
        }.get(command.status, "clarifying")


def describe(db: Session, session: DialogueSession) -> DialogueRead:
    command = commands.get_command(db, session.command_id)
    slots = [
        SlotValueRead(slot=s.slot_type.code, name=s.slot_type.name, value=s.value)
        for s in command.slots
    ]
    summary = command.intent.name + "."
    if slots:
        summary += " " + ". ".join(f"{s.name}: {s.value}" for s in slots) + "."
    question = None
    if session.phase == "clarifying":
        question = commands.next_question(db, command)
        spoken = question or "Уточните команду."
    elif session.phase == "awaiting_confirmation":
        question = "Всё верно? Скажите «да» или «нет»."
        spoken = "Я понял: " + summary + " " + question
    elif session.phase == "ready":
        spoken = "Вы подтвердили команду. " + summary
    elif session.phase == "executed":
        spoken = "Исполнитель подтвердил выполнение: " + (session.execution_message or summary)
    elif session.phase == "execution_failed":
        spoken = "Исполнитель сообщил об ошибке: " + (
            session.execution_message or "действие не выполнено"
        )
    elif session.phase == "cancelled":
        spoken = "Команда отменена. Можно начать новый диалог."
    else:
        spoken = "Не удалось уточнить команду за отведённое число попыток. Начните новый диалог."
    return DialogueRead(
        id=command.id,
        text=command.text,
        user=UserRead.model_validate(command.user),
        phase=session.phase,
        intent=command.intent.code,
        intent_name=command.intent.name,
        confidence=command.confidence,
        slots=slots,
        question=question,
        spoken_text=spoken,
        ready_for_execution=session.phase == "ready",
        execution_confirmed=session.phase == "executed",
        operation_id=session.operation_id,
        execution_message=session.execution_message,
    )


def create(db: Session, text: str) -> DialogueRead:
    command = commands.create_command(db, ensure_owner(db).id, text)
    session = DialogueSession(command_id=command.id, phase="clarifying")
    _advance(session, command)
    db.add(session)
    db.commit()
    return describe(db, session)


def read(db: Session, session_id: int) -> DialogueRead:
    return describe(db, _get(db, session_id))


def answer(db: Session, session_id: int, text: str) -> DialogueRead:
    session = _get(db, session_id)
    if session.phase == "clarifying":
        try:
            command = commands.clarify_command(db, session_id, text)
        except AppError:
            _advance(session, commands.get_command(db, session_id))
            db.commit()
            raise
        _advance(session, command)
    elif session.phase == "awaiting_confirmation":
        clean = normalize(text).strip(". ")
        if clean in YES:
            session.phase = "ready"
        elif clean in NO:
            session.phase = "cancelled"
        else:
            raise BusinessError("Подтвердите команду словом «да» или отмените словом «нет».")
    else:
        raise ConflictError("На этом этапе ответ не ожидается. Начните новый диалог.")
    db.commit()
    return describe(db, session)


def cancel(db: Session, session_id: int) -> DialogueRead:
    session = _get(db, session_id)
    if session.phase == "clarifying":
        commands.cancel_command(db, session_id)
    elif session.phase != "awaiting_confirmation":
        raise ConflictError("Отменить можно команду до её передачи исполнителю.")
    session.phase = "cancelled"
    db.commit()
    return describe(db, session)


def acknowledge(db: Session, session_id: int, receipt: ExecutionReceipt) -> DialogueRead:
    session = db.scalar(
        select(DialogueSession).where(DialogueSession.command_id == session_id).with_for_update()
    )
    if session is None:
        raise NotFoundError(f"Диалог {session_id} не найден")
    if session.phase in {"executed", "execution_failed"}:
        if (session.operation_id, session.execution_success, session.execution_message) == (
            receipt.operation_id,
            receipt.success,
            receipt.message,
        ):
            return describe(db, session)
        raise ConflictError("Результат исполнения уже зафиксирован; заменить его нельзя.")
    if session.phase != "ready":
        raise ConflictError("Сначала соберите параметры и получите подтверждение пользователя.")
    session.operation_id = receipt.operation_id
    session.execution_success = receipt.success
    session.execution_message = receipt.message
    session.phase = "executed" if receipt.success else "execution_failed"
    db.commit()
    return describe(db, session)
