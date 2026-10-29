# Build an MCP server for your own accidents plugin

**English** · [עברית](BUILD_YOUR_OWN_MCP.he.md)

> Your plugin was born from the starter kit (`nl2sql_accidents_starter`), so it shares this plugin's contract
> exactly: an `Action` with `run(ctx, ...)`, one `Result` per action, the envelope (denominator, caveats, credit) in
> `envelope.py`, the studio and the ledger. Everything built here under `nl2sql_roadsafety/mcp/` transfers to you one
> to one. This guide is the path: what to decide, what to copy, what to write, what to test — and the three Claude
> Code prompts that do it with you.

## 1. What you will build

One MCP server that exposes your plugin's actions to Claude Code and Claude Desktop as a small set of **tools by
intent**, with the database's rules as a **resource**, procedures as **prompts**, one **audit** line per call, and
an approval gate before any state change. Here: 30 actions → 13 tools. For you: the 19 starter actions plus what
you built → roughly 8 to 10 tools.

What you will **not** build: a free-SQL tool. The database's traps (two series, the composite key, counts versus
risk) live inside the actions; an agent writing its own SQL bypasses them. A design decision, not a technical limit.

## 2. The principle — seven rules

1. **The core in-process.** `Context(db_path)` + `Registry(modules=[MODULE]).run(...)`, exactly what the app does in
   `adapters.module_run`, without port 8000. "Works when the app is off."
2. **A tool is an intent, not an action.** `roadsafety_sites` wraps five ranking actions; `roadsafety_breakdown`
   three. The model's context holds 13 descriptions instead of 30, and it chooses better. The grouping is your decision.
3. **The envelope is rendered, not translated.** Title · basis · denominator · model id · caveats · rows (capped, and
   the cap stated) · credit · image. What the page draws, the chat gets as text and a PNG.
4. **State changes pass a gate.** Train and deploy: the server's own approval form (elicitation) when the client
   supports it; otherwise a `confirm` flag that refuses without it and says what would have happened.
5. **One audit line per call.** Which tool, which actions, how long, error, note — never the numbers (the ledger
   already holds them).
6. **Knowledge as a resource, procedure as a prompt.** The golden rules as static text; about/models/ledger as live
   resources; "site review", "the trap", "model governance" as prompts.
7. **Clean stdout.** Over stdio every byte on stdout is protocol. Logs go to stderr; `MPLBACKEND=Agg` before
   matplotlib loads; the SDK is imported only in `server.py`, never in the package's `__init__.py` (an optional
   extra's import error must not take the actions down).

## 3. Our server as the reference

| File (`nl2sql_roadsafety/mcp/`) | Role | For you |
|---|---|---|
| `runner.py` | `Runner(db_path)`: Context + Registry, the actions' own defaults, "no database" as a sentence not a crash, the audit line | **Copy as is.** Change: `from .. import MODULE` (works if your package has `MODULE`), `AUDIT_REL` (`accidents_starter/mcp_audit.jsonl`), `ENV_DB` / `DEFAULT_DB` |
| `render.py` | `Result` → blocks (text/image), a table capped at 60 with a legend for helper columns, the credit line | **Copy.** Update `COLUMN_NOTES` for your columns |
| `tools.py` | the `TOOL_ACTIONS` map, typed closures (Literal = enum, `int \| None` = optional), `face` → `view`, the studio with `confirm` + `hard_gate` | **Your design.** The structure stays, the content is yours |
| `server.py` | `MCPServer(name, instructions)`, tool registration with `ToolAnnotations`, resources, prompts, `main()` | **Rewrite briefly:** the name, the instructions, 2–3 live resources, 2–3 prompts |
| `register.py` | merging one entry into Desktop's config file, with a backup | **Copy.** Change `DEFAULT_NAME` |
| `lookup.py` | name → site key (`roadsafety_find`) | Optional. Useful if your users speak in names |
| `knowledge/rules.md` | the golden rules as text | **Write yours** (or start from a copy) |
| `tests/test_mcp_tools.py`, `tests/test_mcp_server.py` | 25 + 8 tests: map coverage, clean signatures, every render kind, runs on the fixture, audit without numbers, the gate, the lifecycle, Desktop registration, in-process client, stdio subprocess | **Copy the shape,** adapt to your tools |

## 4. Step by step

### 0. Prerequisites
- Your plugin installed in the app's environment (`..\app\.venv\Scripts\python -m pip install -e ".[dev,ml]"`) with
  its tests green.
