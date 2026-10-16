import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import StatusBadge from '../../components/StatusBadge';
import { LEVEL_LABELS, STATE_LABELS } from '../../constants/status';
import { colors } from '../../theme/colors';

// Chú giải thu gọn: giải thích màu (mức độ) và kiểu nét (độ chắc chắn)
export default function Legend({ dimension }) {
  const [open, setOpen] = useState(false);
  const levels = Object.keys(LEVEL_LABELS[dimension]);
  const exampleLevel = levels[Math.min(3, levels.length - 1)];

  return (
    <View style={styles.box}>
      <Pressable onPress={() => setOpen((v) => !v)} accessibilityRole="button" hitSlop={8}>
        <Text style={styles.toggle}>{open ? 'Chú giải ▴' : 'Chú giải ▾'}</Text>
      </Pressable>
      {open && (
        <View style={styles.body}>
          <Text style={styles.heading}>Màu = mức độ</Text>
          {levels.map((level) => (
            <StatusBadge
              key={level}
              dimension={dimension}
              status={{ state: 'CONFIRMED', level }}
              text={LEVEL_LABELS[dimension][level]}
            />
          ))}
          <Text style={[styles.heading, styles.gap]}>Nét = độ tin cậy</Text>
          <StatusBadge dimension={dimension} status={{ state: 'CONFIRMED', level: exampleLevel }} text={STATE_LABELS.CONFIRMED} />
          <StatusBadge dimension={dimension} status={{ state: 'UNVERIFIED', level: exampleLevel }} text={STATE_LABELS.UNVERIFIED} />
          <StatusBadge dimension={dimension} status={{ state: 'STALE', level: exampleLevel }} text={STATE_LABELS.STALE} />
          <StatusBadge dimension={dimension} status={{ state: 'NO_DATA' }} />
          <Text style={styles.note}>Chưa có dữ liệu KHÔNG có nghĩa là bình thường.</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    alignSelf: 'flex-start',
    maxWidth: 280,
    padding: 10,
    borderRadius: 12,
    backgroundColor: colors.surface,
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  toggle: { fontSize: 13, fontWeight: '600', color: colors.primary },
  body: { marginTop: 6 },
  heading: { fontSize: 12, fontWeight: '700', color: colors.textMuted, marginBottom: 2 },
  gap: { marginTop: 8 },
  note: { marginTop: 6, fontSize: 12, color: colors.danger },
});
