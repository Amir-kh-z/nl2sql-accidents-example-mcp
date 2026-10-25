import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { runAction } from "../../api.js";
import { probeBasemap } from "./basemap.js";
import MapCanvas from "./MapCanvas.jsx";
import FilterBar from "./FilterBar.jsx";
import TimeSlider from "./TimeSlider.jsx";
import SearchBox from "./SearchBox.jsx";
import Legend from "./Legend.jsx";
import CreditBadge from "./CreditBadge.jsx";
import SitePanel from "./SitePanel.jsx";
import ZHistogram from "./ZHistogram.jsx";
import Card from "../Card.jsx";
import Seg from "../Seg.jsx";

// P10: the מפה חיה state owner. ONE map_scene fetch per server scope (years/road) — everything else
// (severity, day/night, year window, animation, layer toggles, selection) is client-side and GPU-filtered.
// Failure is never blank: error card + the envelope's PNG twin (the MapView precedent).

// Deep-linkable scope (?road=&from_year=&to_year= — the ?tab/?run pattern): demo links open the map
// pre-scoped, and the headless checks use a small scope that fits the virtual-time budget.
function scopeFromUrl() {
  const p = new URLSearchParams(window.location.search);
  return { road: Number(p.get("road")) || 0,
           from_year: Number(p.get("from_year")) || 2008,
           to_year: Number(p.get("to_year")) || 2024,
           color_by: p.get("color") === "excess" ? "excess" : "observed" };
}

