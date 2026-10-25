import React, { useCallback, useEffect, useRef, useState } from "react";
import Plotly from "plotly.js-cartesian-dist";
import Form from "./Form.jsx";
import Answer from "./Answer.jsx";
import { runAction } from "../api.js";
import { useThemeTokens } from "../theme.js";
import { BLURBS } from "./blurbs.js";

// P11: the trend composer — up to THREE parameterizations of `trend`, composed client-side. Page-only by
// design: each run keeps its complete envelope (badge, ribbon, SQL, credit, its own ledger line); the
// composition is a VIEW affordance. Composition rules (the approved P11 design):
//   · different granularities → no composed figure (the runs render separately + a note);
//   · overlay on ONE shared y-axis iff every run has IDENTICAL gap_periods AND max-scale ratio ≤ SCALE_RATIO_MAX;
//   · otherwise split: one figure, one panel per run — matched x, free y;
//   · NEVER two independent y-axes (the chart-lie configuration);
//   · the אוטו/מאוחד/מפוצל toggle is always visible on a composed figure and overrides the auto choice; a
//     forced overlay across differing gap sets drops the gap band and names the series with missing periods.

// series palette + layout skeleton mirror PlotlyChart.jsx (which mirrors charts.py) — duplicated on
// purpose so the P11 rebase touches no shared chart file. P13: structural colors (ink, grid, gap band)
// come from the CSS custom properties via theme.js so the composed figure follows dark mode; the three
// series hues stay fixed (meaning-bound, legible on both grounds). FALLBACK_TOKENS keeps the exported
// pure builders callable from a DOM-less harness (light values, matching styles.css :root).
const SERIES = ["#0d9488", "#c0392b", "#f7931e"];
const FONT_FAMILY = "'Segoe UI', 'Assistant', 'Noto Sans Hebrew', sans-serif";
const FALLBACK_TOKENS = { ink: "#1a1f26", inkSoft: "#5b6673", grid: "#dfe3e8", card: "#f4f6f8" };
const LEGEND_LEFT = { orientation: "h", x: 0, xanchor: "left", y: 1.08, font: { size: 11 } };
const SCALE_RATIO_MAX = 3;                       // beyond ~3× the smaller series is squeezed unreadable
const MAX_ROWS = 3;

function baseLayout(t, overrides = {}) {
  return {
    font: { family: FONT_FAMILY, color: t.ink, size: 12 },
    paper_bgcolor: "rgba(0,0,0,0)",              // the page ground behind it is token-painted already
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: { l: 24, r: 30, t: 34, b: 44 },
    dragmode: false,
    ...overrides,
  };
}

const catAxis = (t, extra = {}) => ({ type: "category", gridcolor: t.grid, zerolinecolor: t.grid,
                                      tickfont: { size: 11, color: t.inkSoft }, ...extra });
const numAxis = (t, extra = {}) => ({ gridcolor: t.grid, zerolinecolor: t.grid,
                                      tickfont: { size: 11, color: t.inkSoft }, ...extra });

const colIndex = (spec) => Object.fromEntries(spec.columns.map((n, i) => [n, i]));

// x labels exactly as the single-run trend builder makes them (monthly composite labels — the P8 fix)
function xsOf(spec) {
  const c = colIndex(spec);
  return spec.granularity === "month" && c.month != null
    ? spec.rows.map((r) => `${r[c.year]}-${String(r[c.month]).padStart(2, "0")}`)
    : spec.rows.map((r) => String(r[c[spec.x]]));
}

function ysOf(spec) {
  const c = colIndex(spec);
  const covered = c.covered != null ? spec.rows.map((r) => r[c.covered]) : spec.rows.map(() => true);
  return spec.rows.map((r, i) => (covered[i] === false ? null : r[c[spec.y]]));
}

const shortTitle = (t) => String(t || "").replace(/^מגמה · /, "");
const LRM = "\u200E";                       // pins the year range against the RTL en-dash flip (P8 pitfall)
// composed-view labels carry the year window — two runs differing only by window would otherwise be
// byte-identical (sweep finding); the spec echoes the effective range
const labelOf = (run) => `${shortTitle(run.env.title)} · ${LRM}${run.env.data.from_year}–${run.env.data.to_year}${LRM}`;

