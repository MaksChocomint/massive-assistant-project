"""Состояние ассистивного диалога и подтверждение внешнего исполнителя."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DialogueSession(Base):
    __tablename__ = "dialogue_sessions"
    __table_args__ = (
        CheckConstraint(
            "phase IN ('clarifying', 'awaiting_confirmation', 'ready', 'executed', "
            "'execution_failed', 'cancelled', 'failed')",
            name="ck_dialogue_phase",
        ),
    )

    command_id: Mapped[int] = mapped_column(
        ForeignKey("commands.id", ondelete="CASCADE"), primary_key=True
    )
    phase: Mapped[str] = mapped_column(String(30), default="clarifying", index=True)
    operation_id: Mapped[str | None] = mapped_column(String(100))
    execution_success: Mapped[bool | None] = mapped_column(Boolean)
    execution_message: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
