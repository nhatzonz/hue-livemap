import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import CurrentPrincipal
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.services import reports as reports_service
from app.services import segments as service

router = APIRouter(tags=["segments"])

Dimension = Literal["flood", "obstacle", "traffic"]
MAX_BBOX_DEG = 0.25  # ≈ 27 km; chặn truy vấn cả nước khi client gửi bbox sai


def get_visibility(settings: Annotated[Settings, Depends(get_settings)]) -> service.Visibility:
    return service.Visibility.from_settings(settings)


DB = Annotated[Session, Depends(get_db)]
Vis = Annotated[service.Visibility, Depends(get_visibility)]


def parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if bbox is None:
        return None
    try:
        minx, miny, maxx, maxy = (float(v) for v in bbox.split(","))
    except ValueError as exc:
        raise AppError("INVALID_BBOX", "bbox phải có dạng minLon,minLat,maxLon,maxLat") from exc
    if not (-180 <= minx < maxx <= 180 and -90 <= miny < maxy <= 90):
        raise AppError("INVALID_BBOX", "bbox không hợp lệ (min phải nhỏ hơn max, trong khoảng toạ độ)")
    if maxx - minx > MAX_BBOX_DEG or maxy - miny > MAX_BBOX_DEG:
        raise AppError("BBOX_TOO_LARGE", f"bbox tối đa {MAX_BBOX_DEG}° mỗi chiều")
    return (minx, miny, maxx, maxy)


@router.get("/segments")
def list_segments(
    request: Request,
    response: Response,
    db: DB,
    vis: Vis,
    dimension: Dimension = "flood",
    bbox: Annotated[str | None, Query(description="minLon,minLat,maxLon,maxLat")] = None,
):
    """Các đoạn trong khung nhìn (GeoJSON) kèm trạng thái của một chiều. Hỗ trợ ETag/304."""
    box = parse_bbox(bbox)
    etag = '"' + hashlib.sha1(service.map_version(db, vis, dimension, box).encode()).hexdigest()[:20] + '"'
    # If-None-Match có thể chứa nhiều ETag, có tiền tố W/ (weak) do proxy thêm vào
    client_tags = {t.strip().removeprefix("W/") for t in request.headers.get("if-none-match", "").split(",")}
    if etag in client_tags:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"
    collection = service.segments_geojson(db, vis, dimension, box)
    collection["meta"] = {"dimension": dimension, "count": len(collection["features"])}
    return collection


@router.get("/segments/{code}")
def get_segment(code: str, db: DB, vis: Vis):
    detail = service.segment_detail(db, vis, code)
    if detail is None:
        raise AppError("SEGMENT_NOT_FOUND", f"Không tìm thấy đoạn {code}", status_code=404)
    return detail


@router.get("/search")
def search(
    db: DB,
    vis: Vis,
    q: Annotated[str, Query(min_length=2, max_length=80)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
):
    """Tìm đoạn theo tên (không dấu cũng được) hoặc mã đoạn."""
    return {"query": q, "results": service.search_segments(db, vis, q.strip(), limit)}


@router.get("/regions/{region_id}")
def get_region(region_id: str, db: DB):
    region = service.pilot_region(db, region_id)
    if region is None:
        raise AppError("REGION_NOT_FOUND", f"Chưa có vùng thí điểm cho {region_id}", status_code=404)
    return region


class ConfirmRequest(BaseModel):
    dimension: Dimension
    still_present: bool = Field(description="true = 'Vẫn còn', false = 'Đã hết'")
    lat: Annotated[float | None, Field(ge=-90, le=90)] = None
    lon: Annotated[float | None, Field(ge=-180, le=180)] = None


@router.post("/segments/{code}/confirm", status_code=201)
def confirm(code: str, body: ConfirmRequest, db: DB, vis: Vis, principal: CurrentPrincipal):
    reporter = (
        reports_service.Point(body.lat, body.lon) if body.lat is not None and body.lon is not None else None
    )
    return reports_service.quick_confirm(
        db, vis, principal, code, body.dimension, body.still_present, reporter, datetime.now(UTC)
    )


@router.get("/segments/{code}/history")
def history(
    code: str,
    db: DB,
    vis: Vis,
    dimension: Dimension = "flood",
    hours: Annotated[int, Query(ge=1, le=24 * 30)] = 24 * 7,
):
    rows = service.segment_history(db, vis, code, dimension, datetime.now(UTC) - timedelta(hours=hours))
    if rows is None:
        raise AppError("SEGMENT_NOT_FOUND", f"Không tìm thấy đoạn {code}", status_code=404)
    return {"code": code, "dimension": dimension, "hours": hours, "entries": rows}


@router.get("/status/changes")
def status_changes(
    db: DB,
    vis: Vis,
    since: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
):
    """Delta trạng thái kể từ change_seq `since`. Client lưu `next_since` cho lần gọi sau.

    Lưu ý: change_seq cấp trong transaction nên có thể commit lệch thứ tự; client nên tải lại toàn bộ định kỳ
    (mobile hiện dùng ETag trên /segments) thay vì chỉ dựa vào delta.
    """
    changes = service.status_changes(db, vis, since, limit)
    next_since = changes[-1]["change_seq"] if changes else since
    return {"since": since, "next_since": next_since, "changes": changes, "has_more": len(changes) == limit}
