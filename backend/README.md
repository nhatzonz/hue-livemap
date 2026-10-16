# HUE-LIVEMAP — Backend (FastAPI)

| Thành phần | Phiên bản dev (16/10/2026) |
|---|---|
| Python | 3.12 (quản lý bằng `uv`) |
| PostgreSQL | 17.11 (Homebrew), cổng **5433** |
| PostGIS | 3.6.4 |
| FastAPI / SQLAlchemy / Alembic | xem `uv.lock` |

Không dùng Docker. Xem `docs/adr/0001-modular-monolith-no-docker.md`.

## Cài đặt lần đầu (macOS)

```bash
brew install postgresql@17 postgis uv
./infra/scripts/setup_dev_db.sh        # chạy từ thư mục gốc repo: initdb, cổng 5433, tạo DB dev + test, bật extension

cd backend
cp .env.example .env
uv sync                                # tự tải Python 3.12 và cài thư viện
uv run alembic upgrade head            # tạo bảng
```

> Cổng 5433 được chọn vì máy dev đã có PostgreSQL 16 (bản EDB) chạy ở 5432 nhưng không có PostGIS.

## Chạy

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- `--host 0.0.0.0` để điện thoại cùng Wi-Fi gọi được qua `http://<ip-máy>:8000`.
- Kiểm tra: `curl http://localhost:8000/health/ready` →
  `{"status":"ready","postgres_version":"17.11 (Homebrew)","postgis_version":"3.6.4"}`
- Tài liệu API: http://localhost:8000/docs

Sau khi khởi động lại máy, PostgreSQL không tự chạy. Chạy lại `./infra/scripts/setup_dev_db.sh` (an toàn khi chạy nhiều lần). Muốn tự chạy khi đăng nhập thì dùng `brew services start postgresql@17`; cổng 5433 đã được ghi vào `postgresql.auto.conf`.

## Kiểm thử và lint

```bash
uv run pytest              # dùng DB hue_livemap_test, dựng lại schema từ migration mỗi lần chạy
uv run ruff check . && uv run ruff format --check .
```

## Cấu trúc

```
app/
├── main.py          # create_app(): middleware, error handler, router
├── core/            # config (pydantic-settings), errors, logging
├── db/              # engine/session, Base
├── models/          # SQLAlchemy + GeoAlchemy2
├── api/             # health.py, v1/ (các router nghiệp vụ)
├── schemas/  services/  jobs/
migrations/          # Alembic; SQL thuần cho phần PostGIS. Đây là nguồn sự thật của schema.
tests/
```

## API hiện có (`/api/v1`)

| Endpoint | Quyền | Ghi chú |
|---|---|---|
| `POST /auth/device`, `POST /auth/refresh` | công khai | Thiết bị ẩn danh → JWT 60' + refresh 30 ngày (xoay vòng) |
| `GET /regions/hue` | công khai | Ranh giới thí điểm, phiên bản dữ liệu |
| `GET /segments?bbox=&dimension=` | công khai | GeoJSON + trạng thái; ETag/304 |
| `GET /segments/{code}` | công khai | Trạng thái 3 chiều + bằng chứng gần đây (ẩn danh) |
| `GET /segments/{code}/history` | công khai | Lịch sử trạng thái |
| `GET /status/changes?since=` | công khai | Delta trạng thái theo `change_seq` |
| `GET /search?q=` | công khai | Không dấu, trigram |
| `GET /snap?lat=&lon=` | công khai | ≤ 3 đoạn trong 30 m |
| `POST /reports` | thiết bị | Idempotent theo `id` do client sinh |
| `PUT /reports/{id}/media` | chủ phản ánh | Ảnh ≤ 5 MB, server mã hoá lại + xoá EXIF |
| `POST /segments/{code}/confirm` | thiết bị | "Vẫn còn / Đã hết" |
| `GET /me/reports` | thiết bị | Phản ánh của tôi |

Status engine: [app/services/status_engine.py](app/services/status_engine.py). Tham số nằm trong bảng `status_rule` (có version); job nền tính suy giảm mỗi phút (`ENABLE_JOBS`).

## Quy ước

- Lỗi API luôn có dạng `{"error": {"code", "message", "details"}}`.
- Mọi bảng nghiệp vụ có `is_demo`. `APP_ENV=production` sẽ từ chối khởi động nếu `INCLUDE_DEMO_DATA=true`.
- Thay đổi schema = migration mới (`uv run alembic revision -m "..."`), không sửa migration đã chạy.
