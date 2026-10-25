# P8 — Chart & Hebrew polish (plotly.js on the page + a real bidi/typography fix for the PNG twins)

## Context

The pathfinder wrapped at v0.7, but the instructor reviewed the live page and rejected the chart quality
(screenshots on record): the Hebrew inside the matplotlib PNGs reads wrong to a native eye, and the charts are
unpolished (annotation collisions on dense charts, hairline whiskers, cramped margins, ugly glyphs). Decision
(user, 2026-09-02): fix IN THIS repo as **P8**, direction = **plotly.js interactive charts on the 🚦 page** +
a **matplotlib fix/restyle for the PNG twins** (Layer 0 + Plan-B), the map's twin pattern. Version **0.8.0**,
`[P8]`, tag `v0.8`. v0.7 + its release wheel stay the seminar safe point.

## Root causes (bidi/font audit, verified in the app venv — the diff table is the regression fixture)

`charts.heb()` ALREADY calls python-bidi (`bidi.algorithm.get_display`, legacy impl, 0.6.11); `_mirror` is a
dead fallback (contractual — `dependencies = []`, bidi is borrowed from the host). The actual defects:

1. **Forced `base_dir="R"`** wrecks Latin-dominant strings: `ADT as-of (Σ ADT × אורך × 365)` renders with two
   `(` and zero `)`. Auto base direction fixes it.
2. **En-dash number ranges FLIP**: `2005–2024` → `2024–2005`, `1001–1300 סמ"ק` → `1300–1001` (U+2013 splits the
   EN runs; UBA-correct, human-wrong). Fix verified: LRM (U+200E) wrapping the range — zero-width in all our
   fonts, keeps the en-dash. Applied centrally in `heb()` via a digit-range regex, no call-site changes.
3. **No font is configured at all** — every glyph is DejaVu Sans, whose Hebrew is a low-quality Vera add-on
   (uneven stroke weight, wrong x-height). Fix: bundle an OFL 1.1 Hebrew+Latin family (candidates: Heebo /
   Assistant / Rubik — all SIL OFL, bundleable with OFL.txt) as package data, `font_manager.addfont` +
   `rcParams` chain (bundled font first, DejaVu fallback for Σ/≠ if absent). matplotlib 3.11 does per-glyph
   fallback.
4. **RTL layout bugs bidi cannot fix**: `stacked_bars` legend entries run LTR; `hbars` annotations `ha="left"`
   grow away from their bar; caveat continuation indent lands on the LEFT (prepended in logical order); the
   caveat/label wrap is char-counted (font-coupled magic numbers 118 / 0.011).
5. **TRAP (do not step in it)**: the maintained Rust `bidi.get_display` drops rule-L4 paren mirroring — a naive
   "upgrade" REGRESSES parens. Keep `bidi.algorithm` (it applies L4), change only base_dir + the LRM step.
6. Latent: `line_chart`/`multi_lines`/`explain_png` x-tick labels never pass through `heb()` (safe today —
   years only — but the restyle adds the call for safety).

## Scope

1. **Page charts → plotly.js** (`plotly.js-basic-dist`, bundled offline): `PlotlyChart` component keyed on
   `spec.type` (the 10-mapping table below), hooked at Answer.jsx's map/img branch; PNG stays the fallback for
   unmapped types + Layer 0 + Plan-B. Browser bidi = Hebrew simply correct; system font stack.
2. **PNG twins**: the four bidi/layout fixes above + a designed style pass (palette, whisker weight ≥1.6,
   annotation placement without collisions, margins, density handling — site_ranking PNG shows top ~15 with an
   "ועוד N" note when top_n is larger; vehicle_cells label/marker cleanup) + the bundled font.
3. **Taste checkpoint (user-facing)**: after the core fix, render the SAME two charts (trend + site_ranking)
   in 2–3 candidate fonts/styles and show them to the user for a pick BEFORE mass application. Aesthetics are
   the user's call — this phase exists because of taste.
4. **Page-side RTL nits**: headless DOM + screenshot audit of badge lines/trailing LTR runs; fix what shows.
5. Regenerate what the restyle invalidates: chart-face test pins, `plan_b.pdf`, the rehearsal frames.

## Exploration results (1 of 2 — spec inventory, verified)

**Every chart spec is already client-renderable from `rows` + extras** — the twin pattern needs NO Python
rewrites, only ONE small additive key:

