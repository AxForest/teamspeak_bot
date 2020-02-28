from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from . import models

# TODO: Properly integrate alembic and run migrations when necessary


def create_session(database_uri: str) -> Session:
    if database_uri.startswith("sqlite"):
        engine = create_engine(
            database_uri, echo=False, connect_args={"check_same_thread": False}
        )
    else:
        engine = create_engine(
            database_uri,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=600,
            pool_size=10,
            pool_use_lifo=True,
            poolclass=QueuePool,
        )
    models.Base.metadata.create_all(engine)
    models.Base.metadata.bind = engine

    session = sessionmaker(bind=engine)()

    return session
