"""Ограничения целостности схемы: UNIQUE, CHECK, внешние ключи."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Command, Intent, Scenario, User, Utterance


def make_intent(db: Session) -> Intent:
    scenario = Scenario(code="alarm", name="Будильник")
    db.add(scenario)
    db.flush()
    intent = Intent(code="alarm_set", name="Поставить будильник", scenario_id=scenario.id)
    db.add(intent)
    db.flush()
    return intent


def test_unique_code(db: Session) -> None:
    make_intent(db)
    db.add(Scenario(code="alarm", name="Ещё один"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_partition_check(db: Session) -> None:
    intent = make_intent(db)
    db.add(
        Utterance(external_id="1", text="x", annotated="x", partition="other", intent_id=intent.id)
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_command_status_check(db: Session) -> None:
    intent = make_intent(db)
    user = User(username="ivan", name="Иван")
    db.add(user)
    db.flush()
    db.add(
        Command(user_id=user.id, text="x", intent_id=intent.id, confidence=1.0, status="unknown")
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_foreign_key(db: Session) -> None:
    db.add(Intent(code="x_y", name="Икс", scenario_id=999))
    with pytest.raises(IntegrityError):
        db.flush()
