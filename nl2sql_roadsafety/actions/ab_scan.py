# -*- coding: utf-8 -*-
"""ab_scan (the discoverer): sweep every traffic-count segment across every possible change year for its
strongest network-adjusted difference-in-differences candidate, ranked by |z| — a RANK SCORE only, never a
test: after many correlated overlapping windows a 95% CI on the winner would be anti-conservative, so none
is shown and every answer routes the chosen row to before_after for the deep check (whose single-candidate
interval, after a sweep, is itself post-selection and descriptive). Counting rule = before_after's: one
literal latest-vintage km range per unit applied to ALL years, and the event year excluded from both
windows ([e-w..e-1] vs [e+1..e+w]) — so the hand-off reproduces the same cells."""
from __future__ import annotations

import math

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, dispatch, guard, make_spec, stamp, view_input
from ..sqlkit import (MIN_CELL_DEFAULT, NAMES_CTE, STATIC_GEOMETRY_CTE, ActionError, Refusal, as_choice,
                      as_int, build_ab_scan_sql, did_math, double_did, rows_safe, year_range)

VIEWS = ("chart", "table", "sql")
TITLE = "סריקת שינויים · מועמדים לבדיקה"
COLS = ["site_key", "label", "change_year", "before", "after", "ratio", "z", "controlled", "direction"]
IMPROVE, WORSEN = "שיפור", "החמרה"
IMPROVE_COLOR, WORSEN_COLOR = "#0d9488", "#c0392b"      # the diverging convention: below one teal, above one red


def _r4(x):
    return None if x is None else round(x, 4)


