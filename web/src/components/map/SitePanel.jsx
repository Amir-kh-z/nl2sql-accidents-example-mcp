import React, { useEffect, useState } from "react";
import { runAction } from "../../api.js";
import Card from "../Card.jsx";

// P10: the click panel — site_profile rendered as sections. What the server did not compute is ABSENT here
// and its degrade caveat shows in the ribbon (never a blank or an invented number). Digit ranges use ASCII
// hyphens; Latin/keys sit in .ltr islands (the bidi checklist for every new surface).


function Spark({ years, acc, mu }) {
  const w = 320; const h = 52; const pad = 2;
  const vmax = Math.max(1, ...acc, ...(mu || []).filter((v) => v != null));
  const x = (i) => pad + (i * (w - 2 * pad)) / Math.max(1, years.length - 1);
  const y = (v) => h - pad - ((v || 0) * (h - 2 * pad)) / vmax;
  const accPts = acc.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const muPts = (mu || []).map((v, i) => (v == null ? null : `${x(i)},${y(v)}`)).filter(Boolean).join(" ");
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true">
      <polyline points={accPts} fill="none" stroke="#2da898" strokeWidth="1.6" />
      {muPts && <polyline points={muPts} fill="none" stroke="#e8504c" strokeWidth="1.4" strokeDasharray="4 3" />}
    </svg>
  );
}

function KV({ k, v, ltr }) {
  return (
    <div className="kv"><span className="k">{k}</span><span className={`v${ltr ? " ltr" : ""}`}>{v}</span></div>
  );
}

export default function SitePanel({ db, site, years, onClose, onHandoff, onExplain }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [env, setEnv] = useState(null);

  useEffect(() => {
    if (!site || !db) return;
    let alive = true;
    setBusy(true); setErr(""); setEnv(null);
    runAction("site_profile", db, { site: site.site_key, from_year: years[0], to_year: years[1], view: "chart" })
      .then((res) => { if (alive) setEnv(res); })
      .catch((e) => { if (alive) setErr(String(e.message || e)); })
      .finally(() => { if (alive) setBusy(false); });
    return () => { alive = false; };
    // years as SCALARS: the array identity churns with every scene refetch (color toggle) and re-ran this
    // expensive fetch for identical values (sweep L11)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [site, db, years[0], years[1]]);

  useEffect(() => {                                   // Escape closes — the panel must never be a trap
    if (!site) return undefined;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [site, onClose]);

  if (!site) return null;
  const spec = env && env.kind === "chart" ? env.data : null;
  const mb = spec ? spec.model : null;
  const sev = spec ? spec.severity_rel : null;
  const yearsList = spec ? spec.rows.map((r) => r[0]) : [];
  const accCol = spec ? spec.columns.indexOf("accidents") : -1;
  const muCol = spec ? spec.columns.indexOf("mu") : -1;

  return (
    <aside className="site-panel" dir="rtl" aria-label="site profile">
      <button type="button" className="close" onClick={onClose} aria-label="close">✕</button>
      <h3>{spec ? spec.site.label : site.label}</h3>
      <div className="key ltr">{site.site_key}</div>
      {busy && <div className="empty small">טוען את פרופיל האתר…</div>}
      {err && <div className="error">{err}</div>}
      {env && env.kind === "markdown" && <Card text={env.data} />}
      {env && env.kind === "error" && <div className="error">{env.data}</div>}
      {spec && (
        <>
          <div className="section">
            <KV k="תאונות עם נפגעים" v={spec.splits.accidents.toLocaleString()} ltr />
            <KV k="קטלניות · קשות · קלות"
                v={`${spec.splits.fatal} · ${spec.splits.severe} · ${spec.splits.slight}`} ltr />
            {spec.splits.night + spec.splits.day > 0 && (
              <KV k="לילה" v={`${Math.round((100 * spec.splits.night) / (spec.splits.night + spec.splits.day))}%`} ltr />
            )}
            {accCol >= 0 && <Spark years={yearsList} acc={spec.rows.map((r) => r[accCol])}
                                   mu={muCol >= 0 ? spec.rows.map((r) => r[muCol]) : null} />}
          </div>
          {mb && (
            <div className="section">
              <h4>מדדי המודל (מקטע)</h4>
              <span className="model-chip">🔮 תחזית מודל · <span className="ltr">{mb.model_id}</span></span>
              <KV k="צפוי לפי המודל" v={mb.mu} ltr />
              <KV k="נצפה" v={mb.observed} ltr />
              <KV k={<>עודף · <bdi className="ltr">excess</bdi></>} v={mb.excess > 0 ? `+${mb.excess}` : mb.excess} ltr />
              <KV k="EB" v={mb.eb} ltr />
              <KV k="רווח תשעים אחוז" v={`${mb.lo90}-${mb.hi90}`} ltr />
              <div className="verdict">{mb.verdict}</div>
              {mb.drivers && mb.drivers.length > 0 && (
                <KV k="מה מזין את התחזית" v={mb.drivers.map((d) => d.label).join(" · ")} />
              )}
              {onExplain && mb.segment && (
                <button type="button" className="mini" style={{ marginBlockStart: 6 }}
                        onClick={() => onExplain(`${mb.segment.road}/${mb.segment.seg}`)}>
                  הסבר SHAP מלא לפי שנים ←
                </button>
              )}
            </div>
          )}
          {sev && (
            <div className="section">
              <h4>פרופיל חומרה מותנה — יחסי בלבד</h4>
              <span className="model-chip">🔮 מודל חומרה · <span className="ltr">{sev.model_id}</span></span>
              {sev.labels.map((lb, c) => (
                <KV key={lb} k={lb} v={`פי ${sev.relative[c].toFixed(2)}`} />
              ))}
              <div className="muted">על {sev.n_persons.toLocaleString()} נפגעי האתר עצמם · מול בסיס שנות האימות</div>
            </div>
          )}
          {spec.caveats && spec.caveats.length > 0 && (
            <ul className="ribbon">{spec.caveats.map((c, i) => <li key={i}>{c}</li>)}</ul>
          )}
          <button type="button" className="mini" onClick={() => onHandoff(spec.site_key)}>
            לפני/אחרי לאתר הזה ←
          </button>
          <div className="credit">{spec.credit}</div>
        </>
      )}
    </aside>
  );
}
