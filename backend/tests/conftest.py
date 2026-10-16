import os

# Phải đặt trước khi import app: mọi kết nối trong test đi vào DB test riêng.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://localhost:5433/hue_livemap_test"
)

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.db.session import get_db, get_engine  # noqa: E402
from app.main import create_app  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    """Dựng lại schema từ đầu mỗi lần chạy test để kiểm tra luôn cả migration."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_url"] = os.environ["DATABASE_URL"]
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    get_engine().dispose()


@pytest.fixture
def db():
    """Session trong một transaction được rollback sau mỗi test."""
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def settings(tmp_path):
    """Cấu hình test mặc định giống production: ẩn demo, ẩn đoạn chưa khảo sát. Test được chỉnh tại chỗ."""
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=os.environ["DATABASE_URL"],
        include_demo_data=False,
        show_unverified_segments=False,
        enable_jobs=False,
        media_dir=str(tmp_path / "media"),
    )


@pytest.fixture
def client(db, settings):
    """API dùng chung session/transaction của test → thấy dữ liệu test tạo, rollback sau test."""
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app, client=("203.0.113.10", 50000)) as c:  # IP dải tài liệu (RFC 5737)
        yield c
