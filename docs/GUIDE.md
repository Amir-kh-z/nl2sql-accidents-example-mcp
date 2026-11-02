# The field guide — how to use it, how to read it, how to poke it

For whoever runs the lab: what every option does, how to read each answer **analytically** and **ML-wise**,
experiments that expose the methodology, and where the knobs live when you want to suggest changes. Companion
docs: `PLAN_1_CONCEPT_MAP.md` (the design), `DOSSIER.md` (the database knowledge base and golden rules),
`demo/MCP_DEMO.md` (the chat-channel script), `PITFALLS.md` (every recorded stumble).

## 0. Two ways in, and a warning about state

- **Layer 1 — the 🚦 page** (`http://localhost:8000/page/roadsafety/`): seven tabs, forms, interactive charts.
  Deep links: `?tab=<trends|hotspots|map|severity|before_after|studio|findings>`, `?run=<action>` (auto-runs with
  defaults). This is where you play.
- **Layer 0 — the generic 🧩 Modules page**: the same thirty actions rendered by the host with zero plugin UI.
  (P13 added `heat_matrix`, `zone_ranking`, `city_ranking`, `ab_scan` — the zone/city pair lives in its own
  cumulative-snapshot universe and says so on every answer; `ab_scan` discovers before/after candidates and
  hands each row to `before_after` with the site + change year pre-filled. Their full stories: CHANGELOG P13.)
  Everything important must survive here — that constraint shaped the whole answer format.
- **State warning**: the running app writes to the shared data dir (`%LOCALAPPDATA%\nl2sql-core`) — every
  answered run appends a ledger line, and every training run adds a registry entry. **Play freely** — nothing
  there is precious: `seed-models.bat` re-creates the two reference models whenever a family has no deployed
  model (`-Force` trains again), and the ledger is yours to grow. If you want consequence-free deep play (mass
  trainings, deploy experiments), start a second session against a scratch dir instead:

```powershell
# stop the stage app first (one copy at a time — shared port 8000), then:
$s = "C:\tmp\play-dir"; New-Item -ItemType Directory -Force $s | Out-Null
Copy-Item "$env:LOCALAPPDATA\nl2sql-core\added_connections.json" $s   # else the page 404s (PITFALLS)
$env:NL2SQL_CORE_DATA_DIR = $s; $env:PYTHONUTF8 = "1"
Start-Process -WorkingDirectory app app\.venv\Scripts\python.exe -ArgumentList "-m","uvicorn","api.main:app","--port","8000"
```
  (The env var is read ONCE at import — set it before starting, and unset it before restarting the stage app.)

## 1. How to read ANY answer — the five-step discipline

Every answer, on both layers, has the same anatomy. Read it in this order:

1. **The denominator badge** (top). This is the single most important pixel on the screen:
   🟢 **מכנה חשיפה אמיתי** = a real exposure denominator (vehicle-km, fleet) — this is a *risk*.
   🟠 **ספירות בלבד** = counts — this is *where*, never *how dangerous*.
   🔴 **ללא מכנה** = explicitly no denominator. ⚪ **לא רלוונטי** = not applicable (cards, studio).
   The badge label names the denominator exactly. If you remember one habit: *counts are not risk*.
2. **The 🔮 model chip** — present iff a deployed model computed part of this answer; names the exact
   `model_id` and what the face compares (observed vs predicted / two hypothetical scenarios / drivers).
   No chip = pure SQL aggregation, no ML.
3. **The caveat ribbon** — ordered most-specific-first, and every number in it is computed live for the range
   you chose (coverage shares, dropped years, gap bands), never a hard-coded global.
4. **The face**, then the table behind it (`טבלה`), then **הצג SQL** — the exact single SELECT that produced
   the rows, plus the ASCII `basis` provenance line. Everything is reproducible from there.
5. **Refusals are answers**: `# ❌ לא ניתן לענות` cards state *why* and what IS answerable. The gate refusing
   a model, triage refusing "which car model is safest" — those are product features, not errors.

ML-wise, add three standing questions: *what did the model train on and until when* (the chip's id encodes it:
`site-2023-…` = trained through 2023), *what was held out* (always the years after `train_until`), and *is the
claim a ranking or a level* (the two families gate differently — see §4/§5).

