import asyncio
import os

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from packages.persistence.models import Base

config = context.config
target_metadata = Base.metadata
url = os.environ.get("PLATFORM_MIGRATION_DATABASE_URL")
if not url or not url.startswith("postgresql+asyncpg://"):
    raise RuntimeError("PLATFORM_MIGRATION_DATABASE_URL must be an async PostgreSQL URL")
# ConfigParser treats percent signs as interpolation syntax.
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))


def run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_async_migrations())
