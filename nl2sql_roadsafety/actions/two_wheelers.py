# -*- coding: utf-8 -*-
"""two_wheelers (use ח, stretch): motorcycle involvement rates per registered active fleet by engine-cc band
(2013+, when the cc bands enter the coding), with bicycles / e-bikes / e-scooters as honest counts-only rows.
The fleet is a CURRENT snapshot (no per-year fleet series exists) and there is no VKT denominator for
two-wheelers — the caveats say both. Solo falls are under-reported: these numbers are the floor of the truth.

The curated view `v_motorcycle_accident_rate` inner-joins fleet cohorts per (band, manufacture_year), so summing
its fleet per (year, band) UNDERCOUNTS (zero-accident cohorts drop out) — this action computes the numerator
(vehicles ⋈ accidents, same golden-rule discipline) and the denominator (the FULL fleet per band) directly;
the view stays the cross-check at cohort grain (tests)."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, dispatch, guard, make_spec, stamp, view_input
from ..sqlkit import CASE_FILTER, Refusal, as_choice, ilit, on_key, rows_safe, year_range

VIEWS = ("chart", "table", "sql")
TITLE = "דו-גלגלי"
METRICS = {"accidents": "מעורבות בתאונות", "fatal": "מעורבות בתאונות קטלניות"}
CC_ERA = 2013                                   # engine-cc bands are coded from 2013 (dossier §era-scoped fields)
MOTO_CODES = "(8, 9, 10, 19)"                   # the four cc bands, mapped to fleet_motorcycles
COUNT_ONLY = {15: "אופניים", 23: "אופניים חשמליים", 21: "קורקינט חשמלי"}   # 22 = קלנועית (mobility scooter) is NOT a two-wheeler
COLS = ["year", "unit", "band_code", "accidents", "fatal", "active_fleet", "per_1000", "fatal_per_1000"]


def rate_sql(y0: int, y1: int) -> str:
    """The fleet-driven grid: every (year, band) cell exists, zero-accident cells at rate 0 (a true rate)."""
    return f"""WITH fleet AS (
    SELECT engine_cc_band_code AS band_code, any_value(engine_cc_band) AS band, sum(active) AS active_fleet
    FROM fleet_motorcycles GROUP BY 1
), grid AS (
    SELECT y.year, f.band_code, f.band, f.active_fleet
    FROM (SELECT unnest(range({ilit(y0)}, {ilit(y1 + 1)})) AS year) y CROSS JOIN fleet f
), acc AS (
    SELECT a.year, v.vehicle_type_code AS band_code,
           count(*) AS accidents,
           count(*) FILTER (WHERE a.severity_code = 1) AS fatal
    FROM vehicles v
    JOIN accidents a ON {on_key('a', 'v')}
    WHERE a.{CASE_FILTER} AND a.year BETWEEN {ilit(y0)} AND {ilit(y1)}
      AND v.vehicle_type_code IN {MOTO_CODES}
    GROUP BY 1, 2
)
SELECT g.year, g.band AS unit, g.band_code,
       coalesce(acc.accidents, 0) AS accidents, coalesce(acc.fatal, 0) AS fatal, g.active_fleet,
       round(1000.0 * coalesce(acc.accidents, 0) / nullif(g.active_fleet, 0), 2) AS per_1000,
       round(1000.0 * coalesce(acc.fatal, 0) / nullif(g.active_fleet, 0), 3) AS fatal_per_1000
FROM grid g LEFT JOIN acc ON acc.year = g.year AND acc.band_code = g.band_code
ORDER BY g.year, g.band_code"""


def counts_sql(y0: int, y1: int) -> str:
    codes = "(" + ", ".join(str(c) for c in sorted(COUNT_ONLY)) + ")"
    return f"""SELECT a.year, v.vehicle_type_code, count(*) AS accidents,
       count(*) FILTER (WHERE a.severity_code = 1) AS fatal
FROM vehicles v
JOIN accidents a ON {on_key('a', 'v')}
WHERE a.{CASE_FILTER} AND a.year BETWEEN {ilit(y0)} AND {ilit(y1)}
  AND v.vehicle_type_code IN {codes}
