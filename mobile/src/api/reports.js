import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { authFetch } from './auth';
import { apiFetch, buildQuery } from './client';

export function useSnap(point) {
  return useQuery({
    queryKey: ['snap', point?.latitude?.toFixed(5), point?.longitude?.toFixed(5)],
    queryFn: () => apiFetch(`/api/v1/snap${buildQuery({ lat: point.latitude, lon: point.longitude })}`),
    enabled: Boolean(point),
  });
}

export function submitReport(body) {
  return authFetch('/api/v1/reports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function uploadReportPhoto(reportId, photo) {
  const form = new FormData();
  form.append('file', { uri: photo.uri, name: 'photo.jpg', type: 'image/jpeg' });
  return authFetch(`/api/v1/reports/${reportId}/media`, { method: 'PUT', body: form, timeoutMs: 60000 });
}

export function useMyReports() {
  return useQuery({
    queryKey: ['my-reports'],
    queryFn: () => authFetch('/api/v1/me/reports'),
  });
}

export function useConfirmSegment(code) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ dimension, stillPresent, location }) =>
      authFetch(`/api/v1/segments/${encodeURIComponent(code)}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dimension,
          still_present: stillPresent,
          lat: location?.latitude,
          lon: location?.longitude,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segment', code] });
      queryClient.invalidateQueries({ queryKey: ['segments'] });
    },
  });
}

export function useSegmentHistory(code, dimension) {
  return useQuery({
    queryKey: ['segment-history', code, dimension],
    queryFn: () =>
      apiFetch(`/api/v1/segments/${encodeURIComponent(code)}/history${buildQuery({ dimension, hours: 168 })}`),
    enabled: Boolean(code),
  });
}
