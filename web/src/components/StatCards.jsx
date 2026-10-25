import React, { useMemo } from "react";

// P13: the KPI strip above the tab bar, parsed from the about card App already fetches at boot —
// no extra request, no ledger write. The server-side contract (about.py, extended concurrently) is a
// "# מדדים אחרונים" section of `**key** — value` lines:
//   # מדדים אחרונים
//   - **שנה אחרונה** — 2024
//   - **תאונות** — 8,315 · לפני: 8,832
//   - **הרוגים** — 439 · לפני: 361
//   - **פצועים קשה** — 2,808 · לפני: 2,668
// Parsing is SCOPED to that section (the card carries an unrelated `**תאונות**` line higher up) and
// tolerates a missing leading "- ". An old server or the wrong DB has no section → render nothing.
// CSS contract (added by the styles.css owner): .stat-cards / .stat-card / .stat-num / .stat-label /
// .delta.up (an increase — red, worse) / .delta.down.

const METRIC_KEYS = ["תאונות", "הרוגים", "פצועים קשה"];

function toInt(s) {
  const n = parseInt(String(s).replace(/,/g, ""), 10);
  return Number.isFinite(n) ? n : null;
}

export function parseKpis(text) {
  const lines = String(text || "").split("\n");
  const start = lines.findIndex((l) => l.trim() === "# מדדים אחרונים");
  if (start < 0) return null;
  const entries = {};
  for (let i = start + 1; i < lines.length; i++) {
    if (lines[i].trim().startsWith("#")) break;                     // next section — stop
    const m = lines[i].match(/^\s*(?:-\s*)?\*\*([^*]+)\*\*\s*—\s*(.+)$/);
    if (m) entries[m[1].trim()] = m[2].trim();
  }
  const year = toInt(entries["שנה אחרונה"]);
  if (year === null) return null;
  const cards = [];
  METRIC_KEYS.forEach((key) => {
    const v = entries[key];
    if (!v) return;
    const m = v.match(/^([\d,]+)(?:\s*·\s*לפני:\s*([\d,]+))?/);
    if (!m) return;
    const cur = toInt(m[1]);
    if (cur === null) return;
    cards.push({ key, cur, prev: m[2] ? toInt(m[2]) : null });
  });
  return cards.length ? { year, cards } : null;
}

function Delta({ cur, prev }) {
  if (!prev || prev <= 0) return null;
  const pct = ((cur - prev) / prev) * 100;
  const cls = pct > 0 ? "delta up" : pct < 0 ? "delta down" : "delta";
  const txt = pct > 0 ? `▲ +${pct.toFixed(1)}%` : pct < 0 ? `▼ ${pct.toFixed(1)}%` : "0.0%";
  return <span className={`${cls} ltr`} title={`לפני: ${prev.toLocaleString()}`}>{txt}</span>;
}

export default function StatCards({ about }) {
  const parsed = useMemo(
    () => (about && about.kind === "markdown" ? parseKpis(about.data) : null),
    [about],
  );
  if (!parsed) return null;
  return (
    <div className="stat-cards">
      {parsed.cards.map((c) => (
        <div className="stat-card" key={c.key}>
          <div className="stat-num ltr">{c.cur.toLocaleString()}</div>
          <div className="stat-label">{c.key} · <span className="ltr">{parsed.year}</span></div>
          <Delta cur={c.cur} prev={c.prev} />
        </div>
      ))}
    </div>
  );
}
