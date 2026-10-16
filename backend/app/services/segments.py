"""Truy vấn đoạn đường + trạng thái hiện tại.

Nguyên tắc (PROJECT_PLAN.md mục 6.2): đoạn không có bản ghi trạng thái luôn trả về state = NO_DATA,
không bao giờ null hay "bình thường".
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.status import DIMENSIONS

NO_DATA = "NO_DATA"


@dataclass(frozen=True)
class Visibility:
    include_demo: bool
    include_unverified: bool

    @classmethod
    def from_settings(cls, settings: Settings) -> "Visibility":
        return cls(settings.include_demo_data, settings.show_unverified_segments)

    def where(self, alias: str = "s") -> str:
        clauses = [f"{alias}.verification_status <> 'retired'"]
        if not self.include_demo:
            clauses.append(f"NOT {alias}.is_demo")
        if not self.include_unverified:
            clauses.append(f"{alias}.verification_status = 'field_verified'")
        return " AND ".join(clauses)


def _status(row) -> dict:
    if row is None or row.state is None:
        return {
            "state": NO_DATA,
            "level": None,
            "confidence": None,
            "evidence_count": 0,
            "last_evidence_at": None,
        }
    return {
        "state": row.state,
        "level": row.level,
        "confidence": row.confidence,
        "evidence_count": row.evidence_count,
        "last_evidence_at": row.last_evidence_at.isoformat() if row.last_evidence_at else None,
    }


def segments_geojson(db: Session, vis: Visibility, dimension: str, bbox: tuple | None) -> dict:
    bbox_clause = "AND s.geom && ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326)" if bbox else ""
    params = {"dimension": dimension}
    if bbox:
        params.update(dict(zip(("minx", "miny", "maxx", "maxy"), bbox, strict=True)))

    rows = db.execute(
        text(f"""
            SELECT s.code, s.display_name, s.segment_type, s.pilot_tier, s.verification_status, s.is_demo,
                   round(s.length_m)::int AS length_m,
                   ST_AsGeoJSON(s.geom, 6)::json AS geometry,
                   st.state, st.level, st.confidence, st.evidence_count, st.last_evidence_at
            FROM road_segment s
            LEFT JOIN segment_status_current st ON st.segment_id = s.id AND st.dimension = :dimension
            WHERE {vis.where()} {bbox_clause}
            ORDER BY s.pilot_tier, s.code
        """),
        params,
    ).all()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": row.code,
                "geometry": row.geometry,
                "properties": {
                    "code": row.code,
                    "name": row.display_name,
                    "segment_type": row.segment_type,
                    "pilot_tier": row.pilot_tier,
                    "verification_status": row.verification_status,
                    "is_demo": row.is_demo,
                    "length_m": row.length_m,
                    "status": _status(row),
                },
            }
            for row in rows
        ],
    }


def map_version(db: Session, vis: Visibility, dimension: str, bbox: tuple | None) -> str:
    """Chuỗi đổi mỗi khi dữ liệu bản đồ có thể đổi, dùng làm ETag."""
    row = db.execute(
        text("""
            SELECT coalesce((SELECT max(change_seq) FROM segment_status_current), 0) AS seq,
                   coalesce((SELECT max(id) FROM dataset_import), 0) AS imp,
                   coalesce((SELECT extract(epoch FROM max(updated_at))::bigint FROM road_segment), 0) AS upd
        """)
    ).one()
    return f"{row.seq}-{row.imp}-{row.upd}-{dimension}-{int(vis.include_demo)}{int(vis.include_unverified)}-{bbox}"


def segment_detail(db: Session, vis: Visibility, code: str) -> dict | None:
    seg = db.execute(
        text(f"""
            SELECT s.id, s.code, s.display_name, s.segment_type, s.pilot_tier, s.verification_status,
                   s.verified_at, s.is_demo, round(s.length_m)::int AS length_m, s.width_class,
                   s.vehicle_access, s.flood_prone, s.geom_version, s.updated_at,
                   r.name AS road_name, ds.name AS source_name, ds.license AS source_license,
                   ds.attribution AS source_attribution, di.id AS dataset_version, di.imported_at,
                   ST_AsGeoJSON(s.geom, 6)::json AS geometry,
                   ST_AsGeoJSON(ST_LineInterpolatePoint(s.geom, 0.5), 6)::json AS midpoint
            FROM road_segment s
            LEFT JOIN road r ON r.id = s.road_id
            LEFT JOIN data_source ds ON ds.id = s.source_id
            LEFT JOIN dataset_import di ON di.id = s.dataset_import_id
            WHERE s.code = :code AND {vis.where()}
        """),
        {"code": code},
    ).one_or_none()
    if seg is None:
        return None

    status_rows = {
        row.dimension: row
        for row in db.execute(
            text("""
                SELECT dimension, state, level, confidence, evidence_count, last_evidence_at
                FROM segment_status_current WHERE segment_id = :id
            """),
            {"id": seg.id},
        ).all()
    }
    return {
        "code": seg.code,
        "name": seg.display_name,
        "road_name": seg.road_name,
        "segment_type": seg.segment_type,
        "pilot_tier": seg.pilot_tier,
        "length_m": seg.length_m,
        "width_class": seg.width_class,
        "vehicle_access": seg.vehicle_access,
        "flood_prone": seg.flood_prone,
        "verification_status": seg.verification_status,
        "verified_at": seg.verified_at.isoformat() if seg.verified_at else None,
        "is_demo": seg.is_demo,
        "geom_version": seg.geom_version,
        "source": {
            "name": seg.source_name,
            "license": seg.source_license,
            "attribution": seg.source_attribution,
            "dataset_version": seg.dataset_version,
            "imported_at": seg.imported_at.isoformat() if seg.imported_at else None,
        },
        "status": {dim: _status(status_rows.get(dim)) for dim in DIMENSIONS},
        "recent_evidence": recent_evidence(db, seg.id),
        "geometry": seg.geometry,
        "midpoint": seg.midpoint,
    }


def search_segments(db: Session, vis: Visibility, query: str, limit: int) -> list[dict]:
    """Tìm theo tên đoạn hoặc mã, chấp nhận không dấu. Xếp hạng theo độ tương đồng trigram."""
    rows = db.execute(
        text(f"""
            WITH q AS (SELECT lower(immutable_unaccent(:q)) AS term)
            SELECT s.code, s.display_name, s.segment_type,
                   ST_AsGeoJSON(ST_LineInterpolatePoint(s.geom, 0.5), 6)::json AS midpoint,
                   ARRAY[ST_XMin(s.geom), ST_YMin(s.geom), ST_XMax(s.geom), ST_YMax(s.geom)] AS bbox,
                   similarity(lower(immutable_unaccent(s.display_name)), q.term) AS score
            FROM road_segment s, q
            WHERE {vis.where()}
              AND (lower(immutable_unaccent(s.display_name)) LIKE '%' || q.term || '%'
                   OR lower(immutable_unaccent(s.display_name)) % q.term
                   OR lower(s.code) = lower(:q))
            ORDER BY (lower(immutable_unaccent(s.display_name)) LIKE q.term || '%') DESC, score DESC, s.code
            LIMIT :limit
        """),
        {"q": query, "limit": limit},
    ).all()
    return [
        {
            "code": row.code,
            "name": row.display_name,
            "segment_type": row.segment_type,
            "midpoint": row.midpoint,
            "bbox": [round(v, 6) for v in row.bbox],
        }
        for row in rows
    ]


def pilot_region(db: Session, region_id: str) -> dict | None:
    areas = db.execute(
        text("""
            SELECT id, name, status, method,
                   round((ST_Area(geom::geography) / 1e6)::numeric, 2)::float AS area_km2,
                   ST_AsGeoJSON(geom, 6)::json AS geometry,
                   ARRAY[ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)] AS bbox
            FROM pilot_area WHERE region_id = :region AND status <> 'retired'
            ORDER BY id
        """),
        {"region": region_id},
    ).all()
    if not areas:
        return None
    dataset = db.execute(
        text("""
            SELECT id, imported_at FROM dataset_import
            WHERE kind = 'segments' AND region_id = :region ORDER BY id DESC LIMIT 1
        """),
        {"region": region_id},
    ).one_or_none()
    return {
        "region_id": region_id,
        "pilot_areas": [
            {
                "id": a.id,
                "name": a.name,
                "status": a.status,
                "method": a.method,
                "area_km2": a.area_km2,
                "bbox": [round(v, 6) for v in a.bbox],
                "geometry": a.geometry,
            }
            for a in areas
        ],
        "dataset": {"version": dataset.id, "imported_at": dataset.imported_at.isoformat()}
        if dataset
        else None,
        "attribution": "Dữ liệu đường © OpenStreetMap contributors (ODbL)",
    }


def _visible_segment_id(db: Session, vis: Visibility, code: str) -> int | None:
    return db.execute(
        text(f"SELECT s.id FROM road_segment s WHERE s.code = :code AND {vis.where()}"), {"code": code}
    ).scalar_one_or_none()


def segment_history(db: Session, vis: Visibility, code: str, dimension: str, since) -> list[dict] | None:
    segment_id = _visible_segment_id(db, vis, code)
    if segment_id is None:
        return None
    rows = db.execute(
        text("""
            SELECT state, level, confidence, valid_from, valid_to, cause
            FROM segment_status_history
            WHERE segment_id = :sid AND dimension = :dim AND (valid_to IS NULL OR valid_to >= :since)
            ORDER BY valid_from DESC
        """),
        {"sid": segment_id, "dim": dimension, "since": since},
    ).all()
    return [
        {
            "state": r.state,
            "level": r.level,
            "confidence": r.confidence,
            "valid_from": r.valid_from.isoformat(),
            "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            "cause": r.cause,
        }
        for r in rows
    ]


def recent_evidence(db: Session, segment_id: int, limit: int = 10) -> list[dict]:
    """Bằng chứng gần đây, ẩn danh: không trả thiết bị/người gửi hay vị trí người gửi."""
    rows = db.execute(
        text("""
            SELECT dimension, level, source_type, has_photo, observed_at
            FROM observation
            WHERE segment_id = :sid AND invalidated_at IS NULL AND observed_at > now() - interval '72 hours'
            ORDER BY observed_at DESC LIMIT :limit
        """),
        {"sid": segment_id, "limit": limit},
    ).all()
    return [
        {
            "dimension": r.dimension,
            "level": r.level,
            "source_type": r.source_type,
            "has_photo": r.has_photo,
            "observed_at": r.observed_at.isoformat(),
        }
        for r in rows
    ]


def status_changes(db: Session, vis: Visibility, since: int, limit: int) -> list[dict]:
    rows = db.execute(
        text(f"""
            SELECT st.change_seq, s.code, st.dimension, st.state, st.level, st.confidence, st.evidence_count,
                   st.last_evidence_at
            FROM segment_status_current st JOIN road_segment s ON s.id = st.segment_id
            WHERE st.change_seq > :since AND {vis.where()}
            ORDER BY st.change_seq LIMIT :limit
        """),
        {"since": since, "limit": limit},
    ).all()
    return [
        {"change_seq": r.change_seq, "code": r.code, "dimension": r.dimension, "status": _status(r)}
        for r in rows
    ]
