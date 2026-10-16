# HUE-LIVEMAP

Bản đồ trạng thái đô thị thời gian thực cấp đoạn đường và kiệt cho thành phố Huế: ngập, vật cản, giao thông. Mỗi trạng thái đều kèm độ tin cậy và thời điểm cập nhật.

| Thư mục | Nội dung | Trạng thái |
|---|---|---|
| [backend/](backend/) | FastAPI + PostgreSQL/PostGIS | Tuần 5: auth thiết bị, phản ánh, ảnh, status engine, lịch sử, 76 test |
| [mobile/](mobile/) | Expo SDK 58 (JavaScript, Expo Router) | Tuần 5: bản đồ trạng thái, gửi phản ánh có ảnh, xác nhận nhanh, lịch sử |
| [gis/](gis/) | Pipeline mạng lưới đường | Tuần 2: ranh giới, cắt đoạn, QA, nhập DB (222 đoạn nháp), 20 test |
| web/ | Dashboard kiểm duyệt (React + Vite) | Tuần 6 |
| [ai/](ai/) | Mô hình, chỉ khi đủ dữ liệu | Chưa bắt đầu (có chủ ý) |
| [infra/](infra/) | Script cài đặt, triển khai, backup (không Docker) | Script DB dev |
| [docs/](docs/) | ADR, đặc tả | ADR 0001 |

## Chạy nhanh trên máy dev (macOS)

```bash
brew install postgresql@17 postgis uv
./infra/scripts/setup_dev_db.sh

# Terminal 1: backend
cd backend && cp .env.example .env && uv sync && uv run alembic upgrade head
(cd ../gis && uv sync && uv run python scripts/qa_checks.py && uv run python scripts/import_segments.py)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: mobile (điện thoại cùng Wi-Fi, cài Expo Go)
cd mobile && npm install && npm start
```

## Nguyên tắc dữ liệu

- Đoạn chưa có dữ liệu **không bao giờ** hiển thị là bình thường.
- Một phản ánh đơn lẻ không đủ để xác nhận trạng thái.
- Mọi dữ liệu minh hoạ gắn `is_demo = true` và không xuất hiện ở production.

Dữ liệu bản đồ © OpenStreetMap contributors (ODbL).
# hue-livemap
