"""Persist outbound send gates and exclusive lease fields.

Revision ID: 0002_outbound_send_gates
Revises: 0001_initial
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_outbound_send_gates"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("outbound_messages", sa.Column("send_gate", sa.String(16), nullable=False, server_default="ai"))
    op.add_column(
        "outbound_messages",
        sa.Column("expected_control_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("outbound_messages", sa.Column("expected_inbound_seq", sa.Integer(), nullable=True))
    op.add_column(
        "outbound_messages",
        sa.Column("expected_attention_mode", sa.String(32), nullable=False, server_default="ai_active"),
    )
    op.add_column("outbound_messages", sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbound_messages", sa.Column("leased_by", sa.String(80), nullable=True))
    op.create_index("ix_outbound_messages_status", "outbound_messages", ["status"])


def downgrade() -> None:
    op.drop_index("ix_outbound_messages_status", table_name="outbound_messages")
    op.drop_column("outbound_messages", "leased_by")
    op.drop_column("outbound_messages", "leased_until")
    op.drop_column("outbound_messages", "expected_attention_mode")
    op.drop_column("outbound_messages", "expected_inbound_seq")
    op.drop_column("outbound_messages", "expected_control_version")
    op.drop_column("outbound_messages", "send_gate")
