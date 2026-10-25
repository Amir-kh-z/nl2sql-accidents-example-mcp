# -*- coding: utf-8 -*-
"""studio_deploy: write the deployed.json pointer — and REFUSE non-validated models, re-listing the gate's
reasons. This refusal is the governance beat: model risk management as a product rule, not a slide."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import DENOM_NA, guard, markdown_answer
from ..sqlkit import Refusal, as_choice
from ..studio import constants, registry

TITLE = "פריסת מודל"


@guard(TITLE)
def run(ctx, model_id="latest", family="site"):
    family = as_choice(family, "family", (constants.FAMILY_SITE, "severity"))
    meta, ids = registry.resolve_id(ctx, model_id, want="validated" if str(model_id).strip() in ("", "latest") else "any",
                                    family=family)
    if meta is None:
        raise Refusal(f"לא נמצא מודל מאומת לפריסה ('{model_id}', משפחה {family})",
                      [("מזהים קיימים: " + " · ".join(ids[-5:])) if ids else "הרישום ריק — אמנו מודל קודם",
                       "השער קודם לפריסה"])
    status = meta.get("status")
    trainer = "studio_train_severity" if family == "severity" else "studio_train_site"
    if status == "rejected":
        reasons = (meta.get("gate") or {}).get("reasons", [])
        raise Refusal(f"המודל {meta['model_id']} נדחה בשער האימות ואינו ניתן לפריסה — ריק עדיף על מספר מזויף",
                      [f"{trainer} עם train_until או preset אחרים", "studio_models לרשימת המודלים"],
                      detail=" | ".join(reasons) or "rejected by the validation gate")
    if status == "candidate":
        raise Refusal(f"המודל {meta['model_id']} טרם אומת — השער קודם לפריסה", ["הריצו את שער האימות של המשפחה ואז studio_deploy"])
    if status == "unreadable":
        raise Refusal(f"קובץ המטא של {meta['model_id']} אינו קריא", [trainer])
    already = status == "deployed"
    if not already:
        registry.deploy(ctx, meta)  # demote → pointer → status, one atomic sequence under the registry lock (family from meta)
    g = (meta.get("gate") or {}).get("metrics", {})
    if family == "severity":
        gate_line = (f"- רגישות להרוגים {g.get('fatal_recall')} · AUC {g.get('auc_fatal')} · "
                     f"פער אימון-אימות {g.get('overfit_auc_gap')}")
        readers = "- severity_predict ו-what_if קוראים את המודל הפרוס בכל הרצה — ללא אימון בזמן חיזוי"
    else:
        gate_line = (f"- Spearman {g.get('spearman')} · כיול {g.get('calibration')} · "
                     f"יחס סטייה {g.get('deviance_ratio')} · α {g.get('alpha')}")
        readers = "- site_ranking ומפת excess קוראים את המודל הפרוס בכל הרצה — ללא אימון בזמן חיזוי"
    body = [
        f"# {'כבר פרוס' if already else 'נפרס'} {meta['model_id']}",
        gate_line,
        readers,
        "- הסרת פריסה = פריסת מודל אחר (מצביע יחיד למשפחה)",
    ]
    caveats = ["פריסה = כתיבת deployed.json ברישום — אין אימון בזמן חיזוי (כלל הזהב של הדו״ח)",
               "מודל שנדחה אינו נפרס — הסירוב הזה הוא כלל המוצר"]
    return markdown_answer(TITLE, body, denom=DENOM_NA, caveats=caveats)


ACTION = Action(
    name="studio_deploy", label="פריסת מודל · studio_deploy",
    help="Write the single deployed.json pointer for a model family (site or severity). REFUSES rejected models "
         "(re-listing the gate's reasons) and unvalidated candidates - the governance rule, visible. 'latest' "
         "deploys the family's newest VALIDATED model.",
    inputs={"model_id": Input(kind="text", label="מזהה מודל", default="latest",
                              help="a VALIDATED model id from studio_models, or 'latest'"),
            "family": Input(kind="choice", label="משפחה", default="site",
                            choices=["site", "severity"], help="which model family to deploy into")},
    run=run)
