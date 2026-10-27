"""Пользователи и их команды ассистенту."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.catalog import Intent, SlotType

COMMAND_STATUSES = ("needs_clarification", "completed", "cancelled", "failed")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    commands: Mapped[list["Command"]] = relationship(back_populates="user")


class Command(Base):
    """Команда пользователя. Статус меняется только через сервис (app/services/commands.py)."""

    __tablename__ = "commands"
    __table_args__ = (
        CheckConstraint(
            "status IN ('needs_clarification', 'completed', 'cancelled', 'failed')",
            name="ck_command_status",
        ),
        CheckConstraint("clarifications >= 0", name="ck_command_clarifications"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    intent_id: Mapped[int] = mapped_column(ForeignKey("intents.id"), index=True)
    confidence: Mapped[float]
    status: Mapped[str] = mapped_column(String(30), index=True)
    clarifications: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="commands")
    intent: Mapped[Intent] = relationship()
    slots: Mapped[list["CommandSlot"]] = relationship(
        back_populates="command", cascade="all, delete-orphan", order_by="CommandSlot.id"
    )


class CommandSlot(Base):
    """Значение параметра в конкретной команде: время = «семь утра»."""

    __tablename__ = "command_slots"
    __table_args__ = (UniqueConstraint("command_id", "slot_type_id", name="uq_command_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    command_id: Mapped[int] = mapped_column(ForeignKey("commands.id", ondelete="CASCADE"))
    slot_type_id: Mapped[int] = mapped_column(ForeignKey("slot_types.id"))
    value: Mapped[str] = mapped_column(String(200))

    command: Mapped[Command] = relationship(back_populates="slots")
    slot_type: Mapped[SlotType] = relationship()
