"""Тестовая БД — SQLite в памяти: отдельная от рабочей и пересоздаётся для каждого теста."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.etl.import_massive import run
from app.main import app
from app.models import User
from app.services.nlu import reset_nlu

SAMPLE = Path(__file__).parent / "fixtures" / "sample.csv"

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _record):  # type: ignore[no-untyped-def]
    # SQLite по умолчанию не проверяет внешние ключи
    connection.execute("PRAGMA foreign_keys=ON")


TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def db() -> Iterator[Session]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture
def loaded_db(db: Session) -> Session:
    """БД со справочником из тестового CSV (8 намерений) и одним пользователем."""
    run(db, SAMPLE)
    db.add(User(username="ivan", name="Иван"))
    db.commit()
    reset_nlu()
    return db


@pytest.fixture
def client(loaded_db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: loaded_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
