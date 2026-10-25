// P10: the basemap modes and the probe that picks between them.
// "street" = the offline PMTiles Israel extract served from this page's own static dir over HTTP Range,
// with vendored glyphs/sprites and the RTL text plugin for correct Hebrew labels.
// "osm" = ONLINE OpenStreetMap raster tiles — the fallback when the local PMTiles extract is missing.
// POLICY CHANGE (2026-09-06, instructor decision): the page is no longer required to work offline, so a
// remote tile server is now permitted; a wheel-only install gets real streets instead of the bare canvas.
// "canvas" = the dark data-canvas built from the SAME bundled Israel outline the Leaflet map and
// matplotlib use — ZERO symbol layers, no glyphs, no sprite, no network: still the `?basemap=off` mode
// and the final fallback if constructing another style throws.
import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import { layers as basemapLayers, namedFlavor } from "@protomaps/basemaps";
import outline from "../../../../nl2sql_roadsafety/data/israel.json";

export const BASE = import.meta.env.BASE_URL;                     // "/page/accidents/"
// MapLibre REJECTS a style whose sprite URL is not absolute ("Invalid sprite URL ... must be absolute",
// found live in P10) — build every style URL on the page's own origin.
const ABS = () => window.location.origin + BASE;
export const ISRAEL_BOUNDS = [[33.8, 29.25], [36.2, 33.55]];      // [[lonW, latS], [lonE, latN]]

let protocolAdded = false;
export function ensurePmtilesProtocol() {
  if (protocolAdded) return;
  const protocol = new Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);
  protocolAdded = true;
}

let rtlRequested = false;
export function ensureRtlPlugin() {
  // Hebrew basemap labels render reversed without the plugin; lazy = loaded only when RTL text appears.
  if (rtlRequested) return;
  rtlRequested = true;
  try {
    maplibregl.setRTLTextPlugin(`${ABS()}basemap/rtl-text.js`, true);
  } catch { /* already set by a previous style — fine */ }
}

/** "street" | "osm" | "canvas" — HEAD-probe the pmtiles; `?basemap=off` forces the canvas (demo/debug
 * knob). A missing/short extract falls back to online OSM raster (2026-09-06: offline no longer required). */
export async function probeBasemap() {
  if (new URLSearchParams(window.location.search).get("basemap") === "off") return "canvas";
  try {
    const r = await fetch(`${BASE}basemap/israel.pmtiles`, { method: "HEAD" });
    const len = Number(r.headers.get("content-length") || 0);
    return r.ok && len > 1_000_000 ? "street" : "osm";
  } catch {
    return "osm";
  }
}

export function flavorForTheme() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function canvasStyle() {
  return {
    version: 8,
    sources: { outline: { type: "geojson", data: outline } },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": "#0b1016" } },
      { id: "land", type: "fill", source: "outline", paint: { "fill-color": "#151d26" } },
      { id: "coast", type: "line", source: "outline", paint: { "line-color": "#3d4c5c", "line-width": 1.1 } },
    ],
  };
}

export function streetStyle(flavorName) {
  ensureRtlPlugin();
  return {
    version: 8,
    glyphs: `${ABS()}basemap-assets/fonts/{fontstack}/{range}.pbf`,
    sprite: `${ABS()}basemap-assets/sprites/v4/${flavorName}`,
    sources: {
      protomaps: {
        type: "vector",
        url: `pmtiles://${ABS()}basemap/israel.pmtiles`,
        attribution: "© OpenStreetMap",
      },
    },
    layers: basemapLayers("protomaps", namedFlavor(flavorName), { lang: "he" }),
  };
}

// Online OSM raster (policy change 2026-09-06: online tile layers are permitted). No glyphs/sprite
// needed — a single raster layer; the tile-usage policy asks for attribution, carried by CreditBadge.
export function osmStyle() {
  return {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        maxzoom: 19,
        attribution: "© OpenStreetMap",
      },
    },
    layers: [{ id: "osm", type: "raster", source: "osm" }],
  };
}

export function styleFor(mode) {
  if (mode === "street") return streetStyle(flavorForTheme());
  if (mode === "osm") {
    try { return osmStyle(); } catch { return canvasStyle(); }      // canvas stays the final fallback
  }
  return canvasStyle();
}
