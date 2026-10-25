import { useEffect, useState } from "react";

// P13: ONE source of truth for chart theming — the charts read the SAME CSS custom properties
// styles.css already defines (the dark-mode values for the semantic tokens live there too), so the
// plotly faces and the DOM around them can never disagree. Plotly needs concrete color strings, not
// var() references, so we snapshot the computed values and re-read them when the scheme flips.
export function tok(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function chartTokens() {
  return {
    ink: tok("--app-text"),      // primary text / axis ink
    inkSoft: tok("--muted"),     // tick labels, secondary annotations
    grid: tok("--border"),       // gridlines, zero lines
    card: tok("--card"),         // raised surfaces (gap bands, heat-matrix zero cells)
    bg: tok("--app-bg"),         // the page ground (charts keep transparent paper over it)
    accent: tok("--accent"),
    red: tok("--red"),
    amber: tok("--amber"),
    green: tok("--green"),
    grey: tok("--grey"),         // neutral marks (null dots, reference lines, damage-only series)
  };
}

// Re-render charts when the OS scheme flips: the page has no manual toggle — styles.css switches on
// prefers-color-scheme, so matchMedia's change event is exactly the moment the vars change. The state
// object is replaced only on a real flip, so it is a stable useEffect dependency between flips.
export function useThemeTokens() {
  const [tokens, setTokens] = useState(chartTokens);
  useEffect(() => {
    let mq;
    try {
      mq = window.matchMedia("(prefers-color-scheme: dark)");
    } catch {
      return undefined;                       // headless DOM without matchMedia — keep the snapshot
    }
    const onChange = () => setTokens(chartTokens());
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return tokens;
}
