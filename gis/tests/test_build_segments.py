"""Kiểm thử quy tắc cắt đoạn trên mạng lưới tổng hợp (không phải dữ liệu thật)."""

from build_segments import build, classify
from shapely.geometry import box

LAT0, LON0 = 16.47, 107.57
STEP = 0.001  # ≈ 110 m theo vĩ độ ở Huế
BIG_BOUNDARY = box(LON0 - 0.05, LAT0 - 0.05, LON0 + 0.05, LAT0 + 0.05)


def node_xy(i: int, j: int) -> tuple[float, float]:
    """Toạ độ lưới: i = cột (kinh độ), j = hàng (vĩ độ)."""
    return (LON0 + i * STEP, LAT0 + j * STEP)


def way(way_id, nodes, grid, **tags):
    return {
        "properties": {"osm_id": way_id, "osm_nodes": nodes, **tags},
        "geometry": {"type": "LineString", "coordinates": [node_xy(*grid[n]) for n in nodes]},
    }


def raw(*ways):
    return {"type": "FeatureCollection", "features": list(ways)}


# Ngã tư: nút 2 ở giữa, 1–3 theo hàng ngang, 4–5 theo cột dọc
CROSS = {1: (-1, 0), 2: (0, 0), 3: (1, 0), 4: (0, -1), 5: (0, 1)}


def names(features):
    return sorted(f["properties"]["name"] for f in features)


def test_classify():
    assert classify({"highway": "secondary", "name": "Lê Duẩn"}) == 1
    assert classify({"highway": "residential", "name": "Ngô Đức Kế"}) == 2
    assert classify({"highway": "residential", "name": "Kiệt 12 Đinh Tiên Hoàng"}) == 3
    assert classify({"highway": "service", "service": "alley", "name": "Kiệt 5"}) == 3
    assert classify({"highway": "residential"}) is None  # không tên
    assert classify({"highway": "residential", "name": "X", "access": "private"}) is None
    assert classify({"highway": "footway", "name": "Lối đi bộ"}) is None


def test_two_arterials_split_at_crossing():
    features = build(
        raw(
            way(1, [1, 2, 3], CROSS, highway="secondary", name="A"),
            way(2, [4, 2, 5], CROSS, highway="tertiary", name="B"),
        ),
        BIG_BOUNDARY,
    )
    assert names(features) == ["A", "A", "B", "B"]
    first_a = next(f for f in features if f["properties"]["name"] == "A")
    assert "B" in (first_a["properties"]["from_name"], first_a["properties"]["to_name"])


def test_local_street_does_not_split_arterial():
    features = build(
        raw(
            way(1, [1, 2, 3], CROSS, highway="secondary", name="A"),
            way(2, [4, 2, 5], CROSS, highway="residential", name="R"),
        ),
        BIG_BOUNDARY,
    )
    assert names(features) == ["A", "R", "R"]


def test_kiet_does_not_split_street_but_ends_at_it():
    grid = {1: (-1, 0), 2: (0, 0), 3: (1, 0), 4: (0, 1)}
    features = build(
        raw(
            way(1, [1, 2, 3], grid, highway="residential", name="R"),
            way(2, [2, 4], grid, highway="service", service="alley", name="Kiệt 3 R"),
        ),
        BIG_BOUNDARY,
    )
    assert names(features) == ["Kiệt 3 R", "R"]
    kiet = next(f for f in features if f["properties"]["pilot_tier"] == 3)
    assert kiet["properties"]["segment_type"] == "kiet"


def test_osm_way_split_is_merged_back():
    grid = {1: (0, 0), 2: (1, 0), 3: (2, 0)}
    features = build(
        raw(
            way(10, [1, 2], grid, highway="tertiary", name="A"),
            way(11, [3, 2], grid, highway="tertiary", name="A"),  # ngược chiều
        ),
        BIG_BOUNDARY,
    )
    assert len(features) == 1
    props = features[0]["properties"]
    assert set(props["osm_way_ids"]) == {10, 11}
    assert 205 < props["length_m"] < 220  # 2 bước kinh độ ≈ 2 × 106.7 m ở vĩ độ 16.47°


