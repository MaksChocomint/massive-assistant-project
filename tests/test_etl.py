"""Unit-тесты ETL: очистка данных и идемпотентная загрузка."""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.etl.import_massive import Report, clean, extract, normalize_text, parse_slot_types, run
from app.models import Intent, IntentSlot, SlotType, Utterance
from tests.conftest import SAMPLE


def row(**fields: str) -> dict[str, str]:
    base = {
        "id": "1",
        "partition": "train",
        "scenario": "alarm",
        "intent": "alarm_set",
        "utt": "разбуди меня в семь",
        "annot_utt": "разбуди меня в [time : семь]",
    }
    return {**base, **fields}


def test_normalize_text() -> None:
    assert normalize_text("  разбуди   меня  ") == "разбуди меня"


def test_parse_slot_types() -> None:
    assert parse_slot_types("в [time : семь] [date : завтра]") == ["time", "date"]
    assert parse_slot_types("без параметров") == []
    assert parse_slot_types("сломано [time : семь") is None


def test_clean_rejects_bad_rows() -> None:
    report = Report()
    rows = [
        row(id="1"),
        row(id="2", utt="   "),  # пустой текст
        row(id="3", partition="validation"),  # неизвестный partition
        row(id="1", utt="другая фраза"),  # повтор id
        row(id="4", utt="Разбуди  меня в семь"),  # дубликат фразы (регистр и пробелы)
        row(id="5", utt="поставь будильник", annot_utt="поставь [time : будильник"),
        row(id="6", utt="какая погода", intent="weather_query", annot_utt="какая погода"),
    ]
    result = clean(rows, report)

    assert [r.external_id for r in result] == ["1", "6"]
    assert result[0].slot_types == ["time"]
    assert report.read == 7
    assert report.rejected == {
        "пустое поле": 1,
        "неизвестный partition": 1,
        "повтор id": 1,
        "дубликат фразы": 1,
        "сломанная разметка": 1,
    }
    assert "отклонено 5" in report.summary()


def test_extract_requires_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("id,text\n1,привет\n", encoding="utf-8")
    with pytest.raises(ValueError, match="нет колонок"):
        extract(path)


def test_import_is_idempotent(db: Session) -> None:
    first = run(db, SAMPLE)
    assert first.loaded > 200
    utterances = db.scalar(select(func.count()).select_from(Utterance))

    second = run(db, SAMPLE)
    assert second.loaded == 0
    assert second.already_in_db == first.loaded
    assert db.scalar(select(func.count()).select_from(Utterance)) == utterances
    assert db.scalar(select(func.count()).select_from(Intent)) == 8


def test_import_creates_required_slots(db: Session) -> None:
    run(db, SAMPLE)
    ticket = db.scalar(select(Intent).where(Intent.code == "transport_ticket"))
    assert ticket is not None and ticket.name == "Купить билет"
    links = db.scalars(
        select(IntentSlot).where(IntentSlot.intent_id == ticket.id).order_by(IntentSlot.position)
    ).all()
    codes = [db.get(SlotType, link.slot_type_id).code for link in links]  # type: ignore[union-attr]
    assert codes == ["transport_type", "place_name"]
    assert links[0].question.startswith("Какой билет")
