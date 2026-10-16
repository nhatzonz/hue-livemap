"""Nhận phản ánh hiện trường → gắn đoạn → gộp sự vụ → bằng chứng → tính lại trạng thái (PROJECT_PLAN.md 10.4)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import Principal
from app.models import CATEGORIES
from app.services import status_engine
from app.services.segments import Visibility

SNAP_RADIUS_M = 30
MAX_CHOSEN_SEGMENT_DISTANCE_M = 60
INCIDENT_WINDOW = timedelta(minutes=60)
MAX_REPORT_AGE = timedelta(hours=24)
MAX_CLOCK_SKEW = timedelta(minutes=5)
RATE_WINDOW = timedelta(hours=1)
QUICK_CONFIRM_COOLDOWN = timedelta(minutes=30)
# Độ (kinh/vĩ) đủ phủ 1 m ở vĩ độ Huế (1° kinh độ ≈ 106,7 km) — dùng lọc bbox để tận dụng index GIST
DEG_PER_M = 1 / 100_000


@dataclass(frozen=True)
class Point:
    lat: float
    lon: float


def _point_params(point: Point | None, prefix: str) -> dict:
    return {f"{prefix}lon": point.lon if point else None, f"{prefix}lat": point.lat if point else None}


def in_pilot_area(db: Session, point: Point) -> bool:
    return db.execute(
        text("""
            SELECT EXISTS (
              SELECT 1 FROM pilot_area
              WHERE status <> 'retired' AND ST_Covers(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            )
        """),
        {"lon": point.lon, "lat": point.lat},
    ).scalar_one()


# `s.geom && ST_Expand(...)` dùng index GIST trên geometry; ST_DWithin(geography) sau đó lọc chính xác theo mét.
# reporter_distance_m: khoảng cách từ vị trí người gửi tới đoạn (NULL nếu không có vị trí người gửi).
_CANDIDATE_COLUMNS = """
    s.id, s.code, s.display_name, s.segment_type,
    ST_Distance(s.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS distance_m,
    ST_Distance(s.geom::geography,
                ST_SetSRID(ST_MakePoint(CAST(:rlon AS float8), CAST(:rlat AS float8)), 4326)::geography)
      AS reporter_distance_m
"""


def snap_candidates(
    db: Session,
    vis: Visibility,
    point: Point,
    radius_m: float = SNAP_RADIUS_M,
    limit: int = 3,
    reporter: Point | None = None,
):
    rows = db.execute(
        text(f"""
            SELECT {_CANDIDATE_COLUMNS}
            FROM road_segment s
            WHERE {vis.where()}
              AND s.geom && ST_Expand(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :deg)
              AND ST_DWithin(s.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius)
            ORDER BY distance_m LIMIT :limit
        """),
        {
            "lon": point.lon,
            "lat": point.lat,
            "radius": radius_m,
            "deg": radius_m * DEG_PER_M,
            "limit": limit,
            **_point_params(reporter, "r"),
        },
    ).all()
    return [
        {
            "id": r.id,
            "code": r.code,
            "name": r.display_name,
            "segment_type": r.segment_type,
            "distance_m": round(r.distance_m, 1),
            "reporter_distance_m": r.reporter_distance_m,
        }
        for r in rows
    ]


def _segment_by_code(db: Session, vis: Visibility, code: str, point: Point, reporter: Point | None):
    return db.execute(
        text(f"SELECT {_CANDIDATE_COLUMNS} FROM road_segment s WHERE s.code = :code AND {vis.where()}"),
        {"code": code, "lon": point.lon, "lat": point.lat, **_point_params(reporter, "r")},
    ).one_or_none()


def _attach_incident(
    db: Session, segment_id: int | None, dimension: str, point: Point, observed_at: datetime, severity: float
) -> int:
    """Gộp vào sự vụ đang mở cùng (đoạn, chiều) trong 60 phút; nếu không có thì tạo mới.

    priority = số phản ánh + mức nghiêm trọng cao nhất (0..1) → hàng đợi moderator ưu tiên sự vụ đông người
    báo và nặng.
    """
    incident_id = None
    if segment_id is not None:
        incident_id = db.execute(
            text("""
                SELECT id FROM incident
                WHERE segment_id = :sid AND dimension = :dim AND status IN ('open', 'verified')
                  AND last_seen_at >= :since
                ORDER BY last_seen_at DESC LIMIT 1 FOR UPDATE
            """),
            {"sid": segment_id, "dim": dimension, "since": observed_at - INCIDENT_WINDOW},
        ).scalar_one_or_none()

    if incident_id is None:
        return db.execute(
            text("""
                INSERT INTO incident (segment_id, dimension, status, priority, report_count,
                                      first_seen_at, last_seen_at, location)
                VALUES (:sid, :dim, 'open', :priority, 1, :at, :at, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                RETURNING id
            """),
            {
                "sid": segment_id,
                "dim": dimension,
                "priority": 1 + severity,
                "at": observed_at,
                "lon": point.lon,
                "lat": point.lat,
            },
        ).scalar_one()

    db.execute(
        text("""
            UPDATE incident SET report_count = report_count + 1,
                   last_seen_at = greatest(last_seen_at, :at),
                   -- (priority - report_count) là mức nghiêm trọng cao nhất hiện có
                   priority = report_count + 1 + greatest(priority - report_count, :severity)
            WHERE id = :id
        """),
        {"id": incident_id, "at": observed_at, "severity": severity},
    )
    return incident_id


def _existing_report(db: Session, report_id: uuid.UUID):
    return db.execute(
        text("""
            SELECT r.id, r.device_id, r.status, r.incident_id, s.code AS segment_code, s.display_name AS segment_name
            FROM report r LEFT JOIN road_segment s ON s.id = r.segment_id WHERE r.id = :id
        """),
        {"id": report_id},
    ).one_or_none()


def _summary(report_id, status: str, incident_id: int, segment_code: str | None, segment_name: str | None):
    return {
        "id": str(report_id),
        "status": status,
        "incident_id": incident_id,
        "segment": {"code": segment_code, "name": segment_name} if segment_code else None,
        "upload_url": f"/api/v1/reports/{report_id}/media",
    }


def _reliability(db: Session, principal: Principal) -> float:
    if principal.user_id:
        query, params = "SELECT reputation FROM app_user WHERE id = :id", {"id": principal.user_id}
    else:
        query, params = "SELECT reputation FROM device WHERE id = :id", {"id": principal.device_id}
    return float(db.execute(text(query), params).scalar_one())


def _validate(data, levels: list[str], now: datetime) -> None:
    if data.level not in levels:
        raise AppError(
            "INVALID_LEVEL",
            f"Mức '{data.level}' không hợp lệ cho {data.dimension}",
            status_code=422,
            details={"allowed": levels},
        )
    if data.category not in CATEGORIES[data.dimension]:
        raise AppError(
            "INVALID_CATEGORY",
            f"Loại '{data.category}' không hợp lệ cho {data.dimension}",
            status_code=422,
            details={"allowed": list(CATEGORIES[data.dimension])},
        )
    if data.client_created_at > now + MAX_CLOCK_SKEW:
        raise AppError("INVALID_TIME", "Thời điểm phản ánh nằm ở tương lai", status_code=422)
    if data.client_created_at < now - MAX_REPORT_AGE:
        raise AppError(
            "REPORT_TOO_OLD",
            "Phản ánh đã quá 24 giờ, không còn phản ánh tình trạng hiện tại",
            status_code=422,
        )


def _resolve_segment(db: Session, vis: Visibility, data, location: Point, reporter: Point | None):
    """Đoạn người dùng chọn (khi ở giao lộ), nếu không thì đoạn gần nhất trong 30 m; None = phản ánh điểm."""
    if data.segment_code:
        segment = _segment_by_code(db, vis, data.segment_code, location, reporter)
        if segment is None:
            raise AppError("SEGMENT_NOT_FOUND", f"Không tìm thấy đoạn {data.segment_code}", status_code=422)
        if segment.distance_m > MAX_CHOSEN_SEGMENT_DISTANCE_M:
            raise AppError("SEGMENT_TOO_FAR", "Đoạn đã chọn cách vị trí phản ánh quá xa", status_code=422)
        return {
            "id": segment.id,
            "code": segment.code,
            "name": segment.display_name,
            "distance_m": segment.distance_m,
            "reporter_distance_m": segment.reporter_distance_m,
        }
    candidates = snap_candidates(db, vis, location, limit=1, reporter=reporter)
    return candidates[0] if candidates else None


def _check_rate_limits(db: Session, settings: Settings, principal: Principal, segment_id, dimension, now):
    counts = db.execute(
        text("""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE segment_id = :s AND dimension = :dim) AS same_segment
            FROM report WHERE device_id = :d AND received_at > :since
        """),
        {"d": principal.device_id, "s": segment_id, "dim": dimension, "since": now - RATE_WINDOW},
    ).one()
    if counts.total >= settings.max_reports_per_device_hour:
        raise AppError(
            "RATE_LIMITED", "Bạn đã gửi nhiều phản ánh trong 1 giờ qua, vui lòng thử lại sau", status_code=429
        )
    if segment_id is not None and counts.same_segment >= settings.max_reports_per_segment_device_hour:
        raise AppError("RATE_LIMITED", "Bạn đã phản ánh đoạn này nhiều lần trong 1 giờ qua", status_code=429)


def create_report(
    db: Session, settings: Settings, vis: Visibility, principal: Principal, data, now: datetime
) -> tuple[dict, bool]:
    """Trả về (summary, created). Gửi lại cùng id từ cùng thiết bị → trả bản cũ (idempotent)."""
    found = _existing_report(db, data.id)
    if found is not None:
        if str(found.device_id) != principal.device_id:
            raise AppError("REPORT_ID_CONFLICT", "Mã phản ánh đã được dùng", status_code=409)
        return _summary(
            found.id, found.status, found.incident_id, found.segment_code, found.segment_name
        ), False

    rule = status_engine.active_rule(db)
    levels = rule.params["dimensions"][data.dimension]["levels"]
    _validate(data, levels, now)

    location = Point(data.location.lat, data.location.lon)
    reporter = (
        Point(data.reporter_location.lat, data.reporter_location.lon) if data.reporter_location else None
    )
    if not in_pilot_area(db, location):
        raise AppError("OUTSIDE_PILOT_AREA", "Vị trí nằm ngoài vùng thí điểm", status_code=422)

    segment = _resolve_segment(db, vis, data, location, reporter)
    segment_id = segment["id"] if segment else None
    _check_rate_limits(db, settings, principal, segment_id, data.dimension, now)

    proximity = segment["reporter_distance_m"] if segment else None
    severity = levels.index(data.level) / max(1, len(levels) - 1)
    incident_id = _attach_incident(db, segment_id, data.dimension, location, data.client_created_at, severity)

    db.execute(
        text("""
            INSERT INTO report (id, device_id, user_id, segment_id, incident_id, dimension, category, level,
                                description, location, reporter_location, gps_accuracy_m, snap_distance_m,
                                proximity_m, client_created_at, received_at)
            VALUES (:id, :device, :user, :sid, :incident, :dim, :category, :level, :description,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    ST_SetSRID(ST_MakePoint(CAST(:rlon AS float8), CAST(:rlat AS float8)), 4326),
                    :accuracy, :snap, :proximity, :created, :now)
        """),
        {
            "id": data.id,
            "device": principal.device_id,
            "user": principal.user_id,
            "sid": segment_id,
            "incident": incident_id,
            "dim": data.dimension,
            "category": data.category,
            "level": data.level,
            "description": data.description,
            "lon": location.lon,
            "lat": location.lat,
            **_point_params(reporter, "r"),
            "accuracy": data.gps_accuracy_m,
            "snap": segment["distance_m"] if segment else None,
            "proximity": proximity,
            "created": data.client_created_at,
            "now": now,
        },
    )

    if segment_id is not None:
        db.execute(
            text("""
                INSERT INTO observation (segment_id, dimension, level, source_type, source_ref, actor_key,
                                         reliability, has_photo, proximity_m, observed_at)
                VALUES (:sid, :dim, :level, 'citizen_report', :ref, :actor, :rel, false, :prox, :at)
            """),
            {
                "sid": segment_id,
                "dim": data.dimension,
                "level": data.level,
                "ref": str(data.id),
                "actor": principal.actor_key,
                "rel": _reliability(db, principal),
                "prox": proximity,
                "at": data.client_created_at,
            },
        )
        status_engine.recompute(db, segment_id, data.dimension, now, rule=rule)

    db.commit()
    return _summary(
        data.id,
        "pending",
        incident_id,
        segment["code"] if segment else None,
        segment["name"] if segment else None,
    ), True


def quick_confirm(
    db: Session,
    vis: Visibility,
    principal: Principal,
    code: str,
    dimension: str,
    still_present: bool,
    reporter: Point | None,
    now: datetime,
) -> dict:
    """'Vẫn còn' / 'Đã hết' trên đoạn đang có trạng thái (PROJECT_PLAN.md M5)."""
    current = db.execute(
        text(f"""
            SELECT s.id AS segment_id, st.state, st.level,
                   ST_Distance(s.geom::geography,
                               ST_SetSRID(ST_MakePoint(CAST(:rlon AS float8), CAST(:rlat AS float8)), 4326)::geography)
                     AS reporter_distance_m,
                   EXISTS (
                     SELECT 1 FROM observation o
                     WHERE o.segment_id = s.id AND o.dimension = :dim AND o.actor_key = :actor
                       AND o.observed_at > :since AND o.invalidated_at IS NULL
                   ) AS recently_voted
            FROM road_segment s
            LEFT JOIN segment_status_current st ON st.segment_id = s.id AND st.dimension = :dim
            WHERE s.code = :code AND {vis.where()}
        """),
        {
            "code": code,
            "dim": dimension,
            "actor": principal.actor_key,
            "since": now - QUICK_CONFIRM_COOLDOWN,
            **_point_params(reporter, "r"),
        },
    ).one_or_none()
    if current is None:
        raise AppError("SEGMENT_NOT_FOUND", f"Không tìm thấy đoạn {code}", status_code=404)
    if current.state is None or current.state == "NO_DATA":
        raise AppError(
            "NOTHING_TO_CONFIRM",
            "Đoạn này chưa có trạng thái để xác nhận; hãy gửi phản ánh mới",
            status_code=409,
        )
    if current.recently_voted:
        raise AppError(
            "RATE_LIMITED", "Bạn vừa cập nhật đoạn này, vui lòng thử lại sau 30 phút", status_code=429
        )

    rule = status_engine.active_rule(db)
    level = current.level if still_present else rule.params["dimensions"][dimension]["levels"][0]
    db.execute(
        text("""
            INSERT INTO observation (segment_id, dimension, level, source_type, source_ref, actor_key,
                                     reliability, proximity_m, observed_at)
            VALUES (:s, :d, :level, 'quick_confirm', :ref, :actor, :rel, :prox, :now)
        """),
        {
            "s": current.segment_id,
            "d": dimension,
            "level": level,
            "ref": f"confirm:{uuid.uuid4()}",
            "actor": principal.actor_key,
            "rel": _reliability(db, principal),
            "prox": current.reporter_distance_m,
            "now": now,
        },
    )
    status_engine.recompute(db, current.segment_id, dimension, now, rule=rule)
    db.commit()
    return {"segment": code, "dimension": dimension, "level": level}
