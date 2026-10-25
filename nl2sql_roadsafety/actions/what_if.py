# -*- coding: utf-8 -*-
"""what_if (P9, use ו): TWO scenarios through the deployed severity model — a baseline profile and one canned
switch (day→night, belted→unbelted, urban→interurban, fifty→ninety) — and the RELATIVE deltas of the severity
distribution. Deltas between scenarios are the only honest way to read this model; absolute fates never leave.
Since P12 the chart carries a second panel: the φ DIFFERENCES between the scenarios on the fatal-class margin
(the switch's own contribution vs everything the tree interactions moved with it; the shared bias cancels)."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, dispatch, guard, make_spec, markdown_answer, stamp, view_input
from ..sqlkit import as_choice
from ..studio import explain_severity as xs
from ..studio import severity
from .severity_predict import contribs_guarded, deployed_severity, model_caveats, profile_inputs, profile_words

VIEWS = ("chart", "markdown", "table", "sql")
TITLE = "מה אם · תרחישים"
COLS = ["class", "label", "p_baseline", "p_scenario", "ratio"]
_LRM = chr(0x200E)                             # pins tight signed numbers on the browser-rendered card (P9 rule)
SWITCHES = {  # label -> (profile field, from value, to value, ASCII slug for spec.basis — basis is strict ASCII)
    "יום לעומת לילה": ("time", "יום", "לילה", "day -> night"),
    "חגור לעומת לא חגור": ("safety", "חגור או קסדה", "ללא אמצעי בטיחות", "belted -> unbelted"),
    "עירוני לעומת לא-עירוני": ("road_type", "עירוני לא בצומת", "לא-עירוני לא בצומת", "urban -> interurban"),
    "חמישים לעומת תשעים": ("speed", "עד חמישים", "תשעים", "fifty -> ninety kph"),
}


@guard(TITLE)
def run(ctx, switch="יום לעומת לילה", road_type=severity.UNSET, time=severity.UNSET, casualty=severity.UNSET,
        age=severity.UNSET, safety=severity.UNSET, speed=severity.UNSET, view="chart"):
    view = as_choice(view, "view", VIEWS)
    switch = as_choice(switch, "switch", SWITCHES)
    base = {"road_type": road_type, "time": time, "casualty": casualty, "age": age,
            "safety": safety, "speed": speed}
    for field, v in base.items():
        base[field] = as_choice(v, field, [severity.UNSET] + list(severity.PROFILE_FIELDS[field][1]))
    field, from_v, to_v, slug = SWITCHES[switch]
    base = {**base, field: from_v}                            # the switch's field overrides the profile input
    scen = {**base, field: to_v}
    switch_col = severity.PROFILE_FIELDS[field][0]
    meta, raw = deployed_severity(ctx)
    p = severity.predict_proba(raw, [severity.profile_row(base), severity.profile_row(scen)])
    ratios = severity.relative(p[1], p[0])
    phi3, _ = contribs_guarded(meta, raw, [severity.profile_row(base), severity.profile_row(scen)])
    delta = [float(phi3[1][0][j] - phi3[0][0][j]) for j in range(len(severity.FEATURES))]  # class 0 = הרוג
    items, rest, _bias = xs.waterfall_parts(delta + [0.0], severity.FEATURES,
                                            severity.FEATURE_LABELS_HE, k=5)  # the shared bias cancels
    rows = [[c, severity.CLASS_LABELS_HE[c], round(p[0][c], 4), round(p[1][c], 4), round(ratios[c], 2)]
            for c in range(3)]
    caveats = model_caveats(meta) + [
        "הדלתא בין שני התרחישים היא הקריאה היחידה — לא הרמות · מתאם ולא סיבתיות: המודל לא מודד התערבות",
        "פאנל המובילים: הפרשי φ בין שני התרחישים על סקלת המרגין של מחלקת הרוג — לא יחידות הסתברות",
    ]
    denom = denominator("exposure", f"שני תרחישים דרך מודל חומרה פרוס {meta['model_id']} · יחס תרחיש/בסיס",
                        model_id=meta["model_id"])
    stamp_text = stamp("what_if", meta["model_id"][:40])
    spec = make_spec("accidents/what_if",
                     basis=f"what_if | model {meta['model_id']} | switch {field}: {slug}",
                     rows=rows, columns=COLS, sql=meta["sql"]["matrix"], denominator=denom, caveats=caveats,
                     model_id=meta["model_id"], switch=switch, profile=base, stamp=stamp_text,
                     drivers={"class_label": "הרוג", "items": items, "rest": rest, "bias": None,
                              "switch_feature": switch_col},
                     x="label", y="ratio", chip="יחס בין שני תרחישים חזויים")
    if view == "chart":
        from .. import charts
        spec["png_base64"] = charts.ratio_with_drivers(
            [r[1] for r in rows], [r[4] for r in rows],
            [i["label"] for i in items] + ["היתר"],
            [i["phi"] for i in items] + [rest],
            xlabel_ratio="יחס תרחיש מול בסיס (אחד = ללא שינוי)",
            xlabel_drivers="שינוי תרומת φ בין התרחישים (מחלקת הרוג)",
            ratio_colors=["#26323d", "#f7931e", "#0d9488"],
            annot=[f"{r[4]:g}x" for r in rows], neutral=(5,),
            title=f"מה אם · {switch} · {profile_words(base)}",
            badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
        spec["renderer"] = "png"
        return dispatch("chart", spec, TITLE)
    if view in ("table", "sql"):
        return dispatch(view, spec, TITLE)
    worst = max(range(3), key=lambda c: ratios[c])
    switch_delta = delta[severity.FEATURES.index(switch_col)]
    movers = [i for i in items if i["feature"] != switch_col][:2]
    body = [
        f"# מה אם · {switch}",
        f"- הפרופיל: {profile_words(base)}",
    ] + [f"- {severity.CLASS_LABELS_HE[c]}: פי {ratios[c]:.2f}" for c in range(3)] + [
        f"- ההסטה הגדולה ביותר: {severity.CLASS_LABELS_HE[worst]} (פי {ratios[worst]:.2f})",
        f"- ההחלפה עצמה ({severity.FEATURE_LABELS_HE[switch_col]}): {_LRM}{switch_delta:+.2f}{_LRM} על המרגין",
    ] + [f"- מוביל נוסף: {i['label']} ({_LRM}{i['phi']:+.2f}{_LRM})" for i in movers]
    return markdown_answer(TITLE, body, denom=denom, caveats=caveats)


ACTION = Action(
    name="what_if", label="מה אם · what_if",
    help="Two scenarios through the DEPLOYED severity model - a baseline profile and one canned switch "
         "(day->night, belted->unbelted, urban->interurban, fifty->ninety kph) - and the RELATIVE deltas of the "
         "predicted severity distribution. Association, not intervention. Refuses without a deployed severity "
         "model. Needs the [ml] extra.",
    inputs={"switch": Input(kind="choice", label="ההחלפה", default="יום לעומת לילה", choices=list(SWITCHES),
                            help="the one field that flips between the two scenarios"),
            **profile_inputs(), "view": view_input("chart", VIEWS)},
    run=run)
