
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError

from backend.database.models import AIExtractionAttempt


def test_ai_usage_schema_and_reservation():
    """Verify that the usage table can store reservations."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    table = AIExtractionAttempt.__table__
    table.create(engine)

    inspector = inspect(engine)

    assert inspector.has_table("ai_extraction_attempts")

    column_names = {
        column["name"]
        for column in inspector.get_columns(
            "ai_extraction_attempts"
        )
    }

    assert column_names == {
        "id",
        "visitor_hash",
        "created_at",
        "lease_expires_at",
        "status",
    }

    index_names = {
        index["name"]
        for index in inspector.get_indexes(
            "ai_extraction_attempts"
        )
    }

    assert index_names == {
        "ix_ai_extraction_attempts_visitor_created",
        "ix_ai_extraction_attempts_created_at",
        "ix_ai_extraction_attempts_status_lease",
    }

    expires_at = datetime.now(
        timezone.utc
    ) + timedelta(minutes=2)

    with engine.begin() as connection:
        connection.execute(
            table.insert().values(
                visitor_hash="a" * 64,
                lease_expires_at=expires_at,
            )
        )

        row = connection.execute(
            select(table)
        ).one()

    assert row.visitor_hash == "a" * 64
    assert row.status == "reserved"
    assert row.created_at is not None
    assert row.lease_expires_at is not None

    engine.dispose()


def test_ai_usage_schema_rejects_invalid_status():
    """Only recognized reservation states are allowed."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    table = AIExtractionAttempt.__table__
    table.create(engine)

    expires_at = datetime.now(
        timezone.utc
    ) + timedelta(minutes=2)

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                table.insert().values(
                    visitor_hash="b" * 64,
                    lease_expires_at=expires_at,
                    status="unknown",
                )
            )

    engine.dispose()
