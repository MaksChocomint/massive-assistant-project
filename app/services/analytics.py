"""Аналитика: агрегирующие запросы по командам и датасету."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Command, Intent, Scenario, Utterance


def top_intents(db: Session, limit: int = 5) -> list[dict[str, object]]:
    """Топ-N намерений по числу команд и доля успешно выполненных."""
    completed = func.sum(case((Command.status == "completed", 1), else_=0))
    rows = db.execute(
        select(Intent.code, Intent.name, func.count(Command.id), completed)
        .join(Command, Command.intent_id == Intent.id)
        .group_by(Intent.id)
        .order_by(func.count(Command.id).desc(), Intent.name)
        .limit(limit)
    ).all()
    return [
        {
            "intent": code,
            "name": name,
            "commands": total,
            "completed": int(done or 0),
            "success_rate": round((done or 0) / total, 3),
        }
        for code, name, total, done in rows
    ]


def status_summary(db: Session) -> dict[str, object]:
    """Сколько команд в каждом статусе и среднее число уточнений."""
    rows = db.execute(select(Command.status, func.count()).group_by(Command.status)).all()
    by_status = {status: n for status, n in rows}
    total = sum(by_status.values())
    avg = db.scalar(select(func.avg(Command.clarifications))) or 0
    return {
        "total": total,
        "by_status": by_status,
        "success_rate": round(by_status.get("completed", 0) / total, 3) if total else 0.0,
        "avg_clarifications": round(float(avg), 2),
    }


def commands_by_day(db: Session, days: int = 7) -> list[dict[str, object]]:
    """Динамика: число команд по дням за последние N дней."""
    since = datetime.now(UTC) - timedelta(days=days)
    day = func.date(Command.created_at)
    rows = db.execute(
        select(day, func.count()).where(Command.created_at >= since).group_by(day).order_by(day)
    ).all()
    return [{"day": str(d), "commands": n} for d, n in rows]


def dataset_by_scenario(db: Session) -> list[dict[str, object]]:
    """Сколько фраз датасета приходится на каждый сценарий."""
    rows = db.execute(
        select(Scenario.code, Scenario.name, func.count(Utterance.id))
        .join(Intent, Intent.scenario_id == Scenario.id)
        .join(Utterance, Utterance.intent_id == Intent.id)
        .group_by(Scenario.id)
        .order_by(func.count(Utterance.id).desc())
    ).all()
    return [{"scenario": code, "name": name, "utterances": n} for code, name, n in rows]
