// Tiện ích hình học nhẹ phía client. Đủ chính xác ở quy mô vài km (phép chiếu equirectangular).

const EARTH_RADIUS_M = 6371000;
const toRad = (deg) => (deg * Math.PI) / 180;

export function lineToLatLngs(geometry) {
  return geometry.coordinates.map(([longitude, latitude]) => ({ latitude, longitude }));
}

export function polygonToLatLngs(geometry) {
  return geometry.coordinates[0].map(([longitude, latitude]) => ({ latitude, longitude }));
}

// Chiếu về mét quanh vĩ độ tham chiếu
function project(lon, lat, refLat) {
  return [toRad(lon) * Math.cos(toRad(refLat)) * EARTH_RADIUS_M, toRad(lat) * EARTH_RADIUS_M];
}

function distancePointToSegment(p, a, b) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

export function distanceToLineMeters(point, geometry) {
  const refLat = point.latitude;
  const p = project(point.longitude, point.latitude, refLat);
  const coords = geometry.coordinates.map(([lon, lat]) => project(lon, lat, refLat));
  let best = Infinity;
  for (let i = 0; i < coords.length - 1; i += 1) {
    best = Math.min(best, distancePointToSegment(p, coords[i], coords[i + 1]));
  }
  return best;
}

// Đoạn gần điểm chạm nhất trong ngưỡng (mét); null nếu không có
export function nearestFeature(point, features, maxMeters) {
  let best = null;
  let bestDistance = maxMeters;
  for (const feature of features) {
    const d = distanceToLineMeters(point, feature.geometry);
    if (d <= bestDistance) {
      best = feature;
      bestDistance = d;
    }
  }
  return best;
}

// Ngưỡng chạm theo mức zoom: khoảng 24 điểm ảnh quy ra mét
export function tapToleranceMeters(region, screenHeightPx) {
  const metersPerPx = (region.latitudeDelta * 111320) / screenHeightPx;
  return Math.max(8, Math.min(120, metersPerPx * 24));
}

export function bboxToRegion([minLon, minLat, maxLon, maxLat], padding = 1.3) {
  return {
    latitude: (minLat + maxLat) / 2,
    longitude: (minLon + maxLon) / 2,
    latitudeDelta: Math.max((maxLat - minLat) * padding, 0.003),
    longitudeDelta: Math.max((maxLon - minLon) * padding, 0.003),
  };
}

// Vòng ngoài phủ rộng quanh Huế để tạo lớp mờ "ngoài vùng thí điểm"
export const OUTER_RING = [
  { latitude: 16.2, longitude: 107.3 },
  { latitude: 16.2, longitude: 107.9 },
  { latitude: 16.8, longitude: 107.9 },
  { latitude: 16.8, longitude: 107.3 },
];
