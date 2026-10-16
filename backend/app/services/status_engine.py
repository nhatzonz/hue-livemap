"""Status engine v1 (luật, không ML), theo PROJECT_PLAN.md mục 6.3.

`compute()` là hàm thuần: nhận danh sách bằng chứng + tham số + thời điểm, trả về trạng thái.
`recompute()` đọc DB, gọi compute(), ghi trạng thái hiện tại và lịch sử khi có thay đổi.

Nguyên tắc bất biến (có test):
  - Không có bằng chứng còn hiệu lực → NO_DATA (không bao giờ "bình thường" mặc định).
  - Một nguồn đơn lẻ (không phải moderator/cảm biến tin cậy) không bao giờ tạo CONFIRMED.
  - Bằng chứng quá TTL tươi → STALE; quá hạn cứng → NO_DATA.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

AUTHORITATIVE_SOURCES = {"moderator", "iot_trusted", "official"}
FUTURE_TOLERANCE = timedelta(minutes=5)
DIMENSION_KEYS = {"flood": 0, "obstacle": 1, "traffic": 2}
# Độ tin cậy chỉ hiển thị theo mức (Thấp/Trung bình/Cao). Chỉ đổi mức mới tính là "thay đổi hiển thị",
# để suy giảm liên tục theo thời gian không làm đổi ETag bản đồ của mọi client mỗi phút.
CONFIDENCE_BANDS = (0.4, 0.75)


@dataclass(frozen=True)
class Rule:
    version: int
    params: dict


@dataclass(frozen=True)
class Evidence:
    level: str
    source_type: str
    actor_key: str
    observed_at: datetime
    reliability: float = 1.0
    has_photo: bool = False
    proximity_m: float | None = None


@dataclass(frozen=True)
class StatusResult:
    state: str
    level: str | None
    confidence: float | None
    evidence_count: int
    independent_sources: int
    last_evidence_at: datetime | None


NO_DATA_RESULT = StatusResult("NO_DATA", None, None, 0, 0, None)


def _weight(e: Evidence, params: dict, half_life_min: float, now: datetime) -> float:
    age_min = max(0.0, (now - e.observed_at).total_seconds() / 60)
    reliability = min(1.5, max(0.5, e.reliability))
    near_m = params["proximity"]["near_m"]
    proximity = (
        1.0 if e.proximity_m is not None and e.proximity_m <= near_m else params["proximity"]["far_factor"]
    )
    if e.source_type in AUTHORITATIVE_SOURCES or e.source_type.startswith("iot"):
        proximity = 1.0  # moderator/cảm biến không phụ thuộc vị trí người gửi
    photo = params["photo_bonus"] if e.has_photo else 1.0
    decay = 0.5 ** (age_min / half_life_min)
    return params["source_weight"].get(e.source_type, 1.0) * reliability * proximity * photo * decay


def _weighted_median(pairs: list[tuple[int, float]]) -> int:
    pairs = sorted(pairs)
    total = sum(w for _, w in pairs)
    acc = 0.0
    for idx, w in pairs:
        acc += w
        if acc >= total / 2:
            return idx
    return pairs[-1][0]


def latest_per_actor(evidences: list[Evidence]) -> list[Evidence]:
    """Mỗi nguồn (thiết bị/người/cảm biến) chỉ có một phiếu: ý kiến mới nhất của họ."""
    latest: dict[str, Evidence] = {}
    for e in evidences:
        if e.actor_key not in latest or e.observed_at > latest[e.actor_key].observed_at:
            latest[e.actor_key] = e
    return list(latest.values())


def compute(evidences: list[Evidence], dimension: str, params: dict, now: datetime) -> StatusResult:
    dim = params["dimensions"][dimension]
    levels: list[str] = dim["levels"]
    hard_expiry = timedelta(minutes=dim["hard_expiry_min"])
    fresh_ttl = timedelta(minutes=dim["fresh_ttl_min"])

    valid = [
        e
        for e in evidences
        if e.level in levels and now - hard_expiry <= e.observed_at <= now + FUTURE_TOLERANCE
    ]
    votes = latest_per_actor(valid)
    if not votes:
        return NO_DATA_RESULT

    weighted = [(levels.index(e.level), _weight(e, params, dim["half_life_min"], now), e) for e in votes]
    total = sum(w for _, w, _ in weighted)
    estimate_idx = _weighted_median([(idx, w) for idx, w, _ in weighted])
    confidence = round(1 - math.exp(-total), 3)
    last_at = max(e.observed_at for e in votes)
    fresh = [e for e in votes if e.observed_at >= now - fresh_ttl]

    conflicting_weight = sum(w for idx, w, _ in weighted if abs(idx - estimate_idx) >= 2)
    if fresh and total > 0 and conflicting_weight > params["conflict_share"] * total:
        state = "CONFLICTING"
    elif not fresh:
        state = "STALE"
    else:
        # Nguồn tươi đồng thuận (lệch tối đa 1 bậc so với ước lượng)
        agreeing = [e for e in fresh if abs(levels.index(e.level) - estimate_idx) <= 1]
        authoritative = any(e.source_type in AUTHORITATIVE_SOURCES for e in agreeing)
        photos = sum(1 for e in agreeing if e.has_photo)
        crowd_confirmed = (
            len(agreeing) >= params["confirm_min_independent"] and photos >= params["confirm_min_photos"]
        )
        state = "CONFIRMED" if authoritative or crowd_confirmed else "UNVERIFIED"

    independent = len({e.actor_key for e in fresh}) if fresh else len(votes)
    return StatusResult(
        state=state,
        level=levels[estimate_idx],
        confidence=confidence,
        evidence_count=len(votes),
        independent_sources=independent,
        last_evidence_at=last_at,
    )


# ---------------------------------------------------------------- DB


def active_rule(db: Session) -> Rule:
    row = db.execute(
        text(
            "SELECT version, params FROM status_rule WHERE active_from <= now() ORDER BY version DESC LIMIT 1"
        )
    ).one()
    return Rule(row.version, row.params)


def load_evidences(db: Session, segment_id: int, dimension: str, since: datetime) -> list[Evidence]:
    rows = db.execute(
        text("""
            SELECT level, source_type, actor_key, observed_at, reliability, has_photo, proximity_m
            FROM observation
            WHERE segment_id = :sid AND dimension = :dim AND invalidated_at IS NULL AND observed_at >= :since
        """),
        {"sid": segment_id, "dim": dimension, "since": since},
    ).all()
    return [Evidence(**row._mapping) for row in rows]


def confidence_band(confidence: float | None) -> int:
    return sum(1 for edge in CONFIDENCE_BANDS if (confidence or 0) >= edge)


def _significant_change(old, new: StatusResult) -> bool:
    if old is None:
        return new.state != "NO_DATA"
    return (
        old.state != new.state
        or old.level != new.level
        or old.evidence_count != new.evidence_count
        or old.last_evidence_at != new.last_evidence_at
        or confidence_band(old.confidence) != confidence_band(new.confidence)
    )


def recompute(
    db: Session,
    segment_id: int,
    dimension: str,
    now: datetime,
    cause: str = "new_evidence",
    rule: Rule | None = None,
) -> bool:
    """Tính lại trạng thái một (đoạn, chiều). Trả về True nếu trạng thái hiển thị thay đổi.

    Khoá advisory theo (đoạn, chiều) trong transaction: hai phản ánh đồng thời vào cùng đoạn được tính
    tuần tự, tránh ghi hai bản lịch sử "đang hiệu lực" (FOR UPDATE không khoá được khi chưa có dòng).
    """
    db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": segment_id * len(DIMENSION_KEYS) + DIMENSION_KEYS[dimension]},
    )
    rule = rule or active_rule(db)
    params = rule.params
    version = rule.version
    hard_expiry = timedelta(minutes=params["dimensions"][dimension]["hard_expiry_min"])
    result = compute(load_evidences(db, segment_id, dimension, now - hard_expiry), dimension, params, now)

    current = db.execute(
        text("""
            SELECT state, level, confidence, evidence_count, last_evidence_at
            FROM segment_status_current WHERE segment_id = :sid AND dimension = :dim
        """),
        {"sid": segment_id, "dim": dimension},
    ).one_or_none()
    if not _significant_change(current, result):
        return False

    values = {
        "sid": segment_id,
        "dim": dimension,
        "state": result.state,
        "level": result.level,
        "confidence": result.confidence,
        "count": result.evidence_count,
        "independent": result.independent_sources,
        "last_at": result.last_evidence_at,
        "now": now,
        "rule": version,
    }
    db.execute(
        text("""
            INSERT INTO segment_status_current
              (segment_id, dimension, state, level, confidence, evidence_count, independent_sources,
               last_evidence_at, computed_at, rule_version, change_seq)
            VALUES (:sid, :dim, :state, :level, :confidence, :count, :independent, :last_at, :now, :rule,
                    nextval('status_change_seq'))
            ON CONFLICT (segment_id, dimension) DO UPDATE SET
              state = EXCLUDED.state, level = EXCLUDED.level, confidence = EXCLUDED.confidence,
              evidence_count = EXCLUDED.evidence_count, independent_sources = EXCLUDED.independent_sources,
              last_evidence_at = EXCLUDED.last_evidence_at, computed_at = EXCLUDED.computed_at,
              rule_version = EXCLUDED.rule_version, change_seq = nextval('status_change_seq')
        """),
        values,
    )

    # Lịch sử chỉ ghi khi state hoặc level đổi
    if current is None or current.state != result.state or current.level != result.level:
        if result.state == "NO_DATA" and cause == "decay":
            cause = "expiry"
        db.execute(
            text("""
                UPDATE segment_status_history SET valid_to = :now
                WHERE segment_id = :sid AND dimension = :dim AND valid_to IS NULL
            """),
            values,
        )
        db.execute(
            text("""
                INSERT INTO segment_status_history
                  (segment_id, dimension, state, level, confidence, valid_from, cause, rule_version)
                VALUES (:sid, :dim, :state, :level, :confidence, :now, :cause, :rule)
            """),
            {**values, "cause": cause},
        )
    return True


def recompute_all_active(db: Session, now: datetime) -> int:
    """Job định kỳ: áp dụng suy giảm theo thời gian (UNVERIFIED → STALE → NO_DATA) cho mọi đoạn đang có trạng thái."""
    pairs = db.execute(
        text("SELECT segment_id, dimension FROM segment_status_current WHERE state <> 'NO_DATA'")
    ).all()
    rule = active_rule(db)
    return sum(
        1 for segment_id, dimension in pairs if recompute(db, segment_id, dimension, now, "decay", rule)
    )
