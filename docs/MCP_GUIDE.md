# Chat with the lab — using the MCP channel, and why it exists

**English** · [עברית](MCP_GUIDE.he.md)

> For the researcher who already knows what to ask. The plugin gives you a page with tabs, forms and menus,
> which is great for discovering what exists. Once you know what you want, the form is in the way: you want to
> ask in your own words, chain one question on the previous one, train a model while talking, and end with a
> finding card. That is what the MCP channel does — the same instruments, in natural language, with no clicks.

## 1. Why

**The problem.** The plugin's page (🚦 מעבדת הבטיחות בדרכים) is a "set and run" interface: pick a measure, the
years, a road type, press run. Excellent for a first exploration and for showing. A researcher who already knows
what to test works differently: ask, read, ask the next question *based on* the answer, compare, go back, "show me
that as a table", "and what if it were at night?", "train a model through 2021 and tell me whether it passes the
gate". A conversation, not a form.

**The answer.** The plugin ships an MCP server (`roadsafety-mcp`). It exposes the **same 30 actions** to Claude as
**13 tools**, and Claude becomes a research colleague who speaks Hebrew: you ask, the model picks the tool, the
tool computes, the model narrates. Three principles keep it honest:

1. **The model narrates, the tool computes.** Every number in an answer comes from a tool, with its denominator,
   its caveats and the CBS credit line. The model is instructed never to answer from memory when a tool can, and
   never to derive numbers from a capped table.
2. **The traps live inside the tools.** The two series in one table (`case_type_code`), the composite key, "counts
   are not risk", the two universes (yearly series versus cumulative snapshot) are coded into the actions. An agent
   writing its own SQL would fall into them, so **there is no free-SQL tool**, on purpose.
3. **State changes ask first.** Training or deploying a model changes the shared registry. The server stops and asks
   you: in Claude Code through a form the model cannot answer itself; in Claude Desktop through a ⏸ card and a
   request for approval in the chat.

**Three channels, one server.** The same server serves the page (through the app), the chat (Claude Code or
Claude Desktop) and automation (a script on a clock with `--tools read-only`). The core runs **in-process**: the app
need not be running, and the database never leaves the machine.

## 2. What you need

- The kit installed: `install-plugin.bat`, `install-chat.bat`, `seed-models.bat` (see the README). Without deployed
  models, the model-backed tools (`sites rank_by=excess`, `predict`, `explain`) answer with a readable refusal.
- **Claude Code** (the VS Code extension or the CLI): after `install-chat.bat`, open a **new** session; `/mcp` lists
  `roadsafety` connected with 13 tools. **Or Claude Desktop**: restart it; `roadsafety` is in the tools menu of a
  new chat.
- A first check: `כמה הרוגים היו בתאונות דרכים ב-2024, ומה המגמה מ-2019?` → 355 · 305 · 364 · 351 · 361 · **439**,
  the "ספירות בלבד" badge, the credit line.

## 3. The tools, in plain words

