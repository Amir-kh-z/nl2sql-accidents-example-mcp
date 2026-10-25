// P10: pure deck.gl layer builders. The cloud rides binary attributes (one Float32Array upload) and is
// filtered ON THE GPU — year range as a filter value, severity/day-night as filter categories — so the year
// animation and every checkbox re-render without re-uploading or re-fetching anything.
import { IconLayer, ScatterplotLayer } from "@deck.gl/layers";
import { DataFilterExtension } from "@deck.gl/extensions";

export const SEV_COLORS = { 1: [232, 80, 66], 2: [247, 147, 30], 3: [45, 168, 152] };   // fatal / severe / slight
export const SEV_LABELS = { 1: "קטלנית", 2: "קשה", 3: "קלה" };
export const NIGHT_LABELS = { 0: "יום", 1: "לילה", 2: "לא קודד" };
// The instructor's palette rule (P10 review): hues belong to MEANINGS only — severity on the dots, the
// diverging scale on excess. Site marks are NEUTRAL graphite: shape says the entity (square = segment,
// filled circle = non-urban junction, hollow circle = urban junction), intensity says the count.
export const SITE_NEUTRAL = [44, 55, 68];
export const SITE_LABELS = { segments: "מקטעים", njunctions: "צמתים לא-עירוניים", ujunctions: "צמתים עירוניים" };
const GREY = [139, 149, 158];
// ONE diverging ramp for excess — hotspot_map's exact hexes (blue = below the model, red = above);
// counts NEVER use it: counts get an intensity ramp within each layer's own hue.
export const DIVERGING = [[29, 78, 216], [147, 197, 253], [229, 231, 235], [252, 165, 165], [185, 28, 28]];

function shade(base, q) {          // q in [0,1]: 0 = light (few), 1 = the layer's full hue (many)
  const w = 0.72 * (1 - Math.max(0, Math.min(1, q)));
  return base.map((c) => Math.round(c + (255 - c) * w));
}

// Color = distance from the model expectation in UNITS OF THE SITE'S OWN NB UNCERTAINTY (the same concept
// as the significance ring and the panel verdicts, graduated). Raw-excess normalization by max|excess| let
// one +40 outlier own the scale — the blue half never appeared (instructor's catch). Z90 = 1.6449.
export function excessZ(d) {
  // sd from the UPPER half only: nb_interval floors lo90 at 0, so (hi-lo)/2Z understates sd for low-mu
  // segments and inflates |z| up to ~1.4x (sweep C6). Parity with map_scene._excess_hex.
  const sd = Math.max(0.5, ((d.hi90 || 0) - (d.mu || 0)) / 1.6449);
  return ((d.accidents || 0) - (d.mu || 0)) / sd;
}

export function divergingByZ(z) {
  if (z <= -2) return DIVERGING[0];
  if (z <= -0.75) return DIVERGING[1];
  if (z < 0.75) return DIVERGING[2];
  if (z < 2) return DIVERGING[3];
  return DIVERGING[4];
}

export function siteFill(kind, d, mode, emax, vmax) {
  if (mode === "excess" && kind === "segments" && d.excess != null) {
    return divergingByZ(excessZ(d));
  }
  return shade(SITE_NEUTRAL, Math.sqrt((d.accidents || 0) / (vmax || 1)));
}

/** One-time typed-array build per map_scene envelope. */
export function cloudArrays(cloud) {
  const n = cloud.n || 0;
  const pos = new Float32Array(n * 2);
  for (let i = 0; i < n; i += 1) {
    pos[i * 2] = cloud.lon[i];
    pos[i * 2 + 1] = cloud.lat[i];
  }
  return { n, pos, year: cloud.year, sev: cloud.sev, night: cloud.night };
}

