# -*- coding: utf-8 -*-
"""city_ranking (P14): municipality ranking over accidents_by_municipality — the second dark
geographic aggregate (1,174 rows). The same CUMULATIVE, UNDATED snapshot universe as zone_ranking
(dossier §4.7): no year input, and every answer carries the snapshot stamp + the universe totals
(276,849 accidents but only 2,091 killed — visibly NOT the yearly series' 270,723 / 7,052).
dim_settlement supplies city + region names, with the 'קוד' fallback where a code has no row."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import CAVEAT_COUNTS_NOT_RISK, denominator, dispatch, guard, make_spec, stamp, view_input
from ..sqlkit import (CITY_MEASURES, ActionError, as_choice, as_int, build_city_ranking_sql,
                      city_universe_sql, rows_safe, series_totals_sql)

VIEWS = ("chart", "table", "sql")
TITLE = "דירוג יישובים"
# columns, from the statement itself: city · region · value · accidents · killed · area_km2


@guard(TITLE)
def run(ctx, measure="density", top_n=20, view="chart"):
    measure = as_choice(measure, "measure", CITY_MEASURES)
    top_n = as_int(top_n, "top_n")
    if not 1 <= top_n <= 100:
        raise ActionError(f"top_n must be between 1 and 100; got {top_n}.")
    view = as_choice(view, "view", VIEWS)
    sql = build_city_ranking_sql(measure, top_n)
    columns, raw = ctx.query(sql)
    rows = rows_safe(raw)
    u_cols, u_raw = ctx.query(city_universe_sql())
    u = dict(zip(u_cols, rows_safe(u_raw)[0]))
    s_cols, s_raw = ctx.query(series_totals_sql())
    s = dict(zip(s_cols, rows_safe(s_raw)[0]))
    caveats = _caveats(measure, u, s, columns, rows)
    _, _, denom_kind, denom_label, axis_he = CITY_MEASURES[measure]
    denom = denominator(denom_kind, denom_label, snapshot=u["snapshot"], cities=u["cities"])
    stamp_text = stamp("city_ranking", f"measure={measure}", f"top {top_n}")
    png = None
    if view == "chart":
        from .. import charts
        png = charts.hbars([r[0] for r in rows], [r[2] for r in rows],
                           xlabel=axis_he,
                           annot=[f"{r[3]:,} תאונות" for r in rows],
                           max_rows=20,                     # the table face keeps everything
                           title=f"דירוג יישובים · {axis_he}",
                           badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
    basis = (f"city_ranking | measure={measure} | top {len(rows)} of {u['cities']} localities | "
             f"snapshot {u['snapshot']} | cumulative undated universe (never compare with the yearly series)")
    spec = make_spec("accidents/city_ranking", png_base64=png, basis=basis, rows=rows, columns=columns,
                     sql=sql, denominator=denom, caveats=caveats, measure=measure, top_n=top_n,
                     snapshot=u["snapshot"],
                     universe={"cities": u["cities"], "accidents": u["accidents"], "killed": u["killed"],
                               "area_km2": u["area_km2"]},
                     unnamed=u["unnamed"], no_injured=u["no_injured"], stamp=stamp_text,
                     x="city", y="value")
    return dispatch(view, spec, TITLE)


def _caveats(measure, u, s, columns, rows):
    """Data-derived, most specific first; no ';' in any line (it is the note's separator)."""
    out = []
    merged = u["raw_rows"] - u["cities"]
    if merged:
        # the snapshot carries split rows (live: 4 localities appear twice) — summed per locality
        out.append(f"{merged} שורות כפולות בצילום אוחדו ליישוב אחד — הדירוג בגרעין יישוב, לא שורת קובץ")
    if measure == "ped_share":
        out.append(f"{u['no_injured']:,} יישובים ללא נפגעים כלל הוחרגו מחישוב אחוז הולכי הרגל")
        ii = columns.index("injured") if "injured" in columns else -1
        if ii >= 0:
            tiny = sum(1 for r in rows if (r[ii] or 0) < 20)
            if tiny:
                out.append(f"{tiny} מתוך {len(rows)} השורות המוצגות עם פחות מעשרים נפגעים בסך הכול — "
                           f"שיעור על מכנה זעיר רועש · בשוויון אחוזים מדורג קודם מי שמכנהו גדול")
    if measure == "density":
        out.append("צפיפות על שטח שיפוט מלא (כולל שטחים פתוחים) — מדד עומס ולא סיכון לתושב")
    if measure == "total":
        out.append(CAVEAT_COUNTS_NOT_RISK)
    if u["unnamed"]:
        out.append(f"{u['unnamed']:,} יישובים ללא שורה במילון היישובים מוצגים כקוד")
    out.append(f"צילום מצטבר חד-פעמי ללא ממד זמן (חותמת פרסום {u['snapshot']}) — אין להשוות את המספרים "
               f"לפעולות השנתיות כמו trend או heat_matrix")
    out.append(f"סך הצילום: {u['accidents']:,} תאונות ו-{u['killed']:,} הרוגים על {u['area_km2']:,} קמ״ר "
               f"לעומת {s['series_accidents']:,} תאונות עם נפגעים ו-{s['series_killed']:,} הרוגים בסדרה "
               f"השנתית המלאה — יקום נתונים נפרד")
    return out


# Declared LAST (Action.run is evaluated at import).
ACTION = Action(
    name="city_ranking", label="דירוג יישובים · city_ranking",
    help="Ranking of municipalities (accidents_by_municipality, 1,174 rows) from the CUMULATIVE, undated "
         "publication snapshot - the same separate universe as zone_ranking, never compare the numbers "
         "with the yearly series (the caveats carry both sides' totals). Measures: density = accidents "
         "per square km of jurisdiction area, total = raw accident counts, ped_share = pedestrian share "
         "of the injured. Joins dim_settlement for city and region names (a missing code falls back to "
         "the code itself). No year input exists on purpose.",
    inputs={
        "measure": Input(kind="choice", label="מדד", default="density", choices=list(CITY_MEASURES),
                         help="density = per square km (jurisdiction area); total = raw counts; "
                              "ped_share = pedestrian share of the injured"),
        "top_n": Input(kind="number", label="מספר יישובים", default=20, help="1-100"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
