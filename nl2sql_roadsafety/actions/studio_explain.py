# -*- coding: utf-8 -*-
"""studio_explain (use ז, stretch): TreeSHAP over the site model — WHY a segment's expectation is what it is.
Per-site: the top features' φ per year (log-rate scale) next to observed-vs-predicted (the report's rendering).
Empty site = the global mean|φ| profile. φ sums to ln μ exactly — the identity the tests pin. No training at
prediction time; features rebuilt from the artifact's contract like site_ranking."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import DENOM_NA, denominator, dispatch, guard, make_spec, markdown_answer, stamp, view_input
from ..sqlkit import ActionError, Refusal, as_choice
from ..studio import constants, explain, gate, model, panel, predict, registry

VIEWS = ("chart", "markdown", "table", "sql")
TITLE = "תחזית והסבר לאתר"
_LRM = chr(0x200E)                                        # pins tight digit ranges in the browser-rendered card
                                                          # (the P8 en-dash flip — a literal LRM fights tooling)
SITE_COLS = ["year", "observed", "mu"]                    # + the top-k feature φ columns + bias (built per run)
GLOBAL_COLS = ["feature", "label", "mean_abs_phi", "mean_phi"]


@guard(TITLE)
def run(ctx, site="", model_id="deployed", style="פרופיל", view="chart"):
    view = as_choice(view, "view", VIEWS)
    style = as_choice(style, "style", ("פרופיל", "נחיל"))
    meta = _resolve_model(ctx, model_id)
    model.require_xgboost()
    predict.contract_check(meta)
    raw = registry.model_bytes(ctx, meta["model_id"])
    if raw is None:
        raise Refusal("קובץ המודל חסר מהרישום — יש לאמן ולפרוס מחדש", ["studio_models", "studio_train_site"],
                      detail=f"model.ubj missing for {meta['model_id']}")
    y0, y1 = meta["panel"]["years"]
    adt_fill = float(meta["adt_fill"]["value"])
    cols, rows = panel.fetch_panel(ctx, y0, y1, adt_fill)
    sql = panel.panel_sql(y0, y1, adt_fill)
    static = {(r[0], r[1]): dict(zip(panel.STATIC_COLUMNS[2:], r[2:]))
              for r in (meta.get("static_attrs") or {}).get("rows", [])}
    X, y, years, keys, _ksi = panel.matrix(cols, rows, static)
    site = str(site or "").strip()
    if view == "markdown":                       # P9: the one-sentence prediction card ("predict for THIS place")
        return _prediction_card(ctx, meta, raw, X, y, years, keys, site)
    if site:
        spec, png = _site_faces(ctx, meta, raw, X, y, years, keys, site, sql, view)
    else:
        spec, png = _global_faces(meta, raw, X, sql, view, style)
    if png is not None:
        spec["png_base64"] = png
        spec["renderer"] = "png"                 # make_spec derives the renderer at build time — keep them in step
    return dispatch(view, spec, TITLE)


def _prediction_card(ctx, meta, raw, X, y, years, keys, site):
    """A markdown card that says the prediction out loud: what the model forecasts for one segment, the
    interval, what actually happened, and the top drivers in words."""
    g = (meta.get("gate") or {}).get("metrics", {})
    alpha = float(meta.get("alpha") or 0.0)
    if not site:
        phi = model.contribs(raw, X)
        _enforce_identity(phi, model.predict(raw, X), meta)
        order = explain.top_k(explain.mean_abs_phi(phi), k=3)
        drivers = " · ".join(constants.FEATURE_LABELS_HE[constants.FEATURES[j]] for j in order)
        body = [
            "# מה מזין את תחזיות המודל",
            f"- שלושת המאפיינים המשפיעים ביותר (ממוצע |φ| על הלוח המלא): {drivers}",
            f"- מודל {meta['model_id']} · Spearman {g.get('spearman')} · כיול {g.get('calibration')}",
            "- לתחזית של מקטע מסוים: מלאו site (למשל 60/850)",
        ]
        return markdown_answer(TITLE, body, denom=DENOM_NA, caveats=_model_caveats(meta))
    key = explain.resolve_site(ctx, site)
    idx = sorted((i for i, k in enumerate(keys) if k == key), key=lambda i: years[i])
    if not idx:
        raise Refusal(f"המקטע {key[0]}/{key[1]} אינו בלוח המודל (מקטעים לא-עירוניים עם שכבת תנועה בלבד)",
                      ["site_ranking לרשימת המקטעים", "hotspot_map לספירות"])
    Xs = [X[i] for i in idx]
    mu = model.predict(raw, Xs)
    phi = model.contribs(raw, Xs)
    _enforce_identity(phi, mu, meta)
    obs_total, mu_total = sum(y[i] for i in idx), float(sum(mu))
    lo, hi = gate.nb_interval(list(mu), alpha)
    order = explain.top_k(explain.mean_abs_phi(phi), k=3)
    drivers = " · ".join(constants.FEATURE_LABELS_HE[constants.FEATURES[j]] for j in order)
    verdict = ("מעל רווח התחזית — חריג לרעה" if obs_total > hi
               else "מתחת לרווח התחזית — טוב מהצפוי" if obs_total < lo else "בתוך רווח התחזית")
    span = f"{_LRM}{years[idx[0]]}–{years[idx[-1]]}{_LRM}"
    body = [
        f"# תחזית המודל לאתר {key[0]}/{key[1]}",
        f"- המודל חוזה {mu_total:.1f} תאונות עם נפגעים בשנים {span} (רווח ~90%: {_LRM}{lo:.0f}–{hi:.0f}{_LRM})",
        f"- בפועל: {obs_total} — עודף {_LRM}{obs_total - mu_total:+.1f}{_LRM} · {verdict}",
        f"- מה מזין את התחזית כאן: {drivers} (לפי ממוצע |φ|)",
        f"- איכות המודל בשער: Spearman {g.get('spearman')} · כיול {g.get('calibration')}",
        "- הפירוק המלא לפי שנים: view = chart",
    ]
    denom = denominator("exposure", f"תחזית מודל אתר {meta['model_id']} (היסטוריה, מאפייני מקטע ו-ADT as-of)",
                        model_id=meta["model_id"])
    return markdown_answer(TITLE, body, denom=denom, caveats=_model_caveats(meta))


def _resolve_model(ctx, model_id):
    s = str(model_id or "").strip()
    if s in ("", "deployed"):
        pointer, meta = registry.deployed(ctx)
        if pointer is None:
            raise Refusal("אין מודל אתר פרוס — ההסבר רץ על מודל מהרישום",
                          ["סטודיו: studio_train_site ואז studio_validate ואז studio_deploy",
                           "או model_id מפורש מתוך studio_models"])
        if meta is None:
            raise Refusal("deployed.json מצביע על מודל חסר או בלתי קריא — יש לפרוס מחדש",
                          ["studio_models", "studio_deploy"])
        return meta
    meta, ids = registry.resolve_id(ctx, s)
    if meta is None or meta.get("status") == "unreadable":
        raise Refusal(f"לא נמצא מודל קריא בשם '{s}'",
                      [("מזהים קיימים: " + " · ".join(ids[-5:])) if ids else "הרישום ריק — studio_train_site"])
    return meta


def _model_caveats(meta):
    g = (meta.get("gate") or {}).get("metrics", {})
    status = meta.get("status")
    lines = [
        "ערכי φ (SHAP) חיים על סקלת הלוג של הקצב — סכומם לשורה הוא לוגריתם הצפי, לא תאונות",
        "מתאם ולא סיבתיות · מאפיינים מתואמים (נפח תנועה ושנה קודמת) נקראים כקבוצה",
        f"מודל {meta['model_id']}: train_until {meta['panel']['train_until']}, Spearman {g.get('spearman')}, "
        f"כיול {g.get('calibration')}",
    ]
    if status != "deployed":
        lines.append(f"המודל המוסבר אינו המודל הפרוס (סטטוס: {status}) — אבחון, לא כלי דירוג")
    return lines


def _site_faces(ctx, meta, raw, X, y, years, keys, site, sql, view):
    key = explain.resolve_site(ctx, site)
    idx = [i for i, k in enumerate(keys) if k == key]
    if not idx:
        raise Refusal(f"המקטע {key[0]}/{key[1]} אינו בלוח המודל (מקטעים לא-עירוניים עם שכבת תנועה בלבד)",
                      ["site_ranking לרשימת המקטעים", "hotspot_map לספירות"])
    idx.sort(key=lambda i: years[i])
    Xs = [X[i] for i in idx]
    ys_year = [years[i] for i in idx]
    obs = [y[i] for i in idx]
    mu = model.predict(raw, Xs)
    phi = model.contribs(raw, Xs)
    _enforce_identity(phi, mu, meta)
    top = explain.top_k(explain.mean_abs_phi(phi))
    feats = [constants.FEATURES[j] for j in top]
    cols = SITE_COLS + [f"phi_{f}" for f in feats] + ["phi_bias"]
    rows = [[ys_year[i], obs[i], round(mu[i], 2)] + [round(phi[i][j], 4) for j in top] + [round(phi[i][-1], 4)]
            for i in range(len(idx))]
    caveats = _model_caveats(meta) + [
        f"חמשת המאפיינים המובילים לפי ממוצע |φ| על שנות המקטע — {len(constants.FEATURES)} מאפיינים במודל",
    ]
    denom = denominator("exposure", f"ציפייה מודלית ממודל אתר {meta['model_id']} — ההסבר מפרק את לוג הצפי",
                        model_id=meta["model_id"])
    stamp_text = stamp("studio_explain", f"{key[0]}/{key[1]}", meta["model_id"][:40])
    basis = (f"studio_explain | site {key[0]}/{key[1]} | model {meta['model_id']} | years {ys_year[0]}-{ys_year[-1]}"
             f" | top {len(feats)} of {len(constants.FEATURES)}")
    spec = make_spec("accidents/studio_explain", basis=basis, rows=rows, columns=cols, sql=sql,
                     denominator=denom, caveats=caveats, model_id=meta["model_id"], site=f"{key[0]}/{key[1]}",
                     features=feats, stamp=stamp_text, y="mu")
    png = None
    if view == "chart":
        from .. import charts
        series = [(constants.FEATURE_LABELS_HE[f], [phi[i][j] for i in range(len(idx))])
                  for f, j in zip(feats, top)]
        png = charts.explain_png(
            ys_year, series, obs, mu,
            ylabel_phi="תרומת φ ללוג הצפי", ylabel_right="תאונות עם נפגעים",
            title=f"הסבר המודל למקטע {key[0]}/{key[1]} · נצפה מול צפוי",
            badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
    return spec, png


def _enforce_identity(phi, mu, meta):
    worst = explain.check_identity(phi, mu)
    if worst > explain.IDENTITY_TOL:
        raise ActionError(f"SHAP identity violated for {meta['model_id']}: max |sum(phi) - ln(mu)| = {worst:.4g} "
                          f"> {explain.IDENTITY_TOL} - the artifact does not match this xgboost build, retrain")


def _global_faces(meta, raw, X, sql, view, style="פרופיל"):
    phi = model.contribs(raw, X)
    _enforce_identity(phi, model.predict(raw, X), meta)
    imp = explain.mean_abs_phi(phi)
    signed = explain.mean_phi(phi)
    order = explain.top_k(imp, k=len(constants.FEATURES))
    rows = [[constants.FEATURES[j], constants.FEATURE_LABELS_HE[constants.FEATURES[j]],
             round(imp[j], 4), round(signed[j], 4)] for j in order]
    caveats = _model_caveats(meta) + [
        f"פרופיל גלובלי: ממוצע |φ| על {len(X):,} שורות הלוח המלא — חשיבות, לא כיוון",
    ]
    swarm = None
    if view == "chart" and style == "נחיל":              # P12: the beeswarm style, this face only
        from ..studio import explain_severity
        phi_no_bias = [row[:len(constants.FEATURES)] for row in phi]
        sw_order, _sw_imp, dots = explain_severity.build_swarm(
            phi_no_bias, X, constants.FEATURES, set(constants.FEATURES),
            constants.FEATURE_LABELS_HE, {})             # ALL site features are ordered -> full coloring is honest
        row_labels = [constants.FEATURE_LABELS_HE[constants.FEATURES[j]] for j in sw_order]
        swarm = {"features": row_labels, "ordered": [True] * len(sw_order), **dots}
        caveats.append("צבע ערך מלא — כל מאפייני מודל האתר סדורים (שיעורים, נפחים, שנים)")
    stamp_text = stamp("studio_explain", "global", meta["model_id"][:40])
    basis = f"studio_explain | global | model {meta['model_id']} | rows {len(X)} | features {len(constants.FEATURES)}"
    spec = make_spec("accidents/studio_explain", basis=basis, rows=rows, columns=GLOBAL_COLS, sql=sql,
                     denominator=DENOM_NA, caveats=caveats, model_id=meta["model_id"], site="",
                     stamp=stamp_text, y="mean_abs_phi",
                     chip="מה מזין את תחזיות המודל — חשיבות מאפיינים")  # no observed side on this face (P9 sweep)
    png = None
    if view == "chart":
        from .. import charts
        if swarm is not None:
            spec["swarm"] = swarm
            spec["style"] = "נחיל"
            png = charts.beeswarm(
                row_labels, dots, xlabel="תרומת φ ללוג הצפי",
                ordered_rows=[True] * len(sw_order), colorbar_label="ערך המאפיין (מנורמל)",
                title="נחיל SHAP של מודל האתר — הלוח המלא",
                badge=f"מכנה: {DENOM_NA['label']}", caveats=caveats, stamp=stamp_text)
        else:
            k = constants.EXPLAIN_TOP_K
            png = charts.hbars(
                [r[1] for r in rows[:k]], [r[2] for r in rows[:k]],
                xlabel="ממוצע |φ| על הלוח המלא (סקלת לוג)",
                annot=[f"{r[3]:+.3f}" for r in rows[:k]],
                title="פרופיל חשיבות גלובלי של מודל האתר",
                badge=f"מכנה: {DENOM_NA['label']}", caveats=caveats, stamp=stamp_text)
    return spec, png


ACTION = Action(
    name="studio_explain", label="תחזית והסבר לאתר · studio_explain",
    help="TreeSHAP over the site model (pred_contribs): per-site profile = the top-5 features' phi per year on "
         "the log-rate scale next to observed-vs-predicted; empty site = the global mean|phi| importance profile. "
         "phi rows sum exactly to ln(mu). Accepts '60/836' (road/seg) or a road:<n>/<km>-<km> site key. "
         "Needs the [ml] extra.",
    inputs={
        "site": Input(kind="text", label="מקטע", default="",
                      help="empty = global profile; '60/836' (road/seg) or a site_key from site_ranking"),
        "model_id": Input(kind="text", label="מזהה מודל", default="deployed",
                          help="'deployed' (default) or an explicit id from studio_models"),
        "style": Input(kind="choice", label="סגנון", default="פרופיל", choices=["פרופיל", "נחיל"],
                       help="profile bars (default) or a SHAP beeswarm over the full panel rows; "
                            "applies to the global face only"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