## 2. The analytical tier — action by action

**trend** (`measure ∈ accidents|killed|severe_injured|slight_injured|fatal_accidents`, `granularity`,
`road_type`, years): counts over time under the golden series rule (`case_type_code = 1`). Gaps are drawn as
gaps, never zero. Check: 2024 killed = **439**. Play: `granularity=month` and watch seasonality;
`road_type=urban` vs `nonurban` split.
P11 — **the composer** (page-only): the small `+ השוואה` button opens up to two more slicer rows (prefilled
from row 1; `הרץ הכול` runs them together), and the page composes the runs: ONE shared y-axis when honest
(identical gap periods AND scale ratio ≤ 3), small multiples otherwise — never two independent y-axes,
which is the classic chart lie. The אוטו/מאוחד/מפוצל toggle shows and overrides the auto decision; a forced
overlay across differing coverage drops the gap band and names the series with missing periods. Each run
keeps its full envelope (collapsed under the composed figure) and its own ledger line — the composition
itself is a view, not a finding.

**naive_vs_correct** (`year`): THE trap card. A naive slight-accidents count for 2024 gives **50,145**; the
correct one **5,458** (≈9×) — damage-only case rows carry "severity 3" without casualties. Every number in the
plugin flows through this filter; this card is why chat-alone over raw tables is dangerous.

**segment_rates** (`road`, years, `severity ∈ all|ksi`, `order_by`, `top_n`): casualty accidents per 100M
vehicle-km on interurban count segments — a 🟢 real-exposure rate, with Byar CIs computed in SQL. Analytical
reading: `order_by=rate_lo` ranks by the CI's LOWER bound (a high point-rate on tiny exposure ranks below a
solid one) — flip to `order_by=rate` and watch small-exposure segments jump; that difference IS the lesson.
The exposure is as-of ADT vintages (2017–2024 only); the coverage caveat tells you how much of the network the
scope covers. This instrument is plugin-defined (the methodology report has no per-vkm rate) — the caveat says so.

**hotspot_map** (`unit ∈ segments|njunctions|ujunctions`, `road`, years, `color_by ∈ observed|excess`,
`points`): WHERE things happen. `observed` is 🟠 counts-only on purpose; `color_by=excess` switches the color to
observed − model-predicted (needs a deployed site model; falls back to observed with an honest caveat if none).
`points=true` adds row-level accident dots (fine internally — never captured into anything published). Play:
road 60, 2019–2024, `color_by=excess` — the leader is 60/850 (+39.7 above prediction), and 60/836 shows −2.0.

