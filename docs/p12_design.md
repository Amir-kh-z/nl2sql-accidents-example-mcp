# P12 — SHAP explainability: the severity model explains itself

## Context

Scheduled 2026-09-05 (the P10+P11 gate lifted the same day; scoped with the instructor 2026-09-04,
package **Full**; parked meanwhile as `context\PLAN_SHAP_EXPLAIN.md` — this file is that design,
retitled, with the open decisions settled). The severity family predicts but cannot explain itself —
the only explainability surface in the plugin is the site family's `studio_explain`. The source
methodology report's "grand finale" beeswarm (SHAP effects on P(fatal), its 17-feature severity model)
has no counterpart here. This phase closes that gap **production-grade, not as a copy of the report's
plot**: honest scales, honest coloring, decoded values, deterministic sampling, runtime identity
guards, tested against the fixture's planted signal. Motivation is not only the seminar: the prototype
goes to the course owner and should be as rich as the methodology it implements.
Version **0.12.0**, commit `[P12]`, tag `v0.12`. N_ACTIONS 25→26.

**Decisions settled at scheduling (instructor, 2026-09-05):**

- **(A) Class scope** — `severity_class` choice **הרוג (default) | קשה**; קל omitted (the majority
  complement — its beeswarm is roughly the mirror). Nearly free: `pred_contribs` returns all three
  classes in one call.
- **(B) Contract v2 (report-17 features)** — **deferred to its own later phase**; see §6 for the spike
  evidence that makes it concrete. The SHAP phase ships on person-12 and loses nothing: presets are
  already the architecture (`person-12` / `shuffled`), so a `person-18` preset slots in later and every
  explain surface picks it up through the model contract automatically.

## 2. Spike results (2026-09-04, read-only, deployed `severity-2022-person12-s42-20260903T123808`)

Script: session scratchpad `shap_spike.py` (meta.json + xgboost + read-only DuckDB; zero plugin
imports, zero writes). Findings, all pinned:

- **Matrix**: the meta's stored SQL returns 340,498 rows × (sev + 12 features + year) in **0.13 s**.
- **Contribs timing** (`pred_contribs=True`, fresh Booster, 176 rounds, depth 4, 3 classes, nthread 4):
  5k rows **0.52 s** · 20k **1.95 s** · full 340,498 **32.4 s** (linear). → default sample 20k is a
  ~2 s action; "full" is a labelled ~30 s option, not the default.
- **Shape**: xgboost 3.4.1 multiclass contribs are **3-D `(n, 3, 13)`** — per class, 12 features + bias
  LAST (class order = class 0 fatal / 1 severe / 2 slight, the training encoding).
- **Identity**: max |Σφ − raw margin| = **2.6e-06** across 20k × 3 classes → the runtime guard pins to
  1e-3 (ActionError), tests to 1e-4 — same regime as P5's `check_identity`.
- **Bias**: per-class mean ≈ [−0.0001, +0.045, −0.041] (includes base_margin — the P5 note holds).
- **NaN shares** (sentinel→NULL is structural in the matrix SQL): `safety_equipment` **62.7 %**,
  `involved_vehicle_type` 13.5 % (≈ the non-occupants), `speed_limit` 8.7 %, `age_group` 1.2 %.
  The safety row of the beeswarm is two-thirds "לא ידוע" — the plot must show that honestly (§4).
- **Fatal-class mean|φ| ranking (full matrix)** — our person-12 tells the same headline story as the
  report's 17-feature plot (speed and road type lead there too):
  `speed_limit` .283 (corr value↔φ **+0.94** — the clean "red-right") · `road_type` .268 (+0.95) ·
  `vehicle_type` .263 · `safety_equipment` .172 (+0.91) · `age_group` .166 (+0.72) · `hour` .118 (−0.43)
  · `sex` .110 · `population_group` .107 · `casualty_type` .043 · `month` .041 · `year_idx` .037 ·
  `day_night` .018.

## 3. Scope (package: Full) — cut-freely order

1. **`severity_explain`** — new four-view action: global beeswarm + mean|φ| + drivers card + sql.
2. **Per-prediction drivers** — a waterfall face/lines on `severity_predict` and `what_if`.
3. **Dependence view** — `feature` input on `severity_explain` flips the chart face.
4. **Site-family beeswarm** — `studio_explain`'s global face gains the style (reuses the builder).

## 4. Design

### `severity_explain` (item 1)

