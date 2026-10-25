# -*- coding: utf-8 -*-
"""The SEVERITY family (P9, use ג): person-level conditional injury severity — XGBoost multi:softprob over
casualties 2010–2024 (the 2009 involved gap starts the era), class weights 1/share (the report's rule, no SMOTE),
and a DISCRIMINATION gate: fatal recall + AUC(fatal) + a no-overfit bound. Discrimination, not calibration, on
purpose — the severe share TRIPLES over the era (6.1 % 2010 → 19.4 % 2024; live-verified), so a calibration
metric on a temporal holdout would reject every honest model the way the site family's 2022 was rejected.
Probabilities are RELATIVE on every face: the model ranks risk profiles, it does not predict a person's fate.

Leakage exclusions are STRUCTURAL — the matrix SQL selects only the contract columns; `late_death_code` (part of
the killed definition), ISS/hospitalized/discharge (post-outcome, 97 % NULL, 2010–2012 only) and every severity
label can never enter (the leakage test token-scans this file's SQL)."""
from __future__ import annotations

import hashlib
import math

from ..sqlkit import Refusal, ilit
from . import constants, model

FAMILY = "severity"
ERA = (2010, 2024)
TRAIN_UNTIL_DEFAULT = 2022                     # holdout 2023–24 — the drift years, held out on purpose
TRAIN_UNTIL = (2018, 2023)
# person-12: the person row + ONE accidents join (composite key; verified 0 % unmatched on 340,498 rows)
FEATURES = ("casualty_type_code", "age_group_code", "sex_code", "safety_equipment_code",
            "population_group_code", "involved_vehicle_type_code", "road_type_code", "day_night_code",
            "speed_limit_code", "hour_of_day", "month", "year_idx")
PRESETS = {
    "person-12": "the person row + crash context (one accidents join)",
    "shuffled": "person-12 with the TRAINING target permuted (a straw man that must fail the gate)",
}
XGB_PARAMS = {"objective": "multi:softprob", "num_class": 3, "max_depth": 4, "eta": 0.1,
              "min_child_weight": 20, "subsample": 0.8, "colsample_bytree": 0.8, "eval_metric": "mlogloss",
              "nthread": 4, "verbosity": 0}
MAX_ROUNDS, EARLY_STOP = 500, 25
# the gate — ALL plugin-chosen, set BELOW the report's achieved ~0.6 recall / 0.85 AUC
GATE = {
    "fatal_recall_min": (0.5, "plugin"),
    "auc_fatal_min": (0.8, "plugin"),
    "overfit_auc_gap_max": (0.05, "plugin"),
}
CLASSES = ("killed", "severe", "slight")       # target: injury_severity_code 1/2/3 -> class 0/1/2
CLASS_LABELS_HE = {0: "הרוג", 1: "פצוע קשה", 2: "פצוע קל"}

FEATURE_LABELS_HE = {
    "casualty_type_code": "סוג נפגע", "age_group_code": "קבוצת גיל", "sex_code": "מין",
    "safety_equipment_code": "אמצעי בטיחות", "population_group_code": "קבוצת אוכלוסייה",
    "involved_vehicle_type_code": "סוג רכב הנפגע", "road_type_code": "סוג דרך", "day_night_code": "יום/לילה",
    "speed_limit_code": "מהירות מותרת", "hour_of_day": "שעה", "month": "חודש", "year_idx": "מדד שנה",
}

# profile-input maps for severity_predict / what_if (choices only; "לא צוין" -> None -> xgboost missing)
PROFILE_FIELDS = {
    "road_type": ("road_type_code", {"עירוני בצומת": 1, "עירוני לא בצומת": 2,
                                     "לא-עירוני בצומת": 3, "לא-עירוני לא בצומת": 4}),
    "time": ("day_night_code", {"יום": 1, "לילה": 5}),
    "casualty": ("casualty_type_code", {"הולך רגל": 1, "נהג רכב": 2, "נוסע רכב": 3,
                                        "רוכב אופנוע": 4, "רוכב אופניים": 6}),
    "age": ("age_group_code", {"ילד עד גיל עשר": 2, "צעיר": 5, "מבוגר": 10, "ותיק": 14, "קשיש": 17}),
    "safety": ("safety_equipment_code", {"חגור או קסדה": 1, "ללא אמצעי בטיחות": 4}),
    "speed": ("speed_limit_code", {"עד חמישים": 1, "שבעים": 3, "תשעים": 5, "מאה ומעלה": 6}),
}
UNSET = "לא צוין"