def test_merge_blocked_at_real_junction():
    grid = {1: (0, 0), 2: (1, 0), 3: (2, 0), 4: (1, 1)}
    features = build(
        raw(
            way(10, [1, 2], grid, highway="tertiary", name="A"),
            way(11, [2, 3], grid, highway="tertiary", name="A"),
            way(12, [2, 4], grid, highway="tertiary", name="B"),
        ),
        BIG_BOUNDARY,
    )
    assert names(features) == ["A", "A", "B"]


def test_long_segment_is_split_evenly():
    grid = {1: (0, 0), 2: (0, 10)}  # ≈ 1.1 km
    features = build(raw(way(1, [1, 2], grid, highway="secondary", name="Dài")), BIG_BOUNDARY, max_m=400)
    assert len(features) == 3
    lengths = [f["properties"]["length_m"] for f in features]
    assert all(length <= 400 for length in lengths)
    assert max(lengths) - min(lengths) < 1
    refs = [f["properties"]["source_ref"] for f in features]
    assert len(set(refs)) == 3 and all("#" in r for r in refs)


def test_median_connector_is_dropped():
    # Đường đôi D (hai way song song cách ~22 m) nối nhau bằng mẩu ngắn tên "C"
    grid = {1: (0, 0), 2: (2, 0), 3: (0, 0.2), 4: (2, 0.2), 5: (1, 0), 6: (1, 0.2)}
    features = build(
        raw(
            way(1, [1, 5, 2], grid, highway="primary", name="D", oneway="yes"),
            way(2, [4, 6, 3], grid, highway="primary", name="D", oneway="yes"),
            way(3, [5, 6], grid, highway="tertiary", name="C"),
        ),
        BIG_BOUNDARY,
    )
    assert "C" not in names(features)


def test_clipped_by_boundary():
    grid = {1: (-5, 0), 2: (5, 0)}
    boundary = box(LON0, LAT0 - 0.01, LON0 + 0.01, LAT0 + 0.01)  # chỉ nửa phía đông
    features = build(raw(way(1, [1, 2], grid, highway="secondary", name="A")), boundary, max_m=1000)
    assert len(features) == 1
    props = features[0]["properties"]
    assert "clipped_by_boundary" in props["qa_flags"]
    assert 520 < props["length_m"] < 545


def test_segmentation_is_deterministic():
    data = raw(
        way(1, [1, 2, 3], CROSS, highway="secondary", name="A"),
        way(2, [4, 2, 5], CROSS, highway="tertiary", name="B"),
    )
    first = [f["properties"]["source_ref"] for f in build(data, BIG_BOUNDARY)]
    second = [f["properties"]["source_ref"] for f in build(data, BIG_BOUNDARY)]
    assert first == second


def test_merge_result_does_not_depend_on_input_order():
    import random

    grid = {i: (i, 0) for i in range(6)}
    ways = [way(10 + i, [i, i + 1], grid, highway="tertiary", name="A") for i in range(5)]
    expected = [f["properties"]["source_ref"] for f in build(raw(*ways), BIG_BOUNDARY, max_m=2000)]
    for seed in range(5):
        shuffled = ways[:]
        random.Random(seed).shuffle(shuffled)
        assert [
            f["properties"]["source_ref"] for f in build(raw(*shuffled), BIG_BOUNDARY, max_m=2000)
        ] == expected
    assert len(expected) == 1


def test_closed_ring_is_merged_into_one_segment():
    grid = {1: (0, 0), 2: (1, 0), 3: (1, 1), 4: (0, 1)}
    features = build(
        raw(
            way(1, [1, 2, 3], grid, highway="residential", name="Vòng"),
            way(2, [3, 4, 1], grid, highway="residential", name="Vòng"),
        ),
        BIG_BOUNDARY,
        max_m=2000,
    )
    assert len(features) == 1
    assert set(features[0]["properties"]["osm_way_ids"]) == {1, 2}
