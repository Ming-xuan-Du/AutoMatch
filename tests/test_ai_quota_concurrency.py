
"""Concurrent PostgreSQL AI quota tests.

Creates an isolated PostgreSQL schema per test.
Never changes public.ai_extraction_attempts.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from backend.ai.quota_service import (
    AIQuotaExceeded,
    QuotaLimits,
    reserve_ai_extraction,
)
from backend.database.connection import engine
from backend.database.models import AIExtractionAttempt


@pytest.fixture
def isolated_quota_sessions():
    """Create a separate schema for concurrent tests."""

    schema = f"automatch_quota_test_{uuid.uuid4().hex}"

    with engine.begin() as connection:
        connection.exec_driver_sql(
            f'CREATE SCHEMA "{schema}"'
        )

    isolated_engine = engine.execution_options(
        schema_translate_map={None: schema}
    )

    try:
        with isolated_engine.begin() as connection:
            AIExtractionAttempt.__table__.create(
                connection
            )

        yield sessionmaker(
            bind=isolated_engine,
            expire_on_commit=False,
        )

    finally:
        # Remove only this test's generated table/schema.
        with isolated_engine.begin() as connection:
            AIExtractionAttempt.__table__.drop(
                connection,
                checkfirst=True,
            )

        with engine.begin() as connection:
            connection.exec_driver_sql(
                f'DROP SCHEMA "{schema}"'
            )


def run_concurrent_reservations(
    factory,
    visitors,
    limits,
):
    """Start independent reservations concurrently."""

    barrier = Barrier(len(visitors))

    def attempt(visitor_hash):
        barrier.wait(timeout=15)

        try:
            reservation_id = reserve_ai_extraction(
                factory,
                visitor_hash,
                limits=limits,
            )
            return ("granted", reservation_id)

        except AIQuotaExceeded as exc:
            return ("limited", exc.reason)

    with ThreadPoolExecutor(
        max_workers=len(visitors)
    ) as executor:
        return list(
            executor.map(attempt, visitors)
        )


def count_attempts(factory):
    with factory() as session:
        return session.scalar(
            select(
                func.count(AIExtractionAttempt.id)
            )
        )


def test_concurrent_requests_respect_global_slot(
    isolated_quota_sessions,
):
    """Only one concurrent reservation is granted."""

    visitors = [
        f"{index:064x}"
        for index in range(8)
    ]

    limits = QuotaLimits(
        visitor_per_hour=10,
        global_per_day=20,
        global_per_month=20,
        max_concurrent=1,
    )

    results = run_concurrent_reservations(
        isolated_quota_sessions,
        visitors,
        limits,
    )

    granted = [
        value
        for status, value in results
        if status == "granted"
    ]

    rejected = [
        value
        for status, value in results
        if status == "limited"
    ]

    assert len(granted) == 1
    assert len(rejected) == 7
    assert all(
        reason == "concurrency"
        for reason in rejected
    )

    assert count_attempts(
        isolated_quota_sessions
    ) == 1


def test_concurrent_requests_respect_daily_quota(
    isolated_quota_sessions,
):
    """Requests cannot race past the global daily cap."""

    visitors = [
        f"{index:064x}"
        for index in range(8)
    ]

    limits = QuotaLimits(
        visitor_per_hour=10,
        global_per_day=3,
        global_per_month=20,
        max_concurrent=8,
    )

    results = run_concurrent_reservations(
        isolated_quota_sessions,
        visitors,
        limits,
    )

    granted = [
        value
        for status, value in results
        if status == "granted"
    ]

    rejected = [
        value
        for status, value in results
        if status == "limited"
    ]

    assert len(granted) == 3
    assert len(rejected) == 5
    assert all(
        reason == "global_day"
        for reason in rejected
    )

    assert count_attempts(
        isolated_quota_sessions
    ) == 3
