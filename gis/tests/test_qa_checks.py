from qa_checks import check
from shapely.geometry import box

BOUNDARY = box(107.56, 16.46, 107.58, 16.48)


def feature(ref, coords, tier=1, name="A", flags=()):
    return {
        "properties": {"source_ref": ref, "name": name, "pilot_tier": tier, "qa_flags": list(flags)},
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def collection(*features):
    return {"type": "FeatureCollection", "features": list(features)}


LINE = [(107.565, 16.465), (107.565, 16.467)]  # ≈ 221 m


def test_clean_data_has_no_errors():
    errors, _ = check(collection(feature("a", LINE)), BOUNDARY, 400, 30)
    assert errors == []


def test_overlap_and_duplicate_ref_are_errors():
    errors, _ = check(collection(feature("a", LINE), feature("a", LINE)), BOUNDARY, 400, 30)
    assert any("trùng" in e for e in errors)
    assert any("Chồng lấn" in e for e in errors)


def test_outside_boundary_and_too_long_are_errors():
    far = [(107.59, 16.465), (107.59, 16.475)]
    errors, _ = check(collection(feature("far", far)), BOUNDARY, 400, 30)
    assert any("ngoài ranh giới" in e for e in errors)
    assert any("> 400" in e for e in errors)


def test_self_intersection_is_error():
    loop = [(107.565, 16.465), (107.567, 16.467), (107.567, 16.465), (107.565, 16.467)]
    errors, _ = check(collection(feature("x", loop)), BOUNDARY, 1000, 30)
    assert any("tự cắt" in e for e in errors)


def test_disconnected_kiet_is_warning():
    kiet = [(107.57, 16.47), (107.57, 16.471)]
    errors, warnings = check(
        collection(feature("a", LINE), feature("k", kiet, tier=3, name="Kiệt 1")), BOUNDARY, 400, 30
    )
    assert errors == []
    assert any("Kiệt không nối" in w for w in warnings)
