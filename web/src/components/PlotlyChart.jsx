import { useEffect, useRef, useState } from "react";
// cartesian dist since P13 round 2: basic ships NO heatmap trace, and the instructor picked the rival's
// real heatmap over our 168-square scatter stand-in — cartesian adds heatmap/histogram for ~15% bundle
import Plotly from "plotly.js-cartesian-dist";
import { useThemeTokens } from "../theme.js";

// P8: interactive charts for the 🚦 page — the browser does real Unicode bidi, so Hebrew is simply correct
// (no mirror hack anywhere client-side). The matplotlib PNG twin stays in the spec for Layer 0, the Plan-B
// deck, and as the runtime fallback: an unmapped spec type or a builder error falls back to the <img> in
// Answer.jsx.
// P13: structural colors (ink, gridlines, gap bands, reference lines) come from the CSS custom properties
// via theme.js, so dark mode never draws near-black text on a dark card; meaning-bound series hues
// (teal/red/orange severity trio etc.) stay fixed — they read on both grounds and mirror charts.py.
const TEAL = "#0d9488", RED = "#c0392b", ORANGE = "#f7931e";
const SEVERE = "#f7931e", SLIGHT = "#0d9488";
// "killed" is by design the INK hue (charts.py) — it must follow the token or it vanishes on a dark
// ground; strongest-contrast-against-the-ground = worst outcome holds in both themes.
const killedColor = (t) => t.ink;
const seriesPalette = (t) => [TEAL, RED, ORANGE, t.ink, "#7d3c98", "#2471a3"];
const FONT_FAMILY = "'Segoe UI', 'Assistant', 'Noto Sans Hebrew', sans-serif";

const ci = (spec) => Object.fromEntries(spec.columns.map((c, i) => [c, i]));
const col = (spec, name) => spec.rows.map((r) => r[ci(spec)[name]]);
const segLabel = (r, c) => `${r[c.road]}/${r[c.seg]} · ${r[c.name_from] || ""} ← ${r[c.name_to] || ""}`;

function base(t, overrides = {}) {
  return {
    font: { family: FONT_FAMILY, color: t.ink, size: 12 },
    // transparent paper on purpose: the page ground behind it is already token-painted by styles.css
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: { l: 20, r: 30, t: 16, b: 44 },
    dragmode: false,
    showlegend: false,
    xaxis: { gridcolor: t.grid, zerolinecolor: t.grid, tickfont: { size: 11, color: t.inkSoft } },
    yaxis: { gridcolor: t.grid, zerolinecolor: t.grid, tickfont: { size: 11, color: t.inkSoft } },
    ...overrides,
  };
}

// horizontal category charts: labels on the RIGHT (RTL reading), first row on top. automargin is load-bearing —
// without it the right-side category labels clip at the edge; the legend lives at the LEFT corner so it never
// collides with them.
function hbarAxes(t, labels, height) {
  // deterministic right margin from the longest label — automargin under-reserved in headless rendering
  const longest = Math.max(0, ...labels.map((l) => String(l).length));
  return {
    height,
    yaxis: { side: "right", autorange: "reversed", automargin: true,
             tickfont: { size: 11.5, color: t.inkSoft }, gridcolor: "rgba(0,0,0,0)" },
    xaxis: { gridcolor: t.grid, zeroline: false, automargin: true, tickfont: { size: 11, color: t.inkSoft } },
    margin: { l: 16, r: Math.min(360, 16 + longest * 6.2), t: 10, b: 34 },
  };
}

const LEGEND_LEFT = { orientation: "h", x: 0, xanchor: "left", y: 1.06, font: { size: 11 } };

const rowHeight = (n, per = 26, pad = 110) => Math.max(300, n * per + pad);

// P13: a dashed baseline without a name reads as data — every reference line carries a small muted label
const refNote = (t, text, pos) => ({ text, showarrow: false, font: { size: 10, color: t.inkSoft }, ...pos });
// placement for a VERTICAL x=v line: just inside the top edge, to the line's right (the top margin is
// only ~10px on the hbar layouts, so the label must live inside the plot area, not above it)
const vRefPos = (x) => ({ x, xref: "x", xanchor: "left", xshift: 4, y: 1, yref: "paper", yanchor: "top" });

// the severity family's relative charts: 3 class bars (killed/severe/slight palette) around the 1.0 baseline
function ratioBars(spec, ycol, t) {
  const c = ci(spec);
  const labels = col(spec, "label");
  return {
    data: [{ type: "bar", orientation: "h", y: labels, x: col(spec, ycol),
             marker: { color: [killedColor(t), SEVERE, SLIGHT] },
             hovertemplate: "%{y}: פי %{x:.2f}<extra></extra>" }],
    layout: base(t, { ...hbarAxes(t, labels, 300),
                      shapes: [{ type: "line", xref: "x", yref: "paper", x0: 1, x1: 1, y0: 0, y1: 1,
                                 line: { color: ORANGE, width: 1.5, dash: "dash" } }],
                      annotations: [refNote(t, "יחס = 1", vRefPos(1))] }),
  };
}

// ── P12: the SHAP faces (PNG twins: charts.beeswarm / dependence_dots / ratio_with_drivers). The SERVER
// computes subsampling + jitter (deterministic — spec dots are byte-comparable across runs); the page only
// places them. Coloring policy mirrors charts.py: value-color ONLY ordered features, nominal codes neutral
// grey, NULL dots hollow — "לא ידוע" is a real model input, shown as such.
const NOMINAL_GREY = "#9aa4ad";
const phiScale = (t) => [[0, TEAL], [0.5, t.grid], [1, ORANGE]];