export default function MapTab({ db, active, onHandoff, onExplain }) {
  const [scope, setScope] = useState(scopeFromUrl);
  const [draft, setDraft] = useState(scope);
  const [env, setEnv] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [glErr, setGlErr] = useState("");
  const [basemapMode, setBasemapMode] = useState("");            // "" = probing
  const [filters, setFilters] = useState({ yearLo: 2008, yearHi: 2024, playYear: null,
                                           sev: { 1: true, 2: true, 3: true },
                                           night: { 0: true, 1: true, 2: true } });
  const [layerToggles, setLayerToggles] = useState({ cloud: true, segments: true, njunctions: true, ujunctions: true });
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState(null);
  const [flyTarget, setFlyTarget] = useState(null);
  const [twinPng, setTwinPng] = useState("");           // fetched only on GL failure (the interactive fetch skips the twin)

  useEffect(() => {
    if (!glErr || !db || twinPng) return;
    let alive = true;
    runAction("map_scene", db, { ...scope, view: "chart" })
      .then((res) => { if (alive && res.kind === "chart" && res.data.png_base64) setTwinPng(res.data.png_base64); })
      .catch(() => { /* the error card already shows */ });
    return () => { alive = false; };
  }, [glErr, db, twinPng, scope]);

  useEffect(() => { probeBasemap().then(setBasemapMode); }, []);

  // One fetch per scope, on first activation. Deduped by a ref key — NEVER by effect cleanup: a state
  // flip in the dep array re-runs the effect and its cleanup, and an `alive=false` cleanup then discards
  // the RESOLVED response, leaving the tab busy forever (found by the P10 headless network log).
  const fetchedScope = useRef("");
  useEffect(() => {
    if (!active || !db) return;
    const key = JSON.stringify(scope);
    if (fetchedScope.current === key) return;
    fetchedScope.current = key;
    setBusy(true); setErr("");
    runAction("map_scene", db, { ...scope, twin: false, view: "chart" })
      .then((res) => {
        if (fetchedScope.current !== key) return;                // a newer scope superseded this fetch
        setEnv(res);
        if (res.kind === "chart") {
          const [y0, y1] = res.data.meta.years;
          setFilters((f) => ({ ...f, yearLo: y0, yearHi: y1, playYear: null }));
        }
      })
      .catch((e) => {
        if (fetchedScope.current === key) {
          setErr(String(e.message || e));
          fetchedScope.current = "";                             // a failed scope must be retryable (sweep C4)
        }
      })
      .finally(() => { setBusy((b) => (fetchedScope.current === key || fetchedScope.current === "" ? false : b)); });
  }, [active, db, scope]);

  const scene = env && env.kind === "chart" ? env.data : null;
  const years = scene ? scene.meta.years : [scope.from_year, scope.to_year];

  const apply = useCallback(() => {
    fetchedScope.current = "";       // an UNCHANGED scope must refetch too, or the tab blanks forever (sweep C4)
    setEnv(null); setSelected(null); setPlaying(false);
    setScope((s) => ({ road: Number(draft.road) || 0,
                       from_year: Number(draft.from_year) || 2008,
                       to_year: Number(draft.to_year) || 2024,
                       color_by: s.color_by }));
  }, [draft]);

  const setColor = useCallback((mode) => {
    setScope((s) => (s.color_by === mode ? s : { ...s, color_by: mode }));
  }, []);

  const onPick = useCallback((siteObj) => {
    setSelected(siteObj);
    setFlyTarget({ lon: siteObj.lon, lat: siteObj.lat, zoom: 12.5, ts: Date.now() });
  }, []);

  const onGo = useCallback((hit) => {
    setFlyTarget({ lon: hit.lon, lat: hit.lat, zoom: hit.site ? 12.5 : 11, ts: Date.now() });
    if (hit.site) setSelected(hit.site);
  }, []);

  const effectiveFilters = useMemo(() => (filters.playYear != null
    ? { ...filters, yearLo: filters.playYear, yearHi: filters.playYear } : filters), [filters]);

  return (
    <div className="map-tab">
      <div className="map-toolbar">
        <SearchBox scene={scene} onGo={onGo} />
        <span className="field-inline">כביש
          <input type="number" min="0" value={draft.road}
                 onChange={(e) => setDraft((d) => ({ ...d, road: e.target.value }))} />
        </span>
        <span className="field-inline">משנת
          <input type="number" min="2005" max="2024" value={draft.from_year}
                 onChange={(e) => setDraft((d) => ({ ...d, from_year: e.target.value }))} />
        </span>
        <span className="field-inline">עד שנת
          <input type="number" min="2005" max="2024" value={draft.to_year}
                 onChange={(e) => setDraft((d) => ({ ...d, to_year: e.target.value }))} />
        </span>
        <button type="button" className="mini" onClick={apply} disabled={busy}>רענון היקף</button>
        <span className="field-inline">צבע:
          {/* P13: the shared Seg component (extracted segmented control) replaces the local .color-toggle */}
          <Seg label="צבע" value={scope.color_by} onChange={setColor}
               options={[{ value: "observed", label: "ספירות" }, { value: "excess", label: "מול המודל" }]} />
        </span>
        {busy && <span className="chip busy">טוען את סצנת המפה…</span>}
        {scene && scene.cloud.capped && <span className="chip chip-amber">הענן הוגבל — ראו הסתייגויות</span>}
        {scene && scene.color_by === "excess" && scene.color_by_effective === "observed" && (
          <span className="chip chip-amber">צביעת מודל לא זמינה — מוצגות ספירות (ראו הסתייגויות)</span>
        )}
        {basemapMode === "canvas" && <span className="chip">רקע: קנבס נתונים (אין קובץ מפת רחובות)</span>}
        {/* 2026-09-06 policy change: online tiles allowed — the no-PMTiles fallback is now OSM, and it says so */}
        {basemapMode === "osm" && <span className="chip">רקע: OpenStreetMap (מקוון)</span>}
      </div>
      {scene && <TimeSlider years={years} filters={filters} setFilters={setFilters}
                            playing={playing} setPlaying={setPlaying} />}
      {scene && <FilterBar filters={filters} setFilters={setFilters}
                           layerToggles={layerToggles} setLayerToggles={setLayerToggles} />}
      {err && <div className="error">{err}</div>}
      {env && env.kind === "markdown" && <Card text={env.data} />}
      {env && env.kind === "error" && <div className="error">{env.data}</div>}
      {glErr && (
        <div>
          <div className="error">{glErr}</div>
          {twinPng && <img className="png" alt="map (static twin)" src={`data:image/png;base64,${twinPng}`} />}
        </div>
      )}
      {scene && basemapMode && !glErr && (
        <div className="map-shell">
          <MapCanvas scene={scene} filters={effectiveFilters} layerToggles={layerToggles}
                     basemapMode={basemapMode} colorMode={scene.color_by_effective}
                     selectedKey={selected ? selected.site_key : ""}
                     onPick={onPick} onClear={() => setSelected(null)}
                     flyTarget={flyTarget} active={active} onFail={setGlErr} />
          <div className="map-overlay-tl"><Legend scene={scene} filters={effectiveFilters} /></div>
          <div className="map-overlay-br"><CreditBadge basemapMode={basemapMode} /></div>
          <SitePanel db={db} site={selected} years={years}
                     onClose={() => setSelected(null)} onHandoff={onHandoff} onExplain={onExplain} />
        </div>
      )}
      {scene && (
        <div className="map-sub">
          ענן: <span className="ltr">{scene.cloud.n.toLocaleString()}</span> תאונות ממוקמות
          {" · "}כיסוי: <span className="ltr">{scene.coverage.geocoded.toLocaleString()}/{scene.coverage.total.toLocaleString()}</span>
          {" · "}אתרים: <span className="ltr">{scene.sites.segments.length}/{scene.sites.njunctions.length}/{scene.sites.ujunctions.length}</span>
          {scene.model_id && <> {" · "}מודל: <span className="ltr">{scene.model_id}</span></>}
          {/* P13: the spec's strict-ASCII basis line, surfaced for the curious (machine text — LTR island) */}
          {scene.basis && <> {" · "}<span className="ltr" style={{ fontSize: 11 }}>{scene.basis}</span></>}
        </div>
      )}
      {scene && scene.color_by_effective === "excess" && <ZHistogram segments={scene.sites.segments} />}
      {scene && scene.caveats && scene.caveats.length > 0 && (
        <details className="map-caveats">
          <summary>הסתייגויות ({scene.caveats.length})</summary>
          <ul className="ribbon">{scene.caveats.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </details>
      )}
    </div>
  );
}
