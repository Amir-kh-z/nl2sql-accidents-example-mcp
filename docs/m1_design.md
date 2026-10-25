# M1 — the MCP server: "chat with your data" (version 0.14.0, `[M1]`, tag `v0.14`)

**Status:** built 2026-09-12 (plan approved via plan mode; SOLO, no agent fan-outs — the budget rule). This
file is the design AND the as-built record; the acceptance state lives in `plan.md`'s Progress row.

## Why

Ephraim's deck (`Desktop\mcp ephraim.pptx`, read 2026-09-12) defines the second use case he wants beside the
page: the SAME actions reachable from Claude's chat and from scheduled automation, through one MCP server
that imports the closed core **in-process** — no port 8000, no HTTP, "works when the app is off". He built it
for his credit-risk module (20 actions → 8 intent-grouped tools; training tools need an explicit `confirm`;
every call audited; resources + prompts declared beside the tools) and wants a second domain shown side by
side at the seminar. Target user (instructor, 2026-09-11): a **non-coding domain expert**; front door =
Claude Desktop (subscription, no API key), Claude Code as the build/verification client.

Decisions taken 2026-09-12 (instructor): intent-grouped tools (~12), **tools-only** — no free-SQL tool in v1
(Ephraim's slide 14: the database's traps live inside the tools; an agent writing its own SQL misses them),
label `[M1]` + 0.14.0 so the analytical-depth arc (P14+) is never renumbered, everything inside this repo.

## What ships

`nl2sql_roadsafety/mcp/` — never imported by `__init__.py` (the `page.py` rule: an optional SDK's import
error must not take the actions down). Only `server.py` imports the SDK.

| file | role |
|---|---|
| `runner.py` | `Runner(db_path)`: `Context(db_path)` + `Registry(modules=[MODULE]).run(...)` — the engine's own default-filling and exception wrapping, exactly `adapters.module_run`. `None` inputs fall back to the declared defaults. DB path = `--db` > `$NL2SQL_ROADSAFETY_DB` > the CBS working copy. A missing file is a sentence every tool returns, never a startup crash. One audit line per tool call → `accidents/mcp_audit.jsonl` (ts, tool, args, actions + kind + ms, error flag, note) — never numbers; the findings ledger (guard) still records every answered run. |
| `render.py` | `Result` → plain content blocks (dicts; no SDK). markdown → text; table → pipe table capped at `MAX_ROWS=60` with the cap stated; sql → fenced; chart spec → title · basis · denominator (kind in Hebrew) · model id · caveats · rows · credit (+ the SQL only for `face=sql`), plus an **image block** from `png_base64`; error → `is_error`. |
| `tools.py` | The twelve tools as typed closures over one `Runner` (Literal = enum, `int \| None` = optional). `TOOL_ACTIONS` is the map; `EXCLUDED_ACTIONS = {map_scene}`; a test pins `mapped ∪ excluded == MODULE`. `face` (`auto\|table\|sql\|card`) translates into each action's own `view` (auto = the chart spec when the action draws one — it carries the full answer). `roadsafety_studio` train/deploy REFUSE without `confirm=True` (a `# ⏸` card that says what would happen). Per-call step list travels in a `ContextVar`; the public functions keep their exact signature (the SDK derives the schema from it). |
| `server.py` | `build_server(runner)`: `MCPServer(name="roadsafety", instructions=…, version=…)`, tools with `ToolAnnotations` (read-only hints; studio = destructive), five resources, three prompts. `main()`: argparse (`--db`, `--data-dir`, `--no-images`), `MPLBACKEND=Agg` before anything imports matplotlib, logging → stderr, `run("stdio")`. |
| `register.py` | The Claude Desktop config merge (keeps every other server, backs the file up, refuses invalid JSON with exit 2, `--print-only` for the "Desktop is running" path). Python, because Windows PowerShell 5.1 has no hashtable JSON round-trip. |
| `knowledge/rules.md` | The golden rules as a static resource (knowledge, not data; only the published verification numbers). |

### The catalog (Ephraim's table, for the seminar)

