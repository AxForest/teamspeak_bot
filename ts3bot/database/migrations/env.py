import os
import sys
from logging.config import fileConfig

from alembic import context  # type: ignore
from sqlalchemy import create_engine, pool

# Force module path
sys.path.insert(
    0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from ts3bot.config import Config
from ts3bot.database.models.base import Base

# Load custom config
Config.load()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = Config.get("database", "uri")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    database_uri = Config.get("database", "uri")
    if database_uri.startswith("sqlite"):
        connectable = create_engine(
            database_uri,
            connect_args={"check_same_thread": False},
            poolclass=pool.NullPool,
        )
    else:
        connectable = create_engine(database_uri, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=database_uri.startswith("sqlite"),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
