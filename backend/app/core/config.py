from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = "postgresql+psycopg://localhost:5433/hue_livemap"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    enable_docs: bool = True
    include_demo_data: bool = False
    # false: chỉ trả đoạn đã khảo sát thực địa (field_verified). Dev bật để xem dữ liệu nháp từ OSM.
    show_unverified_segments: bool = False
    log_level: str = "INFO"

    jwt_secret: str = DEV_JWT_SECRET
    access_token_ttl_min: int = 60
    refresh_token_ttl_days: int = 30
    # Chống lạm dụng (PROJECT_PLAN.md mục 9.3)
    max_devices_per_ip_hour: int = 20
    max_reports_per_device_hour: int = 10
    max_reports_per_segment_device_hour: int = 3

    media_dir: str = "var/media"
    max_upload_bytes: int = 5 * 1024 * 1024
    max_photos_per_report: int = 3

    # Job nền (tính suy giảm trạng thái mỗi phút). Tắt trong test.
    enable_jobs: bool = True
    job_interval_s: int = 60

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def production_guards(self):
        # Nguyên tắc dự án: dữ liệu minh hoạ không bao giờ xuất hiện ở production.
        if self.app_env == "production" and self.include_demo_data:
            raise ValueError("INCLUDE_DEMO_DATA phải là false khi APP_ENV=production")
        if self.app_env in ("staging", "production") and (
            self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET phải được đặt (≥ 32 ký tự) ở staging/production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
