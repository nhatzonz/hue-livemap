// Cấu hình Expo động để đọc biến môi trường (API key, bundle id) thay vì ghi cứng.
// Biến EXPO_PUBLIC_* được nhúng vào bundle JS; biến không có tiền tố chỉ dùng lúc build.

const IS_DEV = process.env.APP_VARIANT !== 'production';

module.exports = {
  expo: {
    name: IS_DEV ? 'HUE-LIVEMAP (dev)' : 'HUE-LIVEMAP',
    slug: 'hue-livemap',
    scheme: 'huelivemap',
    version: '0.1.0',
    orientation: 'portrait',
    icon: './assets/icon.png',
    userInterfaceStyle: 'light',
    ios: {
      supportsTablet: false,
      // Tạm thời; chốt khi đăng ký Apple Developer (PROJECT_PLAN.md, D9/D12)
      bundleIdentifier: 'com.huelivemap.app',
    },
    android: {
      package: 'com.huelivemap.app',
      adaptiveIcon: {
        backgroundColor: '#E6F4FE',
        foregroundImage: './assets/android-icon-foreground.png',
        backgroundImage: './assets/android-icon-background.png',
        monochromeImage: './assets/android-icon-monochrome.png',
      },
    },
    web: {
      favicon: './assets/favicon.png',
    },
    plugins: [
      'expo-router',
      [
        'expo-location',
        {
          locationWhenInUsePermission:
            'HUE-LIVEMAP dùng vị trí để hiển thị các đoạn đường gần bạn và gắn phản ánh vào đúng đoạn đường.',
        },
      ],
      [
        'expo-image-picker',
        {
          cameraPermission: 'HUE-LIVEMAP dùng camera để bạn chụp ảnh hiện trường khi gửi phản ánh.',
          microphonePermission: false,
        },
      ],
      [
        'react-native-maps',
        {
          // Chỉ cần cho bản build (dev build / store). Expo Go không cần.
          androidGoogleMapsApiKey: process.env.GOOGLE_MAPS_ANDROID_API_KEY,
        },
      ],
    ],
  },
};
