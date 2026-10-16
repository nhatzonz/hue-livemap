# HUE-LIVEMAP — Mobile (Expo)

Ứng dụng React Native + Expo, viết bằng JavaScript, điều hướng bằng Expo Router.

| Thành phần | Phiên bản (ghi lại ngày 16/10/2026) |
|---|---|
| Expo SDK | 58 (`expo ~58.0.12`) |
| React Native | 0.88.0 |
| React | 19.3.0 |
| expo-router | ~58.0.21 |
| react-native-maps | 1.29.11 |
| expo-location | ~58.0.16 |
| @tanstack/react-query, zustand | xem package.json |
| react-dom | 19.3.0 (chỉ để thoả peer dependency của expo-router; không dùng trên native) |

> Luôn thêm gói bằng `npx expo install <gói>` (không dùng `npm install` trực tiếp) để Expo chọn phiên bản tương thích SDK. Sau đó chạy `npm run doctor` và `npm run lint`.
>
> Ứng dụng không nhắm tới web (react-native-maps không hỗ trợ web).

## Chạy trên điện thoại thật (Expo Go)

1. Cài **Expo Go** từ App Store / Google Play. Expo Go trên store chỉ hỗ trợ SDK mới nhất (hiện là 58).
2. Điện thoại và máy dev **cùng mạng Wi-Fi**.
3. Chạy backend (xem `../backend/README.md`), backend phải lắng nghe ở `0.0.0.0:8000`.
4. Trong thư mục `mobile/`:
   ```bash
   npm install
   npm start
   ```
5. Quét mã QR: dùng Camera trên iPhone hoặc ứng dụng Expo Go trên Android.

App tự suy ra địa chỉ backend từ IP LAN của máy chạy Metro (`http://<ip-máy-dev>:8000`). Ở bản dev, ô trạng thái trên bản đồ cho biết có gọi được backend không:

- 🟢 `Máy chủ OK · PostGIS 3.x`: thông suốt
- 🔴 `Không kết nối được máy chủ · http://…`: xem phần xử lý sự cố bên dưới

### Xử lý sự cố kết nối

- **macOS Firewall** chặn cổng 8000: System Settings → Network → Firewall → cho phép Python/uvicorn nhận kết nối đến.
- Wi-Fi công cộng hoặc mạng công ty có thể chặn kết nối giữa các thiết bị (client isolation). Khi đó dùng `npm start -- --tunnel` cho Metro, và đặt `EXPO_PUBLIC_API_URL` trỏ tới một tunnel cho backend.
- Máy có nhiều card mạng nên IP tự dò bị sai: tạo `mobile/.env` với `EXPO_PUBLIC_API_URL=http://<ip-đúng>:8000`, rồi chạy `npm start -- --clear`.

## Chạy trên iOS Simulator (cần Xcode)

```bash
npm start -- --ios        # tự cài Expo Go đúng phiên bản vào simulator
xcrun simctl openurl booted "exp://<ip>:8081/--/segment/HUE-KT-0148"   # mở thẳng một màn hình
```

## Cấu trúc

```
src/
├── app/            # routes (Expo Router): index (bản đồ), search, segment/[code], about
├── api/            # fetch client (ETag), hook react-query
├── features/map/   # MapScreen, lớp đoạn, ranh giới, chú giải, panel chi tiết
├── components/     # StatusBadge…
├── constants/      # nhãn tiếng Việt cho trạng thái
├── lib/            # config (dò IP LAN), geo (chạm chọn đoạn), format
├── store/          # zustand
└── theme/          # màu + mã hoá trạng thái (PROJECT_PLAN.md 6.4)
```

Chạm chọn đoạn: app tìm đoạn gần điểm chạm nhất trong ngưỡng khoảng 24 px (quy ra mét theo mức zoom), thay vì dựa vào `onPress` của từng Polyline, vốn khó chạm với nét mảnh và khác nhau giữa iOS và Android.

## Development build (từ tuần 8)

Push notification trên Android và các thư viện native ngoài Expo Go cần development build:

```bash
npx eas-cli@latest build --profile development --platform android
```

Google Maps trên Android build cần `GOOGLE_MAPS_ANDROID_API_KEY` (xem `.env.example`). Expo Go không cần key này.
