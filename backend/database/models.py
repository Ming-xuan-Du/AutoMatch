from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.connection import Base


def utc_now():
    return datetime.now(timezone.utc)


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    source_listing_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(
        String(300), nullable=False
    )

    year: Mapped[int | None] = mapped_column(Integer)
    price_cash: Mapped[int | None] = mapped_column(Integer)
    price_finance: Mapped[int | None] = mapped_column(Integer)
    mileage_km: Mapped[int | None] = mapped_column(Integer)

    exterior_color: Mapped[str | None] = mapped_column(String(100))
    stock_no: Mapped[str | None] = mapped_column(String(100))
    doors: Mapped[int | None] = mapped_column(Integer)
    body_style: Mapped[str | None] = mapped_column(String(100))
    transmission: Mapped[str | None] = mapped_column(String(100))
    drivetrain: Mapped[str | None] = mapped_column(String(100))
    engine: Mapped[str | None] = mapped_column(String(100))
    vin: Mapped[str | None] = mapped_column(String(100))

    listing_url: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    image_url: Mapped[str | None] = mapped_column(Text)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    is_active: Mapped[bool] = mapped_column(default=True)

    missing_streak: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    total_vehicles: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    source_file: Mapped[str | None] = mapped_column(Text)

    
    # Identifies one independent scraper execution.
    # Nullable so existing snapshots remain valid.
    crawl_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=True,
    )

    # SHA-256 fingerprint of the crawl contents.
    payload_hash: Mapped[str | None] = mapped_column(
        String(64)
    )

    # success / partial
    status: Mapped[str | None] = mapped_column(
        String(20)
    )

    pages_expected: Mapped[int] = mapped_column(
        Integer, nullable=False,
        default=0, server_default="0",
    )

    pages_seen: Mapped[int] = mapped_column(
        Integer, nullable=False,
        default=0, server_default="0",
    )

    added: Mapped[int] = mapped_column(
        Integer, nullable=False,
        default=0, server_default="0",
    )

    updated: Mapped[int] = mapped_column(
        Integer, nullable=False,
        default=0, server_default="0",
    )

    unchanged: Mapped[int] = mapped_column(
        Integer, nullable=False,
        default=0, server_default="0",
    )

    suspected_missing: Mapped[int] = mapped_column(
        Integer, nullable=False,
        default=0, server_default="0",
    )

    inactive: Mapped[int] = mapped_column(
        Integer, nullable=False,
        default=0, server_default="0",
    )

    error_detail: Mapped[str | None] = mapped_column(
        Text
    )



class InventoryChange(Base):
    __tablename__ = "inventory_changes"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_snapshots.id"),
        nullable=False,
    )

    source_listing_id: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    change_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    changes: Mapped[dict | None] = mapped_column(JSON)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    snapshot: Mapped["InventorySnapshot"] = relationship()