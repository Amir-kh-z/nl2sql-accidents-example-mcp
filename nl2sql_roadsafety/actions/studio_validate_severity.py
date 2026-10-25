# -*- coding: utf-8 -*-
"""studio_validate_severity (P9): the severity family's gate — predict the REAL target over the person matrix
with the stored artifact and score the holdout years on DISCRIMINATION: fatal recall, AUC(fatal), and a
no-overfit bound (all plugin-labelled; calibration is deliberately NOT a gate metric — the class shares drift
across the era). Writes validated/rejected WITH reasons into the registry."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import DENOM_NA, dispatch, guard, make_spec, markdown_answer, stamp
from ..sqlkit import ActionError, Refusal, as_choice
from ..studio import model, registry, severity

VIEWS = ("markdown", "chart", "table")
TITLE = "אימות מודל חומרה"


@guard(TITLE)
def run(ctx, model_id="latest", view="markdown"):
    view = as_choice(view, "view", VIEWS)
    meta, ids = registry.resolve_id(ctx, model_id, family=severity.FAMILY)
    if meta is None or meta.get("status") == "unreadable":
        raise Refusal(f"לא נמצא מודל חומרה קריא ('{model_id}')",
                      [("מזהים קיימים: " + " · ".join(ids[-5:])) if ids else "הרישום ריק — studio_train_severity"])
    severity.contract_check(meta)                             # version tripwire first — names can hide recipe drift
    model.require_xgboost()
    raw = registry.model_bytes(ctx, meta["model_id"], family=severity.FAMILY)
    if raw is None:
        raise Refusal("קובץ המודל חסר מהרישום — יש לאמן מחדש", ["studio_train_severity"])
    train_until = int(meta["panel"]["train_until"])
    y0, y1 = meta["panel"]["years"]
    X, y, years = severity.fetch_matrix(ctx, y0, y1)          # the REAL target — a shuffled model fails here
    probs = severity.predict_proba(raw, X)
    tr = [i for i, yr in enumerate(years) if yr <= train_until]
    ho = [i for i, yr in enumerate(years) if yr > train_until]
    metrics = severity.evaluate([y[i] for i in tr], [probs[i] for i in tr],
                                [y[i] for i in ho], [probs[i] for i in ho])
    status, reasons = severity.verdict(metrics)
    gate_block = {
        "validated_at": registry.now_utc(),
        "holdout_years": sorted({yr for yr in years if yr > train_until}),
        "metrics": metrics,
        "thresholds": {k: v[0] for k, v in severity.GATE.items()},
        "sources": {k: v[1] for k, v in severity.GATE.items()},
        "reasons": reasons, "verdict": status,
    }
    if registry.record_gate(ctx, meta["model_id"], gate_block, status, family=severity.FAMILY) is None:
        raise ActionError(f"meta.json for {meta['model_id']} became unreadable - the gate verdict was not saved, "
                          f"rerun studio_validate_severity")
    deciles = _fatal_deciles([y[i] for i in ho], [probs[i][0] for i in ho])
    caveats = _caveats(gate_block)
    spec = make_spec("accidents/studio_gate_severity",
                     basis=f"studio_validate_severity | {meta['model_id']} | holdout "
                           f"{'-'.join(map(str, gate_block['holdout_years']))} | fatal_recall "
                           f"{metrics['fatal_recall']} | auc_fatal {metrics['auc_fatal']} | gap "
                           f"{metrics['overfit_auc_gap']} | {status}",
                     rows=deciles, columns=["decile", "n", "fatal", "fatal_pct", "lift"],
                     sql=meta["sql"]["matrix"], denominator=DENOM_NA, caveats=caveats,
                     model_id=meta["model_id"], gate=gate_block, metrics=metrics,
                     stamp=stamp("studio_validate_severity", meta["model_id"][:26], status))  # sans timestamp — the full id is in basis/caveats/chip; with it the stamp collides with the RTL credit
    if view == "table":
        return dispatch("table", spec, TITLE)
    if view == "chart":
        from .. import charts
        spec["png_base64"] = charts.hbars(
            [f"עשירון {int(d[0])}" for d in deciles], [d[4] for d in deciles],
            xlabel="Lift של הרוגים בעשירון לפי הסתברות המודל (פי כמה מהבסיס)", vline=1.0, vline_label="בסיס",
            annot=[f"n={d[1]}" for d in deciles],
            title="הפרדה בשנות האימות: עשירוני סיכון קטלני",
            badge=f"מכנה: {DENOM_NA['label']}", caveats=caveats,
            stamp=spec["stamp"])
        spec["renderer"] = "png"
        return dispatch("chart", spec, TITLE)
    verdict_he = "עבר את השער — validated" if status == "validated" else "נדחה — rejected"
    body = [
        f"# {verdict_he} · {meta['model_id']}",
        f"- רגישות להרוגים (recall): {metrics['fatal_recall']} (סף {severity.GATE['fatal_recall_min'][0]} · כלל התוסף)",
        f"- AUC להרוגים: {metrics['auc_fatal']} (סף {severity.GATE['auc_fatal_min'][0]} · כלל התוסף)",
        f"- פער אימון-אימות: {metrics['overfit_auc_gap']} (מרבי {severity.GATE['overfit_auc_gap_max'][0]} · כלל התוסף)",
        f"- רגישות לקשה: {metrics['severe_recall']} · לקל: {metrics['slight_recall']}",
    ] + ([f"- הסיבה: {r}" for r in reasons] if reasons else ["- ניתן לפרוס: studio_deploy (משפחה severity)"])
    return markdown_answer(TITLE, body, denom=DENOM_NA, caveats=caveats)


def _fatal_deciles(y_hold, p_fatal, k: int = 10):
    order = sorted(range(len(y_hold)), key=lambda i: -p_fatal[i])
    base = sum(1 for v in y_hold if v == 0) / max(len(y_hold), 1)
    out = []
    for d in range(k):
        chunk = order[d * len(order) // k:(d + 1) * len(order) // k]
        fatal = sum(1 for i in chunk if y_hold[i] == 0)
        pct = fatal / max(len(chunk), 1)
        out.append([d + 1, len(chunk), fatal, round(100 * pct, 2), round(pct / base, 2) if base else 0.0])
    return out


def _caveats(gate_block):
    return [
        "השער מודד הפרדה (רגישות ו-AUC) ולא כיול — שיעורי החומרה נודדים לאורך התקופה ותחזית רמה תיכשל בכנות",
        "הסתברויות יחסיות בלבד: המודל מדרג פרופילי סיכון, אינו חוזה גורל של אדם",
        f"שנות האימות: {'-'.join(map(str, gate_block['holdout_years']))} — המודל לא ראה אותן",
        "כל שלושת הספים הם כללי התוסף, שמרניים מהערכים שהושגו בדו״ח המתודולוגי",
    ]


ACTION = Action(
    name="studio_validate_severity", label="אימות מודל חומרה · studio_validate_severity",
    help="The severity gate: predict the REAL target with the stored artifact and score the holdout years on "
         "DISCRIMINATION - fatal recall >= 0.5, AUC(fatal) >= 0.8, overfit gap <= 0.05 (all plugin rules, set "
         "below the report's achieved values). Calibration is deliberately not gated: the class shares drift. "
         "Writes validated/rejected WITH reasons. Needs the [ml] extra.",
    inputs={
        "model_id": Input(kind="text", label="מזהה מודל", default="latest",
                          help="a severity model id from studio_models, or 'latest'"),
        "view": Input(kind="choice", label="תצוגה", default="markdown", choices=list(VIEWS),
                      help="markdown = the gate card; chart = fatal-risk decile lift; table = the deciles"),
    },
    run=run)
