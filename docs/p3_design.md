<!-- Saved from the approved plan file on 2026-08-30; the plan file wins on conflicts until P3 acceptance, then this copy is the record. -->

**As built (2026-08-30):** everything below shipped as planned, with these notes. Live numbers pinned in
`tests/test_live.py::test_hotspot_map_live`: segments 2019–2024 top = 70/120 with **176** (= `segment_rates`),
coverage 15,366 / 20,355 (75.5 %); 2017–2024 coverage 19,865 / 28,213 (= the `segment_rates` pin); default 2008–2024
top = 20/13 with 347 (167 static-assigned), coverage 49,185 / 64,772 (static 29,320 + as-of 19,865), 64,091 geocoded;
njunctions top = 323 מחלף מורשה 219 (dim rows 2), coverage 21,973 / 22,517 (97.6 %); ujunctions top = 5000/14900823
270, coverage 67,050 / 70,084 (95.7 %); road 60 top = 60/818 with 310; 2005–2007 → the "no coordinates" refusal;
top 5 with `points` → 702 points. Outline: Natural Earth 1:10m simplified at 0.0015° → 355 vertices, 7.3 KB
(`tools/fetch_outline.py`). Page bundle ≈ 321 KB JS + 23 KB CSS; the page also takes `?run=<action>` (auto-run
with the defaults — demo pre-flight and headless checks). The map twin is landscape (9.6 × 7.6 in: map left, top-12
list right) rather than the portrait frame suggested in the design pass, so the caveat lines keep the frame's width.
Suite: 236 tests (13 live). Wheel acceptance done from `dist/nl2sql_accidents-0.3.0-py3-none-any.whl` (page mounted,
30 markers in the headless DOM, Layer 0 chart), then the editable install was restored for development.

**Sweep corrections (2026-08-30, ultracode verification, confirmed by refuters):** (1) urban-junction labels were
built from two independent `min()`s — with the police recording a junction's streets in either order, 28 of the
top 30 read "X / X"; now `UJ_NAMES_CTE` takes ONE row's pair (the lexicographically smallest) over all accidents
and both `hotspot_map` and `before_after.site_label_sql` use it, so the hand-off label equals the map label;
(2) `urban_junction_code = 99999999` is an "unknown junction" sentinel (556 casualty accidents in 82 cities, no dim
row) that ranked 16th on the default urban map — added to `JUNCTION_SENTINEL_CODES` used by the map, the coverage,
`site_coding_exprs` and `parse_site_key`; (3) junction caveats: the coordinates line says the units are placed from
the dimension (a junction range with 0 % accident coordinates still maps), the omitted line names the real reason, and
the closing line no longer promises `excess` for junctions; (4) the popup lists the unit's accidents when `points`
(12 newest; the rest stay grey markers with tooltips) — the beat-3 drill-down as scripted; (5) the triage map route's
Hebrew stems are anchored (מוקדם, מפתח, רמפה are not map questions). Refuted: "junctions 2005–2007 should refuse"
(they are placed from the dimension by design — the caveat now says so).

# P3 — 🚦 page (Layer 1) + `hotspot_map` (detailed plan)

## Context

P3 ships the plugin's own page: `🚦 תאונות` at `/page/accidents/` (React + Vite, RTL-first, plain CSS with the app's
design tokens), which draws every P1/P2 answer with the full **answer anatomy** (denominator badge, caveat ribbon,
PNG, table, show-SQL, CBS credit; styled refusal / route cards), the six-tab layout from PLAN_1 §6, the `about`
header strip and a `triage` box on every tab — plus the new **`hotspot_map`** action (observed casualty-accident
counts per unit on a Leaflet map with no tile layer, and a server-drawn PNG twin so Layer 0 and any map failure
still show a static map). סטודיו / ממצאים ship as empty states (P4 flips them). Version **0.3.0**, `[P3]`, `v0.3`.
Acceptance rule from `docs/plan.md` §P3: the page must work on the clone **from a built wheel** (not `-e`), and
Layer 0 must still render everything.

