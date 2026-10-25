# -*- coding: utf-8 -*-
"""site_profile (P10 — the מפה חיה click panel): ONE site, everything that can honestly be said about it.
Every site kind gets the observed strip (yearly counts, severity split, day/night, geocoding). Model measures
are STRUCTURAL, not policy: the site-model block is reachable only for road-segment keys — junctions have no
exposure denominator, so they never carry μ, excess, EB or any rate, and the standing caveat says so. The
severity block (all kinds) is conditional-only and leaves the family RELATIVE: the deployed severity model's
mean prediction over the site's own person rows against the holdout baseline. A missing prerequisite (no
deployment, era, panel membership, missing [ml], contract drift) degrades to an ABSENT section plus one
caveat — never a refusal; refusals are for a malformed/unknown key or an empty legal range."""
from __future__ import annotations

import re

from nl2sql_engine.modules import Action, Input

from ..envelope import (CAVEAT_COUNTS_NOT_RISK, denominator, dispatch, guard, make_spec, markdown_answer,
                        stamp, view_input)
from ..sqlkit import (DATA_YEARS, EXPOSURE_YEARS, ActionError, Refusal, SITE_FORMS, Site, as_choice,
                      parse_site_key, road_seg_km_sql, rows_safe, site_label_sql, site_predicate,
                      site_profile_strip_sql, year_range)
from ..studio import severity as _severity

VIEWS = ("chart", "markdown", "table", "sql")
TITLE = "פרופיל אתר"
_LRM = chr(0x200E)                             # pins tight digit ranges on the browser-rendered card (P8/P9)
_ROAD_SEG = re.compile(r"^(\d+)/(\d+)$")
STRIP_COLS = ["year", "accidents", "ksi_accidents", "fatal", "severe", "slight", "geocoded", "night", "day"]
JUNCTION_RULE = ("צמתים מדורגים לפי ספירות בלבד — אין נפח תנועה לצמתים: אין excess, אין שיעור "
                 "ואין מדדי מודל אתר")
# Live lesson (P10): a road: key's km range comes from the LATEST traffic_segments vintage — earlier vintages
# can be much wider (70/120 spans 66.2-78.7 in every vintage but 2024's 66.2-67.4), so the strip's literal-km
# counts and the model/hotspot per-year assignment counts are DIFFERENT instruments. Said out loud, always.
ROAD_STRIP_RULE = ("ספירות הרצועה נמנות לפי טווח הק״מ המילולי של המפתח — כמו before_after · "
                   "הקצאת המקטעים של המודל ושל hotspot_map נמנית לפי גיאומטריה לשנה ועשויה להיבדל")


