# P11 — trend compare (the page-side composer) + the share-drift view

## Context

Reviewing the trend tab (2026-09-04), the instructor asked why only one line, and three discussion rounds
settled the design: comparison should be **page-side composition of multiple runs** (not a backend multi-series
action — the engine has no multi-select input kind, and each run keeps its own envelope), with a **3-row cap
behind a small opt-in button**, **overlay on ONE shared axis only when honest** (similar scale + matching
coverage), **small multiples otherwise**, a **visible מאוחד/מפוצל toggle**, and **never two independent
y-axes** (the chart-lie configuration — refused on methodology-brand grounds). Bundled second item: the
**severity-share-drift view** — the one comparison with real teaching power (the severe share triples
6.1 % → 19.4 %, which is WHY the P9 severity gate measures discrimination) — as a backend face so it is
demo-able, Layer-0-able, and ledger-able. Version **0.11.0**, commit `[P11]`, tag `v0.11`.

## Track A — the trend composer (web/src only; zero backend changes)

New `web/src/components/TrendCompare.jsx`, used in `App.jsx` in place of `ActionPanel` for `trend` only
(`name === "trend" ? <TrendCompare .../> : <ActionPanel .../>`); every other action keeps `ActionPanel`
untouched.

- **Row model**: row 1 = today's behavior (Form + Answer; the one visible addition when alone is the small
  compare bar between the form and the answer — below the whole answer it was undiscoverable, the user's find).
  A small **"+ השוואה"** button reveals row 2, prefilled with row 1's current form values (falling back to
  its last run's spec when the form was never edited — the common case is "same thing, change one field");
  a further "+" reveals row 3; **hard cap 3**; rows 2–3 get minimize/remove.
  Reuses `Form.jsx` as-is per row; `Form` gains one optional `runTick` prop (an effect that submits when the
  counter bumps) so a **"הרץ הכול"** button can run every visible row — the user's explicit ask.
- **Composition rules** (client-side, computed from the returned specs — `spec.gap_periods`, `spec.granularity`,
  the y values; each run's `Result.title` is the legend/panel label, already human-exact):
  1. Runs with different `granularity` → no composed figure; stacked individual Answers + a one-line note.
  2. **Overlay** (one figure, one shared y-axis, 2–3 traces) iff all runs have IDENTICAL `gap_periods` AND the
     max-y scale ratio ≤ 3 (a tunable constant).
  3. Otherwise **split**: one figure, one row per run — matched x across rows, free y per row (manual plotly
     axis domains; `plotly.js-basic-dist` supports multi-axis layouts without a subplot helper).
  4. **Never two independent y-axes.**
  5. The **מאוחד/מפוצל toggle** is always visible on a composed figure and overrides the auto choice; a forced
     overlay across differing `gap_periods` drops the gap band and adds a text note naming which series has
     missing periods (a shaded band that applies to only one line would mislead).
- **Envelope preservation**: under the composed figure, each run's full `Answer` (badge · ribbon · face ·
  table · SQL · credit) collapses into a `<details>` per row — nothing about the answer contract changes, and
  each run is still individually ledgered. A small fixed line states the limitation honestly:
  ההשוואה היא תצוגת עמוד — כל ריצה נרשמת בפנקס בנפרד.
- `styles.css` additions (row chrome, the toggle, RTL for the new controls); gap bands in overlay mode render
  once when shared (both person measures carry the same 2009 gap).

## Track B — `severity_profile by=year` (the share-drift exhibit, backend)

- `sqlkit.PROFILE_DIMS` += `"year"` (Hebrew "שנה"); `build_severity_profile_sql` orders by year for this dim
  (the existing dims keep their casualties-DESC order). 2005–2024 = 20 rows — inside the chart's top-20 cap.
- `severity_profile.DIM_CAVEATS["year"]` = the lesson: the severe share triples over the era (reporting
  collapse of slight + real growth) — share drift, not label drift, and the reason the severity gate measures
  discrimination rather than calibration.
- The existing stacked-shares chart (PNG + the plotly builder) renders it with no chart changes; the dropped
  2009 stays dropped-and-named by the existing coverage rule.
- Tests: fixture run `by=year` (rows ordered by year, shares consistent, the caveat present); live smoke
  assertion (the 2024 severe share ≈ 3× the 2010 one, loose tolerance).

## Shared

- 0.11.0 across the five touch points (pyproject, `__init__`, package.json, test_contract pin, preflight
  `PLUGIN_VERSION`; `N_ACTIONS` stays 25) + npm build + `-e` refresh + full suite + wheel sanity + app restart
  (backend changed → loaded modules must reload) + headless checks (scratch data dir, env-first, the
  `+ השוואה` button present in the DOM).
- Docs: plan.md P11 row, CHANGELOG v0.11, GUIDE.md (§2 trend entry gains the composer; §6 gains a compare
  experiment + the by=year drift exhibit), README one-liner. PITFALLS as they happen.
- Stage discipline unchanged: composer plays append the ledger like any runs; preflight re-verifies before
  any show.

## Order of work

1. Track B first (small, testable): sqlkit dim + caveat + tests + live smoke line.
2. `Form.jsx` `runTick` prop; `TrendCompare.jsx` (rows → run-all → composition rules → toggle → collapsed
   answers); `App.jsx` wiring; styles; npm build.
3. Headless checks + manual screenshots of overlay and split modes (urban vs non-urban killed = overlay;
   killed vs slight = split).
4. 0.11.0 bump + full suite + wheel sanity (dist\ + the committed release\ wheel per the Branches policy) + restart.
5. Sweep question (ALWAYS ask first; guardrails: no port 8000 exercise beyond the running app's own page, no
   live CLI, env-first scratch dirs) → fixes → recap with screenshots → acceptance word → `[P11]` + `v0.11`.

## Verification

- Suite green at 0.11.0 (Track B tests + all 333 existing); `git -C app status` clean throughout.
- Composition rules exercised manually (no JS test infra in the repo): urban vs non-urban killed → overlay,
  one axis, shared 2009 band; killed vs fatal_accidents → split (coverage mismatch) with the toggle able to
  force overlay + the per-series missing-periods note; killed vs slight_injured → split (scale); month vs
  year rows → no composed figure. Screenshots of each in the recap.
- `severity_profile by=year` on live shows the severe share tripling; the caveat names it.
- Headless DOM: the compare button exists; a composed run renders two traces/panels.
