# -*- coding: utf-8 -*-
"""studio_train_severity (P9, use ג): the person-level conditional severity model — build the person matrix
(2010–2024, one accidents join), freeze the contract + the 1/share class weights (computed on the TRAIN window:
the shares DRIFT), train XGBoost multi:softprob with early stopping on a temporal inner fold, register a
CANDIDATE. The gate is studio_validate_severity's separate, visible step."""
from __future__ import annotations

import time

from nl2sql_engine.modules import Action, Input

from .. import __version__
from ..envelope import DENOM_NA, dispatch, guard, make_spec, markdown_answer, stamp
from ..sqlkit import Refusal, as_choice, as_int
from ..studio import constants, model, registry, severity

VIEWS = ("markdown", "table")
TITLE = "אימון מודל חומרה"
SUMMARY_COLS = ("year", "rows", "killed", "severe", "slight")
_LRM = chr(0x200E)                                        # pins the era's tight digit range in the browser card


@guard(TITLE)
def run(ctx, train_until=severity.TRAIN_UNTIL_DEFAULT, features="person-12", seed=42, view="markdown"):
    view = as_choice(view, "view", VIEWS)
    features = as_choice(features, "features", severity.PRESETS)
    train_until = as_int(train_until, "train_until")
    seed = as_int(seed, "seed")
    lo, hi = severity.TRAIN_UNTIL
    if not lo <= train_until <= hi:
        raise Refusal(f"שנת האימון האחרונה חייבת להיות בין {lo} ל-{hi} — נדרשות שנת קיפול פנימי ושנת אימות",
                      [f"train_until בין {lo} ל-{hi}", "ברירת המחדל היא " + str(severity.TRAIN_UNTIL_DEFAULT)])
    model.require_xgboost()
    t0 = time.perf_counter()
    y0, y1 = severity.ERA
    X, y, years = severity.fetch_matrix(ctx, y0, y1)
    if not X:
        raise Refusal("אין רשומות נפגעים במסד הזה — אין על מה לאמן", ["about לבדיקת החיבור"])
    y_train_vec, shuffle_meta = y, None
    if features == "shuffled":
        y_train_vec = severity.shuffle_target(y, years, train_until, seed)
        shuffle_meta = {"seed": seed, "rule": "target permuted over training rows in sha256('{seed}:{i}') order"}
    tr = [i for i, yr in enumerate(years) if yr <= train_until]
    weights3 = severity.class_weights([y_train_vec[i] for i in tr])
    shares_train = [round(sum(1 for i in tr if y[i] == c) / max(len(tr), 1), 5) for c in range(3)]
    ho = [i for i, yr in enumerate(years) if yr > train_until]
    shares_holdout = [round(sum(1 for i in ho if y[i] == c) / max(len(ho), 1), 5) for c in range(3)]
    raw, best, inner_score = severity.train(X, y_train_vec, years, train_until, seed, weights3)
    seconds = round(time.perf_counter() - t0, 2)
    model_id = registry.new_model_id(train_until, features, seed, family=severity.FAMILY)
    summary = _summary(y, years)
    import xgboost  # noqa: PLC0415 — present: require_xgboost passed

    meta = {
        "contract_version": constants.CONTRACT_VERSION, "family": severity.FAMILY, "model_id": model_id,
        "status": "candidate", "created_at": registry.now_utc(), "plugin_version": __version__,
        "xgboost_version": getattr(xgboost, "__version__", "?"), "preset": features, "seed": seed,
        "features": list(severity.FEATURES),
        "target": "injury_severity_code 1/2/3 -> class 0/1/2 per casualty person-row (case_type_code = 1)",
        "panel": {"years": list(severity.ERA), "train_until": train_until,
                  "n_train": len(tr), "n_holdout": len(ho),
                  "class_counts_train": [sum(1 for i in tr if y[i] == c) for c in range(3)]},
        "class_weights": {"values": weights3, "rule": "n/count(c) on the train window", "window": [y0, train_until]},
        "class_shares_train": shares_train, "class_shares_holdout": shares_holdout,
        "sql": {"matrix": severity.matrix_sql(y0, y1)},
        "shuffle": shuffle_meta,
        "params": {**severity.XGB_PARAMS, "seed": seed},
        "rounds": {"max": severity.MAX_ROUNDS, "early_stopping": severity.EARLY_STOP,
                   "inner_fold_year": train_until, "best": best, "inner_score": round(inner_score, 4)},
        "training_seconds": seconds, "gate": None, "deployed_at": None,
    }
    model_id = registry.save(ctx, model_id, meta, raw, family=severity.FAMILY)
    caveats = _caveats(train_until, len(tr), weights3, features)
    spec = make_spec("accidents/studio_train_severity",
                     basis=f"studio_train_severity | {features} | train_until {train_until} | seed {seed} | "
                           f"rows {len(X)} | train {len(tr)} | holdout {len(ho)} | rounds {best} | {seconds}s",
                     rows=summary, columns=list(SUMMARY_COLS), sql=meta["sql"]["matrix"], denominator=DENOM_NA,
                     caveats=caveats, model_id=model_id,
                     stamp=stamp("studio_train_severity", features, f"tu={train_until}", f"seed={seed}"))
    if view == "table":
        return dispatch("table", spec, TITLE)
    body = [
        f"# מודל מועמד {model_id}",
        f"- {len(X):,} רשומות נפגעים ({_LRM}{y0}–{y1}{_LRM}) · אימון: {len(tr):,} עד {train_until} · "
        f"אימות בהמתנה: {len(ho):,}",
        f"- משקלי מחלקות (אחד חלקי שכיחות, על חלון האימון): הרוג {weights3[0]:.1f} · קשה {weights3[1]:.1f} · "
        f"קל {weights3[2]:.2f}",
        f"- סבבים: {best} (עצירה מוקדמת על {train_until}) · {seconds} שניות",
        ("- הזהרה: המטרה עורבבה (preset shuffled) — מודל קש שנועד להיכשל בשער" if features == "shuffled" else
         "- סטטוס: candidate — הריצו studio_validate_severity לשער האימות"),
    ]
    return markdown_answer(TITLE, body, denom=DENOM_NA, caveats=caveats)


