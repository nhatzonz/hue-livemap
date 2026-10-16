from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (đăng ký model vào metadata)
from app.core.config import get_settings
from app.db.base import Base

config = context.config
target_metadata = Base.metadata


def get_url() -> str:
    # Cho phép test truyền URL riêng: alembic_cfg.attributes["database_url"]
    return config.attributes.get("database_url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
