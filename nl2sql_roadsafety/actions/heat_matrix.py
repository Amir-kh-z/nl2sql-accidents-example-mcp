# -*- coding: utf-8 -*-
"""heat_matrix (P13, descriptive): casualty accidents by day of week × hour of day — a zero-filled
7×24 grid (exactly 168 cells, a quiet cell is a real zero, never a hole). Honest about unknowns:
rows the grid cannot place (unknown/invalid hour or day) are excluded AND counted into a caveat —
on the live copy that count is zero (hour_of_day is complete in both series). Counts, not risk."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import (CAVEAT_COUNTS_NOT_RISK, CAVEAT_DATA_END, denominator, dispatch, guard,
                        make_spec, stamp, view_input)
from ..sqlkit import (DAY_LABELS_SQL, DAY_NAMES_HE, as_choice, build_heat_matrix_sql,
                      heat_matrix_unknown_sql, rows_safe, year_range)

VIEWS = ("chart", "table", "sql")


@guard("מטריצת יום ושעה")
def run(ctx, from_year=2015, to_year=2024, view="chart"):
    view = as_choice(view, "view", VIEWS)
    y0, y1 = year_range(from_year, to_year)
    sql = build_heat_matrix_sql(y0, y1)
    columns, raw = ctx.query(sql)
    rows = rows_safe(raw)
    placed = sum(r[2] for r in rows)
    total, unknown = (int(v) for v in rows_safe(ctx.query(heat_matrix_unknown_sql(y0, y1))[1])[0])
    # day labels from the pre-joined column (dossier rule); the plugin map fills a day the data never saw
    db_labels = {int(r[0]): r[1] for r in ctx.query(DAY_LABELS_SQL)[1] if r[1]}
    day_labels = [db_labels.get(d) or DAY_NAMES_HE[d] for d in range(1, 8)]
    caveats = _caveats(unknown, total)
    denom = denominator("counts", "ספירות תאונות עם נפגעים — ללא מכנה חשיפה")
    stamp_text = stamp("heat_matrix", f"{y0}-{y1}")
    png = None
    if view == "chart":
        from .. import charts
        grid = [[0] * 24 for _ in range(7)]
        for d, h, n in rows:
            grid[int(d) - 1][int(h)] = int(n)
        png = charts.heat_png(grid, day_labels, cbar_label="תאונות עם נפגעים",
                              title=f"תאונות עם נפגעים לפי יום בשבוע ושעה · {y0}–{y1}",
                              badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
    basis = (f"heat_matrix | {y0}-{y1} | 7x24 grid, {len(rows)} cells | {placed} accidents placed | "
             f"unknown hour/day excluded: {unknown}")
    spec = make_spec("accidents/heat_matrix", png_base64=png, basis=basis, rows=rows, columns=columns,
                     sql=sql, denominator=denom, caveats=caveats, from_year=y0, to_year=y1,
                     day_labels=day_labels, unknown_hour_excluded=unknown, stamp=stamp_text,
                     x="hour_of_day", y="accidents")
    return dispatch(view, spec, "מטריצת יום ושעה")


def _caveats(unknown, total):
    """Data-driven, most specific first; no ';' in any line (it is the note's separator)."""
    out = []
    if unknown:
        pct = round(100.0 * unknown / total, 1) if total else 0.0
        out.append(f"{unknown:,} תאונות ללא שעה או יום תקינים הוחרגו מהמטריצה ({pct}% מהטווח)")
    else:
        out.append("לכל התאונות בטווח שעה ויום ידועים — אף תאונה לא הוחרגה")
    out.append(CAVEAT_COUNTS_NOT_RISK)
    out.append("הדפוס משקף גם מתי נוסעים בכלל — שעה עמוסה אינה בהכרח מסוכנת יותר לנסיעה בודדת")
    out.append(CAVEAT_DATA_END)
    return out


# Declared LAST (Action.run is evaluated at import).
ACTION = Action(
    name="heat_matrix", label="מטריצת יום ושעה · heat_matrix",
    help="Casualty accidents by day of week x hour of day - a zero-filled 7x24 grid (exactly 168 cells; "
         "a quiet cell is a real zero). Rows whose hour or day is unknown are excluded and counted in a "
         "caveat (live copy: none - hour_of_day is complete). Counts, not risk: no exposure denominator, "
         "busy hours are also just busy roads.",
    inputs={
        "from_year": Input(kind="number", label="שנת התחלה", default=2015, help="2005-2024"),
        "to_year": Input(kind="number", label="שנת סיום", default=2024, help="data ends 2024-12-31"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