// shared by severity_explain and studio_explain's swarm face
function beeswarmLayout(swarm, t) {
  const n = swarm.features.length;
  const idx = swarm.phi.map((_, i) => i);
  const trace = (is, marker) => ({
    type: "scatter", mode: "markers",
    x: is.map((i) => swarm.phi[i]),
    y: is.map((i) => (n - 1 - swarm.row[i]) + swarm.jitter[i]),
    text: is.map((i) => swarm.label[i]), marker,
    hovertemplate: "%{text}<br>φ %{x:.3f}<extra></extra>",
  });
  const coloredI = idx.filter((i) => swarm.value_norm[i] != null);
  const longest = Math.max(0, ...swarm.features.map((l) => String(l).length));
  return {
    data: [
      // scatter markers hide their colorbar unless showscale is set — gated like the PNG twin's
      // show_bar (an all-nominal swarm has no honest 0-1 scale to draw)
      trace(coloredI, { color: coloredI.map((i) => swarm.value_norm[i]), colorscale: phiScale(t),
                        cmin: 0, cmax: 1, size: 5, showscale: swarm.ordered.some(Boolean),
                        // the bar lives in the LEFT margin: plotly's default (~paper x 1.02) paints it
                        // over the side-right Hebrew row labels (the instructor's screenshot, 2026-09-05)
                        colorbar: { title: { text: "ערך מנורמל", font: { size: 11, color: t.inkSoft } },
                                    x: -0.02, xanchor: "right", len: 0.8, thickness: 10,
                                    tickfont: { size: 10, color: t.inkSoft } } }),
      trace(idx.filter((i) => swarm.value_norm[i] == null && !swarm.is_null[i]),
            { color: NOMINAL_GREY, size: 5, opacity: 0.55 }),
      trace(idx.filter((i) => swarm.is_null[i]),
            { symbol: "circle-open", color: t.grey, size: 5 }),
    ],
    layout: base(t, {
      height: Math.max(320, 34 * n),
      yaxis: { side: "right", automargin: true, autorange: false, range: [-0.7, n - 0.3],
               tickvals: swarm.features.map((_, i) => n - 1 - i), ticktext: swarm.features,
               tickfont: { size: 11.5, color: t.inkSoft }, gridcolor: "rgba(0,0,0,0)" },
      xaxis: { title: { text: swarm.xlabel || "תרומת φ", font: { size: 11 } }, gridcolor: t.grid,
               zeroline: false, automargin: true, tickfont: { size: 11, color: t.inkSoft } },
      margin: { l: 76, r: Math.min(360, 16 + longest * 6.2), t: 10, b: 40 },
      shapes: [{ type: "line", xref: "x", yref: "paper", x0: 0, x1: 0, y0: 0, y1: 1,
                 line: { color: t.grey, width: 1 } }],
      annotations: [refNote(t, "φ = 0", vRefPos(0))],
    }),
  };
}

// the dependence face: x = the server-jittered value axis (tick slots for nominals, "לא ידוע" the last
// slot), y = φ; vertical spread = interactions. Monochrome by design — the value IS the x axis.
function dependenceLayout(dep, t) {
  const idx = dep.phi.map((_, i) => i);
  const trace = (is, marker) => ({
    type: "scatter", mode: "markers",
    x: is.map((i) => dep.xj[i]), y: is.map((i) => dep.phi[i]),
    text: is.map((i) => dep.label[i]), marker,
    hovertemplate: "%{text}<br>φ %{y:.3f}<extra></extra>",
  });
  const ticksAxis = dep.ticks
    ? { tickvals: dep.ticks.map((_, i) => i), ticktext: dep.ticks.map((t2) => String(t2[1])),
        tickangle: dep.ticks.length > 6 ? 30 : 0 }
    : {};
  // the numeric-axis NULL strip (sweep): the builder reserves null_x right of the known range —
  // name it, so the hollow dots there read as the explicit "לא ידוע" slot the caveat promises
  const nullNote = (!dep.ticks && dep.null_x != null && dep.is_null.some(Boolean))
    ? [{ x: dep.null_x, y: 1.03, xref: "x", yref: "paper", text: dep.null_label || "לא ידוע",
         showarrow: false, font: { size: 10, color: t.inkSoft } }]
    : [];
  return {
    data: [
      trace(idx.filter((i) => !dep.is_null[i]), { color: TEAL, size: 5, opacity: 0.5 }),
      trace(idx.filter((i) => dep.is_null[i]), { symbol: "circle-open", color: t.grey, size: 5 }),
    ],
    layout: base(t, {
      height: 380,
      xaxis: { ...ticksAxis, gridcolor: t.grid, zeroline: false, automargin: true,
               title: dep.xlabel ? { text: dep.xlabel, font: { size: 11 } } : undefined,
               tickfont: { size: 10.5, color: t.inkSoft } },
      yaxis: { title: { text: dep.ylabel || "תרומת φ", font: { size: 11 } }, gridcolor: t.grid,
               zerolinecolor: t.grid, tickfont: { size: 11, color: t.inkSoft } },
      annotations: [...nullNote,
                    refNote(t, "φ = 0", { xref: "paper", x: 1, xanchor: "right",
                                          yref: "y", y: 0, yanchor: "bottom" })],
      shapes: [{ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: 0, y1: 0,
                 line: { color: t.grey, width: 1 } }],
    }),
  };
}

// severity_predict / what_if with the P12 drivers panel (PNG twin: charts.ratio_with_drivers): right
// panel (RTL: read first) = the EXISTING ratio bars around the 1.0 baseline; left panel = the profile's
// φ drivers of the chosen class (grey = היתר / בסיס המודל, signed colors otherwise).
function ratioWithDrivers(spec, ycol, t) {
  const d = spec.drivers;
  const hasBias = d.bias != null;
  // switch_feature is set ONLY by what_if: those bars are Δφ BETWEEN the scenarios, not contributions —
  // the axis and hover must say so (the PNG twin always did; the sweep caught the interactive face lying)
  const isDelta = d.switch_feature != null;
  const dLabels = [...d.items.map((it) => it.label), "היתר", ...(hasBias ? ["בסיס המודל"] : [])];
  const dVals = [...d.items.map((it) => it.phi), d.rest, ...(hasBias ? [d.bias] : [])];
  const dSwitch = [...d.items.map((it) => it.feature === d.switch_feature), false,
                   ...(hasBias ? [false] : [])];
  const labels = col(spec, "label");
  const longest = Math.max(0, ...labels.map((l) => String(l).length));
  return {
    data: [
      { type: "bar", orientation: "h", xaxis: "x", yaxis: "y", y: dLabels, x: dVals,
        marker: { color: dVals.map((v, i) => (i >= d.items.length ? NOMINAL_GREY
                                                                  : v >= 0 ? ORANGE : TEAL)),
                  line: { width: dSwitch.map((s) => (s ? 1.6 : 0)), color: t.inkSoft } },
        hovertemplate: isDelta ? "%{y}: Δφ %{x:+.2f}<extra></extra>"
                               : "%{y}: φ %{x:+.2f}<extra></extra>" },
      { type: "bar", orientation: "h", xaxis: "x2", yaxis: "y2", y: labels, x: col(spec, ycol),
        marker: { color: [killedColor(t), SEVERE, SLIGHT] },
        hovertemplate: "%{y}: פי %{x:.2f}<extra></extra>" },
    ],
    layout: base(t, {
      height: 360,
      xaxis: { domain: [0, 0.42],
               title: { text: isDelta
                          ? `שינוי תרומת φ בין התרחישים · ${d.class_label || ""}`.trim()
                          : (d.class_label ? `תרומת φ · ${d.class_label}` : "תרומת φ"),
                        font: { size: 11 } },
               gridcolor: t.grid, zeroline: false, automargin: true,
               tickfont: { size: 10.5, color: t.inkSoft } },
      yaxis: { side: "right", autorange: "reversed", automargin: true,
               tickfont: { size: 10, color: t.inkSoft }, gridcolor: "rgba(0,0,0,0)" },
      xaxis2: { domain: [0.58, 1], gridcolor: t.grid, zeroline: false, automargin: true,
                tickfont: { size: 11, color: t.inkSoft } },
      yaxis2: { anchor: "x2", side: "right", autorange: "reversed", automargin: true,
                tickfont: { size: 11.5, color: t.inkSoft }, gridcolor: "rgba(0,0,0,0)" },
      margin: { l: 16, r: Math.min(360, 16 + longest * 6.2), t: 10, b: 40 },
      shapes: [
        { type: "line", xref: "x", yref: "paper", x0: 0, x1: 0, y0: 0, y1: 1,
          line: { color: t.grey, width: 1 } },
        { type: "line", xref: "x2", yref: "paper", x0: 1, x1: 1, y0: 0, y1: 1,
          line: { color: ORANGE, width: 1.5, dash: "dash" } },
      ],
      annotations: [refNote(t, "φ = 0", vRefPos(0)),
                    refNote(t, "יחס = 1", { ...vRefPos(1), xref: "x2" })],
    }),
  };
}

