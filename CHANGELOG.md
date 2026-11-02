# Changelog — nl2sql-roadsafety-lab (the Task-4 pathfinder)

## kit — 2026-10-25 · the participants' kit `nl2sql-accidents-example-mcp` (0.14.3, package unchanged)
A frozen export of the pathfinder repository at `c39991f` for the course participants, built in its own repository
beside a fresh clone of the closed core and verified on it. The Python package and the wheel are the 0.14.3 ones.
- **Installers**: `install-chat.bat` now also registers the server with **Claude Code** (user scope, `claude mcp add`
  after removing a stale entry; `-NoClaudeCode` keeps it Desktop-only; without a `claude` command it prints the
  one-liner as before). The sibling-folder example names this repository. The final hints point at the next two
  double-clicks.
- **`seed-models.bat` / `tools/seed_models.py`**: train → validate → deploy the two reference models in-process
  (site 2023 doc-11 s42, severity 2022 person-12 s42) so every pinned number in the docs appears on a fresh machine;
  idempotent per family, `-Force` trains again.
- **Docs**: README pair (English + Hebrew) written for participants — three double-clicks, the first ten minutes, the
  chat channel, the thirteen-question set, troubleshooting; `docs/DOSSIER.md` brought in from the lab workspace;
  `CLAUDE.md` re-headed for a kit that sits beside the app; GUIDE/MCP_DEMO notes where the instructor's stage leaked.
