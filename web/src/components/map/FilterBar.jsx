import React from "react";
import { NIGHT_LABELS, SEV_COLORS, SEV_LABELS, SITE_LABELS } from "./layers.js";

// Neutral shape swatches — sites carry no hue (colors belong to severity / excess only)
const SHAPE_SWATCH = {
  segments: { background: "#3a4552", borderRadius: 1 },
  njunctions: { background: "#3a4552", borderRadius: "50%" },
  ujunctions: { background: "transparent", border: "2px solid #3a4552", borderRadius: "50%" },
};

// P10: every control here drives a GPU filter or a layer toggle — zero re-fetches.

function rgb(c) { return `rgb(${c[0]},${c[1]},${c[2]})`; }

export default function FilterBar({ filters, setFilters, layerToggles, setLayerToggles }) {
  const flipSev = (s) => setFilters((f) => ({ ...f, sev: { ...f.sev, [s]: !f.sev[s] } }));
  const flipNight = (s) => setFilters((f) => ({ ...f, night: { ...f.night, [s]: !f.night[s] } }));
  const flipLayer = (k) => setLayerToggles((t) => ({ ...t, [k]: !t[k] }));
  return (
    <div className="map-filters">
      <span className="group">
        <span className="muted">חומרה:</span>
        {[1, 2, 3].map((s) => (
          <label key={s}>
            <input type="checkbox" checked={filters.sev[s]} onChange={() => flipSev(s)} />
            <span className="sev-dot" style={{ background: rgb(SEV_COLORS[s]) }} />
            {SEV_LABELS[s]}
          </label>
        ))}
      </span>
      <span className="group">
        <span className="muted">יום ולילה:</span>
        {[0, 1, 2].map((s) => (
          <label key={s}>
            <input type="checkbox" checked={filters.night[s]} onChange={() => flipNight(s)} />
            {NIGHT_LABELS[s]}
          </label>
        ))}
      </span>
      <span className="group">
        <span className="muted">שכבות:</span>
        <label>
          <input type="checkbox" checked={layerToggles.cloud} onChange={() => flipLayer("cloud")} />
          ענן הנקודות
        </label>
        {["segments", "njunctions", "ujunctions"].map((k) => (
          <label key={k}>
            <input type="checkbox" checked={layerToggles[k]} onChange={() => flipLayer(k)} />
            <span className="sev-dot" style={SHAPE_SWATCH[k]} />
            {SITE_LABELS[k]}
          </label>
        ))}
      </span>
    </div>
  );
}
