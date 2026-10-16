import { StyleSheet, Text, View } from 'react-native';

import { describeStatus } from '../constants/status';
import { timeAgo } from '../lib/format';
import { colors } from '../theme/colors';
import { segmentStyle } from '../theme/status';

// Mẫu nét vẽ bằng các vạch nhỏ: borderStyle 'dashed' trên iOS chỉ chạy khi cả 4 cạnh có viền.
function Swatch({ color, pattern, width }) {
  if (!pattern) return <View style={[styles.swatch, { backgroundColor: color, height: width }]} />;
  const [dash, gap] = pattern;
  const count = Math.max(2, Math.floor(28 / (dash + gap)));
  return (
    <View style={[styles.swatch, styles.swatchRow]}>
      {Array.from({ length: count }, (_, i) => (
        <View key={i} style={{ width: dash, height: width, marginRight: gap, backgroundColor: color }} />
      ))}
    </View>
  );
}

// Một dòng trạng thái: mẫu nét giống trên bản đồ + mô tả + số nguồn + thời gian cập nhật
// `text` ghi đè mô tả mặc định (dùng trong chú giải).
export default function StatusBadge({ dimension, label, status, segmentType = 'street', text }) {
  const style = segmentStyle(dimension, segmentType, status);
  const updated = timeAgo(status?.last_evidence_at);
  const meta = [
    status?.evidence_count ? `${status.evidence_count} nguồn` : null,
    updated ? `cập nhật ${updated}` : null,
  ].filter(Boolean);

  return (
    <View style={styles.row}>
      <Swatch color={style.strokeColor} pattern={style.lineDashPattern} width={Math.min(4, style.strokeWidth)} />
      <View style={styles.texts}>
        <Text style={styles.text}>
          {label ? <Text style={styles.label}>{label}: </Text> : null}
          {text ?? describeStatus(dimension, status)}
        </Text>
        {meta.length > 0 && <Text style={styles.meta}>{meta.join(' · ')}</Text>}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: 4 },
  swatch: { width: 28, marginRight: 10 },
  swatchRow: { flexDirection: 'row', overflow: 'hidden' },
  texts: { flex: 1 },
  label: { fontWeight: '600' },
  text: { fontSize: 14, color: colors.text },
  meta: { fontSize: 12, color: colors.textMuted, marginTop: 1 },
});
