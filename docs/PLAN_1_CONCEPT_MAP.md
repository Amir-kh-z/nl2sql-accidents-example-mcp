# PLAN 1 — Concept Map: `nl2sql-accidents` (מעבדת הבטיחות בדרכים)

**Status:** v2, 2026-08-28 — frame approved by the user; then corrected by a 36-agent ultracode
verification sweep (66 confirmed findings applied; the four judgment calls were decided by the user
and are marked ⚖️). Companion docs: `PLAN_2_DEMO_SCRIPT.md`, `PLAN_3_PHASED_BUILD.md`.
Knowledge base: `DOSSIER_TASK4_ACCIDENTS_DB.md` (dossier §n references below); methodology
detail beyond the dossier: the methodology report in the pristine folder's `docs\`.

## 0. Settled decisions (2026-08-28)

| # | Decision | Outcome |
|---|---|---|
| 0 | One plugin, two tiers | **Ratified.** One `Module`, one wheel, one page; studio actions lazy-import xgboost and return a readable `Result.error` with the pip command when `[ml]` is absent. Flag to Efraim: supersedes the old "two plugins" framing. |
| 1 | DB working location | **`C:\data\israel_accidents\` is LIVE.** Re-point the existing `israel_accidents` connection in `%LOCALAPPDATA%\nl2sql-core\added_connections.json` (same name → same sidecar basename). Desktop folder files set read-only as a guard. |
| 2 | Name | dist **`nl2sql-accidents`** · package `nl2sql_accidents` · module id `accidents` · **pages entry-point name `accidents`** (it becomes the URL `/page/accidents/`) · sidebar `🚦 תאונות` · product **מעבדת הבטיחות בדרכים** (Road Safety Lab). |
| 3 | Scope | **Core: א ב ג ד ה.** Stretch (cut freely): ח two-wheelers, ז per-unit SHAP profile, ו what-if. |
| 4 | Map | **Client-side Leaflet + bundled GeoJSON, no tile layer** (user's call over server-PNG). Units (segments/junctions) colored by observed/excess, optional individual-accident point layer (internal use — permitted); the action also carries a server-drawn `png_base64` so Layer 0 and any page failure still show a static map. Lands in P3, colored by EB excess in P4. |
| 5 | Studio depth | **Site model (ב) core** — full Train→Validate→Deploy→Predict, **designed as in the methodology report** (⚖️ no exposure offset; its 11-feature preset). **Severity model (ג) stretch**; if cut, ג ships as a descriptive SQL profile. |
| 6 | Insight ledger | ⚖️ **Mandatory, end of P4** (it is beat 3's closer and fallback): every action appends one JSONL entry; `finding_card` renders one entry as a markdown card with caveats + CBS credit. No editing UI. |
| 7 | Process | `[Pn]` commit prefixes, tag `v0.n` per accepted phase; synthetic-fixture unit tests + live-DB smoke test (skips when the copy is absent); `PITFALLS.md` + `docs/plan.md` living plan. |
| 8 | Tier 1 | **Out.** ⚖️ The planned "widen scope to a dark table" experiment is **dropped** — it would be a no-op (see §1: chat already sees every table). |

**License clarification (user, 2026-08-28):** showing CBS data at **any level** — row-level
included — is fine: this is internal use and **the seminar counts as internal**. No aggregate-only
guard, no small-cell suppression, no seminar-approval question. What stays: the DB is never
transferred (the demo runs on the user's own laptop), never in git/cloud (so nothing row-level
is committed — screenshots in the repo are chart/ranking frames); CBS credit on every rendered output.

Standing asks to Efraim (blockers for the seminar, not for the build): seminar date ·
the "15 steps" DoD list · whether "one plugin" is acceptable.

## 1. Verified extension-point facts the design rests on

Source: `nl2sql_engine` 1.6.0 (API 1.0) as installed in the Rebuild venv — the only version the
clone's `nl2sql-core>=1.0,<2.0` pin resolves to on this machine; app `api/main.py`,
`api/adapters.py`, `web-modules/app.js`, `launcher.js`; precedents `nl2sql-eda` / `nl2sql-shapes`.
Verified 2026-08-28, re-verified by the sweep.

- `Result(kind, data, title, note)` — `note` exists on **every** kind but only `Result.table()`
  exposes it; use the positional constructor (Shapes precedent). Kinds: table | markdown | sql |
  chart | error. **An action returns exactly one Result** (see §3 composition rule).
- Chart = `Result("chart", spec, title, note)`, `spec` any dict; the generic Modules page draws
  `spec.png_base64` + prints `spec.basis`; only when there is **no** png does it print `spec.rows`.
- Generic Modules page renders `note` (escaped plain text) under every kind; its markdown renderer
  supports only headings, bullets, paragraphs, inline code/bold/italic — no tables, links, images.
- `Input` kinds: table | column | text | number | bool | choice — **no range, no date**. Ranges
  are two `number` inputs; dates are `text` (ISO, validated in the action); choice values arrive
  as strings; every input needs a non-`None` default (empty strings are dropped by the page).
- `ctx.query(sql) -> (columns, rows)` is gated only by `guardrails.check_sql_is_safe` (single
  SELECT/WITH, no file functions) — never by scope.json.
- **Scope, corrected:** the live `israel_accidents.scope.json` has `"tables": []`, which the engine
  treats as *describe everything* — chat's prompt already lists **all 43 objects** (column lists
  narrow only the six tables that carry them). The old "chat sees 6" claim (dossier §3, kickoff)
  was a wrong inference from "has a column list". The plugin's differentiator is not visibility
  but **rules**: the exposure/weather/traffic layers reach chat with no join keys, series filter,
  denominators or caveats.
- `ctx.data_dir()` → `%LOCALAPPDATA%\nl2sql-core` (or `NL2SQL_CORE_DATA_DIR`, read only until
  the first resolve in a process); proven to survive core upgrades (`proof\upgrade_loop.ps1`).
- `Context(db_path=...)` is all a module gets — no connection name. The plugin detects "is this
  the accidents DB?" itself (probe `accidents.case_type_code`) and refuses readably otherwise.
- Page = entry point in `nl2sql.pages` **named `accidents`** (the name, lower-cased, is the URL
  segment) returning `{"path": <webdist>, "label": "🚦 תאונות"}`; mounted at import → **restart
  after install**; page calls `POST /api/modules/run {module, action, db, inputs}`; `?db=` is
  appended by `launcher.js` from the main app's Connection select **at click time** (stale tabs
  keep their old db). Vite `base` must equal `/page/accidents/`.
- Install = `pip install` into `app\.venv` (no plugins dir); no engine pin — `requires_core` is
  the contract. Host provides numpy, matplotlib (DejaVu Sans covers Hebrew — glyphs are not the
  problem, **ordering** is) and `python-bidi` (via `nl2sql-core[export]`); import lazily.
  The app venv ships neither `pytest` nor `build` — install them once for dev.
- Chat replay/record: `NL2SQL_REPLAY=1` + `app\cassettes\` (gitignored runtime state); the app has
  no record switch; **both replay and record exist only in the no-API-key branch** (with
  `ANTHROPIC_API_KEY` set the app calls the model live while `/health` still says `replay: true`);
  cassette key = sha256(model + full prompt), so schema/semantic/examples/history must be
  byte-identical between recording and replay. Chat has **no method switch** — it runs the deployed
  method from the Test Suite.
- xgboost ships a `py3-none-win_amd64` wheel (requires-python ≥ 3.12); numpy/scipy have cp314
  wheels — Spike C is a runtime smoke test, not an availability check.

## 2. The value thesis in one line

Chat sees a raw 43-object schema with no rules for the exposure, weather and traffic layers; the
plugin bakes the rules in. Every action carries the right series filter, join key, denominator and
caveat — *correct by construction* — and refuses, readably, what the data cannot answer. Master
frame (dossier §8): **expected_harm = Exposure × P(accident | exposure) × E(severity | accident).**

## 3. The answer envelope (every action, every render surface)

**Composition rule.** An action returns ONE Result. Every chart Result's spec carries the *full*
answer: `{type, png_base64, basis, rows, columns, sql, denominator, caveats, credit, …}`. Layer 1
draws png + table + collapsible SQL from that one call. Because Layer 0 shows only the png for a
chart, every multi-faced action takes a `view` choice input (`chart | table | sql`, per-action
default) that selects which single kind is returned: `chart` → the spec above; `table` →
`Result.table(rows, columns, title, note)`; `sql` → `Result.sql`. The page always calls with the
default view and reads the other faces from the spec.

| Element | Where it lives | Layer 0 (Modules page) | Layer 1 (🚦 page) |
|---|---|---|---|
| Denominator badge | `spec.denominator` · first line of markdown | inside `note` | badge (green = real exposure, amber = counts only, red = none) |
| Caveat ribbon | `spec.caveats: [str]` · markdown bullets | inside `note` | ribbon under the title |
| Show-SQL | `spec.sql` (the exact statement run) | `view=sql` | collapsible |
| CBS credit | drawn into every PNG footer · `spec.credit` · last markdown line | png footer + `note` | footer |
| Refusal card | `Result.markdown` with `## ❌ לא ניתן לענות` + reason + what *is* answerable | plain markdown | styled card |
| Uncertainty | CI/interval columns and bands in every rate or model output | table columns | table + band |

