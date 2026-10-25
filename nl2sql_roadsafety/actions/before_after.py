# -*- coding: utf-8 -*-
"""before_after (use ה): Double difference-in-differences for one site — the casualty series and the
damage-only series, each against the whole national network; the double ratio removes what traffic
explains. Thin cells give n/a: an empty answer beats a fake number."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, dispatch, guard, make_spec, stamp, view_input
from ..sqlkit import (CONTROL_FLAG_REL, DATA_YEARS, MIN_CELL_DEFAULT, ActionError, Refusal, as_choice, as_int,
                      build_before_after_sql, control_flag, did_math, double_did, parse_site_key, rows_safe,
                      site_label_sql)

VIEWS = ("chart", "table", "sql")
SERIES_HE = {1: "נפגעים", 3: "נזק בלבד"}


def _r4(x):
    return None if x is None else round(x, 4)


@guard("לפני ואחרי · יחס כפול")
def run(ctx, site="road:60/96.0-98.8", change_year=2017, window_years=3, min_cell=MIN_CELL_DEFAULT, view="chart"):
    view = as_choice(view, "view", VIEWS)
    st = parse_site_key(site)
    cy = as_int(change_year, "change_year")
    w = as_int(window_years, "window_years")
    if not 1 <= w <= 3:
        raise ActionError(f"window_years must be 1, 2 or 3; got {w}.")
    mc = as_int(min_cell, "min_cell")
    if mc < 1:
        raise ActionError(f"min_cell must be at least 1; got {mc}.")
    lo, hi = DATA_YEARS
    if cy - w < lo or cy + w > hi:
        raise Refusal(f"החלון {cy - w}–{cy + w} חורג מהנתונים ({lo}–{hi})",
                      [f"שנת שינוי בין {lo + w} ל-{hi - w} בחלון של {w} שנים"])
    sql = build_before_after_sql(st, cy, w)
    columns, raw = ctx.query(sql)
    rows = rows_safe(raw)
    cell = {(int(r[0]), r[1]): r for r in rows}

    def counts(series):
        b = cell.get((series, "before"), [series, "before", 0, 0, 0, 0])
        a = cell.get((series, "after"), [series, "after", 0, 0, 0, 0])
        return b[2], a[2], b[3], a[3], (b[4], b[5]), (a[4], a[5])

    sb, sa, nb, na, cb, ca = counts(1)
    db, da, ndb, nda, dcb, dca = counts(3)
    if sb + sa + db + da == 0:
        raise Refusal("לא נמצאו תאונות באתר בחלונות שנבחרו", ["בדקו את מפתח האתר", "מקטעים עם תאונות: segment_rates"],
                      detail=f"site {st.key}, windows {cy - w}-{cy - 1} / {cy + 1}-{cy + w}")
    cas = did_math(sb, sa, nb, na, mc)
    dmg = did_math(db, da, ndb, nda, mc)
    dbl = double_did(cas, dmg)
    share_b = (dcb[0] / dcb[1]) if dcb[1] else None
    share_a = (dca[0] / dca[1]) if dca[1] else None
    flagged = control_flag(share_b, share_a)
    label = _site_label(ctx, st)
    caveats = _caveats(st, cy, w, mc, cas, dmg, share_b, share_a, flagged)
    out_rows = [
        ["casualty", sb, sa, _r4(sa / sb) if sb else None, nb, na, _r4(na / nb) if nb else None,
         _r4(cas["ratio"]), _r4(cas["lo"]), _r4(cas["hi"]), cas["status"]],
        ["damage_only", db, da, _r4(da / db) if db else None, ndb, nda, _r4(nda / ndb) if ndb else None,
         _r4(dmg["ratio"]), _r4(dmg["lo"]), _r4(dmg["hi"]), dmg["status"]],
        ["double", None, None, None, None, None, None, _r4(dbl["ratio"]), _r4(dbl["lo"]), _r4(dbl["hi"]), dbl["status"]],
    ]
    out_cols = ["series", "site_before", "site_after", "site_ratio", "network_before", "network_after",
                "network_ratio", "ratio", "ci_lo", "ci_hi", "status"]
    denom = denominator("exposure", "פרוקסי לחשיפה: סדרת הנזק-בלבד (case_type_code = 3) · קבוצת השוואה: כל הרשת הארצית")
    stamp_text = stamp("before_after", st.key, f"{cy} w{w}")            # short: it shares the footer with the credit
    headline = (f"יחס כפול {dbl['ratio']:.3f} ({dbl['lo']:.3f}–{dbl['hi']:.3f})" if dbl["status"] == "ok"
                else "יחס כפול: n/a")
    png = None
    if view == "chart":
        from .. import charts

        def panel(title, b, a, n_b, n_a, d):
            t = f"{title} · DiD {d['ratio']:.3f} ({d['lo']:.3f}–{d['hi']:.3f})" if d["status"] == "ok" else f"{title} · DiD n/a"
            return {"title": t, "site_before": b, "site_after": a, "net_before": n_b, "net_after": n_a}

        png = charts.before_after_bars([panel("נפגעים", sb, sa, nb, na, cas), panel("נזק בלבד", db, da, ndb, nda, dmg)],
                                       headline=headline, title=f"לפני ואחרי · {label} · שינוי {cy} · חלון {w}+{w}",
                                       badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)

    def fmt(d):
        return f"{d['ratio']:.4f} ({d['lo']:.4f}-{d['hi']:.4f})" if d["status"] == "ok" else "n/a"

    basis = (f"before_after | site={st.key} | change {cy} | window {w}+{w} | min_cell {mc} | control=network | "
             f"casualty {sb}->{sa} vs {nb}->{na} = {fmt(cas)} | damage {db}->{da} vs {ndb}->{nda} = {fmt(dmg)} | "
             f"double {fmt(dbl)}")
    spec = make_spec("accidents/before_after", png_base64=png, basis=basis, rows=out_rows, columns=out_cols, sql=sql,
                     denominator=denom, caveats=caveats, site_key=st.key, site_kind=st.kind, site_label=label,
                     change_year=cy, window_years=w, min_cell=mc, stamp=stamp_text,
                     counts={"casualty": [sb, sa, nb, na], "damage_only": [db, da, ndb, nda]},
                     coding_share={"before": _r4(share_b), "after": _r4(share_a), "kind": st.kind},
                     control_flag=flagged, double=dbl, headline=headline, x="series", y="ratio")
    return dispatch(view, spec, "לפני ואחרי · יחס כפול")


def _site_label(ctx, st) -> str:
    try:
        cols, rows = ctx.query(site_label_sql(st))
    except Exception:  # noqa: BLE001 — a label is a nicety, never a failure
        rows = []
    if st.kind == "road":
        km = f"כביש {st.road} ק״מ {st.km_from:g}–{st.km_to:g}"
        if rows and rows[0][0]:
            return f"{km} · {rows[0][0]} ← {rows[0][1]}"          # ← points toward name_to in an RTL line
        return km
    if st.kind == "njunction":
        name = rows[0][0] if rows and rows[0][0] else None
        return f"צומת {st.code}" + (f" · {name}" if name else "")
    if rows and rows[0][0]:
        city, s1, s2 = rows[0]
        return f"{city} · {s1 or ''} / {s2 or ''} (צומת {st.code})"
    return f"צומת עירוני {st.city}/{st.code}"


def _caveats(st, cy, w, mc, cas, dmg, share_b, share_a, flagged):
    out = []
    pb = f"{100 * share_b:.1f}%" if share_b is not None else "אין בסיס"
    pa = f"{100 * share_a:.1f}%" if share_a is not None else "אין בסיס"
    kind = {"road": "ק״מ בכביש", "njunction": "קוד צומת לא-עירוני", "ujunction": "קוד צומת עירוני"}[st.kind]
    if flagged:
        out.append(f"בקרה מסומנת: שיעור קידוד המיקום בסדרת הנזק-בלבד השתנה מ-{pb} ל-{pa} בין החלונות "
                   f"(מעל {int(CONTROL_FLAG_REL * 100)}% יחסית) — שינוי קידוד עלול להיקרא כשינוי תנועה")
    else:
        out.append(f"קידוד מיקום בסדרת הנזק-בלבד: {pb} לפני, {pa} אחרי ({kind})")
    thin = [SERIES_HE[1]] if cas["status"] != "ok" else []
    if dmg["status"] != "ok":
        thin.append(SERIES_HE[3])
    if thin:
        out.append(f"תא דק (פחות מ-{mc} רשומות) בסדרת {' ו'.join(thin)} — היחס לא חושב: ריק עדיף על מספר מזויף")
    out.append("SE של היחס הכפול = שורש סכום ריבועי ה-SE של שתי הסדרות — הרחבה של התוסף (הדו״ח אינו נותן SE ליחס הכפול)")
    out.append("רווח בר-סמך 95%: exp(ln r ± 1.96·SE), SE² = Σ 1/(n+½) על ארבע הספירות (Haldane)")
    out.append(f"שנת השינוי {cy} מוחרגת משני החלונות · אי-ודאות של שנה-שנתיים בתאריך השינוי")
    out.append("קבוצת ההשוואה = כל הרשת הארצית (שתי הסדרות), לא אותו סוג דרך")
    out.append("מתאם ולא סיבתיות: שינויים אחרים באתר וברשת אינם מבוקרים")
    out.append(f"מינימום {mc} רשומות לתא — כלל התוסף, מותאם מסף גלאי השינוי של הדו״ח")
    return out


ACTION = Action(
    name="before_after", label="לפני ואחרי · before_after",
    help="Double difference-in-differences for one site: the casualty series and the damage-only series, each "
         "against the whole national network in the windows before and after a change year (the change year "
         "itself is excluded); the double ratio removes what traffic explains. 95% CI via exp(ln r +/- 1.96 SE), "
         "SE^2 = sum 1/(n+0.5). Thin cells give n/a. Site keys: road:<n>/<km_from>-<km_to>, njunction:<code>, "
         "ujunction:<city_code>/<code>.",
    inputs={
        "site": Input(kind="text", label="אתר", default="road:60/96.0-98.8",
                      help="road:<n>/<km_from>-<km_to> | njunction:<code> | ujunction:<city_code>/<code>"),
        "change_year": Input(kind="number", label="שנת השינוי", default=2017, help="the year of the change (excluded from both windows)"),
        "window_years": Input(kind="number", label="חלון בשנים", default=3, help="1-3 years on each side (3 recommended)"),
        "min_cell": Input(kind="number", label="מינימום לתא", default=MIN_CELL_DEFAULT, help="a site cell below this -> n/a"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
