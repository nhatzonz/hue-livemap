from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import error_body
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def liveness():
    """Process đang sống (không kiểm tra phụ thuộc)."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: Annotated[Session, Depends(get_db)]):
    """Sẵn sàng phục vụ: DB kết nối được và có PostGIS. Trả phiên bản để đối chiếu dev/prod."""
    try:
        row = db.execute(
            text("SELECT current_setting('server_version') AS pg, postgis_lib_version() AS postgis")
        ).one()
    except SQLAlchemyError as exc:
        return JSONResponse(
            error_body("DB_UNAVAILABLE", "Không kết nối được cơ sở dữ liệu", {"reason": type(exc).__name__}),
            status_code=503,
        )
    return {"status": "ready", "postgres_version": row.pg, "postgis_version": row.postgis}
