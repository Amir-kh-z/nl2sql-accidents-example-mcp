# P1 — Skeleton + answer envelope · final plan (synthesis, corrected 2026-08-29)

Winner = design A (envelope-first, "maintainability-and-demo-value"); grafts (1)–(21) merged. Two graft pairs contradict each other and were resolved (recorded in §6): **(8) beats (18)'s "ASCII `Result.title`" clause** → Layer-0 titles are Hebrew, no digits, `·`-separated; **(19) beats (9)** → the "correct" trap statement is the naive one + one added line (`AND case_type_code = 1`), with a SQL comment naming the code-canon equivalent. The review sweep's 37 corrections are applied; where they offered competing fixes for the same defect, one was chosen and the choice is recorded in §6 (basis/stamp = **strict ASCII**; caveat order = **data gap first**; `Result`-construction test = **token scan of construction sites**; trap test = **targeted line assertions, comment kept**).

Everything below was checked read-only against the live copy on 2026-08-29 through the engine's own `Context.query` (guardrail included): coverage rule fires for exactly 2009 at year level (16,856 casualty accidents vs 15 involved rows), for all 12 months of 2009 and for both road groups (urban 12,091 vs 9 · nonurban 4,765 vs 6); killed urban 2005 = **180** composite vs 373 single-key; 2024 breakdown (1,1)=405 (1,2)=2,452 (1,3)=5,458 (3,3)=44,687; `information_schema` = 31 BASE TABLE + 12 VIEW; last month 12; `max(accident_date)` = 2024-12-31; `ctx.tables()` = 43; the coverage statements run in ≈ 0.1 s. Added this pass: `involved` 2009 by series = **15 (case 1) / 139,368 (case 3)** — the 15 casualty-series rows are 3 uninjured, 1 severe, 11 slight; `vehicles` 2009 = 31,199 / 106,651; `accidents` 2009 = 16,856 casualty (308 fatal) / 61,391 damage-only; **no `road_type_code` outside 1–4 in either series (no NULLs)**; a single-key join attaches 11,848 damage-only person rows to 2009 casualty accidents; `app\bird_bench\acme_insurance.sqlite` has **29 tables** (Agreement, Agreement_Assessment, Agreement_Party_Role, Assesment_Party_Role, Assessment, Assessment_Result, …); `app\run.ps1` sets `$env:PYTHONUTF8 = "1"` before uvicorn.

---

## 1. Context

- Scope fixed by `docs/plan.md` §P1: dist `nl2sql-accidents` 0.1.0; package `nl2sql_accidents/{__init__, sqlkit, envelope, charts, dbcheck, actions/{trend,trap,about}}`; three actions exactly as PLAN_1 §4.1; envelope + `view`; tests per §8; editable install into `app\.venv`; restart; three actions on the 🧩 Modules page with note + credit in the PNG; `[P1]` commit; tag `v0.1`; data-dir state = shared default (P1 writes nothing; `about` only reads).
- Contract facts used (not re-derived): `Result(kind, data, title, note)` positional; one Result per action; `Registry.run` fills defaults only for `None`/`""`, validates nothing else; `Action.run` is a **required dataclass field evaluated at import** — a forward reference to `run` is a `NameError` that `discover()` turns into `Problem(name, "failed to import: NameError: …")` and the run route into "no module named 'accidents' is available"; `discover()` → `Registry(modules, problems)`, `Registry.get(name)`; number inputs arrive as JSON numbers from the page and strings elsewhere; markdown = `#` headings only, `-` bullets, `**`, `` ` ``, one paragraph per line, no tables/links/fences; note = muted `<p>` under every kind (a newline inside it collapses on the page but survives in JSON); chart with `png_base64` shows img + `spec.basis` + note; `adapters.module_run` discards tracebacks; route runs in a threadpool; `discover()` per request; `ctx.query` caches the read-only connection; `nl2sql_engine.configure()` is a **process-global** setter and `resolve_data_dir()` falls back to (and mkdirs) `%LOCALAPPDATA%\nl2sql-core` when `data_dir` is None.
- Data facts used: years 2005–2024, data end 2024-12-31; `involved` has no `road_type_code`; composite key `(accident_id, case_type_code)`; `road_type_code` ∈ {1, 2, 3, 4} only (both series, no NULLs; the dictionary's 5 = off-road never occurs); **the casualty-series `involved` rows for 2009 (case_type_code = 1) are missing — 15 rows vs 16,856 casualty accidents (every other year 20,981–51,093)**; the 2009 damage-only person rows (case 3: 139,368), vehicles 2009 (31,199 casualty / 106,651 damage-only) and `accidents` 2009 (16,856 casualty / 308 fatal / 61,391 damage-only) are complete → the data-driven coverage rule (no magic constant), which must be evaluated **inside the casualty series on the composite key** (a plain `count(*) FROM involved WHERE year = 2009` = 139,383 hides the gap; a single-key join attaches 11,848 damage-only person rows to 2009 casualty accidents).

## 2. File-by-file design

```
nl2sql-accidents-plugin/
  pyproject.toml
  nl2sql_accidents/__init__.py       __version__, MODULE (light imports only)
  nl2sql_accidents/sqlkit.py         ActionError, Refusal(reason, answerable, what_to_do, detail), q/lit/ilit/slit, on_key,
                                     as_int/as_choice/year_in_coverage/year_range, scalar/rows_safe, byar_ci, DATA_YEARS, ROAD_TYPES,
                                     MEASURES, GRANULARITY, build_trend_sql, other_road_sql, trap_statements, ABOUT_SQL
  nl2sql_accidents/envelope.py       CREDIT/CREDIT_SHORT/LAB_LINE, denominator kinds, version(), stamp_line, view_input, note_line,
                                     make_spec, dispatch, markdown_answer, refusal, guard(title)   ← the ONLY place that constructs Result
  nl2sql_accidents/charts.py         heb() (bidi + digit-preserving _mirror), PNG_CAVEAT_CAP, caveat_ys(), png() frame, line_chart()
  nl2sql_accidents/dbcheck.py        check(ctx) -> reason | None, require(ctx) (three reason variants)
  nl2sql_accidents/actions/__init__.py (empty)
  nl2sql_accidents/actions/trend.py  run + _caveats, then ACTION (declared LAST — see §2.7)
  nl2sql_accidents/actions/trap.py   run, then ACTION  (naive_vs_correct)
  nl2sql_accidents/actions/about.py  _deployed + run, then ACTION
  tests/conftest.py, helpers.py, test_contract.py, test_sqlkit.py, test_envelope.py, test_charts.py,
        test_trend.py, test_trap.py, test_about.py, test_live.py
```

### 2.1 `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "nl2sql-accidents"
version = "0.1.0"
description = "Road Safety Lab (מעבדת הבטיחות בדרכים): correct-by-construction actions over the Israel road-accidents database (CBS) for the NL2SQL app — series filter, join key, denominator badge, caveats and CBS credit on every answer."
readme = "README.md"
requires-python = ">=3.11"
# No engine dependency on purpose: installed into the app venv that provides nl2sql-core; requires_core in the
# Module declaration is the contract. numpy / matplotlib / python-bidi are borrowed from the host, imported lazily.
dependencies = []

[project.optional-dependencies]
ml = ["xgboost"]            # studio tier (P4+); xgboost wheels need Python >= 3.12
dev = ["pytest", "build"]

[project.entry-points."nl2sql.modules"]
accidents = "nl2sql_accidents:MODULE"

