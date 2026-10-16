#!/usr/bin/env python3
"""Nhập đoạn đường ứng viên + ranh giới thí điểm vào PostgreSQL/PostGIS.

    uv run python scripts/import_segments.py [--tiers 1,3] [--dry-run]

- Khớp đoạn cũ theo (source_id=osm, source_ref) → GIỮ mã đoạn; hình học đổi thì tăng geom_version.
- Đoạn mới nhận mã HUE-KT-<số> tiếp theo.
- Đoạn nguồn OSM ở trạng thái draft/desk_reviewed không còn trong lần nhập → 'retired'.
  Đoạn field_verified KHÔNG bao giờ tự retire; chỉ báo để người rà soát quyết định.
- Mọi đoạn nhập ở đây là dữ liệu OSM thật (is_demo = false) nhưng CHƯA khảo sát: verification_status='draft'.

Cần chạy migration backend trước (cd backend && uv run alembic upgrade head).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import psycopg
from common import CURATED_DIR, load_boundary, read_geojson
from shapely.geometry import mapping

OSM_SOURCE_ID = 1
CODE_PREFIX = "HUE-KT-"
PILOT_AREA_ID = "hue-pilot-a"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql://localhost:5433/hue_livemap")
    return url.replace("postgresql+psycopg://", "postgresql://")


def display_name(props: dict) -> str:
    """'Đinh Tiên Hoàng (từ Mai Thúc Loan đến Lê Huân)', 'Lê Duẩn · phần 2/3'."""
    name = props["name"]
    start, end = props.get("from_name"), props.get("to_name")
    if start and end:
        name = f"{name} (từ {start} đến {end})"
    elif start:
        name = f"{name} (từ {start})"
    elif end:
        name = f"{name} (đến {end})"
    if props.get("part") and not (start and end):
        name = f"{name} · phần {props['part']}"
    return name


def next_code_number(cur) -> int:
    cur.execute("SELECT code FROM road_segment WHERE code LIKE %s", (CODE_PREFIX + "%",))
    numbers = [
        int(m.group(1)) for (code,) in cur.fetchall() if (m := re.match(rf"{CODE_PREFIX}(\d+)$", code))
    ]
    return max(numbers, default=0) + 1


def upsert_pilot_area(cur, boundary, meta: dict) -> None:
    cur.execute(
        """
        INSERT INTO pilot_area (id, name, geom, status, method, source_id, updated_at)
        VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 'draft', %s, %s, now())
        ON CONFLICT (id) DO UPDATE
          SET geom = EXCLUDED.geom, method = EXCLUDED.method, updated_at = now()
        """,
        (
            PILOT_AREA_ID,
            "Thí điểm A: Kinh thành và bờ Bắc sông Hương",
            json.dumps(mapping(boundary)),
            meta.get("method"),
            OSM_SOURCE_ID,
        ),
    )


def upsert_road(cur, name: str, road_class: str | None) -> int:
    cur.execute(
        """
        INSERT INTO road (region_id, name, road_class) VALUES ('hue', %s, %s)
        ON CONFLICT (region_id, name) DO UPDATE SET road_class = COALESCE(road.road_class, EXCLUDED.road_class)
        RETURNING id
        """,
        (name, road_class),
    )
    return cur.fetchone()[0]


GEOMETRY_MATCH_M = 2.0  # sai khác hình học tối đa để coi là "cùng một đoạn" khi source_ref đổi


def _find_by_ref(cur, ref: str, geom_json: str):
    cur.execute(
        """
        SELECT id, verification_status, road_id, display_name, segment_type, pilot_tier,
               ST_Equals(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)) AS same_geom
        FROM road_segment WHERE source_id = %s AND source_ref = %s
        """,
        (geom_json, OSM_SOURCE_ID, ref),
    )
    return cur.fetchone()


def _find_by_geometry(cur, geom_json: str, import_id: int):
    """Đoạn OSM chưa được khớp trong lần nhập này có hình học gần như trùng (≤ 2 m Hausdorff).

    Giữ mã đoạn ổn định khi source_ref đổi (OSM tách/gộp way, hoặc thuật toán ghép đổi thứ tự mẩu).
    """
    cur.execute(
        """
        WITH g AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) AS geom)
        SELECT s.id, s.verification_status, s.road_id, s.display_name, s.segment_type, s.pilot_tier,
               ST_Equals(s.geom, g.geom) AS same_geom
        FROM road_segment s, g
        WHERE s.source_id = %s AND s.dataset_import_id IS DISTINCT FROM %s
          AND s.geom && ST_Expand(g.geom, 0.0001)
          AND ST_HausdorffDistance(ST_Transform(s.geom, 32648), ST_Transform(g.geom, 32648)) <= %s
        ORDER BY ST_HausdorffDistance(ST_Transform(s.geom, 32648), ST_Transform(g.geom, 32648))
        LIMIT 1
        """,
        (geom_json, OSM_SOURCE_ID, import_id, GEOMETRY_MATCH_M),
    )
    return cur.fetchone()


def _update_existing(cur, existing, values: tuple, ref: str, geom_json: str, import_id: int, stats: dict):
    segment_id, status, road_id, name, seg_type, tier, same_geom = existing
    attrs_changed = (road_id, name, seg_type, tier) != values[:4] or status == "retired"
    cur.execute(
        """
        UPDATE road_segment
           SET road_id = %s, display_name = %s, segment_type = %s, pilot_tier = %s, source_ref = %s,
               dataset_import_id = %s,
               updated_at = CASE WHEN %s THEN now() ELSE updated_at END,
               verification_status = CASE WHEN verification_status = 'retired'
                                          THEN 'draft' ELSE verification_status END
         WHERE id = %s
        """,
        (*values[:4], ref, import_id, attrs_changed or not same_geom, segment_id),
    )
    if not same_geom:
        cur.execute(
            "UPDATE road_segment SET geom = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), "
            "geom_version = geom_version + 1 WHERE id = %s",
            (geom_json, segment_id),
        )
        stats["geometry_changed"] += 1
    stats["updated" if attrs_changed or not same_geom else "unchanged"] += 1


def import_segments(conn, features: list[dict], source_file: str, source_meta: dict, tiers: set[int]) -> dict:
    stats = {
        "inserted": 0,
        "updated": 0,
        "geometry_changed": 0,
        "unchanged": 0,
        "matched_by_geometry": 0,
        "retired": 0,
        "verified_missing": [],
        "tiers": sorted(tiers),
    }
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO dataset_import (kind, source_file, source_meta, stats, imported_by) "
            "VALUES ('segments', %s, %s, '{}', %s) RETURNING id",
            (source_file, json.dumps(source_meta, ensure_ascii=False), os.environ.get("USER")),
        )
        import_id = cur.fetchone()[0]
        code_no = next_code_number(cur)
        road_ids: dict[str, int] = {}

        selected = []
        for feature in features:
            props = feature["properties"]
            if props["pilot_tier"] not in tiers:
                continue
            if props["name"] not in road_ids:
                road_ids[props["name"]] = upsert_road(cur, props["name"], props.get("highway"))
            values = (
                road_ids[props["name"]],
                display_name(props),
                props["segment_type"],
                props["pilot_tier"],
            )
            selected.append((props["source_ref"], json.dumps(feature["geometry"]), values))

        # Lượt 1: khớp chính xác theo source_ref. Lượt 2 (sau, để không "giành" đoạn của lượt 1): theo hình học.
        unmatched = []
        for ref, geom_json, values in selected:
            existing = _find_by_ref(cur, ref, geom_json)
            if existing is None:
                unmatched.append((ref, geom_json, values))
            else:
                _update_existing(cur, existing, values, ref, geom_json, import_id, stats)

        for ref, geom_json, values in unmatched:
            existing = _find_by_geometry(cur, geom_json, import_id)
            if existing is not None:
                stats["matched_by_geometry"] += 1
                _update_existing(cur, existing, values, ref, geom_json, import_id, stats)
                continue
            cur.execute(
                """
                INSERT INTO road_segment (code, road_id, display_name, segment_type, pilot_tier,
                                          dataset_import_id, geom, source_id, source_ref)
                VALUES (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s, %s)
                """,
                (f"{CODE_PREFIX}{code_no:04d}", *values, import_id, geom_json, OSM_SOURCE_ID, ref),
            )
            code_no += 1
            stats["inserted"] += 1

        cur.execute(
            """
            UPDATE road_segment SET verification_status = 'retired', updated_at = now()
             WHERE source_id = %s AND dataset_import_id IS DISTINCT FROM %s
               AND verification_status IN ('draft', 'desk_reviewed')
            """,
            (OSM_SOURCE_ID, import_id),
        )
        stats["retired"] = cur.rowcount
        cur.execute(
            """
            SELECT code FROM road_segment
             WHERE source_id = %s AND dataset_import_id IS DISTINCT FROM %s
               AND verification_status = 'field_verified'
            """,
            (OSM_SOURCE_ID, import_id),
        )
        stats["verified_missing"] = [code for (code,) in cur.fetchall()]
        cur.execute("UPDATE dataset_import SET stats = %s WHERE id = %s", (json.dumps(stats), import_id))
        stats["dataset_import_id"] = import_id
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--file", type=Path, default=CURATED_DIR / "segments_candidates.geojson")
    parser.add_argument("--tiers", default="1,3", help="Tầng cần nhập: 1 trục chính, 2 dân sinh, 3 kiệt")
    parser.add_argument("--dry-run", action="store_true", help="Chạy rồi rollback, không ghi gì")
    args = parser.parse_args()

    collection = read_geojson(args.file)
    qa_report = args.file.with_suffix(".qa.txt")
    if not qa_report.exists() or " 0 lỗi " not in qa_report.read_text(encoding="utf-8").splitlines()[0]:
        sys.exit("QA chưa chạy hoặc còn lỗi. Chạy scripts/qa_checks.py trước.")

    tiers = {int(t) for t in args.tiers.split(",")}
    boundary, boundary_meta = load_boundary()

    with psycopg.connect(database_url()) as conn:
        upsert_pilot_area(conn.cursor(), boundary, boundary_meta)
        stats = import_segments(
            conn, collection["features"], args.file.name, collection.get("metadata", {}), tiers
        )
        if args.dry_run:
            conn.rollback()
            print("DRY RUN — đã rollback, không ghi gì.")
        else:
            conn.commit()

    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
