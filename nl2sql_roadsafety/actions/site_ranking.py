# -*- coding: utf-8 -*-
"""site_ranking (use ב, the flagship): Empirical-Bayes network screening against the DEPLOYED site model —
excess = observed − μ, EB = w·μ + (1−w)·observed, NB 90% intervals from the stored α. No training at prediction
time; the features are rebuilt from the artifact's contract; refuses, readably, when nothing is deployed."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, dispatch, guard, make_spec, stamp, view_input
from ..sqlkit import (NAMES_CTE, STATIC_GEOMETRY_CTE, ActionError, Refusal, as_int, as_choice, exposure_year_range,
                      ilit, rows_safe, segment_coverage_sql)
from ..studio import constants, model, predict, registry

VIEWS = ("chart", "table", "sql")
TITLE = "דירוג אתרים לפי עודף"
COLS = ["road", "seg", "name_from", "name_to", "km_from", "km_to", "observed", "ksi_observed", "mu", "excess",
        "eb", "lo90", "hi90", "significant", "years_known", "site_key", "rank"]


@guard(TITLE)
def run(ctx, road=0, from_year=2019, to_year=2024, top_n=30, view="chart"):
    view = as_choice(view, "view", VIEWS)
    y0, y1 = exposure_year_range(from_year, to_year)
    road = as_int(road, "road")
    if road < 0:
        raise ActionError(f"road must be 0 (all roads) or a road number; got {road}.")
    top_n = as_int(top_n, "top_n")
    if not 1 <= top_n <= 200:
        raise ActionError(f"top_n must be between 1 and 200; got {top_n}.")
    pointer, meta = registry.deployed(ctx)
    if pointer is None:
        raise Refusal("אין מודל אתר פרוס — דירוג לפי excess דורש מודל מאומת ופרוס",
                      ["סטודיו: studio_train_site ואז studio_validate ואז studio_deploy",
                       "hotspot_map לספירות observed", "segment_rates לשיעורים לק״מ-רכב"])
    if meta is None:
        raise Refusal("deployed.json מצביע על מודל חסר או בלתי קריא — יש לפרוס מחדש",
                      ["studio_models", "studio_deploy"])
    model.require_xgboost()
    agg, panel_sql_text = predict.expected_by_segment(ctx, meta, y0, y1, road)
    if not agg:
        raise Refusal(f"אין מקטעים בלוח עבור כביש {road}" if road else "הלוח ריק — אין שכבת תנועה",
                      ["road = 0 לכל הכבישים", "hotspot_map"])
    names = _names(ctx, set(agg))
    ranked = sorted(agg.items(), key=lambda kv: (-kv[1]["excess"], -kv[1]["observed"], kv[0]))
    rows = []
    for rank, (key, e) in enumerate(ranked[:top_n], start=1):
        nm = names.get(key, (None, None, None, None, None))
        rows.append([key[0], key[1], nm[0], nm[1], nm[2], nm[3], e["observed"], e["ksi"], e["mu"], e["excess"],
                     e["eb"], e["lo90"], e["hi90"], e["significant"], e["years_known"], nm[4], rank])
    alpha = float(meta.get("alpha") or 0.0)
    total_obs = sum(e["observed"] for e in agg.values())
    cov = rows_safe(ctx.query(segment_coverage_sql(y0, y1, road))[1])
    asof_matched = sum(r[2] for r in cov)
    caveats = _caveats(meta, alpha, y0, y1, road, total_obs, asof_matched, len(agg))
    denom = denominator("exposure",
                        f"ציפייה מודלית ממודל אתר פרוס {meta['model_id']} (היסטוריה, מאפייני מקטע ו-ADT as-of "
                        f"כמשתנים) · excess = נצפה − צפוי", model_id=meta["model_id"], alpha=alpha)
    stamp_text = stamp("site_ranking", f"road={road or 'all'}", f"{y0}-{y1}", f"top {top_n}")
    png = None
    if view == "chart":
        from .. import charts
        show = rows
        png = charts.hbars(
            [f"{r[0]}/{r[1]} · {r[2] or ''} ← {r[3] or ''}" for r in show], [r[8] for r in show],
            xlabel="תאונות עם נפגעים: תחזית המודל (עמודה) מול מה שקרה בפועל (עיגול)",
            lo=[r[11] for r in show], hi=[r[12] for r in show], markers=[r[6] for r in show],
            annot=[f"{r[9]:+g}" for r in show],
            colors=["#c0392b" if r[13] else "#0d9488" for r in show],
            max_rows=15,                     # the 30-row PNG was annotation soup (P8) — the table face keeps all
            title=f"תחזית המודל מול המציאות · דירוג לפי עודף · {'כביש ' + str(road) if road else 'כל הכבישים'} · {y0}–{y1}",
            badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
    basis = (f"site_ranking | road={road or 'all'} | {y0}-{y1} | top {len(rows)} of {len(agg)} | model "
             f"{meta['model_id']} | alpha {alpha} | observed {total_obs} (panel) vs {asof_matched} (asof)")
    spec = make_spec("accidents/site_ranking", png_base64=png, basis=basis, rows=rows, columns=COLS,
                     sql=panel_sql_text, denominator=denom, caveats=caveats, model_id=meta["model_id"],
                     alpha=alpha, road=road, from_year=y0, to_year=y1, top_n=top_n, stamp=stamp_text,
                     static_attrs_sql=meta["sql"]["static_attrs"], y="mu")
    return dispatch(view, spec, TITLE)


def _names(ctx, keys):
    sql = (f"WITH {STATIC_GEOMETRY_CTE},\n{NAMES_CTE}\n"
           f"SELECT g.road, g.seg, n.name_from, n.name_to, g.km_from, g.km_to,\n"
           f"       printf('road:%d/%g-%g', g.road, g.km_from, g.km_to) AS site_key\n"
           f"FROM latest_segments g LEFT JOIN names n USING (road, seg)")
    out = {}
    for r in rows_safe(ctx.query(sql)[1]):
        if (r[0], r[1]) in keys:
            out[(r[0], r[1])] = (r[2], r[3], r[4], r[5], r[6])
    return out


def _caveats(meta, alpha, y0, y1, road, total_obs, asof_matched, n_units):
    g = (meta.get("gate") or {}).get("metrics", {})
    scope = f" בכביש {road}" if road else ""
    diff = total_obs - asof_matched
    return [
        f"נצפה = הקצאה על גיאומטריית הלוח המלאה כמו במודל — {diff:+,} תאונות לעומת שכבת ה-as-of של "
        f"segment_rates בטווח{scope} (מקטעים-שנים ללא שורת as-of מוקצים על הגרסה האחרונה)",
        f"excess = נצפה − צפוי · EB = w·μ + (1−w)·נצפה עם w = 1/(1+α·μ) · α = {alpha:g} · "
        f"רווח 90% מקירוב נורמלי ל-NB בהנחת אי-תלות בין שנים",
        f"מודל {meta['model_id']}: train_until {meta['panel']['train_until']}, Spearman {g.get('spearman')}, "
        f"כיול {g.get('calibration')} · מתאם ולא סיבתיות",
        "מובהקות = נצפה מעל הגבול העליון של רווח ה-90% — ללא תיקון להשוואות מרובות על פני היחידות",
        "דירוג לפי excess, לא לפי שיעור — שיעור לק״מ-רכב: segment_rates · צמתים אינם במודל (hotspot_map לספירות)",
    ]


ACTION = Action(
    name="site_ranking", label="דירוג אתרים לפי עודף · site_ranking",
    help="Empirical-Bayes network screening against the DEPLOYED site model: excess = observed - expected, "
         "EB shrinkage, NB 90% intervals from the stored alpha, ranked by excess. No training at prediction time; "
         "refuses when no model is deployed. Needs the [ml] extra.",
    inputs={
        "road": Input(kind="number", label="כביש", default=0, help="0 = all roads; otherwise a road number"),
        "from_year": Input(kind="number", label="שנת התחלה", default=2019, help="2017-2024 (the panel era)"),
        "to_year": Input(kind="number", label="שנת סיום", default=2024, help="2017-2024"),
        "top_n": Input(kind="number", label="מספר יחידות", default=30, help="1-200"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
