#!/usr/bin/env python3
"""Cắt mạng lưới đường OSM thành đoạn (segment) theo quy tắc PROJECT_PLAN.md mục 3.3.

    uv run python scripts/build_segments.py [--raw FILE] [--max-m 400] [--min-m 30]

Quy tắc:
  1. Chỉ lấy đường có tên mà xe máy đi được. Phân tầng (pilot_tier):
       1 = trục chính (primary/secondary/tertiary), 2 = đường dân sinh có tên, 3 = kiệt/hẻm có tên.
     Kiệt không tên chưa đưa vào; khảo sát thực địa sẽ bổ sung (OSM thiếu tên phần lớn kiệt).
  2. Đường phố (tầng 1–2) chỉ cắt tại giao lộ với ĐƯỜNG PHỐ khác, không cắt ở mỗi đầu kiệt,
     để tránh đoạn vụn. Kiệt cắt tại mọi chỗ giao với đường đã chọn (nhánh kiệt).
  3. Ghép các way OSM nối tiếp cùng tên/cùng tầng (OSM tách way vì lý do gắn thẻ).
  4. Cắt theo ranh giới thí điểm; bỏ mẩu cụt < min-m do cắt ranh giới.
  5. Đoạn dài hơn max-m được chia đều.

Phân đoạn KHÔNG phụ thuộc tầng nào sẽ được nhập DB, nên khoá `source_ref` ổn định giữa các lần chạy
(miễn là dữ liệu OSM không đổi). Đầu ra: data/curated/segments_candidates.geojson
"""

import argparse
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from common import (
    CURATED_DIR,
    latest_raw,
    load_boundary,
    now_iso,
    read_geojson,
    to_utm,
    to_wgs84,
    write_geojson,
)
from shapely import ops
from shapely.geometry import LineString, MultiLineString, mapping

ARTERIAL = {"primary", "secondary", "tertiary", "primary_link", "secondary_link", "tertiary_link"}
LOCAL = {"residential", "unclassified", "living_street"}
ALLEY_CLASSES = LOCAL | {"service", "footway", "pedestrian"}
ALLEY_PREFIXES = ("kiệt", "hẻm", "ngõ", "ngách")
STREET_TIERS = {1, 2}


@dataclass
class Way:
    id: int
    nodes: list[int]
    coords: list[tuple[float, float]]
    tags: dict
    tier: int


@dataclass
class Piece:
    """Một đoạn liên tục giữa hai node, có thể gồm nhiều mẩu way đã ghép."""

    name: str
    tier: int
    nodes: list[int]
    coords: list[tuple[float, float]]
    refs: list[str] = field(default_factory=list)  # "w<id>[<n_đầu>..<n_cuối>]"
    way_ids: list[int] = field(default_factory=list)
    tags: dict = field(default_factory=dict)

    @property
    def start(self) -> int:
        return self.nodes[0]

    @property
    def end(self) -> int:
        return self.nodes[-1]


def classify(tags: dict) -> int | None:
    """Trả về pilot_tier, hoặc None nếu không lấy."""
    name = tags.get("name", "").strip()
    highway = tags.get("highway")
    if not name or tags.get("access") in ("private", "no") or tags.get("area") == "yes":
        return None
    if name.lower().startswith(ALLEY_PREFIXES) and highway in ALLEY_CLASSES:
        return 3
    if highway == "service" and tags.get("service") == "alley":
        return 3
    if highway in ARTERIAL:
        return 1
    if highway in LOCAL:
        return 2
    return None


def load_ways(raw: dict) -> list[Way]:
    ways = []
    for feature in raw["features"]:
        props = feature["properties"]
        tags = {k: v for k, v in props.items() if k not in ("osm_id", "osm_nodes")}
        tier = classify(tags)
        if tier is None:
            continue
        coords = [tuple(c) for c in feature["geometry"]["coordinates"]]
        ways.append(Way(props["osm_id"], props["osm_nodes"], coords, tags, tier))
    return ways


