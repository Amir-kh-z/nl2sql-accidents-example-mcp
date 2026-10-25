# -*- coding: utf-8 -*-
"""vehicle_cells_ranking (use ד): Empirical-Bayes involvement rate per (manufacture_year × cc_band) cell over
real exposure (million vehicle-km), M = 200 Mkm, tiers by EB quintiles — the honest resolution: no make/model
can be linked to accident records."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, dispatch, guard, make_spec, stamp, view_input
from ..sqlkit import (CELL_METRICS, EB_M_MKM, as_choice, build_vehicle_cells_cohort_sql,
                      build_vehicle_cells_sql, rows_safe, vehicle_cells_excluded_sql)

VIEWS = ("chart", "table", "sql")
BANDS = {"all": "כל נפחי המנוע", "known_engine": "נפח מנוע ידוע בלבד"}
GROUPS = {"cell": "תא בודד (שנת ייצור × נפח)", "cohort": "עוקבת שנת ייצור"}


@guard("דירוג תאי רכב")
def run(ctx, metric="involvements", bands="all", group="cell", view="chart"):
    metric = as_choice(metric, "metric", CELL_METRICS)
    bands = as_choice(bands, "bands", BANDS)
    group = as_choice(group, "group", GROUPS)
    view = as_choice(view, "view", VIEWS)
    if group == "cohort":
        return _run_cohort(ctx, metric, bands, view)
    sql = build_vehicle_cells_sql(metric, bands)
    columns, raw = ctx.query(sql)
    rows = rows_safe(raw)
    ex_cols, ex_raw = ctx.query(vehicle_cells_excluded_sql())
    ex = dict(zip(ex_cols, rows_safe(ex_raw)[0]))
    ci = {c: columns.index(c) for c in columns}
    n = len(rows)
    tiers = {t: sum(1 for r in rows if r[ci["tier"]] == t) for t in ("safest", "regular", "highest_risk")}
    global_rate = rows[0][ci["global_rate_per_mkm"]] if rows else None
    n_band0 = sum(1 for r in rows if r[ci["cc_band"]] == 0)
    ev = max((r[ci["ev_share"]] or 0.0 for r in rows if r[ci["cc_band"]] == 0), default=0.0)
    fleet_all = ex["fleet_all"] or 0
    pct_excluded = round(100.0 * (ex["fleet"] or 0) / fleet_all, 1) if fleet_all else 0.0
    dropped_band0 = ex["band0_cells"] if bands == "known_engine" else 0
    pct_band0 = round(100.0 * (ex["band0_fleet"] or 0) / fleet_all, 1) if fleet_all else 0.0
    caveats = _caveats(ex, pct_excluded, n_band0, ev, global_rate, dropped_band0, pct_band0)
    metric_he = CELL_METRICS[metric][1]
    label = f"מיליוני ק״מ-רכב (exposure_mkm מאומדני מד-אוץ) · {n} תאים, {ex['cells']} הוחרגו (חשיפה אפס)"
    if dropped_band0:
        label += f" ועוד {dropped_band0} תאי נפח 0 הושמטו לפי בחירה"
    denom = denominator("exposure", label, cells=n, excluded=ex["cells"], dropped_band0=dropped_band0)
    stamp_text = stamp("vehicle_cells_ranking", metric, bands, f"M={EB_M_MKM:g}")
    png = None
    if view == "chart":
        from .. import charts
        top = [r for r in rows if r[ci["tier"]] == "highest_risk"][::-1][:10]     # highest EB first
        bottom = [r for r in rows if r[ci["tier"]] == "safest"][:10]
        pick = [{"label": f"{r[ci['manufacture_year']]} · {r[ci['cc_band_label']]} סמ״ק", "eb": r[ci["eb_rate_per_mkm"]],
                 "raw": r[ci["raw_rate_per_mkm"]], "tier": r[ci["tier"]]} for r in top + bottom]
        png = charts.tier_bars(pick, global_rate=global_rate or 0.0, xlabel=f"{metric_he} למיליון ק״מ-רכב",
                               gap_text=f"… {tiers['regular']} תאים רגילים",
                               title=f"דירוג תאי רכב לפי שיעור EB · {metric_he} למיליון ק״מ",
                               badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
    basis = (f"vehicle_cells_ranking | metric={metric} | bands={bands} | M={EB_M_MKM:g} Mkm | {n} cells "
             f"({ex['cells']} excluded, exposure 0) | global {global_rate} per Mkm | "
             f"tiers {tiers['safest']}/{tiers['regular']}/{tiers['highest_risk']}")
    spec = make_spec("accidents/vehicle_cells_ranking", png_base64=png, basis=basis, rows=rows, columns=columns,
                     sql=sql, denominator=denom, caveats=caveats, metric=metric, bands=bands, group="cell",
                     tiers=tiers, global_rate=global_rate, excluded=ex, stamp=stamp_text,
                     x="cc_band_label", y="eb_rate_per_mkm")
    return dispatch(view, spec, f"דירוג תאי רכב · {metric_he}")


def _run_cohort(ctx, metric, bands, view):
    """P13 cohort roll-up: the SAME cube summed over cc_band per manufacture_year, then the SAME EB shrinkage
    on the cohort cells. The honest exposure: sums of the cube's real per-cell exposure_mkm — never the biased
    fleet × years denominator."""
    sql = build_vehicle_cells_cohort_sql(metric, bands)
    columns, raw = ctx.query(sql)
    rows = rows_safe(raw)
    ex_cols, ex_raw = ctx.query(vehicle_cells_excluded_sql())
    ex = dict(zip(ex_cols, rows_safe(ex_raw)[0]))
    ci = {c: columns.index(c) for c in columns}
    n = len(rows)
    tiers = {t: sum(1 for r in rows if r[ci["tier"]] == t) for t in ("safest", "regular", "highest_risk")}
    # the prior's global rate = Σevents/Σexposure over the included cells — recomputed from the cohort sums
    # (identical by construction: cohorts partition the included cells)
    sum_ev = sum(r[ci["involvements"]] for r in rows)
    sum_ex = sum(r[ci["exposure_mkm"]] for r in rows)
    global_rate = round(sum_ev / sum_ex, 5) if sum_ex else None
    fleet_all = ex["fleet_all"] or 0
    pct_excluded = round(100.0 * (ex["fleet"] or 0) / fleet_all, 1) if fleet_all else 0.0
    dropped_band0 = ex["band0_cells"] if bands == "known_engine" else 0
    pct_band0 = round(100.0 * (ex["band0_fleet"] or 0) / fleet_all, 1) if fleet_all else 0.0
    caveats = _cohort_caveats(ex, pct_excluded, global_rate, dropped_band0, pct_band0, bands, tiers)
    metric_he = CELL_METRICS[metric][1]
    label = f"מיליוני ק״מ-רכב (סכום exposure_mkm של תאי העוקבה) · {n} עוקבות שנת ייצור, {ex['cells']} תאים הוחרגו (חשיפה אפס)"
    if dropped_band0:
        label += f" ועוד {dropped_band0} תאי נפח 0 הושמטו לפי בחירה"
    denom = denominator("exposure", label, cohorts=n, excluded=ex["cells"], dropped_band0=dropped_band0)
    stamp_text = stamp("vehicle_cells_ranking", metric, bands, "cohort", f"M={EB_M_MKM:g}")
    png = None
    if view == "chart":
        from .. import charts
        pick = [{"label": str(r[ci["manufacture_year"]]), "eb": r[ci["eb_rate"]], "raw": r[ci["rate"]],
                 "tier": r[ci["tier"]],
                 "annot": f"{r[ci['involvements']]:,} · {r[ci['exposure_mkm']]:,.0f} מלמ״ק"} for r in rows]
        png = charts.cohort_bars(pick, global_rate=global_rate or 0.0,
                                 xlabel=f"{metric_he} למיליון ק״מ-רכב (עמודה = EB, עיגול חלול = גולמי)",
                                 title=f"עוקבות שנת ייצור · שיעור EB לפי {metric_he}",
                                 badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
    basis = (f"vehicle_cells_ranking | group=cohort | metric={metric} | bands={bands} | M={EB_M_MKM:g} Mkm | "
             f"{n} cohorts ({ex['cells']} cells excluded, exposure 0) | global {global_rate} per Mkm | "
             f"tiers {tiers['safest']}/{tiers['regular']}/{tiers['highest_risk']}")
    spec = make_spec("accidents/vehicle_cells_ranking", png_base64=png, basis=basis, rows=rows, columns=columns,
                     sql=sql, denominator=denom, caveats=caveats, metric=metric, bands=bands, group="cohort",
                     tiers=tiers, global_rate=global_rate, excluded=ex, stamp=stamp_text,
                     x="manufacture_year", y="eb_rate")
    return dispatch(view, spec, f"דירוג תאי רכב · {metric_he}")


def _caveats(ex, pct_excluded, n_band0, ev, global_rate, dropped_band0=0, pct_band0=0.0):
    out = []
    if ex["cells"]:
        out.append(f"{ex['cells']} תאים (שנות ייצור {ex['y0']}–{ex['y1']}, {ex['fleet']:,} כלי רכב = {pct_excluded}% מהצי) "
                   f"הוחרגו: אין עדיין היסטוריית מד-אוץ (חשיפה 0)")
    if dropped_band0:
        out.append(f"{dropped_band0} תאי נפח מנוע 0 (חשמלי, {ex['band0_fleet']:,} כלי רכב = {pct_band0}% מהצי) "
                   f"הושמטו לפי בחירה (bands = known_engine)")
    out.append("תאים (שנת ייצור × נפח מנוע), לא דגמים: קבצי התאונות אינם נושאים לוחית, VIN או קוד דגם — "
               "הרישום (fleet_by_model, vehicle_mileage) מכיר דגמים אך אין מפתח מקשר")
    if n_band0:
        out.append(f"נפח מנוע 0 = רכב חשמלי/ללא נפח (ev_share {100 * ev:.0f}%, {n_band0} תאים) — "
                   f"צי צעיר וקטן, שיעורים קיצוניים, לקרוא בזהירות")
    out.append(f"EB: M = {EB_M_MKM:g} מיליון ק״מ, שיעור גלובלי {global_rate} למיליון ק״מ על התאים הכלולים — "
               f"תאים קטנים נמשכים לממוצע")
    out.append("שכבות = חמישוני EB: 20% הבטוחים / 60% רגילים / 20% בסיכון הגבוה")
    out.append("תוקף: רכב פרטי, שנות ייצור 2016+, תאונות 2018–2024, ארצי בלבד")
    return out


def _cohort_caveats(ex, pct_excluded, global_rate, dropped_band0, pct_band0, bands, tiers):
    out = []
    if ex["cells"]:
        out.append(f"{ex['cells']} תאים (שנות ייצור {ex['y0']}–{ex['y1']}, {ex['fleet']:,} כלי רכב = {pct_excluded}% מהצי) "
                   f"הוחרגו: אין עדיין היסטוריית מד-אוץ (חשיפה 0)")
    if dropped_band0:
        out.append(f"{dropped_band0} תאי נפח מנוע 0 (חשמלי, {ex['band0_fleet']:,} כלי רכב = {pct_band0}% מהצי) "
                   f"הושמטו לפי בחירה (bands = known_engine)")
    out.append("עוקבה = כל רצועות הנפח של שנת ייצור אחת — האירועים והחשיפה הם סכומי התאים האמיתיים מהקוביה, "
               "לא צי × שנים (מכנה כזה מוטה: הוא מתעלם מקילומטראז' שונה בין עוקבות)")
    if bands == "all" and ex["band0_cells"]:
        out.append(f"{ex['band0_cells']} תאי נפח מנוע 0 (חשמלי/ללא נפח) נכללים בתוך העוקבות")
    out.append(f"EB: M = {EB_M_MKM:g} מיליון ק״מ, שיעור גלובלי {global_rate} למיליון ק״מ על התאים הכלולים — "
               f"עוקבות קטנות נמשכות לממוצע")
    # data-derived, never the fixed 20/60/20 claim: ntile(5) over FEW cohorts is lopsided (live: 9 → 2/6/1)
    out.append(f"שכבות = חמישוני EB על העוקבות בפועל: {tiers['safest']} בטוחות / {tiers['regular']} רגילות / "
               f"{tiers['highest_risk']} בסיכון הגבוה")
    out.append("תוקף: רכב פרטי, שנות ייצור 2016+, תאונות 2018–2024, ארצי בלבד")
    return out


ACTION = Action(
    name="vehicle_cells_ranking", label="תאי רכב · vehicle_cells_ranking",
    help="Empirical-Bayes involvement rate per vehicle cell (manufacture year x engine-volume band) over real "
         "exposure in million vehicle-km (odometer-based), M = 200 Mkm, three tiers by EB quintiles. Cells, not "
         "models: the accident files carry no plate, VIN or model code. group=cohort rolls the cells up to one "
         "row per manufacture year (events and exposure are sums of the real per-cell exposure - never "
         "fleet x years) with the same EB shrinkage on the cohort cells.",
    inputs={
        "metric": Input(kind="choice", label="מדד", default="involvements", choices=list(CELL_METRICS),
                        help="involvements = all; ksi = severe + fatal; fatal = fatal only"),
        "bands": Input(kind="choice", label="נפחי מנוע", default="all", choices=list(BANDS),
                       help="known_engine excludes cc_band 0 = unknown engine (mostly EVs)"),
        "group": Input(kind="choice", label="קיבוץ", default="cell", choices=list(GROUPS),
                       help="cell = one row per (manufacture year x engine band); cohort = one row per "
                            "manufacture year, cells summed (real exposure, same EB)"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
