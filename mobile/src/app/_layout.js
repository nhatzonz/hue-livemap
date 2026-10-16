import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { AppState } from 'react-native';

import { colors } from '../theme/colors';

// React Query không tự biết app RN vào nền: báo cho nó qua AppState để dừng polling khi app ở nền
// (tiết kiệm pin/dữ liệu) và tải lại ngay khi người dùng mở lại app.
function useAppStateFocus() {
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => focusManager.setFocused(state === 'active'));
    return () => subscription.remove();
  }, []);
}

export default function RootLayout() {
  const [queryClient] = useState(() => new QueryClient());
  useAppStateFocus();

  return (
    <QueryClientProvider client={queryClient}>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerTintColor: colors.primary,
          headerTitleStyle: { color: colors.text },
          headerBackTitle: 'Quay lại',
        }}
      >
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="search" options={{ title: 'Tìm đường, kiệt' }} />
        <Stack.Screen name="segment/[code]" options={{ title: 'Chi tiết đoạn' }} />
        <Stack.Screen name="about" options={{ title: 'Giới thiệu' }} />
        <Stack.Screen name="report/new" options={{ title: 'Gửi phản ánh', gestureEnabled: false }} />
        <Stack.Screen name="my-reports" options={{ title: 'Phản ánh của tôi' }} />
      </Stack>
    </QueryClientProvider>
  );
}
