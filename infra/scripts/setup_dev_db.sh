#!/usr/bin/env bash
# Tạo cụm PostgreSQL 17 (Homebrew) ở cổng 5433 cùng DB dev/test cho HUE-LIVEMAP.
# Chạy lại nhiều lần vẫn an toàn (idempotent). Không dùng Docker.
#
# Cổng 5433 để không đụng PostgreSQL khác có thể đang chạy ở 5432.
set -euo pipefail

# Trên macOS, postmaster dừng với "became multithreaded during startup" nếu LC_ALL không hợp lệ.
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

PG_PREFIX="$(brew --prefix postgresql@17)"
PG_BIN="$PG_PREFIX/bin"
PG_PORT="${PG_PORT:-5433}"
PG_DATA="${PG_DATA:-$(brew --prefix)/var/postgresql@17}"
PG_LOG="${PG_DATA}/server.log"

if ! brew list postgis >/dev/null 2>&1; then
  echo "Thiếu PostGIS. Chạy: brew install postgresql@17 postgis" >&2
  exit 1
fi

# 1. Khởi tạo cụm nếu chưa có
if [ ! -f "$PG_DATA/PG_VERSION" ]; then
  echo "→ initdb tại $PG_DATA"
  "$PG_BIN/initdb" -D "$PG_DATA" --encoding=UTF8 --locale=C --auth=trust -U "$(whoami)"
fi

# 2. Đặt cổng (ghi vào postgresql.auto.conf, không sửa file mặc định)
if ! grep -q "^port = '$PG_PORT'" "$PG_DATA/postgresql.auto.conf" 2>/dev/null; then
  echo "port = '$PG_PORT'" >> "$PG_DATA/postgresql.auto.conf"
fi

# 3. Khởi động nếu chưa chạy
if ! "$PG_BIN/pg_isready" -q -h localhost -p "$PG_PORT"; then
  echo "→ khởi động PostgreSQL ở cổng $PG_PORT (log: $PG_LOG)"
  "$PG_BIN/pg_ctl" -D "$PG_DATA" -l "$PG_LOG" -w start
fi

# 4. Tạo DB dev + test và bật extension (cần quyền superuser, migration chỉ "IF NOT EXISTS")
for db in hue_livemap hue_livemap_test; do
  if ! "$PG_BIN/psql" -h localhost -p "$PG_PORT" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1; then
    echo "→ tạo database $db"
    "$PG_BIN/createdb" -h localhost -p "$PG_PORT" "$db"
  fi
  "$PG_BIN/psql" -h localhost -p "$PG_PORT" -d "$db" -q -v ON_ERROR_STOP=1 <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS citext;
SQL
done

"$PG_BIN/psql" -h localhost -p "$PG_PORT" -d hue_livemap -tAc \
  "SELECT 'PostgreSQL ' || current_setting('server_version') || ' · PostGIS ' || postgis_lib_version()"
echo "✓ Sẵn sàng: postgresql+psycopg://localhost:$PG_PORT/hue_livemap"
