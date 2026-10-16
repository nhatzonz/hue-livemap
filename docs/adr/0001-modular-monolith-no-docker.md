# ADR 0001 — Modular monolith, cài đặt trực tiếp (không Docker)

- Trạng thái: Chấp nhận
- Ngày: 16/10/2026

## Bối cảnh

Dự án do 1 developer (hoặc nhóm rất nhỏ) xây dựng và vận hành. Quy mô thí điểm khoảng 100 đoạn đường, dưới 500 người dùng đồng thời. Chủ dự án không muốn dùng Docker.

## Quyết định

- Backend là **một ứng dụng FastAPI** chia module theo thư mục (`api/`, `services/`, `models/`, `jobs/`), không tách microservice.
- PostgreSQL + PostGIS là nguồn sự thật duy nhất. Chưa dùng Redis hay hàng đợi tác vụ.
- **Dev (macOS):** PostgreSQL 17 + PostGIS cài bằng Homebrew, chạy ở cổng **5433** để không đụng tới PostgreSQL 16 (EDB) đang chạy ở cổng 5432 trên máy dev.
- **Prod:** VPS Ubuntu LTS, PostgreSQL/PostGIS từ apt PGDG, API chạy dưới systemd, Caddy làm reverse proxy + TLS. Deploy bằng script.

## Hệ quả

- Ít lớp trừu tượng, dễ debug.
- Phải tự giữ phiên bản dev và prod khớp nhau (PostgreSQL 17, PostGIS 3.x, Python 3.12). `/health/ready` trả về phiên bản PostGIS để kiểm tra.
- Khi cần nhiều instance API, phải thêm Redis (rate limit, pub/sub) và chuyển job ra worker riêng.