**map_scene** (`road`, years, `top_sites`, `max_points`, `color_by`, `twin`) — P10, the מפה חיה tab's data door: ONE
envelope with the whole geocoded point cloud as columnar arrays (~218k points 2008–2024; the page renders it
on the GPU and filters year/severity/day-night client-side — zero re-fetches; hovering a point shows its
year, severity and day/night — the columns the payload ships; date-level drill-down lives in hotspot_map's
points and the site panel), the three site layers (the hotspot SQL verbatim), locality centroids for the
offline search, and the coverage numbers. 🟠 counts by
design — model depth lives one click away. The tab itself: street basemap when `web/basemap/israel.pmtiles`
exists (offline PMTiles; `tools/fetch_basemap.py`), dark data-canvas otherwise — a wheel-only install lands
on the canvas automatically. **The risk view** (`color_by=excess`, the page's "מול המודל" toggle): with a
deployed site model the SEGMENTS layer re-ranks and re-colors by excess on the shared diverging scale
(blue = below the expectation band, red = above — the DEPTH is the site's distance from expectation in its
own uncertainty units, so no outlier can own the scale; white ring = significant; ALL panel segments show,
red through blue) — the EB network screening as a map; junctions stay in the counts grammar (no denominator,
the map itself draws the golden rule), and without a deployment it falls back to counts with a caveat.
Below the map in model mode: the **z-distribution drawer** — the histogram of band distances across the
whole panel (residual-diagnostics EDA): center left of zero = the calibration shift, the fat right tail =
the screening population beyond chance (live: 63 above · 839 within · 85 below of 987, vs ~49+49 expected
at the 90% band). Deep links:
`?tab=map&road=60&from_year=2019&to_year=2024` (+`&basemap=off`, +`&color=excess`).

**site_profile** (`site`, years) — P10, the map's click panel and a four-view action in its own right: the
yearly observed strip for ANY site kind; μ/excess/EB/interval/verdict/top-3 SHAP drivers for road segments
when a site model is deployed (🟢 exposure); a conditional severity profile (relative only) over the site's
own person rows when a severity model is deployed. Junctions NEVER carry rates or excess — structural, with
the standing caveat. Missing prerequisites degrade to absent sections + a caveat, never a refusal. Accepts
`60/836`, `road:<n>/<a>-<b>`, `njunction:<code>`, `ujunction:<city>/<code>`. Play: `njunction:323`
(מחלף מורשה, counts-only) vs `60/836` post-deploy (excess −2.0 — below expectation, verdict "בתוך רווח התחזית":
the deficit is real but inside the noise band; that nuance IS the teaching point).

**site_ranking** (`road`, years, `top_n`): the prediction workhorse. Per segment: observed, **צפוי** (the
deployed model's μ summed over your years), excess = observed − μ, an EB-shrunk estimate
(w = 1/(1+α·μ) — small-μ segments get pulled harder toward the model), and an NB 90% interval
(Var = Σ(μₜ + α·μₜ²)). A segment is flagged iff observed falls outside its interval. ML-wise: this face is
"model as ruler" — the interesting rows are the residuals, not the counts. No training happens here, ever
(golden rule: predict-time reads the frozen artifact).

**before_after** (`site`, `change_year`, `window_years`, `min_cell`): Double-DiD. Site keys:
`road:<n>/<km_from>-<km_to>`, `njunction:<code>`, `ujunction:<city>/<code>`. The site's before/after ratio is
divided by the whole national network's ratio over the same windows (the control) — that quotient is the
**double ratio**; SE via Haldane, CI on the log scale. `min_cell` guards thin cells (below it → n/a, never a
fake number). The demo beat: `road:60/96.0-98.8`, `change_year=2017` → double ratio 0.11. A caveat fires if
the damage-only coding share moved >25% between windows (a recording-practice change can fake a treatment
effect). Cross-check against site_ranking: the same treated site sits BELOW its model expectation — two
independent methods, one conclusion. That triangulation is the strongest analytical move in the plugin.

**severity_profile** (`by ∈ casualty_type|road_type|day_night|age_group|weather|involved_vehicle_type|sex|year`,
years): casualty-person composition. Coverage rule: a year where people < casualty accidents is dropped and
named (2009 is missing from `involved` — you'll see it dropped). P11 — **`by=year` is the share-drift
exhibit**: the severity composition per year, chronological, and you SEE the severe share roughly triple
(6% → 19% live) while the codes never changed — share drift (reporting collapse of slight + real growth),
not label drift, and the visual reason the severity gate (§5) measures discrimination instead of calibration.

**vehicle_cells_ranking** (`metric ∈ involvements|ksi|fatal`, `bands ∈ all|known_engine`): EB-shrunk rates per
Mkm over manufacture-year × engine-cc cells (M = 200). `cc_band 0` = electric/no-engine — kept and labelled;
`bands=known_engine` drops it and the caveat names the dropped fleet share. Play: switch metric to `fatal` and
watch the shrinkage matter more (rarer events → heavier pull to the global rate).

**two_wheelers** (`metric`, years): motorcycle involvement per 1,000 ACTIVE registered vehicles by cc band
(2013+), computed on the full fleet — the curated view undercounts (it inner-joins accident cohorts, so
zero-accident cohorts vanish). Bicycles/e-bikes/e-scooters appear as counts-only rows: no fleet denominator
exists, and the caveat says solo falls are under-reported — a floor, not a rate.

**weather_check** (years, `rain_threshold_mm`): the officer's weather label vs ERA5 measured rain.
`לא ידוע` is shown (it is the second-largest label). Play with the threshold and watch agreement move — a
lesson in operationalization.

**triage** (`question`): the routing/refusal gate. Ask it the demo question ("איזה דגם רכב הכי בטוח?") and read
a principled refusal; ask "תחזית לאתר" / "פרופיל סיכון" / "מה אם" and it routes to the model actions.

**ledger_list / finding_card**: every answered run (refusals included) appends one line to
`accidents/ledger.jsonl`. `finding_card entry=latest claim=<your sentence>` promotes the last run into
claim + evidence + rerun recipe — "what leaves the room."

## 3. The ML studio — the shared governance cycle

Both model families follow the same product cycle, and the cycle IS the methodology:

```
studio_train_*  →  candidate in the registry   (never usable for prediction yet)
studio_validate_*  →  the GATE: validated | rejected WITH reasons   (written into meta.json)
studio_deploy   →  ONE deployed pointer per family; REFUSES rejected models, re-listing the reasons
readers         →  site_ranking / hotspot excess / studio_explain   |   severity_predict / what_if
```

Key objects to read: **studio_models** (`family ∈ site|severity`) lists every model with status and gate
metrics — the registry is plain files under the data dir (`accidents/models/<family>/<id>/{model.ubj,
meta.json}`), and `meta.json` is the full contract: features, the exact SQL, frozen fill values/weights,
params, the gate block with thresholds AND their source tag. **Every threshold on every card is labelled**
`דו״ח` (from the methodology report) or `כלל התוסף` (the plugin's own rule) — when you want to argue with a
gate, that tag tells you whom you're arguing with.

## 4. Reading the SITE family (counts per segment-year)

- **Model**: XGBoost `count:poisson` over the full 1,311-segment × 2017–2024 panel; features = doc-11 (traffic
  ADT as-of, lag-1 history, geometry, coded attributes); y = casualty accidents.
- **Gate metrics** (validate card / studio_models):
  - **Spearman** (≥ 0.3, report): does the model RANK holdout segments correctly? The deployed 2023 model:
    0.693.
  - **כיול = Σpredicted/Σobserved** (± 25%, report): does the LEVEL match? 1.0 is perfect; 1.17 = 17%
    over-prediction.
  - **Deviance ratio** (≤ bound, plugin rule): holdout vs training deviance — an overfit tripwire.
  - **α**: the NB dispersion estimated from residuals; 0 = pure Poisson. Feeds the EB weights and intervals.
- **The two governance exhibits, live in the seeded registry**:
  - `site-2022-…` is **genuinely rejected** (כיול 1.35): trees cannot extrapolate the 2023–24 decline. This is
    an honest model failing an honest gate — not a staged prop.
  - `site-2018-shuffled-…` (Spearman 0.201): the training target was permuted — a model that learned nothing
    must fail. If your gate can't reject a shuffled model, you don't have a gate.
- **studio_explain** (`site=60/850` or empty): TreeSHAP. Each feature's φ is on the log-rate scale and the φ
  sum equals ln μ *exactly* (enforced at runtime — an identity, not an approximation). Empty site = global
  mean|φ| = what feeds the model's predictions overall; a specific site = why THIS place, plus the markdown
  prediction card (μ, 90% interval, observed, verdict).

## 5. Reading the SEVERITY family (P9 — conditional severity per person)

- **Model**: XGBoost `multi:softprob` over 340,498 casualty person-rows 2010–2024 (person-12 features: the
  person + one crash-context join). Classes: killed / severe / slight. Class weights = 1/share computed on the
  TRAIN window and frozen into meta (live, train ≤ 2022: 69.5 / 11.2 / 1.12) — the rare class weighs ~62×.
- **Why a DIFFERENT gate**: the severe share TRIPLES over the era (6.1% → 19.4%) — reporting/mix drift, not a
  join artifact. A calibration gate on a temporal holdout would reject every honest model (exactly how site-2022
  died). So this gate measures **discrimination** — metrics that survive level drift:
  - **Fatal recall ≥ 0.5** (plugin): of the holdout's actual killed, how many did argmax catch? Live: 0.64.
  - **AUC(fatal) ≥ 0.8** (plugin, Mann-Whitney): the probability a random killed person ranks above a random
    non-killed one on the model's fatal score. 0.5 = coin flip. Live: 0.841.
  - **Overfit gap ≤ 0.05** (plugin): train-AUC − holdout-AUC. Live: 0.026.
  All three are set BELOW the methodology report's achieved ~0.6 / 0.85 — an honest model passes, a broken one
  cannot. Calibration is *deliberately absent*, and the card says so.
- **The decile-lift chart** (validate, view=chart): holdout persons sorted by the model's fatal probability,
  cut into tenths. Decile 1's bar ≈ 5 = the riskiest tenth contains 5× its share of actual deaths; the decay
  toward 0 IS the discrimination, visualized. A shuffled model draws a flat wall at 1.
- **severity_predict**: build a profile from the six dropdowns → the model's class distribution **relative to
  the holdout-era baseline shares**. Reading "הרוג פי 11.96": this profile's predicted fatal share is ~12× the
  population's — NOT "a 12% chance of dying." Unset fields stay honestly missing (the model's default path,
  never imputed). The framing line on every face is the methodology: *the model ranks risk profiles; it does
  not predict a person's fate.*
- **what_if**: one profile, one canned switch, ratio = p(scenario)/p(baseline) per class. Live anchors:
  belted→unbelted flips fatal ×1.38 and slight ×0.21 (mass moves UP the severity scale — read all three bars
  together); urban→interurban fatal ×1.92; fifty→ninety fatal ×1.29. The extra caveat is the second
  methodology lesson: **association, not intervention** — the model measures how outcomes differ across
  recorded circumstances, not what a policy change would cause.
- **severity_explain (P12)** — the model explains itself. Reading the beeswarm: rows are ordered by mean|φ|
  (importance, top = strongest); a "clean red-right" row (high values consistently pushing φ up, e.g. speed
  limit) is the textbook risk pattern; GREY rows are nominal codes — no color scale because their numbers
  carry no order (the source report colors everything; we refuse to fake it); HOLLOW dots are "לא ידוע" — a
  real model input, not missing data to hide (the safety row is ~⅔ hollow on live). x is the **softmax margin**
  of the chosen class (הרוג default, קשה selectable) — never probability units. Hover decodes the value via
  `code_lookups` ("אופנוע", not 8.0). `feature=<name>` flips to the dependence view — vertical spread at one
  value = interactions. `sample` trades speed for coverage (20k ≈ 7 s live end to end, full ≈ under a minute;
  both deterministic — the same seed, so repeated runs are identical). The predict/what_if charts carry a per-profile waterfall of the
  same φ (what_if shows Δφ between the scenarios — the switch's own contribution made visible); the parts sum
  to the margin exactly, and the action refuses to draw if they don't (the identity guard).

## 6. Experiments — a play curriculum

Each is a few clicks on the studio/severity tabs (or Layer 0). Expected outcomes stated so you can check.

1. **Break the gate on purpose** (site): train with `features=shuffled`, `train_until=2018` → validate →
   rejected, Spearman ≈ 0.2 → try `studio_deploy model_id=<that id>` → the refusal re-lists the reasons.
2. **Watch drift kill an honest model** (site): train `train_until=2022` → validate → rejected, כיול 1.35.
   Then read §5's gate design and ask: which site-gate metric would the severity family's drift have broken?
3. **The same two, severity**: `studio_train_severity features=shuffled` → validate → AUC ≈ 0.5, rejected.
   Then `train_until=2018` vs the default 2022 — compare gate metrics across a longer holdout (more drift
   inside the holdout window; watch what moves — recall/AUC hold up far better than any level metric would).
4. **Monotonicity probes** (severity_predict): fix a profile, flip ONE field at a time — does adding
   `ללא אמצעי בטיחות` raise the fatal ratio for a driver? For a pedestrian (where safety equipment is mostly
   meaningless)? Does `קשיש` vs `ילד עד גיל עשר` behave as the literature says? Where the model surprises you,
   that's either a data truth or a critique to raise — check the SQL and the feature's missingness first.
5. **Consistency check**: severity_predict with `time=לילה` minus the same profile with `time=יום` should agree
   in direction with what_if's `יום לעומת לילה` on the same profile (it's the same two model calls).
6. **Counts vs risk**: segment_rates road 60 (🟢 rate) vs hotspot_map road 60 observed (🟠 counts) — find a
   segment that is top-5 in counts but unremarkable per vkm. That contrast is the plugin's founding argument.
7. **Ranking honesty**: segment_rates with `order_by=rate` vs `order_by=rate_lo` — who enters/leaves the top-10?
8. **The triangulation**: before_after on `road:60/96.0-98.8` (double ratio 0.11) + site_ranking road 60
   (60/836 excess −2.0) — one intervention, two methods.
9. **Provenance drill**: open any answer's `הצג SQL`, paste the statement into chat ("run this SQL") — same
   numbers. The plugin's value is the rules baked into the SQL, not access.
10. **The ledger**: after a session of play, `ledger_list` — then `finding_card claim=...` on your best find.
11. **The composer's honesty rules** (P11, trends tab): compare urban vs non-urban killed → one shared axis,
    one shared 2009 band (the gap belongs to BOTH person series). Then killed vs slight_injured → it SPLITS
    (scale ratio ~72×). Then killed vs fatal_accidents — similar magnitudes, yet it still splits: the
    coverage rule outranks scale (the person series has the 2009 gap, the accident series does not). Force
    מאוחד and read the missing-periods note that replaces the band. That's the whole chart-honesty doctrine
    in three clicks.
12. **The drift, twice** (P11): `severity_profile by=year` (the severe share tripling as a picture), then
    composer-compare `severe_injured` vs `slight_injured` — watch slight collapse while severe grows. Ask:
    how much is the road and how much is the reporting? (§5's answer: enough of it is reporting that only a
    discrimination gate is honest.)
13. **Cross-examine the explanation** (P12): `severity_explain` on the deployed model, then the same with
    `severity_class=פצוע קשה` — which features trade places? Then pick play 4's most surprising
    severity_predict flip and look at its waterfall: WHICH feature carried the flip? Finally
    `feature=speed_limit_code` — is the dependence monotone, or does the spread at one value (interactions)
    explain the surprise? An explanation you can interrogate is the difference between SHAP and a poster.

## 7. Where the knobs live (for suggesting changes)

| You want to change… | It lives in… |
|---|---|
| Site gate thresholds / their source tags | `nl2sql_roadsafety/studio/constants.py` → `GATE` |
| Severity gate thresholds / era / features / xgb params | `nl2sql_roadsafety/studio/severity.py` → `GATE`, `ERA`, `FEATURES`, `XGB_PARAMS`, `PRESETS` |
| Profile dropdowns and their code mappings | `severity.py` → `PROFILE_FIELDS` |
| what_if's canned switches | `nl2sql_roadsafety/actions/what_if.py` → `SWITCHES` |
| Explain coloring policy / sample sizes / seed (P12) | `nl2sql_roadsafety/studio/explain_severity.py` → `ORDERED`, `SAMPLES`, `SAMPLE_SEED`, `MAX_DOTS` |
| EB shrinkage / intervals / site gate math | `nl2sql_roadsafety/studio/gate.py`, `predict.py` |
| Panel recipe (site features SQL) | `nl2sql_roadsafety/studio/panel.py` |
| Person-matrix recipe (severity SQL, sentinel→NULL rules) | `severity.py` → `matrix_sql` |
| Any caveat/card wording | the action module under `nl2sql_roadsafety/actions/` |
| Tab layout on the page | `web/src/tabs.js` (then `cd web; npm run build`) |
| Basemap fetch / zoom / bbox (P10) | `tools/fetch_basemap.py` (`--maxzoom`, `ISRAEL_BBOX`; `--assets-only`, `--sync-only`) |
| Map colors, GPU filters, site-layer looks (P10) | `web/src/components/map/layers.js` (+ `basemap.js` for the two styles) |
| Cloud cap / gazetteer size (P10) | `nl2sql_roadsafety/sqlkit.py` → `MAP_CLOUD_BOUNDS`, `GAZETTEER_LIMIT` |
| Golden series/join rules shared by everything | `nl2sql_roadsafety/sqlkit.py` |

Two contract warnings before proposing feature/SQL changes: the feature recipe is version-stamped
(`CONTRACT_VERSION`) — changing matrix/panel semantics must bump it, or stored models will be served on
mis-built features (the tripwire refuses); and thresholds carry source tags — a new threshold is a `כלל התוסף`
until the report backs it. Every change lands through the phase process: tests green (`..\app\.venv\Scripts\python -m pytest -q`),
page rebuilt if `web/src` changed, restart after backend changes (loaded modules don't reload).

## 8. The chat channel (M1) — reading answers through a co-pilot

`nl2sql_roadsafety/mcp/` exposes the same actions as twelve MCP tools (catalog: `docs/m1_design.md`). Three
things to know when you read a chat answer instead of the page:

- **The text IS the envelope.** Every chart-faced answer arrives as: title · basis · `מכנה: … [kind]` · model id
  when one is involved · caveats · the rows (first 60, the cap stated) · the CBS credit, plus the PNG twin as an
  image. `face=table` / `face=sql` / `face=card` pick the action's other views. Apply the five-step discipline
  of §1 exactly as on the page — the co-pilot summarizes, the envelope is the evidence.
- **State.** Chat runs write to the same shared data dir as the app (the ledger line per answered run, the
  `accidents/mcp_audit.jsonl` line per tool call, registry entries on a confirmed train). The seeded-stage rule
  of §0 applies: for consequence-free play register the server with `NL2SQL_CORE_DATA_DIR=<scratch>` in its env
  (Claude Code: `claude mcp add … -e NL2SQL_CORE_DATA_DIR=c:\tmp\rs-mcp-data …`). Train/deploy from chat always
  stops at a `# ⏸ נדרש אישור` card until the person says yes and the tool is called with `confirm=true`.
- **Transit.** Tool outputs (aggregates, PNGs) go to the LLM provider like any chat message; row-level faces
  (`map_scene`, individual accident points) are not exposed. The same transit the app's own chat tab
  has always had; the README states it plainly.

Debugging: run the server by hand — `..\app\.venv\Scripts\python -m nl2sql_roadsafety.mcp.server --db <path>`
talks the protocol on stdout (nothing else may print there; logs go to stderr). `tests/test_mcp_server.py`
launches exactly that subprocess.

### 8.1 The web channel (M3) — the same server from claude.ai in a browser

> Not part of this kit: the tunnel script was left out on purpose (no hosted or tunnelled server for this
> database — a CBS decision), and nothing below is needed for Claude Code or Claude Desktop. Kept for the record.

`tools\web_tunnel.ps1` opens a cloudflared quick tunnel to a local `roadsafety-mcp --transport http` and the
server carries its own OAuth login (`nl2sql_roadsafety/mcp/web.py`: a Hebrew page asking for a display name and
the shared passphrase). What changes for the reader of an answer: nothing — the same twelve tools, the same
envelope. What changes for state: every audit line now says `channel: web` and `user: <the login name>`, so a
ledger entry can be traced to the person who asked. Run demos with `-ScratchDataDir` (own ledger, own registry
copy) so the stage never drifts. The browser connector is a demo door for the plugin's owners; the participants'
browser-equivalent remains Claude Desktop (the bridge test of 2026-10-16 was negative — see `docs/mcp_acceptance.md`).

### 8.2 Reading a chat answer after M2

- **The legend (מקרא) under a table is part of the answer.** `people` is everyone involved including the uninjured
  (a coverage check), `killed` counts people, `fatal_accidents` counts events, `mu` is the model's expectation and
  `excess` the gap. A number quoted without its column is the one thing the 2026-09-25 session got wrong.
- **Names become keys through `roadsafety_find`.** "צומת העשור" → `njunction:433`; a street or a town → urban
  junction keys; a segment name → `road/seg` and the latest km range. Junction keys never carry model measures.
- **Training from chat.** In Claude Code the server itself puts a confirmation form in front of you — the model
  cannot answer it. In Desktop and claude.ai the model asks in the chat and the tool refuses without `confirm`.
  `--tools read-only` removes the studio from the catalog for automation or a shared server.
- **The web login** locks after five wrong passphrases per attempt and pauses everyone after thirty failures in
  ten minutes.
