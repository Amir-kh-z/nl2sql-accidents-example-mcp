import React, { useMemo, useState } from "react";
import { SITE_LABELS } from "./layers.js";

// P10: OFFLINE search — substring over the site labels and the gazetteer (city centroids derived from the
// data itself). No external geocoder, ever (the CBS rule: nothing leaves the machine).

const MAX_RESULTS = 8;

function norm(s) { return String(s || "").toLowerCase(); }

export default function SearchBox({ scene, onGo }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);

  const index = useMemo(() => {
    if (!scene) return [];
    const out = [];
    for (const kind of ["segments", "njunctions", "ujunctions"]) {
      for (const e of scene.sites[kind] || []) {
        if (e.lat != null) out.push({ text: e.label, kindLabel: SITE_LABELS[kind], lat: e.lat, lon: e.lon, site: e, kind });
      }
    }
    for (const g of scene.gazetteer || []) {
      out.push({ text: g.name, kindLabel: "יישוב", lat: g.lat, lon: g.lon });
    }
    return out;
  }, [scene]);

  const hits = useMemo(() => {
    const needle = norm(q).trim();
    if (needle.length < 2) return [];
    return index.filter((e) => norm(e.text).includes(needle)).slice(0, MAX_RESULTS);
  }, [q, index]);

  const go = (hit) => {
    setOpen(false);
    setQ(hit.text);
    onGo(hit);
  };

  return (
    <div className="map-search">
      <input type="text" value={q} placeholder="חיפוש: כביש, צומת או יישוב…"
             onChange={(e) => { setQ(e.target.value); setOpen(true); }}
             onFocus={() => setOpen(true)}
             onKeyDown={(e) => { if (e.key === "Enter" && hits.length) go(hits[0]); if (e.key === "Escape") setOpen(false); }} />
      {open && hits.length > 0 && (
        <div className="results">
          {hits.map((h, i) => (
            <button key={i} type="button" onClick={() => go(h)}>
              {h.text}<span className="kind">{h.kindLabel}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
