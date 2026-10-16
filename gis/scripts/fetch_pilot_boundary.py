#!/usr/bin/env python3
"""Tạo ranh giới vùng thí điểm (phương án A) từ relation OSM "Kinh thành Huế".

Ranh giới = đa giác Kinh thành + vùng đệm (mặc định 300 m) để gồm các tuyến bao quanh hào
và dải ven bờ Bắc sông Hương. Kết quả là BẢN NHÁP, chờ xác nhận quyết định D1 (PROJECT_PLAN.md).

    uv run python scripts/fetch_pilot_boundary.py [--buffer-m 300]
"""

import argparse

from common import CURATED_DIR, OSM_LICENSE, now_iso, overpass, to_utm, to_wgs84, write_geojson
from shapely import ops
from shapely.geometry import LineString, mapping

CITADEL_RELATION_ID = 21657722  # "Kinh thành Huế" trên OSM


def citadel_polygon():
    data = overpass(f"[out:json][timeout:60];relation({CITADEL_RELATION_ID});out geom;")
    relation = data["elements"][0]
    outer_lines = [
        LineString([(p["lon"], p["lat"]) for p in member["geometry"]])
        for member in relation["members"]
        if member["type"] == "way" and member.get("role", "outer") in ("outer", "") and "geometry" in member
    ]
    polygons = list(ops.polygonize(ops.unary_union(outer_lines)))
    if not polygons:
        raise SystemExit("Không ghép được đa giác Kinh thành từ các way outer")
    # Đa giác lớn nhất là vòng thành ngoài
    return max(polygons, key=lambda p: to_utm(p).area), relation.get("tags", {})


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--buffer-m", type=float, default=300.0)
    args = parser.parse_args()

    citadel, tags = citadel_polygon()
    citadel_utm = to_utm(citadel)
    pilot_utm = citadel_utm.buffer(args.buffer_m, join_style="mitre").simplify(5)
    pilot = to_wgs84(pilot_utm)

    collection = {
        "type": "FeatureCollection",
        "metadata": {
            **OSM_LICENSE,
            "generated_at": now_iso(),
            "method": f"OSM relation {CITADEL_RELATION_ID} ({tags.get('name')}) + buffer {args.buffer_m:.0f} m",
            "status": "draft — chờ xác nhận D1",
        },
        "features": [
            {
                "type": "Feature",
                "id": "hue-pilot-a",
                "properties": {
                    "region_id": "hue",
                    "name": "Thí điểm A: Kinh thành và bờ Bắc sông Hương",
                    "citadel_area_km2": round(citadel_utm.area / 1e6, 2),
                    "area_km2": round(pilot_utm.area / 1e6, 2),
                },
                "geometry": mapping(pilot),
            }
        ],
    }
    out = CURATED_DIR / "pilot_boundary.geojson"
    write_geojson(out, collection)
    print(
        f"Kinh thành: {citadel_utm.area / 1e6:.2f} km² · vùng thí điểm (buffer {args.buffer_m:.0f} m): "
        f"{pilot_utm.area / 1e6:.2f} km²"
    )
    print(f"Bao: {pilot.bounds}")
    print(f"Đã lưu: {out}")


if __name__ == "__main__":
    main()
