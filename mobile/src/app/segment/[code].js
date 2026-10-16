import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';

import { useSegmentHistory } from '../../api/reports';
import { useSegment } from '../../api/segments';
import StatusBadge from '../../components/StatusBadge';
import {
  DIMENSIONS,
  levelLabel,
  SEGMENT_TYPE_LABELS,
  SOURCE_LABELS,
  STATE_LABELS,
  VERIFICATION_LABELS,
} from '../../constants/status';
import LayerChips from '../../features/map/LayerChips';
import { formatLength, timeAgo } from '../../lib/format';
import { colors } from '../../theme/colors';

const WIDTH_LABELS = { '<2': 'dưới 2 m', '2-4': '2–4 m', '4-7': '4–7 m', '>7': 'trên 7 m' };
const FLOOD_PRONE_LABELS = { unknown: 'Chưa rõ', low: 'Thấp', medium: 'Trung bình', high: 'Cao' };

function Row({ label, value }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value ?? 'Chưa có thông tin'}</Text>
    </View>
  );
}

const TIME_FORMAT = { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' };

function History({ code }) {
  const [dimension, setDimension] = useState('flood');
  const { data, isPending } = useSegmentHistory(code, dimension);
  const entries = data?.entries ?? [];
  return (
    <View>
      <LayerChips value={dimension} onChange={setDimension} />
      {isPending && <ActivityIndicator style={styles.gap} />}
      {!isPending && entries.length === 0 && (
        <Text style={styles.note}>Chưa có thay đổi trạng thái nào trong 7 ngày qua.</Text>
      )}
      {entries.map((e) => (
        <View key={e.valid_from} style={styles.row}>
          <Text style={styles.rowLabel}>
            {new Date(e.valid_from).toLocaleString('vi-VN', TIME_FORMAT)}
            {e.valid_to ? ` → ${new Date(e.valid_to).toLocaleString('vi-VN', TIME_FORMAT)}` : ' → nay'}
          </Text>
          <Text style={styles.rowValue}>
            {e.state === 'NO_DATA' ? STATE_LABELS.NO_DATA : `${levelLabel(dimension, e.level)} · ${STATE_LABELS[e.state]}`}
          </Text>
        </View>
      ))}
    </View>
  );
}

export default function SegmentDetailScreen() {
  const { code } = useLocalSearchParams();
  const { data, isPending, error } = useSegment(code);

  if (isPending) return <ActivityIndicator style={styles.center} />;
  if (error) return <Text style={[styles.center, styles.error]}>{error.message}</Text>;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{data.name}</Text>
      <Text style={styles.subtitle}>
        {SEGMENT_TYPE_LABELS[data.segment_type]} · {formatLength(data.length_m)} · {data.code}
      </Text>
      {data.is_demo && <Text style={styles.demo}>DỮ LIỆU MINH HOẠ, không phải dữ liệu thật</Text>}

      <Text style={styles.section}>Trạng thái hiện tại</Text>
      {DIMENSIONS.map(({ key, label }) => (
        <StatusBadge key={key} dimension={key} label={label} status={data.status[key]} segmentType={data.segment_type} />
      ))}
      <Text style={styles.note}>
        Trạng thái được tổng hợp từ phản ánh, kiểm duyệt và cảm biến. Đoạn chưa có dữ liệu không có nghĩa là bình
        thường.
      </Text>

      <Text style={styles.section}>Bằng chứng gần đây (72 giờ)</Text>
      {data.recent_evidence.length === 0 && <Text style={styles.note}>Chưa có.</Text>}
      {data.recent_evidence.map((e, i) => (
        <View key={`${e.observed_at}-${i}`} style={styles.row}>
          <Text style={styles.rowLabel}>
            {SOURCE_LABELS[e.source_type] ?? e.source_type} · {timeAgo(e.observed_at)}
            {e.has_photo ? ' · có ảnh' : ''}
          </Text>
          <Text style={styles.rowValue}>{levelLabel(e.dimension, e.level)}</Text>
        </View>
      ))}

      <Text style={styles.section}>Lịch sử trạng thái (7 ngày)</Text>
      <History code={data.code} />

      <Text style={styles.section}>Thông tin đoạn</Text>
      <Row label="Tên đường" value={data.road_name} />
      <Row label="Bề rộng" value={WIDTH_LABELS[data.width_class]} />
      <Row label="Nguy cơ ngập (khảo sát)" value={FLOOD_PRONE_LABELS[data.flood_prone]} />
      <Row label="Xác minh" value={VERIFICATION_LABELS[data.verification_status]} />

      <Text style={styles.section}>Nguồn dữ liệu</Text>
      <Row label="Hình học" value={data.source?.attribution ?? data.source?.name} />
      <Row label="Giấy phép" value={data.source?.license} />
      <Row label="Phiên bản dữ liệu" value={data.source?.dataset_version ? `v${data.source.dataset_version}` : null} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  content: { padding: 16, paddingBottom: 40 },
  center: { marginTop: 40, textAlign: 'center' },
  error: { color: colors.danger },
  title: { fontSize: 20, fontWeight: '700', color: colors.text },
  subtitle: { marginTop: 4, fontSize: 13, color: colors.textMuted },
  demo: { marginTop: 8, fontWeight: '700', color: colors.danger },
  section: { marginTop: 20, marginBottom: 6, fontSize: 13, fontWeight: '700', color: colors.textMuted },
  note: { marginTop: 6, fontSize: 12, color: colors.textMuted },
  gap: { marginTop: 8 },
  row: { paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rowLabel: { fontSize: 12, color: colors.textMuted },
  rowValue: { marginTop: 2, fontSize: 15, color: colors.text },
});
