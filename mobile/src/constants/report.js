// Loại phản ánh và mức độ cho luồng gửi phản ánh (PROJECT_PLAN.md mục 5.4).
// category/dimension phải khớp app/models/reports.py (CATEGORIES) ở backend.

export const REPORT_TYPES = [
  { key: 'flood', icon: '💧', label: 'Ngập', dimension: 'flood', category: 'flood' },
  { key: 'tree_fall', icon: '🌳', label: 'Cây đổ / vật cản', dimension: 'obstacle', category: 'tree_fall' },
  { key: 'construction', icon: '🚧', label: 'Thi công / cấm đường', dimension: 'obstacle', category: 'construction' },
  { key: 'accident', icon: '🚨', label: 'Tai nạn', dimension: 'obstacle', category: 'accident' },
  { key: 'power_line', icon: '⚡', label: 'Nguy hiểm (dây điện…)', dimension: 'obstacle', category: 'power_line' },
  { key: 'congestion', icon: '🚦', label: 'Ùn tắc', dimension: 'traffic', category: 'congestion' },
  { key: 'other', icon: '❓', label: 'Khác', dimension: 'obstacle', category: 'other' },
];

// Chỉ các mức "có vấn đề". Báo "đã hết" dùng nút xác nhận nhanh trên đoạn đường.
export const REPORT_LEVELS = {
  flood: [
    { level: 'puddle', label: 'Đọng nước', hint: 'Mặt đường ướt, vũng nước nhỏ' },
    { level: 'ankle', label: 'Mắt cá chân', hint: 'Khoảng 10–20 cm, xe máy vẫn đi được' },
    { level: 'calf', label: 'Bắp chân', hint: 'Khoảng 20–35 cm, xe máy dễ chết máy' },
    { level: 'knee', label: 'Đầu gối', hint: 'Khoảng 35–50 cm, không nên đi xe máy' },
    { level: 'above_knee', label: 'Trên đầu gối', hint: 'Trên 50 cm, nguy hiểm' },
  ],
  obstacle: [
    { level: 'partial', label: 'Chắn một phần', hint: 'Vẫn đi qua được nhưng phải cẩn thận' },
    { level: 'blocked', label: 'Chắn hoàn toàn', hint: 'Không đi qua được' },
  ],
  traffic: [
    { level: 'slow', label: 'Chậm', hint: 'Đi chậm hơn bình thường' },
    { level: 'congested', label: 'Ùn tắc', hint: 'Dừng đi liên tục' },
    { level: 'standstill', label: 'Đứng yên', hint: 'Gần như không di chuyển' },
  ],
};

export const EMERGENCY_NUMBERS = [
  ['112', 'Tìm kiếm cứu nạn'],
  ['114', 'Cứu hoả, cứu nạn'],
  ['115', 'Cấp cứu'],
  ['113', 'Công an'],
];

export const MAX_GPS_ACCURACY_M = 50;
export const DESCRIPTION_MAX = 280;
