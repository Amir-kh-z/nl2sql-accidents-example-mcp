# P9 — Predictions front and center (visibility pass + the severity model & what_if)

## Context

Reviewing the live app (2026-09-03), the instructor asked: "where are the predictions? I see descriptive
analysis." The model layer EXISTS (site_ranking's צפוי column IS a per-site prediction; studio_validate predicts
a held-out year; studio_explain decomposes a site's prediction) but the UI never says the word. Decision (user):
**(a)** make the predictions unmissable, **(b)** revive the P5-cut severity model cycle + what_if — real
"heavy ML" with its own governance. Version **0.9.0**, commit `[P9]`, tag `v0.9`. The CHANGELOG v0.8 block
(accepted after the last commit) rides this phase's docs.

## Track A — the visibility pass (~½ day)

1. **A generic "prediction chip"**: Answer.jsx — any chart spec carrying `model_id` renders a small strip above
   the face: `🔮 תחזית המודל <id> — צפוי מול נצפה` (auto-covers site_ranking, the excess map, studio_explain,
   studio_validate, and the future severity actions with zero per-action work).
2. **Wording**: site_ranking chart title/xlabel gain "תחזית המודל מול מה שקרה בפועל"; the hotspot excess legend
   says "עודף מעל תחזית המודל"; studio_explain's label becomes `תחזית והסבר לאתר · studio_explain` (a rename —
   test_contract LABELS + tabs + DEMO.md updated).
3. **The per-site prediction card**: `studio_explain` gains `view=markdown` — a card for one segment:
   `# תחזית המודל לאתר <road>/<seg>` · "המודל חוזה X תאונות בטווח (lo–hi 90%), בפועל Y — עודף Z" · the top-3
   drivers in words (from mean|φ|) · the gate line (Spearman/כיול) · the standing caveats. Answers "predict for
   THIS place" in one sentence. Triage routes `תחזית` → studio_explain.
4. DEMO.md beats 2/5b re-worded to SAY "prediction" (the audience-facing framing the instructor was missing).

## Track B — the severity model + what_if (~2–3 days; the P5 cut, now revived)

