import React, { useState } from "react";
import Card from "./Card.jsx";

// The status strip: parsed from the `about` card's known lines (**חיבור**, **כיסוי**, **מודל אתר פרוס**); the raw
// card stays one click away. P4 wires the deployed-model chip to the registry. The build's own version is baked in
// by Vite (`__PLUGIN_VERSION__`, from web/package.json) so a refusing or missing connection still names the build.

function chipsOf(text) {
  const out = {};
  String(text || "").split("\n").forEach((line) => {
    const m = line.match(/^\*\*([^*]+)\*\* — (.*)$/);
    if (m) out[m[1]] = m[2];
  });
  return out;
}

// `busy` = the api.js ref-counted run counter is > 0 (App subscribes) — a page-wide "something is
// running" pulse, so a long action (severity training ~25 s) is visibly alive from any tab.
export default function Header({ db, about, version, dbSource, busy }) {
  const [open, setOpen] = useState(false);
  const refused = about && about.kind === "markdown" && String(about.data).startsWith("# ❌");
  const failed = about && about.kind === "error";
  const chips = about && !refused && !failed ? chipsOf(about.data) : {};
  const shownVersion = version || (typeof __PLUGIN_VERSION__ !== "undefined" ? __PLUGIN_VERSION__ : "");
  return (
    <header className="header">
      <div className="header-row">
        <h1>🚦 מעבדת הבטיחות בדרכים</h1>
        <span className="sub ltr">Road Safety Lab · nl2sql-roadsafety-lab {shownVersion}</span>
      </div>
      <div className="strip">
        {busy && <span className="chip busy">עובד…</span>}
        <span className={`chip ${db ? "" : "chip-bad"}`} title={dbSource}>
          חיבור: <span className="ltr">{db || "—"}</span>{dbSource === "fallback" ? " (ניחוש — לא מהסרגל)" : ""}
        </span>
        {about === null && db && <span className="chip busy">בודק את המסד…</span>}
        {failed && <span className="chip chip-bad">❌ החיבור אינו זמין: <span className="ltr">{String(about.data)}</span></span>}
        {refused && <span className="chip chip-bad">❌ זה אינו מסד תאונות הדרכים — הפעולות יסרבו</span>}
        {chips["חיבור"] && <span className="chip chip-ok">✓ {chips["חיבור"]}</span>}
        {chips["כיסוי"] && <span className="chip">{chips["כיסוי"]}</span>}
        {"מודל אתר פרוס" in chips && (
          <span className={`chip ${chips["מודל אתר פרוס"] === "אין" ? "chip-amber" : "chip-ok"}`}>
            מודל אתר פרוס: {chips["מודל אתר פרוס"]}
          </span>
        )}
        <span className="chip">רישיון: נתוני למ״ס באישור אישי · שימוש פנימי</span>
        {about && !failed && <button type="button" className="mini" onClick={() => setOpen(!open)}>{open ? "סגור אודות" : "אודות"}</button>}
      </div>
      {open && about && !failed && <Card text={about.data} />}
    </header>
  );
}
