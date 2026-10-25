# PITFALLS — recorded when they happen, not at phase end

Format: `## <YYYY-MM-DD> · <title> · [category]` · **What happened** · **Root cause** · **What the real
build & participants should do**. Categorized and ordered strictly reverse-chronologically at P7.

## Category index (P7)

| category | entries |
|---|---|
| **SQL** (14) | Feature engineering against coded columns: the "אחר" jump, t · `any_value` names, silent drops, and a national number next  · `road_km = 0` was a location on one side and "not coded" on  · Two `min()`s do not make a pair, and the sentinel list was o · The 2009 casualty-series `involved` rows are missing (15 row · Make/model DOES exist in the registry tables — only the key  · `לא ידוע` is the second-largest weather label (24,896 accide · Junction/damage-only control: 5.6 % urban, 23.3 % non-urban, · `nonurban_junction_code` exists only for `road_type_code = 3 · `traffic_adt_asof` is 2017–2024 only — `before_after` cannot · 489 pedestrians carry a vehicle-type code — bucket pedestria · "BETWEEN or no QUALIFY double-counts ~25 %" is true of the r · Segment-rate coverage is the units-CTE number: 71.5 % (55 →  · DuckDB 1.5.0 (the app's pin) mis-binds QUALIFY over an impli |
| **API** (9) | The in-process test client has no back-channel — server-ini · "Chat from the browser" is a different product from "chat fro · The SDK derives the bearer verifier from the authorization-ser · A `confirm=true` flag gates the TOOL, not the agent — a headl · A decorator wrapper's signature IS the tool schema — an int · Caveat numbers that were true for the whole range went stale · A constant imported by name defeats a monkeypatch — the cave · Layer-0 `help` text must be plain ASCII to render predictabl · After `pip install -e`, the running app shows the plugin as  |
| **state** (4) | The rehearsal app "started" on 8010 and answered with somebod · The running app is a side door into the shared data dir — sc · The connection pointed at the pristine folder · Port 8000 was held by a fourth app copy |
| **concurrency** (1) | "Atomic" os.replace is not atomic against Windows readers —  |
| **model** (4) | "latest" is the deployed site model only by accident — mixed U · A second model family found the registry family-blind — list · The severe share TRIPLES over the era — a calibration gate w · The gate rejecting the planned default was the finding, not  |
| **map** (4) | The empty map had three stacked causes — none visible to a D · The first non-echarts page: Leaflet + RTL + one outline file · Leaflet: add vector layers only AFTER the map has a view — o · Leaflet under Vite: `.geojson` is not a JSON module; the CSS |
| **page** (5) | The site panel was a trap: the ✕ hid under the RTL title an · A resolved fetch was thrown away by its own effect cleanup — · The PNG path's bidi machinery guards nothing on browser-rende · The Hebrew was "already using bidi" — and still wrong: forced · Page defects only a headless DOM count catches: grouped year |
| **packaging** (9) | Windows PowerShell 5.1 turned `claude mcp remove`'s one std · Claude Desktop keeps `roadsafety-mcp.exe` running — `pip insta · Claude Desktop from the Store is an MSIX app — it never rea · `mcp` 2.x renamed FastMCP — the documented import path ra · `pip install -e` over the wheel while the app runs left a th · The wheel shipped two generations of the page: setuptools' ` · `python -m build --no-isolation` fails in the app venv (no s · `packages = [...]` does not recurse — the actions subpackage · `nl2sql-shapes` is not on the public index |
| **demo** (7) | The demo agenda slide would have sent the model to the wrong · A Hebrew deck from pptxgenjs needs a bidi post-pass — Pow · Preflight's port probe FAILED whenever no app was running — · The spike's "~2 s" was the compute, not the answer — an acti · `--virtual-time-budget` dumps a lazy-chunk SPA before its fe · Headless Edge `--dump-dom` through PowerShell's `&` captured · Chat without an API key works through the `claude` CLI — and |
| **process** (4) | The rename had a SIXTH layer: the installer's verify blo · The version bump has a SIXTH touch point: the editable insta · A fixture table addition moved a pinned count two files away · The verification sweep ran out of credits twice — verificati |

(No `license` entries — the license rules never caused a stumble; they live in `CLAUDE.md`. No pure
`RTL` entry either — the RTL lessons live inside the `[page]`/`[map]` entries. `concurrency`/`state`/
`model`/`process`/`page` were added to the planned seven — the material demanded them.)

## 2026-10-25 · Windows PowerShell 5.1 turned `claude mcp remove`'s one stderr line into a terminating error — the registration never ran · [packaging]
**What happened:** the participants' kit gave `install-chat.bat` a Claude Code step: remove any stale `roadsafety`
entry, then `claude mcp add --scope user …`. On the first rehearsal it reported "did not succeed" and printed the
one-liner; `claude mcp get roadsafety` found nothing. The add had never executed.
**Root cause:** the installer runs under Windows PowerShell 5.1 (what the `.bat` launches) with
`$ErrorActionPreference = "Stop"`. There, the FIRST line a native command writes to stderr becomes a terminating error
the moment the error stream is redirected (`*> $null`, `2>&1`) — and `claude mcp remove` on a missing entry writes
exactly one ("No MCP server named …", exit 1). The `try` caught it, `$added` stayed false and the `add` line after it
was skipped. PowerShell 7 does not do this, so a quick check in the dev shell would never have shown it.
**What the real build & participants should do:** around native commands whose stderr is expected, relax the preference
(`$prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"; try { … } finally { restore }`), merge `2>&1`
into a variable and let `$LASTEXITCODE` decide — what the installer's pip helper already did by habit. Test one-click
scripts under `powershell.exe`, the host the `.bat` actually uses, never only under `pwsh`.

## 2026-10-25 · The rehearsal app "started" on 8010 and answered with somebody else's plugins · [state]
**What happened:** verifying the kit on a fresh clone of the app, uvicorn was started on port 8010 (8000 holds the
lab's stage app) and `/api/modules` answered at once — listing Ephraim's `accidents` module, the participants'
FinOps/Security plugins and no `roadsafety`. For a minute the kit looked broken.
**Root cause:** a third app copy (`Desktop\NL2SQL Closed Core Example`) had been serving 8010 since the day before
(the 2026-10-24 recap even said so). uvicorn logged "Application startup complete" and only THEN failed to bind
(WinError 10048) and shut down; every probe talked to the other process. On a machine with several app copies a
free-looking port is an assumption — and all the copies share one data dir.
**What the real build & participants should do:** before starting an app for a check, probe the port
(`Get-NetTCPConnection -LocalPort N -State Listen`) and read the owner's command line; after starting, assert that the
listener's command line IS yours before trusting an answer. The kit's README keeps the participants' simpler rule:
one app copy at a time, on 8000.

## 2026-10-24 · "latest" is the deployed site model only by accident — mixed UTC offsets sort as text · [model]
**What happened:** scripting the recording, `studio_validate model_id=latest` was expected to pick the newest site
model, which in the seeded stage is the rejected shuffled one. It returned the deployed 2023 model instead (verified on
a scratch copy of the registry: same card as the explicit id, Spearman 0.693, calibration 1.173).
**Root cause:** `registry.list_models` sorts on the `created_at` STRING. The deployed model's meta carries a local
`+03:00` stamp (`2026-09-01T16:03:42…+03:00`), the two rejected ones UTC (`2026-09-01T13:03:43…+00:00`), so the oldest
model sorts last. Every "latest" on the site family therefore lands on the deployed model today.
**What the real build & participants should do:** stamp every timestamp in UTC and sort parsed datetimes. But do not
"fix" the sort alone: with true order, "latest" would become the rejected shuffled model, and the read paths that
default to "latest" would quietly score or explain a rejected model. Decide the meaning first ("latest" for read paths =
the deployed model), then correct the order. Until then, demo prompts name the deployed model explicitly.


## 2026-10-24 · The demo agenda slide would have sent the model to the wrong segment and carded the wrong answer · [demo]
**What happened:** the deck's demo slide asked about "the change on segment 60/96" and placed "turn this into a
finding card" after the training step.
**Root cause:** to the tools, "60/96" is road 60, segment 96; the treated site is `road:60/96.0-98.8` (km range) or
segment `60/836`. And `finding_card entry=latest` cards whatever ran last, which there would have been the validate
run, not the before/after.
**What the real build & participants should do:** demo prompts use the tools' key formats or plain kilometre language
("כביש 60 בין ק״מ 96.0 ל-98.8"), and a card step comes directly after the run it cards. Slide 17 and
`docs/demo/MCP_DEMO.md` now follow both rules.


## 2026-10-20 · A Hebrew deck from pptxgenjs needs a bidi post-pass — PowerPoint takes punctuation direction from the RUN's language · [demo]
**What happened:** the MCP talk deck (`docs/demo/mcp_roadsafety_he.pptx`, 17 slides) rendered with doubled or
mirrored brackets around Latin words ("elicitation))", "NB))"), the colon on the wrong side of "13.9:",
"code = 1" reversed to "1 = code", "doc-11" shown as "11-doc", Hebrew titles in a serif face, and Latin words
inside Hebrew runs spelled backwards ("ledom").
**Root cause:** four separate things. pptxgenjs writes `rtl="1"` only for plain-string text (never for run
arrays) and leaves the theme's Hebrew heading font as Times New Roman; a whole run tagged `lang="he-IL"` makes
PowerPoint reverse the Latin letters inside it; and PowerPoint resolves the direction of neutral characters
(brackets, colon, spaces) at a run's edge from that run's `lang`, not from the Unicode bidi algorithm alone —
a ")" left in an en-US run after a Latin word renders LTR, and "= 1" left in the Hebrew run reorders around the
"=". Word joiners (U+2060) do not stop PowerPoint from breaking a line at an en dash.
**What the real build & participants should do:** generate, never hand-edit: `docs/demo/deck/build.js` then
`fix_rtl.py` (every Hebrew paragraph gets `rtl="1"`; runs are re-cut by script — Latin letters, with digits
glued to them through operators, → `en-US`; everything else incl. brackets and run-final punctuation → `he-IL`;
flow arrows inside Hebrew text → "←"; theme `Hebr` heading font → Arial). QA with a PowerPoint COM render
(`SaveAs(dir, 18)`), not LibreOffice, and zoom into every mixed-script line. Shorten a line rather than fight a
dash break.


## 2026-10-19 · The in-process test client has no back-channel — server-initiated requests (elicitation) need the stream mode · [API]
**What happened:** the first elicitation tests used `Client(server, elicitation_callback=cb)` exactly as the
earlier protocol tests did, and the server's `ctx.elicit(...)` raised `NoBackChannelError: this transport
context has no back-channel for server-initiated requests` — while the same server over stdio and streamable
HTTP asks fine.
**Root cause:** the SDK's in-process `Client` defaults to a direct dispatcher (no JSON-RPC streams, no initialize
handshake, request → handler → result) which is fast but one-directional; elicitation, sampling and roots are
SERVER → client requests and need the stream-backed `InMemoryTransport` (`mode="legacy"`). Real transports have
the back-channel; only the shortcut lacks it.
**What the real build & participants should do:** any test of a tool that calls `ctx.elicit`/`ctx.session.*`
back to the client must open `Client(..., mode="legacy")`; keep the fast default for everything else; and test
the three gate outcomes separately (accept → runs, decline → `# ⛔` and nothing on disk, no capability → the flag
card), because the capability check and the answer are two different branches.

## 2026-10-16 · Claude Desktop keeps `roadsafety-mcp.exe` running — `pip install -e` under it fails halfway and leaves a half-installed venv that only the suite's `pythonpath` hides · [packaging]
**What happened:** the 0.14.2 editable reinstall printed one quiet line, "Check the permissions.", and reported
0.14.2 installed. The full suite then failed ONE test: the page is "served by another installed package".
`pip list` showed NO plugin at all; site-packages held only `~l2sql_roadsafety_lab-0.14.1.dist-info` — pip's
tilde-renamed corpse of a failed uninstall — and no editable finder. Everything else had kept working because
pytest's `pythonpath = ["."]` imports the source tree and finds the repo-root `*.egg-info` metadata, so the
tests saw 0.14.2 while the venv had nothing. `importlib.metadata.entry_points()` still enumerates a `~`
dist-info, so the SAME page was advertised twice (egg-info 0.14.2 + corpse 0.14.1); a stale pre-rename
`nl2sql_accidents.egg-info` in the repo root added a third, "failed to load" entry.
**Root cause:** Claude Desktop spawns the server per chat (six `roadsafety-mcp.exe` / python processes were
alive) and Windows locks a running .exe — pip's rewrite of `Scripts\roadsafety-mcp.exe` is denied AFTER the old
install was already removed. The 2026-09-05 corpse lesson named the running APP; the running CHAT SERVER is the
same lock in a new costume, and a console script makes it an .exe lock, which is stricter than a .py.
**What the real build & participants should do:** before any reinstall, stop every process that runs the
console script (`Get-Process roadsafety-mcp`, plus the venv pythons whose command line names it) — Desktop
relaunches them on the next chat; read pip's FULL output (grep "ERROR|denied" — never trust the version line
alone); verify `pip list` shows the dist and site-packages holds exactly one dist-info + the editable pair;
delete repo-root `*.egg-info` of any former name (they are gitignored but they advertise entry points); and
let a test assert `entry_points(group="nl2sql.pages")` carries the page ONCE.

## 2026-10-16 · "Chat from the browser" is a different product from "chat from Desktop" — the Desktop bridge does not carry local servers into claude.ai · [API]
**What happened:** after the Desktop channel worked, the instructor asked to work from claude.ai in Chrome.
Desktop's main.log shows `[localMcpBridge] announcing roadsafety: 12 tool(s)` to `bridge.claudeusercontent.com`
at every start, which read like "the web sees it too". The browser's connector list never showed it, and no
audit line ever arrived from a browser session.
**Root cause:** the bridge serves Desktop's own cloud sessions (Cowork, remote devices), not the chat's
connector list. claude.ai reaches only REMOTE connectors: a public HTTPS address plus an OAuth login in the
browser — a server on a laptop is invisible to it by design. Two assumptions hid in one word, "chat".
**What the real build & participants should do:** decide the CLIENT before the transport: Desktop / Claude Code =
stdio on the laptop (the participants' path — they hold the database); a browser = `--transport http` behind
the server's own OAuth, reached through a tunnel (the instructor's demo) or a hosted machine (a CBS decision).
Write the bridge verdict down the day it is tested (`docs/mcp_acceptance.md` §0) so nobody re-tests it.

## 2026-10-16 · The SDK derives the bearer verifier from the authorization-server provider — passing both is refused, and the bearer check runs BEFORE the Host check · [API]
**What happened:** the first `build_web_server` passed `auth_server_provider=provider` AND
`token_verifier=ProviderTokenVerifier(provider)` (the obvious reading of the two parameters) → `ValueError:
Cannot specify both auth_server_provider and token_verifier`. Then the foreign-Host test expected the
DNS-rebinding middleware to refuse an unauthenticated stranger with 400/421 and got 401.
**Root cause:** `MCPServer` wraps the provider in `ProviderTokenVerifier` itself when `auth` is set; and the
auth middleware sits outside the transport, so a request without a bearer never reaches the Host check.
**What the real build & participants should do:** pass the provider only; test the Host allow-list WITH a valid
token (issued through the public host, replayed from a foreign one); and remember the SDK's
`StreamableHTTPSessionManager` runs once per app instance — build one Starlette app per test client, sharing the
provider, instead of reusing the app across `TestClient` contexts.

## 2026-09-23 · Claude Desktop from the Store is an MSIX app — it never reads `%APPDATA%\Claude\claude_desktop_config.json` · [packaging]
**What happened:** the first real Desktop registration on the instructor's machine: the config was written to
`%APPDATA%\Claude\claude_desktop_config.json` exactly as every tutorial says, Desktop was fully quit and
restarted (a first attempt had only closed the window — 21 processes kept running since 09-15), and still no
`roadsafety` connector, no `mcp-server-*.log`. The suspects (the G-Stat org account, a policy) were wrong:
main.log says `Organization allowlist enabled: false`.
**Root cause:** this Desktop is the Microsoft-Store (MSIX) build, `C:\Program Files\WindowsApps\Claude_2.7032…`.
MSIX runs with filesystem virtualization: the app's `%APPDATA%\Claude` is really
`%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude`, and main.log names it:
`Reading claude_desktop_config.json from …\Packages\…\LocalCache\Roaming\Claude\…` + `[MSIX] Filesystem
virtualization active`. The file we wrote sat in a folder the app cannot see; the file it reads held only its
own preferences.
**What the real build & participants should do:** never hard-code the Roaming path — detect
`%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude` first (`register.default_config_path()`, the
installer asks the module with `--print-path`), merge into THAT file preserving Desktop's `preferences`, and
when a connector does not appear, read `%LOCALAPPDATA%\Claude\logs\main.log` for the `Reading
claude_desktop_config.json from` line before blaming accounts or policies. Two other lessons from the same
hour: closing Desktop's window is not quitting it (check `Get-Process Claude` start times), and `$env:APPDATA`
is PowerShell — in cmd it is `%APPDATA%`.

## 2026-09-13 · A `confirm=true` flag gates the TOOL, not the agent — a headless model told "don't ask" set it itself · [API]
**What happened:** the live smoke asked Claude Code (`claude -p`, no human in the loop) to "train a severity
model with train_until=2021 and deploy it, don't ask questions". The audit shows the model never met the
`# ⏸ נדרש אישור` card at all: obeying the prompt, it set `confirm=true` on its FIRST `roadsafety_studio` call
(the tool description told it the flag exists), trained 12 s, validated, deployed — into the scratch data dir.
The server's instructions say "ask the person first"; a one-shot run has no person, so the instruction had no
one to defer to. (In the unit tests and in an ordinary chat the card does appear first — the flag works as a
PAUSE, not as a LOCK.)
**Root cause:** a boolean the caller sets is a contract with the agent, not a lock. Ephraim's design (and
ours) relies on the model honoring "ask first" — sound in Claude Desktop with a human reading the chat, void in
an automation channel or under an adversarial prompt.
**What the real build & participants should do:** keep the flag (it is what makes the model pause and explain
in a normal chat), but for a hard gate use MCP **elicitation** (the 2.x SDK's `ctx.elicit(...)`): the SERVER
asks the CLIENT to put a form in front of the human, and a headless run has no human to answer — the train
never happens. Scheduled automation then needs an explicit allow-list (e.g. validate only). Scheduled as an M2
item; until then the automation channel must run with a scratch `NL2SQL_CORE_DATA_DIR`.
**Resolved 2026-10-19 (M2):** `roadsafety_studio` asks through `ctx.elicit` whenever the client advertises
elicitation, and `--tools read-only` is the allow-list. The same prompt, headless through Claude Code, now ends in
"declined train" with nothing on disk.

## 2026-09-12 · The rename had a SIXTH layer: the installer's verify block and preflight's action pin · [process]
**What happened:** M1 read `install-plugin.ps1` and found its post-install check still looking for module id
and page id `"accidents"` — every fresh install since the rename would have died with "The plugin loaded but
its actions or page are missing." `tools/preflight.py` still pinned `N_ACTIONS = 26` against 30 live actions
(P13 added four), so its `--live` check would have failed too. Both had survived 417 green tests.
**Root cause:** the five-layer rename lesson (2026-09-08) was applied to what the SUITE exercises; the
installer's embedded Python and preflight's live pin run only from a fresh clone or with `--live`, and no test
touches either. Bare-string ids inside a PowerShell here-string are invisible to every import-based search.
**What the real build & participants should do:** the installer IS a test target — run it from a fresh clone
after any rename or action-count change (the P10 packaging session did; the rename session did not), and grep
the repo for the OLD id as a string (`"accidents"`), not only for the dotted package name.

## 2026-09-12 · A decorator wrapper's signature IS the tool schema — an internal `steps` parameter leaked into the model's form · [API]
**What happened:** the first tools.py passed a per-call `steps` list as the first parameter of every tool
function and wrapped them with `functools.wraps`; the MCP SDK builds each tool's JSON schema from
`inspect.signature(fn, eval_str=True)`, which follows `__wrapped__` — so `steps` would have appeared as a
REQUIRED input in Claude's form, and `from __future__ import annotations` would have handed the SDK strings
to evaluate against the wrong globals.
**Root cause:** in an MCP server the Python signature is a public contract, not an implementation detail;
anything a wrapper adds or hides changes what the model is asked to fill in.
**What the real build & participants should do:** keep tool functions' signatures exactly what the model
should see (real annotations, no future-import strings, every parameter defaulted except the true
required ones), carry per-call state in a `contextvars.ContextVar`, copy `__signature__`/`__annotations__`
explicitly instead of `functools.wraps`, and pin the schema in a protocol-level test (`"steps" not in
schema["properties"]`, the Hebrew enums present, `required == [...]`).

## 2026-09-12 · `mcp` 2.x renamed FastMCP — the documented import path raises on the current SDK · [packaging]
**What happened:** the step-0 spike's `from mcp.server.fastmcp import FastMCP` (every tutorial, Ephraim's
deck era) raised `ModuleNotFoundError` on the freshly installed `mcp` 2.2.0: the module exists only to point
at the migration guide.
**Root cause:** the SDK's 2.0 major (2026) renamed `FastMCP` → `mcp.server.mcpserver.MCPServer`, moved the
in-memory test client to `mcp.Client(server)`, and renamed image fields (`mime_type`). A version-free
`pip install mcp` lands on 2.x; a `mcp<2` pin keeps the 1.x API.
**What the real build & participants should do:** pin the MAJOR (`mcp>=2,<3`) and record the exact API used in
the phase design (`docs/m1_design.md` §SDK); spike the SDK in a scratch venv BEFORE writing server code, and
let the protocol tests (in-process + stdio subprocess) be the compatibility gate on every upgrade.

