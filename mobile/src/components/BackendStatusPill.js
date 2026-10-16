import { StyleSheet, Text, View } from 'react-native';

import { useBackendHealth } from '../api/health';
import { API_URL } from '../lib/config';
import { colors } from '../theme/colors';

// Chỉ hiển thị ở bản dev: giúp kiểm tra nhanh điện thoại có gọi được backend qua LAN không.
export default function BackendStatusPill() {
  const { data, error, isPending } = useBackendHealth();

  let color = colors.noData;
  let label = 'Đang kiểm tra máy chủ…';
  if (data) {
    color = colors.ok;
    label = `Máy chủ OK · PostGIS ${data.postgis_version ?? '?'}`;
  } else if (error && !isPending) {
    color = colors.danger;
    label = `${error.message} · ${API_URL}`;
  }

  return (
    <View style={styles.pill}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={styles.text} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    maxWidth: '100%',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  text: { fontSize: 12, color: colors.text, flexShrink: 1 },
});
