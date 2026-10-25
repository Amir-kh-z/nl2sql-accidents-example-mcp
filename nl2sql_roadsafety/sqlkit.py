# -*- coding: utf-8 -*-
"""SQL and input helpers shared by every action.

No bound parameters exist through the module contract, so the only things that ever reach SQL text
are: quoted identifiers (q), integers this code validated (ilit), floats this code computed (lit)
and string literals this code owns (slit). User input never reaches SQL unvalidated.
"""
from __future__ import annotations

import datetime as _dt
import math
import re
from dataclasses import dataclass
from decimal import Decimal


class ActionError(Exception):
    """A person's mistake (bad input). envelope.guard turns it into an error result: one sentence, no traceback."""


class Refusal(Exception):
    """What the data cannot answer → refusal card. `reason` is ONE Hebrew sentence (no newline: it is
    the note's head); `detail` is optional free text (English allowed) rendered as its own bullet in
    the card body only."""

    def __init__(self, reason: str, answerable=(), what_to_do: str | None = None,
                 detail: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.answerable = list(answerable)
        self.what_to_do = what_to_do
        self.detail = detail


DATA_YEARS = (2005, 2024)
DATA_END_HE = "31.12.2024"
CASE_FILTER = "case_type_code = 1"


def on_key(a: str = "a", i: str = "i") -> str:
    """The composite join key (dossier §5.3): accident_id alone collides across the two series."""
    return f"{a}.accident_id = {i}.accident_id AND {a}.case_type_code = {i}.case_type_code"


def q(ident) -> str:
    """One identifier, made safe to sit inside double quotes."""
    return '"' + str(ident).replace('"', '""') + '"'


def lit(v) -> str:
    """One float this code computed, as a SQL literal. Refuses non-finite values."""
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(f"non-finite value {v!r} cannot become a SQL literal")
    return repr(f)


def ilit(v) -> str:
    """One integer this code validated, as a SQL literal. Refuses bool and non-integers."""
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"{v!r} is not an int")
    return str(int(v))


def slit(s) -> str:
    """One string literal this code owns."""
    return "'" + str(s).replace("'", "''") + "'"


def as_int(v, name: str) -> int:
    """JSON number, float with no fraction, or numeric string ('2024', '2024.0') → int.
    bool / NaN / 'abc' / 2023.5 → ActionError naming the input."""
    if isinstance(v, bool):
        raise ActionError(f"{name} must be a whole number; got {v!r}.")
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        if math.isfinite(v) and v.is_integer():
            return int(v)
        raise ActionError(f"{name} must be a whole number; got {v!r}.")
    if isinstance(v, str):
        s = v.strip()
        try:
            return int(s)
        except ValueError:
            pass
        try:
            f = float(s)
        except ValueError:
            raise ActionError(f"{name} must be a whole number; got {v!r}.") from None
        if math.isfinite(f) and f.is_integer():
            return int(f)
    raise ActionError(f"{name} must be a whole number; got {v!r}.")


def as_choice(v, name: str, choices) -> str:
    """The server validates nothing: a choice value must be one of the declared choices."""
    s = str(v).strip() if v is not None else ""
    if s not in choices:
        raise ActionError(f"Unknown {name} {s!r}. One of: {', '.join(choices)}.")
    return s


def year_in_coverage(y: int, name: str) -> int:
    """Outside DATA_YEARS → a refusal card (what the data cannot answer). No clamping."""
    lo, hi = DATA_YEARS
    answerable = [f"כל שנה בין {lo} ל-{hi}"]
    if y > hi:
        raise Refusal(f"אין נתונים לשנת {y} — הנתונים מסתיימים ב-{DATA_END_HE}", answerable)
    if y < lo:
        raise Refusal(f"אין נתונים לשנת {y} — הנתונים מתחילים ב-{lo}", answerable)
    return y


def year_range(from_year, to_year) -> tuple[int, int]:
    y0 = as_int(from_year, "from_year")
    y1 = as_int(to_year, "to_year")
    if y0 > y1:
        raise ActionError(f"from_year ({y0}) is after to_year ({y1}) — swap them.")
    return year_in_coverage(y0, "from_year"), year_in_coverage(y1, "to_year")


def scalar(v):
    """A JSON-safe cell: Decimal→float, NaN/inf→None, numpy→.item(), date/time→str; bool/int/str kept."""
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, Decimal):
        v = float(v)
    if isinstance(v, (int, str)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, (_dt.date, _dt.datetime, _dt.time)):
        return v.isoformat()
    if hasattr(v, "item") and not isinstance(v, (bytes, bytearray)):
        try:
            return scalar(v.item())
        except Exception:  # noqa: BLE001 — not a numpy scalar after all
            pass
    return str(v)


def rows_safe(rows) -> list[list]:
    return [[scalar(c) for c in r] for r in rows]


def byar_ci(count, denom: float = 1.0, z: float = 1.96) -> tuple[float, float]:
    """Exact-style Poisson interval (Byar's approximation, no scipy) for a count, divided by denom."""
    n = float(count)
    if n < 0 or denom <= 0:
        raise ValueError("byar_ci needs count >= 0 and denom > 0")
    lower = 0.0 if n == 0 else n * (1 - 1 / (9 * n) - z / (3 * math.sqrt(n))) ** 3
    m = n + 1
    upper = m * (1 - 1 / (9 * m) + z / (3 * math.sqrt(m))) ** 3
    return lower / denom, upper / denom


# key: (grain table, value expression, Hebrew label) — PLAN_1 §4.1 order: it IS the dropdown order
# and the error-text order.
MEASURES = {
    "accidents":       ("accidents", "count(DISTINCT (a.accident_id, a.case_type_code))", "תאונות עם נפגעים"),
    "killed":          ("involved",  "count(*) FILTER (WHERE i.injury_severity_code = 1)", "הרוגים"),
    "severe_injured":  ("involved",  "count(*) FILTER (WHERE i.injury_severity_code = 2)", "פצועים קשה"),
    "slight_injured":  ("involved",  "count(*) FILTER (WHERE i.injury_severity_code = 3)", "פצועים קל"),
    "fatal_accidents": ("accidents", "count(DISTINCT (a.accident_id, a.case_type_code)) FILTER (WHERE a.severity_code = 1)", "תאונות קטלניות"),
}
GRANULARITY = {"year": "שנה", "month": "חודש"}
ROAD_TYPES = {
    "all":      ((), "כל הדרכים"),
    "urban":    ((1, 2), "דרכים עירוניות"),
    "nonurban": ((3, 4), "דרכים לא-עירוניות"),
}
# live: codes 1–4 only, both series, no NULLs. Any other code (dictionary: 5 = off-road) would count in
# "all" only — the road caveat is data-driven (other_road_sql), never an assertion about a code the
# data does not carry.


