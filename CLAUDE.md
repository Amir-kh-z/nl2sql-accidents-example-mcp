# nl2sql-roadsafety-lab — rules for every session (participants' agents included)

> **What this repository is.** The complete Road Safety Lab plugin — dist `nl2sql-roadsafety-lab` · import package
> `nl2sql_roadsafety` · module id `roadsafety` · page entry point `roadsafety` → `/page/roadsafety/` (== the Vite
> `base`) · sidebar + MODULE label `🚦 מעבדת הבטיחות בדרכים` — exported for the course participants from the
> pathfinder repository at version **0.14.3** (commit `c39991f`, 2026-10-25). The Python package is unchanged; the kit
> adds `install-plugin.*`, `install-chat.bat`, `seed-models.*`, the README pair and this file. It sits BESIDE the
> closed-core app clone (`..\app\`) and installs INTO the app's Python environment through the app's own entry
> points — **no core changes, ever**. The starter kit (`nl2sql-accidents-starter`, module id `accidents_starter`)
> coexists with it: different distribution, module id, page route and data-dir prefix (`accidents/` here,
> `accidents_starter/` there). The 69 `accidents/<name>` chart-spec type strings and the `accidents/` data-dir prefix
> predate the product name and are a contract between this plugin's Python and its own page — leave them.

Read first: `README.md` (install, the question set, troubleshooting), `docs/GUIDE.md` (how to use and read every
instrument, the play curriculum), `docs/DOSSIER.md` (the database knowledge base — its golden rules are
non-negotiable: `case_type_code = 1`, the composite key, the sentinel lists, the exposure eras),
`docs/PLAN_1_CONCEPT_MAP.md` (the design: envelope, action catalog, studio, tests), `docs/m1_design.md` (the MCP
server and its tool catalog), `PITFALLS.md` (every recorded stumble, categorized — read the index before touching
SQL, packaging, the page or the MCP layer). `docs/p*_design.md` and `docs/plan.md` are the build's history:
records, not instructions.

## Hard rules
- NEVER edit `..\app\` (the closed core) or anything under its `.venv\Lib\site-packages` by hand — the plugin
  enters it only through `pip` (the installer, or the dev install below). `git -C ..\app status` stays clean.
- Data only through `ctx` (`ctx.query` / `ctx.tables` / `ctx.columns` / `ctx.schema_text`); files only
  under `ctx.data_dir()` (prefix `accidents/`).
- The DB (`C:\data\israel_accidents\israel_accidents.duckdb`, opened read-only by absolute path) never
  enters this repo, a wheel, a fixture, a committed screenshot, or any cloud service. Tests use a
  synthetic DuckDB. Committed screenshots are chart/ranking/card frames only.
- CBS credit on every rendered output:
  `מקור הנתונים: הלשכה המרכזית לסטטיסטיקה (למ״ס); עיבוד: מעבדת הבטיחות בדרכים`
  (PNG footer, `spec.credit`, last markdown line, inside `note`).
- Display level: internal use — row-level display is permitted (the seminar counts as internal).
  No aggregate-only guard, no small-cell suppression. No publishing without an explicit yes.
- One phase at a time; diff before approval; the app stays startable; every stumble → `PITFALLS.md`
  the day it happens (what happened / root cause / what to do next time); a wheel in `release\` only from a
  committed tree.

## Contract facts (engine 1.6.0, API 1.0 — verified in P0)
- `Result(kind, data, title, note)`; kinds table | markdown | sql | chart | error; ONE Result per action;
  positional constructor for `note` on non-table kinds.
- Chart spec carries the full answer: `{type, png_base64, basis, rows, columns, sql, denominator,
  caveats, credit}`; the generic Modules page shows png + basis + note only → multi-faced actions take
  a `view` input (chart | table | sql).
- `Input` kinds: table | column | text | number | bool | choice — no range/date; every input needs a
  non-None default; choice values arrive as strings.
- `ctx.query` = one read-only SELECT/WITH, no bound parameters — never interpolate user values
  unvalidated; quote identifiers. It is gated by guardrails only, never by scope.json.
- Chat already sees all 43 objects (`tables: []` = describe everything); the plugin's value is RULES
  (series filter `case_type_code = 1`, join keys, denominators, caveats), not visibility.
- `Context(db_path=...)` has no connection name: probe `accidents.case_type_code` and refuse readably elsewhere.
- Pages: entry point `nl2sql.pages` named `roadsafety` == Vite `base: "/page/roadsafety/"`; mounted at
  import → RESTART after install (before the restart the running app lists the new module/page as a
  *Problem*, "failed to import"); `webdist/` is committed so the wheel builds without Node.
- Host provides numpy, matplotlib (DejaVu Sans covers Hebrew), python-bidi (via `nl2sql-core[export]`);
  import lazily. `[ml]` = xgboost (py3-none wheel; runs on 3.14), lazy, readable `Result.error` with the
  pip command when absent. TreeSHAP: `pred_contribs` bias column INCLUDES `base_margin`.
- Hebrew in PNGs: `bidi.algorithm.get_display(s, base_dir="R")` (fallback `[::-1]`).
- Map: Leaflet with an ONLINE OSM tile basemap since P13 (instructor's 2026-09-06 call: offline is no longer a
  requirement; a 5-tileerror fallback removes the tiles, restores the outline fill and hides the OSM credit),
  GeoJSON imported as `*.json` (a `.geojson` is not a Vite JSON module), `L.circleMarker` only (no image assets:
  Leaflet's default icon resolves its PNGs from the CSS at runtime and Vite inlines them as `data:` URIs, so the
  path detection is fragile — draw vectors).

## Envelope facts (P1, verified)
- `envelope.py` is the ONLY module that constructs a `Result` (token-scan test). `guard(title)` wraps every
  action: DB probe first, `Refusal` → refusal card, `ActionError` → one-sentence error, anything else → error
  with a short traceback. `ACTION = Action(..., run=run)` is the LAST statement of every action module.
- Denominator kinds: exposure | counts | none | na. Note (one line, no newline):
  `מכנה: <label> · הסתייגות: <c1>; <c2> · מקור: הלשכה המרכזית לסטטיסטיקה` — no caveat ever contains `;`.
- Markdown cards: `#` headings only (deeper levels render tiny on Layer 0), `-` bullets, one paragraph per
  line, no tables/links/fences; answer cards start `מכנה:` and end with the CBS credit; refusal cards start
  `# ❌ לא ניתן לענות` and end with the lab line (never a CBS credit on non-CBS output).
- `spec.basis` and the PNG stamp are strict ASCII (`|`, `-`); `Result.title` is Hebrew without digits;
  `action.help` / `input.help` / `description` are ASCII prose; Hebrew lives in labels, values, PNGs.
- Coverage rule for person measures: `people >= casualty_accidents` per period, inside `case_type_code = 1`
  on the composite key → NULL (gap band), never 0. Caveats most-specific-first (the gap line leads); the PNG
  shows up to 6.
- Road caveat is data-driven (`other_road_sql`): live carries road codes 1–4 only.

## Analytical tier facts (P2, verified)
- Segment unit = the traffic count segment `(road, seg)` with ONE geometry vintage per segment-year (`UNITS_CTE`,
  6,233 of 8,100 rows); accidents are assigned with the view's exact predicate (half-open km + `ASSIGN_QUALIFY`);
  numerator and denominator share the same `units`. `traffic_adt_asof` is 2017–2024 only (`EXPOSURE_YEARS`) —
  `before_after` locates sites by a literal km range instead. Never `traffic_adt_filled`.
- `road_km = 0` is "not coded" on BOTH sides (assignment join, road site keys, the control's coded share) — one rule.
  Segment names come from the latest `traffic_segments` vintage (`arg_max(name, src_year)`); non-urban junction names
  via `min()`; urban junction names = ONE row's street pair, the lexicographically smallest (`UJ_NAMES_CTE`, shared by
  `hotspot_map` and `before_after` — two independent `min()`s named a junction "X / X").
- Junction sentinels are ONE constant: `JUNCTION_SENTINEL_CODES = (0, 99, 9999, 99999999)` — the all-nines code is
  "unknown junction" (556 casualty accidents in 82 cities, no dim row); the map, the coverage, `site_coding_exprs` and
  `parse_site_key` all read it.
- `segment_rates` is a plugin-defined descriptive instrument (the report has no per-vkm rate) — say so in the caveat.
  Its coverage numbers describe the scope shown (the chosen road, or all roads).
- Every number inside a caveat is computed from the statement for the selected range (coverage shape, the 0-mm rain
  share, band-0 cells dropped by `known_engine`, APE from `traffic_fill_validation`) or is explicitly scoped
  ("בכלל הנתונים 2005–2024"). A legal range with no rows is a refusal card, never a blank chart.
- Site keys: `road:<n>/<km_from>-<km_to>` · `njunction:<code>` · `ujunction:<city_code>/<code>`; both series located
  by the same predicate; control = the whole national network; `did_math` (Haldane SE, exp-CI), n/a when a site cell
  is below `min_cell` (default 6) or a network cell is zero; `double_did` SE² = sum (plugin extension); the control
  flag fires when the damage-only coding share moves > 25 % relative between windows.
- Vehicle cells: EB with M = 200 Mkm over cells with exposure > 0, global rate over the included cells, `ntile(5)`
  tiers; `cc_band 0` = electric/no engine (`ev_share` = 1.0 in every band-0 cell) — kept and labelled;
  `bands=known_engine` drops it and a caveat names the dropped cells and their fleet share.
- Weather: `v_accidents_weather`, `precipitation_mm > 0.1` reproduces `weather_agreement`; `לא ידוע` is shown.
- Severity profile: casualties only, coverage rule per year (2009 dropped and named), pedestrians keyed on
  `casualty_type_code = 1`, age labels from `AGE_GROUPS` (DB labels are NULL/mangled).
- Number inputs keep int defaults (contract test): a decimal threshold is a `choice` of strings.
- Three markdown card shapes: answer (`מכנה:` … credit), refusal (`# ❌` … lab line), route (`# 🧭` … lab line).
- Since P4 the ONE write under the data dir per run is the findings ledger (`accidents/ledger.jsonl`, appended by
  `guard` for answers AND refusal cards, never errors; `about`/`ledger_list`/`finding_card` are exempt via
  `guard(..., ledger=False)`); `tools/` stays repo-side only (not in the wheel).

## Studio facts (P4, verified)
- Registry: `ctx.data_dir()/accidents/models/site/<model_id>/{model.ubj, meta.json}` + `deployed.json`
  (`about` reads `model_id`). ALL registry reads AND writes serialize on ONE module-wide RLock (P4 sweep: on Windows
  `os.replace` onto a file any thread holds open raises WinError 5 — 98.9 % of writes failed under 4 readers; Python
  opens without FILE_SHARE_DELETE) + a bounded os.replace retry for external openers; multi-step invariants
  (save's collision check, `registry.deploy`'s demote→pointer→status) run entirely under the lock; `update_meta`
  returns None on unreadable meta and WRITE-PATH callers must check it (studio_validate raises ActionError).
  ALL readers tolerant (garbled → status "unreadable"); `created_at` has microseconds and same-second id collisions
  re-suffix (both bit us). `meta.json` IS the feature contract: features, target, panel numbers, ADT fill, the three SQL
  texts, the FROZEN static-attribute rows, params, gate {metrics, thresholds, sources, reasons}, α, status.
- Panel = the FULL 1,311 × 2017–2024 grid (10,488 rows, 0.07 s): per-year as-of geometry where it exists, the
  latest `traffic_segments` vintage elsewhere; `lag1` from a window over the GRID (never over a range join);
  ADT median fill + `adt_known`; static attrs from BOTH series 2005–train_until on the latest vintage — but the
  five coding columns are casualty-coded in practice, and `pct_curve` counts only rows with a SPECIFIC shape code
  (code 9 "אחר" is a 2011 coding change). Never `traffic_adt_filled`; y = casualty accidents; no offset.
- xgboost 3.4.1 NATIVE API only (`xgb.train`/`Booster`/`DMatrix`; XGBRegressor needs sklearn — absent); lazy import;
  missing → `ActionError` with the pip command; a fresh Booster from bytes per request (thread safety).
- Gate on live: default `train_until = 2023` → validated (Spearman 0.693, כיול 1.17, ratio 0.82, α 0.16, ~1.2 s);
  **2022 is genuinely rejected (כיול 1.35 — the 2023–24 decline)** and stays in the seeded registry as the honest
  governance beat next to shuffled/2018 (Spearman 0.201). Thresholds live in `studio/constants.GATE` with their
  source tag (report vs plugin) — every card prints the tag.
- `site_ranking` / excess map: NO training at predict time; features rebuilt from the contract
  (`predict.expected_by_segment`, shared); excess = observed − μ (panel observed — a caveat carries the difference
  vs `segment_rates`); EB w = 1/(1+α·μ); NB 90 % normal approx (Var = Σ(μₜ + α·μₜ²)); ranks by excess; refuses
  without a deployment. Demo: 60/850 is the excess leader (+40); **60/836 (the 2017-treated site) shows excess −2 —
  below its expectation, which is beat 3's story.**
- Seeded shared dir (the stage state): deployed doc-11/2023 + rejected doc-11/2022 + rejected shuffled/2018 +
  the rehearsal `before_after` ledger entry. NL2SQL_CORE_DATA_DIR is read once per process (move tests are
  subprocesses); never set it on stage. **The RUNNING app on port 8000 writes to this dir** — anything that
  exercises the live API (agents, headless checks) contaminates the stage state; re-verify before the show.

## P5 facts (studio_explain + two_wheelers, verified)
- `studio_explain`: `model.contribs` = `pred_contribs=True` on a fresh Booster (bias LAST, includes base_margin);
  Σφ_row = ln μ_row exactly (count:poisson margin) — pinned to 1e-4; the site table shows top-5 + bias ONLY (a
  ~0.1 gap to ln μ is the 6 dropped features, not a bug). `site` accepts `60/836` (road/seg) or a `road:` site key
  (junctions refuse); `model_id` "deployed" or any explicit id (non-deployed adds a status caveat); Hebrew feature
  labels in `studio/constants.FEATURE_LABELS_HE` (digit-free). Attaching a PNG AFTER `make_spec` must also set
  `spec["renderer"] = "png"` (make_spec derives it at build time — bit us).
- `two_wheelers`: NEVER sum `v_motorcycle_accident_rate.active_fleet` per (year, band) — the view inner-joins
  accident cohorts, zero-accident cohorts drop out (undercount). Numerator = `vehicles ⋈ accidents` (composite key,
  case 1, codes 8/9/10/19), denominator = full `sum(active)` per band from `fleet_motorcycles` (a CURRENT per-model
  snapshot, no year column — a caveat says so); the grid is fleet-driven and zero-filled (a zero-accident cell IS a
  rate). cc bands are 2013+ (era refusal). Counts-only codes: 15 אופניים, 23 אופניים חשמליים, 21 קורקינט חשמלי;
  **22 קלנועית is a mobility scooter — excluded** (labels resolved from `code_lookups`, field `vehicle_type_code`).

## P9 facts (the severity family + the visibility pass, verified)
- Registry is family-threaded EVERYWHERE since P9: `save/read_meta/update_meta/model_bytes/new_model_id` take
  `family` (the P4 quartet was family-blind — a latent bug with zero one-family symptoms; two-family regression
  test pins it). Per-family `deployed.json`; `registry.deploy`/`set_deployed` read the family from the meta.
- Severity family: person grain = `involved` ⋈ `accidents` on the COMPOSITE key (accident_id, case_type_code),
  case 1, `injury_severity_code IN (1,2,3)` → class 0/1/2; ERA 2010–2024 = **340,498 live rows** (the dossier's
  "~482K" is the 2005–2024 pool). Sentinels → NULL in the SQL itself (age 99 · safety 0/5/99/999 ·
  speed 0/9/99/999); leakage exclusions are STRUCTURAL — the matrix SQL selects only the 12 contract columns
  (token-scan test); `year_idx = year − 2010` is derived, not selected.
- The share-drift trap: the severe share TRIPLES (6.1 % 2010 → 19.4 % 2024) → the gate is DISCRIMINATION only:
  fatal recall ≥ 0.5 · AUC(fatal, Mann-Whitney with average ranks) ≥ 0.8 · train-holdout AUC gap ≤ 0.05, ALL
  plugin-labelled; calibration is deliberately absent (it would reject every honest model, like site-2022).
  Class weights n/count(c) FROZEN from the train window into meta (live train ≤ 2022: 69.48/11.21/1.116 — the
  design doc's 64.68/10.27/1.127 were the FULL-era shares, not the train window's; the window matters). Probabilities
  leave the family only RELATIVE (to `class_shares_holdout`, or scenario/baseline in what_if).
- `severity.train`: inner fold = the LAST training year (empty fold → ActionError), early stop 25/500, refit
  ≤ train_until with best+1 rounds; `train_until` 2018–2023, default 2022; fresh Booster per predict call.
  `model._dmatrix` takes `names=` (defaults to the SITE feature list — always pass `severity.FEATURES`).
- `severity_predict`/`what_if`: full refusal ladder without a deployed severity model; UNSET = "לא צוין" → None
  (xgboost's missing path, never imputed); what_if's switch field OVERRIDES the matching profile input; both are
  four-view (chart | markdown | table | sql) like studio_explain — test_contract's FOUR_VIEW set.
- Studio fixture: severity person rows come from a SEPARATE `LCG(SEED + 1)` AFTER the accident loop — the
  accident stream is PINNED by SUMMARY + the drop_after 5-draw alignment; planted signal (night ×3.5, ped/moto
  ×6, no-safety ×5, speed ≥5 ×2.2 on killed odds) makes person-12 validate (AUC ≈ 0.845 · recall ≈ 0.693 ·
  gap ≈ 0.029) and shuffled fail (AUC ≈ 0.46). conftest's `involved` DDL is 18 columns since P9
  (`safety_equipment_code`, `population_group_code`). The PLAIN fixture trains only with `train_until=2018`
  (2022 leaves no inner-fold rows there).
- Track A: `Answer.jsx` renders the 🔮 model chip for ANY spec carrying `model_id` (site_ranking, excess map,
  studio_explain, the gate faces, severity_predict, what_if — zero per-action work); `studio_explain` gained
  `view=markdown` = the per-site prediction card (μ, NB 90 % interval, observed, verdict מעל/מתחת/בתוך, top-3
  drivers) and the empty-site global-drivers card; triage routes תחזית → studio_explain, פרופיל סיכון →
  severity_predict, מה אם → what_if.

## P12 facts (SHAP explainability, verified)
- Multiclass contribs: xgboost 3.4.1 `pred_contribs` on multi:softprob is **(n, 3, 13)** — per class, 12
  features + bias LAST (incl. base_margin); margins via `output_margin`. ONE guarded pass for all three
  explain surfaces: `severity_predict.contribs_guarded` (Σφ+bias=margin, ActionError over 1e-3; tests 1e-4).
- Coloring policy (`studio/explain_severity.py`): value-color ONLY `ORDERED` (age/speed/hour/year_idx/
  day_night/sex); road_type is a 2×2 and month cyclic → NOMINAL grey; NULL hollow "לא ידוע".
  **Display sentinels** (`DISPLAY_NULL_CODES`): sex_code 0 = "לא רלוונטי" (3,797 live era rows) is masked
  to NULL for coloring/direction/shares — the model still sees the raw value (matrix-side 0→NULL =
  CONTRACT_VERSION bump + retrain, parked). Dependence NULLs get an explicit slot on BOTH axis kinds
  (`null_x` strip right of a numeric range — x=None dots are silently skipped by every renderer, the sweep's
  5× catch).
- Determinism: `SAMPLE_SEED` fixed; per-feature rng streams (seed+1+j / seed+101+j); `stack_jitter` is
  rng-free binning; jitter/subsample land IN the spec so plotly and the PNG twin share one layout and
  repeated runs are byte-comparable (pinned).
- Decode is TOLERANT garnish: `code_lookups` by field name, latest year via `arg_max(label_he, year)`;
  `involved_vehicle_type_code` decodes under field **`vehicle_type_code`** (code 4 has no dictionary entry —
  671 era rows fall back to the number, by design). A failing lookup → numeric labels, never an error.
- Latency: state action latency from a FULL-action live probe, never a kernel benchmark — 20k ≈ 7 s end to
  end (contribs alone was the spike's 2 s), full ≈ under a minute. The five bump touch points have a SIXTH:
  re-run `pip install -e` (stop the app first — a mid-run editable swap left a shadowing package corpse;
  both in PITFALLS).
- Fixtures: `code_lookups` exists in BOTH test DBs (conftest `CODE_LOOKUPS`); it moved the about card's
  schema pin to 15 objects. The about card's פעולות roster is now derived-asserted from MODULE (third
  drift catch). what_if's drivers are Δφ (bias cancels; `switch_feature` marks the switch) — every face
  must SAY delta, not φ.

## P13 facts (the borrow build, 2026-09-06 — two implementation waves + an adversarial verify + a fix wave)

- **30 actions.** New: `heat_matrix` (7×24 zero-filled grid, unknown-hour exclusion caveat is data-driven — live
  hour_of_day is complete), `zone_ranking` + `city_ranking` (the dark geographic aggregates), `ab_scan` (the
  before/after discoverer). `severity_profile` gained lighting/hour_of_day (4 SQL buckets)/day_of_week/
  speed_limit/road_shape (code-9 share caveat carries the 2011 discontinuity); `vehicle_cells_ranking` gained
  `group=cohort` (real per-cell exposure summed — never the rival's flat-fleet denominator); `about` gained the
  `# מדדים אחרונים` KPI block (feeds the page's StatCards, ledger-clean).
- **Zones/cities are a SEPARATE UNIVERSE** (dossier §4.7): cumulative undated snapshots (stamp 202604) — NO year
  inputs by design; every answer carries the stamp + both sides' totals (TAZ 38,363 · municipality 276,849 ·
  series 270,723). `accident_index` ≡ density (r = 1.000, recomputed live per run) and r = 0.04 vs per-capita —
  the demo beat. `city_ranking` ranks at LOCALITY grain (live: 1,174 rows / 1,170 codes — split rows summed);
  ped_share ships its denominator column, breaks % ties by it, and counts tiny-denominator rows in a caveat.
- **ab_scan's counting rule** (post-refuter): BOTH series counted on the LATEST traffic_segments vintage only —
  one literal km range per unit for ALL years (before_after's rule; the wave-1 static/as-of splice made 19/20
  top candidates geometry artifacts and flipped the leader's sign under its own hand-off — the chain-consistency
  test in test_ab_scan pins cells equality with before_after). Windows exclude the event year ([e-w..e-1] vs
  [e+1..e+w]); |z| is a RANK SCORE, no CI anywhere; the hand-off pre-fills site + change_year (Answer.jsx rides
  change_year through onHandoff's extra param). Live sanity: the discoverer independently surfaces road:60/96-98.8
  e=2017 (the demo's treated site) as an improvement.
- **Gate ROC/calibration are DIAGNOSTICS, never gates**: gate.roc_curve (tie-collapsed, AUC == Mann-Whitney,
  cross-pinned vs severity.auc_binary at 1e-12), positive = top-decile observed, plugin-tagged caveat;
  spec['points'] + spec['roc'] ride the chart face only — constants.GATE and every stored verdict untouched.
- **The page is theme-aware** (was the "his looks better" gap): web/src/theme.js reads the CSS tokens with a
  matchMedia re-render; Plotly structural colors from tokens, meaning hues fixed; five semantic tokens have dark
  values; Leaflet chrome tokenized; `img.png` stays white ON PURPOSE (the matplotlib twin is light by design).
  PlotlyChart + TrendCompare carry their own ResizeObserver (plotly 3.7 has none and rejects hidden divs).
  StatCards' CSS contract is `.stat-card .stat-num/.stat-label`; dark-mode `.on`/`.primary` ink is var(--app-bg)
  via a LAST dark block (cascade order beats the light rules — a rule in the token block silently loses).
- **One excess colour rule everywhere**: z in the site's own NB units (sd floored 0.5), hotspot_map._excess_color
  ≡ map_scene._excess_hex ≡ the page (parity-tested). Degrade paths: ONE merged reason line (no false
  "no deployment" claims — the y1<2017 arm is ported, junctions lead with the segments-only truth, a model-path
  Refusal degrades to observed like any failure); y0e resets so a degrade never silently narrows the range.
- **OSM POLICY CHANGE (2026-09-06, instructor):** offline is no longer required. Leaflet has OSM tiles with a
  tile-death fallback; the MapLibre tab falls back pmtiles → OSM raster ('osm' mode) → canvas; test_page pins
  attribution-if-OSM, and the three basemap leak guards stand.
- **DEFERRED (dormant, wire when wanted):** studio_train_site/severity have client-side chart builders in
  PlotlyChart but still declare VIEWS = (markdown, table) — adding 'chart' + a PNG twin + contract entries
  activates them.
- Hebrew reading-blurbs for all 30 actions live page-side in web/src/components/blurbs.js (ActionPanel +
  TrendCompare render them); the ASCII-help contract is untouched.
- **P13 round 2 (2026-09-07, instructor's side-by-side review):** the bundle is `plotly.js-cartesian-dist`
  (NOT basic — basic has no heatmap trace; heat_matrix draws a real heatmap now). `severity_profile` has a
  `display` input (shares|counts): counts + by=year = the three-line severity trend (rival-inspired, our
  gap discipline — uncovered years break under a grey band; PNG twin `charts.severity_lines`); counts with
  any other by is an ActionError; the action ALSO sits on the מגמות tab (two independent panels, by design).
  The studio tab opens with the WORKBENCH (`web/src/components/Workbench.jsx`): per-family verb bars over
  the same actions, output through Answer; `studio_models` is guard(ledger=False) since P13r2 — that is
  what allows its auto-load on tab activation; NEVER auto-run any ledger-writing action.

## Page + map facts (P3, verified)
- `nl2sql_roadsafety/page.py` (stdlib-only, never imported by `__init__`) → `{"path": webdist, "label": "🚦 מעבדת הבטיחות בדרכים"}`;
  entry point `roadsafety` == Vite `base: "/page/roadsafety/"` (tests/test_page.py pins it). `webdist/` is committed;
  `pyproject` ships it plus `data/israel.json` via `[tool.setuptools.package-data]` (+ `MANIFEST.in`).
- Source in `web/` (React 18 + Vite 6 + Leaflet 1.9.4, plain CSS with the app tokens, RTL html, `.ltr` islands).
  Build: `cd web; npm install; npm run build` (node ≥ 20; this machine v24.16). Dev: `npm run dev` proxies `/api`.
- The page reads `?db=` (sidebar link), falls back to the most-recent connection, `?tab=<id>` and `?run=<action>`
  (auto-run with defaults — demo pre-flight + headless checks). Forms come from `GET /api/modules` declarations; the
  page always sends `view=chart` when the action has one and reads png + rows + sql + caveats from the ONE spec.
- Answer anatomy = `components/Answer.jsx`: badge by `denominator.kind` (exposure green / counts amber / none red /
  na grey), ribbon = `spec.caveats`, face by kind (`accidents/map` → Leaflet, png, card, table, sql, error), table
  + show-SQL `<details>`, `spec.credit` footer, the Layer-0 `note` behind a toggle. Cards by first line
  (`# ❌` refusal, `# 🧭` route with action buttons, `מכנה:` answer).
- Map contract: `spec.geojson` = FeatureCollection of Point features, `properties.kind` = `unit` (site_key, label,
  rank, accidents, ksi_accidents, geocoded, first/last_year, km range or geometry_source/dim_rows) or `accident`
  (site_key, rank, accident_id, date, severity…). Leaflet: OSM tiles under the vectors (P13; outline fill goes
  transparent while tiles live, restored on tile death), `fitBounds` BEFORE layers, `L.circleMarker`
  only, the map div a `dir="ltr"` island, popup content `dir="rtl"`, popup buttons via `popupopen`, `maxZoom: 11`,
  try/catch → error card + the PNG twin. ONE outline file (`data/israel.json`, Natural Earth 1:10m) for Vite and
  `charts.map_png`.
- `hotspot_map`: geometry per (road, seg, year) = `units` 2017+ ∪ latest `traffic_segments` vintage × earlier years
  (`assign_join("geom")` keeps the year equality DuckDB 1.5.0 needs); counts for 2017+ equal `segment_rates`;
  `GEO_PREDICATE` bbox; junction dims grouped (never a plain join); `site_key` from the latest vintage; two refusals
  (no rows / nothing placeable); `color_by=excess` → observed + caveat (`color_by_effective`); points capped in SQL.
- Headless check: `Start-Process msedge -ArgumentList --headless=new,--user-data-dir=<fresh>,--virtual-time-budget=20000,
  --dump-dom,"<url>&run=hotspot_map" -RedirectStandardOutput dom.html -Wait`, then count markers.

## Provenance and updates

- A frozen export of the pathfinder repository (`Amir-kh-z/nl2sql-accidents-plugin`, private) at 0.14.3; the wheel
  in `release\` was built from exactly this source. `install-plugin.bat` installs the newest VERSION found there —
  never the newest name ("0.9.0" sorts after "0.10.0" as text).
- The distribution surface (`install-*.bat/.ps1`, `seed-models.*`, `fetch-basemap.*`, `release\*.whl`, the two
  READMEs) is user-facing: ASCII-only console output (the console code page mangles Hebrew), CRLF line endings on
  `.bat`/`.ps1` (`.gitattributes` enforces them), no prompt that cannot be answered by Enter.
- A new release of YOUR fork: suite green → version bumped (`pyproject.toml` + `nl2sql_roadsafety\__init__.py`;
  the bump has six touch points — PITFALLS 2026-09-05) → delete `build\` → `python -m build --wheel` → the wheel into
  `release\` (one wheel per release) → commit. Published versions are immutable: never rebuild under a used number.

## Commands (from this folder, `nl2sql-roadsafety-lab\`)
- Tests: `..\app\.venv\Scripts\python -m pytest -q` (≈ 45 min when the live DB is at its default path; otherwise the
  synthetic fixtures only). Quick gate: `-x -q tests\test_contract.py tests\test_page.py`.
- Dev install (after changing Python): STOP THE APP, then `..\app\.venv\Scripts\python -m pip install -e ".[dev,ml]"`,
  then start it again (`install-plugin.bat -FromSource` is the non-editable equivalent). An editable swap over a
  running app, or under a running `roadsafety-mcp.exe` (Claude Desktop keeps one alive per chat), leaves a
  half-installed package — PITFALLS 2026-09-05 / 2026-10-16.
- Start / restart the app without a browser: stop the uvicorn whose command line contains your app path — filter on
  `Name -eq 'python.exe'` too, or the PowerShell that runs the filter matches itself and dies — then
  `$env:PYTHONUTF8 = "1"; Start-Process -WorkingDirectory ..\app ..\app\.venv\Scripts\python.exe -ArgumentList "-m","uvicorn","api.main:app","--port","8000"`
  (exactly what `run.ps1` sets; without it the console encoding is cp1255). One app copy at a time: every copy on a
  machine shares port 8000 AND the data dir.
- Scratch state: `$env:NL2SQL_CORE_DATA_DIR = "c:\tmp\play"` before starting the app, the MCP server or
  `seed_models.py` gives a consequence-free data dir (copy `added_connections.json` from `%LOCALAPPDATA%\nl2sql-core`
  into it, else the page 404s — PITFALLS). The variable is read once per process.
- The two reference models: `seed-models.bat` (in-process, idempotent; `-Force` trains again). The page's studio
  tab does the same by hand: train → validate → deploy, per family.
- MCP without a chat window: `..\app\.venv\Scripts\python -m pytest -q tests\test_mcp_server.py tests\test_mcp_tools.py`;
  the acceptance question set is `docs/mcp_acceptance.md`; one audit line per tool call lands in
  `accidents\mcp_audit.jsonl` under the data dir.
- Wheel sanity once per release: delete `build\` first (setuptools' `build/lib` keeps STALE hashed page assets and
  ships them), then `..\app\.venv\Scripts\python -m build --wheel` (isolated) and inspect the namelist (must list
  exactly the current `webdist/**`, `data/israel.json`, `data/fonts/*`, `mcp/knowledge/*.md`, `page.py`; never
  `tools/`, `web/` or a basemap).
- Page rebuild after any `web/src` change: `cd web; npm install` (once; node ≥ 20) `; npm run build` (then commit
  `nl2sql_roadsafety/webdist/`); the app serves the new files without a restart — a NEW page (entry point) needs one.
- Verification answers (2024): 439 killed · 5,458 slight accidents (naive: 50,145) · 8,315 casualty
  accidents · 43 schema objects · `weather_hourly` 10,519,200 rows.
