import Constants from 'expo-constants';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import { ApiError, apiFetch } from './client';

// Thiết bị ẩn danh: UUID sinh một lần, lưu SecureStore. Không cần tài khoản (PROJECT_PLAN.md mục 9.3).
const DEVICE_ID_KEY = 'hue_livemap.device_id';
const REFRESH_KEY = 'hue_livemap.refresh_token';

let session = null; // { accessToken, expiresAt }
let pending = null; // gộp các lần đăng nhập đồng thời

export async function getDeviceId() {
  let id = await SecureStore.getItemAsync(DEVICE_ID_KEY);
  if (!id) {
    id = Crypto.randomUUID();
    await SecureStore.setItemAsync(DEVICE_ID_KEY, id);
  }
  return id;
}

async function storeTokens(tokens) {
  await SecureStore.setItemAsync(REFRESH_KEY, tokens.refresh_token);
  session = {
    accessToken: tokens.access_token,
    // làm mới sớm 60 s để tránh token hết hạn giữa chừng
    expiresAt: Date.now() + (tokens.expires_in - 60) * 1000,
  };
  return session;
}

async function login() {
  const refreshToken = await SecureStore.getItemAsync(REFRESH_KEY);
  if (refreshToken) {
    try {
      const tokens = await apiFetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      return storeTokens(tokens);
    } catch (err) {
      // Chỉ đăng ký lại khi refresh token thật sự không còn hiệu lực; lỗi mạng/429/5xx thì báo lỗi,
      // tránh tạo phiên mới (và thu hồi phiên cũ) mỗi khi máy chủ tạm lỗi.
      if (err.status !== 401) throw err;
    }
  }
  const tokens = await apiFetch('/api/v1/auth/device', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      device_id: await getDeviceId(),
      platform: Platform.OS,
      app_version: Constants.expoConfig?.version,
    }),
  });
  return storeTokens(tokens);
}

async function ensureSession(force = false) {
  if (!force && session && session.expiresAt > Date.now()) return session;
  if (!pending) {
    pending = login().finally(() => {
      pending = null;
    });
  }
  return pending;
}

// Gọi API cần đăng nhập; tự đăng nhập lại và thử lại một lần khi token hết hạn.
export async function authFetch(path, options = {}) {
  const attempt = async (force) => {
    const { accessToken } = await ensureSession(force);
    return apiFetch(path, {
      ...options,
      headers: { ...options.headers, Authorization: `Bearer ${accessToken}` },
    });
  };
  try {
    return await attempt(false);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return attempt(true);
    throw err;
  }
}
