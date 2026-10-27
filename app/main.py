"""Точка входа FastAPI: роутеры и обработчики ошибок."""

import logging

from fastapi import FastAPI

from app.api import catalog, commands
from app.core.config import settings
from app.core.errors import register_error_handlers

logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

app = FastAPI(
    title="Голосовой помощник: команды и справочник",
    description="Информационная система на датасете MASSIVE: справочник намерений, "
    "обработка команд пользователей с уточняющими вопросами, ETL и аналитика.",
    version="1.0.0",
)
register_error_handlers(app)

for router in (catalog.router, commands.router):
    app.include_router(router, prefix="/api")


@app.get("/api/health", tags=["Служебное"])
def health() -> dict[str, str]:
    return {"status": "ok"}
