import { memo, useMemo } from 'react';
import { Polyline } from 'react-native-maps';

import { lineToLatLngs } from '../../lib/geo';
import { segmentStyle } from '../../theme/status';

const SELECTED_COLOR = '#FFB300';

// Một đoạn = một component memo: chọn đoạn khác chỉ vẽ lại 2 đoạn (cũ + mới), không phải toàn bộ.
const SegmentPolyline = memo(function SegmentPolyline({ geometry, segmentType, status, dimension, selected }) {
  const coordinates = useMemo(() => lineToLatLngs(geometry), [geometry]);
  const style = segmentStyle(dimension, segmentType, status);
  return (
    <>
      {selected && (
        <Polyline coordinates={coordinates} strokeColor={SELECTED_COLOR} strokeWidth={style.strokeWidth + 6} zIndex={1} />
      )}
      <Polyline
        coordinates={coordinates}
        strokeColor={style.strokeColor}
        strokeWidth={style.strokeWidth}
        lineDashPattern={style.lineDashPattern}
        // Đầu nét tròn biến mỗi gạch ngắn thành chấm tròn to; nét đứt phải dùng đầu vuông
        lineCap={style.lineDashPattern ? 'butt' : 'round'}
        zIndex={selected ? 3 : 2}
      />
    </>
  );
});

function SegmentLayer({ features, dimension, selectedCode }) {
  return features.map(({ geometry, properties }) => (
    <SegmentPolyline
      // key đổi theo trạng thái để native Polyline cập nhật nét đứt (một số nền tảng không cập nhật pattern tại chỗ)
      key={`${properties.code}-${dimension}-${properties.status.state}-${properties.status.level}`}
      geometry={geometry}
      segmentType={properties.segment_type}
      status={properties.status}
      dimension={dimension}
      selected={properties.code === selectedCode}
    />
  ));
}

export default memo(SegmentLayer);