// the auto decision, from the specs alone — inspectable, and overridable by the toggle
export function decide(specs) {
  if (new Set(specs.map((s) => s.granularity)).size > 1) return { auto: "stack", gapsEqual: true, ratio: 1 };
  const gapSets = specs.map((s) => JSON.stringify([...(s.gap_periods || [])].sort()));
  const gapsEqual = gapSets.every((g) => g === gapSets[0]);
  const maxes = specs.map((s) => Math.max(0, ...ysOf(s).filter((v) => v != null)));
  const positive = maxes.filter((m) => m > 0);
  const ratio = positive.length ? Math.max(...maxes) / Math.min(...positive) : 1;
  return { auto: gapsEqual && ratio <= SCALE_RATIO_MAX ? "overlay" : "split", gapsEqual, ratio };
}

function gapShapes(union, gapLabels, yref = "paper", fill = FALLBACK_TOKENS.card) {
  return gapLabels.flatMap((g) => {
    const i = union.indexOf(g);
    return i < 0 ? [] : [{ type: "rect", xref: "x", yref, x0: i - 0.5, x1: i + 0.5, y0: 0, y1: 1,
                           fillcolor: fill, line: { width: 0 }, layer: "below" }];
  });
}

// exported for the harness/tests (pure) — `t` defaults to the light tokens so 3-arg callers still work
export function buildComposed(runs, effective, gapsEqual, t = FALLBACK_TOKENS) {
  const specs = runs.map((r) => r.env.data);
  const union = [...new Set(specs.flatMap(xsOf))].sort();     // "2005" / "2005-01" both sort chronologically
  if (effective === "overlay") {
    const data = specs.map((s, i) => ({
      type: "scatter", mode: "lines+markers", x: xsOf(s), y: ysOf(s), connectgaps: false,
      name: labelOf(runs[i]), line: { color: SERIES[i], width: 2.5 },
      marker: { size: 6, color: SERIES[i] }, hovertemplate: "%{x}: %{y:,}<extra></extra>",
    }));
    const shapes = gapsEqual ? gapShapes(union, specs[0].gap_periods || [], "paper", t.card) : [];
    return { data,
             layout: baseLayout(t, { height: 400, showlegend: true, legend: LEGEND_LEFT, shapes,
                                     xaxis: catAxis(t, { categoryorder: "array", categoryarray: union }),
                                     yaxis: numAxis(t) }) };
  }
  // split: one figure, one panel per run — matched x (matches: "x"), FREE y per panel, never dual axes
  const n = specs.length;
  const data = [];
  const layout = baseLayout(t, { height: n * 240 + 80, showlegend: false, annotations: [], shapes: [] });
  specs.forEach((s, i) => {
    const xa = i === 0 ? "x" : `x${i + 1}`, ya = i === 0 ? "y" : `y${i + 1}`;
    const top = 1 - i / n, bottom = 1 - (i + 1) / n + 0.05;
    data.push({ type: "scatter", mode: "lines+markers", x: xsOf(s), y: ysOf(s), connectgaps: false,
                xaxis: xa, yaxis: ya, name: labelOf(runs[i]),
                line: { color: SERIES[i], width: 2.5 },
                marker: { size: 6, color: SERIES[i] }, hovertemplate: "%{x}: %{y:,}<extra></extra>" });
    layout[i === 0 ? "xaxis" : `xaxis${i + 1}`] = catAxis(t, {
      categoryorder: "array", categoryarray: union, anchor: ya,
      matches: i === 0 ? undefined : "x", showticklabels: i === n - 1,
    });
    layout[i === 0 ? "yaxis" : `yaxis${i + 1}`] = numAxis(t, { domain: [bottom, top - 0.07], anchor: xa });
    layout.annotations.push({ text: labelOf(runs[i]), xref: "paper", yref: "paper",
                              x: 1, y: top - 0.005, xanchor: "right", yanchor: "top", showarrow: false,
                              font: { size: 11.5, color: t.ink } });
    layout.shapes.push(...gapShapes(union, s.gap_periods || [], `${ya} domain`, t.card));
  });
  return { data, layout };
}

