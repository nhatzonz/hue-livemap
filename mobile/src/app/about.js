import Constants from 'expo-constants';
import { useRouter } from 'expo-router';
import { Linking, ScrollView, StyleSheet, Text } from 'react-native';

import { useRegion } from '../api/segments';
import { API_URL } from '../lib/config';
import { colors } from '../theme/colors';

export default function AboutScreen() {
  const router = useRouter();
  const { data } = useRegion();
  const area = data?.pilot_areas?.[0];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>HUE-LIVEMAP</Text>
      <Text style={styles.p}>
        Bản đồ trạng thái từng đoạn đường và kiệt ở Huế: ngập, vật cản, giao thông. Mỗi trạng thái đều kèm độ tin
        cậy và thời điểm cập nhật.
      </Text>

      <Text style={styles.link} onPress={() => router.push('/my-reports')}>
        Phản ánh của tôi ›
      </Text>

      <Text style={styles.section}>Vùng thí điểm</Text>
      <Text style={styles.p}>
        {area ? `${area.name} · ${area.area_km2} km²` : 'Đang tải…'}
        {area?.status === 'draft' ? ' (ranh giới dự kiến)' : ''}
      </Text>
      {data?.dataset && <Text style={styles.small}>Dữ liệu đường phiên bản v{data.dataset.version}</Text>}

      <Text style={styles.section}>Cách đọc bản đồ</Text>
      <Text style={styles.p}>• Màu cho biết mức độ (ví dụ mức ngập).</Text>
      <Text style={styles.p}>• Nét liền: đã xác nhận. Nét đứt: chưa xác minh. Nét mờ: dữ liệu cũ.</Text>
      <Text style={styles.p}>• Nét chấm xám: chưa có dữ liệu. Điều này KHÔNG có nghĩa là đường bình thường.</Text>

      <Text style={styles.section}>Khẩn cấp</Text>
      <Text style={styles.p}>
        Ứng dụng không thay thế kênh khẩn cấp. Khi có người gặp nguy hiểm, hãy gọi:
      </Text>
      {[
        ['112', 'Tìm kiếm cứu nạn'],
        ['114', 'Cứu hoả, cứu nạn'],
        ['115', 'Cấp cứu'],
        ['113', 'Công an'],
      ].map(([number, label]) => (
        <Text key={number} style={styles.link} onPress={() => Linking.openURL(`tel:${number}`)}>
          {number}: {label}
        </Text>
      ))}

      <Text style={styles.section}>Nguồn dữ liệu</Text>
      <Text style={styles.p}>{data?.attribution ?? 'Dữ liệu đường © OpenStreetMap contributors (ODbL)'}</Text>
      <Text style={styles.link} onPress={() => Linking.openURL('https://www.openstreetmap.org/copyright')}>
        openstreetmap.org/copyright
      </Text>

      <Text style={styles.section}>Phiên bản</Text>
      <Text style={styles.small}>
        Ứng dụng {Constants.expoConfig?.version} · máy chủ {API_URL}
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  content: { padding: 16, paddingBottom: 40 },
  title: { fontSize: 22, fontWeight: '700', color: colors.primary },
  section: { marginTop: 20, marginBottom: 4, fontSize: 13, fontWeight: '700', color: colors.textMuted },
  p: { fontSize: 15, lineHeight: 21, color: colors.text, marginTop: 4 },
  small: { fontSize: 12, color: colors.textMuted, marginTop: 4 },
  link: { fontSize: 15, color: colors.primary, marginTop: 6 },
});
