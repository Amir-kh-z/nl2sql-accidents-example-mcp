# -*- coding: utf-8 -*-
"""One-off (repo-side, NOT in the wheel): fetch the Natural Earth 1:10m admin-0 countries layer (public domain),
keep the Israel feature, simplify it (Douglas-Peucker, degrees) and write it as the plugin's single outline file
`nl2sql_roadsafety/data/israel.json` — imported by the Vite page as a JSON module and read by the matplotlib twin.

Network is needed ONCE, here; the wheel and the page never fetch anything at runtime. When the download fails the
script falls back to the P0 spike's coarse outline (106 vertices) and says so in the file's properties.

    python tools/fetch_outline.py [--tolerance 0.0015] [--fallback c:\\tmp\\spike-mod\\web\\src\\israel.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

SOURCES = [
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson",
    "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",   # zip: not parsed here, listed for the record
]
OUT = Path(__file__).resolve().parents[1] / "nl2sql_roadsafety" / "data" / "israel.json"
SPIKE = Path(r"c:\tmp\spike-mod\web\src\israel.json")


def _dp(points, tol):
    """Douglas-Peucker on a ring of [lon, lat] pairs (planar, degrees — fine at Israel's latitudes for an outline)."""
    if len(points) < 3:
        return list(points)
    (x0, y0), (x1, y1) = points[0], points[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = (dx * dx + dy * dy) ** 0.5
    best, idx = -1.0, 0
    for i in range(1, len(points) - 1):
        x, y = points[i]
        d = abs(dy * x - dx * y + x1 * y0 - y1 * x0) / norm if norm else ((x - x0) ** 2 + (y - y0) ** 2) ** 0.5
        if d > best:
            best, idx = d, i
    if best > tol:
        left = _dp(points[: idx + 1], tol)
        right = _dp(points[idx:], tol)
        return left[:-1] + right
    return [points[0], points[-1]]


def simplify_ring(ring, tol):
    closed = ring[0] == ring[-1]
    pts = ring[:-1] if closed else ring
    if len(pts) > 4:
        # split at the farthest point from pts[0] so DP has two open chains
        far = max(range(len(pts)), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
        a = _dp(pts[: far + 1], tol)
        b = _dp(pts[far:] + [pts[0]], tol)
        pts = a[:-1] + b[:-1]
    out = [[round(x, 5), round(y, 5)] for x, y in pts]
    return out + [out[0]]


def simplify_geometry(geom, tol):
    if geom["type"] == "Polygon":
        rings = [simplify_ring(r, tol) for r in geom["coordinates"]]
        return {"type": "Polygon", "coordinates": [r for r in rings if len(r) >= 4]}
    if geom["type"] == "MultiPolygon":
        polys = []
        for poly in geom["coordinates"]:
            rings = [simplify_ring(r, tol) for r in poly]
            rings = [r for r in rings if len(r) >= 4]
            if rings:
                polys.append(rings)
        return {"type": "MultiPolygon", "coordinates": polys}
    raise SystemExit(f"unexpected geometry type {geom['type']}")


def n_vertices(geom):
    if geom["type"] == "Polygon":
        return sum(len(r) for r in geom["coordinates"])
    return sum(len(r) for poly in geom["coordinates"] for r in poly)


def fetch_israel():
    url = SOURCES[0]
    print(f"downloading {url} ...")
    with urllib.request.urlopen(url, timeout=120) as r:      # noqa: S310 — a fixed public-domain URL
        data = json.loads(r.read().decode("utf-8"))
    for f in data["features"]:
        p = f.get("properties", {})
        if p.get("ADM0_A3") == "ISR" or p.get("ISO_A3") == "ISR" or p.get("NAME") == "Israel":
            return f
    raise SystemExit("Israel feature not found in the Natural Earth layer")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tolerance", type=float, default=0.0015, help="Douglas-Peucker tolerance in degrees")
    ap.add_argument("--fallback", default=str(SPIKE))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out)
    try:
        feat = fetch_israel()
        raw_n = n_vertices(feat["geometry"])
        geom = simplify_geometry(feat["geometry"], args.tolerance)
        props = {"name": "Israel", "source": "Natural Earth 1:10m admin-0 countries (public domain)",
                 "simplified": {"tolerance_deg": args.tolerance, "vertices_raw": raw_n, "vertices": n_vertices(geom)}}
    except Exception as exc:  # noqa: BLE001 — the fallback IS the handling
        print(f"download failed ({exc}); using the P0 spike outline {args.fallback}", file=sys.stderr)
        spike = json.loads(Path(args.fallback).read_text(encoding="utf-8"))
        feat = spike["features"][0]
        geom = feat["geometry"]
        props = {"name": "Israel", "source": "Natural Earth 1:110m (P0 spike fallback, public domain)",
                 "simplified": {"tolerance_deg": None, "vertices_raw": n_vertices(geom), "vertices": n_vertices(geom)},
                 "fallback": True}
    fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": props, "geometry": geom}]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size:,} bytes, {props['simplified']['vertices']} vertices, {geom['type']})")


if __name__ == "__main__":
    main()
