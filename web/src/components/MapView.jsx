import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
// ONE outline file, shared with the matplotlib twin (package data). Vite inlines it — no runtime fetch.
// POLICY CHANGE 2026-09-06 (instructor): the page no longer must work offline, so an online OSM tile
// basemap is permitted; the outline stays bundled as the offline fallback under the tiles.
import outline from "../../../nl2sql_roadsafety/data/israel.json";

const RAMP = ["#b2dfdb", "#4db6ac", "#0d9488", "#0a6e64", "#063f39"];   // observed: by rank quintile, rank 1 darkest
const DIVERGING = ["#1d4ed8", "#93c5fd", "#e5e7eb", "#fca5a5", "#b91c1c"]; // excess: blue below the model, red above
const POPUP_LIST = 12;
const Z90 = 1.6449;
const TILE_ERRORS_MAX = 5;    // ~a screenful of failed tiles = no network: drop the layer, restore the outline fill

function rankColor(rank, n) {
  if (n <= 1) return RAMP[4];
  const q = Math.min(4, Math.floor(((n - rank) / (n - 1)) * 4.999));
  return RAMP[q];
}

// Excess color = distance from the model expectation in UNITS OF THE SITE'S OWN NB UNCERTAINTY — the
// exact rule of the deck.gl map (map/layers.js excessZ + divergingByZ) and map_scene._excess_hex.
// Unified 2026-09-06: the old max|excess| normalization here let one +40 outlier own the scale, so
// the blue half never appeared (the known self-inflicted inconsistency between the two maps).
function excessZ(p) {
  const sd = Math.max(0.5, ((Number(p.hi90) || 0) - (Number(p.mu) || 0)) / Z90);
  return ((Number(p.accidents) || 0) - (Number(p.mu) || 0)) / sd;
}

