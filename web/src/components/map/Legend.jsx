import React from "react";
import { DIVERGING, SEV_COLORS, SEV_LABELS, SITE_LABELS } from "./layers.js";

// Neutral shape swatches on the dark legend background
const SHAPE_SWATCH = {
  segments: { background: "#c9d2da", borderRadius: 1 },
  njunctions: { background: "#c9d2da", borderRadius: "50%" },
  ujunctions: { background: "transparent", border: "2px solid #c9d2da", borderRadius: "50%" },
};

// P10: the legend states the encoding AND the discipline. Counts mode: darker = more, counts are not risk.
// Excess mode: the diverging model scale on SEGMENTS ONLY — junctions stay counts (no denominator, ever).

function rgb(c) { return `rgb(${c[0]},${c[1]},${c[2]})`; }

export default function Legend({ scene, filters }) {
  if (!scene) return null;
  const lo = filters.playYear != null ? filters.playYear : filters.yearLo;
  const hi = filters.playYear != null ? filters.playYear : filters.yearHi;
  const excess = scene.color_by_effective === "excess";
  return (
    <div className="map-legend">
      <div className="row"><b>תאונות עם נפגעים</b><span className="ltr">{String(lo)}-{String(hi)}</span></div>
      <div className="row">
        {[1, 2, 3].map((s) => (
          <span key={s} className="row" style={{ gap: 3 }}>
            <span className="sev-dot" style={{ background: rgb(SEV_COLORS[s]) }} />{SEV_LABELS[s]}
          </span>
        ))}
      </div>
      <div className="row">
        {["segments", "njunctions", "ujunctions"].map((k) => (
          <span key={k} className="row" style={{ gap: 3 }}>
            <span className="sev-dot" style={SHAPE_SWATCH[k]} />
            {SITE_LABELS[k]}
          </span>
        ))}
      </div>
      <div className="row">הצורה = סוג האתר · גודל = ספירות · הצבעים שמורים לחומרה ולמודל</div>
      {excess ? (
        <>
          <div className="row">
            <b>מקטעים מול המודל:</b>
            {DIVERGING.map((c, i) => <span key={i} className="sev-dot" style={{ background: rgb(c), borderRadius: 2 }} />)}
          </div>
          <div className="row">אדום = מעל הציפייה · כחול = מתחת · עומק הצבע = המרחק ביחידות אי-הוודאות של האתר · טבעת = מובהק (מעל הרווח)</div>
          <div className="row">כל מקטעי הלוח מוצגים ({scene.sites.segments.length}) · צמתים: המובילים בספירות</div>
          <div className="row">🔮 <span className="ltr">{scene.model_id}</span></div>
          <div className="row">צמתים: ספירות בלבד — אין נפח תנועה לצמתים</div>
        </>
      ) : (
        <div className="row">כהה יותר = יותר · המובילים בכל שכבה · ספירות אינן סיכון — מדדי מודל בלחיצה על אתר</div>
      )}
    </div>
  );
}
