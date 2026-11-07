
"""Create the original AutoMatch database schema.

Revision ID: 83bf07dc056d
Revises:
Create Date: 2026-11-01 19:35:58.997790

The original revision was an empty baseline for an
already-initialized local database.

This revision now creates the foundational schema
when migrations run on a fresh PostgreSQL database.

Fields introduced by later revisions are intentionally
excluded here.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "83bf07dc056d"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the original inventory tables."""

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "source_listing_id",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=300),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("price_cash", sa.Integer(), nullable=True),
        sa.Column("price_finance", sa.Integer(), nullable=True),
        sa.Column("mileage_km", sa.Integer(), nullable=True),
        sa.Column(
            "exterior_color",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "stock_no",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column("doors", sa.Integer(), nullable=True),
        sa.Column(
            "body_style",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "transmission",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "drivetrain",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "engine",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "vin",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "listing_url",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_vehicles_source_listing_id",
        "vehicles",
        ["source_listing_id"],
        unique=True,
    )

    op.create_table(
        "inventory_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "total_vehicles",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "source_file",
            sa.Text(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "inventory_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "snapshot_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "source_listing_id",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "change_type",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "changes",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["inventory_snapshots.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Remove foundational inventory tables."""

    op.drop_table("inventory_changes")
    op.drop_table("inventory_snapshots")

    op.drop_index(
        "ix_vehicles_source_listing_id",
        table_name="vehicles",
    )
    op.drop_table("vehicles")
