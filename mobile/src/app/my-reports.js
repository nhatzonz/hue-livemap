import { useRouter } from 'expo-router';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';

import { useMyReports } from '../api/reports';
import { REPORT_TYPES } from '../constants/report';
import { levelLabel, REPORT_STATUS_LABELS } from '../constants/status';
import { timeAgo } from '../lib/format';
import { colors } from '../theme/colors';

const TYPE_BY_CATEGORY = Object.fromEntries(REPORT_TYPES.map((t) => [t.category, t]));

export default function MyReportsScreen() {
  const router = useRouter();
  const { data, isPending, error, refetch, isRefetching } = useMyReports();

  if (isPending) return <ActivityIndicator style={styles.center} />;
  if (error) return <Text style={[styles.center, styles.error]}>{error.message}</Text>;

  return (
    <FlatList
      style={styles.container}
      data={data.reports}
      keyExtractor={(r) => r.id}
      onRefresh={refetch}
      refreshing={isRefetching}
      ListEmptyComponent={<Text style={styles.empty}>Bạn chưa gửi phản ánh nào.</Text>}
      renderItem={({ item }) => {
        const type = TYPE_BY_CATEGORY[item.category];
        return (
          <Pressable
            style={styles.item}
            disabled={!item.segment}
            onPress={() => router.push(`/segment/${encodeURIComponent(item.segment.code)}`)}
          >
            <Text style={styles.title}>
              {type?.icon} {type?.label} · {levelLabel(item.dimension, item.level)}
            </Text>
            <Text style={styles.meta}>{item.segment ? item.segment.name : 'Không gắn đoạn (theo vị trí)'}</Text>
            <View style={styles.footer}>
              <Text style={styles.status}>{REPORT_STATUS_LABELS[item.status] ?? item.status}</Text>
              <Text style={styles.meta}>
                {timeAgo(item.created_at)}
                {item.photo_count ? ` · ${item.photo_count} ảnh` : ''}
              </Text>
            </View>
          </Pressable>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  center: { marginTop: 40, textAlign: 'center' },
  error: { color: colors.danger },
  empty: { padding: 24, textAlign: 'center', color: colors.textMuted },
  item: { padding: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  title: { fontSize: 15, fontWeight: '600', color: colors.text },
  meta: { marginTop: 2, fontSize: 13, color: colors.textMuted },
  footer: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6 },
  status: { fontSize: 13, fontWeight: '600', color: colors.warn },
});
