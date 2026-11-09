from sqlalchemy import text

from backend.database.connection import engine


def test_database_connection():
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT current_database()")
        )

        database_name = result.scalar()

        assert database_name == "automatch_test"
        assert database_name == engine.url.database