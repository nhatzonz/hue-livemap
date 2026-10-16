import { create } from 'zustand';

// Trạng thái bản đồ dùng chung giữa các màn hình (vd. màn tìm kiếm yêu cầu bản đồ zoom tới một đoạn).
export const useMapStore = create((set) => ({
  dimension: 'flood',
  selectedCode: null,
  // { code, bbox } do màn tìm kiếm đặt; MapScreen xử lý rồi xoá
  focusRequest: null,

  setDimension: (dimension) => set({ dimension }),
  select: (code) => set({ selectedCode: code }),
  requestFocus: (code, bbox) => set({ focusRequest: { code, bbox }, selectedCode: code }),
  clearFocusRequest: () => set({ focusRequest: null }),
}));
