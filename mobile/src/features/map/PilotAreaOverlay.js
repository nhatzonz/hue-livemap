import { memo } from 'react';
import { Polygon } from 'react-native-maps';

import { OUTER_RING, polygonToLatLngs } from '../../lib/geo';

// Làm mờ phần ngoài vùng thí điểm và kẻ viền ranh giới, để không ai hiểu nhầm
// rằng khu vực không có đoạn nào là "bình thường".
function PilotAreaOverlay({ areas }) {
  return areas.map((area) => {
    const ring = polygonToLatLngs(area.geometry);
    return [
      <Polygon
        key={`${area.id}-mask`}
        coordinates={OUTER_RING}
        holes={[ring]}
        fillColor="rgba(30, 35, 45, 0.18)"
        strokeColor="transparent"
        strokeWidth={0}
        zIndex={0}
      />,
      <Polygon
        key={`${area.id}-outline`}
        coordinates={ring}
        fillColor="transparent"
        strokeColor="rgba(11, 95, 165, 0.7)"
        strokeWidth={2}
        lineDashPattern={[8, 6]}
        zIndex={0}
      />,
    ];
  });
}

export default memo(PilotAreaOverlay);
