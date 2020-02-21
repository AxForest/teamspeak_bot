from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from . import models

# TODO: Properly integrate alembic and run migrations when necessary


def create_session(database_uri: str) -> Session:
    if database_uri.startswith("sqlite"):
        engine = create_engine(
            database_uri, echo=False, connect_args={"check_same_thread": False}
        )
    else:
        engine = create_engine(database_uri, echo=False)
    models.Base.metadata.create_all(engine)
    models.Base.metadata.bind = engine

    session = sessionmaker(bind=engine)()

    return session
