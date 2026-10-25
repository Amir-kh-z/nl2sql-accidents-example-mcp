# P5 — Stretch: `studio_explain` (TreeSHAP) + `two_wheelers` (detailed plan)

## Context

P4 (`v0.4`, commit `c25e903`) shipped the studio; P5 is the stretch phase — plan.md §P5 says "cut freely, in this
order". **Your cut (2026-09-02): items 1+2 — `studio_explain` + `two_wheelers`; the severity model cycle and
`what_if` are CUT** (recorded as a deviation in plan.md's P5 row). ~1 day, keeping P6 (demo hardening) on schedule.
Version **0.5.0**, commit `[P5]`, tag `v0.5`. Data-dir state: shared, seeded from P4, unchanged.

What each buys the demo: `studio_explain` answers "WHY is 60/850's expectation what it is" on the deployed model —
an optional beat-2/5b extension; `two_wheelers` answers the audience's "מה עם אופנועים?" with a real fleet
denominator and an honest "floor of the truth" caveat.

**Constraint note:** the monthly spend limit currently blocks all agent launches. Design and build run solo; the
end-of-phase sweep question still gets asked — if credits are still unavailable then, verification is inline
(the P2/P4 fallback pattern).

## Facts the design rests on (verified read-only, 2026-09-02)

- `v_motorcycle_accident_rate` (877 rows): grain = `accident_year × engine_cc_band(_code) × manufacture_year`,
  columns `active_fleet, in_accidents, in_fatal, accidents_per_1000_active`; 2013+ (cc bands era-scoped). Aggregate
  per (accident_year, band): `Σin_accidents / Σactive_fleet × 1000` (each manufacture_year row is a distinct cohort
  → the sum IS the total active fleet). Bands ≤50/51–125/126–400/401+ (codes 8/9/10/19).
- Bicycles/e-scooters: `vehicle_type_code` 15 = bicycle, 21–23 = אופניים חשמליים / קורקינט ממונע / קורקינט חשמלי
  (dossier: "docs vary — resolve via `code_lookups`", key (code_table, code, year, field)). Counts only — no
  denominator exists.
- Envelope denominator kinds: `exposure` (green) fits the fleet rate with an explicit not-VKT label; the
  bicycle/e-scooter rows carry the counts-only caveat.
- `charts.py` has `hbars`/`line_chart` (single series) — needs a `multi_lines` (per-band rates) and a two-panel
  `explain_png` (the `map_png` landscape-composite precedent).
- SHAP: P0 Spike C proved `pred_contribs=True` sums to the margin; p4_design notes the bias column includes
  base_margin. For `count:poisson` the margin is **log μ** → the exact-sum identity is `Σφ_row ≈ ln μ_row`.
- `predict.contract_check` (P4, now version-enforcing) and `panel.matrix` are reused as-is; per-site rows are a
  key filter over the panel exactly as `predict.expected_by_segment` does for a road.

## Files

```
nl2sql_accidents/studio/explain.py         SHAP mechanics: contribs → per-site per-year φ table, top-5 by mean|φ|,
                                           global mean|φ|; the exact-sum identity helper (log scale)
nl2sql_accidents/studio/model.py           + contribs(raw, X): fresh Booster from bytes, DMatrix, pred_contribs=True
nl2sql_accidents/studio/constants.py       + FEATURE_LABELS_HE (Hebrew, digit-free — envelope rule) for legends
nl2sql_accidents/actions/studio_explain.py the action (thin, like the other studio actions)
nl2sql_accidents/actions/two_wheelers.py   the action + its SQL over v_motorcycle_accident_rate + the counts query
nl2sql_accidents/actions/triage.py         routes: הסבר/למה/explain/SHAP → studio_explain; אופנוע/דו-גלגלי/אופניים/
                                           קורקינט → two_wheelers (P2's false-positive discipline); the curated
                                           ALL_ACTIONS fallback list gains two_wheelers (12 actions — NOT all 19)
nl2sql_accidents/charts.py                 + multi_lines (one line per band) + explain_png (left φ-lines per top-5
                                           feature over years; right observed bars vs μ line per year)
nl2sql_accidents/__init__.py               19 actions (two_wheelers after vehicle_cells; studio_explain after
                                           studio_deploy), __version__ 0.5.0
web/src/tabs.js                            חומרה tab += two_wheelers; studio tab += studio_explain
web/ + webdist/                            version 0.5.0, npm run build
pyproject.toml · web/package.json          0.5.0
tests/test_explain.py · test_two_wheelers.py · conftest.py (fixture DDL: the view's base shape + code_lookups rows)
tests/test_contract.py · test_live.py      19 names/labels, CHART_ACTIONS/VIEW_RUNS additions, version, live pins
docs/p5_design.md · docs/plan.md P5 row · README · CLAUDE.md · PITFALLS.md (as they happen)
```

## The two actions

| | `studio_explain` · הסבר מודל אתר | `two_wheelers` · דו-גלגלי |
|---|---|---|
| inputs | `site` text "" (empty = the GLOBAL mean-abs-φ profile; a `road:n/km-km` key = the per-site profile) · `model_id` text "deployed" (also accepts explicit ids incl. rejected ones — explaining a rejection is legitimate diagnostics, the card says the status) · `view` chart\|table\|sql | `metric` choice תאונות\|קטלניות (in_accidents / in_fatal) · `from_year` num 2019 (min 2013) · `to_year` num 2024 · `view` chart\|table\|sql |
| answer | site: per-year φ for the top-5 features by mean\|φ\| + observed/μ panel (`explain_png`); global: `hbars` mean\|φ\|; table = per-year rows [year, observed, mu, φ…, bias] or per-feature [feature, mean_abs_phi, mean_phi]; sql = the meta's panel SQL | chart = `multi_lines` rate per 1,000 active fleet per band per year; table = [year, band, accidents, fatal, active_fleet, rate] + bicycle/e-scooter count rows labelled ספירה בלבד; sql shown |
| denominator | exposure — "ציפייה מודלית ממודל אתר <id>" (the site face); na for global | exposure — "פר אלף כלי רכב רשומים פעילים (מצבת) — אין נסועה לדו-גלגלי" |
| caveats | φ on the log-rate scale (Σφ = ln μ); מתאם ולא סיבתיות; correlated features read as a group (adt·lag1); model id · train_until · status; the casualty-coded statics note | fleet ≠ travel (no VKT); solo falls under-reported — רצפת האמת; cc bands 2013+; bicycles/e-scooters counts only (codes from code_lookups); every number computed for the selected scope |
| refusals | model_id="deployed" with nothing deployed (→ studio); unknown id (lists ids); junction site key (the model covers segments only); site absent from the panel; `contract_check` refusals inherited | from_year < 2013 (era rule); empty year range; wrong connection (guard probe, as everywhere) |
| errors | `[ml]` missing → the exact pip command (`model.require_xgboost`) | none ML-related (pure SQL) |
| ledger | logged (default guard) | logged (default guard) |

## Tests

- `test_explain.py` (fixture, xgboost importorskip): **exact-sum identity** — every φ row sums to ln μ within 1e-4;
  top-5 selection deterministic; global face shape; refusal without deployment / unknown id / junction key;
  ml-missing readable; the card carries the log-scale caveat.
- `test_two_wheelers.py`: fixture plants a small motorcycle-rate base (2 bands × 3 years, known rates) + bicycle
  rows + `code_lookups` entries → rate arithmetic pinned; era refusal (2012); counts-only rows present; caveat
  numbers move with scope.
- `test_contract.py`: 19 names/labels/views, version 0.5.0, token-scan covers the new files, VIEW_RUNS additions.
- `test_live.py`: view pins (877 rows; one aggregate recomputed); `studio_explain` on the deployed model for
  60/850 — runs, adt/lag1 among the top features, identity holds on live; timings printed.
- Full suite green (`app\.venv\Scripts\python -m pytest -q` from the plugin repo; 265 + new).

## Steps (from `accidents-lab\`)

0. Save `docs/p5_design.md`; pre-flight (tree clean at v0.4, app runs, `git -C app status` clean). Build-start
   inspections (read-only): the view's definition (`duckdb_views()`), `code_lookups` labels for 15/21/22/23.
1. `studio/explain.py` + `model.contribs` + `constants.FEATURE_LABELS_HE` + `charts.explain_png` → the action +
   triage routes → tests red → green.
2. `two_wheelers` (+ fixture DDL) + `charts.multi_lines` → tests.
3. Page: tabs.js, 0.5.0 everywhere, `npm run build`, restart, headless DOM checks (studio tab shows explain;
   חומרה shows two_wheelers; 19 actions on Layer 0, `problems: []`).
4. Wheel sanity (delete `build\` first; namelist: no leaks, fresh bundle) + wheel-install acceptance on the clone,
   then `-e` restored.
5. **Sweep question** (I ask you before launching, as always): SHAP arithmetic vs the identity, the two SQL
   statements vs the golden rules/era rules, caveat numbers, page contract, docs vs code. If the spend limit still
   blocks agents → inline verification, recorded as such.
6. Docs (plan.md P5 row + the severity/what_if CUT deviation, README 19 actions, CLAUDE.md facts, PITFALLS) →
   recap with exact commands → on your acceptance: `[P5] stretch: studio_explain (TreeSHAP) + two_wheelers`
   + tag `v0.5`.

## Acceptance

- [ ] Suite green incl. the two live smokes; wheel namelist clean.
- [ ] On the clone: `studio_explain` renders the site profile for the demo sites and the global profile; refuses
      without a deployment; `two_wheelers` renders rates by band with the fleet badge and the bicycle count rows;
      both appear on their tabs and on Layer 0 (19 actions); ledger grows by the runs.
- [ ] `git -C app status` clean; no data/artifacts in the repo; CBS credit everywhere.
- [ ] Sweep run or inline-verified (with your go); `[P5]` + `v0.5` only after your acceptance word.

## Risks / pitfall watch

xgboost `pred_contribs` output shape (n_features+1, bias last — includes base_margin; assert the identity, don't
assume); Hebrew feature labels must be digit-free (envelope rule) yet unambiguous; the view's `in_accidents`
semantics verified against its definition before trusting (record in p5_design); triage keyword false positives
(P2 lesson); `code_lookups` label drift across years (resolve at the latest year); new ACTIONS need an app restart;
delete `build\` before the wheel; the ledger on the shared dir grows during clone verification (fine — append-only).

## Build-start facts (2026-09-02, read-only inspection)

- `v_motorcycle_accident_rate` definition verified golden-rule compliant (`case_type_code = 1`, composite-key join,
  2013+, codes 8/9/10/19; fatal = `severity_code = 1`). BUT its fleet CTE inner-joins per (band, manufacture_year)
  cohort — summing its `active_fleet` per (year, band) undercounts the true fleet (zero-accident cohorts drop out).
  `two_wheelers` therefore computes numerator (vehicles ⋈ accidents, same discipline) and denominator
  (`fleet_motorcycles` full sum per band) DIRECTLY; the view stays as a cross-check pin at cohort grain.
- `fleet_motorcycles` (10,858 rows) is a per-MODEL CURRENT snapshot (make/model/manufacture_year/band/fuel/active
  — no year column). The denominator is the current active fleet; cross-year comparisons lean on fleet stability —
  said in a caveat (the curated view has the same semantics).
- `code_lookups` key: (code_table INT, code, year, field, label_he). vehicle_type_code labels (2024): 8 אופנוע עד
  50 · 9 אופנוע 51–125 · 10 אופנוע 126–400 · 19 אופנוע 401+ · 15 אופניים · 21 קורקינט חשמלי · 22 קלנועית חשמלית ·
  23 אופניים חשמליים. **22 is a mobility scooter, not a two-wheeler → EXCLUDED** (the "docs vary" resolution);
  count rows = 15, 23, 21. Live involvement counts (casualty series): 15 → 5,951 (2005+), 23 → 4,191, 21 → 1,532,
  22 → 400 (2013+).

## As built (2026-09-02)

Both actions shipped as planned; deviations: the P4 `deployed_ctx` pattern reused per-file; `make_spec` derives
`renderer` at build time so a post-attach PNG must set it too (fixed in both new actions); the live identity bound
on the TABLE face is 0.25 (top-5 + bias only — the exact 1e-4 identity is pinned on the full φ rows); band labels
carry digits legitimately (the no-digit rule covers Input labels and Result.title). Live pins: explain site 0.2 s,
global contribs over 10,488 rows ~0.5 s, adt_asof/lag1 among the top-5 at 60/850; two_wheelers 877-row view parity
at cohort grain, full fleet > 100k, 24 grid rows for 2019–2024. Suite 283 (265 + 18 new). Wheel 0.5.0 (44 files,
studio/explain.py + both actions + bundle index-D-inDmsd.js, no leaks) verified on the clone (19 actions,
problems: [], both tabs render headless with zero errors), then `-e` restored. The shared data dir was found
CONTAMINATED by the P4 sweep's port-8000 traffic (3 stray models, ledger 11→57) — restored to the accepted stage
state + PITFALLS entry + the PLAN_2 pre-flight row now demands re-verification.

## Sweep (2026-09-02, 14 agents, run wf_5171b2f9-3c8)

Port 8000 declared off-limits after the P4 contamination — the stage state verified byte-identical before/after.
6 confirmed findings (0 refuted), ALL fixed: (1) MEDIUM the English make/model refusal (`\bmodel\b`) swallowed
P5's own phrasings ("explain the site model") — explain-intent wording now bypasses the refusal into the routes
(the beat-4 refusal untouched); (2) MEDIUM `two_wheelers view=sql` exposed only the grid statement while 4 of 16
rows came from `counts_sql` — the sql face now carries both (the trap.py precedent); (3) LOW `check_identity` was
a "runtime guard" that never ran and had a dead `tol` — now enforced by the action on every run (ActionError over
`IDENTITY_TOL = 1e-3`, both faces); (4) LOW the unanchored `הסבר` stem routed הסברה (advocacy) questions to
TreeSHAP — anchored `הסבר(?![הות])`; (5)+(6) LOW doc corrections (the three unrecorded as-built deviations added
to plan.md; "ALL_ACTIONS 19" corrected — it is the curated 12-action fallback). Regression tests added for 1–4.
