# -*- coding: utf-8 -*-
"""severity_explain (P12, use ג's explanation face): the severity model explains itself — a SHAP beeswarm
over the person matrix (the report's "grand finale", production-grade), a dependence view per feature, the
mean|φ| ranking and a plain-Hebrew drivers card.

Honesty rules this face draws, not just declares: φ on the SOFTMAX MARGIN scale of ONE chosen class (never
"effect on probability"); value-color only for genuinely ordered features (nominal codes grey — no fake
ordinal scale); NULL dots hollow ("לא ידוע" is a real model input); deterministic sampling and jitter
(repeated runs are byte-comparable); Σφ + bias = margin enforced at runtime on every run."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, dispatch, guard, make_spec, markdown_answer, stamp, view_input
from ..sqlkit import Refusal, as_choice
from ..studio import explain_severity as xs
from ..studio import model, registry, severity
from .severity_predict import contribs_guarded, deployed_severity

VIEWS = ("chart", "markdown", "table", "sql")
TITLE = "הסבר מודל החומרה"
COLS = ["feature", "label", "mean_abs_phi", "mean_phi", "direction", "unknown_share"]
POLICY_CAVEAT = "צבע ערך רק למאפיינים סדורים · קטגוריאלי אפור ללא סולם · לא ידוע חלול"
READING_NOTE = "פיזור אנכי בערך נתון = אינטראקציות עם מאפיינים אחרים"
_WARNINGS = [
    "מתאם ולא סיבתיות — המודל לא מודד התערבות",
    "מאפיינים מתואמים מתחלקים בקרדיט — נקראים כקבוצה",
    "סקלת מרגין (סופטמקס), לא יחידות הסתברות",
    "מדגם דטרמיניסטי בזרע קבוע — ריצות חוזרות זהות",
]


def _resolve(ctx, model_id):
    """(meta, raw, status_caveat) — 'deployed' walks the family's refusal ladder; an explicit id (rejected
    included — explaining a rejection is legitimate diagnostics) adds the status caveat, the studio_explain
    precedent."""
    s = str(model_id or "").strip()
    if s in ("", "deployed"):
        meta, raw = deployed_severity(ctx)
        return meta, raw, None
    meta, ids = registry.resolve_id(ctx, s, family=severity.FAMILY)
    if meta is None or meta.get("status") == "unreadable":
        raise Refusal(f"לא נמצא מודל חומרה קריא בשם '{s}'",
                      [("מזהים קיימים: " + " · ".join(ids[-5:])) if ids
                       else "הרישום ריק — studio_train_severity"])
    severity.contract_check(meta)
    raw = registry.model_bytes(ctx, meta["model_id"], family=severity.FAMILY)
    if raw is None:
        raise Refusal("קובץ המודל חסר מהרישום — יש לאמן ולפרוס מחדש",
                      ["studio_models (משפחה severity)", "studio_train_severity"])
    status = meta.get("status")
    cav = (None if status == "deployed"
           else f"המודל המוסבר אינו המודל הפרוס (סטטוס: {status}) — אבחון, לא כלי דירוג")
    return meta, raw, cav


def _null_share_caveat(rows):
    """The high-unknown honesty line (live: the safety row is ~63% hollow). Pure, so the 0.3 threshold
    and the :.0% formatting are unit-testable — the fixture's shares never reach it (sweep)."""
    worst = max(rows, key=lambda r: r[5])
    if worst[5] >= 0.3:
        return f"{worst[1]}: {worst[5]:.0%} לא ידוע — הנקודות החלולות הן קלט אמיתי של המודל"
    return None


def _direction(feature: str, corr) -> str:
    if feature not in xs.ORDERED:
        return "קטגוריאלי"
    if corr is None:
        return "מדגם קטן"
    if corr > 0.2:
        return "עולה עם הערך"
    if corr < -0.2:
        return "יורדת עם הערך"
    return "שטוחה"


