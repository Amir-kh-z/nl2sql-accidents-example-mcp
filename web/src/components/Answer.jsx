import React, { useCallback, useState } from "react";
import Card from "./Card.jsx";
import MapView from "./MapView.jsx";
import PlotlyChart, { PLOTLY_TYPES } from "./PlotlyChart.jsx";

// The answer anatomy (PLAN_1 §3), one component for every Result kind: title · denominator badge · caveat ribbon ·
// the face (map / png / card / table / sql / error) · table · show-SQL · CBS credit · the Layer-0 note.

const BADGE = {
  exposure: { cls: "badge-green", word: "מכנה חשיפה אמיתי" },
  counts: { cls: "badge-amber", word: "ספירות בלבד" },
  none: { cls: "badge-red", word: "ללא מכנה" },
  na: { cls: "badge-grey", word: "לא רלוונטי" },
};

const nf = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });
const nfPlain = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4, useGrouping: false });
// identifier / year columns are never thousands-grouped (2,019 reads as a count, not a year)
const NO_GROUP = /^(year|month|first_year|last_year|change_year|from_year|to_year|accident_id|code|city|city_code|road|seg|rank|manufacture_year|cc_band|band_code|quintile|decile|class|train_until|seed|rounds|best|n_train|n_holdout|idx)$/;

export function fmt(v, col) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return (col && NO_GROUP.test(col) ? nfPlain : nf).format(v);
  if (typeof v === "boolean") return v ? "✓" : "✗";
  return String(v);
}

function siteKeyOf(columns, row) {
  const ci = Object.fromEntries(columns.map((c, i) => [c, i]));
  if ("site_key" in ci) return row[ci.site_key];
  if ("road" in ci && "seg" in ci && "km_from" in ci && "km_to" in ci && row[ci.km_from] !== null && row[ci.km_to] !== null) {
    return `road:${row[ci.road]}/${row[ci.km_from]}-${row[ci.km_to]}`;
  }
  return null;
}

// before_after's table carries the site's before/after count pair — append a computed Δ column
// (2026-09-06): red up (more accidents = bad), green down, '·' where a side is missing (the double row).
function deltaCell(row, bi, ai) {
  const b = row[bi];
  const a = row[ai];
  if (typeof b !== "number" || typeof a !== "number") return <td className="num">·</td>;
  const d = a - b;
  if (d > 0) return <td className="num"><span style={{ color: "var(--red)" }}>▲ +{nfPlain.format(d)}</span></td>;
  if (d < 0) return <td className="num"><span style={{ color: "var(--green)" }}>▼ −{nfPlain.format(-d)}</span></td>;
  return <td className="num">0</td>;
}

