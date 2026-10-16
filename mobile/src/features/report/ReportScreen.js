import { useQueryClient } from '@tanstack/react-query';
import * as Crypto from 'expo-crypto';
import * as Location from 'expo-location';
import { useRouter } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { submitReport, uploadReportPhoto } from '../../api/reports';
import { DESCRIPTION_MAX, EMERGENCY_NUMBERS, REPORT_LEVELS, REPORT_TYPES } from '../../constants/report';
import { takeReportPhoto } from '../../lib/image';
import { colors } from '../../theme/colors';
import { useForegroundLocation } from '../map/useForegroundLocation';
import LocationStep from './LocationStep';

const STEPS = ['type', 'level', 'photo', 'location', 'review'];
const STEP_TITLES = {
  type: 'Bạn muốn báo gì?',
  level: 'Mức độ',
  photo: 'Ảnh hiện trường',
  location: 'Vị trí',
  review: 'Ghi chú và gửi',
};

function EmergencyNote() {
  return (
    <Text style={styles.emergency}>
      Nếu có người gặp nguy hiểm, hãy gọi{' '}
      {EMERGENCY_NUMBERS.slice(0, 2).map(([number], i) => (
        <Text key={number} style={styles.emergencyLink} onPress={() => Linking.openURL(`tel:${number}`)}>
          {i > 0 ? ' / ' : ''}
          {number}
        </Text>
      ))}
    </Text>
  );
}

function Choice({ title, subtitle, icon, active, onPress }) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.choice, active && styles.choiceActive, pressed && styles.pressed]}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
    >
      {icon ? <Text style={styles.choiceIcon}>{icon}</Text> : null}
      <View style={styles.choiceText}>
        <Text style={styles.choiceTitle}>{title}</Text>
        {subtitle ? <Text style={styles.choiceSubtitle}>{subtitle}</Text> : null}
      </View>
    </Pressable>
  );
}

