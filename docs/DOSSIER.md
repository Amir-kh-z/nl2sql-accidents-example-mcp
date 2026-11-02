# DOSSIER — Israel Road Accidents Database (Task 4)

**Surveyed 2026-08-26** from the pristine CBS delivery folder (read-only).
Sources: `קרא-אותי.md` (install README), `docs/db-tables-report.html` (inventory + variable
dictionary), `docs/methodology-report.html` (analysis methodology, ~14 sections),
`semantic_layer.yaml` + `israel_accidents.semantic.json` (NL2SQL semantic layer),
`israel_accidents.scope.json`, and a live read-only survey of `israel_accidents.duckdb`
(duckdb 1.5.0). Facts verified live are marked ✅.

This document is the permanent knowledge base for the Task-4 dedicated plugin. It will
move into the plugin repo when that repo exists.

---

## 1. Identity & provenance

- **What:** Israeli road-accidents analytical database, built from **266 licensed CBS
  (למ״ס) microdata files** — two series unified: **ת״ד 104** (accidents with casualties)
  and **ת״ד 116** (damage-only), 20 years × 3 files each, mixed encodings (UTF-8/cp1255).
- **Coverage:** 2005–2024 ✅. Data ends 2024-12-31; published in arrears — questions about
  later dates have NO data (answer explicitly, don't return empty).
- **File:** `israel_accidents.duckdb`, 437 MB on disk ✅ (inventory report quotes ~1.6 GB —
  the shipped file was rebuilt **without PK indexes** to shrink it; analytically harmless).
- **Contents:** **31 tables + 12 views** ✅. 1,290,788 accidents · 2,987,206 involved
  persons · 2,297,533 vehicles · 10.5M weather hours (ERA5) · 11.9M traffic-count records.
- **Source families:** CBS licensed files; data.gov.il open data (vehicle registry, fleet,
  odometer, WLTP, TAZ); ERA5 weather via Open-Meteo; Open Bus SIRI GPS (+ a recovered
  2.2 GB backup for Feb–Mar 2022).
- Companion docs were generated August 2026; `semantic_layer.yaml` generated 2026-08-08 by
  `build/18_semantic_layer.py`, with 14/14 example queries validated against the live DB.

## 2. ⚖️ License constraints (HARD RULES)

CBS microdata under the user's personal CBS approval:

1. **Never** transfer the database to anyone else.
2. **Never** upload it to any public service, shared cloud, or **git** — the plugin repo
   ships code and knowledge, never data. (This dossier contains only aggregate figures,
   which are fine to publish; the data itself never is.)
3. Rows are individual-level — **publications at aggregate level only**.
4. Every product/publication credits the CBS (הלשכה המרכזית לסטטיסטיקה).

Open-data layers (data.gov.il, ERA5, Open Bus) are freely usable with processing.

## 3. How it loads into the NL2SQL app

- Prereq: the closed-core app installed. Add connection: **Connections → file source →
  full path to `israel_accidents.duckdb`**.
- **Sidecar convention (critical):** `israel_accidents.{scope,semantic,learned_examples,
  chat_history}.json` must sit **in the same folder with the same basename** as the
  .duckdb — the app discovers them by name. Separating them silently drops the semantic
  layer.
- **Verification answers** (all reproduced live ✅):
  - "כמה הרוגים היו בשנת 2024?" → **439**
    (`involved WHERE case_type_code=1 AND year=2024 AND injury_severity_code=1`)
  - "כמה תאונות קלות היו ב-2024?" → **5,458**. If you get ~50,145 the semantic layer
    didn't load (see §5.2).
  - Schema browser shows 31 tables + 12 views.
- Troubleshooting (from README): "could not open it" = file locked by another app
  instance; "Invalid unicode" schema error = `scope.json` missing/renamed; inflated
  counts = `semantic.json` not loaded.
- **Scope**: `scope.json` exposes only **6 objects** to the NL2SQL chat: `accidents`,
  `involved`, `vehicles`, `v_casualty_accidents`, `v_casualty_involved`,
  `fleet_motorcycles` (with explicit column lists; `tables: []`). The other ~37 objects —
  all the weather, traffic, exposure, bus-speed, and aggregate layers — are **invisible
  to plain chat**. This is the plugin's opportunity surface.
- `learned_examples.json` currently holds 1 trivial example; `chat_history.json` shows the
  app already answered the fatalities question correctly via the semantic layer.
- **CORRECTION 2026-08-28 (verified against `nl2sql_engine/scope.py` + `schema.py`, core 1.6.0,
  and a live `get_schema_text` run):** the "exposes only 6 objects" reading above is wrong.
  `"tables": []` means *describe everything* — chat's prompt lists **all 43 objects**; the column
  lists narrow only the six tables that carry them (`scoped_tables` returns `None` when `tables`
  is empty; `out_of_scope_tables` is `[]`). The other ~37 objects are described **raw, with no
  semantic rules** (no join keys, series filter, denominators or caveats) — that, not visibility,
  is the plugin's opportunity surface. §9 and §10.1 read accordingly.

## 4. Inventory (live row counts ✅)

### 4.1 CBS core (licensed) — the three grains

| Table | Rows | Grain / key |
|---|---|---|
| `accidents` | 1,290,788 | one accident; **PK (accident_id, case_type_code)** — 96 cols |
| `vehicles` | 2,297,533 | one vehicle in an accident; key (+ vehicle_num) — 22 cols |
| `involved` | 2,987,206 | one involved person; key (+ person_id); `vehicle_num` links to their vehicle — 40 cols |

Column pattern: every categorical is `*_code:SMALLINT` + `*_label:VARCHAR` (labels
pre-joined per-year from the official dictionary). Typical ratios: 1 casualty accident
≈ 1.8 vehicles ≈ 2.5 people.

### 4.2 Dictionaries / dimensions

`code_lookups` 15,828 (keyed **(code_table, code, year, field)** — meanings drift across
years; prefer the pre-joined `*_label` columns) · `dim_settlement` 1,310 ·
`dim_street` 24,737 (street_code unique only within city) · `dim_junction_urban` 14,592
(key junction_code + city_code; codes repeat across cities) · `dim_junction_nonurban`
4,202 · `dim_weather_code` 28 (WMO/ERA5) · `dim_count_vehicle_type` 87 ·
`label_drift` 112 (QA: codes whose label changed between years).

### 4.3 Weather (ERA5)

`weather_grid` 60 (0.25° cells containing accidents) · `weather_hourly` 10,519,200
(key cell_id + observed_at UTC; temp, precip, humidity, wind, WMO code) ·
`weather_agreement` 6 (QA: police weather label vs measured rain — e.g. גשום → 56.8%
measured rain, בהיר → 3.7%).

### 4.4 Traffic volumes & counts

`count_sites` 8,746 + `count_volumes` 11,868,551 (turning movements; one-week surveys,
NOT continuous) · `traffic_segments` 4,834 · `traffic_hourly` 1,436,568 (**columns are
transliterated Hebrew**: shana/kvish/keta/maslul/nefah = year/road/segment/lane/volume) ·
`traffic_adt` 4,834 · `traffic_adt_asof` 8,100 (time-honest "as known then"; deliberately
empty before 2017) · `traffic_adt_filled` 38,320 (back-filled; descriptive only —
**leakage-toxic** for temporal ML validation; `source` ∈ measured/interpolated/backcast/
forecast) · `traffic_year_index` 20 · `traffic_fill_validation` 6 (median APE: 12.4% at
1-year gap → 21.6% at 3).

### 4.5 Fleet, mileage & exposure

`fleet_by_model` 100,735 (registry: active/inactive by make × model × manufacture year) ·
`fleet_motorcycles` 10,858 (cc mapped to CBS bands 8/9/10/19 so it joins to accidents) ·
`vehicle_mileage` 1,680,679 (odometer annual-km; **2017+ registrations only**; annual_km
kept in [1,000, 60,000]; ownership private/company/leasing matters hugely) ·
`vehicle_cells` 81 (**the exposure cube**: manufacture_year × cc-band cells; fleet, mean
weight, EV share, mean annual km, exposure_mkm, involvements/KSI/fatal; built for EB
rates with prior M = 200 Mkm).

### 4.6 Bus GPS speeds (urban context)

`bus_speed_near_accident` 11,918 (urban casualty accidents 2022–24; ±330 m, ±30 min;
mean/median/p85 km/h, pct_stopped) · `bus_speed_windows` 11,920 (same split pre/post
impact; `truncated` flags 800-sample cap). Coverage ~90% of urban casualty accidents
2023–24, only 38% in the 2022 window.

### 4.7 Geographic aggregates (pre-aggregated CBS snapshots)

`accidents_by_taz` 2,637 · `accidents_by_municipality` 1,174. **Cumulative ~5.2-year
undated snapshots** (`snapshot_yearmonth` = publication date). NEVER join/compare/add
them with per-year figures from `accidents` — separate universe.

### 4.8 The 12 views (each encodes a correctness rule) ✅

| View | Rows | Rule it encodes |
|---|---|---|
| `v_casualty_accidents` | 270,723 | `SELECT * FROM accidents WHERE case_type_code = 1` |
| `v_casualty_involved` | 684,051 | same filter on `involved` |
| `v_accident_casualty_counts` | 1,290,788 | per-accident casualties/killed/severe/slight/people_involved without join fan-out (×2.2 inflation otherwise) |
| `v_accidents_weather` | 1,290,788 | correct grid-cell + hour-truncated join to `weather_hourly` |
| `v_accident_adt` | 251,661 | attach ADT (descriptive, filled); join: `road1_number=road AND road_km/10.0 BETWEEN km_from AND km_to AND year=year`, QUALIFY nearest |
| `v_accident_adt_asof` | 84,271 | same, time-honest (for ML) |
| `v_accident_rate_by_model_year` | 400 | involvement per 1000 active fleet by model-year (`is_latest_year` filter for rates) |
| `v_motorcycle_accident_rate` | 877 | motorcycle rate per registered fleet by cc band (2013+) |
| `v_fleet_all` | 148 / `v_fleet_by_year` 62 | fleet aggregates (incl. motorcycles as דו-גלגלי) |
| `v_mileage_by_model` | 6,519 / `v_mileage_by_ownership` 50 | mileage aggregates (median annual km) |

(The tables report says "10 views"; the DB actually has 12 — the four fleet/mileage
aggregates are the ones the report didn't enumerate.)

## 5. Golden semantic rules (get these wrong → confidently wrong answers)

### 5.1 Two series in one table

`case_type_code`: **1 = casualty accident (270,723) · 3 = damage-only (1,020,065)** ✅.
The damage-only series is ~3.8× larger. **Any question about injuries, casualties,
severity, fatalities REQUIRES `case_type_code = 1`** (it's the declared default_filter
on accidents/involved/vehicles; the two v_casualty_* views bake it in).

### 5.2 The light-accident trap ✅

Damage-only rows carry `severity_code = 3` where the label means **"no casualties," not
"slight."** Naive `severity_label='קלה' AND year=2024` → **50,145**; with
`case_type_code=1` → **5,458**. (2024 casualty accidents: 405 fatal, 2,452 severe,
5,458 slight = 8,315 total — that 8,315 is the "all casualty accidents" figure the
inventory report cites.)

### 5.3 Composite key everywhere

`accident_id` is NOT unique alone (41,935 cross-series collisions were resolved during
the build; 2005–2009 reuses IDs across series for different accidents). **Every join to
vehicles/involved is on (accident_id, case_type_code)**; accident counting after a join
is `count(DISTINCT (accident_id, case_type_code))`. accident_id encodes year
(e.g. 2023000009).

### 5.4 People vs accidents

- `involved` includes **uninjured** drivers (`injury_severity_code = 0`, ~1.13M rows) —
  `count(*)` on involved counts people present, not hurt.
- Person severity: `injury_severity_code` **1 = killed (incl. death ≤30 days via
  late_death_code) · 2 = severe · 3 = slight · 0 = uninjured** ✅.
- Accident `severity_code` = the accident's **worst** outcome. Fatal-accident count ≠
  people killed (2024: 405 fatal accidents, 439 killed).
- **2009 gap (found 2026-08-29 ✅):** the casualty-series `involved` rows for 2009
  (`case_type_code = 1`) are missing — **15 rows** (3 uninjured, 1 severe, 11 slight; killed
  2009 = 0) against 16,856 casualty accidents (every other year 20,981–51,093). The damage-only
  person rows 2009 (139,368), vehicles 2009 (both series) and accidents 2009 (16,856 casualty /
  308 fatal) are complete, so a plain `count(*) FROM involved WHERE year = 2009` (139,383)
  hides it. Person-level measures for 2009 are **missing, not zero**; the plugin derives
  coverage per period from the accident spine (`people >= casualty_accidents`, series filter +
  composite key) and shows the year as a gap (NULL, never 0).

### 5.5 Other traps

- **Pedestrians** = `casualty_type_code = 1` (never role_code; role 3 mixes pedestrians
  and passengers).
- **Sentinels**: 0 = N/A, 99/999 = unknown in most coded columns — include in totals,
  exclude from "top category" rankings. Junction codes carry a fourth sentinel: **`urban_junction_code =
  99999999`** ("unknown junction" — 556 casualty accidents across 82 cities, no `dim_junction_urban` row; found
  by the P3 sweep 2026-08-30). The plugin's `JUNCTION_SENTINEL_CODES = (0, 99, 9999, 99999999)`.
- **No plate/make/model in accident records** (deliberate CBS anonymization). Precision
  (2026-08-29): make/model **do** exist in the registry tables (`fleet_by_model`,
  `vehicle_mileage`, `fleet_motorcycles`); what is missing is the **key** — the accident
  files carry no plate, VIN or model code — so no join can ever connect them. "Is a
  Corolla safer than a Mazda 3" is **unanswerable** — say so. The honest resolution is
  manufacture_year × cc-band (`vehicle_cells`).
- **`road_km` is stored in 100-m units (×10)** ✅ — divide by 10.0 for km (4771 = km 477.1).
- `residence_*` columns = where the person lives, never accident location.
- `junction_control_code` NULL in 49% = structurally "not at a junction" — own category,
  never impute or drop.
- Coordinates: lat/lon NULL ~5% overall but ~60% of 2005–2009 (temporal bias if dropped;
  missing `weather_cell_id` ⇒ missing coords, 19% of casualty accidents). Filter
  `latitude IS NOT NULL` for maps.
- Mileage comparisons must hold manufacture_year AND ownership constant (leasing median
  25,010 km/yr vs private 15,440); safe default `ownership='פרטי'`, HAVING count ≥ 400.
  Use **median** annual km, not mean (right-skewed; national median 16,381).
- `involved_vehicle_type_label` is unreliably populated (code present, label NULL on many
  rows ✅) — group/filter by **code** for this field. Same for `age_group_label` (NULL on ~46 k
  casualty rows; codes 2–3 carry Excel-mangled month-name variants) — use `age_group_code`
  (5-year bands 1–18, 99 unknown) with a plugin-side label map. There is no `age_band` column.
  (added 2026-08-28)
- `day_of_week`: 1 = Sunday. `day_night`: 1 = day, 5 = night. Time precision is 15 min
  (96 bins; prefer derived `hour_of_day`).
- Era-scoped fields: `damage_code` 2013+ · motorcycle cc bands 2013+ · ISS score
  2005–2012 only · `travel_direction` codes era-scoped · mileage 2017+ · measured
  traffic 2017–2024.
- Officer `weather_code` is an observation, not a measurement (cross-check table:
  `weather_agreement`); ERA5 is 25-km reanalysis, not station gauges.
- `geocode_status_code` is undecoded (CBS ships an empty code table); `city_code = 0`
  for non-urban accidents.

## 6. Key enumerations

- `severity_code` (accidents): 1 קטלנית (6,589) · 2 קשה (38,316) · 3 קלה (1,245,883 —
  includes damage-only!) ✅. Labels stable 2005–2024.
- `injury_severity_code` (involved): 0 לא רלוונטי · 1 הרוג (7,052) · 2 פצוע קשה (42,542)
  · 3 פצוע קל (1,811,621) ✅.
- `role_code`: 1 נהג · 2 נהג נפגע (damage-only series) · 3 נפגע (passenger/pedestrian).
- `casualty_type_code`: 1 pedestrian · 2/3 four-wheel driver/passenger · 4/5 motorcycle ·
  6/7 bicycle · 8/9 unknown vehicle.
- `vehicle_type_code`: 1 private car · trucks by weight class · **8/9/10/19 motorcycles
  by cc band (≤50/51–125/126–400/401+)** · 15 bicycle · 21 e-bike/e-scooter codes
  (21–23: אופניים חשמליים / קורקינט ממונע / קורקינט חשמלי; docs vary — resolve via
  code_lookups when it matters).
- `road_type_code`: 1–2 urban (junction / not) · 3–4 non-urban · 5 off-road.
- `engine_volume_code`: CBS cc bands; **0 = electric/no engine**.
- Full maps for ~25 enums live in `semantic_layer.yaml` (`enums` section).

## 7. The semantic layer (what the app already knows)

- `semantic_layer.yaml` = human-readable contract: 10 critical rules, 17 tables + 10
  views described, 10 join specs, 9 metrics, ~25 enum maps, **14 validated example
  queries** (each with a "teaches" note), 7 named pitfalls.
- `israel_accidents.semantic.json` = machine flattening (term_glossary, column_notes,
  relationships, 32 rules, empty `cube`), **plus 7 `[auto:*]` rules absent from the
  YAML** (data-ends-2024, municipality-snapshot isolation, ADT join recipe + coverage
  ~92% interurban / 0% urban, ADT ≠ AADT with error bounds, junction-NULL semantics,
  weather-missingness bias, asof-vs-filled leakage rule).
- Canonical metrics: `people_killed` = `count(*) FILTER (injury_severity_code=1)` on
  involved (+case filter) · `accident_count` = `count(DISTINCT (accident_id,
  case_type_code))` · `fatal_accident_count` on accidents.severity_code = 1 ("NOT the
  number killed") · rates from the two rate views with `is_latest_year` · shares via
  window `sum(count(*)) OVER ()`.
- Named pitfalls: join fan-out; cumulative-rate (never divide 20y of accidents by today's
  fleet snapshot); damage-only trap; residence≠location; aggregate-layer isolation;
  mileage without controls; raw counts without denominators ("big cities top raw counts
  because they're big").
- Hebrew/English synonym maps for tables, metrics, and values (labels are Hebrew; safer
  to filter numeric codes for English questions).

## 8. The methodology layer (the analysis "uses" — the plugin's menu)

Master framework: **expected_harm = Exposure × P(accident|exposure) × E(severity|accident)**.
Counts without an exposure denominator are "a list of busy places, not dangerous places."

Eight uses (א–ח): **א** trend monitoring · **ב** site risk models (segments/junctions:
Poisson/NB SPF or XGBoost count:poisson; **Empirical-Bayes network screening ranked by
excess = observed − μ_model**, the flagship policy output; validation gate: Spearman
≥ 0.3, calibration ±25%, no overfit — non-validated models refuse to predict) · **ג**
conditional severity model (person-level, ~482K casualties, XGBoost multi:softprob,
class weights not SMOTE, fatal recall ~0.6, AUC fatal 0.85; probabilities read
relatively, never absolutely) · **ד** vehicle-group ranking (`vehicle_cells`, EB_rate =
(involvements + M·global_rate)/(exposure + M), M=200; tiers by EB quintiles) · **ה**
before/after evaluation (**Double-DiD**: DiD(casualty) ÷ DiD(damage-only) with
CI = exp(ln ratio ± 1.96·SE), SE² = Σ 1/(count+½); physical-change detection: 25%/75%
share flip, ≥6 records/side; breakpoint scan as discovery only) · **ו** environmental
risk via severity-model interactions · **ז** map hotspots + per-unit TreeSHAP profile
(prediction = base + Σφᵢ exactly; per-unit factor lines over 2005–2024) · **ח**
two-wheelers (rates per registered fleet — no VKT denominator exists; bicycles/scooters
have no denominator at all; solo falls under-reported — "numbers are the floor of the
truth").

SHAP interpretation rules (from the doc): importance = mean|φ|; beeswarm patterns
(clean red-right = risk, reversed = protective, mixed-near-zero = negligible);
dependence plots as points (vertical spread = interactions); four warnings —
association ≠ causation, correlated features split credit (read vehicle_age +
manufacture_year as a group), scale is log-odds/log-rate, seeded samples.

Three golden prediction rules: (1) no training at prediction time — read a stored,
validated artifact; (2) inputs built exactly as in training (feature list stored in
artifact meta as a contract); (3) every output carries uncertainty — "a naked number is
not a deliverable."

Validity boundaries: per-km risk claims only where a real denominator exists (interurban
segments 2017+, vehicle cells 2018+); junctions = relative ranking only; urban should be
its own third frame (TAZ population / damage-only density / bus data as proxy
denominators); congestion↔severity only on urban 2023–2024; vehicle ranking national
only; severity model unified 2010–2024 with urban flag.

**Where model outputs live: NOT in the database** ✅ (no prediction/SHAP tables exist).
The methodology assumes trained models live in an external **registry of artifacts**
consumed via "module actions," with a Streamlit-style UI (Models/Risk-changes/Map tabs).
That analysis layer is **not shipped** — the DB is the substrate; the intelligence layer
is exactly what a Task-4 plugin can become inside the NL2SQL app.

## 9. Discrepancies & verification notes

- README/live: **12 views** ✅; inventory report text says 10 (didn't count the 4
  fleet/mileage aggregate views).
- File size 437 MB ✅ vs report's ~1.6 GB (index-stripped shipping copy per README).
- "Slight accidents 2024": README ~5,458 ✅ live; inventory report's 8,315 = ALL casualty
  accidents 2024 (405+2,452+5,458) — both right, different measures.
- Semantic docs say the damage-only trap inflates "about fourfold" (series-level 3.8×);
  for 2024 slight specifically it's ~9× (50,145/5,458) ✅ — magnitude depends on the slice.
- Methodology doc writes EB excess in both orderings (observed−predicted and reversed);
  the operative definition is **excess = observed − μ_model** (rank by surplus).
- `label_drift` holds 112 rows ✅; the semantic.json prose says "3 codes" (it's
  summarizing severity only). Severity labels are drift-free 2005–2024 ✅.
- **`road_type_code` 5 (off-road) does not occur** in this build ✅ — codes 1–4 only, both
  series, no NULLs (§6 lists the dictionary). "All roads" = urban + non-urban exactly.
- **involved 2009** — see §5.4: the casualty-series person rows for 2009 are missing
  (15 rows); the plugin flags the year as uncovered. (added 2026-08-29)

## 10. Implications for the Task-4 plugin (not yet decided — input for planning)

1. **The scope gap is the value gap.** Plain NL2SQL sees 6 objects; the other ~37
   (weather, traffic/ADT, exposure cells, bus speeds, TAZ) are dark. A dedicated plugin
   can light them up *safely* — each behind an action that bakes in the correct join and
   the correct caveat.
2. **The views' philosophy extends naturally to actions:** every methodology formula
   (EB screening, Double-DiD, rate-with-denominator, severity profiles) is a candidate
   action that produces a correct-by-construction result where free-form SQL would
   silently mislead.
3. **The methodology's app surface doesn't exist here** — the plugin can be it, at
   whatever depth we choose (from "correct analytical queries + caveats" up to trained
   site/severity models with the validation-gate discipline).
4. **Aggregate-only outputs by design** satisfy the CBS license (never emit row-level
   person data; credit CBS in rendered outputs).
5. **Denominator discipline as UX:** the plugin should refuse or reframe questions that
   lack a valid denominator (per-km urban, junction entry rates, model-level safety) —
   the methodology explicitly defines what's answerable.
6. Machine constraints to remember: plugin repo in ASCII path (`c:\Users\A\dev\...`);
   data stays in the Hebrew folder (or a copy in an ASCII path if tooling chokes);
   both app copies share `%LOCALAPPDATA%\nl2sql-core` and port 8000; page-shipping
   plugins need an app restart after install.

## 11. Open questions

- Where should the .duckdb + sidecars live for daily work? (README suggests
  `C:\data\israel_accidents\` — ASCII, matches the long-path lesson.)
- Task 4 was originally framed as **two** plugins for the dedicated DB — is it now one
  advanced plugin, or a pair (e.g. analyst + modeler)? User to decide at planning.
- Which of uses א–ח are in scope for "highest level possible"? Training/persisting real
  models inside a plugin raises registry/artifact questions (where do artifacts live —
  `ctx.data_dir()`?).
- Does the core need anything (parked core changes from Task 3, e.g. `log_activity`)?
- The course owner's "15 steps" definition-of-done list is still missing (also open from Task 3).

---

## 12. What the pathfinder build AMENDED or discovered (P7 addendum, 2026-09-02; additions only)

The build (v0.0–v0.7) verified the dossier's golden rules live and found the following beyond them. The LIVING
reference is the plugin repo: `nl2sql-accidents-plugin\nl2sql_accidents\sqlkit.py` (the rules as code) and
`PITFALLS.md` (34 categorized entries with the full stories).

- **`road_km = 0` means "not coded" on BOTH sides** (location AND coding) — treating it as km 0.0 inflated
  vehicle-km; the live segment-assignment coverage is **70.4 %** (19,865/28,213), not 71.5 %.
- **Junction sentinels are FOUR**: `0, 99, 9999` (dossier) **+ `99999999`** = "unknown junction" (556 casualty
  accidents in 82 cities, no dim row) — one list for maps, coverage, controls, and key parsing.
- **Urban junction names**: the police record a junction's two streets in either order (5,684 swapped pairs);
  labels must come from ONE row's lexicographically-smallest pair, never two independent `min()`s.
- **`road_shape_code = 9` ("אחר")**: casualty-row interurban shares climbed ~5 % (2005–2007) → 24 % (2010) →
  47 % (2011, the coding discontinuity); over BOTH series it is 57 % of interurban rows overall (casualty-only
  overall: 34 %). "≠ straight" is not a curve feature; count only specific shape codes.
- **The damage-only series carries ~0 %** of the speed/surface/carriageway codings — "static attributes from both
  series" are casualty-coded in practice.
- **DuckDB 1.5.0 (the app's pin)** mis-binds QUALIFY/windows over pure range joins — keep `a.year = u.year`
  equality in every assignment join; `lag()` only over a full grid CTE.
- **`v_motorcycle_accident_rate`'s fleet is cohort-inner-joined** — summing its `active_fleet` per (year, band)
  undercounts the true fleet (zero-accident cohorts drop out); compute the denominator from `fleet_motorcycles`
  directly (a CURRENT snapshot — no per-year fleet series exists).
- **`vehicle_type_code` 22 = קלנועית חשמלית (a mobility scooter), NOT a two-wheeler** — the "docs vary" question
  resolved from `code_lookups`; two-wheeler counts-only codes are 15/21/23.
- **The gate rejected the planned `train_until = 2022`** on live (calibration 1.35 — the 2023–24 decline: the
  site-model PANEL's interurban casualty accidents fell 3,074 → 2,587 → 2,329 over 2022→2024; the NATIONAL 2024
  casualty-accident count is 8,315): the default is 2023, and the rejected 2022 artifact is kept as the
  governance demonstration.
- **Operational (see PITFALLS `state`/`concurrency`)**: the running app is a side door into the shared data dir
  (three distinct contamination vectors recorded); `os.replace` is not atomic against Windows readers — the
  registry serializes all I/O on one lock.

P9 additions (2026-09-03, the severity model build):

- **The 2010–2024 casualty person pool is 340,498 rows** (`involved`, case 1, severity 1–3, one accidents join,
  0 % unmatched on the composite key) — the "~482K casualty person-rows" figure is the 2005–2024 pool; the
  severity era starts 2010 because 2009 `involved` rows are missing (§5's coverage rule).
- **Labels drift-free ≠ shares drift-free**: the severity CODES are stable across the era, but the severe-injury
  SHARE triples (6.1 % of casualty person-rows in 2010 → 19.4 % in 2024; same shape on the accident grain — real
  reporting/mix drift, not a join artifact). Any calibration-style temporal-holdout gate on this target rejects
  every honest model; discrimination metrics (per-class recall, one-vs-rest AUC) survive it. Class-share
  baselines and 1/share weights must name their window.
- **Severity-feature sentinels**: `age_group_code 99`, `speed_limit_code 0/9/99/999`, and
  `safety_equipment_code 0/5/99/999` are "not recorded" → NULL, never levels; `involved_vehicle_type_code` is
  ~13.5 % NULL and RISING (a monotone-missing caveat, kept as xgboost missing). `late_death_code` partially
  DEFINES the killed class and ISS/hospitalized/discharge are post-outcome (97 % NULL, 2010–2012 only) — all
  excluded from any severity feature set, structurally.
