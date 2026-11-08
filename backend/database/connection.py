
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, sessionmaker


load_dotenv()


def normalize_database_url(raw_url: str) -> URL:
    """Normalize PostgreSQL URLs to the psycopg 3 driver.

    Preserve credentials, host, database, and query options
    such as sslmode=require.
    """

    if not raw_url or not raw_url.strip():
        raise RuntimeError("DATABASE_URL is missing.")

    try:
        url = make_url(raw_url.strip())
    except (ArgumentError, ValueError):
        raise RuntimeError(
            "DATABASE_URL has an invalid URL format."
        ) from None

    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")

    if url.drivername != "postgresql+psycopg":
        raise RuntimeError(
            "DATABASE_URL must use PostgreSQL "
            "with the psycopg 3 driver."
        )

    return url


DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Check your .env file."
    )

engine = create_engine(
    normalize_database_url(DATABASE_URL),
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass
