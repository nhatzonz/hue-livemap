// Mã hoá trực quan trạng thái đoạn đường (PROJECT_PLAN.md mục 6.4):
//   màu        = mức độ (level)
//   kiểu nét   = độ chắc chắn: liền = đã xác nhận, đứt = chưa xác minh, chấm xám = chưa có dữ liệu
//   độ mờ      = độ tươi: dữ liệu cũ (STALE) hiển thị mờ
//   độ dày     = cố định theo loại đoạn (đường chính dày hơn kiệt), KHÔNG mã hoá trạng thái

export const LEVEL_COLORS = {
  flood: {
    dry: '#2E9E5B',
    puddle: '#8EC9F2',
    ankle: '#4FA3E0',
    calf: '#1F6FC5',
    knee: '#203F9A',
    above_knee: '#5B1A8C',
  },
  obstacle: {
    none: '#2E9E5B',
    partial: '#F29D38',
    blocked: '#D93025',
  },
  traffic: {
    free: '#2E9E5B',
    slow: '#F2C94C',
    congested: '#F2994A',
    standstill: '#C0392B',
  },
};

export const NO_DATA_COLOR = '#7D8590';
export const CONFLICT_COLOR = '#8E24AA';

const DASH = {
  CONFIRMED: undefined,
  UNVERIFIED: [10, 6],
  STALE: [10, 6],
  CONFLICTING: [4, 4],
  NO_DATA: [2, 6],
};

function withAlpha(hex, alpha) {
  const a = Math.round(alpha * 255)
    .toString(16)
    .padStart(2, '0');
  return `${hex}${a}`;
}

export function segmentStyle(dimension, segmentType, status) {
  const state = status?.state ?? 'NO_DATA';
  const baseWidth = segmentType === 'kiet' || segmentType === 'hem' ? 3.5 : 5;

  if (state === 'NO_DATA') {
    return { strokeColor: withAlpha(NO_DATA_COLOR, 0.8), strokeWidth: 2, lineDashPattern: DASH.NO_DATA };
  }
  if (state === 'CONFLICTING') {
    return { strokeColor: CONFLICT_COLOR, strokeWidth: baseWidth, lineDashPattern: DASH.CONFLICTING };
  }
  const color = LEVEL_COLORS[dimension]?.[status.level] ?? NO_DATA_COLOR;
  return {
    strokeColor: state === 'STALE' ? withAlpha(color, 0.4) : color,
    strokeWidth: baseWidth,
    lineDashPattern: DASH[state],
  };
}
