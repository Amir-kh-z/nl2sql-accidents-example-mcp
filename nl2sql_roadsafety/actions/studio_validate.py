# -*- coding: utf-8 -*-
"""studio_validate: the gate. Predict the REAL target over the whole panel with the stored artifact, score the
holdout (the years the model never saw), and stamp the verdict — validated or rejected WITH reasons — into the
registry. Spearman >= 0.3 and calibration +-25% come from the report; the deviance-ratio bound is the plugin's
rule and is labelled as such on every card."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import DENOM_NA, dispatch, guard, make_spec, markdown_answer, stamp
from ..sqlkit import ActionError, Refusal, as_choice, rows_safe
from ..studio import constants, gate, model, panel, registry

VIEWS = ("markdown", "chart", "table")
TITLE = "אימות מודל"


@guard(TITLE)
def run(ctx, model_id="latest", view="markdown"):
    view = as_choice(view, "view", VIEWS)
    meta, ids = registry.resolve_id(ctx, model_id, want="any")
    if meta is None:
        raise Refusal(f"לא נמצא מודל '{model_id}' ברישום",
                      [("מזהים קיימים: " + " · ".join(ids[-5:])) if ids else "הרישום ריק — studio_train_site"])
    if meta.get("status") == "unreadable":
        raise Refusal(f"קובץ המטא של {meta['model_id']} אינו קריא — יש לאמן מחדש", ["studio_train_site"])
    model.require_xgboost()
    raw = registry.model_bytes(ctx, meta["model_id"])
    if raw is None:
        raise Refusal(f"קובץ המודל של {meta['model_id']} חסר מהרישום", ["studio_train_site"])
    y0, y1 = meta["panel"]["years"]
    train_until = meta["panel"]["train_until"]
    adt_fill = float(meta["adt_fill"]["value"])
    cols, rows = panel.fetch_panel(ctx, y0, y1, adt_fill)
    static = {(r[0], r[1]): dict(zip(panel.STATIC_COLUMNS[2:], r[2:])) for r in meta["static_attrs"]["rows"]}
    X, y, years, keys, ksi = panel.matrix(cols, rows, static)          # the REAL target — a shuffled model fails here
    mu = model.predict(raw, X)
    metrics = gate.evaluate(y, mu, years, train_until)
    status, reasons = gate.verdict(metrics)
    gate_block = {
        "validated_at": registry.now_utc(),
        "holdout_years": sorted({yr for yr in years if yr > train_until}),
        "metrics": metrics,
        "thresholds": {"spearman_min": constants.GATE["spearman_min"][0],
                       "calibration": list(constants.GATE["calibration"][0]),
                       "deviance_ratio_max": constants.GATE["deviance_ratio_max"][0]},
        "sources": {k: v[1] for k, v in constants.GATE.items()},
        "reasons": reasons, "verdict": status,
    }
    if registry.record_gate(ctx, meta["model_id"], gate_block, status, alpha=metrics["alpha"]) is None:
        # the verdict on the card MUST be the verdict in the registry — a silent 'candidate' was a sweep finding
        raise ActionError(f"meta.json for {meta['model_id']} became unreadable - the gate verdict was not saved, rerun studio_validate")
    ho = [i for i, yr in enumerate(years) if yr > train_until]
    hold_rows = sorted(([keys[i][0], keys[i][1], years[i], y[i], round(mu[i], 3)] for i in ho),
                       key=lambda r: (-r[3], r[0], r[1], r[2]))
    caveats = _caveats(gate_block, train_until, reasons)
    verdict_he = "עבר את השער — validated" if status == "validated" else "נדחה — rejected"
    spec = make_spec("accidents/studio_gate",
                     basis=f"studio_validate | {meta['model_id']} | holdout {'-'.join(map(str, gate_block['holdout_years']))} | "
                           f"spearman {metrics['spearman']} | calibration {metrics['calibration']} | "
                           f"deviance_ratio {metrics['deviance_ratio']} | alpha {metrics['alpha']} | {status}",
                     rows=hold_rows, columns=["road", "seg", "year", "observed", "mu"],
                     sql=meta["sql"]["panel"], denominator=DENOM_NA, caveats=caveats,
                     model_id=meta["model_id"], gate=gate_block, metrics=metrics, alpha=metrics["alpha"],
                     deciles=_deciles(y, mu, ho),           # [n, sum_obs, sum_mu] per μ-decile — the page's
                     stamp=stamp("studio_validate", meta["model_id"][:40], status))   # plotly chart reads these (P8)
    if view == "table":
        return dispatch("table", spec, TITLE)
    if view == "chart":
        from .. import charts
        deciles = _deciles(y, mu, ho)
        # DIAGNOSTICS on the chart face only (markdown/table untouched): the calibration scatter and the ROC.
        # ROC is reported, never gating — constants.GATE and gate.verdict are untouched, so the seeded
        # registry's frozen verdicts (deployed 2023, rejected 2022, rejected shuffled) cannot move.
        y_ho, mu_ho = [y[i] for i in ho], [mu[i] for i in ho]
        spec["points"] = _points(y_ho, mu_ho)
        extra = []
        roc = gate.roc_curve(y_ho, mu_ho)
        if roc is None:                            # degenerate positive class — degrade, never error
            extra.append("ROC לא זמין — מחלקה מנוונת")
        else:
            fpr, tpr, auc, info = roc
            spec["roc"] = {"fpr": [round(v, 4) for v in fpr], "tpr": [round(v, 4) for v in tpr],
                           "auc": round(auc, 4), "positive": info}
            # the gate discipline: every threshold prints its source tag — this one is plugin-defined,
            # like the deviance-ratio rule
            extra.append(f"מחלקה חיובית ל-ROC: תצפית בעשירון העליון של הנצפה (y ≥ {info['threshold']:g}) — "
                         f"n={info['positive_n']:,} ({info['share'] * 100:.1f}% משורות האימות) (כלל התוסף)")
        spec["caveats"] = caveats + extra          # the PNG below keeps the ORIGINAL caveats — its twin
        spec["png_base64"] = charts.hbars(         # stays the deciles image, byte-identical to before
            [f"עשירון {i + 1}" for i in range(len(deciles))], [d[1] for d in deciles],
            xlabel="תאונות בשנות האימות", markers=[d[2] for d in deciles],
            annot=[f"n={d[0]}" for d in deciles],
            title=f"כיול לפי עשירוני חיזוי · {verdict_he}",
            badge=f"מכנה: {DENOM_NA['label']}", caveats=caveats, stamp=spec["stamp"])
        spec["renderer"] = "png"
        return dispatch("chart", spec, TITLE)
    m = metrics
    body = [
        f"# {verdict_he}",
        f"- מודל: {meta['model_id']} (preset {meta['preset']}, train_until {train_until})",
        f"- Spearman: {m['spearman']} (סף ≥ {gate_block['thresholds']['spearman_min']} — דו״ח)",
        f"- כיול Σצפוי/Σנצפה: {m['calibration']} (תחום {gate_block['thresholds']['calibration'][0]}–"
        f"{gate_block['thresholds']['calibration'][1]} — דו״ח)",
        f"- יחס סטייה אימות/אימון: {m['deviance_ratio']} (סף ≤ {gate_block['thresholds']['deviance_ratio_max']} — כלל התוסף)",
        f"- α (פיזור NB לפי מומנטים): {m['alpha']} · שנות אימות: "
        + ", ".join(map(str, gate_block["holdout_years"])) + f" ({m['n']:,} שורות)",
    ]
    body += [f"- סיבת דחייה: {r}" for r in reasons]
    if status == "validated":
        body.append("- הצעד הבא: studio_deploy")
    return markdown_answer(TITLE, body, denom=DENOM_NA, caveats=caveats)


def _points(y_ho, mu_ho, cap: int = 600):
    """Calibration scatter pairs [mu, observed] over the holdout: sorted by mu (observed breaks ties — fully
    deterministic) and stride-sampled to <= cap points (every k-th after the sort — no RNG)."""
    pairs = sorted(zip(mu_ho, y_ho), key=lambda p: (p[0], p[1]))
    k = max(1, -(-len(pairs) // cap))
    return [[round(float(m), 3), int(o)] for m, o in pairs[::k]]


def _deciles(y, mu, ho, k: int = 10):
    """[(n, sum_obs, sum_mu)] by predicted-μ decile over the holdout rows."""
    pairs = sorted(((mu[i], y[i]) for i in ho), key=lambda p: p[0])
    if not pairs:
        return []
    out = []
    n = len(pairs)
    for d in range(k):
        chunk = pairs[d * n // k: (d + 1) * n // k]
        if chunk:
            out.append((len(chunk), sum(p[1] for p in chunk), round(sum(p[0] for p in chunk), 1)))
    return out


def _caveats(gate_block, train_until, reasons):
    t = gate_block["thresholds"]
    out = [
        f"שער: Spearman ≥ {t['spearman_min']} וכיול {t['calibration'][0]}–{t['calibration'][1]} לפי הדו״ח · "
        f"יחס סטייה ≤ {t['deviance_ratio_max']} = כלל התוסף (ממוצע לשורה, לא סכום)",
        "אימות על שנים שהמודל לא ראה: " + ", ".join(map(str, gate_block["holdout_years"])),
        f"α לפי מומנטים על שאריות האימות — אפס פירושו פואסון",
    ]
    out += [f"נדחה: {r}" for r in reasons]
    return out


ACTION = Action(
    name="studio_validate", label="אימות מודל · studio_validate",
    help="The gate: predict the REAL target over the panel with the stored artifact and score the holdout years "
         "the model never saw. Spearman >= 0.3 and calibration within 25% are the report's thresholds; the "
         "deviance-ratio bound is the plugin's rule (labelled). Writes validated/rejected WITH reasons into the "
         "registry. Needs the [ml] extra.",
    inputs={
        "model_id": Input(kind="text", label="מזהה מודל", default="latest",
                          help="a model id from studio_models, or 'latest'"),
        "view": Input(kind="choice", label="תצוגה", default="markdown", choices=list(VIEWS),
                      help="markdown = the gate card; chart = calibration by prediction decile; table = holdout rows"),
    },
    run=run)
