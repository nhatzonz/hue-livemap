import { API_URL } from '../lib/config';

const DEFAULT_TIMEOUT_MS = 10000;

// Cache ETag theo URL: gửi If-None-Match, nhận 304 thì dùng lại body cũ (tiết kiệm dữ liệu di động).
const etagCache = new Map();

export class ApiError extends Error {
  constructor(message, { status, code, details } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function buildQuery(params) {
  const entries = Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== null && v !== '');
  if (entries.length === 0) return '';
  return `?${entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&')}`;
}

// fetch có timeout và chuẩn hoá lỗi theo định dạng { error: { code, message, details } } của backend.
export async function apiFetch(path, { timeoutMs = DEFAULT_TIMEOUT_MS, useEtag = false, ...options } = {}) {
  const url = `${API_URL}${path}`;
  const cached = useEtag ? etagCache.get(url) : undefined;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        Accept: 'application/json',
        ...(cached ? { 'If-None-Match': cached.etag } : {}),
        ...options.headers,
      },
      signal: controller.signal,
    });
  } catch (err) {
    const message = err.name === 'AbortError' ? 'Hết thời gian chờ máy chủ' : 'Không kết nối được máy chủ';
    throw new ApiError(message, { code: 'NETWORK_ERROR' });
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 304 && cached) return cached.body;

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error ?? {};
    throw new ApiError(error.message ?? `Lỗi máy chủ (${response.status})`, {
      status: response.status,
      code: error.code,
      details: error.details,
    });
  }
  const etag = response.headers.get('etag');
  if (useEtag && etag) etagCache.set(url, { etag, body });
  return body;
}
