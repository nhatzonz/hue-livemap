"""Status engine: kiểm thử các nguyên tắc ở PROJECT_PLAN.md mục 6 bằng dữ liệu tổng hợp."""

import copy
from datetime import UTC, datetime, timedelta

import pytest

from app.services.status_engine import Evidence, compute

NOW = datetime(2026, 11, 2, 17, 0, tzinfo=UTC)

# Bản sao tham số status_rule v1 (migration 0001)
PARAMS = {
    "dimensions": {
        "flood": {
            "fresh_ttl_min": 180,
            "hard_expiry_min": 1440,
            "half_life_min": 60,
            "levels": ["dry", "puddle", "ankle", "calf", "knee", "above_knee"],
        },
        "obstacle": {
            "fresh_ttl_min": 720,
            "hard_expiry_min": 4320,
            "half_life_min": 240,
            "levels": ["none", "partial", "blocked"],
        },
        "traffic": {
            "fresh_ttl_min": 30,
            "hard_expiry_min": 180,
            "half_life_min": 10,
            "levels": ["free", "slow", "congested", "standstill"],
        },
    },
    "source_weight": {
        "moderator": 5.0,
        "iot_trusted": 4.0,
        "iot_testing": 1.0,
        "citizen_report": 1.0,
        "quick_confirm": 0.8,
        "gps_agg": 0.5,
    },
    "photo_bonus": 1.3,
    "proximity": {"near_m": 50, "far_factor": 0.6},
    "confirm_min_independent": 3,
    "confirm_min_photos": 1,
    "conflict_share": 0.4,
    "one_vote_per_actor_min": 30,
}


def ev(level, actor="device:a", minutes_ago=5, source="citizen_report", photo=False, proximity=10.0):
    return Evidence(
        level=level,
        source_type=source,
        actor_key=actor,
        observed_at=NOW - timedelta(minutes=minutes_ago),
        has_photo=photo,
        proximity_m=proximity,
    )


def flood(*evidences):
    return compute(list(evidences), "flood", PARAMS, NOW)


def test_no_evidence_is_no_data_never_normal():
    result = flood()
    assert result.state == "NO_DATA"
    assert result.level is None


def test_single_report_is_unverified_even_with_photo():
    result = flood(ev("calf", photo=True))
    assert result.state == "UNVERIFIED"
    assert result.level == "calf"
    assert result.evidence_count == 1


def test_same_actor_cannot_confirm_alone():
    result = flood(*[ev("calf", actor="device:same", minutes_ago=m, photo=True) for m in (1, 5, 9, 13)])
    assert result.state == "UNVERIFIED"
    assert result.evidence_count == 1  # chỉ phiếu mới nhất của mỗi nguồn


def test_three_independent_with_photo_confirms():
    result = flood(ev("calf", "device:a", photo=True), ev("calf", "device:b"), ev("knee", "device:c"))
    assert result.state == "CONFIRMED"
    assert result.independent_sources == 3


def test_three_independent_without_photo_stays_unverified():
    result = flood(ev("calf", "device:a"), ev("calf", "device:b"), ev("calf", "device:c"))
    assert result.state == "UNVERIFIED"


def test_moderator_confirms_and_dominates_level():
    result = flood(ev("ankle", "device:a"), ev("knee", "user:7", source="moderator"))
    assert result.state == "CONFIRMED"
    assert result.level == "knee"


def test_stale_after_fresh_ttl_keeps_last_level():
    result = flood(ev("calf", minutes_ago=181))
    assert result.state == "STALE"
    assert result.level == "calf"


def test_no_data_after_hard_expiry():
    assert flood(ev("calf", minutes_ago=24 * 60 + 1)).state == "NO_DATA"


def test_future_evidence_ignored():
    assert flood(ev("calf", minutes_ago=-30)).state == "NO_DATA"


def test_unknown_level_ignored():
    assert flood(ev("waist")).state == "NO_DATA"


def test_conflicting_reports():
    result = flood(ev("above_knee", "device:a"), ev("dry", "device:b"))
    assert result.state == "CONFLICTING"


def test_one_level_apart_is_not_conflict():
    result = flood(ev("calf", "device:a"), ev("knee", "device:b"))
    assert result.state == "UNVERIFIED"


def test_confirmed_dry_requires_evidence():
    # "Không ngập" chỉ xuất hiện khi có người báo đã hết, và vẫn cần đủ nguồn mới xác nhận
    one = flood(ev("dry", "device:a"))
    assert (one.state, one.level) == ("UNVERIFIED", "dry")
    many = flood(ev("dry", "device:a", photo=True), ev("dry", "device:b"), ev("dry", "device:c"))
    assert (many.state, many.level) == ("CONFIRMED", "dry")


def test_newer_evidence_outweighs_old():
    # Báo cáo "knee" cũ 3 tiếng (đã suy giảm) vs hai báo cáo "dry" mới → nước đã rút
    result = flood(
        ev("knee", "device:a", minutes_ago=170), ev("dry", "device:b", 2), ev("dry", "device:c", 3)
    )
    assert result.level == "dry"


def test_far_reporter_has_less_weight():
    near = flood(ev("calf", proximity=10))
    far = flood(ev("calf", proximity=500))
    assert far.confidence < near.confidence


def test_traffic_ttl_is_short():
    assert compute([ev("congested", minutes_ago=31)], "traffic", PARAMS, NOW).state == "STALE"
    assert compute([ev("congested", minutes_ago=181)], "traffic", PARAMS, NOW).state == "NO_DATA"


@pytest.mark.parametrize("min_independent", [2, 4])
def test_thresholds_come_from_params(min_independent):
    params = copy.deepcopy(PARAMS)
    params["confirm_min_independent"] = min_independent
    evidences = [ev("calf", "device:a", photo=True), ev("calf", "device:b"), ev("calf", "device:c")]
    expected = "CONFIRMED" if min_independent <= 3 else "UNVERIFIED"
    assert compute(evidences, "flood", params, NOW).state == expected


def test_params_match_seeded_rule(db):
    from app.models import StatusRule

    assert db.get(StatusRule, 1).params == PARAMS


def test_confidence_decay_alone_is_not_a_visible_change():
    from app.services.status_engine import StatusResult, _significant_change

    base = StatusResult("UNVERIFIED", "calf", 0.63, 1, 1, NOW)
    decayed = StatusResult("UNVERIFIED", "calf", 0.55, 1, 1, NOW)  # cùng mức "Trung bình"
    assert not _significant_change(base, decayed)
    assert _significant_change(base, StatusResult("UNVERIFIED", "calf", 0.35, 1, 1, NOW))  # xuống mức "Thấp"
