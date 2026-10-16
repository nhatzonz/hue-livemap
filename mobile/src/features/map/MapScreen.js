import { useRouter } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Linking, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import MapView from 'react-native-maps';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useShallow } from 'zustand/react/shallow';

import { useRegion, useSegments } from '../../api/segments';
import BackendStatusPill from '../../components/BackendStatusPill';
import { HUE_INITIAL_REGION, MY_LOCATION_DELTA } from '../../constants/region';
import { bboxToRegion, nearestFeature, tapToleranceMeters } from '../../lib/geo';
import { useMapStore } from '../../store/mapStore';
import { colors } from '../../theme/colors';
import LayerChips from './LayerChips';
import Legend from './Legend';
import PilotAreaOverlay from './PilotAreaOverlay';
import SegmentLayer from './SegmentLayer';
import SegmentSheet from './SegmentSheet';
import { useForegroundLocation } from './useForegroundLocation';

export default function MapScreen() {
  const router = useRouter();
  const mapRef = useRef(null);
  const regionRef = useRef(HUE_INITIAL_REGION);
  const { height: screenHeight } = useWindowDimensions();
  const { permission, getCurrent } = useForegroundLocation();
  const [locating, setLocating] = useState(false);

  // useShallow: chỉ render lại khi các trường dùng ở đây đổi, không phải mọi thay đổi của store
  const { dimension, setDimension, selectedCode, select, focusRequest, clearFocusRequest } = useMapStore(
    useShallow((s) => ({
      dimension: s.dimension,
      setDimension: s.setDimension,
      selectedCode: s.selectedCode,
      select: s.select,
      focusRequest: s.focusRequest,
      clearFocusRequest: s.clearFocusRequest,
    })),
  );
  const regionQuery = useRegion();
  const pilotAreas = regionQuery.data?.pilot_areas ?? [];
  const pilotBbox = pilotAreas[0]?.bbox;
  const segmentsQuery = useSegments(dimension, pilotBbox);
  const features = useMemo(() => segmentsQuery.data?.features ?? [], [segmentsQuery.data]);

  // Lần đầu có ranh giới thí điểm: đưa khung nhìn về toàn vùng
  const fittedRef = useRef(false);
  useEffect(() => {
    if (pilotBbox && !fittedRef.current) {
      fittedRef.current = true;
      mapRef.current?.animateToRegion(bboxToRegion(pilotBbox, 1.1), 400);
    }
  }, [pilotBbox]);

  // Yêu cầu zoom từ màn tìm kiếm
  useEffect(() => {
    if (focusRequest?.bbox) {
      mapRef.current?.animateToRegion(bboxToRegion(focusRequest.bbox, 3), 500);
      clearFocusRequest();
    }
  }, [focusRequest, clearFocusRequest]);

  function handleMapPress(event) {
    const point = event.nativeEvent.coordinate;
    const hit = nearestFeature(point, features, tapToleranceMeters(regionRef.current, screenHeight));
    select(hit ? hit.properties.code : null);
  }

  async function goToMyLocation() {
    setLocating(true);
    try {
      const coords = await getCurrent();
      if (!coords) {
        Alert.alert(
          'Chưa có quyền vị trí',
          'Hãy cho phép HUE-LIVEMAP dùng vị trí khi đang mở ứng dụng để xem các đoạn đường gần bạn.',
          [
            { text: 'Để sau', style: 'cancel' },
            { text: 'Mở Cài đặt', onPress: () => Linking.openSettings() },
          ],
        );
        return;
      }
      mapRef.current?.animateToRegion(
        {
          latitude: coords.latitude,
          longitude: coords.longitude,
          latitudeDelta: MY_LOCATION_DELTA,
          longitudeDelta: MY_LOCATION_DELTA,
        },
        500,
      );
    } catch {
      Alert.alert('Không lấy được vị trí', 'Hãy kiểm tra GPS đã bật và thử lại.');
    } finally {
      setLocating(false);
    }
  }

  const loadError = regionQuery.error ?? segmentsQuery.error;

  return (
    <View style={styles.container}>
      <MapView
        ref={mapRef}
        style={StyleSheet.absoluteFill}
        initialRegion={HUE_INITIAL_REGION}
        showsUserLocation={permission === 'granted'}
        showsMyLocationButton={false}
        showsPointsOfInterests={false}
        toolbarEnabled={false}
        onPress={handleMapPress}
        onRegionChangeComplete={(region) => {
          regionRef.current = region;
        }}
      >
        <PilotAreaOverlay areas={pilotAreas} />
        <SegmentLayer features={features} dimension={dimension} selectedCode={selectedCode} />
      </MapView>

      <SafeAreaView style={styles.topOverlay} edges={['top']} pointerEvents="box-none">
        <Pressable style={styles.searchBar} onPress={() => router.push('/search')} accessibilityRole="search">
          <Text style={styles.searchText}>🔍 Tìm đường, kiệt…</Text>
          <Pressable onPress={() => router.push('/about')} hitSlop={10} accessibilityLabel="Giới thiệu">
            <Text style={styles.infoIcon}>ⓘ</Text>
          </Pressable>
        </Pressable>
        <LayerChips value={dimension} onChange={setDimension} />
        {loadError && <Text style={styles.errorBanner}>Không tải được dữ liệu: {loadError.message}</Text>}
        {__DEV__ && <BackendStatusPill />}
      </SafeAreaView>

      <View style={styles.bottomOverlay} pointerEvents="box-none">
        {!selectedCode && (
          <SafeAreaView edges={['bottom']} style={styles.bottomRow} pointerEvents="box-none">
            <View style={styles.legendSlot}>
              <Legend dimension={dimension} />
            </View>
            <View style={styles.fabColumn} pointerEvents="box-none">
            <Pressable
              style={({ pressed }) => [styles.fab, pressed && styles.fabPressed]}
              onPress={goToMyLocation}
              disabled={locating}
              accessibilityRole="button"
              accessibilityLabel="Về vị trí của tôi"
            >
              <Text style={styles.fabText}>{locating ? '…' : '◎'}</Text>
            </Pressable>
            <Pressable
              style={({ pressed }) => [styles.reportButton, pressed && styles.fabPressed]}
              onPress={() => router.push('/report/new')}
              accessibilityRole="button"
              accessibilityLabel="Gửi phản ánh"
            >
              <Text style={styles.reportText}>+ Phản ánh</Text>
            </Pressable>
            </View>
          </SafeAreaView>
        )}
        {selectedCode && (
          <SafeAreaView edges={['bottom']} style={styles.sheetWrap}>
            <SegmentSheet
              // key: trạng thái nút "Vẫn còn / Đã hết" không được mang sang đoạn/lớp khác
              key={`${selectedCode}-${dimension}`}
              code={selectedCode}
              dimension={dimension}
              onClose={() => select(null)}
            />
          </SafeAreaView>
        )}
      </View>
    </View>
  );
}