| Tool | What you ask | What it does | Actions behind it |
|---|---|---|---|
| `roadsafety_orient` | "What is this database?", "What is the trap?", "Which models are deployed?" | the about card (coverage, rows, rules), the model registry, the two-series trap, the tool catalog | about · studio_models · naive_vs_correct |
| `roadsafety_trend` | "How many killed / injured / accidents over the years?" | counts over time from the casualty series, by year or month, all roads or urban / non-urban | trend |
| `roadsafety_breakdown` | "By age / casualty type / hour / weather / year" | casualties by one dimension (13 of them), the day×hour grid, officer's weather label versus measured rain | severity_profile · heat_matrix · weather_check |
| `roadsafety_sites` | "Where is road 60 dangerous?", "Which towns?", "Traffic zones?" | site rankings: excess over the model's expectation, per-vehicle-km rates, observed counts, the two cumulative universes | site_ranking · segment_rates · hotspot_map · zone_ranking · city_ranking |
| `roadsafety_site` | "What happens at segment 60/836?", "And at junction HaAsor?" | one site, everything honest: the yearly strip, severity, model measures (segments only), and with `drivers` a SHAP card | site_profile · studio_explain |
| `roadsafety_find` | "junction HaAsor", "street X in town Y", "the segment called…" | a name → a site key (`njunction:433`, `ujunction:…`, `road:…`) to hand to the other tools | — (a lookup, no action) |
| `roadsafety_change_effect` | "Did the 2017 change work?", "Where were there changes?" | before/after as a double difference-in-differences against the national network; or a change-point scan (a rank score, not a test) | before_after · ab_scan |
| `roadsafety_vehicles` | "Which vehicle cells are involved more?", "Motorcycles?" | empirical-Bayes involvement per vehicle cell (manufacture year × engine band); motorcycles per 1,000 active vehicles | vehicle_cells_ranking · two_wheelers |
| `roadsafety_predict` | "What is the severity risk for this profile?", "Belted versus unbelted?" | the severity model on a profile, relative to the baseline; with `switch`, a what-if pair | severity_predict · what_if |
| `roadsafety_explain` | "What did the model learn?", "What drives death?" | SHAP: beeswarm, dependence on one feature, a site's drivers | severity_explain · studio_explain |
| `roadsafety_studio` ✎ | "Train a site model through 2021", "validate the model", "deploy" | the lifecycle: train → validate (the gate) → deploy; train and deploy require approval | studio_train_* · studio_validate* · studio_deploy |
| `roadsafety_finding` | "What is in the ledger?", "Turn that into a finding card" | the findings ledger; a card = claim + evidence + caveats + rerun recipe | ledger_list · finding_card |
| `roadsafety_triage` | "Which car model is safest?" (and other boundary questions) | the "can this be answered" gate: refuses with a reason and points to the alternative | triage |

**Resources** (the model can read them): `roadsafety://rules` (the golden rules), `roadsafety://catalog`,
`roadsafety://about`, `roadsafety://models`, `roadsafety://ledger` (live).
**Procedure prompts** (in Claude Code they appear as commands): `/roadsafety:the_trap 2024`,
`/roadsafety:site_review 60/836`, `/roadsafety:model_governance`. In Desktop they are reachable from the chat's
+ menu.

## 4. How to ask

- **Start with orientation.** "What is this database and what can I ask?" The model reads the about card and the
  rules before answering anything; the server's instructions tell it to do that once per conversation.
- **Words the server understands** (from the synonym table in its instructions): "מודל חומרה" = the severity
  family; "מודל אתר / מקטע" = the site family; "מסוכן" / "סיכון" = excess over expectation (`rank_by=excess`),
  never raw counts; "צומת" is a junction (no exposure denominator, no model measures) while "מקטע" is a segment
  (rates and model measures exist); "לפני/אחרי", "האם השינוי עבד" = change_effect; "מה אם", "חגור לעומת לא
  חגור" = predict with switch; "למה", "מה מניע" = explain; "פנקס", "ממצא", "כרטיס" = finding.
- **A place name → `find` first.** "צומת העשור" becomes `njunction:433`; a street in a town becomes an urban
  junction; a segment name becomes a km range. The model is instructed to do this by itself; if it does not, ask:
  "use roadsafety_find".
- **Faces of an answer.** Every tool can return `face=table`, `face=sql` (the exact statement), `face=card`
  (a markdown card) or `auto` (the chart, which carries the full answer plus an image). "Show me the SQL" works.
- **When the model answers from the web instead of the tool** (in Desktop, with web search on): switch web search
  off for that chat, or add "use the roadsafety tool". The audit file (§7) tells you what really happened.

## 5. How to read an answer

A tool answer is the plugin's **envelope**, as text: title · basis · **denominator** (`ספירות בלבד` counts only /
`חשיפה` exposure / none / not applicable) · the model id when one is involved · **caveats** · the rows (up to 60,
the cap stated) · the **credit line** · and an image (the PNG twin). Three habits:

1. **A number only with its column.** The legend (מקרא: …) under every table explains the helper columns:
   `people` = everyone involved including the uninjured (a coverage check, not casualties); `killed` = people
   versus `fatal_accidents` = events; `mu` = the model's expectation; `excess` = observed − expected; `lo90/hi90` =
   the 90 % interval; `rate` = per 100 million vehicle-km; `ratio` = the DiD ratio (association, not causation);
   `p_baseline/p_scenario` = relative probabilities; `z` = a rank score, not significance; `site_key` = the key to
   pass to the site tools; `idx` = the ledger entry id.
