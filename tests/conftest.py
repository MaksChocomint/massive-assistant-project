"""Тестовая БД — SQLite в памяти: отдельная от рабочей и пересоздаётся для каждого теста."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401 — регистрирует таблицы в Base.metadata
from app.db import Base

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
