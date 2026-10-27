"""Справочник: намерения, сценарии, типы параметров, пользователи."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import Intent, Scenario, SlotType, User
from app.repositories import catalog as repo
from app.schemas.catalog import IntentCreate, IntentUpdate
from app.schemas.users import UserCreate
from app.services.nlu import reset_nlu


def list_intents(
    db: Session,
    scenario_id: int | None = None,
    search: str | None = None,
    active: bool | None = None,
    sort: str = "id",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[tuple[Intent, int]], int]:
    return repo.find_intents(db, scenario_id, search, active, sort, limit, offset)


def get_intent(db: Session, intent_id: int) -> Intent:
    intent = db.get(Intent, intent_id)
    if intent is None:
        raise NotFoundError(f"Намерение {intent_id} не найдено")
    return intent


def create_intent(db: Session, data: IntentCreate) -> Intent:
    if db.get(Scenario, data.scenario_id) is None:
        raise NotFoundError(f"Сценарий {data.scenario_id} не найден")
    intent = Intent(**data.model_dump())
    db.add(intent)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(f"Намерение с кодом {data.code} уже есть") from None
    return intent


def update_intent(db: Session, intent_id: int, data: IntentUpdate) -> Intent:
    intent = get_intent(db, intent_id)
    changes = data.model_dump(exclude_unset=True)
    if "scenario_id" in changes and db.get(Scenario, changes["scenario_id"]) is None:
        raise NotFoundError(f"Сценарий {changes['scenario_id']} не найден")
    for field, value in changes.items():
        setattr(intent, field, value)
    db.commit()
    if "is_active" in changes:
        reset_nlu()  # неактивные намерения не участвуют в распознавании
    return intent


def delete_intent(db: Session, intent_id: int) -> None:
    """Бизнес-правило: нельзя удалить намерение, по которому уже есть команды или фразы."""
    intent = get_intent(db, intent_id)
    if repo.count_commands(db, intent_id):
        raise ConflictError("По этому намерению есть команды — его можно только деактивировать")
    if repo.count_utterances(db, intent_id):
        raise ConflictError("У намерения есть фразы из датасета — его можно только деактивировать")
    db.delete(intent)
    db.commit()


def list_scenarios(db: Session) -> list[tuple[Scenario, int]]:
    return repo.scenarios_with_counts(db)


def list_slot_types(db: Session) -> list[SlotType]:
    return repo.all_slot_types(db)


def create_user(db: Session, data: UserCreate) -> User:
    user = User(**data.model_dump())
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(f"Логин {data.username} уже занят") from None
    return user


def list_users(db: Session) -> list[User]:
    return repo.all_users(db)


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"Пользователь {user_id} не найден")
    return user