[tool.setuptools]
# BOTH packages — an explicit list does not recurse. plan.md's single entry would build a wheel without actions/.
packages = ["nl2sql_accidents", "nl2sql_accidents.actions"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [".", "tests"]
```

### 2.2 `__init__.py`

```python
# -*- coding: utf-8 -*-
"""nl2sql-accidents — מעבדת הבטיחות בדרכים. discover() runs per request: keep this import light."""
__version__ = "0.1.0"          # defined BEFORE the action imports (envelope.version() falls back to it); pinned to pyproject by a test
from nl2sql_engine.modules import Module
from .actions import about, trap, trend

MODULE = Module(
    name="accidents", label="🚦 מעבדת הבטיחות בדרכים",
    description="Road Safety Lab over the Israel road-accidents database (CBS). Every answer carries its series filter, join key, denominator, caveats and CBS credit — correct by construction; and it refuses, readably, what the data cannot answer.",
    requires_core=">=1.0,<2.0",
    actions=[trend.ACTION, trap.ACTION, about.ACTION])
```
Action modules import only stdlib + `nl2sql_engine.modules` + `..sqlkit/..envelope/..dbcheck`; `charts` (and matplotlib inside it) is imported inside `run` only when `view == "chart"`. **Every action module defines the decorated `run` (and its helpers) first and `ACTION = Action(…, run=run)` as its last statement** — this import succeeds only if all three `ACTION`s bind.

### 2.3 `sqlkit.py`

```python
class ActionError(Exception):
    """A person's mistake (bad input). envelope.guard turns it into an error result: one sentence, no traceback."""
class Refusal(Exception):
    """What the data cannot answer → refusal card. `reason` is ONE Hebrew sentence (no newline: it is the note's head);
    `detail` is optional free text (English allowed) rendered as its own bullet in the card body only."""
    def __init__(self, reason, answerable=(), what_to_do=None, detail=None): ...

DATA_YEARS = (2005, 2024); DATA_END_HE = "31.12.2024"
CASE_FILTER = "case_type_code = 1"
def on_key(a="a", i="i"): return f"{a}.accident_id = {i}.accident_id AND {a}.case_type_code = {i}.case_type_code"
def q(ident): return '"' + str(ident).replace('"', '""') + '"'
def lit(v):  # float this code computed; refuses non-finite (Shapes idiom) — P2 consumer
def ilit(v): # int this code validated; refuses bool / non-int
def slit(s): return "'" + str(s).replace("'", "''") + "'"

def as_int(v, name) -> int:
    """JSON number, float or string ('2024', '2024.0') → int; bool/NaN/'abc'/2023.5 → ActionError naming the input."""
def as_choice(v, name, choices) -> str:   # ActionError("Unknown <name> 'x'. One of: a, b, c.") in dict order — the server validates nothing
def year_in_coverage(y: int, name) -> int:
    """Outside DATA_YEARS → Refusal('אין נתונים לשנת 2030 — הנתונים מסתיימים ב-31.12.2024' | 'אין נתונים לשנת 2000 — הנתונים מתחילים ב-2005',
       answerable=['כל שנה בין 2005 ל-2024']). No clamping."""
def year_range(from_year, to_year) -> tuple[int, int]:
    """as_int both → from > to → ActionError('from_year (2024) is after to_year (2020) — swap them.') → year_in_coverage both."""
def scalar(v):  # Decimal→float, NaN/inf→None, numpy→.item(), date/time→str, bool kept, int/str passthrough
def rows_safe(rows): return [[scalar(c) for c in r] for r in rows]
def byar_ci(count, denom=1.0, z=1.96) -> tuple[float, float]:   # exact-style Poisson interval, no scipy; P2 consumer, tested now

MEASURES = {   # key: (grain table, value expression, Hebrew label) — PLAN_1 §4.1 order: it IS the dropdown order and the error-text order
    "accidents":       ("accidents", "count(DISTINCT (a.accident_id, a.case_type_code))", "תאונות עם נפגעים"),
    "killed":          ("involved",  "count(*) FILTER (WHERE i.injury_severity_code = 1)", "הרוגים"),
    "severe_injured":  ("involved",  "count(*) FILTER (WHERE i.injury_severity_code = 2)", "פצועים קשה"),
    "slight_injured":  ("involved",  "count(*) FILTER (WHERE i.injury_severity_code = 3)", "פצועים קל"),
    "fatal_accidents": ("accidents", "count(DISTINCT (a.accident_id, a.case_type_code)) FILTER (WHERE a.severity_code = 1)", "תאונות קטלניות"),
}
GRANULARITY = {"year": "שנה", "month": "חודש"}
ROAD_TYPES = {"all": ((), "כל הדרכים"), "urban": ((1, 2), "דרכים עירוניות"), "nonurban": ((3, 4), "דרכים לא-עירוניות")}
# live: codes 1–4 only, both series, no NULLs. Any other code (dictionary: 5 = off-road) would count in "all" only —
# the road caveat is data-driven (other_road_sql), never an assertion about a code the data does not carry.

def other_road_sql(y0, y1) -> str:   # one cheap count behind the road caveat (live: always 0)
    return (f"SELECT count(*) AS n FROM accidents\nWHERE case_type_code = 1\n  AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"  AND (road_type_code IS NULL OR road_type_code NOT IN (1, 2, 3, 4))")
```

**`build_trend_sql(measure, granularity, road_type, y0, y1) -> str`** — four switches (grain, value expr, period keys, road join+predicate); the series filter is written on the base table (never hidden in `v_casualty_*`); accidents counted on the composite key; a calendar CTE zero-fills real zeros; person measures carry the **coverage CTE** (graft 1/14): `covered = people >= casualty_accidents`, value `CASE WHEN covered THEN coalesce(value, 0) END` (NULL, never 0); the join to `accidents` in `counts` exists only for person measures with a road filter. The header comment uses the same ASCII separators as `basis`/`stamp` (`|`, `-`) for consistency.

```python
def build_trend_sql(measure, granularity, road_type, y0, y1):
    grain, expr, _ = MEASURES[measure]; codes = ROAD_TYPES[road_type][0]; monthly = granularity == "month"
    t = "i" if grain == "involved" else "a"
    keys = lambda al: f"{al}.year" + (f", {al}.month" if monthly else "")
    road = f"\n      AND a.road_type_code IN ({', '.join(ilit(c) for c in codes)})   -- {road_type}" if codes else ""
    head = f"-- nl2sql-accidents | trend | measure={measure} | granularity={granularity} | road_type={road_type} | {y0}-{y1}\n"
    periods = (f"periods AS (\n    SELECT y AS year{', m AS month' if monthly else ''}\n"
               f"    FROM range({ilit(y0)}, {ilit(y1 + 1)}) t(y){', range(1, 13) u(m)' if monthly else ''}\n)")
    join = f"\n    JOIN accidents a ON {on_key()}   -- composite key (dossier §5.3): involved has no road_type_code" \
           if (grain == "involved" and codes) else ""
    counts = (f"counts AS (\n    SELECT {keys(t)},\n           {expr} AS value\n    FROM {grain} {t}{join}\n"
              f"    WHERE {t}.case_type_code = 1     -- casualty series only (dossier §5.1)\n"
              f"      AND {t}.year BETWEEN {ilit(y0)} AND {ilit(y1)}{road}\n    GROUP BY {keys(t)}\n)")
    on = "c.year = p.year" + (" AND c.month = p.month" if monthly else "")
    sel = keys("p")
    if grain == "accidents":
        return head + f"WITH {periods},\n{counts}\nSELECT {sel}, coalesce(c.value, 0) AS {q(measure)}\nFROM periods p\nLEFT JOIN counts c ON {on}\nORDER BY {sel}"
    coverage = (f"coverage AS (                    -- person-level completeness per period (dossier §5.4; involved 2009 (case 1) = 15 rows)\n"
                f"    SELECT {keys('a')},\n           count(DISTINCT (a.accident_id, a.case_type_code)) AS casualty_accidents,\n"
                f"           count(i.person_id) AS people\n    FROM accidents a\n    LEFT JOIN involved i ON {on_key()}\n"
                f"    WHERE a.case_type_code = 1\n      AND a.year BETWEEN {ilit(y0)} AND {ilit(y1)}{road}\n    GROUP BY {keys('a')}\n)")
    onc = "cv.year = p.year" + (" AND cv.month = p.month" if monthly else "")
    return head + (f"WITH {periods},\n{coverage},\n{counts}\n"
                   f"SELECT {sel},\n       CASE WHEN coalesce(cv.people, 0) >= coalesce(cv.casualty_accidents, 0) THEN coalesce(c.value, 0) END AS {q(measure)},\n"
                   f"       coalesce(cv.people, 0) AS people,\n       coalesce(cv.casualty_accidents, 0) AS casualty_accidents,\n"
                   f"       coalesce(cv.people, 0) >= coalesce(cv.casualty_accidents, 0) AS covered\n"
                   f"FROM periods p\nLEFT JOIN counts c ON {on}\nLEFT JOIN coverage cv ON {onc}\nORDER BY {sel}")
```

Expanded statements (all three run live through `ctx.query`, 2026-08-29):

`killed · year · all · 2005–2024` → 20 rows; `(2005, 476, 50370, 17509, True)`, `(2009, None, 15, 16856, False)`, `(2024, 439, 20981, 8315, True)`:
```sql
-- nl2sql-accidents | trend | measure=killed | granularity=year | road_type=all | 2005-2024
WITH periods AS (
    SELECT y AS year
    FROM range(2005, 2025) t(y)
),
coverage AS (                    -- person-level completeness per period (dossier §5.4; involved 2009 (case 1) = 15 rows)
    SELECT a.year,
           count(DISTINCT (a.accident_id, a.case_type_code)) AS casualty_accidents,
           count(i.person_id) AS people
    FROM accidents a
    LEFT JOIN involved i ON a.accident_id = i.accident_id AND a.case_type_code = i.case_type_code
    WHERE a.case_type_code = 1
      AND a.year BETWEEN 2005 AND 2024
    GROUP BY a.year
),
counts AS (
    SELECT i.year,
           count(*) FILTER (WHERE i.injury_severity_code = 1) AS value
    FROM involved i
    WHERE i.case_type_code = 1     -- casualty series only (dossier §5.1)
      AND i.year BETWEEN 2005 AND 2024
    GROUP BY i.year
)
SELECT p.year,
       CASE WHEN coalesce(cv.people, 0) >= coalesce(cv.casualty_accidents, 0) THEN coalesce(c.value, 0) END AS "killed",
       coalesce(cv.people, 0) AS people,
       coalesce(cv.casualty_accidents, 0) AS casualty_accidents,
       coalesce(cv.people, 0) >= coalesce(cv.casualty_accidents, 0) AS covered
FROM periods p
LEFT JOIN counts c ON c.year = p.year
LEFT JOIN coverage cv ON cv.year = p.year
ORDER BY p.year
```
`killed · month · urban` → `periods` = `range(y0, y1+1) t(y), range(1, 13) u(m)`; `counts` adds `JOIN accidents a ON a.accident_id = i.accident_id AND a.case_type_code = i.case_type_code` and `AND a.road_type_code IN (1, 2)   -- urban`; `coverage` carries the same road predicate; keys `year, month`. Live 2005–2024: 240 rows, exactly the 12 months of 2009 uncovered, urban 2005 Σ = **180**, urban 2024 Σ = 150.
`fatal_accidents · month · nonurban` → no coverage CTE, no join: `count(DISTINCT (a.accident_id, a.case_type_code)) FILTER (WHERE a.severity_code = 1)` on `accidents a` with `a.road_type_code IN (3, 4)`; 2024 Σ = 256. The other 27 combinations differ only by the switch values.

**`trap_statements(year) -> dict`** (graft 19 + 9's comment; 19 wins on the shape; the comment stays — the literal `case_type_code = 1` therefore appears twice in statement 2, and the tests assert on the predicate line, §3.3):
```sql
-- 1. naive — what a plain "light accidents" query does: the label alone, both series answer
SELECT count(*) AS n
FROM accidents
WHERE severity_label = 'קלה' AND year = 2024
```
```sql
-- 2. correct — the SAME statement plus one line: the casualty series only (dossier §5.1–5.2)
--    code canon equivalent: case_type_code = 1 AND severity_code = 3 (severity labels are drift-free 2005–2024)
SELECT count(*) AS n
FROM accidents
WHERE severity_label = 'קלה' AND year = 2024
  AND case_type_code = 1
```
```sql
-- 3. breakdown — both series by severity code: the arithmetic behind the gap
SELECT case_type_code, severity_code, count(*) AS n
FROM accidents
WHERE year = 2024
GROUP BY 1, 2
ORDER BY 1, 2
```
**`ABOUT_SQL`** (one statement, scalar subqueries; `CAST(max(accident_date) AS VARCHAR)` keeps JSON safe): `accidents_rows, casualty_accidents (case 1), damage_only (case 3), involved_rows, casualty_involved (case 1), vehicles_rows, first_year, last_year, last_month (max(month) WHERE year = max(year)), data_end, n_tables (information_schema.tables main/BASE TABLE), n_views (VIEW)`. Live: 1,290,788 · 270,723 · 1,020,065 · 2,987,206 · 684,051 · 2,297,533 · 2005 · 2024 · 12 · '2024-12-31' · 31 · 12.

### 2.4 `envelope.py` — the one Result factory

```python
CREDIT = "מקור הנתונים: הלשכה המרכזית לסטטיסטיקה (למ״ס); עיבוד: מעבדת הבטיחות בדרכים"
CREDIT_SHORT = "הלשכה המרכזית לסטטיסטיקה"
LAB_LINE = "מעבדת הבטיחות בדרכים · פועלת רק על מסד תאונות הדרכים (למ״ס)"      # refusal-card footer (never a CBS data credit)
REFUSAL_HEADING = "# ❌ לא ניתן לענות"          # single '#': Layer 0 renders deeper levels tiny (deviation from concept map's '##')
CAVEAT_DATA_END = "הנתונים מסתיימים ב-31.12.2024"
CAVEAT_COUNTS_NOT_RISK = "ספירות אינן סיכון — אין כאן מכנה חשיפה"
DENOM_KINDS = ("exposure", "counts", "none", "na")    # green / amber / red (a rate with no denominator) / grey (not a rate)
def denominator(kind, label) -> dict: ...             # {"kind","label"}; ValueError on an unknown kind
DENOM_COUNTS = denominator("counts", "ספירות בלבד — ללא מכנה חשיפה"); DENOM_NA = denominator("na", "לא רלוונטי")
VIEWS = ("chart", "table", "sql", "markdown")
_VIEW_HELP = {"chart": "chart = PNG (+ the full answer in the spec)", "table": "table = the rows",
              "sql": "sql = the exact statement run", "markdown": "markdown = the explanation card"}

def version() -> str:            # importlib.metadata.version("nl2sql-accidents") → fallback nl2sql_accidents.__version__
def stamp_line(measure, granularity, road_type, y0, y1) -> str:      # the PNG footer provenance — ASCII by construction (drawn un-shaped)
    return f"nl2sql-accidents {version()} | {measure} / {granularity} / {road_type} | {y0}-{y1}"
def view_input(default, choices) -> Input:   # tooltip built from THIS action's choices, never advertising a view it lacks
    return Input(kind="choice", label="תצוגה", default=default, choices=list(choices), help="; ".join(_VIEW_HELP[c] for c in choices))
def note_line(denom, caveats) -> str:        # EXACT: f"מכנה: {denom['label']} · הסתייגות: {'; '.join(caveats) or 'אין'} · מקור: {CREDIT_SHORT}"
def make_spec(type_, *, basis, rows, columns, sql, denominator, caveats, png_base64=None, **extra) -> dict:
    # {"type", "renderer": "png"|"data", "png_base64", "basis", "rows", "columns", "sql", "denominator", "caveats", "credit": CREDIT,
    #  "plugin_version": version(), "x": columns[0], "y": columns[-1], **extra}
def dispatch(view, spec, title, body=None) -> Result:
    # chart → Result("chart", spec, title, note); table → Result("table", {"rows","columns"}, title, note); sql → Result("sql", spec["sql"], title, note)
    # markdown (body given) → markdown_answer(...); anything else → ActionError("Unknown view 'x'. One of: chart, table, sql, markdown.")
def markdown_answer(title, body: list[str], *, denom, caveats) -> Result:
    # lines = [f"מכנה: {denom['label']}"] + body + (["# הסתייגויות"] + ["- c"...] if caveats) + [CREDIT]; note = note_line(...)
def refusal(reason, answerable=(), *, title, what_to_do=None, detail=None) -> Result:
    lines = ([REFUSAL_HEADING, reason] + ([f"- הסיבה: {detail}"] if detail else []) + ([f"- מה לעשות: {what_to_do}"] if what_to_do else [])
             + [f"- מה כן אפשר: {a}" for a in answerable] + [LAB_LINE])
    note = f"לא ניתן לענות · {reason.splitlines()[0][:80]} · מעבדת הבטיחות בדרכים"     # ONE line: head sentence only, detail stays in the body
    return Result("markdown", "\n".join(lines), title, note)
def guard(title: str):
    """Decorator factory. Folds the DB probe in (one place — impossible to forget in P2). adapters.module_run discards
    tracebacks, so unexpected failures come back WITH a short traceback."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapped(ctx, **kw):
            try:
                from . import dbcheck; dbcheck.require(ctx)
                return fn(ctx, **kw)
            except Refusal as r:      return refusal(r.reason, r.answerable, title=title, what_to_do=r.what_to_do, detail=r.detail)
            except ActionError as e:  return Result.error(str(e))
            except Exception as e:    return Result.error(f"{type(e).__name__}: {e}\n\n{traceback.format_exc(limit=4)}")   # noqa: BLE001
        return wrapped
    return deco
```
Layer-0 string discipline (grafts 8/18): `Result.title` = Hebrew, **no digits**, `·`-separated (`מגמה · הרוגים לפי שנה · כל הדרכים`, `המלכודת של התאונות הקלות`, `אודות · מעבדת הבטיחות בדרכים`); **`spec.basis` and the PNG `stamp` are strict ASCII** (`|` and `-` as separators; asserted with `.isascii()` — the basis is the one un-shaped LTR line Layer 0 prints under the PNG, the stamp is drawn un-shaped in a monospace font); `·`/`–` live only in Hebrew-facing text (titles, note, PNG title/caveats, markdown); `action.help` (visible) and `input.help` (tooltip) English; input labels short Hebrew without digits (`מדד`, `רזולוציה`, `סוג דרך`, `שנת התחלה`, `שנת סיום`, `תצוגה`, `שנה`); action labels `מגמות · trend`, `המלכודת · naive_vs_correct`, `אודות · about`; the note is **one line** (no newline: a refusal's `reason` is one sentence, its `detail` goes to the body only); **no caveat ever contains `;`** (it is the note's separator). Digits live in the PNG (bidi-shaped), markdown values and the note.

### 2.5 `charts.py` — thread-safe, lazy, Hebrew-safe

```python
_HEB = re.compile(r"[\u0590-\u05ff]")
_INK, _INK_SOFT, _INK_FAINT = "#26323d", "#5a6672", "#8b959e"
_TEAL, _ORANGE, _GRID = "#0d9488", "#f7931e", "#e8e4e0"            # engine palette if importable, else these
_AMBER_FACE, _AMBER_EDGE, _AMBER_TEXT = "#fff4e0", "#f7931e", "#8a5a00"
PNG_CAVEAT_CAP = 6          # P1's longest list is exactly 6 (gap · data-end · counts≠risk · killed≠fatal · COVID · road): nothing P1 emits is truncated
_CAVEAT_TOP, _CAVEAT_FLOOR, _CAVEAT_PITCH = 0.245, 0.090, 0.034

def heb(text) -> str:
    s = str(text)
    if not _HEB.search(s): return s
    try:
        from bidi.algorithm import get_display
        return get_display(s, base_dir="R")
    except Exception:                                  # noqa: BLE001 — host bidi missing/broken
        return _mirror(s)
def _mirror(s):   # [::-1] that keeps digit/Latin runs readable: reverse all, re-reverse the non-Hebrew runs
    return re.sub(r"[^\u0590-\u05ff\s]+", lambda m: m.group(0)[::-1], s[::-1])

def caveat_ys(n_shown: int) -> list[float]:
    """Figure-fraction tops of the caveat lines: the 0.034 pitch up to 5 lines, then compressed so the LAST line's top stays at
    0.090 (its bbox bottom ≈ 0.072; the credit's top ≈ 0.048) — 6 lines → 0.031, 7 (6 + overflow marker) → 0.026.
    0.245 sits 8 pt below the rotated monthly tick labels. Pure, so the geometry is unit-tested."""
    pitch = min(_CAVEAT_PITCH, (_CAVEAT_TOP - _CAVEAT_FLOOR) / max(n_shown - 1, 1))
    return [_CAVEAT_TOP - i * pitch for i in range(n_shown)]

def png(draw, *, title, badge, caveats, stamp, figsize=(9.6, 5.8), dpi=140) -> str:
    """Figure + FigureCanvasAgg (no pyplot: the route is threaded); explicit white background (dark mode)."""
    from matplotlib.figure import Figure; from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=figsize, dpi=dpi); FigureCanvasAgg(fig)
    fig.text(0.97, 0.955, heb(title), ha="right", va="top", fontsize=13, color=_INK, fontweight="bold")         # Hebrew title, top-RIGHT
    fig.text(0.97, 0.895, heb(badge), ha="right", va="top", fontsize=8.5, color=_AMBER_TEXT,                     # amber denominator badge
             bbox=dict(boxstyle="round,pad=0.35", facecolor=_AMBER_FACE, edgecolor=_AMBER_EDGE, linewidth=0.8))
    ax = fig.add_axes([0.08, 0.33, 0.89, 0.50]); draw(fig, ax)
    shown = list(caveats[:PNG_CAVEAT_CAP])                                                                        # caveat list, right-aligned '•'
    if len(caveats) > PNG_CAVEAT_CAP: shown.append(f"… ועוד {len(caveats) - PNG_CAVEAT_CAP} הסתייגויות (בהערה)")
    for line, y in zip(shown, caveat_ys(len(shown))):
        fig.text(0.97, y, heb("• " + line), ha="right", va="top", fontsize=7.5, color=_INK_SOFT)
    fig.text(0.97, 0.03, heb(CREDIT), ha="right", va="bottom", fontsize=7, color=_INK_FAINT)                     # CBS credit bottom-RIGHT
    fig.text(0.03, 0.03, stamp, ha="left", va="bottom", fontsize=6.5, color=_INK_FAINT, family="monospace")      # ASCII provenance bottom-LEFT (drawn un-shaped: must carry no Hebrew)
    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor="white")
    return base64.b64encode(buf.getvalue()).decode("ascii")

def line_chart(labels, values, *, ylabel, gaps: list[int], monthly: bool, **frame) -> str:
    from matplotlib.ticker import FuncFormatter        # lazy, beside png()'s Figure imports — pyplot is never imported (threaded route)
    def draw(fig, ax):
        ys = [float("nan") if v is None else float(v) for v in values]; xs = range(len(ys))
        ax.plot(xs, ys, color=_TEAL, linewidth=2, marker="o", markersize=3 if monthly else 4)
        for i in gaps:   # uncovered periods: grey band + ✕ + 'אין נתונים'
            ax.axvspan(i - 0.5, i + 0.5, color="#f1f1f1", zorder=0)
            ax.plot([i], [0], marker="x", color=_ORANGE, markersize=7, markeredgewidth=1.6, clip_on=False)
            ax.annotate(heb("אין נתונים"), (i, 0), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=7, color=_ORANGE, rotation=90 if monthly else 0)
        real = [(i, y) for i, y in enumerate(ys) if y == y]
        for i, y in (real[0], real[-1]) if real else ():                       # first/last non-gap values annotated
            ax.annotate(f"{int(y):,}", (i, y), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8, color=_INK)
        ticks = [i for i, l in enumerate(labels) if (l.endswith("-01") if monthly else True)]
        ax.set_xticks(ticks); ax.set_xticklabels([labels[i][:4] if monthly else labels[i] for i in ticks], rotation=45 if len(ticks) > 12 else 0, fontsize=8)
        top = max((y for y in ys if y == y), default=0.0); ax.set_ylim(0, max(1.0, top * 1.18))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}")); ax.set_ylabel(heb(ylabel), fontsize=9, color=_INK_SOFT)
        ax.grid(axis="y", color=_GRID, linewidth=0.8); ax.set_axisbelow(True)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    return png(draw, **frame)
```
PNG anatomy (grafts 7/15), top→bottom: Hebrew title (`הרוגים לפי שנה · כל הדרכים · 2005–2024`) → amber badge (`מכנה: ספירות בלבד — ללא מכנה חשיפה`) → plot (time axis left→right; only text is bidi-shaped) → up to 6 caveat lines, most specific first (the data-gap line leads, so it is always on the canonical face next to the grey band; the block self-compresses so the last line always clears the credit) → footer: credit right, stamp left (`nl2sql-accidents 0.1.0 | killed / year / all | 2005-2024`).

### 2.6 `dbcheck.py`

```python
PROBE_SQL = "SELECT 1 FROM accidents WHERE case_type_code = 1 LIMIT 1"
REASON_HE = "החיבור הנוכחי אינו מסד תאונות הדרכים של הלמ״ס"          # one sentence, no newline — it heads the one-line note
WHAT_TO_DO = "בחרו את החיבור israel_accidents באפליקציה הראשית ופתחו את עמוד המודולים מחדש"
ANSWERABLE = ["EDA ו-Shapes פועלים על כל מסד נתונים"]

def check(ctx) -> str | None:
    """None on the accidents DB, else a reason a person can act on (three variants + a catch-all)."""
    try:
        tables = ctx.tables()
        if "accidents" not in tables:
            n = len(tables)
            return f"no table named accidents in this connection ({n} table{'s' if n != 1 else ''}: {', '.join(tables[:6])}{', …' if n > 6 else ''})"
        if "case_type_code" not in ctx.columns("accidents"):
            return "accidents has no column case_type_code (not the CBS two-series schema)"
        if not ctx.query(PROBE_SQL)[1]:
            return "accidents holds no casualty rows (case_type_code = 1)"
    except Exception as exc:                               # noqa: BLE001 — a foreign DB may raise anything
        return f"accidents.case_type_code could not be read: {str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__}"
    return None

def require(ctx) -> None:
    reason = check(ctx)
    if reason:
        raise Refusal(REASON_HE, ANSWERABLE, what_to_do=WHAT_TO_DO, detail=reason)     # detail → the "- הסיבה: …" bullet, body only
```
Called by `guard` before every action body (≈1 ms; `tables()`/`columns()` cached by the engine).

### 2.7 `actions/trend.py`

`run` and `_caveats` come first; `ACTION` is the **last statement** of the module.

```python
@guard("מגמה")
def run(ctx, measure="killed", granularity="year", road_type="all", from_year=2005, to_year=2024, view="chart"):
    measure = as_choice(measure, "measure", MEASURES); granularity = as_choice(granularity, "granularity", GRANULARITY)
    road_type = as_choice(road_type, "road_type", ROAD_TYPES); view = as_choice(view, "view", ("chart", "table", "sql"))
    y0, y1 = year_range(from_year, to_year)                       # from > to → error; outside 2005–2024 → refusal card
    sql = build_trend_sql(measure, granularity, road_type, y0, y1)
    columns, raw = ctx.query(sql); rows = rows_safe(raw)
    grain, _, label = MEASURES[measure]; vi = columns.index(measure); monthly = granularity == "month"
    labels = [str(r[0]) if not monthly else f"{r[0]}-{r[1]:02d}" for r in rows]
    gap_idx = [i for i, r in enumerate(rows) if grain == "involved" and r[-1] is False]
    gaps = [(labels[i], rows[i][columns.index("people")], rows[i][columns.index("casualty_accidents")]) for i in gap_idx]
    other_roads = int(ctx.query(other_road_sql(y0, y1))[1][0][0]) if road_type != "all" else 0   # one cheap count behind the road caveat (live: 0)
    caveats = _caveats(measure, road_type, y0, y1, gaps, other_roads)
    heb_title = f"{label} לפי {GRANULARITY[granularity]} · {ROAD_TYPES[road_type][1]} · {y0}–{y1}"
    stamp = stamp_line(measure, granularity, road_type, y0, y1)   # built before the view branch: it rides in the spec for every view
    png = None
    if view == "chart":
        from .. import charts
        png = charts.line_chart(labels, [r[vi] for r in rows], ylabel=label, gaps=gap_idx, monthly=monthly,
                                title=heb_title, badge=f"מכנה: {DENOM_COUNTS['label']}", caveats=caveats, stamp=stamp)
    basis = f"{measure} by {granularity} | road_type={road_type} | {y0}-{y1} | {len(rows)} rows | {grain} WHERE case_type_code = 1"
    spec = make_spec("accidents/trend", png_base64=png, basis=basis, rows=rows, columns=columns, sql=sql,
                     denominator=DENOM_COUNTS, caveats=caveats, measure=measure, granularity=granularity, road_type=road_type,
                     from_year=y0, to_year=y1, gap_periods=[g[0] for g in gaps], stamp=stamp, y=measure)
    return dispatch(view, spec, f"מגמה · {label} לפי {GRANULARITY[granularity]} · {ROAD_TYPES[road_type][1]}")

def _caveats(measure, road_type, y0, y1, gaps, other_roads=0):
    """Most specific first: the data-gap line leads so it survives any PNG cap and opens the note. No ';' inside any line."""
    out = []
    if len(gaps) == 1:
        p, people, acc = gaps[0]; out.append(f"נתוני נפגעים (involved) חסרים ב-{p}: {people:,} רשומות מול {acc:,} תאונות — הערך מוצג כריק")
    elif gaps:
        people, acc = sum(g[1] for g in gaps), sum(g[2] for g in gaps)
        out.append(f"נתוני נפגעים (involved) חסרים ב-{len(gaps)} תקופות: {', '.join(g[0] for g in gaps[:3])}"
                   f"{' ועוד ' + str(len(gaps) - 3) if len(gaps) > 3 else ''} ({people:,} רשומות מול {acc:,} תאונות) — הערכים מוצגים כריק")
    out += [CAVEAT_DATA_END, CAVEAT_COUNTS_NOT_RISK]
    if measure in ("killed", "fatal_accidents"): out.append("הרוגים (אנשים) ≠ תאונות קטלניות (אירועים)")
    if y0 <= 2021 and y1 >= 2020:                out.append("2020–2021: ירידה זמנית בתקופת הקורונה")
    if road_type != "all":                       # data-driven: live carries codes 1–4 only, so live always gets the second wording
        out.append(f"עירוני = road_type_code 1–2, לא-עירוני = 3–4 — {other_roads:,} תאונות עם קוד דרך אחר (5 = שטח) נכללות רק ב'כל הדרכים'" if other_roads
                   else "עירוני = road_type_code 1–2, לא-עירוני = 3–4 (כל הדרכים = סכום שניהם בנתונים אלה)")
    return out

ACTION = Action(name="trend", label="מגמות · trend",
    help="Counts over time from the casualty series (case_type_code = 1): accidents, fatal accidents, people killed / severely / slightly injured — by year or month, all roads or urban / non-urban. Counts, not risk: there is no exposure denominator. Periods whose person-level records are missing are shown as gaps, never as 0 (on the live copy: 2009).",
    inputs={
        "measure":     Input(kind="choice", label="מדד", default="killed", choices=list(MEASURES),
                             help="accidents / fatal_accidents count events (table accidents); killed / severe_injured / slight_injured count people (table involved). killed ≠ fatal_accidents."),
        "granularity": Input(kind="choice", label="רזולוציה", default="year", choices=list(GRANULARITY)),
        "road_type":   Input(kind="choice", label="סוג דרך", default="all", choices=list(ROAD_TYPES),
                             help="urban = road_type_code 1-2, nonurban = 3-4; any other code would count in all only (the live copy carries none); person measures join accidents on (accident_id, case_type_code)"),
        "from_year":   Input(kind="number", label="שנת התחלה", default=2005, help="2005-2024"),
        "to_year":     Input(kind="number", label="שנת סיום", default=2024, help="data ends 2024-12-31"),
        "view":        view_input("chart", ["chart", "table", "sql"]),
    }, run=run)   # defined after run: Action.run is a required field evaluated at import — adapters/discover() turn a NameError here into a 'failed to import' Problem card
```
Exact spec (chart, defaults, live): `type accidents/trend · renderer png · basis "killed by year | road_type=all | 2005-2024 | 20 rows | involved WHERE case_type_code = 1" · stamp "nl2sql-accidents 0.1.0 | killed / year / all | 2005-2024" · columns ["year","killed","people","casualty_accidents","covered"] · rows [[2005,476,50370,17509,true], …, [2009,null,15,16856,false], …, [2024,439,20981,8315,true]] · denominator {"kind":"counts","label":"ספירות בלבד — ללא מכנה חשיפה"} · caveats ["נתוני נפגעים (involved) חסרים ב-2009: 15 רשומות מול 16,856 תאונות — הערך מוצג כריק", data-end, counts≠risk, killed≠fatal, COVID] · credit CREDIT · plugin_version "0.1.0" · gap_periods ["2009"]`. With `road_type=urban` the list is six (gap `9 רשומות מול 12,091 תאונות` first, the road line last, "סכום שניהם" wording on live).
Exact note (identical on chart/table/sql, defaults): `מכנה: ספירות בלבד — ללא מכנה חשיפה · הסתייגות: נתוני נפגעים (involved) חסרים ב-2009: 15 רשומות מול 16,856 תאונות — הערך מוצג כריק; הנתונים מסתיימים ב-31.12.2024; ספירות אינן סיכון — אין כאן מכנה חשיפה; הרוגים (אנשים) ≠ תאונות קטלניות (אירועים); 2020–2021: ירידה זמנית בתקופת הקורונה · מקור: הלשכה המרכזית לסטטיסטיקה`.

### 2.8 `actions/trap.py` — `naive_vs_correct`

Imports `from nl2sql_engine.modules import Action, Input` and `from ..envelope import view_input, make_spec, dispatch, denominator, guard, CAVEAT_DATA_END` (allowed by §2.2's import rule). Inputs `year` (number, default 2024, label `שנה`), `view` (`markdown | sql`, default markdown). Title `המלכודת של התאונות הקלות`.

```python
@guard("המלכודת של התאונות הקלות")
def run(ctx, year=2024, view="markdown"):
    y = year_in_coverage(as_int(year, "year"), "year"); view = as_choice(view, "view", ("markdown", "sql"))
    s = trap_statements(y)
    naive = int(ctx.query(s["naive"])[1][0][0]); correct = int(ctx.query(s["correct"])[1][0][0])
    by = {(int(c), int(sv)): int(n) for c, sv, n in ctx.query(s["breakdown"])[1]}
    dmg = by.get((3, 3), 0); fatal, severe, slight = by.get((1, 1), 0), by.get((1, 2), 0), by.get((1, 3), 0)
    ratio = round(naive / correct, 1) if correct else None
    body = [f"# {naive:,} לעומת {correct:,}",
            f"**נאיבי** — {naive:,} רשומות עם severity_label = 'קלה' בשנת {y} (ללא סינון סדרה)",
            f"**נכון** — {correct:,} תאונות קלות עם נפגעים (אותה שאילתה + case_type_code = 1)",
            (f"**הפער** — פי {ratio}: {naive - correct:,} רשומות נזק-בלבד (case_type_code = 3) נספרו כ\"קלות\"" if ratio
             else f"**הפער** — אין תאונות קלות עם נפגעים ב-{y}"),
            "# למה זה קורה",
            "- בטבלה accidents שתי סדרות: 1 = תאונות עם נפגעים, 3 = נזק-בלבד",
            "- בסדרת הנזק-בלבד severity_code = 3 והתווית \"קלה\" פירושם \"ללא נפגעים\" — לא \"פצועים קל\"",
            "- לכן כל שאלה על נפגעים, חומרה או הרוגים חייבת case_type_code = 1 (או את המבט v_casualty_accidents)",
            "# בדיקה",
            f"- {correct:,} + {dmg:,} = {correct + dmg:,} — הפער הוא בדיוק סדרת הנזק-בלבד",
            f"- {y}, עם נפגעים: {fatal:,} קטלניות · {severe:,} קשות · {slight:,} קלות = {fatal + severe + slight:,}"]
    if naive != correct + dmg:                       # never on this DB — printed, never hidden
        body.append(f"- הערה: הפער אינו מוסבר במלואו על-ידי סדרת הנזק-בלבד (הפרש {naive - correct - dmg:,})")
    caveats = [CAVEAT_DATA_END, "ספירת תאונות ≠ ספירת נפגעים (פצועים קל נספרים בטבלת involved)"]
    spec = make_spec("accidents/naive_vs_correct", basis=f"year={y} | three statements | accidents",
                     rows=[["naive", naive], ["correct", correct], ["damage_only_slight", dmg], ["ratio", ratio]], columns=["measure", "value"],
                     sql="\n\n".join(s.values()), denominator=denominator("na", "לא רלוונטי (השוואת שתי ספירות)"), caveats=caveats,
                     year=y, naive=naive, correct=correct, damage_only=dmg, ratio=ratio, breakdown=[[c, sv, n] for (c, sv), n in sorted(by.items())])
    return dispatch(view, spec, "המלכודת של התאונות הקלות", body=body)

ACTION = Action(
    name="naive_vs_correct", label="המלכודת · naive_vs_correct",
    help="Runs the naive 'light accidents' count (severity_label = 'קלה' alone — both series answer) and the correct one (the same statement + case_type_code = 1) for one year: both counts, the ratio, and why the damage-only series inflates it.",
    inputs={
        "year": Input(kind="number", label="שנה", default=2024, help="2005-2024"),
        "view": view_input("markdown", ["markdown", "sql"]),      # tooltip names markdown and sql only
    },
    run=run)   # defined after run: Action.run is a required field evaluated at import — a forward reference is a 'failed to import' Problem card
```
Live markdown 2024: `מכנה: לא רלוונטי (השוואת שתי ספירות)` / `# 50,145 לעומת 5,458` / … `**הפער** — פי 9.2: 44,687 …` / `- 5,458 + 44,687 = 50,145 — הפער הוא בדיוק סדרת הנזק-בלבד` / `- 2024, עם נפגעים: 405 קטלניות · 2,452 קשות · 5,458 קלות = 8,315` / `# הסתייגויות` bullets / last line CREDIT. `view=sql` → the three commented statements in one `<pre>`. The trap's spec (and its basis) never reaches a Result in P1 — markdown carries the body, sql carries `spec["sql"]` — so its basis is pinned at unit level (§3.3).

### 2.9 `actions/about.py`

Imports `from nl2sql_engine.modules import Action`; `ACTION` last.

```python
def _deployed(ctx) -> str:   # read-only look at the P4 registry pointer; nothing is written
    p = ctx.data_dir() / "accidents" / "models" / "site" / "deployed.json"
    if not p.exists(): return "אין"
    try: return str(json.loads(p.read_text("utf-8")).get("model_id", "?"))
    except Exception: return "לא ברור (deployed.json אינו קריא)"          # noqa: BLE001

@guard("אודות · מעבדת הבטיחות בדרכים")
def run(ctx):
    cols, rows = ctx.query(ABOUT_SQL); c = dict(zip(cols, rows_safe(rows)[0])); n_obj = len(ctx.tables())
    body = [f"# מעבדת הבטיחות בדרכים · nl2sql-accidents {version()}",
            "**חיבור** — מסד תאונות הדרכים של הלמ״ס זוהה (accidents.case_type_code)",
            f"**כיסוי** — {c['first_year']} עד {c['last_year']} · חודש אחרון בנתונים: {c['last_month']}/{c['last_year']} · הנתונים מסתיימים ב-{c['data_end']}",
            f"**תאונות** — {c['accidents_rows']:,} רשומות = {c['casualty_accidents']:,} עם נפגעים (case_type_code = 1) + {c['damage_only']:,} נזק-בלבד (case_type_code = 3)",
            f"**מעורבים** — {c['involved_rows']:,} ({c['casualty_involved']:,} בסדרת הנפגעים) · **כלי רכב** — {c['vehicles_rows']:,}",
            f"**אובייקטים בסכמה** — {n_obj} ({c['n_tables']} טבלאות + {c['n_views']} מבטים); הצ'אט רואה את כולם — בלי כללי הסדרה, המפתחות והמכנים",
            f"**מודל אתר פרוס** — {_deployed(ctx)}",
            "# כללי הזהב",
            "- שאלות על נפגעים, חומרה או הרוגים: תמיד case_type_code = 1",
            "- צירוף למעורבים ולכלי רכב: על המפתח (accident_id, case_type_code)",
            "- הרוגים (אנשים) ≠ תאונות קטלניות (אירועים)",
            "- ספירות אינן סיכון בלי מכנה חשיפה",
            "# רישיון",
            "- נתוני למ״ס באישור אישי: המסד לא מועבר, לא מועלה לענן ולא נשמר בגיט",
            "- כל פלט נושא את קרדיט הלמ״ס",
            "# פעולות", "- trend · naive_vs_correct · about"]
    return markdown_answer("אודות · מעבדת הבטיחות בדרכים", body, denom=DENOM_NA, caveats=[CAVEAT_DATA_END])

ACTION = Action(
    name="about", label="אודות · about",
    help="Connection probe (is this the CBS accidents database?), coverage and data end, row counts per series, schema object count, golden rules, license rules and the deployed site model (P4).",
    inputs={},          # Registry.run calls run(ctx) with no kwargs; Layer 0 still renders a Run button (Shapes' `tables` precedent)
    run=run)   # defined after run: Action.run is a required field evaluated at import
```
Refusal card on `acme_insurance` (any action; kind markdown, the action's own title, no CBS credit; note = `לא ניתן לענות · החיבור הנוכחי אינו מסד תאונות הדרכים של הלמ״ס · מעבדת הבטיחות בדרכים` — one line, no cut):
```
# ❌ לא ניתן לענות
החיבור הנוכחי אינו מסד תאונות הדרכים של הלמ״ס
- הסיבה: no table named accidents in this connection (29 tables: Agreement, Agreement_Assessment, Agreement_Party_Role, Assesment_Party_Role, Assessment, Assessment_Result, …)
- מה לעשות: בחרו את החיבור israel_accidents באפליקציה הראשית ופתחו את עמוד המודולים מחדש
- מה כן אפשר: EDA ו-Shapes פועלים על כל מסד נתונים
מעבדת הבטיחות בדרכים · פועלת רק על מסד תאונות הדרכים (למ״ס)
```
Data-limit card (`year=2030`; trend `to_year=2030`): `# ❌ לא ניתן לענות` / `אין נתונים לשנת 2030 — הנתונים מסתיימים ב-31.12.2024` / `- מה כן אפשר: כל שנה בין 2005 ל-2024` / lab line. Person mistakes → `Result.error` one-liners: `from_year must be a whole number; got 'abc'.`, `Unknown measure 'x'. One of: accidents, killed, severe_injured, slight_injured, fatal_accidents.` (dict order = dropdown order = PLAN_1 §4.1 order), `from_year (2024) is after to_year (2020) — swap them.` Unexpected exceptions → `Result.error("RuntimeError: boom\n\nTraceback …")`.

## 3. Tests

Run from the plugin repo: `..\app\.venv\Scripts\python -m pytest -q`. `tests/helpers.py`: `PNG_MAGIC`; `run(ctx, action, **inputs)` through `Registry()` (Shapes idiom); `png_of(spec)` (magic + > 2,000 bytes); `json_safe(r)` (`json.dumps(r.to_dict(), allow_nan=False, ensure_ascii=False)`); `installed = any(ep.name == "accidents" for ep in entry_points(group="nl2sql.modules"))` and `needs_install = pytest.mark.skipif(not installed, reason="pip install -e . first")` (shared by the entry-point/metadata/discovery tests). Every test file imports `MODULE` at collection, so an import-order slip in any action module errors the whole suite — the named `discover()` test in §3.5 is what makes it readable.

### 3.1 `conftest.py` — hand-planted fixture (no RNG, no CBS data)

```sql
CREATE TABLE accidents (accident_id BIGINT, case_type_code SMALLINT, year SMALLINT, month SMALLINT, accident_date DATE,
                        severity_code SMALLINT, severity_label VARCHAR, road_type_code SMALLINT, road_type_label VARCHAR);
CREATE TABLE involved  (accident_id BIGINT, person_id INTEGER, case_type_code SMALLINT, year SMALLINT, month SMALLINT,
                        injury_severity_code SMALLINT, injury_severity_label VARCHAR);
CREATE TABLE vehicles  (accident_id BIGINT, case_type_code SMALLINT, year SMALLINT, vehicle_num SMALLINT);
CREATE VIEW v_casualty_accidents AS SELECT * FROM accidents WHERE case_type_code = 1;
CREATE VIEW v_casualty_involved  AS SELECT * FROM involved  WHERE case_type_code = 1;
```
Labels: severity 1 `קטלנית` 2 `קשה` 3 `קלה`; road 1 `עירונית בצומת` 2 `עירונית לא בצומת` 3 `לא-עירונית בצומת` 4 `לא-עירונית לא בצומת` 5 `שטח`; injury 0 `לא נפגע` 1 `הרוג` 2 `פצוע קשה` 3 `פצוע קל`. `accident_date = date(year, month, 15)`.

Casualty accidents (case 1) and their involved rows (injury codes):

| id | year | m | sev | road | involved (case 1) |
|---|---|---|---|---|---|
| C1 2024000001 | 2024 | 1 | 1 | 1 | 1, 1, 3, 0 |
| C2 2024000002 | 2024 | 1 | 3 | 2 | 3, 0 |
| C3 2024000003 | 2024 | 2 | 2 | 3 | 2, 3 |
| C4 2024000004 | 2024 | 3 | 3 | 4 | 3 |
| C5 2024000005 | 2024 | 3 | 3 | 4 | 3, 0 |
| C6 2024000006 | 2024 | 5 | 3 | **5** (off-road, graft 20 — a guard for a code the live data never carries; it drives the "other code" wording of the road caveat) | 3 |
| C7 2023000001 | 2023 | 6 | 1 | 4 | 1, 0 |
| C8 2023000002 | 2023 | 7 | 3 | 1 | 3 |
| C9 2022000001 | 2022 | 12 | 2 | 2 | — (none) |
| C10 2022000002 | 2022 | 11 | 3 | 4 | 0 |

Damage-only (case 3, all `severity_code 3 / 'קלה'`): 2024 → ids 2024000001…2024000020 (**collide with C1–C6**), month `((i−1) % 12)+1`, road 2 for i ≤ 15 else 4; 2023 → 2023000001…004, month i, road 2; 2022 → 2022000001…005, month i, road 4 (29 rows). Damage-only involved (case 3): `(2024000001, 1, 3, 2024, 1, 1 'הרוג')` ← **the planted killed row in the wrong series (graft 20)**, `(2024000001, 2, 3, 2024, 1, 0)`, `(2024000002, 1, 3, 2024, 2, 0)`. Vehicles: `(2024000001,1,2024,1) (2024000001,1,2024,2) (2024000001,3,2024,1)`.

Fixtures: `ctx` (above) and `other_ctx` (`CREATE TABLE t (x INTEGER)`, 2 rows); both function-scoped: `nl2sql_engine.configure(data_dir=tmp_path)` → `yield Context(db_path=…)` → `configure(data_dir=None)` (`configure()` is process-global, so every fixture that sets it resets it in its own teardown — `test_live.py` follows the same shape, §3.7).

Planted truth: casualty accidents 10 (2022: 2 · 2023: 2 · 2024: 6), damage-only 29, accidents 39, involved 19 (16 casualty), vehicles 3, years 2022–2024, last month 12, data end 2024-12-15, objects 5 (3 tables + 2 views); rows with `road_type_code` outside 1–4: exactly one (C6, 2024).

### 3.2 `test_trend.py` — expected rows (`from_year=2022, to_year=2024` unless stated; no monkeypatch anywhere)

| measure | road | 2022 | 2023 | 2024 | proves |
|---|---|---|---|---|---|
| accidents | all / urban / nonurban | 2 / 1 / 1 | 2 / 1 / 1 | **6 / 2 / 3** | off-road counted by `all` only (6 ≠ 2+3) |
| fatal_accidents | all / urban / nonurban | 0/0/0 | 1/0/1 | 1/1/0 | |
| killed | all | **None** (people 1 < acc 2, covered False) | 1 | **2** | the coverage rule; the damage-only killed row is excluded (3 if the case filter is forgotten) |
| killed | urban | None (0 < 1) | 0 (covered) | **2** | composite key (an `accident_id`-only join gives 4) |
| killed | nonurban | 0 (1 ≥ 1, covered) | 1 | 0 | month/road-level coverage is per period |
| severe_injured | all | None | 0 | 1 | |
| slight_injured | all / urban / nonurban | None | 1 | **6 / 2 / 3** | |
| accidents, month, all, 2024 | | 12 rows: 01→2, 02→1, 03→2, 05→1, else 0 | | | zero-fill |
| killed, month, all, 2024 | | 01→2, else 0; all covered (empty month = 0 ≥ 0) | | | |
| killed, month, all, 2022 | | 11→0 covered (1 ≥ 1), 12→None (0 < 1) | | | |

Other trend tests: `columns == ["year","killed","people","casualty_accidents","covered"]` (person) / `["year","accidents"]` (accident); `spec["gap_periods"] == ["2022"]` and `spec["caveats"][0]` contains `2022: 1 רשומות מול 2 תאונות` (the gap line leads); `"2022" in r.note`; `view=sql` data contains `case_type_code = 1` and, for killed·urban, the `JOIN accidents a ON a.accident_id = i.accident_id AND a.case_type_code = i.case_type_code` line; **`test_sql_face_is_the_statement_that_ran`**: `rows_safe(ctx.query(spec["sql"])[1]) == spec["rows"]` (the gap None is computed in SQL, so equality is exact), `run(view="sql").data == spec["sql"]`, `run(view="table").data["rows"] == spec["rows"]`; coercion `from_year="2023"` / `2023.0` → chart with 2023/2024 rows; `from_year="abc"` → error naming `from_year`; `from_year=2024, to_year=2022` → error; `to_year=2030` and `from_year=2000` → markdown starting `# ❌` mentioning `2030`/`2000` and `2005 ל-2024`; `measure="bogus"` / `view="png"` → error listing the legal set (assert on the **set** of names, not their order); COVID caveat present for 2005–2024, absent for 2022–2024; road caveat only when road_type ≠ all — urban 2022–2024 → contains `1 תאונות עם קוד דרך אחר` (C6 is in range), urban 2022–2023 → contains `סכום שניהם`; `all(";" not in c for c in spec["caveats"])` on every run; **`test_six_caveats_keep_the_gap_first`** (the 6-caveat case without live data — 2020–21 zero-filled and covered, 2022 gap, COVID fires): `_caveats("killed", "urban", 2020, 2024, [("2022", 0, 1)])` → 6 entries, gap at index 0 (< `PNG_CAVEAT_CAP`); `run(ctx, "trend", measure="killed", road_type="urban", from_year=2020, to_year=2024, view="chart")` → `len(spec["caveats"]) == 6`, `spec["caveats"][0].startswith("נתוני נפגעים")` and contains `2022: 0 רשומות מול 1 תאונות`, `spec["caveats"][1] == CAVEAT_DATA_END`, PNG valid (NOT 2022–2024 — that yields 5 and passes without the fix); **`test_basis_and_stamp_are_ascii`**: chart 2022–2024 → `spec["basis"] == "killed by year | road_type=all | 2022-2024 | 3 rows | involved WHERE case_type_code = 1"`, `spec["stamp"] == f"nl2sql-accidents {__version__} | killed / year / all | 2022-2024"`, both `.isascii()`; `other_ctx` → refusal card (title `מגמה`, last line `LAB_LINE`, `CREDIT` absent, `"no table named accidents"` in data, `"\n" not in r.note`).

### 3.3 `test_trap.py`

2024 → markdown; `"# 24 לעומת 4"` (4 casualty slight + 20 damage-only), `"20"`, `"פי 6.0"`, `"- 4 + 20 = 24"`, `"1 קטלניות · 1 קשות · 4 קלות = 6"`, `"case_type_code = 1"`, last line CREDIT, first line starts `מכנה:`; 2023 → `5 לעומת 1`, `פי 5.0`; 2022 → `6 לעומת 1`; `view="sql"` → kind sql, `data == "\n\n".join(trap_statements(2024).values())`, contains `-- 1. naive`, `-- 2. correct`, `-- 3. breakdown`, `severity_label = 'קלה'` twice (statements 1 and 2 only). **The correct statement is the naive one plus exactly one line** — asserted comment-insensitively, never as a bare literal count (the literal `case_type_code = 1` is 2 on statement 2 because the code-canon comment is kept on purpose): `s = trap_statements(2024); body = lambda sql: "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))`; `body(s["correct"]) == body(s["naive"]) + "\n  AND case_type_code = 1"`; `s["naive"].count("case_type_code = 1") == 0`; on the sql face: `data.count("\n  AND case_type_code = 1") == 1` (the predicate line once — only statement 2 can carry it), `"code canon equivalent: case_type_code = 1 AND severity_code = 3" in data` (the graft-9 comment survives — the (9)-vs-(19) resolution is asserted, not tolerated), `data.split("-- 2. correct")[0].count("case_type_code = 1") == 0` (the naive statement stays unfiltered). Consistency: `ctx.query(trap_statements(2024)["naive"])[1] == [(24,)]`; `year="2024"` works; `year=2030` → `# ❌` card with `31.12.2024`; `year="x"` → error; `other_ctx` → refusal with `"\n" not in r.note`; no mismatch line present (`"הערה:" not in data`). **`test_basis_is_ascii`** (the trap spec never reaches a Result): `monkeypatch.setattr(trap, "make_spec", <recording wrapper around the real make_spec>)`, run `naive_vs_correct` 2024 → recorded `spec["basis"] == "year=2024 | three statements | accidents"` and `.isascii()`.

### 3.4 `test_about.py`

Contains `39 רשומות = 10 עם נפגעים` … `+ 29 נזק-בלבד`, `**מעורבים** — 19 (16 בסדרת הנפגעים)`, `**כלי רכב** — 3`, `2022 עד 2024`, `12/2024`, `2024-12-15`, `5 (3 טבלאות + 2 מבטים)`, `**מודל אתר פרוס** — אין`, `0.1.0`; last line CREDIT; note == `מכנה: לא רלוונטי · הסתייגות: הנתונים מסתיימים ב-31.12.2024 · מקור: הלשכה המרכזית לסטטיסטיקה`; `json_safe`. **`test_about_sees_a_deployment`**: write `tmp_path/accidents/models/site/deployed.json` = `{"model_id": "site-x"}` → `**מודל אתר פרוס** — site-x` (proves the data-dir sandbox + P4 forward-compat). `other_ctx` → refusal (title `אודות · מעבדת הבטיחות בדרכים`, `"Traceback" not in data`, `"no table named accidents" in r.data`, `"1 table:" in r.data` (singular), `"\n" not in r.note`). **`test_guard_turns_crashes_into_error_results`**: `monkeypatch.setattr(about, "_deployed", lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")))` → kind error, `"RuntimeError: boom"` and `"Traceback"` in data. **`test_p1_writes_nothing_under_data_dir`**: after running all three actions, files under `tmp_path` == the fixture db only.

### 3.5 `test_contract.py`

Declarations (no DB): `MODULE.name == "accidents"`, label starts `🚦`, `requires_core == ">=1.0,<2.0"`, action names `== {"trend","naive_vs_correct","about"}`, action labels `מגמות · trend` / `המלכודת · naive_vs_correct` / `אודות · about`; every input kind legal, `default is not None`, choice default ∈ choices, number defaults are ints, no input label contains a digit; `trend.view.choices == ["chart","table","sql"]`, `naive_vs_correct.view.choices == ["markdown","sql"]` and its help mentions neither `chart` nor `table`, `about.inputs == {}`; `list(trend.inputs["measure"].choices) == ["accidents","killed","severe_injured","slight_injured","fatal_accidents"]` (PLAN_1 order); every `action.help` is non-empty and ASCII-only prose (visible Layer-0 text). **`test_version_pinned`** (no install needed): `tomllib.load((Path(__file__).resolve().parents[1] / "pyproject.toml").open("rb"))["project"]["version"] == __version__ == "0.1.0"`. **`test_installed_version_matches`** (`@needs_install`): `importlib.metadata.version("nl2sql-accidents") == __version__`. **`test_entry_point_resolves`** (`@needs_install`): `[ep for ep in entry_points(group="nl2sql.modules") if ep.name == "accidents"][0].load() is MODULE`. **`test_discovery_offers_accidents_without_problems`** (`@needs_install` — mirrors `adapters.module_run`'s exact path, `discover()` → `reg.get`):
```python
from nl2sql_engine.modules import discover
reg = discover()
assert not [p for p in reg.problems if p.name == "accidents"], reg.problems
assert reg.get("accidents") is MODULE
```
With `ctx`: every declared view → its kind (trend chart/table/sql; trap markdown/sql; about markdown); every result `json_safe`; **`"\n" not in r.note`** for every action × view result (and for every `other_ctx` refusal); every non-error note starts with `מכנה:` or `לא ניתן לענות` and ends with `CREDIT_SHORT` or `מעבדת הבטיחות בדרכים`; chart spec keys ⊇ `{type, renderer, png_base64, basis, rows, columns, sql, denominator, caveats, credit, plugin_version, stamp}`, `denominator["kind"] in DENOM_KINDS`, `credit == CREDIT`, `plugin_version == __version__`; **`spec["basis"].isascii() and spec["stamp"].isascii()`** for every chart result (trend view=chart × 5 measures; trap's basis is covered at unit level in §3.3, about has none). Markdown discipline, split by fixture: **answer markdowns** (`ctx`, declared views: trap markdown, about) → `lines[0].startswith("מכנה:") and lines[-1] == CREDIT`; **refusal markdowns** (`other_ctx` for all three actions; trend `to_year=2030`; trap `year=2030`) → `lines[0] == REFUSAL_HEADING and lines[-1] == LAB_LINE and CREDIT not in data`. Layer-0 discipline on every markdown: no line starts with `##`, no `|`, no "```", no `](`; `Result.title` has no ASCII digit. **`test_no_result_outside_envelope`**: tokenize every `.py` under `nl2sql_accidents/`; NAME `Result` followed by OP `(` or `.` (STRING/COMMENT tokens ignored, so docstrings and comments may mention Result; `-> Result` annotations and imports are not constructions) occurs only in `envelope.py`, and does occur there:
```python
def test_no_result_outside_envelope():
    """Only envelope.py may construct a Result — `Result(...)` or `Result.<factory>(...)`.
    Scanned as Python tokens, so docstrings and comments are exempt and free to mention Result;
    `-> Result` annotations and `import Result` are not constructions and are allowed anywhere."""
    import io, tokenize
    from pathlib import Path
    import nl2sql_accidents
    pkg = Path(nl2sql_accidents.__file__).parent
    offenders = {}
    for py in sorted(pkg.rglob("*.py")):                       # rglob covers actions/
        toks = [t for t in tokenize.generate_tokens(io.StringIO(py.read_text(encoding="utf-8")).readline)
                if t.type in (tokenize.NAME, tokenize.OP)]    # drops STRING, COMMENT, NEWLINE/NL, INDENT/DEDENT
        hits = [a.start[0] for a, b in zip(toks, toks[1:])
                if a.type == tokenize.NAME and a.string == "Result"
                and b.type == tokenize.OP and b.string in ("(", ".")]
        if hits:
            offenders[py.relative_to(pkg).as_posix()] = hits
    assert set(offenders) == {"envelope.py"}, offenders     # == (not <=) so the test cannot pass vacuously
```
**`test_png_is_thread_safe`**: `ThreadPoolExecutor(4)` × trend chart (5 measures) → all valid PNGs.

### 3.6 `test_sqlkit.py`, `test_envelope.py`, `test_charts.py`

- sqlkit: `as_int("2024") == 2024`, `as_int(2024.0) == 2024`, `as_int("abc")`/`as_int(True)`/`as_int(2023.5)` → ActionError naming the input; `year_in_coverage(2030)` → Refusal with `2030` and `31.12.2024`, `(2000)` → Refusal with `2005`; `year_range(2024, 2005)` → ActionError; `as_choice("x","measure",MEASURES)` message lists the five names (assert on the set); `Refusal("r", detail="d").detail == "d"`; `ilit(7) == "7"`, `ilit(True)` raises, `slit("a'b") == "'a''b'"`, `lit(inf)` raises; `scalar(Decimal("1.5")) == 1.5`, `scalar(nan) is None`, `scalar(date(2024,12,31)) == "2024-12-31"`, bool kept; `byar_ci(10) ≈ (4.79, 18.39)` ±0.01, `byar_ci(100) ≈ (81.36, 121.63)`, `byar_ci(0) == (0.0, ≈3.67)`; `build_trend_sql` for all 30 combinations: contains `case_type_code = 1`, the composite-key join iff (person measure and road filter), never `accident_id = i.accident_id` without `case_type_code`, coverage CTE iff person measure, first line `.isascii()`; `other_road_sql(2022, 2024)` contains `NOT IN (1, 2, 3, 4)` and `case_type_code = 1`, and on the fixture returns 1.
- envelope: `note_line(DENOM_COUNTS, ["a","b"]) == "מכנה: ספירות בלבד — ללא מכנה חשיפה · הסתייגות: a; b · מקור: הלשכה המרכזית לסטטיסטיקה"`; `note_line(DENOM_NA, [])` ends `הסתייגות: אין · …`; `denominator("bogus", "x")` raises; `dispatch("xml", …)` → ActionError listing the views; `refusal("x", title="t")` starts with `REFUSAL_HEADING`, last line `LAB_LINE`; `r = refusal("x\ny", title="t", detail="d")` → `"\n" not in r.note`, `"- הסיבה: d" in r.data`, `r.note.startswith("לא ניתן לענות · x ·")`; `make_spec(...)["plugin_version"] == version()`; `stamp_line("killed","year","all",2005,2024) == f"nl2sql-accidents {version()} | killed / year / all | 2005-2024"` and `.isascii()`; `view_input("markdown", ["markdown","sql"]).help == "markdown = the explanation card; sql = the exact statement run"`.
- charts: `heb("abc") == "abc"`; `heb("שלום") != "שלום"` (bidi present); `_mirror("5,458 תאונות") == "תונואת 5,458"`; **`test_label_falls_back_to_reverse`**: `monkeypatch.setitem(sys.modules, "bidi", None)` + `"bidi.algorithm"` → `heb("שלום") == "םולש"` and `heb("5,458 תאונות") == "תונואת 5,458"` (the fallback path itself through `heb()`); `png(lambda f, a: None, title="כותרת", badge="x", caveats=["a"]*7, stamp="s")` → PNG magic (7 > `PNG_CAVEAT_CAP`: the overflow-marker branch); `line_chart(["2023","2024"], [1, 2], ylabel="x", gaps=[], monthly=False, title="t", badge="b", caveats=[], stamp="s")` → PNG magic (a direct render, so a missing `FuncFormatter` import fails here with a readable location instead of inside the contract sweep); `line_chart` with an all-None series renders; geometry via the pitch rule: `caveat_ys(5) == approx([0.245, 0.211, 0.177, 0.143, 0.109])`, `caveat_ys(6)[-1] == approx(0.090)`, `caveat_ys(7)[-1] == approx(0.090)`, `min(caveat_ys(7)) >= 0.090` (every caveat line stays above the credit).

### 3.7 `test_live.py`

```python
LIVE = Path(r"C:\data\israel_accidents\israel_accidents.duckdb")
pytestmark = pytest.mark.skipif(not LIVE.exists(), reason="live CBS working copy absent")
@pytest.fixture()                      # FUNCTION-scoped, same yield/reset shape as ctx: configure() is process-global, and a
def live(tmp_path):                    # module-scoped fixture would be silently re-pointed at %LOCALAPPDATA%\nl2sql-core by any
    nl2sql_engine.configure(data_dir=tmp_path)    # other fixture's teardown (P4's seeded registry would then leak into `about`)
    yield Context(db_path=str(LIVE))
    nl2sql_engine.configure(data_dir=None)
```
`test_live.py` uses only `live` (never `ctx`/`other_ctx`); the DuckDB connection is cached per db_path, so per-test scope costs nothing. Assertions: killed/year/all 2005–2024 → 20 rows, 2005 = 476, **2009 = None with people 15 / casualty_accidents 16,856 / covered False**, `gap_periods == ["2009"]`, `caveats[0]` contains `"15 רשומות מול 16,856 תאונות"` and `"2009"` in the note, 2023 = 361, **2024 = 439**, `basis == "killed by year | road_type=all | 2005-2024 | 20 rows | involved WHERE case_type_code = 1"`, `stamp == f"nl2sql-accidents {__version__} | killed / year / all | 2005-2024"`; killed/year/urban 2005–2024 → 6 caveats, `caveats[0]` contains `9 רשומות מול 12,091 תאונות`, `gap_periods == ["2009"]`, the road caveat is the `סכום שניהם` wording (no other road code on live); killed/year/nonurban → `caveats[0]` contains `6 רשומות מול 4,765 תאונות`; killed/month/urban 2005–2024 → 240 rows, exactly 12 uncovered (all 2009), `caveats[0]` contains `12 תקופות` and `(9 רשומות מול 12,091 תאונות)`; accidents/year/all → 2005 17,509, **2024 8,315**, no gaps; 2024: fatal_accidents 405, severe 2,808, slight 11,203, accidents urban 5,447 / nonurban 2,868, killed urban 150 / nonurban 289, severe urban 1,624, fatal nonurban 256; **killed · urban · 2005 = 180** (pins the composite key on live — a single-key join gives 373); accidents/month/all 2024 → 12 rows, Σ 8,315; fatal_accidents/month/nonurban 2024 Σ 256; trap 2024 → `50,145`, `5,458`, `44,687`, `פי 9.2`, `405 קטלניות · 2,452 קשות · 5,458 קלות = 8,315`, no `הערה:`; about → `1,290,788`, `270,723`, `1,020,065`, `2,987,206 (684,051`, `2,297,533`, `43 (31 טבלאות + 12 מבטים)`, `2005 עד 2024`, `12/2024`, `2024-12-31`, `**מודל אתר פרוס** — אין` (the sandboxed data dir, not the shared one); every result carries CREDIT_SHORT in the note / CREDIT in chart specs and markdown, and no note contains a newline. **Timing**: no bound on the first chart (cold matplotlib font cache ≈ 90 s); the second chart render < 15 s; SQL-only actions < 5 s.

Red→green slice order: (0) `app\.venv\Scripts\python -m pip install -e "nl2sql-accidents-plugin[dev]"` first — the entry point, the dist metadata and `discover()` exist only after it (the three `@needs_install` tests skip, never error, before it) → (1) pyproject + `__init__` stub + `test_contract` declarations (red) → (2) conftest/helpers + `test_sqlkit` + `test_envelope` → sqlkit, envelope (green) → (3) `test_charts` → charts → (4) `test_trend` → dbcheck, trend → (5) `test_trap` → trap → (6) `test_about` → about → (7) `test_live` → (8) restart / Modules page / docs / commit / tag.

## 4. Install & acceptance (PowerShell, from `accidents-lab\`)

```powershell
# 0. pre-flight
git -C app status --short                                                        # empty
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | % { (Get-Process -Id $_.OwningProcess).Path }

# 1. editable install + dev extras, entry point, suite
app\.venv\Scripts\python -m pip install -e "nl2sql-accidents-plugin[dev]"
app\.venv\Scripts\python -c "from importlib.metadata import entry_points as e; print(sorted(x.name for x in e(group='nl2sql.modules')))"   # ['accidents','eda','shapes']
cd nl2sql-accidents-plugin; ..\app\.venv\Scripts\python -m pytest -q; cd ..    # green; first live PNG may take ~90 s (font cache)

# 2. wheel sanity — the editable install hides a packages= omission until P3
cd nl2sql-accidents-plugin
..\app\.venv\Scripts\python -m build --wheel
..\app\.venv\Scripts\python -c "import zipfile,glob; n=zipfile.ZipFile(glob.glob('dist/nl2sql_accidents-0.1.0-*.whl')[0]).namelist(); a=[x for x in n if x.startswith('nl2sql_accidents/actions/') and x.endswith('.py')]; print(a); assert len(a)==4"
cd ..                                                                            # dist/ is gitignored

# 3. restart the app (modules discover per request, but the running interpreter cannot see the new editable finder — PITFALLS 3)
Get-CimInstance Win32_Process -Filter "name like 'python%'" | ? { $_.CommandLine -like '*accidents-lab*' -and $_.CommandLine -like '*uvicorn*' } | % { Stop-Process -Id $_.ProcessId -Force }
$env:PYTHONUTF8 = "1"                                                            # exactly what app\run.ps1 sets before uvicorn (Start-Process inherits it); without it the console encoding is cp1255
Start-Process -WorkingDirectory app app\.venv\Scripts\python.exe -ArgumentList "-m","uvicorn","api.main:app","--port","8000"
$ok = $false; foreach ($i in 1..40) { try { Invoke-RestMethod http://127.0.0.1:8000/api/health | Out-Null; $ok = $true; break } catch { Start-Sleep 1 } }; if (-not $ok) { throw 'app did not come up' }
$m = Invoke-RestMethod http://127.0.0.1:8000/api/modules; $m | ConvertTo-Json -Depth 6           # accidents with 3 actions
if ($m.problems.Count) { throw "problems: $($m.problems | ConvertTo-Json)" }                       # problems: [] — an import-order slip shows here as 'failed to import: NameError'

# 4. headless runs through the page's own route (adapters.module_run)
function Run($action, $inputs, $db = "israel_accidents") {
  $body = @{module="accidents"; action=$action; db=$db; inputs=$inputs} | ConvertTo-Json -Depth 4
  Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/modules/run -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body))
}
$r = Run "trend" @{}; $r.kind; $r.title; $r.note; $r.data.basis; $r.data.stamp; $r.data.plugin_version   # chart · Hebrew title · one-line note starting מכנה: · ASCII basis/stamp
[IO.File]::WriteAllBytes("c:\tmp\p1_trend_killed.png", [Convert]::FromBase64String($r.data.png_base64))   # eyeball: title/badge/5 caveats (gap line first)/credit/stamp, 2009 band, white bg
$u = Run "trend" @{road_type="urban"}; $u.data.caveats.Count; $u.data.caveats[0]                   # 6 · '… 9 רשומות מול 12,091 תאונות …'
[IO.File]::WriteAllBytes("c:\tmp\p1_trend_killed_urban.png", [Convert]::FromBase64String($u.data.png_base64))   # eyeball: six caveat lines, gap first, credit clear (the default PNG has only five and cannot show a cap defect)
(Run "trend" @{granularity="month"; road_type="urban"; from_year=2024; to_year=2024; view="table"}).data.rows.Count   # 12
(Run "trend" @{from_year="2023"; to_year="2024"; view="sql"}).kind                                 # sql (string numbers coerced)
(Run "trend" @{from_year="abc"}).data                                                              # error naming from_year
(Run "trend" @{to_year=2030}).data                                                                 # ❌ card: אין נתונים לשנת 2030
(Run "naive_vs_correct" @{year=2024}).data                                                         # 50,145 לעומת 5,458 + check lines
(Run "naive_vs_correct" @{year="2024"; view="sql"}).data                                           # three statements
(Run "about" @{}).data                                                                             # 43 (31 טבלאות + 12 מבטים), credit last
$x = Run "about" @{} "acme_insurance"; $x.data; $x.note                                            # ❌ card '(29 tables: Agreement, Agreement_Assessment, …)', lab-line footer; note is ONE line with no cut
# 5. browser: http://127.0.0.1:8000 → 🧩 Modules → 🚦 מעבדת הבטיחות בדרכים → run all three (each view); switch the main Connection to
#    acme_insurance and reopen the Modules page → ❌ card. This manual run + step 4's API runs + the saved PNGs are the evidence for
#    "three actions render with note + credit in the PNG". Optional frame capture — sidebar/collapsed-cards check ONLY (the page
#    builds each form on the first <details> toggle and results only after Run, so a headless screenshot shows three collapsed cards):
#    msedge --headless=new --user-data-dir=c:\tmp\edge-p1 --screenshot=c:\tmp\p1_modules.png --window-size=1400,1800 "http://127.0.0.1:8000/modules-page/?db=israel_accidents"
# 6. docs (see §5), then commit from a clean tree and tag
git -C app status --short                                                        # still empty
git -C nl2sql-accidents-plugin add -A
git -C nl2sql-accidents-plugin commit -m "[P1] skeleton + answer envelope: trend, naive_vs_correct, about"
git -C nl2sql-accidents-plugin tag v0.1
```
Acceptance checklist: three actions render on the clone's Modules page with note + credit in the PNG (`/api/modules` `problems` empty); suite green from the plugin repo with `..\app\.venv` (live tests run on this machine); wheel lists `nl2sql_accidents/actions/*.py`; `about` refuses on `acme_insurance` with a one-line note; `git -C app status` clean; `[P1]` commit + `v0.1`; data-dir state: shared default, nothing written under it (asserted by `test_p1_writes_nothing_under_data_dir`).

## 5. Docs updated in the same phase

- `docs/plan.md`: Progress row P1 → done + date + `v0.1`; deviations recorded: explicit `packages` list includes the subpackage; four denominator kinds; refusal heading single `#`; refusal footer = lab line (no CBS credit on non-CBS output); Hebrew no-digit `Result.title`; correct trap statement = naive + one line (code canon in a comment); `basis`/`stamp` strict ASCII with `|`/`-`; caveats most-specific-first (data gap leads); road caveat data-driven; `ACTION` declared last in every action module.
- `PITFALLS.md` (written now — the stumble happened during P1 planning verification, 2026-08-28/29): **The 2009 casualty-series `involved` rows are missing (15 rows vs 16,856 casualty accidents)** · What happened: killed 2009 = 0 rows (the 15 rows: 3 uninjured, 1 severe, 11 slight) while accidents 2009 = 16,856 casualty / 308 fatal — a naive chart draws a plausible zero · Root cause: the 2009 ת״ד 104 (casualty) persons file is effectively absent from the build; the 2009 ת״ד 116 (damage-only) persons file (139,368 rows), the 2009 vehicles files (both series: 31,199 / 106,651) and both accident series (16,856 / 61,391) are complete — so `count(*) FROM involved WHERE year = 2009` (139,383) hides the gap; it shows only under `case_type_code = 1`, and a single-key join would attach 11,848 damage-only person rows to 2009 casualty accidents (ID reuse 2005–2009) · What the real build should do: never a magic threshold — derive coverage from the accident spine per period with the series filter AND the composite key (`people >= casualty_accidents`) inside the statement, NULL not 0, caveat with both counts, band in the PNG; participants should assert one early year on live. Plus entries as they happen (packages= omission; cold font cache; bidi surprises on Layer 0).
- `..\context\DOSSIER_TASK4_ACCIDENTS_DB.md` §5.4 bullet + §9 entry (workspace level, not `app\`): "involved 2009: the casualty series (case_type_code = 1) holds 15 rows (3 uninjured, 1 severe, 11 slight; killed 2009 = 0) vs 16,856 casualty accidents — person-level measures for 2009 are missing; the damage-only series 2009 (139,368 rows), vehicles 2009 (both series) and accidents 2009 (16,856 casualty / 308 fatal) are complete; the plugin flags the year as uncovered (NULL, never 0)." Also §5.5/§6: `road_type_code` 5 (off-road) does not occur in this build — codes 1–4 only, both series.
- `README.md`: status → P1; the three actions; "restart after install — the symptom of forgetting is a Problem card"; "restart exactly as `run.ps1` does (`$env:PYTHONUTF8 = "1"` before uvicorn)".
- `CLAUDE.md` (plugin): envelope facts (denominator kinds, exact note format, `#`-only markdown, the coverage rule, Layer-0 string discipline incl. **`spec.basis` and the PNG stamp strict ASCII (`|`/`-`), asserted `.isascii()`; `·`/`–` only in Hebrew-facing text; the note is one line; no `;` inside a caveat**, `guard(title)` folds the DB probe, `ACTION` last in every action module); the restart line gains `$env:PYTHONUTF8 = "1";` before `Start-Process`.

## 6. Risks / pitfall watch

- **Graft conflicts resolved**: (8) vs (18) → Hebrew no-digit titles (the `<h3>` is the first thing the audience reads; an all-Hebrew run renders correctly left-aligned; `basis` stays ASCII). (9) vs (19) → label-based correct statement + one added line, code canon named in the SQL comment and shown by the breakdown statement. Both noted in `docs/plan.md`.
- **Review-sweep conflicts resolved** (each pair proposed valid but mutually exclusive fixes; one applied everywhere, never mixed): basis/stamp → **strict ASCII** (`|`, `-`; `.isascii()` in tests) rather than "Hebrew-free with `·`/`–`" — the rule was already stated three times, the assertion is a one-liner, and the stamp is drawn un-shaped in a monospace font; caveat order → **data gap first** (most specific first, so it opens the note and survives any PNG cap) rather than second; `Result`-construction test → **token scan of `Result(` / `Result.` construction sites** (docstrings/comments/annotations/imports exempt) rather than any NAME token; trap test → **targeted predicate-line assertions with the code-canon comment kept** rather than rewording the comment.
- **Import-time NameError in an action module** (ACTION referencing `run` before its def) → whole package fails to import → Problem card `failed to import: NameError…` and "no module named 'accidents' is available" on the run route; caught by `test_discovery_offers_accidents_without_problems` and by the whole suite erroring at collection. Fix is ordering only — no lambda/late-binding shim.
- **Subpackage not shipped**: explicit `packages` list must name `nl2sql_accidents.actions`; caught by the wheel listing (step 2) and `test_entry_point_resolves`.
- **Coverage rule false positives**: cannot fire on complete data (every casualty accident has ≥ 1 involved row); verified live — only 2009 fires at year, month and road-group level (urban 12,091 vs 9; nonurban 4,765 vs 6). Empty fixture months are covered (0 ≥ 0) and show a real 0. The gap is invisible outside the casualty series (involved 2009 = 139,383 rows in total) — the rule lives inside `case_type_code = 1` on the composite key.
- **Composite key**: invisible on 2024 (150 either way), fans out 2005–2008 (and 2009: 11,848 damage-only person rows would attach to casualty accidents) — the live test pins urban killed 2005 = 180 and the fixture's colliding ids pin 2 vs 4.
- **PNG caveat block**: cap 6 = P1's maximum, so nothing P1 emits is truncated; the block self-compresses (`caveat_ys`) so the last line clears the credit even with the overflow marker; the gap line is at index 0 by construction. Geometry unit-tested; the urban PNG is eyeballed in acceptance because the default PNG has only five lines.
- **Road caveat is data-driven**: live has `road_type_code` 1–4 only, so live always gets the "כל הדרכים = סכום שניהם" wording; the fixture's C6 row exercises the "other code counts in all only" wording. Costs one cheap count per non-`all` run (not part of `spec.sql`, which stays the exact trend statement).
- **Refusal note**: `Refusal.reason` is one sentence, `detail` (English, may be long) goes to the body bullet only; the note is built from `reason.splitlines()[0][:80]` — today's reasons are 45 and ~52 chars, so the cut never fires; `"\n" not in r.note` is asserted on every result.
- **Threaded route + matplotlib**: `Figure` + `FigureCanvasAgg` only, no pyplot; `FuncFormatter` imported lazily from `matplotlib.ticker` inside `line_chart` (with pyplot excluded there is no `plt.FuncFormatter` to lean on); 4-thread test. Cold font cache ≈ 90 s on the first PNG after restart — no first-render timing bound; warm-up belongs in the demo pre-flight.
- **adapters discards tracebacks**: `guard` returns them inside `Result.error`; tested with the monkeypatched crash.
- **Coercion / validation**: the server does none; `as_int`/`as_choice` accept JSON numbers, floats and strings, refuse the rest by name; `0` and `False` survive `Registry.run`'s `in (None, "")` check; MEASURES dict order = dropdown order = error-text order = PLAN_1 §4.1 order, and tests assert on the set.
- **JSON safety**: `rows_safe` on every row, `data_end` cast in SQL, `allow_nan=False` asserted on every action × view; `None` gaps are legal JSON.
- **Guardrail**: every statement is a single `WITH`/`SELECT`, comments and the Hebrew literal `'קלה'` accepted (verified through `Context.query`); never a trailing `;`.
- **Layer-0 bidi**: notes mix Hebrew and digits in a left-aligned `<p>` — readable, not pretty; the PNG is the canonical face; P3 renders RTL. Titles carry no digits; `basis`/stamp are ASCII so the two un-shaped lines are unambiguous.
- **`configure()` is process-global**: every fixture that sets `data_dir` (incl. `live`) is function-scoped and resets to `None` in its own teardown; a module-scoped `live` would be silently re-pointed at the shared `%LOCALAPPDATA%\nl2sql-core` by another fixture's teardown (and from P4 on, `about` would show the seeded model id and a "writes nothing" assertion would touch the shared dir).
- **Environment parity**: the manual restart sets `PYTHONUTF8=1` exactly as `run.ps1` does — the one difference between the plan's server and the participants' server is thereby removed (a plain `print('≠')` from `app\.venv` without it raises `UnicodeEncodeError` on cp1255).
- **`ctx.columns()` on a foreign DB** may raise — `dbcheck.check` wraps everything and checks `ctx.tables()` first.
- **License**: synthetic fixture only; nothing under `C:\data` referenced except the skip-guard path; credit on every PNG/note/markdown/spec; refusal cards carry the lab line instead (not CBS output).
- **Byar CI** ships unused by P1 actions; unit-tested now so P2 `segment_rates` inherits a verified helper.
- Ultracode (optional): adversarial pass over the 30 `build_trend_sql` outputs against dossier §5 (series filter present, composite key on every join, coverage CTE on every person measure, no `accident_id`-only join).