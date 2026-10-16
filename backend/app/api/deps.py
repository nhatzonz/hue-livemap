from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import Principal, decode_access_token
from app.db.session import get_db

DB = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_principal(request: Request, db: DB, settings: AppSettings) -> Principal:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError("UNAUTHORIZED", "Cần đăng nhập thiết bị", status_code=401)
    principal = decode_access_token(settings, token)
    banned = db.execute(
        text("SELECT is_banned FROM device WHERE id = :id"), {"id": principal.device_id}
    ).scalar_one_or_none()
    if banned is None:
        raise AppError("UNAUTHORIZED", "Thiết bị chưa đăng ký", status_code=401)
    if banned:
        raise AppError("DEVICE_BANNED", "Thiết bị đã bị chặn gửi dữ liệu", status_code=403)
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
