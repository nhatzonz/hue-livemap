import { useQuery } from '@tanstack/react-query';

import { apiFetch } from './client';

export function useBackendHealth() {
  return useQuery({
    queryKey: ['health', 'ready'],
    queryFn: () => apiFetch('/health/ready', { timeoutMs: 5000 }),
    refetchInterval: 30000,
    retry: 1,
  });
}
