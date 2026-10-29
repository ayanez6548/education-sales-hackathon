"""Schedule outbound retries with available_at.

Revision ID: 0003_outbound_available_at
Revises: 0002_outbound_send_gates
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_outbound_available_at"
down_revision: Union[str, Sequence[str], None] = "0002_outbound_send_gates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outbound_messages",
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_outbound_messages_available_at", "outbound_messages", ["available_at"])


def downgrade() -> None:
    op.drop_index("ix_outbound_messages_available_at", table_name="outbound_messages")
    op.drop_column("outbound_messages", "available_at")