@guard(TITLE)
def run(ctx, site="60/836", from_year=2008, to_year=2024, view="chart"):
    view = as_choice(view, "view", VIEWS)
    y0, y1 = year_range(from_year, to_year)
    s = _resolve_site(ctx, site)
    label = _label_of(ctx, s)
    sql = site_profile_strip_sql(s, y0, y1)
    cols, raw = ctx.query(sql)
    strip = rows_safe(raw)
    if not strip:
        raise Refusal(f"לא נמצאו תאונות עם נפגעים באתר {_LRM}{s.key}{_LRM} בשנים {y0}-{y1}",
                      [f"טווח שנים אחר בין {DATA_YEARS[0]} ל-{DATA_YEARS[1]}",
                       "hotspot_map או מפה חיה לאיתור אתרים פעילים", "site_ranking לדירוג המודל"])
    ci = {c: i for i, c in enumerate(cols)}
    by_year = {int(r[ci["year"]]): r for r in strip}
    years = list(range(y0, y1 + 1))

    def col(name):                               # zero-filled: a year with no accidents at the site IS a zero
        return [int(by_year[y][ci[name]]) if y in by_year else 0 for y in years]

    acc, ksi = col("accidents"), col("ksi_accidents")
    totals = {name: sum(col(name)) for name in ("accidents", "ksi_accidents", "fatal", "severe", "slight",
                                                "geocoded", "night", "day")}
    lat, lon = _mean_coord(strip, ci)

    model_block, mu_map, model_cavs = _model_block(ctx, s, y0, y1)
    sev_block, sev_cavs = _severity_block(ctx, s, y0, y1)
    caveats = (list(model_cavs) + ([ROAD_STRIP_RULE] if s.kind == "road" else [JUNCTION_RULE])
               + list(sev_cavs))
    without = totals["accidents"] - totals["geocoded"]
    if without:
        caveats.append(f"{without:,} מתוך {totals['accidents']:,} תאונות האתר ללא קואורדינטות — נספרות, לא ממוקמות")
    if model_block is None:
        caveats.append(CAVEAT_COUNTS_NOT_RISK)

    rows = [[y, *(col(n)[i] for n in STRIP_COLS[1:])] for i, y in enumerate(years)]
    columns = list(STRIP_COLS)
    mu_line = None
    if model_block is not None:
        mu_line = [mu_map.get(y) for y in years]
        rows = [r + [mu_line[i]] for i, r in enumerate(rows)]
        columns = columns + ["mu"]
        denom = denominator("exposure",
                            f"ציפייה מודלית ממודל אתר פרוס {model_block['model_id']} · excess = נצפה − צפוי",
                            model_id=model_block["model_id"])
        chip_model_id, chip = model_block["model_id"], "תחזית מול נצפה לאתר"
    elif sev_block is not None:
        denom = denominator("counts", "ספירות תאונות עם נפגעים באתר — ללא מכנה חשיפה")
        chip_model_id, chip = sev_block["model_id"], "פרופיל חומרה מותנה — יחסי בלבד"
    else:
        denom = denominator("counts", "ספירות תאונות עם נפגעים באתר — ללא מכנה חשיפה")
        chip_model_id, chip = None, None

    stamp_text = stamp("site_profile", s.key, f"{y0}-{y1}")
    basis = (f"site_profile | {s.key} | {y0}-{y1} | accidents {totals['accidents']} | ksi {totals['ksi_accidents']}"
             + (f" | model {model_block['model_id']}" if model_block else " | counts-only")
             + (f" | severity {sev_block['model_id']} n={sev_block['n_persons']}" if sev_block else ""))
    png = None
    if view == "chart":
        from .. import charts
        png = charts.site_card_png(years, acc, ksi, mu_line,
                                   title=f"{TITLE} · {label}", badge=f"מכנה: {denom['label']}",
                                   caveats=caveats, stamp=stamp_text)
    spec = make_spec("accidents/site_profile", png_base64=png, basis=basis, rows=rows, columns=columns,
                     sql=sql, denominator=denom, caveats=caveats,
                     **({"model_id": chip_model_id, "chip": chip} if chip_model_id else {}),
                     site={"key": s.key, "kind": s.kind, "label": label, "lat": lat, "lon": lon},
                     site_key=s.key, splits=totals,
                     **({"model": model_block} if model_block else {}),
                     **({"severity_rel": sev_block} if sev_block else {}),
                     stamp=stamp_text, x="year", y="accidents")
    if view == "markdown":
        return markdown_answer(TITLE, _card_body(s, label, y0, y1, totals, model_block, sev_block),
                               denom=denom, caveats=caveats)
    return dispatch(view, spec, TITLE)


def _resolve_site(ctx, site) -> Site:
    """The three site-key forms, or a bare 'road/seg' resolved through the latest traffic_segments vintage
    (the same rule as the hotspot site keys). Unknown (road, seg) → refusal (a data question, not a typo)."""
    s = str(site or "").strip()
    m = _ROAD_SEG.match(s)
    if not m:
        return parse_site_key(s)
    road, seg = int(m.group(1)), int(m.group(2))
    rows = rows_safe(ctx.query(road_seg_km_sql(road, seg))[1])
    if not rows:
        raise Refusal(f"המקטע {_LRM}{road}/{seg}{_LRM} אינו מוכר — אין לו שורת traffic_segments",
                      ["site_ranking לרשימת המקטעים", f"או מפתח אתר מלא: {SITE_FORMS}"])
    km0, km1 = float(rows[0][0]), float(rows[0][1])
    return parse_site_key(f"road:{road}/{km0:g}-{km1:g}")