def other_road_sql(y0: int, y1: int) -> str:
    """One cheap count behind the road caveat (live: always 0)."""
    return (f"SELECT count(*) AS n FROM accidents\nWHERE case_type_code = 1\n"
            f"  AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"  AND (road_type_code IS NULL OR road_type_code NOT IN (1, 2, 3, 4))")


def build_trend_sql(measure: str, granularity: str, road_type: str, y0: int, y1: int) -> str:
    """Four switches: grain, value expression, period keys, road join + predicate.

    The series filter is written on the base table (never hidden in v_casualty_*); accidents are
    counted on the composite key; a calendar CTE zero-fills real zeros; person measures carry the
    coverage CTE (people >= casualty accidents per period, evaluated inside the casualty series on the
    composite key) and yield NULL — never 0 — where the person-level file is missing (involved 2009).
    """
    grain, expr, _ = MEASURES[measure]
    codes = ROAD_TYPES[road_type][0]
    monthly = granularity == "month"
    t = "i" if grain == "involved" else "a"

    def keys(al: str) -> str:
        return f"{al}.year" + (f", {al}.month" if monthly else "")

    road = (f"\n      AND a.road_type_code IN ({', '.join(ilit(c) for c in codes)})   -- {road_type}"
            if codes else "")
    head = (f"-- nl2sql-roadsafety-lab | trend | measure={measure} | granularity={granularity} "
            f"| road_type={road_type} | {y0}-{y1}\n")
    periods = (f"periods AS (\n    SELECT y AS year{', m AS month' if monthly else ''}\n"
               f"    FROM range({ilit(y0)}, {ilit(y1 + 1)}) t(y)"
               f"{', range(1, 13) u(m)' if monthly else ''}\n)")
    join = (f"\n    JOIN accidents a ON {on_key()}   -- composite key (dossier §5.3): involved has no road_type_code"
            if (grain == "involved" and codes) else "")
    counts = (f"counts AS (\n    SELECT {keys(t)},\n           {expr} AS value\n    FROM {grain} {t}{join}\n"
              f"    WHERE {t}.case_type_code = 1     -- casualty series only (dossier §5.1)\n"
              f"      AND {t}.year BETWEEN {ilit(y0)} AND {ilit(y1)}{road}\n    GROUP BY {keys(t)}\n)")
    on = "c.year = p.year" + (" AND c.month = p.month" if monthly else "")
    sel = keys("p")
    if grain == "accidents":
        return head + (f"WITH {periods},\n{counts}\n"
                       f"SELECT {sel}, coalesce(c.value, 0) AS {q(measure)}\n"
                       f"FROM periods p\nLEFT JOIN counts c ON {on}\nORDER BY {sel}")
    coverage = (f"coverage AS (                    -- person-level completeness per period (dossier §5.4; involved 2009 (case 1) = 15 rows)\n"
                f"    SELECT {keys('a')},\n"
                f"           count(DISTINCT (a.accident_id, a.case_type_code)) AS casualty_accidents,\n"
                f"           count(i.person_id) AS people\n"
                f"    FROM accidents a\n    LEFT JOIN involved i ON {on_key()}\n"
                f"    WHERE a.case_type_code = 1\n"
                f"      AND a.year BETWEEN {ilit(y0)} AND {ilit(y1)}{road}\n    GROUP BY {keys('a')}\n)")
    onc = "cv.year = p.year" + (" AND cv.month = p.month" if monthly else "")
    return head + (f"WITH {periods},\n{coverage},\n{counts}\n"
                   f"SELECT {sel},\n"
                   f"       CASE WHEN coalesce(cv.people, 0) >= coalesce(cv.casualty_accidents, 0) "
                   f"THEN coalesce(c.value, 0) END AS {q(measure)},\n"
                   f"       coalesce(cv.people, 0) AS people,\n"
                   f"       coalesce(cv.casualty_accidents, 0) AS casualty_accidents,\n"
                   f"       coalesce(cv.people, 0) >= coalesce(cv.casualty_accidents, 0) AS covered\n"
                   f"FROM periods p\nLEFT JOIN counts c ON {on}\nLEFT JOIN coverage cv ON {onc}\nORDER BY {sel}")


def trap_statements(year: int) -> dict[str, str]:
    """The three statements behind naive_vs_correct: naive, the same + one line, and the breakdown."""
    y = ilit(year)
    naive = (f"-- 1. naive — what a plain \"light accidents\" query does: the label alone, both series answer\n"
             f"SELECT count(*) AS n\nFROM accidents\nWHERE severity_label = 'קלה' AND year = {y}")
    correct = (f"-- 2. correct — the SAME statement plus one line: the casualty series only (dossier §5.1–5.2)\n"
               f"--    code canon equivalent: case_type_code = 1 AND severity_code = 3 (severity labels are drift-free 2005–2024)\n"
               f"SELECT count(*) AS n\nFROM accidents\nWHERE severity_label = 'קלה' AND year = {y}\n"
               f"  AND case_type_code = 1")
    breakdown = (f"-- 3. breakdown — both series by severity code: the arithmetic behind the gap\n"
                 f"SELECT case_type_code, severity_code, count(*) AS n\nFROM accidents\n"
                 f"WHERE year = {y}\nGROUP BY 1, 2\nORDER BY 1, 2")
    return {"naive": naive, "correct": correct, "breakdown": breakdown}


# ───────────────────────────── P2: analytical tier ─────────────────────────────

EXPOSURE_YEARS = (2017, 2024)        # traffic_adt_asof holds 2017-2024 only (live-asserted)
EB_M_MKM = 200.0                     # the report's EB prior weight, in million vehicle-km
MIN_CELL_DEFAULT = 6                 # plugin thinness rule (adapted from the report's change-detector threshold)
CONTROL_FLAG_REL = 0.25              # coded-share relative change that flags the damage-only control


def as_float(v, name: str) -> float:
    """int / float / numeric string → float; refuses bool, NaN, inf, text."""
    if isinstance(v, bool):
        raise ActionError(f"{name} must be a number; got {v!r}.")
    try:
        f = float(str(v).strip()) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        raise ActionError(f"{name} must be a number; got {v!r}.") from None
    if not math.isfinite(f):
        raise ActionError(f"{name} must be a finite number; got {v!r}.")
    return f


def exposure_year_range(from_year, to_year) -> tuple[int, int]:
    """Like year_range, but against the as-of exposure layer (2017-2024)."""
    y0 = as_int(from_year, "from_year")
    y1 = as_int(to_year, "to_year")
    if y0 > y1:
        raise ActionError(f"from_year ({y0}) is after to_year ({y1}) — swap them.")
    lo, hi = EXPOSURE_YEARS
    for y in (y0, y1):
        if y < lo or y > hi:
            raise Refusal(f"אין נתוני תנועה (as-of) לשנת {y} — שכבת החשיפה מכסה {lo} עד {hi}",
                          [f"כל שנה בין {lo} ל-{hi}"])
    return y0, y1


def byar_sql(count_expr: str, z: float = 1.96) -> tuple[str, str]:
    """Byar's Poisson interval as SQL expressions over a count expression (matches byar_ci)."""
    n = f"({count_expr})"
    zz = lit(z)
    lo = (f"CASE WHEN {n} = 0 THEN 0.0 ELSE {n} * power(1 - 1.0 / (9 * {n}) - {zz} / (3 * sqrt({n})), 3) END")
    hi = f"({n} + 1) * power(1 - 1.0 / (9 * ({n} + 1)) + {zz} / (3 * sqrt({n} + 1)), 3)"
    return lo, hi


UNITS_CTE = """units AS (                      -- one geometry vintage per segment-year (PLAN_1 'Segment unit')
    SELECT CAST(road AS INTEGER) AS road, CAST(seg AS INTEGER) AS seg,   -- typed keys: DuckDB 1.5.0 mis-binds QUALIFY over an implicit-cast join
           year, km_from, km_to, adt_asof, based_on_year, gap_years
    FROM traffic_adt_asof
    QUALIFY row_number() OVER (PARTITION BY road, seg, year ORDER BY gap_years, km_to - km_from) = 1
)"""
_ASSIGN_ON = ("ON a.road1_number = u.road\n     AND a.road_km <> 0\n"                     # km 0 = not coded (same rule as the control's coded share)
              "     AND a.road_km / 10.0 >= u.km_from\n"
              "     AND a.road_km / 10.0 <  u.km_to\n     AND a.year = u.year")             # half-open, the view's predicate


def assign_join(table: str = "units") -> str:
    """The assignment join over any relation exposing road, seg, year, km_from, km_to, gap_years — always alias
    `u`, so ASSIGN_QUALIFY applies verbatim (segment_rates joins `units`, hotspot_map joins `geom`)."""
    return f"JOIN {table} u\n      {_ASSIGN_ON}"


ASSIGN_JOIN = assign_join()
ASSIGN_QUALIFY = ("QUALIFY row_number() OVER (PARTITION BY a.accident_id, a.case_type_code "
                  "ORDER BY u.gap_years, u.km_to - u.km_from) = 1")                        # one row per accident
NAMES_CTE = """names AS (                            -- traffic_segments: several vintages per key — one name pair
    SELECT CAST(road AS INTEGER) AS road, CAST(seg AS INTEGER) AS seg,
           arg_max(name_from, src_year) AS name_from, arg_max(name_to, src_year) AS name_to   -- latest vintage
    FROM traffic_segments GROUP BY road, seg
)"""


def units_count_sql() -> str:
    return f"WITH {UNITS_CTE}\nSELECT count(*) AS units, count(DISTINCT (road, seg)) AS segments FROM units"


def coverage_cte(y0: int, y1: int) -> str:
    """Person-level completeness per year, inside the casualty series on the composite key (involved 2009)."""
    return (f"coverage AS (                    -- person-level completeness per year (dossier §5.4; involved 2009 (case 1) = 15 rows)\n"
            f"    SELECT a.year,\n"
            f"           count(DISTINCT (a.accident_id, a.case_type_code)) AS casualty_accidents,\n"
            f"           count(i.person_id) AS people\n"
            f"    FROM accidents a\n    LEFT JOIN involved i ON {on_key()}\n"
            f"    WHERE a.case_type_code = 1\n"
            f"      AND a.year BETWEEN {ilit(y0)} AND {ilit(y1)}\n    GROUP BY a.year\n)")


def coverage_years_sql(y0: int, y1: int) -> str:
    return (f"-- nl2sql-roadsafety-lab | coverage | {y0}-{y1}\nWITH {coverage_cte(y0, y1)}\n"
            f"SELECT year, casualty_accidents, people, people >= casualty_accidents AS covered\n"
            f"FROM coverage ORDER BY year")


def _segment_base_ctes(y0: int, y1: int, road: int = 0) -> str:
    road_filter = f"\n      AND road1_number = {ilit(road)}" if road else ""
    return (f"{UNITS_CTE},\n"
            f"base AS (                             -- casualty series, interurban, requested years (dossier 5.1)\n"
            f"    SELECT accident_id, case_type_code, year, road1_number, road_km, severity_code\n"
            f"    FROM accidents\n"
            f"    WHERE case_type_code = 1\n"
            f"      AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"      AND road_type_code IN (3, 4){road_filter}\n"
            f"),\n"
            f"matched AS (                          -- exact assignment predicate: half-open km, one row per accident\n"
            f"    SELECT a.accident_id, a.case_type_code, a.severity_code, u.road, u.seg, u.year\n"
            f"    FROM base a\n    {ASSIGN_JOIN}\n    {ASSIGN_QUALIFY}\n)")


SEGMENT_ORDERS = {
    "rate_lo": "rate_lo DESC, rate_per_100m_vkm DESC, road, seg",
    "rate": "rate_per_100m_vkm DESC, accidents DESC, road, seg",
    "count": "{metric} DESC, rate_per_100m_vkm DESC, road, seg",
}
SEGMENT_SEVERITY = {"all": "accidents", "ksi": "ksi_accidents"}


def build_segment_rates_sql(road: int, y0: int, y1: int, severity: str, order_by: str, top_n: int) -> str:
    """Casualty accidents per 100 M vehicle-km per traffic count segment — numerator and denominator over the
    SAME units CTE; a plugin-defined descriptive instrument (the report has no per-vkm rate)."""
    metric = SEGMENT_SEVERITY[severity]
    lo, hi = byar_sql(f"coalesce(m.{metric}, 0)")
    order = SEGMENT_ORDERS[order_by].format(metric=metric)
    road_filter = f"\n  AND d.road = {ilit(road)}" if road else ""
    return (f"-- nl2sql-roadsafety-lab | segment_rates | road={road or 'all'} | severity={severity} | order={order_by} "
            f"| {y0}-{y1} | top {top_n}\n"
            f"WITH {_segment_base_ctes(y0, y1, road)},\n"
            f"num AS (\n"
            f"    SELECT road, seg, count(*) AS accidents,\n"
            f"           count(*) FILTER (WHERE severity_code IN (1, 2)) AS ksi_accidents,\n"
            f"           count(DISTINCT year) AS accident_years\n"
            f"    FROM matched GROUP BY road, seg\n"
            f"),\n"
            f"den AS (                              -- vehicle-km over the SAME units CTE (both sides share it)\n"
            f"    SELECT road, seg, sum(adt_asof * (km_to - km_from) * 365) AS vkm, count(*) AS unit_years,\n"
            f"           min(km_from) AS km_from, max(km_to) AS km_to, max(gap_years) AS max_gap_years\n"
            f"    FROM units WHERE year BETWEEN {ilit(y0)} AND {ilit(y1)} GROUP BY road, seg\n"
            f"),\n"
            f"{NAMES_CTE}\n"
            f"SELECT d.road, d.seg, n.name_from, n.name_to,\n"
            f"       d.km_from, d.km_to,\n"
            f"       coalesce(m.accidents, 0) AS accidents, coalesce(m.ksi_accidents, 0) AS ksi_accidents,\n"
            f"       coalesce(m.accident_years, 0) AS accident_years, d.unit_years,\n"
            f"       round(d.vkm / 1e6, 1) AS vkm_millions,\n"
            f"       round(coalesce(m.{metric}, 0) / (d.vkm / 1e8), 2) AS rate_per_100m_vkm,\n"
            f"       round(({lo}) / (d.vkm / 1e8), 2) AS rate_lo,\n"
            f"       round(({hi}) / (d.vkm / 1e8), 2) AS rate_hi,\n"
            f"       d.max_gap_years\n"
            f"FROM den d\n"
            f"LEFT JOIN num m USING (road, seg)\n"
            f"LEFT JOIN names n USING (road, seg)\n"
            f"WHERE d.vkm > 0{road_filter}\n"
            f"ORDER BY {order}\n"
            f"LIMIT {ilit(top_n)}")


def segment_coverage_sql(y0: int, y1: int, road: int = 0) -> str:
    """Per-year share of interurban casualty accidents (of the road when one is chosen) that the units CTE can locate."""
    return (f"-- nl2sql-roadsafety-lab | segment_rates coverage | road={road or 'all'} | {y0}-{y1}\n"
            f"WITH {_segment_base_ctes(y0, y1, road)}\n"
            f"SELECT b.year, count(*) AS interurban_casualty, count(m.accident_id) AS matched,\n"
            f"       round(100.0 * count(m.accident_id) / count(*), 1) AS pct\n"
            f"FROM base b\n"
            f"LEFT JOIN matched m ON m.accident_id = b.accident_id AND m.case_type_code = b.case_type_code\n"
            f"GROUP BY b.year ORDER BY b.year")


def segment_count_sql(road: int, y0: int, y1: int) -> str:
    road_filter = f" AND road = {ilit(road)}" if road else ""
    return (f"WITH {UNITS_CTE}\nSELECT count(DISTINCT (road, seg)) AS segments, count(DISTINCT road) AS roads\n"
            f"FROM units WHERE year BETWEEN {ilit(y0)} AND {ilit(y1)}{road_filter}")


# ── severity profile ──
AGE_GROUPS = {1: "0–4", 2: "5–9", 3: "10–14", 4: "15–19", 5: "20–24", 6: "25–29", 7: "30–34", 8: "35–39",
              9: "40–44", 10: "45–49", 11: "50–54", 12: "55–59", 13: "60–64", 14: "65–69", 15: "70–74",
              16: "75–79", 17: "80–84", 18: "85+", 99: "לא ידוע"}
AGE_CASE = ("CASE i.age_group_code " + " ".join(f"WHEN {ilit(k)} THEN {slit(v)}" for k, v in AGE_GROUPS.items())
            + " ELSE 'קוד ' || CAST(i.age_group_code AS VARCHAR) END")
PEDESTRIAN_LABEL = "הולך רגל — ללא רכב"
# P13 hour buckets: 24 hourly categories drown a 100% stacked bar — the four standard ranges instead.
# hour_of_day is complete on the live copy (0-23, no NULL, no sentinel, both series — probed 2026-09-06);
# the ELSE bucket still catches a NULL/sentinel hour as 'לא ידוע' (key 9 sorts last) rather than dropping it.
HOUR_BUCKET_LABELS = {1: "בוקר (6–11)", 2: "צהריים (12–17)", 3: "ערב (18–23)", 4: "לילה (0–5)", 9: "לא ידוע"}
HOUR_BUCKET_KEY = ("CASE WHEN a.hour_of_day BETWEEN 6 AND 11 THEN 1 "
                   "WHEN a.hour_of_day BETWEEN 12 AND 17 THEN 2 "
                   "WHEN a.hour_of_day BETWEEN 18 AND 23 THEN 3 "
                   "WHEN a.hour_of_day BETWEEN 0 AND 5 THEN 4 ELSE 9 END")
HOUR_BUCKET_CASE = ("CASE code " + " ".join(f"WHEN {ilit(k)} THEN {slit(v)}" for k, v in HOUR_BUCKET_LABELS.items())
                    + " END")
# Speed-limit sentinels: live carries ONLY code 0 = 'לא ידוע' (24,282 casualty rows, probed 2026-09-06); the
# severity matrix (studio/severity.py) already NULLs the (0, 9, 99, 999) family — the SAME family folds into the
# 'לא ידוע' bucket here, never silently dropped.
SPEED_SENTINEL_KEY = ("CASE WHEN coalesce(a.speed_limit_code, 0) IN (0, 9, 99, 999) THEN 0 "
                      "ELSE a.speed_limit_code END")
# key: (key_expr, label_raw_expr, label_agg_expr, needs_accidents_join, Hebrew label)
PROFILE_DIMS = {
    "casualty_type":         ("i.casualty_type_code", "i.casualty_type_label", "any_value(label_raw)", False, "סוג נפגע"),
    "road_type":             ("a.road_type_code", "a.road_type_label", "any_value(label_raw)", True, "סוג דרך"),
    "day_night":             ("a.day_night_code", "a.day_night_label", "any_value(label_raw)", True, "יום ולילה"),
    "age_group":             ("i.age_group_code", AGE_CASE, "any_value(label_raw)", False, "קבוצת גיל"),
    "weather":               ("a.weather_code", "a.weather_label", "any_value(label_raw)", True, "מזג אוויר (דיווח שוטר)"),
    "involved_vehicle_type": ("CASE WHEN i.casualty_type_code = 1 THEN -1 ELSE coalesce(i.involved_vehicle_type_code, 0) END",
                              "i.involved_vehicle_type_label",
                              f"CASE WHEN code = -1 THEN {slit(PEDESTRIAN_LABEL)} ELSE coalesce(any_value(label_raw), 'לא ידוע') END",
                              False, "סוג הרכב של הנפגע"),
    "sex":                   ("i.sex_code", "i.sex_label", "any_value(label_raw)", False, "מין"),
    # P13 accident-attribute dims: the pre-joined *_label columns (dossier rule), NULL label → 'לא ידוע'
    "lighting":              ("a.light_code", "a.light_label", "coalesce(any_value(label_raw), 'לא ידוע')",
                              True, "תאורה"),
    "hour_of_day":           (HOUR_BUCKET_KEY, "NULL", HOUR_BUCKET_CASE, True, "שעה ביום"),
    "day_of_week":           ("a.day_of_week", "a.day_of_week_label", "coalesce(any_value(label_raw), 'לא ידוע')",
                              True, "יום בשבוע"),
    "speed_limit":           (SPEED_SENTINEL_KEY, "a.speed_limit_label",
                              "CASE WHEN code = 0 THEN 'לא ידוע' ELSE coalesce(any_value(label_raw), 'לא ידוע') END",
                              True, "מהירות מותרת"),
    # road_shape code 9 'אחר' is the 2011 coding-change trap (dossier §12) — kept as its own category,
    # the action computes its share for the selected range into a caveat
    "road_shape":            ("a.road_shape_code", "a.road_shape_label", "coalesce(any_value(label_raw), 'לא ידוע')",
                              True, "צורת דרך"),
    # P11: the share-drift exhibit — severity composition per year (chronological, not by size)
    "year":                  ("i.year", "CAST(i.year AS VARCHAR)", "any_value(label_raw)", False, "שנה"),
}
PROFILE_CHRONOLOGICAL = ("year", "day_of_week", "hour_of_day")   # time-like axes read in code order


def build_severity_profile_sql(by: str, y0: int, y1: int) -> str:
    key_expr, label_raw, label_agg, needs_join, _ = PROFILE_DIMS[by]
    join = (f"\n    JOIN accidents a ON {on_key()}   -- composite key (dossier §5.3)" if needs_join else "")
    order = "code" if by in PROFILE_CHRONOLOGICAL else "casualties DESC, code"   # a time axis reads chronologically
    return (f"-- nl2sql-roadsafety-lab | severity_profile | by={by} | {y0}-{y1}\n"
            f"WITH {coverage_cte(y0, y1)},\n"
            f"people AS (\n"
            f"    SELECT {key_expr} AS code, {label_raw} AS label_raw, i.injury_severity_code\n"
            f"    FROM involved i{join}\n"
            f"    WHERE i.case_type_code = 1\n"
            f"      AND i.injury_severity_code IN (1, 2, 3)       -- casualties only (0 = uninjured)\n"
            f"      AND i.year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"      AND i.year IN (SELECT year FROM coverage WHERE people >= casualty_accidents)\n"
            f"),\n"
            f"grouped AS (\n"
            f"    SELECT code, {label_agg} AS label, count(*) AS casualties,\n"
            f"           count(*) FILTER (WHERE injury_severity_code = 1) AS killed,\n"
            f"           count(*) FILTER (WHERE injury_severity_code = 2) AS severe,\n"
            f"           count(*) FILTER (WHERE injury_severity_code = 3) AS slight\n"
            f"    FROM people GROUP BY code\n"
            f")\n"
            f"SELECT code, label, casualties, killed, severe, slight,\n"
            f"       round(100.0 * casualties / sum(casualties) OVER (), 1) AS share_pct,\n"
            f"       round(100.0 * killed / casualties, 2) AS killed_pct,\n"
            f"       round(100.0 * severe / casualties, 2) AS severe_pct,\n"
            f"       round(100.0 * slight / casualties, 2) AS slight_pct\n"
            f"FROM grouped ORDER BY {order}")


# ── vehicle cells ──
CELL_METRICS = {"involvements": ("involvements", "מעורבויות"), "ksi": ("ksi_involvements", "מעורבויות קשות וקטלניות (KSI)"),
                "fatal": ("fatal_involvements", "מעורבויות קטלניות")}
CC_BANDS = {0: "חשמלי/ללא נפח (קוד 0)", 4: "501–1000", 5: "1001–1300", 6: "1301–1600", 7: "1601–1800",
            8: "1801–2000", 9: "2001–3000", 10: "3001–4000"}
CC_BAND_CASE = ("CASE cc_band " + " ".join(f"WHEN {ilit(k)} THEN {slit(v)}" for k, v in CC_BANDS.items())
                + " ELSE 'קוד ' || CAST(cc_band AS VARCHAR) END")


def build_vehicle_cells_sql(metric: str, bands: str) -> str:
    col = CELL_METRICS[metric][0]
    band_filter = "\n      AND cc_band <> 0" if bands == "known_engine" else ""
    return (f"-- nl2sql-roadsafety-lab | vehicle_cells_ranking | metric={metric} | bands={bands} | M={EB_M_MKM:g} Mkm\n"
            f"WITH cells AS (                       -- exposure > 0 only: model years without odometer history are excluded\n"
            f"    SELECT manufacture_year, cc_band, fleet, exposure_mkm, mean_annual_km, ev_share,\n"
            f"           involvements, ksi_involvements, fatal_involvements, {col} AS events\n"
            f"    FROM vehicle_cells\n"
            f"    WHERE coalesce(exposure_mkm, 0) > 0{band_filter}\n"
            f"),\n"
            f"prior AS (SELECT sum(events) / sum(exposure_mkm) AS global_rate, {lit(EB_M_MKM)} AS m_mkm FROM cells),\n"
            f"eb AS (\n"
            f"    SELECT c.*, p.global_rate, p.m_mkm,\n"
            f"           c.events / c.exposure_mkm AS raw_rate,\n"
            f"           (c.events + p.m_mkm * p.global_rate) / (c.exposure_mkm + p.m_mkm) AS eb_rate,     -- the report's EB formula\n"
            f"           c.exposure_mkm / (c.exposure_mkm + p.m_mkm) AS weight_on_data\n"
            f"    FROM cells c CROSS JOIN prior p\n"
            f"),\n"
            f"ranked AS (\n"
            f"    SELECT *, ntile(5) OVER (ORDER BY eb_rate, manufacture_year, cc_band) AS quintile,\n"
            f"           count(*) OVER () AS n_cells\n"
            f"    FROM eb\n"
            f")\n"
            f"SELECT manufacture_year, cc_band, {CC_BAND_CASE} AS cc_band_label,\n"
            f"       fleet, round(exposure_mkm, 1) AS exposure_mkm, events,\n"
            f"       round(raw_rate, 4) AS raw_rate_per_mkm, round(eb_rate, 4) AS eb_rate_per_mkm,\n"
            f"       round(global_rate, 5) AS global_rate_per_mkm, round(weight_on_data, 3) AS weight_on_data,\n"
            f"       quintile,\n"
            f"       CASE WHEN quintile = 1 THEN 'safest' WHEN quintile = 5 THEN 'highest_risk' ELSE 'regular' END AS tier,\n"
            f"       n_cells, ev_share\n"
            f"FROM ranked ORDER BY eb_rate, manufacture_year, cc_band")


def build_vehicle_cells_cohort_sql(metric: str, bands: str) -> str:
    """P13 cohort roll-up: the SAME cube summed over cc_band per manufacture_year — events and exposure_mkm are
    real per-cell sums (never fleet × years), then the report's EB formula on the cohort cells. The prior's
    global rate is over the included cells, so it equals the cell-mode prior for the same `bands`."""
    col = CELL_METRICS[metric][0]
    band_filter = "\n      AND cc_band <> 0" if bands == "known_engine" else ""
    return (f"-- nl2sql-roadsafety-lab | vehicle_cells_ranking | group=cohort | metric={metric} | bands={bands} "
            f"| M={EB_M_MKM:g} Mkm\n"
            f"WITH cells AS (                       -- exposure > 0 only: model years without odometer history are excluded\n"
            f"    SELECT manufacture_year, exposure_mkm, {col} AS events\n"
            f"    FROM vehicle_cells\n"
            f"    WHERE coalesce(exposure_mkm, 0) > 0{band_filter}\n"
            f"),\n"
            f"cohorts AS (                          -- sum the cube's REAL per-cell exposure, never fleet x years\n"
            f"    SELECT manufacture_year, sum(events) AS events, sum(exposure_mkm) AS exposure_mkm\n"
            f"    FROM cells GROUP BY manufacture_year\n"
            f"),\n"
            f"prior AS (SELECT sum(events) / sum(exposure_mkm) AS global_rate, {lit(EB_M_MKM)} AS m_mkm FROM cells),\n"
            f"eb AS (\n"
            f"    SELECT c.*, p.global_rate,\n"
            f"           c.events / c.exposure_mkm AS raw_rate,\n"
            f"           (c.events + p.m_mkm * p.global_rate) / (c.exposure_mkm + p.m_mkm) AS eb_rate     -- the report's EB formula\n"
            f"    FROM cohorts c CROSS JOIN prior p\n"
            f"),\n"
            f"ranked AS (SELECT *, ntile(5) OVER (ORDER BY eb_rate, manufacture_year) AS quintile FROM eb)\n"
            f"SELECT manufacture_year, events AS involvements, round(exposure_mkm, 1) AS exposure_mkm,\n"
            f"       round(raw_rate, 4) AS rate, round(eb_rate, 4) AS eb_rate,\n"
            f"       CASE WHEN quintile = 1 THEN 'safest' WHEN quintile = 5 THEN 'highest_risk' ELSE 'regular' END AS tier\n"
            f"FROM ranked ORDER BY manufacture_year")


def vehicle_cells_excluded_sql() -> str:
    """Cells outside the ranking: exposure 0 (always) and band 0 with exposure (dropped only by bands=known_engine)."""
    return ("-- nl2sql-roadsafety-lab | vehicle_cells_ranking | cells outside the ranking\n"
            "SELECT count(*) FILTER (WHERE NOT (coalesce(exposure_mkm, 0) > 0)) AS cells,\n"
            "       coalesce(sum(fleet) FILTER (WHERE NOT (coalesce(exposure_mkm, 0) > 0)), 0) AS fleet,\n"
            "       min(manufacture_year) FILTER (WHERE NOT (coalesce(exposure_mkm, 0) > 0)) AS y0,\n"
            "       max(manufacture_year) FILTER (WHERE NOT (coalesce(exposure_mkm, 0) > 0)) AS y1,\n"
            "       count(*) FILTER (WHERE coalesce(exposure_mkm, 0) > 0 AND cc_band = 0) AS band0_cells,\n"
            "       coalesce(sum(fleet) FILTER (WHERE coalesce(exposure_mkm, 0) > 0 AND cc_band = 0), 0) AS band0_fleet,\n"
            "       sum(fleet) AS fleet_all\n"
            "FROM vehicle_cells")


# ── before/after (Double-DiD) ──
_ROAD_KEY = re.compile(r"^road:(\d+)/(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$")
_NJ_KEY = re.compile(r"^njunction:(\d+)$")
_UJ_KEY = re.compile(r"^ujunction:(\d+)/(\d+)$")
SITE_FORMS = "road:<n>/<km_from>-<km_to>, njunction:<code> or ujunction:<city_code>/<code>"
# Junction-code sentinels: 0 / 99 / 9999 (dossier) and 99999999 = "unknown junction" (live: 556 casualty accidents
# in 82 cities, no dim_junction_urban row — found by the P3 sweep). ONE rule for the map, the coverage, the control
# and the key parser.
JUNCTION_SENTINEL_CODES = (0, 99, 9999, 99999999)
JUNCTION_SENTINELS = "(" + ", ".join(str(c) for c in JUNCTION_SENTINEL_CODES) + ")"
UJ_NAMES_CTE = """ujnames AS (                        -- one deterministic (city, street pair) per urban junction key over ALL accidents (both series):
    SELECT city_code AS city, urban_junction_code AS code, min(city_name) AS city_name,           -- the lexicographically smallest pair,
           arg_min(street1_name, (coalesce(street1_name, ''), coalesce(street2_name, ''))) AS street1_name,   -- taken from ONE row (the police
           arg_min(street2_name, (coalesce(street1_name, ''), coalesce(street2_name, ''))) AS street2_name    -- record the pair in either order)
    FROM accidents
    WHERE urban_junction_code IS NOT NULL AND urban_junction_code NOT IN (0, 99, 9999, 99999999) AND coalesce(city_code, 0) > 0
    GROUP BY city_code, urban_junction_code
)"""


@dataclass(frozen=True)
class Site:
    kind: str
    key: str
    road: int | None = None
    km_from: float | None = None
    km_to: float | None = None
    code: int | None = None
    city: int | None = None


def parse_site_key(s) -> Site:
    key = str(s or "").strip()
    m = _ROAD_KEY.match(key)
    if m:
        road, k0, k1 = int(m.group(1)), float(m.group(2)), float(m.group(3))
        if road < 1:
            raise ActionError(f"road number must be >= 1; got {key!r}.")
        if not k0 < k1:
            raise ActionError(f"km_from ({m.group(2)}) is not below km_to ({m.group(3)}) - swap them.")
        return Site("road", key, road=road, km_from=k0, km_to=k1)
    m = _NJ_KEY.match(key)
    if m:
        code = int(m.group(1))
        if code < 1 or code in JUNCTION_SENTINEL_CODES:
            raise ActionError(f"junction code must be a real code (not 0/99/9999/99999999); got {key!r}.")
        return Site("njunction", key, code=code)
    m = _UJ_KEY.match(key)
    if m:
        city, code = int(m.group(1)), int(m.group(2))
        if code < 1 or code in JUNCTION_SENTINEL_CODES or city < 1:
            raise ActionError(f"junction code must be a real code (not 0/99/9999/99999999); got {key!r}.")
        return Site("ujunction", key, code=code, city=city)
    raise ActionError(f"site must be {SITE_FORMS}; got {key!r}.")


def site_predicate(site: Site) -> str:
    if site.kind == "road":
        return (f"road1_number = {ilit(site.road)} AND road_km <> 0 AND road_km / 10.0 >= {lit(site.km_from)} "
                f"AND road_km / 10.0 < {lit(site.km_to)}")           # km 0 = not coded, as in site_coding_exprs
    if site.kind == "njunction":
        return f"nonurban_junction_code = {ilit(site.code)}"
    return f"city_code = {ilit(site.city)} AND urban_junction_code = {ilit(site.code)}"


def site_coding_exprs(site: Site) -> tuple[str, str]:
    """(coded, base) predicates for the damage-only control's location coding share."""
    if site.kind == "road":
        return ("road_type_code IN (3, 4) AND road_km IS NOT NULL AND road_km <> 0", "road_type_code IN (3, 4)")
    if site.kind == "njunction":
        return (f"road_type_code IN (3, 4) AND nonurban_junction_code IS NOT NULL AND nonurban_junction_code NOT IN {JUNCTION_SENTINELS}",
                "road_type_code IN (3, 4)")
    return (f"road_type_code IN (1, 2) AND urban_junction_code IS NOT NULL AND urban_junction_code NOT IN {JUNCTION_SENTINELS}",
            "road_type_code IN (1, 2)")


def site_label_sql(site: Site) -> str:
    if site.kind == "road":
        k0, k1 = lit(site.km_from), lit(site.km_to)
        return (f"SELECT name_from, name_to, km_from, km_to FROM traffic_segments\n"
                f"WHERE road = {ilit(site.road)} AND km_from < {k1} AND km_to > {k0}\n"
                f"ORDER BY (least(km_to, {k1}) - greatest(km_from, {k0})) DESC, src_year DESC LIMIT 1")
    if site.kind == "njunction":
        c = ilit(site.code)
        return (f"SELECT coalesce((SELECT min(junction_name) FROM dim_junction_nonurban WHERE junction_code = {c}),\n"
                f"                (SELECT min(nonurban_junction_name) FROM accidents WHERE nonurban_junction_code = {c})) AS label")
    return (f"WITH {UJ_NAMES_CTE}\n"                  # the same pair rule as hotspot_map, so the hand-off label matches
            f"SELECT city_name AS city, street1_name AS street1, street2_name AS street2\n"
            f"FROM ujnames WHERE city = {ilit(site.city)} AND code = {ilit(site.code)}")


def build_before_after_sql(site: Site, cy: int, w: int) -> str:
    b0, b1, a0, a1 = cy - w, cy - 1, cy + 1, cy + w
    coded, coded_base = site_coding_exprs(site)
    return (f"-- nl2sql-roadsafety-lab | before_after | site={site.key} | change {cy} | window {w} | control=network\n"
            f"WITH win AS (                         -- both series, the two windows, change year excluded\n"
            f"    SELECT case_type_code, year,\n"
            f"           CASE WHEN year BETWEEN {ilit(b0)} AND {ilit(b1)} THEN 'before'\n"
            f"                WHEN year BETWEEN {ilit(a0)} AND {ilit(a1)} THEN 'after' END AS period,\n"
            f"           ({site_predicate(site)}) AS at_site,\n"
            f"           ({coded}) AS is_coded,\n"
            f"           ({coded_base}) AS is_coded_base\n"
            f"    FROM accidents\n"
            f"    WHERE case_type_code IN (1, 3)\n"
            f"      AND (year BETWEEN {ilit(b0)} AND {ilit(b1)} OR year BETWEEN {ilit(a0)} AND {ilit(a1)})\n"
            f")\n"
            f"SELECT case_type_code AS series, period,\n"
            f"       count(*) FILTER (WHERE at_site) AS site,\n"
            f"       count(*) AS network,                                             -- the whole national network of the series\n"
            f"       count(*) FILTER (WHERE is_coded) AS coded,                       -- location coding of the control\n"
            f"       count(*) FILTER (WHERE is_coded_base) AS coded_base\n"
            f"FROM win\n"
            f"GROUP BY 1, 2\n"
            f"ORDER BY 1, period DESC")


def did_math(site_before, site_after, net_before, net_after, min_cell: int) -> dict:
    """DiD ratio = (site_after/site_before) / (net_after/net_before); SE² = Σ 1/(n+½) (Haldane);
    CI = exp(ln r ± 1.96·SE). Thin cells → n/a: any site count below max(min_cell, 1), or a zero network count."""
    counts = [int(site_before), int(site_after), int(net_before), int(net_after)]
    need = max(int(min_cell), 1)
    if counts[0] < need or counts[1] < need or counts[2] == 0 or counts[3] == 0:
        return {"ratio": None, "se2": None, "lo": None, "hi": None, "status": "n/a"}
    ratio = (counts[1] / counts[0]) / (counts[3] / counts[2])
    se2 = sum(1.0 / (c + 0.5) for c in counts)
    se = math.sqrt(se2)
    return {"ratio": ratio, "se2": se2, "lo": ratio * math.exp(-1.96 * se), "hi": ratio * math.exp(1.96 * se),
            "status": "ok"}


def double_did(cas: dict, dmg: dict) -> dict:
    """Double DiD = DiD(casualty) / DiD(damage-only); SE² = SE²_cas + SE²_dmg (plugin extension — the report
    gives no SE for the double ratio)."""
    if cas["status"] != "ok" or dmg["status"] != "ok" or not dmg["ratio"]:
        return {"ratio": None, "se2": None, "lo": None, "hi": None, "status": "n/a"}
    ratio = cas["ratio"] / dmg["ratio"]
    se2 = cas["se2"] + dmg["se2"]
    se = math.sqrt(se2)
    return {"ratio": ratio, "se2": se2, "lo": ratio * math.exp(-1.96 * se), "hi": ratio * math.exp(1.96 * se),
            "status": "ok"}


def control_flag(before_share, after_share) -> bool:
    """True when the damage-only control's location-coding share moved > CONTROL_FLAG_REL relative."""
    if before_share is None or before_share == 0:
        return bool(after_share)
    if after_share is None:
        return True
    return abs(after_share - before_share) / before_share > CONTROL_FLAG_REL


# ── weather ──
WEATHER_THRESHOLDS = ("0.1", "0", "0.5", "1")


def build_weather_check_sql(y0: int, y1: int, thr: float) -> str:
    t = lit(thr)
    return (f"-- nl2sql-roadsafety-lab | weather_check | threshold {thr:g} mm | {y0}-{y1}\n"
            f"WITH w AS (                           -- v_accidents_weather: LEFT JOIN on (cell, hour) — precipitation IS NOT NULL is the filter\n"
            f"    SELECT cbs_weather_label, precipitation_mm, temperature_c\n"
            f"    FROM v_accidents_weather\n"
            f"    WHERE case_type_code = 1\n"
            f"      AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"      AND precipitation_mm IS NOT NULL\n"
            f")\n"
            f"SELECT coalesce(cbs_weather_label, 'ללא תווית') AS cbs_weather_label,\n"
            f"       count(*) AS accidents,\n"
            f"       count(*) FILTER (WHERE precipitation_mm > {t}) AS rainy_measured,\n"
            f"       round(100.0 * count(*) FILTER (WHERE precipitation_mm > {t}) / count(*), 1) AS pct_measured_rain,\n"
            f"       round(median(temperature_c), 1) AS median_temp_c,\n"
            f"       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct,\n"
            f"       round(100.0 * count(*) FILTER (WHERE precipitation_mm > 0) / count(*), 1) AS pct_any_rain\n"
            f"FROM w\n"
            f"GROUP BY 1\n"
            f"ORDER BY accidents DESC, 1")


def weather_coverage_sql(y0: int, y1: int) -> str:
    return (f"-- nl2sql-roadsafety-lab | weather_check coverage | {y0}-{y1}\n"
            f"SELECT year, count(*) AS casualty_accidents, count(*) FILTER (WHERE weather_cell_id IS NULL) AS without_cell\n"
            f"FROM accidents WHERE case_type_code = 1 AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"GROUP BY year ORDER BY year")


# ── P13: heat matrix (day × hour) ──
# Live facts (probed 2026-09-06): hour_of_day is COMPLETE — 0-23 in both series, no NULL, no 99-style sentinel
# (the case-1 hours sum to exactly 270,723 = every casualty accident); day_of_week is 1-7 (1 = ראשון) with a
# pre-joined day_of_week_label. The exclusion predicate below is therefore defensive: it fires on a NULL or
# out-of-range value if one ever appears, and its count feeds a data-driven caveat (live: 0).
DAY_NAMES_HE = {1: "ראשון", 2: "שני", 3: "שלישי", 4: "רביעי", 5: "חמישי", 6: "שישי", 7: "שבת"}
DAY_LABELS_SQL = ("-- nl2sql-roadsafety-lab | heat_matrix | day labels from the pre-joined column (dossier rule)\n"
                  "SELECT day_of_week, min(day_of_week_label) AS label FROM accidents\n"
                  "WHERE day_of_week BETWEEN 1 AND 7 AND day_of_week_label IS NOT NULL\n"
                  "GROUP BY day_of_week ORDER BY day_of_week")
HEAT_UNKNOWN_PRED = ("day_of_week IS NULL OR hour_of_day IS NULL "
                     "OR day_of_week NOT BETWEEN 1 AND 7 OR hour_of_day NOT BETWEEN 0 AND 23")


def build_heat_matrix_sql(y0: int, y1: int) -> str:
    """Casualty accidents per day_of_week × hour_of_day, ZERO-FILLED to the full 7×24 grid in SQL — exactly
    168 rows always return (a quiet cell is a real zero, never a hole), ordered dow then hour. Unknown
    hour/day rows are excluded here and counted by heat_matrix_unknown_sql for the caveat."""
    return (f"-- nl2sql-roadsafety-lab | heat_matrix | {y0}-{y1} | 7x24 grid, zero-filled\n"
            f"WITH grid AS (                        -- the full week x day grid: 168 cells, always\n"
            f"    SELECT d AS day_of_week, h AS hour_of_day\n"
            f"    FROM range(1, 8) t(d) CROSS JOIN range(0, 24) u(h)\n"
            f"),\n"
            f"counts AS (\n"
            f"    SELECT day_of_week, hour_of_day, count(*) AS accidents\n"
            f"    FROM accidents\n"
            f"    WHERE case_type_code = 1              -- casualty series only (dossier §5.1)\n"
            f"      AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"      AND day_of_week BETWEEN 1 AND 7    -- a NULL/sentinel day or hour never lands in a cell\n"
            f"      AND hour_of_day BETWEEN 0 AND 23\n"
            f"    GROUP BY day_of_week, hour_of_day\n"
            f")\n"
            f"SELECT g.day_of_week, g.hour_of_day, coalesce(c.accidents, 0) AS accidents\n"
            f"FROM grid g\n"
            f"LEFT JOIN counts c ON c.day_of_week = g.day_of_week AND c.hour_of_day = g.hour_of_day\n"
            f"ORDER BY g.day_of_week, g.hour_of_day")


def heat_matrix_unknown_sql(y0: int, y1: int) -> str:
    """Total casualty accidents in range and how many the grid excludes (unknown/invalid hour or day) —
    total = sum(grid) + unknown by construction, and the caveat carries the number."""
    return (f"-- nl2sql-roadsafety-lab | heat_matrix | unknown hour/day in {y0}-{y1}\n"
            f"SELECT count(*) AS total,\n"
            f"       count(*) FILTER (WHERE {HEAT_UNKNOWN_PRED}) AS unknown\n"
            f"FROM accidents\n"
            f"WHERE case_type_code = 1 AND year BETWEEN {ilit(y0)} AND {ilit(y1)}")


ABOUT_SQL = """\
-- nl2sql-roadsafety-lab | about | one statement of scalar subqueries
SELECT
  (SELECT count(*) FROM accidents) AS accidents_rows,
  (SELECT count(*) FROM accidents WHERE case_type_code = 1) AS casualty_accidents,
  (SELECT count(*) FROM accidents WHERE case_type_code = 3) AS damage_only,
  (SELECT count(*) FROM involved) AS involved_rows,
  (SELECT count(*) FROM involved WHERE case_type_code = 1) AS casualty_involved,
  (SELECT count(*) FROM vehicles) AS vehicles_rows,
  (SELECT min(year) FROM accidents) AS first_year,
  (SELECT max(year) FROM accidents) AS last_year,
  (SELECT max(month) FROM accidents WHERE year = (SELECT max(year) FROM accidents)) AS last_month,
  (SELECT CAST(max(accident_date) AS VARCHAR) FROM accidents) AS data_end,
  (SELECT count(*) FROM information_schema.tables
    WHERE table_schema = 'main' AND table_type = 'BASE TABLE') AS n_tables,
  (SELECT count(*) FROM information_schema.tables
    WHERE table_schema = 'main' AND table_type = 'VIEW') AS n_views"""

# P13: the KPI strip behind the page — latest covered year vs the year before, casualty filter on EVERY
# subquery (the involved counts additionally key on injury_severity_code; a naive count would take both series).
ABOUT_KPI_SQL = """\
-- nl2sql-roadsafety-lab | about | latest-year KPIs, one statement of scalar subqueries
WITH y AS (SELECT max(year) AS latest FROM accidents WHERE case_type_code = 1)
SELECT
  (SELECT latest FROM y) AS latest_year,
  (SELECT count(*) FROM accidents WHERE case_type_code = 1
     AND year = (SELECT latest FROM y)) AS accidents_latest,
  (SELECT count(*) FROM accidents WHERE case_type_code = 1
     AND year = (SELECT latest FROM y) - 1) AS accidents_prev,
  (SELECT count(*) FROM involved WHERE case_type_code = 1 AND injury_severity_code = 1
     AND year = (SELECT latest FROM y)) AS killed_latest,
  (SELECT count(*) FROM involved WHERE case_type_code = 1 AND injury_severity_code = 1
     AND year = (SELECT latest FROM y) - 1) AS killed_prev,
  (SELECT count(*) FROM involved WHERE case_type_code = 1 AND injury_severity_code = 2
     AND year = (SELECT latest FROM y)) AS severe_latest,
  (SELECT count(*) FROM involved WHERE case_type_code = 1 AND injury_severity_code = 2
     AND year = (SELECT latest FROM y) - 1) AS severe_prev"""


# ───────────────────────────── P3: hotspot map ─────────────────────────────

GEO_PREDICATE = "latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 36.0"   # WGS84 Israel bbox; NULL fails BETWEEN
POINTS_PER_UNIT, POINTS_TOTAL = 300, 3000                                             # the drill-down cap (newest first)
HOTSPOT_TOP_N = (1, 200)
HOTSPOT_UNITS = {"segments": "מקטעים", "njunctions": "צמתים לא-עירוניים", "ujunctions": "צמתים עירוניים"}
HOTSPOT_COLOR_BY = ("observed", "excess")


def geo_pred(alias: str) -> str:
    return f"{alias}.latitude BETWEEN 29.0 AND 34.0 AND {alias}.longitude BETWEEN 34.0 AND 36.0"


def as_bool(v, name: str) -> bool:
    """bool, 0/1, 'true'/'false'/'yes'/'no'/'1'/'0' (any case) → bool; anything else → ActionError naming the input."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "1", "yes", "on"):
            return True
        if s in ("false", "0", "no", "off", ""):
            return False
    raise ActionError(f"{name} must be true or false; got {v!r}.")


STATIC_GEOMETRY_CTE = """latest_segments AS (            -- the latest traffic_segments vintage per key: static geometry before the as-of years, and the site key
    SELECT CAST(road AS INTEGER) AS road, CAST(seg AS INTEGER) AS seg, km_from, km_to
    FROM traffic_segments
    QUALIFY row_number() OVER (PARTITION BY road, seg ORDER BY src_year DESC, loaded_at DESC, km_to - km_from, km_from) = 1
)"""


def _segment_map_ctes(y0: int, y1: int, road: int = 0) -> str:
    static_end = min(y1 + 1, EXPOSURE_YEARS[0])            # range(y0, static_end) is empty when y0 >= 2017
    road_filter = f"\n      AND road1_number = {ilit(road)}" if road else ""
    return (f"{UNITS_CTE},\n{STATIC_GEOMETRY_CTE},\n"
            f"geom AS (                             -- one geometry per (road, seg, year): as-of units {EXPOSURE_YEARS[0]}+ (segment_rates' unit), static latest vintage before\n"
            f"    SELECT road, seg, year, km_from, km_to, gap_years, 'asof' AS geometry\n"
            f"    FROM units WHERE year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"    UNION ALL\n"
            f"    SELECT s.road, s.seg, t.y AS year, s.km_from, s.km_to, 99 AS gap_years, 'static' AS geometry\n"
            f"    FROM latest_segments s CROSS JOIN range({ilit(y0)}, {ilit(static_end)}) t(y)\n"
            f"),\n"
            f"base AS (                             -- casualty series, interurban, requested years (dossier 5.1)\n"
            f"    SELECT accident_id, case_type_code, year, accident_date, severity_code, severity_label,\n"
            f"           road1_number, road_km, latitude, longitude\n"
            f"    FROM accidents\n"
            f"    WHERE case_type_code = 1\n"
            f"      AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"      AND road_type_code IN (3, 4){road_filter}\n"
            f"),\n"
            f"matched AS (                          -- exact assignment predicate: half-open km, year equality, one row per accident\n"
            f"    SELECT a.accident_id, a.case_type_code, a.year, a.accident_date, a.severity_code, a.severity_label,\n"
            f"           a.road_km, a.latitude, a.longitude, u.road, u.seg, u.geometry\n"
            f"    FROM base a\n    {assign_join('geom')}\n    {ASSIGN_QUALIFY}\n)")


def _junction_base_cte(unit: str, y0: int, y1: int, road: int = 0) -> str:
    road_filter = f"\n      AND road1_number = {ilit(road)}" if road else ""
    if unit == "njunctions":
        return (f"base AS (                             -- casualty series, non-urban, a real junction code (site_coding_exprs' coded rule)\n"
                f"    SELECT accident_id, case_type_code, year, accident_date, severity_code, severity_label, road_type_code,\n"
                f"           nonurban_junction_code AS code, nonurban_junction_name AS name, latitude, longitude\n"
                f"    FROM accidents\n"
                f"    WHERE case_type_code = 1\n"
                f"      AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
                f"      AND road_type_code IN (3, 4)\n"
                f"      AND nonurban_junction_code IS NOT NULL AND nonurban_junction_code NOT IN {JUNCTION_SENTINELS}{road_filter}\n)")
    return (f"base AS (                             -- casualty series, urban, a real junction code within a city (the ujunction site key)\n"
            f"    SELECT accident_id, case_type_code, year, accident_date, severity_code, severity_label, road_type_code,\n"
            f"           city_code AS city, urban_junction_code AS code, city_name, street1_name, street2_name, latitude, longitude\n"
            f"    FROM accidents\n"
            f"    WHERE case_type_code = 1\n"
            f"      AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"      AND road_type_code IN (1, 2)\n"
            f"      AND urban_junction_code IS NOT NULL AND urban_junction_code NOT IN {JUNCTION_SENTINELS}\n"
            f"      AND coalesce(city_code, 0) > 0\n)")


DIM_NONURBAN_CTE = (f"dim AS (                              -- dim_junction_nonurban: several rows per code (live 4,202 rows / 2,525 codes) — grouped: min() name, mean coordinates\n"
                    f"    SELECT junction_code AS code, min(junction_name) AS name, count(*) AS dim_rows,\n"
                    f"           avg(latitude) FILTER (WHERE {GEO_PREDICATE}) AS lat, avg(longitude) FILTER (WHERE {GEO_PREDICATE}) AS lon\n"
                    f"    FROM dim_junction_nonurban GROUP BY junction_code\n)")
DIM_URBAN_CTE = (f"dim AS (                              -- dim_junction_urban: key (junction_code, city_code) — grouped anyway, so a duplicate can never double a count\n"
                 f"    SELECT city_code AS city, junction_code AS code, count(*) AS dim_rows,\n"
                 f"           avg(latitude) FILTER (WHERE {GEO_PREDICATE}) AS lat, avg(longitude) FILTER (WHERE {GEO_PREDICATE}) AS lon\n"
                 f"    FROM dim_junction_urban GROUP BY city_code, junction_code\n)")


def build_hotspot_sql(unit: str, y0: int, y1: int, top_n: int, road: int = 0) -> str:
    """Observed casualty-accident counts per unit, ranked — aggregate first, geometry after (PLAN_1 §4.1)."""
    if unit != "segments":
        return _build_hotspot_junctions_sql(unit, y0, y1, top_n, road)
    return (f"-- nl2sql-roadsafety-lab | hotspot_map | unit=segments | road={road or 'all'} | {y0}-{y1} | top {top_n}\n"
            f"WITH {_segment_map_ctes(y0, y1, road)},\n"
            f"counts AS (                           -- aggregate first, geometry after\n"
            f"    SELECT road, seg, count(*) AS accidents,\n"
            f"           count(*) FILTER (WHERE severity_code IN (1, 2)) AS ksi_accidents,\n"
            f"           count(*) FILTER (WHERE {GEO_PREDICATE}) AS geocoded,\n"
            f"           avg(latitude) FILTER (WHERE {GEO_PREDICATE}) AS lat,\n"
            f"           avg(longitude) FILTER (WHERE {GEO_PREDICATE}) AS lon,\n"
            f"           min(year) AS first_year, max(year) AS last_year,\n"
            f"           count(*) FILTER (WHERE geometry = 'static') AS static_assigned\n"
            f"    FROM matched GROUP BY road, seg\n"
            f"),\n"
            f"{NAMES_CTE}\n"
            f"SELECT c.road, c.seg, n.name_from, n.name_to, g.km_from, g.km_to,\n"
            f"       c.accidents, c.ksi_accidents, c.geocoded,\n"
            f"       round(c.lat, 5) AS latitude, round(c.lon, 5) AS longitude,\n"
            f"       c.first_year, c.last_year, c.static_assigned,\n"
            f"       printf('road:%d/%g-%g', c.road, g.km_from, g.km_to) AS site_key,   -- the before_after key syntax\n"
            f"       row_number() OVER (ORDER BY c.accidents DESC, c.ksi_accidents DESC, c.road, c.seg) AS rank\n"
            f"FROM counts c\n"
            f"LEFT JOIN latest_segments g USING (road, seg)\n"
            f"LEFT JOIN names n USING (road, seg)\n"
            f"ORDER BY rank\n"
            f"LIMIT {ilit(top_n)}")


def _build_hotspot_junctions_sql(unit: str, y0: int, y1: int, top_n: int, road: int = 0) -> str:
    nonurban = unit == "njunctions"
    key = "code" if nonurban else "city, code"
    name_cols = "min(name) AS acc_name, " if nonurban else ""
    label = "coalesce(d.name, c.acc_name) AS name" if nonurban else "n.city_name, n.street1_name, n.street2_name"
    names = "" if nonurban else f",\n{UJ_NAMES_CTE}"
    names_join = "" if nonurban else "\nLEFT JOIN ujnames n USING (city, code)"
    site_key = "printf('njunction:%d', c.code)" if nonurban else "printf('ujunction:%d/%d', c.city, c.code)"
    order = "c.accidents DESC, c.ksi_accidents DESC, " + ("c.code" if nonurban else "c.city, c.code")
    return (f"-- nl2sql-roadsafety-lab | hotspot_map | unit={unit} | road={road or 'all'} | {y0}-{y1} | top {top_n}\n"
            f"WITH {_junction_base_cte(unit, y0, y1, road)},\n"
            f"{DIM_NONURBAN_CTE if nonurban else DIM_URBAN_CTE}{names},\n"
            f"counts AS (                           -- aggregate first, join the dimension after (a plain join would double counts)\n"
            f"    SELECT {key}, {name_cols}count(*) AS accidents,\n"
            f"           count(*) FILTER (WHERE severity_code IN (1, 2)) AS ksi_accidents,\n"
            f"           count(*) FILTER (WHERE {GEO_PREDICATE}) AS geocoded,\n"
            f"           avg(latitude) FILTER (WHERE {GEO_PREDICATE}) AS lat, avg(longitude) FILTER (WHERE {GEO_PREDICATE}) AS lon,\n"
            f"           min(year) AS first_year, max(year) AS last_year\n"
            f"    FROM base GROUP BY {key}\n"
            f")\n"
            f"SELECT c.{key.replace(', ', ', c.')}, {label},\n"
            f"       c.accidents, c.ksi_accidents, c.geocoded,\n"
            f"       round(coalesce(d.lat, c.lat), 5) AS latitude, round(coalesce(d.lon, c.lon), 5) AS longitude,\n"
            f"       CASE WHEN d.lat IS NOT NULL THEN 'dim' WHEN c.lat IS NOT NULL THEN 'accidents' END AS geometry_source,\n"
            f"       coalesce(d.dim_rows, 0) AS dim_rows, c.first_year, c.last_year,\n"
            f"       {site_key} AS site_key,\n"
            f"       row_number() OVER (ORDER BY {order}) AS rank\n"
            f"FROM counts c\n"
            f"LEFT JOIN dim d USING ({key}){names_join}\n"
            f"ORDER BY rank\n"
            f"LIMIT {ilit(top_n)}")


def hotspot_coverage_sql(unit: str, y0: int, y1: int, road: int = 0) -> str:
    """Per-year scope numbers behind every caveat: population, matched to a unit, geocoded, outside the bbox."""
    if unit != "segments":
        return _junction_coverage_sql(unit, y0, y1, road)
    g = geo_pred("b")
    return (f"-- nl2sql-roadsafety-lab | hotspot_map coverage | unit=segments | road={road or 'all'} | {y0}-{y1}\n"
            f"WITH {_segment_map_ctes(y0, y1, road)}\n"
            f"SELECT b.year,\n"
            f"       CASE WHEN b.year < {ilit(EXPOSURE_YEARS[0])} THEN 'static' ELSE 'asof' END AS geometry,\n"
            f"       count(*) AS total, count(m.accident_id) AS matched,\n"
            f"       count(*) FILTER (WHERE {g}) AS with_coords,\n"
            f"       count(m.accident_id) FILTER (WHERE {g}) AS matched_with_coords,\n"
            f"       count(*) FILTER (WHERE b.latitude IS NOT NULL AND NOT ({g})) AS outside_bbox\n"
            f"FROM base b\n"
            f"LEFT JOIN matched m ON m.accident_id = b.accident_id AND m.case_type_code = b.case_type_code\n"
            f"GROUP BY b.year ORDER BY b.year")


def _junction_coverage_sql(unit: str, y0: int, y1: int, road: int = 0) -> str:
    nonurban = unit == "njunctions"
    rt_all, rt_junction = ("(3, 4)", "3") if nonurban else ("(1, 2)", "1")
    coded = (f"nonurban_junction_code IS NOT NULL AND nonurban_junction_code NOT IN {JUNCTION_SENTINELS}" if nonurban
             else f"urban_junction_code IS NOT NULL AND urban_junction_code NOT IN {JUNCTION_SENTINELS} AND coalesce(city_code, 0) > 0")
    road_filter = f" AND road1_number = {ilit(road)}" if road else ""
    return (f"-- nl2sql-roadsafety-lab | hotspot_map coverage | unit={unit} | road={road or 'all'} | {y0}-{y1}\n"
            f"SELECT year,\n"
            f"       count(*) FILTER (WHERE road_type_code = {rt_junction}) AS total,                       -- at a junction\n"
            f"       count(*) FILTER (WHERE road_type_code = {rt_junction} AND ({coded})) AS matched,       -- ... with a real code\n"
            f"       count(*) FILTER (WHERE road_type_code = {rt_junction} AND {GEO_PREDICATE}) AS with_coords,\n"
            f"       count(*) FILTER (WHERE road_type_code = {rt_junction} AND ({coded}) AND {GEO_PREDICATE}) AS matched_with_coords,\n"
            f"       count(*) FILTER (WHERE road_type_code <> {rt_junction} AND ({coded})) AS coded_off_junction,\n"
            f"       count(*) FILTER (WHERE latitude IS NOT NULL AND NOT ({GEO_PREDICATE})) AS outside_bbox\n"
            f"FROM accidents\n"
            f"WHERE case_type_code = 1 AND year BETWEEN {ilit(y0)} AND {ilit(y1)} AND road_type_code IN {rt_all}{road_filter}\n"
            f"GROUP BY year ORDER BY year")


def hotspot_points_sql(unit: str, y0: int, y1: int, keys, road: int = 0, per_unit: int | None = None,
                       total: int | None = None) -> str:
    """The shown units' individual accidents (drill-down): keys = the (road, seg) / (code,) / (city, code) tuples of
    the rows shown, in rank order; capped in SQL (newest first) so the statement returns exactly the points shown."""
    per_unit, total = per_unit or POINTS_PER_UNIT, total or POINTS_TOTAL
    keys = list(keys)
    if not keys:
        raise ValueError("hotspot_points_sql needs at least one key")
    if unit == "segments":
        vals = ", ".join(f"({ilit(r)}, {ilit(s)}, {ilit(i)})" for i, (r, s) in enumerate(keys, start=1))
        rel, keys_cte, on, part, cols = "matched", "keys(road, seg, rank)", "k.road = m.road AND k.seg = m.seg", "m.road, m.seg", "m.road, m.seg"
        extra, ctes = ", m.road_km", _segment_map_ctes(y0, y1, road)
    elif unit == "njunctions":
        vals = ", ".join(f"({ilit(c)}, {ilit(i)})" for i, (c,) in enumerate(keys, start=1))
        rel, keys_cte, on, part, cols = "base", "keys(code, rank)", "k.code = m.code", "m.code", "m.code"
        extra, ctes = "", _junction_base_cte(unit, y0, y1, road)
    else:
        vals = ", ".join(f"({ilit(city)}, {ilit(c)}, {ilit(i)})" for i, (city, c) in enumerate(keys, start=1))
        rel, keys_cte, on, part, cols = "base", "keys(city, code, rank)", "k.city = m.city AND k.code = m.code", "m.city, m.code", "m.city, m.code"
        extra, ctes = "", _junction_base_cte(unit, y0, y1, road)
    return (f"-- nl2sql-roadsafety-lab | hotspot_map points | unit={unit} | {y0}-{y1} | {len(keys)} units | cap {per_unit}/unit, {total} total\n"
            f"WITH {ctes},\n"
            f"{keys_cte} AS (VALUES {vals})\n"
            f"SELECT k.rank, {cols}, m.accident_id, m.case_type_code, m.year, m.accident_date,\n"
            f"       m.severity_code, m.severity_label{extra}, m.latitude, m.longitude\n"
            f"FROM {rel} m\n"
            f"JOIN keys k ON {on}\n"
            f"WHERE {geo_pred('m')}\n"
            f"QUALIFY row_number() OVER (PARTITION BY {part} ORDER BY m.accident_date DESC, m.accident_id) <= {ilit(per_unit)}\n"
            f"ORDER BY k.rank, m.accident_date DESC, m.accident_id\n"
            f"LIMIT {ilit(total)}")


FIRST_GEOCODED_YEAR_SQL = f"SELECT min(year) FROM accidents WHERE case_type_code = 1 AND {GEO_PREDICATE}"


# ───────────────────────────── P10: map scene (מפה חיה) ─────────────────────────────

MAP_CLOUD_BOUNDS = (10, 400000)                 # max_points bounds — the SQL cap; the page filters on the GPU
GAZETTEER_LIMIT = 1500                          # localities with at least one geocoded casualty accident in range


def build_map_cloud_sql(y0: int, y1: int, road: int = 0, cap: int = 300000) -> str:
    """The accident point cloud, columnar-ready: one row per GEOCODED casualty accident (bbox rule, newest
    first, capped in SQL). sev = severity_code (real severities inside the casualty series); night encodes
    day_night_code 1/5 as 0/1 and anything else as 2 (uncoded — its own category, never dropped)."""
    road_filter = f"\n  AND road1_number = {ilit(road)}" if road else ""
    return (f"-- nl2sql-roadsafety-lab | map_scene cloud | road={road or 'all'} | {y0}-{y1} | cap {cap}\n"
            f"SELECT round(longitude, 5) AS lon, round(latitude, 5) AS lat, year,\n"
            f"       severity_code AS sev,\n"
            f"       CASE day_night_code WHEN 5 THEN 1 WHEN 1 THEN 0 ELSE 2 END AS night\n"
            f"FROM accidents\n"
            f"WHERE case_type_code = 1\n"
            f"  AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"  AND {GEO_PREDICATE}{road_filter}\n"
            f"ORDER BY accident_date DESC, accident_id DESC\n"
            f"LIMIT {ilit(cap)}")


def map_cloud_coverage_sql(y0: int, y1: int, road: int = 0) -> str:
    """Per-year scope behind the cloud's caveats: population, geocoded (= inside the bbox), outside it."""
    road_filter = f" AND road1_number = {ilit(road)}" if road else ""
    return (f"-- nl2sql-roadsafety-lab | map_scene coverage | road={road or 'all'} | {y0}-{y1}\n"
            f"SELECT year, count(*) AS total,\n"
            f"       count(*) FILTER (WHERE {GEO_PREDICATE}) AS geocoded,\n"
            f"       count(*) FILTER (WHERE latitude IS NOT NULL AND NOT ({GEO_PREDICATE})) AS outside_bbox\n"
            f"FROM accidents\n"
            f"WHERE case_type_code = 1 AND year BETWEEN {ilit(y0)} AND {ilit(y1)}{road_filter}\n"
            f"GROUP BY year ORDER BY year")


def gazetteer_sql(y0: int, y1: int) -> str:
    """Locality centroids for the page's offline search box: the mean of each city's geocoded casualty
    accidents (internal data — no external geocoder, ever). A city with no geocoded accident in range is
    not searchable, which is honest: the map has nothing to fly to."""
    return (f"-- nl2sql-roadsafety-lab | map_scene gazetteer | {y0}-{y1}\n"
            f"SELECT city_code AS city, min(city_name) AS name, count(*) AS accidents,\n"
            f"       round(avg(latitude) FILTER (WHERE {GEO_PREDICATE}), 5) AS lat,\n"
            f"       round(avg(longitude) FILTER (WHERE {GEO_PREDICATE}), 5) AS lon\n"
            f"FROM accidents\n"
            f"WHERE case_type_code = 1 AND year BETWEEN {ilit(y0)} AND {ilit(y1)} AND coalesce(city_code, 0) > 0\n"
            f"GROUP BY city_code\n"
            f"HAVING count(*) FILTER (WHERE {GEO_PREDICATE}) > 0\n"
            f"ORDER BY accidents DESC, city_code\n"
            f"LIMIT {ilit(GAZETTEER_LIMIT)}")


def site_profile_strip_sql(site: Site, y0: int, y1: int) -> str:
    """site_profile's observed strip: one row per year with the severity split, day/night and the geocode
    counts, plus the site's accident-mean coordinate (the page already knows the clicked marker; this is the
    fallback). Casualty series + the shared site predicate — the same rows before_after would count."""
    return (f"-- nl2sql-roadsafety-lab | site_profile | site={site.key} | {y0}-{y1}\n"
            f"SELECT year, count(*) AS accidents,\n"
            f"       count(*) FILTER (WHERE severity_code IN (1, 2)) AS ksi_accidents,\n"
            f"       count(*) FILTER (WHERE severity_code = 1) AS fatal,\n"
            f"       count(*) FILTER (WHERE severity_code = 2) AS severe,\n"
            f"       count(*) FILTER (WHERE severity_code = 3) AS slight,\n"
            f"       count(*) FILTER (WHERE {GEO_PREDICATE}) AS geocoded,\n"
            f"       count(*) FILTER (WHERE day_night_code = 5) AS night,\n"
            f"       count(*) FILTER (WHERE day_night_code = 1) AS day,\n"
            f"       avg(latitude) FILTER (WHERE {GEO_PREDICATE}) AS lat,\n"
            f"       avg(longitude) FILTER (WHERE {GEO_PREDICATE}) AS lon\n"
            f"FROM accidents\n"
            f"WHERE case_type_code = 1 AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"  AND ({site_predicate(site)})\n"
            f"GROUP BY year ORDER BY year")


def road_seg_km_sql(road: int, seg: int) -> str:
    """The latest traffic_segments vintage's km range for one (road, seg) — the same vintage rule as
    STATIC_GEOMETRY_CTE, so a bare '60/836' resolves to exactly the site key hotspot_map prints."""
    return (f"SELECT km_from, km_to FROM traffic_segments\n"
            f"WHERE CAST(road AS INTEGER) = {ilit(road)} AND CAST(seg AS INTEGER) = {ilit(seg)}\n"
            f"QUALIFY row_number() OVER (PARTITION BY road, seg "
            f"ORDER BY src_year DESC, loaded_at DESC, km_to - km_from, km_from) = 1")


def outline() -> dict:
    """The bundled Israel outline (Natural Earth, public domain) as a GeoJSON FeatureCollection — package data,
    the same file the page imports as a JSON module."""
    import json
    from importlib.resources import files
    return json.loads((files("nl2sql_roadsafety") / "data" / "israel.json").read_text(encoding="utf-8"))


# ───────────────────────────── P14: geographic snapshot tier ─────────────────────────────
# accidents_by_taz (2,637 zones) / accidents_by_municipality (1,174 municipalities) / dim_settlement (names).
# Dossier §4.7, non-negotiable: these are CUMULATIVE, UNDATED publication snapshots (~5.2 years, stamp
# 202604) — a SEPARATE UNIVERSE from the yearly casualty series. Verified totals that do NOT reconcile:
# TAZ 38,363 accidents / 1,772 killed / 70,799 injured vs municipality 276,849 accidents / 2,091 killed vs
# the series' 270,723 casualty accidents / 7,052 killed people. Consequences built in: NO year inputs on
# these actions, and every answer carries the snapshot stamp + the universe totals in its caveats.
# taz_area is SQUARE METERS (852978.0 = 0.85 km2 — always /1e6); area_sqkm is already km2.
# The shipped accident_index correlates r = 1.000 with accidents per km2 and r = 0.038 with accidents per
# 1,000 residents (probed 2026-09-06): it is a DENSITY, not per-person risk — recomputed live per answer.

# live code_lookups has NO land-use field (probed 2026-09-06) — the plugin map fills in, and the answer says so
LAND_USE_LABELS_FALLBACK = {1: "מגורים", 2: "מסחר", 3: "תעשייה", 4: "מוסדות", 5: "אחר"}
LAND_USE_CHOICES = ("all", "1", "2", "3", "4", "5")
LAND_USE_SQL = ("-- nl2sql-roadsafety-lab | zone_ranking | land-use labels from the code dictionary (live: absent)\n"
                "SELECT code, arg_max(label_he, year) AS label FROM code_lookups\n"
                "WHERE field = 'land_use_code' AND label_he IS NOT NULL GROUP BY code")

# key: (value expression, guard predicate or None, denominator kind, denominator label, Hebrew axis label)
ZONE_MEASURES = {
    "per_capita": ("round(total_accidents * 1000.0 / population_2018, 1)", None, "exposure",
                   "ל-1,000 תושבים (אוכלוסיית 2018)", "תאונות לאלף תושבים"),
    "density":    ("round(total_accidents / area_km2, 1)", "area_km2 > 0", "exposure",
                   'לקמ"ר', "תאונות לקמ״ר"),
    "ped_share":  ("round(pedestrians_injured * 100.0 / injured_total, 1)", "coalesce(injured_total, 0) > 0",
                   "counts", "אחוז הולכי הרגל מכלל הנפגעים באזור — ספירות בלבד", "אחוז הולכי רגל מהנפגעים"),
}
CITY_MEASURES = {
    "density":   ("round(total_accidents / area_sqkm, 1)", "area_sqkm > 0", "exposure",
                  'לקמ"ר (שטח שיפוט)', "תאונות לקמ״ר"),
    "total":     ("total_accidents", "TRUE", "counts",
                  "ספירות תאונות בצילום המצטבר — ללא מכנה חשיפה", "סך תאונות בצילום"),
    "ped_share": ("round(pedestrians_injured * 100.0 / injured_total, 1)", "coalesce(injured_total, 0) > 0",
                  "counts", "אחוז הולכי הרגל מכלל הנפגעים ביישוב — ספירות בלבד", "אחוז הולכי רגל מהנפגעים"),
}


def build_zone_ranking_sql(measure: str, land_use: int, min_pop: int, top_n: int) -> str:
    """Ranking over the cumulative TAZ snapshot. The label joins dim_settlement (codes can miss — the
    'קוד' fallback); per_capita guards on min_pop (zones with 193 residents and 145 accidents exist:
    through-traffic inflates per-person rates absurdly); density converts taz_area from square meters."""
    expr, guard, _, _, _ = ZONE_MEASURES[measure]
    if measure == "per_capita":
        guard = f"coalesce(population_2018, 0) >= {ilit(min_pop)}"
    lu = f"\n  AND land_use_code = {ilit(land_use)}" if land_use else ""
    # ped_share also SELECTS the denominator and breaks 100%-share ties by it (refuter 2026-09-06: the
    # top-20 was a flat wall of 100.0% zones with 1-4 accidents — a bigger denominator now ranks first)
    ped_col = ",\n       injured_total AS injured" if measure == "ped_share" else ""
    order = "value DESC, injured DESC, label" if measure == "ped_share" else "value DESC, label"
    return (f"-- nl2sql-roadsafety-lab | zone_ranking | measure={measure} | land_use={land_use or 'all'} "
            f"| min_pop={ilit(min_pop)} | top {top_n}\n"
            f"WITH zones AS (                       -- the cumulative snapshot + settlement names (codes can miss)\n"
            f"    SELECT t.taz_object_id, t.population_2018, t.land_use_code,\n"
            f"           t.taz_area / 1e6 AS area_km2,                 -- taz_area is SQUARE METERS\n"
            f"           t.total_accidents, t.pedestrians_injured, t.injured_total,\n"
            f"           coalesce(s.city_name_he, {slit('קוד ')} || CAST(t.city_code AS VARCHAR)) AS city_name\n"
            f"    FROM accidents_by_taz t\n"
            f"    LEFT JOIN dim_settlement s USING (city_code)\n"
            f")\n"
            f"SELECT city_name || {slit(' · אזור ')} || CAST(taz_object_id AS VARCHAR) AS label,\n"
            f"       {expr} AS value,\n"
            f"       total_accidents AS accidents,\n"
            f"       population_2018 AS population,\n"
            f"       round(area_km2, 3) AS area_km2,\n"
            f"       land_use_code AS land_use{ped_col}\n"
            f"FROM zones\n"
            f"WHERE {guard}{lu}\n"
            f"ORDER BY {order}\n"
            f"LIMIT {ilit(top_n)}")


def zone_universe_sql(land_use: int, min_pop: int) -> str:
    """One aggregate behind every zone caveat: whole-snapshot totals (the mismatch line is scope-independent),
    the scope counts for the chosen land use, and the accident_index correlations (index == density live).
    The CASE guards keep a zero denominator out of corr (DuckDB yields inf, not NULL, on x/0)."""
    lu = f"land_use_code = {ilit(land_use)}" if land_use else "TRUE"
    return (f"-- nl2sql-roadsafety-lab | zone_ranking universe | land_use={land_use or 'all'} | min_pop={ilit(min_pop)}\n"
            f"SELECT count(*) AS zones,\n"
            f"       sum(total_accidents) AS accidents, sum(killed) AS killed,\n"
            f"       sum(injured_total) AS injured, sum(population_2018) AS population,\n"
            f"       max(snapshot_yearmonth) AS snapshot,\n"
            f"       count(*) FILTER (WHERE {lu}) AS zones_in_scope,\n"
            f"       count(*) FILTER (WHERE {lu} AND coalesce(population_2018, 0) < {ilit(min_pop)}) AS below_min_pop,\n"
            f"       count(*) FILTER (WHERE {lu} AND coalesce(injured_total, 0) <= 0) AS no_injured,\n"
            f"       corr(accident_index, CASE WHEN taz_area > 0 THEN total_accidents / (taz_area / 1e6) END) AS corr_density,\n"
            f"       corr(accident_index, CASE WHEN coalesce(population_2018, 0) > 0 "
            f"THEN total_accidents * 1000.0 / population_2018 END) AS corr_per_capita\n"
            f"FROM accidents_by_taz")


def build_city_ranking_sql(measure: str, top_n: int) -> str:
    """Ranking over the cumulative municipality snapshot AT LOCALITY GRAIN: the snapshot carries split
    rows (live: 1,174 rows over 1,170 distinct city codes — 4 localities appear twice), so outcomes and
    area are summed per city_code BEFORE ranking (refuter 2026-09-06: a split locality's merged value was
    understated and one label could rank twice). dim_settlement supplies city + region names with the
    'קוד' fallback."""
    expr, guard, _, _, _ = CITY_MEASURES[measure]
    ped_col = ",\n       injured_total AS injured" if measure == "ped_share" else ""
    order = "value DESC, injured DESC, city, city_code" if measure == "ped_share" else "value DESC, city, city_code"
    return (f"-- nl2sql-roadsafety-lab | city_ranking | measure={measure} | locality grain | top {top_n}\n"
            f"WITH merged AS (                      -- split snapshot rows summed per locality\n"
            f"    SELECT city_code, sum(total_accidents) AS total_accidents, sum(killed) AS killed,\n"
            f"           sum(area_sqkm) AS area_sqkm,                                 -- area_sqkm is ALREADY km2\n"
            f"           sum(pedestrians_injured) AS pedestrians_injured, sum(injured_total) AS injured_total\n"
            f"    FROM accidents_by_municipality GROUP BY city_code\n"
            f"),\n"
            f"cities AS (                           -- + settlement names (codes can miss)\n"
            f"    SELECT m.*,\n"
            f"           coalesce(s.city_name_he, {slit('קוד ')} || CAST(m.city_code AS VARCHAR)) AS city,\n"
            f"           coalesce(s.region_name, {slit('קוד ')} || CAST(m.city_code AS VARCHAR)) AS region\n"
            f"    FROM merged m\n"
            f"    LEFT JOIN dim_settlement s USING (city_code)\n"
            f")\n"
            f"SELECT city, region, {expr} AS value, total_accidents AS accidents, killed,\n"
            f"       round(area_sqkm, 1) AS area_km2{ped_col}\n"
            f"FROM cities\n"
            f"WHERE {guard}\n"
            f"ORDER BY {order}\n"
            f"LIMIT {ilit(top_n)}")


def city_universe_sql() -> str:
    """The municipality snapshot's totals at LOCALITY grain (split rows merged per city_code) + the
    dictionary-miss, no-injured, and merged-row counts behind the caveats."""
    return ("-- nl2sql-roadsafety-lab | city_ranking universe | locality grain\n"
            "WITH merged AS (\n"
            "    SELECT city_code, sum(total_accidents) AS total_accidents, sum(killed) AS killed,\n"
            "           sum(area_sqkm) AS area_sqkm, sum(injured_total) AS injured_total,\n"
            "           max(snapshot_yearmonth) AS snapshot\n"
            "    FROM accidents_by_municipality GROUP BY city_code\n"
            ")\n"
            "SELECT count(*) AS cities,\n"
            "       (SELECT count(*) FROM accidents_by_municipality) AS raw_rows,\n"
            "       sum(m.total_accidents) AS accidents, sum(m.killed) AS killed,\n"
            "       round(sum(m.area_sqkm), 1) AS area_km2, max(m.snapshot) AS snapshot,\n"
            "       count(*) FILTER (WHERE coalesce(m.injured_total, 0) <= 0) AS no_injured,\n"
            "       count(*) FILTER (WHERE s.city_code IS NULL) AS unnamed\n"
            "FROM merged m\n"
            "LEFT JOIN dim_settlement s USING (city_code)")


def series_totals_sql() -> str:
    """The yearly casualty series' own totals — the other side of every separate-universe mismatch caveat."""
    return ("-- nl2sql-roadsafety-lab | geographic snapshot | the yearly-series side of the mismatch caveat\n"
            "SELECT (SELECT count(*) FROM accidents WHERE case_type_code = 1) AS series_accidents,\n"
            "       (SELECT count(*) FROM involved WHERE case_type_code = 1 AND injury_severity_code = 1) AS series_killed")


# ───────────────────────────── P15: ab_scan (the before/after discoverer) ─────────────────────────────

def build_ab_scan_sql(y0: int, y1: int, road: int = 0) -> str:
    """Per-(road, seg, year) counts of BOTH series on the LATEST traffic_segments vintage ONLY — one literal
    km range per unit, applied uniformly to every year in range (exactly the counting rule before_after uses
    on a literal road site: road + non-zero km in the half-open range, no road-type filter, and an accident
    inside two overlapping ranges counts for each of them) — plus the two national yearly series totals
    (before_after's control: the whole network, never road-filtered). One statement, the sweep's entire
    input; a unit-year with no matching accidents is simply absent and reads as a genuine zero (no as-of /
    static splice, no missing-geometry years). Scope 'unit' rows carry (road, seg); scope 'network' rows
    carry NULL keys."""
    road_filter = f"\n      AND road1_number = {ilit(road)}" if road else ""
    return (f"-- nl2sql-roadsafety-lab | ab_scan | road={road or 'all'} | {y0}-{y1} | both series | "
            f"static latest-vintage geometry | unit + network rows\n"
            f"WITH {STATIC_GEOMETRY_CTE},\n"
            f"base AS (                             -- BOTH series, requested years (the sweep needs case 3 for the controlled ratio)\n"
            f"    SELECT accident_id, case_type_code, year, road1_number, road_km\n"
            f"    FROM accidents\n"
            f"    WHERE case_type_code IN (1, 3)\n"
            f"      AND year BETWEEN {ilit(y0)} AND {ilit(y1)}{road_filter}\n"
            f"),\n"
            f"per_unit AS (                         -- before_after's literal-range site predicate, one static range per unit for ALL years\n"
            f"    SELECT s.road, s.seg, a.year,\n"
            f"           count(*) FILTER (WHERE a.case_type_code = 1) AS casualty,\n"
            f"           count(*) FILTER (WHERE a.case_type_code = 3) AS damage\n"
            f"    FROM base a\n"
            f"    JOIN latest_segments s\n"
            f"      ON a.road1_number = s.road\n"
            f"     AND a.road_km <> 0                 -- km 0 = not coded, as in site_predicate\n"
            f"     AND a.road_km / 10.0 >= s.km_from\n"
            f"     AND a.road_km / 10.0 <  s.km_to\n"
            f"    GROUP BY s.road, s.seg, a.year\n"
            f"),\n"
            f"network AS (                          -- the whole national network of each series (before_after's control, never road-filtered)\n"
            f"    SELECT year,\n"
            f"           count(*) FILTER (WHERE case_type_code = 1) AS casualty,\n"
            f"           count(*) FILTER (WHERE case_type_code = 3) AS damage\n"
            f"    FROM accidents\n"
            f"    WHERE case_type_code IN (1, 3)\n"
            f"      AND year BETWEEN {ilit(y0)} AND {ilit(y1)}\n"
            f"    GROUP BY year\n"
            f")\n"
            f"SELECT 'unit' AS scope, road, seg, year, casualty, damage FROM per_unit\n"
            f"UNION ALL\n"
            f"SELECT 'network' AS scope, NULL AS road, NULL AS seg, year, casualty, damage FROM network\n"
            f"ORDER BY scope DESC, road, seg, year")
