import { useRouter } from 'expo-router';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { useConfirmSegment } from '../../api/reports';
import { useSegment } from '../../api/segments';
import StatusBadge from '../../components/StatusBadge';
import { DIMENSIONS, LEVEL_LABELS, SEGMENT_TYPE_LABELS } from '../../constants/status';
import { formatLength } from '../../lib/format';
import { colors } from '../../theme/colors';

const GONE_LABELS = { flood: 'Đã hết ngập', obstacle: 'Đã thông', traffic: 'Đã thông thoáng' };

// "Vẫn còn / Đã hết" cho lớp đang xem: cách rẻ nhất để giữ dữ liệu tươi (PROJECT_PLAN.md M5)
function QuickConfirm({ code, dimension, status }) {
  const confirm = useConfirmSegment(code);
  const normalLevel = Object.keys(LEVEL_LABELS[dimension])[0];
  if (!status || status.state === 'NO_DATA' || status.level === normalLevel) return null;

  if (confirm.isSuccess) return <Text style={styles.thanks}>Cảm ơn bạn đã cập nhật.</Text>;
  return (
    <View>
      <View style={styles.confirmRow}>
        <Pressable
          style={[styles.confirmButton, confirm.isPending && styles.dim]}
          disabled={confirm.isPending}
          onPress={() => confirm.mutate({ dimension, stillPresent: true })}
        >
          <Text style={styles.confirmText}>Vẫn còn</Text>
        </Pressable>
        <Pressable
          style={[styles.confirmButton, confirm.isPending && styles.dim]}
          disabled={confirm.isPending}
          onPress={() => confirm.mutate({ dimension, stillPresent: false })}
        >
          <Text style={styles.confirmText}>{GONE_LABELS[dimension]}</Text>
        </Pressable>
      </View>
      {confirm.error && <Text style={styles.error}>{confirm.error.message}</Text>}
    </View>
  );
}

// Panel nửa dưới màn hình khi chạm vào một đoạn (PROJECT_PLAN.md mục 5.3).
// Tự viết thay vì dùng thư viện bottom sheet để chạy được ngay trong Expo Go, không thêm native module.
export default function SegmentSheet({ code, dimension, onClose }) {
  const router = useRouter();
  const { data, isPending, error } = useSegment(code);

  return (
    <View style={styles.sheet}>
      <View style={styles.header}>
        <View style={styles.titleBox}>
          <Text style={styles.title} numberOfLines={2}>
            {data?.name ?? code}
          </Text>
          {data && (
            <Text style={styles.subtitle}>
              {SEGMENT_TYPE_LABELS[data.segment_type]} · {formatLength(data.length_m)} · {data.code}
            </Text>
          )}
        </View>
        <Pressable onPress={onClose} hitSlop={12} accessibilityRole="button" accessibilityLabel="Đóng">
          <Text style={styles.close}>✕</Text>
        </Pressable>
      </View>

      {isPending && <ActivityIndicator style={styles.loading} />}
      {error && <Text style={styles.error}>{error.message}</Text>}
      {data && (
        <>
          {data.is_demo && <Text style={styles.demo}>DỮ LIỆU MINH HOẠ, không phải dữ liệu thật</Text>}
          {data.verification_status !== 'field_verified' && (
            <Text style={styles.draft}>Đoạn nháp từ OpenStreetMap, chưa khảo sát thực địa</Text>
          )}
          <View style={styles.statuses}>
            {DIMENSIONS.map(({ key, label }) => (
              <StatusBadge
                key={key}
                dimension={key}
                label={label}
                status={data.status[key]}
                segmentType={data.segment_type}
              />
            ))}
          </View>
          <QuickConfirm code={data.code} dimension={dimension} status={data.status[dimension]} />
          <Pressable
            style={styles.link}
            onPress={() => router.push(`/segment/${encodeURIComponent(data.code)}`)}
            accessibilityRole="button"
          >
            <Text style={styles.linkText}>Xem chi tiết ›</Text>
          </Pressable>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: 16,
    paddingBottom: 8,
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: -2 },
    elevation: 10,
  },
  header: { flexDirection: 'row', alignItems: 'flex-start' },
  titleBox: { flex: 1, paddingRight: 12 },
  title: { fontSize: 17, fontWeight: '700', color: colors.text },
  subtitle: { marginTop: 2, fontSize: 13, color: colors.textMuted },
  close: { fontSize: 18, color: colors.textMuted },
  loading: { marginVertical: 16 },
  error: { marginTop: 12, color: colors.danger },
  demo: { marginTop: 8, fontSize: 12, fontWeight: '700', color: colors.danger },
  draft: { marginTop: 8, fontSize: 12, color: colors.warn },
  statuses: { marginTop: 8 },
  link: { marginTop: 6, paddingVertical: 8 },
  linkText: { fontSize: 15, fontWeight: '600', color: colors.primary },
  confirmRow: { flexDirection: 'row', gap: 10, marginTop: 8 },
  confirmButton: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.primary,
  },
  confirmText: { color: colors.primary, fontWeight: '600', fontSize: 15 },
  dim: { opacity: 0.5 },
  thanks: { marginTop: 8, color: colors.ok, fontSize: 14 },
});
