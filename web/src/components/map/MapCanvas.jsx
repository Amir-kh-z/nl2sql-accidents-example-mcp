import React, { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { ISRAEL_BOUNDS, ensurePmtilesProtocol, styleFor } from "./basemap.js";
import { cloudArrays, cloudLayer, siteLayers, tooltipFor } from "./layers.js";

// P10: ONE maplibre map + ONE deck.gl overlay for the tab's whole life. The map is created with `bounds`
// in the constructor (never fitBounds after layers — the P3 React-18 pitfall class), the container is a
// dir="ltr" island, and any construction failure surfaces through onFail (error card + PNG twin above,
// never a blank tab). Layers are rebuilt per prop change; the binary attributes upload once.

export default function MapCanvas({ scene, filters, layerToggles, basemapMode, colorMode, selectedKey, onPick,
                                    onClear, flyTarget, active, onFail }) {
  const divRef = useRef(null);
  const mapRef = useRef(null);
  const overlayRef = useRef(null);
  const arrsRef = useRef(null);

  useEffect(() => {                                        // create once
    let map;
    try {
      ensurePmtilesProtocol();
      map = new maplibregl.Map({
        container: divRef.current,
        style: styleFor(basemapMode),
        bounds: ISRAEL_BOUNDS,
        fitBoundsOptions: { padding: 24 },
        minZoom: 5.5,
        maxZoom: 17,
        attributionControl: false,                         // CreditBadge carries CBS + OSM instead
      });
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      const overlay = new MapboxOverlay({ interleaved: false, layers: [], pickingRadius: 4,
                                          getTooltip: (info) => tooltipFor(info, arrsRef.current) });
      map.addControl(overlay);
      mapRef.current = map;
      overlayRef.current = overlay;
    } catch (e) {
      if (onFail) onFail(`המפה נכשלה: ${e && e.message ? e.message : e}`);
    }
    return () => {
      overlayRef.current = null;
      if (map) { try { map.remove(); } catch { /* gone */ } }
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);                                                  // basemapMode is resolved before first mount

  const modeRef = useRef(basemapMode);
  useEffect(() => {                                        // style switch on a REAL mode change only — a
    if (modeRef.current === basemapMode) return;           // mount-time setStyle rebuilds mid-load and killed
    modeRef.current = basemapMode;                         // the style entirely (found live in P10)
    const map = mapRef.current;
    if (map) { try { map.setStyle(styleFor(basemapMode)); } catch { /* keep the old style */ } }
  }, [basemapMode]);

  useEffect(() => {                                        // typed arrays: once per envelope
    arrsRef.current = scene ? cloudArrays(scene.cloud) : null;
    // a ROAD-scoped scene frames its own corridor (marks are meter-sized — they only reach full size
    // zoomed in; the national default keeps the whole-country frame)
    const map = mapRef.current;
    const bb = scene && scene.meta && scene.meta.bbox;
    if (map && bb && scene.meta.road) {
      try {
        map.fitBounds([[bb[0], bb[1]], [bb[2], bb[3]]], { padding: 70, duration: 900, maxZoom: 11.5 });
      } catch { /* mid-teardown */ }
    }
  }, [scene]);

  useEffect(() => {                                        // layers: every filter/selection change (GPU-side)
    const overlay = overlayRef.current;
    if (!overlay || !scene || !arrsRef.current) return;
    try {
      const layers = [];
      if (layerToggles.cloud) layers.push(cloudLayer(arrsRef.current, filters));
      for (const kind of ["ujunctions", "njunctions", "segments"]) {   // segments on top — the model layer
        if (layerToggles[kind]) layers.push(...siteLayers(kind, scene.sites[kind] || [], selectedKey, onPick, colorMode));
      }
      // a click on EMPTY map closes the site panel (the ✕ and Escape are the other two exits)
      overlay.setProps({ layers, onClick: (info) => { if (!info.picked && onClear) onClear(); } });
    } catch (e) {
      if (onFail) onFail(`שכבות המפה נכשלו: ${e && e.message ? e.message : e}`);
    }
  }, [scene, filters, layerToggles, colorMode, selectedKey, onPick, onClear, onFail]);

  useEffect(() => {                                        // fly-to from the search box / site pick
    const map = mapRef.current;
    if (map && flyTarget && flyTarget.lon != null) {
      try { map.flyTo({ center: [flyTarget.lon, flyTarget.lat], zoom: flyTarget.zoom || 12.5, duration: 900 }); }
      catch { /* mid-teardown */ }
    }
  }, [flyTarget]);

  useEffect(() => {                                        // hidden tabs give the canvas size 0 — re-measure
    if (active && mapRef.current) { try { mapRef.current.resize(); } catch { /* gone */ } }
  }, [active]);

  useEffect(() => {
    if (typeof ResizeObserver === "undefined" || !divRef.current) return undefined;
    const ro = new ResizeObserver(() => { try { mapRef.current && mapRef.current.resize(); } catch { /* gone */ } });
    ro.observe(divRef.current);
    return () => ro.disconnect();
  }, []);

  return <div ref={divRef} className="map-gl" dir="ltr" />;
}