GROUP BY 1, 2 ORDER BY 1, 2"""


@guard(TITLE)
def run(ctx, metric="accidents", from_year=2019, to_year=2024, view="chart"):
    view = as_choice(view, "view", VIEWS)
    metric = as_choice(metric, "metric", tuple(METRICS))
    y0, y1 = year_range(from_year, to_year)
    if y0 < CC_ERA:
        raise Refusal(f"רצועות נפח המנוע מקודדות רק משנת {CC_ERA} — אין שיוך למצבה לפני כן",
                      [f"from_year בין {CC_ERA} ל-{y1 if y1 >= CC_ERA else 2024}"])
    grid_sql, only_counts_sql = rate_sql(y0, y1), counts_sql(y0, y1)
    # the sql face must reproduce the WHOLE answer — both statements, the trap.py precedent (P5 sweep finding)
    sql = grid_sql + "\n\n-- counts-only rows (bicycles / e-bikes / e-scooters — no denominator exists):\n" + only_counts_sql
    rows = rows_safe(ctx.query(grid_sql)[1])
    if not any(r[5] for r in rows):
        raise Refusal("מצבת האופנועים ריקה בחיבור הזה", ["about לבדיקת החיבור"])
    crows = rows_safe(ctx.query(only_counts_sql)[1])
    count_rows = [[r[0], COUNT_ONLY[r[1]], r[1], r[2], r[3], None, None, None] for r in crows]
    n_count = sum(r[3] for r in count_rows)
    moto_total = sum(r[3] for r in rows)
    fatal_total = sum(r[4] for r in rows)
    caveats = [
        "המצבה = צילום נוכחי של כלי רכב פעילים (אין סדרת מצבה שנתית) — השוואה בין שנים נשענת על יציבות המצבה",
        "אין נסועה (VKT) לדו-גלגלי — שיעור למצבה, לא לק״מ-רכב",
        "נפילות יחיד מדווחות בחסר — המספרים הם רצפת האמת",
        f"אופניים · אופניים חשמליים · קורקינט חשמלי: ספירות בלבד ({n_count:,} מעורבויות בטווח) — אין להם מצבה",
        f"בטווח: {moto_total:,} מעורבויות אופנוע ({fatal_total:,} בקטלניות) על מצבה נוכחית",
    ]
    denom = denominator("exposure", "פר אלף כלי רכב רשומים פעילים (מצבה נוכחית) — אין נסועה לדו-גלגלי")
    stamp_text = stamp("two_wheelers", metric, f"{y0}-{y1}")
    basis = (f"two_wheelers | {metric} | {y0}-{y1} | moto {moto_total} (fatal {fatal_total}) | "
             f"count-only {n_count}")
    all_rows = rows + count_rows
    spec = make_spec("accidents/two_wheelers", basis=basis, rows=all_rows, columns=COLS, sql=sql,
                     denominator=denom, caveats=caveats, metric=metric, from_year=y0, to_year=y1,
                     stamp=stamp_text, y="per_1000" if metric == "accidents" else "fatal_per_1000")
    if view == "chart":
        from .. import charts
        vi = 6 if metric == "accidents" else 7
        bands = sorted({(r[2], r[1]) for r in rows})
        by_band = {bc: {r[0]: r[vi] for r in rows if r[2] == bc} for bc, _ in bands}
        years = list(range(y0, y1 + 1))
        series = [(name, [by_band[bc].get(yr) for yr in years]) for bc, name in bands]
        spec["png_base64"] = charts.multi_lines(
            years, series,
            ylabel=f"{METRICS[metric]} לאלף כלי רכב פעילים",
            title=f"דו-גלגלי · {METRICS[metric]} למצבה · {y0}–{y1}",
            badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
        spec["renderer"] = "png"                 # make_spec derives the renderer at build time — keep them in step
    return dispatch(view, spec, TITLE)


ACTION = Action(
    name="two_wheelers", label="דו-גלגלי · two_wheelers",
    help="Motorcycle involvement rates per 1,000 registered ACTIVE vehicles by engine-cc band (2013+, the cc-band "
         "era); bicycles / e-bikes / e-scooters as counts-only rows (no denominator exists). The fleet is a current "
         "snapshot and there is no VKT for two-wheelers - solo falls are under-reported (the floor of the truth).",
    inputs={
        "metric": Input(kind="choice", label="מדד", default="accidents", choices=list(METRICS),
                        help="accidents = all casualty involvements; fatal = fatal-accident involvements. "
                             "The chart draws the chosen rate; the table carries both"),
        "from_year": Input(kind="number", label="שנת התחלה", default=2019, help="2013-2024 (cc bands are 2013+)"),
        "to_year": Input(kind="number", label="שנת סיום", default=2024, help="2013-2024"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