- **Inputs**: `model_id` text "deployed" (explicit ids incl. rejected allowed + status caveat — the
  `studio_explain` precedent); `severity_class` choice **הרוג (default) | קשה** (decision A); `sample`
  choice `20k (default) | 50k | full` with a help note naming the ~30 s cost of full; `feature` choice
  `none (default) | <the 12>` (item 3 — `none` = beeswarm); `view` chart | markdown | table | sql.
  Contract: every default non-None; choice values are strings; ints stay ints.
- **Chart face — beeswarm**: features as rows ordered by mean|φ| desc; per row ≤ ~300 jittered dots
  drawn from the contribs sample (per-row deterministic subsample). **Coloring policy (the honesty
  differentiator)**: value-color ONLY genuinely ordered features — `age_group`, `speed_limit`,
  `hour_of_day`, `year_idx`, and the binaries `day_night`, `sex`; NOMINAL codes (`casualty_type`,
  `vehicle_type`, `safety_equipment`, `population_group`, `month` as cyclic) draw neutral grey with a
  legend line "קטגוריאלי — ללא סולם צבע"; NULL (sentinel) dots draw hollow grey "לא ידוע". The report's
  plot colors everything — ours refuses to imply order where none exists, and says so.
- **Scale honesty**: x = φ on the **softmax margin scale** of the chosen class, axis-labelled as such —
  never "effect on P(fatal)" (the report's gloss). Caveats carry: margin ≠ probability units;
  association ≠ causation; correlated features split credit (read vehicle_age-style groups together);
  the sample size; the dossier §8 SHAP warnings verbatim where they apply.
- **Runtime guard**: Σφ + bias = raw margin per row/class on the contribs sample, ActionError over
  1e-3 (spike: 2.6e-06). Tested at 1e-4 on the fixture.
- **Determinism**: `default_rng(SEED)` row sampling; **jitter computed server-side into the spec rows**
  (deterministic per-point), so plotly and the PNG twin share one layout and repeated runs are
  byte-comparable (testable).
- **Hover decoding**: dot hover shows the Hebrew feature label + the DECODED value label
  (`code_lookups` by field name — second read-only query in the same action; multiple `ctx.query`
  calls per action are the P3/P10 precedent), e.g. a סוג רכב dot reads "אופנוע", not "8.0".
- **Faces**: table = mean|φ| ranking + direction (corr sign as ↑/↓ סיכון) + "לא ידוע" share per
  feature; sql = BOTH statements (matrix + lookups; P5's two-statement precedent); markdown = the
  global drivers card — top-5 in plain Hebrew with direction, sample + model id, the four warnings,
  ends with the CBS credit. `spec.model_id` present → the 🔮 chip covers it with zero page work.
- **Envelope**: denominator kind `counts` (person-rows of the era; amber); basis strict-ASCII, e.g.
  `class fatal | sample 20000 | rows 340498 | model <id>`; title Hebrew, digit-free
  ("הסבר מודל החומרה"); ledger on; `[ml]` absent → the standard `Result.error` + pip line; no
  deployment and `model_id=deployed` → the severity refusal ladder (points to the studio).

### Per-prediction drivers (item 2)

`severity_predict` and `what_if` gain a drivers face: contribs for the ONE profile row (a single
`pred_contribs` call — sub-millisecond), rendered as a signed hbar "waterfall": top-K φ + "היתר"
+ bias, for the fatal class (or decision A's chosen class), placed next to the existing relative-
probability statement; the markdown card gains top-3 drivers lines (the P9 site-card pattern, LRM
rules from the P9 en-dash pitfall apply). `what_if` shows the DELTA story: which feature's φ moved
between baseline and scenario — the switch's contribution made visible. UNSET profile fields appear
as "לא ידוע" drivers when their φ ≠ 0 (the missing-path is a real model input; say so, don't hide it).

### Dependence view (item 3)

`feature=<f>` flips the chart face: x = the feature's value (decoded category ticks for nominals,
numeric axis for ordinals; NULL as an explicit "לא ידוע" column), y = φ(f), monochrome dots + the
dossier's reading note as a caveat ("פיזור אנכי = אינטראקציות"). **`pred_interactions` is explicitly
OUT** — O(features²) per row and not needed for the reading; recorded here so the sweep doesn't
"suggest" it.

### Site-family reuse (item 4, smallest, cut first)

`studio_explain` empty-site global face gains a `style` choice `profile (default) | beeswarm` over the
panel rows (10,488 × 11, ln-μ scale — already labelled honestly there). Reuses the same builders;
site-family ordinals: the pct_* shares, adt, lag1, years_active, year_idx are ALL ordered → full
coloring is legitimate there.

### Builders (both faces, shared)

`charts.py`: one generic matplotlib beeswarm (density-jitter, colorbar only when ordinal coloring is
active, Assistant font, base direction ALWAYS R, LRM-pinned numbers, footer credit, ≤ 6 caveat lines)
+ one waterfall hbar. Page: PlotlyChart gains `accidents/beeswarm` + `accidents/waterfall` trace
builders (dependence reuses the scatter path); jitter/colors arrive in the spec, the page never
randomizes. Offline plotly-basic covers scatter/bar — no new JS deps.

## 5. Tests (the planted signal makes the plot assertable)

- Identity 1e-4 (fixture) + the 1e-3 runtime guard raising on a corrupted-φ monkeypatch.
- **Planted-signal assertions** (studio fixture LCG effects: night ×3.5, ped/moto ×6, no-safety ×5,
  speed ≥5 ×2.2 on killed odds): mean φ(fatal | night=1) > mean φ(fatal | night=0); the analogous
  inequalities for safety and speed; ped/moto vehicle codes' mean φ above the vehicle-row mean.
- Determinism: two runs, same inputs → identical spec rows (sample + jitter both seeded).
- Coloring policy unit test: nominal features never get a color scale; NULL dots always "לא ידוע".
- Contract: `severity_explain` joins the FOUR_VIEW set; every input defaulted; basis ASCII; title
  digit-free; PNG magic + size; new Hebrew strings → byte-exact bidi fixtures (the P8 harness).
- Waterfall: rendered bars + "היתר" + bias sum to the row margin (same identity, per profile).
- Fixture note: severity fixture trains only with `train_until=2018` (the P9 inner-fold constraint).

## 6. Contract v2 evidence (decision B — for the LATER phase, not this one)

Spike probe, live DB, read-only: the composite key **(accident_id, case_type_code, vehicle_num)
exists on BOTH `involved` and `vehicles`**; 2010–2024 casualty person-rows = 340,498, of which
**86.5 % match a vehicles row; occupants unmatched = 0** — the 13.5 % gap is exactly the
non-occupants (pedestrians etc.), i.e. missingness would be STRUCTURAL, not noisy. Available on
`vehicles`: `engine_volume_code`, `seats`, `total_weight_code`, `manufacture_year` (→ vehicle_age
vs accident year); on `involved`: `license_year` (→ license_years), `role_code`. That reconstructs
the report's `engine_volume / seats / weight_class / vehicle_age / license_years / role`; its
`cohort_km_year` / `adt_measured` need the fleet/traffic sources — separate analysis. A v2 phase =
`person-18` preset + leakage review (e.g. `vehicle_condition`/`damage_code` are post-hoc — exclude)
+ retrain + re-gate; every §4 surface then picks v2 up through the meta contract with no plot work.

## 7. Demo & docs touches (inside the phase)

DEMO.md: the studio/governance beat gains "the model explains itself" (beeswarm on stage, hover a
decoded dot, point at the grey safety row and SAY why it is grey — the honesty is the show);
plan_b.pdf +1 frame; preflight: version bump across the five touch points (stage state itself is
already seeded with the deployed severity model — no new seed step); `participants.md`: instructor-
grade (studio tier); triage: הסבר-מודל intents route to `severity_explain` (keep the P5 anchoring
against הסברה); CHANGELOG. Cassettes untouched.

## 8. Expected pitfall harvest (deliberate)

Margin-vs-probability labelling; nominal value-coloring honesty; the 62.7 %-NULL beeswarm row's
readability; cross-face jitter determinism; contribs time/memory budgeting (sample as an input);
category ticks + bidi on a dependence axis; waterfall sign conventions in RTL.

## 8.1 As-built deviations (recorded during the build, 2026-09-05)

- **`studio/explain.py` untouched** (the plan said "generalize with a features param"): the severity core
  computes its means with numpy directly in `studio/explain_severity.py`, so the site helpers keep their
  exact bytes — smaller touch-set, same outcome.
- **The identity guard centralized as `severity_predict.contribs_guarded`** (the fan-out's cleanup):
  severity_explain, severity_predict and what_if share ONE guarded contribs pass.
- **Latency honesty**: the spike's ~2 s was contribs alone; the full action answers in ~7 s live (50k ~11 s,
  full ≈ under a minute) — matrix fetch + a second predict pass for the margins + swarm/decode + the PNG
  twin. Help/GUIDE/DEMO wordings updated; PITFALLS `[demo]` entry.
- **`road_type_code` resolved NOMINAL** (§4 listed it in neither set): a 2×2 of urban × junction carries no
  scalar order — it draws grey.
- **Dependence `xj`**: the categorical x-jitter is computed server-side into the spec (the same stack-jitter,
  cap 0.30 inside the slot) so plotly and the PNG twin share one layout — the beeswarm determinism rule
  applied to the second face.
- **Decode is tolerant**: a DB without `code_lookups` still explains (dots fall back to numeric codes) — the
  dictionary is garnish, never a dependency; `involved_vehicle_type_code` decodes under the dictionary field
  `vehicle_type_code` (verified live).
- **Fixtures**: `code_lookups` joined BOTH test DBs (a small live slice incl. one older-year row pinning the
  arg_max rule); the about card's schema-object pin moved 14→15 (PITFALLS `[process]`).
- Built under ultracode: a three-agent implementation fan-out over disjoint file ownership (waterfalls /
  site style / page builders) + the inline core; the acceptance sweep is the standing separate step.

**Post-sweep additions (2026-09-06; the sweep: 8 finder dimensions → 28 deduped findings → 2 adversarial
verifiers each; 15 confirmed, 13 verified inline after the spend limit killed their verifiers twice —
ALL fixed or recorded):**

- **Dependence NULLs get an explicit slot on BOTH axis kinds** (the sweep's 5× consensus catch): ordered
  axes gain a labelled `null_x` strip right of the known range (stack-jittered, drawn by both renderers) —
  x=None dots were silently skipped everywhere while the caveat claimed them hollow.
- **`DISPLAY_NULL_CODES`**: sex_code 0 = "לא רלוונטי" (3,797 live era rows) is masked to NULL at the
  display layer — a sentinel is never a LEVEL on the color scale; the FROZEN matrix contract is untouched
  (a matrix-side 0→NULL = CONTRACT_VERSION bump + retrain, parked for a later phase).
- **Candidate metas have `gate=None`** → the model-quality caveat now says "טרם אומת — ללא מדדי שער",
  never a literal "None"; the shared no-deployment refusal wording went action-neutral.
- **what_if's interactive drivers panel says Δφ** (axis title + hover + the switch bar outlined) — the PNG
  twin always did; `switch_feature` in the spec is the delta marker.
- **Dependence caveats**: the reading note ("פיזור אנכי = אינטראקציות") now LEADS and the coloring-policy
  caveat leaves that face (monochrome — inapplicable); the 6-line PNG cap was cutting exactly the note.
- **Faces carry their axis labels in the spec** (`swarm.xlabel`, `dependence.xlabel/ylabel`) — the plotly
  faces no longer lose the labels their PNG twins had; `ratio_with_drivers` sizes its left edge from the
  longest label (a fixed 0.06 clipped "קבוצת אוכלוסייה"), and the page's inter-panel gap widened to 16%.
- **PlotlyChart's PNG-fallback now resets per spec** (one builder throw no longer downgrades the panel for
  the session). No `accidents/waterfall` spec type exists as designed — the drivers hbar is a panel of
  `ratioWithDrivers` on the existing predict/what_if types; `charts.waterfall` stays as the tested
  standalone builder.
- **Roster discipline**: the about card's פעולות list gained severity_explain AND test_about now derives
  the roster from MODULE (the P5/P9/P12 drift class is closed). GUIDE §0 reads 26; CHANGELOG carries the
  honest ~7 s latency; repo CLAUDE.md gained the P12 facts section.
- **Dictionary hole recorded**: `involved_vehicle_type_code` 4 (671 era rows) has no entry under field
  `vehicle_type_code` — the tolerant fallback shows the number, by design ("decode is garnish").
- **Demo assets**: `tools/rehearse.py` gained beats 5c (belt what_if) + 5d (explain + dependence) and
  `make_plan_b.py` the beat-5d frame page; the plan_b.pdf REGENERATION (and DEMO's page count) is deferred
  to the pre-show asset refresh alongside the projector rehearsals — a recorded deviation from §7, not a
  silent gap. A permanent JS-side builder smoke stays backlog: the builder-throw → PNG-twin fallback plus
  the live CDP check cover the release.
- **New tests**: ordered-NULL strip, display-sentinel mask, the 0.3-threshold caveat helper (extracted
  pure), decode tolerance via a failing lookup, empty-matrix refusal, the identity guard through ALL three
  actions, candidate-caveat wording, the derived about roster.

## 9. Size & acceptance

~1–1.5 days + sweep (P5-sized). Acceptance: all faces on the clone's Modules page AND the 🚦 page
(wheel install, restart); suite green incl. the planted-signal and identity tests; the rehearsal
driver runs the beat; PITFALLS entries written when stumbles happen; `[P12]` commit, `v0.12` tag.