function excessColor(p) {
  const z = excessZ(p);
  if (z <= -2) return DIVERGING[0];
  if (z <= -0.75) return DIVERGING[1];
  if (z < 0.75) return DIVERGING[2];
  if (z < 2) return DIVERGING[3];
  return DIVERGING[4];
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function rtl(s) {
  return `<span dir="rtl">${esc(s)}</span>`;
}

// Unit tooltip, 3-4 short lines (rank · label / counts / the model line in excess mode / the
// click-for-popup affordance). Numbers ride dir="ltr" spans — digit ranges flip under bidi otherwise.
function unitTooltip(p, excessMode) {
  const lines = [
    `<b>#${esc(p.rank)}</b> · ${esc(p.label)}`,
    `<span dir="ltr">${esc(p.accidents)}</span> תאונות עם נפגעים · <span dir="ltr">${esc(p.ksi_accidents)}</span> KSI`,
  ];
  if (excessMode && p.excess !== undefined) {
    lines.push(`צפוי (מודל) <span dir="ltr">${esc(p.mu)}</span> · עודף <span dir="ltr">${esc(Number(p.excess) > 0 ? `+${p.excess}` : p.excess)}</span>`);
  }
  lines.push(`<span class="muted">לחיצה לפרטים מלאים ולפעולות</span>`);
  return `<div dir="rtl">${lines.map((l) => `<div>${l}</div>`).join("")}</div>`;
}

function popupHtml(p, unit, accidents) {
  const rows = [
    ["תאונות עם נפגעים", p.accidents], ["מהן KSI", p.ksi_accidents], ["ממוקמות", p.geocoded],
    ["שנים", `${p.first_year}–${p.last_year}`],
  ];
  if (p.excess !== undefined) {
    rows.push(["צפוי (מודל)", p.mu], ["excess", p.excess], ["EB", p.eb],
              ["רווח תשעים אחוז", `${p.lo90}–${p.hi90}`], ["מובהק", p.significant ? "✓" : "✗"]);
  }
  if (unit === "segments") rows.push(["ק״מ", `${p.km_from}–${p.km_to}`]);
  else rows.push(["מקור המיקום", p.geometry_source === "dim" ? "טבלת הצמתים" : "ממוצע התאונות"]);
  const list = rows.map(([k, v]) => `<div><span class="k">${esc(k)}</span> <span class="v ltr">${esc(v)}</span></div>`).join("");
  // the drill-down (points=true): the unit's accidents, newest first — internal use, the row level is permitted
  let drill = "";
  if (accidents && accidents.length) {
    const items = accidents.slice(0, POPUP_LIST).map((a) =>
      `<li><span class="ltr">${esc(a.date)}</span> · ${esc(a.severity_label)}${a.road_km != null ? ` · ק״מ <span class="ltr">${esc(a.road_km / 10)}</span>` : ""}</li>`).join("");
    const more = accidents.length > POPUP_LIST ? `<div class="popup-more">… ועוד ${accidents.length - POPUP_LIST} (סמנים אפורים במפה)</div>` : "";
    drill = `<div class="popup-list-title">התאונות מאחורי המספר (${accidents.length} ממוקמות)</div><ul class="popup-list">${items}</ul>${more}`;
  }
  // second hand-off (2026-09-06), road segments only: the model's TreeSHAP story — the SAME road/seg
  // contract SitePanel hands to App's onExplain (studio_explain's site input accepts "60/836")
  const explainBtn = unit === "segments" && p.road !== undefined && p.seg !== undefined
    ? ` <button type="button" class="mini popup-explain" data-seg="${esc(p.road)}/${esc(p.seg)}">הסבר מודל 🔮</button>`
    : "";
  return `<div class="popup" dir="rtl">
    <div class="popup-title">#${esc(p.rank)} · ${esc(p.label)}</div>
    <div class="popup-key ltr">${esc(p.site_key)}</div>
    ${list}
    ${drill}
    <div class="popup-caveat">${p.excess !== undefined
      ? "excess = נצפה − צפוי לפי מודל האתר הפרוס · מתאם ולא סיבתיות"
      : "ספירות אינן סיכון — אין כאן מכנה חשיפה"}</div>
    <button type="button" class="mini popup-handoff" data-key="${esc(p.site_key)}">לפני/אחרי לאתר הזה ←</button>${explainBtn}
  </div>`;
}

export default function MapView({ spec, onHandoff, onExplain, selected, onSelect, active }) {
  const ref = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef({});        // site_key -> circleMarker, for the linked selection
  const fromMap = useRef(false);        // a marker click set the selection — skip the pan-back
  const selRef = useRef(null);          // the live selection for the (long-lived) marker click closures
  const [err, setErr] = useState("");
  const [nPlaced, setNPlaced] = useState(0);
  selRef.current = selected;

  useEffect(() => {
    let map;
    let ro;
    setErr("");
    markersRef.current = {};
    try {
      // preferCanvas: with points=true the map draws hundreds of circleMarkers — one canvas, not one DOM node each
      map = L.map(ref.current, { attributionControl: false, zoomSnap: 0.5, preferCanvas: true });
      mapRef.current = map;
      // POLICY CHANGE 2026-09-06 (instructor): online tiles are now permitted (the offline-only rule is
      // lifted). The bundled outline stays UNDER the tiles with a transparent fill (subtle stroke only);
      // if TILE_ERRORS_MAX tiles fail — a seminar room with no wifi — the tile layer is removed and the
      // fill returns, so the map never looks broken offline.
      const outlineLayer = L.geoJSON(outline, {
        style: { color: "#8b959e", weight: 1, fillColor: "#eef2f5", fillOpacity: 0 },
        interactive: false,
      });
      // Leaflet 1.9.4: the map needs a VIEW before any vector layer is added (PITFALLS 2026-08-28).
      map.fitBounds(outlineLayer.getBounds(), { padding: [8, 8] });
      let tilesDead = false;
      let osmLine = null;               // the legend's © OpenStreetMap line — hidden when the tiles are gone
      let tileErrors = 0;
      const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18 });
      tiles.on("tileerror", () => {
        tileErrors += 1;
        if (tileErrors >= TILE_ERRORS_MAX && !tilesDead) {
          tilesDead = true;
          if (map.hasLayer(tiles)) map.removeLayer(tiles);
          outlineLayer.setStyle({ fillOpacity: 1 });      // offline: the outline is the basemap again
          if (osmLine) osmLine.style.display = "none";    // no tiles on screen -> no OSM credit
        }
      });
      tiles.addTo(map);                 // the tile pane sits under Leaflet's vector panes by default
      outlineLayer.addTo(map);

      const feats = (spec.geojson?.features || []);
      const units = feats.filter((f) => f.properties?.kind === "unit");
      const points = feats.filter((f) => f.properties?.kind === "accident");
      const counts = units.map((f) => Number(f.properties.accidents || 0)).sort((a, b) => a - b);
      const vmax = counts.length ? counts[counts.length - 1] : 1;
      const vmin = counts.length ? counts[0] : 0;
      const group = L.featureGroup();
      const byKey = {};
      points.forEach((f) => { (byKey[f.properties.site_key] = byKey[f.properties.site_key] || []).push(f.properties); });

      points.forEach((f) => {
        const [lon, lat] = f.geometry.coordinates;
        const p = f.properties;
        L.circleMarker([lat, lon], { radius: 3, color: "#5a6672", weight: 0.5, fillColor: "#8b959e", fillOpacity: 0.7 })
          .bindTooltip(rtl(`${p.date} · ${p.severity_label}${p.road_km != null ? ` · ק״מ ${p.road_km / 10}` : ""}`), { direction: "top" })
          .addTo(group);
      });
      const excessMode = spec.color_by_effective === "excess";
      units.forEach((f) => {
        const [lon, lat] = f.geometry.coordinates;
        const p = f.properties;
        const n = Number(p.accidents || 0);
        const r = 5 + 16 * Math.sqrt(n / (vmax || 1));
        const m = L.circleMarker([lat, lon], {
          radius: r, color: "#26323d", weight: excessMode && p.significant ? 2.5 : 1,
          fillColor: excessMode ? excessColor(p) : rankColor(Number(p.rank), units.length),
          fillOpacity: 0.8,
        })
          .bindTooltip(unitTooltip(p, excessMode), { direction: "top" })
          .bindPopup(popupHtml(p, spec.unit, byKey[p.site_key]), { maxWidth: 340 });
        // linked selection: the marker click selects; the popup still opens through Leaflet itself.
        // Re-clicking the selected marker is a no-op (a same-value setState never re-renders, and a
        // stuck fromMap flag would swallow the next table-driven pan).
        m.on("click", () => {
          if (!onSelect || p.site_key == null || p.site_key === selRef.current) return;
          fromMap.current = true;
          onSelect(p.site_key);
        });
        m.addTo(group);
        if (p.site_key != null) markersRef.current[p.site_key] = m;
      });
      group.addTo(map);
      if (units.length) map.fitBounds(group.getBounds(), { padding: [24, 24], maxZoom: 11 });
      setNPlaced(units.length);

      map.on("popupopen", (e) => {
        const root = e.popup.getElement();
        const btn = root?.querySelector(".popup-handoff");
        if (btn && onHandoff) btn.addEventListener("click", () => onHandoff(btn.dataset.key));
        const ex = root?.querySelector(".popup-explain");
        if (ex && onExplain) ex.addEventListener("click", () => onExplain(ex.dataset.seg));
      });

      const legend = L.control({ position: "bottomleft" });
      legend.onAdd = () => {
        const div = L.DomUtil.create("div", "legend");
        if (excessMode) {
          // the z buckets of layers.js divergingByZ — one scale story on both maps (2026-09-06)
          div.innerHTML = `<div class="legend-title">${esc("סטייה מהצפוי ביחידות אי-ודאות (z) — אדום: מעל המודל, כחול: מתחת · גודל = נצפה · טבעת = מובהק")}</div>` +
            DIVERGING.map((c) => `<span class="swatch" style="background:${c}"></span>`).join("") +
            `<div class="legend-sub ltr">${esc(`z<=-2 · -2..-0.75 · -0.75..0.75 · 0.75..2 · z>=2 (${units.length})`)}</div>`;
        } else {
          div.innerHTML = `<div class="legend-title">${esc("תאונות עם נפגעים ליחידה — לפי דירוג היחידות המוצגות")}</div>` +
            RAMP.map((c) => `<span class="swatch" style="background:${c}"></span>`).join("") +
            `<div class="legend-sub ltr">${esc(vmin)} … ${esc(vmax)} (${esc(units.length)})</div>`;
        }
        // the OSM license line (policy change 2026-09-06) — removed with the tiles on offline fallback
        div.innerHTML += `<div class="legend-sub ltr legend-osm">© OpenStreetMap</div>`;
        osmLine = div.querySelector(".legend-osm");
        if (tilesDead && osmLine) osmLine.style.display = "none";
        return div;
      };
      legend.addTo(map);

      // the panel may be hidden (another tab) when this runs; Leaflet must re-measure when it becomes visible
      if (typeof ResizeObserver !== "undefined") {
        ro = new ResizeObserver(() => { try { map.invalidateSize(); } catch { /* removed */ } });
        ro.observe(ref.current);
      }
    } catch (e) {
      // never a blank page: the error card + the PNG twin below
      setErr(`המפה נכשלה: ${e && e.message ? e.message : e}`);
    }
    return () => { if (ro) ro.disconnect(); if (map) map.remove(); mapRef.current = null; markersRef.current = {}; };
  }, [spec, onHandoff, onExplain, onSelect]);

  // linked selection set from OUTSIDE (a ranking-table row): pan to the marker and open its tooltip.
  // A selection born from the marker's own click skips the pan — the popup interaction stays undisturbed.
  useEffect(() => {
    if (fromMap.current) { fromMap.current = false; return; }
    const map = mapRef.current;
    const m = selected != null ? markersRef.current[selected] : null;
    if (!map || !m) return;
    try {
      map.panTo(m.getLatLng());
      m.openTooltip();
    } catch { /* map torn down mid-flight */ }
  }, [selected]);

  useEffect(() => {
    if (active && mapRef.current) { try { mapRef.current.invalidateSize(); } catch { /* removed */ } }
  }, [active]);

  return (
    <div className="mapview">
      {err && <div className="error">{err}</div>}
      <div ref={ref} className="map" dir="ltr" style={{ display: err ? "none" : "block" }} />
      {!err && spec.map && (
        <div className="map-sub">
          {spec.map.units_placed} יחידות במפה מתוך {spec.map.units_listed} בדירוג
          {spec.map.units_omitted > 0 && ` · ${spec.map.units_omitted} ללא מיקום (בטבלה בלבד)`}
          {spec.map.points > 0 && ` · ${spec.map.points} תאונות בודדות`}
          {nPlaced === 0 && " · אין יחידות ממוקמות"}
        </div>
      )}
      {err && spec.png_base64 && <img className="png" alt="map (static twin)" src={`data:image/png;base64,${spec.png_base64}`} />}
    </div>
  );
}
