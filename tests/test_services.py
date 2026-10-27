"""Unit-тесты сервисного слоя: бизнес-правила команд и справочника."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.models import Intent, User
from app.services import catalog, commands
from app.services.nlu import get_nlu


def user_id(db: Session) -> int:
    user = db.scalar(select(User))
    assert user is not None
    return user.id


def test_command_with_all_slots_is_completed(loaded_db: Session) -> None:
    command = commands.create_command(loaded_db, user_id(loaded_db), "разбуди меня в семь утра")
    assert command.status == "completed"
    assert [(s.slot_type.code, s.value) for s in command.slots] == [("time", "семь утра")]


def test_command_without_slot_needs_clarification(loaded_db: Session) -> None:
    command = commands.create_command(loaded_db, user_id(loaded_db), "поставь будильник")
    assert command.status == "needs_clarification"
    assert commands.next_question(loaded_db, command) == "На какое время поставить будильник?"


def test_clarify_fills_slot(loaded_db: Session) -> None:
    command = commands.create_command(loaded_db, user_id(loaded_db), "поставь будильник")
    command = commands.clarify_command(loaded_db, command.id, "на семь утра")
    assert command.status == "completed"
    assert command.clarifications == 1
    assert command.slots[0].value == "семь утра"


def test_time_cannot_be_arbitrary_text(loaded_db: Session) -> None:
    command = commands.create_command(loaded_db, user_id(loaded_db), "поставь будильник")
    with pytest.raises(BusinessError, match="не похож на время"):
        commands.clarify_command(loaded_db, command.id, "напиши музыку")
    assert commands.get_command(loaded_db, command.id).clarifications == 1


def test_too_many_clarifications_fail_command(loaded_db: Session) -> None:
    command = commands.create_command(loaded_db, user_id(loaded_db), "поставь будильник")
    for answer in ("не знаю", "потом"):
        with pytest.raises(BusinessError):
            commands.clarify_command(loaded_db, command.id, answer)
    with pytest.raises(ConflictError, match="Слишком много"):
        commands.clarify_command(loaded_db, command.id, "когда-нибудь")
    assert commands.get_command(loaded_db, command.id).status == "failed"


def test_cancel_only_active_command(loaded_db: Session) -> None:
    command = commands.create_command(loaded_db, user_id(loaded_db), "поставь будильник")
    assert commands.cancel_command(loaded_db, command.id).status == "cancelled"
    with pytest.raises(ConflictError):
        commands.cancel_command(loaded_db, command.id)
    with pytest.raises(ConflictError):
        commands.clarify_command(loaded_db, command.id, "в семь утра")


def test_unknown_user_and_command(loaded_db: Session) -> None:
    with pytest.raises(NotFoundError):
        commands.create_command(loaded_db, 999, "привет")
    with pytest.raises(NotFoundError):
        commands.get_command(loaded_db, 999)


def test_intent_with_commands_cannot_be_deleted(loaded_db: Session) -> None:
    command = commands.create_command(loaded_db, user_id(loaded_db), "поставь будильник")
    with pytest.raises(ConflictError, match="есть команды"):
        catalog.delete_intent(loaded_db, command.intent_id)


def test_intent_with_utterances_cannot_be_deleted(loaded_db: Session) -> None:
    intent = loaded_db.scalar(select(Intent).where(Intent.code == "general_joke"))
    assert intent is not None
    with pytest.raises(ConflictError, match="фразы"):
        catalog.delete_intent(loaded_db, intent.id)


def test_find_slot(loaded_db: Session) -> None:
    nlu = get_nlu(loaded_db)
    assert nlu.find_slot("time", "разбуди в 7:30") == "7:30"
    assert nlu.find_slot("date", "что будет завтра") == "завтра"
    assert nlu.find_slot("time", "просто текст") is None
    assert nlu.find_slot("transport_type", "билет на поезд до казани") is not None
