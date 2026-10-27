"""Бизнес-логика команд.

Правила:
1. Новая команда распознаётся: определяется намерение и параметры из текста.
   Если не хватает обязательных параметров — статус needs_clarification и вопрос,
   иначе — completed.
2. Уточнение заполняет первый недостающий параметр. Время и дату нельзя заполнить
   произвольным текстом — ответ должен быть похож на время / дату (иначе 400).
3. На уточнение даётся не больше settings.max_clarifications попыток, после этого
   команда получает статус failed.
4. Уточнять и отменять можно только команду в статусе needs_clarification (иначе 409).
Каждая операция выполняется в одной транзакции: параметры и статус сохраняются вместе.
"""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.models import Command, CommandSlot, IntentSlot, User
from app.repositories import commands as repo
from app.services.nlu import FORMAT_RULES, get_nlu, normalize

ACTIVE = "needs_clarification"
EXPECTED = {"time": "время", "date": "дату"}


def get_command(db: Session, command_id: int) -> Command:
    command = repo.get_with_slots(db, command_id)
    if command is None:
        raise NotFoundError(f"Команда {command_id} не найдена")
    return command


def missing_slots(db: Session, command: Command) -> list[IntentSlot]:
    filled = {slot.slot_type_id for slot in command.slots}
    return [s for s in repo.required_slots(db, command.intent_id) if s.slot_type_id not in filled]


def next_question(db: Session, command: Command) -> str | None:
    """Вопрос по первому недостающему параметру (None — всё заполнено)."""
    if command.status != ACTIVE:
        return None
    missing = missing_slots(db, command)
    return missing[0].question if missing else None


def update_status(db: Session, command: Command) -> None:
    if not missing_slots(db, command):
        command.status = "completed"
    elif command.clarifications >= settings.max_clarifications:
        command.status = "failed"
    else:
        command.status = ACTIVE


def create_command(db: Session, user_id: int, text: str) -> Command:
    if db.get(User, user_id) is None:
        raise NotFoundError(f"Пользователь {user_id} не найден")
    nlu = get_nlu(db)
    prediction = nlu.predict(text)

    command = Command(
        user_id=user_id,
        text=text.strip(),
        intent_id=prediction.intent_id,
        confidence=prediction.confidence,
        status=ACTIVE,
        clarifications=0,
    )
    db.add(command)
    db.flush()
    for slot in repo.required_slots(db, prediction.intent_id):
        value = nlu.find_slot(slot.slot_type.code, text)
        if value:
            command.slots.append(CommandSlot(slot_type_id=slot.slot_type_id, value=value))
    db.flush()
    update_status(db, command)
    db.commit()
    return get_command(db, command.id)


def clarify_command(db: Session, command_id: int, answer: str) -> Command:
    command = get_command(db, command_id)
    if command.status != ACTIVE:
        raise ConflictError(f"Команда в статусе {command.status}, уточнять её нельзя")

    slot = missing_slots(db, command)[0]
    code = slot.slot_type.code
    value = normalize(answer)
    if code in FORMAT_RULES:
        match = FORMAT_RULES[code].search(value)
        if match is None:
            # неудачная попытка тоже считается: иначе можно спрашивать бесконечно
            command.clarifications += 1
            update_status(db, command)
            db.commit()
            if command.status == "failed":
                raise ConflictError("Слишком много неудачных уточнений, команда отклонена")
            raise BusinessError(f"Ответ «{answer}» не похож на {EXPECTED[code]}")
        value = match.group(0)

    command.slots.append(CommandSlot(slot_type_id=slot.slot_type_id, value=value))
    command.clarifications += 1
    db.flush()
    update_status(db, command)
    db.commit()
    return get_command(db, command.id)


def cancel_command(db: Session, command_id: int) -> Command:
    command = get_command(db, command_id)
    if command.status != ACTIVE:
        raise ConflictError(f"Команда в статусе {command.status}, отменить её нельзя")
    command.status = "cancelled"
    db.commit()
    return get_command(db, command.id)


def list_commands(
    db: Session,
    status: str | None = None,
    user_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Command], int]:
    return repo.find_commands(db, status, user_id, limit, offset)
