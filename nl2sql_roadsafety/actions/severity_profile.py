# -*- coding: utf-8 -*-
"""severity_profile (use ג, descriptive): the distribution of casualties (killed / severe / slight) by a
chosen dimension — conditional on being a casualty, relative shares, never a risk."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import (CAVEAT_COUNTS_NOT_RISK, CAVEAT_DATA_END, denominator, dispatch, guard, make_spec,
                        stamp, view_input)
from ..sqlkit import (DATA_YEARS, PROFILE_DIMS, ActionError, Refusal, as_choice, build_severity_profile_sql,
                      coverage_years_sql, rows_safe, year_range)

VIEWS = ("chart", "table", "sql")
DISPLAYS = ("shares", "counts")     # counts = the three absolute lines over time (by=year only) — P13 round 2,
                                    # the instructor's pick from the rival's Trends tab, WITH our gap handling
DIM_CAVEATS = {
    "age_group": "תוויות הגיל נבנו מהקוד age_group_code: תווית המסד חסרה ב-46 אלף רשומות ומשובשת בקודים 2–3 (בכלל הנתונים 2005–2024)",
    "involved_vehicle_type": "הולכי רגל = casualty_type_code 1 גם כשנרשם להם קוד רכב (489 רשומות בכלל הנתונים 2005–2024) · הרכב לפי involved_vehicle_type_code",
    "weather": "מזג האוויר = דיווח השוטר (weather_code), לא מדידה · 'לא ידוע' מוצג",
    "road_type": "מאפייני התאונה מצורפים על המפתח (accident_id, case_type_code)",
    "day_night": "מאפייני התאונה מצורפים על המפתח (accident_id, case_type_code)",
    "year": "שיעור הפצועים קשה גדל בערך פי שלושה לאורך התקופה (בנתונים החיים: מכ-6% ב-2010 לכ-19% ב-2024) — "
            "נדידת שיעורים (דיווח ותמהיל), לא נדידת תוויות · זו הסיבה ששער מודל החומרה מודד הפרדה ולא כיול",
    # P13 accident-attribute dims (light/hour/day/speed/shape) — the join line + the sentinel discipline
    "lighting": "תאורה = light_code כפי שקודד בזירה · תווית חסרה = 'לא ידוע' · "
                "מאפייני התאונה מצורפים על המפתח (accident_id, case_type_code)",
    "hour_of_day": "השעות קובצו לארבע רצועות (בוקר 6–11, צהריים 12–17, ערב 18–23, לילה 0–5) · "
                   "שעה חסרה או לא תקינה = 'לא ידוע' (בנתונים החיים אין כאלה)",
    "day_of_week": "סדר הימים כרונולוגי (ראשון עד שבת) · מאפייני התאונה מצורפים על המפתח (accident_id, case_type_code)",
    "speed_limit": "קוד מהירות 0 או חסר = 'לא ידוע' — נכלל כקטגוריה ולא הושמט · "
                   "המהירות המותרת כפי שקודדה בזירה, לא המהירות בפועל",
}


@guard("פרופיל חומרה")
def run(ctx, by="casualty_type", from_year=2005, to_year=2024, display="shares", view="chart"):
    by = as_choice(by, "by", PROFILE_DIMS)
    display = as_choice(display, "display", DISPLAYS)
    view = as_choice(view, "view", VIEWS)
    if display == "counts" and by != "year":
        raise ActionError(f"display=counts is a time view - it needs by=year; got by={by}.")
    y0, y1 = year_range(from_year, to_year)
    sql = build_severity_profile_sql(by, y0, y1)
    columns, raw = ctx.query(sql)
    rows = rows_safe(raw)
    if not rows:
        _refuse_no_covered_years(ctx)                       # live: 2009-2009, the one dropped year (P2 rule)
    cov = rows_safe(ctx.query(coverage_years_sql(y0, y1))[1])
    uncovered = [r for r in cov if r[3] is False]
    caveats = _caveats(by, uncovered, rows, columns, display)
    dim_he = PROFILE_DIMS[by][4]
    denom = denominator("counts", "נפגעים (case_type_code = 1, injury_severity_code 1–3) — שיעורים יחסיים בתוך הנפגעים, לא סיכון")
    stamp_text = stamp("severity_profile", by, f"{y0}-{y1}")
    png = None
    if view == "chart":
        from .. import charts
        ci = {c: columns.index(c) for c in ("label", "casualties", "killed", "severe", "slight")}
        if display == "counts":
            # the three absolute lines over the years — uncovered years break the lines (NaN) and are shaded,
            # never drawn as zero and never bridged (the rival draws straight through his missing years)
            years = [int(r[columns.index("code")]) for r in rows]
            png = charts.severity_lines(years,
                                        {"killed": [r[ci["killed"]] for r in rows],
                                         "severe": [r[ci["severe"]] for r in rows],
                                         "slight": [r[ci["slight"]] for r in rows]},
                                        uncovered=[r[0] for r in uncovered], y0=y0, y1=y1,
                                        title=f"מגמת חומרה · ספירות לפי שנה · {y0}–{y1}",
                                        badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
        else:
            top = rows[:20]
            png = charts.stacked_bars([r[ci["label"]] or "" for r in top],
                                      {"killed": [r[ci["killed"]] for r in top], "severe": [r[ci["severe"]] for r in top],
                                       "slight": [r[ci["slight"]] for r in top]},
                                      [r[ci["casualties"]] for r in top], xlabel="אחוז מהנפגעים בקבוצה",
                                      title=f"פרופיל חומרה לפי {dim_he} · {y0}–{y1}", badge=f"מכנה: {denom['label']}",
                                      caveats=caveats, stamp=stamp_text)
    unc = ", ".join(str(r[0]) for r in uncovered) or "none"
    basis = (f"severity_profile | by={by} | display={display} | {y0}-{y1} | {len(rows)} rows | "
             f"uncovered years: {unc} | "
             f"involved WHERE case_type_code = 1 AND injury_severity_code IN (1, 2, 3)")
    spec = make_spec("accidents/severity_profile", png_base64=png, basis=basis, rows=rows, columns=columns, sql=sql,
                     denominator=denom, caveats=caveats, by=by, display=display, from_year=y0, to_year=y1,
                     uncovered_years=[r[0] for r in uncovered], stamp=stamp_text, x="label", y="casualties")
    title = "מגמת חומרה · ספירות לפי שנה" if display == "counts" else f"פרופיל חומרה · לפי {dim_he}"
    return dispatch(view, spec, title)


def _year_spans(years) -> str:
    """Sorted years compressed to en-dash runs: [2005..2008, 2010..2024] -> '2005–2008, 2010–2024'."""
    runs, start, prev = [], None, None
    for y in years:
        if start is None:
            start = prev = y
        elif y == prev + 1:
            prev = y
        else:
            runs.append((start, prev))
            start = prev = y
    if start is not None:
        runs.append((start, prev))
    return ", ".join(f"{a}–{b}" if a != b else f"{a}" for a, b in runs)


def _refuse_no_covered_years(ctx):
    """The coverage rule left ZERO rows in the selected range (live: from_year=to_year=2009, the dropped
    year) — a refusal card naming the covered span, never a blank chart with a vacuous 0.0% caveat."""
    cov = rows_safe(ctx.query(coverage_years_sql(*DATA_YEARS))[1])
    covered = sorted(r[0] for r in cov if r[3] is True)
    answerable = [f"שנים מכוסות במסד: {_year_spans(covered)}"] if covered else []
    raise Refusal("אין שנים מכוסות בטווח שנבחר", answerable,
                  what_to_do="הרחיבו את הטווח לשנים המכוסות")


def _caveats(by, uncovered, rows, columns, display="shares"):
    out = []
    if display == "counts":
        out.append(CAVEAT_COUNTS_NOT_RISK)
    if len(uncovered) == 1:
        y, acc, people, _ = uncovered[0]
        out.append(f"נתוני נפגעים (involved) חסרים ב-{y}: {people:,} רשומות מול {acc:,} תאונות — השנה הושמטה מהפרופיל")
    elif uncovered:
        ys = ", ".join(str(r[0]) for r in uncovered[:3]) + (f" ועוד {len(uncovered) - 3}" if len(uncovered) > 3 else "")
        out.append(f"נתוני נפגעים (involved) חסרים ב-{len(uncovered)} שנים: {ys} — השנים הושמטו מהפרופיל")
    if by == "road_shape":
        # data-driven: code 9's share IN THE SELECTED RANGE (the SQL's own share_pct), the 2011 jump scoped to live
        ci = {c: columns.index(c) for c in ("code", "share_pct")}
        share = next((r[ci["share_pct"]] for r in rows if r[ci["code"]] == 9), 0.0)
        out.append(f"קוד 9 'אחר' = {share}% מהנפגעים בטווח שנבחר — שינוי הקידוד ב-2011 הקפיץ אותו "
                   f"(מכ-3% עד 2010 לכ-44% מ-2011 בנתונים החיים), ולכן השוואות צורת דרך על-פני 2011 שבורות")
    out.append("מותנה בהיותו נפגע: השיעורים יחסיים לכל הנפגעים, לא סיכון לתאונה")
    if by in DIM_CAVEATS:
        out.append(DIM_CAVEATS[by])
    out.append("קודי 0/99 (לא ידוע) נכללים בסך הכל")
    out.append(CAVEAT_DATA_END)
    return out


ACTION = Action(
    name="severity_profile", label="חומרה · severity_profile",
    help="Casualties (people killed / severely / slightly injured, casualty series only) by one dimension - "
         "casualty type, road type, day/night, age group, officer-reported weather, the casualty's vehicle type, "
         "sex, lighting, hour of day (four buckets), day of week, speed limit, road shape, or year (severity "
         "composition per year - the share-drift exhibit) - with shares and severity percentages. Conditional on "
         "being a casualty: relative, not risk. Unknown/sentinel codes become an explicit unknown bucket, never "
         "dropped; road shape carries the 2011 coding-change caveat (code 9). "
         "Years whose person-level records are missing are dropped and named (live copy: 2009); a range "
         "with no covered years refuses and names the covered span. display=counts (by=year only) draws the "
         "three severities as absolute lines over time - uncovered years break the lines and are shaded, "
         "never bridged or drawn as zero.",
    inputs={
        "by": Input(kind="choice", label="חתך", default="casualty_type", choices=list(PROFILE_DIMS)),
        "from_year": Input(kind="number", label="שנת התחלה", default=2005, help="2005-2024"),
        "to_year": Input(kind="number", label="שנת סיום", default=2024, help="data ends 2024-12-31"),
        "display": Input(kind="choice", label="תצוגה", default="shares", choices=list(DISPLAYS),
                         help="shares = the 100% stacked profile; counts = three absolute lines over "
                              "time (by=year only)"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
