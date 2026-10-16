"""Người dùng, thiết bị, phản ánh, sự vụ, ảnh, bằng chứng (observation).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE app_user (
      id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      role          text NOT NULL DEFAULT 'citizen'
                    CONSTRAINT ck_app_user_role
                    CHECK (role IN ('citizen','contributor','moderator','partner','admin')),
      display_name  text,
      email         citext UNIQUE,
      password_hash text,
      reputation    real NOT NULL DEFAULT 1.0,
      is_banned     boolean NOT NULL DEFAULT false,
      created_at    timestamptz NOT NULL DEFAULT now(),
      deleted_at    timestamptz
    );

    -- Thiết bị ẩn danh: id do client sinh (UUID v4, lưu SecureStore). Uy tín gắn với thiết bị
    -- vì người dùng thường không cần tài khoản.
    CREATE TABLE device (
      id            uuid PRIMARY KEY,
      user_id       bigint REFERENCES app_user(id),
      platform      text,
      app_version   text,
      push_token    text,
      gps_opt_in    boolean NOT NULL DEFAULT false,
      reputation    real NOT NULL DEFAULT 1.0,
      is_banned     boolean NOT NULL DEFAULT false,
      created_ip    inet,
      created_at    timestamptz NOT NULL DEFAULT now(),
      last_seen_at  timestamptz
    );
    CREATE INDEX ix_device_created_ip ON device (created_ip, created_at);

    CREATE TABLE refresh_token (
      id          uuid PRIMARY KEY,
      device_id   uuid NOT NULL REFERENCES device(id) ON DELETE CASCADE,
      token_hash  text NOT NULL UNIQUE,
      expires_at  timestamptz NOT NULL,
      revoked_at  timestamptz,
      created_at  timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE incident (
      id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      segment_id     bigint REFERENCES road_segment(id),
      dimension      text NOT NULL CONSTRAINT ck_incident_dimension CHECK (dimension IN ('flood','obstacle','traffic')),
      status         text NOT NULL DEFAULT 'open'
                     CONSTRAINT ck_incident_status CHECK (status IN ('open','verified','rejected','resolved','expired')),
      priority       real NOT NULL DEFAULT 0,
      report_count   int NOT NULL DEFAULT 0,
      first_seen_at  timestamptz NOT NULL,
      last_seen_at   timestamptz NOT NULL,
      location       geometry(Point, 4326),
      verified_by    bigint REFERENCES app_user(id),
      verified_at    timestamptz,
      moderator_note text,
      is_demo        boolean NOT NULL DEFAULT false
    );
    CREATE INDEX ix_incident_queue ON incident (status, priority DESC, last_seen_at DESC);
    CREATE INDEX ix_incident_segment ON incident (segment_id, dimension, last_seen_at DESC);

    CREATE TABLE report (
      id                uuid PRIMARY KEY,
      device_id         uuid NOT NULL REFERENCES device(id),
      user_id           bigint REFERENCES app_user(id),
      segment_id        bigint REFERENCES road_segment(id),
      incident_id       bigint REFERENCES incident(id),
      dimension         text NOT NULL CONSTRAINT ck_report_dimension CHECK (dimension IN ('flood','obstacle','traffic')),
      category          text NOT NULL,
      level             text NOT NULL,
      description       text CONSTRAINT ck_report_description CHECK (char_length(description) <= 280),
      location          geometry(Point, 4326) NOT NULL,
      reporter_location geometry(Point, 4326),
      gps_accuracy_m    real,
      snap_distance_m   real,
      proximity_m       real,
      client_created_at timestamptz NOT NULL,
      received_at       timestamptz NOT NULL DEFAULT now(),
      status            text NOT NULL DEFAULT 'pending'
                        CONSTRAINT ck_report_status CHECK (status IN ('pending','accepted','rejected','duplicate','expired')),
      reject_reason     text,
      is_demo           boolean NOT NULL DEFAULT false
    );
    CREATE INDEX ix_report_location ON report USING gist (location);
    CREATE INDEX ix_report_device_time ON report (device_id, received_at DESC);
    CREATE INDEX ix_report_segment ON report (segment_id, dimension, received_at DESC);

    CREATE TABLE report_media (
      id           uuid PRIMARY KEY,
      report_id    uuid NOT NULL REFERENCES report(id) ON DELETE CASCADE,
      storage_key  text NOT NULL,
      thumb_key    text NOT NULL,
      mime_type    text NOT NULL,
      width        int NOT NULL,
      height       int NOT NULL,
      bytes        int NOT NULL,
      sha256       text NOT NULL,
      duplicate_of uuid REFERENCES report_media(id),   -- ảnh y hệt ảnh đã có ở phản ánh khác → nghi vấn
      moderation   text NOT NULL DEFAULT 'pending'
                   CONSTRAINT ck_report_media_moderation CHECK (moderation IN ('pending','approved','hidden')),
      created_at   timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_report_media_sha ON report_media (sha256);

    -- Bằng chứng chuẩn hoá: mọi nguồn quy về đây; status engine chỉ đọc bảng này.
    CREATE TABLE observation (
      id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      segment_id     bigint NOT NULL REFERENCES road_segment(id) ON DELETE CASCADE,
      dimension      text NOT NULL CONSTRAINT ck_observation_dimension CHECK (dimension IN ('flood','obstacle','traffic')),
      level          text NOT NULL,
      source_type    text NOT NULL CONSTRAINT ck_observation_source
                     CHECK (source_type IN ('citizen_report','quick_confirm','moderator','iot_trusted','iot_testing','gps_agg','official')),
      source_ref     text,
      actor_key      text NOT NULL,      -- 'device:<uuid>', 'user:<id>', 'sensor:<id>' — đếm nguồn độc lập
      reliability    real NOT NULL DEFAULT 1.0,   -- uy tín người gửi tại thời điểm ghi (0.5–1.5)
      has_photo      boolean NOT NULL DEFAULT false,
      proximity_m    real,
      observed_at    timestamptz NOT NULL,
      created_at     timestamptz NOT NULL DEFAULT now(),
      invalidated_at timestamptz,
      is_demo        boolean NOT NULL DEFAULT false
    );
    CREATE INDEX ix_observation_lookup ON observation (segment_id, dimension, observed_at DESC)
      WHERE invalidated_at IS NULL;
    CREATE INDEX ix_observation_source_ref ON observation (source_type, source_ref);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS observation;
    DROP TABLE IF EXISTS report_media;
    DROP TABLE IF EXISTS report;
    DROP TABLE IF EXISTS incident;
    DROP TABLE IF EXISTS refresh_token;
    DROP TABLE IF EXISTS device;
    DROP TABLE IF EXISTS app_user;
    """)