- **Hardened during the instructor's acceptance and the clean-room run (2026-10-25)**: the Desktop guard identifies
  Claude Desktop by path (Claude Code's engine is also `claude.exe`); the Desktop entry is written into every config
  location Desktop has used (classic, LocalCache, `Claude-Data`); the same version is never reinstalled and a due
  replacement names/stops the processes holding the files (`-Reinstall` repairs); `-CheckOnly` reports cleanly; the
  engine version is checked (1.6.0 for the sidebar page, upgrade offered) and the verify step tolerates an older
  core; Claude Code is registered through `claude` on PATH, else the VS Code extension's own binary, else Desktop's.
- **Guides (2026-10-29)**: `docs/MCP_GUIDE` (how to use the chat channel and why it exists — for the researcher who
  already knows what to ask) and `docs/BUILD_YOUR_OWN_MCP` (the server pattern transferred to a starter-derived plugin,
  step by step, with the three Claude Code prompts), each in Hebrew and English; the repository renamed to
  `nl2sql-accidents-example-mcp` so it cannot collide with anyone's own plugin.
- **Left out on purpose**: the seminar run-book, the deck generator, `plan_b.pdf`, the rehearsal/preflight/cassette
  tooling and the web-tunnel script (no hosted server for this database).

## unreleased — 2026-10-19 · M2: hardening for real researchers (0.14.3)
Everything phase A (`docs/mcp_acceptance.md`) and the 2026-09-25 play session asked for. Thirteen tools now.
- **Column legend** (`render.COLUMN_NOTES`, `HIDDEN_COLUMNS`): a one-line מקרא under every table names the helper
  columns (`people` = everyone involved incl. the uninjured — a coverage check, never "injured"; `killed` people vs
  `fatal_accidents` events; `mu`, `excess`, `eb`, `lo90/hi90`, `ratio`, `p_baseline`…); the internal `covered` flag is
  hidden. Instructions: state a number only with the column it came from.
- **`roadsafety_find`** (`mcp/lookup.py`): a site by NAME → the key the other tools take — segment names
  (traffic_segments, latest vintage), non-urban junction names ("צומת העשור" → `njunction:433`), urban junctions by
  street/city (→ `ujunction:<city>/<code>`, with casualty-accident counts), settlements. A navigation helper over
  `ctx.query` (no Result, no ledger line; audited like every tool). Phase A's question 4 could not reach the junction
  without it.
- **The hard confirmation gate**: `roadsafety_studio` is async and takes the SDK `Context`; for train/deploy, when the
  client advertises elicitation the SERVER asks the person through a form and proceeds only on an explicit accept —
  `confirm=true` is ignored there. Without the capability (Claude Desktop, claude.ai) the `# ⏸` flag card stays.
  A decline returns `# ⛔` and runs nothing. Verified in-process (stream mode) and live headless through Claude Code.
- **`--tools read-only`**: the studio leaves the catalog entirely (automation, shared servers); `build_server(read_only=)`.
- **Hebrew synonym table** in the server instructions (מודל חומרה / מודל אתר / מסוכן = excess / צומת ≠ מקטע / לפני-אחרי /
  מה אם / למה / פנקס) and sharper `roadsafety_finding` wording (a card promotes a LEDGER entry, never a chat message).
- **Login brute-force limits** on the web channel: 5 wrong passphrases invalidate the login id (start again from
  Claude); 30 failures per 10 minutes across all logins → 429 with Retry-After.
- Audit lines exclude the injected context; 13 new tests (legend, find incl. metacharacters, async wrapper, the
  gate accept/decline/unavailable, read-only, rate limits). Also fixed: a half-installed venv after a reinstall under
  Desktop's running server (PITFALLS 2026-10-16) — a test now pins the install in site-packages exactly once.
- **The talk deck and the recording script** (2026-10-20, 2026-10-24): `docs/demo/mcp_roadsafety_he.pptx`, 17 Hebrew
  slides (why, what MCP is, the catalog, anatomy of an answer, the rules, the models, governance, data flow,
  acceptance, the demo agenda), generated by `docs/demo/deck/build.js` + the bidi post-pass `fix_rtl.py` (PITFALLS
  2026-10-20; the pptx skill's `apply_theme.js` stays local: copyrighted, gitignored); `docs/demo/MCP_DEMO.md`, the
  Claude Desktop take: pre-flight with the ledger trim, ten prompts with their pinned numbers, the after-take checks.

## unreleased — 2026-10-16 · M3: the web channel — the same server from claude.ai in a browser (0.14.2)
The instructor wants to work from claude.ai in Chrome, not Desktop. A browser reaches only remote connectors
(public HTTPS + OAuth), so the stdio server gained a second transport and its own login. Design + as-built:
`docs/m1_design.md` §M3; the acceptance protocol for any channel: `docs/mcp_acceptance.md`.
- **`nl2sql_roadsafety/mcp/web.py`** — `WebConfig` (public URL, passphrase, store), `PassphraseProvider` = the
  SDK's `OAuthAuthorizationServerProvider` for one lab (Dynamic Client Registration, PKCE codes, 1 h access +
  30 d refresh tokens with rotation, revocation; clients/tokens persist under `accidents/mcp_web/oauth.json`,
  codes and pending logins in memory), a Hebrew login page (display name + shared passphrase, constant-time
  compare), a landing page and `/healthz`. `build_web_server()` = `build_server()` + `AuthSettings`
  (`validate_token_resource=False`: the verifier IS the issuer) + the provider; the SDK mounts `/.well-known/*`,
  `/register`, `/authorize`, `/token`, `/revoke` and the bearer middleware itself.
- **`server.py`**: `--transport http --host --port --public-url [--no-auth] [--channel]`; `--no-auth` only on
  loopback; `parse_args` / `make_server` / `transport_security` factored for tests; DNS-rebinding protection on
  the MCP endpoint (loopback forms + the tunnel's host). `build_server(**mcp_kwargs)` passes auth through.
- **`runner.py`**: every audit line carries `channel` (local | web) and `user` (the OAuth login name via the
  SDK's auth context; "local" on stdio).
- **`tools/web_tunnel.ps1`**: downloads cloudflared once to `%LOCALAPPDATA%\nl2sql-roadsafety\`, opens a quick
  tunnel to 127.0.0.1:<port> (`--http-host-header` pins the Host the server sees), starts the server with the
  tunnel's `https://…trycloudflare.com` as `--public-url`, prints the connector URL for claude.ai → Settings →
  Connectors → Add custom connector. `-ScratchDataDir` for consequence-free demos. The address and all tokens
  die with the window — a demo channel, not a service.
- **Phase A result** (`docs/mcp_acceptance.md`): the Desktop bridge test is NEGATIVE — Desktop announces the tools
  to its cloud bridge but claude.ai's chat never lists them; participants' browser path = Claude Desktop, the
  web server = the instructor's demo. Q1 + Q2 of the protocol pass in Desktop.
- 10 new tests (`tests/test_mcp_web.py`: metadata, DCR, authorize → login → code → token, refusals — wrong
  passphrase, empty name, stale login, one-use and expired codes, wrong PKCE, foreign Host —, refresh
  rotation, persistence incl. a corrupt store, MCP calls with a bearer and the audit `user`, CLI validation).
- CBS: aggregate answers and PNGs transit Anthropic's API like any chat message; row-level faces stay excluded;
  the same transit the app's own chat tab has always had (README, GUIDE §8).

## unreleased — 2026-09-23 · 0.14.1: the Claude Desktop config path is detected, not assumed
The first real Desktop registration (the instructor's machine) wrote to `%APPDATA%\Claude\...` and Desktop
never saw it: the Microsoft-Store (MSIX) build virtualizes Roaming and reads
`%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json` (its main.log says so).
- `mcp.register.default_config_path()` prefers the package path when it exists; `--config` is now optional,
  `--print-path` prints the detection, and the merge preserves Desktop's own `preferences` block.
- `install-plugin.ps1 -Mcp` asks the module for the path instead of hard-coding Roaming.
- PITFALLS entry (2026-09-23, packaging) with the two side lessons: closing Desktop's window is not quitting it,
  and `$env:APPDATA` is PowerShell, not cmd. Two new tests; wheel 0.14.1 in `release\`.

## v0.14 — 2026-09-23 · M1: the MCP server — the same actions from Claude's chat (0.14.0, commit `9a3f70c`, tag `v0.14`)
The course owner's second use case (his deck: one server, three channels — page, chat, automation; the core imported
in-process). Design + as-built: `docs/m1_design.md`. SOLO build, no agent fan-outs.
- **`nl2sql_roadsafety/mcp/`** — `runner` (engine `Context` + `Registry` in-process, exactly as the app's
  adapters; DB path from `--db` / `$NL2SQL_ROADSAFETY_DB`; one audit line per call in `accidents/mcp_audit.jsonl`,
  never numbers), `render` (Result → text + the PNG as an image block; tables capped at 60 rows, stated),
  `tools` (**12 intent-grouped tools over 29 actions** — `map_scene` excluded on purpose, `hotspot_map` never
  with points; a `face` param maps to each action's own `view`; `roadsafety_studio` train/deploy REFUSE without
  `confirm=true`), `server` (mcp SDK 2.x `MCPServer`, stdio; instructions, 5 resources, 3 prompts), `register`
  (the Claude Desktop config merge), `knowledge/rules.md`. Never imported by `__init__`.
- **Distribution:** extra `[mcp]` (`mcp>=2,<3`), console script `roadsafety-mcp`, `install-plugin.ps1 -Mcp`
  (installs the SDK, registers with Claude Desktop — refuses while Desktop runs, prints the entry instead —
  and prints the Claude Code `claude mcp add` line).
- **Fixed on the way:** the installer's verify block still looked for module/page id `accidents` after the
  rename (a fresh install would have failed); preflight `N_ACTIONS` 26 → 30 (stale since P13).
- 46 new tests (tools/render/audit/confirm gate/lifecycle/registration + the protocol in-process and over a
  real stdio subprocess); the suite is 464 green. Version 0.14.0 across the touch points; page rebuilt for the
  stamp; `release\` wheel swapped to 0.14.0 (98 files, no leaks).
- Live smoke through Claude Code (scratch data dir): the trap 50,145 vs 5,458, killed 2019–2024 ending at
  439, the 60/850 excess story (+39.7, rank 1/21 on road 60) — all through the tools. Known limit recorded
  (PITFALLS 2026-09-13): `confirm=true` gates the tool, not a headless agent → M2: MCP elicitation.

## unreleased — 2026-09-08 · the rename: the plugin takes the product's own name
The instructor's call, and the last thing blocking co-installability with the course owner's plugin.
- `nl2sql-accidents` → **`nl2sql-roadsafety-lab`** (dist) · `nl2sql_accidents` → **`nl2sql_roadsafety`**
  (import package, moved with `git mv` so history follows) · module id `accidents` → **`roadsafety`** ·
  page entry point and URL `/page/accidents/` → **`/page/roadsafety/`** (Vite `base` moved with it) ·
  sidebar label → **🚦 מעבדת הבטיחות בדרכים**, which every CBS credit line already carried.
- All four had to change together: the course owner's plugin claims the same dist name, package, module id and
  page id, and any single collision makes the two uninstallable side by side.
- Untouched on purpose: the repo folder name, the frozen per-phase design docs (history), and the
  `accidents/<name>` chart-spec strings (internal to our own Python↔page contract).
- The editable install was swapped (old dist uninstalled first, so no shadowing corpse) and the page
  rebuilt for the new base.

## v0.13 — 2026-09-08 · P12 + P13, accepted and tagged together (commit `58c2701`, tag `v0.13`)
P12 and P13 were built back-to-back and their edits interleave across the same files, so they landed in
ONE commit and v0.12 was never separately tagged. The P12 entry below records its own scope.

### P13: the borrow build — everything worth taking from the rival plugin, done our way
Two implementation waves (7 + 3 agents under ultracode), an adversarial verify wave (6 refuters), and a fix
wave. Instructor's policy change: **offline is no longer required** — online tile layers are permitted.
- **Four new actions (30 total).** `heat_matrix` — casualty counts on a zero-filled 7×24 day×hour grid (168
  cells always; the unknown-hour exclusion is data-driven — live hours are complete). `zone_ranking` +
  `city_ranking` — the database's own dark geographic aggregates (`accidents_by_taz` 2,637 zones,
  `accidents_by_municipality` at locality grain), a CUMULATIVE UNDATED snapshot: no year inputs by design,
  every answer carries the stamp + both universes' totals, and the demo beat is computed live per run — the
  official `accident_index` correlates 1.000 with density and 0.04 with per-capita risk. `ab_scan` — the
  before/after DISCOVERER: every segment × event year swept for the strongest network-adjusted DiD candidate,
  counted on ONE static latest-vintage geometry with the event year excluded from both windows so the
  before_after hand-off (site + change year pre-filled) reproduces the same cells; |z| is a rank score only,
  no CI by design. The verify wave killed wave 1's version — geometry splicing made 19/20 top candidates
  artifacts and flipped the leader's sign — and the rebuilt one re-verified CLEAN, with a chain-consistency
  test pinning cell equality against before_after. It independently rediscovers the demo's treated site
  (road:60/96-98.8, e=2017) as an improvement.
- **Existing actions widened.** `severity_profile`: by=lighting / hour_of_day (four buckets) / day_of_week /
  speed_limit (sentinels → explicit 'לא ידוע') / road_shape (the code-9 caveat computes the share and names
  the 2011 coding discontinuity); an empty covered frame now refuses instead of drawing a blank chart.
  `vehicle_cells_ranking group=cohort`: the honest cohort exposure curve (real per-cell exposure summed —
  never the rival's flat-fleet denominator); tier caveats state the ACTUAL tier counts. `about`: the
  `# מדדים אחרונים` KPI block (ledger-clean, feeds the page's stat cards). `studio_validate`: ROC/AUC
  (tie-collapsed, AUC ≡ Mann-Whitney, cross-pinned vs `auc_binary` at 1e-12; positive = top-decile observed,
  plugin-tagged) + a calibration scatter — chart-face DIAGNOSTICS only; the gate and every stored verdict
  are byte-identical.
- **The page, themed and joined up.** `theme.js` reads the CSS tokens live with a matchMedia re-render —
  dark mode is finally correct on every chart and the Leaflet chrome (the PNG twin stays white on purpose);
  ResizeObserver fixes plotly's hidden-tab re-measure hole; KPI stat cards with ▲/▼ deltas; sticky table
  headers + row hover + linked map↔table selection joined on site keys; progress placeholders + a
  ref-counted global busy chip; Hebrew reading-blurbs for all 30 actions; the studio orientation table;
  labelled reference lines; the Δ column on before/after tables; a second popup hand-off (הסבר מודל 🔮);
  segmented controls on short choice inputs; OSM tiles on the Leaflet map (tile-death fallback) and an OSM
  raster fallback mode on the MapLibre tab; the אזורים tab.
- **Honesty fixes from the verify wave.** ONE excess colour rule everywhere (z in the site's own NB units —
  hotspot_map/map_scene/page parity-tested); hotspot_map's degrade path ports map_scene's y1<2017 arm, leads
  junction requests with the segments-only truth, degrades (never refuses) on a model-path Refusal, resets
  y0e, and merges the reason into ONE line; zone/city ped_share ships its denominator column, breaks ties by
  it, counts tiny-denominator rows, and scopes its universe honestly; the population-vintage caveat rides
  per_capita only; city_ranking merges the snapshot's split rows per locality.
- Deferred, dormant: `studio_train_*` chart faces exist client-side but the actions still declare
  markdown/table views. Five PITFALLS entries recorded. Suite: 425 tests + live pins, all green.
- **Round 2 (2026-09-07, the instructor's side-by-side review of both running apps):** (1) the heat matrix
  is a REAL heatmap now — the bundle moved `plotly.js-basic-dist` → `plotly.js-cartesian-dist` (basic ships
  no heatmap trace; the 168-square scatter stand-in retired); (2) `severity_profile` gained
  `display=counts` (by=year only) — the rival's three-line severity trend, WITH our gap discipline
  (uncovered years break the lines under a grey band, never bridged — he draws straight through his missing
  years) and a `charts.severity_lines` PNG twin; the action now also rides the מגמות tab; (3) the studio
  **workbench** — the rival's Models-tab cockpit rebuilt over OUR Answer anatomy: per-family panels (site /
  severity), a shared parameter row, one-click verbs onto the SAME actions the full panels expose, one
  output region each, and it opens on the registry — `studio_models` is ledger-exempt now (registry
  inspection is state, not a finding), so the auto-load cannot pollute the stage ledger. In addition to the
  full panels, never instead.

### P12: SHAP explainability — the severity model explains itself (built 2026-09-05, shipped in v0.13)
- **`severity_explain`** (26 actions): the severity family's SHAP faces — a global beeswarm over the person
  matrix (class הרוג default / קשה selectable; deterministic 20k sample, ~7 s end to end live; full ~340k
  rows, under a minute), a per-feature **dependence view** (decoded category ticks, an explicit "לא ידוע"
  slot on BOTH axis kinds), the mean|φ| ranking with direction + unknown-share, and a plain-Hebrew drivers
  card with the four SHAP warnings. Honesty drawn, not declared: φ on the softmax MARGIN scale (never
  probability), value-color only for ordered features (nominal codes grey, NULL dots hollow, sex_code's
  live sentinel 0 masked from the scale), hover values decoded via `code_lookups` (the involved vehicle
  type decodes under the dictionary field `vehicle_type_code`), Σφ + bias = margin enforced at 1e-3 on
  every run and pinned at 1e-4 in tests against the fixture's planted signal.
- **Per-prediction waterfalls**: `severity_predict` and `what_if` charts gained a drivers panel — the ONE
  profile's top-5 φ + היתר + בסיס (what_if shows the Δφ story between the scenarios, the switch's own
  contribution named); the markdown cards carry the top drivers in words.
- **`studio_explain style=נחיל`**: the site model's global face as a beeswarm (full value coloring — all
  site features are ordered); triage routes severity-explain phrasing to `severity_explain`.
- Built under ultracode: a three-agent implementation fan-out over disjoint file ownership.

## v0.11 — 2026-09-05 · P11: the trend composer + the share-drift view
- **The trend composer** (page-only): up to 3 slicer rows behind `+ השוואה` (prefilled from row 1, הרץ הכול,
  minimize/remove), composed client-side — overlay on ONE shared y-axis iff identical gap_periods AND
  scale ratio ≤ 3, small multiples (matched x, free y) otherwise, NEVER two independent y-axes; the
  אוטו/מאוחד/מפוצל toggle overrides; a forced overlay across differing coverage drops the gap band and names
  the missing periods. Each run keeps its full envelope + its own ledger line. `Form` gained a `runTick` prop.
- **`severity_profile by=year`** — the share-drift exhibit: severity composition per year, chronological, with
  the caveat naming the drift and why the severity gate measures discrimination. Live-pinned: severe share
  6.1 % (2010) → 19.4 % (2024).
- Sweep: 14 findings fixed — the high: a remounting Form replayed a stale runTick and silently re-ran with
  default values; plus the closed-`<details>` zero-width plotly draw, current-values prefill (Form `onValues`),
  the row-1 stray separator, dark-theme token fixes, window-carrying LRM-pinned labels, and doc/comment drift.

Plugin for the Israel road-accidents database (CBS) on the NL2SQL closed core. Versions are immutable
once tagged; releases are built only from committed trees. Full per-phase detail (deviations included) lives in
`docs/plan.md`; every stumble in `PITFALLS.md` (categorized).

## v0.10 — 2026-09-05 · P10: מפה חיה — the advanced interactive map
- A new custom **מפה חיה** tab: MapLibre GL + deck.gl (own lazy chunk — the other tabs load unchanged) over an
  **offline PMTiles street basemap** of Israel (one-time `tools/fetch_basemap.py` download, ~171 MB, gitignored
  and wheel-excluded by three independent guards) with an automatic **dark data-canvas fallback** when the file
  is absent (wheel-only installs need nothing). The full geocoded cloud (218,144 points 2008–2024) renders on
  the GPU with client-side year/severity/day-night filters + a year animation (zero re-fetches), three
  clickable site layers, offline search (sites + locality centroids), Hebrew street labels (vendored glyphs +
  RTL plugin), a persistent CBS credit badge (+OSM attribution in street mode only) and deep-linkable scope.
- **The risk view**: `map_scene color_by=excess` (the "מול המודל" toggle) re-ranks and re-colors the
  segments layer by the deployed model's excess — the EB network screening as a map layer (diverging scale,
  significance rings, 🔮 chip in the legend); junctions stay counts-colored (no denominator — the golden
  rule drawn), and the mode falls back to counts with a caveat when nothing is deployed. Mark grammar
  (three instructor review calls): shape = entity class (square segment / filled circle non-urban / hollow
  circle urban junction), size = counts (meter-scaled with pixel clamps; road scopes auto-frame their
  corridor), and hues belong to MEANINGS only — the severity palette on the dots, the diverging scale on
  excess-mode segments; site marks themselves are neutral graphite. Model mode shows ALL panel segments
  (never just the red tail), colors by band distance (z) rather than outlier-normalized raw excess, and
  ships a client-side **z-distribution drawer** (residual-diagnostics EDA: center shift = calibration,
  right tail = the screening population).
- Two new actions (25 total): **map_scene** (the whole scene as ONE envelope — columnar cloud, site layers,
  gazetteer, coverage; hexbin-density PNG twin for Layer 0; `twin=false` for the page's fast fetch) and
  **site_profile** (the click panel: observed strip for every site kind; μ/excess/EB/interval/verdict/SHAP
  drivers for segments with a deployed site model; conditional severity profile — relative only — over the
  site's own person rows; junctions structurally never carry rates/excess; degrade-to-caveat, never refuse).
  `severity.matrix_sql` gained an optional site predicate (default byte-identical).
- Check infrastructure: `web/scripts/dom-dump.mjs` (CDP real-time headless DOM — the virtual-time recipe
  cannot see post-load fetches), `web/scripts/sync-basemap.mjs` (post-build hardlink; vite wipes webdist),
  a `basemap` preflight check (PASS/SKIP/FAIL), packaging leak-guard tests, and live pins (cloud = inline
  count equality, מחלף מורשה counts-only, 60/836 excess < 0 through the panel). Four new PITFALLS entries.
- Sweep (44 agents, 8 dimensions + adversarial refuters): 11 confirmed findings ALL fixed — highs: the
  רענון-היקף refetch trap (permanent blank tab), silent `error`-kind envelopes, raw exception text reaching
  the caveat contract on the excess degrade path, and the floored-lo90 z inflation (sd now from the un-floored
  upper half in both renderers); plus the instrument-switch caveat, legend band-boundary overclaim, signed-
  excess LRM pins, ASCII range hyphens across the new surfaces, and doc corrections (GUIDE §0, the 60/836
  verdict quote).

## v0.9 — 2026-09-04 · P9: predictions front and center
- Track A (visibility): the 🔮 model chip on every model-computed answer (any spec carrying `model_id`),
  prediction wording on site_ranking/hotspot-excess, `studio_explain` renamed "תחזית והסבר לאתר" + a new
  markdown **per-site prediction card** (μ, NB interval, observed, verdict, top-3 drivers), triage routes
  תחזית/מה-אם/פרופיל-סיכון. Track B (the P5 cut revived): the **severity family** — person-level XGBoost
  multi:softprob (340,498 casualty rows 2010–2024, person-12 features, 1/share class weights frozen from the
  train window) with its own **discrimination gate** (fatal recall ≥ 0.5, AUC(fatal) ≥ 0.8, overfit gap ≤ 0.05 —
  all plugin rules; calibration deliberately NOT gated: the severe share triples over the era) behind
  `studio_train_severity`/`studio_validate_severity`, plus `severity_predict` (profile → relative distribution)
  and `what_if` (two scenarios, four canned switches) — relative probabilities only, on every face. Registry
  family-blindness fixed (the latent P4 bug) with a two-family regression test. 23 actions; three new plotly
  builders; the חומרה tab gains the two prediction actions. Sweep: 8 findings fixed — highs: Hebrew in
  what_if's strict-ASCII basis, the excess map missing the 🔮 chip, browser-card en-dash ranges flipping (the
  P8 pitfall's markdown-face variant); plus the severity contract_version tripwire, family-aware deploy
  remedies, spec-driven chip text, and the stale keep_deployed read (registry.record_gate, both families).

## v0.8 — 2026-09-03 · P8: chart & Hebrew polish
- Plotly.js on the 🚦 page (13 interactive builders over the same specs, offline `plotly.js-basic-dist` 3.7.0,
  PNG twins kept for Layer 0/Plan-B/fallback); the PNG bidi fix (base ALWAYS R, LRM-pinned parens and number
  ranges, the Rust-L4 trap documented) + bundled Assistant font (SIL OFL) via the `font.family` list; RTL layout
  fixes (legend order, caveat indents, annotation collisions, hbars density cap). 14-case byte-exact bidi
  fixture; 286 tests. Sweep (27 agents): 9 findings fixed — incl. the auto-base-direction revert and the plotly
  monthly-trend composite labels.

## v0.7 — 2026-09-02 · P7: wrap
- PITFALLS.md categorized (34 entries, 10 categories, index; chronology preserved); `docs/participants.md`
  (teachable band, seed skeleton, planning prompt — the scoping decision's input); this CHANGELOG; README handoff
  polish; the `context\` pack refreshed (kickoff status header + dossier addendum). Release wheel built from the
  committed tree — NOT published to any index.

## v0.6 — 2026-09-02 · P6: demo hardening
- `tools/preflight.py` (10 automated pre-show checks incl. stage re-verification, booster load probe, chat-history
  guard), `tools/rehearse.py` (all demo beats via the module API with timings), `tools/record_cassettes.py`
  (2 chat cassettes recorded keylessly, replay-verified at cost 0), `tools/make_plan_b.py` → `docs/demo/plan_b.pdf`
  (12 fallback frames), `docs/demo/DEMO.md` (the run-book). 35-agent sweep: 10 findings fixed (highs: the
  chat-history cassette miss, the 0-byte-booster false pass, the wrong finding-card frame). The shared-data-dir
  "side door" pitfall gained its third vector (env read-once ordering).

## v0.5 — 2026-09-02 · P5: stretch (studio_explain + two_wheelers)
- `studio_explain`: TreeSHAP over the deployed site model (per-site top-5 φ per year beside observed-vs-predicted;
  global mean|φ|; Σφ = ln μ enforced at runtime). `two_wheelers`: motorcycle rates per 1,000 active registered
  vehicles by cc band (2013+) on a fleet-driven zero-filled grid computed under the golden rules (the curated
  view's cohort join undercounts the fleet); bicycles/e-bikes/e-scooters as counts-only rows. 19 actions;
  285 tests. Severity model + what_if cut by decision. Sweep: 6 findings fixed.

## v0.4 — 2026-09-02 · P4: the studio (built 09-01, accepted and tagged the next morning)
- Site model (XGBoost count:poisson over the full 1,311×2017–2024 panel), registry under the app data dir
  (atomic, tolerant, serialized — the WinError-5 sweep high), the validation gate (report thresholds + a labelled
  plugin rule; `train_until=2023` default — 2022 is genuinely rejected and kept as the governance artifact),
  `studio_train_site`/`studio_validate`/`studio_deploy`/`studio_models`, `site_ranking` (excess/EB/NB),
  `hotspot_map color_by=excess`, the findings ledger + `ledger_list`/`finding_card`. Sweep: 8 findings fixed.

## v0.3 — 2026-08-30 · P3: the 🚦 page
- React/Vite RTL page at `/page/accidents/` (six tabs, full answer anatomy, deep links, offline Leaflet with a
  355-vertex Israel outline shared with matplotlib), `hotspot_map` (observed counts, PNG twin). Sweep fixes incl.
  the urban-junction street-pair rule and the `99999999` sentinel.

## v0.2 — 2026-08-30 · P2: the analytical tier
- `segment_rates` (per-vkm with as-of vintages, Byar CI in SQL, live coverage 70.4 %), `severity_profile`,
  `vehicle_cells_ranking` (EB, Mkm), `before_after` (network control, double ratio), `weather_check`, `triage`
  (the rule-table refusal gate). 23 sweep findings fixed pre-acceptance.

## v0.1 — 2026-08-29 · P1: skeleton + envelope
- The answer envelope (denominator kinds, caveats, credit, refusal/route cards, `view` dispatch), `trend`,
  `naive_vs_correct` (50,145 vs 5,458), `about`; the fixture-DB test pattern; installs on the clone.

## v0.0 — 2026-08-28 · P0: ground & spikes
- Clone installed + sisters; working copy connected read-only; five spikes positive (unscoped ctx.query, keyless
  chat via the claude CLI, xgboost on 3.14, Hebrew matplotlib, RTL page + offline Leaflet); repo skeleton + docs.
