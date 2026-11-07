"""Выбранный владелец домашнего интерфейса. Это не идентификация по голосу."""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Command, User

OWNER_USERNAME = "maksim_ivanov"
OWNER_NAME = "maksim ivanov"
LEGACY_USERNAME = "voice_dialogue"


def ensure_owner(db: Session) -> User:
    """Переиспользует старый профиль и его историю, не затрагивая других пользователей."""
    owner = db.scalar(select(User).where(User.username == OWNER_USERNAME))
    legacy = db.scalar(select(User).where(User.username == LEGACY_USERNAME))
    if owner is None:
        owner = legacy if legacy is not None else User()
        owner.username = OWNER_USERNAME
        owner.name = OWNER_NAME
        db.add(owner)
    else:
        owner.name = OWNER_NAME
        if legacy is not None:
            db.execute(update(Command).where(Command.user_id == legacy.id).values(user_id=owner.id))
    try:
        db.commit()
    except IntegrityError:
        # Два первых запроса могут одновременно создать одного владельца.
        db.rollback()
        owner = db.scalar(select(User).where(User.username == OWNER_USERNAME))
        if owner is None:
            raise
    return owner