const shadow = {
  shadowColor: '#000',
  shadowOpacity: 0.15,
  shadowRadius: 6,
  shadowOffset: { width: 0, height: 2 },
  elevation: 3,
};

const styles = StyleSheet.create({
  container: { flex: 1 },
  topOverlay: { position: 'absolute', top: 0, left: 0, right: 0, paddingHorizontal: 12, gap: 8 },
  searchBar: {
    marginTop: 8,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: colors.surface,
    ...shadow,
  },
  searchText: { flex: 1, fontSize: 15, color: colors.textMuted },
  infoIcon: { fontSize: 20, color: colors.primary },
  errorBanner: {
    alignSelf: 'flex-start',
    padding: 8,
    borderRadius: 8,
    backgroundColor: '#FDECEA',
    color: colors.danger,
    fontSize: 13,
  },
  bottomOverlay: { position: 'absolute', left: 0, right: 0, bottom: 0 },
  bottomRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingBottom: 12,
  },
  sheetWrap: { backgroundColor: colors.surface },
  fab: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
    ...shadow,
  },
  fabPressed: { opacity: 0.7 },
  // Chú giải được co lại (chữ xuống dòng); cột nút luôn giữ nguyên kích thước, không bị đẩy ra ngoài màn hình
  legendSlot: { flexShrink: 1, marginRight: 12 },
  fabColumn: { alignItems: 'flex-end', gap: 12, flexShrink: 0 },
  reportButton: {
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderRadius: 28,
    backgroundColor: colors.danger,
    ...shadow,
  },
  reportText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  fabText: { fontSize: 24, color: colors.primary },
});
