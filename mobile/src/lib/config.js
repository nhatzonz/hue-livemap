import Constants from 'expo-constants';

const API_PORT = 8000;

// Trên điện thoại thật, "localhost" là chính điện thoại chứ không phải máy dev.
// Thứ tự ưu tiên:
//   1. EXPO_PUBLIC_API_URL trong mobile/.env (staging/prod, hoặc khi cần ghi đè)
//   2. Ở chế độ dev: lấy IP LAN của máy chạy Metro từ hostUri ("192.168.1.5:8081")
//      → http://192.168.1.5:8000, để điện thoại cùng Wi-Fi gọi được backend.
function resolveApiUrl() {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  if (fromEnv) return fromEnv.replace(/\/+$/, '');

  const hostUri = Constants.expoConfig?.hostUri;
  if (__DEV__ && hostUri) {
    const host = hostUri.split(':')[0];
    return `http://${host}:${API_PORT}`;
  }
  return `http://localhost:${API_PORT}`;
}

export const API_URL = resolveApiUrl();