**Decisions taken 2026-08-30 (user):** segment geometry = **Point at the mean lat/lon** of the unit's geocoded
accidents (km range + names in the popup); Israel outline = **Natural Earth 1:10m fetched once at build time**
(public domain, simplified, committed as package data; the P0 spike's coarse outline is the fallback); ultracode =
**one adversarial sweep at the end of P3** (I ask before launching it — the P2 sweep hit the monthly spend limit).

## Facts the design rests on (verified by the exploration + a design pass on DuckDB 1.5.0, 2026-08-30)

- **Pages**: `nl2sql.pages` entry point named `accidents` → `page()` returns `{"path": <webdist>, "label"}`;
  discovered **once at app import** (restart after install; before it the page/module show as a *Problem*);
  `StaticFiles(html=True)` — no SPA fallback, so page state lives in the query string; `?db=` is appended by
  `launcher.js` at click time from the main app's Connection select; a page opens in its own named tab.
  `GET /api/modules` returns every action's input declarations (`kind, label, default, choices, help`) — the page
  builds its forms from them (no second copy of the catalog in JS). `POST /api/modules/run {module, action, db,
  inputs}` → `{ok, kind, data, title, note}`; with `view=chart` the `data` is the whole spec (png, rows, columns,
  sql, denominator, caveats, credit, stamp + extras). Layer 0 shows only `png_base64 + basis + note`.
- **Precedents**: `nl2sql-shapes/web` (api.js single door, tabs-as-state, busy/err/data triad, tokens CSS, Vite
  config, `page.py`, `MANIFEST.in` + `package-data`, committed `webdist/`) and the P0 spike `c:\tmp\spike-mod\`
  (RTL html, Leaflet without tiles, `fitBounds` **before** `addTo`, `L.circleMarker` only, JSON-module outline,
  `dir="ltr"` islands). No RTL precedent, no page tests in any precedent, no page template in `app\plugin-template`.
- **Geometry in the DB**: `accidents.latitude/longitude` are WGS84 (no reprojection): casualty accidents 2005–2007
  **0 %** geocoded, 2008+ **99.6 %**, interurban 2008+ 98.9 %. `dim_junction_nonurban` 4,202 rows / 2,525 codes
  (873 NULL coords — dedupe or a join doubles counts); `dim_junction_urban` 14,592 rows, `(junction_code, city_code)`
  unique, 4,550 NULL coords (31 % — the "mean of own accidents" fallback is load-bearing). **No traffic table has
  coordinates**; `traffic_segments` has km ranges only (4,834 rows / 1,311 keys). `road_km = 0` = not coded.
- **DuckDB 1.5.0** (app pin): a window over a range join *without* a year equality mis-binds → the map keeps
  `a.year = u.year` in the assignment join by giving every year a geometry row (per-year vintage 2017+ from
  `UNITS_CTE`; each key's **latest `traffic_segments` vintage** for the years before). For 2017+ ranges the
  per-segment counts therefore **equal `segment_rates`' `accidents`** for the same segment/years (demo continuity).
  All six statements below bind and return the hand-derived rows on 1.5.0 (design pass, fixture shapes).
- Tooling: node v24.16.0 / npm 11 on this machine (participants: node ≥ 20); Python 3.14; pip only.

## Files

```
nl2sql_accidents/page.py                     stdlib-only; never imported by __init__; {"path": webdist, "label": "🚦 תאונות"}
nl2sql_accidents/data/israel.json            Natural Earth 1:10m Israel outline (public domain), simplified ≤ ~120 KB — ONE file used by
                                             Vite (imported as a JSON module) AND by the matplotlib twin (package data)
nl2sql_accidents/actions/hotspot_map.py      the action (run first, ACTION last)
nl2sql_accidents/sqlkit.py                   + assign_join(table) (ASSIGN_JOIN = assign_join(), text unchanged), NAMES_CTE (extracted from
                                             build_segment_rates_sql), STATIC_GEOMETRY_CTE, GEO_PREDICATE, JUNCTION_SENTINELS, HOTSPOT_UNITS,
                                             POINTS_PER_UNIT/POINTS_TOTAL, as_bool, build_hotspot_sql / hotspot_coverage_sql / hotspot_points_sql,
                                             FIRST_GEOCODED_YEAR_SQL, outline() loader (importlib.resources)
nl2sql_accidents/charts.py                   + map_png(units, *, title, badge, caveats, stamp) inside the existing png() frame
nl2sql_accidents/__init__.py                 __version__ = "0.3.0"; ten actions (hotspot_map after segment_rates)
nl2sql_accidents/actions/{about,triage}.py   about lists ten actions; triage route "מפת מוקדים" → hotspot_map (+ answerable in the per-km refusal)
nl2sql_accidents/webdist/                    the BUILT page (committed — decided in P0, not re-opened)
web/index.html · vite.config.js · package.json · src/{main.jsx, App.jsx, api.js, md.jsx, tabs.js, styles.css}
web/src/components/{Header, TriageBox, ActionPanel, Form, Answer, Card, MapView, Empty}.jsx
tools/fetch_outline.py                       one-off (repo-side, not in the wheel): NE 1:10m admin-0 → the Israel feature → simplify →
                                             nl2sql_accidents/data/israel.json; fallback = the spike's outline (said in the file + PITFALLS)
pyproject.toml                               0.3.0; [project.entry-points."nl2sql.pages"] accidents = "nl2sql_accidents.page:page";
                                             [tool.setuptools.package-data] nl2sql_accidents = ["webdist/**/*", "data/*.json"]
MANIFEST.in                                  recursive-include nl2sql_accidents/webdist *  ·  include nl2sql_accidents/data/*.json
tests/test_hotspot_map.py · tests/test_page.py · conftest coordinates · test_contract / test_live / test_triage / test_sqlkit / test_charts additions
docs/p3_design.md · docs/plan.md · README.md · CLAUDE.md · PITFALLS.md · docs/PLAN_1_CONCEPT_MAP.md (corrections paragraph)
```

## `hotspot_map` (action)

- **Inputs**: `unit` choice `segments | njunctions | ujunctions` (default segments) · `road` number 0 (0 = all;
  filters `road1_number` for segments **and** njunctions — the demo goes `segment_rates(road=…)` → `hotspot_map`;
  `road` with ujunctions → ActionError) · `from_year` 2008 · `to_year` 2024 (any range inside 2005–2024; 2005–2007
  rows are **counted but not placed**) · `color_by` choice `observed | excess` (default observed; **excess in P3 =
  observed + a leading caveat "התבקשה צביעה לפי excess — אין מודל אתר פרוס…"**, `color_by_effective` in the spec —
  the P4 hook) · `top_n` 30 (1–200) · `points` bool False (the top units' individual accidents in the geojson for
  the popup drill-down — internal use, permitted; cap 300/unit, 3,000 total, in SQL) · `view` chart | table | sql.
- **Method** — aggregate first, geometry after. Segments: `geom` = `units` (2017+) ∪ latest-vintage
  `traffic_segments` rows × `range(y0, min(y1+1, 2017))`, the assignment join (`assign_join("geom")`, alias `u`,
  `a.road_km <> 0`, half-open km, `a.year = u.year`) + `ASSIGN_QUALIFY`; counts per `(road, seg)`: accidents,
  KSI, geocoded (**`GEO_PREDICATE` = lat 29–34 ∧ lon 34–36**, so a 0/0 point is "not geocoded"), mean lat/lon of
  the geocoded, first/last year, `static_assigned`; km range + `site_key` (`printf('road:%d/%g-%g')`, parses with
  `parse_site_key`) from the **latest vintage** (pasteable into `before_after`; may differ from the years' vintages
  — said in a caveat); names from `NAMES_CTE` (identical to `segment_rates`, so map label == ranking label);
  `rank` by accidents desc, KSI desc, key; `LIMIT top_n`. Junctions: base = the `site_coding_exprs` *coded* rule
  (real code, not 0/99/9999; nonurban `road_type_code IN (3,4)`, urban `IN (1,2)` + `city_code > 0`), counts per code
  / `(city, code)`, then a `LEFT JOIN` to the **grouped** dimension (`min(name)`, `avg(lat/lon)`, `dim_rows`) with
  `coalesce(dim, accident-mean)` and a `geometry_source` column (`dim` | `accidents`). A coverage statement per
  year (segments: `geometry`, total, matched, with_coords, matched_with_coords, outside_bbox; junctions: population =
  `road_type_code = 3` / `= 1`, coded, with_coords, `coded_off_junction`, outside_bbox) feeds every caveat number.
  Points statement only when `points`: the shown keys as a `VALUES` list joined by equality, `QUALIFY row_number()
  … <= POINTS_PER_UNIT` (newest first), `LIMIT POINTS_TOTAL`.
- **Spec**: `type "accidents/map"`; `rows/columns` = the ranking (segments: `road, seg, name_from, name_to, km_from,
  km_to, accidents, ksi_accidents, geocoded, latitude, longitude, first_year, last_year, static_assigned, site_key,
  rank`; junctions: `code` (+ `city, city_name, street1_name, street2_name`), `name`, counts, coords,
  `geometry_source, dim_rows, first_year, last_year, site_key, rank`); `geojson` = FeatureCollection of Point
  features (`properties {kind:"unit", unit, site_key, label, rank, accidents, ksi_accidents, geocoded, first_year,
  last_year, …}` + `{kind:"accident", site_key, rank, accident_id, case_type_code, year, date, severity_code,
  severity_label, road_km?}` when `points`), rows without a placeable coordinate stay in `rows` only;
  `png_base64` = the twin; `denominator("counts", "ספירות תאונות עם נפגעים לפי יחידה — ללא מכנה חשיפה", matched,
  total, pct)` (amber); extras `unit, road, color_by, color_by_effective, from_year, to_year, top_n, points, coverage,
  coverage_sql, points_sql, map{units_listed, units_placed, units_omitted, points, bbox}, stamp`; `x="site_key"`,
  `y="accidents"`; basis `hotspot_map | unit=… | road=… | color_by=… | y0-y1 | top n | placed p | points k |
  coverage m/t (pct%) | geocoded g/t`. Title `מפת מוקדים · <unit Hebrew>`.
- **Caveats (data-driven, most specific first, no `;`)**: (1) excess fallback when requested; (2) coordinates —
  "N מתוך T … ללא קואורדינטות — נספרות אך אינן ממוקמות" + "שנים ללא קואורדינטות כלל: …" + "K מחוץ לגבולות ישראל"
  when > 0; (3) units listed but not on the map (when > 0); (4) assignment — segments: matched/total, 2017+ per-year
  vintage like `segment_rates` (n), before that the latest `traffic_segments` vintage as static geometry (n), ק״מ 0
  = לא קודד; junctions: coded share of junction accidents, `coded_off_junction` when > 0; (5) geometry source —
  Point = mean of the assigned accidents' coordinates, names/km/site key from the latest vintage (fits
  `before_after`); junctions: dim dedupe (rows merged) + fallback count; (6) `CAVEAT_COUNTS_NOT_RISK` + pointers
  (`segment_rates` for rates, excess after a deployed site model; junctions rank by counts only — no traffic
  volume); (7) the points cap line when `points`.
- **Refusals / errors**: no unit with an accident in range → refusal; rows but **zero placeable** units (live
  2005–2007) → refusal naming the first geocoded year (`FIRST_GEOCODED_YEAR_SQL`); outside 2005–2024 (`year_range`);
  `top_n` ∉ 1–200, `road < 0`, `road` with ujunctions, unknown choices, non-boolean `points` → `ActionError`;
  foreign DB → the guard's refusal.
- **PNG twin** (`charts.map_png`): portrait frame (`figsize=(7.2, 9.6)`), the outline rings from the package file
  (Polygon/MultiPolygon), circles at the unit points (area ∝ count, teal, largest first, rank digits on the top 5,
  `set_aspect(1/cos 31.5°)`, axis off), a side list of the top 12 labels with counts; standard title/amber
  badge/caveats/credit/stamp; **never draws individual points** (Layer-0/fallback face = units only); Figure/Agg
  only (thread-safety test).

## The page (`web/`)

- **Boot** (`App.jsx`): `db` from `?db=`; fallback `GET /api/connections` most-recent (eda pattern); else a boot
  card telling the user to open the page from the sidebar. `GET /api/modules` once → the `accidents` module's actions
  (declarations drive the forms) + `problems` (a card if the accidents module is missing/broken). `about` once →
  **header strip** chips (connection · data end · deployed model · license) parsed from the card's `**חיבור** — …`,
  `**כיסוי** — …`, `**מודל אתר פרוס** — …` lines, raw card as fallback; `document.title`.
- **Tabs** (state + `?tab=` deep link, `tabs.js`): מגמות (`trend`, `naive_vs_correct`) · נקודות תורפה
  (`segment_rates`, `hotspot_map`) · חומרה (`severity_profile`, `vehicle_cells_ranking`, `weather_check`) ·
  לפני/אחרי (`before_after`) · סטודיו (empty state → "אין מודל אתר פרוס · הסטודיו מגיע בשלב P4") · ממצאים (empty
  state). **`TriageBox`** at the top of every tab: a question → the card; route actions are buttons that switch the
  tab and open that action's panel.
- **`ActionPanel`** = `Form` built from the declarations (number → `<input type="number">` sent as a JSON number;
  choice → `<select>`; bool → checkbox; text → input; Hebrew labels; ASCII `help` as the title attribute; the `view`
  input is hidden — the page always sends `chart` for chart actions and the declared default otherwise) + Run +
  `Answer`. Busy / error / data triad per panel; the last inputs stay in the form. A "hand-off" from
  `segment_rates` rows / map popups: a button that fills `before_after.site` with the row's `site_key`.
- **`Answer`** (the anatomy, one component for all kinds): `title`; **badge** by `denominator.kind` (exposure =
  green, counts = amber, none = red, na = grey) with the label; **caveat ribbon** (all caveats, not the PNG's six);
  body by kind — `chart`: `type === "accidents/map"` → `MapView` else `<img src=data:image/png;base64,…>`, then the
  table (`columns/rows`, collapsed beyond 15 rows), then **show-SQL** `<details>` (`spec.sql`, LTR monospace);
  `markdown` → `Card`; `table` → table; `sql` → `<pre>`; `error` → error box; **credit footer** (`spec.credit`) on
  every CBS answer; the Layer-0 `note` under a small "הערה" toggle.
- **`Card`** (`md.jsx`): the Layer-0 markdown subset rendered to React (single `#`, `-` bullets, bold/italic/code,
  escape-first); shape by first line — answer (`מכנה:` … credit), **refusal** (`# ❌` … lab line: red-bordered card
  with reason / הסיבה / מה לעשות / מה כן אפשר), **route** (`# 🧭`: actions as buttons).
- **`MapView`**: Leaflet 1.9.4, `attributionControl: false`, **no tile layer**; outline imported as a JSON module
  from the single package file (`import outline from "../../../nl2sql_accidents/data/israel.json"`; `server.fs.allow`
  = repo root if the dev server objects); `fitBounds` first (max zoom capped for a single feature), then the outline,
  then `L.circleMarker` per unit feature (radius ∝ √count, colour by rank quintile), popups (label, `site_key` as an
  LTR chip + the before_after hand-off button, accidents/KSI, km range or dim source, first–last year, the accident
  list when `points`), a legend, the credit line; the map `div` is a `dir="ltr"` island; **try/catch → a visible
  error card + the PNG twin** (never a blank page); `map.remove()` on unmount.
- **CSS**: `styles.css` starts with the app tokens byte-for-byte (from `nl2sql-shapes/web/src/styles.css`, incl. the
  dark block), logical properties only, `.ltr` class for numbers/SQL/keys, `font-variant-numeric: tabular-nums`.
- **Build**: `cd web; npm install; npm run build` → `nl2sql_accidents/webdist/` (≈ 300 KB), committed;
  `npm run dev` proxies `/api` to :8000.

## Tests

- **`tests/conftest.py`**: coordinates exist iff `cell` (as today) but become deterministic — urban
  `lat = 32.0 + uj/10000, lon = 34.0 + city/10000`; otherwise `lat = 32.0 + (road_km or 0)/1000, lon = 35.0 +
  (road1 or 0)/100`; `NO_GEO = {"S3"}` keeps one celled row without coordinates (the live 0.4 %); the urban dim row
  777/5000 gets NULL coordinates (exercises the accident-mean fallback); the duplicated 433 rows stay. No row is
  added; no existing test reads coordinates (grep-verified) → every P1/P2 pin stays.
- **`tests/test_hotspot_map.py`** (numbers derived from the planted rows and reproduced on 1.5.0 in the design pass):
  segments 2019–2021 table rows `[1,10,'צומת א','צומת ב',0.0,12.0,3,1,3,32.056,35.01,2019,2020,0,'road:1/0-12',1]`,
  `[2,20,…,5.0,7.5,2,2,2,…,'road:2/5-7.5',2]`, `[1,11,…,9.5,15.0,1,1,0,None,None,2019,2019,0,'road:1/9.5-15',3]` and
  `{(road,seg): (accidents, ksi)}` **equals `segment_rates(order_by="count")`** = `{(1,10):(3,1),(2,20):(2,2),
  (1,11):(1,1)}`; coverage by_year `[[2019,'asof',4,3,3,2,0],[2020,'asof',3,2,3,2,0],[2021,'asof',3,1,3,1,0]]`
  (6/10, 60.0 %, with_coords 9) and the "1 מתוך 10 … ללא קואורדינטות" caveat; geojson has 2 unit features (1/10
  rank 1), `map.units_omitted == 1` + its caveat; defaults 2008–2024: row 1 `[1,10,…,12,4,11,32.05073,35.01,2012,
  2020,9,'road:1/0-12',1]`, coverage 15/32 (46.9 %), with_coords 25, static 9 / asof 6, `years_without_coords ==
  [2022, 2023, 2024]`; `road=1` 2019–2021 → keys `[[1,10],[1,11]]`, coverage 4/7, `road1_number = 1` in
  `coverage_sql`; njunctions → one row `[433,'צומת העשור',7,1,7,≈32.10005,≈35.10005,'dim',2,2012,2018,
  'njunction:433',1]` (dedupe: `dim_rows == 2`, a plain join would give 14), coverage 7/8; ujunctions →
  `[5000,777,'תל אביב - יפו','רחוב א','רחוב ב',5,1,5,32.0777,34.5,'accidents',1,2012,2018,'ujunction:5000/777',1]`,
  coverage 5/7, the fallback caveat; `points=True` 2019–2021 → 5 point features newest-first (2020000002,
  2019000002, 2019000001; 2021000002, 2020000003), `points_sql` face re-runs to the same rows; cap via
  `monkeypatch(sqlkit.POINTS_PER_UNIT, 2)` → 4 points + the "תקרה 2" caveat; refusals (2022–2024; njunctions
  2019–2021; segments 2008–2011; `to_year=2030` → "31.12.2024"); errors (`top_n` 0/201, `road=-1`, `unit="x"`,
  `color_by="x"`, `points="maybe"`, ujunctions + road); excess fallback (kind counts, `caveats[0]`,
  `color_by_effective`, basis "fallback observed", stamp `excess->observed`); faces (sql re-runs to `rows`,
  `view="sql"` == `spec["sql"]`, coverage_sql re-runs to by_year); discipline (`json_safe` incl. geojson, `png_of`,
  ASCII basis/stamp, no `;`, no digits in the title, `a.road_km <> 0` / `a.year = u.year` / `arg_max(name_from,
  src_year)` / `case_type_code = 1` in the SQL, no `traffic_adt_filled`).
- **`test_sqlkit.py`**: `assign_join() == ASSIGN_JOIN` (text identical to today's constant), `as_bool` table,
  `range(2019, 2017)` present in the 2019–2021 text (empty static branch), `STATIC_GEOMETRY_CTE` deterministic
  ordering. **`test_charts.py`**: `map_png` with 0 units (outline only), a MultiPolygon outline, 200 units.
- **`tests/test_page.py`**: entry-point name `accidents` == the segment of `base` in `web/vite.config.js`; `page()`
  path exists with `index.html` containing `dir="rtl"`, `lang="he"`, `/page/accidents/assets/`; `data/israel.json`
  is a FeatureCollection inside the bbox (29–34 N, 34–36 E); `page.py` imports only stdlib (AST check).
- **`test_contract.py`**: `NAMES`/`LABELS` (`מפת מוקדים · hotspot_map`)/`CHART_ACTIONS`/`VIEW_RUNS` (2019–2021)/
  `CHART_RUNS` (`{}` and `{"unit": "njunctions"}`) + the data-dir test gains `hotspot_map(points=True)`; version 0.3.0.
- **`test_live.py`**: segments 2019–2024 row 1 == `[70, 120, 'צומת יסיף', 'כניסה לגדידה רח 115', …, 176, 16, …]`
  (the `segment_rates` pin); segments 2017–2024 coverage **19,865 / 28,213** (same units + assignment as
  `segment_rates`); 2005–2007 → the "no coordinates" refusal; `outside_bbox == 0` (else the caveat must fire); the
  njunctions / ujunctions top rows and `geometry_source` pinned after the first live run.
- **`test_triage.py`**: "מפת מוקדים" / "hotspot" / "map" → route `hotspot_map`; the model rule still excludes it.

## Steps (from `accidents-lab\`)

0. Save `docs/p3_design.md` (this plan + the SQL below); pre-flight (`git -C app status` empty, port 8000 = the lab clone, tree clean at `v0.2`).
1. `tools/fetch_outline.py` → `nl2sql_accidents/data/israel.json` (network once; fallback = the spike outline, noted in PITFALLS if used).
2. Python, red → green per slice: `sqlkit` (assign_join / NAMES_CTE extraction / constants / builders / as_bool + tests) → `conftest` coordinates (whole suite must stay green untouched) → package-data + `charts.map_png` + tests → `pyproject` 0.3.0 + `__init__` + contract lists → `actions/hotspot_map.py` + `test_hotspot_map.py` → `about`/`triage` lines → live pins.
3. `page.py` + entry point + `MANIFEST.in` + `tests/test_page.py` (red until the build exists).
4. `web/`: scaffold (spike + shapes patterns) → `api.js`, `md.jsx`, `Form`, `Answer`, `Card` → tabs, header, triage box → `MapView` → `styles.css` → `npm run build` → commit `webdist/`. Record node/npm versions and the build recipe for participants (README).
5. **Wheel acceptance**: `..\app\.venv\Scripts\python -m build --wheel` (namelist has `webdist/**`, `data/israel.json`, `page.py`, no `tools/`, no `web/`); `pip install dist\nl2sql_accidents-0.3.0-py3-none-any.whl` into the clone (**not** `-e`); restart; `/api/modules` → `pages` has `accidents` (`🚦 תאונות`, `/page/accidents/`), ten actions, `problems: []`; browser: sidebar tab → every tab, every action, the map (popups, legend, hand-off to before_after), a refusal card, the route card, the empty states; Layer 0 still renders all ten; headless Edge screenshots with a fresh `--user-data-dir` (committed frames = chart/ranking/card frames only, never the point layer). After acceptance, reinstall `-e` for P4 development (recorded).
6. **Ultracode verification sweep** (on your go, after the credits check): emitted SQL for the three unit kinds × ranges × road vs the golden rules and the units/assignment recipe; geojson ⇄ rows ⇄ PNG consistency; the page contract (every kind/shape rendered, RTL islands, error paths, `?db=` handling); caveat numbers vs the coverage statements. Confirmed findings fixed before the commit.
7. Docs: `docs/plan.md` (P3 done + deviations), `README` (page, node ≥ 20, `npm run build`, commit webdist, the restart-after-install sentence verbatim), plugin `CLAUDE.md` (page + map facts), `PITFALLS.md` (first non-echarts page; every stumble), PLAN_1 corrections paragraph (`hotspot_map` row: `road` input, Point geometry, static-vintage rule, bbox predicate, deterministic names, `top_n`/`points` caps, `color_by=excess` fallback).
8. Recap → on your acceptance: `[P3] page (Layer 1): RTL React page, answer anatomy, hotspot_map` + tag `v0.3`.

## Acceptance
- [x] Suite green from the repo with `..\app\.venv` (fixture + live); wheel namelist as above (2026-08-30).
- [x] Page works on the clone **from the built wheel**: sidebar `🚦 תאונות` → all six tabs, ten actions, map with popups, refusal/route cards, header strip, triage box; Layer 0 unchanged (wheel install + headless DOM counts, 2026-08-30).
- [x] `hotspot_map(segments, 2019–2024)` counts == `segment_rates` counts (row by row, 987 keys, 0 diffs — sweep); PNG twin renders; `color_by=excess` falls back with the caveat.
- [x] Ultracode sweep run (19 agents, 4 checkers + 15 refuters): 8 confirmed medium/high + 13 low findings fixed; 3 refuted (2005–2007 junctions, the triage stems, the fallback connection).
- [ ] `git -C app status` clean; nothing new under `%LOCALAPPDATA%\nl2sql-core`; no CBS data in the repo (the only data file is the Natural Earth outline); docs updated; `[P3]` + `v0.3` after acceptance.

## Risks / pitfall watch
DuckDB 1.5.0 binder (year equality in the join, typed keys, no window over a pure range join — the points window
sits over the already-one-row-per-accident `matched`); junction dedupe (grouped dim, never a plain join); NULL dim
coordinates (fallback + caveat); the 2005–2007 coordinate floor (count, don't place; refuse when nothing is
placeable); `GEO_PREDICATE` bbox (a 0/0 point must not drag a mean into the Atlantic); latest-vintage `site_key` ≠ the
years' vintages (caveat); Leaflet order trap + visible error card; single-feature `fitBounds` (max zoom); `.geojson`
naming; Vite importing a JSON file from outside `web/`; RTL bidi in mixed lines (LTR islands for keys/SQL/numbers);
the wheel must carry `webdist/**` and `data/*.json` (explicit `package-data`, non-recursing `packages`); restart
after install; stale `?db=` tabs; geojson size at `top_n=200, points=True` (≈ 0.6 MB, default off); committed
frames = chart/ranking/card only.

## Design detail — the SQL (verified on DuckDB 1.5.0 against the fixture shapes)

```python
_ASSIGN_ON = ("ON a.road1_number = u.road\n     AND a.road_km <> 0\n"          # km 0 = not coded
              "     AND a.road_km / 10.0 >= u.km_from\n"
              "     AND a.road_km / 10.0 <  u.km_to\n     AND a.year = u.year")   # half-open, the view's predicate

def assign_join(table: str = "units") -> str:
    return f"JOIN {table} u\n      {_ASSIGN_ON}"          # alias u, so ASSIGN_QUALIFY applies verbatim

ASSIGN_JOIN = assign_join()                                # text identical to today's constant

GEO_PREDICATE = "latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 36.0"   # NULL fails BETWEEN
JUNCTION_SENTINELS = "(0, 99, 9999)"
POINTS_PER_UNIT, POINTS_TOTAL = 300, 3000
HOTSPOT_UNITS = {"segments": "מקטעים", "njunctions": "צמתים לא-עירוניים", "ujunctions": "צמתים עירוניים"}

STATIC_GEOMETRY_CTE = """latest_segments AS (             -- latest traffic_segments vintage per key: static geometry before the as-of years, and the site key
    SELECT CAST(road AS INTEGER) AS road, CAST(seg AS INTEGER) AS seg, km_from, km_to
    FROM traffic_segments
    QUALIFY row_number() OVER (PARTITION BY road, seg ORDER BY src_year DESC, loaded_at DESC, km_to - km_from, km_from) = 1
)"""
NAMES_CTE = """names AS (                            -- traffic_segments: several vintages per key — one name pair
    SELECT CAST(road AS INTEGER) AS road, CAST(seg AS INTEGER) AS seg,
           arg_max(name_from, src_year) AS name_from, arg_max(name_to, src_year) AS name_to   -- latest vintage
    FROM traffic_segments GROUP BY road, seg
)"""

def _segment_map_ctes(y0, y1, road=0):
    static_end = min(y1 + 1, EXPOSURE_YEARS[0])            # range(y0, static_end) is empty when y0 >= 2017
    road_filter = f"\n      AND road1_number = {ilit(road)}" if road else ""
    return (f"{UNITS_CTE},\n{STATIC_GEOMETRY_CTE},\n"
            f"geom AS (                             -- one geometry per (road, seg, year): as-of units 2017+, static latest vintage before\n"
            f"    SELECT road, seg, year, km_from, km_to, gap_years, 'asof' AS geometry\n"
            f"    FROM units WHERE year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"    UNION ALL\n"
            f"    SELECT s.road, s.seg, t.y AS year, s.km_from, s.km_to, 99 AS gap_years, 'static' AS geometry\n"
            f"    FROM latest_segments s CROSS JOIN range({ilit(y0)}, {ilit(static_end)}) t(y)\n"
            f"),\n"
            f"base AS (                             -- casualty series, interurban, requested years (dossier 5.1)\n"
            f"    SELECT accident_id, case_type_code, year, accident_date, severity_code, severity_label,\n"
            f"           road1_number, road_km, latitude, longitude\n"
            f"    FROM accidents\n"
            f"    WHERE case_type_code = 1\n"
            f"      AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"      AND road_type_code IN (3, 4){road_filter}\n"
            f"),\n"
            f"matched AS (                          -- exact assignment predicate: half-open km, year equality, one row per accident\n"
            f"    SELECT a.accident_id, a.case_type_code, a.year, a.accident_date, a.severity_code, a.severity_label,\n"
            f"           a.road_km, a.latitude, a.longitude, u.road, u.seg, u.geometry\n"
            f"    FROM base a\n    {assign_join('geom')}\n    {ASSIGN_QUALIFY}\n)")

def build_hotspot_sql(unit, y0, y1, top_n, road=0):        # segments; junctions in _build_hotspot_junctions_sql
    return (f"-- nl2sql-accidents | hotspot_map | unit=segments | road={road or 'all'} | {y0}-{y1} | top {top_n}\n"
            f"WITH {_segment_map_ctes(y0, y1, road)},\n"
            f"counts AS (                           -- aggregate first, geometry after\n"
            f"    SELECT road, seg, count(*) AS accidents,\n"
            f"           count(*) FILTER (WHERE severity_code IN (1, 2)) AS ksi_accidents,\n"
            f"           count(*) FILTER (WHERE {GEO_PREDICATE}) AS geocoded,\n"
            f"           avg(latitude) FILTER (WHERE {GEO_PREDICATE}) AS lat,\n"
            f"           avg(longitude) FILTER (WHERE {GEO_PREDICATE}) AS lon,\n"
            f"           min(year) AS first_year, max(year) AS last_year,\n"
            f"           count(*) FILTER (WHERE geometry = 'static') AS static_assigned\n"
            f"    FROM matched GROUP BY road, seg\n"
            f"),\n"
            f"{NAMES_CTE}\n"
            f"SELECT c.road, c.seg, n.name_from, n.name_to, g.km_from, g.km_to,\n"
            f"       c.accidents, c.ksi_accidents, c.geocoded,\n"
            f"       round(c.lat, 5) AS latitude, round(c.lon, 5) AS longitude,\n"
            f"       c.first_year, c.last_year, c.static_assigned,\n"
            f"       printf('road:%d/%g-%g', c.road, g.km_from, g.km_to) AS site_key,   -- the before_after key syntax\n"
            f"       row_number() OVER (ORDER BY c.accidents DESC, c.ksi_accidents DESC, c.road, c.seg) AS rank\n"
            f"FROM counts c\n"
            f"LEFT JOIN latest_segments g USING (road, seg)\n"
            f"LEFT JOIN names n USING (road, seg)\n"
            f"ORDER BY rank\nLIMIT {ilit(top_n)}")
```

Segment coverage (per year; the action sums): `SELECT b.year, CASE WHEN b.year < 2017 THEN 'static' ELSE 'asof' END AS
geometry, count(*) AS total, count(m.accident_id) AS matched, count(*) FILTER (WHERE <geo b>) AS with_coords,
count(m.accident_id) FILTER (WHERE <geo b>) AS matched_with_coords, count(*) FILTER (WHERE b.latitude IS NOT NULL AND
NOT (<geo b>)) AS outside_bbox FROM base b LEFT JOIN matched m ON m.accident_id = b.accident_id AND m.case_type_code =
b.case_type_code GROUP BY b.year ORDER BY b.year` (a `geo_pred(alias)` helper builds `<geo b>`).

Junctions — base (`site_coding_exprs`' coded rule): nonurban `case_type_code = 1 AND year BETWEEN … AND road_type_code
IN (3, 4) AND nonurban_junction_code IS NOT NULL AND nonurban_junction_code NOT IN (0, 99, 9999) [AND road1_number = r]`;
urban `… road_type_code IN (1, 2) AND urban_junction_code … NOT IN (0, 99, 9999) AND coalesce(city_code, 0) > 0`.
Dim CTEs: `dim AS (SELECT junction_code AS code, min(junction_name) AS name, count(*) AS dim_rows, avg(latitude)
FILTER (WHERE <geo>) AS lat, avg(longitude) FILTER (WHERE <geo>) AS lon FROM dim_junction_nonurban GROUP BY
junction_code)` / urban grouped by `(city_code, junction_code)`. `counts` groups the base by the key with
`min(name)`/`min(city_name, street1_name, street2_name)`, accidents, KSI, geocoded, mean lat/lon, first/last year; the
final SELECT `LEFT JOIN dim USING (key)`, `round(coalesce(d.lat, c.lat), 5)`, `CASE WHEN d.lat IS NOT NULL THEN 'dim'
WHEN c.lat IS NOT NULL THEN 'accidents' END AS geometry_source`, `coalesce(d.dim_rows, 0) AS dim_rows`,
`printf('njunction:%d', code)` / `printf('ujunction:%d/%d', city, code)` AS site_key, `rank`, `LIMIT top_n`.
Junction coverage (one scan of `accidents`, population `road_type_code = 3` / `= 1`): total, matched (coded),
with_coords, matched_with_coords, `coded_off_junction` (coded rows on the other road type), outside_bbox, per year.

Points: `WITH <ctes>, keys(road, seg, rank) AS (VALUES (…), …) SELECT k.rank, m.road, m.seg, m.accident_id,
m.case_type_code, m.year, m.accident_date, m.severity_code, m.severity_label, m.road_km, m.latitude, m.longitude FROM
matched m JOIN keys k ON k.road = m.road AND k.seg = m.seg WHERE <geo m> QUALIFY row_number() OVER (PARTITION BY m.road,
m.seg ORDER BY m.accident_date DESC, m.accident_id) <= 300 ORDER BY k.rank, m.accident_date DESC, m.accident_id LIMIT
3000` (junctions: `base` + `keys(code, rank)` / `keys(city, code, rank)`). `FIRST_GEOCODED_YEAR_SQL = "SELECT min(year)
FROM accidents WHERE case_type_code = 1 AND <geo>"`.

Action module order: `run` → `_coverage` → `_caveats` → `_geojson` → `_keys` → `_png` → `ACTION`. Labels: segments
`f"{road}/{seg} · {name_from or ''} → {name_to or ''}"` (as `segment_rates`); njunction `f"צומת {code} · {name}"`;
ujunction `f"{city_name} · {street1} / {street2} (צומת {code})"` (as `before_after._site_label`). Every geojson
property passes through `scalar()` (dates → ISO, non-finite → None).

