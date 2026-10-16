"""JWT cho access token; refresh token là chuỗi ngẫu nhiên, DB chỉ lưu hash."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import Settings
from app.core.errors import AppError

ALGORITHM = "HS256"


@dataclass(frozen=True)
class Principal:
    device_id: str
    user_id: int | None
    role: str

    @property
    def actor_key(self) -> str:
        """Khoá đếm nguồn độc lập: tài khoản nếu có, nếu không thì thiết bị."""
        return f"user:{self.user_id}" if self.user_id else f"device:{self.device_id}"


def create_access_token(settings: Settings, principal: Principal, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    payload = {
        "sub": principal.device_id,
        "uid": principal.user_id,
        "role": principal.role,
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_ttl_min)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(settings: Settings, token: str) -> Principal:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AppError("TOKEN_EXPIRED", "Phiên đăng nhập đã hết hạn", status_code=401) from exc
    except jwt.PyJWTError as exc:
        raise AppError("INVALID_TOKEN", "Token không hợp lệ", status_code=401) from exc
    if payload.get("typ") != "access":
        raise AppError("INVALID_TOKEN", "Token không hợp lệ", status_code=401)
    return Principal(
        device_id=payload["sub"], user_id=payload.get("uid"), role=payload.get("role", "citizen")
    )


def new_refresh_token() -> tuple[str, str]:
    """Trả về (token gửi client, hash lưu DB)."""
    token = secrets.token_urlsafe(32)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
