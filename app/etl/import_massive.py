"""ETL: импорт фраз MASSIVE из CSV в базу данных.

Запуск:
    python -m app.etl.import_massive --source data/massive_ru.csv

Этапы:
1. extract   — читаем CSV;
2. clean     — отбрасываем некорректные строки и дубликаты, считаем причины;
3. transform — нормализуем текст, достаём типы параметров из разметки;
4. load      — записываем в БД. Повторный запуск не создаёт дубликатов:
               справочники ищутся по коду, фразы — по external_id.
"""

import argparse
import csv
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.etl.labels import INTENT_RU, REQUIRED_SLOTS, SCENARIO_RU, SLOT_RU, slot_question
from app.models import Intent, IntentSlot, Scenario, SlotType, Utterance

logger = logging.getLogger("app.etl")

REQUIRED_COLUMNS = ("id", "partition", "scenario", "intent", "utt", "annot_utt")
PARTITIONS = ("train", "dev", "test")
SLOT_PATTERN = re.compile(r"\[\s*(\w+)\s*:\s*([^\[\]]*?)\s*\]")


@dataclass
class CleanRow:
    external_id: str
    partition: str
    scenario: str
    intent: str
    text: str
    annotated: str
    slot_types: list[str]


@dataclass
class Report:
    read: int = 0
    loaded: int = 0
    already_in_db: int = 0
    rejected: Counter[str] = field(default_factory=Counter)

    def summary(self) -> str:
        reasons = ", ".join(f"{reason}: {n}" for reason, n in self.rejected.most_common()) or "нет"
        rejected = sum(self.rejected.values())
        return (
            f"прочитано {self.read}, загружено {self.loaded}, "
            f"уже было в БД {self.already_in_db}, отклонено {rejected} ({reasons})"
        )


# --- 1. Извлечение ---------------------------------------------------------------


def extract(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"В CSV нет колонок: {', '.join(sorted(missing))}")
        return list(reader)


# --- 2. Очистка ------------------------------------------------------------------


def normalize_text(text: str) -> str:
    """Убирает лишние пробелы по краям и внутри фразы."""
    return " ".join(text.split())


def parse_slot_types(annotated: str) -> list[str] | None:
    """Типы параметров из разметки «[time : семь утра]». None — разметка сломана."""
    remainder = SLOT_PATTERN.sub("", annotated)
    if "[" in remainder or "]" in remainder:
        return None
    matches = list(SLOT_PATTERN.finditer(annotated))
    if any(not match.group(2).strip() for match in matches):
        return None
    return [match.group(1) for match in matches]


def clean(rows: list[dict[str, str]], report: Report) -> list[CleanRow]:
    """Проверяет строки; некорректные отбрасывает и записывает причину в отчёт."""
    result: list[CleanRow] = []
    seen_ids: set[str] = set()
    seen_texts: set[tuple[str, str]] = set()

    for row in rows:
        report.read += 1
        external_id = (row.get("id") or "").strip()
        text = normalize_text(row.get("utt") or "")
        intent = (row.get("intent") or "").strip()
        scenario = (row.get("scenario") or "").strip()
        partition = (row.get("partition") or "").strip()
        annotated = (row.get("annot_utt") or "").strip()

        if not external_id or not text or not intent or not scenario or not annotated:
            reason = "пустое поле"
        elif len(external_id) > 20 or any(
            not re.fullmatch(r"[a-z_]{1,50}", value) for value in (intent, scenario)
        ):
            reason = "некорректный идентификатор"
        elif partition not in PARTITIONS:
            reason = "неизвестный partition"
        elif external_id in seen_ids:
            reason = "повтор id"
        elif (text.lower(), intent) in seen_texts:
            reason = "дубликат фразы"
        elif (slots := parse_slot_types(annotated)) is None:
            reason = "сломанная разметка"
        elif normalize_text(SLOT_PATTERN.sub(lambda m: m.group(2), annotated)) != text:
            reason = "разметка не соответствует фразе"
        else:
            seen_ids.add(external_id)
            seen_texts.add((text.lower(), intent))
            result.append(
                CleanRow(external_id, partition, scenario, intent, text, annotated, slots)
            )
            continue
        report.rejected[reason] += 1
    return result


# --- 3–4. Преобразование и загрузка ----------------------------------------------


def get_or_create(db: Session, model: type, code: str, **fields: object) -> object:
    """Ищет запись по коду, создаёт при отсутствии (так повторный запуск не плодит дубли)."""
    obj = db.scalar(select(model).where(model.code == code))
    if obj is None:
        obj = model(code=code, **fields)
        db.add(obj)
        db.flush()
    return obj


def load(db: Session, rows: list[CleanRow], report: Report) -> None:
    scenarios: dict[str, Scenario] = {}
    intents: dict[str, Intent] = {}
    slot_types: dict[str, SlotType] = {}

    for row in rows:
        if row.scenario not in scenarios:
            name = SCENARIO_RU.get(row.scenario, row.scenario)
            scenarios[row.scenario] = get_or_create(db, Scenario, row.scenario, name=name)
        if row.intent not in intents:
            intents[row.intent] = get_or_create(
                db,
                Intent,
                row.intent,
                name=INTENT_RU.get(row.intent, row.intent),
                scenario_id=scenarios[row.scenario].id,
            )
        for slot in row.slot_types:
            if slot not in slot_types:
                slot_types[slot] = get_or_create(db, SlotType, slot, name=SLOT_RU.get(slot, slot))

    existing = set(db.scalars(select(Utterance.external_id)))
    for row in rows:
        if row.external_id in existing:
            report.already_in_db += 1
            continue
        db.add(
            Utterance(
                external_id=row.external_id,
                text=row.text,
                annotated=row.annotated,
                partition=row.partition,
                intent_id=intents[row.intent].id,
            )
        )
        report.loaded += 1

    # Обязательные параметры намерений (связь многие-ко-многим)
    for intent_code, slots in REQUIRED_SLOTS.items():
        if intent_code not in intents:
            continue
        intent = intents[intent_code]
        for position, slot in enumerate(slots):
            slot_type = slot_types.get(slot) or get_or_create(
                db, SlotType, slot, name=SLOT_RU.get(slot, slot)
            )
            link = db.get(IntentSlot, (intent.id, slot_type.id))
            if link is None:
                db.add(
                    IntentSlot(
                        intent_id=intent.id,
                        slot_type_id=slot_type.id,
                        required=True,
                        position=position,
                        question=slot_question(intent_code, slot),
                    )
                )
    db.commit()


def run(db: Session, source: Path) -> Report:
    report = Report()
    rows = clean(extract(source), report)
    load(db, rows, report)
    logger.info("Импорт %s: %s", source, report.summary())
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Импорт фраз MASSIVE из CSV в БД")
    parser.add_argument("--source", type=Path, default=Path("data/massive_ru.csv"))
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    from app.db import SessionLocal

    with SessionLocal() as db:
        run(db, args.source)


if __name__ == "__main__":
    main()
