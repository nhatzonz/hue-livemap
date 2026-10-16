import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import text

from app.api.deps import DB, AppSettings, CurrentPrincipal
from app.api.v1.segments import Vis
from app.core.config import Settings, get_settings
from app.services import media as media_service
from app.services import reports as service
from app.services.storage import LocalDiskStorage, Storage

router = APIRouter(tags=["reports"])


class LatLon(BaseModel):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]


class ReportCreate(BaseModel):
    id: uuid.UUID = Field(description="UUID do client sinh, dùng để gửi lại an toàn từ hàng đợi offline")
    dimension: Literal["flood", "obstacle", "traffic"]
    category: Annotated[str, Field(max_length=30)]
    level: Annotated[str, Field(max_length=30)]
    description: Annotated[str | None, Field(max_length=280)] = None
    location: LatLon
    reporter_location: LatLon | None = None
    gps_accuracy_m: Annotated[float | None, Field(ge=0, le=5000)] = None
    segment_code: Annotated[str | None, Field(max_length=30)] = None
    client_created_at: AwareDatetime


def get_storage(settings: Annotated[Settings, Depends(get_settings)]) -> Storage:
    return LocalDiskStorage(settings.media_dir)


@router.get("/snap")
def snap(
    db: DB,
    vis: Vis,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
):
    """Tối đa 3 đoạn trong 30 m quanh vị trí, để người dùng chọn khi đứng ở giao lộ."""
    point = service.Point(lat, lon)
    return {
        "in_pilot_area": service.in_pilot_area(db, point),
        "candidates": [
            {k: c[k] for k in ("code", "name", "segment_type", "distance_m")}
            for c in service.snap_candidates(db, vis, point)
        ],
    }


@router.post("/reports", status_code=201)
def create_report(
    body: ReportCreate,
    response: Response,
    db: DB,
    settings: AppSettings,
    vis: Vis,
    principal: CurrentPrincipal,
):
    summary, created = service.create_report(db, settings, vis, principal, body, datetime.now(UTC))
    if not created:
        response.status_code = 200
    return summary


@router.put("/reports/{report_id}/media", status_code=201)
def upload_media(
    report_id: uuid.UUID,
    db: DB,
    settings: AppSettings,
    principal: CurrentPrincipal,
    storage: Annotated[Storage, Depends(get_storage)],
    file: Annotated[UploadFile, File(description="Ảnh JPEG/PNG/WebP, tối đa 5 MB")],
):
    raw = file.file.read(settings.max_upload_bytes + 1)
    return media_service.attach_photo(db, settings, storage, principal, report_id, raw, datetime.now(UTC))


@router.get("/me/reports")
def my_reports(db: DB, principal: CurrentPrincipal, limit: Annotated[int, Query(ge=1, le=100)] = 50):
    rows = db.execute(
        text("""
            SELECT r.id, r.dimension, r.category, r.level, r.status, r.client_created_at, r.received_at,
                   s.code AS segment_code, s.display_name AS segment_name, i.status AS incident_status,
                   (SELECT count(*) FROM report_media m WHERE m.report_id = r.id) AS photo_count
            FROM report r
            LEFT JOIN road_segment s ON s.id = r.segment_id
            LEFT JOIN incident i ON i.id = r.incident_id
            WHERE r.device_id = :device
            ORDER BY r.received_at DESC LIMIT :limit
        """),
        {"device": principal.device_id, "limit": limit},
    ).all()
    return {
        "reports": [
            {
                "id": str(r.id),
                "dimension": r.dimension,
                "category": r.category,
                "level": r.level,
                "status": r.status,
                "incident_status": r.incident_status,
                "created_at": r.client_created_at.isoformat(),
                "segment": {"code": r.segment_code, "name": r.segment_name} if r.segment_code else None,
                "photo_count": r.photo_count,
            }
            for r in rows
        ]
    }
