# -*- coding: utf-8 -*-
"""The page contract: the entry-point name IS the URL segment and must equal the Vite base; the built page is
committed and RTL; the outline is the one Natural Earth file (no CBS data); page.py is stdlib-only."""
from __future__ import annotations

import ast
import json
import re
from importlib.metadata import entry_points
from pathlib import Path

import pytest

from nl2sql_roadsafety import page as page_module
from helpers import needs_install

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "nl2sql_roadsafety"


def test_the_pages_api_client_posts_the_real_module_id():
    """The rename's last hiding place (2026-09-09): `api.js`'s MODULE constant is the id every runAction
    POSTs, so if it drifts from MODULE.name the page loads, renders its tabs — and every action fails with
    "No module named '<old>' is installed". Nothing else pins it: the Python suite never exercises the
    page's HTTP path, and the entry-point/Vite pins above cover the URL, not the payload."""
    from nl2sql_roadsafety import MODULE

    api = (REPO / "web" / "src" / "api.js").read_text(encoding="utf-8")
    declared = re.search(r'const\s+MODULE\s*=\s*"([a-z0-9_]+)"', api).group(1)
    assert declared == MODULE.name, f"api.js posts {declared!r}, the module registers as {MODULE.name!r}"
    # and the SHIPPED bundle must carry it too — a stale webdist would fail the same way at runtime
    bundle = "".join(p.read_text(encoding="utf-8", errors="ignore")
                     for p in (PKG / "webdist" / "assets").glob("index-*.js"))
    assert f'"{MODULE.name}"' in bundle or f"'{MODULE.name}'" in bundle


def test_entry_point_name_equals_the_vite_base():
    vite = (REPO / "web" / "vite.config.js").read_text(encoding="utf-8")
    base = re.search(r'base:\s*"(/page/[a-z0-9._-]+/)"', vite).group(1)
    assert base == "/page/roadsafety/"
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    # the entry-point NAME is the URL segment — it must equal the Vite base's segment, not just exist
    assert re.search(r'\[project\.entry-points\."nl2sql\.pages"\]\s*\nroadsafety = "nl2sql_roadsafety\.page:page"', pyproject)
    assert re.search(r'outDir:\s*"\.\./nl2sql_roadsafety/webdist"', vite)


def test_page_bundle_version_tracks_the_package():
    import tomllib
    from nl2sql_roadsafety import __version__
    with (REPO / "pyproject.toml").open("rb") as fh:
        assert tomllib.load(fh)["project"]["version"] == __version__
    assert json.loads((REPO / "web" / "package.json").read_text(encoding="utf-8"))["version"] == __version__
    bundle = "".join(a.read_text(encoding="utf-8", errors="ignore") for a in (PKG / "webdist" / "assets").glob("*.js"))
    assert f'"{__version__}"' in bundle                                       # baked in by Vite `define`


def test_page_hook_is_stdlib_only_and_points_at_the_built_page():
    tree = ast.parse((PKG / "page.py").read_text(encoding="utf-8"))
    imports = {n.names[0].name.split(".")[0] if isinstance(n, ast.Import) else n.module.split(".")[0]
               for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))}
    assert imports == {"pathlib"}
    p = page_module.page()
    assert p["label"] == "🚦 מעבדת הבטיחות בדרכים"
    assert Path(p["path"]) == PKG / "webdist"


def test_built_page_is_committed_rtl_and_uses_the_base():
    index = PKG / "webdist" / "index.html"
    assert index.exists(), "run `cd web; npm install; npm run build` — the built page is committed"
    html = index.read_text(encoding="utf-8")
    assert 'dir="rtl"' in html and 'lang="he"' in html
    assert "/page/roadsafety/assets/" in html
    assets = list((PKG / "webdist" / "assets").glob("*.js"))
    assert assets and any(a.stat().st_size > 50_000 for a in assets)
    bundle = "".join(a.read_text(encoding="utf-8", errors="ignore") for a in assets)
    assert "/api/modules/run" in bundle and "leaflet" in bundle.lower()
    # POLICY CHANGE 2026-09-06 (instructor): the page no longer must work offline — an online OSM tile
    # basemap is now permitted (MapView adds tile.openstreetmap.org with an offline degradation path).
    # The old absolute pin (`"tile.openstreetmap" not in bundle`) enforced the offline rule; the LICENSE
    # pin replaces it, and it holds both before and after the next build: any OSM reference in the bundle
    # must carry the OSM attribution string (the מפה חיה pmtiles style already carried one).
    if "openstreetmap" in bundle.lower():
        assert "© OpenStreetMap" in bundle


def test_outline_is_natural_earth_inside_israel_bbox_and_small():
    path = PKG / "data" / "israel.json"
    fc = json.loads(path.read_text(encoding="utf-8"))
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) == 1
    f = fc["features"][0]
    assert "Natural Earth" in f["properties"]["source"]
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    pts = [p for poly in polys for ring in poly for p in ring]
    assert 100 <= len(pts) <= 5000 and path.stat().st_size < 200_000
    assert all(29.0 <= lat <= 34.0 and 34.0 <= lon <= 36.0 for lon, lat in pts)


def test_basemap_never_ships_and_the_committed_assets_do():
    """P10, the three leak guards asserted at the source level: .gitignore, exclude-package-data and
    MANIFEST all name the basemap; the SMALL committed assets (glyphs incl. the Hebrew range, sprites)
    exist in web/public/ and ride into webdist on every build; the lazy map chunk exists and is committed.
    (Since the 2026-09-06 policy change the bundle MAY name tile.openstreetmap.org — the attribution pin
    in test_built_page_is_committed_rtl_and_uses_the_base covers that; this test guards the local basemap
    leak paths only.)"""
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "web/basemap/" in gitignore and "nl2sql_roadsafety/webdist/basemap/" in gitignore
    manifest = (REPO / "MANIFEST.in").read_text(encoding="utf-8")
    assert "prune nl2sql_roadsafety/webdist/basemap" in manifest and "global-exclude *.pmtiles" in manifest
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "exclude-package-data" in pyproject and "webdist/basemap/*" in pyproject
    hebrew = REPO / "web" / "public" / "basemap-assets" / "fonts" / "Noto Sans Regular" / "1280-1535.pbf"
    assert hebrew.exists() and hebrew.stat().st_size > 10_000, "the Hebrew glyph range must be committed"
    assert (REPO / "web" / "public" / "basemap-assets" / "sprites" / "v4" / "light.json").exists()
    built = PKG / "webdist" / "basemap-assets" / "fonts" / "Noto Sans Regular" / "1280-1535.pbf"
    assert built.exists(), "run `cd web; npm run build` — public/ assets ride into webdist"
    chunks = list((PKG / "webdist" / "assets").glob("MapTab-*.js"))
    assert chunks and chunks[0].stat().st_size > 500_000, "the lazy map chunk must be built and committed"


@needs_install
def test_pages_entry_point_resolves_to_the_hook():
    eps = [ep for ep in entry_points(group="nl2sql.pages") if ep.name == "roadsafety"]
    assert eps and eps[0].load()() == page_module.page()


@needs_install
def test_discovery_offers_the_page_without_problems():
    from nl2sql_engine.modules import discover_pages
    pages, problems = discover_pages()
    assert not [p for p in problems if p.name == "roadsafety"], problems
    found = next((p for p in pages if p.name == "roadsafety"), None)
    assert found is not None and found.label == "🚦 מעבדת הבטיחות בדרכים" and Path(found.path) == PKG / "webdist"