def _label_of(ctx, s: Site) -> str:
    rows = rows_safe(ctx.query(site_label_sql(s))[1])
    if s.kind == "road":
        base = f"כביש {s.road} · ק״מ {s.km_from:g}-{s.km_to:g}"
        if rows and (rows[0][0] or rows[0][1]):
            base += f" · {rows[0][0] or ''} ← {rows[0][1] or ''}"        # ← points at name_to in an RTL line
        return base
    if s.kind == "njunction":
        name = rows[0][0] if rows and rows[0][0] else None
        return f"צומת {s.code}" + (f" · {name}" if name else "")
    if rows:
        city, s1, s2 = rows[0][0] or "", rows[0][1] or "", rows[0][2] or ""
        return f"{city} · {s1} / {s2} (צומת {s.code})"
    return f"צומת עירוני {s.city}/{s.code}"


def _mean_coord(strip, ci):
    pairs = [(float(r[ci["lat"]]), float(r[ci["lon"]]), int(r[ci["geocoded"]]))
             for r in strip if r[ci["lat"]] is not None and r[ci["lon"]] is not None and int(r[ci["geocoded"]])]
    w = sum(g for _, _, g in pairs)
    if not w:
        return None, None
    return (round(sum(la * g for la, _, g in pairs) / w, 5),
            round(sum(lo * g for _, lo, g in pairs) / w, 5))


def _clean(text) -> str:
    """One caveat-safe sentence out of an exception text (no ';', bounded)."""
    return str(text).replace(";", " ·").replace("\n", " ")[:200]


def _model_block(ctx, s: Site, y0: int, y1: int):
    """(block dict | None, {year: μ} | None, caveats). Reachable ONLY for road keys — the golden rule is
    structure, not policy. Every missing prerequisite degrades to (None, None, [why])."""
    if s.kind != "road":
        return None, None, []
    from ..studio import explain, model as _model, predict, registry
    try:
        key = explain.resolve_site(ctx, s.key)
    except (Refusal, ActionError) as r:
        return None, None, [f"מדדי המודל אינם מוצגים: {_clean(getattr(r, 'reason', r))}"]
    pointer, meta = registry.deployed(ctx)
    if pointer is None:
        return None, None, ["אין מודל אתר פרוס — מדדי המודל אינם מוצגים (סטודיו: אימון, אימות, פריסה)"]
    if meta is None:
        return None, None, ["deployed.json מצביע על מודל חסר או בלתי קריא — מדדי המודל אינם מוצגים"]
    if y1 < EXPOSURE_YEARS[0]:
        return None, None, [f"excess קיים מ-{EXPOSURE_YEARS[0]} (עידן החשיפה) — הטווח כולו לפניו, מדדי המודל אינם מוצגים"]
    y0e = max(y0, EXPOSURE_YEARS[0])
    try:
        _model.require_xgboost()
        exp, _panel_sql = predict.expected_by_segment(ctx, meta, y0e, y1, key[0])
        e = exp.get(key)
        if e is None:
            return None, None, [f"המקטע {key[0]}/{key[1]} אינו בלוח המודל בשנים {y0e}-{y1} — מדדי המודל אינם מוצגים"]
        drivers, mu_map = _drivers_and_mu(ctx, meta, key, y0e, y1)
        g = (meta.get("gate") or {}).get("metrics", {})
        block = {"model_id": meta["model_id"], "from_year": y0e, "to_year": y1,
                 "observed": e["observed"], "ksi": e["ksi"], "mu": e["mu"], "excess": e["excess"],
                 "eb": e["eb"], "lo90": e["lo90"], "hi90": e["hi90"], "significant": e["significant"],
                 "years_known": e["years_known"], "verdict": _verdict(e),
                 "drivers": drivers, "gate": {"spearman": g.get("spearman"), "calibration": g.get("calibration")},
                 "alpha": float(meta.get("alpha") or 0.0), "train_until": meta["panel"]["train_until"],
                 "segment": {"road": key[0], "seg": key[1]}}
        cavs = [f"excess = נצפה − צפוי · EB ורווח מקירוב נורמלי ל-NB · מודל {meta['model_id']}: "
                f"train_until {meta['panel']['train_until']}, Spearman {g.get('spearman')}, "
                f"כיול {g.get('calibration')} · מתאם ולא סיבתיות"]
        if y0e != y0:
            cavs.insert(0, f"מדדי המודל מחושבים על {y0e}-{y1} (עידן החשיפה) — הספירות על מלוא הטווח")
        return block, mu_map, cavs
    except Refusal as r:
        return None, None, [f"מדדי המודל אינם מוצגים: {_clean(r.reason)}"]
    except ActionError as err:
        return None, None, [f"מדדי המודל אינם מוצגים: {_clean(err)}"]


