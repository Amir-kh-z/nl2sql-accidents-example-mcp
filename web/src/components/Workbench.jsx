import React, { useCallback, useEffect, useRef, useState } from "react";
import Answer from "./Answer.jsx";
import { runAction } from "../api.js";

// P13 round 2 — the studio WORKBENCH, the instructor's pick from the rival's Models tab ("exactly what he
// did — but in addition to our things"): one compact panel per model family with a shared parameter row and
// a bar of one-click verbs, all writing into ONE output region per family. The rival's renderML is replaced
// by our full Answer anatomy (badge · ribbon · faces · show-SQL · credit), and the verbs call the SAME
// actions the full panels below expose — this is a faster cockpit over them, not a second API.
// It opens on the registry (his "state visible at a glance"): studio_models is ledger-exempt since P13r2,
// so the auto-load cannot pollute the stage ledger; every OTHER verb is a deliberate click.

const FAMILIES = [
  {
    id: "site",
    title: "מודל אתרים (מקטעים)",
    params: [
      { name: "train_until", label: "אימון עד", kind: "number", def: 2023 },
      { name: "features", label: "מאפיינים", kind: "choice", def: "doc-11", fromAction: "studio_train_site" },
    ],
    verbs: [
      { label: "אימון", action: "studio_train_site", inputs: (p) => ({ train_until: p.train_until, features: p.features }) },
      { label: "אימות", action: "studio_validate", inputs: () => ({ model_id: "latest" }) },
      { label: "פריסה", action: "studio_deploy", inputs: () => ({ model_id: "latest", family: "site" }) },
      { label: "דירוג excess", action: "site_ranking", inputs: () => ({}) },
      { label: "הסבר גלובלי", action: "studio_explain", inputs: () => ({ site: "" }) },
      { label: "רישום", action: "studio_models", inputs: () => ({ family: "site" }) },
    ],
  },
  {
    id: "severity",
    title: "מודל חומרה (נפגעים)",
    params: [
      { name: "train_until", label: "אימון עד", kind: "number", def: 2022 },
      { name: "features", label: "מאפיינים", kind: "choice", def: "person-12", fromAction: "studio_train_severity" },
    ],
    verbs: [
      { label: "אימון", action: "studio_train_severity", inputs: (p) => ({ train_until: p.train_until, features: p.features }) },
      { label: "אימות", action: "studio_validate_severity", inputs: () => ({ model_id: "latest" }) },
      { label: "פריסה", action: "studio_deploy", inputs: () => ({ model_id: "latest", family: "severity" }) },
      { label: "חיזוי", action: "severity_predict", inputs: () => ({}) },
      { label: "מה-אם", action: "what_if", inputs: () => ({}) },
      { label: "הסבר", action: "severity_explain", inputs: () => ({}) },
      { label: "רישום", action: "studio_models", inputs: () => ({ family: "severity" }) },
    ],
  },
];

function FamilyPanel({ fam, db, actions, active, onRoute, onHandoff, onExplain }) {
  const [params, setParams] = useState(() =>
    Object.fromEntries(fam.params.map((p) => [p.name, p.def])));
  const [busyVerb, setBusyVerb] = useState("");
  const [err, setErr] = useState("");
  const [env, setEnv] = useState(null);
  const [loadedRegistry, setLoadedRegistry] = useState(false);
  const outRef = useRef(null);

  const runVerb = useCallback(async (verb, scroll = true) => {
    const decl = actions[verb.action];
    if (!decl || !db) return;
    setBusyVerb(verb.label);
    setErr("");
    if (scroll && outRef.current) outRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    try {
      const viewDecl = decl.inputs?.view;
      const view = viewDecl ? (viewDecl.choices?.includes("chart") ? "chart" : viewDecl.default) : undefined;
      const inputs = { ...verb.inputs(params), ...(view ? { view } : {}) };
      setEnv(await runAction(verb.action, db, inputs));
    } catch (e) {
      setErr(String(e.message || e));
      setEnv(null);
    } finally {
      setBusyVerb("");
    }
  }, [actions, db, params]);

  // "opens on the registry": the ledger-exempt studio_models loads once, on the tab's FIRST activation —
  // never any other verb (auto-running a ledger-writing action would pollute the stage before a show)
  useEffect(() => {
    if (active && db && !loadedRegistry && actions.studio_models) {
      setLoadedRegistry(true);
      runVerb(fam.verbs.find((v) => v.action === "studio_models"), false);
    }
  }, [active, db, loadedRegistry, actions, fam.verbs, runVerb]);

  return (
    <div className="wb-panel">
      <div className="wb-head">
        <h3>{fam.title}</h3>
        {fam.params.map((p) => {
          const choices = p.kind === "choice"
            ? actions[p.fromAction]?.inputs?.[p.name]?.choices || [p.def] : null;
          return (
            <label key={p.name} className="wb-param">
              <span>{p.label}</span>
              {choices ? (
                <select value={params[p.name]}
                        onChange={(e) => setParams((s) => ({ ...s, [p.name]: e.target.value }))}>
                  {choices.map((ch) => <option key={ch} value={ch}>{ch}</option>)}
                </select>
              ) : (
                <input type="number" className="ltr" value={params[p.name]}
                       onChange={(e) => setParams((s) => ({ ...s, [p.name]: Number(e.target.value) }))} />
              )}
            </label>
          );
        })}
      </div>
      <div className="wb-verbs">
        {fam.verbs.map((v) => (
          <button key={v.label} type="button" disabled={Boolean(busyVerb) || !actions[v.action]}
                  title={actions[v.action] ? v.action : `${v.action} — לא מותקן`}
                  onClick={() => runVerb(v)}>
            {v.label}
          </button>
        ))}
      </div>
      <div ref={outRef}>
        {busyVerb && <div className="empty small">מריץ… {busyVerb}</div>}
        {err && <div className="error">{err}</div>}
        {!busyVerb && <Answer env={env} onRoute={onRoute} onHandoff={onHandoff} onExplain={onExplain} active={active} />}
      </div>
    </div>
  );
}

export default function Workbench({ db, actions, active, onRoute, onHandoff, onExplain }) {
  if (!actions) return null;
  return (
    <section className="workbench panel">
      <div className="panel-head">
        <h2>שולחן עבודה</h2>
        <span className="chip ltr">workbench</span>
        <span className="blurb muted" style={{ flexBasis: "100%" }}>
          פקודות בלחיצה אחת על שתי משפחות המודלים — אותן פעולות בדיוק כמו הפאנלים המלאים מטה, עם ברירות
          המחדל של הבמה. הרישום נטען מעצמו; כל השאר רץ רק בלחיצה.
        </span>
      </div>
      <div className="wb-grid">
        {FAMILIES.map((fam) => (
          <FamilyPanel key={fam.id} fam={fam} db={db} actions={actions} active={active}
                       onRoute={onRoute} onHandoff={onHandoff} onExplain={onExplain} />
        ))}
      </div>
    </section>
  );
}