`note` (Layer-0 carrier) is one line: `מכנה: … · הסתייגות: … · מקור: הלשכה המרכזית לסטטיסטיקה`.
Credit constant: `מקור הנתונים: הלשכה המרכזית לסטטיסטיקה (למ״ס); עיבוד: מעבדת הבטיחות בדרכים`.
Hebrew text in PNGs goes through `bidi.algorithm.get_display(s, base_dir="R")` (host-provided;
`[::-1]` fallback) before drawing.

**Display level:** internal use — outputs may be row-level where useful (accidents behind a
hotspot, a site's accident list in beat 3). No suppression helper. License terms that remain in
code: credit on every output; nothing from `C:\data` referenced by, copied into, or written under the repo.

## 4. Action catalog (module id `accidents`)

Legend: **Tier** base | ml · **Layer** 0 = Modules page, 1 = 🚦 page tab · **Phase** per `PLAN_3`.
Conventions for every SQL below: `case_type_code = 1` for casualty measures; joins on
`(accident_id, case_type_code)`; accidents counted as `count(DISTINCT (accident_id, case_type_code))`;
sentinels 0/99 kept in totals, excluded from rankings; year ranges as `from_year`/`to_year` numbers.

**Site key syntax** (shared by `before_after`, `hotspot_map`, `site_ranking`):
`road:<n>/<km_from>-<km_to>` (km, decimal) · `njunction:<code>` → `nonurban_junction_code = code`
(nonurban accidents carry `city_code = 0`) · `ujunction:<city_code>/<code>` → `city_code = … AND
urban_junction_code = …`.

**P2 corrections (2026-08-29, live probe; sweep 2026-08-30):** as-of coverage with the units CTE is **70.4 %**
(19,865 of 28,213; 54 % → 81 %, non-monotonic, dip 72 % in 2023; 71.5 % before `road_km = 0` was treated as
"not coded" on the assignment side too) — the "~75 %, 55 → 89 %" below is the raw view's number; raw rows overstate
vehicle-km **0 % in 2017 → 77 % in 2024** (38.5 % overall); after the units CTE, dropping QUALIFY is +0.4 % and
BETWEEN +18.5 % (the "~25 %" belongs to the raw table); `traffic_adt_asof` is **2017–2024 only**, so `before_after`
locates sites by a literal km range; make/model **does** exist in the registry tables — only the key to the
accident files is missing; damage-only junction coding 5.6 % urban / 23.3 % non-urban (the plugin's
`site_coding_exprs`, 2005–2024, non-stationary) with a data-driven control flag;
`cc_band 0` = unknown engine (EV cohort), kept and labelled; `severity_profile` gains `sex` and keys pedestrians on
`casualty_type_code = 1` (489 carry a vehicle code); `before_after` takes `change_year`/`min_cell` (no `control`
input), `vehicle_cells_ranking` takes `bands` (no minimum exposure), `weather_check`'s threshold is a choice.
The rows below are the original design; `docs/p2_design.md` is the implemented one.

**P3 corrections (2026-08-30, built):** `hotspot_map` takes `road` (0 = all) so the demo hand-off from
`segment_rates(road=…)` lands on the same road; the segment geometry is a **Point at the mean of the unit's geocoded
accidents** (the LineString variant was not built); units are the as-of per-year vintage for 2017+ **and each key's
latest `traffic_segments` vintage as static geometry before 2017**, so a 2017+ range gives exactly `segment_rates`'
counts; the `site_key` (`road:<n>/<km_from>-<km_to>`) comes from the latest vintage and may differ from the years'
vintages (said in a caveat); "geocoded" means inside the Israel bbox (a 0/0 point is not a location); junction names
via `min()` and segment names via `arg_max(name, src_year)` (not `any_value`); `top_n` 30 (1–200); the `points` layer
is capped 300 per unit / 3,000 total in SQL; a range with rows but no placeable unit (2005–2007) is a refusal, never a
blank map; `color_by=excess` falls back to observed with a leading caveat until a site model is deployed (P4 reads
`color_by_effective`). The page: `?tab=` and `?run=<action>` deep links; the `view` input is never shown (the page
always asks for the chart spec); סטודיו / ממצאים are empty states.

**P4 corrections (2026-09-01, built):** default `train_until = 2023` (holdout 2024) — the §4.2 default of 2022 is
genuinely rejected by the gate on live (calibration 1.35: the 2023–24 casualty decline; the artifact is kept in the
seeded registry as the real governance-beat rejection, alongside the shuffled straw man at Spearman 0.201); the panel
is the FULL 1,311 × 8 grid (10,488 rows — the "4,695 / 3,405" split quoted earlier was raw as-of rows); `pct_curve`
counts only rows with a specific `road_shape_code` (code 9 "אחר" climbed ~5 % in 2005–2007 to 24 % by 2010 and
jumped to 47 % in 2011 — a coding discontinuity); the static attributes'
five coding columns are casualty-coded in practice (the damage-only series carries ~0 % of them — the card says so);
xgboost params are depth-2; `site_ranking` drops the `severity` input (KSI is a column) and gains `road`; excess-mode
observed comes from the panel's assignment (a caveat carries the difference vs `segment_rates`); the ledger logs
answers AND refusals (never errors), with `about`/`ledger_list`/`finding_card` exempt; `studio_train_site` /
`studio_validate` are the only multi-faced studio actions (deploy/models/ledger/finding are single-faced); the
demo-site criterion is re-worded — 60/836's excess is −2.0 (rank 8 of 21 on road 60): the treated site sits BELOW
its model expectation, and that inversion is the demo's point.

**Segment unit** (shared by `segment_rates`, `hotspot_map`, the site model): the traffic **count
segment** `(road, seg)` — a deliberate departure from the report's fixed 5-km unit (recorded in
`docs/plan.md`; lengths: median 3.6 km, p10 1.0, p90 11.7, max 120). One geometry vintage per
segment-year: `units AS (SELECT road, seg, year, km_from, km_to, adt_asof, based_on_year, gap_years
FROM traffic_adt_asof QUALIFY row_number() OVER (PARTITION BY road, seg, year ORDER BY gap_years,
km_to - km_from) = 1)` → 6,233 segment-years from 8,100 raw rows (1,511 keys carry overlapping-km
rows from different vintages; summing raw rows overstates vehicle-km ≈ 38 %). Accident→unit
assignment uses the view's exact predicate: `a.road1_number = u.road AND a.road_km/10.0 >= u.km_from
AND a.road_km/10.0 < u.km_to AND a.year = u.year QUALIFY row_number() OVER (PARTITION BY
a.accident_id, a.case_type_code ORDER BY u.gap_years, u.km_to - u.km_from) = 1` (half-open + one
row per accident; BETWEEN or no QUALIFY double-counts ~25 % of matched accidents).
`v_accident_adt_asof` itself exposes no road/seg/km and is not read.

### 4.1 Analytical tier (base install)

| Action | Use | Inputs | Method / correct-by-construction core | Denominator | Caveats baked in | Views | Phase |
|---|---|---|---|---|---|---|---|
| `trend` | א | `measure` (accidents / killed / severe_injured / slight_injured / fatal_accidents) · `granularity` (year / month) · `road_type` (all / urban / nonurban) · `from_year` · `to_year` · `view` | accidents or `v_casualty_involved` grouped by year(/month); `people_killed = count(*) FILTER (injury_severity_code=1)`; fatal accidents = `severity_code=1` on accidents | **none — counts** (amber) | data ends 2024-12-31; killed ≠ fatal accidents; 2020–21 COVID dip; counts ≠ risk | chart / table / sql | P1 |
| `naive_vs_correct` | §5.2 trap | `year` · `view` | runs BOTH statements deliberately: naive `severity_label='קלה' AND year=?` vs correct with `case_type_code=1`; the two numbers, the ratio, and why | n/a | damage-only `severity_code=3` means "no casualties" | markdown / sql | P1 |
| `about` | — | — | connection probe (is this the accidents DB?), row counts, data end date, license text, deployed-model status (reads the registry from P4 on) | n/a | — | markdown | P1 |
| `segment_rates` | ב (descriptive) | `road` (0 = all) · `from_year` · `to_year` (2017–2024) · `severity` (all / KSI) · `top_n` · `view` | casualty accidents per **100 M vehicle-km** per segment-year using the shared `units` CTE for BOTH sides: numerator = accidents assigned by the exact predicate above; denominator = `Σ adt_asof × (km_to − km_from) × 365` over `units`; exact-style Poisson CI by the Byar approximation (no scipy); live coverage = matched / all interurban casualty accidents per requested year, emitted in `spec.denominator` | **real: vehicle-km** (green) | interurban 2017+ only; ADT ≠ AADT (12–22 % APE); as-of used, never `traffic_adt_filled`; as-of covers ~75 % of interurban casualty accidents 2017–24 (55 % in 2017 → 89 % in 2024; the 92 % in semantic.json is the filled layer) and only a subset of segments per year (N / 1,311, printed); unmatched accidents excluded from both sides | chart / table / sql | P2 |
| `severity_profile` | ג (descriptive) | `by` (casualty_type / road_type / day_night / age_group / weather / involved_vehicle_type) · `from_year` · `to_year` · `view` | `v_casualty_involved i` with `injury_severity_code IN (1,2,3)`; `JOIN accidents a USING (accident_id, case_type_code)` for road_type / day_night / weather_label; age = `age_group_code` (5-year bands 1–18, 99 unknown; plugin-side label map — `age_group_label` is NULL on ~46 k rows and Excel-mangled for codes 2–3); vehicle = `involved_vehicle_type_code` (no join; pedestrians → "no vehicle"); shares via `sum(count(*)) OVER ()`; pedestrians = `casualty_type_code=1` | casualties (amber) | conditional on being a casualty; shares are relative; labels for age/vehicle come from codes | chart / table / sql | P2 |
| `vehicle_cells_ranking` | ד | `min_exposure_mkm` (default 50) · `metric` (involvements / ksi / fatal) · `view` | `vehicle_cells` (81 cells, manufacture years 2016–2026; 13 have `exposure_mkm = 0` → excluded, count reported): `global_rate = Σ metric / Σ exposure_mkm` over included cells; `EB_rate = (metric + M·global_rate)/(exposure_mkm + M)`, M = 200; **three tiers** by EB: safest 20 % / regular / highest-risk 20 % | **real: Mkm** (green) | national only; private cars, manufacture 2016+; cells, not models — no make/model exists in CBS data | chart / table / sql | P2 |
| `before_after` | ה | `site` (key syntax above) · `change_date` (text, ISO) · `window_years` (default 3) · `control` (national / same_road_class — the latter a plugin extension) · `view` | Double-DiD: `DiD(casualty) ÷ DiD(damage-only)`, each `DiD = (site_after/site_before) ÷ (control_after/control_before)`; control = whole network by default (the report's definition); `CI = exp(ln ratio ± 1.96·SE)`, `SE² = Σ over the 8 counts of 1/(count+½)`; casualty series `case_type_code=1`, control series **damage-only accidents `case_type_code=3`** (complete 2005–2024 — `damage_code` is an unrelated 2013+ `vehicles` column, never used) | damage-only series as exposure proxy (green-amber) | window must fit the series (`change_date ± window_years` within 2005–2024 → 3+3 ⇒ change year 2008–2021, validated with a readable error); thin cells: < 6 records on any of the 8 counts → result "n/a — ריק עדיף על מספר מזויף" (plugin thinness rule, adapted from the report's change-detector threshold — not a dossier fact); damage-only control located for ~88 % of interurban segment records but ~23 % at junctions → "control n/a" rather than a ratio; change year ±1–2 y uncertainty; association ≠ causation | chart (2×2) / table / sql | P2 |
| `weather_check` | dark-layer light-up | `from_year` · `to_year` · `rain_threshold_mm` (default 0.1) · `view` | `v_accidents_weather` where `case_type_code = 1 AND precipitation_mm IS NOT NULL`, grouped by `cbs_weather_label`: `accidents = count(*)`, `pct_measured_rain = 100.0 * count(*) FILTER (precipitation_mm > threshold) / count(*)`, `median_temp_c = median(temperature_c)` — with 0.1 this reproduces `weather_agreement` exactly (גשום 8,256 / 56.8 % / 12.7 °C; בהיר 183,482 / 3.7 % / 22.2 °C); `> 0` gives 67 % | share of accidents | ERA5 = 25 km reanalysis; threshold printed; 2005–2007 carry no weather cell, from 2008 < 1 % missing (computed live for the selected years) | chart / table / sql | P2 |
| `triage` | refusal gate | `question` (text) | rule table (no LLM): make/model → unanswerable (§5.5) → redirect `vehicle_cells_ranking`; per-km urban / junction entry rate → no denominator → redirect relative ranking; dates > 2024 → no data; residence → not location; else → matching actions | n/a | — | markdown | P2 |
| `hotspot_map` | ז (presentation of ב) | `unit` (segments / njunctions / ujunctions) · `from_year` (default 2008) · `to_year` · `color_by` (observed / excess) · `top_n` · `points` (bool: include individual accidents) · `view` | **aggregate first, join geometry after.** Segments: counts per `units` key; geometry derived from the unit's geocoded casualty accidents (no traffic table carries coordinates): a LineString of accident points ordered by `road_km`, or a Point at the mean lat/lon with the km range in the popup (P3 default); segments with no geocoded accident listed in `rows`, omitted from `geojson` with a count. Junctions: counts per `nonurban_junction_code` / `(city_code, urban_junction_code)`, then join `dim_junction_urban` (1:1 on `(junction_code, city_code)`) or the **deduped** `dim_nu AS (SELECT junction_code, any_value(junction_name) junction_name, avg(latitude) latitude, avg(longitude) longitude FROM dim_junction_nonurban GROUP BY junction_code)` (4,202 rows / 2,525 codes — a plain join doubles counts); NULL-coordinate junctions fall back to the mean of their own accidents' coordinates. `excess` only for segments and only with a deployed site model (P4), else observed with an amber badge | per `color_by` | 2005–2007 have no coordinates (floor 2008 is a data limit; < 1 % missing after); counts ≠ danger unless `excess`; junctions are ranked by counts only | chart (`spec = {type:"accidents/map", geojson, png_base64, rows, …}`) / table / sql | P3 |
| `two_wheelers` (stretch) | ח | `metric` · `from_year` (≥ 2013) · `to_year` · `view` | `v_motorcycle_accident_rate` per registered fleet by cc band; bicycles/e-scooters counts only | fleet (amber-green) | no VKT denominator; solo falls under-reported — "floor of the truth" | chart / table / sql | P5 |

### 4.2 Studio tier (`pip install "nl2sql-accidents[ml]"`)

Registry root: `ctx.data_dir()/accidents/models/<family>/<model_id>/` with `model.ubj`, `meta.json`
(feature contract incl. the SQL recipe and frozen static attributes, training window, ADT median
used, per-year `adt_known` share, metrics, α, gate verdict with the plugin-chosen thresholds
labelled as such, status ∈ candidate | validated | rejected | deployed, created_at, plugin version)
and a family-level `deployed.json` pointer. Nothing under the repo.

| Action | Use | Inputs | Method | Gate / rule | Views | Phase |
|---|---|---|---|---|---|---|
| `studio_train_site` | ב | `train_until` (default 2022) · `features` (preset `doc-11`) · `seed` | ⚖️ **as in the methodology report:** panel = full 1,311-segment × 2017–`train_until` grid of segment-years (zero years included); y = casualty accidents; **no offset**; features `doc-11`: `adt_asof` (national-median fill where no as-of row; never `traffic_adt_filled`), `adt_known` (1 = as-of measured), `lag1` (unit's casualty accidents in year−1; 2016 feeds 2017), `pct_night`, `pct_single_carr`, `pct_at_junction`, `pct_curve` (`road_shape_code` ≠ straight), `pct_wet_surface`, `speed_mix` (mean `speed_limit_code`), `years_active`, `year_idx`. **Static segment attributes are computed once from ALL accident records on the geometry (both series, 2005–`train_until`) and frozen in `meta.json`** — no feature is a function of the target window's casualty rows. XGBoost `count:poisson`, early stopping on a temporal inner fold | golden rule 2: contract in `meta.json` | markdown + table | P4 |
| `studio_validate` | ב | `model_id` | holdout = years after `train_until` (2023–2024, 3,405 segment-years vs 4,695 train): Spearman(observed, μ) hand-rolled; calibration `Σμ/Σobs ∈ [0.75, 1.25]`; overfit = **mean per-row** Poisson deviance (holdout) / (train) ≤ 1.5 (plugin operationalisation of the report's unspecified "גבול התאמת־יתר"; mean, not sum, because the panel grows yearly); NB dispersion `α = max(0, (Σ(y−μ)²/μ − n) / Σμ)` from holdout residuals, stored | Spearman ≥ 0.3 and calibration ±25 % (from the report) and overfit ≤ 1.5 (plugin) → `validated`, else `rejected` with reasons | markdown gate card + table + chart (calibration png) | P4 |
| `studio_deploy` | ב | `model_id` | writes `deployed.json`; **refuses non-validated / rejected ids, re-listing the reasons** (this refusal is the governance beat) | golden rule 1 | markdown | P4 |
| `site_ranking` | ב flagship | `from_year` · `to_year` · `severity` · `top_n` · `view` | reads the deployed artifact (no training), rebuilds features from the stored contract, μ per segment-year; columns: observed, μ, `excess = observed − μ`, `EB_estimate = w·μ + (1−w)·observed` with `w = 1/(1+α·μ)`, `lo90`/`hi90` from NB(μ, α) (normal approximation with Var = μ + α·μ², collapsing to Poisson when α ≈ 0 — said in the caveat), `significant = observed > hi90`; ranks by excess | refuses with no deployed model → refusal card pointing to סטודיו | chart / table / sql; feeds `hotspot_map color_by=excess` | P4 |
| `studio_models` | — | `family` | lists registry entries with status/metrics/α | — | table | P4 |
| `studio_explain` (stretch) | ז | `model_id` · `site` | `pred_contribs=True` TreeSHAP; per-unit profile = top-5 features by mean|φ| drawn as **lines per year** next to observed-vs-predicted (the report's rendering); global mean|φ| bars | exact-sum identity tested on the log-rate scale; caveats: log-rate scale, association ≠ causation, correlated features read as a group | chart + table | P5 |
| `studio_train_severity` / `studio_validate_severity` / `severity_predict` (stretch) | ג | `train_until` · … | person-level `v_casualty_involved` 2010–2024 with urban flag, XGBoost `multi:softprob`, class weights `1/share(c)` (the report's rule; no SMOTE) | **plugin gate** set below the report's achieved values (recall 0.6 / AUC 0.85): fatal recall ≥ 0.5, AUC(fatal) ≥ 0.8, no overfit; relative probabilities only | markdown + chart | P5 |
| `what_if` (stretch) | ו | scenario fields | severity model over a scenario grid; relative deltas only | needs a deployed severity model | table + chart | P5 |

### 4.3 Ledger (⚖️ mandatory, end of P4)

| Action | Inputs | Method | Result | Phase |
|---|---|---|---|---|
| (implicit) `ledger.append` | — | every action appends `{ts, action, inputs, headline, numbers, caveats, plugin_version}` to `ctx.data_dir()/accidents/ledger.jsonl` (no png) | — | P4 |
| `finding_card` | `entry` (index or latest) · `claim` (text) | claim + evidence (the numbers) + caveats + rerun recipe (action + inputs) + CBS credit | markdown | P4 |
| `ledger_list` | `last_n` | tail of the ledger | table | P4 |

## 5. Uses × methods × outputs × dependencies × surface (the map)

```
USE (dossier §8)        METHOD (correct-by-construction)               OUTPUT (one Result; view)   DEPS         SURFACE
א trend monitoring  ──► case filter + killed≠fatal + data-end     ──► png line / table / sql   host mpl+bidi tab מגמות / L0
   └ the trap       ──► both statements, ratio, explanation      ──► markdown / sql           —             tab מגמות / L0
