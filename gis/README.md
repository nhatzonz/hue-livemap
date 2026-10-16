# HUE-LIVEMAP — GIS pipeline

Chuẩn bị mạng lưới đoạn đường cho vùng thí điểm (PROJECT_PLAN.md mục 3.3, 3.4, 10.1).

```bash
cd gis && uv sync
uv run python scripts/fetch_pilot_boundary.py   # ranh giới thí điểm từ OSM (Kinh thành + 300 m)
uv run python scripts/fetch_osm.py              # tải đường OSM bao ranh giới (kèm ID node)
uv run python scripts/build_segments.py         # cắt đoạn → data/curated/segments_candidates.geojson
uv run python scripts/qa_checks.py              # kiểm tra; exit 1 nếu có lỗi chặn
uv run python scripts/import_segments.py        # nhập DB (mặc định tầng 1 + 3); --dry-run để thử
uv run pytest
```

`import_segments.py` từ chối chạy nếu QA chưa chạy hoặc còn lỗi. Có thể chạy lại nhiều lần: đoạn cũ được khớp theo `source_ref` nên **giữ nguyên mã `HUE-KT-xxxx`**.

## Quy tắc cắt đoạn

| Tầng (`pilot_tier`) | Gồm | Cắt tại |
|---|---|---|
| 1 Trục chính | primary/secondary/tertiary có tên | giao lộ với trục chính khác |
| 2 Đường dân sinh | residential/unclassified/living_street có tên | giao lộ với đường tầng 1–2 |
| 3 Kiệt/hẻm | tên bắt đầu Kiệt/Hẻm/Ngõ, hoặc `service=alley` có tên | mọi giao cắt |

Thêm: ghép các way OSM nối tiếp cùng tên; cắt theo ranh giới; đoạn > 400 m chia đều; bỏ đoạn nối ngang dải phân cách (< 30 m, hai đầu cùng một đường). Đường đôi (Lê Duẩn, Trần Hưng Đạo…) giữ thành hai đoạn theo hai chiều.

## Kết quả hiện tại (16/10/2026)

- Ranh giới **bản nháp**: Kinh thành 5,16 km² + đệm 300 m = **8,49 km²**. Chờ xác nhận D1.
- Đường có tên trong ranh giới: 39,7 km trục chính, 44,8 km dân sinh, 4,4 km kiệt có tên.
- Ứng viên: **579 đoạn**, gồm 175 trục chính (TB 227 m), 357 dân sinh, 47 kiệt. QA: 0 lỗi, 63 cảnh báo.
- Đã nhập DB: **222 đoạn** (tầng 1 + 3), `verification_status = draft`.
- OSM có khoảng 729 kiệt/hẻm trong khung tải nhưng chỉ khoảng 75 có tên. **Kiệt không tên chưa vào dữ liệu**; khảo sát thực địa phải định danh.

> Con số 222 đoạn lớn hơn nhiều so với mục tiêu ~100 đoạn khảo sát đợt đầu trong kế hoạch. Việc chọn tập khảo sát ưu tiên là quyết định cần chốt (xem báo cáo giai đoạn).

## Dữ liệu và giấy phép

| Thư mục | Nội dung | Lưu trữ |
|---|---|---|
| `data/raw/` | Dữ liệu tải về (OSM…) | Không cần lưu (tải lại được) |
| `data/curated/` | Ranh giới, đoạn ứng viên, báo cáo QA | Lưu cùng mã nguồn |
| `data/demo/` | Dữ liệu **minh hoạ**, luôn gắn `is_demo=true` | Lưu cùng mã nguồn |

Dữ liệu OSM theo **ODbL 1.0**, © OpenStreetMap contributors. CSDL dẫn xuất công bố công khai phải chia sẻ theo ODbL và ghi công.