export function Table({ columns, rows, onHandoff, selectedKey, onSelect, limit = 15 }) {
  const [all, setAll] = useState(false);
  if (!columns || !rows) return null;
  const shown = all ? rows : rows.slice(0, limit);
  const withKey = onHandoff && rows.length && siteKeyOf(columns, rows[0]) !== null;
  // ab_scan rows carry the discovered candidate year — the hand-off pre-sets it in before_after
  const cyi = columns.indexOf("change_year");
  const bi = columns.indexOf("site_before");
  const ai = columns.indexOf("site_after");
  const withDelta = bi >= 0 && ai >= 0;
  const linked = Boolean(onSelect) || selectedKey != null;     // linked selection joins on siteKeyOf, never on indices
  return (
    <div className="table-wrap">
      <table className="ltr">
        <thead>
          <tr>{withKey && <th />}{columns.map((c) => <th key={c}>{c}</th>)}{withDelta && <th>Δ</th>}</tr>
        </thead>
        <tbody>
          {shown.map((row, i) => {
            const key = linked ? siteKeyOf(columns, row) : null;
            return (
              <tr key={i}
                  className={key != null && key === selectedKey ? "selected" : undefined}
                  onClick={key != null && onSelect ? () => onSelect(key) : undefined}
                  style={key != null && onSelect ? { cursor: "pointer" } : undefined}>
                {withKey && (
                  <td>
                    <button type="button" className="mini" title="לפני/אחרי לאתר הזה"
                            onClick={() => onHandoff(siteKeyOf(columns, row),
                                                     cyi >= 0 && typeof row[cyi] === "number" ? { change_year: row[cyi] } : undefined)}>
                      לפני/אחרי
                    </button>
                  </td>
                )}
                {row.map((v, j) => <td key={j} className={typeof v === "number" ? "num" : ""}>{fmt(v, columns[j])}</td>)}
                {withDelta && deltaCell(row, bi, ai)}
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length > limit && (
        <button type="button" className="mini" onClick={() => setAll(!all)}>
          {all ? "הצג פחות" : `הצג את כל ${rows.length} השורות`}
        </button>
      )}
    </div>
  );
}

export default function Answer({ env, onRoute, onHandoff, onExplain, active }) {
  const [showNote, setShowNote] = useState(false);
  // linked selection (2026-09-06): the map face and the ranking-table face share one selectedKey,
  // joined on siteKeyOf — a marker click highlights the row, a row click pans the map and opens the tooltip
  const [selectedKey, setSelectedKey] = useState(null);
  // second hand-off (2026-09-06): the popup's הסבר מודל 🔮 hands the segment's road/seg to studio_explain —
  // the SitePanel/onExplain contract, threaded App → ActionPanel → here. The route-only branch remains as a
  // defensive fallback for any older caller that renders Answer without the prop.
  const explain = useCallback((roadSeg) => {
    if (onExplain) onExplain(roadSeg);
    else if (onRoute) onRoute("studio_explain");
  }, [onExplain, onRoute]);
  if (!env) return null;
  const { kind, data, title, note } = env;
  const spec = kind === "chart" && data && typeof data === "object" ? data : null;
  const denom = spec?.denominator;
  const badge = denom ? BADGE[denom.kind] || BADGE.na : null;
  const caveats = spec?.caveats || [];

  let face = null;
  if (kind === "chart") {
    // P8: the map keeps Leaflet; every mapped chart type renders interactively via plotly (browser bidi —
    // Hebrew is simply correct); anything unmapped falls back to the matplotlib PNG twin, as does a
    // builder error inside PlotlyChart itself. Layer 0 always shows the PNG — the twin contract.
    face = spec.type === "accidents/map"
      ? <MapView spec={spec} onHandoff={onHandoff} onExplain={explain} selected={selectedKey}
                 onSelect={setSelectedKey} active={active} />
      : PLOTLY_TYPES.has(spec.type)
        ? <PlotlyChart spec={spec} title={title} />
        : spec.png_base64
          ? <img className="png" alt={title} src={`data:image/png;base64,${spec.png_base64}`} />
          : <Table columns={spec.columns} rows={spec.rows} onHandoff={onHandoff} />;
  } else if (kind === "markdown") {
    face = <Card text={data} onRoute={onRoute} />;
  } else if (kind === "table") {
    face = <Table columns={data.columns} rows={data.rows} onHandoff={onHandoff} />;
  } else if (kind === "sql") {
    face = <pre className="sql ltr">{data}</pre>;
  } else if (kind === "error") {
    face = <div className="error">{String(data)}</div>;
  }

  return (
    <section className="answer">
      <div className="answer-head">
        <h3>{title}</h3>
        {badge && (
          <span className={`badge ${badge.cls}`} title={denom.label}>
            {badge.word} · {denom.label}
          </span>
        )}
      </div>
      {spec && spec.model_id && (
        // P9: any answer computed BY a model announces it — the instructor's "where are the predictions?"
        // The tail is spec-driven (spec.chip): "vs what actually happened" is wrong on faces with no observed
        // side (what_if's two hypotheticals, the global drivers profile) — the P9 sweep's finding.
        <div className="model-chip">
          🔮 תחזית המודל <bdi className="ltr">{spec.model_id}</bdi> — {spec.chip || "צפוי מול מה שקרה בפועל"}
        </div>
      )}
      {caveats.length > 0 && (
        <ul className="ribbon">
          {caveats.map((c, i) => <li key={i}>{c}</li>)}
        </ul>
      )}
      {face}
      {spec && spec.type !== "accidents/map" && spec.rows && spec.rows.length > 0 && (
        <details className="face">
          <summary>טבלה ({spec.rows.length} שורות)</summary>
          <Table columns={spec.columns} rows={spec.rows} onHandoff={onHandoff} />
        </details>
      )}
      {spec && spec.type === "accidents/map" && spec.rows && (
        <details className="face">
          <summary>דירוג ({spec.rows.length} יחידות)</summary>
          <Table columns={spec.columns} rows={spec.rows} onHandoff={onHandoff}
                 selectedKey={selectedKey} onSelect={setSelectedKey} />
        </details>
      )}
      {spec && spec.sql && (
        <details className="face">
          <summary>הצג SQL</summary>
          <pre className="sql ltr">{spec.sql}</pre>
          {spec.basis && <div className="basis ltr">{spec.basis}</div>}
        </details>
      )}
      {spec && spec.credit && <div className="credit">{spec.credit}</div>}
      {note && (
        <div className="note-row">
          <button type="button" className="mini" onClick={() => setShowNote(!showNote)}>הערה (Layer 0)</button>
          {showNote && <div className="note">{note}</div>}
        </div>
      )}
    </section>
  );
}
