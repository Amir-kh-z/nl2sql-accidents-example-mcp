import React, { useEffect, useRef, useState } from "react";
import Seg from "./Seg.jsx";

// The form is built from the action's declarations (GET /api/modules): kind, Hebrew label, default, choices, ASCII
// help. Number inputs are sent as JSON numbers (an empty field falls back to the declared default server-side);
// `view` is never shown — the page decides the view (chart when available).

function initial(inputs) {
  const out = {};
  Object.entries(inputs).forEach(([name, decl]) => {
    if (name === "view") return;
    out[name] = decl.default;
  });
  return out;
}

function payloadOf(inputs, values) {
  const payload = {};
  Object.entries(inputs).forEach(([name, decl]) => {
    if (name === "view") return;
    const v = values[name];
    if (decl.kind === "number") {
      if (v === "" || v === null || v === undefined) return;      // server default
      const n = Number(v);
      if (!Number.isNaN(n)) payload[name] = n;
    } else if (decl.kind === "bool") {
      payload[name] = Boolean(v);
    } else {
      payload[name] = v;
    }
  });
  return payload;
}

export default function Form({ inputs, onRun, busy, prefill, autorun, runTick, onValues }) {
  const [values, setValues] = useState(() => initial(inputs));
  const seenTick = useRef(runTick);            // the mount-time tick — a remount must NOT replay an old bump

  useEffect(() => {
    if (prefill) setValues((v) => ({ ...v, ...prefill }));
  }, [prefill]);

  // `?run=<action>` deep link (demo pre-flight, headless checks): run once with the defaults
  useEffect(() => {
    if (autorun) onRun(payloadOf(inputs, initial(inputs)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autorun]);

  // P11: an external "run all" — the parent bumps runTick and the form submits its CURRENT values.
  // Guarded by a ref so it fires only on an actual CHANGE: the effect also runs on mount, and a minimized
  // row's Form remounts with the old tick still in parent state (sweep high: a silent default-values re-run).
  useEffect(() => {
    if (runTick !== seenTick.current) {
      seenTick.current = runTick;
      onRun(payloadOf(inputs, values));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runTick]);

  const set = (name, value) => setValues((v) => {
    const next = { ...v, [name]: value };
    if (onValues) onValues(next);              // P11: the compare panel prefills new rows from CURRENT values
    return next;
  });

  const submit = (e) => {
    e.preventDefault();
    onRun(payloadOf(inputs, values));
  };

  return (
    <form className="controls" onSubmit={submit}>
      {Object.entries(inputs).map(([name, decl]) => {
        if (name === "view") return null;
        const id = `f-${name}-${Math.random().toString(36).slice(2, 6)}`;
        const v = values[name];
        let field;
        if (decl.kind === "choice") {
          const choices = decl.choices || [];
          // P13: a tiny choice reads faster as a segmented control than a dropdown — but only when it
          // fits (<= 3 options, every label <= 12 chars); year lists and long labels keep the <select>.
          const segish = choices.length > 0 && choices.length <= 3 &&
                         choices.every((c) => String(c).length <= 12);
          field = segish ? (
            <Seg label={decl.label || name} options={choices} value={v ?? ""}
                 onChange={(val) => set(name, val)} />
          ) : (
            <select id={id} value={v ?? ""} onChange={(e) => set(name, e.target.value)}>
              {choices.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          );
        } else if (decl.kind === "bool") {
          field = <input id={id} type="checkbox" checked={Boolean(v)} onChange={(e) => set(name, e.target.checked)} />;
        } else if (decl.kind === "number") {
          field = <input id={id} type="number" step="1" className="ltr" value={v ?? ""} onChange={(e) => set(name, e.target.value)} />;
        } else {
          field = <input id={id} type="text" dir="auto" value={v ?? ""} onChange={(e) => set(name, e.target.value)} />;
        }
        return (
          <div className="field" key={name} title={decl.help || ""}>
            <label htmlFor={id}>{decl.label || name} <span className="muted ltr">{name}</span></label>
            {field}
          </div>
        );
      })}
      <button type="submit" className="primary" disabled={busy}>{busy ? "מריץ…" : "הרץ"}</button>
    </form>
  );
}