// ── Wave 2: the zones tab's ranking hbars (zone_ranking / city_ranking share one shape). The zone
// snapshot is a SEPARATE universe from the yearly series (the blurb carries that warning) — the chart
// itself stays a plain house-style ranking: value bars desc, first row on top, the measure's own
// components in the hover. Bars take the theme accent (structural, not meaning-bound: rank IS the
// position, color encodes nothing), with the top three at full strength so the leaders read at a glance.
const RANK_VALUE_LABELS = {
  per_capita: "שיעור לאוכלוסייה",
  density: "צפיפות תאונות",
  ped_share: "שיעור הולכי רגל",
};

function rankedHbar(t, labels, values, customdata, hover, xtitle) {
  const axes = hbarAxes(t, labels, rowHeight(labels.length));
  return {
    data: [{ type: "bar", orientation: "h", y: labels, x: values,
             marker: { color: t.accent, opacity: values.map((_, i) => (i < 3 ? 1 : 0.72)) },
             customdata, hovertemplate: hover }],
    layout: base(t, { ...axes,
                      xaxis: { ...axes.xaxis, title: { text: xtitle, font: { size: 11 } } } }),
  };
}

const BUILDERS = {
  "accidents/trend"(spec, t) {
    const c = ci(spec);
    // monthly specs keep x="year" (make_spec's default) — build the composite label or 24 months
    // collapse onto 2 category ticks (P8 sweep's plotly high)
    const xs = spec.granularity === "month" && c.month != null
      ? spec.rows.map((r) => `${r[c.year]}-${String(r[c.month]).padStart(2, "0")}`)
      : col(spec, spec.x);
    const covered = c.covered != null ? col(spec, "covered") : xs.map(() => true);
    const ys = spec.rows.map((r, i) => (covered[i] === false ? null : r[c[spec.y]]));
    const shapes = xs.flatMap((x, i) => covered[i] === false
      ? [{ type: "rect", xref: "x", yref: "paper", x0: i - 0.5, x1: i + 0.5, y0: 0, y1: 1,
           fillcolor: t.card, line: { width: 0 }, layer: "below" }] : []);
    return {
      data: [{ type: "scatter", mode: "lines+markers", x: xs, y: ys, connectgaps: false,
               line: { color: TEAL, width: 2.5 }, marker: { size: 6, color: TEAL },
               hovertemplate: "%{x}: %{y:,}<extra></extra>" }],
      layout: base(t, { height: 380, shapes,
                        xaxis: { type: "category", tickfont: { size: 11, color: t.inkSoft } } }),
    };
  },

  // P13: the מפה חיה click panel's chart face — the yearly observed strip, with the deployed site
  // model's μ overlaid as a dashed line when the spec carries the model block (road segments only).
  // Years the model cannot cover (pre-exposure era, outside the panel) are null → the dashed line
  // simply stops (connectgaps false), like the trend builder's gap semantics.
  "accidents/site_profile"(spec, t) {
    const c = ci(spec);
    const xs = col(spec, "year").map(String);
    const covered = c.covered != null ? col(spec, "covered") : xs.map(() => true);
    const obs = spec.rows.map((r, i) => (covered[i] === false ? null : r[c.accidents]));
    const shapes = xs.flatMap((_, i) => covered[i] === false
      ? [{ type: "rect", xref: "x", yref: "paper", x0: i - 0.5, x1: i + 0.5, y0: 0, y1: 1,
           fillcolor: t.card, line: { width: 0 }, layer: "below" }] : []);
    const observed = { type: "scatter", mode: "lines+markers", x: xs, y: obs, connectgaps: false,
                       name: "נצפה", line: { color: TEAL, width: 2.5 }, marker: { size: 6, color: TEAL },
                       hovertemplate: "%{x}: %{y:,} תאונות<extra></extra>" };
    if (c.ksi_accidents != null) {
      observed.customdata = col(spec, "ksi_accidents");
      observed.hovertemplate = "%{x}: %{y:,} תאונות · קשות+קטלניות: %{customdata:,}<extra></extra>";
    }
    const data = [observed];
    const hasMu = c.mu != null;
    if (hasMu) {
      const mu = spec.rows.map((r, i) => (covered[i] === false ? null : r[c.mu]));
      data.push({ type: "scatter", mode: "lines", x: xs, y: mu, connectgaps: false,
                  name: "צפוי (מודל)", line: { color: RED, width: 2, dash: "dash" },
                  hovertemplate: "צפוי %{x}: %{y:.1f}<extra></extra>" });
    }
    return {
      data,
      layout: base(t, { height: 380, shapes, showlegend: hasMu,
                        legend: { ...LEGEND_LEFT, y: 1.12 },
                        ...(hasMu ? { margin: { l: 20, r: 30, t: 40, b: 44 } } : {}),
                        xaxis: { type: "category", tickfont: { size: 10.5, color: t.inkSoft } } }),
    };
  },

  "accidents/segment_rates"(spec, t) {
    const c = ci(spec);
    const labels = spec.rows.map((r) => segLabel(r, c));
    const rate = col(spec, "rate_per_100m_vkm"), lo = col(spec, "rate_lo"), hi = col(spec, "rate_hi");
    return {
      data: [{ type: "bar", orientation: "h", y: labels, x: rate, marker: { color: TEAL },
               error_x: { type: "data", symmetric: false, array: hi.map((h, i) => h - rate[i]),
                          arrayminus: lo.map((l, i) => rate[i] - l), color: t.inkSoft, thickness: 1.8, width: 4 },
               customdata: spec.rows.map((r) => [r[c.accidents], r[c.vkm_millions]]),
               hovertemplate: "%{y}<br>שיעור: %{x:.1f} · תאונות: %{customdata[0]:,} · " +
                              "‎%{customdata[1]:,.1f}M‎ ק״מ-רכב<extra></extra>" }],
      layout: base(t, hbarAxes(t, labels, rowHeight(labels.length))),
    };
  },

  "accidents/site_ranking"(spec, t) {
    const c = ci(spec);
    const labels = spec.rows.map((r) => segLabel(r, c));
    const mu = col(spec, "mu"), lo = col(spec, "lo90"), hi = col(spec, "hi90");
    const obs = col(spec, "observed"), sig = col(spec, "significant"), excess = col(spec, "excess");
    return {
      data: [
        { type: "bar", orientation: "h", y: labels, x: mu, name: "צפוי",
          marker: { color: sig.map((s) => (s ? RED : TEAL)) },
          error_x: { type: "data", symmetric: false, array: hi.map((h, i) => h - mu[i]),
                     arrayminus: mu.map((m, i) => m - lo[i]), color: t.inkSoft, thickness: 1.8, width: 4 },
          customdata: excess, hovertemplate: "%{y}<br>צפוי: %{x:.1f} · עודף: %{customdata:+.1f}<extra></extra>" },
        { type: "scatter", mode: "markers", y: labels, x: obs, name: "נצפה",
          marker: { symbol: "circle-open", size: 10, color: t.ink, line: { width: 2 } },
          hovertemplate: "נצפה: %{x}<extra></extra>" },
      ],
      layout: base(t, { ...hbarAxes(t, labels, rowHeight(labels.length)), showlegend: true,
                        legend: LEGEND_LEFT }),
    };
  },

  "accidents/severity_profile"(spec, t) {
    const c = ci(spec);
    // P13 round 2 (the instructor's pick from the rival's Trends tab): display=counts (by=year only) —
    // three ABSOLUTE severity lines, descending stroke weights, and OUR gap discipline: uncovered years
    // break the lines (null, connectgaps false) under a grey band — never bridged, never drawn as zero.
    if (spec.display === "counts") {
      const gap = new Set(spec.uncovered_years || []);
      const byYear = {};
      for (const r of spec.rows) byYear[Number(r[c.code])] = r;
      const xs = [];
      for (let y = spec.from_year; y <= spec.to_year; y++) xs.push(y);
      const line = (colName, name, color, width) => ({
        type: "scatter", mode: "lines+markers", x: xs, name, connectgaps: false,
        y: xs.map((y) => (gap.has(y) || !byYear[y] ? null : byYear[y][c[colName]])),
        line: { color, width }, marker: { size: 4.5, color },
        hovertemplate: `%{x} · ${name}: %{y:,}<extra></extra>`,
      });
      const shapes = xs.flatMap((y) => gap.has(y)
        ? [{ type: "rect", xref: "x", yref: "paper", x0: y - 0.5, x1: y + 0.5, y0: 0, y1: 1,
             fillcolor: t.card, line: { width: 0 }, layer: "below" }] : []);
      return {
        data: [line("killed", "הרוגים", killedColor(t), 3),
               line("severe", "פצועים קשה", SEVERE, 2.2),
               line("slight", "פצועים קל", SLIGHT, 1.6)],
        layout: base(t, { height: 380, shapes, showlegend: true,
                          legend: { ...LEGEND_LEFT, y: 1.07, traceorder: "reversed" },
                          xaxis: { dtick: xs.length > 12 ? 2 : 1, gridcolor: t.grid,
                                   tickfont: { size: 11, color: t.inkSoft } },
                          yaxis: { rangemode: "tozero", gridcolor: t.grid,
                                   tickfont: { size: 11, color: t.inkSoft } } }),
      };
    }
    const labels = col(spec, "label").map((l) => l || "");
    const totals = col(spec, "casualties");
    const mk = (colName, name, color) => ({
      type: "bar", orientation: "h", y: labels, x: col(spec, colName), name, marker: { color },
      hovertemplate: `%{y}<br>${name}: %{x:.1f}%<extra></extra>`,
    });
    return {
      data: [mk("slight_pct", "פצועים קל", SLIGHT), mk("severe_pct", "פצועים קשה", SEVERE),
             mk("killed_pct", "הרוגים", killedColor(t)),
             { type: "scatter", mode: "text", y: labels, x: labels.map(() => 104),
               text: totals.map((v) => v.toLocaleString("en-US")), textfont: { size: 11, color: t.inkSoft },
               textposition: "middle right", hoverinfo: "skip", showlegend: false }],
      layout: base(t, { ...hbarAxes(t, labels, rowHeight(labels.length)), barmode: "stack", showlegend: true,
                        legend: { ...LEGEND_LEFT, y: 1.07, traceorder: "reversed" },
                        xaxis: { range: [0, 118], tickvals: [0, 25, 50, 75, 100], gridcolor: t.grid,
                                 tickfont: { size: 11, color: t.inkSoft } } }),
    };
  },

  "accidents/vehicle_cells_ranking"(spec, t) {
    const c = ci(spec);
    if (spec.group === "cohort") {
      // P13 server contract (vehicle_cells group=cohort): per-manufacture-year aggregates, columns
      // ['manufacture_year','involvements','exposure_mkm','rate','eb_rate','tier'] — a cohort curve,
      // not a ranking: x = manufacture year ascending, y = the EB rate.
      const rows = [...spec.rows].sort((a, b) => a[c.manufacture_year] - b[c.manufacture_year]);
      const shapes = [], annotations = [];
      if (spec.global_rate != null) {
        shapes.push({ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1,
                      y0: spec.global_rate, y1: spec.global_rate,
                      line: { color: ORANGE, width: 1.5, dash: "dash" } });
        annotations.push(refNote(t, "שיעור ארצי", { xref: "paper", x: 0, xanchor: "left",
                                                    yref: "y", y: spec.global_rate, yanchor: "bottom" }));
      }
      return {
        data: [{ type: "scatter", mode: "lines+markers",
                 x: rows.map((r) => String(r[c.manufacture_year])),
                 y: rows.map((r) => r[c.eb_rate]),
                 line: { color: TEAL, width: 2.5 },
                 marker: { size: 7, color: rows.map((r) => (r[c.tier] === "highest_risk" ? RED : TEAL)) },
                 customdata: rows.map((r) => [r[c.rate], r[c.involvements], r[c.exposure_mkm]]),
                 hovertemplate: "שנתון %{x}<br>EB: %{y:.3f} · גולמי: %{customdata[0]:.3f}<br>" +
                                "מעורבויות: %{customdata[1]:,} · ‎%{customdata[2]:,.1f}M‎ ק״מ-רכב<extra></extra>" }],
        layout: base(t, { height: 380, shapes, annotations,
                          xaxis: { type: "category", tickfont: { size: 10.5, color: t.inkSoft } },
                          yaxis: { title: { text: "מעורבויות למיליון ק״מ (EB)", font: { size: 11 } },
                                   gridcolor: t.grid, zerolinecolor: t.grid,
                                   tickfont: { size: 11, color: t.inkSoft } } }),
      };
    }
    const labels = spec.rows.map((r) => `${r[c.cc_band_label]} · ${r[c.manufacture_year]}`);
    const eb = col(spec, "eb_rate_per_mkm"), raw = col(spec, "raw_rate_per_mkm");
    const tier = col(spec, "tier");
    return {
      data: [
        { type: "bar", orientation: "h", y: labels, x: eb, name: "EB",
          marker: { color: tier.map((v) => (v === "highest_risk" ? RED : TEAL)) },
          hovertemplate: "%{y}<br>EB: %{x:.3f}<extra></extra>" },
        { type: "scatter", mode: "markers", y: labels, x: raw, name: "גולמי",
          marker: { symbol: "circle-open", size: 9, color: t.ink, line: { width: 1.8 } },
          hovertemplate: "גולמי: %{x:.3f}<extra></extra>" },
      ],
      layout: base(t, { ...hbarAxes(t, labels, rowHeight(labels.length, 24)), showlegend: true,
                        legend: LEGEND_LEFT,
                        shapes: [{ type: "line", xref: "x", yref: "paper", x0: spec.global_rate,
                                   x1: spec.global_rate, y0: 0, y1: 1,
                                   line: { color: ORANGE, width: 1.5, dash: "dash" } }],
                        annotations: [refNote(t, "שיעור ארצי", vRefPos(spec.global_rate))] }),
    };
  },

  "accidents/before_after"(spec, t) {
    const k = spec.counts;
    const cats = ["אתר · לפני", "אתר · אחרי", "רשת · לפני", "רשת · אחרי"];
    const norm = (v) => [100, (100 * v[1]) / (v[0] || 1), 100, (100 * v[3]) / (v[2] || 1)];
    const mk = (key, name, color) => ({
      type: "bar", x: cats, y: norm(k[key]), name, marker: { color },
      text: k[key].map((v) => v.toLocaleString("en-US")), textposition: "outside",
      textfont: { size: 11, color: t.inkSoft }, hovertemplate: `${name} · %{x}: %{text}<extra></extra>`,
    });
    return {
      data: [mk("casualty", "נפגעים", TEAL), mk("damage_only", "נזק בלבד", t.grey)],
      layout: base(t, { height: 400, barmode: "group", showlegend: true,
                        legend: { ...LEGEND_LEFT, y: 1.14 },
                        yaxis: { title: { text: "לפני = 100", font: { size: 11 } }, gridcolor: t.grid },
                        annotations: [{ text: spec.headline || "", xref: "paper", yref: "paper", x: 1, y: 1.24,
                                        xanchor: "right", showarrow: false, font: { size: 13, color: t.ink } }],
                        margin: { l: 30, r: 12, t: 64, b: 40 } }),
    };
  },

  // Wave 2 server contract (zone_ranking — built to the concurrent action's spec): columns
  // ['label','value','accidents','population','area_km2','land_use'], spec.measure ∈
  // {per_capita, density, ped_share}. Sorted HERE so the visual guarantee (desc, leader on top)
  // never depends on the server's ORDER BY; the hover carries the measure's own components.
  "accidents/zone_ranking"(spec, t) {
    const c = ci(spec);
    const rows = [...spec.rows].sort((a, b) => (b[c.value] ?? -Infinity) - (a[c.value] ?? -Infinity));
    const labels = rows.map((r) => r[c.label] || "");
    const comp = spec.measure === "per_capita" ? { col: c.population, label: "אוכלוסייה", fmt: ":," }
               : spec.measure === "density" ? { col: c.area_km2, label: "שטח בקמ״ר", fmt: ":,.1f" }
               : null;                                       // ped_share: the accidents count IS the component
    // the row carries the land_use CODE; the spec ships land_use_labels (string keys) — the hover must
    // say "מסחר", not "2". Unknown/missing codes fall back to the raw value.
    const luLabel = (v) => (v == null || v === "" ? "" : ((spec.land_use_labels || {})[String(v)] ?? v));
    const customdata = rows.map((r) => [r[c.accidents], comp ? r[comp.col] : null, luLabel(r[c.land_use])]);
    const vlabel = RANK_VALUE_LABELS[spec.measure] || "ערך";
    const hover = rows.map((r) =>
      `%{y}<br>${vlabel}: %{x:,.2f} · תאונות: %{customdata[0]:,}` +
      (comp ? ` · ${comp.label}: %{customdata[1]${comp.fmt}}` : "") +
      (r[c.land_use] ? "<br>%{customdata[2]}" : "") + "<extra></extra>");
    return rankedHbar(t, labels, rows.map((r) => r[c.value]), customdata, hover, vlabel);
  },

  // Wave 2 server contract (city_ranking): columns ['city','region','value','accidents','killed',
  // 'area_km2'] — the same ranking shape, label = city · region; killed rides every hover, area only
  // when the measure divides by it.
  "accidents/city_ranking"(spec, t) {
    const c = ci(spec);
    const rows = [...spec.rows].sort((a, b) => (b[c.value] ?? -Infinity) - (a[c.value] ?? -Infinity));
    const labels = rows.map((r) => `${r[c.city]} · ${r[c.region]}`);
    const customdata = rows.map((r) => [r[c.accidents], r[c.killed], r[c.area_km2]]);
    const vlabel = RANK_VALUE_LABELS[spec.measure] || "ערך";
    const hover = `%{y}<br>${vlabel}: %{x:,.2f} · תאונות: %{customdata[0]:,} · הרוגים: %{customdata[1]:,}` +
                  (spec.measure === "density" ? " · שטח: %{customdata[2]:,.1f} קמ״ר" : "") +
                  "<extra></extra>";
    return rankedHbar(t, labels, rows.map((r) => r[c.value]), customdata, hover, vlabel);
  },

  // Wave 2 server contract (ab_scan): columns ['site_key','label','change_year','before','after',
  // 'ratio','z','controlled','direction'] — signed hbars of z, SERVER order kept (the scan's order IS
  // the ranking). Colors mirror the map's DIVERGING ramp endpoints (map/layers.js — not imported: that
  // module pulls the deck.gl chunk into this one); the neutral middle bucket is dropped on purpose —
  // a signed bar near zero is already visually near-zero. `direction` stays a table-face column: on
  // the chart the sign and the hue family say it (blue = improvement, red = deterioration).
  "accidents/ab_scan"(spec, t) {
    const c = ci(spec);
    const labels = spec.rows.map((r) => `${r[c.label]} · ${r[c.change_year]}`);
    const z = spec.rows.map((r) => r[c.z]);
    const zColor = (v) => (v <= -2 ? "#1d4ed8" : v < 0 ? "#93c5fd" : v < 2 ? "#fca5a5" : "#b91c1c");
    const customdata = spec.rows.map((r) => [r[c.before], r[c.after], r[c.ratio], r[c.controlled]]);
    const hover = spec.rows.map((r) => {
      const core = "%{y}<br>z: %{x:+.2f} · לפני: %{customdata[0]:,} ← אחרי: %{customdata[1]:,} · " +
                   "יחס: %{customdata[2]:.2f}";
      const ctrl = r[c.controlled];
      return (ctrl != null && ctrl !== "n/a" ? `${core}<br>בקרה: %{customdata[3]}` : core) + "<extra></extra>";
    });
    const axes = hbarAxes(t, labels, rowHeight(labels.length));
    return {
      data: [{ type: "bar", orientation: "h", y: labels, x: z, marker: { color: z.map(zColor) },
               customdata, hovertemplate: hover }],
      layout: base(t, { ...axes,
                        xaxis: { ...axes.xaxis, title: { text: "ציון z", font: { size: 11 } } },
                        shapes: [{ type: "line", xref: "x", yref: "paper", x0: 0, x1: 0, y0: 0, y1: 1,
                                   line: { color: t.grey, width: 1.5, dash: "dash" } }],
                        annotations: [refNote(t, "אין שינוי", vRefPos(0))] }),
    };
  },

  "accidents/weather_check"(spec, t) {
    const labels = col(spec, "cbs_weather_label");
    return {
      data: [{ type: "bar", orientation: "h", y: labels, x: col(spec, "pct_measured_rain"),
               marker: { color: TEAL },
               customdata: col(spec, "accidents"),
               hovertemplate: "%{y}<br>גשם נמדד: %{x:.1f}% · תאונות: %{customdata:,}<extra></extra>" }],
      layout: base(t, hbarAxes(t, labels, rowHeight(labels.length))),
    };
  },

  "accidents/two_wheelers"(spec, t) {
    const c = ci(spec);
    const series = seriesPalette(t);
    const ycol = spec.metric === "fatal" ? "fatal_per_1000" : "per_1000";
    const moto = spec.rows.filter((r) => r[c.active_fleet] != null);
    const bands = [...new Map(moto.map((r) => [r[c.band_code], r[c.unit]])).entries()];
    return {
      data: bands.map(([code, name], i) => {
        const rs = moto.filter((r) => r[c.band_code] === code);
        return { type: "scatter", mode: "lines+markers", name,
                 x: rs.map((r) => r[c.year]), y: rs.map((r) => r[c[ycol]]),
                 line: { color: series[i % series.length], width: 2.5 }, marker: { size: 6 },
                 hovertemplate: `${name} · %{x}: %{y}<extra></extra>` };
      }),
      layout: base(t, { height: 400, showlegend: true,
                        legend: { ...LEGEND_LEFT, y: 1.12 },
                        xaxis: { type: "category", tickfont: { size: 11, color: t.inkSoft } } }),
    };
  },

  // P13: the studio training cards' chart face (the specs carry NO png twin — before this builder the
  // chart view fell through to a blank image). Site family: per-year panel summary
  // (year, rows, sum_y, adt_known, static_assigned) → target totals + the ADT coverage the caveats cite.
  "accidents/studio_train"(spec, t) {
    const c = ci(spec);
    const years = col(spec, "year").map(String);
    const adtShare = spec.rows.map((r) => (r[c.rows] ? Math.round((1000 * r[c.adt_known]) / r[c.rows]) / 10
                                                    : null));
    return {
      data: [
        { type: "bar", xaxis: "x", yaxis: "y", x: years, y: col(spec, "sum_y"), name: "תאונות בלוח",
          marker: { color: TEAL }, customdata: col(spec, "rows"),
          hovertemplate: "%{x}: %{y:,} תאונות · %{customdata:,} שורות מקטע-שנה<extra></extra>" },
        { type: "scatter", mode: "lines+markers", xaxis: "x2", yaxis: "y2", x: years, y: adtShare,
          name: "ADT ידוע", line: { color: ORANGE, width: 2.5 }, marker: { size: 6, color: ORANGE },
          hovertemplate: "%{x}: ADT ידוע ב-%{y:.1f}% מהשורות<extra></extra>" },
      ],
      layout: base(t, { height: 380, showlegend: true, legend: { ...LEGEND_LEFT, y: 1.14 },
                        xaxis: { domain: [0, 0.55], type: "category",
                                 tickfont: { size: 10, color: t.inkSoft } },
                        yaxis: { title: { text: "תאונות", font: { size: 11 } }, gridcolor: t.grid,
                                 tickfont: { size: 11, color: t.inkSoft } },
                        xaxis2: { domain: [0.65, 1], type: "category",
                                  tickfont: { size: 10, color: t.inkSoft } },
                        yaxis2: { anchor: "x2", range: [0, 102],
                                  title: { text: "% ADT ידוע", font: { size: 11 } }, gridcolor: t.grid,
                                  tickfont: { size: 11, color: t.inkSoft } },
                        margin: { l: 40, r: 16, t: 56, b: 40 } }),
    };
  },

  // Severity family: per-year class counts (year, rows, killed, severe, slight) → the stacked yearly
  // composition, which SHOWS the share-drift story the gate caveats talk about.
  "accidents/studio_train_severity"(spec, t) {
    const c = ci(spec);
    const years = col(spec, "year").map(String);
    const mk = (name, label, color) => ({
      type: "bar", x: years, y: col(spec, name), name: label, marker: { color },
      customdata: spec.rows.map((r) => (r[c.rows] ? Math.round((1000 * r[c[name]]) / r[c.rows]) / 10 : 0)),
      hovertemplate: `%{x} · ${label}: %{y:,} (%{customdata}%)<extra></extra>`,
    });
    return {
      data: [mk("slight", "פצועים קל", SLIGHT), mk("severe", "פצועים קשה", SEVERE),
             mk("killed", "הרוגים", killedColor(t))],
      layout: base(t, { height: 380, barmode: "stack", showlegend: true,
                        legend: { ...LEGEND_LEFT, y: 1.12, traceorder: "reversed" },
                        xaxis: { type: "category", tickfont: { size: 10.5, color: t.inkSoft } } }),
    };
  },

  // P13 server contract (heat_matrix): columns ['day_of_week','hour_of_day','accidents'], 168 rows of
  // [dow 1-7, hour 0-23, count], day_labels = 7 Hebrew day names indexed dow-1, first day at the TOP.
  // A REAL heatmap trace since P13 round 2 (the cartesian dist ships it; the instructor preferred the
  // rival's continuous-cell look over the 168-square scatter stand-in): touching cells with a crisp
  // 1.5px gap, the token colorscale, and the sentence tooltip.
  "accidents/heat_matrix"(spec, t) {
    const c = ci(spec);
    const days = spec.day_labels || [];
    const z = days.map((_, d) => Array(24).fill(0));
    for (const r of spec.rows) z[r[c.day_of_week] - 1][r[c.hour_of_day]] = r[c.accidents];
    return {
      data: [{ type: "heatmap", z, x: Array.from({ length: 24 }, (_, h) => h), y: days,
               zmin: 0, xgap: 1.5, ygap: 1.5, hoverongaps: false,
               colorscale: [[0, t.card], [0.55, t.accent], [1, t.red]],
               // colorbar in the LEFT margin — the Hebrew day labels own the right edge
               colorbar: { title: { text: "תאונות", font: { size: 11, color: t.inkSoft } },
                           x: -0.02, xanchor: "right", len: 0.85, thickness: 10,
                           tickfont: { size: 10, color: t.inkSoft } },
               hovertemplate: "<b>%{y}</b> %{x}:00 — %{z:,} תאונות<extra></extra>" }],
      layout: base(t, {
        height: 7 * 38 + 120,
        xaxis: { range: [-0.5, 23.5], dtick: 3, gridcolor: "rgba(0,0,0,0)", zeroline: false,
                 tickfont: { size: 10.5, color: t.inkSoft },
                 title: { text: "שעה ביממה", font: { size: 11 } } },
        yaxis: { type: "category", categoryorder: "array", categoryarray: days,
                 autorange: "reversed",                       // first day (ראשון) at the top
                 side: "right", automargin: true, gridcolor: "rgba(0,0,0,0)",
                 tickfont: { size: 11.5, color: t.inkSoft } },
        margin: { l: 64, r: 60, t: 16, b: 44 },
      }),
    };
  },

  "accidents/studio_explain"(spec, t) {
    if (spec.swarm) return beeswarmLayout(spec.swarm, t);   // P12: the site-model beeswarm face
    const c = ci(spec);
    if (c.feature != null) {                       // the global mean|φ| profile
      const labels = col(spec, "label");
      return {
        data: [{ type: "bar", orientation: "h", y: labels, x: col(spec, "mean_abs_phi"),
                 marker: { color: TEAL },
                 customdata: col(spec, "mean_phi"),
                 hovertemplate: "%{y}<br>ממוצע |φ|: %{x:.4f} · ממוצע φ: %{customdata:+.4f}<extra></extra>" }],
        layout: base(t, hbarAxes(t, labels, rowHeight(labels.length))),
      };
    }
    const series = seriesPalette(t);
    const years = col(spec, "year");               // the per-site two-panel profile
    const phiCols = spec.columns.filter((n) => n.startsWith("phi_") && n !== "phi_bias");
    const left = phiCols.map((name, i) => ({
      type: "scatter", mode: "lines+markers", name: name.slice(4), xaxis: "x", yaxis: "y",
      x: years, y: col(spec, name), line: { color: series[i % series.length], width: 2 },
      marker: { size: 5 }, hovertemplate: `${name.slice(4)} · %{x}: %{y:+.3f}<extra></extra>`,
    }));
    return {
      data: [...left,
             { type: "bar", name: "נצפה", xaxis: "x2", yaxis: "y2", x: years, y: col(spec, "observed"),
               marker: { color: TEAL }, hovertemplate: "נצפה %{x}: %{y}<extra></extra>" },
             { type: "scatter", mode: "lines+markers", name: "צפוי", xaxis: "x2", yaxis: "y2",
               x: years, y: col(spec, "mu"), line: { color: RED, width: 2.5 }, marker: { size: 6 },
               hovertemplate: "צפוי %{x}: %{y:.1f}<extra></extra>" }],
      layout: base(t, { height: 420, showlegend: true,
                        legend: { ...LEGEND_LEFT, y: 1.14, font: { size: 10.5 } },
                        xaxis: { domain: [0, 0.55], type: "category", tickfont: { size: 10, color: t.inkSoft } },
                        yaxis: { title: { text: "תרומת φ (לוג)", font: { size: 11 } }, gridcolor: t.grid,
                                 zerolinecolor: t.grey },
                        xaxis2: { domain: [0.65, 1], type: "category", tickfont: { size: 10, color: t.inkSoft } },
                        yaxis2: { anchor: "x2", title: { text: "תאונות", font: { size: 11 } }, gridcolor: t.grid },
                        margin: { l: 40, r: 16, t: 56, b: 40 } }),
    };
  },

  "accidents/studio_gate_severity"(spec, t) {
    const c = ci(spec);
    const labels = spec.rows.map((r) => `עשירון ${r[c.decile]}`);
    return {
      data: [{ type: "bar", orientation: "h", y: labels, x: col(spec, "lift"), marker: { color: TEAL },
               customdata: spec.rows.map((r) => [r[c.n], r[c.fatal]]),
               hovertemplate: "%{y}<br>Lift: %{x:.2f} · n=%{customdata[0]:,} · הרוגים: %{customdata[1]}<extra></extra>" }],
      layout: base(t, { ...hbarAxes(t, labels, rowHeight(labels.length, 28)),
                        shapes: [{ type: "line", xref: "x", yref: "paper", x0: 1, x1: 1, y0: 0, y1: 1,
                                   line: { color: ORANGE, width: 1.5, dash: "dash" } }],
                        annotations: [refNote(t, "יחס = 1", vRefPos(1))] }),
    };
  },

  // severity_predict + what_if share the relative-ratio shape: 3 class bars around the 1.0 baseline;
  // a spec carrying `drivers` (P12) gains the φ panel — older saved specs keep the single-panel shape
  "accidents/severity_predict"(spec, t) {
    return spec.drivers ? ratioWithDrivers(spec, "relative", t) : ratioBars(spec, "relative", t);
  },
  "accidents/what_if"(spec, t) {
    return spec.drivers ? ratioWithDrivers(spec, "ratio", t) : ratioBars(spec, "ratio", t);
  },

  // P12: the person-level SHAP faces — beeswarm (spec.swarm) or dependence (spec.dependence)
  "accidents/severity_explain"(spec, t) {
    return spec.swarm ? beeswarmLayout(spec.swarm, t) : dependenceLayout(spec.dependence, t);
  },

  "accidents/studio_gate"(spec, t) {
    const dec = spec.deciles || [];
    const labels = dec.map((_, i) => `עשירון ${i + 1}`);
    const data = [
      { type: "bar", orientation: "h", y: labels, x: dec.map((d) => d[1]), name: "נצפה",
        marker: { color: TEAL }, customdata: dec.map((d) => d[0]),
        hovertemplate: "%{y}<br>נצפה: %{x:,} · n=%{customdata}<extra></extra>" },
      { type: "scatter", mode: "markers", y: labels, x: dec.map((d) => d[2]), name: "צפוי",
        marker: { symbol: "circle-open", size: 10, color: t.ink, line: { width: 2 } },
        hovertemplate: "צפוי: %{x:,.1f}<extra></extra>" },
    ];
    const layout = base(t, { ...hbarAxes(t, labels, rowHeight(labels.length, 30)), showlegend: true,
                             legend: { ...LEGEND_LEFT, y: 1.08 } });
    // P13: optional evidence panels — a spec without `points`/`roc` keeps the decile face untouched
    const panels = [spec.points ? "cal" : null, spec.roc ? "roc" : null].filter(Boolean);
    if (!panels.length) return { data, layout };
    // side panels LEFT of the decile bars (whose Hebrew labels own the right edge — RTL reads bars first)
    const doms = panels.length === 1 ? [[0, 0.42]] : [[0, 0.26], [0.34, 0.6]];
    layout.xaxis = { ...layout.xaxis, domain: panels.length === 1 ? [0.56, 1] : [0.68, 1] };
    layout.margin = { ...layout.margin, l: 48 };
    layout.shapes = [...(layout.shapes || [])];
    layout.annotations = [...(layout.annotations || [])];
    panels.forEach((kind, i) => {
      const ax = `x${i + 2}`, ay = `y${i + 2}`;
      const small = { font: { size: 10.5 } };
      if (kind === "cal") {
        // calibration: μ vs observed per decile/site point, against the perfect-calibration diagonal
        const mus = spec.points.map((p) => p[0]), obsv = spec.points.map((p) => p[1]);
        const m = Math.max(1, ...mus, ...obsv);
        data.push({ type: "scatter", mode: "markers", xaxis: ax, yaxis: ay, x: mus, y: obsv,
                    marker: { color: TEAL, size: 5, opacity: 0.55 }, showlegend: false,
                    hovertemplate: "צפוי %{x:.1f} · נצפה %{y}<extra></extra>" });
        layout[`xaxis${i + 2}`] = { domain: doms[i], anchor: ay, title: { text: "צפוי (μ)", ...small },
                                    gridcolor: t.grid, zeroline: false, automargin: true,
                                    tickfont: { size: 10, color: t.inkSoft } };
        layout[`yaxis${i + 2}`] = { anchor: ax, title: { text: "נצפה", ...small },
                                    gridcolor: t.grid, zeroline: false, automargin: true,
                                    tickfont: { size: 10, color: t.inkSoft } };
        layout.shapes.push({ type: "line", xref: ax, yref: ay, x0: 0, y0: 0, x1: m, y1: m,
                             line: { color: t.grey, width: 1.2, dash: "dash" } });
        layout.annotations.push(refNote(t, "כיול מושלם", { x: m, y: m, xref: ax, yref: ay,
                                                          xanchor: "right", yanchor: "top" }));
      } else {
        // ROC: the deployed gate's discrimination curve against the chance diagonal
        const r = spec.roc;
        data.push({ type: "scatter", mode: "lines", xaxis: ax, yaxis: ay, x: r.fpr, y: r.tpr,
                    line: { color: TEAL, width: 2 }, showlegend: false,
                    hovertemplate: "FPR %{x:.2f} · TPR %{y:.2f}<extra></extra>" });
        layout[`xaxis${i + 2}`] = { domain: doms[i], anchor: ay, range: [0, 1.02],
                                    title: { text: "FPR", ...small }, gridcolor: t.grid, zeroline: false,
                                    automargin: true, tickfont: { size: 10, color: t.inkSoft } };
        layout[`yaxis${i + 2}`] = { anchor: ax, range: [0, 1.02], title: { text: "TPR", ...small },
                                    gridcolor: t.grid, zeroline: false, automargin: true,
                                    tickfont: { size: 10, color: t.inkSoft } };
        layout.shapes.push({ type: "line", xref: ax, yref: ay, x0: 0, y0: 0, x1: 1, y1: 1,
                             line: { color: t.grey, width: 1.2, dash: "dash" } });
        const auc = typeof r.auc === "number" ? r.auc.toFixed(3) : String(r.auc);
        layout.annotations.push({ text: `AUC ${auc}${r.positive ? ` · ${r.positive}` : ""}`,
                                  x: 0.97, y: 0.05, xref: ax, yref: ay, xanchor: "right",
                                  yanchor: "bottom", showarrow: false,
                                  font: { size: 11, color: t.ink } });
      }
    });
    return { data, layout };
  },
};

