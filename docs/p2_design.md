The Write tool is not available in this read-only session, so the plan is delivered here in full (the parent should save it as `docs/p2_design.md` when approved).

# P2 — Analytical tier · implementation plan (nl2sql-accidents 0.2.0)

**Scope:** `docs/plan.md` §P2 — six actions (`segment_rates`, `severity_profile`, `vehicle_cells_ranking`, `before_after`, `weather_check`, `triage`), `tools/find_demo_site.py` → `docs/demo/sites.md`, fixture + tests, docs/PITFALLS, `[P2]` commit, tag `v0.2`. No map, no page, no studio. Data-dir state: shared default (P2 writes nothing).

**Verified for this plan (read-only, 2026-08-29):** every statement below was run through DuckDB on the live copy (`C:\data\israel_accidents\israel_accidents.duckdb`, `read_only=True`; each ≤ 0.1 s) and every fixture number was reproduced on an in-memory DuckDB built from the planted rows in §5. Live facts used: units 6,233 / 8,100 raw / 1,311 segments; coverage 19,865 / 28,213 (70.4 %, 53.7 % → 81.2 %, dip 72.1 % in 2023 — re-pinned 2026-08-30 after the sweep's `road_km = 0` rule; the plan's original figure was 20,185 = 71.5 %); road 60 seg 836 = `road:60/96.0-98.8` (49→6 casualty, 22→23 damage-only; network 38,867→36,102 / 143,423→120,421 for 2014–16 vs 2018–20); road 2 seg 20 = `road:2/21.9-24.0`; vehicle cells 68 included / 13 excluded (465,636 vehicles = 17.0 % of 2,733,087), global 0.19299 / 0.03362 / 0.00456 per Mkm, `ntile(5)` tiers 14 / 41 / 13; weather 56.8 / 3.7 / 7.8 reproduced, 67.0 at threshold 0; years without any weather cell 2005–2007 (51,772 accidents), then 807 of 218,951 (0.4 %) without a cell; profile total 482,347 casualties with 2009 excluded by the coverage rule; 489 pedestrians carry a vehicle code (the `casualty_type_code = 1` mapping makes both dimensions agree at 58,985).

