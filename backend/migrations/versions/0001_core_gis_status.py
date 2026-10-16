"""Extension PostGIS, mạng lưới đường, trạng thái đoạn đường.

Revision ID: 0001
Revises:
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE EXTENSION IF NOT EXISTS unaccent;
    CREATE EXTENSION IF NOT EXISTS citext;

    -- unaccent() không IMMUTABLE nên không dùng trực tiếp trong generated column/index được.
    CREATE OR REPLACE FUNCTION immutable_unaccent(text) RETURNS text
      LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
      AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$;

    CREATE TABLE data_source (
      id          smallint PRIMARY KEY,
      code        text NOT NULL UNIQUE,
      name        text NOT NULL,
      license     text,
      attribution text,
      url         text,
      notes       text
    );

    CREATE TABLE road (
      id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      region_id   text NOT NULL DEFAULT 'hue',
      name        text NOT NULL,
      name_search text GENERATED ALWAYS AS (lower(immutable_unaccent(name))) STORED,
      road_class  text,
      osm_way_ids bigint[],
      is_demo     boolean NOT NULL DEFAULT false
    );
    CREATE INDEX ix_road_name_search ON road USING gin (name_search gin_trgm_ops);

    CREATE TABLE road_segment (
      id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      code                text NOT NULL UNIQUE,
      region_id           text NOT NULL DEFAULT 'hue',
      road_id             bigint REFERENCES road(id),
      display_name        text NOT NULL,
      segment_type        text NOT NULL
                          CONSTRAINT ck_road_segment_type
                          CHECK (segment_type IN ('street','kiet','hem','bridge','other')),
      geom                geometry(LineString, 4326) NOT NULL
                          CONSTRAINT ck_road_segment_geom_valid CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom)),
      length_m            numeric GENERATED ALWAYS AS (ST_Length(geom::geography)) STORED,
      geom_version        int NOT NULL DEFAULT 1,
      width_class         text CONSTRAINT ck_road_segment_width CHECK (width_class IN ('<2','2-4','4-7','>7')),
      vehicle_access      text CONSTRAINT ck_road_segment_access
                          CHECK (vehicle_access IN ('pedestrian','motorbike','car')),
      drainage_notes      text,
      flood_prone         text NOT NULL DEFAULT 'unknown'
                          CONSTRAINT ck_road_segment_flood_prone
                          CHECK (flood_prone IN ('unknown','low','medium','high')),
      source_id           smallint REFERENCES data_source(id),
      source_ref          text,
      verification_status text NOT NULL DEFAULT 'draft'
                          CONSTRAINT ck_road_segment_verification
                          CHECK (verification_status IN ('draft','desk_reviewed','field_verified','retired')),
      verified_at         timestamptz,
      verified_by         bigint,
      supersedes          bigint[],
      is_demo             boolean NOT NULL DEFAULT false,
      created_at          timestamptz NOT NULL DEFAULT now(),
      updated_at          timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_road_segment_geom ON road_segment USING gist (geom);
    CREATE INDEX ix_road_segment_road_id ON road_segment (road_id);
    CREATE INDEX ix_road_segment_name_search
      ON road_segment USING gin (lower(immutable_unaccent(display_name)) gin_trgm_ops);

    CREATE TABLE segment_hotspot (
      id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      segment_id bigint NOT NULL REFERENCES road_segment(id) ON DELETE CASCADE,
      geom       geometry(Point, 4326) NOT NULL,
      kind       text NOT NULL CONSTRAINT ck_segment_hotspot_kind
                 CHECK (kind IN ('low_point','drain','known_flood')),
      notes      text,
      source_id  smallint REFERENCES data_source(id)
    );
    CREATE INDEX ix_segment_hotspot_geom ON segment_hotspot USING gist (geom);

    CREATE TABLE status_rule (
      version     int PRIMARY KEY,
      params      jsonb NOT NULL,
      active_from timestamptz NOT NULL,
      notes       text
    );

    CREATE SEQUENCE status_change_seq;

    CREATE TABLE segment_status_current (
      segment_id          bigint NOT NULL REFERENCES road_segment(id) ON DELETE CASCADE,
      dimension           text NOT NULL CONSTRAINT ck_status_current_dimension
                          CHECK (dimension IN ('flood','obstacle','traffic')),
      state               text NOT NULL CONSTRAINT ck_status_current_state
                          CHECK (state IN ('NO_DATA','STALE','UNVERIFIED','CONFIRMED','CONFLICTING')),
      level               text,
      confidence          real CONSTRAINT ck_status_current_confidence CHECK (confidence BETWEEN 0 AND 1),
      evidence_count      int NOT NULL DEFAULT 0,
      independent_sources int NOT NULL DEFAULT 0,
      last_evidence_at    timestamptz,
      computed_at         timestamptz NOT NULL,
      rule_version        int NOT NULL REFERENCES status_rule(version),
      change_seq          bigint NOT NULL DEFAULT nextval('status_change_seq'),
      PRIMARY KEY (segment_id, dimension)
    );
    CREATE INDEX ix_status_current_change_seq ON segment_status_current (change_seq);

    CREATE TABLE segment_status_history (
      id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      segment_id   bigint NOT NULL REFERENCES road_segment(id) ON DELETE CASCADE,
      dimension    text NOT NULL,
      state        text NOT NULL,
      level        text,
      confidence   real,
      valid_from   timestamptz NOT NULL,
      valid_to     timestamptz,
      cause        text NOT NULL CONSTRAINT ck_status_history_cause
                   CHECK (cause IN ('new_evidence','decay','moderator_override','expiry','invalidation')),
      rule_version int NOT NULL REFERENCES status_rule(version)
    );
    CREATE INDEX ix_status_history_lookup ON segment_status_history (segment_id, dimension, valid_from DESC);
    """)

    # Dữ liệu cấu hình (không phải dữ liệu demo): danh mục nguồn và tham số engine v1 (PROJECT_PLAN.md 6.1, 6.3).
    op.execute("""
    INSERT INTO data_source (id, code, name, license, attribution, url) VALUES
      (1, 'osm', 'OpenStreetMap', 'ODbL-1.0', '© OpenStreetMap contributors', 'https://www.openstreetmap.org/copyright'),
      (2, 'field_survey', 'Khảo sát thực địa HUE-LIVEMAP', 'internal', NULL, NULL),
      (3, 'pre_pilot_survey_2026', 'Quan sát ngập trước thí điểm (mùa lũ 2026)', 'internal', NULL, NULL),
      (4, 'citizen', 'Phản ánh người dùng', 'internal', NULL, NULL),
      (5, 'moderator', 'Ban kiểm duyệt HUE-LIVEMAP', 'internal', NULL, NULL),
      (6, 'iot', 'Cảm biến IoT HUE-LIVEMAP', 'internal', NULL, NULL),
      (99, 'demo', 'DỮ LIỆU MINH HOẠ (không phải dữ liệu thật)', 'internal', NULL, NULL);

    INSERT INTO status_rule (version, active_from, notes, params) VALUES (1, now(),
      'Giá trị khởi điểm theo PROJECT_PLAN.md mục 6; hiệu chỉnh sau pilot.',
      '{
        "dimensions": {
          "flood":    {"fresh_ttl_min": 180, "hard_expiry_min": 1440, "half_life_min": 60,
                       "levels": ["dry","puddle","ankle","calf","knee","above_knee"]},
          "obstacle": {"fresh_ttl_min": 720, "hard_expiry_min": 4320, "half_life_min": 240,
                       "levels": ["none","partial","blocked"]},
          "traffic":  {"fresh_ttl_min": 30,  "hard_expiry_min": 180,  "half_life_min": 10,
                       "levels": ["free","slow","congested","standstill"]}
        },
        "source_weight": {"moderator": 5.0, "iot_trusted": 4.0, "iot_testing": 1.0,
                          "citizen_report": 1.0, "quick_confirm": 0.8, "gps_agg": 0.5},
        "photo_bonus": 1.3,
        "proximity": {"near_m": 50, "far_factor": 0.6},
        "confirm_min_independent": 3,
        "confirm_min_photos": 1,
        "conflict_share": 0.4,
        "one_vote_per_actor_min": 30
      }'::jsonb);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS segment_status_history;
    DROP TABLE IF EXISTS segment_status_current;
    DROP SEQUENCE IF EXISTS status_change_seq;
    DROP TABLE IF EXISTS status_rule;
    DROP TABLE IF EXISTS segment_hotspot;
    DROP TABLE IF EXISTS road_segment;
    DROP TABLE IF EXISTS road;
    DROP TABLE IF EXISTS data_source;
    DROP FUNCTION IF EXISTS immutable_unaccent(text);
    """)
