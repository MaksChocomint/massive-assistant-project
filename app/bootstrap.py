"""Подготовка приложения: миграции, импорт MASSIVE и демонстрационные команды.

Запуск: python -m app.bootstrap [--no-demo]. Повторный запуск сохраняет данные.
"""

import argparse
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import settings
from app.db import SessionLocal
from app.etl.import_massive import run
from app.seed import seed

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-demo", action="store_true", help="Применить только миграции")
    args = parser.parse_args(argv)
    logging.basicConfig(level=settings.log_level)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")
    # Alembic применяет свой logging-конфиг; возвращаем уровень приложения.
    logging.getLogger().setLevel(settings.log_level)
    if not args.no_demo:
        with SessionLocal() as db:
            run(db, ROOT / "data" / "massive_ru.csv")
            seed(db)


if __name__ == "__main__":
    main()
