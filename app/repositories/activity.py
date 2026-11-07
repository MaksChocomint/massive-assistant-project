"""Журнал и агрегации по реальным квитанциям, включая старые команды без диалога."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Command, DialogueSession, Intent, User
from app.repositories.commands import WITH_SLOTS

PHASE = func.coalesce(DialogueSession.phase, "legacy")
EXECUTED = func.sum(case((DialogueSession.phase == "executed", 1), else_=0))


def filters(user_id: int | None, days: int | None) -> list:
    result = []
    if user_id is not None:
        result.append(Command.user_id == user_id)
    if days is not None:
        since = (datetime.now(UTC) - timedelta(days=days - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        result.append(Command.created_at >= since)
    return result


def history(
    db: Session,
    user_id: int | None,
    days: int | None,
    phase: str | None,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list, int]:
    query = (
        select(Command, DialogueSession)
        .outerjoin(DialogueSession, DialogueSession.command_id == Command.id)
        .where(*filters(user_id, days))
    )
    if phase is not None:
        query = query.where(PHASE == phase)
    if search:
        query = query.where(Command.text.icontains(search, autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.options(WITH_SLOTS, joinedload(Command.user), joinedload(Command.intent))
        .order_by(Command.created_at.desc(), Command.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total


def summary(db: Session, user_id: int | None, days: int | None) -> dict:
    conditions = filters(user_id, days)
    phases = db.execute(
        select(PHASE, func.count(Command.id))
        .select_from(Command)
        .outerjoin(DialogueSession, DialogueSession.command_id == Command.id)
        .where(*conditions)
        .group_by(PHASE)
    ).all()
    by_phase = dict(phases)
    avg = db.scalar(select(func.avg(Command.clarifications)).where(*conditions)) or 0
    attempted = by_phase.get("executed", 0) + by_phase.get("execution_failed", 0)
    top = db.execute(
        select(Intent.code, Intent.name, func.count(Command.id), EXECUTED)
        .select_from(Command)
        .join(Intent, Intent.id == Command.intent_id)
        .outerjoin(DialogueSession, DialogueSession.command_id == Command.id)
        .where(*conditions)
        .group_by(Intent.id, Intent.code, Intent.name)
        .order_by(func.count(Command.id).desc(), Intent.code)
        .limit(10)
    ).all()
    users = db.execute(
        select(User.id, User.username, User.name, func.count(Command.id), EXECUTED)
        .select_from(Command)
        .join(User, User.id == Command.user_id)
        .outerjoin(DialogueSession, DialogueSession.command_id == Command.id)
        .where(*conditions)
        .group_by(User.id, User.username, User.name)
        .order_by(func.count(Command.id).desc(), User.id)
    ).all()
    day = func.date(Command.created_at)
    daily = db.execute(
        select(day, func.count(Command.id), EXECUTED)
        .select_from(Command)
        .outerjoin(DialogueSession, DialogueSession.command_id == Command.id)
        .where(*conditions)
        .group_by(day)
        .order_by(day)
    ).all()
    return {
        "total": sum(by_phase.values()),
        "by_phase": by_phase,
        "execution_success_rate": round(by_phase.get("executed", 0) / attempted, 3)
        if attempted
        else None,
        "avg_clarifications": round(float(avg), 2),
        "top_intents": [
            {"intent": code, "name": name, "commands": n, "executed": int(done or 0)}
            for code, name, n, done in top
        ],
        "by_user": [
            {
                "user_id": uid,
                "username": username,
                "name": name,
                "commands": n,
                "executed": int(done or 0),
            }
            for uid, username, name, n, done in users
        ],
        "by_day": [
            {"day": str(d), "commands": n, "executed": int(done or 0)} for d, n, done in daily
        ],
    }
