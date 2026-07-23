from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from snoc_agent.config import load_settings
from snoc_agent.db import models  # noqa: F401
from snoc_agent.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = load_settings()
runtime_url = config.attributes.get("runtime_database_url")
database_value = runtime_url or settings.database_url

database_url = (
    database_value.get_secret_value()
    if hasattr(database_value, "get_secret_value")
    else str(database_value)
)

if not database_url.strip():
    raise RuntimeError("DATABASE_URL is empty. Configure it in backend/.env.")

config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