2. **Counts are not risk.** The "ספירות בלבד" badge means no exposure denominator. A busy road is also just busy.
   Per-vehicle-km rates exist for interurban segments only; never for junctions or streets.
3. **The prose varies, the numbers do not.** Check numbers against the tool (or against the question set in the
   README); the wording changes from run to run, and that is fine.

## 6. Use cases — what to type, what to expect, what to notice

The numbers are pinned against the two reference models `seed-models.bat` creates (site: through 2023, doc-11,
seed 42; severity: through 2022, person-12, seed 42) and the 2024 data. They come from `docs/mcp_acceptance.md`.

### a. The trap — why a naive count is wrong by nine

```
למה ספירה נאיבית של תאונות קלות ב-2024 נותנת מספר גדול פי תשע?
```
Expect `roadsafety_orient section=trap` → **50,145** versus **5,458**, ratio ≈ 9.2, and the two series explained
(`case_type_code = 1` casualties, `3` damage-only). **Notice:** the rule lives in the tool; the model did not have
to remember it. Also: `/roadsafety:the_trap 2024`.

### b. A site review — from a road to a junction to a change

```
איפה הכי מסוכן בכביש 60 — ביחס למה שהמודל מצפה?
```
Expect `roadsafety_sites rank_by=excess road=60` → 60/850 כניסה לעפרה–צומת תפוח: observed **113**, expected
**73.3**, excess **+39.7**, significant, **rank 1 of 21**; second 60/823 +13.6 (not significant). **Notice:**
"dangerous" means above what the model expects for its traffic, not the biggest count.

```
מה קורה בצומת העשור? יש לו מודל?
```
Expect `roadsafety_find name=העשור` → `njunction:433`, then `roadsafety_site` → the yearly strip, and **no model
measures**: junctions carry no exposure denominator, and the caveat says so. **Notice:** an honest answer, not a hole.

```
האם השינוי ב-2017 במקטע road:60/96.0-98.8 עבד?
```
Expect `roadsafety_change_effect mode=evaluate` → casualty ratio **0.13** (0.06–0.30); damage-only 1.25; **double
ratio 0.11** (0.04–0.29). **Notice:** association, not proof, and the caveat says so every time.

### c. Severity — drift, what-if, and what the model learned

```
איך השתנה הרכב החומרה לאורך השנים?
```
Expect `roadsafety_breakdown by=year` → the severe share **6.1 % (2010) → 19.4 % (2024)**, slight 92.6 % → 77.5 %,
and the reporting-drift caveat (reporting of slight injuries fell). **Notice:** because of that drift the severity
gate measures discrimination, not calibration.

```
מה ההבדל בסיכון לחומרה בין חגור ללא חגור?
```
Expect `roadsafety_predict switch=חגור לעומת לא חגור` → killed **×1.38**, severe **×1.28**, slight **×0.21**;
"relative only". **Notice:** the model ranks profiles, it never predicts a person's fate; and "association, not
intervention".

```
מה המודל של החומרה למד? מה מניע מוות?
```
Expect `roadsafety_explain family=severity` → a beeswarm image; speed limit, road type and vehicle type lead;
margin-scale wording. **Notice:** grey rows are nominal codes with no order (uncoloured on purpose); hollow dots
are "unknown".

### d. What the data cannot say

```
איזה דגם רכב הכי בטוח?
```
Expect a **refusal** (through `roadsafety_triage` or from whichever tool was called): no plate, VIN or model code
in the files; the honest alternative is vehicle cells (manufacture year × engine band) in `roadsafety_vehicles`.
**Notice:** a readable refusal with a reason and an alternative is a good answer.

### e. Model governance — training with approval

```
בדוק את מודל האתר האחרון.
```
Expect `roadsafety_studio op=validate family=site`, allowed without approval (read-only); the gate card: Spearman
≥ 0.3 (report), calibration ± 25 % (report), deviance ratio (plugin rule), every threshold with its source tag.

