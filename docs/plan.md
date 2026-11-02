# PLAN 3 — Phased Build Plan: `nl2sql-roadsafety-lab` pathfinder

**Status:** v2, 2026-08-28 — corrected by the verification sweep. Becomes `docs/plan.md` in the
plugin repo at P0 and is kept current there. **This is the phase skeleton; each phase gets its own
detailed plan (plan mode → plan file → approval) before it is executed.** Definition of done for
**every** phase: **runs on `app\`** (the participants' clone), plain-language recap + exact
runnable commands, diff shown before approval, app stays startable, every stumble → `PITFALLS.md`
(written when it happens). Commits `[Pn] …`; tag `v0.n` at acceptance. Ultracode is used
**inside** build phases only where marked, and only when you say "ultracode" for that phase.

Standing rules: never edit `app\` — the one sanctioned write under it is `app\cassettes\`
(gitignored per-user runtime state, hard-coded by `adapters.py`; `git -C app status` must stay
clean); DB opened read-only by absolute path; no data in the repo (screenshots committed are
chart/ranking frames only); CBS credit on every output (display level is free — internal use,
seminar included); no publishing without an explicit yes. Working-directory convention for every
command: **from `accidents-lab\`** (`app\.venv\Scripts\python …`, `nl2sql-accidents-plugin\…`).

## Progress

| Phase | Status | Accepted | Notes |
|---|---|---|---|
| P0 | **done** | 2026-08-28 · `v0.0` | all five spikes positive (see `spikes.md`); 7 pitfalls recorded; xgboost viable on 3.14; chat works key-less via the `claude` CLI |
| P1 | **done** | 2026-08-29 · `v0.1` | 117 tests green (incl. 6 live); three actions on the clone's Modules page; wheel verified. Design: `docs/p1_design.md`. Deviations recorded: explicit `packages` list incl. the subpackage; four denominator kinds; single-`#` refusal heading; lab-line refusal footer; no-digit `Result.title`; trap "correct" = naive + one line (code canon in a comment); strict-ASCII `basis`/stamp; caveats most-specific-first with a 6-line PNG cap; data-driven road caveat; `ACTION` last in every action module; **2009 casualty-series involved gap** handled by the coverage rule |
| P2 | **done** | 2026-08-30 · `v0.2` | six analytical actions (segment_rates, severity_profile, vehicle_cells_ranking, before_after, weather_check, triage), 208 tests green incl. 12 live smoke; `docs/p2_design.md`; `docs/demo/sites.md`; adversarial sweep: 23 findings fixed before acceptance (live coverage 70.4 % after the km-0 rule). Deviations recorded: `segment_rates` is a plugin-defined instrument (the report has no per-vkm rate) with `order_by` (rate_lo default), exposure-year refusal, Byar CI in SQL, live coverage in the answer; unit = count segment; `severity_profile` adds `sex`, applies the coverage rule per year, pedestrians keyed on `casualty_type_code = 1`; `vehicle_cells_ranking`: `bands` choice instead of a minimum exposure (EB is the substitute), band 0 kept and labelled, `ntile(5)` tiers; `before_after`: `change_year`, `min_cell`, network control only, double-ratio SE = plugin extension, data-driven control flag (coding share > 25 % relative); `weather_check`: threshold as a choice, `לא ידוע` shown; `triage`: rule table, three card shapes (answer / refusal / route); make/model refusal reworded (the registry knows models, the accident files carry no key) |
| P3 | **done** | 2026-08-30 · `v0.3` | the 🚦 page (React + Vite, RTL, `/page/accidents/`, `webdist/` committed) with the full answer anatomy, six tabs, `about` strip, triage box, hand-off to before_after; `hotspot_map` (observed counts, Leaflet + PNG twin); 236 tests green incl. 13 live; `docs/p3_design.md`. Deviations recorded: `hotspot_map` gains `road`; geometry = Point at the mean of the unit's geocoded accidents (no LineString); 2017+ per-year vintage ∪ latest `traffic_segments` vintage before → counts equal `segment_rates`; `site_key` from the latest vintage; "geocoded" = inside the Israel bbox; `top_n` 30 (1–200); `points` capped 300/unit, 3,000 total in SQL; refusal when nothing is placeable; `color_by=excess` falls back with a caveat (`color_by_effective`, the P4 hook). Page: `?tab=` / `?run=` deep links, the `view` input hidden (chart always), Studio/Findings empty states, no JS test runner (page contract tests in Python + headless Edge evidence). Outline: Natural Earth 1:10m simplified (355 vertices, 7.3 KB) as package data — one file for Vite and matplotlib. Sweep fixes (2026-08-30): urban-junction names = ONE row's street pair (the lexicographically smallest), shared by the map and `before_after` (`UJ_NAMES_CTE`) — two independent `min()`s had named a junction "X / X"; `99999999` added to the junction sentinels everywhere (map, coverage, control, key parser); junction caveats no longer promise `excess` and say the units are placed from the dimension; the popup lists the unit's accidents when `points` (12 shown, the rest as grey markers with tooltips); page: year/id columns never thousands-grouped, a missing connection shows a ❌ chip, the legend states the shown range, every tab stays mounted (the map survives a tab switch), unknown `?tab=` falls back, Latin runs in cards are bidi-isolated, tooltips escaped, the build's version is baked in; PNG twin is landscape (map left, top-12 list right) and long caveats wrap at their seams; basis `top N | listed n | placed p`; segment labels use `←` (the arrow must point toward name_to in an RTL line); geojson ≈ 1.1 MB at `top_n=200, points=true`. Wheel built and installed on the clone (namelist: `webdist/**`, `data/israel.json`, `page.py`), then reinstalled `-e` for P4 |
| P4 | **done** | 2026-09-02 · `v0.4` (built 09-01, accepted next morning — the tag is the record) | the studio (site model + registry + ledger): `studio_train_site` / `studio_validate` / `studio_deploy` / `studio_models`, `site_ranking` (excess = observed − μ, EB, NB 90 %), `hotspot_map color_by=excess` live, the findings ledger (`guard` appends answers AND refusals; `about`/`ledger_list`/`finding_card` exempt) with `ledger_list` + `finding_card`; 17 actions; 265 tests incl. the live studio end-to-end (train 1.2 s, validate 0.2 s, rank 0.1 s); `docs/p4_design.md`. Sweep (26 agents): 8 confirmed findings ALL fixed — the high: `os.replace` vs Windows readers (WinError 5, 98.9 % write failure under load) → one registry RLock + retry + atomic `registry.deploy`; plus `contract_version` now enforced at predict, the ledger cap re-checked after the last fallback, `md.jsx`'s stateful /g-regex `<bdi>` bug, doc corrections (details in `docs/p4_design.md` + PITFALLS). Deviations recorded: **default `train_until = 2023`** — the planned 2022 is genuinely REJECTED by the gate on live (calibration 1.35: the 2023–24 casualty decline is outside what the features carry; kept as the third seeded artifact — the honest governance beat), holdout = 2024 only; panel = the FULL 1,311 × 8 grid (10,488 rows; 4,695/3,405 in the planning docs were raw as-of counts); `pct_curve` over rows with a SPECIFIC shape code only (code 9 "אחר" climbed ~5 % in 2005–2007 → 24 % by 2010 → 47 % in 2011, a coding discontinuity); static attrs effectively casualty-coded (the damage-only series carries ~0 % of the codings — said on the card); depth-2 xgboost params; `severity` dropped from `site_ranking` (KSI is a column); `road` input added; excess-mode observed = the panel's assignment (a caveat carries the difference vs `segment_rates`); the demo criterion re-worded — **60/836 shows excess −2.0 (rank 8 of 21 on road 60): the treated site sits BELOW its model expectation, which IS the beat-3 story**; live gate pins: doc-11/2023 Spearman 0.693 · calibration 1.17 · ratio 0.82 · α 0.16, shuffled/2018 Spearman 0.201 (the script promised 0.21). Wheel (with `studio/`) installed on the clone for acceptance, then `-e` restored; shared data dir seeded (deployed 2023 + rejected 2022 + rejected shuffled + the rehearsal `before_after` ledger entry) |
| P5 | **done** | 2026-09-02 · `v0.5` | stretch, user's cut 2026-09-02: **`studio_explain` + `two_wheelers` shipped; the severity model cycle and `what_if` are CUT** (recorded deviation — P6 stays on schedule). `studio_explain` (TreeSHAP via `pred_contribs`, native API): per-site top-5 φ lines per year next to observed-vs-μ (`charts.explain_png`), empty site = the global mean\|φ\| profile, `model_id` default "deployed" (explicit ids incl. rejected ones allowed — with a status caveat), Σφ = ln μ identity pinned to 1e-4 on the full φ rows (the table shows top-5 + bias only — a 0.25 subset bound on live); refuses junction keys, unknown segments, empty registries. `two_wheelers`: fleet-driven zero-filled grid per (year, cc band) — numerator = vehicles ⋈ accidents under the golden rules, denominator = the FULL current fleet per band from `fleet_motorcycles` (the curated view's cohort INNER JOIN undercounts — live parity with the view pinned at cohort grain, 877 rows); bicycles/e-bikes/e-scooters as counts-only rows (code 22 קלנועית EXCLUDED — a mobility scooter, the "docs vary" resolution); era refusal < 2013; the fleet-snapshot and floor-of-the-truth caveats. 19 actions; triage routes (+`two_wheelers` in the curated `ALL_ACTIONS` fallback — a 12-action list, not all 19); page: חומרה += two_wheelers, סטודיו += studio_explain, `band_code` un-grouped. Sweep (14 agents, port 8000 off-limits — the stage state verified byte-identical after): 6 confirmed findings ALL fixed — English "model" questions with explain intent no longer swallowed by the make/model refusal, the sql face carries BOTH statements (grid + counts), `check_identity` is now a real runtime guard (ActionError over 1e-3), `הסבר` anchored against הסברה (advocacy), two doc corrections. Further as-built deviations: the P4 `deployed_ctx` test pattern reused per-file; a post-`make_spec` PNG attach must also set `renderer`; band labels carry digits legitimately (the no-digit rule covers Input labels and `Result.title`); the live identity bound on the TABLE face is 0.25 (top-5 + bias subset — the exact 1e-4 identity is pinned on full φ rows). 285 tests green incl. two live smokes (explain site 0.2 s / global contribs on 10,488 rows ~0.5 s); wheel 0.5.0 verified on the clone then `-e` restored; the shared data dir RESTORED to the seeded stage state after the sweep's port-8000 contamination (PITFALLS 2026-09-02) |
| P6 | **done** | 2026-09-02 · `v0.6` | demo hardening, no new actions, version 0.6.0: `tools/preflight.py` (the automated PLAN_2 §0 table incl. the stage re-verification born of the port-8000 pitfall; FAILS loudly on a doctored dir — tested via a scratch LOCALAPPDATA), `tools/rehearse.py` (the beat driver — module API, never port 8000), `tools/record_cassettes.py` (+ 2 cassettes recorded keylessly and replay-verified: `replayed: true` · cost 0 · 5,458/439 stable), `tools/make_plan_b.py` → `docs/demo/plan_b.pdf` (12 pages, chart/ranking/card frames only), `docs/demo/DEMO.md` (the run-book; PLAN_2 marked superseded) + `docs/demo/rehearsal_p6.md`. Rehearsal A (fresh `c:\tmp\demo-data`, seeded live: train 1.2 s · gate 0.2 s · deploy 0.04 s) and Rehearsal B (stage) both ran all 11 beats without a fallback (≤ 0.77 s/beat); a separate app-boot smoke proved the redirected dir end-to-end (health reports it, 19 actions, ~2 s boot); stage dir verified/restored after each. Deviations: the fresh-dir rehearsal ran at MODULE level (no app-swap juggling — the boot smoke covers the app side); recording usage read from the engine's process-global `get_usage_cost` (`run_question` carries no usage); plan_b's table frame shows ASCII columns only (DejaVu Mono has no Hebrew). Sweep (35 agents): 10 confirmed ALL fixed — the highs: the chat-history sidecar breaks cassette replay on stage (new preflight check + the sidecar cleared + the one-question-per-fresh-conversation rule), preflight accepted a 0-byte deployed booster (size floor + subprocess load probe), plan_b's finding card carried the triage refusal ("latest" → explicit ledger idx + a content gate); plus content-validated connection/sidecar checks, a locale-independent port probe, make_plan_b's real-dir guard, doc corrections. The sweep also exposed the THIRD stage-contamination vector (env read-once ordering — PITFALLS updated); preflight flagged the drift mid-sweep and the stage was restored |
| P7 | **done** | 2026-09-02 · `v0.7` | wrap, version 0.7.0: PITFALLS.md categorized (34 entries, category index, chronology fixed to strictly reverse-chronological; deviation: the planned seven categories became TEN — `concurrency`/`state`/`model`/`process` added, `license` empty by design, and the page-defects entry moved from `[RTL]` to a new `[page]` after the sweep judged 1/8 of its sub-defects RTL); `docs/participants.md` (teachable band, seed skeleton, planning prompt — the scoping decision's input); `CHANGELOG.md` v0.0–v0.7 (v0.4's date corrected to the tag's 2026-09-02); README handoff status; 0.7.0 across FIVE touch points (pyproject, `__init__`, package.json, test_contract, tools/preflight PLUGIN_VERSION); context\ pack refreshed OUTSIDE this repo (kickoff STATUS header — worded to stay true pre- and post-tag — and dossier §12 addendum; the sweep corrected two of its numbers: 2,329 is the PANEL's 2024 Σy, national is 8,315; the shape-9 57 % is both-series, casualty-only is 34 %). Sweep (18 agents): 8 confirmed ALL fixed (the highs: this Progress table itself lagged P6/P7 — the ground-truth doc failed its own rule; the two dossier-addendum number scopes), 1 refuted. 285 tests at 0.7.0; preflight green; release wheel built from the committed `v0.7` tree post-acceptance, NOT published |
| P8 | **done** | 2026-09-03 · `v0.8` | chart & Hebrew polish (user-requested after reviewing the live page, 2026-09-02), version 0.8.0: **plotly.js on the 🚦 page** (`web/src/components/PlotlyChart.jsx` — 10 spec-type trace builders over rows+extras, browser-native bidi, hover/zoom, offline `plotly.js-basic-dist` pinned 3.7.0, PNG twin kept for Layer 0/Plan-B/fallback — the map's twin pattern; one additive spec key: `studio_gate.deciles`) + **the PNG bidi/typography fix**: auto base direction from the original string's first strong char, LRM-pinned tight number ranges (spaced em-dash = separator), the L4 trap documented (NEVER switch to the Rust bidi), bundled **Assistant** (SIL OFL, Regular+Bold statics cut from the variable font, `tools/fetch_font.py`) via `font.family` LIST (per-glyph fallback for ← and Σ; ≠ is native to Assistant), 8-string byte-exact bidi fixture in test_charts.py; layout fixes: RTL legend order, caveat continuation indent to the right, annotations clear bar+whisker+marker, `hbars max_rows` density cap (site_ranking PNG shows top 15 of N with an honest caveat). Deviations/serendipity: matplotlib per-glyph fallback works ONLY via the `font.family` list; `instantiateVariableFont` needs `inplace=True`; plotly `automargin` under-reserves in headless — deterministic label-width margins; a fresh `NL2SQL_CORE_DATA_DIR` lacks `added_connections.json` and page runs 404 (PITFALLS). plan_b.pdf + frames REGENERATED in the new style. 286 tests green; wheel 47 files incl. the fonts; preflight caught mid-phase stage drift that the ledger attributed to the INSTRUCTOR's own UI sessions — pruned per the pre-show rule (the governance loop working as designed). Sweep (27 agents): 9 confirmed ALL fixed — the highs: the mid-phase auto-base-direction heuristic scrambled acronym-opening Hebrew caveats (base is ALWAYS R now), and the plotly monthly trend collapsed 24 months onto 2 category ticks (composite year-month labels); plus the paren-pairing class broken since P2 (LRM-pinned LTR-content groups + Hebrew-first content rewrites in three source strings), paren-aware caveat wrapping, the ≠-glyph doc claim, README/doc staleness. The bidi fixture grew to 14 machine-generated byte-exact cases |
| P10 | **done** | 2026-09-05 · `v0.10` | מפה חיה, the advanced interactive map, version 0.10.0 (design + full as-built record: `docs/p10_design.md`): the custom GPU tab (MapLibre GL 5 + deck.gl 9 in an isolated lazy chunk ~1.77MB; the other tabs untouched) over an **offline PMTiles street basemap** (171MB z15 Israel extract via `tools/fetch_basemap.py`, gitignored + wheel-excluded by three verified guards, hardlink-synced past vite's emptyOutDir; automatic dark data-canvas fallback — wheel-install smoke boots into it) with vendored Hebrew glyphs + RTL plugin; the full geocoded cloud (218,144 pts 2008–2024) GPU-filtered (year/severity/day-night + animation, zero re-fetches, per-accident hover), three site layers, offline search, deep links (`?tab=map&road=&from_year=&to_year=&color=&basemap=off`). Two actions → 25: `map_scene` (ONE columnar envelope + hexbin PNG twin; `twin=false` page fetch; `color_by=excess` = the EB screening as a layer — ALL panel segments red→blue, re-ranked by excess, z-colored) and `site_profile` (the click panel: strip for every kind; μ/excess/EB/interval/verdict/SHAP for segments only — junctions structurally model-free; conditional severity, relative-only; degrade-to-caveat ladder). Six instructor review rounds folded in (empty-map triple, panel three-exits, hover tooltips, SHAP hand-off, shape/neutral-hue mark grammar, all-panel + band-distance colors, z-distribution drawer — residual-diagnostics EDA). Sweep (44 agents): **11 confirmed ALL fixed** (highs: the רענון refetch trap, silent error-kind envelopes, caveat-contract leak on the excess degrade path, floored-lo90 z inflation), 7 refuted, 17 lows triaged (10 fixed). 335 tests incl. live pins (cloud=inline-count equality, 60/850 top red significant, מחלף מורשה counts-only, 60/836 excess −2 via the panel); CDP screenshot/click/hover harness (`web/scripts/dom-dump.mjs`) replaces virtual-time dumps for the map. Stage restored to seeded + preflight green (new `basemap` check). Four PITFALLS entries |
| P11 | **done** | 2026-09-05 · `v0.11` | the trend composer + the share-drift view (user-requested after asking why trend shows one line; three discussion rounds settled the design), version 0.11.0, design `docs/p11_design.md`: **page-only composer** — `TrendCompare.jsx` replaces ActionPanel for trend alone; up to 3 slicer rows behind `+ השוואה` (row 2/3 prefilled from row 1's current values with the last-run spec as fallback, `הרץ הכול` via a new Form `runTick` prop, minimize/remove, hard cap 3); composition client-side from the specs — same granularity required (mixed granularities compose NOTHING: separate answers + a note); then overlay on ONE shared y-axis iff identical `gap_periods` AND scale ratio ≤ 3, else small multiples (matched x via `matches:"x"`, free y), NEVER two independent y-axes; אוטו/מאוחד/מפוצל toggle overrides, forced overlay across differing coverage drops the band + names the missing periods; each run keeps its full envelope (collapsed `<details>` under the composed figure) and its own ledger line — the composition is a view, not a finding (accepted limitation). **Backend**: `severity_profile by=year` (PROFILE_DIMS + chronological ORDER + the share-drift caveat) — the P9 drift trap as a picture, live-pinned 6.1 %→19.4 % severe share. Verified: the decision matrix on REAL live runs via a node harness over the stubbed component (urban/nonurban→overlay ratio 1.54 · killed/slight→split ratio 72 · killed/fatal_accidents→split by COVERAGE (gapsEqual false, ratio 1.18) · year/month→stack · 3-way→overlay 2.48) + headless DOM (button present, single-row unchanged, מפה חיה intact) + real-data overlay/split screenshots; 334 tests; wheel 0.11.0 clean (pmtiles excluded, glyphs/sprites ship); release\ wheel swapped per the Branches policy. Sweep (20 agents, 14 confirmed findings ALL fixed) — the high: Form's runTick effect fired on REMOUNT, so expanding a minimized row after הרץ הכול silently re-ran with stock defaults (ref-guarded now: fires only on an actual tick change); the mediums: stale `open` map mounted plotly inside a closed `<details>` at zero width (controlled `open` attr now), prefill came from row 1's last-run spec instead of its current values (Form gained `onValues`, spec stays the fallback — a recorded extension of the one-prop design), `.compare-row:first-of-type` never matched so row 1 got a stray separator (`+`-combinator now), the P11 CSS referenced nonexistent tokens (--ink-soft/--teal → --muted/--accent; dark theme was frozen light), and same-measure-different-window runs produced byte-identical labels (labelOf appends the LRM-pinned year window everywhere); plus the year help-text, three P10→P11 comment labels, and five doc-vs-code drifts (N_ACTIONS 25, 333 existing tests, gap_periods not "coverage caveats", the granularity rule composes NOTHING, the prefill wording) |
| P12 | **done** | 2026-09-08 · shipped in `v0.13` (commit `58c2701`; interleaved with P13, so v0.12 was never separately tagged) | SHAP explainability — the severity model explains itself (design `docs/p12_design.md`; scheduled 2026-09-05 after the P10+P11 gate lifted; decisions settled at scheduling: class scope = הרוג default + קשה, contract v2 person-18 deferred), version 0.12.0, 26 actions: `severity_explain` (four-view beeswarm / dependence / ranking / drivers card; margin-scale honesty, ordered-only value coloring, hollow NULL dots, code_lookups hover decoding — involved vehicle type decodes under field `vehicle_type_code`; deterministic 20k sample; Σφ+bias=margin guarded 1e-3 runtime / 1e-4 tests), per-prediction waterfalls on `severity_predict`/`what_if` (shared `contribs_guarded`; what_if = the Δφ story), `studio_explain style=נחיל`, triage severity-explain route. Built under ultracode: 3-agent implementation fan-out (waterfalls / site style / page builders) over disjoint file ownership + the standing sweep at acceptance. **Built, tests green — awaiting the instructor's acceptance + tag (uncommitted with P13)** |
| P13 | **done** | 2026-09-08 · `v0.13` (commit `58c2701`, 417 tests green at the gate) | the borrow build (2026-09-06, instructor: "take anything not in my building" + the OFFLINE REQUIREMENT RETIRED): 30 actions. Waves: 7-agent implementation (theme-aware page via `theme.js` + dark tokens + ResizeObserver fix + KPI cards + blurbs + OSM basemaps; `heat_matrix`; severity dims lighting/hour/day/speed/road_shape; `vehicle_cells group=cohort`; about KPI block; gate ROC/calibration diagnostics — never gating; hotspot_map degrade fixes + ONE z-based excess rule parity-tested with map_scene) → 3-agent wave (`zone_ranking`/`city_ranking` over the dark cumulative aggregates — separate-universe caveats, locality grain, index≡density r=1.000 live; `ab_scan` the before/after discoverer; the אזורים tab + builders) → **6-refuter adversarial verify** (killed wave-1 ab_scan: geometry splice = 19/20 artifact candidates, leader sign-flip under its own hand-off; found the dead StatCards CSS contract, two false no-deployment claims, stale docs) → fix wave (ab_scan rebuilt on ONE static latest-vintage geometry with event-year-excluded windows matching before_after — chain-consistency test pins cell equality; re-verified CLEAN live, and the discoverer independently surfaces the demo's treated site 60/96-98.8 e=2017 as an improvement; zones polish: per_capita-only population caveat, ped_share denominator column + tie-break + tiny-denominator caveat + honest scope, split municipality rows merged). Spend-limit interruptions twice (agents resumed / finished inline). Deferred dormant: studio_train chart views. 5 PITFALLS entries. CHANGELOG carries the full record. This row is updated at acceptance |
| M1 | **built** | 2026-09-12 · awaiting the acceptance word → `[M1]` + `v0.14` | the MCP server — "chat with your data" (design + as-built `docs/m1_design.md`; the course owner's deck): `nl2sql_roadsafety/mcp/` = the closed core imported in-process (engine `Context` + `Registry`, no port 8000) behind **12 intent-grouped tools over 29 actions** (`map_scene` excluded; `face` → each action's own view; `roadsafety_studio` train/deploy refuse without `confirm=true`), Result → text + PNG image block (60-row cap, stated), one audit line per call, 5 resources (rules · catalog · about · models · ledger), 3 prompts; mcp SDK **2.x** (`MCPServer` — FastMCP is gone in 2.x, pinned `>=2,<3`), stdio; extra `[mcp]`, console script `roadsafety-mcp`, `install-plugin.ps1 -Mcp` (Claude Desktop config merge in Python — refuses while Desktop runs; prints the Claude Code line). Fixed on the way: the installer's rename leftover (`accidents` in the verify block) and preflight `N_ACTIONS` 26→30. 46 tests (tool layer + real protocol in-process and as a stdio subprocess). Decisions (instructor 2026-09-12): tools-only (no free SQL in v1), `[M1]`/0.14.0 so P14+ keep their numbers. CBS transit of aggregates to the LLM API: the same as the app's own chat tab, stated in the README |
| P9 | **done** | 2026-09-04 · `v0.9` | predictions front and center (user-requested after reviewing the live app: "where are the predictions?"), version 0.9.0, design `docs/p9_design.md`: **Track A visibility** — the 🔮 model chip (any spec with `model_id`), prediction wording on site_ranking/hotspot excess, `studio_explain` → "תחזית והסבר לאתר" + a markdown per-site prediction card (μ, NB 90 % interval, observed, verdict מעל/מתחת/בתוך, top-3 drivers), triage routes תחזית/פרופיל סיכון/מה אם; **Track B, the P5 cut revived** — the severity family: person-level multi:softprob (340,498 rows 2010–2024, person-12 features incl. sentinel→NULL rules, ONE accidents join on the composite key; leakage exclusions STRUCTURAL in the matrix SQL), 1/share class weights frozen from the train window, a DISCRIMINATION gate (fatal recall ≥ 0.5 · AUC(fatal) ≥ 0.8 · overfit gap ≤ 0.05, all plugin-labelled — calibration deliberately not gated: the severe share triples 6.1 %→19.4 % over the era), `studio_train_severity` / `studio_validate_severity` (decile-lift face) / `severity_predict` (profile → RELATIVE distribution vs the holdout baseline) / `what_if` (four canned switches) = 23 actions; registry family-threading fixed (the latent P4 family-blind bug, two-family regression test); studio-fixture person rows on a SEPARATE LCG (planted signal: person-12 validates AUC ≈ 0.845, shuffled rejected AUC ≈ 0.46); three new plotly builders; studio_deploy/studio_models family-switched; about shows both deployments. Sweep (19 agents; 3 died on the spend limit — fixture-tests and docs covered inline): 8 distinct findings ALL fixed — the mediums: what_if wrote Hebrew into the strict-ASCII spec.basis (ASCII switch slugs now), the excess hotspot map never carried a top-level model_id so the 🔮 chip skipped it, and the prediction card's tight en-dash ranges flipped in the browser ("117–79") — the P8 pitfall's markdown-face variant, LRM-pinned now (plus the training card's era range); the lows: the severity family's contract_version was write-only (severity.contract_check twin + test), studio_deploy's rejected/unreadable remedies named the site trainer for severity models, the chip tail "צפוי מול מה שקרה בפועל" was false on faces with no observed side (spec-driven chip text now), and keep_deployed was computed from a pre-compute stale read in BOTH validate actions (registry.record_gate derives status under the lock); CLAUDE.md's frozen-weights claim corrected to the train-window values 69.48/11.21/1.116 |

## Phase map

| Phase | Name | Ships | Tag | Rough size |
|---|---|---|---|---|
| P0 | Ground & spike | installed clone + sister plugins, live copy connected, five spike answers, repo skeleton + docs | v0.0 | ½–1 day |
| P1 | Skeleton + answer envelope | `trend`, `naive_vs_correct`, `about`; envelope + `view`; tests; installs on clone | v0.1 | 1 day |
| P2 | Analytical tier | `segment_rates`, `severity_profile`, `vehicle_cells_ranking`, `before_after`, `weather_check`, `triage`; demo-site shortlist | v0.2 | 2 days |
| P3 | 🚦 page (Layer 1) | RTL React page, tabs, answer anatomy, refusal cards, Leaflet `hotspot_map` (observed) | v0.3 | 2 days |
| P4 | Studio: site model + ledger | registry, train/validate/deploy, `site_ranking`, map `excess`, `studio_models`, header wiring, **ledger + `finding_card`** | v0.4 | 2–3 days |
| P5 | Stretch | `studio_explain`; `two_wheelers`; severity model; `what_if` | v0.5 | 1–2 days, cut freely |
| P6 | Demo hardening | cassette recorder, seeded-dir rehearsal, Plan-B deck, DEMO.md, two rehearsals | v0.6 | 1 day |
| P7 | Wrap | PITFALLS consolidation, participant-scoping notes, handoff, release from committed tree | v0.7 | ½ day |

## P0 — Ground & spike (no plugin code yet)

Goal: prove the load-bearing assumptions and put the workspace in its final shape.

1. **Install the clone:** `cd app; .\install.ps1` (pip path; no uv). Record install time and any
   long-path issue. Then dev tools + sister plugins into the same venv:
   `app\.venv\Scripts\python -m pip install pytest build`;
   `app\.venv\Scripts\python -m pip install nl2sql-eda --extra-index-url https://amir-kh-z.github.io/nl2sql-core/simple/`;
   `app\.venv\Scripts\python -m pip install c:\Users\A\dev\nl2sql-shapes` (not on the index; path
   install — record if it fails on 3.14).
2. **Re-point the connection** (decision 1): show the diff of
   `%LOCALAPPDATA%\nl2sql-core\added_connections.json` (`israel_accidents.path` →
   `C:\data\israel_accidents\israel_accidents.duckdb`), apply after approval. `attrib +R` on the
   Desktop folder's files.
3. **Run the app:** `cd app; .\run.ps1` → Connections shows `israel_accidents`; schema browser
   31 tables + 12 views; `🔬 EDA` and `📐 Shapes` tabs present after the restart.
4. **Spike A — `ctx.query` is unscoped, and what chat actually sees:** copy `app\plugin-template`
   to `c:\tmp\spike-mod\`, add one action `SELECT count(*) FROM weather_hourly` via `ctx.query`,
   `pip install -e` into `app\.venv`, run on the 🧩 Modules page → 10,519,200. Then measure the
   chat side: `GET /api/schema?db=israel_accidents` → count `Table:` headers in `schema_text`
   (expect 43) and confirm `weather_hourly` appears. Conclusion to record: scope.json never gates
   `ctx.query`, and chat already sees every object — the gap is rules, not visibility.
5. **Spike B — verification answers** through `Context(db_path=...)` in a throwaway script: 439
   killed 2024; 5,458 slight; 8,315 casualty accidents. Also try the built-in chat with the `claude`
   CLI present and no key — record whether it answers and what it costs.
6. **Spike C — xgboost runtime on 3.14.6:** scratch venv in `c:\tmp\xgb314\`; `pip install xgboost`
   (py3-none wheel; numpy has cp314 wheels); toy `count:poisson`; `pred_contribs=True` sums to the
   prediction. Only if this fails → numpy-IRLS Poisson contingency.
7. **Spike D — Hebrew in matplotlib:** confirm `from bidi.algorithm import get_display` imports
   from `app\.venv`; render one Hebrew title + Hebrew tick labels through `get_display(s,
   base_dir="R")` and eyeball the order (fonts are fine — DejaVu Sans covers Hebrew; the risk is
   ordering). Only if glyph boxes appear, bundle Noto Sans Hebrew.
8. **Spike E — RTL page + offline Leaflet:** in the spike module, a throwaway Vite page with
   `dir="rtl"`, one LTR number island, and Leaflet drawing a bundled GeoJSON with no tile layer
   and `circleMarker`s, mounted via `nl2sql.pages` (entry-point name = Vite base segment). Proves
   the restart-after-install pitfall early; uninstall afterwards.
9. **Repo skeleton:** `git init` in `nl2sql-accidents-plugin\`; copy the three PLAN files to
   `docs/`; `PITFALLS.md` (format: `## <date> · <title>` / what happened / root cause / what the
   real build & participants should do); `CLAUDE.md` (rules distilled from concept map §1, §3,
   incl. the internal-use display clarification); `.gitignore` = the precedent set
   (`__pycache__/`, `*.pyc`, `*.egg-info/`, `.venv/`, `.pytest_cache/`, `dist/`, `build/`,
   `web/node_modules/`) — **`nl2sql_roadsafety/webdist/` IS committed** (Shapes/EDA precedent, so
   the wheel builds without node; decided here, not re-opened in P3); README with the private notice.

Acceptance: app runs on the clone with the live copy and both sister tabs; Spikes A–E answered in
`docs/spikes.md` + `PITFALLS.md`; `[P0]` commit; tag `v0.0`. Data-dir state: shared default.

## P1 — Skeleton + answer envelope

- `pyproject.toml`: dist `nl2sql-roadsafety-lab` 0.1.0; `requires-python = ">=3.11"` (`[ml]` documented
  3.12+); `[build-system] requires = ["setuptools>=77"]`; `[tool.setuptools] packages =
  ["nl2sql_roadsafety"]`; no engine dependency; `[project.optional-dependencies] ml = ["xgboost"]`,
  `dev = ["pytest", "build"]`; `[project.entry-points."nl2sql.modules"] accidents =
  "nl2sql_roadsafety:MODULE"` (pages entry point added in P3 with the name `accidents`).
- Package layout: `nl2sql_roadsafety/{__init__.py (MODULE), sqlkit.py (case filter, keys, sentinel
  helpers, input coercion, Byar CI), envelope.py (denominator/caveat/credit/note builders, view
  dispatch), charts.py (matplotlib, png footer credit, bidi labels), actions/{trend,trap,about}.py,
  dbcheck.py}`.
- `about` refuses readably on a non-accidents connection (probe `accidents.case_type_code`).
- Tests per concept map §8: fixture DB, Registry-driven, contract test (incl. `view`), live smoke
  (skipped if absent), data-dir reset on teardown.
- Install into the clone: `app\.venv\Scripts\python -m pip install -e "nl2sql-accidents-plugin[dev]"`;
  restart; the three actions render on the 🧩 Modules page with note + credit in the png.
- Ultracode (optional): adversarial check of the two actions' SQL against dossier §5.

Acceptance: three actions on the clone's Modules page; `..\app\.venv\Scripts\python -m pytest -q`
green from the plugin repo; `[P1]`, `v0.1`. Data-dir state: shared default (no registry needed).

## P2 — Analytical tier

Actions from concept map §4.1 (minus `hotspot_map`, `two_wheelers`): `segment_rates` (shared
`units` CTE + exact assignment predicate, live coverage), `severity_profile` (joins stated,
`age_group_code`), `vehicle_cells_ranking` (`global_rate`, 3 tiers, exposure > 0),
`before_after` (network control, 8-count SE, n/a on thin cells, site key syntax, window
validation), `weather_check` (0.1 mm threshold), `triage`.
- Each action: recipe from concept map §4.1, envelope + `view`, PNG, fixture test with a planted
  known answer, live smoke assertion on at least one aggregate the dossier states (weather 56.8 %,
  units 6,233).
- `tools/find_demo_site.py`: shortlist demo sites by casualty count (interurban segments 2017+)
  with ≥ 6 records per cell within ±3 years of a candidate change date (share-flip detector or a
  known project) → `docs/demo/sites.md` (provisional; confirmed in P4).
- Ultracode (recommended): fan-out implementation per action + adversarial verification of every
  statement against the golden rules (§5.1–5.5, §7 metrics, the units/assignment recipes) + test
  generation.
- **Sweep outcome (2026-08-30):** the adversarial sweep (SQL vs golden rules + caveats/docs checkers, refuters per
  finding) confirmed 23 findings, refuted 1 (before_after's caveat overflow is by design); all 23 fixed before
  acceptance — data-driven caveat numbers (0-mm rain share, coverage shape, APE table, band-0 cells dropped by
  `known_engine`), road-scoped coverage, `road_km = 0` as "not coded" on both sides (coverage 71.5 → 70.4 %),
  deterministic names, weather refusal on empty ranges, triage regex false positives, test/doc corrections. The
  arithmetic and edge-case checkers never ran (spend limit) — Byar/EB/Double-DiD recomputed inline instead
  (see `PITFALLS.md` 2026-08-30).

Acceptance: all six on the Modules page; suite green; `PITFALLS.md` updated; `[P2]`, `v0.2`.
Data-dir state: shared default (no registry needed).

## P3 — 🚦 page (Layer 1)

- `web/` (Vite + React), `base: "/page/accidents/"`, output `nl2sql_roadsafety/webdist/` (committed);
  `page.py` stdlib-only returning `{"path", "label": "🚦 תאונות"}`; `[project.entry-points.
  "nl2sql.pages"] accidents = "nl2sql_roadsafety.page:page"`; `MANIFEST.in recursive-include
  nl2sql_roadsafety/webdist *` + `[tool.setuptools.package-data] nl2sql_roadsafety = ["webdist/**/*"]`;
  test asserting entry-point name == Vite base segment.
- RTL: `dir="rtl" lang="he"`, logical CSS, LTR islands; tabs per concept map §6; answer anatomy
  (badge, ribbon, show-SQL from `spec.sql`, credit footer, refusal card); `about` header strip;
  `triage` box; empty states pointing to סטודיו.
- `hotspot_map` action (observed counts; `excess` wired in P4): aggregate-first, deduped junction
  dimension, segment geometry from geocoded accidents (Point at mean lat/lon for P3), optional
  `points` layer; returns `{geojson, png_base64, rows, …}`. Leaflet with the bundled Israel GeoJSON
  imported as a JSON module, no tile layer, `L.circleMarker` only, `leaflet/dist/leaflet.css`
  imported from node_modules; png fallback. Record in `PITFALLS.md` as the first non-echarts page.
- Record how the participants' template should do the page build (node version, commit webdist).
- Install → **restart** → tab appears (record the restart pitfall verbatim for participants).

Acceptance: page works on the clone from a **built wheel** (`app\.venv\Scripts\python -m build`
in the repo, then `pip install dist\…whl`, not `-e`); Layer 0 still renders everything; `[P3]`,
`v0.3`. Data-dir state: shared default (studio tabs show the empty state).

## P4 — Studio: site model + ledger

- `registry.py` under `ctx.data_dir()/accidents/models/`; `meta.json` contract; `deployed.json`.
- `panel.py`: full 1,311-segment × year grid 2017–2024 (zero years included), `doc-11` features
  as in concept map §4.2 — `adt_asof` with national-median fill + `adt_known`, `lag1`, static
  segment attributes frozen from ALL accident records 2005–`train_until` (both series), no offset.
- `studio_train_site`, `studio_validate` (Spearman ≥ 0.3, calibration ±25 %, **mean** per-row
  deviance ratio ≤ 1.5 — thresholds in one constants block, the 1.5 labelled plugin-chosen; α by
  moments stored in `meta.json`), `studio_deploy` (refuses rejected ids with reasons),
  `studio_models`, `site_ranking` (excess = observed − μ, `EB_estimate`, NB 90 % interval from α),
  map `color_by=excess`.
- Wire `about` and the page header strip to `registry.deployed()`; empty states in נקודות תורפה
  flip when a deployment exists.
- **Ledger** (⚖️ mandatory): `ledger.jsonl` append in the action dispatcher, `finding_card`,
  `ledger_list`, tab ממצאים.
- `[ml]` missing → every studio action returns `Result.error` with the exact pip command.
- Tests: planted panel where one model passes and a shuffled-target model is rejected; deploy
  refuses a rejected id; `site_ranking` refuses with no deployment; leakage test (static attributes
  unchanged when target-window rows are removed); registry survives a data-dir move (subprocess).
- Confirm the demo site: the P2 provisional segment must be in the excess top-10, else re-choose
  from the intersection; final `docs/demo/sites.md`.
- Seminar seed in the shared data dir: one deployed model + one rejected model (`train_until=2018`,
  shuffled preset) + the rehearsal `before_after` ledger entry.
- Ultracode (recommended): verification of the panel SQL (never `traffic_adt_filled`; no feature
  from the target window's casualty rows), the gate math, α, and the feature-contract round trip.

Acceptance: train→validate→deploy→rank on the clone with the live DB, timings recorded; ledger
entry visible via `ledger_list`; `[P4]`, `v0.4`. Data-dir state: shared default, **ending
seeded** (one deployed + one rejected); the data-dir-move test runs under
`NL2SQL_CORE_DATA_DIR=<tmp>` in a subprocess and is torn down.

## P5 — Stretch (cut freely, in this order)

1. `studio_explain` (TreeSHAP per unit — top-5 φ as lines per year + observed/predicted panel;
   global mean|φ|; SHAP warnings in caveats; exact-sum test on the log-rate scale).
2. `two_wheelers`.
3. Severity model cycle (`studio_train_severity` … `severity_predict`, class weights `1/share`,
   plugin gate labelled as such), `what_if`.

Acceptance per item; `[P5]`, `v0.5`. Data-dir state: shared default, seeded from P4.

## P6 — Demo hardening

- `tools/record_cassettes.py` (the app has no record switch): run from `app\` with the clone's
  venv, **no `ANTHROPIC_API_KEY`** in the environment (the cassette hook lives only in the no-key
  CLI branch), `nl2sql_engine.configure(cassette_dir=<app>\cassettes, record=True)`, then call the
  clone's own `api.adapters.run_question(...)` per scripted question with the exact bodies the Chat
  UI sends (deployed method, empty history) so the prompt is built by the same code path. Run it as
  the **last** P6 step (after every sidecar/learned-example change); verify `NL2SQL_REPLAY=1`
  replays with `replayed: true`; also verify the bypass with a key present and document it.
- Fresh-experience rehearsal: `NL2SQL_CORE_DATA_DIR=c:\tmp\demo-data` → empty registry → seed via
  the studio → full script run; then the shared-dir run (no env var). Timings, warm-up numbers.
- `docs/demo/DEMO.md` = PLAN 2 finalized with the real site, inputs, and screenshots; `plan_b.pdf`
  — both hold chart/ranking/card frames only (no drill-down popup / point-layer captures in
  anything committed; a row-level fallback frame, if wanted, lives under `C:\data\demo\`).
- Demo machine = the user's laptop (the DB never moves); two rehearsals with the projector setup
  (needs the course owner's date).

Acceptance: full script runs twice without a fallback; `[P6]`, `v0.6`. Data-dir state: both — the
fresh `c:\tmp\demo-data` run and the shared seeded run; the shared dir is the one used on stage.

## P7 — Wrap

- `PITFALLS.md` consolidated and categorized (packaging / API / SQL / RTL / map / demo / license);
  `docs/participants.md`: which actions form the teachable band, the planning prompt, the seed
  skeleton proposal (input for the participant scoping decision, made after this).
- Handoff: README (install with/without `[ml]`, license rules), `CHANGELOG.md`, version 0.7.0;
  build the wheel from a committed tree; **no index publish** without an explicit yes.
- Context refresh: update `context\` pointers and the dossier so the next session starts warm.

Acceptance: `[P7]`, `v0.7`. Data-dir state: shared seeded (unchanged).

## Cross-cutting

- **Pitfall ledger discipline:** write the entry when the stumble happens, not at phase end.
- **Data-dir state** stated in every acceptance (done above).
- **License checklist** per phase: credit in every png and note; nothing under `C:\data` or the
  Desktop folder copied into or referenced from git; no data in test fixtures; committed
  screenshots are chart/ranking/card frames. (Display level is unrestricted — internal use.)
- **Open external asks** (the course owner): seminar date · 15-steps DoD · "one plugin" ok — tracked at
  the top of `docs/plan.md`.