export default function ReportScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { getCurrent } = useForegroundLocation(Location.Accuracy.High);

  const [step, setStep] = useState(0);
  const [type, setType] = useState(null);
  const [level, setLevel] = useState(null);
  const [photo, setPhoto] = useState(null);
  const [photoMessage, setPhotoMessage] = useState(null);
  const [gps, setGps] = useState(null);
  const [gpsError, setGpsError] = useState(null);
  const [pin, setPin] = useState(null);
  const [segmentCode, setSegmentCode] = useState(null);
  const [locationValid, setLocationValid] = useState(false);
  const [description, setDescription] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState(null);
  const [result, setResult] = useState(null); // { report, photoFailed }

  // id + thời điểm cố định từ lần gửi đầu → bấm "Thử lại" không tạo phản ánh trùng
  const identityRef = useRef(null);

  // Lấy GPS ngay khi mở màn hình để đến bước vị trí là có sẵn
  useEffect(() => {
    getCurrent()
      .then((coords) => {
        if (!coords) {
          setGpsError('Cần quyền vị trí để gửi phản ánh. Hãy bật trong Cài đặt.');
          return;
        }
        setGps(coords);
        setPin({ latitude: coords.latitude, longitude: coords.longitude });
      })
      .catch(() => setGpsError('Không lấy được vị trí. Hãy kiểm tra GPS đã bật.'));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onValidity = useCallback((valid) => setLocationValid(valid), []);
  const current = STEPS[step];
  const canNext = {
    type: Boolean(type),
    level: Boolean(level),
    photo: true,
    location: locationValid,
    review: !sending,
  }[current];

  async function capturePhoto() {
    setPhotoMessage(null);
    try {
      const outcome = await takeReportPhoto();
      if (outcome.denied) setPhotoMessage('Chưa có quyền camera. Bạn vẫn có thể gửi không kèm ảnh.');
      if (outcome.photo) setPhoto(outcome.photo);
    } catch {
      setPhotoMessage('Không chụp được ảnh. Bạn vẫn có thể gửi không kèm ảnh.');
    }
  }

  async function send() {
    setSending(true);
    setSendError(null);
    identityRef.current ??= { id: Crypto.randomUUID(), createdAt: new Date().toISOString() };
    try {
      const report = await submitReport({
        id: identityRef.current.id,
        dimension: type.dimension,
        category: type.category,
        level,
        description: description.trim() || null,
        location: { lat: pin.latitude, lon: pin.longitude },
        reporter_location: gps ? { lat: gps.latitude, lon: gps.longitude } : null,
        gps_accuracy_m: gps?.accuracy ?? null,
        segment_code: segmentCode,
        client_created_at: identityRef.current.createdAt,
      });
      let photoFailed = false;
      if (photo) {
        try {
          await uploadReportPhoto(report.id, photo);
        } catch {
          photoFailed = true;
        }
      }
      queryClient.invalidateQueries({ queryKey: ['segments'] });
      queryClient.invalidateQueries({ queryKey: ['my-reports'] });
      if (report.segment) queryClient.invalidateQueries({ queryKey: ['segment', report.segment.code] });
      setResult({ report, photoFailed });
    } catch (err) {
      setSendError(
        err.code === 'NETWORK_ERROR'
          ? 'Không gửi được do mất kết nối. Kiểm tra mạng rồi bấm Gửi lại.'
          : err.message,
      );
    } finally {
      setSending(false);
    }
  }

  async function retryPhoto() {
    try {
      await uploadReportPhoto(result.report.id, photo);
      setResult({ ...result, photoFailed: false });
    } catch {
      setPhotoMessage('Vẫn chưa gửi được ảnh. Thử lại sau.');
    }
  }

  if (result) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.successIcon}>✓</Text>
          <Text style={styles.successTitle}>Đã gửi phản ánh</Text>
          <Text style={styles.p}>
            {result.report.segment
              ? `Đã gắn vào: ${result.report.segment.name}.`
              : 'Phản ánh được lưu theo vị trí ghim.'}
          </Text>
          <Text style={styles.p}>
            Trạng thái: chờ xác minh. Bản đồ chỉ hiện “đã xác nhận” khi có người kiểm duyệt hoặc đủ nhiều nguồn
            độc lập cùng báo.
          </Text>
          {result.photoFailed && (
            <View style={styles.warnBox}>
              <Text style={styles.warnText}>Ảnh chưa gửi được.</Text>
              <Pressable onPress={retryPhoto} style={styles.secondaryButton}>
                <Text style={styles.secondaryText}>Gửi lại ảnh</Text>
              </Pressable>
            </View>
          )}
          <EmergencyNote />
          <Pressable style={styles.primaryButton} onPress={() => router.back()}>
            <Text style={styles.primaryText}>Về bản đồ</Text>
          </Pressable>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.progress}>
          {STEPS.map((s, i) => (
            <View key={s} style={[styles.progressDot, i <= step && styles.progressDotActive]} />
          ))}
        </View>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.stepTitle}>{STEP_TITLES[current]}</Text>

          {current === 'type' &&
            REPORT_TYPES.map((t) => (
              <Choice
                key={t.key}
                icon={t.icon}
                title={t.label}
                active={type?.key === t.key}
                onPress={() => {
                  if (type?.dimension !== t.dimension) setLevel(null);
                  setType(t);
                  setStep(1);
                }}
              />
            ))}

          {current === 'level' &&
            REPORT_LEVELS[type.dimension].map((l) => (
              <Choice
                key={l.level}
                title={l.label}
                subtitle={l.hint}
                active={level === l.level}
                onPress={() => {
                  setLevel(l.level);
                  setStep(2);
                }}
              />
            ))}

          {current === 'photo' && (
            <View>
              <Text style={styles.p}>
                Ảnh giúp xác minh nhanh hơn. Chỉ chụp trực tiếp, tránh chụp rõ mặt người hoặc biển số xe.
              </Text>
              {photo && <Image source={{ uri: photo.uri }} style={styles.photo} resizeMode="cover" />}
              <Pressable style={styles.secondaryButton} onPress={capturePhoto}>
                <Text style={styles.secondaryText}>{photo ? '📷 Chụp lại' : '📷 Chụp ảnh'}</Text>
              </Pressable>
              {photo && (
                <Pressable onPress={() => setPhoto(null)}>
                  <Text style={styles.link}>Bỏ ảnh</Text>
                </Pressable>
              )}
              {photoMessage && <Text style={styles.warnText}>{photoMessage}</Text>}
            </View>
          )}

          {current === 'location' && (
            <LocationStep
              gps={gps}
              gpsError={gpsError}
              pin={pin}
              onPinChange={setPin}
              segmentCode={segmentCode}
              onSegmentChange={setSegmentCode}
              onValidity={onValidity}
            />
          )}

          {current === 'review' && (
            <View>
              <Text style={styles.p}>
                {type.icon} {type.label} · {REPORT_LEVELS[type.dimension].find((l) => l.level === level)?.label}
                {photo ? ' · có ảnh' : ' · không có ảnh'}
              </Text>
              <TextInput
                style={styles.input}
                value={description}
                onChangeText={setDescription}
                placeholder="Ghi chú thêm (không bắt buộc)"
                multiline
                maxLength={DESCRIPTION_MAX}
              />
              <Text style={styles.counter}>
                {description.length}/{DESCRIPTION_MAX}
              </Text>
              {sendError && <Text style={styles.error}>{sendError}</Text>}
              <EmergencyNote />
            </View>
          )}
        </ScrollView>

        <View style={styles.footer}>
          <Pressable
            style={styles.backButton}
            onPress={() => (step === 0 ? router.back() : setStep(step - 1))}
            disabled={sending}
          >
            <Text style={styles.secondaryText}>{step === 0 ? 'Huỷ' : '‹ Quay lại'}</Text>
          </Pressable>
          {current !== 'type' && current !== 'level' && (
            <Pressable
              style={[styles.primaryButton, styles.footerPrimary, !canNext && styles.disabled]}
              disabled={!canNext}
              onPress={() => (current === 'review' ? send() : setStep(step + 1))}
            >
              {sending ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.primaryText}>
                  {current === 'review' ? (sendError ? 'Gửi lại' : 'Gửi') : current === 'photo' && !photo ? 'Bỏ qua ›' : 'Tiếp ›'}
                </Text>
              )}
            </Pressable>
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: { flex: 1, backgroundColor: colors.surface },
  content: { padding: 16, paddingBottom: 32 },
  progress: { flexDirection: 'row', gap: 6, paddingHorizontal: 16, paddingTop: 12 },
  progressDot: { flex: 1, height: 4, borderRadius: 2, backgroundColor: colors.border },
  progressDotActive: { backgroundColor: colors.primary },
  stepTitle: { fontSize: 20, fontWeight: '700', color: colors.text, marginBottom: 12 },
  p: { fontSize: 15, lineHeight: 21, color: colors.text, marginBottom: 8 },
  choice: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    marginBottom: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  choiceActive: { borderColor: colors.primary, backgroundColor: '#EEF5FC' },
  pressed: { opacity: 0.7 },
  choiceIcon: { fontSize: 26, marginRight: 12 },
  choiceText: { flex: 1 },
  choiceTitle: { fontSize: 16, fontWeight: '600', color: colors.text },
  choiceSubtitle: { marginTop: 2, fontSize: 13, color: colors.textMuted },
  photo: { width: '100%', aspectRatio: 4 / 3, borderRadius: 12, marginBottom: 10, backgroundColor: '#eee' },
  input: {
    minHeight: 90,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    fontSize: 15,
    textAlignVertical: 'top',
  },
  counter: { alignSelf: 'flex-end', fontSize: 12, color: colors.textMuted, marginTop: 4 },
  error: { marginTop: 10, fontSize: 14, color: colors.danger },
  emergency: { marginTop: 16, fontSize: 13, color: colors.textMuted },
  emergencyLink: { color: colors.danger, fontWeight: '700' },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  backButton: { paddingVertical: 12, paddingHorizontal: 8 },
  primaryButton: {
    marginTop: 16,
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 12,
    alignItems: 'center',
    backgroundColor: colors.primary,
  },
  footerPrimary: { marginTop: 0, minWidth: 120 },
  primaryText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  disabled: { opacity: 0.4 },
  secondaryButton: {
    marginTop: 4,
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.primary,
  },
  secondaryText: { color: colors.primary, fontSize: 16, fontWeight: '600' },
  link: { marginTop: 10, color: colors.danger, textAlign: 'center' },
  warnBox: { marginTop: 12, padding: 12, borderRadius: 10, backgroundColor: '#FFF4E5' },
  warnText: { marginTop: 8, color: colors.warn, fontSize: 14 },
  successIcon: { fontSize: 48, color: colors.ok, textAlign: 'center', marginTop: 24 },
  successTitle: { fontSize: 22, fontWeight: '700', textAlign: 'center', marginBottom: 12, color: colors.text },
});
