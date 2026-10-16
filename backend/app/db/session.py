from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        # API luôn trả thời gian UTC; client tự đổi sang giờ Việt Nam khi hiển thị.
        connect_args={"options": "-c timezone=UTC"},
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependency FastAPI: một session cho mỗi request."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
