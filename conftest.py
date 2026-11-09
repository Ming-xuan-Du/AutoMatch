"""Prevent pytest from targeting a non-test database."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def pytest_sessionstart(session):
    from backend.database.connection import engine

    if os.getenv("AUTOMATCH_RUN_DB_TESTS") != "1":
        raise pytest.UsageError(
            "Set AUTOMATCH_RUN_DB_TESTS=1 only after "
            "configuring a dedicated test database."
        )

    url = engine.url
    host = (url.host or "").lower()

    if (
        engine.dialect.name != "postgresql"
        or host not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }
        or url.database != "automatch_test"
    ):
        raise pytest.UsageError(
            "Backend tests require a local PostgreSQL "
            "database named automatch_test."
        )

    try:
        with engine.connect() as connection:
            actual_database = connection.scalar(
                text("SELECT current_database()")
            )
    except SQLAlchemyError as exc:
        raise pytest.UsageError(
            "Cannot verify the dedicated test database."
        ) from exc

    if actual_database != "automatch_test":
        raise pytest.UsageError(
            "Connected database is not automatch_test."
        )