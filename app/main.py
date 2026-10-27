"""Точка входа FastAPI: роутеры, обработчики ошибок, раздача веб-интерфейса."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import analytics, catalog, commands
from app.core.config import settings
from app.core.errors import register_error_handlers

logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

STATIC = Path(__file__).parent / "static"

app = FastAPI(
    title="Голосовой помощник: команды и справочник",
    description="Информационная система на датасете MASSIVE: справочник намерений, "
    "обработка команд пользователей с уточняющими вопросами, ETL и аналитика.",
    version="1.0.0",
)
register_error_handlers(app)

for router in (catalog.router, commands.router, analytics.router):
    app.include_router(router, prefix="/api")

app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Веб-интерфейс (HTML + JS), работает через этот же API."""
    return FileResponse(STATIC / "index.html")


@app.get("/api/health", tags=["Служебное"])
def health() -> dict[str, str]:
    return {"status": "ok"}