- This kit cloned beside it (`..\nl2sql-accidents-example-mcp\`), the reference your agent will read.
- `mcp>=2,<3` in the environment (the kit's `install-chat.bat` already installed it; otherwise `pip install "mcp>=2,<3"`).

### 1. Decide the tool table (on paper, before code)
List every action of your module (`MODULE.actions`). Group by intent: orientation · trend · breakdown · sites ·
prediction · explanation · studio · finding · triage. Name each group `<plugin>_<intent>` (here `roadsafety_…`; for
you perhaps `starter_…` or the name you chose). Mark which **change state** (train, deploy). Decide which stay
**page-only** (here `map_scene`: a point cloud is not a chat answer). Write **one sentence of description** per tool;
that is what the model sees. The deliverable: a table like "the catalog" in `docs/m1_design.md`.

### 2. Copy the generic layer
```
nl2sql_accidents_starter\mcp\__init__.py      (empty, with a docstring)
nl2sql_accidents_starter\mcp\runner.py        <- from nl2sql_roadsafety\mcp\runner.py
nl2sql_accidents_starter\mcp\render.py        <- render.py
nl2sql_accidents_starter\mcp\register.py      <- register.py
nl2sql_accidents_starter\mcp\knowledge\rules.md
```
In the three files replace `roadsafety` / `accidents` with your name in the strings (`AUDIT_REL`, `ENV_DB`,
`DEFAULT_NAME`) and nothing else. They do not depend on the specific plugin.

### 3. Write `tools.py`
- `TOOL_ACTIONS: dict[str, tuple[str, ...]]`: the table from step 1. `EXCLUDED_ACTIONS` for what stays on the page.
  **Your first test:** `mapped ∪ excluded == {a.name for a in MODULE.actions}`; every action is either behind a tool
  or excluded on purpose. That test is what stops a tool from being forgotten when an action is added.
- Each tool is a typed closure over the `Runner`: Hebrew choice values as `Literal` (they are your actions' contract
  and pass through verbatim); `int | None` for optional (the action's own default); `face: Face = "auto"` →
  `view_for(action, face)`.
- **The signature is the schema.** The SDK derives the form from `inspect.signature`. No internal parameter enters
  the public signature (here the audit steps travel in a `ContextVar`). PITFALLS 2026-09-12.
- The studio: `STATE_CHANGING_OPS = ("train", "deploy")`, a `confirm: bool = False` parameter, and `ctx: Context |
  None = None` (the SDK injects it and leaves it out of the form). Copy `hard_gate` and `ConfirmSchema` as they are:
  elicitation available → a form; absent → the flag; not approved → `# ⛔` and nothing runs. Your `CONFIRM_TEXT` says
  what *would* have happened.
- `catalog_text()`: the map as text, for the `…://catalog` resource.

### 4. Write `server.py`
- `MCPServer(name="<name>", title=…, instructions=INSTRUCTIONS, version=…)`. **The most important paragraph in the
  whole project is `INSTRUCTIONS`:** answer in the person's language; never from memory when a tool can answer; a
  number only with its column; the denominator and caveats in every answer; state changes → ask, then
  `confirm=true`; never train → deploy without a validate; a Hebrew synonym table → tools. Copy ours and change the words.
- The registration loop: for each `ToolDef`, `server.tool(name, description, annotations=ToolAnnotations(
  read_only_hint=…, destructive_hint=…))(fn)`. `--tools read-only` leaves out what is not read-only.
- Resources: `@server.resource("<name>://rules")` static; `about` / `models` / `ledger` live through
  `runner.run(...)` rendered to text. Prompts: `@server.prompt(name=…)` returning a string with the order of steps.
- `main()`: argparse (`--db`, `--data-dir`, `--no-images`, `--tools`), `os.environ.setdefault("MPLBACKEND", "Agg")`,
  `logging.basicConfig(stream=sys.stderr)`, `server.run("stdio")`. You do not need the http channel (`web.py`).

### 5. Packaging
In `pyproject.toml`: `[project.optional-dependencies] mcp = ["mcp>=2,<3"]`; `[project.scripts] <name>-mcp =
"nl2sql_accidents_starter.mcp.server:main"`; add `nl2sql_accidents_starter.mcp` to `packages` (the list does not
recurse, PITFALLS 2026-08-29); `mcp/knowledge/*.md` to `package-data`. Reinstall (`pip install -e`) and check that
`..\app\.venv\Scripts\<name>-mcp.exe` exists.

### 6. Tests
Copy the shape of `tests/test_mcp_tools.py` and `tests/test_mcp_server.py` and adapt:
- the map covers everything; clean signatures (no internal parameter); `face` translates to each action's `view`.
- every `Result` kind renders (markdown/table/sql/chart/error); the cap at 60 is stated; the legend appears.
- N tool×mode runs on your synthetic fixture (the starter kit's own `conftest.py`) without error.
- one audit line per call, and never numbers inside it.
- the gate: train/deploy without approval touch nothing in the registry; the approved train → validate → deploy
  lifecycle works on the studio fixture. For the elicitation test the in-process client must use `mode="legacy"`
  (PITFALLS 2026-10-19).
- `Client(server)` in-process: N tools, Hebrew enums in the schema, resources, prompts; and a real stdio
  subprocess (`python -m …mcp.server --db … --data-dir …`), which proves stdout is clean.

### 7. Register and smoke
```powershell
claude mcp add --scope user <name> -e <ENV_DB>="C:\data\israel_accidents\israel_accidents.duckdb" -e PYTHONUTF8=1 -- "<app>\.venv\Scripts\<name>-mcp.exe"
```
For Desktop: `python -m nl2sql_accidents_starter.mcp.register --config <file> --exe … --db …` for every config
location Desktop uses (see the loop in the kit's `install-plugin.ps1`: classic, LocalCache, Claude-Data), or run your
register inside an installer of your own. Then a **new** session, `/mcp`, orientation → trend → your questions.
**Verify through the audit file, not through the prose.** Unattended: `claude -p "<question>" --mcp-config <json>
--strict-mcp-config` **from an empty folder** (otherwise the model reads the expected numbers from your README
instead of calling the tool).

### 8. An acceptance protocol
Write your own `docs/mcp_acceptance.md`: 8 to 13 Hebrew questions, each with the expected tool → action and the
expected numbers, one refusal, one training that must be declined. Run it after every change to the server, the SDK
version or the client. That is what turns "seems to work" into "verified".

## 5. The three Claude Code prompts

In your plugin folder, in a new session, one after the other. Each ends with a diff to approve before going on.

**Prompt 1, plan (no code):**
```
I want to build an MCP server for this plugin, following the example in ..\nl2sql-accidents-example-mcp. Read first:
docs/BUILD_YOUR_OWN_MCP.md and docs/m1_design.md there, and nl2sql_roadsafety/mcp/ (runner, render, tools, server).
Then read my plugin's MODULE and list every action. Propose: (1) a tool table by intent — name, one-sentence
description, the actions behind it, which change state, which stay page-only; (2) the server's INSTRUCTIONS text,
with a Hebrew synonym table; (3) 2–3 resources and 2–3 prompts; (4) the list of tests. Do not write code yet — show
me the plan and wait for approval.
```

**Prompt 2, build:**
```
Build according to the approved plan. Copy runner.py, render.py and register.py from the example and change only
names; write tools.py and server.py from the table; add the studio with confirm + hard_gate exactly as in the
example; package it (the mcp extra, the console script, packages, package-data); never import the SDK in
__init__.py; keep stdout clean. Write the tests after the example's tests/test_mcp_tools.py and test_mcp_server.py.
Finally: pip install -e, run the tests, and show me a diff.
```

**Prompt 3, test:**
```
Register the server in Claude Code (user scope) and in Desktop's config files (every location). Run an unattended
smoke with claude -p and --strict-mcp-config from an empty folder: orientation, trend, one question per tool, one
refusal, and a training "without asking" (it must be declined). Verify every answer through mcp_audit.jsonl, not
through the text. Write docs/mcp_acceptance.md with the questions and the measured numbers, and record every stumble
in my PITFALLS.md the same day.
```

## 6. Known traps (all recorded in the kit's `PITFALLS.md`)

- **`mcp` 2.x changed the import path:** `from mcp.server.mcpserver import MCPServer` (not `fastmcp`). Pin `mcp>=2,<3`.
- **The signature is the schema:** a helper parameter exposed in the signature becomes a field in the model's form.
- **`confirm` is a flag, not a lock:** a model with no human in front of it passes `confirm=true` itself. The real gate
  is elicitation; and in a client without a back-channel (an unattended run) the call fails before the audit, so no
  line is written.
- **The in-process client needs `mode="legacy"`** for server-initiated requests (the form) to work in tests.
- **Desktop keeps the server's exe alive:** `pip install -e` under it fails halfway and leaves a half-removed package.
  Stop the processes first (the kit's installer does).
- **`claude.exe` is both Claude Code and Desktop:** identify processes by path, not by name.
- **Desktop has had three config locations** across versions (`%APPDATA%\Claude`, `…\Packages\Claude_*\LocalCache\…`,
  `%LOCALAPPDATA%\Claude-Data\claude_*`). Write all of them, and verify by the process Desktop actually spawns.
- **PowerShell 5.1 under `$ErrorActionPreference = Stop`** turns a native command's stderr line into a terminating
  error: wrap calls to `claude mcp …` and pip and decide by the exit code.
- **Chat in a browser ≠ chat in Desktop:** the browser does not see local servers. And no server for this database is
  hosted (CBS).
- **Tool outputs travel to Anthropic's API:** before widening the audience, that is a question for whoever owns the licence.

## 7. Definition of done

- [ ] every action of the module is behind a tool or excluded on purpose, and a test pins it.
- [ ] public signatures are clean; Hebrew choice values pass through verbatim.
- [ ] train/deploy refuse without approval and touch nothing in the registry; with approval, the full lifecycle on the fixture.
- [ ] one audit line per call; no numbers in it.
- [ ] clean stdout (the stdio subprocess test green); the SDK is not imported in `__init__.py`.
- [ ] registered in Claude Code (user scope) and in every Desktop config location; `/mcp` shows the server.
- [ ] `docs/mcp_acceptance.md` with measured numbers; an unattended smoke from an empty folder, verified in the audit.
- [ ] every stumble in your `PITFALLS.md`, the same day.

## 8. What next

- **A generic adapter:** one package that wraps any NL2SQL module as an MCP server (the tool map as a config file,
  shared runner/render/register) would turn this guide into "install, point at the module, write the tool table". On
  the list; not needed to build today.
- **The automation channel:** `--tools read-only` plus a script on a clock that produces a report; the output comes
  from an action (HTML), not from the model.
- **The web channel** (`web.py`): exists, works, off — a CBS decision.
