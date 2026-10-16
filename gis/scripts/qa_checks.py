#!/usr/bin/env python3
"""Kiểm tra chất lượng đoạn đường trước khi nhập DB.

    uv run python scripts/qa_checks.py [--file data/curated/segments_candidates.geojson]

LỖI (chặn nhập, exit 1): hình học không hợp lệ/tự cắt, trùng source_ref, chồng lấn với đoạn khác,
nằm ngoài ranh giới, dài hơn giới hạn.
CẢNH BÁO (cần rà soát trong QGIS/thực địa): đoạn ngắn, kiệt không nối với đoạn nào, bị cắt ở ranh giới.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from common import CURATED_DIR, load_boundary, read_geojson, to_utm
from shapely import STRtree
from shapely.geometry import Point, shape

OVERLAP_TOLERANCE_M = 10.0
ENDPOINT_SNAP_M = 1.0


def check(collection: dict, boundary, max_m: float, min_m: float) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    features = collection["features"]
    geoms_utm = [to_utm(shape(f["geometry"])) for f in features]
    labels = [f"{f['properties']['name']} [{f['properties']['source_ref']}]" for f in features]
    boundary_utm = to_utm(boundary).buffer(1.0)

    for ref, count in Counter(f["properties"]["source_ref"] for f in features).items():
        if count > 1:
            errors.append(f"source_ref trùng ({count} lần): {ref}")

    for i, (feature, geom) in enumerate(zip(features, geoms_utm, strict=True)):
        props = feature["properties"]
        if not geom.is_valid or geom.is_empty:
            errors.append(f"Hình học không hợp lệ: {labels[i]}")
            continue
        if not geom.is_simple:
            errors.append(f"Đoạn tự cắt: {labels[i]}")
        if geom.length > max_m * 1.01:
            errors.append(f"Dài {geom.length:.0f} m > {max_m:.0f} m: {labels[i]}")
        if not boundary_utm.contains(geom):
            errors.append(f"Nằm ngoài ranh giới thí điểm: {labels[i]}")
        if geom.length < min_m:
            warnings.append(f"Ngắn {geom.length:.0f} m: {labels[i]}")
        if "clipped_by_boundary" in props.get("qa_flags", []):
            warnings.append(f"Bị cắt ở ranh giới: {labels[i]}")

    tree = STRtree(geoms_utm)
    for i, geom in enumerate(geoms_utm):
        for j in tree.query(geom.buffer(0.5)):
            if j <= i:
                continue
            shared = geom.intersection(geoms_utm[j].buffer(0.5)).length
            if shared > OVERLAP_TOLERANCE_M:
                errors.append(f"Chồng lấn {shared:.0f} m: {labels[i]} ↔ {labels[j]}")

    for i, feature in enumerate(features):
        if feature["properties"]["pilot_tier"] != 3:
            continue
        geom = geoms_utm[i]
        ends = [Point(geom.coords[0]), Point(geom.coords[-1])]
        connected = any(
            j != i and geoms_utm[j].distance(end) <= ENDPOINT_SNAP_M
            for end in ends
            for j in tree.query(end.buffer(ENDPOINT_SNAP_M))
        )
        if not connected:
            warnings.append(f"Kiệt không nối với đoạn nào (có thể nối vào đường không tên): {labels[i]}")

    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--file", type=Path, default=CURATED_DIR / "segments_candidates.geojson")
    args = parser.parse_args()

    collection = read_geojson(args.file)
    rules = collection.get("metadata", {}).get("rules", {})
    boundary, _ = load_boundary()
    errors, warnings = check(collection, boundary, rules.get("max_m", 400.0), rules.get("min_m", 30.0))

    lines = [
        f"QA {args.file.name}: {len(collection['features'])} đoạn · {len(errors)} lỗi · {len(warnings)} cảnh báo",
        *[f"LỖI  {e}" for e in errors],
        *[f"CẢNH {w}" for w in warnings],
    ]
    report = args.file.with_suffix(".qa.txt")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:1] + [line for line in lines[1:] if line.startswith("LỖI")][:30]))
    print(f"Báo cáo đầy đủ: {report}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
