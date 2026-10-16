import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { useSegmentSearch } from '../api/segments';
import { SEGMENT_TYPE_LABELS } from '../constants/status';
import { useMapStore } from '../store/mapStore';
import { colors } from '../theme/colors';

function useDebounced(value, delayMs) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export default function SearchScreen() {
  const router = useRouter();
  const requestFocus = useMapStore((s) => s.requestFocus);
  const [text, setText] = useState('');
  const query = useDebounced(text, 300);
  const { data, isFetching, error } = useSegmentSearch(query);
  const results = query.trim().length >= 2 ? (data?.results ?? []) : [];

  function choose(item) {
    requestFocus(item.code, item.bbox);
    router.back();
  }

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.input}
        value={text}
        onChangeText={setText}
        placeholder="Ví dụ: kiet 12 dinh tien hoang, Lê Duẩn"
        autoFocus
        autoCorrect={false}
        returnKeyType="search"
        clearButtonMode="while-editing"
      />
      <Text style={styles.hint}>Gõ không dấu cũng được. Chỉ tìm trong vùng thí điểm.</Text>
      {isFetching && <ActivityIndicator style={styles.spinner} />}
      {error && <Text style={styles.error}>{error.message}</Text>}
      <FlatList
        data={results}
        keyExtractor={(item) => item.code}
        keyboardShouldPersistTaps="handled"
        renderItem={({ item }) => (
          <Pressable style={({ pressed }) => [styles.item, pressed && styles.pressed]} onPress={() => choose(item)}>
            <Text style={styles.itemTitle}>{item.name}</Text>
            <Text style={styles.itemMeta}>
              {SEGMENT_TYPE_LABELS[item.segment_type]} · {item.code}
            </Text>
          </Pressable>
        )}
        ListEmptyComponent={
          query.trim().length >= 2 && !isFetching && !error ? (
            <Text style={styles.empty}>Không tìm thấy đoạn nào. Có thể đoạn này chưa có trong dữ liệu.</Text>
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface, padding: 12 },
  input: {
    fontSize: 16,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
  },
  hint: { marginTop: 6, fontSize: 12, color: colors.textMuted },
  spinner: { marginTop: 12 },
  error: { marginTop: 12, color: colors.danger },
  item: { paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  pressed: { backgroundColor: '#F1F4F8' },
  itemTitle: { fontSize: 15, color: colors.text },
  itemMeta: { marginTop: 2, fontSize: 12, color: colors.textMuted },
  empty: { marginTop: 16, color: colors.textMuted },
});
