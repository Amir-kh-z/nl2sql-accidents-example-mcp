# -*- coding: utf-8 -*-
"""Provision the offline basemap for the מפה חיה tab (P10). One-time downloads on the DEV machine — the demo
then runs fully offline, and a wheel-only install needs NONE of this (the tab probes for the file and
degrades to the canvas style automatically).

    app\\.venv\\Scripts\\python nl2sql-accidents-plugin\\tools\\fetch_basemap.py --assets-only
    app\\.venv\\Scripts\\python nl2sql-accidents-plugin\\tools\\fetch_basemap.py [--maxzoom N] [--date YYYYMMDD]

--assets-only fetches the SMALL, COMMITTED assets into web/public/basemap-assets/ — the glyph ranges
(Latin + Hebrew + Arabic + punctuation + presentation forms, for the Noto stacks the Protomaps flavors use)
and the v4 light/dark sprites — plus the RTL text plugin into web/basemap/ (gitignored; it rides beside the
pmtiles and ships in neither git nor the wheel).
The default run ALSO fetches the go-pmtiles CLI (into a scratch dir), extracts the Israel bbox from a daily
Protomaps planet build over HTTP Range (never the planet itself), verifies the PMTiles magic + a size floor
(the 0-byte-booster lesson), and hardlinks web/basemap/* into nl2sql_roadsafety/webdist/basemap/ — the same
sync `npm run build` performs, because vite's emptyOutDir wipes webdist on every build."""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
PUBLIC = REPO / "web" / "public" / "basemap-assets"
CACHE = REPO / "web" / "basemap"
WEBDIST = REPO / "nl2sql_roadsafety" / "webdist" / "basemap"

ASSETS_BASE = "https://raw.githubusercontent.com/protomaps/basemaps-assets/main"
FONT_STACKS = ("Noto Sans Regular", "Noto Sans Medium", "Noto Sans Italic")
# 256-codepoint blocks: Latin, Latin-1/ext, Hebrew (U+05xx), Arabic (U+06xx), general punctuation (U+20xx),
# presentation forms A start + forms B (the RTL plugin shapes Arabic into these; Hebrew presentation sits in A)
GLYPH_RANGES = ("0-255", "256-511", "1280-1535", "1536-1791", "8192-8447", "64256-64511", "65024-65279")
SPRITE_FILES = tuple(f"{flavor}{suffix}" for flavor in ("light", "dark")
                     for suffix in (".json", ".png", "@2x.json", "@2x.png"))
RTL_URLS = (  # tried in order — the package moved files across versions
    "https://unpkg.com/@mapbox/mapbox-gl-rtl-text@0.3.0/dist/mapbox-gl-rtl-text.js",
    "https://unpkg.com/@mapbox/mapbox-gl-rtl-text@0.2.3/mapbox-gl-rtl-text.min.js",
    "https://unpkg.com/@mapbox/mapbox-gl-rtl-text@0.2.3/mapbox-gl-rtl-text.js",
)
ISRAEL_BBOX = "34.2,29.45,35.9,33.35"                     # lon_min,lat_min,lon_max,lat_max (WGS84)
BUILDS = "https://build.protomaps.com"
GO_PMTILES_LATEST = "https://api.github.com/repos/protomaps/go-pmtiles/releases/latest"
PMTILES_MAGIC = b"PMTiles"
SIZE_FLOOR = 20_000_000                                    # a real Israel extract is far above 20 MB


def _get(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "nl2sql-roadsafety-basemap-fetch"})
    with urlopen(req, timeout=120) as r:
        return r.read()


def _head_ok(url: str) -> bool:
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": "nl2sql-roadsafety-basemap-fetch"})
        with urlopen(req, timeout=30) as r:
            return 200 <= r.status < 300
    except Exception:  # noqa: BLE001 — a missing daily build is expected, not an error
        return False


def _save(data: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"  {dest.relative_to(REPO)}  {len(data):,} B")


def fetch_assets() -> None:
    print("glyphs (committed, web/public/basemap-assets/fonts/):")
    for stack in FONT_STACKS:
        for rng in GLYPH_RANGES:
            url = f"{ASSETS_BASE}/fonts/{stack.replace(' ', '%20')}/{rng}.pbf"
            try:
                _save(_get(url), PUBLIC / "fonts" / stack / f"{rng}.pbf")
            except Exception as e:  # noqa: BLE001 — a stack may lack a range; say so, do not die
                print(f"  MISSING {stack}/{rng}.pbf ({e}) - labels in that block would show tofu")
    print("sprites (committed, web/public/basemap-assets/sprites/v4/):")
    for name in SPRITE_FILES:
        _save(_get(f"{ASSETS_BASE}/sprites/v4/{name}"), PUBLIC / "sprites" / "v4" / name)
    print("rtl-text plugin (gitignored, web/basemap/):")
    for url in RTL_URLS:
        try:
            _save(_get(url), CACHE / "rtl-text.js")
            print(f"  from {url}")
            break
        except Exception as e:  # noqa: BLE001 — try the next candidate
            print(f"  {url} failed ({e})")
    else:
        raise SystemExit("no RTL plugin candidate URL worked - Hebrew basemap labels would render reversed")
    hebrew = PUBLIC / "fonts" / "Noto Sans Regular" / "1280-1535.pbf"
    if not hebrew.exists():
        raise SystemExit("the Hebrew glyph range (1280-1535) is missing - the street style cannot label in Hebrew")