def _verdict(e) -> str:
    if e["observed"] > e["hi90"]:
        return "מעל רווח התחזית — חריג לרעה"
    if e["observed"] < e["lo90"]:
        return "מתחת לרווח התחזית — טוב מהצפוי"
    return "בתוך רווח התחזית"


def _drivers_and_mu(ctx, meta, key, y0e, y1):
    """Top-3 TreeSHAP drivers over THIS segment's panel rows in the window, plus {year: μ} for the strip line.
    The Σφ = ln μ identity is enforced — a foreign/corrupt artifact must fail the whole model block loudly."""
    from ..studio import constants, explain, model as _model, panel, registry
    raw = registry.model_bytes(ctx, meta["model_id"])
    if raw is None:
        raise Refusal("קובץ המודל הפרוס חסר מהרישום — יש לאמן ולפרוס מחדש", ["studio_models"])
    py0, py1 = meta["panel"]["years"]
    cols, rows = panel.fetch_panel(ctx, py0, py1, float(meta["adt_fill"]["value"]))
    static = {(r[0], r[1]): dict(zip(panel.STATIC_COLUMNS[2:], r[2:]))
              for r in (meta.get("static_attrs") or {}).get("rows", [])}
    X, _y, yrs, keys, _ksi = panel.matrix(cols, rows, static)
    idx = sorted((i for i, k in enumerate(keys) if k == key and y0e <= yrs[i] <= y1), key=lambda i: yrs[i])
    if not idx:
        raise Refusal(f"המקטע {key[0]}/{key[1]} אינו בלוח המודל בשנים {y0e}-{y1}", ["site_ranking"])
    Xs = [X[i] for i in idx]
    mu = _model.predict(raw, Xs)
    phi = _model.contribs(raw, Xs)
    worst = explain.check_identity(phi, mu)
    if worst > explain.IDENTITY_TOL:
        raise ActionError(f"SHAP identity violated for {meta['model_id']}: max |sum(phi) - ln(mu)| = "
                          f"{worst:.4g} > {explain.IDENTITY_TOL} - the artifact does not match this xgboost "
                          f"build, retrain")
    order = explain.top_k(explain.mean_abs_phi(phi), k=3)
    drivers = [{"feature": constants.FEATURES[j], "label": constants.FEATURE_LABELS_HE[constants.FEATURES[j]]}
               for j in order]
    mu_map = {int(yrs[i]): round(float(m), 3) for i, m in zip(idx, mu)}
    return drivers, mu_map


def _severity_block(ctx, s: Site, y0: int, y1: int):
    """(block dict | None, caveats). Conditional severity over the site's OWN person rows — relative reading
    only, every site kind. Any missing prerequisite degrades to (None, [why])."""
    if y1 < _severity.ERA[0]:
        return None, [f"פרופיל החומרה המותנה מחושב מ-{_severity.ERA[0]} — הטווח כולו לפניו"]
    from .severity_predict import deployed_severity
    try:
        meta, raw = deployed_severity(ctx)
    except Refusal as r:
        return None, [f"פרופיל החומרה המותנה אינו מוצג: {_clean(r.reason)}"]
    y0s = max(y0, _severity.ERA[0])
    baseline = meta.get("class_shares_holdout") or meta.get("class_shares_train")
    if not baseline:                                     # sweep L9: a meta missing both share keys must degrade
        return None, ["פרופיל החומרה המותנה אינו מוצג: למטא של המודל הפרוס חסר בסיס שיעורי החומרה"]
    sql = _severity.matrix_sql(y0s, y1, site_predicate(s))
    try:
        X, yv, _yrs = _severity.fetch_matrix(ctx, y0s, y1, site_predicate(s))
        n = len(X)
        if n == 0:
            return None, [f"אין נפגעים באתר בעידן מודל החומרה ({y0s}-{y1}) — הפרופיל המותנה אינו מוצג"]
        probs = _severity.predict_proba(raw, X)
    except Refusal as r:
        return None, [f"פרופיל החומרה המותנה אינו מוצג: {_clean(r.reason)}"]
    except ActionError as err:
        return None, [f"פרופיל החומרה המותנה אינו מוצג: {_clean(err)}"]
    mean_p = [sum(p[c] for p in probs) / n for c in range(3)]
    rel = _severity.relative(mean_p, [float(b) for b in baseline])
    emp = [sum(1 for v in yv if v == c) / n for c in range(3)]
    g = (meta.get("gate") or {}).get("metrics", {})
    block = {"model_id": meta["model_id"], "n_persons": n, "from_year": y0s, "to_year": y1,
             "labels": [_severity.CLASS_LABELS_HE[c] for c in range(3)],
             "mean_p": [round(v, 4) for v in mean_p], "baseline": [round(float(b), 4) for b in baseline],
             "relative": [round(v, 2) for v in rel], "empirical": [round(v, 4) for v in emp], "sql": sql}
    cavs = [
        "הסתברויות יחסיות בלבד — המודל מדרג פרופילי סיכון, אינו חוזה גורל של אדם",
        f"פרופיל מותנה: ממוצע תחזיות על {n:,} נפגעי האתר עצמם ({y0s}-{y1}) מול בסיס שנות האימות — "
        f"מודל {meta['model_id']}: רגישות להרוגים {g.get('fatal_recall')} · AUC {g.get('auc_fatal')}",
    ]
    return block, cavs


