"""Справочник ассистента: сценарии, намерения, типы параметров (слотов) и фразы-примеры."""

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Scenario(Base):
    """Сценарий — группа намерений: alarm, weather, music…"""

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))

    intents: Mapped[list["Intent"]] = relationship(back_populates="scenario")


class Intent(Base):
    """Намерение пользователя: «поставить будильник», «узнать погоду»…"""

    __tablename__ = "intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    scenario: Mapped[Scenario] = relationship(back_populates="intents")
    slots: Mapped[list["IntentSlot"]] = relationship(
        back_populates="intent", cascade="all, delete-orphan"
    )
    utterances: Mapped[list["Utterance"]] = relationship(back_populates="intent")


class SlotType(Base):
    """Тип параметра команды: время, дата, место…"""

    __tablename__ = "slot_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))


class IntentSlot(Base):
    """Связь «многие-ко-многим» намерений и типов параметров.

    required — без этого параметра команду нельзя выполнить;
    question — что спросить у пользователя, если параметр не указан.
    """

    __tablename__ = "intent_slots"
    __table_args__ = (CheckConstraint("position >= 0", name="ck_intent_slot_position"),)

    intent_id: Mapped[int] = mapped_column(ForeignKey("intents.id"), primary_key=True)
    slot_type_id: Mapped[int] = mapped_column(ForeignKey("slot_types.id"), primary_key=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(default=0)  # порядок, в котором задаются вопросы
    question: Mapped[str] = mapped_column(String(200))

    intent: Mapped[Intent] = relationship(back_populates="slots")
    slot_type: Mapped[SlotType] = relationship()


class Utterance(Base):
    """Фраза-пример из датасета MASSIVE с размеченным намерением."""

    __tablename__ = "utterances"
    __table_args__ = (
        CheckConstraint("partition IN ('train', 'dev', 'test')", name="ck_utterance_partition"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(20), unique=True)  # id в MASSIVE
    text: Mapped[str] = mapped_column(Text)
    annotated: Mapped[str] = mapped_column(Text)
    partition: Mapped[str] = mapped_column(String(10), index=True)
    intent_id: Mapped[int] = mapped_column(ForeignKey("intents.id"), index=True)

    intent: Mapped[Intent] = relationship(back_populates="utterances")