def _summary(y, years):
    out = {}
    for v, yr in zip(y, years):
        row = out.setdefault(yr, [yr, 0, 0, 0, 0])
        row[1] += 1
        row[2 + v] += 1
    return [out[k] for k in sorted(out)]


def _caveats(train_until, n_train, weights3, features):
    out = [
        "רשומה = נפגע (סדרת הנפגעים בלבד) · המודל מדרג פרופילי סיכון — הסתברויות יחסיות, לא גורל של אדם",
        "שיעור הפצועים קשה גדל פי שלושה לאורך התקופה (קריסת דיווח הקל + גידול אמיתי) — שער האימות מודד הפרדה "
        "(רגישות ו-AUC) ולא כיול, בכוונה",
        f"משקלי המחלקות הוקפאו מחלון האימון (עד {train_until}) יחד עם חוזה המאפיינים",
        "עמודות תוצאה (מוות מאוחר, ימי אשפוז) מוחרגות מהמאפיינים — דליפת מטרה",
        "עצירה מוקדמת על שנת האימון האחרונה כקיפול פנימי — אין כאן הערכת שער, הריצו studio_validate_severity",
    ]
    if features == "shuffled":
        out.insert(0, "המטרה עורבבה בכוונה (preset shuffled) — מודל ביקורת שחייב להידחות בשער")
    return out


ACTION = Action(
    name="studio_train_severity", label="אימון מודל חומרה · studio_train_severity",
    help="Person-level conditional injury-severity model (killed/severe/slight): XGBoost multi:softprob over "
         "casualties 2010-2024 with 1/share class weights frozen from the train window. Registers a CANDIDATE - "
         "run studio_validate_severity for the gate. Relative probabilities only. Needs the [ml] extra.",
    inputs={
        "train_until": Input(kind="number", label="שנת אימון אחרונה", default=severity.TRAIN_UNTIL_DEFAULT,
                             help="2018-2023; the years after it are the validation holdout"),
        "features": Input(kind="choice", label="מאפיינים", default="person-12", choices=list(severity.PRESETS),
                          help="person-12 = person + crash context; shuffled = a straw-man that must fail"),
        "seed": Input(kind="number", label="זרע", default=42, help="random seed for xgboost and the shuffle"),
        "view": Input(kind="choice", label="תצוגה", default="markdown", choices=list(VIEWS),
                      help="markdown = the training card; table = per-year class counts"),
    },
    run=run)
