# -*- coding: utf-8 -*-
"""studio_train_site: build the segment-year panel (the FULL grid, zero years included), freeze the feature
contract, train the XGBoost count:poisson model with early stopping on a temporal inner fold, and register a
CANDIDATE. No gate here — that is studio_validate's job (golden rule: the gate is a separate, visible step)."""
from __future__ import annotations

import time

from nl2sql_engine.modules import Action, Input

from .. import __version__
from ..envelope import DENOM_NA, dispatch, guard, make_spec, markdown_answer, stamp
from ..sqlkit import Refusal, as_choice, as_int, rows_safe
from ..studio import constants, model, panel, registry

VIEWS = ("markdown", "table")
TITLE = "אימון מודל אתר"
SUMMARY_COLS = ("year", "rows", "sum_y", "adt_known", "static_assigned")


@guard(TITLE)
def run(ctx, train_until=constants.TRAIN_UNTIL_DEFAULT, features="doc-11", seed=42, view="markdown"):
    view = as_choice(view, "view", VIEWS)
    features = as_choice(features, "features", constants.PRESETS)
    train_until = as_int(train_until, "train_until")
    seed = as_int(seed, "seed")
    lo, hi = constants.TRAIN_UNTIL
    if not lo <= train_until <= hi:
        raise Refusal(f"שנת האימון האחרונה חייבת להיות בין {lo} ל-{hi} — נדרשות שנת קיפול פנימי ושנת אימות",
                      [f"train_until בין {lo} ל-{hi}", "ברירת המחדל היא " + str(constants.TRAIN_UNTIL_DEFAULT)])
    model.require_xgboost()                                 # a readable error BEFORE any heavy work
    t0 = time.perf_counter()
    y0, y1 = constants.PANEL_YEARS
    adt_fill = panel.fetch_adt_fill(ctx, train_until)
    cols, rows = panel.fetch_panel(ctx, y0, y1, adt_fill["value"])
    if not rows:
        raise Refusal("אין שכבת תנועה (traffic_segments / traffic_adt_asof) במסד הזה — אין על מה לאמן",
                      ["segment_rates לבדיק(ת) שכבת התנועה"])
    static = panel.fetch_static(ctx, train_until)
    X, y, years, keys, ksi = panel.matrix(cols, rows, static)
    y_train, shuffle_meta = y, None
    if features == "shuffled":
        y_train = panel.shuffle_target(y, years, keys, train_until, seed)
        shuffle_meta = {"seed": seed,
                        "rule": "target permuted over training rows in sha256('{seed}:{road}:{seg}:{year}') order"}
    raw, best, inner_score = model.train(X, y_train, years, train_until, seed)
    seconds = round(time.perf_counter() - t0, 2)
    model_id = registry.new_model_id(train_until, features, seed)
    summary = panel.panel_summary(cols, rows)
    n_train = sum(r[1] for r in summary if r[0] <= train_until)
    n_holdout = sum(r[1] for r in summary if r[0] > train_until)
    sum_y_train = sum(r[2] for r in summary if r[0] <= train_until)
    static_rows = [[r, s, *[static[(r, s)].get(c) for c in panel.STATIC_COLUMNS[2:]]] for r, s in sorted(static)]
    import xgboost                                          # noqa: PLC0415 — present: require_xgboost passed

    meta = {
        "contract_version": constants.CONTRACT_VERSION, "family": constants.FAMILY_SITE, "model_id": model_id,
        "status": "candidate", "created_at": registry.now_utc(), "plugin_version": __version__,
        "xgboost_version": getattr(xgboost, "__version__", "?"), "preset": features, "seed": seed,
        "features": list(constants.FEATURES),
        "target": "casualty accidents (case_type_code = 1, road_type 3-4) per traffic-count segment-year, "
                  "assigned on the panel geometry", "offset": None,
        "panel": {"years": list(constants.PANEL_YEARS), "train_until": train_until,
                  "lag_feed_year": constants.LAG_FEED_YEAR, "history_start": constants.HISTORY_START,
                  "n_segments": len({k for k in keys}), "n_train": n_train, "n_holdout": n_holdout,
                  "sum_y_train": sum_y_train, "zero_share_train": round(
                      sum(1 for i, yr in enumerate(years) if yr <= train_until and y[i] == 0) / max(n_train, 1), 3),
                  "adt_known_share_by_year": {str(r[0]): round(r[3] / r[1], 3) for r in summary},
                  "static_assigned_by_year": {str(r[0]): r[4] for r in summary}},
        "adt_fill": adt_fill,
        "sql": {"adt_median": panel.adt_median_sql(train_until), "panel": panel.panel_sql(y0, y1, adt_fill["value"]),
                "static_attrs": panel.static_attrs_sql(train_until)},
        "static_attrs": {"columns": list(panel.STATIC_COLUMNS), "rows": static_rows,
                         "segments_with_history": len(static_rows)},
        "shuffle": shuffle_meta,
        "params": {**constants.XGB_PARAMS, "seed": seed},
        "rounds": {"max": constants.MAX_ROUNDS, "early_stopping": constants.EARLY_STOP,
                   "inner_fold_year": train_until, "best": best, "inner_score": round(inner_score, 4)},
        "training_seconds": seconds, "gate": None, "alpha": None, "deployed_at": None,
    }
    model_id = registry.save(ctx, model_id, meta, raw)      # a same-second collision may re-suffix the id
    caveats = _caveats(train_until, adt_fill, summary, len(static_rows), len({k for k in keys}), features)
    spec = make_spec("accidents/studio_train", basis=f"studio_train_site | {features} | train_until {train_until} | "
                     f"seed {seed} | rows {len(rows)} | train {n_train} | holdout {n_holdout} | rounds {best} | "
                     f"{seconds}s", rows=summary, columns=list(SUMMARY_COLS),
                     sql=meta["sql"]["panel"], denominator=DENOM_NA, caveats=caveats, model_id=model_id,
                     stamp=stamp("studio_train_site", features, f"tu={train_until}", f"seed={seed}"))
    if view == "table":
        return dispatch("table", spec, TITLE)
    known_share = round(100.0 * sum(r[3] for r in summary) / max(len(rows), 1), 1)
    body = [
        f"# מודל מועמד {model_id}",
        f"- לוח: {len(rows):,} שורות מקטע-שנה ({meta['panel']['n_segments']} מקטעים × {y0}–{y1}, שנות אפס נכללות)",
        f"- אימון: {n_train:,} שורות עד {train_until} (סך תאונות {sum_y_train:,}) · אימות בהמתנה: {n_holdout:,} שורות",
        f"- ADT ידוע ב-{known_share}% מהשורות · מילוי חציוני {adt_fill['value']:,.0f} · "
        f"{len(static_rows)} מקטעים עם היסטוריית מאפיינים",
        f"- סבבים: {best} (עצירה מוקדמת על {train_until}) · {seconds} שניות",
        ("- הזהרה: המטרה עורבבה (preset shuffled) — מודל קש שנועד להיכשל בשער" if features == "shuffled" else
         "- סטטוס: candidate — הריצו studio_validate לשער האימות"),
    ]
    return markdown_answer(TITLE, body, denom=DENOM_NA, caveats=caveats)