**Deviations from PLAN_1 §4.1 decided here (recorded in `docs/plan.md` at acceptance):**
- `segment_rates`: `order_by` input (`rate_lo` default = the Byar lower bound, `rate`, `count`) — the raw-rate top-10 on live is all 0.5–1 km segments with 2–11 accidents (rate 100–160, CI 18–578); years outside 2017–2024 refuse (exposure layer bounds); the CI is computed in SQL (`byar_sql`) so the SQL face is the full recipe; per-year coverage from a second statement (`spec.coverage_sql`).
- `severity_profile`: a seventh dimension `sex`; the 2009-style coverage rule applied per year (uncovered years dropped and named).
- `vehicle_cells_ranking`: `min_exposure_mkm` dropped (the report has no rule; EB is the substitute) → `bands` choice (`all` / `known_engine`) instead; tiers by `ntile(5)`.
- `before_after`: `change_year` (number) instead of `change_date` (annual windows make the date a year); `control` input dropped (network only, the report's definition); `min_cell` input (default 6); SE of the double ratio = √(SE²_cas + SE²_dmg), labelled a plugin extension; data-driven control flag (coding share > 25 % relative).
- `weather_check`: `rain_threshold_mm` is a **choice** of strings (`"0.1"`, `"0"`, `"0.5"`, `"1"`) — number inputs must keep int defaults (contract test) and `as_int` refuses 0.1.
- `triage`: no LLM, three card shapes (refusal / route / answer); no `view` input.
- Version 0.2.0 (`pyproject.toml`, `__init__.py`, `test_version_pinned`).

---

## 1. Shared additions (P1 code untouched; additions only)

### 1.1 `nl2sql_accidents/sqlkit.py`

```python
EXPOSURE_YEARS = (2017, 2024)        # traffic_adt_asof holds 2017-2024 only (live-asserted)
EB_M_MKM = 200.0                     # the report's prior weight
MIN_CELL_DEFAULT = 6                 # plugin thinness rule (adapted from the report's change-detector threshold)
CONTROL_FLAG_REL = 0.25              # coded-share relative change that flags the control

def as_float(v, name) -> float          # like as_int, accepts int/float/numeric str, refuses bool/NaN/inf/text
def exposure_year_range(from_year, to_year) -> tuple[int, int]
    # as_int both, from > to -> ActionError('... swap them.'); outside EXPOSURE_YEARS ->
    # Refusal("אין נתוני תנועה (as-of) לשנת {y} — שכבת החשיפה מכסה 2017 עד 2024", ["כל שנה בין 2017 ל-2024"])
def byar_sql(count_expr: str, z=1.96) -> tuple[str, str]
    # lo = "CASE WHEN {n} = 0 THEN 0.0 ELSE {n} * power(1 - 1.0/(9*{n}) - {z}/(3*sqrt({n})), 3) END"
    # hi = "({n} + 1) * power(1 - 1.0/(9*({n} + 1)) + {z}/(3*sqrt({n} + 1)), 3)"
    # verified: n=0 -> (0, 3.6681); 1 -> (0.0131, 5.5639); 3 -> (0.603, 8.7655); 10 -> (4.7874, 18.3916); 100 -> (81.3618, 121.6283) == byar_ci
UNITS_CTE = """units AS (                      -- one geometry vintage per segment-year (PLAN_1 'Segment unit')
    SELECT road, seg, year, km_from, km_to, adt_asof, based_on_year, gap_years
    FROM traffic_adt_asof
    QUALIFY row_number() OVER (PARTITION BY road, seg, year ORDER BY gap_years, km_to - km_from) = 1
)"""
ASSIGN_JOIN = ("JOIN units u\n      ON a.road1_number = u.road\n     AND a.road_km / 10.0 >= u.km_from\n"
               "     AND a.road_km / 10.0 <  u.km_to\n     AND a.year = u.year")       # half-open, exact view predicate
ASSIGN_QUALIFY = ("QUALIFY row_number() OVER (PARTITION BY a.accident_id, a.case_type_code "
                  "ORDER BY u.gap_years, u.km_to - u.km_from) = 1")                         # one row per accident
def units_count_sql() -> str            # f"WITH {UNITS_CTE}\nSELECT count(*) AS units, count(DISTINCT (road, seg)) AS segments FROM units"
def coverage_cte(y0, y1) -> str         # the trend coverage CTE text (people >= casualty_accidents per year, composite key, case 1)
def coverage_years_sql(y0, y1) -> str   # WITH coverage AS (...) SELECT year, casualty_accidents, people, people >= casualty_accidents AS covered FROM coverage ORDER BY year
```

Builders (one per action) are specified in §2; `parse_site_key`, `did_math`, `double_did`, `control_flag` in §3. Header comment of every statement: `-- nl2sql-accidents | <action> | k=v | ... | y0-y1` (ASCII, `|`/`-`).

### 1.2 `nl2sql_accidents/envelope.py`

```python
def denominator(kind, label, **extra) -> dict      # {"kind","label", **extra}; extra carries coverage numbers etc.
def stamp(action: str, *parts) -> str              # f"nl2sql-accidents {version()} | {action} | " + " | ".join(parts) — ASCII, tested
ROUTE_HEADING = "# 🧭 ניתוב"                        # single '#'
def route_card(title, head: str, body: list[str], actions: list[str]) -> Result
    # lines = [ROUTE_HEADING, head, *body, *[f"- פעולה מתאימה: {a}" for a in actions], LAB_LINE]
    # note = f"ניתוב · {head.splitlines()[0][:80]} · מעבדת הבטיחות בדרכים"   (one line; no CBS credit — no CBS data in it)
```
`dispatch`, `make_spec`, `refusal`, `guard`, `note_line`, `markdown_answer`, `view_input` unchanged.

### 1.3 `nl2sql_accidents/charts.py` (all through the existing `png()` frame; `Figure` only, lazy imports)

- `hbars(labels, values, *, xlabel, lo=None, hi=None, annot=None, colors=None, vline=None, vline_label=None, gap_after=None, gap_text=None, **frame)` — horizontal bars, top = first row, Hebrew labels via `heb()`, optional CI whiskers (`ax.errorbar(..., xerr=[v-lo, hi-v], fmt="none")`), optional per-bar annotation (`annot[i]`, e.g. `"176 · 908 M"`), optional vertical reference line (global rate), optional dashed separator after index `gap_after` with `gap_text` (the "… ועוד N תאים רגילים" break). Used by `segment_rates`, `weather_check`, `vehicle_cells_ranking`.
- `stacked_bars(labels, parts: dict[str, list[float]], totals, *, xlabel, **frame)` — 100 % stacked horizontal bars (killed `#26323d`, severe `_ORANGE`, slight `_TEAL`), N annotated at the bar end, legend top-left. Used by `severity_profile` (≤ 20 rows).
- `before_after_bars(panels: list[dict], *, headline: str, **frame)` — hides the frame `ax`, splits its area `[0.08, 0.33, 0.89, 0.50]` into two axes; per panel two groups (site, network) × two bars (before = 100, after = 100·after/before) with raw counts annotated, panel title = series label + `DiD r (lo–hi)` or `n/a`; `headline` (double ratio) drawn between the badge and the panels. Used by `before_after`.
- `tier_bars(...)` = `hbars` with tier colours (`#c0392b` highest-risk, `#0d9488` safest), `vline` at the global rate, at most 10 bars per tier and the break marker for the regular tier.

### 1.4 `nl2sql_accidents/__init__.py`, `pyproject.toml`, `actions/about.py`
`__version__ = "0.2.0"`; `actions=[trend, trap, about, segment_rates, severity_profile, vehicle_cells_ranking, before_after, weather_check, triage]` (each module `run` first, `ACTION` last, stdlib + engine + siblings only; `charts` imported inside `run` when `view == "chart"`); `about`'s `# פעולות` line lists all nine.

---

## 2. Actions

Common: `@guard(<title>)`; `view = as_choice(view, "view", (...))`; ONE Result via `dispatch(view, spec, title)`; `spec = make_spec(type_, basis=<ASCII>, rows=rows_safe(...), columns=..., sql=<the statement that produced rows>, denominator=..., caveats=<most specific first, no ';'>, png_base64=<only for view == chart>, stamp=stamp(...), ...extra)`; `Result.title` Hebrew without digits; `help` ASCII.

### 2.1 `segment_rates` (use ב, descriptive)

Inputs: `road` number default 0 (label `כביש`, help "0 = all roads; otherwise the road number of traffic_adt_asof"), `from_year` 2017 (`שנת התחלה`), `to_year` 2024 (`שנת סיום`), `severity` choice `all | ksi` default `all` (`חומרה`), `order_by` choice `rate_lo | rate | count` default `rate_lo` (`מיון`, help "rate_lo = lower bound of the 95% Poisson CI (conservative); rate = point estimate; count = accidents"), `top_n` number 10 (`מספר שורות`, 1–30 else ActionError), `view` chart|table|sql.

Validation: `exposure_year_range` (refusal outside 2017–2024); `as_int(road)` ≥ 0 else ActionError; `road > 0` with no units in range → `Refusal("אין נתוני תנועה (as-of) לכביש N בשנים y0–y1", ["road = 0 לכל הכבישים", "כבישים עם נתוני תנועה: 449 מספרי כביש (as-of 2017–2024)"])` (the count comes from `SELECT count(DISTINCT road) FROM traffic_adt_asof`, run only on this path).

`build_segment_rates_sql(road, y0, y1, severity, order_by, top_n)` — exact statement (metric = `accidents` | `ksi_accidents`; `<lo>`, `<hi>` = `byar_sql(f"coalesce(m.{metric}, 0)")`):

```sql
-- nl2sql-accidents | segment_rates | road=all | severity=all | order=rate_lo | 2019-2024 | top 10
WITH units AS (...UNITS_CTE...),
base AS (                             -- casualty series, interurban, requested years (dossier 5.1)
    SELECT accident_id, case_type_code, year, road1_number, road_km, severity_code
    FROM accidents
    WHERE case_type_code = 1
      AND year BETWEEN 2019 AND 2024
      AND road_type_code IN (3, 4)
),
matched AS (                          -- exact assignment predicate: half-open km, one row per accident
    SELECT a.accident_id, a.case_type_code, a.severity_code, u.road, u.seg, u.year
    FROM base a
    JOIN units u ON a.road1_number = u.road AND a.road_km / 10.0 >= u.km_from AND a.road_km / 10.0 < u.km_to AND a.year = u.year
    QUALIFY row_number() OVER (PARTITION BY a.accident_id, a.case_type_code ORDER BY u.gap_years, u.km_to - u.km_from) = 1
),
num AS (
    SELECT road, seg, count(*) AS accidents,
           count(*) FILTER (WHERE severity_code IN (1, 2)) AS ksi_accidents,
           count(DISTINCT year) AS accident_years
    FROM matched GROUP BY road, seg
),
den AS (                              -- vehicle-km over the SAME units CTE (both sides share it)
    SELECT road, seg, sum(adt_asof * (km_to - km_from) * 365) AS vkm, count(*) AS unit_years,
           min(km_from) AS km_from, max(km_to) AS km_to, max(gap_years) AS max_gap_years
    FROM units WHERE year BETWEEN 2019 AND 2024 GROUP BY road, seg
),
names AS (                            -- traffic_segments: 4,834 rows / 1,311 keys — one name pair per key
    SELECT road, seg, any_value(name_from) AS name_from, any_value(name_to) AS name_to
    FROM traffic_segments GROUP BY road, seg
)
SELECT CAST(d.road AS INTEGER) AS road, CAST(d.seg AS INTEGER) AS seg, n.name_from, n.name_to, d.km_from, d.km_to,
       coalesce(m.accidents, 0) AS accidents, coalesce(m.ksi_accidents, 0) AS ksi_accidents,
       coalesce(m.accident_years, 0) AS accident_years, d.unit_years,
       round(d.vkm / 1e6, 1) AS vkm_millions,
       round(coalesce(m.accidents, 0) / (d.vkm / 1e8), 2) AS rate_per_100m_vkm,
       round((<lo>) / (d.vkm / 1e8), 2) AS rate_lo,
       round((<hi>) / (d.vkm / 1e8), 2) AS rate_hi,
       d.max_gap_years
FROM den d
LEFT JOIN num m USING (road, seg)
LEFT JOIN names n USING (road, seg)
WHERE d.vkm > 0                       -- [AND d.road = 60]
ORDER BY rate_lo DESC, rate_per_100m_vkm DESC, road, seg        -- rate: rate_per_100m_vkm DESC, accidents DESC | count: <metric> DESC, rate_per_100m_vkm DESC
LIMIT 10
```
Second statement `segment_coverage_sql(y0, y1)` (same `units`, `base`, `matched` CTEs; `spec.coverage_sql`, `spec.coverage_by_year`): `SELECT b.year, count(*) AS interurban_casualty, count(m.accident_id) AS matched, round(100.0 * count(m.accident_id) / count(*), 1) AS pct FROM base b LEFT JOIN matched m ON m.accident_id = b.accident_id AND m.case_type_code = b.case_type_code GROUP BY b.year ORDER BY b.year`. Segment count for the basis: `count(DISTINCT (road, seg))` from `units` in range (third tiny statement, or fold into coverage as a scalar column).

Spec: `type "accidents/segment_rates"`, columns as selected (15), `rows` = top_n; extras `road, severity, order_by, from_year, to_year, coverage={"matched","total","pct","by_year"}, n_segments, stamp`. Denominator: `denominator("exposure", f"ק״מ-רכב ממדידות ADT as-of (Σ ADT × אורך × 365) · כיסוי {matched:,} מתוך {total:,} תאונות לא-עירוניות עם נפגעים ({pct}%)", matched=..., total=..., pct=..., segments=...)`.

Caveats (order): (1) data-driven per-year coverage `"כיסוי לפי שנה: {min_pct}% ({min_year}) עד {max_pct}% ({max_year}) — {עולה|יורד|לא מונוטוני}, תאונות ללא מקטע תואם אינן בשני הצדדים"` (a single year: `"כיסוי {pct}% ({year}) — …"`; the shape is computed, not asserted — sweep fix 2026-08-30); (2) `"מדד תיאורי של התוסף: הדו״ח המתודולוגי אינו מגדיר שיעור לק״מ-רכב למקטע (החשיפה נכנסת בו כמשתנה מסביר)"`; (3) `"יחידה = מקטע ספירת תנועה (road, seg), לא יחידת 5 ק״מ כבדו״ח · גרסת גיאומטריה אחת לכל מקטע-שנה · שמות לפי הגרסה האחרונה · ק״מ 0 = לא קודד"`; (4) data-driven `"ADT ≠ AADT: בשורות המוצגות ספירה מלפני עד {max_gap} שנים (סטייה חציונית {ape1}–{ape3}% בפער 1–3 שנים, {ape4}% בפער 4, מעבר לכך מעט זוגות)"` (APE from `traffic_fill_validation`, dossier constants when the table is absent); (5) `"רווח בר-סמך 95% פואסוני (קירוב Byar) — מיון לפי הגבול התחתון · שיעורים ממעט תאונות אינם יציבים"`; (6) `"לא-עירוני 2017+ בלבד (road_type_code 3–4) · שכבת as-of בלבד, לא traffic_adt_filled"`. Six — nothing truncated in the PNG.

PNG: `hbars` — labels `"{road}/{seg} · {name_from} → {name_to}"`, values = rate, whiskers lo/hi, annot `"{accidents} · {vkm_millions} M"`; title `f"תאונות עם נפגעים ל-100 מיליון ק״מ-רכב · {'כל הכבישים' if road == 0 else f'כביש {road}'} · {y0}–{y1}"` (`KSI` variant: `"תאונות KSI …"`); badge = the denominator label. `Result.title`: `f"שיעורי תאונות למקטע · {'כל התאונות'|'KSI'} · {'כל הכבישים'|'כביש נבחר'}"`. Basis: `f"segment_rates | road={road or 'all'} | severity={sev} | order={order_by} | {y0}-{y1} | top {n} of {n_segments} segments | coverage {matched}/{total} ({pct}%)"`. Stamp: `stamp("segment_rates", f"road={road or 'all'}", sev, order_by, f"{y0}-{y1}")`.

Live expectations (smoke): `units_count_sql()` → (6233, 1311); coverage 2017–2024 → 19,865 / 28,213 (70.4), by year 53.7, 61.8, 66.3, 78.8, 84.3, 75.4, 72.1, 81.2; `order_by=count`, 2019–2024 → row 0 = `[70, 120, 'צומת יסיף', 'צומת כברי', 66.2, 78.7, 176, 16, 5, 6, 908.3, 19.38, 16.62, 22.46, 1]`; `severity=ksi, order_by=rate_lo`, 2019–2024 → row 0 = road 411 seg 10 (16 acc, 10 KSI, 6/6 years, 45.5 M, 21.99, lo 10.53, hi 40.43); `road=60`, 2017–2024, `order_by=rate` → row 0 = seg 34 (34 acc, 219.1 M, 15.52); `from_year=2010` → refusal card with `2017`; `road=9999` → refusal.

### 2.2 `severity_profile` (use ג, descriptive)

Inputs: `by` choice `casualty_type | road_type | day_night | age_group | weather | involved_vehicle_type | sex` default `casualty_type` (`חתך`), `from_year` 2005, `to_year` 2024, `view` chart|table|sql. Validation: `year_range`.

```python
PROFILE_DIMS = {   # key: (key_expr, label_raw_expr, label_agg_expr, needs_accidents_join, Hebrew label)
  "casualty_type":         ("i.casualty_type_code", "i.casualty_type_label", "any_value(label_raw)", False, "סוג נפגע"),
  "road_type":             ("a.road_type_code", "a.road_type_label", "any_value(label_raw)", True, "סוג דרך"),
  "day_night":             ("a.day_night_code", "a.day_night_label", "any_value(label_raw)", True, "יום ולילה"),
  "age_group":             ("i.age_group_code", AGE_CASE, "any_value(label_raw)", False, "קבוצת גיל"),
  "weather":               ("a.weather_code", "a.weather_label", "any_value(label_raw)", True, "מזג אוויר (דיווח שוטר)"),
  "involved_vehicle_type": ("CASE WHEN i.casualty_type_code = 1 THEN -1 ELSE coalesce(i.involved_vehicle_type_code, 0) END",
                            "i.involved_vehicle_type_label",
                            "CASE WHEN code = -1 THEN 'הולך רגל — ללא רכב' ELSE coalesce(any_value(label_raw), 'לא ידוע') END", False, "סוג הרכב של הנפגע"),
  "sex":                   ("i.sex_code", "i.sex_label", "any_value(label_raw)", False, "מין"),
}
AGE_GROUPS = {1:"0–4", 2:"5–9", 3:"10–14", ..., 17:"80–84", 18:"85+", 99:"לא ידוע"}   # AGE_CASE = "CASE i.age_group_code WHEN 1 THEN '0–4' ... ELSE 'קוד ' || i.age_group_code END" (slit-owned literals)
```
`build_severity_profile_sql(by, y0, y1)`:
```sql
-- nl2sql-accidents | severity_profile | by=age_group | 2005-2024
WITH coverage AS (...coverage_cte(y0, y1)...),          -- person-level completeness per year (involved 2009 = 15 rows)
people AS (
    SELECT <key_expr> AS code, <label_raw_expr> AS label_raw, i.injury_severity_code
    FROM involved i
    [JOIN accidents a ON a.accident_id = i.accident_id AND a.case_type_code = i.case_type_code]   -- composite key, only when needed
    WHERE i.case_type_code = 1
      AND i.injury_severity_code IN (1, 2, 3)       -- casualties only (0 = uninjured)
      AND i.year BETWEEN 2005 AND 2024
      AND i.year IN (SELECT year FROM coverage WHERE people >= casualty_accidents)
),
grouped AS (
    SELECT code, <label_agg_expr> AS label, count(*) AS casualties,
           count(*) FILTER (WHERE injury_severity_code = 1) AS killed,
           count(*) FILTER (WHERE injury_severity_code = 2) AS severe,
           count(*) FILTER (WHERE injury_severity_code = 3) AS slight
    FROM people GROUP BY code
)
SELECT code, label, casualties, killed, severe, slight,
       round(100.0 * casualties / sum(casualties) OVER (), 1) AS share_pct,
       round(100.0 * killed / casualties, 2) AS killed_pct,
       round(100.0 * severe / casualties, 2) AS severe_pct,
       round(100.0 * slight / casualties, 2) AS slight_pct
FROM grouped ORDER BY casualties DESC, code
```
Second statement: `coverage_years_sql(y0, y1)` → uncovered years list for the caveat and `spec.uncovered_years`.

Denominator: `denominator("counts", "נפגעים (case_type_code = 1, injury_severity_code 1–3) — שיעורים יחסיים בתוך הנפגעים, לא סיכון")`. Caveats: (1) data-driven gap: `"נתוני נפגעים (involved) חסרים ב-{y}: {people:,} רשומות מול {acc:,} תאונות — השנה הושמטה מהפרופיל"` (plural form for > 1 year, as in trend); (2) `"מותנה בהיותו נפגע: השיעורים יחסיים לכל הנפגעים, לא סיכון לתאונה"`; (3) per dimension — age: `"תוויות הגיל נבנו מהקוד age_group_code: תווית המסד חסרה ב-46 אלף רשומות ומשובשת בקודים 2–3"`, vehicle: `"הולכי רגל = casualty_type_code 1 גם כשנרשם להם קוד רכב (489 רשומות) · הרכב לפי involved_vehicle_type_code"`, weather: `"מזג האוויר = דיווח השוטר (weather_code), לא מדידה · 'לא ידוע' מוצג"`, road/day_night: `"מאפייני התאונה מצורפים על המפתח (accident_id, case_type_code)"`; (4) `"קודי 0/99 (לא ידוע) נכללים בסך הכל"`; (5) `CAVEAT_DATA_END`.

PNG: `stacked_bars` (top 20 rows by casualties; killed/severe/slight shares; N at the bar end); title `f"פרופיל חומרה לפי {dim_he} · {y0}–{y1}"`. `Result.title` `f"פרופיל חומרה · לפי {dim_he}"`. Basis `f"severity_profile | by={by} | {y0}-{y1} | {n} rows | uncovered years: {list or 'none'} | involved WHERE case_type_code = 1 AND injury_severity_code IN (1, 2, 3)"`. Stamp `stamp("severity_profile", by, f"{y0}-{y1}")`.

Live: `by=involved_vehicle_type` → total Σ casualties 482,347, code 1 = 292,420 (2,495 / 13,305 / 276,620, share 60.6), code −1 (pedestrians) = 58,985 (2,144 / 11,902 / 44,939, 12.2); `by=casualty_type` code 1 = 58,985 (identity holds); `uncovered_years == [2009]`, caveat[0] contains `2009: 15 רשומות מול 16,856 תאונות`.

### 2.3 `vehicle_cells_ranking` (use ד)

Inputs: `metric` choice `involvements | ksi | fatal` default `involvements` (`מדד`), `bands` choice `all | known_engine` default `all` (`נפחי מנוע`, help "known_engine excludes cc_band 0 = unknown engine (mostly EVs)"), `view` chart|table|sql.

`build_vehicle_cells_sql(metric, bands)` (metric column `involvements | ksi_involvements | fatal_involvements`; `M = lit(EB_M_MKM)`):
```sql
-- nl2sql-accidents | vehicle_cells_ranking | metric=involvements | bands=all | M=200 Mkm
WITH cells AS (                       -- exposure > 0 only: 13 cells (model years 2025-2026) have no odometer history yet
    SELECT manufacture_year, cc_band, fleet, exposure_mkm, mean_annual_km, ev_share,
           involvements, ksi_involvements, fatal_involvements, involvements AS events
    FROM vehicle_cells
    WHERE exposure_mkm > 0            -- [AND cc_band <> 0]
),
prior AS (SELECT sum(events) / sum(exposure_mkm) AS global_rate, 200.0 AS m_mkm FROM cells),   -- global rate over INCLUDED cells
eb AS (
    SELECT c.*, p.global_rate, p.m_mkm,
           c.events / c.exposure_mkm AS raw_rate,
           (c.events + p.m_mkm * p.global_rate) / (c.exposure_mkm + p.m_mkm) AS eb_rate,     -- the report's EB formula
           c.exposure_mkm / (c.exposure_mkm + p.m_mkm) AS weight_on_data
    FROM cells c CROSS JOIN prior p
),
ranked AS (
    SELECT *, ntile(5) OVER (ORDER BY eb_rate, manufacture_year, cc_band) AS quintile, count(*) OVER () AS n_cells
    FROM eb
)
SELECT manufacture_year, cc_band,
       CASE cc_band WHEN 0 THEN 'לא ידוע (חשמלי/ללא נפח)' WHEN 4 THEN '501–1000' WHEN 5 THEN '1001–1300' WHEN 6 THEN '1301–1600'
                    WHEN 7 THEN '1601–1800' WHEN 8 THEN '1801–2000' WHEN 9 THEN '2001–3000' WHEN 10 THEN '3001–4000'
                    ELSE 'קוד ' || cc_band END AS cc_band_label,
       fleet, round(exposure_mkm, 1) AS exposure_mkm, events,
       round(raw_rate, 4) AS raw_rate_per_mkm, round(eb_rate, 4) AS eb_rate_per_mkm,
       round(global_rate, 5) AS global_rate_per_mkm, round(weight_on_data, 3) AS weight_on_data,
       quintile, CASE WHEN quintile = 1 THEN 'safest' WHEN quintile = 5 THEN 'highest_risk' ELSE 'regular' END AS tier,
       n_cells
FROM ranked ORDER BY eb_rate, manufacture_year, cc_band
```
Second statement `vehicle_cells_excluded_sql()`: `SELECT count(*) AS cells, coalesce(sum(fleet), 0) AS fleet, min(manufacture_year) AS y0, max(manufacture_year) AS y1, (SELECT sum(fleet) FROM vehicle_cells) AS fleet_all FROM vehicle_cells WHERE NOT (exposure_mkm > 0)` → `spec.excluded`.

Denominator: `denominator("exposure", f"מיליוני ק״מ-רכב (exposure_mkm מאומדני מד-אוץ) · {n} תאים, {excluded} הוחרגו (חשיפה אפס)")`. Caveats: (1) data-driven `"{excluded} תאים (שנות ייצור {y0}–{y1}, {fleet:,} כלי רכב = {pct}% מהצי) הוחרגו: אין עדיין היסטוריית מד-אוץ (חשיפה 0)"`; (2) `"תאים (שנת ייצור × נפח מנוע), לא דגמים: קבצי התאונות אינם נושאים לוחית, VIN או קוד דגם — הרישום (fleet_by_model, vehicle_mileage) מכיר דגמים אך אין מפתח מקשר"`; (3) when band 0 included and present: `"נפח מנוע 0 = לא ידוע (בעיקר רכב חשמלי, {k} תאים) — שיעורים קיצוניים, לקרוא בזהירות"`; (4) `f"EB: M = 200 מיליון ק״מ, שיעור גלובלי {g} ל-Mkm על התאים הכלולים — תאים קטנים נמשכים לממוצע"`; (5) `"שכבות = חמישוני EB: 20% הבטוחים / 60% רגילים / 20% בסיכון הגבוה"`; (6) `"תוקף: רכב פרטי, שנות ייצור 2016+, תאונות 2018–2024, ארצי בלבד"`.

PNG: `tier_bars` — highest-risk tier on top (≤ 10 bars, red), break marker `"… {n_regular} תאים רגילים"`, safest tier at the bottom (≤ 10, teal), raw rate as a hollow marker, `vline` at the global rate; labels `"{year} · {cc_band_label} סמ״ק"`; title `f"דירוג תאי רכב לפי שיעור EB · {metric_he} ל-מיליון ק״מ"`. `Result.title` `f"דירוג תאי רכב · {metric_he}"` (`מעורבויות` / `KSI` / `הרוגים`). Basis `f"vehicle_cells_ranking | metric={metric} | bands={bands} | M=200 Mkm | {n} cells ({excluded} excluded, exposure 0) | global {g:.5f} per Mkm | tiers {a}/{b}/{c}"`.

Live: 68 rows, tiers 14/41/13, excluded 13 / 465,636 / 2025–2026, global 0.19299 (`ksi` 0.03362, `fatal` 0.00456); first row (2024, 0) EB 0.0277 `safest`; last row (2016, 5) EB 0.8597 `highest_risk`; `bands=known_engine` → 62 rows (68 − 6 band-0 cells with exposure), no `cc_band = 0`. (Corrected 2026-08-30 by the verification sweep; the six dropped band-0 cells are now named in a caveat.)

### 2.4 `before_after` (use ה, Double-DiD)

Inputs: `site` text default `road:60/96.0-98.8` (`אתר`, help "road:<n>/<km_from>-<km_to> | njunction:<code> | ujunction:<city_code>/<code>"), `change_year` number 2017 (`שנת השינוי`), `window_years` number 3 (`חלון בשנים`, 1–3 else ActionError), `min_cell` number 6 (`מינימום לתא`, ≥ 1), `view` chart|table|sql.

Validation: `parse_site_key` (§3); `window_years ∈ 1..3`; `change_year - w < 2005 or change_year + w > 2024` → `Refusal(f"החלון {cy-w}–{cy+w} חורג מהנתונים (2005–2024)", [f"שנת שינוי בין {2005+w} ל-{2024-w} בחלון של {w} שנים"])`; all four site counts 0 → `Refusal("לא נמצאו תאונות באתר בחלונות שנבחרו", ["בדקו את מפתח האתר", "מקטעים עם תאונות: segment_rates"], detail=site key)`.

`build_before_after_sql(site, cy, w)` (`yb = (cy-w, cy-1)`, `ya = (cy+1, cy+w)`; `<pred>`, `<coded>`, `<coded_base>` from the site kind, §3):
```sql
-- nl2sql-accidents | before_after | site=road:60/96.0-98.8 | change 2017 | window 3 | control=network
WITH win AS (                         -- both series, the two windows, change year excluded
    SELECT case_type_code, year, road_type_code, road_km, nonurban_junction_code, urban_junction_code,
           CASE WHEN year BETWEEN 2014 AND 2016 THEN 'before' WHEN year BETWEEN 2018 AND 2020 THEN 'after' END AS period,
           (road1_number = 60 AND road_km / 10.0 >= 96.0 AND road_km / 10.0 < 98.8) AS at_site
    FROM accidents
    WHERE case_type_code IN (1, 3)
      AND (year BETWEEN 2014 AND 2016 OR year BETWEEN 2018 AND 2020)
)
SELECT case_type_code AS series, period,
       count(*) FILTER (WHERE at_site) AS site,
       count(*) AS network,                                             -- the whole national network of the series
       count(*) FILTER (WHERE road_type_code IN (3, 4) AND road_km IS NOT NULL AND road_km <> 0) AS coded,   -- location coding of the control
       count(*) FILTER (WHERE road_type_code IN (3, 4)) AS coded_base
FROM win
GROUP BY 1, 2
ORDER BY 1, period DESC
```
Second statement `site_label_sql(site)` (§3) → the Hebrew site label for the PNG.

Python (`did_math`, §3): per series `ratio = (site_after/site_before) / (net_after/net_before)`, `SE² = Σ 1/(n+½)` over the 4 counts, `CI = exp(ln r ± 1.96·SE)`; status `n/a` when any site count `< max(min_cell, 1)` (zero counts are n/a even at `min_cell = 1`); `double = r_cas / r_dmg`, `SE²_double = SE²_cas + SE²_dmg` (plugin extension), n/a if either series is n/a. Control flag: damage-only series coded share before vs after, `|after − before| / before > 0.25` (before = 0 → flagged).

Spec rows/columns: `["series", "site_before", "site_after", "site_ratio", "network_before", "network_after", "network_ratio", "ratio", "ci_lo", "ci_hi", "status"]`; rows `casualty`, `damage_only`, `double` (site/network cells `None` on the double row; ratios rounded to 4 decimals); extras `site_key, site_label, change_year, window_years, min_cell, counts=<the 4×(site,network) raw>, coding_share={"before","after","kind"}, control_flag, stamp`. Denominator: `denominator("exposure", "פרוקסי לחשיפה: סדרת הנזק-בלבד (case_type_code = 3) · קבוצת השוואה: כל הרשת הארצית")`.

Caveats (order; data-driven first): (1) `"בקרה מסומנת: שיעור קידוד המיקום בסדרת הנזק-בלבד השתנה מ-{b}% ל-{a}% בין החלונות (מעל 25% יחסית) — שינוי קידוד עלול להיקרא כשינוי תנועה"` when flagged, else `"קידוד מיקום בסדרת הנזק-בלבד: {b}% לפני, {a}% אחרי ({kind})"`; (2) when any n/a: `"תא דק (פחות מ-{min_cell} רשומות) בסדרת {series} — היחס לא חושב: ריק עדיף על מספר מזויף"`; (3) `"SE של היחס הכפול = שורש סכום ריבועי ה-SE של שתי הסדרות — הרחבה של התוסף (הדו״ח אינו נותן SE ליחס הכפול)"`; (4) `"רווח בר-סמך 95%: exp(ln r ± 1.96·SE), SE² = Σ 1/(n+½) על ארבע הספירות (Haldane)"`; (5) `f"שנת השינוי {cy} מוחרגת משני החלונות · אי-ודאות של שנה-שנתיים בתאריך השינוי"`; (6) `"קבוצת ההשוואה = כל הרשת הארצית (שתי הסדרות), לא אותו סוג דרך"`; (7) `"מתאם ולא סיבתיות: שינויים אחרים באתר וברשת אינם מבוקרים"`; (8) `f"מינימום {min_cell} רשומות לתא — כלל התוסף, מותאם מסף גלאי השינוי של הדו״ח"`. Up to 8 → PNG shows 6 + the overflow marker (existing frame behaviour).

PNG: `before_after_bars` with two panels (`נפגעים`, `נזק בלבד`), headline `f"יחס כפול {d} ({lo}–{hi})"` or `"יחס כפול: n/a"`; title `f"לפני ואחרי · {site_label} · שינוי {cy} · חלון {w}+{w}"`. `Result.title` `"לפני ואחרי · יחס כפול"`. Basis `f"before_after | site={key} | change {cy} | window {w}+{w} | min_cell {m} | control=network | casualty {sb}->{sa} vs {nb}->{na} | damage {..} | double {d} ({lo}-{hi})"` (ASCII: the key is ASCII; `n/a` when so). Stamp `stamp("before_after", key, f"change {cy}", f"window {w}")`.

Live: `road:60/96.0-98.8`, 2017, 3, 6 → counts (49, 6, 38867, 36102) / (22, 23, 143423, 120421); casualty DiD 0.1318 (0.0582–0.2987), damage 1.2452 (0.6984–2.2198), double 0.1059 (0.0389–0.2882); coding share 88.61 → 95.38, `control_flag False`; label contains `מחלף כיכר אדם`. `road:2/21.9-24.0`, 2011 → double 1.0943 (0.6045–1.9812); 2010 → 1.2983 (0.7897–2.1345). `njunction:433` → runs, label `צומת העשור` (deduped dim). `change_year=2023` → refusal; `window_years=4` → error.

### 2.5 `weather_check` (dark-layer light-up)

Inputs: `from_year` 2005, `to_year` 2024, `rain_threshold_mm` choice `["0.1", "0", "0.5", "1"]` default `"0.1"` (`סף גשם במילימטרים`), `view` chart|table|sql. Validation: `year_range`; `thr = float(as_choice(...))` → `lit(thr)`.

`build_weather_check_sql(y0, y1, thr)`:
```sql
-- nl2sql-accidents | weather_check | threshold 0.1 mm | 2005-2024
WITH w AS (                           -- v_accidents_weather: LEFT JOIN on (cell, hour) — precipitation IS NOT NULL is the filter
    SELECT cbs_weather_label, precipitation_mm, temperature_c
    FROM v_accidents_weather
    WHERE case_type_code = 1
      AND year BETWEEN 2005 AND 2024
      AND precipitation_mm IS NOT NULL
)
SELECT coalesce(cbs_weather_label, 'ללא תווית') AS cbs_weather_label,
       count(*) AS accidents,
       count(*) FILTER (WHERE precipitation_mm > 0.1) AS rainy_measured,
       round(100.0 * count(*) FILTER (WHERE precipitation_mm > 0.1) / count(*), 1) AS pct_measured_rain,
       round(median(temperature_c), 1) AS median_temp_c,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct
FROM w
GROUP BY 1
ORDER BY accidents DESC, 1
```
Second statement `weather_coverage_sql(y0, y1)`: `SELECT year, count(*) AS casualty_accidents, count(*) FILTER (WHERE weather_cell_id IS NULL) AS without_cell FROM accidents WHERE case_type_code = 1 AND year BETWEEN y0 AND y1 GROUP BY year ORDER BY year` → `years_no_cell = [y where without_cell == n]`, `rest = Σ over the other years`.

Denominator: `denominator("counts", "חלק מהתאונות עם נפגעים שיש להן תא מזג אוויר (ERA5) — שיעורים יחסיים בתוך כל תווית")`. Caveats: (1) data-driven `"שנים ללא תא מזג אוויר: {years} ({n:,} תאונות הושמטו)"` (when any); (2) data-driven `"{missing:,} מתוך {n:,} תאונות בשאר השנים ({pct}%) ללא תא — הושמטו"`; (3) FLAG 7, data-driven when the row exists: `"'לא ידוע' ({n:,} תאונות, {share}%) — {pct}% גשם מדוד, פי {ratio} מ'בהיר'"`; (4) `f"סף גשם: {thr} מ״מ בשעת התאונה (ERA5) — בסף 0 'גשום' עולה ל-67%"` (the 67 only when `thr == 0.1`); (5) `"ERA5 = ריאנליזה ברזולוציית כ-25 ק״מ, שעה עגולה — לא מד-גשם תחנתי"`; (6) `"תווית מזג האוויר = דיווח השוטר (weather_code), לא מדידה"`.

PNG: `hbars` — values `pct_measured_rain`, annot `"{accidents:,} תאונות"`, labels the CBS labels; title `f"מזג אוויר: דיווח השוטר מול גשם מדוד (סף {thr} מ״מ) · {y0}–{y1}"`. `Result.title` `"מזג אוויר · דיווח מול מדידה"`. Basis `f"weather_check | threshold {thr} mm | {y0}-{y1} | {n} rows | v_accidents_weather WHERE case_type_code = 1 AND precipitation_mm IS NOT NULL | {with_cell} with cell of {total}"`.

Live: rows `גשום` = (8256, 56.8, 12.7), `בהיר` = (183482, 3.7, 22.2), `לא ידוע` = (24896, 7.8, 20.9); `"0"` → `גשום` 67.0; caveats: years 2005, 2006, 2007 (51,772), then 807 of 218,951 (0.4 %).

### 2.6 `triage` (refusal gate)

Input: `question` text default `"איזה דגם רכב הכי בטוח?"` (`שאלה`). Output: refusal card (raised `Refusal`) or `route_card`. Rule table `RULES` (ordered; regex on the lowercased question; Hebrew + English):

| # | pattern (abridged) | verdict |
|---|---|---|
| 1 | `דגם|יצרן|מותג|לוחית|מספר רישוי|טויוטה|מאזדה|יונדאי|קיה|סקודה|model|make|brand|plate|corolla|mazda|toyota|hyundai` | `Refusal("לא ניתן לענות על דגם, יצרן או מספר רישוי: קבצי התאונות אינם נושאים אותם ואין מפתח לרישום הרכבים", answerable=["בטיחות לפי שנת ייצור × נפח מנוע עם חשיפה אמיתית: vehicle_cells_ranking"], what_to_do="הריצו vehicle_cells_ranking (metric = ksi)", detail="fleet_by_model / vehicle_mileage carry make and model, accidents / involved / vehicles carry no plate, VIN or model code - the finest linkable cell is manufacture_year x cc_band")` |
| 2 | (`לק"מ|לקילומטר|per km|entry|לכניסה`) AND (`עירוני|צומת|urban|junction`) | `Refusal("אין מכנה חשיפה לדרכים עירוניות ולצמתים — שיעור לק״מ קיים רק למקטעים לא-עירוניים 2017+", ["segment_rates (לא-עירוני)", "before_after לצומת עם בקרה", "דירוג יחסי לפי ספירות (P3 hotspot_map)"])` |
| 3 | a 4-digit year > 2024 or `השנה|2025|2026|next year` | `Refusal("אין נתונים אחרי 31.12.2024", ["כל שנה בין 2005 ל-2024: trend"])` |
| 4 | `מגורים|תושב|גר ב|residence|lives in` | `Refusal("מקום מגורים ≠ מקום התאונה — עמודות residence_* מתארות את הנפגע, לא את המיקום", ["severity_profile לפי חתכי נפגעים", "segment_rates לפי מיקום"])` |
| 5 | keyword → actions: `מגמה|שנה|לאורך זמן|trend` → trend · `קל|קלות|נאיבי|naive` → naive_vs_correct · `מקטע|כביש|ק"מ|segment|road` → segment_rates · `חומרה|הרוג|פצוע|גיל|הולך רגל|severity|age|pedestrian` → severity_profile · `גשם|מזג|weather|rain` → weather_check · `לפני|אחרי|שינוי|before|after` → before_after · `רכב|שנת ייצור|נפח|vehicle|engine` → vehicle_cells_ranking | `route_card(title, head=f"זוהו {n} פעולות מתאימות" | "לא זוהתה שאלה מוכרת — כל הפעולות", body=[the matched rule names], actions=[...])` |

`Result.title` `"טריאז׳ · מה אפשר לשאול"`. Unit test: each rule with one Hebrew and one English question; rule 1 wins over rule 5 ("דגם רכב"); the default question → refusal card whose body contains `vehicle_cells_ranking` and whose note starts `לא ניתן לענות`.

---

## 3. Site keys and the shared segment helpers (`sqlkit`)

```python
@dataclass(frozen=True)
class Site: kind: str; road: int|None; km_from: float|None; km_to: float|None; code: int|None; city: int|None; key: str

_ROAD = re.compile(r"^road:(\d+)/(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$")
_NJ   = re.compile(r"^njunction:(\d+)$")
_UJ   = re.compile(r"^ujunction:(\d+)/(\d+)$")
def parse_site_key(s) -> Site:
    # strip; road: n >= 1, km_from < km_to (equal -> empty half-open interval -> error), negatives never match the regex ->
    # ActionError("site must be road:<n>/<km_from>-<km_to>, njunction:<code> or ujunction:<city_code>/<code>; got 'x'.");
    # reversed -> ActionError("km_from (98.8) is not below km_to (96.0) - swap them."); njunction/ujunction code >= 1 and not in (99, 9999)
def site_predicate(site) -> str      # road: f"road1_number = {ilit(n)} AND road_km / 10.0 >= {lit(k0)} AND road_km / 10.0 < {lit(k1)}"
                                     # njunction: f"nonurban_junction_code = {ilit(code)}"; ujunction: f"city_code = {ilit(city)} AND urban_junction_code = {ilit(code)}"
def site_coding_exprs(site) -> tuple[str, str]   # (coded, base):
    # road:      ("road_type_code IN (3, 4) AND road_km IS NOT NULL AND road_km <> 0", "road_type_code IN (3, 4)")
    # njunction: ("road_type_code IN (3, 4) AND nonurban_junction_code IS NOT NULL AND nonurban_junction_code NOT IN (0, 99, 9999)", "road_type_code IN (3, 4)")
    # ujunction: ("road_type_code IN (1, 2) AND urban_junction_code IS NOT NULL AND urban_junction_code NOT IN (0, 99, 9999)", "road_type_code IN (1, 2)")
def site_label_sql(site) -> str
    # road: SELECT name_from, name_to, km_from, km_to FROM traffic_segments WHERE road = n AND km_from < k1 AND km_to > k0
    #       ORDER BY (least(km_to, k1) - greatest(km_from, k0)) DESC, src_year DESC LIMIT 1        -> "כביש 60 ק״מ 96.0–98.8 · מחלף כיכר אדם → צומת כוכב יעקב" (fallback: the km text)
    # njunction: SELECT coalesce((SELECT any_value(junction_name) FROM dim_junction_nonurban WHERE junction_code = c),
    #                            (SELECT any_value(nonurban_junction_name) FROM accidents WHERE nonurban_junction_code = c)) AS label   -- deduped: 4,202 rows / 2,525 codes
    # ujunction: SELECT any_value(city_name), any_value(street1_name), any_value(street2_name) FROM accidents WHERE city_code = city AND urban_junction_code = c
def did_math(site_before, site_after, net_before, net_after, min_cell) -> dict
    # {"ratio", "se2", "lo", "hi", "status"}; status "ok" | "n/a" (any site count < max(min_cell, 1), or a zero network count)
def double_did(cas: dict, dmg: dict) -> dict          # ratio = cas/dmg, se2 = sum, CI as above; n/a if either n/a
def control_flag(before_share, after_share) -> bool   # before is None/0 -> True if after; else abs(a-b)/b > CONTROL_FLAG_REL (strict)
```
Both series are located by the same predicate; the national network = every accident of the series in the window (no location filter). Segment sites deliberately do **not** use the `units` CTE (FLAG 4: as-of years are 2017–2024; the km range is literal).

---

## 4. `tools/find_demo_site.py` → `docs/demo/sites.md`

Repo-side script (not in the wheel; `packages` unchanged). Run from `accidents-lab\`: `app\.venv\Scripts\python nl2sql-accidents-plugin\tools\find_demo_site.py --out nl2sql-accidents-plugin\docs\demo\sites.md` (default: print to stdout; `--db` defaults to the live path; refuses to run if the path is missing). Uses `nl2sql_engine.modules.Context(db_path=...)` (read-only, guardrail) and `nl2sql_accidents.sqlkit.did_math/double_did`. One statement (probe §D, verbatim logic): `units` → `geom` (latest vintage per `(road, seg)`: `QUALIFY row_number() OVER (PARTITION BY road, seg ORDER BY year DESC, gap_years, km_to - km_from) = 1`) → `base` (both series, interurban, 2005–2024) → `m` (half-open match, `QUALIFY` by shortest geometry) → `yr` (per road/seg/year `cas`, `dmg`) → `years AS (SELECT unnest(range(2008, 2022)) AS y)` → `cand` (`cas_before/after`, `dmg_before/after` via `sum(...) FILTER (WHERE yr.year BETWEEN y-3 AND y-1 | y+1 AND y+3)`) joined to `nat` (national per window) and `names` (`any_value`). Filter all four site cells ≥ 6. Python: `did_math` per series with the network, `double_did`; print two markdown tables — top 10 by `|cas_after − cas_before|` and top 10 by casualty ratio (`cas_before ≥ 15`) — with columns `road, seg, site key (road:<n>/<km_from>-<km_to>), names, change_year, cas b→a, dmg b→a, DiD_cas, DiD_dmg, double (CI)`; a note that the probe's "double_ratio" was site-only with +0.5 continuity while these are network-controlled. Then the **named demo sites**: road 60 seg 836 `road:60/96.0-98.8` (מחלף כיכר אדם → צומת כוכב יעקב), change 2017: casualties 49→6, damage-only 22→23, DiD 0.132 / 1.245, **double 0.106 (0.039–0.288)**; road 2 seg 20 `road:2/21.9-24.0` (צומת גלילות → מחלף הסירה), change 2011: casualties 63→15 (×0.24), damage-only 499→106 (×0.21) → **double 1.094 (0.60–1.98)** (2010: 1.298) — "the control removes the effect". `sites.md` = aggregates only (names, counts, ratios), header "provisional — confirmed in P4 (excess top-10)".

---

## 5. Fixture extension (`tests/conftest.py`)

New rows live in **2012–2021 only**, so every P1 expectation for 2022–2024 stays (trend, trap, monthly zero-fill, the 2022 gap, C6's road-code caveat). P1 rows get defaults for the new columns: `road1_number/road_km NULL`, junction codes 0, `city_code 5000 'תל אביב - יפו'` for road types 1–2 else 0, `weather_code 1 'בהיר'`, `day_night 1 'יום'`, `accident_timestamp = date 15th 10:30`, `weather_cell_id NULL`, lat/lon NULL; P1 involved rows: `casualty_type 2`, `age_group 5 '20-24'`, `vehicle 1`, `sex 1`.

DDL (types as live): `accidents(+ road1_number INTEGER, road_km DOUBLE, nonurban_junction_code INTEGER, nonurban_junction_name VARCHAR, urban_junction_code INTEGER, city_code INTEGER, city_name, street1_name, street2_name VARCHAR, weather_code SMALLINT, weather_label VARCHAR, day_night_code SMALLINT, day_night_label VARCHAR, hour_of_day SMALLINT, accident_timestamp TIMESTAMP, weather_cell_id INTEGER, latitude DOUBLE, longitude DOUBLE, road_surface_label VARCHAR)`; `involved(+ casualty_type_code/label, age_group_code/label, involved_vehicle_type_code/label, sex_code/label, vehicle_num)`; `traffic_adt_asof(road DOUBLE, seg DOUBLE, km_from, km_to DOUBLE, year BIGINT, adt_asof DOUBLE, based_on_year, gap_years BIGINT)`; `traffic_segments(road BIGINT, seg BIGINT, km_from, km_to, name_from, name_to, placement, technology, src_year, loaded_at)`; `vehicle_cells` (12 live columns); `dim_junction_nonurban(junction_code, road1_number, road2_number, road_km, junction_name, x_itm, y_itm, latitude, longitude)`; `dim_junction_urban(junction_code, city_code, street1_code, street2_code, x_itm, y_itm, latitude, longitude)`; `weather_hourly(cell_id, observed_at TIMESTAMP, temperature_c, precipitation_mm, humidity_pct, wind_speed_kmh, weather_code)`; `dim_weather_code(weather_code, description_en, description_he)`; views `v_casualty_*` + **`v_accidents_weather` verbatim from the live definition** (probe §E10). Objects: 10 tables + 3 views.

**Traffic:** `traffic_adt_asof` = (1,10, 0–10, 2019, 10000, gap 0), (1,10, 0–10, 2020, 10000, 0), **(1,10, 0–12, 2020, 12000, based 2018, gap 2)** ← the overlapping vintage the units CTE discards, (1,10, 0–10, 2021, 10000, 0), (1,11, 9.5–15, 2019, 5000, gap 1), (2,20, 5–7.5, 2020, 20000, 0), (2,20, 5–7.5, 2021, 20000, 0). `traffic_segments` = (1,10, 0–10, 'צומת א', 'צומת ב', 2019), **(1,10, 0–12, same names, 2020)** ← two vintages → `any_value`, (1,11, 9.5–15, 'צומת ב', 'צומת ה', 2019), (2,20, 5–7.5, 'מחלף ג', 'צומת ד', 2020).

**Casualty accidents (case 1)** — columns: id · year-month · sev · road_type · road1/road_km · nu-junction · u-junction/city · weather · day/night · cell · involved `(injury, casualty_type, age_group, age_label, vehicle, sex)`:

| key | id | y-m | sev | rt | road/km | junction | w | dn | cell | involved |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 2012000001 | 2012-01 | 3 | 4 | 1 / 10 | — | 1 | 1 | 1 | (3,2,5,'20-24',1,1) |
| A2 | 2012000002 | 2012-02 | 2 | 4 | 1 / 20 | — | 2 | 5 | 1 | (2,3,6,'25-29',1,2) |
| A3 | 2012000003 | 2012-03 | 3 | 4 | 1 / 30 | — | 1 | 1 | 1 | (3,4,5,'20-24',9,1) |
| A4 | 2013000001 | 2013-01 | 1 | 4 | 1 / 40 | — | 1 | 1 | 1 | (1,1,17,'80-84',NULL,2) |
| A5 | 2013000002 | 2013-02 | 3 | 4 | 1 / 50 | — | 9 | 1 | 1 | (3,2,2,**'05-ספטמבר'**,1,1) |
| A6 | 2013000003 | 2013-03 | 3 | 4 | 1 / 60 | — | 1 | 5 | **NULL** | (3,2,7,**NULL**,2,1) |
| A7 | 2014000001 | 2014-01 | 2 | 4 | 1 / 70 | — | 2 | 1 | 1 | (2,**1**,99,'לא ידוע',**1**,1) pedestrian with a vehicle code |
| A8 | 2014000002 | 2014-02 | 3 | 4 | 1 / 80 | — | 1 | 1 | 1 | (3,3,10,'45-49',1,2), (0,2,8,'35-39',1,1) |
| A9 | 2016000001 | 2016-01 | 3 | 4 | 1 / 90 | — | 1 | 1 | 1 | (3,2,5,'20-24',1,1) |
| S11 | 2018000001 | 2018-06 | 3 | 4 | 1 / 30 | — | 1 | 1 | 1 | (3,2,6,'25-29',1,1) |
| B1 | 2012000004 | 2012-05 | 3 | 3 | 9 / 500 | nu 433 | 1 | 1 | 2 | (3,2,5,'20-24',1,1) |
| B2 | 2012000005 | 2012-06 | 3 | 1 | NULL | u 777 / 5000 | 1 | 1 | 2 | (3,1,3,**'אוקטובר-14'**,NULL,1) |
| B3 | 2012000006 | 2012-07 | 2 | 3 | 9 / 500 | nu 433 | 2 | 5 | 2 | (2,4,5,'20-24',10,1) |
| B4 | 2013000004 | 2013-05 | 3 | 1 | NULL | u 777 / 5000 | 1 | 1 | 2 | (3,3,12,'55-59',1,2) |
| B5 | 2013000005 | 2013-06 | 3 | 3 | 9 / 500 | nu 433 | 1 | 1 | 2 | (3,2,9,'40-44',3,1) |
| B6 | 2013000006 | 2013-07 | 1 | 2 | NULL | u 0 / 5000 | 1 | 1 | 2 | (1,1,18,'85+',NULL,2), (3,2,4,'15-19',1,1) |
| B7 | 2014000003 | 2014-05 | 3 | 3 | 9 / 500 | nu 433 | 1 | 1 | 2 | (3,2,5,'20-24',1,1) |
| B8 | 2014000004 | 2014-06 | 3 | 1 | NULL | u 777 / 5000 | 1 | 1 | 2 | (3,6,4,'15-19',15,1) |
| B9 | 2016000002 | 2016-05 | 3 | 3 | 9 / 500 | nu 433 | 1 | 1 | 2 | (3,2,5,'20-24',1,1) |
| B10 | 2016000003 | 2016-06 | 2 | 1 | NULL | u 777 / 5000 | 1 | 1 | 2 | (2,1,1,'00-04',NULL,1) |
| B11 | 2017000001 | 2017-05 | 3 | 3 | 9 / 500 | nu 433 | 1 | 1 | 2 | (3,2,6,'25-29',1,2) |
| B12 | 2017000002 | 2017-06 | 3 | 2 | NULL | u 0 / 5000 | 1 | 1 | 2 | (3,2,7,'30-34',12,1) |
| B13 | 2018000002 | 2018-05 | 3 | 3 | 9 / 500 | nu 433 | 1 | 1 | 2 | (3,2,5,'20-24',1,1) |
| B14 | 2018000003 | 2018-07 | 3 | 1 | NULL | u 777 / 5000 | 1 | 1 | 2 | (3,3,11,'50-54',11,2) |
| S1 | 2019000001 | 2019-01 | 3 | 4 | 1 / 20 | — | 1 | 1 | 1 | (3,2,5,'20-24',1,1) |
| S2 | 2019000002 | 2019-02 | 1 | 4 | 1 / **98** | — | 1 | 1 | 1 | (1,2,5,'20-24',1,1) matches seg 10 AND 11 → QUALIFY picks 10 |
| S3 | 2019000003 | 2019-03 | 2 | 4 | 1 / 120 | — | 1 | 1 | 1 | (2,2,5,'20-24',1,1) → seg 11 |
| S9 | 2019000004 | 2019-04 | 3 | 4 | 1 / **NULL** | — | 1 | 1 | 1 | (3,2,5,'20-24',1,1) |
| S4 | 2020000001 | 2020-01 | 3 | 4 | 1 / **110** | — | 1 | 1 | 1 | (3,2,5,'20-24',1,1) unmatched (the 0–12 vintage is discarded) |
| S5 | 2020000002 | 2020-02 | 3 | 4 | 1 / 50 | — | 1 | 1 | 1 | (3,2,5,'20-24',1,1) |
| S6 | 2020000003 | 2020-03 | 2 | 4 | 2 / 60 | — | 1 | 1 | 1 | (2,3,6,'25-29',1,2) |
| S7 | 2021000001 | 2021-01 | 3 | 4 | 2 / **75** | — | 1 | 1 | 1 | (3,2,5,'20-24',1,1) half-open: 7.5 < 7.5 is false → unmatched |
| S8 | 2021000002 | 2021-02 | 1 | 4 | 2 / 74 | — | 1 | 1 | 1 | (1,4,5,'20-24',9,1) |
| S10 | 2021000003 | 2021-03 | 3 | 4 | 1 / **-5** | — | 1 | 1 | 1 | (3,2,5,'20-24',1,1) negative km |

Timestamps: day rows 10:30, night rows 22:30 on the 15th; `hour_of_day` 10/22; lat/lon 32.0/35.0 when a cell exists; `nonurban_junction_name 'צומת העשור'` on the 433 rows; `street1/2` 'רחוב א'/'רחוב ב' on the 777 rows.

**Damage-only (case 3)** per year y ∈ {2012, 2013, 2014, 2016, 2017, 2018}: `y·10⁶+1` (m 8, rt 4, road 1 km 15) and `+2` (m 9, road 1 km 25) — the site rows (ids **collide** with A-ids); `+3` (m 10, rt 3, road 9, nu 433, km 1000) and `+4` (m 11, km 1010) — the junction rows, **with `road_km NULL` in 2017 and 2018** (the coding-share flag).

**Weather:** `weather_hourly` = one row per cell-bearing casualty accident at `date_trunc('hour', ts)`: precipitation 0.0 / 25.0 °C except A2 (2.0, 12.0), A7 (0.5, 14.0), B3 (0.05, 16.0), A5 (0.3, 18.0), A8 (1.0, 20.0), S4 (0.05, 30.0); `weather_code` 61 when > 0.1 else 1; `dim_weather_code` = (1, 'clear', 'בהיר'), (61, 'rain', 'גשם').

**Vehicle cells** (year, band, fleet 10,000, exposure_mkm, inv, ksi, fatal): (2016,5,1000,400,40,4), (2016,6,4000,800,80,8), (2017,6,4000,600,60,6), (2018,6,2000,500,50,5), **(2019,0,50,40,4,1)** band 0, (2019,8,1000,100,10,1), (2020,6,2000,300,30,3), (2021,9,500,350,35,4), (2022,6,1000,50,5,0), (2023,4,200,10,1,0); zero-exposure **(2025,6, fleet 1000, 0,0,0,0)**, **(2026,0, fleet 500, 0,…)**. `mean_weight_kg/ev_share/mean_annual_km/km_measured/years_exposed` any plausible constants.

**Junction dims:** `dim_junction_nonurban` = (433, 'צומת העשור', 32.1/35.1) **twice** (slightly different coords) + (500, 'צומת אחר'); `dim_junction_urban` = (777, 5000, …).

**Planted truth (all verified in-memory):**
- `about`: accidents 97 = 44 casualty + 53 damage-only; involved 55 (52 casualty); vehicles 3; `2012 עד 2024`; `12/2024`; `2024-12-15`; `13 (10 טבלאות + 3 מבטים)`.
- units: 6 rows — (1,10,2019), (1,10,2020, **km_to 10.0**), (1,10,2021), (1,11,2019), (2,20,2020), (2,20,2021); raw 7.
- matched (2017–2024): S1→(1,10), S2→(1,10), S3→(1,11), S5→(1,10), S6→(2,20), S8→(2,20); without QUALIFY 7 rows (S2 twice); coverage by year 2018 1/0, 2019 4/3, 2020 3/2, 2021 3/1, 2022 1/0, 2023 1/0, 2024 3/0 → 16 / 6 (37.5 %); 2019–2021 → 10 / 6 (60.0 %).
- segment rows (2019–2021, `all`): (2,20): acc 2, ksi 2, years 2/2, 36.5 M, rate 5.48, lo 0.62, hi 19.78, gap 0 · (1,10): 3, 1, 2/3, 109.5 M, 2.74, 0.55, 8.01 (= `byar_ci(3, 1.095)`), gap 0 · (1,11): 1, 1, 1/1, 10.0375 M, 9.96, 0.13, 55.43, gap **1**. Order `rate_lo`: (2,20), (1,10), (1,11); `rate`: (1,11), (2,20), (1,10); `count`: (1,10), (2,20), (1,11); `ksi` rate: (1,11) 9.96, (2,20) 5.48, (1,10) 0.91 (lo 0.01, hi 5.08). `road=1` → 2 rows; `road=3` → refusal. 2017–2024 defaults give the same three rows.
- before_after `road:1/0-10`, 2015: w3 counts casualty 8→2 (network 16→8), damage 6→6 (12→12); damage coded share 12/12 → 8/12 (**flag**); w1: 2→1 (4→3), 2→2 (4→4), coded 4/4 → 4/4 (no flag); w2: 5→1 (10→5), 4→4 (8→8), 8/8 → 6/8 (= 25 %, **not** flagged, strict). `njunction:433` w3: 4→3 (16→8), 6→6 (12→12), junction-coded 6/12 → 6/12 (no flag). `ujunction:5000/777` w3: 3→2, damage 0→0 (coded base 0 → flag).
- DiD (T2, `min_cell=2`): casualty 0.5, SE² 0.6959, CI 0.0975–2.5648; damage 1.0, SE² 0.467692, CI 0.2617–3.8206; double 0.5, SE² 1.163592, CI 0.0604–4.1417. T1 (defaults, `min_cell=6`): casualty `n/a` (after = 2), damage 1.0 as above, double `n/a`. T3 (w1, `min_cell=1`): 0.6667 (0.057–7.7991), 1.0 (0.1123–8.9037), double 0.6667 (0.0248–17.9112). T4 (`njunction:433`, `min_cell=3`): casualty 1.5 (0.2958–7.6069), damage 1.0. T5 (`ujunction:5000/777`, `min_cell=1`): casualty 1.3333 (0.2156–8.2441), damage `n/a` (zero cells), double `n/a`.
- weather 2012–2021 @0.1: `בהיר` 29 (1 rainy, 3.4 %, median 25.0, share 87.9), `גשום` 3 (2, 66.7, 14.0, 9.1), `לא ידוע` 1 (1, 100.0, 18.0, 3.0); @0: 6.9 / 100.0 / 100.0; @1: 0.0 / 33.3 / 0.0; 2005–2024 identical rows; coverage: years without any cell **2022, 2023, 2024** (10 accidents), remainder 1 of 34 (2.9 %) (A6).
- severity_profile 2005–2024 (2022 uncovered: 1 person vs 2 accidents), total 46 casualties (killed 7, severe 7, slight 32): casualty_type 2: 32 (4/2/26, 69.6 %, killed_pct 12.5) · 1: 5 (2/2/1, 10.9, 40.0) · 3: 5 (0/2/3) · 4: 3 (1/1/1) · 6: 1; involved_vehicle_type 1: 33 (4/4/25, 71.7) · −1 pedestrians: 5 (2/2/1) · 9: 2 · 2, 3, 10, 11, 12, 15: 1 each; age_group 5: 28 (5/3/20) · 6: 4 · 4: 2 · 7: 2 (label `30–34` from the map, DB label NULL) · 2: 1 (label `5–9`, DB label mangled) · 1, 3, 9, 10, 11, 12: 1 · 17: 1 (killed) · 18: 1 (killed) · 99: 1 (`לא ידוע`); road_type 4: 23 (4/4/15) · 1: 9 (2/1/6) · 3: 9 (0/2/7) · 2: 4 (1/0/3) · 5: 1; day_night 1: 43 (7/5/31) · 5: 3 (0/2/1); weather 1: 42 (7/4/31) · 2: 3 (0/3/0) · 9: 1; sex 1: 38 (5/5/28) · 2: 8 (2/2/4); 2023–2024 → one row, type 2: 11 (3/1/7, 100 %).
- vehicle cells (`involvements`, `all`): global 0.2, 10 cells, ntile sizes 2/2/2/2/2; EB ascending: (2022,6) 0.075, (2019,8) 0.1167 [safest tier] · (2023,4) 0.125, (2017,6) 0.1524, (2020,6) 0.1545, (2016,6) 0.2, (2018,6) 0.2455, **(2019,0) 0.32 (raw 0.80 — highest raw, regular tier)** · (2016,5) 0.3667, (2021,9) 0.5571 [highest-risk]; `ksi`: global 0.02, same order; `fatal`: global 0.0020317, safest (2022,6), (2023,4), riskiest (2019,0) 0.005625, (2021,9) 0.006295; `known_engine`: 9 cells, global 0.198089, ntile 2/2/2/2/1, no band 0; excluded 2 cells / fleet 1,500 / 2025–2026 / total 101,500.

---

## 6. Tests

- **`tests/test_sqlkit.py` (additions):** `as_float`; `exposure_year_range` (2016 → Refusal with `2017`; swap error); `byar_sql` vs `byar_ci` for n ∈ {0, 1, 3, 10, 100} through `ctx.query("SELECT ...")`; `units_count_sql` on the fixture → (6, 3) and the 2020 row's `km_to == 10.0`; assignment: `build_segment_match_sql(2017, 2024)` → the six ids/segments above, S2 → seg 10, and the no-QUALIFY variant → 7; `parse_site_key` (valid three kinds incl. decimals `road:60/96.0-98.8`; rejects `road:60/98.8-96.0`, `road:60/-5-10`, `road:60/96-96`, `njunction:0`, `njunction:99`, `ujunction:5000`, `foo`); `did_math((8,2,16,8), 6)` → n/a, `min_cell=2` → 0.5 / 0.6959 / 0.0975 / 2.5648; `did_math((6,6,12,12))` → 1.0 / 0.467692; `double_did` → 0.5 / 1.163592 / 0.0604–4.1417; zero cell → n/a at `min_cell=1`; `control_flag(1.0, 0.667) True`, `(0.8861, 0.9538) False`, `(1.0, 0.75) False`, `(0, 0.5) True`; every builder: first line ASCII, contains `case_type_code = 1` (before_after: `case_type_code IN (1, 3)`), no trailing `;`, `build_segment_rates_sql` contains `road_km / 10.0 <  u.km_to` and the QUALIFY line, `build_severity_profile_sql` has the composite join iff the dimension needs it, `build_vehicle_cells_sql("involvements", "known_engine")` contains `cc_band <> 0`.
- **`tests/test_envelope.py`:** `denominator("exposure", "x", matched=1)["matched"] == 1`; `stamp("a", "b=c", "2019-2024")` exact and ASCII; `route_card` shape (heading, LAB_LINE last, one-line note starting `ניתוב ·`).
- **`tests/test_charts.py`:** `hbars` (with/without CI, with `vline` and `gap_after`), `stacked_bars`, `before_after_bars` (2 panels; one panel n/a), `tier_bars` → PNG magic; 25 labels still render.
- **`tests/test_segment_rates.py`:** the row values above per `order_by`/`severity`/`road`; `spec.coverage == {"matched": 6, "total": 10, "pct": 60.0}` for 2019–2021 and by-year list; caveat[0] starts `כיסוי לפי שנה` and mentions `33.3% (2021)`; caveat contains `מדד תיאורי של התוסף`; `spec.rows == rows_safe(ctx.query(spec["sql"])[1])` and `spec.coverage_by_year == rows of spec.coverage_sql`; `road=3` → refusal (`אין נתוני תנועה`); `from_year=2010` → refusal mentioning `2017`; `top_n=0`/`31` → error; `view=table` rows == chart rows; PNG valid; basis/stamp ASCII.
- **`tests/test_severity_profile.py`:** per dimension the rows above (assert code→(casualties, killed, severe, slight) dicts); age labels `5–9`, `30–34`, `לא ידוע`; pedestrian bucket = 5 in both `casualty_type` and `involved_vehicle_type` (A7 with vehicle code 1 counted as pedestrian, not in `veh 1`); `spec.uncovered_years == [2022]` and caveat[0] contains `2022: 1 רשומות מול 2 תאונות`; 2023–2024 → one row with 100 %; `by=road_type` SQL contains the composite join, `by=casualty_type` does not; `view=sql` == `spec.sql`; rows == query.
- **`tests/test_vehicle_cells.py`:** ordering and tiers above; `global_rate_per_mkm == 0.2` (`ksi` 0.02); (2019,0) `regular` with `raw_rate_per_mkm 0.8`; `known_engine` → 9 rows, global ≈ 0.19809; `spec.excluded == {"cells": 2, "fleet": 1500, "y0": 2025, "y1": 2026, "fleet_all": 101500}`; caveat[0] contains `2 תאים` and `1,500`; band-0 caveat present for `all`, absent for `known_engine`; basis contains `tiers 2/6/2`.
- **`tests/test_before_after.py`:** T1–T5 rows (4-decimal approx), statuses, `control_flag`, `coding_share`, caveat order (flag line first when flagged; n/a line second); label `צומת העשור` for `njunction:433` (dedup: exactly one label); refusals (window 2007/2022, no-accident site `road:77/0-1`); errors (`window_years=4`, `min_cell=0`, bad keys); `spec.counts` equals the four site/network pairs from `ctx.query(spec["sql"])`; PNG valid for T2 and T1 (n/a panel).
- **`tests/test_weather_check.py`:** rows above at `"0.1"`, `"0"`, `"1"`; `spec.rows == query`; caveats: `שנים ללא תא מזג אוויר: 2022, 2023, 2024 (10 תאונות הושמטו)` first, then `1 מתוך 34`; `לא ידוע` caveat present (`100.0%`); threshold caveat text; `rain_threshold_mm="2"` → error listing the choices.
- **`tests/test_triage.py`:** rule table cases (Hebrew + English per rule), precedence (rule 1 over 5), route card shape and note, refusal card body contains `vehicle_cells_ranking`, `Traceback` never present.
- **`tests/test_contract.py`:** names set = nine; labels `מקטעים · segment_rates`, `חומרה · severity_profile`, `תאי רכב · vehicle_cells_ranking`, `לפני ואחרי · before_after`, `מזג אוויר · weather_check`, `טריאז׳ · triage`; view choices per action (`chart, table, sql` ×5; triage has no `view`); number defaults ints (unchanged rule); `VIEW_RUNS` += 15 chart/table/sql cases (segment_rates 2019–2021; before_after `road:1/0-10`, 2015, `min_cell=2`; weather 2012–2021) + triage (default → note starts `לא ניתן לענות`; `"מגמת הרוגים"` → note starts `ניתוב`); note-prefix set gains `ניתוב`; `test_chart_spec_carries_the_full_answer` parametrized over the five chart actions; three markdown shapes (answer / refusal / route) each asserted; refusal cases += `segment_rates from_year=2010`, `before_after change_year=2023`, `triage` default; `test_no_result_outside_envelope` unchanged; `test_png_is_thread_safe` over the five chart actions; `test_version_pinned` → `"0.2.0"`.
- **`tests/test_about.py`:** the new fixture numbers (§5); `test_writes_nothing_under_data_dir` runs all nine actions.
- **`tests/test_live.py` (additions):** units (6233, 1311); coverage 19,865 / 28,213 and by-year 53.7 … 81.2; `order_by=count` 2019–2024 row 0 = road 70 seg 120 / 176 / 16 / 908.3 / 19.38 (16.62–22.46); `ksi`+`rate_lo` row 0 = road 411 seg 10; weather (8256, 56.8, 12.7), (183482, 3.7, 22.2), (24896, 7.8), `"0"` → 67.0, caveat years 2005–2007 / 51,772 and 807 of 218,951; vehicle cells 68 / 13 / 465,636 / global 0.19299, 0.03362, 0.00456 / tiers 14/41/13 / (2024,0) 0.0277 safest / (2016,5) 0.8597; profile total 482,347, vehicle code 1 = 292,420, pedestrians 58,985 in both dims, `uncovered_years == [2009]`; before_after `road:60/96.0-98.8` 2017 → counts and 0.1318 / 1.2452 / 0.1059 (0.0389–0.2882), no flag, label contains `כיכר אדם`; `road:2/21.9-24.0` 2011 → double 1.0943; `njunction:433` label `צומת העשור`; triage default → refusal. Every result: credit, one-line note, JSON-safe.

---

## 7. Steps (from `accidents-lab\`), acceptance, docs

1. `git -C app status --short` empty; port 8000 check (PITFALLS #1).
2. Write PITFALLS entries for flags 1–8 now (found during P2 planning, dated 2026-08-29) — titles: (1) *segment_rates coverage is the units-CTE number (70.4 %, 55→83 %, non-monotonic), and the raw-vs-units vkm overstatement is 0 % in 2017 but 77 % in 2024* [flags 1+10]; (2) *"BETWEEN or no QUALIFY double-counts ~25 %" belongs to the raw table — with the units CTE it is +0.4 % / +18.5 %* [2]; (3) *489 pedestrians carry a vehicle-type code — bucket on `casualty_type_code = 1`, never on NULL* [3]; (4) *`traffic_adt_asof` is 2017–2024 only — `before_after` cannot reuse the units CTE; km-range site keys resolve without a year* [4]; (5) *`nonurban_junction_code` is populated only for `road_type_code = 3` (35 % of non-urban casualty accidents, 0 % on type 4)* [5]; (6) *the junction control is 5.6 % urban / 23.3 % non-urban (corrected 2026-08-30; the planning probe's 22/49 used another definition), damage-only junction coding collapsed 2010–2014 and interurban km-coding swings 70–98 % — hence the data-driven control flag* [6+9]; (7) *`לא ידוע` is the second-largest weather label (24,896, 7.8 % measured rain, twice `בהיר`)* [7]; (8) *make/model exists in `fleet_by_model` / `vehicle_mileage` — only the key to the accident files is missing, and `cc_band 0` (unknown engine, the EV cohort) has the cube's wildest rates* [8+11]. Each with What happened / Root cause / What the real build & participants should do.
3. Red→green slices: (a) `pyproject` 0.2.0 + `__init__` + `test_contract` declarations (red) → (b) `sqlkit` additions + `conftest` extension + `test_sqlkit`/`test_about` (green) → (c) `envelope` + `charts` additions + tests → (d) `segment_rates` → (e) `severity_profile` → (f) `vehicle_cells_ranking` → (g) `before_after` → (h) `weather_check` → (i) `triage` → (j) `tools/find_demo_site.py` + `docs/demo/sites.md` → (k) `test_live` additions. After each slice: `cd nl2sql-accidents-plugin; ..\app\.venv\Scripts\python -m pytest -q; cd ..`.
4. Wheel sanity: `..\app\.venv\Scripts\python -m build --wheel`; namelist has `nl2sql_accidents/actions/{segment_rates,severity_profile,vehicle_cells,before_after,weather_check,triage}.py` and **no** `tools/`.
5. Install + restart (editable install already present; the interpreter must be restarted): stop the uvicorn whose command line contains `accidents-lab`; `$env:PYTHONUTF8 = "1"; Start-Process -WorkingDirectory app app\.venv\Scripts\python.exe -ArgumentList "-m","uvicorn","api.main:app","--port","8000"`; `Invoke-RestMethod http://127.0.0.1:8000/api/modules` → `accidents` with 9 actions, `problems: []`.
6. Acceptance on the clone via the page's own route (`Run` helper from `docs/p1_design.md` §4) — API runs + PNG eyeballing list:
   - `segment_rates {}` → chart, note starts `מכנה: ק״מ-רכב`, basis has `coverage 19865/28213 (70.4%)`; `{order_by="count"; from_year=2019}` → row 0 road 70/120 = 176; PNG `c:\tmp\p2_segments.png`: bars with whiskers, six caveats, credit, stamp.
   - `severity_profile {by="age_group"}` → PNG `c:\tmp\p2_profile.png`: 100 % stacked bars, `5–9` label (not the Excel text), 2009 gap caveat first.
   - `vehicle_cells_ranking {metric="ksi"}` → PNG `c:\tmp\p2_cells.png`: two tiers with the break, global line, band-0 label honest; `{bands="known_engine"}` → 61 cells.
   - `before_after {}` (demo default) → PNG `c:\tmp\p2_before_after.png`: two panels, headline `יחס כפול 0.106`, site label `מחלף כיכר אדם → צומת כוכב יעקב`; `{site="road:2/21.9-24.0"; change_year=2011}` → headline ≈ 1.09; `{site="njunction:433"; change_year=2015}` → n/a or ratio with the junction label; `{change_year=2023}` → ❌ card.
   - `weather_check {}` → rows 56.8 / 3.7 / 7.8; `{rain_threshold_mm="0"}` → 67.0; PNG `c:\tmp\p2_weather.png`.
   - `triage {}` → ❌ card naming `vehicle_cells_ranking`; `{question="כמה הרוגים היו בכל שנה?"}` → 🧭 route card → `trend`.
   - `about {}` lists nine actions; `about` on `acme_insurance` still refuses.
   - Browser: 🧩 Modules → each action, each view; `git -C app status` clean.
7. `tools/find_demo_site.py --out docs/demo/sites.md`; commit the aggregates-only file.
8. Docs: `docs/plan.md` progress row P2 → done + `v0.2` + the deviations list (top of this plan) + "descriptive segment rate is plugin-defined"; `README.md` status → P2 + the nine actions; `CLAUDE.md` additions: units CTE + exact predicate + QUALIFY (one paragraph), site-key syntax and the network control, denominator labels per action, the n/a rule (`min_cell`, zero cells), the control flag (25 % relative), `EXPOSURE_YEARS`, `rain_threshold_mm` is a choice (number inputs keep int defaults), three markdown card shapes, "P2 writes nothing under the data dir"; `docs/PLAN_1_CONCEPT_MAP.md` corrections: coverage "~75 %, 55 % → 89 %" → "~72 % (units CTE), 55 % → 83 %, non-monotonic (dip 73 % in 2023)"; "no make/model exists in CBS data" → "the registry (fleet_by_model, vehicle_mileage) knows make/model, the accident files carry no plate/VIN/model code — no key connects them; finest linkable cell = manufacture_year × cc_band"; junction control "~23 %" → "5.6 % urban / 23.3 % non-urban (corrected 2026-08-30; the planning probe's 22/49 used another definition), damage-only junction coding collapsed 2010–2014 → data-driven control flag"; "BETWEEN or no QUALIFY double-counts ~25 %" → "raw table +31 % / +51 %; after the units CTE +0.4 % / +18.5 %"; "≈ 38 %" → "38.5 % overall, 0 % in 2017 → 77 % in 2024"; `cc_band` "8 bands incl. 0 = unknown engine"; `before_after` row: `change_year`, `min_cell`, control dropped, SE of the double ratio = plugin extension; `segment_rates` row: `order_by`, exposure-year refusal; `vehicle_cells_ranking` row: `bands` instead of `min_exposure_mkm`; `severity_profile` row: `sex`, coverage rule; `weather_check` row: threshold as a choice, the `לא ידוע` line; `docs/spikes.md` untouched; dossier §5.5 make/model wording (workspace level).
9. `git -C nl2sql-accidents-plugin add -A; commit -m "[P2] analytical tier: segment_rates, severity_profile, vehicle_cells_ranking, before_after, weather_check, triage"; tag v0.2`.

**Ultracode (only if the user says "ultracode" for P2):** (a) adversarial verification of every builder's emitted SQL (all `order_by` × `severity`, seven profile dimensions, three site kinds × windows, metric × bands, threshold values) against dossier §5.1–5.5 and the units/assignment recipe — series filter on the base table, composite key on every `involved` join, half-open predicate + QUALIFY, `any_value` on both multi-vintage tables, never `traffic_adt_filled`, no user text in SQL; (b) the DiD/Byar/EB arithmetic against the report formulas (Haldane SE, exp-CI, M = 200, quintile collapse) with independent recomputation; (c) generated edge-case tests for `parse_site_key`, the coverage rule with several uncovered years, `top_n` bounds, `min_cell`/zero cells; (d) caveat wording vs flags 1–8 (no `;`, most specific first, data-driven numbers match the spec fields).

---

### Critical Files for Implementation
- `c:\Users\A\dev\accidents-lab\nl2sql-accidents-plugin\nl2sql_accidents\sqlkit.py` (units CTE, assignment predicate, `byar_sql`, the six builders, site keys, DiD math)
- `c:\Users\A\dev\accidents-lab\nl2sql-accidents-plugin\nl2sql_accidents\envelope.py` (`denominator(**extra)`, `stamp`, `route_card`)
- `c:\Users\A\dev\accidents-lab\nl2sql-accidents-plugin\nl2sql_accidents\charts.py` (`hbars`, `stacked_bars`, `before_after_bars`, `tier_bars`)
- `c:\Users\A\dev\accidents-lab\nl2sql-accidents-plugin\nl2sql_accidents\actions\before_after.py` (the most rule-laden action; pattern from `actions\trend.py`)
- `c:\Users\A\dev\accidents-lab\nl2sql-accidents-plugin\tests\conftest.py` (the planted fixture in §5 — every expected number depends on it)