"""Unit-тесты сервисного слоя: бизнес-правила команд и справочника."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessError, ConflictError, NotFoundError, ServiceUnavailableError
from app.models import Intent, User, Utterance
from app.services import catalog, commands
from app.services.nlu import Nlu, disambiguate_light_intent, get_nlu, train_nlu


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
    with pytest.raises(BusinessError, match="Не удалось определить время"):
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


@pytest.mark.parametrize(
    "text",
    [
        "99:99",
        "25:15",
        "7:70",
        "через музыку",
        "99 часов",
        "двадцать четыре часа",
        "семь часов семьдесят минут",
        "7 часов 70 минут",
        "25 часов 10 минут",
        "7:300",
        "через ноль минут",
        "-7:30",
    ],
)
def test_invalid_time_is_rejected(text: str) -> None:
    assert Nlu().find_slot("time", text) is None


@pytest.mark.parametrize(
    "text",
    [
        "7:30",
        "07.30",
        "23:59",
        "через пять минут",
        "через час",
        "семь часов десять минут",
        "7 часов 10 минут",
        "семь часов",
        "семь часов десять минут утра",
        "двадцать три часа пятьдесят девять минут",
        "ноль часов пять минут",
        "тринадцать часов пятнадцать минут",
        "через двадцать пять минут",
        "через полчаса",
        "полдень",
        "семь утра",
    ],
)
def test_supported_time_formats(text: str) -> None:
    assert Nlu().find_slot("time", text) == text


def test_empty_training_data_is_reported(db: Session) -> None:
    with pytest.raises(ServiceUnavailableError, match="нет фраз"):
        Nlu().train(db)


@pytest.mark.parametrize(
    "text",
    ["через минуту", "через одну минуту", "через 10 секунд", "через секунду", "на минуту вперед"],
)
def test_relative_alarm_time_formats(text: str) -> None:
    assert Nlu().find_slot("time", text) == text


@pytest.mark.parametrize("text", ["через ноль секунд", "на ноль минут вперед"])
def test_zero_relative_alarm_is_rejected(text: str) -> None:
    assert Nlu().find_slot("time", text) is None


@pytest.mark.parametrize(
    ("text", "predicted", "expected"),
    [
        ("Включи свет", "iot_hue_lightup", "iot_hue_lighton"),
        ("Включить свет", "iot_hue_lightup", "iot_hue_lighton"),
        ("Зажги свет", "iot_hue_lightchange", "iot_hue_lighton"),
        ("Выключи свет", "iot_hue_lightdim", "iot_hue_lightoff"),
        ("Не включай свет", "iot_hue_lightup", "iot_hue_lightup"),
        ("Как включить свет", "iot_hue_lightup", "iot_hue_lightup"),
        ("Сделай свет ярче", "iot_hue_lightup", "iot_hue_lightup"),
        ("Включи свет", "alarm_set", "alarm_set"),
    ],
)
def test_explicit_light_action_disambiguation(text: str, predicted: str, expected: str) -> None:
    assert disambiguate_light_intent(text, predicted) == expected


def test_training_requires_more_than_one_class(loaded_db: Session) -> None:
    for intent in loaded_db.scalars(select(Intent)):
        intent.is_active = intent.code == "alarm_set"
    loaded_db.commit()
    with pytest.raises(ServiceUnavailableError, match="2 активных"):
        train_nlu(loaded_db)


def test_failed_retraining_keeps_previous_model(loaded_db: Session) -> None:
    previous = get_nlu(loaded_db)
    previous_prediction = previous.predict("поставь будильник")
    for utterance in loaded_db.scalars(select(Utterance).where(Utterance.partition == "train")):
        loaded_db.delete(utterance)
    loaded_db.commit()
    with pytest.raises(ServiceUnavailableError):
        train_nlu(loaded_db)
    assert get_nlu(loaded_db) is previous
    assert previous.predict("поставь будильник") == previous_prediction