def _pmtiles_exe(scratch: Path) -> Path:
    exe = scratch / "pmtiles.exe"
    if exe.exists():
        return exe
    rel = json.loads(_get(GO_PMTILES_LATEST))
    asset = next(a for a in rel["assets"] if "Windows_x86_64.zip" in a["name"])
    print(f"go-pmtiles {rel['tag_name']} ({asset['name']})")
    with zipfile.ZipFile(io.BytesIO(_get(asset["browser_download_url"]))) as z:
        member = next(n for n in z.namelist() if n.endswith("pmtiles.exe"))
        exe.write_bytes(z.read(member))
    return exe


def _build_date(explicit: str | None) -> str:
    if explicit:
        return explicit
    day = dt.date.today()
    for _ in range(10):
        stamp = day.strftime("%Y%m%d")
        if _head_ok(f"{BUILDS}/{stamp}.pmtiles"):
            return stamp
        day -= dt.timedelta(days=1)
    raise SystemExit("no daily Protomaps build found in the last 10 days - pass --date YYYYMMDD")


def fetch_extract(maxzoom: int, date: str | None) -> None:
    scratch = Path(tempfile.gettempdir()) / "go-pmtiles"
    scratch.mkdir(parents=True, exist_ok=True)
    exe = _pmtiles_exe(scratch)
    stamp = _build_date(date)
    out = CACHE / "israel.pmtiles"
    CACHE.mkdir(parents=True, exist_ok=True)
    cmd = [str(exe), "extract", f"{BUILDS}/{stamp}.pmtiles", str(out), f"--bbox={ISRAEL_BBOX}"]
    if maxzoom:
        cmd.append(f"--maxzoom={maxzoom}")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    verify(out)


def verify(out: Path) -> None:
    size = out.stat().st_size
    with out.open("rb") as fh:
        magic = fh.read(7)
    if magic != PMTILES_MAGIC:
        raise SystemExit(f"{out} is not a PMTiles v3 archive (magic {magic!r})")
    if size < SIZE_FLOOR:
        raise SystemExit(f"{out} is suspiciously small ({size:,} B < {SIZE_FLOOR:,}) - truncated download?")
    print(f"{out.relative_to(REPO)}  {size:,} B  magic ok")


def _served_webdists() -> list[Path]:
    """Every webdist that could be the one the app serves: this checkout's (editable installs and the repo
    itself) AND the INSTALLED package's (a wheel install — site-packages, a different folder entirely).
    Getting this wrong is silent: the download succeeds and the page still shows the canvas fallback."""
    out = [WEBDIST]
    try:
        import nl2sql_roadsafety                                        # noqa: PLC0415 — optional at fetch time
        installed = Path(nl2sql_roadsafety.__file__).resolve().parent / "webdist" / "basemap"
        if installed.parent.exists() and installed != WEBDIST:
            out.append(installed)
    except Exception as e:  # noqa: BLE001 — not installed into THIS interpreter: the checkout copy is enough
        print(f"  (nl2sql_roadsafety not importable here: {e}) - syncing the checkout copy only")
    return out


def sync() -> None:
    """web/basemap/* -> every served webdist/basemap/* as hardlinks (copy fallback across volumes) — the
    same rule as sync-basemap.mjs, plus the installed-package location for wheel installs."""
    if not CACHE.exists() or not any(f.is_file() for f in CACHE.iterdir()):
        print("web/basemap/ absent or empty - nothing to sync (the map runs in canvas fallback mode)")
        return
    for dest_dir in _served_webdists():
        dest_dir.mkdir(parents=True, exist_ok=True)
        for f in sorted(CACHE.iterdir()):
            if not f.is_file():
                continue
            dest = dest_dir / f.name
            if dest.exists():
                try:
                    dest.unlink()
                except OSError as e:                                   # the app is serving it right now
                    print(f"  SKIPPED {dest}: {e} - stop the app and re-run with --sync-only")
                    continue
            try:
                os.link(f, dest)
                how = "hardlinked"
            except OSError:
                shutil.copy2(f, dest)
                how = "copied"
            try:
                shown = dest.relative_to(REPO)
            except ValueError:
                shown = dest
            print(f"  {how} {f.name} -> {shown}  {dest.stat().st_size:,} B")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets-only", action="store_true", help="glyphs + sprites + rtl plugin, no pmtiles extract")
    ap.add_argument("--maxzoom", type=int, default=0, help="cap the extract zoom (0 = the tileset maximum)")
    ap.add_argument("--date", default=None, help="daily build YYYYMMDD (default: newest available)")
    ap.add_argument("--sync-only", action="store_true", help="just re-place web/basemap/* into webdist/basemap/")
    args = ap.parse_args()
    if args.sync_only:
        sync()
        return 0
    fetch_assets()
    if not args.assets_only:
        fetch_extract(args.maxzoom, args.date)
    sync()
    return 0


if __name__ == "__main__":
    sys.exit(main())