def _caveats(train_until, adt_fill, summary, n_static, n_segments, features):
    fill_rows = sum(r[1] - r[3] for r in summary)
    total = sum(r[1] for r in summary)
    out = [
        f"יחידה = מקטע ספירת תנועה (road, seg) על הגרסה האחרונה של traffic_segments — {n_segments} מקטעים, שנות אפס נכללות",
        f"מטרה = תאונות עם נפגעים למקטע-שנה ללא היסט חשיפה (כבדו״ח) — ADT as-of הוא משתנה מסביר, "
        f"חציון ארצי {adt_fill['value']:,.0f} ב-{fill_rows:,} מתוך {total:,} שורות ללא ספירה (adt_known = 0)",
        f"מאפייני מקטע קבועים מכל הרשומות {constants.HISTORY_START}–{train_until} בשתי הסדרות "
        f"(סדרת הנזק-בלבד כמעט ללא קידודי מהירות/משטח/מסלולים — הממוצעים על השורות המקודדות בלבד) · "
        f"{n_segments - n_static} מקטעים ללא היסטוריה = חסר",
        f"lag1 = תאונות המקטע בשנה הקודמת ({constants.LAG_FEED_YEAR} מזין את {constants.PANEL_YEARS[0]})",
        f"עצירה מוקדמת על {train_until} כקיפול פנימי — אין כאן הערכת שער, הריצו studio_validate",
    ]
    if features == "shuffled":
        out.insert(0, "המטרה עורבבה בכוונה (preset shuffled) — מודל ביקורת שחייב להידחות בשער")
    return out


ACTION = Action(
    name="studio_train_site", label="אימון מודל אתר · studio_train_site",
    help="Build the full segment-year panel (zero years included), freeze the doc-11 feature contract (ADT as-of "
         "with a national-median fill, lag1, static segment attributes 2005..train_until) and train an XGBoost "
         "count:poisson model with early stopping on the last training year. Registers a CANDIDATE - run "
         "studio_validate for the gate. Needs the [ml] extra (xgboost).",
    inputs={
        "train_until": Input(kind="number", label="שנת אימון אחרונה", default=constants.TRAIN_UNTIL_DEFAULT,
                             help="2018-2023; the years after it are the validation holdout"),
        "features": Input(kind="choice", label="מאפיינים", default="doc-11", choices=list(constants.PRESETS),
                          help="doc-11 = the report's preset; shuffled = a straw-man that must fail the gate"),
        "seed": Input(kind="number", label="זרע", default=42, help="random seed for xgboost and the shuffle"),
        "view": Input(kind="choice", label="תצוגה", default="markdown", choices=list(VIEWS),
                      help="markdown = the training card; table = the per-year panel summary"),
    },
    run=run)