function ComposedFigure({ runs, effective, gapsEqual }) {
  const el = useRef(null);
  const [failed, setFailed] = useState(false);
  const tokens = useThemeTokens();
  useEffect(() => {
    if (!el.current) return undefined;
    try {
      const { data, layout } = buildComposed(runs, effective, gapsEqual, tokens);
      Plotly.react(el.current, data, layout, { displayModeBar: false, responsive: true, doubleClick: false });
      setFailed(false);
    } catch (err) {
      console.error("composed trend failed", err);
      setFailed(true);
    }
    const node = el.current;
    return () => { try { Plotly.purge(node); } catch { /* unmounted */ } };
    // tokens in the deps: an OS theme flip re-reads the CSS vars and Plotly.react redraws with them
  }, [runs, effective, gapsEqual, tokens]);
  // P13 resize fix — same story as PlotlyChart: plotly 3.7.0 has no ResizeObserver and skips hidden
  // divs, and the tabs stay mounted under [hidden]; poke Plotly when the container gains real width.
  useEffect(() => {
    const node = el.current;
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    let ro;
    try {
      ro = new ResizeObserver((entries) => {
        for (const e of entries) {
          const w = e.contentRect ? e.contentRect.width : node.clientWidth;
          if (w > 0) {
            try { Plotly.Plots.resize(node); } catch { /* not plotted yet */ }
          }
        }
      });
      ro.observe(node);
    } catch { return undefined; }
    return () => ro.disconnect();
  }, [failed]);   // `failed` swaps the div for the error card and back — re-attach to the live node
  if (failed) return <div className="error">הרכבת הגרף נכשלה — התשובות המלאות מוצגות מטה</div>;
  return <div className="plotly-chart" dir="ltr" ref={el} />;
}

