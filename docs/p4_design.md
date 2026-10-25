<!-- P4 design record, saved 2026-08-30 from the approved plan (the design pass's full text lives in the session transcript; the plan below is the operative spec; this copy becomes the record at acceptance). -->

**As built (2026-09-01):** everything below shipped; the deviations are in `docs/plan.md`'s P4 row. Live pins
(`tests/test_live.py::test_studio_live_end_to_end`): panel 10,488 rows in 0.07 s; doc-11/2023 → **validated**
(Spearman 0.693, calibration 1.173, deviance ratio 0.816, α 0.161; 222 rounds; train ≈ 1.2 s end-to-end);
doc-11/2022 → **rejected on calibration 1.35** (kept as the honest governance artifact); shuffled/2018 → rejected at
Spearman 0.201 (the script's 0.21, reproduced); `site_ranking` national top = 60/850 (+39.7, significant), 20/13
(+38.5), 4/150 (+32.1); **60/836 = excess −2.0, rank 8 of 21 on road 60** (the demo decision: negative excess IS
beat 3's story); ranking 0.1 s, excess map ≈ 0.6 s. Suite 261 tests (fixture + the synthetic studio panel + live).
Wheel 0.4.0 with `studio/` installed on the clone for acceptance (17 actions, page mounted, headless DOM checks:
the header chip green with the model id, the models table with the Hebrew rejection reasons), then `-e` restored.
Shared data dir seeded through the running clone (2.5 s): deployed 2023 + the two rejections + the rehearsal
`before_after` entry (ledger 11 lines, ~10 KB; models ≈ 190 KB meta + 65–200 KB model each). Fixture round trip:
doc-11/2022 validates at 0.82/1.03/1.08 and shuffled fails at −0.2 — wide margins against xgboost float drift.

**Sweep (2026-09-01/02, 26 agents; the registry-ledger refuters and the envelope checker were lost to the spend
limit — those findings verified by hand, envelope re-checked inline):** 8 findings confirmed and ALL fixed.
(1) HIGH: `os.replace` raises WinError 5 against any concurrent reader on Windows — 98.9 % of `update_meta` calls
failed under 4 readers; plus three stacked defects: save()'s collision check was a TOCTOU, two concurrent deploys
left two "deployed" metas, `studio_validate` silently discarded a lost verdict. Fix: one module-wide registry RLock
around every read/write, bounded os.replace retry, atomic `registry.deploy()` (demote→pointer→status under the
lock), validate raises ActionError on a lost verdict; regression `test_registry_concurrency` (real threads).
(2) `contract_version` was write-only — `contract_check` now enforces it (missing = mismatch). (3) ledger's final
truncation fallback never re-checked the 4 KB cap — now shrinks `inputs` and re-checks. (4) `md.jsx` used a stateful
/g regex for `.test()` — the `<bdi>` Latin isolation was nondeterministic; fixed with an anchored non-global copy,
webdist rebuilt. (5) docs: the shape-code-9 story corrected (5 % is 2005–2007; 24 %→47 % is the 2011 jump).
Refuted: the ledger line-count "discrepancy" (the doc states the count at seeding time). Suite after fixes: 265.
# P4 — Studio: site model + registry + ledger (detailed plan)

## Context

P4 ships the governance tier: a **site model** (XGBoost `count:poisson` over the segment-year panel) trained,
validated against the report's gate, and deployed through a **registry** under `ctx.data_dir()/accidents/`; the
flagship **`site_ranking`** (excess = observed − μ, EB, NB 90 % intervals); **`hotspot_map color_by=excess`** flips
from its P3 fallback; the **ledger** (`ledger.jsonl` appended by the envelope on every answer/refusal) with
**`finding_card`** and **`ledger_list`**; the page's סטודיו / ממצאים tabs go live and the header's deployed-model
chip turns green. Version **0.4.0**, `[P4]`, `v0.4`. Data-dir state: shared default, **ending seeded** (one deployed
+ two rejected models + the rehearsal `before_after` ledger entry).

**Decisions (user, 2026-08-30):** install `[ml]` into the clone venv (`pip install -e "nl2sql-accidents-plugin[dev,ml]"`,
xgboost 3.4.1 + scipy ≈ 175 MB — native API only, no scikit-learn); panel = the **full 1,311 × 2017–2024 grid**
(median-filled ADT + `adt_known`); ledger logs **answers AND refusals** (never errors); demo keeps
**`road:60/96.0-98.8`** — negative excess IS the story (the 2017-treated site now sits below its model expectation,
excess −4; the map's red site on road 60 is 60/850 at +40) — the "excess top-10" criterion is re-worded to
"coherent in `site_ranking(road=60)`" and recorded as a deviation.

## Facts the design rests on (verified live, read-only, 2026-08-30 — design pass on DuckDB 1.5.0 + xgboost 3.4.1)

- **Feature columns (live `accidents`)**: `day_night_code` 5 = night; `road_type_code` 3 = at junction;
  `road_shape_code` 4/5 = slope/sharp curve BUT **9 = "אחר" is 57 % and climbed ~5 % (2005–2007) → 24 % (2010) →
  47 % (2011 — the coding discontinuity)**
  → `pct_curve` = codes (4,5) over rows with a specific shape code (1–8, 10, 11) only; `single_carriageway_code`
  1–4 vs `dual_carriageway_code` 1–5 are mutually exclusive on live → `pct_single_carr` from the coded rows;
  `road_surface_code` 2 = wet (1–6 coded); `speed_limit_code` 1..8 = 50..120 (0 unknown) → `speed_mix` = mean code.
  **The damage-only series carries ~0 % of these codings** — static attributes are averages over the CODED rows
  (both series feed `records`/`years_active`/`pct_night`/`pct_at_junction`; the card says so).
- **Panel** (full grid, `latest_segments × range(2016, 2025)` LEFT JOIN `units`, per-year as-of geometry where it
  exists, static latest vintage elsewhere; `lag()` over the grid — never over a range join; `a.year = u.year` kept):
  **10,488 rows = 1,311 × 8 in 0.07 s**; Σy per year 3,522…2,329 (total 24,520 = 19,865 as-of-matched + 4,655
  static-assigned); `adt_known` per year = the units counts (493→1,311); `lag1` never NULL (2016 feeds 2017); zero-y
  share 47.4 %. ADT fill = median over units ≤ train_until (≈ 17,262). Static attributes 0.10 s; 1,184/1,311 segments
  have history; 127 → all-NULL → xgboost `missing`.
- **The gate on live** (depth-2 params): `train_until=2023` → **validated** (Spearman 0.693, calibration 1.194,
  deviance ratio 0.808, α 0.117, 183 rounds, 0.43 s). `train_until=2022` → **rejected on calibration 1.35** (the
  model over-predicts the real 2023–24 casualty decline — trees don't extrapolate; a genuinely instructive
  rejection). 2020 validates; 2019/2021 reject. → **default `train_until = 2023`** (range 2018–2023), and the seeded
  registry holds deployed `doc-11/2023` + rejected `shuffled/2018` (Spearman ≈ −0.19) + rejected `doc-11/2022`
  (the honest governance beat: a real model, rejected for a real reason). Deviation from plan.md's 2022 recorded.
- **Excess-mode observed ≠ `segment_rates`**: the panel assigns 4,655 more accidents 2017–2023 (segment-years
  without an as-of row, on the static geometry). In excess mode the observed column IS the panel's (else the excess
  is biased); a leading caveat states the difference count for the scope shown.
- **Platform**: `ctx.data_dir()` is the SHARED dir (`%LOCALAPPDATA%\nl2sql-core`); `NL2SQL_CORE_DATA_DIR` only
  before the first resolve (the app resolves at import) → the move test is a subprocess. 40-thread pool, fresh
  Context per request, no request timeout → atomic writes (`tmp + os.replace`) and a `threading.Lock` on the ledger
  append. `about` already reads `accidents/models/site/deployed.json → model_id`; the header chip auto-greens.
  xgboost native API only (`xgb.train`/`Booster`/`DMatrix`; `DMatrix` accepts list-of-tuples; NaN = missing;
  `save_raw("ubj")` round-trips with feature names; `pred_contribs` bias includes base_margin — P5). Timings:
  train ≈ 0.5 s, `studio_train_site` end-to-end ≈ 1.5 s, `site_ranking` ≈ 0.7 s, model.ubj ≈ 110 KB.

## Files

```
nl2sql_accidents/studio/__init__.py         empty; nothing imports xgboost at module level
nl2sql_accidents/studio/constants.py        FEATURES (doc-11), STATIC_FEATURES, PRESETS {doc-11, shuffled}, PANEL_YEARS (2017, 2024),
                                            LAG_FEED_YEAR 2016, HISTORY_START 2005, TRAIN_UNTIL (2018, 2023), TRAIN_UNTIL_DEFAULT 2023,
                                            XGB_PARAMS (count:poisson, max_depth 2, eta 0.05, min_child_weight 5, reg_lambda 1,
                                            subsample .8, colsample .8), MAX_ROUNDS 1000, EARLY_STOP 30,
                                            GATE {spearman_min (0.3, report), calibration ((0.75, 1.25), report),
                                            deviance_ratio_max (1.5, plugin)}, Z90 1.6449, ML_EXTRA_CMD, CONTRACT_VERSION 1
nl2sql_accidents/studio/panel.py            adt_median_sql, panel_sql(y0, until, adt_fill), static_attrs_sql(train_until),
                                            fetch_panel/fetch_static/matrix/shuffle_target (sha256-ordered permutation)/panel_summary
nl2sql_accidents/studio/model.py            require_xgboost() → ActionError(ML_EXTRA_CMD); train(X, y, years, train_until, seed) →
                                            (raw_ubj, best_rounds, inner_dev): inner fold = year == train_until, early stop 30, refit
                                            on ≤ train_until with best+1 rounds; predict(raw_ubj, X)
nl2sql_accidents/studio/gate.py             spearman (ties → average ranks), poisson_deviance_mean (y=0 term 0, μ floored 1e-9),
                                            alpha_moments (max(0, (Σ(y−μ)²/μ − n)/Σμ)), calibration, evaluate, verdict → reasons
                                            (Hebrew, no ";"), nb_interval (Var = Σ(μₜ + α·μₜ²), μ ∓ 1.6449·√Var, lo ≥ 0), eb (w = 1/(1+α·μ))
nl2sql_accidents/studio/registry.py         root/model_dir/new_model_id (site-{tu}-{preset}-s{seed}-{ts}); write_json_atomic
                                            (tmp + fsync + os.replace); save/read_meta/update_meta/model_bytes; list_models (tolerant:
                                            unreadable → status "unreadable"); deployed(ctx) → dict|None; set_deployed; resolve_id("latest")
nl2sql_accidents/studio/ledger.py           append(ctx, entry) (Lock, one write, ensure_ascii=False, newline "\n"); read(ctx, last_n)
                                            (bad lines skipped + counted); entry_for(action, inputs, result); numbers_of (whitelisted
                                            spec scalars, capped 4 KB, never png/rows)
nl2sql_accidents/studio/predict.py          expected_by_segment(ctx, meta, y0, y1, road) → {(road, seg): {observed, ksi, mu, mu_by_year,
                                            excess, eb, lo90, hi90, significant, years_known}} — rebuilds features FROM THE CONTRACT
                                            (meta's adt_fill + frozen static_attrs + panel_sql); shared by site_ranking and hotspot_map
nl2sql_accidents/actions/{studio_train_site, studio_validate, studio_deploy, studio_models, site_ranking, ledger_list, finding_card}.py
nl2sql_accidents/envelope.py                guard(title, *, ledger=True): after a successful Result or a Refusal card, append the ledger
                                            entry (never on ActionError/crash; the append itself never raises); finding_card's card built here
nl2sql_accidents/actions/about.py           _deployed → registry.deployed(); actions line lists 17
nl2sql_accidents/actions/hotspot_map.py     the excess wiring (below)
nl2sql_accidents/charts.py                  map_png gains per-unit "color" (default teal)
tests/studio_fixture.py + studio_ctx        deterministic synthetic DB (LCG seed 20260830): 60 segments × 2016–2024, planted rates
                                            λ = f(adt, night, junction) with a 2020 dip; 15 segments never as-of; drop_after= for leakage
tests/test_studio.py · test_ledger.py · test_site_ranking.py · contract/about/live additions
web/src/tabs.js · MapView.jsx · Answer.jsx · App.jsx · package.json 0.4.0 → npm run build → webdist/
pyproject.toml 0.4.0 + packages += "nl2sql_accidents.studio" · __init__.py 17 actions
docs/p4_design.md (the design pass, saved) · docs/plan.md · README · CLAUDE.md · PITFALLS.md · PLAN_1/PLAN_2 corrections · docs/demo/sites.md
```

## The seven actions

| action · label | inputs | views / faces | refusals · errors |
|---|---|---|---|
| `studio_train_site` · אימון מודל אתר | `train_until` num 2023 (2018–2023) · `features` choice doc-11\|shuffled · `seed` num 42 · `view` markdown\|table | card: `# מודל מועמד <id>`, panel summary (rows, Σy, adt_known share, static-assigned, ADT fill, segments with history), rounds/inner deviance/seconds, "סטטוס: candidate — הריצו studio_validate"; table = per-year panel summary; `spec.sql` = the panel SQL | train_until out of range → Refusal; xgboost missing → error with `ML_EXTRA_CMD`; bad preset → ActionError |
| `studio_validate` · אימות מודל | `model_id` text "latest" · `view` markdown\|chart\|table | gate card: each metric vs its threshold with the source tag (דו״ח / כלל התוסף), verdict + reasons, α; chart = calibration by μ-decile via `hbars` (bars Σobs, markers Σμ); table = holdout rows; meta.status → validated\|rejected | unknown id → Refusal listing ids |
| `studio_deploy` · פריסת מודל | `model_id` text "latest" (newest validated) | answer card `# נפרס <id>` + gate summary; writes `deployed.json` atomically | rejected → Refusal re-listing the reasons (THE governance beat); candidate → Refusal "טרם אומת"; deployed → idempotent |
| `studio_models` · רישום מודלים | `family` choice site | table: model_id, status, deployed ✓, created_at, train_until, preset, seed, sizes, metrics, α, reasons | empty registry → refusal card pointing to studio_train_site |
| `site_ranking` · דירוג אתרים לפי עודף | `road` num 0 · `from_year` 2019 · `to_year` 2024 (2017–2024) · `top_n` 30 (1–200) · `view` chart\|table\|sql | rows: road, seg, names, km, observed, ksi_observed, mu, excess, eb, lo90, hi90, significant, years_known, site_key, rank (by excess); chart = `hbars` (bars μ, whiskers lo/hi, markers observed, annot ±excess); denominator **exposure** "ציפייה מודלית ממודל אתר פרוס <id> …"; `spec.sql` = the panel SQL for the range | no deployment → Refusal → סטודיו; years outside 2017–2024 → Refusal; xgboost missing → error. **`severity` input dropped** (μ targets all casualty accidents; KSI is a column) — deviation recorded |
| `ledger_list` · פנקס ממצאים | `last_n` num 20 | table: idx, ts, action, shape, title, headline, inputs (JSON), version; corrupt lines counted in the note | empty ledger → refusal card |
| `finding_card` · כרטיס ממצא | `entry` text "latest" (or an idx) · `claim` text "" | answer card: `# ממצא` (claim) · `# ראיות` (the numbers) · `# הסתייגויות` · `# שחזור` (action, inputs JSON, version, ts) · credit | unknown idx / empty → Refusal |

**Ledger entry** (one line, ≤ 4 KB): `{ts, action, db?, inputs, kind, shape (chart|table|sql|answer|refusal|route),
title, headline (basis | first body line), denominator, numbers (basis, n_rows, top row ≤16 cells + whitelisted spec
scalars: gate, metrics, model_id, alpha, counts, double, coverage totals, tiers, map…), caveats, plugin_version}`.
Appended by `guard` for answers AND refusal cards; never for errors; `about`/`ledger_list`/`finding_card` use
`guard(..., ledger=False)`. The data-dir test becomes: the file set is exactly `{fixture db, accidents/ledger.jsonl}`.

**Registry**: `accidents/models/site/<model_id>/{model.ubj, meta.json}` + `accidents/models/site/deployed.json`
(`{family, model_id, deployed_at, plugin_version, train_until, preset, alpha}` — `about` reads `model_id`, unchanged).
`meta.json` = the full contract: features, target, panel numbers, `adt_fill` (value + rule), the three SQL texts,
**frozen static_attrs rows**, params, rounds, gate {metrics, thresholds, sources, reasons, verdict}, α, status,
created_at, versions. All writes atomic; all readers tolerant.

**`hotspot_map` excess wiring**: at the P4 hook — `color_by == "excess"` and `unit == "segments"` and
`registry.deployed(ctx)` → clip `y0e = max(y0, 2017)` (caveat when clipped), observed from the panel statement over
all keys, μ/excess/eb/lo90/hi90 from `predict.expected_by_segment`, sort by excess, cut to top_n, re-rank;
`effective = "excess"`, denominator exposure with the model id, caveats: the observed-difference count vs
`segment_rates`, the formula line (excess/EB/α/NB), the model line (id, train_until, Spearman, כיול · מתאם ולא
סיבתיות); PNG twin colours per unit (diverging), geojson unit properties gain mu/excess/eb/lo90/hi90/significant;
any predict failure (incl. missing xgboost) → the P3 observed fallback + a caveat, never an error. Junctions keep
the P3 fallback.

**Page**: `tabs.js` — hotspots = [segment_rates, site_ranking, hotspot_map], studio = [studio_models,
studio_train_site, studio_validate, studio_deploy], findings = [ledger_list, finding_card] (empty texts dropped —
refusal cards are the empty state); `MapView.jsx` excess mode: diverging fill (blue below / red above, 5 bins over
±max|excess|), radius still by observed, dark ring on significant, popup rows for צפוי/excess/EB/רווח 90%/מובהק,
legend "עודף תאונות לעומת מודל האתר…"; `Answer.jsx` NO_GROUP += train_until|seed|rounds|best|n_train|n_holdout|idx;
`App.jsx`: after a studio action completes, re-run `about` so the header chip flips live. Version 0.4.0 + rebuild.

## Fixture & tests (numbers from the design pass, reproduced with xgboost on the synthetic panel)

`tests/studio_fixture.py` (own DDL = conftest's + the five live coding columns): 60 segments × 2016–2024,
deterministic LCG + Knuth Poisson, planted λ = adt/6000 · (1 + 1.5·night) · (1 + 0.5·junction) · (0.8 in 2020);
15 segments never have as-of rows (static + `adt_known=0`), one overlapping vintage, damage-only rows with
live-like uncoded values; `drop_after=y` for the leakage test. Panel 480 rows; doc-11/2022 → **validated**
(Spearman 0.82, calibration 1.02, ratio 1.26, α 0.05); shuffled/2018 → **rejected** (Spearman −0.21).

Tests: panel shape/lag/zero-years/SQL-text guards · static-attrs leakage (full DB == drop_after, byte-equal) ·
shuffle determinism · gate math worked examples (ρ 0.778/1.0/0, deviance 0.716, α 1.607/0, NB/EB example) ·
train→validate→deploy→rank round trip (deploy refuses rejected AND candidate; about + header line; site_ranking
refuses before, ranks after; `view=sql` re-runs) · hotspot excess mode (effective, columns, geojson, badge,
fallback when xgboost is monkeypatched away) · `[ml]`-missing readable error for the three ML actions ·
registry atomic/tolerant (garbled meta → "unreadable"; P1-shape deployed.json) · ledger round trip (3 appends for
answer/answer/refusal, none for about/error; JSON-valid, < 4 KB, no png; ledger_list idx; finding_card shape;
corrupt line skipped) · data-dir move (two subprocesses with `NL2SQL_CORE_DATA_DIR`, rename between; nothing under
the real %LOCALAPPDATA%) · contract lists (17 names/labels, views, version 0.4.0, token-scan still envelope-only,
the data-dir whitelist gains the ledger) · live smoke (panel 10,488 + per-year Σy; doc-11/2023 validated ≈
0.693/1.194/0.808/α 0.117 — pinned after the first run; doc-11/2022 rejected on calibration; `site_ranking(road=60,
2019–2024)` top = 60/850, and **60/836 shows negative excess** — the demo assertion; timings printed).

## Steps (from `accidents-lab\`)

0. Save `docs/p4_design.md` (the design pass); pre-flight (tree clean at v0.3, port 8000, `git -C app status`);
   `app\.venv\Scripts\python -m pip install -e "nl2sql-accidents-plugin[dev,ml]"` (record versions + size).
1. `studio/constants.py` + `panel.py` + `gate.py` + `studio_fixture.py` → tests 1–4 (no xgboost) red → green.
2. `registry.py` + `ledger.py` + `envelope.guard(ledger=)` + `about` → registry/ledger/contract tests
   (the data-dir test gains the ledger file).
3. `model.py` + `predict.py` + the five studio/site actions + triage routes (studio/ranking keywords) → the round
   trip, `[ml]`-missing, move-test, live smoke.
4. `hotspot_map` excess wiring + `charts.map_png(color)` → the excess tests.
5. Page (`tabs.js`, `MapView`, `Answer`, `App`, 0.4.0) → `npm run build` → headless checks (`?tab=studio&run=studio_models`,
   `?tab=hotspots&run=hotspot_map` with a deployment: excess legend + markers; the refusal card on findings when empty).
6. Wheel sanity (delete `build\` first; namelist has `studio/`); wheel install acceptance + restore `-e`.
7. **Ultracode sweep** (I ask you before launching, as in P3): panel SQL vs golden rules (never traffic_adt_filled,
   leakage, year equality), gate/α/NB arithmetic recomputed, registry/ledger concurrency + tolerance, the page
   contract, caveats/docs vs code.
8. Seed the shared data dir through the running clone: train/validate/deploy doc-11/2023; train/validate shuffled/2018
   (rejected); train/validate doc-11/2022 (rejected); run the rehearsal `before_after` (the ledger entry); verify
   `about`/header/map excess on the clone; timings recorded.
9. Docs: `docs/plan.md` (P4 row + deviations: train_until 2023 default with the 2022-rejection story, depth-2 params,
   `severity` dropped from site_ranking, `road` added, panel-observed rule, the demo-site criterion re-worded),
   README ([ml] install + 3.12+ note + ledger growth note), CLAUDE.md (studio facts), PITFALLS (road_shape 2011 coding
   jump; the 2022 calibration rejection; damage-only coding gap in static attrs; anything that bites), PLAN_1/PLAN_2
   corrections, `docs/demo/sites.md` final header.
10. Recap → on your acceptance: `[P4] studio: site model, registry, site_ranking, excess map, ledger` + tag `v0.4`.

## Acceptance
- [ ] Suite green (fixture + studio fixture + live incl. the studio smoke) with `[ml]` installed; wheel namelist has `studio/`.
- [ ] On the clone: train→validate→deploy→rank end-to-end with timings; `studio_deploy(rejected)` refuses re-listing reasons;
      `site_ranking` refuses on an empty registry; the map colors by excess with the model caveats; the header chip is green;
      ממצאים shows the ledger and `finding_card` renders the rehearsal entry; Layer 0 renders all 17 actions.
- [ ] Shared data dir ends seeded (deployed doc-11/2023 + rejected shuffled/2018 + rejected doc-11/2022 + the rehearsal ledger entry);
      nothing else new at the data-dir root; `git -C app status` clean; no artifacts/data in the repo.
- [ ] Ultracode sweep run (with your go); confirmed findings fixed. `[P4]` + `v0.4` after acceptance.

## Risks / pitfall watch
DuckDB 1.5.0 binder (year equality everywhere; `lag()` only over the grid CTE — verified); the 2022 calibration
rejection is a feature, not a bug (say it in the card); observed-vs-segment_rates difference carried as a caveat with
the count; concurrency (atomic replace, ledger Lock, Booster-from-bytes per request); `packages` must list the studio
subpackage; xgboost determinism across versions (pin live metrics with tolerance; fixture margins are wide);
`requires-python` 3.11 vs xgboost's 3.12 (README note); ledger growth ~1 KB/run (append-only, tolerant reader, README);
never `traffic_adt_filled`; no model artifacts or CBS data in the repo; the seeded shared dir is the stage state
(NL2SQL_CORE_DATA_DIR never set on stage).