export const PLOTLY_TYPES = new Set(Object.keys(BUILDERS));

export default function PlotlyChart({ spec, title }) {
  const el = useRef(null);
  const [failed, setFailed] = useState(false);
  const tokens = useThemeTokens();

  // a builder throw must not downgrade the panel FOREVER: a new spec gets a fresh try
  // (once `failed` hid the div, el.current stayed null and no later run could recover — P12 sweep)
  useEffect(() => { setFailed(false); }, [spec]);

  useEffect(() => {
    if (!el.current) return undefined;
    try {
      const { data, layout } = BUILDERS[spec.type](spec, tokens);
      Plotly.react(el.current, data, layout,
                   { displayModeBar: false, responsive: true, doubleClick: false });
    } catch (err) {
      console.error("plotly builder failed, falling back to the PNG twin", spec.type, err);
      setFailed(true);
    }
    const node = el.current;
    return () => { try { Plotly.purge(node); } catch { /* unmounted */ } };
    // tokens in the deps: an OS theme flip re-reads the CSS vars and Plotly.react redraws with them
  }, [spec, failed, tokens]);   // re-runs after the reset above re-mounts the div (el was null while failed)

  // P13 resize fix (verified): plotly.js 3.7.0 ships no ResizeObserver of its own, and its window-resize
  // path skips hidden (zero-width) divs — our tabs stay MOUNTED under [hidden], so a chart drawn in a
  // background tab never re-measures when the tab unhides. Observe the container ourselves and poke
  // Plotly the moment it gains real width (0 → N on tab re-activation, and any live container resize).
  useEffect(() => {
    const node = el.current;
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    let ro;
    try {
      ro = new ResizeObserver((entries) => {
        for (const e of entries) {
          const w = e.contentRect ? e.contentRect.width : node.clientWidth;
          if (w > 0) {
            try { Plotly.Plots.resize(node); } catch { /* not plotted yet — the plot effect will size it */ }
          }
        }
      });
      ro.observe(node);
    } catch { return undefined; }
    return () => ro.disconnect();
  }, [failed]);   // `failed` can swap the div for the PNG twin and back — re-attach to the live node

  if (failed && spec.png_base64) {
    return <img className="png" alt={title} src={`data:image/png;base64,${spec.png_base64}`} />;
  }
  return <div className="plotly-chart" dir="ltr" ref={el} />;
}
