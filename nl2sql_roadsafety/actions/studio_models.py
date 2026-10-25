# -*- coding: utf-8 -*-
"""studio_models: the registry, as a table — every artifact with its status, gate metrics and rejection reasons.
Unreadable directories are listed as such, never hidden."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import DENOM_NA, dispatch, guard, make_spec, stamp
from ..sqlkit import Refusal, as_choice
from ..studio import constants, registry

TITLE = "רישום מודלים"
BASE_COLS = ["model_id", "status", "deployed", "created_at", "train_until", "preset", "seed", "n_train",
             "n_holdout", "rounds"]
METRIC_COLS = {  # family-switched gate columns (P9)
    "site": ["spearman", "calibration", "deviance_ratio", "alpha"],
    "severity": ["fatal_recall", "auc_fatal", "overfit_auc_gap", "severe_recall"],
}


# ledger=False (P13 round 2): listing the registry is state INSPECTION, not a finding — like `about`.
# This is what lets the studio workbench open on the registry without polluting the stage ledger.
@guard(TITLE, ledger=False)
def run(ctx, family="site"):
    family = as_choice(family, "family", (constants.FAMILY_SITE, "severity"))
    models = registry.list_models(ctx, family)
    if not models:
        raise Refusal(f"הרישום ריק — אין עדיין מודלים במשפחה ({family})",
                      ["studio_train_site או studio_train_severity לאימון מודל ראשון"])
    pointer, _ = registry.deployed(ctx, family)
    deployed_id = (pointer or {}).get("model_id")
    metric_cols = METRIC_COLS[family]
    cols = BASE_COLS + metric_cols + ["reasons"]
    rows = []
    for m in models:
        g = (m.get("gate") or {}).get("metrics", {})
        p = m.get("panel") or {}
        metrics = [m.get("alpha") if c == "alpha" else g.get(c) for c in metric_cols]
        rows.append([m.get("model_id", "?"), m.get("status", "?"), m.get("model_id") == deployed_id,
                     m.get("created_at", ""), p.get("train_until"), m.get("preset"), m.get("seed"),
                     p.get("n_train"), p.get("n_holdout"), (m.get("rounds") or {}).get("best"),
                     *metrics, " · ".join((m.get("gate") or {}).get("reasons", []))])
    caveats = ["הרישום יושב תחת ספריית הנתונים של האפליקציה (accidents/models) — לא במסד הלמ״ס",
               ("שער: Spearman וכיול לפי הדו״ח · יחס הסטייה = כלל התוסף" if family == "site" else
                "שער החומרה: רגישות להרוגים, AUC ופער התאמת-יתר — כולם כללי התוסף"),
               "המצביע deployed.json יחיד למשפחה — פריסת מודל אחר מחליפה אותו"]
    spec = make_spec("accidents/studio_models",
                     basis=f"studio_models | family {family} | {len(rows)} models | deployed {deployed_id or 'none'}",
                     rows=rows, columns=cols, sql="-- the registry is a directory of json artifacts, not a SQL result",
                     denominator=DENOM_NA, caveats=caveats, stamp=stamp("studio_models", family))
    return dispatch("table", spec, TITLE)


ACTION = Action(
    name="studio_models", label="רישום מודלים · studio_models",
    help="List the model registry: id, status (candidate/validated/rejected/deployed/unreadable), gate metrics, "
         "alpha and the rejection reasons. The deployed pointer is marked.",
    inputs={"family": Input(kind="choice", label="משפחה", default="site",
                            choices=[constants.FAMILY_SITE, "severity"],
                            help="site = the segment-year site model; severity = the person-level severity model")},
    run=run)
