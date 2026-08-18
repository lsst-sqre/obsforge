"""Alembic migration environment."""

import asyncio
from collections.abc import Mapping
from typing import Any

from safir.database import create_database_engine
from safir.database._connection import build_database_url
from safir.logging import configure_alembic_logging, configure_logging
from sqlalchemy.engine import Connection
from sqlalchemy.schema import MetaData

from alembic import context
from obsforge.config import config
from obsforge.schema import SchemaBase


def _include_name(
    name: str | None, type_: str, parent_names: Mapping[str, Any]
) -> bool:
    """Restrict Alembic autogenerate to schemas owned by ObsForge."""
    if type_ == "schema":
        return name in {None, "ivoa"}
    return True


def _run_migrations_offline(metadata: MetaData) -> None:
    """Run migrations without a database connection."""
    context.configure(
        url=build_database_url(config.database_url, None, is_async=False),
        target_metadata=metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=_include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_migrations_online(metadata: MetaData) -> None:
    """Run migrations using an async database connection."""

    def do_migrations(connection: Connection) -> None:
        context.configure(
            connection=connection,
            target_metadata=metadata,
            include_schemas=True,
            include_name=_include_name,
        )
        with context.begin_transaction():
            context.run_migrations()

    async def run_async_migrations() -> None:
        engine = create_database_engine(
            config.database_url, config.database_password
        )
        async with engine.connect() as connection:
            await connection.run_sync(do_migrations)
        await engine.dispose()

    asyncio.run(run_async_migrations())


# Configure structlog.
configure_logging(name="obsforge", log_level=config.log_level)
configure_alembic_logging()

# Run the migrations.
if context.is_offline_mode():
    _run_migrations_offline(SchemaBase.metadata)
else:
    _run_migrations_online(SchemaBase.metadata)