export function cloudLayer(arrs, filters) {
  const sevOn = [1, 2, 3].filter((s) => filters.sev[s]);
  const nightOn = [0, 1, 2].filter((s) => filters.night[s]);
  return new ScatterplotLayer({
    id: "cloud",
    data: { length: arrs.n, attributes: { getPosition: { value: arrs.pos, size: 2 } } },
    getFillColor: (o, { index }) => SEV_COLORS[arrs.sev[index]] || GREY,
    getFilterValue: (o, { index }) => arrs.year[index],
    getFilterCategory: (o, { index }) => [arrs.sev[index], arrs.night[index]],
    filterRange: [filters.yearLo, filters.yearHi],
    filterCategories: [sevOn, nightOn],
    extensions: [new DataFilterExtension({ filterSize: 1, categorySize: 2 })],
    radiusUnits: "meters",
    getRadius: 55,
    radiusMinPixels: 1.1,
    radiusMaxPixels: 5,
    opacity: 0.5,
    pickable: true,                 // hover = year · severity · day/night (all already client-side; row-level
    updateTriggers: { getFillColor: [arrs], getFilterValue: [arrs], getFilterCategory: [arrs] },   // display is permitted)
  });
}

// SHAPE = entity class (the instructor's UI call): SQUARES for segments — the only model-capable entity —
// circles for junctions. Size stays counts in both. deck's ScatterplotLayer draws circles only, so the
// squares ride an IconLayer over a tiny generated atlas (filled square + a ring square for
// significant/selected), tinted per-datum via mask.
let ATLAS = null;
const ICON_MAP = {
  square: { x: 0, y: 0, width: 64, height: 64, mask: true },
  frame: { x: 64, y: 0, width: 64, height: 64, mask: true },
};

function iconAtlas() {
  if (ATLAS) return ATLAS;
  const c = document.createElement("canvas");
  c.width = 128; c.height = 64;
  const g = c.getContext("2d");
  g.fillStyle = "#fff";
  g.fillRect(6, 6, 52, 52);
  g.strokeStyle = "#fff";
  g.lineWidth = 10;
  g.strokeRect(64 + 11, 11, 42, 42);
  ATLAS = c;
  return ATLAS;
}

// Marks are sized in METERS (clamped in pixels): at national zoom they shrink to unobtrusive dots and the
// severity cloud reads; zoomed to a corridor they grow into full click targets. Fixed-pixel marks piled
// into a solid blob over the dense center (the instructor's "does not look good").
function markerRadius(d, vmax) { return 550 + 2600 * Math.sqrt((d.accidents || 0) / vmax); }

/** Clickable site marks. Counts mode: intensity ramp in the layer's hue. Excess mode (segments only):
 *  the diverging blue↔red by excess, white ring = significant. Returns an ARRAY of layers. */