Design anchors (from the original concept map §4.3, to be confirmed/refined by the exploration report):
person-level rows (`v_casualty_involved` 2010–2024, injury_severity 1–3) with an accidents join for the crash
context (composite key!); XGBoost `multi:softprob`, class weights 1/share (the report's rule, no SMOTE);
**its own plugin-labelled gate**: fatal recall ≥ 0.5, AUC(fatal) ≥ 0.8, and a no-overfit check — deliberately
BELOW the report's achieved 0.6/0.85 so a real trained model can pass while a broken one cannot; registry family
`"severity"` beside `"site"`; **relative probabilities only** on every face (the model ranks risk profiles, it
does not predict an individual's fate — said on every card).

Actions (4 new → 23 total):
- `studio_train_severity` (train_until, features preset, seed) — candidate into `accidents/models/severity/`.
- `studio_validate_severity` — the gate card + a reliability/per-class face; validated/rejected with reasons.
- `severity_predict` — a profile → the predicted severity DISTRIBUTION vs the population baseline (relative),
  with the honest framing.
- `what_if` — TWO scenarios (baseline vs changed field(s)) → relative deltas of the severity distribution;
  refuses without a deployed severity model.

### Grounded design (exploration verified live, 2026-09-03)

**Data**: person grain = `v_casualty_involved` (= `involved` + case filter), key (accident_id, case_type,
vehicle_num, person_id) unique; **340,498 rows 2010–2024** at severity 1–3 (the dossier's "~482K" is the
2005–2024 pool — record the correction as a dossier amendment). Class shares 2010–2024: killed 1.546 % ·
severe 9.734 % · slight 88.72 % → `1/share` weights **64.68 / 10.27 / 1.127**, computed on the TRAIN window and
FROZEN into meta.json beside the feature contract.

**Features (preset `person-12`)** — person row: `casualty_type_code` (pedestrian = 1, never role),
`age_group_code` (99 → NaN), `sex_code` (0 kept as its own level), `safety_equipment_code`,
`population_group_code`, `involved_vehicle_type_code` (13.5 % NULL and RISING — kept with NaN + a
monotone-missing caveat); ONE accidents join (composite key, verified 0 % unmatched): `road_type_code`
(urban + junction in one), `day_night_code`, `speed_limit_code` (sentinels 0/9/99 → NaN, the 2011/12
discontinuity noted), `hour_of_day`, `month`, `year_idx`. **Leakage exclusions, hard**: `late_death_code`
(defines class 1), ISS/hospitalized/discharge (97 % NULL, 2010–2012 only, post-outcome), severity labels.
The vehicles second join (engine/weight/age) is SKIPPED — `involved_vehicle_type_code` already carries the
vehicle signal; recorded as a deviation.

**The share-drift trap (the exploration's centerpiece)**: the severe share TRIPLES over the era (6.1 % 2010 →
19.4 % 2024; same shape on the accident grain) — a temporal holdout will read as under-prediction. Design
response: temporal split (train ≤ 2022, holdout 2023–24) with `year_idx` in the features, and a gate built on
DISCRIMINATION (recall/AUC survive level drift; calibration-style metrics would fail exactly like the site
model's rejected 2022): **fatal recall ≥ 0.5 · AUC(fatal, one-vs-rest) ≥ 0.8 · no-overfit = train-AUC −
holdout-AUC ≤ 0.05** (all three plugin-labelled, set below the report's achieved 0.6/0.85). AUC via the
Mann-Whitney rank statistic (pure Python, no sklearn). The drift itself becomes a card caveat and a dossier
amendment ("labels drift-free ≠ shares drift-free").

**Registry prerequisite (a REAL latent bug the exploration found)**: `save`/`read_meta`/`update_meta`/
`model_bytes` are family-blind — `list_models(ctx, "severity")` would enumerate severity dirs but read their
metas under `site/`, returning everything "unreadable". Thread `family` through those four + `new_model_id`'s
hard-coded `site-` prefix; regression test with two families side by side. `root/model_dir/list_models/deployed/
set_deployed/deploy/resolve_id` already take family.

**Twins (Poisson machinery does not generalize)**: `studio/severity.py` = the person-matrix builder (SQL with
the composite join + the NaN rules) + softprob train/predict (weights via `DMatrix(weight=)`, per-family feature
names — `model._dmatrix` currently bakes the SITE feature list) + the discrimination gate. `gate.py`'s
spearman/deviance stay site-only. `studio_deploy` + `studio_models` gain a `family` choice (site|severity);
studio_models' metric columns become family-switched; `about` shows both deployments.

**Faces**: `studio_validate_severity` chart = per-class recall/AUC bars + a fatal-probability decile lift table;
`severity_predict` = the profile's severity distribution vs the population baseline (RELATIVE framing on every
line — "המודל מדרג פרופילי סיכון, אינו חוזה גורל של אדם"); `what_if` = baseline profile vs one changed field →
relative deltas (chart + table), refuses without a deployed severity model. Scenario fields (choices only):
road_type, day/night, casualty type, age band, safety equipment, speed band.

**Fixture**: extend `involved` rows via the existing P2 people-lists pattern ONLY on new dedicated accidents in
years the pinned tests don't count… NO — the P5 lesson: reuse EXISTING accidents, add persons? Person rows DO
move pinned aggregates (about's מעורבים count, severity_profile) → plant the severity training set in the
STUDIO fixture instead (its own DB, no pinned census) with planted class structure (e.g., night+pedestrian
skews severe) so the gate passes on real signal and a shuffled preset fails.

## Shared

- studio_models `family` choices += `severity`; `about` shows both deployments; ledger/guard as everywhere;
  page: studio tab gains the two studio actions, חומרה tab gains severity_predict + what_if (placement TBC).
- Plotly builders for the new chart faces + PNG twins via the P8 machinery (bidi fixture already guards).
- Tests: gate math worked examples, class-weight arithmetic, round trip with refusals, ml-missing, live smoke
  with pinned-tolerance metrics; fixture person rows extended WITHOUT moving pinned aggregates (the P5 pattern).
- Docs: plan.md P9 row, CHANGELOG (+v0.8 block), README, CLAUDE.md facts, PITFALLS as they happen (the
  family-blind registry bug and the share-drift trap are entries the moment they're confirmed in code); dossier
  §12 amendments (340,498 vs "~482K"; share drift ≠ label drift); DEMO.md beat 5b gains the severity gate as a
  second governance exhibit (optional beat) + the "prediction" framing from track A.
- Stage seeding at the end: train/validate/deploy ONE severity model into the shared dir (the demo's second
  deployment), preflight's stage pins extended to cover it.

## Order of work

0. `docs/p9_design.md`; preflight; tree clean at v0.8.
1. Registry family-threading fix + two-family regression test (the prerequisite).
2. Track A (visibility): the prediction chip, wording, studio_explain markdown card, triage route, tests,
   npm build.
3. `studio/severity.py`: matrix SQL + NaN rules → softprob train/predict with frozen weights → the
   discrimination gate (recall/AUC/no-overfit, Mann-Whitney AUC) — worked-example tests first.
4. The four actions + registry/models/deploy family plumbing + `about`; studio-fixture severity rows with
   planted signal; round-trip tests (validated real model, rejected shuffled, deploy refusals, ml-missing).
5. Page: plotly builders for the two new chart faces; tabs (studio += the two studio actions; חומרה +=
   severity_predict + what_if); NO_GROUP additions; npm build; headless checks (scratch dir, env-first).
6. 0.9.0 across the five touch points + full suite + wheel sanity + restart + live smoke (train on live,
   gate metrics recorded with tolerance) + stage seeding + preflight (with the extended pins).
7. Sweep question (I ask first; all guardrails; no live recording) → fixes → recap with the new faces'
   screenshots → your acceptance word → `[P9]` + `v0.9`.

## Verification

- Two-family registry test (site + severity side by side: save/read/list/deploy per family, no cross-reads).
- Gate worked examples (hand-computed recall/AUC on tiny vectors; the no-overfit bound); weights frozen-window
  test; leakage test (the excluded columns never appear in the matrix SQL — token-scan style).
- Studio-fixture round trip: person-12 validates on planted signal; `shuffled` preset REJECTED by AUC.
- Live smoke: 340,498-row matrix builds; train ≤ 2022 → holdout 2023–24 gate metrics printed and pinned with
  tolerance; `severity_predict` pedestrian-night profile shows a higher relative fatal share than baseline;
  `what_if` day→night delta positive; every card carries the relative-only line.
- Suite green at 0.9.0; preflight green with the extended stage pins; `git -C app status` clean throughout.
