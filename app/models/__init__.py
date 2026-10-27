"""SQLAlchemy-модели. Импорт здесь нужен, чтобы Alembic видел все таблицы."""

from app.models.catalog import Intent, IntentSlot, Scenario, SlotType, Utterance
from app.models.commands import COMMAND_STATUSES, Command, CommandSlot, User

__all__ = [
    "COMMAND_STATUSES",
    "Command",
    "CommandSlot",
    "Intent",
    "IntentSlot",
    "Scenario",
    "SlotType",
    "User",
    "Utterance",
]