def contract_check(meta: dict) -> None:
    """The severity twin of predict.contract_check: semantic matrix-recipe drift (the sentinel sets, the
    year_idx anchor) can hide under unchanged feature NAMES — the version stamp is the tripwire (a stored model
    outlives plugin upgrades in the durable data dir); missing counts as a mismatch."""
    if int(meta.get("contract_version") or 0) != int(constants.CONTRACT_VERSION):
        raise Refusal("חוזה המאפיינים של מודל החומרה אינו תואם את גרסת התוסף — יש לאמן מחדש",
                      ["studio_train_severity ואז studio_validate_severity ו-studio_deploy (משפחה severity)"],
                      detail=f"model contract_version {meta.get('contract_version')!r} != plugin "
                             f"{constants.CONTRACT_VERSION}")
    if list(meta.get("features") or []) != list(FEATURES):
        raise Refusal("חוזה המאפיינים של מודל החומרה אינו תואם את גרסת התוסף — יש לאמן מחדש",
                      ["studio_train_severity ואז studio_validate_severity ו-studio_deploy (משפחה severity)"],
                      detail=f"model features {meta.get('features')} != plugin contract {list(FEATURES)}")


def matrix_sql(y0: int, y1: int, site_pred: str | None = None) -> str:
    """The person matrix: sentinels → NULL in SQL (age 99; speed 0/9/99/999; safety 0/5/99/999 = not-recorded).
    P10: an optional site predicate (accidents-side columns — unambiguous in this join, `involved` carries no
    location) narrows the matrix to ONE site's person rows for site_profile's conditional block; None (the
    default) keeps the statement byte-identical to the training/meta text."""
    site_line = f"\n  AND ({site_pred})" if site_pred else ""
    return f"""SELECT i.injury_severity_code AS sev,
       i.casualty_type_code,
       CASE WHEN i.age_group_code IN (99) THEN NULL ELSE i.age_group_code END AS age_group_code,
       i.sex_code,
       CASE WHEN i.safety_equipment_code IN (0, 5, 99, 999) THEN NULL ELSE i.safety_equipment_code END AS safety_equipment_code,
       i.population_group_code,
       i.involved_vehicle_type_code,
       a.road_type_code, a.day_night_code,
       CASE WHEN a.speed_limit_code IN (0, 9, 99, 999) THEN NULL ELSE a.speed_limit_code END AS speed_limit_code,
       a.hour_of_day, a.month, a.year - {ilit(ERA[0])} AS year_idx, a.year
FROM involved i
JOIN accidents a ON a.accident_id = i.accident_id AND a.case_type_code = i.case_type_code
WHERE i.case_type_code = 1 AND a.year BETWEEN {ilit(y0)} AND {ilit(y1)}
  AND i.injury_severity_code IN (1, 2, 3){site_line}
ORDER BY a.year, a.accident_id, i.vehicle_num, i.person_id"""


def fetch_matrix(ctx, y0: int, y1: int, site_pred: str | None = None):
    """(X rows in FEATURES order, y 0/1/2, years)."""
    _, rows = ctx.query(matrix_sql(y0, y1, site_pred))
    X = [list(r[1:13]) for r in rows]
    y = [int(r[0]) - 1 for r in rows]
    years = [int(r[13]) for r in rows]
    return X, y, years


def class_weights(y_train) -> list[float]:
    """1/share(c) = n/count(c) — the report's imbalance rule; computed on the TRAIN window and frozen into
    meta (the shares DRIFT across the era, so the window matters)."""
    n = len(y_train)
    counts = [max(1, sum(1 for v in y_train if v == c)) for c in range(3)]
    return [round(n / c, 4) for c in counts]


def shuffle_target(y, years, train_until: int, seed: int) -> list[int]:
    """sha256-ordered permutation of the TRAINING targets only (holdout untouched) — the straw-man preset."""
    tr = [i for i, yr in enumerate(years) if yr <= train_until]
    order = sorted(tr, key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest())
    out = list(y)
    for slot, src in zip(tr, order):
        out[slot] = y[src]
    return out


def auc_binary(labels, scores) -> float:
    """AUC via the Mann-Whitney rank statistic with average ranks on ties (pure Python, no sklearn)."""
    n_pos = sum(1 for v in labels if v)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.0
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    rank_sum_pos = sum(r for r, l in zip(ranks, labels) if l)
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


def recall_of_class(y_true, probs, cls: int) -> float:
    """Recall of `cls` under argmax of the softprob rows."""
    tp = fn = 0
    for t, p in zip(y_true, probs):
        if t == cls:
            if max(range(3), key=lambda c: p[c]) == cls:
                tp += 1
            else:
                fn += 1
    return tp / (tp + fn) if (tp + fn) else 0.0


