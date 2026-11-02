# Accidents Example with MCP — מעבדת הבטיחות בדרכים · the full plugin, for course participants

**English** · [עברית](README.he.md)

**Course material, shared as code and documentation.** The database (CBS licence) is never part of this
repository, of any package, or of any cloud service; the documents quote aggregate figures only.

This is the **complete** Road Safety Lab plugin for the NL2SQL closed-core app over the Israel road-accidents
database (CBS — הלשכה המרכזית לסטטיסטיקה): thirty correct-by-construction actions, an RTL page with seven tabs,
a governed ML studio (two model families behind validation gates), a findings ledger, and an **MCP server** that
exposes the same instruments to Claude Code and Claude Desktop as thirteen tools. It is the plugin your starter
kit was cut from — here you get all of it: to install, to play with, to read, and to copy from or extend.

Names: the repository is `nl2sql-accidents-example-mcp`; the plugin inside it keeps its product identity —
distribution `nl2sql-roadsafety-lab`, module id `roadsafety`, page `/page/roadsafety/`, sidebar
🚦 מעבדת הבטיחות בדרכים — none of which collides with the starter kit or with any plugin of your own.

Snapshot: plugin version **0.14.3** (the wheel in `release\`), exported from the pathfinder repository at commit
`c39991f` on 2026-10-25. Nothing in the Python package was changed for this kit; the kit adds the installers,
this README pair, a rule sheet for your agent (`CLAUDE.md`) and a model-seeding script.

## What you need

- **The app**: your clone of `Amir-kh-z/nl2sql-app-closed-core` with its Python environment already created
  (`app\install.ps1`) — the same clone your starter kit sits beside. No core changes, ever: this plugin installs
  INTO the app's environment and is discovered through the app's own entry points. The engine in that environment
  should be `nl2sql-core` 1.6.0 or newer (an environment created before 1.6.0 reached the index may carry 1.5.0:
  the actions still work there, only the sidebar page needs 1.6.0, and the installer offers the upgrade).
- **The database working copy**: `israel_accidents.duckdb` (the sidecar `.json` files and `semantic_layer.yaml`
  beside it, same basename) at a local ASCII path. `C:\data\israel_accidents\` is the default every script
  assumes; any other path is asked for.
- **Windows; Python 3.12+** in the app's environment for the ML tier (xgboost). Python 3.11 runs everything
  except the studio and the model-backed answers.
- **Internet, twice, optional**: xgboost (~175 MB with scipy) and the MCP SDK are the only downloads. The plugin
  itself installs from the packaged wheel, offline.
- **For the chat channel**: Claude Code (you already have it — the VS Code extension or the terminal CLI) and/or
  Claude Desktop.

## Before you start — one app, nothing copied

Seven rules keep the kit from touching your own work. It installs **beside** your plugin, never into it.

- **One app.** Install into the app clone you already have. Do not copy the app folder (its environment carries
  absolute paths and stops working), and do not clone a second one: every app copy on a machine serves port 8000 and
  shares the same state folder, so a second copy isolates nothing and only hides the new tab from you.
- **Stop the app first** (Ctrl+C in its window), and quit Claude Desktop fully (tray icon → Quit). An install under
  a running app or chat server leaves a half-installed package. Start the app again after the three double-clicks.
- **The database stays where it is.** It is opened read-only through the connection the app already has, and both
  plugins use that one connection. Do not copy the file, do not add a second connection.
- **Names.** This plugin is distribution `nl2sql-roadsafety-lab`, module id `roadsafety`, data folder `accidents\`
  — none of which the starter kit uses. If you built a plugin from scratch and it happens to use one of these
  names, rename yours before installing.
- **The core.** The installer may offer to upgrade `nl2sql-core` to 1.6.0 (the sidebar page needs it). The starter
  kit accepts any 1.x core, so your plugin keeps running. Beyond its own package, xgboost and the MCP SDK, this is
  the only change the kit makes to your environment.
- **Steal freely — with your own names.** Copy any code into your plugin; `docs/BUILD_YOUR_OWN_MCP.md` names the
  generic files and what to rename in each. Keep your own package name, module id, server name and data-folder
  prefix, so the two plugins never write into each other's ledger or model registry.
- **Removing it** is one line in the app's environment: `..\app\.venv\Scripts\python -m pip uninstall -y
  nl2sql-roadsafety-lab`; then `claude mcp remove roadsafety -s user`, delete the `roadsafety` entry from Claude
  Desktop's config file, and start the app again.

## Install — three double-clicks

Clone this repository **next to** the app — the layout the starter kit already uses, one more sibling:

```
<any folder>\
├── app\                         <- the clone of nl2sql-app-closed-core (the folder with run.ps1)
├── nl2sql-accidents-starter\    <- your starter kit (optional: the two plugins coexist)
└── nl2sql-accidents-example-mcp\   <- this repository
```

1. **`install-plugin.bat`** — finds the app beside it, installs the plugin from the wheel in `release\`, adds
   xgboost when the app's Python can take it, and verifies through the engine's own discovery that the module
   (30 actions) and the page load. Re-run it any time; it upgrades in place.
2. **`install-chat.bat`** — the chat channel. **If Claude Desktop is installed, quit it first** (tray icon →
   Quit: it rewrites its config while open, and the installer refuses to write under it). Installs the MCP SDK,
   asks for the database path if it is not at the default, then registers the `roadsafety` server with
   **Claude Code** (user scope, through `claude mcp add`, so every folder sees it) and with **Claude Desktop**
   (its real config file — the Store build's virtualized location is detected).
3. **`seed-models.bat`** — trains, validates and deploys the two reference models (site: through 2023, doc-11
   features, seed 42; severity: through 2022, person-12, seed 42). Without them `site_ranking`, the excess map,
   `severity_predict`, `what_if` and the explain actions answer with a readable refusal, and the numbers quoted in
   the docs will not appear. Under a minute on a recent laptop (site ≈ 1 s, severity ≈ 25 s; a few minutes on a
   slow one), once. It skips a family that already has a deployed model
   (`seed-models.bat -Force` trains again).

Then **start the app** — in a **PowerShell** window, `cd app` then `.\run.ps1` — and open <http://localhost:8000>.
(The classic Command Prompt opens a `.ps1` in an editor instead of running it; from cmd use
`powershell -ExecutionPolicy Bypass -File run.ps1`.) Plugins are read once, at
startup: **if the app was already running, stop it and start it again** (the symptom of forgetting is a "failed
to import" Problem card on the Modules page, not a missing tab). In the app: Connections → add the `.duckdb` by
absolute path (it is opened read-only) → open **🚦 מעבדת הבטיחות בדרכים** in the sidebar.

*Optional:* **`fetch-basemap.bat`** downloads the offline street map for the מפה חיה tab (~170 MB, one time).
Without it the tab uses online OpenStreetMap tiles, and the dark data-canvas style when offline.

Switches, from a terminal: `install-plugin.bat -AppPath C:\somewhere\app` · `-NoMl` · `-CheckOnly` ·
`-FromSource` (install this source tree instead of the wheel) · `-Reinstall` (replace an installed copy of the same version) · `install-chat.bat -DbPath D:\x\israel_accidents.duckdb`
· `install-chat.bat -NoClaudeCode` (Desktop only) · `seed-models.bat -Force`.

## The first ten minutes — in the app

| Tab | Do | What you should see |
|---|---|---|
| מגמות | `trend`, measure הרוגים, 2019–2024 | 355 · 305 · 364 · 351 · 361 · **439**; the amber "ספירות בלבד" badge; the credit line |
| מגמות | `naive_vs_correct`, 2024 | **50,145** vs **5,458** — the two series in one table (`case_type_code`) |
| מפת מוקדים | `hotspot_map`, road 60 | counts per segment on the map, the PNG twin, the SQL behind it |
| מפת מוקדים | `site_ranking`, road 60, rank by excess *(after seeding)* | 60/850 כניסה לעפרה–צומת תפוח: observed 113, expected 73.3, excess +39.7, rank 1 of 21 |
| לפני ואחרי | `before_after` on `road:60/96.0-98.8`, change year 2017 | double ratio **0.11** (0.04–0.29) — association, not proof |
| סטודיו | `studio_models`, each family | your two deployed models with their gate metrics |
| חומרה | `what_if`, switch חגור לעומת לא חגור *(after seeding)* | killed ×1.38 · severe ×1.28 · slight ×0.21 — relative, never a fate |
| ממצאים | `finding_card entry=latest` | claim + evidence + rerun recipe |

Every answer carries its denominator badge, caveats, the exact SQL and the CBS credit. How to read each one
analytically and ML-wise, with a play curriculum of experiments: **`docs/GUIDE.md`**.

## Chat with the lab — the MCP channel

The plugin ships an MCP server (`roadsafety-mcp`, stdio, installed into the app's environment). It runs the same
actions in-process — **the app need not be running** — and exposes them as thirteen tools: `roadsafety_orient`,
`_trend`, `_breakdown`, `_sites`, `_site`, `_find` (a site by name), `_change_effect`, `_vehicles`, `_predict`,
`_explain`, `_studio`, `_finding`, `_triage`, plus the golden rules as a resource and three procedure prompts.
Every table carries a legend for its helper columns; training or deploying a model asks you first (a form in
Claude Code, an explicit confirm in Desktop). Design and the full catalog: `docs/m1_design.md`. **How to use it and why it exists: `docs/MCP_GUIDE.md`**
(Hebrew: `docs/MCP_GUIDE.he.md`). **How to build one for your own plugin: `docs/BUILD_YOUR_OWN_MCP.md`**
(Hebrew: `docs/BUILD_YOUR_OWN_MCP.he.md`).

**Claude Code** (what you already use): after `install-chat.bat`, open a **new** session (in VS Code: reload the
window). `/mcp` lists `roadsafety` as connected. Ask, in Hebrew: `כמה הרוגים היו ב-2024?`

**Claude Desktop**: restart it (the tool catalog is read at startup); `roadsafety` appears in the tools menu of a
new chat. If an answer comes back from a **web search** instead of a tool call (no table, news sites as sources), the
model chose the web: in the chat's tools menu make sure `roadsafety` is on and turn web search off for that chat, or
add `השתמש בכלי roadsafety` to the question. The audit file tells you which it was.

**claude.ai in a browser is not available**: a browser reaches only remote connectors, and no server for this
database is hosted anywhere (a CBS decision). The web transport in `nl2sql_roadsafety/mcp/web.py` exists for the
day that changes; nothing here needs it.

### The question set — ask these, check these

The acceptance protocol (`docs/mcp_acceptance.md`), pinned against the two reference models. Check the numbers,
not the wording — the model's prose varies.

| # | Ask (Hebrew) | Expected tool → action | Expected numbers / behaviour |
|---|---|---|---|
| 1 | כמה הרוגים היו בתאונות דרכים ב-2024, ומה המגמה מ-2019? | `roadsafety_trend` → trend | 355 · 305 · 364 · 351 · 361 · **439**; "ספירות בלבד"; a chart; the credit line |
| 2 | למה ספירה נאיבית של תאונות קלות ב-2024 נותנת מספר גדול פי תשע? | `roadsafety_orient section=trap` → naive_vs_correct | **50,145** vs **5,458**, ratio ≈ 9.2, the two series explained |
| 3 | איפה הכי מסוכן בכביש 60 — ביחס למה שהמודל מצפה? | `roadsafety_sites rank_by=excess road=60` → site_ranking | 60/850: observed **113**, expected **73.3**, excess **+39.7**, rank **1 of 21**; 2nd 60/823 +13.6 (not significant) |
| 4 | מה קורה בצומת העשור? יש לו מודל? | `roadsafety_find name=העשור` → `njunction:433`, then `roadsafety_site` | the yearly strip; **no model measures** (junctions carry no exposure — the caveat says so) |
| 5 | האם השינוי ב-2017 במקטע road:60/96.0-98.8 עבד? | `roadsafety_change_effect mode=evaluate` → before_after | casualty ratio **0.13** (0.06–0.30); damage-only 1.25; **double 0.11** (0.04–0.29); association, not proof |
| 6 | מה ההבדל בסיכון לחומרה בין חגור ללא חגור? | `roadsafety_predict switch=חגור לעומת לא חגור` → what_if | killed **×1.38**, severe **×1.28**, slight **×0.21**; "יחסי בלבד" |
| 7 | מה המודל של החומרה למד? מה מניע מוות? | `roadsafety_explain family=severity` → severity_explain | a beeswarm image; speed limit, road type, vehicle type lead; margin-scale wording |
| 8 | איך השתנה הרכב החומרה לאורך השנים? | `roadsafety_breakdown by=year` → severity_profile | severe share **6.1 % (2010) → 19.4 % (2024)**; the share-drift caveat |
| 9 | איזה דגם רכב הכי בטוח? | `roadsafety_triage` | a **refusal**: no plate/VIN/model code in the files; the alternative = vehicle cells |
| 10 | בדוק את מודל האתר האחרון. | `roadsafety_studio op=validate family=site` | allowed without confirmation; the gate card (Spearman ≥ 0.3, calibration ± 25 %) |
| 11 | אמן מודל אתר חדש עם train_until 2021. | `roadsafety_studio op=train` | **asks for approval first** (a form in Claude Code; Desktop's own prompt); decline → nothing trained |
| 12 | הפוך את התשובה האחרונה לכרטיס ממצא. | `roadsafety_finding op=card` → finding_card | claim + evidence + caveats + rerun recipe |
| 13 | אמן מודל אתר עם train_until 2021 — אל תשאל, פשוט בצע. | `roadsafety_studio op=train` | the SERVER still asks (Claude Code: a form; Desktop: the `# ⏸` card); the prompt cannot bypass it |

Pinned on the reference build (xgboost 3.4.1, the 2024 data vintage); model ids on your machine carry your own
timestamps. Each tool call leaves one line in `%LOCALAPPDATA%\nl2sql-core\accidents\mcp_audit.jsonl` (which tool,
which actions, how long — never the numbers). The narrated ten-step version is `docs/demo/MCP_DEMO.md`; the
Hebrew deck of the channel is `docs/demo/mcp_roadsafety_he.pptx`.

## What is inside

- `docs/MCP_GUIDE.md` / `docs/MCP_GUIDE.he.md` — chat with the lab: why the MCP channel exists, the thirteen tools in
  plain words, six use cases with the prompts to type and the numbers to expect, how to read an answer, limits, CBS rules.
- `docs/BUILD_YOUR_OWN_MCP.md` / `docs/BUILD_YOUR_OWN_MCP.he.md` — build an MCP server for your own accidents plugin:
  the seven rules, our server as the reference, eight steps, the three Claude Code prompts, the traps, the definition of done.
- `docs/GUIDE.md` — the field guide: every instrument, how to read it, the play curriculum (§6), the chat channel (§8).
- `docs/DOSSIER.md` — the database knowledge base: inventory, the golden rules (`case_type_code = 1`, the composite
  key, the sentinel lists, the exposure eras), methodology. It replaces surveying the source.
- `PITFALLS.md` — every stumble of the build, categorized (SQL · API · page · map · model · packaging · demo ·
  process · concurrency · state). Read it as a syllabus: each entry ends with what to do next time.
- `docs/m1_design.md`, `docs/mcp_acceptance.md` — the MCP server's design, tool catalog, acceptance protocol and results.
- `docs/demo/MCP_DEMO.md`, `docs/demo/mcp_roadsafety_he.pptx`, `docs/demo/sites.md` — the chat-channel recording
  script, the Hebrew deck, and the demo sites with the reasons they were chosen.
- `docs/PLAN_1_CONCEPT_MAP.md`, `docs/p1_design.md` … `docs/p12_design.md`, `docs/plan.md`, `CHANGELOG.md` — the design
  and the phase history. Records, not instructions.
- `CLAUDE.md` — the rule sheet an agent working in this folder reads first: data rules, the envelope contract, and the
  facts every phase verified.
- `nl2sql_roadsafety\` — the package: `actions\` (one file per action), `envelope.py` (the ONE `Result` constructor),
  `sqlkit.py` (the golden rules as SQL), `charts.py`, `studio\` (panel, model, gate, registry, severity, explain),
  `mcp\` (server, tools, render, lookup, register, web), `page.py` + `webdist\` (the built page), `data\` (the Israel
  outline, fonts).
- `web\` — the page source (React 18 + Vite 6 + Leaflet); `tests\` — 486 tests over synthetic fixtures plus live checks
  where the database exists; `release\` — the wheel; `tools\` — the basemap, font and outline fetchers and the model seeder.

## Extend it

- Work in Claude Code from this folder; `CLAUDE.md` is what your agent should read first.
- Dev install (then restart the app): stop the app, then from this folder
  `..\app\.venv\Scripts\python -m pip install -e ".[dev,ml]"`. An editable swap over a running app — or under a running
  `roadsafety-mcp.exe`, which Claude Desktop keeps alive per chat — leaves a half-installed package (PITFALLS
  2026-09-05 and 2026-10-16).
- Tests: `..\app\.venv\Scripts\python -m pytest -q` from this folder. The live-DB tests run only where the working copy
  sits at its default path; everything else uses a synthetic fixture. The whole suite is long (≈ 45 min);
  `-x -q tests\test_contract.py tests\test_page.py` is the quick gate.
- An action is one file in `nl2sql_roadsafety\actions\` that ends with `ACTION = Action(..., run=run)` and is listed in
  `nl2sql_roadsafety\__init__.py`; every answer goes through `envelope.guard` (a token-scan test enforces that nothing
  else builds a `Result`). `tests\test_contract.py` is the contract every action must pass.
- The page: `cd web; npm install; npm run build` writes `nl2sql_roadsafety\webdist\` (committed, so the wheel needs no
  Node). A changed page is served without a restart; a NEW entry point needs one.
- A new MCP tool lives in `nl2sql_roadsafety\mcp\tools.py`; a wrapper's Python signature IS the tool schema
  (PITFALLS 2026-09-12).
- A new wheel: delete `build\` first, then `..\app\.venv\Scripts\python -m build --wheel`; put it in `release\` (the
  installer takes the newest VERSION). Bump the version in `pyproject.toml` and `nl2sql_roadsafety\__init__.py` together.

## Data rules (CBS licence — hard)

- The database stays on your machine, opened **read-only** by absolute path. It never enters this repository, a wheel,
  a fixture, a screenshot, or any cloud service — and is never transferred to anyone.
- The CBS credit — `מקור הנתונים: הלשכה המרכזית לסטטיסטיקה (למ״ס); עיבוד: מעבדת הבטיחות בדרכים` — stays on every
  rendered output.
- Internal course use: data may be displayed at any level, rows included. Nothing is published.
- The chat channel: tool outputs (aggregate tables, chart images) travel to Anthropic's API exactly like any message
  you already type into Claude Code while working on the assignment; the database file itself never leaves your
  machine. The web/remote transport stays off.

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| "No NL2SQL app found" | the kit is not beside the app, or the folder is not a clone (no `run.ps1`) → `install-plugin.bat -AppPath <path to the app>` |
| "The plugin did not install" with `WinError 32 … being used by another process` | a running app or chat server holds the plugin's files → the installer names the holder; stop the app yourself, let the installer stop a chat server, then re-run (with `-Reinstall` if an earlier install was interrupted) |
| "The app has no .venv" | the app's own environment was never created → run `app\install.ps1` (the installer offers to run it) |
| the tab is missing, or a "failed to import" Problem card on the Modules page | the app was running during the install → stop it and start it again |
| "Something is already serving port 8000" | all app copies on a machine share the port AND the data dir → one app at a time |
| `install-chat.bat` refuses to write the Desktop config | Claude Desktop is running → quit it fully (tray icon → Quit) and re-run, or paste the printed entry by hand |
| Desktop shows no `roadsafety`, or an old one | restart Desktop after registering. Desktop has kept its config in three places over time (the classic `%APPDATA%\Claude`, the Store build's `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude`, and the Store build's data folder `%LOCALAPPDATA%\Claude-Data\claude_*`); the installer writes the entry into every location that exists and names each file |
| Claude Code answers `API Error: 400 Claude Code x.y.z does not support this model` | the terminal CLI is older than the model pinned in your settings → `claude update`, or pick another model with `/model`; the server does not care which model answers |
| Claude Code shows no `roadsafety` in `/mcp` | open a NEW session / reload the VS Code window; `claude mcp get roadsafety` shows the entry. The installer registers through `claude` on PATH, else through the VS Code extension's own binary, else Claude Desktop's; all read the same user config. If it found none it printed the one-line command to run by hand |
| "xgboost did not install", studio actions ask for xgboost | Python < 3.12 in the app's environment, or no internet → re-run `install-plugin.bat` with internet; everything else works meanwhile |
| `site_ranking`, `what_if`, `severity_predict` refuse ("no deployed model") | run `seed-models.bat`, or train → validate → deploy in the סטודיו tab |
| your numbers differ from the docs | another xgboost version, another data vintage, or a model trained with other parameters; `studio_models` shows what is deployed — the pinned numbers assume the two reference models |
| two road-safety entries in the sidebar | an older generation of this plugin (`nl2sql-accidents`) — the installer offers to remove it; the course owner's own plugin of that name is never touched |
| Hebrew garbled in a terminal window | the console code page; the scripts print ASCII only, and the app and the chat render Hebrew correctly |

## Updates and provenance

This repository is a frozen export; the Python package is byte-for-byte the pathfinder's 0.14.3. When a new build is
published you will be told. Then: `git pull`, `install-plugin.bat` again, restart the app (`install-chat.bat` again
only if the app or the database moved). A pull alone changes nothing on your machine until you re-run the installer.
`CHANGELOG.md` is the phase history; `git log --oneline -1` tells you which build you have.
