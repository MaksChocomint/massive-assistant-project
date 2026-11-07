"""Точка входа FastAPI: роутеры, обработчики ошибок, раздача веб-интерфейса."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import activity, analytics, catalog, commands, dialogue, speech
from app.core.config import settings
from app.core.errors import ServiceUnavailableError, register_error_handlers

logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

STATIC = Path(__file__).parent / "static"

app = FastAPI(
    title="MASSIVE: ассистивный сервис уточнения команд",
    description="Голосовой диалог для невизуального взаимодействия: уточнение параметров, "
    "проговаривание, подтверждение пользователя и квитанция внешнего исполнителя. "
    "Распознавание намерений основано на MASSIVE; устройства напрямую не управляются.",
    version="1.0.0",
)
register_error_handlers(app)

for router in (
    dialogue.router,
    speech.router,
    catalog.router,
    commands.router,
    analytics.router,
    activity.router,
):
    app.include_router(router, prefix="/api")

app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
@app.get("/history", include_in_schema=False)
def index() -> FileResponse:
    """React-интерфейс, собранный Vite; использует тот же API."""
    index_path = STATIC / "ui" / "index.html"
    if not index_path.is_file():
        raise ServiceUnavailableError(
            "React-интерфейс не собран: выполните npm ci и npm run build в папке frontend"
        )
    return FileResponse(index_path)


@app.get("/api/health", tags=["Служебное"])
def health() -> dict[str, str]:
    return {"status": "ok"}