ב site risk         ──► units CTE, half-open+QUALIFY, Byar CI     ──► png bar / table / sql    host mpl      tab נקודות תורפה
   └ EB screening   ──► deployed Poisson-XGB (doc-11) → excess    ──► table / png / map        xgboost[ml]   tab נקודות תורפה + סטודיו
ג severity          ──► conditional shares, codes, joins stated   ──► png stack / table / sql  host mpl      tab חומרה
   └ model (stretch)──► softprob + 1/share weights + plugin gate  ──► gate card / png          xgboost[ml]   סטודיו
ד vehicle groups    ──► cells EB, M=200, 3 tiers, exposure>0      ──► png / table / sql        —             tab חומרה (refusal redirect)
ה before/after      ──► Double-DiD vs network, 8-count SE, n/a    ──► png 2×2 / table / sql    —             tab לפני/אחרי
ו what-if (stretch) ──► severity model scenario grid              ──► table / png              xgboost[ml]   סטודיו
ז map / SHAP        ──► Leaflet circleMarkers + GeoJSON, png twin ──► chart{geojson,png}       leaflet(js)   tab נקודות תורפה
                    ──► pred_contribs lines per year (stretch)    ──► png                      xgboost[ml]   סטודיו
ח two-wheelers      ──► rate per fleet, cc bands 2013+            ──► png / table / sql        —             tab חומרה
refusals            ──► triage rule table                         ──► refusal card             —             every tab
ledger              ──► jsonl append + finding_card               ──► markdown card            —             tab ממצאים
```

## 6. GUI

**Layer 0** — free: every action is a form + result on the generic 🧩 Modules page; the envelope
survives via `note`, png footer, markdown text, and the `view` input.

**Layer 1** — `🚦 תאונות` page (React + Vite, `base: "/page/accidents/"`, built into
`nl2sql_accidents/webdist/` — **committed to git**, precedent — shipped in the wheel). RTL-first:
`<html dir="rtl" lang="he">`, logical CSS properties, `dir="ltr"` islands for numbers/SQL. New
ground (no RTL precedent in any plugin page; both precedents use echarts, not Leaflet) — spiked in
P0 (Spike E) and recorded in `PITFALLS.md`.

Tabs: **מגמות** (trend, naive_vs_correct) · **נקודות תורפה** (segment_rates, site_ranking,
hotspot_map — Leaflet) · **חומרה** (severity_profile, vehicle_cells_ranking, weather_check,
two_wheelers) · **לפני/אחרי** (before_after) · **סטודיו** (train/validate/deploy/models/explain;
`[ml]` missing → install card) · **ממצאים** (ledger_list, finding_card).
Header: `about` status strip (connection ok · data ends 2024 · deployed model: yes/no — wired to
the registry in P4 · license). Empty states in tabs that need a model point to סטודיו and flip when
a deployment exists (P4). A `triage` box at the top of every tab.

Map (Leaflet, no tiles): boundary = bundled Israel GeoJSON (Natural Earth, public domain,
simplified, ~100 KB — built: 1:10m at 0.0015°, 355 vertices, 7.3 KB) imported as a JSON module (inlined by Vite — no runtime fetch); data =
`spec.geojson`; **all markers are `L.circleMarker`** (no image assets — Leaflet's default icon
breaks under hashed asset paths); `leaflet/dist/leaflet.css` imported from node_modules so Vite
inlines its images as `data:` URIs (built: no image files are emitted); popups show counts + caveat + the hand-off + (with `points`) the accident list;
footer credit. Fallback: `spec.png_base64` when Leaflet fails or on Layer 0.

## 7. Dependencies

| Tier | Python | JS (build-time only) | Data files in wheel |
|---|---|---|---|
| base | none installed. Borrowed from the host: numpy, matplotlib (DejaVu Sans covers Hebrew — verified; no font bundled), `python-bidi` (guaranteed by the clone's `nl2sql-core[export]`; lazy import with `[::-1]` fallback), duckdb via the core | react, vite, leaflet | Israel boundary GeoJSON |
| `[ml]` | `xgboost` (py3-none win wheel, needs Python ≥ 3.12; + `scipy` only if hand-rolled stats prove not worth it) | — | — |
| dev | pytest, build, duckdb (fixture) — installed once into `app\.venv` | node ≥ 20 | — |

`requires-python = ">=3.11"` (matches the app; `[ml]` documented as 3.12+). Spike C (P0) is a
runtime check (import, `count:poisson`, `pred_contribs` sums to prediction); numpy-IRLS Poisson
remains the fallback only if that fails.

## 8. Test strategy (decision 7)

- `tests/conftest.py`: synthetic DuckDB mirroring the real schema for the tables/views the actions
  touch (accidents, involved, vehicles, v_casualty_*, traffic_segments, traffic_adt_asof incl. an
  overlapping-vintage key, vehicle_cells incl. a zero-exposure cell, dim_junction_* incl. a
  duplicated nonurban code, weather view), planted with known answers (a 5,458-vs-50,145-style
  trap, a known EB ordering, a known DiD ratio, a known rate). Synthetic because the suite must
  run without the CBS file and the repo carries no data. `nl2sql_engine.configure(data_dir=tmp_path)`
  per test and `configure(data_dir=None)` on teardown (the env var is read only until the first
  resolve; the data-dir-move test runs as a subprocess or is left to `proof\upgrade_loop.ps1`).
- Actions run through the real `Registry` (Shapes precedent); PNG magic + size checks; JSON-safety
  (`allow_nan=False`); contract test: every input has a non-None default, every kind legal, every
  `view` value returns the declared kind, every output carries denominator/caveat/credit; a test
  asserts the `nl2sql.pages` entry-point name equals the Vite base segment.
- `tests/test_live.py`: skipped unless `C:\data\israel_accidents\israel_accidents.duckdb` exists;
  opens read-only; asserts 439 killed / 5,458 slight / 8,315 casualty accidents 2024; `weather_check`
  reproduces 56.8 % / 3.7 %; `units` CTE yields 6,233 segment-years; every output carries the credit.
- Studio: planted panel where one model passes and a shuffled-target model is rejected; deploy
  refuses a rejected id; `site_ranking` refuses with no deployment; leakage test: static
  attributes unchanged when the target window's casualty rows are removed.
- Run from `nl2sql-accidents-plugin\`: `..\app\.venv\Scripts\python -m pytest -q`
  (one-time: `..\app\.venv\Scripts\python -m pip install pytest build`).
