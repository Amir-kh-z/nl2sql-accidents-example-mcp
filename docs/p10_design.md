# P10 — מפה חיה: the advanced interactive map tab

## Context

After P9 the instructor asked for a second, **advanced** map — "not a polished plotly chart": a navigable,
BI-grade GPU map of Israel with a real street basemap, the full accident point cloud, filters and a year
animation, search/fly-to, and a per-site click panel that shows historical AND model-based measures — the
ML/method layer (EB excess, site model, TreeSHAP, the P9 severity family) made spatial. The existing
`hotspot_map` (Leaflet, outline-only) stays untouched. Planned in plan mode 2026-09-04 and approved; the
plan file lives outside the repo (`~\.claude\plans\`). Version **0.10.0**, commit `[P10]`, tag `v0.10`.
(Numbering note: an earlier P10 candidate — the trend composer — was renumbered **P11** by this approval;
its design is parked in the planning session's scratchpad and returns as `docs/p11_design.md`.)

Decisions fixed with the instructor: ① offline **PMTiles** street basemap (Protomaps Israel extract,
one-time download, gitignored, served locally — Starlette's `FileResponse` Range support was verified
end-to-end: 206/`Content-Range`/`If-Range`/416) with a **canvas fallback** style when the file is absent
(wheel-only installs degrade automatically); ② **MapLibre GL JS + deck.gl** overlay, npm-vendored like
plotly, as a **lazy chunk**; ③ a new full-bleed **tab in the 🚦 page** (`custom` flag in tabs.js, one
branch in App.jsx); ④ **full honest panel depth** — segments carry model measures, junctions NEVER carry
rates/excess (no denominator exists; structural, not policy).

## Track A — two backend actions (23 → 25)

**`map_scene`** (three-view chart|table|sql) — the whole map in ONE envelope. Inputs: `road` (0=all),
`from_year` 2008, `to_year` 2024, `top_sites` 150 (1–200), `max_points` 300000, `view`. New sqlkit
builders: `build_map_cloud_sql` (casualty series + `GEO_PREDICATE` + `round(lon/lat, 5)` + year/severity/
night columns, deterministic newest-first LIMIT), `map_cloud_coverage_sql` (per-year total/geocoded/
outside-bbox — the caveat numbers, computed in-range), `gazetteer_sql` (city centroids from urban casualty
accidents — search targets). Site layers reuse `build_hotspot_sql` three times (segments / njunctions /
ujunctions) so UNITS_CTE, ASSIGN_QUALIFY, km÷10, sentinels, UJ_NAMES_CTE, grouped dims and the
accident-mean coordinate fallback are inherited, not re-derived. Spec type `accidents/map_scene`:
`rows` = the segment ranking (handoff-compatible), extras `cloud {lon[] lat[] year[] sev[] night[] n capped}`
(columnar arrays ≈ 8 MB at ~230k points; the measured serialization envelope is 200k rows ≈ 5.2 MB ≈ 70 ms),
`sites {segments njunctions ujunctions}`, `gazetteer`, `coverage`, `sites_sql`, `meta`. Denominator
**counts** (amber); no `model_id` (model depth lives in `site_profile`). PNG twin `charts.scene_png`:
outline + hexbin density + top-10 segment circles + side list. Refusals: the existing
`FIRST_GEOCODED_YEAR_SQL` card for pre-2008 ranges; a legal range with rows is never blank. Ledger on.

**`site_profile`** (four-view chart|markdown|table|sql) — "only what can be said" per site. Input `site`
accepts the three site-key forms or bare `road/seg` (resolved via `explain.resolve_site`). Yearly observed
strip (accidents, KSI, geocoded, night share) for every kind; label via the shared `site_label_sql`.
**Model block — `road:` kind ONLY, structurally unreachable for junctions**: requires a deployed site
model + panel key + `to_year ≥ 2017`; `predict.expected_by_segment` → μ, μ_by_year, excess, EB, NB 90 %,
significant; verdict wording from `studio_explain`; top-3 TreeSHAP drivers under the Σφ = ln μ guard.
Missing prerequisite → the section is ABSENT and one caveat says why — never a refusal. Junction keys
carry the standing counts-only caveat. **Severity block (all kinds, relative only)**: when a severity
model is deployed, `severity.matrix_sql` gains an optional `site_pred=None` (default output byte-identical;
the leakage token-scan is unaffected) → mean predicted p over the site's own person rows (era 2010+, n
stated) vs `class_shares_holdout` → "פי X.XX מהבסיס" per class + `model_caveats`. Denominator exposure +
`model_id` + spec-driven chip when the model block ran, counts otherwise. `view=markdown` = the honest
card (LRM-pinned ranges); PNG twin `charts.site_card_png` (yearly bars + μ line). Handoff: spec-level
`site_key` → the panel's before_after button → the existing `onHandoff` chain.

## Track B — the map tab (web/)

Deps: `maplibre-gl`, `pmtiles`, `@protomaps/basemaps`, `@deck.gl/{core,layers,mapbox,extensions}`
(+`aggregation-layers`, cut-line) — all inside `React.lazy(() => import(...MapTab.jsx))` so Vite splits a
map chunk and the other tabs load exactly as today. tabs.js gains `{id:"map", label:"מפה חיה",
actions:["map_scene","site_profile"], custom:true}` after נקודות תורפה; App.jsx branches on `t.custom`
inside the mounted-tabs loop (tab stays mounted; `map.resize()` on activation). New
`web/src/components/map/`: `MapTab` (state owner; ONE `map_scene view=chart` fetch per server scope;
error card + PNG-twin fallback — never a blank tab), `MapCanvas` (map created once with `bounds` in the
constructor — the fitBounds-before-layers class; `dir="ltr"` island; pmtiles protocol registered once;
`MapboxOverlay` overlaid mode; ResizeObserver), `basemap.js` (HEAD probe → street|canvas; `?basemap=off`
override; street = Protomaps `layers(..., {lang:"he"})` + LOCAL glyphs/sprites + `setRTLTextPlugin`
(local file, lazy) for correct Hebrew labels; canvas = dark style from the existing `data/israel.json`
JSON-module import, ZERO symbol layers → no glyphs/sprite/RTL needed), `layers.js` (ScatterplotLayer over
Float32Array columns; severity ramp; `DataFilterExtension filterSize 3` on [year, sev, night] → GPU
filtering + the year animation with zero re-fetch; pickable site circles ~ √accidents; HexagonLayer 3D
toggle = cut-line), `SitePanel` (slide-in RTL; fetches `site_profile` on pick; sections render the
server's degrade caveats, never blanks; CBS credit + caveat ribbon in-panel), `FilterBar`, `TimeSlider`
(`String(year)` — never `Intl.NumberFormat`), `SearchBox` (offline substring over site labels +
gazetteer), `Legend` ("ספירות אינן סיכון"), `CreditBadge` (CBS credit ALWAYS; "© OpenStreetMap ·
Protomaps" appended only in street mode). styles.css: full-bleed escape from the 1240 px `.page` cap
(`margin-inline: calc(50% - 50vw)`), `.map-shell` height, panel/toolbar chrome. Every new surface
(tooltip, panel, legend, search, slider) passes the P8/P9 bidi checklist.

## Track C — the basemap pipeline (three leak guards)

`web/basemap/israel.pmtiles` (cache, ~z15 ≈ 300–450 MB) → hardlinked into `nl2sql_accidents/webdist/
basemap/` after every build (`npm run build` = `vite build && node scripts/sync-basemap.mjs`; hardlinks
are real files so the server's realpath containment passes — symlinks are rejected; copy fallback
cross-volume; no-op with a note when the cache is empty — `emptyOutDir: true` wipes webdist every build).
`tools/fetch_basemap.py` (repo-side): `--assets-only` fetches glyph ranges (Latin+Hebrew+punct+Arabic ≈
0.5 MB, committed under `web/public/basemap-assets/`) + sprites + `rtl-text.js`; the default path fetches
the go-pmtiles CLI into the scratch dir and runs `pmtiles extract` with the Israel bbox
(34.2,29.45,35.9,33.35), verifies the PMTiles magic + a size floor, then syncs. Guards: `.gitignore`
(`web/basemap/`, `webdist/basemap/`), `[tool.setuptools.exclude-package-data]` (`webdist/basemap/*`),
MANIFEST.in (`prune`, `global-exclude *.pmtiles`), and the wheel-sanity namelist assertion extended to
FAIL on any `.pmtiles`. Vite dev proxy `/page/accidents/basemap` → :8000. preflight `_check_basemap`:
PASS (present + magic + in sync) / SKIP ("canvas fallback") / FAIL (corrupt — the 0-byte-booster lesson).

## Order of work

1. This doc + 0.10.0 across the five touch points; suite green.
2. `map_scene` backend (sqlkit builders → action → `scene_png` → registration/about/triage → contract
   tests → `test_map_scene.py`); Layer 0 shows the twin on the clone (restart — new action).
3. `site_profile` backend (+`site_pred` param, `site_card_png`, `test_site_profile.py` — the junction
   golden-rule pins run with AND without deployments); `N_ACTIONS = 25`.
4. Frontend foundation on the **canvas fallback** (deps, lazy MapTab, canvas+layers+chrome, tabs/App/
   styles) → npm build → commit webdist; headless DOM-count with a scratch data dir (env-first).
5. Basemap pipeline (fetch tool + assets, the three guards, probe + street style + RTL plugin, preflight
   check, packaging tests); fetch, rebuild, verify street mode + Hebrew labels + 206 ranges + `?basemap=off`.
6. SitePanel + search/fly-to (+ hex toggle if time), handoff, the bidi audit pass, live pins.
7. Wrap: full suite → headless (street, canvas, `?run=hotspot_map` regression) → delete `build\`+`dist\`
   → wheel → namelist (NO `.pmtiles`) → wheel-install smoke on the clone (map tab MUST come up in canvas
   mode) → restore `-e` → CHANGELOG/GUIDE/DEMO/plan.md/PITFALLS → sweep question (ALWAYS ask) → recap →
   acceptance word → `[P10]` + `v0.10`.

Cut line (in order): hex 3D → gazetteer fly-to (label search stays) → `scene_png` hexbin (reuse
`map_png`) → the animation play button (scrub stays) → the Arabic glyph range → triage routes. Never cut:
the probe/fallback duality, the GPU cloud + 3 filters, the SitePanel honesty split, the CBS credit badge,
the packaging guards.

## As-built deviations (recorded during the build)

- **`twin` input on map_scene** (not in the design): the page's interactive fetch passes `twin=false` — it
  renders the GL scene itself, so the server-drawn PNG twin (~1 s matplotlib + ~300 KB base64) is skipped;
  Layer 0 keeps the default `twin=true`, and a GL failure re-fetches with defaults to get the twin. Born from
  the headless timing hunt; kept because it makes every interactive load faster.
- **Deep-linkable map scope** `?road=&from_year=&to_year=` (+ the designed `?basemap=off`): needed so headless
  checks fit a small scope; kept as a product feature (demo links open the map pre-scoped).
- **The headless recipe changed**: the P6 `--virtual-time-budget --dump-dom` recipe cannot see a fetch issued
  after a lazy chunk loads (byte-identical dumps are the tell) — `web/scripts/dom-dump.mjs` (CDP, real
  wall-clock waits, Node ≥ 22 built-ins) replaces it for the map tab. PITFALLS [demo].
- **The fetch-effect cleanup bug** (PITFALLS [page]): the scene fetch is deduped by a ref key compared again
  at resolve time — never by cleanup flags; the CDP network log proved the response arrived and was discarded.
- Steps 4 and 6 merged: the SitePanel, search and animation were built with the foundation (one npm build).
- `MAP_CLOUD_BOUNDS` lower bound is 10 (not 1000) so the cap branch is testable on the 34-row fixture; an
  explicit tiny cap is honest (the caveat fires).
- Glyphs: 3 Noto stacks × 7 ranges ≈ 1.6 MB committed (the Italic stack is real — water labels), above the
  design's ~0.5 MB guess; rtl-text.js is 148 KB (0.3.0), far below the ~0.9 MB estimate.
- `about`'s "# פעולות" list had silently drifted since P5 (6 actions missing) — completed to all 25.
- The Hexagon 3D toggle (cut line #1) was not built; everything above it on the never-cut list shipped.
- The extract: 171 MB at full z15 (in the predicted range); the first run died on a transient network error —
  the quiet rerun succeeded (the tool keeps progress output; rerun with `--date` if a daily build 404s).
- **The risk view, folded in on the instructor's call** (2026-09-04): `map_scene` gained `color_by`
  (hotspot_map's excess recipe verbatim: deployed-model resolve, per-year geometry in the model window,
  merge + re-rank by excess, fallback-with-caveat), and the page a "צבע: ספירות | מול המודל" toggle —
  counts = intensity ramp in each layer's own hue, excess = the shared diverging scale on segments ONLY
  with white significance rings; the legend switches grammar and names the model. Two color grammars kept
  visually incompatible on purpose, and no green: "מתחת לציפייה" is not "בטוח". Pinned on the fixture
  (with/without deployment) and live (60/850 top, +30, significant; junction entries carry no model keys).
  Second instructor call, same day: **shape = entity class** — segments are SQUARES (IconLayer over a
  generated two-icon atlas: fill + significance/selection ring frame), junctions stay circles, size stays
  counts in both; the legend/filter swatches match ("ריבוע = מקטע · עיגול = צומת") and the PNG twin draws
  square markers. Solves the excess-mode ambiguity where a pale segment and a light junction were identical
  round blobs under two different legends.
  Third instructor call, same day — **hues belong to MEANINGS only**: the site layers dropped their
  identity colors (teal/amber/indigo collided head-on with the severity palette — orange was both קשה and
  a non-urban junction) and became NEUTRAL graphite; entity identity = shape alone (square / filled circle /
  hollow circle for urban), intensity = counts, and the only colored site marks are excess-mode segments.
  Marks are sized in METERS with pixel clamps (fixed-pixel marks blobbed over the dense center at national
  zoom), and a road-scoped scene auto-frames its corridor bbox so the meter-sized marks arrive at full size.
  Fourth/fifth instructor calls: **model mode shows ALL panel segments** (a top-N-by-excess cut displayed
  only the red tail — every better-than-expected segment was silently hidden); squares carry a constant
  graphite outline (pale-on-pale camouflage — circles never "vanished" because circles have strokes); and
  **color = band distance (z), not raw excess** — normalizing by max|excess| let one +40 outlier own the
  scale and the blue half never appeared. Same rule in the PNG twin. Plus the instructor-requested
  **z-distribution drawer** (ZHistogram.jsx, client-side from the shipped scene — residual-diagnostics EDA):
  histogram of band distance across the whole panel, map-bucket colors, ±Z90 markers, above/within/below
  counts (live 2008-2024: 63 / 839 / 85 of 987 — the right tail beyond the ~49 chance level = the screening
  population; the heavy below-count = the calibration-1.17 left shift, i.e. the 2023-24 national decline).
- **Instructor's live-review round** (2026-09-04): the site panel gained its three exits (visible ✕ at
  inline-END, Escape, empty-map click — PITFALLS [page] "the panel was a trap"); the cloud became pickable
  with a per-accident hover (year · severity · day/night — exactly the shipped columns; row-level display is
  permitted, richer drill-down stays in hotspot_map points / the panel); and the panel's model block gained a
  SECOND hand-off — "הסבר SHAP מלא לפי שנים ←" routes to studio_explain with the segment prefilled (the
  before_after prefill pattern). All verified by CDP click/hover probes, not DOM counts.
- **The empty-map triple** (instructor's live report, PITFALLS [map] 2026-09-04): absolute style URLs, the
  ref-guarded setStyle, and the two-class `.map-shell .map-gl` sizing rule — plus the diag2 CDP
  screenshot/console harness that found them (DOM counts prove mounting, never pixels). npm @protomaps/basemaps
  5.x is CORRECT for the daily builds' schema-v4 tiles (the package major restarted at 5 with the rename;
  world-label glyph ranges outside the vendored set 404 harmlessly and render via the local fallback).

## Sweep (2026-09-05 · 44 agents: 8 dimension finders + 2 adversarial refuters per high/medium)

**11 confirmed / 7 refuted / 17 lows.** Highs, ALL fixed: the רענון-היקף refetch trap (the fetch-dedupe ref
was never reset, so an unchanged scope — or any failed fetch — blanked the tab forever; both paths reset now);
`kind:"error"` envelopes rendered NOTHING in MapTab and SitePanel (error boxes added); raw exception text
reached the caveat contract on the excess degrade path (`ML_MISSING` itself carries a ';' — cleaned like
site_profile's `_clean`); and the z reconstruction understated sd wherever `nb_interval` floors lo90 at 0,
inflating |z| up to ~1.4× on low-μ segments (sd now from the un-floored upper half, in BOTH layers.js and the
PNG twin). Mediums fixed: the excess-mode instrument-switch caveat (panel-assignment counts ≠ literal-km
counts, now said); the legend no longer claims the 90% boundary for the |z|=0.75 color step; signed-excess
LRM pins on the markdown cards (site_profile AND studio_explain's P8-era card); the road-label km range and
every new caveat/refusal year range moved to ASCII hyphens; GUIDE §0 modernized (25 actions, seven tabs,
`?tab=map`) and the 60/836 verdict misquote fixed in GUIDE + DEMO ("בתוך רווח התחזית" — a real deficit inside
the noise band, which is itself the teaching point). Lows fixed: coverage's no-coords arithmetic no longer
double-counts outside-bbox rows; a severity meta missing both share keys degrades instead of crashing;
SitePanel keys its fetch on year scalars (the years-array identity re-fetched on every color toggle); the
fallback chip no longer asserts a wrong reason; blanket `*.pmtiles` in .gitignore; CHANGELOG/help-number/
doc-pin corrections. Deliberately unchanged after review: Refusal-on-contract-drift still replaces the map
(the tripwire must be loud), and the GL-failure twin's scope staleness (niche, documented here).

## Verification

- Suite green at 0.10.0 (all 303 existing + the new files); `git -C ..\app status` clean throughout.
- Live pins: `cloud.n` equals an inline geocoded count (no magic number); top-segment stability vs the
  hotspot pins; `njunction:323` → counts only + "מחלף מורשה"; post-deploy `60/836` → model block with
  excess < 0 (the beat-3 story); post-severity-deploy the ujunction panel's conditional block is structurally
  present (n_persons > 200, three positive relatives, severity model_id on the chip).
- Headless DOM counts (street AND canvas AND `?basemap=off`): `maplibregl-canvas` present, legend, credit
  badge, panel nodes; the `?run=hotspot_map` regression untouched.
- Wheel namelist: exactly the committed `webdist/**` (now incl. `basemap-assets/`) + `data/israel.json` +
  fonts + `page.py`; **no `*.pmtiles`**; wheel-install on the clone boots into canvas mode.
- Stage discipline: headless/dev runs on a scratch `NL2SQL_CORE_DATA_DIR` (set before process start);
  preflight re-verified before any show.