@guard(TITLE)
def run(ctx, model_id="deployed", severity_class="הרוג", sample="20k", feature="none", view="chart"):
    view = as_choice(view, "view", VIEWS)
    severity_class = as_choice(severity_class, "severity_class", xs.CLASS_CHOICES)
    sample = as_choice(sample, "sample", xs.SAMPLES)
    feature = as_choice(feature, "feature", ["none"] + list(severity.FEATURES))
    meta, raw, status_caveat = _resolve(ctx, model_id)
    model.require_xgboost()                              # fail readable BEFORE the matrix query
    y0, y1 = meta["panel"]["years"]
    X, _y, _years = severity.fetch_matrix(ctx, y0, y1)
    n_total = len(X)
    if n_total == 0:
        raise Refusal("אין שורות נפגעים בתקופת המודל — אין מה להסביר", ["severity_profile לתמונת החומרה"])
    idx = xs.sample_indices(n_total, xs.SAMPLES[sample])
    Xs = [X[i] for i in idx]
    phi3, _margins = contribs_guarded(meta, raw, Xs)      # the shared runtime identity gate (P12)
    cls = xs.CLASS_CHOICES[severity_class]
    k = len(severity.FEATURES)
    phi_cls = phi3[:, cls, :k]
    decode = xs.decode_labels(ctx)
    Xd = xs.mask_display_sentinels(Xs)                    # sweep: sex_code 0 is never a LEVEL on display
    order, imp, dots = xs.build_swarm(phi_cls, Xd, severity.FEATURES, set(xs.ORDERED),
                                      severity.FEATURE_LABELS_HE, decode)
    rows = []
    for j in order:
        f = severity.FEATURES[j]
        corr = xs.value_phi_corr(phi_cls, Xd, j) if f in xs.ORDERED else None
        rows.append([f, severity.FEATURE_LABELS_HE[f], round(imp[j], 4),
                     round(float(phi_cls[:, j].mean()), 4), _direction(f, corr), xs.null_share(Xd, j)])
    g = (meta.get("gate") or {}).get("metrics", {})
    quality = (f"רגישות להרוגים {g.get('fatal_recall')} · AUC {g.get('auc_fatal')}" if g
               else "טרם אומת — ללא מדדי שער")            # sweep: a candidate's gate is None, never "None"
    caveats = [
        "ערכי φ על סקלת המרגין (סופטמקס) של המחלקה הנבחרת — לא יחידות הסתברות",
        "מתאם ולא סיבתיות · מאפיינים מתואמים מתחלקים בקרדיט — נקראים כקבוצה",
        f"מודל {meta['model_id']}: {quality}",
        f"מדגם {len(idx):,} מתוך {n_total:,} שורות נפגעים · זרע קבוע — ריצות חוזרות זהות",
        POLICY_CAVEAT,
    ]
    null_line = _null_share_caveat(rows)
    if null_line:
        caveats.append(null_line)
    if status_caveat:
        caveats.append(status_caveat)
    denom = denominator("counts", "שורות נפגעים של תקופת המודל — הסבר תרומות, לא שיעור סיכון",
                        model_id=meta["model_id"])
    stamp_text = stamp("severity_explain", xs.CLASS_SLUGS[cls], f"n{len(idx)}", meta["model_id"][:40])
    basis = (f"severity_explain | class {xs.CLASS_SLUGS[cls]} | sample {len(idx)} | rows {n_total}"
             f" | model {meta['model_id']}")
    sql = severity.matrix_sql(y0, y1) + "\n\n-- dictionary decode (the second read-only query)\n" + xs.lookup_sql()
    row_labels = [severity.FEATURE_LABELS_HE[severity.FEATURES[j]] for j in order]
    ordered_rows = [severity.FEATURES[j] in xs.ORDERED for j in order]
    spec = make_spec("accidents/severity_explain", basis=basis, rows=rows, columns=COLS, sql=sql,
                     denominator=denom, caveats=caveats, model_id=meta["model_id"], stamp=stamp_text,
                     severity_class=severity_class, sample=sample, y="mean_abs_phi",
                     chip="מה מזין את מודל החומרה — הסבר SHAP")
    if feature == "none":
        spec["swarm"] = {"features": row_labels, "ordered": ordered_rows,
                         "xlabel": f"תרומת φ למרגין · {severity_class}", **dots}
    else:
        j = severity.FEATURES.index(feature)
        dep = xs.build_dependence(phi_cls, Xd, severity.FEATURES, j, decode)
        dep["xlabel"] = severity.FEATURE_LABELS_HE[feature]
        dep["ylabel"] = f"תרומת φ · {severity_class}"
        spec["dependence"] = dep
        # the face's own reading note LEADS (the 6-line PNG cap was cutting exactly it — sweep), and the
        # coloring-policy caveat leaves: the dependence face is monochrome, the policy is inapplicable
        spec["caveats"] = caveats = [READING_NOTE] + [c for c in caveats if c != POLICY_CAVEAT]
    if view == "chart":
        from .. import charts
        if feature == "none":
            png = charts.beeswarm(
                row_labels, dots, xlabel=f"תרומת φ למרגין · {severity_class}",
                ordered_rows=ordered_rows, colorbar_label="ערך המאפיין (מנורמל)",
                title=f"נחיל SHAP — מודל החומרה · {severity_class}",
                badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
        else:
            png = charts.dependence_dots(
                dep["xj"], dep["phi"], dep["is_null"],
                xlabel=severity.FEATURE_LABELS_HE[feature], ylabel=f"תרומת φ · {severity_class}",
                ticks=dep["ticks"], null_x=dep["null_x"],
                title=f"תלות φ — {severity.FEATURE_LABELS_HE[feature]} · {severity_class}",
                badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
        spec["png_base64"] = png
        spec["renderer"] = "png"                        # attached AFTER make_spec — keep them in step (P5)
        return dispatch("chart", spec, TITLE)
    if view in ("table", "sql"):
        return dispatch(view, spec, TITLE)
    top = rows[:5]
    body = [
        "# מה מזין את מודל החומרה",
        f"- המחלקה: {severity_class} · מדגם {len(idx):,} מתוך {n_total:,} שורות נפגעים",
    ] + [f"- {r[1]}: ממוצע φ בערך מוחלט {r[2]:.3f} · המגמה {r[4]}" for r in top] + [
        "# ארבע האזהרות",
    ] + [f"- {w}" for w in _WARNINGS] + [
        "- לתלות של מאפיין בודד: feature · לפרופיל בודד: severity_predict · לתרחישים: what_if",
    ]
    return markdown_answer(TITLE, body, denom=denom, caveats=caveats)


ACTION = Action(
    name="severity_explain", label="הסבר מודל החומרה · severity_explain",
    help="The severity model explains itself: a SHAP beeswarm over the person matrix (phi on the softmax "
         "margin scale of the chosen class - killed by default), a per-feature dependence view, the "
         "mean|phi| ranking with direction and unknown-share, and a plain-Hebrew drivers card. Honest "
         "coloring: value-color only for ordered features, nominal codes grey, NULL dots hollow. "
         "Deterministic sample (20k default, a few seconds end to end; full = ~340k live rows, under a "
         "minute). Refuses without a severity model. Needs the [ml] extra.",
    inputs={
        "model_id": Input(kind="text", label="מזהה מודל", default="deployed",
                          help="'deployed' (default) or an explicit id from studio_models (family severity); "
                               "non-deployed ids add a status caveat"),
        "severity_class": Input(kind="choice", label="מחלקת חומרה", default="הרוג",
                                choices=list(xs.CLASS_CHOICES),
                                help="which class margin the phi values explain; the slight class is the "
                                     "mirror complement and is omitted"),
        "sample": Input(kind="choice", label="מדגם", default="20k", choices=list(xs.SAMPLES),
                        help="contribs are linear in rows: 20k answers in a few seconds end to end, "
                             "full (~340k live rows) takes up to a minute"),
        "feature": Input(kind="choice", label="מאפיין לתלות", default="none",
                         choices=["none"] + list(severity.FEATURES),
                         help="none = the beeswarm; a feature name flips the chart to its dependence view "
                              "(phi vs value)"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
