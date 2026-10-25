# P0 spikes — answers (2026-08-28)

All spike code lives in `c:\tmp` (throwaway; `c:\tmp\spike-mod\` is kept as the P3 page reference).
Nothing here is plugin code.

## Environment
- Python 3.14.6 (only interpreter on the machine) · pip 26.1.2 · node v24.16.0 / npm 11.13.0 · git 2.55 · no uv.
- `app\install.ps1` (pip branch): **175 s** wall incl. three bird_bench downloads; selftest passed with
  zero cassettes ("no recordings shipped" is a note, not a failure).
- App venv after P0: nl2sql-core 1.6.0 (API 1.0), duckdb 1.5.0, matplotlib 3.11.1, numpy 2.5.2,
  pandas 2.3.3, python-bidi 0.6.11, nl2sql-eda 1.0.0, nl2sql-shapes 1.0.0 (local index), pytest 9.1.1, build 1.6.0.
- Entry points seen by the app: `nl2sql.modules: eda, shapes` · `nl2sql.pages: eda, shapes`.
- `run.ps1`: health in **4 s**; first `/api/schema?db=israel_accidents` **15 s** (437 MB open + semantic
  layer); `/api/health` reports `replay: false`, data dir `%LOCALAPPDATA%\nl2sql-core`.
- Registry: `israel_accidents` → `C:\data\israel_accidents\israel_accidents.duckdb` (was the pristine
  Hebrew Desktop path, `\u`-escaped). Pristine folder: 9 files read-only. Working copy: writable.
- `git -C app status` clean throughout.

## Spike A — `ctx.query` is unscoped; what chat actually sees
Method: throwaway `spike-mod` (two no-input actions) installed `-e` into `app\.venv`; `GET /api/schema`.
- `weather-count` → `count(*) FROM weather_hourly` = **10,519,200** through `ctx.query` (scope.json lists
  no column set for this table).
- `schema-probe` → `ctx.schema_text()` = **58,193 chars, 43 `Table:` headers, `weather_hourly` present**;
  `/api/schema` returns the same 58,193 chars and 43 tables.
- Before the restart, `/api/modules` listed the module and the page as *Problems* ("failed to import");
  after the restart: `modules: spike-mod, shapes, eda · pages: shapes, eda, spike · problems: []`.
Conclusion: scope.json never gates `ctx.query`; chat's prompt already carries every object — the gap
is rules, not visibility (concept map §1–§2 stand).

## Spike B — verification answers; chat without a key
`Context(db_path=…)` over the working copy (`c:\tmp\spike_b.py`):
killed 2024 **439** · slight accidents 2024 **5,458** · casualty accidents 2024 **8,315** · naive slight
(no case filter) **50,145** · weather_hourly **10,519,200** · `ctx.tables()` = 43 · no `.wal` / new files
after querying (read-only open confirmed).
Chat via `/api/query` with no `ANTHROPIC_API_KEY` (logged-in `claude` CLI, OAuth Max):
- `כמה הרוגים היו בתאונות דרכים ב-2024?` → `SELECT COUNT(*) … FROM v_casualty_involved WHERE year = 2024
  AND injury_severity_code = 1` → **439**, 15.7 s, 69,274 tokens in / 1,032 out, cost-equivalent $0.27.
- `כמה תאונות קלות היו ב-2024?` → `… FROM accidents WHERE year = 2024 AND case_type_code = 1 AND
  severity_code = 3` → **5,458**, 13 s, 138,620 in / 464 out, $0.20. The semantic layer's rule held.

## Spike C — xgboost on Python 3.14.6
Scratch venv `c:\tmp\xgb314`: xgboost **3.4.1** (`py3-none-win_amd64`), numpy 2.5.2. `count:poisson`
with `set_base_margin(log(exposure))` trains (200 rounds); `exp(raw margin) == predict` (3.8e-6);
**`pred_contribs` sums to the raw margin with the bias column INCLUDING the base margin** (2.9e-6;
excluding it is off by 1.1). Mean y 3.386 vs mean pred 3.386. `SPIKE C OK`.
Decision: xgboost is viable on 3.14; the numpy-IRLS contingency is not needed.

## Spike D — Hebrew in matplotlib (from `app\.venv`)
Font resolved: `mpl-data/fonts/ttf/DejaVuSans.ttf`; **no glyph warnings**. With
`bidi.algorithm.get_display(s, base_dir="R")` the title, axis labels, tick labels, a mixed sentence
(`5,458 תאונות קלות ב-2024 (בלי הסינון: 50,145)`) and the credit footer all read correctly right-to-left
with digits intact (`c:\tmp\spike_d_hebrew.png`, eyeballed).
Decision: no font bundled; `python-bidi` is a host dependency (via `nl2sql-core[export]`).

## Spike E — RTL page + offline Leaflet
`spike-mod` ships a Vite+React page (`nl2sql.pages` entry-point **name `spike` == base `/page/spike/`**),
`<html lang="he" dir="rtl">`, one Hebrew paragraph with `dir="ltr"` islands for `5,458` and
`case_type_code = 1`, a Leaflet map with **no tile layer** drawing `israel.json` (Natural Earth outline,
106 vertices) plus one `circleMarker` at Tel Aviv with a Hebrew tooltip.
- `npm install` (67 packages, network) + `vite build`: 3 files, 298 KB JS / 15.6 KB CSS, base baked in.
- Served after restart: `/page/spike` → 307 → `/page/spike/` (200, `dir="rtl"`, `lang="he"`); JS and CSS
  200; the bundle contains Leaflet, the Israel geometry and the Hebrew tooltip; the CSS contains the
  Leaflet styles and 5 `url(images/…png)` references that were not emitted (harmless with circleMarker).
- **First build was blank in the browser** (owner saw "tab missing / page blank"): Leaflet threw
  `Cannot read properties of undefined (reading 'min')` in `Polyline._clipPoints` because the GeoJSON
  layer was added before `fitBounds` gave the map a view; React 18 unmounted the root. Fix: view first,
  layers after (see `PITFALLS.md`). Found with `msedge --headless=new --enable-logging=stderr --dump-dom`.
- After the fix (headless Edge screenshot `c:\tmp\spike_e_final.png`): heading + paragraph
  right-aligned; `5,458`, `case_type_code = 1`, `50,145` read LTR inside the Hebrew sentence; Israel
  outline on white with no tiles; red Tel Aviv dot; zoom control; credit footer; console shows only
  the step logs, no errors; DOM has `leaflet-container`, 2 SVG paths, tooltip pane, zoom control.
- Sidebar (headless dump of the main app): `🧩 Modules`, `🔬 EDA`, `📐 Shapes`, `🧪 Spike` all present.
- Uninstall + restart left the app clean: **yes** — `pip uninstall spike-mod` → 0 leftovers in
  site-packages; after restart `modules: shapes, eda · pages: shapes, eda · problems: []`;
  `/page/spike/` → 404; `git -C app status` empty; nothing named `*spike*` under the data dir.

## Notes for P3
- GeoJSON as `israel.json` (Vite JSON module); P3 fetches a 1:10m outline (Natural Earth, public domain).
- Map `div` as a `dir="ltr"` island; `L.circleMarker` only; import `leaflet/dist/leaflet.css`.
- **Give the map a view before adding vector layers**; wrap map setup in try/catch with a visible error
  card so a map failure never blanks the page.
- Headless Edge works for visual checks (`--headless=new --dump-dom` / `--screenshot`, with
  `--enable-logging=stderr` for console errors) — but use a fresh `--user-data-dir` per run, otherwise
  the profile serves the previous `index.html` from cache.
