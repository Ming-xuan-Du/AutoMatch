from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
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
class AnomalyFlag(Base):
    __tablename__ = "anomaly_flags"

    __table_args__ = (
        CheckConstraint(
            "detector IN ('rule', 'model')",
            name="ck_anomaly_flags_detector",
        ),
        CheckConstraint(
            "review_status IN "
            "('pending', 'valid_issue', 'false_alarm')",
            name="ck_anomaly_flags_review_status",
        ),
        Index(
            "ix_anomaly_flags_review_status_detector",
            "review_status",
            "detector",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    inventory_change_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "inventory_changes.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    detector: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    issue_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    evidence: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    fingerprint: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    model_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    review_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    reviewer_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    vehicle: Mapped["Vehicle"] = relationship()

    inventory_change: Mapped[
        "InventoryChange | None"
    ] = relationship()

    review_events: Mapped[
        list["AnomalyReviewEvent"]
    ] = relationship(
        back_populates="anomaly",
        order_by="AnomalyReviewEvent.id",
    )


class AnomalyReviewEvent(Base):
    __tablename__ = "anomaly_review_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    anomaly_flag_id: Mapped[int] = mapped_column(
        ForeignKey(
            "anomaly_flags.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    previous_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    new_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    previous_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    new_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    anomaly: Mapped["AnomalyFlag"] = relationship(
        back_populates="review_events",
    )


class AIExtractionAttempt(Base):
    """A granted AI extraction quota reservation.

    Never store raw IP addresses, customer statements,
    API keys, or model responses in this table.
    """

    __tablename__ = "ai_extraction_attempts"

    __table_args__ = (
        CheckConstraint(
            "status IN ('reserved', 'completed', 'failed')",
            name="ck_ai_extraction_attempts_status",
        ),
        Index(
            "ix_ai_extraction_attempts_visitor_created",
            "visitor_hash",
            "created_at",
        ),
        Index(
            "ix_ai_extraction_attempts_created_at",
            "created_at",
        ),
        Index(
            "ix_ai_extraction_attempts_status_lease",
            "status",
            "lease_expires_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    visitor_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    lease_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="reserved",
        server_default="reserved",
    )
