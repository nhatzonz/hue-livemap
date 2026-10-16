import * as Location from 'expo-location';
import { useCallback, useEffect, useState } from 'react';

// Chỉ xin quyền vị trí khi ứng dụng đang mở (foreground). MVP không dùng vị trí nền.
// accuracy: Balanced (~100 m trên iOS) đủ để căn bản đồ; gửi phản ánh cần High vì bán kính gắn đoạn là 30 m.
export function useForegroundLocation(accuracy = Location.Accuracy.Balanced) {
  const [permission, setPermission] = useState('undetermined'); // 'granted' | 'denied' | 'undetermined'

  useEffect(() => {
    Location.getForegroundPermissionsAsync().then(({ status }) => setPermission(status));
  }, []);

  const request = useCallback(async () => {
    const { status } = await Location.requestForegroundPermissionsAsync();
    setPermission(status);
    return status === 'granted';
  }, []);

  const getCurrent = useCallback(async () => {
    const granted = permission === 'granted' || (await request());
    if (!granted) return null;
    const position = await Location.getCurrentPositionAsync({ accuracy });
    return position.coords;
  }, [permission, request, accuracy]);

  return { permission, request, getCurrent };
}