## 2026-09-12 · Preflight's port probe FAILED whenever no app was running — Windows PowerShell exits 1 on an empty pipeline · [demo]
**What happened:** with nothing listening on :8000, `tools/preflight.py` reported `[FAIL] port 8000 — port probe
failed:` with an empty message. The stage was fine; every earlier preflight had run with the app up, so the
zero-listener path had never been exercised.
**Root cause:** `powershell -Command "Get-NetTCPConnection … | Select-Object -ExpandProperty OwningProcess |
ConvertTo-Json"` exits with code 1 and EMPTY stdout/stderr when the pipeline yields nothing — Windows
PowerShell 5.1 sets the process exit code from the last pipeline's `$?`, and the probe treated any non-zero
exit as a broken probe (correctly refusing to guess "0 listeners" — the P6 rule — but for the wrong case).
**What the real build & participants should do:** make a probe's "nothing found" a POSITIVE output, never an
absence: collect into an array (`$p = @(...)`), emit it with `ConvertTo-Json -InputObject $p -Compress` so
zero results print `[]`, and `exit 0` explicitly; then "no output at all" is the only failure. Exercise both
branches of every pre-show check (0 listeners AND 1 listener — a throwaway socket suffices).

## 2026-09-08 · A plugin's name lives in FIVE layers, and a rename that misses one fails 276 tests · [process]
**What happened:** renaming the plugin (`nl2sql-accidents` → `nl2sql-roadsafety-lab`) looked like a
find-and-replace. The first full run after it: **276 failed, 128 passed**. The second: **33 failed**. Two
rounds of "surely that's all of it" before green.
**Root cause:** the name is not one string, it is five INDEPENDENT layers, and each fails differently:
(1) the **import package** (`nl2sql_accidents/` — a directory, moved with `git mv`, and every absolute
import in tests/tools/web); (2) the **distribution** (`pyproject name`, `importlib.metadata.version(...)`
lookups, the pip command shown to users); (3) the **module id** and (4) the **page entry-point id** — bare
strings `"accidents"` that are NOT part of any dotted path, so a `nl2sql_accidents`→`nl2sql_roadsafety`
replace cannot see them: `tests/helpers.py`'s `reg.run("accidents", ...)` alone broke every test in the
suite, and the same id is hard-coded in `tools/preflight.py` and in `App.jsx`'s "find my own module" lookup;
(5) the name as **content** — the ASCII provenance stamp burned into every PNG, the `-- nl2sql-accidents |`
header of ~38 generated SQL statements, the about card's title, and the test pins that assert those strings.
The last survivor was the subtlest: `importlib.resources.files("nl2sql_accidents")` in `sqlkit.outline()` —
a package name as a STRING ARGUMENT inside the package itself, which the first sweep skipped because it
only rewrote files OUTSIDE the package. It raised `ModuleNotFoundError` from `charts.scene_png`, i.e. the
traceback pointed at the map renderer, not at the resource lookup.
**What the real build & participants should do:** treat a rename as five checklists, not one replace, and
verify each independently: `git grep` the underscore form, the hyphen form, the bare module id (`== "<id>"`,
`.run("<id>"`, `ep.name == "<id>"`), the URL segment, and `files("...")`/`version("...")` string arguments.
Rewrite the package's OWN files too. Beware substrings: `nl2sql-accidents-plugin` (the repo folder) and
`nl2sql-accidents-page` (npm) must not become `nl2sql-roadsafety-lab-plugin`. Swap the editable install with
an explicit `pip uninstall <old-dist>` FIRST (two dists both providing the package is the P12 corpse). And
run the FULL suite — the failure count is the map: ~all-fail means a shared helper, a few dozen means one
subsystem, single digits means content pins.

