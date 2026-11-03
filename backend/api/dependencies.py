from collections.abc import Generator

from sqlalchemy.orm import Session

from backend.database.connection import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Provide one SQLAlchemy session per API request.

    Reuses the existing PostgreSQL session factory.
    Does not commit or modify inventory.
    """
    with SessionLocal() as session:
        yield session