def evaluate(y_train, probs_train, y_hold, probs_hold) -> dict:
    auc_tr = auc_binary([v == 0 for v in y_train], [p[0] for p in probs_train])
    auc_ho = auc_binary([v == 0 for v in y_hold], [p[0] for p in probs_hold])
    return {
        "fatal_recall": round(recall_of_class(y_hold, probs_hold, 0), 3),
        "auc_fatal": round(auc_ho, 3),
        "auc_fatal_train": round(auc_tr, 3),
        "overfit_auc_gap": round(auc_tr - auc_ho, 3),
        "severe_recall": round(recall_of_class(y_hold, probs_hold, 1), 3),
        "slight_recall": round(recall_of_class(y_hold, probs_hold, 2), 3),
    }


def verdict(metrics: dict):
    """(status, Hebrew reasons — no ';')."""
    reasons = []
    if metrics["fatal_recall"] < GATE["fatal_recall_min"][0]:
        reasons.append(f"רגישות להרוגים {metrics['fatal_recall']} מתחת ל-{GATE['fatal_recall_min'][0]} (כלל התוסף)")
    if metrics["auc_fatal"] < GATE["auc_fatal_min"][0]:
        reasons.append(f"AUC להרוגים {metrics['auc_fatal']} מתחת ל-{GATE['auc_fatal_min'][0]} (כלל התוסף)")
    if metrics["overfit_auc_gap"] > GATE["overfit_auc_gap_max"][0]:
        reasons.append(f"פער AUC אימון-אימות {metrics['overfit_auc_gap']} מעל {GATE['overfit_auc_gap_max'][0]} "
                       f"— התאמת יתר (כלל התוסף)")
    return ("rejected" if reasons else "validated"), reasons


def train(X, y, years, train_until: int, seed: int, weights3: list[float]):
    """Temporal inner fold (the LAST training year) with per-row class weights; refit ≤ train_until with
    best+1 rounds. Returns (raw_ubj, best_rounds, inner_score)."""
    xgb = model.require_xgboost()
    import numpy as np  # noqa: PLC0415

    from ..sqlkit import ActionError  # noqa: PLC0415 — avoid a cycle at import time

    p = dict(XGB_PARAMS)
    p["seed"] = int(seed)
    w = [weights3[v] for v in y]
    inner_tr = [i for i, yr in enumerate(years) if yr < train_until]
    inner_va = [i for i, yr in enumerate(years) if yr == train_until]
    if not inner_tr or not inner_va:
        raise ActionError(f"train_until {train_until} leaves no inner fold (needs casualty rows before and in it).")
    d_tr = model._dmatrix(xgb, np, [X[i] for i in inner_tr], [y[i] for i in inner_tr],
                          names=FEATURES, weight=[w[i] for i in inner_tr])
    d_va = model._dmatrix(xgb, np, [X[i] for i in inner_va], [y[i] for i in inner_va],
                          names=FEATURES, weight=[w[i] for i in inner_va])
    bst = xgb.train(p, d_tr, num_boost_round=MAX_ROUNDS, evals=[(d_va, "inner")],
                    early_stopping_rounds=EARLY_STOP, verbose_eval=False)
    best = int(getattr(bst, "best_iteration", MAX_ROUNDS - 1)) + 1
    inner = float(getattr(bst, "best_score", float("nan")))
    fit = [i for i, yr in enumerate(years) if yr <= train_until]
    d_all = model._dmatrix(xgb, np, [X[i] for i in fit], [y[i] for i in fit],
                           names=FEATURES, weight=[w[i] for i in fit])
    final = xgb.train(p, d_all, num_boost_round=best)
    return bytes(final.save_raw(raw_format="ubj")), best, inner


def predict_proba(raw: bytes, X) -> list[list[float]]:
    """(n × 3) softprob rows; a fresh Booster per call (thread safety, like the site family)."""
    xgb = model.require_xgboost()
    import numpy as np  # noqa: PLC0415

    bst = xgb.Booster()
    bst.load_model(bytearray(raw))
    out = bst.predict(model._dmatrix(xgb, np, X, names=FEATURES))
    return [[float(v) for v in row] for row in out]


def profile_row(choices: dict, year_idx: float | None = None) -> list:
    """One feature row from the profile choices; unset fields stay None (xgboost missing — honest 'unspecified')."""
    row = {f: None for f in FEATURES}
    row["year_idx"] = ERA[1] - ERA[0] if year_idx is None else year_idx      # "today" on the era clock
    for field, (col, mapping) in PROFILE_FIELDS.items():
        v = choices.get(field)
        if v and v != UNSET:
            row[col] = mapping[v]
    return [row[f] for f in FEATURES]


def relative(probs: list[float], baseline: list[float]) -> list[float]:
    """p_c / baseline_c — the ONLY way a probability leaves this family (relative, never absolute fate)."""
    return [p / b if b > 0 else 0.0 for p, b in zip(probs, baseline)]
