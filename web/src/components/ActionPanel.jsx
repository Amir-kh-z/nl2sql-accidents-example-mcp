import React, { useCallback, useEffect, useRef, useState } from "react";
import Form from "./Form.jsx";
import Answer from "./Answer.jsx";
import { runAction } from "../api.js";
import { BLURBS } from "./blurbs.js";

// One action = one card: the form from the declarations, Run, the answer anatomy. The page always asks for the
// chart view when the action has one (the spec carries png + rows + sql + caveats in ONE call); otherwise the
// declared default view.

export default function ActionPanel({ decl, db, onRoute, onHandoff, onExplain, prefill, focus, autorun, active, onDone }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [env, setEnv] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    if (focus && ref.current) ref.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [focus]);

  const viewDecl = decl.inputs?.view;
  const view = viewDecl ? (viewDecl.choices?.includes("chart") ? "chart" : viewDecl.default) : undefined;

  const run = useCallback(async (values) => {
    setBusy(true);
    setErr("");
    // P13: a long action (severity training ~25 s) used to leave the PREVIOUS answer on screen with only
    // the button label changing — pull the panel into view so the placeholder below is actually seen.
    if (ref.current) ref.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    try {
      const inputs = view ? { ...values, view } : values;
      const res = await runAction(decl.name, db, inputs);
      setEnv(res);
      if (onDone) onDone(decl.name, res);
    } catch (e) {
      setErr(String(e.message || e));
      setEnv(null);
    } finally {
      setBusy(false);
    }
  }, [decl.name, db, view, onDone]);

  const [he, en] = String(decl.label || decl.name).split(" · ");
  const blurb = BLURBS[decl.name];
  return (
    <section className={`panel${focus ? " panel-focus" : ""}`} ref={ref} id={`action-${decl.name}`}>
      <div className="panel-head">
        <h2>{he}</h2>
        <span className="chip ltr">{en || decl.name}</span>
        <span className="help">{decl.help}</span>
        {/* page-owned Hebrew reading line (blurbs.js) — action.help itself stays ASCII by contract */}
        {blurb && <span className="blurb muted" style={{ flexBasis: "100%" }}>{blurb}</span>}
      </div>
      <Form inputs={decl.inputs || {}} onRun={run} busy={busy} prefill={prefill} autorun={autorun && Boolean(db)} />
      {err && <div className="error">{err}</div>}
      {/* P13: while running, the answer slot shows progress INSTEAD of the stale previous answer */}
      {busy && <div className="empty small">מריץ… {he}</div>}
      {!busy && !err && !env && <div className="empty small">עדיין לא הורץ — לחצו «הרץ»</div>}
      {!busy && <Answer env={env} onRoute={onRoute} onHandoff={onHandoff} onExplain={onExplain} active={active} />}
    </section>
  );
}