| spec type | plotly rendition from | note |
|---|---|---|
| accidents/trend | rows (labels, value, coverage flag → gaps) | line + gap shading |
| accidents/segment_rates | rows (rate, lo, hi, accidents) | h-bars + CI + count annotations |
| accidents/site_ranking | rows (observed, mu, excess, lo90, hi90, significant) | h-bars μ + CI + observed markers, red/teal by significance |
| accidents/severity_profile | rows (shares per severity) | 100 % stacked h-bars |
| accidents/vehicle_cells_ranking | rows + spec.tiers/global_rate | h-bars + tier break + reference line |
| accidents/before_after | rows + spec.counts + spec.double | grouped 2×2 bars + the double-ratio annotation |
| accidents/weather_check | rows (pct_measured_rain per label) | h-bars + threshold line |
| accidents/two_wheelers | rows per (year, band) | multi-line per band |
| accidents/studio_explain | rows (site: per-year φ; global: mean\|φ\|) | two-panel lines / h-bars |
| accidents/studio_gate | rows = holdout (road, seg, year, observed, mu) | deciles: ADD `deciles` to the spec (today computed only inside the PNG path — [studio_validate.py:72](nl2sql-accidents-plugin/nl2sql_accidents/actions/studio_validate.py#L72)) or derive client-side; adding the key is cleaner |

Page hook: [Answer.jsx:83-85](nl2sql-accidents-plugin/web/src/components/Answer.jsx#L83-L85) — today `MapView`
(map specs) else `<img png_base64>`. P8 inserts: map → `MapView`; `spec.type` in the plotly registry →
`<PlotlyChart spec>`; else the PNG `<img>` (automatic fallback, nothing breaks). Deps today: react, react-dom,
leaflet only — add `plotly.js-basic-dist` (~1 MB min, bar/scatter/line — all we need), bundled offline by vite
like leaflet. Client font stack: system (`"Segoe UI", "Noto Sans Hebrew", sans-serif`) — the browser shapes
Hebrew natively, no mirror code anywhere client-side.

## Files

```
nl2sql_accidents/charts.py            heb(): auto base_dir + LRM range-wrap (keep bidi.algorithm for L4; _mirror
                                      fallback stays contractual); font bootstrap (addfont + rcParams chain, once,
                                      thread-safe); legend order/annotation ha/indent fixes; style constants;
                                      density cap for hbars via a max_rows+overflow-note arg
nl2sql_accidents/data/fonts/          the chosen OFL .ttf + OFL.txt (package-data gains "data/fonts/*")
tools/fetch_font.py                   one-shot fetcher (network) — repo-side, like fetch_outline.py
nl2sql_accidents/actions/studio_validate.py   + spec["deciles"] (the one additive spec key)
web/src/components/PlotlyChart.jsx    the registry: 10 spec-type → trace builders; Hebrew via browser bidi;
                                      config {displayModeBar:false, responsive}; RTL hover templates
web/src/components/Answer.jsx         hook: map → MapView; type in registry → PlotlyChart; else <img png>
web/package.json                      + plotly.js-basic-dist (pinned); version 0.8.0; npm run build
tests/test_charts.py                  update the heb()/fallback pins; ADD the byte-exact bidi display fixture
                                      (each string → expected display, incl. the range-LRM and paren cases)
tests/test_contract.py · preflight    version 0.8.0 (5 touch points, the P7 pattern)
docs/plan.md · PITFALLS.md            P8 row; a pitfall entry for the forced-base_dir/en-dash/L4 findings
docs/demo/plan_b.pdf + DEMO.md        regenerated frames after the restyle (tools/rehearse + make_plan_b rerun)
```

## Order of work

0. Save `docs/p8_design.md`; preflight; tree clean at v0.7.
1. charts.py bidi core (auto base_dir, LRM ranges, x-tick heb coverage) + the diff-table test fixture red→green.
2. Font: fetch 2–3 OFL candidates to c:\tmp, wire the bootstrap, render the taste samples → **user picks**
   (AskUserQuestion with rendered PNGs described/eyeballed); commit the winner + OFL.txt as package data.
3. Style/layout pass on the PNG functions (legend order, annotations, whiskers, margins, density caps).
4. PlotlyChart + the 10 mappings + deciles key + Answer.jsx hook + npm dep; headless checks per tab
   (charts render as plotly divs, PNG fallback intact on Layer 0).
5. Page RTL nit audit (headless screenshots per tab → fix list → fix).
6. 0.8.0 bump (5 touch points) + webdist rebuild + full suite + wheel sanity + app restart + preflight.
7. Regenerate plan_b.pdf + rehearsal frames (the old-style frames are stale after the restyle).
8. **Sweep question** (ask the user first; the three contamination-vector guardrails + no live recording):
   checkers over the bidi table vs rendered output, the plotly mappings vs the specs, the page contract, docs.
9. Recap with before/after screenshots → the user's acceptance word → `[P8]` + `v0.8`.

## Verification

- The bidi display fixture pins display output exactly (incl. `2005-2024` order, paren orientation, the
  Latin-dominant badge) — the regression net for any future bidi/font touch.
- Headless Edge DOM: each tab's chart renders a plotly root div (`.js-plotly-plot`) with zero console errors;
  Layer 0 still shows PNGs; the two seeded-stage checks (chip, models table) unchanged.
- Full suite green at 0.8.0; `git -C app status` clean; stage dir byte-identical (preflight before/after).
- The user eyeballs the taste samples mid-build AND the final before/after in the recap — aesthetics are the
  acceptance criterion of this phase, so their eye gates it twice.

## Process (standing)

Plan approval → build (with the step-2 taste checkpoint) → suite green → sweep question (ask first) → recap →
acceptance word → `[P8]` + `v0.8`. Stage dir untouched throughout; v0.7's release wheel remains the seminar
fallback until P8 is accepted.

## As built (2026-09-03)

Everything shipped; the full deviations list is in plan.md's P8 row. Highlights beyond the plan: the audit's
"forced base_dir" fix needed a companion — base direction must be detected from the ORIGINAL string because the
inserted LRMs are strong-L and hijack auto-detection when a range opens the line; the range regex learned that a
SPACED em-dash is a separator (site keys `60/850 — 113` must not be glued); matplotlib per-glyph fallback works
ONLY via the `font.family` LIST; `instantiateVariableFont` requires `inplace=True` (the discarded-copy trap);
plotly `automargin` under-reserves for right-side RTL labels in headless — deterministic label-width margins;
headless legend text clips (`צפוי`→`צפ`) while the DOM carries the full string — flagged for the real-browser
eyeball. The user's taste picks: **Assistant** (over Heebo/Rubik/DejaVu, samples in c:\tmp\p8_taste). The scratch
app taught one more: a fresh `NL2SQL_CORE_DATA_DIR` has no `added_connections.json` → page runs 404 ("no
connection named…"). Numbers: 286 tests (285 + the 8-string bidi fixture); bundle 324 KB → ~1.45 MB (plotly,
offline); wheel 47 files incl. Assistant-{Regular,Bold}.ttf + OFL.txt; all four checked tabs render `.js-plotly-plot`
SVG with zero console errors; plan_b.pdf regenerated in the new style (12 pages). Mid-phase, preflight flagged
stage drift twice — the ledger attributed BOTH bursts to the instructor's own UI sessions (the screenshot
exploration and a studio session), pruned per the pre-show rule: the governance loop closing on its own owner.

## Sweep (2026-09-03, 27 agents, run wf_7510c163-a80)

9 confirmed (0 contested, 1 refuted), ALL fixed — and it corrected the As-built above on one point:
**auto base direction was WRONG** (the sweep's high: the neutral "• " bullet made acronym-opening Hebrew caveats
resolve base-L and scramble — "ADT ≠ AADT: …", "EB: M = 200 …"). Final bidi design: base is ALWAYS R; a new
LRM pass pins parenthesized groups with Latin/digit content (both parens resolve unmirrored and paired — this
fixed the Haldane formula, DiD panel titles, and pure-LTR parentheticals that were broken SINCE P2 under the old
forced-R too); mixed-script paren content is fixed EDITORIALLY (Hebrew-first) in three source strings
(segment_rates badge, site_ranking denominator, hotspot_map caveats); wrap_caveat no longer splits inside parens.
The fixture grew to 14 machine-generated byte-exact cases. Also fixed: the plotly monthly-trend collapse
(24 months landed on 2 category ticks — composite year-month labels now), the ≠-glyph doc claim (Assistant has
U+2260 natively; only ← and Σ fall back), README's stale P7 status, and two 7-vs-8-string doc mismatches.
Refuted: the DEMO.md rebuild-command complaint (the flags work as written). Stage verified untouched (the
guardrails held; the earlier "drift" this phase was the instructor's own UI sessions, attributed by the ledger).