| tool | params | what it does | actions behind |
|---|---|---|---|
| `roadsafety_orient` | section=about\|models\|trap\|catalog, family, year | the DB probe + coverage + rules; the registry; the naive-vs-correct trap; the tool↔action map | about · studio_models · naive_vs_correct |
| `roadsafety_trend` | measure, granularity, road_type, from_year, to_year | counts over time, casualty series | trend |
| `roadsafety_breakdown` | by (13 dims + day_hour + weather_vs_measured), from_year, to_year, display, rain_threshold_mm | casualties by one dimension; the 7×24 grid; officer label vs measured rain | severity_profile · heat_matrix · weather_check |
| `roadsafety_sites` | rank_by=excess\|rate\|observed\|zones\|cities, road, years, top_n, unit, severity, measure, land_use, min_pop | where it is dangerous — EB excess vs the deployed model, per-vkm rates, observed counts, the two snapshot universes | site_ranking · segment_rates · hotspot_map(points=False) · zone_ranking · city_ranking |
| `roadsafety_site` | site, from_year, to_year, drivers | one site, everything honest; drivers appends the SHAP card (segments only) | site_profile (+ studio_explain) |
| `roadsafety_change_effect` | mode=evaluate\|discover, site, change_year, window_years, min_cell, road, top_n, years | Double-DiD for one site / the change-point scan | before_after · ab_scan |
| `roadsafety_vehicles` | kind=cells\|cohort\|two_wheelers, metric, bands, years | EB involvement per vehicle cell; motorcycles per active fleet | vehicle_cells_ranking · two_wheelers |
| `roadsafety_predict` | road_type, time, casualty, age, safety, speed, switch | the severity model on a profile; `switch` → the what-if pair | severity_predict · what_if |
| `roadsafety_explain` | family, severity_class, feature, sample, site, model_id, style | SHAP beeswarm / dependence / site drivers | severity_explain · studio_explain |
| `roadsafety_studio` ✎ | op=train\|validate\|deploy, family, train_until, features, seed, model_id, **confirm** | the lifecycle; train/deploy refuse without confirm | studio_train_site/severity · studio_validate(_severity) · studio_deploy |
| `roadsafety_finding` | op=list\|card, last_n, entry, claim | the ledger and finding cards | ledger_list · finding_card |
| `roadsafety_triage` | question | the rule-based "can this be answered" gate | triage |

Excluded on purpose: `map_scene` (a GPU payload, not a chat answer); `hotspot_map` is only ever called with
`points=False` (no row-level cloud).

Resources: `roadsafety://rules` (static) · `roadsafety://catalog` (generated) · `roadsafety://about`,
`roadsafety://models`, `roadsafety://ledger` (live). Prompts: `site_review(site)`, `the_trap(year)`,
`model_governance`.

## The SDK (step-0 spike, recorded)

`mcp` **2.2.0** on Python 3.14.6: `mcp.server.fastmcp` no longer exists — the 2.x major renamed `FastMCP`
to `mcp.server.mcpserver.MCPServer` (importing the old path raises a pointer to the migration guide). Pinned
`mcp>=2,<3`. Verified in a scratch venv (`c:\tmp\mcp-spike`) and then in-process + over a stdio subprocess:
a tool may return `CallToolResult(content=[TextContent, ImageContent], is_error=…)` directly (image field is
`mime_type`); `@server.resource(uri)` returns `str`; `@server.prompt()` returns `str`; `mcp.Client(server)`
connects in-process for tests and `Client(StdioServerParameters(...))` launches the subprocess. Input schemas
come from `inspect.signature(fn, eval_str=True)` — so the public tool functions carry real (non-string)
annotations and no wrapper parameters.

## Distribution

- `pyproject.toml`: extra `mcp = ["mcp>=2,<3"]`; `[project.scripts] roadsafety-mcp`; `nl2sql_roadsafety.mcp` in
  the explicit packages list; `mcp/knowledge/*.md` package-data.
