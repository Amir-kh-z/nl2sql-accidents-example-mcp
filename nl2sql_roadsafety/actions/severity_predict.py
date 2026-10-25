# -*- coding: utf-8 -*-
"""severity_predict (P9, use ג): one risk profile → the DEPLOYED severity model's predicted distribution,
shown RELATIVE to the holdout-era baseline. The model ranks risk profiles — it does not predict a person's
fate; every face says so. Unset fields stay honest missing values (the model's default path), never imputed.
Since P12 the chart carries a second panel: the profile's own φ waterfall on the fatal-class margin."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, dispatch, guard, make_spec, markdown_answer, stamp, view_input
from ..sqlkit import ActionError, Refusal, as_choice
from ..studio import explain_severity as xs
from ..studio import model, registry, severity

VIEWS = ("chart", "markdown", "table", "sql")
TITLE = "פרופיל סיכון לחומרה"
COLS = ["class", "label", "p_model", "baseline", "relative"]
_LRM = chr(0x200E)                             # pins tight signed numbers on the browser-rendered card (P9 rule)


def profile_inputs():
    labels = {"road_type": "סוג דרך", "time": "יום או לילה", "casualty": "סוג נפגע",
              "age": "קבוצת גיל", "safety": "אמצעי בטיחות", "speed": "מהירות מותרת"}
    return {field: Input(kind="choice", label=labels[field], default=severity.UNSET,
                         choices=[severity.UNSET] + list(mapping),
                         help="leave unset for the model's missing-value path (honest 'unspecified')")
            for field, (_, mapping) in severity.PROFILE_FIELDS.items()}


def deployed_severity(ctx):
    pointer, meta = registry.deployed(ctx, severity.FAMILY)
    if pointer is None:
        raise Refusal("אין מודל חומרה פרוס — הפעולה דורשת מודל מאומת ופרוס",
                      ["studio_train_severity ואז studio_validate_severity ואז studio_deploy (משפחה severity)"])
    if meta is None:
        raise Refusal("deployed.json של משפחת החומרה מצביע על מודל חסר או בלתי קריא — יש לפרוס מחדש",
                      ["studio_models (משפחה severity)", "studio_deploy"])
    severity.contract_check(meta)                             # version tripwire first — names can hide recipe drift
    raw = registry.model_bytes(ctx, meta["model_id"], family=severity.FAMILY)
    if raw is None:
        raise Refusal("קובץ המודל הפרוס חסר מהרישום — יש לאמן ולפרוס מחדש", ["studio_train_severity"])
    return meta, raw


def predict_profile(meta, raw, choices: dict):
    probs = severity.predict_proba(raw, [severity.profile_row(choices)])[0]
    baseline = meta.get("class_shares_holdout") or meta.get("class_shares_train")
    rel = severity.relative(probs, baseline)
    return probs, baseline, rel


def contribs_guarded(meta, raw, X):
    """ONE guarded TreeSHAP pass for the profile faces: (phi (n, 3, 13) bias last, margins (n, 3)) with the
    runtime identity gate — a stored artifact that no longer matches this xgboost build fails loudly, never draws."""
    phi3, margins = xs.contribs3(raw, X)
    worst = xs.check_identity3(phi3, margins)
    if worst > xs.IDENTITY_TOL:
        raise ActionError(f"SHAP identity violated for {meta['model_id']}: max |sum(phi) - margin| = "
                          f"{worst:.4g} > {xs.IDENTITY_TOL} - the artifact does not match this xgboost "
                          f"build, retrain")
    return phi3, margins


def profile_words(choices: dict) -> str:
    parts = [v for v in choices.values() if v and v != severity.UNSET]
    return " · ".join(parts) if parts else "פרופיל ריק (הכול לא צוין)"


def model_caveats(meta) -> list[str]:
    g = (meta.get("gate") or {}).get("metrics", {})
    return [
        "הסתברויות יחסיות בלבד — המודל מדרג פרופילי סיכון, אינו חוזה גורל של אדם",
        "הבסיס = שיעורי החומרה בשנות האימות של המודל · שדות שלא צוינו נשארים חסרים (המסלול החסר של המודל)",
        f"מודל {meta['model_id']}: רגישות להרוגים {g.get('fatal_recall')} · AUC {g.get('auc_fatal')} · "
        f"מתאם ולא סיבתיות",
        "שיעורי החומרה נודדים לאורך התקופה — השוואות בין פרופילים, לא רמות מוחלטות",
    ]


@guard(TITLE)
def run(ctx, road_type=severity.UNSET, time=severity.UNSET, casualty=severity.UNSET, age=severity.UNSET,
        safety=severity.UNSET, speed=severity.UNSET, view="chart"):
    view = as_choice(view, "view", VIEWS)
    choices = {"road_type": road_type, "time": time, "casualty": casualty, "age": age,
               "safety": safety, "speed": speed}
    for field, v in choices.items():
        choices[field] = as_choice(v, field, [severity.UNSET] + list(severity.PROFILE_FIELDS[field][1]))
    meta, raw = deployed_severity(ctx)
    probs, baseline, rel = predict_profile(meta, raw, choices)
    phi3, _ = contribs_guarded(meta, raw, [severity.profile_row(choices)])
    items, rest, bias = xs.waterfall_parts(phi3[0][0], severity.FEATURES, severity.FEATURE_LABELS_HE, k=5)
    rows = [[c, severity.CLASS_LABELS_HE[c], round(probs[c], 4), round(baseline[c], 4), round(rel[c], 2)]
            for c in range(3)]
    caveats = model_caveats(meta) + [
        "פאנל המובילים: תרומות φ על סקלת המרגין של מחלקת הרוג — לא יחידות הסתברות",
    ]
    denom = denominator("exposure", f"תחזית מודל חומרה פרוס {meta['model_id']} · יחסית לבסיס שנות האימות",
                        model_id=meta["model_id"])
    words = profile_words(choices)
    stamp_text = stamp("severity_predict", meta["model_id"][:40])
    spec = make_spec("accidents/severity_predict",
                     basis=f"severity_predict | model {meta['model_id']} | profile "
                           f"{sum(1 for v in choices.values() if v != severity.UNSET)} fields set",
                     rows=rows, columns=COLS, sql=meta["sql"]["matrix"], denominator=denom, caveats=caveats,
                     model_id=meta["model_id"], profile=choices, stamp=stamp_text, x="label", y="relative",
                     drivers={"class_label": "הרוג", "items": items, "rest": rest, "bias": bias,
                              "switch_feature": None},
                     chip="פרופיל מול בסיס שנות האימות — יחסי בלבד")
    if view == "chart":
        from .. import charts
        spec["png_base64"] = charts.ratio_with_drivers(
            [r[1] for r in rows], [r[4] for r in rows],
            [i["label"] for i in items] + ["היתר", "בסיס המודל"],
            [i["phi"] for i in items] + [rest, bias],
            xlabel_ratio="סיכון יחסי לעומת הבסיס (אחד = כמו הבסיס)",
            xlabel_drivers="תרומת φ למרגין מחלקת הרוג",
            ratio_colors=["#26323d", "#f7931e", "#0d9488"],
            annot=[f"{r[4]:g}x" for r in rows], neutral=(5, 6),
            title=f"פרופיל: {words}",
            badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
        spec["renderer"] = "png"
        return dispatch("chart", spec, TITLE)
    if view in ("table", "sql"):
        return dispatch(view, spec, TITLE)
    body = [f"# פרופיל: {words}"] + [
        f"- {severity.CLASS_LABELS_HE[c]}: פי {rel[c]:.2f} מהבסיס" for c in range(3)
    ] + [
        f"- מוביל: {i['label']} ({_LRM}{i['phi']:+.2f}{_LRM})" for i in items[:3]
    ] + ["- המודל מדרג פרופילים — לא גורל של אדם · what_if משווה שני תרחישים"]
    return markdown_answer(TITLE, body, denom=denom, caveats=caveats)


ACTION = Action(
    name="severity_predict", label="פרופיל סיכון לחומרה · severity_predict",
    help="One risk profile -> the DEPLOYED severity model's predicted class distribution, RELATIVE to the "
         "holdout-era baseline (killed/severe/slight). Unset fields stay missing - the honest 'unspecified'. "
         "Refuses without a deployed severity model. Needs the [ml] extra.",
    inputs={**profile_inputs(), "view": view_input("chart", VIEWS)},
    run=run)
