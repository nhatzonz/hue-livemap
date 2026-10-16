// Nhãn tiếng Việt cho chiều trạng thái, mức độ và trạng thái nhận thức (PROJECT_PLAN.md mục 6).

export const DIMENSIONS = [
  { key: 'flood', label: 'Ngập' },
  { key: 'obstacle', label: 'Sự cố' },
  { key: 'traffic', label: 'Giao thông' },
];

export const LEVEL_LABELS = {
  flood: {
    dry: 'Không ngập',
    puddle: 'Đọng nước',
    ankle: 'Ngập mắt cá',
    calf: 'Ngập bắp chân',
    knee: 'Ngập đầu gối',
    above_knee: 'Ngập trên đầu gối',
  },
  obstacle: {
    none: 'Không có vật cản',
    partial: 'Chắn một phần',
    blocked: 'Chắn hoàn toàn',
  },
  traffic: {
    free: 'Thông thoáng',
    slow: 'Chậm',
    congested: 'Ùn tắc',
    standstill: 'Đứng yên',
  },
};

export const STATE_LABELS = {
  NO_DATA: 'Chưa có dữ liệu',
  STALE: 'Dữ liệu cũ',
  UNVERIFIED: 'Chưa xác minh',
  CONFIRMED: 'Đã xác nhận',
  CONFLICTING: 'Thông tin trái chiều',
};

export const SEGMENT_TYPE_LABELS = {
  street: 'Đường',
  kiet: 'Kiệt',
  hem: 'Hẻm',
  bridge: 'Cầu',
  other: 'Khác',
};

export const VERIFICATION_LABELS = {
  draft: 'Nháp từ OpenStreetMap, chưa khảo sát thực địa',
  desk_reviewed: 'Đã rà soát trên bản đồ, chưa khảo sát thực địa',
  field_verified: 'Đã khảo sát thực địa',
};

export function levelLabel(dimension, level) {
  return LEVEL_LABELS[dimension]?.[level] ?? level ?? '';
}

// Câu mô tả ngắn cho một trạng thái, ví dụ "Ngập bắp chân · Chưa xác minh".
export function describeStatus(dimension, status) {
  if (!status || status.state === 'NO_DATA') return STATE_LABELS.NO_DATA;
  if (status.state === 'CONFLICTING') return STATE_LABELS.CONFLICTING;
  return `${levelLabel(dimension, status.level)} · ${STATE_LABELS[status.state]}`;
}

export const SOURCE_LABELS = {
  citizen_report: 'Phản ánh người dùng',
  quick_confirm: 'Xác nhận nhanh',
  moderator: 'Ban kiểm duyệt',
  iot_trusted: 'Cảm biến',
  iot_testing: 'Cảm biến (thử nghiệm)',
  gps_agg: 'Dữ liệu di chuyển',
  official: 'Cơ quan chức năng',
};

export const REPORT_STATUS_LABELS = {
  pending: 'Chờ xác minh',
  accepted: 'Đã xác nhận',
  rejected: 'Bị bác bỏ',
  duplicate: 'Trùng lặp',
  expired: 'Hết hiệu lực',
};
