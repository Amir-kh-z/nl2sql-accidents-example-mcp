import React from "react";

// P13: static orientation for the studio tab — which model family answers which question, over which
// population, with what target and gate. Pure JSX, no fetch: the gate numbers restate
// studio/constants.GATE and the severity gate as documentation (the live values render in the actions
// below). The base table CSS is LTR for data tables — this one is Hebrew prose, so direction and
// alignment are overridden inline (styles.css is owned elsewhere).

const COLS = ["משפחה", "שאלה", "אוכלוסייה", "יעד", "שער"];
const ROWS = [
  {
    family: "אתר",
    q: "כמה תאונות צפויות למקטע?",
    pop: "מקטעי ספירת תנועה 2017–2024",
    target: "ספירת תאונות לשנה",
    gate: "Spearman ≥ 0.3 · כיול ±25% · יחס סטייה ≤ 1.5",
  },
  {
    family: "חומרה",
    q: "מה חומרת הפגיעה הצפויה לנפגע?",
    pop: "נפגעים 2010–2024",
    target: "הרוג/קשה/קל",
    gate: "Recall הרוג ≥ 0.5 · AUC ≥ 0.8 · פער ≤ 0.05",
  },
];

const CELL = { textAlign: "right", whiteSpace: "normal" };

export default function StudioIntro() {
  return (
    <div className="card studio-intro">
      <h3>שתי משפחות מודלים</h3>
      <div className="table-wrap">
        <table dir="rtl" style={{ direction: "rtl", width: "100%" }}>
          <thead>
            <tr>{COLS.map((h) => <th key={h} style={CELL}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r.family}>
                <td style={CELL}><strong>{r.family}</strong></td>
                <td style={CELL}>{r.q}</td>
                <td style={CELL}>{r.pop}</td>
                <td style={CELL}>{r.target}</td>
                <td style={CELL}>{r.gate}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