export default function TrendCompare({ decl, db, onRoute, onHandoff, prefill, focus, autorun, active, onDone }) {
  const [rows, setRows] = useState([{ id: 1, min: false, busy: false, err: "", env: null, tick: 0 }]);
  const [mode, setMode] = useState("auto");                  // auto | overlay | split
  const [open, setOpen] = useState({});                      // row id -> its <details> is open
  const [vals, setVals] = useState({});                      // row id -> the form's CURRENT values (via onValues)
  const ref = useRef(null);

  useEffect(() => {
    if (focus && ref.current) ref.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [focus]);

  const viewDecl = decl.inputs?.view;
  const view = viewDecl ? (viewDecl.choices?.includes("chart") ? "chart" : viewDecl.default) : undefined;

  const patch = (id, p) => setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...p } : r)));

  const runOne = useCallback(async (id, values) => {
    patch(id, { busy: true, err: "" });
    try {
      const res = await runAction(decl.name, db, view ? { ...values, view } : values);
      patch(id, { env: res, busy: false });
      if (onDone) onDone(decl.name, res);
    } catch (e) {
      patch(id, { err: String(e.message || e), env: null, busy: false });
    }
  }, [decl.name, db, view, onDone]);

  const addRow = () => setRows((rs) => {
    if (rs.length >= MAX_ROWS) return rs;
    // prefill from row 1's CURRENT form values (the approved design: "same thing, change one field");
    // fall back to its last run's spec when the form was never edited this session
    const first = rs[0]?.env?.data;
    const pre = vals[rs[0]?.id]
      || (first && first.measure
          ? { measure: first.measure, granularity: first.granularity, road_type: first.road_type,
              from_year: first.from_year, to_year: first.to_year }
          : undefined);
    return [...rs, { id: Math.max(...rs.map((r) => r.id)) + 1, min: false, busy: false, err: "", env: null,
                     tick: 0, pre }];
  });
  const dropRow = (id) => setRows((rs) => rs.filter((r) => r.id !== id));
  const runAll = () => setRows((rs) => rs.map((r) => (r.min ? r : { ...r, tick: r.tick + 1 })));

  // composable = completed CHART trend runs (a refusal/error card renders inline in its row, never composes)
  const composable = rows.filter((r) => !r.min && r.env?.kind === "chart" && r.env.data?.type === "accidents/trend");
  const decision = composable.length >= 2 ? decide(composable.map((r) => r.env.data)) : null;
  const effective = decision && decision.auto !== "stack" ? (mode === "auto" ? decision.auto : mode) : null;
  const composed = Boolean(effective);
  const forcedOverGaps = composed && effective === "overlay" && !decision.gapsEqual;

  const [he, en] = String(decl.label || decl.name).split(" · ");
  return (
    <section className={`panel${focus ? " panel-focus" : ""}`} ref={ref} id={`action-${decl.name}`}>
      <div className="panel-head">
        <h2>{he}</h2>
        <span className="chip ltr">{en || decl.name}</span>
        <span className="help">{decl.help}</span>
        {/* trend renders through this panel, not ActionPanel — its reading line must live here too */}
        {BLURBS[decl.name] && <span className="blurb muted" style={{ flexBasis: "100%" }}>{BLURBS[decl.name]}</span>}
      </div>

      {rows.map((r, i) => (
        <div key={r.id} className={`compare-row${r.min ? " compare-min" : ""}`}>
          {i > 0 && (
            <div className="compare-row-head">
              <span className="muted">השוואה {i + 1}</span>
              <button type="button" className="mini" onClick={() => patch(r.id, { min: !r.min })}>
                {r.min ? "הרחב" : "מזער"}
              </button>
              <button type="button" className="mini" onClick={() => dropRow(r.id)}>הסר</button>
            </div>
          )}
          {!r.min && (
            <>
              <Form inputs={decl.inputs || {}} onRun={(v) => runOne(r.id, v)} busy={r.busy}
                    prefill={i === 0 ? prefill : r.pre} autorun={i === 0 && autorun && Boolean(db)}
                    runTick={r.tick} onValues={(v) => setVals((o) => ({ ...o, [r.id]: v }))} />
              {r.err && <div className="error">{r.err}</div>}
              {!r.err && !r.env && <div className="empty small">עדיין לא הורץ — לחצו «הרץ»</div>}
              {/* a non-chart answer (refusal / error card) stays inline next to its own form; chart answers
                  render BELOW the compare bar so the + השוואה control is visible without scrolling (user find) */}
              {r.env && !composable.includes(r) && (
                <Answer env={r.env} onRoute={onRoute} onHandoff={onHandoff} active={active} />
              )}
            </>
          )}
        </div>
      ))}

      <div className="compare-bar">
        {rows.length < MAX_ROWS && (
          <button type="button" className="mini" onClick={addRow}>+ השוואה</button>
        )}
        {rows.filter((r) => !r.min).length >= 2 && (
          <button type="button" className="primary" onClick={runAll}
                  disabled={rows.some((r) => r.busy)}>הרץ הכול</button>
        )}
        {composed && (
          <span className="seg-toggle" role="group" aria-label="compose mode">
            {[["auto", "אוטו"], ["overlay", "מאוחד"], ["split", "מפוצל"]].map(([v, label]) => (
              <button key={v} type="button" className={mode === v ? "on" : ""}
                      onClick={() => setMode(v)}>{label}</button>
            ))}
          </span>
        )}
        {rows.length > 1 && (
          <span className="compare-note">ההשוואה היא תצוגת עמוד — כל ריצה נרשמת בפנקס בנפרד</span>
        )}
      </div>

      {decision && decision.auto === "stack" && (
        <div className="empty small">רזולוציות שונות (שנה מול חודש) אינן מורכבות לגרף אחד — התשובות מוצגות בנפרד</div>
      )}
      {composed && (
        <>
          <ComposedFigure runs={composable} effective={effective} gapsEqual={decision.gapsEqual} />
          {forcedOverGaps && (
            <div className="compare-note">
              איחוד כפוי על כיסויים שונים: פס הפער הוסר — תקופות חסרות: {composable
                .filter((r) => (r.env.data.gap_periods || []).length)
                .map((r) => `${labelOf(r)} (${r.env.data.gap_periods.join(", ")})`).join(" · ") || "אין"}
            </div>
          )}
          {composable.map((r) => (
            <details key={r.id} className="face" open={Boolean(open[r.id])}
                     onToggle={(e) => setOpen((o) => ({ ...o, [r.id]: e.target.open }))}>
              <summary>התשובה המלאה · {labelOf(r)}</summary>
              {open[r.id] && <Answer env={r.env} onRoute={onRoute} onHandoff={onHandoff} active={active} />}
            </details>
          ))}
        </>
      )}
      {!composed && composable.map((r) => (
        <Answer key={r.id} env={r.env} onRoute={onRoute} onHandoff={onHandoff} active={active} />
      ))}
    </section>
  );
}
