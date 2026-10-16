#!/usr/bin/env python3
"""Tải mạng lưới đường OSM quanh vùng thí điểm và báo cáo mức phủ kiệt/hẻm.

Dữ liệu OSM theo giấy phép ODbL 1.0, © OpenStreetMap contributors.

    uv run python scripts/fetch_osm.py                  # khung = bao ranh giới thí điểm + 200 m
    uv run python scripts/fetch_osm.py --bbox S W N E   # khung tuỳ chọn

Mỗi feature giữ danh sách ID node OSM (`osm_nodes`) để build_segments.py cắt đoạn
theo topology thật (node dùng chung giữa các way) thay vì đoán giao lộ bằng hình học.
"""

import argparse
from collections import Counter
from datetime import datetime

from common import OSM_LICENSE, RAW_DIR, load_boundary, now_iso, overpass, to_utm, to_wgs84, write_geojson

EXCLUDED_HIGHWAYS = "motorway|motorway_link|construction|proposed|platform|bus_stop|elevator|corridor"

# Tiền tố tên thường gặp của ngõ nhỏ ở Huế (so khớp trên chữ thường)
ALLEY_PREFIXES = ("kiệt", "kiet", "hẻm", "hem", "ngõ", "ngo", "ngách")


def default_bbox(margin_m: float = 200.0):
    boundary, _ = load_boundary()
    west, south, east, north = to_wgs84(to_utm(boundary).buffer(margin_m)).bounds
    return (south, west, north, east)


def build_query(bbox) -> str:
    south, west, north, east = bbox
    return f"""
[out:json][timeout:120];
way["highway"]["highway"!~"^({EXCLUDED_HIGHWAYS})$"]({south},{west},{north},{east});
out body geom;
"""


def to_geojson(osm: dict, bbox) -> dict:
    features = []
    for element in osm.get("elements", []):
        if element.get("type") != "way" or "geometry" not in element:
            continue
        coords = [[point["lon"], point["lat"]] for point in element["geometry"]]
        if len(coords) < 2 or len(coords) != len(element.get("nodes", [])):
            continue
        features.append(
            {
                "type": "Feature",
                "id": f"way/{element['id']}",
                "properties": {
                    "osm_id": element["id"],
                    "osm_nodes": element["nodes"],
                    **element.get("tags", {}),
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )
    return {
        "type": "FeatureCollection",
        "metadata": {
            **OSM_LICENSE,
            "fetched_at": now_iso(),
            "bbox_swne": [round(v, 6) for v in bbox],
            "osm_base": osm.get("osm3s", {}).get("timestamp_osm_base"),
        },
        "features": features,
    }


def is_alley(props: dict) -> bool:
    name = props.get("name", "").strip().lower()
    return name.startswith(ALLEY_PREFIXES) or props.get("service") == "alley"


def report(geojson: dict) -> str:
    features = geojson["features"]
    by_type = Counter(f["properties"].get("highway") for f in features)
    named = sum(1 for f in features if f["properties"].get("name"))
    alleys = [f for f in features if is_alley(f["properties"])]
    named_alleys = [f for f in alleys if f["properties"].get("name")]
    unnamed_small = [
        f
        for f in features
        if f["properties"].get("highway")
        in {"service", "footway", "path", "track", "living_street", "residential"}
        and not f["properties"].get("name")
    ]
    return "\n".join(
        [
            f"Khung tải (S,W,N,E): {geojson['metadata']['bbox_swne']}",
            f"Tổng số way highway: {len(features)} (có tên: {named})",
            "Theo loại highway:",
            *[f"  {kind:<16} {count}" for kind, count in by_type.most_common()],
            f"Kiệt/hẻm nhận diện được (tên Kiệt/Hẻm/Ngõ… hoặc service=alley): {len(alleys)}"
            f" (có tên: {len(named_alleys)})",
            f"Đường nhỏ KHÔNG tên (residential/service/footway/path/…): {len(unnamed_small)}",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--bbox", type=float, nargs=4, metavar=("S", "W", "N", "E"))
    args = parser.parse_args()

    bbox = tuple(args.bbox) if args.bbox else default_bbox()
    geojson = to_geojson(overpass(build_query(bbox)), bbox)

    out = RAW_DIR / f"osm_highways_{datetime.now():%Y%m%d}.geojson"
    write_geojson(out, geojson)
    summary = report(geojson)
    out.with_suffix(".report.txt").write_text(summary + "\n", encoding="utf-8")
    print(summary)
    print(f"\nĐã lưu: {out}")


if __name__ == "__main__":
    main()
