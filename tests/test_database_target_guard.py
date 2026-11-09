from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from backend.database.target_guard import (
    UnsafeDatabaseTarget,
    require_local_write_target,
)


TEST_URL = (
    "postgresql+psycopg://tester:dummy"
    "@127.0.0.1:5432/automatch_test"
)


def fake_engine(
    url=TEST_URL,
    *,
    dialect="postgresql",
    actual_database="automatch_test",
):
    @contextmanager
    def connect():
        yield SimpleNamespace(
            scalar=lambda statement: actual_database
        )

    return SimpleNamespace(
        url=make_url(url),
        dialect=SimpleNamespace(name=dialect),
        connect=connect,
    )


def test_matching_local_database_is_allowed():
    require_local_write_target(
        fake_engine(),
        confirmed_database="automatch_test",
    )


@pytest.mark.parametrize(
    "confirmation",
    [None, "", " automatch_test", "automatch_test "],
)
def test_missing_or_invalid_confirmation_is_rejected(
    confirmation,
):
    with pytest.raises(UnsafeDatabaseTarget):
        require_local_write_target(
            fake_engine(),
            confirmed_database=confirmation,
        )


def test_wrong_database_name_is_rejected():
    with pytest.raises(
        UnsafeDatabaseTarget,
        match="Configured database name",
    ):
        require_local_write_target(
            fake_engine(),
            confirmed_database="automatch",
        )


def test_remote_database_is_rejected():
    remote = fake_engine(
        url=(
            "postgresql+psycopg://tester:dummy"
            "@db.example.com/automatch_test"
        )
    )

    with pytest.raises(
        UnsafeDatabaseTarget,
        match="Remote database",
    ):
        require_local_write_target(
            remote,
            confirmed_database="automatch_test",
        )


def test_sqlite_is_rejected():
    with pytest.raises(
        UnsafeDatabaseTarget,
        match="PostgreSQL",
    ):
        require_local_write_target(
            fake_engine(
                url="sqlite:///:memory:",
                dialect="sqlite",
            ),
            confirmed_database="automatch_test",
        )


def test_actual_database_mismatch_is_rejected():
    with pytest.raises(
        UnsafeDatabaseTarget,
        match="Connected database",
    ):
        require_local_write_target(
            fake_engine(actual_database="automatch"),
            confirmed_database="automatch_test",
        )