def split_ways(ways: list[Way]) -> list[Piece]:
    """Bước 2: cắt mỗi way tại các node giao cắt có ý nghĩa với tầng của nó.

    Đường phố tầng t chỉ cắt khi gặp đường phố tầng <= t (trục chính không bị cắt ở mỗi
    ngã tư với đường dân sinh, chỉ ở giao lộ với trục chính khác). Kiệt cắt tại mọi giao cắt.
    """
    tiers_at = defaultdict(dict)  # node -> {way_id: tier}
    for way in ways:
        for node in way.nodes:
            tiers_at[node][way.id] = way.tier

    def is_cut_node(way: Way, node: int) -> bool:
        others = {wid: t for wid, t in tiers_at[node].items() if wid != way.id}
        if way.tier in STREET_TIERS:
            return any(t in STREET_TIERS and t <= way.tier for t in others.values())
        return bool(others)

    pieces = []
    for way in ways:
        cut_idx = [0]
        for i in range(1, len(way.nodes) - 1):
            if is_cut_node(way, way.nodes[i]):
                cut_idx.append(i)
        cut_idx.append(len(way.nodes) - 1)
        for a, b in zip(cut_idx, cut_idx[1:], strict=False):
            if b <= a:
                continue
            nodes = way.nodes[a : b + 1]
            pieces.append(
                Piece(
                    name=way.tags["name"],
                    tier=way.tier,
                    nodes=nodes,
                    coords=way.coords[a : b + 1],
                    refs=[f"w{way.id}[{nodes[0]}..{nodes[-1]}]"],
                    way_ids=[way.id],
                    tags=way.tags,
                )
            )
    return pieces


def _reversed(piece: Piece) -> Piece:
    return Piece(
        piece.name,
        piece.tier,
        piece.nodes[::-1],
        piece.coords[::-1],
        piece.refs[::-1],
        piece.way_ids[::-1],
        piece.tags,
    )


def _blocks_merge(tier: int, other_tier: int) -> bool:
    """Mẩu tầng other_tier tại node có làm node đó thành giao lộ thật với tầng tier không."""
    if tier in STREET_TIERS:
        return other_tier in STREET_TIERS and other_tier <= tier
    return True


def _continuation_links(pieces: list[Piece]) -> dict[int, dict[int, int]]:
    """Với mỗi mẩu: {node: mẩu nối tiếp tại node đó}.

    Điều kiện nối chỉ phụ thuộc tầng/tên của các mẩu chạm node — không đổi khi ghép — nên tính một lần.
    Tại mỗi node có tối đa một cặp hợp lệ (hai nhóm cùng tầng chặn lẫn nhau; tầng thấp hơn chặn tầng cao hơn).
    """
    touching = defaultdict(set)
    ends = defaultdict(list)
    for idx, piece in enumerate(pieces):
        for node in piece.nodes:
            touching[node].add(idx)
        if piece.start != piece.end:
            ends[piece.start].append(idx)
            ends[piece.end].append(idx)

    links: dict[int, dict[int, int]] = defaultdict(dict)
    for node, idxs in ends.items():
        for x, i in enumerate(idxs):
            for j in idxs[x + 1 :]:
                a, b = pieces[i], pieces[j]
                if i == j or a.name != b.name or a.tier != b.tier:
                    continue
                if any(_blocks_merge(a.tier, pieces[k].tier) for k in touching[node] - {i, j}):
                    continue
                links[i][node] = j
                links[j][node] = i
    return links


def _join(chain: list[Piece]) -> Piece:
    first = chain[0]
    nodes, coords, refs, way_ids = (
        list(first.nodes),
        list(first.coords),
        list(first.refs),
        list(first.way_ids),
    )
    for piece in chain[1:]:
        nodes += piece.nodes[1:]
        coords += piece.coords[1:]
        refs += piece.refs
        way_ids += [w for w in piece.way_ids if w not in way_ids]
    return Piece(first.name, first.tier, nodes, coords, refs, way_ids, first.tags)


