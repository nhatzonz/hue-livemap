# HUE-LIVEMAP — AI

Chưa có mô hình nào ở giai đoạn MVP. Đây là chủ ý, không phải thiếu sót.

Mỗi module chỉ được bắt đầu khi đạt điều kiện dữ liệu, và chỉ vào production khi vượt baseline không dùng ML (PROJECT_PLAN.md mục 11):

| Module | Điều kiện bắt đầu |
|---|---|
| Hỗ trợ kiểm duyệt phản ánh | ≥ 1.000 phản ánh có nhãn, ≥ 100 bị bác bỏ |
| Ước lượng mức ngập từ ảnh | ≥ 500 ảnh ngập có nhãn, phủ ≥ 4 mức |
| Bất thường cảm biến/giao thông | IoT ≥ 2 tuần/cảm biến; GPS ≥ 8 tuần đủ mật độ |
| Dự báo ngập theo đoạn | ≥ 1 mùa mưa, ≥ 5 sự kiện mưa lớn, ≥ 30 đoạn có ≥ 3 lần ngập có nhãn |
