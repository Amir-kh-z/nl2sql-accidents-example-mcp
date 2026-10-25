# -*- coding: utf-8 -*-
"""trend (use א): counts over time from the casualty series, by year or month, all roads or urban /
non-urban. Counts, not risk — the badge says so. Periods whose person-level records are missing are
shown as gaps (NULL + a grey band), never as 0."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import (CAVEAT_COUNTS_NOT_RISK, CAVEAT_DATA_END, DENOM_COUNTS, dispatch, guard,
                        make_spec, stamp_line, view_input)
from ..sqlkit import (GRANULARITY, MEASURES, ROAD_TYPES, as_choice, build_trend_sql, other_road_sql,
                      rows_safe, year_range)


@guard("מגמה")
def run(ctx, measure="killed", granularity="year", road_type="all", from_year=2005, to_year=2024,
        view="chart"):
    measure = as_choice(measure, "measure", MEASURES)
    granularity = as_choice(granularity, "granularity", GRANULARITY)
    road_type = as_choice(road_type, "road_type", ROAD_TYPES)
    view = as_choice(view, "view", ("chart", "table", "sql"))
    y0, y1 = year_range(from_year, to_year)          # from > to → error; outside 2005–2024 → refusal card
    sql = build_trend_sql(measure, granularity, road_type, y0, y1)
    columns, raw = ctx.query(sql)
    rows = rows_safe(raw)
    grain, _, label = MEASURES[measure]
    vi = columns.index(measure)
    monthly = granularity == "month"
    labels = [str(r[0]) if not monthly else f"{r[0]}-{r[1]:02d}" for r in rows]
    gap_idx = [i for i, r in enumerate(rows) if grain == "involved" and r[-1] is False]
    gaps = [(labels[i], rows[i][columns.index("people")], rows[i][columns.index("casualty_accidents")])
            for i in gap_idx]
    # one cheap count behind the road caveat (live: 0 — codes 1–4 only)
    other_roads = int(ctx.query(other_road_sql(y0, y1))[1][0][0]) if road_type != "all" else 0
    caveats = _caveats(measure, road_type, y0, y1, gaps, other_roads)
    heb_title = f"{label} לפי {GRANULARITY[granularity]} · {ROAD_TYPES[road_type][1]} · {y0}–{y1}"
    stamp = stamp_line(measure, granularity, road_type, y0, y1)   # rides in the spec for every view
    png = None
    if view == "chart":
        from .. import charts
        png = charts.line_chart(labels, [r[vi] for r in rows], ylabel=label, gaps=gap_idx,
                                monthly=monthly, title=heb_title,
                                badge=f"מכנה: {DENOM_COUNTS['label']}", caveats=caveats, stamp=stamp)
    basis = (f"{measure} by {granularity} | road_type={road_type} | {y0}-{y1} | {len(rows)} rows | "
             f"{grain} WHERE case_type_code = 1")
    spec = make_spec("accidents/trend", png_base64=png, basis=basis, rows=rows, columns=columns, sql=sql,
                     denominator=DENOM_COUNTS, caveats=caveats, measure=measure, granularity=granularity,
                     road_type=road_type, from_year=y0, to_year=y1, gap_periods=[g[0] for g in gaps],
                     stamp=stamp, y=measure)
    return dispatch(view, spec, f"מגמה · {label} לפי {GRANULARITY[granularity]} · {ROAD_TYPES[road_type][1]}")


def _caveats(measure, road_type, y0, y1, gaps, other_roads=0):
    """Most specific first: the data-gap line leads so it survives any PNG cap and opens the note.
    No ';' inside any line (it is the note's separator)."""
    out = []
    if len(gaps) == 1:
        p, people, acc = gaps[0]
        out.append(f"נתוני נפגעים (involved) חסרים ב-{p}: {people:,} רשומות מול {acc:,} תאונות — הערך מוצג כריק")
    elif gaps:
        people, acc = sum(g[1] for g in gaps), sum(g[2] for g in gaps)
        more = f" ועוד {len(gaps) - 3}" if len(gaps) > 3 else ""
        out.append(f"נתוני נפגעים (involved) חסרים ב-{len(gaps)} תקופות: {', '.join(g[0] for g in gaps[:3])}"
                   f"{more} ({people:,} רשומות מול {acc:,} תאונות) — הערכים מוצגים כריק")
    out += [CAVEAT_DATA_END, CAVEAT_COUNTS_NOT_RISK]
    if measure in ("killed", "fatal_accidents"):
        out.append("הרוגים (אנשים) ≠ תאונות קטלניות (אירועים)")
    if y0 <= 2021 and y1 >= 2020:
        out.append("2020–2021: ירידה זמנית בתקופת הקורונה")
    if road_type != "all":      # data-driven: live carries codes 1–4 only, so live always gets the second wording
        if other_roads:
            out.append(f"עירוני = road_type_code 1–2, לא-עירוני = 3–4 — {other_roads:,} תאונות עם קוד דרך אחר "
                       f"(5 = שטח) נכללות רק ב'כל הדרכים'")
        else:
            out.append("עירוני = road_type_code 1–2, לא-עירוני = 3–4 (כל הדרכים = סכום שניהם בנתונים אלה)")
    return out


# Declared LAST: Action.run is a required field evaluated at import — a forward reference to `run`
# is a NameError that the app turns into a "failed to import" Problem card.
ACTION = Action(
    name="trend", label="מגמות · trend",
    help="Counts over time from the casualty series (case_type_code = 1): accidents, fatal accidents, "
         "people killed / severely / slightly injured - by year or month, all roads or urban / non-urban. "
         "Counts, not risk: there is no exposure denominator. Periods whose person-level records are "
         "missing are shown as gaps, never as 0 (on the live copy: 2009).",
    inputs={
        "measure": Input(kind="choice", label="מדד", default="killed", choices=list(MEASURES),
                         help="accidents / fatal_accidents count events (table accidents); killed / "
                              "severe_injured / slight_injured count people (table involved). "
                              "killed != fatal_accidents."),
        "granularity": Input(kind="choice", label="רזולוציה", default="year", choices=list(GRANULARITY)),
        "road_type": Input(kind="choice", label="סוג דרך", default="all", choices=list(ROAD_TYPES),
                           help="urban = road_type_code 1-2, nonurban = 3-4; any other code would count "
                                "in all only (the live copy carries none); person measures join accidents "
                                "on (accident_id, case_type_code)"),
        "from_year": Input(kind="number", label="שנת התחלה", default=2005, help="2005-2024"),
        "to_year": Input(kind="number", label="שנת סיום", default=2024, help="data ends 2024-12-31"),
        "view": view_input("chart", ["chart", "table", "sql"]),
    },
    run=run)
