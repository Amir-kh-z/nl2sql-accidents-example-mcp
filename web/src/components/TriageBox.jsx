import React, { useState } from "react";
import Card from "./Card.jsx";
import { runAction } from "../api.js";

/** A question box on top of every tab: the rule-based gate says what the data cannot answer, or routes. */
export default function TriageBox({ db, onRoute }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [text, setText] = useState("");

  const ask = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const res = await runAction("triage", db, q ? { question: q } : {});
      setText(res.kind === "markdown" ? res.data : String(res.data));
    } catch (ex) {
      setErr(String(ex.message || ex));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="triage">
      <form onSubmit={ask} className="triage-form">
        <label htmlFor="triage-q">טריאז׳ · מה אפשר לשאול</label>
        <input id="triage-q" type="text" dir="auto" value={q} placeholder="למשל: איזה דגם רכב הכי בטוח?"
               onChange={(e) => setQ(e.target.value)} />
        <button type="submit" className="primary" disabled={busy}>{busy ? "…" : "שאל"}</button>
      </form>
      {err && <div className="error">{err}</div>}
      {text && <Card text={text} onRoute={onRoute} />}
    </div>
  );
}
