from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Command, DialogueSession, User
from app.services import commands
from app.services.profiles import ensure_owner


def test_legacy_profile_keeps_history_and_receipt(loaded_db: Session) -> None:
    db = loaded_db
    legacy = User(username="voice_dialogue", name="Голосовой диалог")
    db.add(legacy)
    db.commit()
    old_id = legacy.id
    command = commands.create_command(db, old_id, "поставь будильник через минуту")
    db.add(
        DialogueSession(
            command_id=command.id,
            phase="executed",
            operation_id="browser-1",
            execution_success=True,
            execution_message="Будильник установлен",
        )
    )
    db.commit()
    owner = ensure_owner(db)
    assert owner.id == old_id
    assert owner.username == "maksim_ivanov"
    assert owner.name == "maksim ivanov"
    assert db.get(Command, command.id).user_id == owner.id
    assert db.get(DialogueSession, command.id).execution_success is True
    assert ensure_owner(db).id == old_id
    assert db.scalar(select(func.count()).select_from(User)) == 2


def test_existing_owner_receives_only_legacy_commands(loaded_db: Session) -> None:
    db = loaded_db
    owner = User(username="maksim_ivanov", name="Максим")
    legacy = User(username="voice_dialogue", name="Голосовой диалог")
    db.add_all([owner, legacy])
    db.commit()
    other = db.scalar(select(User).where(User.username == "ivan"))
    own_command = commands.create_command(db, legacy.id, "поставь будильник через минуту")
    other_command = commands.create_command(db, other.id, "поставь будильник через минуту")
    assert ensure_owner(db).id == owner.id
    db.expire_all()
    assert db.get(Command, own_command.id).user_id == owner.id
    assert db.get(Command, other_command.id).user_id == other.id
    assert db.get(User, owner.id).name == "maksim ivanov"
    assert ensure_owner(db).id == owner.id
