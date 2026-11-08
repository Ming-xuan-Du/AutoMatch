
"""Add persistent AI extraction usage reservations.

Revision ID: e24c8a7d9f10
Revises: b492ba2cacee

Stores quota reservations without customer text,
raw visitor IP addresses, or API credentials.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e24c8a7d9f10"

down_revision: Union[str, Sequence[str], None] = (
    "b492ba2cacee"
)

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_extraction_attempts",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "visitor_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="reserved",
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'completed', 'failed')",
            name="ck_ai_extraction_attempts_status",
        ),
    )

    op.create_index(
        "ix_ai_extraction_attempts_visitor_created",
        "ai_extraction_attempts",
        ["visitor_hash", "created_at"],
    )

    op.create_index(
        "ix_ai_extraction_attempts_created_at",
        "ai_extraction_attempts",
        ["created_at"],
    )

    op.create_index(
        "ix_ai_extraction_attempts_status_lease",
        "ai_extraction_attempts",
        ["status", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_extraction_attempts_status_lease",
        table_name="ai_extraction_attempts",
    )

    op.drop_index(
        "ix_ai_extraction_attempts_created_at",
        table_name="ai_extraction_attempts",
    )

    op.drop_index(
        "ix_ai_extraction_attempts_visitor_created",
        table_name="ai_extraction_attempts",
    )

    op.drop_table("ai_extraction_attempts")
