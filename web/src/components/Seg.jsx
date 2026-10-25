import React from "react";

// P13: ONE segmented control for the whole page — extracted from the two near-identical copies
// (MapTab's .color-toggle, now migrated here, and TrendCompare's inline .seg-toggle, owned elsewhere —
// migrate it onto this component the next time its owner touches it). Accessible shape: role="group"
// with an aria-label, aria-pressed on every button; styling rides the existing .seg-toggle CSS (P11).
// Options are strings, or {value, label} pairs when the display text differs from the sent value.

export default function Seg({ options, value, onChange, label, disabled }) {
  return (
    <span className="seg-toggle" role="group" aria-label={label || undefined}>
      {(options || []).map((o) => {
        const v = o !== null && typeof o === "object" ? o.value : o;
        const text = o !== null && typeof o === "object" ? o.label : String(o);
        const on = v === value;
        return (
          <button key={String(v)} type="button" className={on ? "on" : ""} aria-pressed={on}
                  disabled={disabled} onClick={() => { if (!on) onChange(v); }}>
            {text}
          </button>
        );
      })}
    </span>
  );
}