```
אמן מודל אתר חדש עם train_until 2021.
```
Expect: in **Claude Code** the server itself shows an approval form ("yes, train / no, cancel"); in **Desktop** the
model asks in the chat and gets a ⏸ card if it called without approval. Decline → nothing trained (check with
`roadsafety_orient section=models`). Approve → a new candidate; then "validate it" → the gate; only a validated
model can be deployed. **Notice:** even "don't ask, just do it" does not bypass the form; it belongs to the server,
not to the model. Also: `/roadsafety:model_governance`.

### f. A finding card — what leaves the room

```
הפוך את התשובה האחרונה לכרטיס ממצא.
```
Expect `roadsafety_finding op=card` → claim + evidence (the numbers) + caveats + a rerun recipe. **Notice:** a card is
built from a ledger entry (a tool run), never from a chat message; if the last answer was prose, the model says so
and offers the latest run. `op=list` shows the ledger and the `idx`.

## 7. Behind the scenes — state and audit

- **Audit:** every tool call leaves one line in `%LOCALAPPDATA%\nl2sql-core\accidents\mcp_audit.jsonl`: which tool,
  which actions, how long, error yes/no, a note (for example `unconfirmed train`). Never the numbers themselves.
- **The ledger:** every answered run (refusals included) appends a line to `accidents\ledger.jsonl`; that is what a
  finding card reads.
- **The registry:** an approved training adds a candidate model; a deploy moves the deployed pointer. All of it under
  the app's shared data dir, so the page, the chat and automation see one state.
- **Consequence-free play:** register a second server with its own data dir —
  `claude mcp add --scope user roadsafety-play -e NL2SQL_ROADSAFETY_DB=<db> -e NL2SQL_CORE_DATA_DIR=C:\tmp\play -e PYTHONUTF8=1 -- <app>\.venv\Scripts\roadsafety-mcp.exe`
  — and train there as much as you like. (`seed-models.bat` honours the same variable if you set it before running.)

## 8. Limits

- **claude.ai in a browser: no.** A browser reaches only remote connectors, and no server for this database is
  hosted anywhere (a CBS decision). The channels are Claude Code and Claude Desktop, on the machine that holds the
  database.
- **Unattended runs (`claude -p`)** cannot show the approval form, so training is refused, correctly. Automation
  gets `--tools read-only`, which removes the studio from the catalog altogether.
- **Tables are capped at 60 rows** and the cap is stated; ask for a filter (road, years, `top_n`) instead of "everything".
- **No point clouds.** `map_scene` (the live map) and individual accident points stay on the page; the chat gets aggregates.
- **The prose is not evidence.** The model may add a remark of its own ("a temporary Corona dip"); what the tool
  returned is what was checked.

## 9. CBS rules

- The database stays on the machine, opened read-only; never uploaded, copied or sent.
- Tool outputs (aggregate tables, chart images) travel to Anthropic's API exactly like any message you type into
  Claude Code while working on the assignment. Internal course use.
- The credit line — `מקור הנתונים: הלשכה המרכזית לסטטיסטיקה (למ״ס); עיבוד: מעבדת הבטיחות בדרכים` — stays on
  anything you produce from these answers.

## 10. When something does not work

| You see | Do |
|---|---|
| `/mcp` shows no `roadsafety` | a new session / reload the VS Code window; `claude mcp get roadsafety`; re-run `install-chat.bat` |
| Desktop shows no connector | quit it fully and re-run `install-chat.bat` (it writes every config location Desktop has used), restart |
| the answer comes from a web search | switch web search off for the chat, or "use the roadsafety tool"; check the audit |
| "no deployed model" | `seed-models.bat`, or train → validate → deploy in the studio (or in the chat, with approval) |
| `API Error: 400 … does not support this model` | the CLI is older than the model in your settings → `claude update`, or `/model` |
| numbers differ from this guide | `roadsafety_orient section=models`: which models are deployed? The numbers assume the two reference models |

The full table: the README. Design and the full catalog: `docs/m1_design.md`. The acceptance set:
`docs/mcp_acceptance.md`. The narrated ten-step script: `docs/demo/MCP_DEMO.md`. Building such a channel for your
own plugin: `docs/BUILD_YOUR_OWN_MCP.md`.