export function siteLayers(kind, entries, selectedKey, onPick, mode) {
  const placed = entries.filter((e) => e.lat != null && e.lon != null);
  const vmax = Math.max(1, ...placed.map((e) => e.accidents || 0));
  const emax = Math.max(1e-9, ...placed.map((e) => Math.abs(e.excess || 0)));
  if (kind === "segments") {
    const ringOn = (d) => d.site_key === selectedKey || (mode === "excess" && d.significant);
    return [
      new IconLayer({
        id: `sites-${kind}`,
        data: placed,
        iconAtlas: iconAtlas(),
        iconMapping: ICON_MAP,
        getIcon: () => "square",
        getPosition: (d) => [d.lon, d.lat],
        getSize: (d) => 2 * markerRadius(d, vmax),
        sizeUnits: "meters",
        sizeMinPixels: 7,
        sizeMaxPixels: 30,
        getColor: (d) => [...siteFill(kind, d, mode, emax, vmax), d.site_key === selectedKey ? 240 : 170],
        pickable: true,
        onClick: (info) => { if (info.object && onPick) onPick(info.object, kind); },
        updateTriggers: { getColor: [selectedKey, mode] },
      }),
      new IconLayer({
        // doubles as the CONSTANT square outline: a pale square on a pale basemap is invisible without
        // one (the junction circles never "vanished" precisely because circles carry a stroke)
        id: `sites-${kind}-ring`,
        data: placed,
        iconAtlas: iconAtlas(),
        iconMapping: ICON_MAP,
        getIcon: () => "frame",
        getPosition: (d) => [d.lon, d.lat],
        getSize: (d) => (ringOn(d) ? 2.3 : 2.06) * markerRadius(d, vmax),
        sizeUnits: "meters",
        sizeMinPixels: 8,
        sizeMaxPixels: 34,
        getColor: (d) => (ringOn(d) ? [255, 255, 255, d.site_key === selectedKey ? 255 : 225]
                                    : [44, 55, 68, 135]),
        pickable: false,
        updateTriggers: { getColor: [selectedKey, mode], getSize: [selectedKey, mode] },
      }),
    ];
  }
  const hollow = kind === "ujunctions";                       // urban = hollow ring, non-urban = filled
  return [new ScatterplotLayer({
    id: `sites-${kind}`,
    data: placed,
    getPosition: (d) => [d.lon, d.lat],
    getRadius: (d) => markerRadius(d, vmax),
    radiusUnits: "meters",
    radiusMinPixels: 3.5,
    radiusMaxPixels: 15,
    getFillColor: (d) => [...siteFill(kind, d, mode, emax, vmax),
                          d.site_key === selectedKey ? 240 : (hollow ? 40 : 150)],
    stroked: true,
    getLineColor: (d) => (d.site_key === selectedKey ? [255, 255, 255, 255]
      : [...shade(SITE_NEUTRAL, Math.sqrt((d.accidents || 0) / vmax)), 230]),
    getLineWidth: (d) => (d.site_key === selectedKey ? 2.5 : (hollow ? 2 : 1)),
    lineWidthUnits: "pixels",
    pickable: true,
    onClick: (info) => { if (info.object && onPick) onPick(info.object, kind); },
    updateTriggers: { getFillColor: [selectedKey, mode], getLineColor: [selectedKey],
                      getLineWidth: [selectedKey] },
  })];
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const TOOLTIP_STYLE = { backgroundColor: "rgba(13,17,23,0.92)", color: "#e6edf3", borderRadius: "8px",
                        padding: "6px 9px", maxWidth: "300px" };

/** Hover tooltips: site circles carry the ranking line; cloud points carry the accident's own year,
 *  severity and day/night (the columns the payload ships — row-level display is permitted; fuller drill-down
 *  lives in the site panel and hotspot_map's points). ASCII hyphens only — digit ranges flip under bidi
 *  otherwise (the P8/P9 checklist for every new surface). */
export function tooltipFor(info, arrs) {
  if (info.layer && info.layer.id === "cloud") {
    const i = info.index;
    if (!arrs || i == null || i < 0) return null;
    const html = `<div class="deck-tooltip" dir="rtl">`
      + `<div><b>תאונה ${esc(SEV_LABELS[arrs.sev[i]] || "")}</b> · <span dir="ltr">${esc(arrs.year[i])}</span>`
      + ` · ${esc(NIGHT_LABELS[arrs.night[i]] || "")}</div>`
      + `<div class="muted">פרופיל מלא: לחיצה על עיגול אתר</div>`
      + `</div>`;
    return { html, style: TOOLTIP_STYLE };
  }
  const d = info.object;
  if (!d || !d.site_key) return null;
  const kind = String(info.layer?.id || "").replace("sites-", "");
  const model = d.excess != null
    ? `<div>צפוי <span dir="ltr">${esc(d.mu)}</span> · עודף <span dir="ltr">${esc(d.excess > 0 ? `+${d.excess}` : d.excess)}</span>`
      + ` · EB <span dir="ltr">${esc(d.eb)}</span>${d.significant ? " · <b>מובהק</b>" : ""}</div>`
    : "";
  const html = `<div class="deck-tooltip" dir="rtl">`
    + `<div><b>#${esc(d.rank)}</b> · ${esc(d.label)}</div>`
    + `<div><span dir="ltr">${esc(d.accidents)}</span> תאונות עם נפגעים · <span dir="ltr">${esc(d.ksi_accidents)}</span> KSI</div>`
    + model
    + `<div class="muted">${esc(SITE_LABELS[kind] || "")} · לחיצה לפרופיל האתר</div>`
    + `</div>`;
  return { html, style: TOOLTIP_STYLE };
}
