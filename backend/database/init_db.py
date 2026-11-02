from backend.database.connection import Base, engine
from backend.database import models  # noqa: F401


def init_db():
    Base.metadata.create_all(bind=engine)
    print("AutoMatch database tables created successfully!")


if __name__ == "__main__":
    init_db()