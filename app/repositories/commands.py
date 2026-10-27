"""Запросы к БД для команд. Здесь только чтение данных — правила в services."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Command, CommandSlot, IntentSlot

WITH_SLOTS = selectinload(Command.slots).selectinload(CommandSlot.slot_type)


def get_with_slots(db: Session, command_id: int) -> Command | None:
    return db.scalar(select(Command).where(Command.id == command_id).options(WITH_SLOTS))


def required_slots(db: Session, intent_id: int) -> list[IntentSlot]:
    """Обязательные параметры намерения в порядке, в котором о них спрашивать."""
    return list(
        db.scalars(
            select(IntentSlot)
            .where(IntentSlot.intent_id == intent_id, IntentSlot.required.is_(True))
            .options(selectinload(IntentSlot.slot_type))
            .order_by(IntentSlot.position)
        )
    )


def find_commands(
    db: Session, status: str | None, user_id: int | None, limit: int, offset: int
) -> tuple[list[Command], int]:
    query = select(Command)
    if status:
        query = query.where(Command.status == status)
    if user_id:
        query = query.where(Command.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.options(WITH_SLOTS).order_by(Command.id.desc()).limit(limit).offset(offset)
    ).all()
    return list(items), total