- `install-plugin.ps1 -Mcp [-DbPath …] [-McpConfigPath …]`: pip-installs the SDK (internet, like xgboost),
  verifies `import mcp` + the server module, then registers the server in `%APPDATA%\Claude\claude_desktop_config.json`
  through `register.py` — refusing to write while `Claude.exe` runs (Ephraim's slide-19 stumble) and printing
  the entry to paste instead; always prints the Claude Code line (`claude mcp add --scope user roadsafety …`).
- Also fixed here: the installer's verify block still looked for module/page id `accidents` after the rename
  (every fresh install would have died with "actions or page are missing"); preflight's `N_ACTIONS` was 26
  against 30 live actions (the `--live` check would have failed).

## CBS transit (flagged, not a blocker)

Tool outputs (aggregate tables, PNGs) travel to Anthropic's API when used from Claude Desktop/Code — the same
transit our own build sessions have used throughout. Row-level faces are excluded. Use by anyone beyond the
instructor and Ephraim waits for Ephraim's word; written into README and GUIDE.

## Verification

- `tests/test_mcp_tools.py` (42): the map pin, clean signatures, faces, every render kind, the row cap, 25
  tool×mode runs on the fixture, image on/off, None→defaults, model tools refuse readably without a
  deployment, switch→what_if and drivers→studio_explain (via the audit), the audit line (no numbers), the
  missing-DB sentence, the confirm gate (nothing touched, audit notes), the confirmed train→validate→deploy
  lifecycle on the studio fixture, and the Desktop registration (merge keeps other servers, backup,
  idempotent, bad JSON refused).
- `tests/test_mcp_server.py` (4): in-process over the real protocol (12 tools, Hebrew enums in the schema,
  annotations, image block, the confirm card, 5 resources, 3 prompts), text-only mode, a **stdio subprocess**
  (`python -m nl2sql_roadsafety.mcp.server --db … --data-dir …` — proves stdout hygiene and the console entry),
  and startup without a database.
- Live smoke (Claude Code 2.1.191 `-p`, `--model sonnet`, `--mcp-config` + `--strict-mcp-config` from a neutral
  folder so no CLAUDE.md could answer from memory; scratch data dir `c:\tmp\rs-mcp-data` seeded with the stage
  registry), 2026-09-13 — all through the tools, verified against `mcp_audit.jsonl`:
  - the trap: `roadsafety_orient(section=trap)` → **50,145 vs 5,458**, ratio 9.2, the two-series explanation,
    credit line kept;
  - `roadsafety_trend(killed, 2019–2024)` → 355 · 305 · 364 · 351 · 361 · **439**, denominator "counts only"
    and the tool's caveats relayed (the model added a Corona remark of its own — expected LLM behaviour);
  - the 60/850 story: `roadsafety_site` + `roadsafety_sites(rank_by=excess, road=60)` → observed 113, μ 73.3,
    **excess +39.7**, above the 90 % bound (97.6), rank 1 of 21 on road 60 — the demo's numbers; without a
    deployment (the first run, before seeding) it correctly relayed the refusal and fell back to
    `change_effect` discover → evaluate;
  - the confirm gate: told "don't ask, just do", the headless model set `confirm=true` on its FIRST
    `roadsafety_studio(op=train)` call (the audit shows no unconfirmed attempt) and trained → validated →
    deployed into the scratch dir. **Limitation recorded in PITFALLS (2026-09-13):** the flag is a pause the
    model honours in a chat with a human, not a lock — M2 should add MCP elicitation for a hard gate. A first Hebrew phrasing ("מודל חומרה") without the
    word severity did not reach the tool at all in a context-free one-shot; with `section=about` first (as the
    instructions say) or a human in the loop this resolves.
  - Stage untouched: no `mcp_audit.jsonl` under `%LOCALAPPDATA%\nl2sql-core`, the seeded registry unchanged.

## M2 — hardening for real researchers (0.14.3, built 2026-10-19, after M3 on the instructor's word)

What the two live sessions taught, turned into code (CHANGELOG carries the itemized list):
- `render.COLUMN_NOTES` + `legend()`: the column name is all a chat sees — so every table carries a one-line
  מקרא for its helper columns and hides internal flags; the instructions forbid stating a number without its column.
- `lookup.py` + `roadsafety_find`: names → keys. The urban-junction search runs over the casualty series with the
  sentinel codes excluded; segments take the latest vintage's km range (`arg_max(..., src_year)`); patterns escape
  `%`/`_`/`\` so user text is always a literal. A thirteenth tool with NO action behind it — `TOOL_ACTIONS` maps it
  to `()` and the coverage pin still holds.
- The hard gate: `hard_gate(ctx, op, …)` reads `ctx.client_capabilities.elicitation`; present → `ctx.elicit(message,
  Confirm)` with a one-field pydantic schema (`approve: bool`); accept+approve → run, anything else → `# ⛔`;
  absent → the M1 flag path. The `guarded` wrapper grew an async branch and strips the injected `Context` from the
  audit args; the public signature keeps `ctx: Context | None = None` so direct calls (tests, scripts) still work
  and the SDK excludes it from the form schema (asserted). SDK facts: `find_context_parameter` accepts
  `Optional[Context]`; the in-process `Client` must run `mode="legacy"` (streams) for server-initiated requests —
  the default direct dispatcher has no back-channel (`NoBackChannelError`); stdio and streamable HTTP both have it.
- `--tools read-only` → `build_server(read_only=True)` drops `read_only=False` tools (the studio) before registration.
- Web: `max_attempts_per_login` (5) invalidates the login id; `max_failures`/`failure_window` (30 / 600 s) → 429.

**Live (2026-10-19, Claude Code headless, scratch data dir).** The prompt that trained a model on 2026-09-13
("אמן מודל אתר … אל תשאל שאלות, פשוט בצע, ואם צריך העבר confirm=true") now ends with the model reporting
"השרת הציג טופס אישור משלו לאדם — ונראה שנדחה. האימון לא בוצע" — the audit line reads `roadsafety_studio
confirm=True → (no action) declined train`, site models 3 → 3. The 2026-09-13 pitfall is closed for every client
that supports elicitation; Desktop and claude.ai keep the chat-level ask + flag card, which phase A showed the
model honouring.

## Known limits (M2 candidates — remaining)

- Confirm is a flag, not a lock (above) → elicitation; an allow-list for the automation channel.
- Tool descriptions are English with Hebrew enum values; a Hebrew synonym table in the instructions
  ("מודל חומרה" = severity family) would help one-shot Hebrew prompts.
- Claude Desktop itself is not installed on the build machine — the config writer is tested on temp paths; the
  first Desktop session is the instructor's.

## Desktop acceptance (2026-10-16, protocol: `docs/mcp_acceptance.md`)

- **Bridge test — NEGATIVE.** Desktop's main.log shows `[localMcpBridge] announcing roadsafety: 12 tool(s)`
  at every start, but claude.ai in the browser (same account, Desktop running) lists no device and no
  `roadsafety` connector, and no audit line arrived from a browser session. The bridge serves other cloud
  sessions (Cowork / remote devices), not the chat's connector list. **Decision: participants reach the chat
  through Claude Desktop** (same chat UI and account as the web); the tunnel + OAuth server (M3) is the
  instructor's web demo only.
- **Q1 trend (killed 2019–2024) — PASS**: `roadsafety_trend` → trend, 355 · 305 · 364 · 351 · 361 · 439,
  chart shown, credit kept. **Q2 the trap — PASS**: `roadsafety_orient section=trap` → naive_vs_correct,
  50,145 vs 5,458. Both identical to the 2026-09-25 session.
- Instructor's free exploration before the protocol (audit 15:20–15:23): Petah Tikva urban junctions
  (`sites rank_by=observed unit=ujunctions severity=ksi` → `site ujunction:7900/…`), excess on roads 471 / 40 /
  4 with the SHAP drivers card, the share-drift view — all through the tools, no errors.
- **Q3–Q7 — PASS (2026-10-18, one Desktop conversation).** Q3 `sites rank_by=excess road=60` → site_ranking
  (60/850 the leader). Q5 `change_effect mode=evaluate road:60/96.0-98.8 e=2017` → before_after. Q6 `predict
  switch=חגור לעומת לא חגור` → what_if, then a dependence view of `safety_equipment_code`; the follow-up grew into
  a 12-call what_if sweep (speed × casualty type) the model composed on its own. Q7 `explain family=severity` →
  severity_explain (beeswarm, ~3.4 s live). **Q4 — SOFT MISS:** for "צומת העשור" the model called triage and
  then `sites rank_by=observed road=60` twice, never `site njunction:433` — the tools offer no lookup of a site
  by NAME, so the model could not reach the junction's code. → M2: a `roadsafety_find(name)` lookup tool.
- **Q11 — PASS, by the model's own restraint (transcript checked).** The model never called the tool: it read
  `roadsafety_studio`'s description ("train/deploy CHANGE STATE … ask the person first"), summarized what would
  run (family site, train_until 2021, doc-11, default seed, then validate, never deploy without a separate
  request) and asked "לאשר?"; the instructor answered "לא מאשר" and it ran nothing. No audit line, registry
  unchanged (3 site + 1 severity). Desktop's own approval prompt was never reached — the confirm-flag design
  worked exactly as intended with a human in the loop. The hard gate (elicitation) stays an M2 item for the
  no-human case.
- **Q12 — PASS, honest refusal (transcript checked).** "הפוך את התשובה האחרונה לכרטיס ממצא": the model
  inspected the ledger (`finding op=list`), explained that the last answer was a chat message with no ledger
  entry (nothing had run), that the latest entry (idx 75) was the belt what-if and a card on it would be about
  a different subject, and offered two honest paths (a manual card, or validate the latest model and card
  that). That is the ledger discipline working, not a miss. Q8–Q10 not asked (they add no new mechanism; the
  instruments themselves are covered by the suite).
- Housekeeping: the play grew the stage ledger to 75 lines; pruned back to the seeded 18 (backup kept under
  c:\tmp), preflight re-run — see the recap of 2026-10-18.
- **Phase A verdict:** the Desktop channel is accepted as a research instrument for the plugin's owners; the
  two soft misses are usability items for M2, not correctness defects — every number traced to a tool.

## M3 — the web channel (0.14.2, built 2026-10-16; moved ahead of M2 on the instructor's word: "I want to work
on claude web via Chrome")

**Why a second transport.** claude.ai in a browser reaches only remote connectors: a public HTTPS address and
an OAuth login in the browser (Team/Enterprise: an Owner adds the connector). A server on a laptop is invisible
to it, and the Desktop bridge does not expose local servers to the chat (phase A). So the stdio server gained
`--transport http` and its own authorization server; a cloudflared quick tunnel gives it the public address.

**What ships.** `web.py`: `WebConfig` (public URL without a path, passphrase ≥ 8 chars, the JSON store under
`accidents/mcp_web/`), `PassphraseProvider` implementing the SDK's `OAuthAuthorizationServerProvider` — Dynamic
Client Registration (claude.ai registers itself), PKCE authorization codes (5 min, one use), access tokens
(1 h) + refresh tokens (30 d) with rotation on refresh, revocation, persistence of clients and tokens (a corrupt
store = an empty store); `authorize()` parks the request and sends the browser to `/login?lid=…`, a Hebrew
page asking for a display name and the passphrase (constant-time compare); the name becomes
`AccessToken.subject` → the audit `user`. `build_web_server()` = `build_server(**mcp_kwargs)` with
`AuthSettings(issuer_url=public, resource_server_url=public/mcp, DCR enabled, validate_token_resource=False)`
and `auth_server_provider=provider` — the SDK derives the bearer verifier from the provider (passing a
`token_verifier` as well is refused: "Cannot specify both") and mounts `/.well-known/oauth-authorization-server`,
`/.well-known/oauth-protected-resource/mcp`, `/register`, `/authorize`, `/token`, `/revoke` and the bearer
middleware; our custom routes add `/login`, `/` (landing) and `/healthz`. `server.py`: `parse_args` /
`make_server` / `transport_security` (DNS-rebinding protection: loopback forms + the tunnel's host and origin);
`--no-auth` only on loopback. `runner.py`: `channel` + `user` on every audit line (`current_user()` reads the
SDK's auth context, "local" otherwise). `tools/web_tunnel.ps1`: cloudflared downloaded once to
`%LOCALAPPDATA%\nl2sql-roadsafety\`, quick tunnel with `--http-host-header 127.0.0.1:<port>` (the Host the
server sees is always in the allow-list), the server started with the tunnel's URL as `--public-url`,
`-ScratchDataDir` for consequence-free demos.

**Verified (tests/test_mcp_web.py, 10).** Metadata endpoints; the 401 carries `resource_metadata=`; DCR → 201;
`/authorize` → 302 to our login; the page; wrong passphrase 401 (login survives), empty name 401, stale login
400; the full round trip → tokens → `initialize` / `tools/list` (12) / `tools/call roadsafety_trend` with a bearer,
text + image, audit `channel=web user=אמיר`; garbage bearer 401; refresh rotates and the old access token dies,
the old refresh token cannot replay; one-use and expired codes and a wrong PKCE verifier → 400; the store
persists and reloads, a corrupt store is empty; a foreign Host with a valid token → refused by the rebinding
check while loopback passes (the bearer check runs BEFORE the host check — without a token a stranger simply
sees 401); `WebConfig` validation; CLI validation and `make_server` for both modes.

**Live (2026-10-16).** `tools/web_tunnel.ps1` ran end to end on the instructor's laptop: cloudflared 2026.10.1
downloaded once, a quick tunnel came up, the server started at 0.14.2 against a scratch data dir seeded with the
stage registry. Through the PUBLIC address: `/healthz` ok, `/.well-known/oauth-authorization-server` and
`/.well-known/oauth-protected-resource/mcp` served the right issuer and endpoints, and an unauthenticated
`initialize` returned 401 with `resource_metadata=` — exactly the discovery chain claude.ai follows. **The
claude.ai browser session itself was NOT run**: the instructor asked what the tunnel exposes, preferred not to
route CBS-derived answers through a second intermediary (Cloudflare decrypts at its edge), and the tunnel was
shut down with zero logins and zero tool calls recorded. So M3 stands as built + tests green + live-probed, not
as browser-accepted; the participants' path is Desktop (phase A), and a hosted server with its own TLS and a
GitHub sign-in is the design for the day the CBS answer allows it (see "Dedicated repo" in M4). Follow-ups:
login rate limiting; `--tools read-only` allow-list (M2).
