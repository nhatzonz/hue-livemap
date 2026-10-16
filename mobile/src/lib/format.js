// "vừa xong", "12 phút trước", "3 giờ trước", "2 ngày trước"
export function timeAgo(isoString, now = Date.now()) {
  if (!isoString) return null;
  const seconds = Math.max(0, Math.round((now - new Date(isoString).getTime()) / 1000));
  if (seconds < 60) return 'vừa xong';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  return `${Math.round(hours / 24)} ngày trước`;
}

export function formatLength(meters) {
  if (meters == null) return '';
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}
