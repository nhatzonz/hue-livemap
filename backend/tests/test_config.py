import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_demo_data():
    with pytest.raises(ValidationError):
        Settings(app_env="production", include_demo_data=True, _env_file=None)


def test_cors_origins_from_comma_string():
    settings = Settings(cors_origins="http://a.test, http://b.test", _env_file=None)
    assert settings.cors_origins == ["http://a.test", "http://b.test"]
