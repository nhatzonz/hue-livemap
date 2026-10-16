"""import_segments trên DB test (schema do backend tạo). Bỏ qua nếu không kết nối được DB."""

import json
import os

import psycopg
import pytest
from import_segments import import_segments

DB_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5433/hue_livemap_test").replace(
    "postgresql+psycopg://", "postgresql://"
)
LINE = {"type": "LineString", "coordinates": [[107.58, 16.47], [107.58, 16.471]]}


def feature(ref, geometry=LINE, name="Đường Test"):
    return {
        "geometry": geometry,
        "properties": {
            "source_ref": ref,
            "name": name,
            "pilot_tier": 1,
            "segment_type": "street",
            "highway": "tertiary",
            "from_name": None,
            "to_name": None,
            "part": None,
        },
    }


@pytest.fixture
def conn():
    try:
        connection = psycopg.connect(DB_URL)
    except psycopg.OperationalError:
        pytest.skip("Không kết nối được DB test")
    with connection.cursor() as cur:
        cur.execute("SELECT to_regclass('road_segment') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.skip("DB test chưa có schema (chạy test backend trước)")
    yield connection
    connection.rollback()
    connection.close()


def codes(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT code, source_ref, verification_status FROM road_segment WHERE source_id = 1 ORDER BY code"
        )
        return cur.fetchall()


def test_reimport_with_new_ref_keeps_code_by_geometry(conn):
    first = import_segments(conn, [feature("w1[1..2]")], "a.geojson", {}, {1})
    assert first["inserted"] == 1
    ((code, _, _),) = codes(conn)

    # cùng hình học, source_ref đổi (ví dụ OSM tách way) → khớp theo hình học, giữ mã
    second = import_segments(conn, [feature("w1[1..5]+w9[5..2]")], "b.geojson", {}, {1})
    assert (second["inserted"], second["matched_by_geometry"], second["retired"]) == (0, 1, 0)
    assert codes(conn) == [(code, "w1[1..5]+w9[5..2]", "draft")]


def test_moved_geometry_is_new_segment_and_old_is_retired(conn):
    import_segments(conn, [feature("w1[1..2]")], "a.geojson", {}, {1})
    far = {"type": "LineString", "coordinates": [[107.585, 16.47], [107.585, 16.471]]}  # cách ~530 m
    stats = import_segments(conn, [feature("w2[3..4]", far)], "b.geojson", {}, {1})
    assert (stats["inserted"], stats["retired"]) == (1, 1)
    assert [row[2] for row in codes(conn)] == ["retired", "draft"]


def test_attribute_change_is_counted_as_update(conn):
    import_segments(conn, [feature("w1[1..2]")], "a.geojson", {}, {1})
    stats = import_segments(conn, [feature("w1[1..2]", name="Đường Đổi Tên")], "b.geojson", {}, {1})
    assert (stats["updated"], stats["unchanged"]) == (1, 0)
    assert json.dumps(stats)  # stats ghi được vào dataset_import
