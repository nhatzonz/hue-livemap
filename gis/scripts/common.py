"""Tiện ích dùng chung cho pipeline GIS: đường dẫn, Overpass, phép chiếu mét."""

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import shapely
from pyproj import Transformer
from shapely.geometry import shape

GIS_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = GIS_DIR / "data" / "raw"
CURATED_DIR = GIS_DIR / "data" / "curated"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "hue-livemap-gis/0.1 (pilot data preparation)"

OSM_LICENSE = {
    "source": "OpenStreetMap via Overpass API",
    "license": "ODbL-1.0",
    "attribution": "© OpenStreetMap contributors",
}

# Huế ≈ 107.58°E → UTM zone 48N. Dùng để tính chiều dài/buffer theo mét.
_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32648", always_xy=True)
_to_wgs = Transformer.from_crs("EPSG:32648", "EPSG:4326", always_xy=True)


def _project(transformer: Transformer, geom):
    return shapely.transform(geom, lambda x, y: transformer.transform(x, y), interleaved=False)


def to_utm(geom):
    return _project(_to_utm, geom)


def to_wgs84(geom):
    return _project(_to_wgs, geom)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def overpass(query: str, retries: int = 3) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    request = urllib.request.Request(OVERPASS_URL, data=data, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)
        except Exception as exc:  # noqa: BLE001 — Overpass hay quá tải, thử lại có giãn cách
            if attempt == retries:
                raise
            wait = 15 * attempt
            print(f"Overpass lỗi ({exc}); thử lại sau {wait}s…", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def read_geojson(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_geojson(path: Path, collection: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collection, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def load_boundary(path: Path | None = None):
    """Trả về (polygon WGS84, metadata) của ranh giới thí điểm."""
    data = read_geojson(path or CURATED_DIR / "pilot_boundary.geojson")
    return shape(data["features"][0]["geometry"]), data.get("metadata", {})


def latest_raw(prefix: str) -> Path:
    candidates = sorted(RAW_DIR.glob(f"{prefix}_*.geojson"))
    if not candidates:
        raise SystemExit(f"Không tìm thấy {RAW_DIR}/{prefix}_*.geojson, hãy chạy fetch_osm.py trước")
    return candidates[-1]
