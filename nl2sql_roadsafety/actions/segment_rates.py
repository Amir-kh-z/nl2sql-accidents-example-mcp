# -*- coding: utf-8 -*-
"""segment_rates (use ב, descriptive): casualty accidents per 100 M vehicle-km per traffic count segment,
numerator and denominator over the SAME units CTE, with a Byar Poisson interval computed in SQL. A
plugin-defined instrument — the methodology report defines no per-vehicle-km segment rate — and it says so."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, dispatch, guard, make_spec, stamp, view_input
from ..sqlkit import (EXPOSURE_YEARS, SEGMENT_ORDERS, SEGMENT_SEVERITY, Refusal, ActionError, as_choice, as_int,
                      build_segment_rates_sql, exposure_year_range, rows_safe, segment_count_sql,
                      segment_coverage_sql)

VIEWS = ("chart", "table", "sql")
SEV_HE = {"all": "כל התאונות", "ksi": "KSI"}


@guard("שיעורי תאונות למקטע")
def run(ctx, road=0, from_year=2017, to_year=2024, severity="all", order_by="rate_lo", top_n=10, view="chart"):
    severity = as_choice(severity, "severity", SEGMENT_SEVERITY)
    order_by = as_choice(order_by, "order_by", SEGMENT_ORDERS)
    view = as_choice(view, "view", VIEWS)
    y0, y1 = exposure_year_range(from_year, to_year)
    road = as_int(road, "road")
    if road < 0:
        raise ActionError(f"road must be 0 (all roads) or a road number; got {road}.")
    top_n = as_int(top_n, "top_n")
    if not 1 <= top_n <= 30:
        raise ActionError(f"top_n must be between 1 and 30; got {top_n}.")
    n_segments, n_roads = ctx.query(segment_count_sql(road, y0, y1))[1][0]
    if road and not n_segments:
        n_all = ctx.query(segment_count_sql(0, EXPOSURE_YEARS[0], EXPOSURE_YEARS[1]))[1][0][1]
        raise Refusal(f"אין נתוני תנועה (as-of) לכביש {road} בשנים {y0}–{y1}",
                      ["road = 0 לכל הכבישים", f"כבישים עם נתוני תנועה: {n_all} מספרי כביש (as-of {EXPOSURE_YEARS[0]}–{EXPOSURE_YEARS[1]})"])
    sql = build_segment_rates_sql(road, y0, y1, severity, order_by, top_n)
    columns, raw = ctx.query(sql)
    rows = rows_safe(raw)
    cov_sql = segment_coverage_sql(y0, y1, road)                     # coverage of the scope shown (the road, or all)
    cov_rows = rows_safe(ctx.query(cov_sql)[1])
    total = sum(r[1] for r in cov_rows)
    matched = sum(r[2] for r in cov_rows)
    pct = round(100.0 * matched / total, 1) if total else 0.0
    max_gap = max((r[-1] or 0 for r in rows), default=0)
    caveats = _caveats(cov_rows, max_gap, _fill_validation(ctx))
    scope = "" if not road else f" בכביש {road}"
    label = (f"ק״מ-רכב ממדידות ADT as-of (אורך × Σ ADT × 365) · כיסוי {matched:,} מתוך {total:,} "
             f"תאונות לא-עירוניות עם נפגעים{scope} ({pct}%)")
    denom = denominator("exposure", label, matched=matched, total=total, pct=pct, segments=n_segments)
    road_he = "כל הכבישים" if not road else f"כביש {road}"
    what = "תאונות עם נפגעים" if severity == "all" else "תאונות KSI"
    heb_title = f"{what} ל-100 מיליון ק״מ-רכב · {road_he} · {y0}–{y1}"
    stamp_text = stamp("segment_rates", f"road={road or 'all'}", severity, order_by, f"{y0}-{y1}")
    png = None
    if view == "chart":
        from .. import charts
        vi = columns.index("rate_per_100m_vkm")
        png = charts.hbars(
            [f"{r[0]}/{r[1]} · {r[2] or ''} ← {r[3] or ''}" for r in rows], [r[vi] for r in rows],   # ← points toward name_to in RTL
            xlabel=f"{what} ל-100 מיליון ק״מ-רכב", lo=[r[columns.index("rate_lo")] for r in rows],
            hi=[r[columns.index("rate_hi")] for r in rows],
            annot=_annot(columns, rows, severity),
            title=heb_title, badge=f"מכנה: {label}", caveats=caveats, stamp=stamp_text)
    basis = (f"segment_rates | road={road or 'all'} | severity={severity} | order={order_by} | {y0}-{y1} | "
             f"top {len(rows)} of {n_segments} segments | coverage {matched}/{total} ({pct}%)")
    spec = make_spec("accidents/segment_rates", png_base64=png, basis=basis, rows=rows, columns=columns, sql=sql,
                     denominator=denom, caveats=caveats, road=road, severity=severity, order_by=order_by,
                     from_year=y0, to_year=y1, n_segments=n_segments, stamp=stamp_text,
                     coverage={"matched": matched, "total": total, "pct": pct, "by_year": cov_rows},
                     coverage_sql=cov_sql, y="rate_per_100m_vkm")
    return dispatch(view, spec, f"שיעורי תאונות למקטע · {SEV_HE[severity]} · {'כל הכבישים' if not road else 'כביש נבחר'}")


def _annot(columns, rows, severity):
    """Per-bar text: the count that is the numerator of the plotted rate, plus the exposure."""
    mi = columns.index(SEGMENT_SEVERITY[severity])
    ai, vi = columns.index("accidents"), columns.index("vkm_millions")
    if severity == "all":
        return [f"{r[ai]} · {r[vi]} M" for r in rows]
    return [f"{r[mi]} KSI מתוך {r[ai]} · {r[vi]} M" for r in rows]


def _fill_validation(ctx):
    """traffic_fill_validation (gap_years → median APE %) when the connection has it; else the dossier constants."""
    try:
        if "traffic_fill_validation" in ctx.tables():
            rows = ctx.query("SELECT gap_years, median_ape_pct FROM traffic_fill_validation ORDER BY gap_years")[1]
            got = {int(g): float(a) for g, a in rows if g is not None and a is not None}
            if got:
                return got
    except Exception:  # noqa: BLE001 — a caveat detail, never a failure
        pass
    return {1: 12.4, 2: 17.3, 3: 21.6, 4: 34.6}


def _caveats(cov_rows, max_gap, ape):
    out = []
    if cov_rows:
        tail = "תאונות ללא מקטע תואם אינן בשני הצדדים"
        if len(cov_rows) == 1:
            out.append(f"כיסוי {cov_rows[0][3]}% ({cov_rows[0][0]}) — {tail}")
        else:
            pcts = [r[3] for r in cov_rows]
            lo = min(cov_rows, key=lambda r: (r[3], r[0]))
            hi = max(cov_rows, key=lambda r: (r[3], r[0]))
            up = all(b >= a for a, b in zip(pcts, pcts[1:]))
            down = all(b <= a for a, b in zip(pcts, pcts[1:]))
            shape = "עולה" if up else "יורד" if down else "לא מונוטוני"
            out.append(f"כיסוי לפי שנה: {lo[3]}% ({lo[0]}) עד {hi[3]}% ({hi[0]}) — {shape}, {tail}")
    out.append("מדד תיאורי של התוסף: הדו״ח המתודולוגי אינו מגדיר שיעור לק״מ-רכב למקטע (החשיפה נכנסת בו כמשתנה מסביר)")
    out.append("יחידה = מקטע ספירת תנועה (road, seg), לא יחידת 5 ק״מ כבדו״ח · גרסת גיאומטריה אחת לכל מקטע-שנה · "
               "שמות לפי הגרסה האחרונה · ק״מ 0 = לא קודד")
    lo_ape, hi_ape = ape.get(1, 12.4), ape.get(3, ape.get(max(ape), 21.6))
    gap4 = f", {ape[4]:g}% בפער 4" if 4 in ape else ""
    out.append(f"ADT ≠ AADT: בשורות המוצגות ספירה מלפני עד {max_gap} שנים "
               f"(סטייה חציונית {lo_ape:g}–{hi_ape:g}% בפער 1–3 שנים{gap4}, מעבר לכך מעט זוגות)")
    out.append("רווח בר-סמך 95% פואסוני (קירוב Byar) — מיון לפי הגבול התחתון · שיעורים ממעט תאונות אינם יציבים")
    out.append(f"לא-עירוני {EXPOSURE_YEARS[0]}+ בלבד (road_type_code 3–4) · שכבת as-of בלבד, לא traffic_adt_filled")
    return out


ACTION = Action(
    name="segment_rates", label="מקטעים · segment_rates",
    help="Casualty accidents per 100 million vehicle-km per interurban traffic-count segment (2017-2024, as-of ADT "
         "x length x 365 over one geometry vintage per segment-year), with a 95% Poisson interval computed in SQL. "
         "A plugin-defined descriptive instrument: the methodology report defines no per-km segment rate.",
    inputs={
        "road": Input(kind="number", label="כביש", default=0, help="0 = all roads; otherwise a road number of traffic_adt_asof"),
        "from_year": Input(kind="number", label="שנת התחלה", default=2017, help="2017-2024 (the as-of exposure layer)"),
        "to_year": Input(kind="number", label="שנת סיום", default=2024, help="2017-2024"),
        "severity": Input(kind="choice", label="חומרה", default="all", choices=list(SEGMENT_SEVERITY),
                          help="all = every casualty accident; ksi = fatal + severe"),
        "order_by": Input(kind="choice", label="מיון", default="rate_lo", choices=list(SEGMENT_ORDERS),
                          help="rate_lo = lower bound of the 95% Poisson CI (conservative); rate = point estimate; count = accidents"),
        "top_n": Input(kind="number", label="מספר שורות", default=10, help="1-30"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
