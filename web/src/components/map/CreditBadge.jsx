import React from "react";

// P10: the CBS credit is ALWAYS on the rendered map (the license term travels with every surface);
// the map-data attribution joins it only when OSM-derived tiles are actually shown (ODbL) — the local
// PMTiles street extract ("street", + Protomaps) or, since the 2026-09-06 online-allowed policy change,
// the online OSM raster fallback ("osm").

const CREDIT = "מקור הנתונים: הלשכה המרכזית לסטטיסטיקה (למ״ס); עיבוד: מעבדת הבטיחות בדרכים";

export default function CreditBadge({ basemapMode }) {
  return (
    <div className="map-credit">
      {CREDIT}
      {basemapMode === "street" && <span className="ltr"> · © OpenStreetMap · Protomaps</span>}
      {basemapMode === "osm" && <span className="ltr"> · © OpenStreetMap</span>}
    </div>
  );
}
