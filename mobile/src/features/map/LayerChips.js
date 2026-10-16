import { Pressable, StyleSheet, Text, View } from 'react-native';

import { DIMENSIONS } from '../../constants/status';
import { colors } from '../../theme/colors';

// Mỗi lúc chỉ hiển thị một lớp trạng thái để bản đồ dễ đọc (PROJECT_PLAN.md mục 5.3)
export default function LayerChips({ value, onChange }) {
  return (
    <View style={styles.row} accessibilityRole="tablist">
      {DIMENSIONS.map(({ key, label }) => {
        const active = key === value;
        return (
          <Pressable
            key={key}
            onPress={() => onChange(key)}
            style={[styles.chip, active && styles.chipActive]}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
          >
            <Text style={[styles.text, active && styles.textActive]}>{label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 8 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 16,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  text: { fontSize: 14, color: colors.text, fontWeight: '500' },
  textActive: { color: '#fff' },
});
