"""Safety guard for local administrative database writes."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


LOCAL_HOSTS = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
})


class UnsafeDatabaseTarget(RuntimeError):
    """Database target has not been safely confirmed."""


def require_local_write_target(
    engine,
    *,
    confirmed_database: str | None,
) -> None:
    """Allow an administrative write only to a confirmed local DB."""

    if (
        engine is None
        or engine.dialect.name != "postgresql"
    ):
        raise UnsafeDatabaseTarget(
            "A PostgreSQL database is required."
        )

    if (
        not confirmed_database
        or confirmed_database != confirmed_database.strip()
    ):
        raise UnsafeDatabaseTarget(
            "An exact --confirm-database value is required."
        )

    host = (engine.url.host or "").lower()

    if host not in LOCAL_HOSTS:
        raise UnsafeDatabaseTarget(
            "Remote database writes are disabled."
        )

    if engine.url.database != confirmed_database:
        raise UnsafeDatabaseTarget(
            "Configured database name does not match confirmation."
        )

    try:
        with engine.connect() as connection:
            actual_database = connection.scalar(
                text("SELECT current_database()")
            )
    except SQLAlchemyError as exc:
        raise UnsafeDatabaseTarget(
            "Unable to verify the connected database."
        ) from exc

    if actual_database != confirmed_database:
        raise UnsafeDatabaseTarget(
            "Connected database does not match confirmation."
        )