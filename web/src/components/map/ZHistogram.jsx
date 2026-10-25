import React, { useMemo } from "react";
import { divergingByZ, excessZ } from "./layers.js";

// P10: residual diagnostics for the risk view — EDA of the model's errors. The histogram of z (distance
// from expectation in each site's own NB-uncertainty units) across the WHOLE panel answers what no single
// square can: is the center at 0 (calibration — the 2023-24 decline shows as a left shift), is the spread
// noise-like, and how exceptional is the red tail. Bars share the map's exact diverging buckets. Data is
// already client-side — no backend, no new action; each site stays individually ledgered elsewhere.

const ZMIN = -4;
const ZMAX = 4;
const BINS = 16;
const W = 320;
const H = 78;
const Z90 = 1.6449;

function rgb(c) { return `rgb(${c[0]},${c[1]},${c[2]})`; }

function xFor(z) { return ((z - ZMIN) / (ZMAX - ZMIN)) * W; }

export default function ZHistogram({ segments }) {
  const { counts, above, below, within, n } = useMemo(() => {
    const zs = (segments || []).filter((e) => e.excess != null).map(excessZ);
    const c = new Array(BINS).fill(0);
    let ab = 0; let be = 0;
    for (const z of zs) {
      const i = Math.min(BINS - 1, Math.max(0, Math.floor(((z - ZMIN) / (ZMAX - ZMIN)) * BINS)));
      c[i] += 1;
      if (z > Z90) ab += 1;
      else if (z < -Z90) be += 1;
    }
    return { counts: c, above: ab, below: be, within: zs.length - ab - be, n: zs.length };
  }, [segments]);
  if (!n) return null;
  const max = Math.max(1, ...counts);
  const barW = W / BINS;
  return (
    <details className="zhist" open>
      <summary>התפלגות מול המודל — כל מקטעי הלוח ({n})</summary>
      <svg viewBox={`0 0 ${W} ${H + 10}`} aria-hidden="true">
        {counts.map((c, i) => {
          const h = (c / max) * H;
          const zMid = ZMIN + (i + 0.5) * ((ZMAX - ZMIN) / BINS);
          return (
            <rect key={i} x={i * barW + 1} y={H - h} width={barW - 2} height={h}
                  fill={rgb(divergingByZ(zMid))} stroke="#5b6673" strokeWidth="0.4" />
          );
        })}
        <line x1={xFor(0)} x2={xFor(0)} y1={0} y2={H} stroke="#3a4552" strokeWidth="1.2" />
        {[-Z90, Z90].map((z) => (
          <line key={z} x1={xFor(z)} x2={xFor(z)} y1={0} y2={H} stroke="#8b959e"
                strokeWidth="1" strokeDasharray="4 3" />
        ))}
        <line x1={0} x2={W} y1={H} y2={H} stroke="#8b959e" strokeWidth="0.8" />
      </svg>
      <div className="zhist-line">
        מעל הרווח: <span className="ltr">{above}</span> · בתוך: <span className="ltr">{within}</span> · מתחת: <span className="ltr">{below}</span>
      </div>
      <div className="zhist-line muted">
        מרכז משמאל לאפס = המודל מצפה ליותר משקרה (כיול) · זנב ימני עבה = אוכלוסיית הסינון — לא רעש
      </div>
    </details>
  );
}
