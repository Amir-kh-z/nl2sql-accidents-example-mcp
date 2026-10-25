import React, { useEffect, useRef } from "react";

// P10: the year window + the animation. Playing sweeps a one-year window across the range (~0.9 s per
// year, GPU filter only — no re-fetch, no layer re-upload). Year labels are String(year) — NEVER
// Intl.NumberFormat (the grouped-years pitfall, "2,019").

export default function TimeSlider({ years, filters, setFilters, playing, setPlaying }) {
  const [y0, y1] = years;
  const timer = useRef(null);

  useEffect(() => {
    if (!playing) { if (timer.current) { clearInterval(timer.current); timer.current = null; } return undefined; }
    setFilters((f) => ({ ...f, playYear: f.playYear != null ? f.playYear : y0 }));
    timer.current = setInterval(() => {
      setFilters((f) => {
        const next = (f.playYear != null ? f.playYear : y0) + 1;
        if (next > y1) { setPlaying(false); return { ...f, playYear: null }; }
        return { ...f, playYear: next };
      });
    }, 900);
    return () => { if (timer.current) { clearInterval(timer.current); timer.current = null; } };
  }, [playing, y0, y1, setFilters, setPlaying]);

  const lo = filters.playYear != null ? filters.playYear : filters.yearLo;
  const hi = filters.playYear != null ? filters.playYear : filters.yearHi;
  return (
    <div className="time-slider">
      <button type="button" className="mini" onClick={() => setPlaying((p) => !p)}
              title="הנפשה לאורך השנים — חלון של שנה אחת">
        {playing ? "⏸ עצירה" : "▶ הנפשה"}
      </button>
      <span className="years ltr">{String(lo)}-{String(hi)}</span>
      <input type="range" min={y0} max={y1} value={lo} aria-label="from year"
             onChange={(e) => {
               const v = Number(e.target.value);
               setPlaying(false);
               setFilters((f) => ({ ...f, playYear: null, yearLo: Math.min(v, f.yearHi) }));
             }} />
      <input type="range" min={y0} max={y1} value={hi} aria-label="to year"
             onChange={(e) => {
               const v = Number(e.target.value);
               setPlaying(false);
               setFilters((f) => ({ ...f, playYear: null, yearHi: Math.max(v, f.yearLo) }));
             }} />
    </div>
  );
}
