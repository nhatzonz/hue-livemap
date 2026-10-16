import ipaddress
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import DB, AppSettings
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import Principal, create_access_token, hash_refresh_token, new_refresh_token

router = APIRouter(prefix="/auth", tags=["auth"])


class DeviceRegistration(BaseModel):
    device_id: uuid.UUID
    platform: Annotated[str | None, Field(max_length=20)] = None
    app_version: Annotated[str | None, Field(max_length=20)] = None


def client_ip(request: Request) -> str | None:
    """IP client nếu hợp lệ. Sau reverse proxy (Caddy) cần bật proxy headers của uvicorn để lấy IP thật."""
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


class RefreshRequest(BaseModel):
    refresh_token: Annotated[str, Field(min_length=20, max_length=200)]


def issue_tokens(db, settings: Settings, principal: Principal, now: datetime) -> dict:
    token, token_hash = new_refresh_token()
    db.execute(
        text("""
            INSERT INTO refresh_token (id, device_id, token_hash, expires_at)
            VALUES (:id, :device, :hash, :exp)
        """),
        {
            "id": uuid.uuid4(),
            "device": principal.device_id,
            "hash": token_hash,
            "exp": now + timedelta(days=settings.refresh_token_ttl_days),
        },
    )
    return {
        "access_token": create_access_token(settings, principal, now),
        "token_type": "bearer",
        "expires_in": settings.access_token_ttl_min * 60,
        "refresh_token": token,
        "device_id": principal.device_id,
        "role": principal.role,
    }


@router.post("/device")
def register_device(body: DeviceRegistration, request: Request, db: DB, settings: AppSettings):
    """Đăng ký (hoặc đăng nhập lại khi mất refresh token) thiết bị ẩn danh. Không cần tài khoản.

    Đăng nhập lại thu hồi mọi refresh token cũ của thiết bị: mỗi thiết bị chỉ có một phiên hiệu lực.
    """
    now = datetime.now(UTC)
    ip = client_ip(request)
    existing = db.execute(
        text("SELECT user_id, is_banned FROM device WHERE id = :id"), {"id": body.device_id}
    ).one_or_none()

    if existing is None:
        if ip:
            recent = db.execute(
                text("SELECT count(*) FROM device WHERE created_ip = :ip AND created_at > :since"),
                {"ip": ip, "since": now - timedelta(hours=1)},
            ).scalar_one()
            if recent >= settings.max_devices_per_ip_hour:
                raise AppError("RATE_LIMITED", "Quá nhiều thiết bị mới từ cùng địa chỉ mạng", status_code=429)
        # ON CONFLICT: hai request đăng ký đồng thời cùng id không gây lỗi 500
        db.execute(
            text("""
                INSERT INTO device (id, platform, app_version, created_ip, last_seen_at)
                VALUES (:id, :platform, :version, CAST(:ip AS inet), :now)
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": body.device_id,
                "platform": body.platform,
                "version": body.app_version,
                "ip": ip,
                "now": now,
            },
        )
        user_id, role = None, "citizen"
    else:
        if existing.is_banned:
            raise AppError("DEVICE_BANNED", "Thiết bị đã bị chặn gửi dữ liệu", status_code=403)
        user_id = existing.user_id
        role = (
            db.execute(text("SELECT role FROM app_user WHERE id = :id"), {"id": user_id}).scalar_one()
            if user_id
            else "citizen"
        )
        db.execute(
            text("UPDATE device SET app_version = :version, last_seen_at = :now WHERE id = :id"),
            {"id": body.device_id, "version": body.app_version, "now": now},
        )
        db.execute(
            text("UPDATE refresh_token SET revoked_at = :now WHERE device_id = :id AND revoked_at IS NULL"),
            {"id": body.device_id, "now": now},
        )

    tokens = issue_tokens(db, settings, Principal(str(body.device_id), user_id, role), now)
    db.commit()
    return tokens


@router.post("/refresh")
def refresh(body: RefreshRequest, db: DB, settings: AppSettings):
    """Đổi refresh token lấy cặp token mới. Thu hồi nguyên tử: mỗi token chỉ dùng được đúng một lần,
    kể cả khi hai request đồng thời gửi cùng token."""
    now = datetime.now(UTC)
    row = db.execute(
        text("""
            WITH used AS (
              UPDATE refresh_token SET revoked_at = :now
              WHERE token_hash = :hash AND revoked_at IS NULL AND expires_at > :now
              RETURNING device_id
            )
            SELECT d.id AS device_id, d.user_id, d.is_banned, coalesce(u.role, 'citizen') AS role
            FROM used JOIN device d ON d.id = used.device_id
            LEFT JOIN app_user u ON u.id = d.user_id
        """),
        {"hash": hash_refresh_token(body.refresh_token), "now": now},
    ).one_or_none()
    if row is None:
        raise AppError("INVALID_REFRESH_TOKEN", "Phiên đăng nhập không còn hiệu lực", status_code=401)
    if row.is_banned:
        db.commit()  # giữ việc thu hồi token
        raise AppError("DEVICE_BANNED", "Thiết bị đã bị chặn gửi dữ liệu", status_code=403)

    tokens = issue_tokens(db, settings, Principal(str(row.device_id), row.user_id, row.role), now)
    db.commit()
    return tokens