## 2026-09-06 · plotly-basic has no ResizeObserver and rejects hidden divs — charts under a hidden tab never re-measure · [page]
**What happened:** during the rival-plugin comparison review, a verified defect surfaced in OUR page: every
Plotly chart rendered while its tab was hidden (tabs stay mounted under `[hidden]`) kept a stale size after
any window resize, and nothing re-measured on re-activation. `MapView` and `MapCanvas` both receive an
`active` prop and handle this; `PlotlyChart` was the one surface that was missed.
**Root cause:** `{responsive: true}` trusts plotly's own window-resize listener, but plotly.js 3.7.0 ships
ZERO `ResizeObserver` usages and its `Plots.resize` explicitly REJECTS hidden elements — so a resize that
happens while the tab is hidden is silently dropped, and unhiding fires no event at all.
**What the real build & participants should do:** attach your own `ResizeObserver` to the chart container
(it fires when the element's size goes 0 → N on unhide) and call `Plots.resize` when width > 0 — done for
`PlotlyChart` and TrendCompare's composed figure. Never assume a chart library re-measures on visibility.

## 2026-09-06 · The interactive palette mirrored the PNG twin — and silently pinned the light theme · [page]
**What happened:** in dark mode every Plotly chart drew near-black ink (#26323d) on the #161b22 card with
near-white gridlines; the Leaflet map, legend and popups were pinned-light too. Found only when the rival's
hand-written page (which reads CSS tokens live at render time) looked "better" on the same design tokens.
**Root cause:** PlotlyChart's constants were deliberately copied from charts.py "so both renditions of one
answer look related" — but the matplotlib twin is light BY DESIGN (Layer 0, the deck, print), while the
browser face must follow the viewer's theme. Mirroring the twin coupled the wrong two things. Compounding:
the dark token block redefined only the 8 app tokens, never `--red/--green/--amber/--grey/--bad`.
**What the real build & participants should do:** structural chart colors (ink, grid, paper) come from
`getComputedStyle` tokens with a `matchMedia` re-render (web/src/theme.js); meaning-bound hues stay fixed;
every semantic token gets a dark value; `img.png` keeps its white ground — the twin is light on purpose.

## 2026-09-06 · Sweep fixes landed in one twin and not the other: excess scale, y0e reset, exception hygiene · [map]
**What happened:** three defects fixed in `map_scene` during earlier sweeps were still live in `hotspot_map`
(and its Leaflet face): (1) the REJECTED `excess/max|excess|` colour rule — one outlier owns the scale and
hides the whole blue half — survived in `_excess_color` and `MapView.excessColor` after `map_scene`/`layers.js`
moved to z-in-NB-units, so the same five colours meant different things on two surfaces of one plugin;
(2) a model-path throw under `color_by=excess` fell back to observed but kept the clipped `y0e`, silently
narrowing a 2008 request to 2017+ with no caveat; (3) the raw exception text (which can carry `;`/newlines)
was spliced into a caveat, corrupting the one-line Layer-0 note whose separator IS `;` — and the degrade
path stacked a second caveat wrongly claiming "no deployed model" when the model had merely thrown.
**Root cause:** each fix landed where the symptom was found, not everywhere the shared pattern lived; no
parity test tied the two implementations of "the excess colour rule" together.
**What the real build & participants should do:** when a rule is REJECTED, grep for every implementation of
the old rule before closing the finding; pin twins together (test_excess_color_matches_map_scene_rule now
asserts `_excess_color == _excess_hex` across all five buckets and the sd floor); degrade paths get their
own tests (reset + cleaned text + ONE merged reason line, never a false "no deployment" claim).

## 2026-09-06 · Widening the shared fixture DDL broke the OTHER fixture's positional INSERT · [process]
**What happened:** appending the P13 columns (road_shape/speed_limit/…) to conftest's shared `accidents`
CREATE TABLE produced 36 errors + 1 failure across the studio suites — `studio_fixture.py` imports the same
DDL constant and does a positional 33-value INSERT, so every planted row landed shifted.
**Root cause:** two fixtures share one DDL constant, and one of them binds columns by POSITION. (Kin to the
P10 entry "a fixture table addition moved a pinned count two files away" — fixture coupling strikes again.)
**What the real build & participants should do:** keep the shared base DDL frozen; extend per-fixture via an
additive `ALTER TABLE` block (the `DDL_P13` pattern now in conftest), or give positional inserts an explicit
column list so a widened table cannot silently shift them.

## 2026-09-06 · A `\*` where `/*` belonged — malformed CSS comments fail silent and eat the NEXT rule · [process]
**What happened:** a fan-out agent wrote a CSS section header as `\* ── … ── */`. CSS error recovery treats
the malformed run as a bad selector and drops the ENTIRE following declaration block — the new `.stat-cards`
rule would have vanished with no error anywhere. Caught by eye in orchestrator review, minutes after landing.
**Root cause:** CSS has no syntax errors a build surfaces — invalid text is recovered over, silently.
**What the real build & participants should do:** after any generated/edited CSS, grep for `\*` at
line starts and unbalanced `/* … */` pairs; a stylesheet linter in the page build would make this a
hard failure instead of a disappearing rule.

## 2026-09-05 · `pip install -e` over the wheel while the app runs left a three-layer corpse · [packaging]
**What happened:** restoring the editable install after the P12 wheel-acceptance smoke — with the app still
running — failed silently mid-command (the error hidden by a `Select-Object -Last 1`). The next app start
reported `cannot import name 'about' from 'nl2sql_accidents.actions' (unknown location)`, 0/26 actions,
page MISSING — and survived clean-looking reinstalls: a CLI `import` worked while the app kept failing.
**Root cause:** pip's Windows uninstall-by-rename collided with the running process and aborted, leaving
THREE layers in site-packages: `~l2sql_accidents*` rename remnants (pip warns about these), the current
`-e` dist-info whose RECORD owns only the `.pth` + `__editable__` finder — and, invisibly, the dead wheel's
REAL package tree (72 files with a gutted `actions/`), which a regular path scan resolves BEFORE the
editable finder. A real-but-partial package dir shadows an editable install and no pip warning names it.
**What the real build & participants should do:** stop the app before switching install modes (wheel ↔ -e),
and never swallow pip's output in a pipeline. After ANY failed pip on Windows, audit site-packages for all
three layers: `~`-prefixed remnants, AND an orphaned real package dir — the current dist-info's RECORD is
the authority on what the live install actually owns; anything else with the package's name is a corpse to
delete. The tell: CLI import resolves the tree while the app resolves garbage.

## 2026-09-05 · The version bump has a SIXTH touch point: the editable install's own metadata · [process]
**What happened:** minutes after the P12 bump landed at all five documented touch points, a fan-out
implementation agent hit 16 failing contract tests — every `plugin_version` spec assertion plus
`test_installed_version_matches` — and burned a verification cycle proving its own edits innocent.
**Root cause:** `envelope.version()` and the install test read `importlib.metadata` — the editable install's
`dist-info` — which still said 0.11.0. An `-e` install pins the FILES to the tree but freezes the METADATA at
install time; the five touch points update the tree only.
**What the real build & participants should do:** treat `pip install -e` as the bump's sixth touch point —
bump and reinstall in the same breath (`--no-deps -q` makes it a two-second step). Agents/tests seeing a
version-shaped failure wave should check `importlib.metadata.version` against `__version__` FIRST.

## 2026-09-05 · The spike's "~2 s" was the compute, not the answer — an action's latency is its envelope · [demo]
**What happened:** the P12 spike timed `pred_contribs` on 20k rows at 1.95 s, and that number flowed verbatim
into the design, the input help and the demo beat. The live action answers in ~7 s (50k in ~11 s).
**Root cause:** the action around the compute fetches the 340k-row matrix, runs a second full predict pass for
the margins (the identity guard), builds the swarm + decode, and renders the PNG twin — the spike measured one
term of a five-term sum.
**What the real build & participants should do:** state user-facing latency from a probe of the FULL action on
live (the P12 probe script pattern), never from a kernel benchmark; keep the spike number only as the scaling
law (linear in rows). The demo script's fix is verbal: say what the model is reading while it draws.

## 2026-09-05 · A fixture table addition moved a pinned count two files away · [process]
**What happened:** adding `code_lookups` to the shared test DDL (the P12 decode dictionary) broke
`test_about_card` — the about card pins the fixture's schema-object count ("14 = 11 tables + 3 views").
**Root cause:** the conftest DDL is load-bearing for pins that never mention it; a schema-shaped pin two
files away is invisible at the point of edit.
**What the real build & participants should do:** when touching the fixture DDL, grep the tests for the
current table/view counts before running anything; expect every "N objects" pin to move and update it in the
same commit (the comment above the pin now names the P12 addition, continuing the P5 convention).

## 2026-09-04 · The site panel was a trap: the ✕ hid under the RTL title and there was no second exit · [page]
**What happened:** the instructor clicked a junction on the מפה חיה; the panel opened and could not be
closed. The ✕ was positioned `inset-inline-start` — in RTL that is the RIGHT edge, exactly where the title's
first characters paint — and it was a borderless grey glyph on white: overlapped AND invisible. Nothing else
closed the panel.
**Root cause:** logical properties flip with direction — a floating control placed "start" in LTR thinking
lands under RTL content; and a dismissible surface with exactly ONE exit is one bug away from being a trap.
**What the real build & participants should do:** place floating controls with inline-END (away from the RTL
text start) and style them as real buttons; give every dismissible surface THREE exits — the button, Escape,
and click-outside (deck.gl: the overlay's `onClick` with `!info.picked`). Verified end-to-end with a CDP
click-through (site click → panel present, empty click → panel gone), not a DOM count.

## 2026-09-04 · The empty map had three stacked causes — none visible to a DOM count · [map]
**What happened:** the instructor opened the finished מפה חיה tab and saw a solid dark rectangle — chrome,
legend and credit all present, `maplibregl-canvas` in the DOM, zero errors — exactly what the headless
DOM-count checks had blessed. A CDP screenshot reproduced it; the console + an in-page size probe found THREE
independent causes stacked: (1) MapLibre REJECTS a style whose `sprite` URL is relative ("must be absolute");
(2) the `[basemapMode]` effect called `setStyle` on mount with the style still loading — "Unable to perform
style diff … Rebuilding from scratch", killing the load; (3) MapLibre stamps `.maplibregl-map{position:relative}`
on the container div, and the lazy chunk's CSS loads AFTER the page CSS — equal specificity, later wins — so
`.map-gl{position:absolute;inset:0}` lost and the container collapsed to **height 0** (canvas fell back to
300 px, clipped away).
**Root cause:** three library contracts nobody states loudly: style URLs are absolute-only; setStyle is not
idempotent during load; the library CLAIMS your container's positioning via an injected class that ties on
specificity with any single-class rule.
**What the real build & participants should do:** build every style URL on `window.location.origin`; guard
mode-change effects with a ref so mount never re-applies the same style; size a GL container with a
TWO-class selector (`.map-shell .map-gl`) so the injected library class can never out-cascade it. And the
instrument lesson: a DOM count proves mounting, never pixels — the acceptance evidence for a canvas is a
CDP screenshot (diag2 pattern: console + failed-network + `Page.captureScreenshot`) plus an in-page probe of
`canvas.width/height` against the container.

## 2026-09-04 · A resolved fetch was thrown away by its own effect cleanup — the busy chip lived forever · [page]
**What happened:** the P10 map tab's `map_scene` fetch never "finished" in any headless dump — the busy chip
pinned, no error card — while the CDP network log showed the response ARRIVING complete (95,883 B, HTTP 200).
The server answered the same call in 0.31 s via curl.
**Root cause:** the fetch effect guarded on `busy`/`env` AND listed them in its dependency array, protecting
its state updates with a cleanup `alive = false`. `setBusy(true)` re-ran the effect; React runs the previous
instance's CLEANUP first; when the response resolved, `if (alive)` was false — `setEnv` and `setBusy(false)`
never ran. The fetch succeeded; the page discarded it.
**What the real build & participants should do:** on a stays-mounted component, dedupe fetches with a ref key
compared again at resolve time — never with cleanup flags; a cleanup-kill is right only where a dep change
STARTS A REPLACEMENT fetch (the site panel), not where a state flip re-runs the effect without refetching.
The CDP network log is the instrument that separates "still pending" from "resolved and discarded".

## 2026-09-04 · `--virtual-time-budget` dumps a lazy-chunk SPA before its fetch resolves — byte-identical dumps are the tell · [demo]
**What happened:** the P6 headless recipe (`--headless=new --virtual-time-budget --dump-dom`) returned the
SAME 35,937-byte DOM for the map tab at 45 s, 60 s and 120 s budgets — always mid-busy — even after the
warmed server call answered in 0.31 s. The hotspot page's fetch had always squeaked through, so the recipe
looked proven.
**Root cause:** virtual time does not wait for a `fetch()` issued after a lazy chunk loads; with an empty
timer queue the budget burns near-instantly, so the dump lands at a fixed early point (~1–2 s real) no matter
the budget. A second, smaller trap: `Start-Process msedge` fails silently-ish in PowerShell — msedge is not
on PATH; use the full `Program Files (x86)` path.
**What the real build & participants should do:** when the page's evidence arrives via fetch after load,
drive headless Edge over CDP with REAL wall-clock waits — `web/scripts/dom-dump.mjs` (Node ≥ 22: built-in
fetch + WebSocket) navigates, sleeps, evaluates `outerHTML`. Byte-identical dump lengths across different
budgets are the signature that virtual time, not the page, chose the moment.

## 2026-09-03 · The PNG path's bidi machinery guards nothing on browser-rendered cards — the en-dash flip returned on the P9 markdown faces · [page]
**What happened:** the P9 sweep found the new prediction card rendering its 90 % interval as "117–79" and its
era span as "2024–2017" in the browser (headless-Edge verified), and the severity training card's "(2010–2024)"
the same — the exact tight-range flip P8 fixed. The PNGs were clean.
**Root cause:** the P8 fix (LRM-pinned `_NUM_RANGE`) lives in `charts.heb()`, which only the PNG path
traverses; `markdown_answer` joins card lines verbatim, and the page's `md.jsx` isolates only Latin-LETTER-led
runs. A U+2013 en-dash between digits is bidi class ON and takes the RTL level (rule N1); ASCII hyphen-minus
survives (class ES, fused by W4).
**What the real build & participants should do:** every SURFACE needs the bidi rules, not every function —
a tight digit range on a browser-rendered RTL card must be LRM-pinned at the string-construction site (or use
ASCII '-'), and a new markdown face is a new surface to audit against the P8 checklist even when the PNG twin
is already clean.

## 2026-09-03 · A second model family found the registry family-blind — listing under one prefix, reading under another · [model]
**What happened:** planning P9's severity family, the exploration traced `registry.list_models(ctx, "severity")`
end to end and found it would enumerate the `severity/` directories but call `read_meta` — hard-coded to
`site/` — for each, returning every severity model as "unreadable". `save`, `update_meta`, `model_bytes` and
`new_model_id`'s `site-` prefix had the same blindness. The bug had zero symptoms with one family.
**Root cause:** the P4 registry took `family` only in the path helpers that P4 itself exercised (`root`,
`model_dir`, `list_models`, `deployed`, `deploy`, `resolve_id`); the read/write quartet baked the constant in,
and no test ever put two families side by side.
**What the real build & participants should do:** a parameter added "for later" is untested code — thread it
through EVERY function of the layer the day it is introduced, and pin it with a two-family regression test
(`test_registry_is_family_correct_with_two_families`) before the second family exists.

## 2026-09-03 · The severe share TRIPLES over the era — a calibration gate would reject every honest severity model · [model]
**What happened:** the P9 exploration found the severe-injury share of casualty person-rows tripling from
6.1 % (2010) to 19.4 % (2024) — the same shape on the accident grain, so it is real reporting/mix drift, not a
join artifact. Any temporal-holdout gate built on level agreement (calibration, like the site family's) would
read this as massive under-prediction and reject every honestly-trained model, exactly the way the site 2022
model was rejected by the 2023–24 decline.
**Root cause:** "labels are drift-free" (the dossier's coding-stability finding) does not imply "shares are
drift-free" — class PREVALENCE is a time series of its own.
**What the real build & participants should do:** match the gate to what survives the drift: discrimination
metrics (per-class recall, one-vs-rest AUC, a train-holdout AUC overfit bound) survive prevalence shifts;
calibration-style metrics do not. Freeze the 1/share class weights from the TRAIN window into the meta (the
window matters when shares drift), show only RELATIVE probabilities, and say the drift on every card.

## 2026-09-03 · The Hebrew was "already using bidi" — and still wrong: forced base_dir, flipping en-dash ranges, and the L4 trap · [page]
**What happened:** the instructor rejected the chart Hebrew (P8). The audit found `heb()` was ALREADY calling
python-bidi — the breakage was subtler: (1) `base_dir="R"` forced on Latin-dominant strings mangled paren pairing
(`ADT as-of (Σ ADT × אורך × 365)` rendered with two `(` and zero `)`); (2) tight number ranges FLIP under the UBA
(`2005–2024` → `2024–2005`, cc bands `1300–1001`) — UBA-correct, human-wrong; (3) no font was configured at all,
so every glyph was DejaVu's low-grade Hebrew. Plus RTL layout bugs bidi can't fix: LTR legend order, caveat
continuation indents landing left, annotations colliding with markers on dense charts.
**Root cause:** the Unicode bidi algorithm is not a rendering strategy by itself — base direction, number-range
pinning, and font/layout are separate decisions the code never made.
**What the real build & participants should do:** base direction is ALWAYS R for these strings (a first-strong
auto heuristic was tried and scrambled Hebrew caveats that OPEN with a Latin acronym — the bullet is neutral);
LRM-pin parenthesized groups whose content starts Latin/digit (raw UBA renders two '(' and zero ')' when the
open paren follows a Latin run) and keep paren CONTENT Hebrew-first when it mixes scripts; pin tight digit-dash-digit runs with
LRM wrapping (zero-width, keeps the en-dash; a SPACED em-dash is a separator, never a range); **keep the legacy
`bidi.algorithm` implementation — the newer Rust `bidi.get_display` drops rule-L4 paren mirroring** and regresses
parentheses; bundle a real Hebrew font (Assistant, SIL OFL) and set matplotlib's `font.family` to the LIST —
per-glyph fallback works ONLY there, `font.sans-serif` picks one font for the whole text (and
`fontTools.instantiateVariableFont` does NOT mutate in place by default — the saved "static" stays variable and
registers at its minimum weight); pin the whole behavior as a byte-exact display fixture (test_charts.py). Also:
the browser does all of this for free — the P8 page renders charts with plotly.js and no mirror code at all.
Bonus gotcha: a fresh `NL2SQL_CORE_DATA_DIR` has no `added_connections.json`, so page runs 404 with "no
connection named …" — copy the registry file into any scratch data dir an app will serve from.

## 2026-09-02 · "Atomic" os.replace is not atomic against Windows readers — the P4 sweep's high · [concurrency]
**What happened:** the registry's tmp + `os.replace` writers looked textbook, and every unit test passed — but the
sweep's stress harness drove the REAL 40-thread execution model and 98.9 % of `update_meta` calls crashed with
`PermissionError [WinError 5]` under four concurrent readers (reproduced twice, independently). Python opens files
without `FILE_SHARE_DELETE`, so replacing a file ANY thread momentarily holds open fails. Three more defects stacked
on the same primitives: `save()`'s collision check was check-then-act (0/60 concurrent collisions re-suffixed, 44/60
silently merged registrations), two concurrent deploys left TWO metas at status "deployed" (21/30 rounds), and
`studio_validate` discarded `update_meta`'s None — a gate verdict shown on the card could silently never reach the
registry. The ledger's final truncation fallback also never re-checked the 4 KB cap (a 9,919-byte line landed).
**Root cause:** POSIX rename intuition on Windows file-sharing semantics, plus multi-step invariants (collision
check, demote→pointer→status) with no serialization. Unit tests are sequential; the failure only exists under
threads.
**What the real build & participants should do:** ONE process serves all requests (modules cached in `sys.modules`),
so a single module-wide RLock around every registry read AND write removes the in-process race entirely; add a
bounded retry on `os.replace` for external openers (antivirus, an editor on meta.json); hold the lock across every
multi-step invariant; make callers of a returns-None writer check the None; re-check any size cap after the LAST
fallback; and stress-test file-based state with real threads — green sequential tests prove nothing about a
40-thread pool.


## 2026-09-02 · The running app is a side door into the shared data dir — scratch instructions don't cover port 8000 · [state]
**What happened:** the P4 sweep's agents were told to point every Context at a scratch dir — and did — but some
also exercised the RUNNING app on port 8000, whose own `ctx.data_dir()` is the real `%LOCALAPPDATA%\nl2sql-core`.
Result: three stray models (a validated doc-11/2023 duplicate + two shuffled/2023) joined the seeded registry and
the findings ledger grew 11 → 57 lines with probe noise (fifteen identical triage routes among them). The deployed
pointer survived untouched. Restored to the accepted stage state by hand (strays deleted, ledger trimmed to the
seeding + the legitimate P5 verification entries).
**Root cause:** the data-dir boundary was enforced at the Context level, not at the transport level — any HTTP
request to the live app writes as the app.
**What the real build & participants should do:** treat the running app as part of the shared state surface: agents
verifying a live system must either not touch its HTTP API or accept they are writing to its real data dir; the
demo pre-flight must RE-VERIFY the data dir contents (models list + ledger length), not assume the seeding
survived; and the ledger's append-only discipline applies to the app — the instructor owns the stage state.
**Third vector (P6 sweep, 2026-09-02 afternoon):** with port 8000 banned, agents STILL contaminated the stage —
they set `NL2SQL_CORE_DATA_DIR` *after* importing the engine, and the env var is read ONCE at first resolve, so
their "redirected" Contexts wrote to the real dir (3 stray models, ledger 15 → 45). The redirect must be in the
environment BEFORE any engine import (`tools/rehearse.py` and `make_plan_b.py` set it as their first act;
`make_plan_b` now also refuses a --data-dir that IS the real dir). `tools/preflight.py` caught the drift mid-sweep
— the re-verification rule keeps proving itself.


## 2026-09-01 · Feature engineering against coded columns: the "אחר" jump, the silent series gap, the missing key · [SQL]
**What happened (P4 panel):** `road_shape_code = 9` ("אחר") is 57 % of interurban rows and its share climbed from
~5 % (2005–2007) to 24 % by 2010, then jumped to 47 % in 2011 (the coding discontinuity; measured on casualty rows) —
"≠ straight" is meaningless as a curve feature; the damage-only series carries ~0 % of the speed/surface/carriageway
codings, so "static attributes from both series" are casualty-coded in practice; and two models registered in the
same second tied on `created_at`, making "latest" ambiguous (a validate ran on the wrong model in the smoke).
**Root cause:** coding practice changes over years and differs across series; second-resolution timestamps.
**What the real build & participants should do:** rate features only over rows with a SPECIFIC code
(`CASE WHEN code IN (real...) THEN ... END` inside `avg()` — NULL elsewhere); say on the card which series actually
feeds each attribute; timestamp registry entries with microseconds and re-suffix same-second id collisions.


## 2026-09-01 · The gate rejecting the planned default was the finding, not the bug · [model]
**What happened:** the planning docs fixed `train_until = 2022`; on the live copy that model is REJECTED — calibration
1.35 (it predicts 35 % more than 2023–24 observed, because the site-model panel's interurban casualty accidents fell 3,074 → 2,587 → 2,329 (2022→2024; national 2024: 8,315) and trees
cannot extrapolate a level shift; `lag1` lags it by a year). 2023 validates (Spearman 0.693, כיול 1.17, ratio 0.82).
**Root cause:** a default chosen before the gate existed; the data moved.
**What the real build & participants should do:** let the gate decide the default (2023), and KEEP the rejected 2022
artifact in the registry — a real model rejected for a real, explainable reason beats a straw man in the governance
beat (the shuffled preset stays as the second, deliberate rejection: Spearman 0.201).


## 2026-08-30 · The verification sweep ran out of credits twice — verification must not be the last step of a phase · [process]
**What happened:** the P2 ultracode sweep hit the session limit, then the monthly spend limit on the resume; two of
its four checker dimensions (arithmetic, edge cases) and four refuters never ran. The Byar / EB / Double-DiD
arithmetic was recomputed inline instead (all pinned numbers reproduce) and the unrefuted findings were verified by
hand against the code and the live copy.
**Root cause:** the sweep is the most expensive step and was scheduled last, when the budget was thinnest.
**What the real build & participants should do:** run the adversarial sweep as soon as the actions are green, not
after acceptance polish; keep the workflow resumable (`resumeFromRunId`); when a dimension cannot run, say so in the
recap and do the cheap part of it inline — never report a partial sweep as a full one.


## 2026-08-30 · `any_value` names, silent drops, and a national number next to a road — the sweep's determinism findings · [SQL]
**What happened:** 396 of 1,311 segment keys carry more than one `name_from`/`name_to` across `traffic_segments`
vintages (229 where the latest vintage differs from `min()`; re-pinned by the P3 sweep) and 61
non-urban junction codes have more than one name — `any_value` picked an arbitrary one (the demo segment 70/120 read
"צומת יסיף → צומת כברי" in one run and "→ כניסה לגדידה רח 115" in another); `bands=known_engine` dropped six band-0
cells (154,924 vehicles, 5.7 % of the fleet) without a word because the band-0 caveat only fired when band 0 was
*present*; `known_engine`'s live row count was 62, not the 61 the design pinned; a NULL `exposure_mkm` would have
fallen out of both the ranking and the "excluded" count.
**Root cause:** convenience aggregates and caveats keyed on what is shown instead of on what was removed.
**What the real build & participants should do:** deterministic name choice (`arg_max(name, src_year)` = the latest
vintage, `min()` for junction names) stated in the caveat; the "outside the ranking" statement counts every kind of
removal (`FILTER` columns) and the caveat names them; `coalesce(x, 0) > 0` for exposure filters; the design doc's live
expectations are re-run, never trusted from memory.


## 2026-08-30 · `road_km = 0` was a location on one side and "not coded" on the other · [SQL]
**What happened:** the damage-only coded share treats `road_km = 0` as not coded (`site_coding_exprs`), while the
assignment join and the road site keys admitted km 0 as a real location — 566 interurban casualty accidents 2017–2024
carry km 0 (all with a road number), 320 of them landed in segments that start at km 0.0. The expected density of
genuine km-0 accidents is ≈ 6× smaller, so the value is a sentinel.
**Root cause:** two rules for one column, written in two places at different times.
**What the real build & participants should do:** one rule, one constant, both sides: `road_km <> 0` in
`ASSIGN_JOIN` and in `site_predicate`, said in the unit caveat ("ק״מ 0 = לא קודד"). Live coverage moved from
71.5 % (20,185) to **70.4 % (19,865 of 28,213)**; every demo number that changed is re-pinned in `test_live.py`.


## 2026-08-30 · Caveat numbers that were true for the whole range went stale for every sub-range · [API]
**What happened:** the P2 verification sweep found five caveat figures typed in as constants: "בסף 0 'גשום'
עולה ל-67%" (true for 2005–2024 only — 65.8 % for 2010–2012, 68.7 % for 2015–2024, and printed even for
2005–2007 where the chart had no rows at all), "46 אלף רשומות" / "489 רשומות" in the severity profile, the ADT ≠
AADT APE figures (`traffic_fill_validation` holds them), and the coverage shape "לא מונוטוני" (asserted even for a
single year and for the strictly rising 2017–2021). A road-filtered `segment_rates` printed the NATIONAL coverage
next to "כביש 60".
**Root cause:** a caveat written at design time from a whole-range probe, copied into an action that takes a
year range / a road; the fixture test asserted the literal, so it could not fail.
**What the real build & participants should do:** every number in a caveat is computed inside the statement for
the selected scope (a `count(*) FILTER (...)` column, a `min()`/`max()` from the coverage rows, a table read with a
constant fallback) or is explicitly scoped ("בכלל הנתונים 2005–2024"); the test pins the FIXTURE's value, not the
live one. A legal range that returns no rows is a refusal card ("אין תאונות עם תא מזג אוויר בשנים 2005–2007"),
never a blank chart with a caveat about another range.


## 2026-08-30 · Headless Edge `--dump-dom` through PowerShell's `&` captured nothing — redirect stdout to a file · [demo]
**What happened:** `& msedge --headless=new --dump-dom <url>` gave 0 bytes in PowerShell 7 while `--screenshot`
worked; `Start-Process msedge … -RedirectStandardOutput dom.html -Wait` captured the 31 KB DOM.
**Root cause:** the DOM is written by a child process whose stdout the call operator does not capture.
**What the real build & participants should do:** `Start-Process … -RedirectStandardOutput`, a fresh
`--user-data-dir` per run, `--virtual-time-budget=20000` so the async fetches finish, then COUNT anatomy markers
(`leaflet-container`, `leaflet-interactive`, `badge-amber`, `class="ribbon"`, `class="error"`) — screenshots alone
cannot tell a rendered map from a blank one. The page's `?run=<action>` deep link exists for exactly this.


## 2026-08-30 · A constant imported by name defeats a monkeypatch — the caveat printed a cap the SQL no longer used · [API]
**What happened:** `hotspot_map` did `from ..sqlkit import POINTS_PER_UNIT`; the test patched
`sqlkit.POINTS_PER_UNIT = 2`; the statement (built inside sqlkit) honoured 2, the caveat (formatted in the action)
still printed 300.
**Root cause:** `from module import NAME` binds a copy at import time.
**What the real build & participants should do:** read tunables through the module at call time
(`sqlkit.POINTS_PER_UNIT`), and format every caveat number from the same source the statement used.


## 2026-08-30 · The first non-echarts page: Leaflet + RTL + one outline file shared with the Python package · [map]
**What happened:** P3 built the 🚦 page (React + Vite, Leaflet with no tile layer) in an RTL document. What bit:
(1) the Israel outline lives in the Python package (`nl2sql_accidents/data/israel.json`, Natural Earth 1:10m,
public domain) and is imported by the page from outside `web/` — the build is fine, the dev server needs
`server.fs.allow: [".."]`; (2) Leaflet popups are HTML strings, so the "לפני/אחרי" hand-off button inside a popup is
wired through `map.on("popupopen")` + `addEventListener` — React cannot render into it; (3) the map `div` must stay a
`dir="ltr"` island with `dir="rtl"` only inside the popup content, or Leaflet's positioning and the Hebrew fight;
(4) a single feature makes `fitBounds` zoom to street level — cap it (`maxZoom: 11`).
**Root cause:** Leaflet is DOM-string based and LTR by construction; the page is RTL and React-based; no precedent
plugin had either.
**What the real build & participants should do:** view before layers, the map as an LTR island, popup buttons via
`popupopen`, `try/catch` around the whole map setup with a visible error card AND the action's `png_base64` twin —
a map failure must never blank the page. Keep ONE outline file (package data) for both the page and matplotlib.


## 2026-08-30 · Page defects only a headless DOM count catches: grouped years, a healthy-looking broken header, a map that dies on a tab switch · [page]
**What happened (P3 sweep, page-contract checker):** `Intl.NumberFormat` grouped every numeric cell, so years
read "2,019" and junction codes "14,900,823"; a `?db=` naming a missing connection produced a normal-looking header
(the about probe's HTTP error was stored but never rendered as a chip); the legend said "1 … 347" while the ramp was
quintiles of the 30 shown units; only the active tab's panels were mounted, so switching tabs destroyed the Leaflet
map and the answers and re-fired the `?run=` deep link; Leaflet tooltips took raw strings while popups were escaped;
an unknown `?tab=` highlighted nothing; a Latin `detail` inside a Hebrew bullet had its closing parenthesis moved by
the bidi algorithm; the build's version came only from the `about` card, so a refusing connection showed none.
**Root cause:** every one of these is invisible in a screenshot of the happy path and in the Python suite.
**What the real build & participants should do:** format numbers per column (year/id columns ungrouped); render
the failure states (missing db, foreign db, unknown tab) as first-class chips; keep every tab mounted (`hidden`) and
`invalidateSize()` the map when it becomes visible; escape everything Leaflet injects; isolate Latin runs in RTL cards
(`<bdi>`); bake the version in at build time; and put the unhappy-path URLs into the headless check list.


## 2026-08-30 · The wheel shipped two generations of the page: setuptools' `build/lib` keeps stale hashed assets · [packaging]
**What happened:** after three `npm run build`s the wheel's namelist had four files under `webdist/assets/` — the
current pair plus an older pair Vite had already deleted from `webdist/` (`emptyOutDir`). `python -m build` copies
the package into `build/lib/` and never removes files that vanished from the source tree.
**Root cause:** setuptools' build directory is additive; hashed asset names make every rebuild a new file.
**What the real build & participants should do:** delete `build\` (and `dist\`) before the phase's wheel build, and
assert the namelist has exactly the files in `webdist/` — the README recipe now says so.


## 2026-08-30 · Two `min()`s do not make a pair, and the sentinel list was one code short — the P3 sweep's two highs · [SQL]
**What happened:** (1) urban junction labels used `min(street1_name), min(street2_name)` independently; the police
record a junction's two streets in either order (5,684 keys carry a swapped pair), so the alphabetically-first street
won BOTH columns and 28 of the top-30 urban hotspots read "חיל השריון / חיל השריון" — a pair no accident carries;
`before_after`'s label used three `any_value`s and never matched the map's. (2) `urban_junction_code = 99999999`
("unknown junction": 556 casualty accidents across 82 cities, no `dim_junction_urban` row) is not in the dossier's
0/99/9999 sentinel list, so it ranked 16th on the default urban map, placed at the city-wide accident mean, with a
`site_key` that `before_after` accepted as a site.
**Root cause:** aggregating columns of a pair separately; a sentinel enumerated from the code table instead of from
the data (`SELECT code, count(DISTINCT city_code) … ORDER BY 2 DESC` finds it in one line).
**What the real build & participants should do:** take a pair from ONE row (`arg_min(a, (a, b))`,
`arg_min(b, (a, b))` — deterministic and real) in ONE CTE shared by every action that prints the name; keep every
sentinel in ONE Python constant read by the ranking, the coverage denominator, the control and the key parser; before
trusting a code table, ask the data which codes span many cities / have no dimension row.


## 2026-08-29 · Layer-0 `help` text must be plain ASCII to render predictably · [API]
**What happened:** the contract test rejected the trend/trap `help` strings for an em dash and a Hebrew
literal. Not a crash — a discipline rule: `action.help` is visible LTR prose on the Modules page, where a
mixed Hebrew/Latin sentence can misorder.
**Root cause:** the generic page has no RTL handling (P0 finding); Hebrew belongs in labels, values and PNGs.
**What the real build & participants should do:** keep `help`/`description` ASCII, put Hebrew in labels and
in the answer itself; assert it in the contract test so it cannot drift.


## 2026-08-29 · `python -m build --no-isolation` fails in the app venv (no setuptools) · [packaging]
**What happened:** `Cannot import 'setuptools.build_meta'` — the app venv (Python 3.14) ships pip only.
**Root cause:** PEP 405 venvs no longer bundle setuptools; `--no-isolation` expects the backend in the venv.
**What the real build & participants should do:** build isolated (the default; needs network once) or
`pip install setuptools` into the venv first.


## 2026-08-29 · `packages = [...]` does not recurse — the actions subpackage would silently miss the wheel · [packaging]
**What happened (avoided, verified by the wheel listing):** the precedents list a single package; this plugin
has `nl2sql_accidents.actions`. An explicit `packages` list must name both, else `pip install <wheel>` gives a
module whose `__init__` fails to import (`No module named nl2sql_accidents.actions`) — the editable install
hides it.
**Root cause:** setuptools' explicit `packages` is literal; discovery is only automatic when the key is absent.
**What the real build & participants should do:** list every subpackage (or use `[tool.setuptools.packages.find]`),
and build + inspect the wheel once per phase (`python -m build --wheel`, then `zipfile.namelist()`).


## 2026-08-29 · The 2009 casualty-series `involved` rows are missing (15 rows vs 16,856 casualty accidents) · [SQL]
**What happened:** while designing `trend`, killed-by-year showed **0 for 2009** (next to 433 in 2008 and 375
in 2010). The 15 casualty-series person rows for 2009 are 3 uninjured, 1 severe, 11 slight; accidents 2009 is
complete (16,856 casualty / 308 fatal / 61,391 damage-only). A naive chart draws a plausible zero.
**Root cause:** the 2009 ת״ד 104 (casualty) persons file is effectively absent from the build. Everything else
for 2009 is complete — the damage-only persons file (139,368 rows), both vehicles files (31,199 / 106,651) and both
accident series — so `count(*) FROM involved WHERE year = 2009` (139,383) hides the gap; it shows only under
`case_type_code = 1`, and a single-key join would attach 11,848 damage-only person rows to 2009 casualty accidents
(ID reuse 2005–2009).
**What the real build & participants should do:** never a magic threshold — derive coverage from the accident
spine per period, with the series filter AND the composite key (`people >= casualty_accidents`) inside the
statement; NULL, not 0; a caveat with both counts; a gap band in the PNG. Participants should assert one early
year on live before trusting any person-level trend. Recorded in the dossier §5.4/§9.


## 2026-08-29 · Make/model DOES exist in the registry tables — only the key to the accident files is missing · [SQL]
**What happened:** the concept map said "no make/model exists in CBS data"; `fleet_by_model` and
`vehicle_mileage` carry make, model, manufacturer, plate.
**Root cause:** the accident files (`accidents`, `involved`, `vehicles`) carry no plate, VIN or model code — the
link is what is missing, not the data.
**What the real build & participants should do:** refuse with the true sentence ("the registry knows make/model,
the accident files carry no key — the finest linkable cell is manufacture_year × cc_band"); a participant who
greps the schema must not catch the plugin in a false statement. Also: `cc_band 0` (unknown engine — the EV
cohort, 550 → 67,893 vehicles) has the cube's wildest rates; label it honestly.


## 2026-08-29 · `לא ידוע` is the second-largest weather label (24,896 accidents, 7.8 % measured rain — twice `בהיר`) · [SQL]
**What happened:** the weather cross-check headline compares גשום vs בהיר; the third row a viewer sees is
`לא ידוע` at 11.4 % of the rows with a rate twice the clear-weather rate.
**Root cause:** unknown-weather reports skew rainy; the officer label is an observation, not a measurement.
**What the real build & participants should do:** show the row and put the finding in the note; never drop
`לא ידוע` from a weather profile.


## 2026-08-29 · Junction/damage-only control: 5.6 % urban, 23.3 % non-urban, and the coding is not stationary · [SQL]
**What happened:** damage-only junction coding collapsed 2010–2014 (997 rows/yr vs 4–5× before and after);
interurban damage-only km-coding swings 69.9 % (2011) → 97.7 % (2019) → 79.3 % (2024). The planning probe
quoted "22 % urban / 49 % non-urban" — a different definition (junction-years with a casualty accident that also
carry a damage-only row); with the plugin's own `site_coding_exprs` (junction code not in 0/99/9999 over road
types 1–2 / 3–4, damage-only 2005–2024) the coded shares are **5.6 % urban / 23.3 % non-urban** (corrected
2026-08-30 by the verification sweep — the original "~23 % at junctions" in the concept map was the closer number).
**Root cause:** police location coding practice changed over the years; the damage-only series is a
report-biased sample; a number quoted without its definition cannot be re-derived.
**What the real build & participants should do:** compute the coded share per window inside the statement and
flag the control when it moves > 25 % relative — a coding change must never read as a traffic change.


## 2026-08-29 · `nonurban_junction_code` exists only for `road_type_code = 3` (0 % on type 4) · [SQL]
**What happened:** 96.9 % of "non-urban at junction" accidents carry a code; none of the "non-urban not at
junction" rows do → 35 % of all non-urban casualty accidents, not ~97 %.
**Root cause:** the code is meaningful only at junctions; the dossier's coverage sentence was read too broadly.
**What the real build & participants should do:** junction sites are `road_type_code = 3` by construction; say
"junctions rank by counts only" and never derive a junction share from all non-urban accidents.


## 2026-08-29 · `traffic_adt_asof` is 2017–2024 only — `before_after` cannot reuse the units CTE · [SQL]
**What happened:** a segment site with a change year in 2008–2016 has no year-matched unit at all.
**Root cause:** the as-of layer starts with the first measured year on purpose (leakage guard).
**What the real build & participants should do:** locate sites by a literal km range (`road:<n>/<km_from>-<km_to>`),
the same predicate for both series; keep the units CTE for rates only (`EXPOSURE_YEARS`).


## 2026-08-29 · 489 pedestrians carry a vehicle-type code — bucket pedestrians on `casualty_type_code = 1`, never on NULL · [SQL]
**What happened:** NULL `involved_vehicle_type_code` ⊂ pedestrians, but 489 of 58,985 pedestrians (0.8 %) have a
vehicle code; a NULL-keyed "no vehicle" bucket disagrees with the pedestrian count by 489.
**Root cause:** the CBS file records the vehicle that hit the pedestrian on some rows.
**What the real build & participants should do:** `CASE WHEN casualty_type_code = 1 THEN 'pedestrian' ...` so both
dimensions agree at 58,985; say so in the caveat.


## 2026-08-29 · "BETWEEN or no QUALIFY double-counts ~25 %" is true of the raw table, not of the units CTE · [SQL]
**What happened:** measured: raw table half-open without QUALIFY +31 %, raw BETWEEN +51 %; after the units CTE,
dropping QUALIFY is +0.4 % and BETWEEN +18.5 %.
**Root cause:** the units CTE already collapses vintages; the QUALIFY then only settles segments whose km ranges
overlap within one vintage (~85 accidents).
**What the real build & participants should do:** keep both guards (half-open + QUALIFY) — they are cheap — but
attribute the effect correctly in caveats and teaching material.


## 2026-08-29 · Segment-rate coverage is the units-CTE number: 71.5 % (55 → 83 %, not monotonic), and raw rows overstate vehicle-km 0 % (2017) → 77 % (2024) · [SQL]
**What happened:** the concept map quoted "~75 %, 55 % → 89 %" for as-of coverage — those are the raw view's
numbers. The `units` CTE (one geometry vintage per segment-year) that `segment_rates` actually uses matches
20,185 of 28,213 interurban casualty accidents 2017–2024 (55.3 % → 82.8 %, dip 73.4 % in 2023) — **19,865 =
70.4 % (53.7 % → 81.2 %, dip 72.1 %) since the km-0 rule of 2026-08-30** (see that entry). Summing
vehicle-km over raw `traffic_adt_asof` rows overstates by 38.5 % overall — but 0 % in 2017 and **77 % in 2024**.
**Root cause:** 1,511 (road, seg, year) keys carry 2–5 overlapping-km vintages; the share grows every year.
**What the real build & participants should do:** numerator AND denominator share the same `units` CTE; print
the live coverage per year in the answer (never a fixed "~x %"); never sum raw rows.


## 2026-08-29 · DuckDB 1.5.0 (the app's pin) mis-binds QUALIFY over an implicit-cast join — silently wrong or an internal error · [SQL]
**What happened:** `tools/find_demo_site.py` returned **0 candidates** through the engine while the same SQL
returned 5,225 rows under the system DuckDB 1.5.2. Bisecting on the app venv's 1.5.0: a CTE with
`JOIN geom g ON a.road1_number = g.road` (INTEGER = DOUBLE) plus `QUALIFY row_number() OVER (...)` produced rows
whose `case_type_code` matched neither 1 nor 3 (counts silently 0); a variant died with
`INTERNAL Error: Failed to bind column reference "case_type_code": inequal types (SMALLINT != DOUBLE)`.
**Root cause:** a DuckDB 1.5.0 binder defect: a window function (`row_number() OVER (PARTITION BY a.accident_id,
a.case_type_code ORDER BY g.km_to - g.km_from)`) over a **range join without a year equality** — typed keys did not
help, and the subquery/alias forms failed the same way. The engine's own `v_accident_adt_asof` shape (join with
`AND a.year = u.year`, ORDER BY `gap_years, km_to - km_from`) binds fine, which is why `segment_rates` is unaffected
(its live numbers match the 1.5.2 probe). The app pins 1.5.0 for its own reason (sqlite scanner).
**What the real build & participants should do:** for one-row-per-accident assignment over a pure range join use
`arg_min(g.road, g.km_to - g.km_from)` with `GROUP BY accident_id, case_type_code` instead of a window function;
type the join keys anyway (`CAST(road AS INTEGER)`); assert one live number per recipe — the live tests are what
caught this.


## 2026-08-28 · Chat without an API key works through the `claude` CLI — and is not cheap · [demo]
**What happened:** with no `ANTHROPIC_API_KEY`, `/api/query` answered both verification questions
correctly (439 in 15.7 s; 5,458 in 13 s) by shelling out to the logged-in `claude` CLI (OAuth Max).
Each question sent 69 K–139 K input tokens (the full schema text + semantic layer ≈ 58 K chars);
CLI-reported equivalent cost ≈ $0.20–0.27 per question (Max-plan quota, not a bill).
**Root cause:** the engine's no-key path is `claude -p`; the prompt carries the whole 43-object schema.
**What the real build & participants should do:** chat beats at the seminar run from cassettes
(`NL2SQL_REPLAY=1`, recorded in P6 with no key in the environment); live chat is a fallback, not the
default; the cost line is a good seminar talking point for "why actions".

## 2026-08-28 · Leaflet: add vector layers only AFTER the map has a view — or React unmounts the whole page · [map]
**What happened:** the spike page came up blank in the browser and the sidebar tab looked "missing".
Headless Edge with `--enable-logging=stderr` showed `TypeError: Cannot read properties of undefined
(reading 'min')` thrown from `Polyline._clipPoints` during `map.fitBounds(...)`; React 18 treats an
uncaught error in an effect as fatal and unmounts the root → empty `<div id="root">`.
**Root cause:** Leaflet 1.9.4 defers `addLayer` until the map is "ready" (has a view). Doing
`L.geoJSON(...).addTo(map)` first and `fitBounds` second makes the deferred path add run before its
SVG renderer has computed `_bounds`. Order matters: `fitBounds`/`setView` → then `addTo`.
**What the real build & participants should do:** always give the map a view before adding vector
layers (`map.fitBounds(layer.getBounds()); layer.addTo(map)`), wrap map setup in try/catch with a
visible error card so a map failure never blanks the page, and debug blank pages with
`msedge --headless=new --enable-logging=stderr --dump-dom <url>` (a fresh `--user-data-dir` each time —
the profile caches the old `index.html`).


## 2026-08-28 · Leaflet under Vite: `.geojson` is not a JSON module; the CSS references images the build does not emit · [map]
**What happened (avoided by design, verified in the build):** Vite parses `*.json` imports as modules
but not `*.geojson`; and the built CSS still carries 5 `url(images/marker-icon…/layers.png)`
references that the bundle did not emit as files.
**Root cause:** Vite's JSON plugin keys on the `.json` extension; Leaflet's default icon and layers
control locate PNGs via CSS at runtime.
**What the real build & participants should do:** name the boundary file `israel.json`; draw points with
`L.circleMarker` only (no image assets); keep the map `div` a `dir="ltr"` island inside the RTL page.


## 2026-08-28 · `nl2sql-shapes` is not on the public index · [packaging]
**What happened:** `pip install nl2sql-shapes --extra-index-url https://amir-kh-z.github.io/...` would
404 — its publish commit in `C:\Users\A\dev\nl2sql-core` is unpushed (`main...origin/main [ahead 1]`).
**Root cause:** publishing to the PEP 503 index is a git push of the index repo; the local tree was
updated, the remote was not.
**What the real build & participants should do:** install from the local index
(`--extra-index-url file:///C:/Users/A/dev/nl2sql-core/docs/simple/`) until the index repo is pushed;
the demo machine must be checked for the tab, not assumed.


## 2026-08-28 · After `pip install -e`, the running app shows the plugin as a *Problem*, not as absent · [API]
**What happened:** right after installing `spike-mod` (module + page) into the running app,
`/api/modules` listed both as problems: `failed to import: ModuleNotFoundError: No module named
'spike_mod'` — which reads like a broken install.
**Root cause:** module discovery runs per request and sees the new entry points (dist-info), but the
already-running interpreter's import path does not include the new editable finder; pages are read
once at import. After a restart both resolve and the problems vanish.
**What the real build & participants should do:** "restart after install" applies to modules too, and
the symptom of forgetting is a *Problem card*, not a missing tab. Put that sentence in the README.


## 2026-08-28 · The connection pointed at the pristine folder · [state]
**What happened:** the shared registry entry `israel_accidents` pointed at the Hebrew Desktop folder
(stored `\u`-escaped), so the pristine copy was silently the live one (its sidecars were app state).
**Root cause:** the registry (`added_connections.json`) is re-read per request and never validated;
whoever added the connection first wins for every copy of the app.
**What the real build & participants should do:** connect by the ASCII working-copy path; sidecars are
discovered from the `.duckdb` path (same folder, same stem), not from the connection name, so the
registry path can be edited in place while the app is stopped. Never set read-only bits on the working
copy: the engine opens the `.duckdb` read-only, but writes `*.chat_history.json` /
`*.learned_examples.json` beside it.


## 2026-08-28 · Port 8000 was held by a fourth app copy · [state]
**What happened:** P0 could not start the lab clone: `Get-NetTCPConnection -LocalPort 8000` showed a
uvicorn from `Desktop\how to build a plugin\nl2sql-app-closed-core` (a copy nobody had on the list).
**Root cause:** every app copy on the machine binds the same hard-coded port and shares
`%LOCALAPPDATA%\nl2sql-core`; `run.ps1` has no port option.
**What the real build & participants should do:** pre-flight = "one app copy at a time"; check the
port before `run.ps1`; the demo script's first row is this check. Stopping a foreign copy is the
owner's call, never a script's.

