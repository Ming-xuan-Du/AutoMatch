
import pytest

from backend.database.connection import normalize_database_url


@pytest.mark.parametrize(
    "scheme",
    [
        "postgres",
        "postgresql",
        "postgresql+psycopg",
    ],
)
def test_postgres_urls_use_psycopg3(scheme):
    raw_url = (
        f"{scheme}://demo_user:demo_password"
        "@db.example.com:5432/automatch"
        "?sslmode=require"
    )

    url = normalize_database_url(raw_url)

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "db.example.com"
    assert url.port == 5432
    assert url.database == "automatch"
    assert url.query["sslmode"] == "require"


def test_encoded_credentials_are_preserved():
    raw_url = (
        "postgresql://demo_user:p%40ss%3Aword"
        "@db.example.com/automatch"
        "?sslmode=verify-full"
    )

    url = normalize_database_url(raw_url)

    assert url.username == "demo_user"
    assert url.password == "p@ss:word"
    assert url.query["sslmode"] == "verify-full"


@pytest.mark.parametrize(
    "invalid_url",
    [
        "",
        "sqlite:///test.db",
        "not-a-database-url",
    ],
)
def test_invalid_database_urls_are_rejected(invalid_url):
    with pytest.raises(RuntimeError):
        normalize_database_url(invalid_url)
