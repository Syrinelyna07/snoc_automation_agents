"""Operational indexes, execution revision uniqueness, and safe outbox claims.

Revision ID: c71a9c65f423
Revises: 8bb4f2a91c7e
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c71a9c65f423"
down_revision: str | None = "8bb4f2a91c7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("executions") as batch:
        batch.create_unique_constraint(
            "uq_execution_operation_revision",
            ["operation_id", "operation_revision"],
        )
        batch.create_index("ix_executions_created_at", ["created_at"])
        batch.create_index("ix_executions_status_created_at", ["status", "created_at"])

    with op.batch_alter_table("outbox_messages") as batch:
        batch.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_outbox_messages_next_attempt_at", ["next_attempt_at"])
        batch.create_index("ix_outbox_messages_claimed_at", ["claimed_at"])
        batch.create_index("ix_outbox_messages_dead_lettered_at", ["dead_lettered_at"])
        batch.create_index(
            "ix_outbox_messages_status_created_at",
            ["status", "created_at"],
        )

    with op.batch_alter_table("email_messages") as batch:
        batch.create_index("ix_email_messages_direction_created_at", ["direction", "created_at"])
        batch.create_index(
            "ix_email_messages_authorization_created_at",
            ["authorization_allowed", "created_at"],
        )
    with op.batch_alter_table("requests") as batch:
        batch.create_index("ix_requests_status_created_at", ["status", "created_at"])
    with op.batch_alter_table("operations") as batch:
        batch.create_index("ix_operations_action_created_at", ["action", "created_at"])
        batch.create_index("ix_operations_status_created_at", ["status", "created_at"])
    with op.batch_alter_table("model_runs") as batch:
        batch.create_index("ix_model_runs_stage_created_at", ["stage", "created_at"])
    with op.batch_alter_table("escalations") as batch:
        batch.create_index("ix_escalations_status_created_at", ["status", "created_at"])


def downgrade() -> None:
    with op.batch_alter_table("escalations") as batch:
        batch.drop_index("ix_escalations_status_created_at")
    with op.batch_alter_table("model_runs") as batch:
        batch.drop_index("ix_model_runs_stage_created_at")
    with op.batch_alter_table("operations") as batch:
        batch.drop_index("ix_operations_status_created_at")
        batch.drop_index("ix_operations_action_created_at")
    with op.batch_alter_table("requests") as batch:
        batch.drop_index("ix_requests_status_created_at")
    with op.batch_alter_table("email_messages") as batch:
        batch.drop_index("ix_email_messages_authorization_created_at")
        batch.drop_index("ix_email_messages_direction_created_at")

    with op.batch_alter_table("outbox_messages") as batch:
        batch.drop_index("ix_outbox_messages_status_created_at")
        batch.drop_index("ix_outbox_messages_dead_lettered_at")
        batch.drop_index("ix_outbox_messages_claimed_at")
        batch.drop_index("ix_outbox_messages_next_attempt_at")
        batch.drop_column("dead_lettered_at")
        batch.drop_column("claimed_at")
        batch.drop_column("next_attempt_at")

    with op.batch_alter_table("executions") as batch:
        batch.drop_index("ix_executions_status_created_at")
        batch.drop_index("ix_executions_created_at")
        batch.drop_constraint("uq_execution_operation_revision", type_="unique")
