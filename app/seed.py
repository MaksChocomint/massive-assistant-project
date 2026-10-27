"""Наполнение БД демонстрационными данными: пользователи и команды.

Запуск (после ETL):
    python -m app.seed

Повторный запуск безопасен: существующие пользователи не дублируются,
команды создаются, только если их ещё нет.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessError, ConflictError
from app.models import Command, User
from app.services import commands as service

logger = logging.getLogger("app.seed")

USERS = [("ivan", "Иван Петров"), ("maria", "Мария Соколова"), ("alex", "Алексей Смирнов")]

# (пользователь, текст команды, ответы на уточняющие вопросы, отменить ли)
COMMANDS = [
    ("ivan", "разбуди меня в семь утра", [], False),
    ("ivan", "поставь будильник", ["на шесть утра"], False),
    ("ivan", "какая погода в казани завтра", [], False),
    ("maria", "закажи пиццу из додо", [], False),
    ("maria", "добавь в календарь", ["день рождения мамы", "в пятницу"], False),
    ("maria", "включи радио", ["европа плюс"], False),
    ("maria", "купи билет", [], True),
    ("alex", "купи билет на поезд до москвы", [], False),
    ("alex", "вызови такси", ["до вокзала"], False),
    ("alex", "поставь будильник", [], False),
    ("alex", "расскажи анекдот", [], False),
    # три ответа не про время — команда получит статус failed
    ("ivan", "разбуди меня", ["не знаю", "потом", "когда-нибудь"], False),
]


def seed(db: Session) -> None:
    users: dict[str, User] = {}
    for username, name in USERS:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(username=username, name=name)
            db.add(user)
            db.commit()
        users[username] = user

    if db.scalar(select(func.count()).select_from(Command)):
        logger.info("Команды уже есть — пропускаю")
        return

    for username, text, answers, cancel in COMMANDS:
        command = service.create_command(db, users[username].id, text)
        for answer in answers:
            if command.status != "needs_clarification":
                break
            try:
                command = service.clarify_command(db, command.id, answer)
            except (BusinessError, ConflictError):
                command = service.get_command(db, command.id)
        if cancel and command.status == "needs_clarification":
            service.cancel_command(db, command.id)
    logger.info("Создано пользователей: %d, команд: %d", len(users), len(COMMANDS))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    from app.db import SessionLocal

    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    main()
