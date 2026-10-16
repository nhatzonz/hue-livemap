import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';

const MAX_SIDE = 1600;
const JPEG_QUALITY = 0.7;

// Chụp ảnh trực tiếp (không chọn từ thư viện, để giảm ảnh cũ/ảnh mạng), rồi thu nhỏ + nén.
// Mã hoá lại JPEG cũng bỏ EXIF (gồm toạ độ GPS trong ảnh); server vẫn xoá thêm lần nữa.
export async function takeReportPhoto() {
  const permission = await ImagePicker.requestCameraPermissionsAsync();
  if (!permission.granted) return { denied: true };

  const result = await ImagePicker.launchCameraAsync({ mediaTypes: 'images', quality: 1, exif: false });
  if (result.canceled || !result.assets?.length) return { canceled: true };

  const asset = result.assets[0];
  const landscape = (asset.width || 0) >= (asset.height || 0);
  const context = ImageManipulator.manipulate(asset.uri);
  // Chỉ thu nhỏ, không phóng to; kích thước 0 (hệ thống không báo) thì vẫn resize cho chắc
  if (!asset.width || Math.max(asset.width, asset.height) > MAX_SIDE) {
    context.resize(landscape ? { width: MAX_SIDE, height: null } : { width: null, height: MAX_SIDE });
  }
  const rendered = await context.renderAsync();
  const saved = await rendered.saveAsync({ format: SaveFormat.JPEG, compress: JPEG_QUALITY });
  return { photo: { uri: saved.uri, width: saved.width, height: saved.height } };
}
