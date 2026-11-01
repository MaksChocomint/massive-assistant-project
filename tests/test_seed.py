"""Демонстрационные данные создаются один раз и не заменяют команды пользователя."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Command, User
from app.seed import COMMANDS, seed


def test_seed_is_idempotent(loaded_db: Session) -> None:
    seed(loaded_db)
    assert loaded_db.scalar(select(func.count()).select_from(User)) == 3
    first_ids = list(loaded_db.scalars(select(Command.id).order_by(Command.id)))
    assert len(first_ids) == len(COMMANDS)
    seed(loaded_db)
    assert list(loaded_db.scalars(select(Command.id).order_by(Command.id))) == first_ids
