import { useEffect } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import MapView, { Marker } from 'react-native-maps';

import { useSnap } from '../../api/reports';
import { MAX_GPS_ACCURACY_M } from '../../constants/report';
import { colors } from '../../theme/colors';

// Bước xác nhận vị trí: ghim kéo được + chọn đoạn khi có nhiều đoạn quanh vị trí (giao lộ).
export default function LocationStep({ gps, gpsError, pin, onPinChange, segmentCode, onSegmentChange, onValidity }) {
  const snap = useSnap(pin);
  const candidates = snap.data?.candidates ?? [];
  const inPilotArea = snap.data?.in_pilot_area;

  // Mặc định chọn đoạn gần nhất; bỏ chọn nếu đoạn đã chọn không còn trong danh sách
  useEffect(() => {
    if (!snap.data) return;
    if (!candidates.some((c) => c.code === segmentCode)) onSegmentChange(candidates[0]?.code ?? null);
  }, [snap.data]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    onValidity(Boolean(pin && snap.data && inPilotArea));
  }, [pin, snap.data, inPilotArea, onValidity]);

  if (!pin) {
    return (
      <View style={styles.center}>
        {gpsError ? <Text style={styles.error}>{gpsError}</Text> : <ActivityIndicator />}
        {!gpsError && <Text style={styles.muted}>Đang lấy vị trí GPS…</Text>}
      </View>
    );
  }

  const inaccurate = gps?.accuracy && gps.accuracy > MAX_GPS_ACCURACY_M;

  return (
    <View>
      <View style={styles.mapBox}>
        <MapView
          style={StyleSheet.absoluteFill}
          initialRegion={{ ...pin, latitudeDelta: 0.003, longitudeDelta: 0.003 }}
          showsUserLocation
          showsPointsOfInterests={false}
          toolbarEnabled={false}
        >
          <Marker coordinate={pin} draggable onDragEnd={(e) => onPinChange(e.nativeEvent.coordinate)} />
        </MapView>
      </View>
      <Text style={styles.muted}>Giữ và kéo ghim nếu vị trí chưa đúng chỗ sự việc.</Text>
      {inaccurate && (
        <Text style={styles.warn}>
          GPS chưa chính xác (±{Math.round(gps.accuracy)} m). Hãy kéo ghim tới đúng chỗ trước khi gửi.
        </Text>
      )}

      {snap.isPending && <ActivityIndicator style={styles.gap} />}
      {snap.error && <Text style={styles.error}>{snap.error.message}</Text>}
      {snap.data && !inPilotArea && (
        <Text style={styles.error}>Vị trí này nằm ngoài vùng thí điểm nên chưa nhận phản ánh.</Text>
      )}
      {snap.data && inPilotArea && candidates.length === 0 && (
        <Text style={styles.muted}>
          Không có đoạn đường nào trong 30 m. Phản ánh sẽ được lưu theo vị trí ghim để người kiểm duyệt xử lý.
        </Text>
      )}
      {candidates.length > 1 && <Text style={styles.question}>Bạn đang ở đoạn nào?</Text>}
      {candidates.map((c) => {
        const active = c.code === segmentCode;
        return (
          <Pressable
            key={c.code}
            onPress={() => onSegmentChange(c.code)}
            style={[styles.option, active && styles.optionActive]}
            accessibilityRole="radio"
            accessibilityState={{ selected: active }}
          >
            <Text style={styles.radio}>{active ? '◉' : '○'}</Text>
            <View style={styles.optionText}>
              <Text style={styles.optionTitle}>{c.name}</Text>
              <Text style={styles.muted}>cách {Math.round(c.distance_m)} m</Text>
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: 'center', paddingVertical: 32, gap: 8 },
  mapBox: { height: 220, borderRadius: 12, overflow: 'hidden', marginBottom: 6 },
  muted: { fontSize: 13, color: colors.textMuted, marginTop: 4 },
  warn: { fontSize: 13, color: colors.warn, marginTop: 6, fontWeight: '600' },
  error: { fontSize: 14, color: colors.danger, marginTop: 8 },
  gap: { marginTop: 8 },
  question: { marginTop: 12, fontSize: 15, fontWeight: '600', color: colors.text },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
  },
  optionActive: { borderColor: colors.primary, backgroundColor: '#EEF5FC' },
  radio: { fontSize: 18, color: colors.primary, marginRight: 10 },
  optionText: { flex: 1 },
  optionTitle: { fontSize: 15, color: colors.text },
});
