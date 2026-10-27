"""Запросы к БД для справочника. Здесь только чтение данных — правила в services."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Command, Intent, Scenario, SlotType, User, Utterance

SORT_FIELDS = {"id": Intent.id, "code": Intent.code, "name": Intent.name}


def find_intents(
    db: Session,
    scenario_id: int | None,
    search: str | None,
    active: bool | None,
    sort: str,
    limit: int,
    offset: int,
) -> tuple[list[tuple[Intent, int]], int]:
    """Намерения с числом фраз-примеров. Фильтры, сортировка (-name — по убыванию), пагинация."""
    query = select(Intent)
    if scenario_id:
        query = query.where(Intent.scenario_id == scenario_id)
    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(or_(func.lower(Intent.name).like(pattern), Intent.code.like(pattern)))
    if active is not None:
        query = query.where(Intent.is_active.is_(active))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    column = SORT_FIELDS.get(sort.lstrip("-"), Intent.id)
    order = column.desc() if sort.startswith("-") else column.asc()
    counts = (
        select(Utterance.intent_id, func.count().label("n"))
        .group_by(Utterance.intent_id)
        .subquery()
    )
    rows = db.execute(
        query.add_columns(func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.intent_id == Intent.id)
        .order_by(order)
        .limit(limit)
        .offset(offset)
    ).all()
    return [(row[0], row[1]) for row in rows], total


def count_commands(db: Session, intent_id: int) -> int:
    return db.scalar(select(func.count()).where(Command.intent_id == intent_id)) or 0


def count_utterances(db: Session, intent_id: int) -> int:
    return db.scalar(select(func.count()).where(Utterance.intent_id == intent_id)) or 0


def scenarios_with_counts(db: Session) -> list[tuple[Scenario, int]]:
    rows = db.execute(
        select(Scenario, func.count(Intent.id))
        .outerjoin(Intent)
        .group_by(Scenario.id)
        .order_by(Scenario.name)
    ).all()
    return [(row[0], row[1]) for row in rows]


def all_slot_types(db: Session) -> list[SlotType]:
    return list(db.scalars(select(SlotType).order_by(SlotType.name)))


def all_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))
