# -*- coding: utf-8 -*-
"""weather_check (dark-layer light-up): the officer's weather label against ERA5 measured rain in the accident
hour — a reliability cross-check of two sources, reproducing the database's own weather_agreement table."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, dispatch, guard, make_spec, stamp, view_input
from ..sqlkit import (DATA_YEARS, WEATHER_THRESHOLDS, Refusal, as_choice, build_weather_check_sql, rows_safe,
                      weather_coverage_sql, year_range)

VIEWS = ("chart", "table", "sql")


@guard("מזג אוויר · דיווח מול מדידה")
def run(ctx, from_year=2005, to_year=2024, rain_threshold_mm="0.1", view="chart"):
    view = as_choice(view, "view", VIEWS)
    thr = float(as_choice(str(rain_threshold_mm), "rain_threshold_mm", WEATHER_THRESHOLDS))
    y0, y1 = year_range(from_year, to_year)
    sql = build_weather_check_sql(y0, y1, thr)
    columns, raw = ctx.query(sql)
    rows = rows_safe(raw)
    if not rows:                                   # a legal range with no weather cell at all (2005-2007): no blank chart
        first = ctx.query("SELECT min(year) FROM v_accidents_weather WHERE case_type_code = 1 "
                          "AND precipitation_mm IS NOT NULL")[1][0][0]
        raise Refusal(f"אין תאונות עם תא מזג אוויר (ERA5) בשנים {y0}–{y1}",
                      [f"כל שנה בין {first or 2008} ל-{DATA_YEARS[1]}: weather_check"])
    cov = rows_safe(ctx.query(weather_coverage_sql(y0, y1))[1])
    years_no_cell = [r[0] for r in cov if r[1] and r[2] == r[1]]
    dropped = sum(r[1] for r in cov if r[0] in years_no_cell)
    rest_total = sum(r[1] for r in cov if r[0] not in years_no_cell)
    rest_missing = sum(r[2] for r in cov if r[0] not in years_no_cell)
    caveats = _caveats(rows, columns, thr, years_no_cell, dropped, rest_total, rest_missing)
    denom = denominator("counts", "חלק מהתאונות עם נפגעים שיש להן תא מזג אוויר (ERA5) — שיעורים יחסיים בתוך כל תווית")
    stamp_text = stamp("weather_check", f"threshold {thr:g} mm", f"{y0}-{y1}")
    png = None
    if view == "chart":
        from .. import charts
        ci = {c: columns.index(c) for c in columns}
        png = charts.hbars([r[ci["cbs_weather_label"]] for r in rows], [r[ci["pct_measured_rain"]] for r in rows],
                           xlabel="אחוז התאונות עם גשם מדוד בשעת התאונה",
                           annot=[f"{r[ci['accidents']]:,} תאונות" for r in rows],
                           title=f"מזג אוויר: דיווח השוטר מול גשם מדוד (סף {thr:g} מ״מ) · {y0}–{y1}",
                           badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
    with_cell = rest_total - rest_missing
    total = rest_total + dropped
    basis = (f"weather_check | threshold {thr:g} mm | {y0}-{y1} | {len(rows)} rows | v_accidents_weather WHERE "
             f"case_type_code = 1 AND precipitation_mm IS NOT NULL | {with_cell} with cell of {total}")
    spec = make_spec("accidents/weather_check", png_base64=png, basis=basis, rows=rows, columns=columns, sql=sql,
                     denominator=denom, caveats=caveats, threshold_mm=thr, from_year=y0, to_year=y1,
                     years_without_cell=years_no_cell, stamp=stamp_text, x="cbs_weather_label", y="pct_measured_rain")
    return dispatch(view, spec, "מזג אוויר · דיווח מול מדידה")


def _caveats(rows, columns, thr, years_no_cell, dropped, rest_total, rest_missing):
    out = []
    if years_no_cell:
        ys = ", ".join(str(y) for y in years_no_cell)
        out.append(f"שנים ללא תא מזג אוויר: {ys} ({dropped:,} תאונות הושמטו)")
    if rest_total:
        pct = round(100.0 * rest_missing / rest_total, 1)
        out.append(f"{rest_missing:,} מתוך {rest_total:,} תאונות בשאר השנים ({pct}%) ללא תא — הושמטו")
    ci = {c: columns.index(c) for c in columns}
    by_label = {r[ci["cbs_weather_label"]]: r for r in rows}
    unk, clear = by_label.get("לא ידוע"), by_label.get("בהיר")
    if unk:
        ratio = (round(unk[ci["pct_measured_rain"]] / clear[ci["pct_measured_rain"]], 1)
                 if clear and clear[ci["pct_measured_rain"]] else None)
        out.append(f"'לא ידוע' ({unk[ci['accidents']]:,} תאונות, {unk[ci['share_pct']]}%) — "
                   f"{unk[ci['pct_measured_rain']]}% גשם מדוד" + (f", פי {ratio} מ'בהיר'" if ratio else ""))
    rainy = by_label.get("גשום")
    tail = (f" — בסף 0 'גשום' עולה ל-{rainy[ci['pct_any_rain']]}%" if thr > 0 and rainy else "")
    out.append(f"סף גשם: {thr:g} מ״מ בשעת התאונה (ERA5)" + tail)
    out.append("ERA5 = ריאנליזה ברזולוציית כ-25 ק״מ, שעה עגולה — לא מד-גשם תחנתי")
    out.append("תווית מזג האוויר = דיווח השוטר (weather_code), לא מדידה")
    return out


ACTION = Action(
    name="weather_check", label="מזג אוויר · weather_check",
    help="The officer's weather label against ERA5 measured rain in the accident hour (v_accidents_weather): share "
         "of accidents with measured rain per label, median temperature, label shares. Reproduces the database's "
         "weather_agreement table at the 0.1 mm threshold. A reliability cross-check of two sources - neither is "
         "ground truth.",
    inputs={
        "from_year": Input(kind="number", label="שנת התחלה", default=2005, help="2005-2024 (2005-2007 carry no weather cell)"),
        "to_year": Input(kind="number", label="שנת סיום", default=2024, help="data ends 2024-12-31"),
        "rain_threshold_mm": Input(kind="choice", label="סף גשם במילימטרים", default="0.1", choices=list(WEATHER_THRESHOLDS),
                                   help="precipitation in the accident hour above this counts as measured rain"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
