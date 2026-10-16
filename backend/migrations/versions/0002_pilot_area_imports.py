"""Vùng thí điểm, lịch sử nhập dữ liệu GIS, tầng thí điểm của đoạn đường.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE pilot_area (
      id          text PRIMARY KEY,                    -- 'hue-pilot-a'
      region_id   text NOT NULL DEFAULT 'hue',
      name        text NOT NULL,
      geom        geometry(Polygon, 4326) NOT NULL
                  CONSTRAINT ck_pilot_area_geom_valid CHECK (ST_IsValid(geom)),
      status      text NOT NULL DEFAULT 'draft'
                  CONSTRAINT ck_pilot_area_status CHECK (status IN ('draft','active','retired')),
      method      text,
      source_id   smallint REFERENCES data_source(id),
      updated_at  timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_pilot_area_geom ON pilot_area USING gist (geom);

    -- Mỗi lần chạy import_segments.py là một phiên bản dữ liệu đường (hiển thị trong app).
    CREATE TABLE dataset_import (
      id           int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      kind         text NOT NULL CONSTRAINT ck_dataset_import_kind CHECK (kind IN ('segments','pilot_area')),
      region_id    text NOT NULL DEFAULT 'hue',
      source_file  text NOT NULL,
      source_meta  jsonb,
      stats        jsonb NOT NULL,
      imported_at  timestamptz NOT NULL DEFAULT now(),
      imported_by  text
    );

    ALTER TABLE road ADD CONSTRAINT uq_road_region_name UNIQUE (region_id, name);

    ALTER TABLE road_segment
      ADD COLUMN pilot_tier smallint
          CONSTRAINT ck_road_segment_pilot_tier CHECK (pilot_tier IN (1, 2, 3)),
      ADD COLUMN dataset_import_id int REFERENCES dataset_import(id);

    -- Khoá ghép với nguồn: import lại cập nhật đúng đoạn cũ thay vì tạo đoạn mới.
    CREATE UNIQUE INDEX uq_road_segment_source_ref ON road_segment (source_id, source_ref)
      WHERE source_ref IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
    DROP INDEX IF EXISTS uq_road_segment_source_ref;
    ALTER TABLE road_segment DROP COLUMN IF EXISTS dataset_import_id, DROP COLUMN IF EXISTS pilot_tier;
    ALTER TABLE road DROP CONSTRAINT IF EXISTS uq_road_region_name;
    DROP TABLE IF EXISTS dataset_import;
    DROP TABLE IF EXISTS pilot_area;
    """)