def _walk(pieces: list[Piece], links, start: int, entry_node: int | None, visited: set[int]) -> list[Piece]:
    """Đi dọc chuỗi từ `start`; mỗi mẩu được xoay chiều để nối liền mẩu trước."""
    chain, idx, node = [], start, entry_node
    while idx is not None and idx not in visited:
        visited.add(idx)
        piece = pieces[idx]
        if node is not None and piece.start != node:
            piece = _reversed(piece)
        elif node is None:
            # mẩu đầu chuỗi: hướng về phía có mẩu nối tiếp
            exits = [n for n in links.get(idx, {}) if n != piece.start]
            if not exits and links.get(idx):
                piece = _reversed(piece)
        chain.append(piece)
        node = piece.end
        idx = links.get(idx, {}).get(node)
    return chain


def merge_continuations(pieces: list[Piece]) -> list[Piece]:
    """Bước 3: ghép các mẩu cùng tên + cùng tầng nối nhau tại node không phải giao lộ thật. O(n).

    Hướng chuỗi được chuẩn hoá (chọn chiều có danh sách ref nhỏ hơn) để kết quả không phụ thuộc thứ tự duyệt.
    """
    links = _continuation_links(pieces)
    visited: set[int] = set()
    merged = []
    # Chuỗi hở: bắt đầu từ mẩu có tối đa một liên kết
    for idx in range(len(pieces)):
        if idx not in visited and len(links.get(idx, {})) <= 1:
            merged.append(_walk(pieces, links, idx, None, visited))
    # Còn lại là chuỗi khép kín (vòng): cắt tại mẩu có chỉ số nhỏ nhất
    for idx in range(len(pieces)):
        if idx not in visited:
            merged.append(_walk(pieces, links, idx, pieces[idx].start, visited))

    result = []
    for chain in merged:
        piece = _join(chain)
        backward = _reversed(piece)
        result.append(backward if backward.refs < piece.refs else piece)
    return result


def neighbour_names(pieces: list[Piece]) -> dict[int, set[str]]:
    """Tên các đường phố chạm vào mỗi node (để mô tả 'từ … đến …')."""
    names = defaultdict(set)
    for piece in pieces:
        if piece.tier in STREET_TIERS:
            for node in piece.nodes:
                names[node].add(piece.name)
    return names


def _pick_name(candidates: set[str], own: str) -> str | None:
    others = sorted(n for n in candidates if n != own)
    return others[0] if others else None


