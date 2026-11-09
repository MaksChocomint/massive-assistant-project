"""Чтение журнала и сводки. completed не считается квитанцией исполнения."""

from sqlalchemy.orm import Session

from app.repositories import activity as repo
from app.schemas.activity import ActivityItem, ActivityPage, ActivitySummary
from app.schemas.commands import SlotValueRead
from app.schemas.users import UserRead


def history(
    db: Session,
    user_id: int | None,
    days: int | None,
    phase: str | None,
    search: str | None,
    limit: int,
    offset: int,
) -> ActivityPage:
    rows, total = repo.history(db, user_id, days, phase, search, limit, offset)
    return ActivityPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            ActivityItem(
                id=c.id,
                text=c.text,
                created_at=c.created_at,
                user=UserRead.model_validate(c.user),
                intent=c.intent.code,
                intent_name=c.intent.name,
                confidence=c.confidence,
                command_status=c.status,
                phase=s.phase if s else "legacy",
                clarifications=c.clarifications,
                slots=[
                    SlotValueRead(slot=v.slot_type.code, name=v.slot_type.name, value=v.value)
                    for v in c.slots
                ],
                execution_confirmed=s is not None and s.phase == "executed",
                execution_message=s.execution_message if s else None,
                execution_recorded_at=s.updated_at
                if s is not None and s.phase in {"executed", "execution_failed"}
                else None,
                operation_id=s.operation_id if s else None,
            )
            for c, s in rows
        ],
    )


def summary(db: Session, user_id: int | None, days: int | None) -> ActivitySummary:
    return ActivitySummary.model_validate(repo.summary(db, user_id, days))
