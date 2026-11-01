"""Диалог, явное подтверждение пользователя и квитанция исполнителя."""

import sqlalchemy as sa
from alembic import op

revision = "b962ae7d1f40"
down_revision = "a81487dc1c6e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dialogue_sessions",
        sa.Column("command_id", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(30), nullable=False),
        sa.Column("operation_id", sa.String(100), nullable=True),
        sa.Column("execution_success", sa.Boolean(), nullable=True),
        sa.Column("execution_message", sa.String(500), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "phase IN ('clarifying', 'awaiting_confirmation', 'ready', 'executed', "
            "'execution_failed', 'cancelled', 'failed')",
            name="ck_dialogue_phase",
        ),
        sa.ForeignKeyConstraint(["command_id"], ["commands.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("command_id"),
    )
    op.create_index("ix_dialogue_sessions_phase", "dialogue_sessions", ["phase"])


def downgrade() -> None:
    op.drop_index("ix_dialogue_sessions_phase", table_name="dialogue_sessions")
    op.drop_table("dialogue_sessions")