def finalize(pieces: list[Piece], boundary, max_m: float, min_m: float) -> list[dict]:
    """Bước 4–5: cắt theo ranh giới, chia đoạn dài, sinh feature GeoJSON."""
    boundary_utm = to_utm(boundary)
    node_names = neighbour_names(pieces)
    features = []

    for piece in pieces:
        line_utm = to_utm(LineString(piece.coords))
        clipped = line_utm.intersection(boundary_utm)
        if clipped.is_empty:
            continue
        parts = list(clipped.geoms) if isinstance(clipped, MultiLineString) else [clipped]
        parts = [p for p in parts if isinstance(p, LineString)]
        was_clipped = not math.isclose(sum(p.length for p in parts), line_utm.length, rel_tol=1e-6)
        from_name = _pick_name(node_names[piece.start], piece.name)
        to_name = _pick_name(node_names[piece.end], piece.name)

        for part_no, part in enumerate(parts, start=1):
            if was_clipped and part.length < min_m:
                continue  # mẩu cụt do cắt ranh giới
            if part.length < min_m and from_name and from_name == to_name:
                continue  # đoạn nối ngang dải phân cách của đường đôi (hai đầu cùng một đường)
            n_sub = max(1, math.ceil(part.length / max_m))
            for k in range(n_sub):
                sub = ops.substring(part, k * part.length / n_sub, (k + 1) * part.length / n_sub)
                ref = "+".join(piece.refs)
                if len(parts) > 1:
                    ref += f"@clip{part_no}"
                if n_sub > 1:
                    ref += f"#{k + 1}/{n_sub}"
                flags = []
                if sub.length < min_m:
                    flags.append("short")
                if was_clipped:
                    flags.append("clipped_by_boundary")
                features.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "source_ref": ref,
                            "name": piece.name,
                            "pilot_tier": piece.tier,
                            "segment_type": segment_type(piece),
                            "highway": piece.tags.get("highway"),
                            "oneway": piece.tags.get("oneway") == "yes",
                            "from_name": from_name if k == 0 else None,
                            "to_name": to_name if k == n_sub - 1 else None,
                            "part": f"{k + 1}/{n_sub}" if n_sub > 1 else None,
                            "length_m": round(sub.length, 1),
                            "osm_way_ids": piece.way_ids,
                            "qa_flags": flags,
                        },
                        "geometry": mapping(to_wgs84(sub)),
                    }
                )
    features.sort(
        key=lambda f: (f["properties"]["pilot_tier"], f["properties"]["name"], f["properties"]["source_ref"])
    )
    return features


def segment_type(piece: Piece) -> str:
    if piece.tags.get("bridge") == "yes":
        return "bridge"
    if piece.tier == 3:
        return "hem" if piece.name.lower().startswith(("hẻm", "ngõ", "ngách")) else "kiet"
    return "street"


def build(raw: dict, boundary, max_m: float = 400.0, min_m: float = 30.0) -> list[dict]:
    ways = load_ways(raw)
    pieces = merge_continuations(split_ways(ways))
    return finalize(pieces, boundary, max_m, min_m)


def summarize(features: list[dict]) -> str:
    by_tier = Counter(f["properties"]["pilot_tier"] for f in features)
    length_by_tier = Counter()
    for f in features:
        length_by_tier[f["properties"]["pilot_tier"]] += f["properties"]["length_m"]
    labels = {1: "trục chính", 2: "đường dân sinh", 3: "kiệt/hẻm"}
    lines = [f"Tổng số đoạn: {len(features)}"]
    for tier in sorted(by_tier):
        n = by_tier[tier]
        km = length_by_tier[tier] / 1000
        lines.append(f"  tầng {tier} ({labels[tier]}): {n} đoạn · {km:.1f} km · TB {km * 1000 / n:.0f} m")
    flags = Counter(flag for f in features for flag in f["properties"]["qa_flags"])
    lines.append(f"Cờ QA: {dict(flags)}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--raw", type=Path, help="GeoJSON OSM thô (mặc định: file mới nhất trong data/raw)")
    parser.add_argument("--max-m", type=float, default=400.0)
    parser.add_argument("--min-m", type=float, default=30.0)
    args = parser.parse_args()

    raw_path = args.raw or latest_raw("osm_highways")
    raw = read_geojson(raw_path)
    boundary, boundary_meta = load_boundary()
    features = build(raw, boundary, args.max_m, args.min_m)

    out = CURATED_DIR / "segments_candidates.geojson"
    write_geojson(
        out,
        {
            "type": "FeatureCollection",
            "metadata": {
                "license": "ODbL-1.0",
                "attribution": "© OpenStreetMap contributors",
                "generated_at": now_iso(),
                "raw_file": raw_path.name,
                "osm_base": raw.get("metadata", {}).get("osm_base"),
                "boundary": boundary_meta.get("method"),
                "rules": {"max_m": args.max_m, "min_m": args.min_m},
                "status": "draft — chưa khảo sát thực địa",
            },
            "features": features,
        },
    )
    print(summarize(features))
    print(f"Đã lưu: {out}")


if __name__ == "__main__":
    main()
