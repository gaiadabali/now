from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from now_platform_db.settings import platform_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No ORM metadata object: migrations are hand-written SQL (DDL is easier to
# review and reason about than autogenerate diffs for a schema this size).
target_metadata = None


def get_url() -> str:
    return config.get_main_option("sqlalchemy.url") or platform_database_url()


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="engine",
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Ensure the schema exists on its own short-lived autocommit connection,
    # *before* opening the connection Alembic will manage transactionally
    # below. Running this DDL on the same connection ahead of
    # `context.configure`/`begin_transaction` was tried first and silently
    # dropped every migration on rollback: the bare `execute()` auto-begins
    # a transaction that Alembic's own `begin_transaction()` then treats as
    # already-owned and never commits on exit.
    with connectable.connect().execution_options(isolation_level="AUTOCOMMIT") as bootstrap:
        bootstrap.execute(text("CREATE SCHEMA IF NOT EXISTS engine"))

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_version",
            version_table_schema="engine",
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