def _card_body(s: Site, label, y0, y1, totals, model_block, sev_block) -> list[str]:
    span = f"{_LRM}{y0}-{y1}{_LRM}"
    known = totals["night"] + totals["day"]
    night_pct = round(100.0 * totals["night"] / known, 1) if known else None
    body = [
        f"# {label}",
        f"- מפתח האתר: {_LRM}{s.key}{_LRM}",
        f"- בשנים {span}: {totals['accidents']:,} תאונות עם נפגעים — {totals['fatal']:,} קטלניות · "
        f"{totals['severe']:,} קשות · {totals['slight']:,} קלות",
    ]
    if night_pct is not None:
        body.append(f"- לילה: {night_pct}% מהתאונות המקודדות ליום/לילה")
    if model_block:
        mb = model_block
        mspan = f"{_LRM}{mb['from_year']}-{mb['to_year']}{_LRM}"
        interval = f"{_LRM}{mb['lo90']:.0f}-{mb['hi90']:.0f}{_LRM}"
        body.append(f"- המודל חוזה {mb['mu']:.1f} תאונות בשנים {mspan} (רווח ~90%: {interval}) · "
                    f"בפועל {mb['observed']} · עודף {_LRM}{mb['excess']:+.1f}{_LRM} · {mb['verdict']}")
        if mb["drivers"]:
            body.append("- מה מזין את התחזית כאן: " + " · ".join(d["label"] for d in mb["drivers"]))
    if sev_block:
        rel = sev_block["relative"]
        labels = sev_block["labels"]
        body.append(f"- פרופיל חומרה מותנה ({sev_block['n_persons']:,} נפגעים): "
                    + " · ".join(f"{labels[c]} פי {rel[c]:.2f}" for c in range(3)) + " — יחסית לבסיס")
    body.append(f"- המשך: before_after עם site = {_LRM}{s.key}{_LRM}")
    return body


# Declared LAST (Action.run is evaluated at import).
ACTION = Action(
    name="site_profile", label="פרופיל אתר · site_profile",
    help="One site, everything that can honestly be said: the yearly observed strip (counts, severity split, "
         "day/night) for every site kind; model measures (mu, excess, EB, interval, TreeSHAP drivers) for road "
         "segments ONLY - junctions have no exposure denominator and never carry rates; a conditional severity "
         "profile (relative only) over the site's own person rows when a severity model is deployed. Missing "
         "prerequisites degrade to absent sections with a caveat, never a refusal. Accepts road:<n>/<a>-<b>, "
         "njunction:<code>, ujunction:<city>/<code> or bare road/seg like 60/836.",
    inputs={
        "site": Input(kind="text", label="אתר", default="60/836",
                      help="road:<n>/<km_from>-<km_to> | njunction:<code> | ujunction:<city_code>/<code> | "
                           "bare road/seg like 60/836 (resolved via the latest traffic_segments vintage)"),
        "from_year": Input(kind="number", label="שנת התחלה", default=2008,
                           help=f"{DATA_YEARS[0]}-{DATA_YEARS[1]}"),
        "to_year": Input(kind="number", label="שנת סיום", default=2024, help="data ends 2024-12-31"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
