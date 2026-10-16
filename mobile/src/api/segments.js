import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { apiFetch, buildQuery } from './client';

const REGION_ID = 'hue';

export function useRegion() {
  return useQuery({
    queryKey: ['region', REGION_ID],
    queryFn: () => apiFetch(`/api/v1/regions/${REGION_ID}`),
    staleTime: 60 * 60 * 1000,
  });
}

// Toàn bộ đoạn trong vùng thí điểm (khoảng vài trăm đoạn, ~13 KB nén) cho một chiều trạng thái.
// Polling 60 s khi app mở; ETag giúp lần gọi không đổi chỉ tốn vài trăm byte.
export function useSegments(dimension, bbox) {
  return useQuery({
    queryKey: ['segments', dimension, bbox?.join(',')],
    queryFn: () => apiFetch(`/api/v1/segments${buildQuery({ dimension, bbox: bbox?.join(',') })}`, { useEtag: true }),
    enabled: Boolean(bbox),
    refetchInterval: 60000,
    placeholderData: keepPreviousData,
  });
}

export function useSegment(code) {
  return useQuery({
    queryKey: ['segment', code],
    queryFn: () => apiFetch(`/api/v1/segments/${encodeURIComponent(code)}`),
    enabled: Boolean(code),
  });
}

export function useSegmentSearch(query) {
  const q = query.trim();
  return useQuery({
    queryKey: ['search', q],
    queryFn: () => apiFetch(`/api/v1/search${buildQuery({ q, limit: 20 })}`),
    enabled: q.length >= 2,
    placeholderData: keepPreviousData,
  });
}