@guard(TITLE)
def run(ctx, from_year=2008, to_year=2024, window_years=2, min_cell=MIN_CELL_DEFAULT, road=0, top_n=20,
        view="chart"):
    view = as_choice(view, "view", VIEWS)
    y0, y1 = year_range(from_year, to_year)
    w = max(1, min(3, as_int(window_years, "window_years")))    # clamped by design (before_after errors instead)
    mc = as_int(min_cell, "min_cell")
    if mc < 1:
        raise ActionError(f"min_cell must be at least 1; got {mc}.")
    road = as_int(road, "road")
    if road < 0:
        raise ActionError(f"road must be 0 (all roads) or a road number; got {road}.")
    top_n = as_int(top_n, "top_n")
    if not 1 <= top_n <= 50:
        raise ActionError(f"top_n must be between 1 and 50; got {top_n}.")
    e0, e1 = y0 + w, y1 - w                                     # before [e-w..e-1], after [e+1..e+w] — the event year
    if e0 > e1:                                                 # excluded from both, exactly before_after's convention
        raise Refusal(f"הטווח {y0}–{y1} קצר מדי לחלון של {w}+{w} ושנת אירוע מוחרגת — אף שנת אירוע לא נכנסת",
                      [f"טווח של לפחות {2 * w + 1} שנים", "חלון קצר יותר (window_years)"])
    sql = build_ab_scan_sql(y0, y1, road)
    _, raw = ctx.query(sql)
    units, net = {}, {}
    for r in rows_safe(raw):
        if r[0] == "unit":
            units.setdefault((int(r[1]), int(r[2])), {})[int(r[3])] = (int(r[4]), int(r[5]))
        else:
            net[int(r[3])] = (int(r[4]), int(r[5]))
    if not units:
        scope = f"בכביש {road} " if road else ""
        raise Refusal(f"לא נמצאו תאונות על מקטעי ספירת תנועה {scope}בטווח שנבחר",
                      ["road = 0 לכל הכבישים", "hotspot_map לפריסת הספירות בטווח"])

    def cells(by_year, e, idx):
        b = sum(by_year.get(y, (0, 0))[idx] for y in range(e - w, e))
        a = sum(by_year.get(y, (0, 0))[idx] for y in range(e + 1, e + w + 1))    # event year e in NEITHER cell
        return b, a

    cands = []
    for key in sorted(units):
        by_year = units[key]
        best = None
        for e in range(e0, e1 + 1):
            sb, sa = cells(by_year, e, 0)
            nb, na = cells(net, e, 0)
            d = did_math(sb, sa, nb, na, mc)                    # did_math's n/a discipline skips thin windows
            if d["status"] != "ok":
                continue
            z = math.log(d["ratio"]) / math.sqrt(d["se2"])
            if best is None or abs(z) > abs(best[0]):           # strict: the earliest year wins a tie
                best = (z, e, sb, sa, d)
        if best is None:
            continue
        z, e, sb, sa, d = best
        db, da = cells(by_year, e, 1)
        ndb, nda = cells(net, e, 1)
        controlled = "n/a"
        if min(db, da, ndb, nda) >= mc:                         # all four damage cells support the double ratio
            dbl = double_did(d, did_math(db, da, ndb, nda, mc))
            if dbl["status"] == "ok":
                controlled = _r4(dbl["ratio"])
        cands.append({"key": key, "z": z, "year": e, "before": sb, "after": sa, "ratio": d["ratio"],
                      "controlled": controlled})
    n_units, n_events = len(units), e1 - e0 + 1
    if not cands:
        raise Refusal(f"אף יחידה לא העמידה מועמד — בכל היחידות ובכל שנות האירוע תא אתר מתחת ל-{mc} רשומות",
                      ["min_cell נמוך יותר", "חלון רחב יותר (window_years)", "before_after לאתר מוכר"],
                      detail=f"{n_units} units x {n_events} event years, min_cell {mc}")
    names = _names(ctx, {c["key"] for c in cands})
    for c in cands:
        r_, s_ = c["key"]
        nm = names.get(c["key"])
        c["site_key"] = nm[2] if nm else f"{r_}/{s_}"
        c["label"] = (f"{r_}/{s_} · {nm[0] or ''} ← {nm[1] or ''}" if nm and (nm[0] or nm[1])
                      else f"{r_}/{s_}")
    ranked = sorted(cands, key=lambda c: (-abs(c["z"]), c["site_key"], c["year"]))[:top_n]
    top = ranked[0]
    caveats = [
        f"נסרקו {n_units} יחידות על פני {n_events} שנות אירוע — ללא תיקון להשוואות מרובות · "
        f"ציון z לדירוג בלבד, לא מבחן",
        "הספירה על תוואי הקילומטרים של מפקד המקטעים העדכני ביותר בכל השנים — "
        "מספרים עשויים להיות שונים מספירה לפי גאומטריה שנתית · מועמד שנמצא טעון אימות ב-before_after",
        "נסיגה לממוצע: תקופת-לפני קיצונית נוטה לחזור לרמתה גם ללא שינוי באתר — חלק מהמועמדים הם רעש שנבחר",
        "גילוי ואינו ייחוס: שנת המועמד היא השערה מהספירות בלבד — הסיבה (שינוי פיזי, אכיפה, תנועה) אינה בנתונים",
        "מקטעי ספירת תנועה בלבד — לצמתים אין זהות חשיפה בסריקה הזו (ספירות לצמתים: hotspot_map)",
        f"להמשך בדיקה של השורה המובילה: before_after עם האתר {top['site_key']} ושנת שינוי {top['year']} — "
        f"שם נבחן המועמד לעומק (תאי הבקרה, יחס מבוקר-נזק ורגישות לחלון) · "
        f"אחרי סריקה גם רווח בר-סמך למועמד יחיד הוא לאחר-בחירה ויש לקרוא אותו כתיאורי",
    ]
    denom = denominator("exposure", "קבוצת השוואה: כל הרשת הארצית (שתי הסדרות) · "
                                    "פרוקסי לחשיפה ליחס המבוקר: סדרת הנזק-בלבד (case_type_code = 3)")
    stamp_text = stamp("ab_scan", f"road={road or 'all'}", f"{y0}-{y1}", f"w{w}")
    basis = (f"ab_scan | road={road or 'all'} | {y0}-{y1} | window {w}+{w} | min_cell {mc} | control=network | "
             f"{n_units} units x {n_events} event years | candidates {len(cands)} | top {len(ranked)} | "
             f"rank=|z| (no CI by design)")
    png = None
    if view == "chart":
        from .. import charts
        png = charts.hbars(
            [c["label"] for c in ranked], [abs(c["z"]) for c in ranked],
            xlabel="ערך מוחלט של z — ציון דירוג של DiD מותאם-רשת (לא מבחן)",
            annot=[f"{c['year']}: z={_r4(c['z']):+g} r={_r4(c['ratio']):g}" for c in ranked],
            colors=[WORSEN_COLOR if c["z"] > 0 else IMPROVE_COLOR for c in ranked],
            max_rows=15,                    # the P8 rule: the drawn rows cap, the table face keeps everything
            title=f"סריקת שינויים · {'כביש ' + str(road) if road else 'כל הכבישים'} · {y0}–{y1} · חלון {w}+{w}",
            badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
    out_rows = [[c["site_key"], c["label"], c["year"], c["before"], c["after"], _r4(c["ratio"]), _r4(c["z"]),
                 c["controlled"], IMPROVE if c["ratio"] < 1 else WORSEN] for c in ranked]
    spec = make_spec("accidents/ab_scan", png_base64=png, basis=basis, rows=out_rows, columns=COLS, sql=sql,
                     denominator=denom, caveats=caveats, stamp=stamp_text, road=road, from_year=y0, to_year=y1,
                     window_years=w, min_cell=mc, top_n=top_n, units_scanned=n_units, event_years=n_events,
                     candidates=len(cands),
                     handoff={"action": "before_after", "site": top["site_key"], "change_year": top["year"],
                              "window_years": w, "min_cell": mc},
                     y="z")
    return dispatch(view, spec, TITLE)


def _names(ctx, keys):
    """(name_from, name_to, site_key) per (road, seg) — the latest-vintage names and the before_after key
    syntax, exactly as hotspot_map / site_ranking print them."""
    sql = (f"WITH {STATIC_GEOMETRY_CTE},\n{NAMES_CTE}\n"
           f"SELECT g.road, g.seg, n.name_from, n.name_to,\n"
           f"       printf('road:%d/%g-%g', g.road, g.km_from, g.km_to) AS site_key\n"
           f"FROM latest_segments g LEFT JOIN names n USING (road, seg)")
    out = {}
    for r in rows_safe(ctx.query(sql)[1]):
        if (r[0], r[1]) in keys:
            out[(r[0], r[1])] = (r[2], r[3], r[4])
    return out


ACTION = Action(
    name="ab_scan", label="סריקת שינויים · ab_scan",
    help="Change-point DISCOVERY over every traffic-count segment: for each unit and each event year e, a "
         "network-adjusted difference-in-differences of casualty accidents ([e-w..e-1] vs [e+1..e+w], the event "
         "year excluded from both windows and the whole national network as the control - before_after's exact "
         "convention, on the unit's latest-vintage km range applied to all years) keeps the unit's strongest "
         "candidate; candidates rank by |z| = |ln ratio| / SE - a RANK SCORE only, because after many correlated "
         "overlapping windows a 95% CI on the winner would be anti-conservative, so none is shown and the caveat "
         "routes the chosen row to before_after (site key + change year) for the deep check - noting that even "
         "that single-candidate interval is post-selection after a sweep and reads as descriptive. A damage-only "
         "controlled double ratio is added where all four damage cells >= min_cell. Segments only: junctions "
         "carry no exposure identity here.",
    inputs={
        "from_year": Input(kind="number", label="שנת התחלה", default=2008, help="2005-2024"),
        "to_year": Input(kind="number", label="שנת סיום", default=2024, help="2005-2024"),
        "window_years": Input(kind="number", label="חלון בשנים", default=2, help="1-3 years on each side (clamped)"),
        "min_cell": Input(kind="number", label="מינימום לתא", default=MIN_CELL_DEFAULT,
                          help="a site cell below this is skipped (did_math's n/a rule)"),
        "road": Input(kind="number", label="כביש", default=0, help="0 = all roads; otherwise a road number"),
        "top_n": Input(kind="number", label="מספר מועמדים", default=20, help="1-50"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
