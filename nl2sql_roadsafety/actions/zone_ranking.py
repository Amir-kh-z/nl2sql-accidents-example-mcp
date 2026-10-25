# -*- coding: utf-8 -*-
"""zone_ranking (P14): traffic-analysis-zone ranking over accidents_by_taz — the database's own dark
geographic aggregate (2,637 zones nothing had ever queried). A CUMULATIVE, UNDATED snapshot (dossier
§4.7): no year input exists on purpose, and every answer carries the snapshot stamp + the universe
totals so the mismatch with the yearly series stays visible. The analytical point: the shipped
accident_index IS accidents per km2 (r = 1.000, recomputed live) and almost unrelated to per-capita
risk (r = 0.038) — the official index ranks how built-up a zone is, not how dangerous it is per person."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, dispatch, guard, make_spec, stamp, view_input
from ..sqlkit import (LAND_USE_CHOICES, LAND_USE_LABELS_FALLBACK, LAND_USE_SQL, ZONE_MEASURES,
                      ActionError, Refusal, as_choice, as_int, build_zone_ranking_sql, rows_safe,
                      series_totals_sql, zone_universe_sql)

VIEWS = ("chart", "table", "sql")
TITLE = "דירוג אזורי תנועה"
# columns, from the statement itself: label · value · accidents · population · area_km2 · land_use


@guard(TITLE)
def run(ctx, measure="per_capita", land_use="all", min_pop=500, top_n=20, view="chart"):
    measure = as_choice(measure, "measure", ZONE_MEASURES)
    land_use = as_choice(land_use, "land_use", LAND_USE_CHOICES)
    min_pop = as_int(min_pop, "min_pop")
    if min_pop < 1:
        raise ActionError(f"min_pop must be at least 1 (a zone with zero residents has no per-person rate); "
                          f"got {min_pop}.")
    top_n = as_int(top_n, "top_n")
    if not 1 <= top_n <= 100:
        raise ActionError(f"top_n must be between 1 and 100; got {top_n}.")
    view = as_choice(view, "view", VIEWS)
    lu = 0 if land_use == "all" else int(land_use)
    sql = build_zone_ranking_sql(measure, lu, min_pop, top_n)
    columns, raw = ctx.query(sql)
    rows = rows_safe(raw)
    if not rows:
        raise Refusal("אף אזור תנועה אינו עובר את הסינון שנבחר",
                      ["סף אוכלוסייה נמוך יותר (min_pop)", "ייעוד קרקע all", "מדד density על כל האזורים"],
                      what_to_do="להקטין את סף האוכלוסייה או להרחיב את ייעוד הקרקע")
    u_cols, u_raw = ctx.query(zone_universe_sql(lu, min_pop))
    u = dict(zip(u_cols, rows_safe(u_raw)[0]))
    s_cols, s_raw = ctx.query(series_totals_sql())
    s = dict(zip(s_cols, rows_safe(s_raw)[0]))
    # land-use labels: the code dictionary first; live carries no land-use field — the plugin map fills in
    db_labels = {int(r[0]): r[1] for r in ctx.query(LAND_USE_SQL)[1] if r[1]}
    labels_map = dict(LAND_USE_LABELS_FALLBACK)
    labels_map.update(db_labels)
    plugin_labels = not db_labels
    caveats = _caveats(measure, min_pop, u, s, plugin_labels, columns, rows)
    _, _, denom_kind, denom_label, axis_he = ZONE_MEASURES[measure]
    # ped_share's guard removes the no-injured zones — its stated scope is the zones that CAN carry the
    # measure, not the raw universe (refuter 2026-09-06: 'top 20 of 2,637' while 380 were excluded)
    in_scope = u["zones_in_scope"] - (u["no_injured"] if measure == "ped_share" else 0)
    denom = denominator(denom_kind, denom_label, snapshot=u["snapshot"], zones_in_scope=in_scope)
    stamp_text = stamp("zone_ranking", f"measure={measure}", f"land_use={land_use}",
                       f"min_pop={min_pop}", f"top {top_n}")
    png = None
    if view == "chart":
        from .. import charts
        scope_he = f" · {labels_map.get(lu, lu)}" if lu else ""
        png = charts.hbars([r[0] for r in rows], [r[1] for r in rows],
                           xlabel=axis_he,
                           annot=[f"{r[2]:,} תאונות" for r in rows],
                           max_rows=20,                     # the table face keeps everything
                           title=f"דירוג אזורי תנועה · {axis_he}{scope_he}",
                           badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
    basis = (f"zone_ranking | measure={measure} | land_use={land_use} | min_pop={min_pop} | "
             f"top {len(rows)} of {in_scope} zones | snapshot {u['snapshot']} | "
             f"cumulative undated universe (never compare with the yearly series)")
    spec = make_spec("accidents/zone_ranking", png_base64=png, basis=basis, rows=rows, columns=columns,
                     sql=sql, denominator=denom, caveats=caveats, measure=measure, land_use=land_use,
                     min_pop=min_pop, top_n=top_n, snapshot=u["snapshot"],
                     universe={"zones": u["zones"], "accidents": u["accidents"], "killed": u["killed"],
                               "injured": u["injured"], "population": u["population"]},
                     corr_index_density=u["corr_density"], corr_index_per_capita=u["corr_per_capita"],
                     below_min_pop=u["below_min_pop"], no_injured=u["no_injured"],
                     land_use_labels={str(k): v for k, v in sorted(labels_map.items())},
                     stamp=stamp_text, y="value")
    return dispatch(view, spec, TITLE)


def _caveats(measure, min_pop, u, s, plugin_labels, columns, rows):
    """Data-derived, most specific first; no ';' in any line (it is the note's separator)."""
    out = []
    if measure == "per_capita":
        out.append(f"סף אוכלוסייה מזערית ({min_pop:,} תושבים) הסיר {u['below_min_pop']:,} מתוך "
                   f"{u['zones_in_scope']:,} אזורים בתחולה — בלעדיו אזורי תעסוקה ותנועה עוברת מזנקים לראש הדירוג")
        # the population-vintage line belongs to the ONE measure whose denominator is population
        # (refuter 2026-09-06: density/ped_share carried a caveat about a denominator they do not use)
        out.append(f"מכנה האוכלוסייה הוא אומדן שנה אחת (אוכלוסיית 2018, {u['population']:,} תושבים בכל האזורים) "
                   f"מול תאונות מצטברות של כחמש שנים")
    if measure == "density" and u["corr_density"] is not None and u["corr_per_capita"] is not None:
        out.append(f"המדד הרשמי accident_index הוא מדד צפיפות ולא סיכון לנפש — מתאם {u['corr_density']:.3f} "
                   f"עם תאונות לקמ״ר לעומת {u['corr_per_capita']:.2f} עם תאונות לאלף תושבים — "
                   f"דירוג הצפיפות שונה כמעט לחלוטין מדירוג הסיכון לתושב")
    if measure == "ped_share":
        out.append(f"{u['no_injured']:,} אזורים ללא נפגעים כלל הוחרגו מחישוב אחוז הולכי הרגל")
        # tiny denominators are headline noise (refuter 2026-09-06: the live top-20 was a flat wall of
        # 100.0% zones with 1-4 accidents) — count them on the SHOWN rows and say so
        ii = columns.index("injured") if "injured" in columns else -1
        if ii >= 0:
            tiny = sum(1 for r in rows if (r[ii] or 0) < 20)
            if tiny:
                out.append(f"{tiny} מתוך {len(rows)} השורות המוצגות עם פחות מעשרים נפגעים בסך הכול — "
                           f"שיעור על מכנה זעיר רועש · בשוויון אחוזים מדורג קודם מי שמכנהו גדול")
    out.append("התאונות משויכות לאזור האירוע ולא למקום מגורי הנפגעים — תנועה עוברת ואזורי תעסוקה "
               "מנפחים מדדים לנפש")
    out.append(f"צילום מצטבר חד-פעמי ללא ממד זמן (חותמת פרסום {u['snapshot']}) — אין להשוות את המספרים "
               f"לפעולות השנתיות כמו trend או heat_matrix")
    out.append(f"סך הצילום: {u['accidents']:,} תאונות, {u['killed']:,} הרוגים ו-{u['injured']:,} נפגעים "
               f"לעומת {s['series_accidents']:,} תאונות עם נפגעים ו-{s['series_killed']:,} הרוגים בסדרה "
               f"השנתית המלאה — יקום נתונים נפרד")
    if plugin_labels:
        out.append("תוויות ייעוד הקרקע ממפת התוסף — מילון הקודים אינו מכיל שדה ייעוד קרקע")
    return out


# Declared LAST (Action.run is evaluated at import).
ACTION = Action(
    name="zone_ranking", label="דירוג אזורי תנועה · zone_ranking",
    help="Ranking of traffic analysis zones (accidents_by_taz, 2,637 zones) from the CUMULATIVE, undated "
         "publication snapshot - a separate universe from the yearly series, never compare the numbers "
         "(the caveats carry both sides' totals). Measures: per_capita = accidents per 1,000 residents "
         "(2018 population, min_pop filter against through-traffic zones), density = accidents per square "
         "km (exactly what the official accident_index tracks, r = 1.0), ped_share = pedestrian share of "
         "the injured. No year input exists on purpose.",
    inputs={
        "measure": Input(kind="choice", label="מדד", default="per_capita", choices=list(ZONE_MEASURES),
                         help="per_capita = per 1,000 residents (2018); density = per square km; "
                              "ped_share = pedestrian share of the injured"),
        "land_use": Input(kind="choice", label="ייעוד קרקע", default="all", choices=list(LAND_USE_CHOICES),
                          help="all, or a land-use code: 1 residential, 2 commerce, 3 industry, "
                               "4 institutions, 5 other"),
        "min_pop": Input(kind="number", label="אוכלוסייה מזערית", default=500,
                         help="per_capita only: exclude zones below this 2018 population (>= 1); "
                              "through-traffic zones with tiny populations inflate per-capita absurdly"),
        "top_n": Input(kind="number", label="מספר אזורים", default=20, help="1-100"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
