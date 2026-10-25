# -*- coding: utf-8 -*-
"""hotspot_map (use ז — the presentation of ב): observed casualty-accident counts per unit (traffic count segment,
non-urban junction, urban junction) as a ranking, a GeoJSON layer for the page's Leaflet map, and a server-drawn
PNG twin for Layer 0 and for any map failure. Aggregate first, geometry after: counts come from the assignment
recipe (the same units CTE and predicate as segment_rates for 2017+; the latest traffic_segments vintage as static
geometry before), coordinates from the geocoded accidents (a Point at their mean) or from the junction dimensions.
`color_by=excess` is the P4 hook: without a deployed site model it falls back to observed counts and says so."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from .. import sqlkit
from ..envelope import CAVEAT_COUNTS_NOT_RISK, denominator, dispatch, guard, make_spec, stamp, view_input
from ..sqlkit import (DATA_YEARS, EXPOSURE_YEARS, FIRST_GEOCODED_YEAR_SQL, HOTSPOT_COLOR_BY, HOTSPOT_TOP_N,
                      HOTSPOT_UNITS, ActionError, Refusal, as_bool, as_choice, as_int, build_hotspot_sql,
                      hotspot_coverage_sql, hotspot_points_sql, rows_safe, scalar, year_range)

VIEWS = ("chart", "table", "sql")
TITLE = "מפת מוקדים"
POP_HE = {"segments": "תאונות לא-עירוניות עם נפגעים", "njunctions": "תאונות עם נפגעים בצמתים לא-עירוניים",
          "ujunctions": "תאונות עם נפגעים בצמתים עירוניים"}


@guard(TITLE)
def run(ctx, unit="segments", road=0, from_year=2008, to_year=2024, color_by="observed", top_n=30, points=False,
        view="chart"):
    unit = as_choice(unit, "unit", HOTSPOT_UNITS)
    color_by = as_choice(color_by, "color_by", HOTSPOT_COLOR_BY)
    view = as_choice(view, "view", VIEWS)
    y0, y1 = year_range(from_year, to_year)
    road = as_int(road, "road")
    top_n = as_int(top_n, "top_n")
    points = as_bool(points, "points")
    if road < 0:
        raise ActionError(f"road must be 0 (all roads) or a road number; got {road}.")
    if road and unit == "ujunctions":
        raise ActionError("road applies to unit=segments or unit=njunctions only (urban junctions have no road number).")
    if not HOTSPOT_TOP_N[0] <= top_n <= HOTSPOT_TOP_N[1]:
        raise ActionError(f"top_n must be between {HOTSPOT_TOP_N[0]} and {HOTSPOT_TOP_N[1]}; got {top_n}.")
    scope_he = f" בכביש {road}" if road else ""
    # P4: a deployed site model flips excess mode for segments — observed and the ranking then come from the
    # model's panel; any failure (no xgboost, a broken OR missing artifact) falls back to observed with a
    # caveat, never an error — a Refusal out of the model path degrades too (refuter 2026-09-06): the
    # refusal card stays for site_ranking, where the model IS the answer, never for a map of counts
    effective, exp, dep_meta, excess_note, y0e = "observed", None, None, None, y0
    if color_by == "excess" and unit == "segments":
        from ..studio import registry as _registry
        pointer, dep_meta = _registry.deployed(ctx)
        if pointer is not None and dep_meta is not None and y1 >= EXPOSURE_YEARS[0]:
            try:
                from ..studio import model as _model, predict as _predict
                _model.require_xgboost()
                y0e = max(y0, EXPOSURE_YEARS[0])
                exp, _ = _predict.expected_by_segment(ctx, dep_meta, y0e, y1, road)
                effective = "excess"
            except Exception as e:  # noqa: BLE001 — the map must never fail on the model path (Refusal included)
                # caveat-contract hygiene (sweep C1): exception texts carry ';'/newlines — clean like
                # site_profile._clean or the one-line Layer-0 note is corrupted on the degrade path (a
                # Refusal's reason is one clean sentence already — cleaned anyway); reset y0e or the
                # observed fallback silently narrows a pre-2017 range to the exposure era with no caveat
                # (the y0e-clip caveat fires only inside the excess branch) — map_scene's fix
                excess_note = str(e).replace(";", " ·").replace("\n", " ")[:200]
                exp, dep_meta, y0e = None, None, y0
        elif pointer is not None and dep_meta is None:
            excess_note = "deployed.json מצביע על מודל חסר או בלתי קריא"
        elif pointer is not None and y1 < EXPOSURE_YEARS[0]:
            # map_scene's arm, ported (refuter 2026-09-06): a deployed model + a pre-exposure-era range is
            # NOT "no deployment" — without this elif the default below told a deployed user the false story
            excess_note = f"excess קיים מ-{EXPOSURE_YEARS[0]} (עידן החשיפה)"
    elif color_by == "excess":
        # junctions never reach the registry — the merged line must lead with the TRUE cause (excess is
        # segments-only), never the "no deployment" default it never checked (refuter 2026-09-06)
        excess_note = "excess קיים רק למקטעים"
    sql = build_hotspot_sql(unit, y0e, y1, 1000000 if effective == "excess" else top_n, road)
    columns, raw = ctx.query(sql)
    rows = rows_safe(raw)
    ci = {c: i for i, c in enumerate(columns)}
    dropped_keys = 0
    if exp is not None:
        by_key = {(r[ci["road"]], r[ci["seg"]]): r for r in rows}
        new_rows = []
        for key, e in sorted(exp.items(), key=lambda kv: (-kv[1]["excess"], -kv[1]["observed"], kv[0])):
            base_row = by_key.get(key)
            if base_row is None:                            # panel key with no map-geometry accidents at all
                dropped_keys += 1
                continue
            row = list(base_row)
            row[ci["accidents"]], row[ci["ksi_accidents"]] = e["observed"], e["ksi"]
            row += [e["mu"], e["excess"], e["eb"], e["lo90"], e["hi90"], e["significant"]]
            new_rows.append(row)
        rows = new_rows[:top_n]
        columns = list(columns) + ["mu", "excess", "eb", "lo90", "hi90", "significant"]
        ci = {c: i for i, c in enumerate(columns)}
        for i, row in enumerate(rows, start=1):
            row[ci["rank"]] = i
    if not rows:
        raise Refusal(f"לא נמצאו {POP_HE[unit]}{scope_he} בשנים {y0}–{y1}",
                      [f"טווח שנים אחר בין {DATA_YEARS[0]} ל-{DATA_YEARS[1]}", "יחידה אחרת (unit)",
                       "road = 0 לכל הכבישים" if road else "trend לספירות ארציות"])
    placed = [r for r in rows if r[ci["latitude"]] is not None and r[ci["longitude"]] is not None]
    if not placed:
        first = ctx.query(FIRST_GEOCODED_YEAR_SQL)[1][0][0]
        raise Refusal(f"אין קואורדינטות לתאונות בשנים {y0}–{y1} — קואורדינטות קיימות מ-{first}",
                      [f"טווח שנים מ-{first}: hotspot_map", "ספירות ללא מפה: trend / segment_rates"],
                      detail=f"{len(rows)} units counted, none with a geocoded accident (coordinates start in {first})")
    cov_sql = hotspot_coverage_sql(unit, y0e, y1, road)
    cov = _coverage(rows_safe(ctx.query(cov_sql)[1]), unit)
    pts_sql, pts = None, []
    if points:
        pts_sql = hotspot_points_sql(unit, y0e, y1, _keys(unit, rows, ci), road)
        pts = rows_safe(ctx.query(pts_sql)[1])
    caveats = _caveats(unit, y0e, y1, road, rows, ci, cov, color_by, effective, points, pts, excess_note)
    if effective == "excess":
        g = (dep_meta.get("gate") or {}).get("metrics", {})
        alpha = float(dep_meta.get("alpha") or 0.0)
        panel_obs = sum(r[ci["accidents"]] for r in rows)
        head = [
            f"נצפה = הקצאה על גיאומטריית הלוח המלאה כמו במודל — מקטעים-שנים ללא שורת as-of מוקצים על הגרסה "
            f"האחרונה, ולכן המספרים עשויים לעלות על segment_rates" + (f" · {dropped_keys} מקטעי לוח ללא תאונה בגיאומטריית המפה — לא הוצגו" if dropped_keys else ""),
            f"excess = נצפה − צפוי · EB = w·μ + (1−w)·נצפה עם w = 1/(1+α·μ) · α = {alpha:g} · רווח 90% מקירוב נורמלי ל-NB"
            " · הצבע לפי המרחק מהציפייה ביחידות אי-הוודאות של האתר עצמו — הדירוג לפי excess",
            f"מודל {dep_meta['model_id']}: train_until {dep_meta['panel']['train_until']}, "
            f"Spearman {g.get('spearman')}, כיול {g.get('calibration')} · מתאם ולא סיבתיות",
        ]
        if y0e != y0:
            head.insert(0, f"excess קיים מ-{EXPOSURE_YEARS[0]} (עידן החשיפה) — הטווח קוצר ל-{y0e}–{y1}")
        caveats = head + [c for c in caveats if not c.startswith("ספירות אינן סיכון")]
        denom = denominator("exposure",
                            f"ציפייה מודלית ממודל אתר פרוס {dep_meta['model_id']} · excess = נצפה − צפוי",
                            model_id=dep_meta["model_id"], alpha=alpha, panel_observed=panel_obs)
    else:
        # the degrade reason rides INSIDE _caveats' one merged excess line (map_scene's rule) — a second
        # standalone line here used to coexist with a wrong "no deployment" claim when the model path threw
        denom = denominator("counts", "ספירות תאונות עם נפגעים לפי יחידה — ללא מכנה חשיפה",
                            matched=cov["matched"], total=cov["total"], pct=cov["pct"])
    geojson = _geojson(unit, rows, ci, pts)
    color_part = color_by if effective == color_by else f"{color_by}->observed"
    stamp_text = stamp("hotspot_map", unit, f"road={road or 'all'}", color_part, f"{y0e}-{y1}", f"top {top_n}")
    png = None
    if view == "chart":
        from .. import charts
        placed = [r for r in rows if r[ci["latitude"]] is not None and r[ci["longitude"]] is not None]
        units = [{"lat": r[ci["latitude"]], "lon": r[ci["longitude"]], "n": r[ci["accidents"]],
                  "rank": r[ci["rank"]], "label": _label(unit, r, ci),
                  **({"color": _excess_color(r, ci)} if effective == "excess" else {})}
                 for r in placed]
        png = charts.map_png(units, title=f"{TITLE}: {HOTSPOT_UNITS[unit]} · {y0e}–{y1}{scope_he}"
                             + (" · excess" if effective == "excess" else ""),
                             badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
    fallback = " (fallback observed)" if color_by != effective else ""
    model_part = f" | model {dep_meta['model_id']}" if effective == "excess" else ""
    basis = (f"hotspot_map | unit={unit} | road={road or 'all'} | color_by={color_by}{fallback}{model_part} | {y0e}-{y1} | "
             f"top {top_n} | listed {len(rows)} | placed {len(placed)} | points {len(pts)} | "
             f"coverage {cov['matched']}/{cov['total']} ({cov['pct']}%) | geocoded {cov['with_coords']}/{cov['total']}")
    spec = make_spec("accidents/map", png_base64=png, basis=basis, rows=rows, columns=columns, sql=sql,
                     # top-level model_id when the model path ran — the page's 🔮 chip keys on it (P9 sweep)
                     **({"model_id": dep_meta["model_id"]} if effective == "excess" else {}),
                     denominator=denom, caveats=caveats, geojson=geojson, unit=unit, road=road, color_by=color_by,
                     color_by_effective=effective, from_year=y0e, to_year=y1, top_n=top_n, points=points,
                     stamp=stamp_text, coverage=cov, coverage_sql=cov_sql, points_sql=pts_sql,
                     map={"units_listed": len(rows), "units_placed": len(placed),
                          "units_omitted": len(rows) - len(placed), "points": len(pts), "bbox": _bbox(placed, ci)},
                     x="site_key", y="accidents")
    return dispatch(view, spec, f"{TITLE} · {HOTSPOT_UNITS[unit]}")


DIVERGING = ("#1d4ed8", "#93c5fd", "#e5e7eb", "#fca5a5", "#b91c1c")     # blue = below the model, red = above


def _excess_color(r, ci) -> str:
    """Diverging bucket by the site's distance from expectation in its OWN NB-uncertainty units — ONE rule
    with map_scene._excess_hex and the page (normalizing by max|excess| let one outlier own the scale and
    hid the whole blue half). sd from the UPPER half only: nb_interval floors lo90 at 0, so (hi-lo)/2Z
    understates sd for low-μ segments and inflates |z| (sweep C6)."""
    sd = max(0.5, (float(r[ci["hi90"]]) - float(r[ci["mu"]])) / 1.6449)
    z = (float(r[ci["accidents"]]) - float(r[ci["mu"]])) / sd
    if z <= -2:
        return DIVERGING[0]
    if z <= -0.75:
        return DIVERGING[1]
    if z < 0.75:
        return DIVERGING[2]
    if z < 2:
        return DIVERGING[3]
    return DIVERGING[4]


def _coverage(by_year, unit) -> dict:
    out = {"by_year": by_year, "total": 0, "matched": 0, "with_coords": 0, "matched_with_coords": 0,
           "outside_bbox": 0, "static_matched": 0, "asof_matched": 0, "coded_off_junction": 0, "years_without_coords": []}
    for r in by_year:
        if unit == "segments":
            year, geometry, total, matched, with_coords, matched_with, outside = r
            off = 0
        else:
            year, total, matched, with_coords, matched_with, off, outside = r
            geometry = None
        out["total"] += total or 0
        out["matched"] += matched or 0
        out["with_coords"] += with_coords or 0
        out["matched_with_coords"] += matched_with or 0
        out["outside_bbox"] += outside or 0
        out["coded_off_junction"] += off or 0
        if geometry == "static":
            out["static_matched"] += matched or 0
        elif geometry == "asof":
            out["asof_matched"] += matched or 0
        if (total or 0) > 0 and not with_coords:
            out["years_without_coords"].append(year)
    out["pct"] = round(100.0 * out["matched"] / out["total"], 1) if out["total"] else 0.0
    return out


def _caveats(unit, y0, y1, road, rows, ci, cov, color_by, effective, points, pts, excess_note=None) -> list[str]:
    out = []
    scope = f" בכביש {road}" if road else ""
    if color_by == "excess" and effective != "excess":
        # ONE merged line, map_scene's rule: the actual degrade reason when there is one, the no-deployment
        # default otherwise — never both (the old pair could wrongly claim "no deployment" on a model throw);
        # for junctions the note itself carries the segments-only fact, so the tail keeps only the ranking rule
        out.append("התבקשה צביעה לפי excess — "
                   + (excess_note or "אין מודל אתר פרוס (סטודיו, שלב P4)")
                   + " · מוצגות ספירות observed"
                   + ("" if unit == "segments" else " · צמתים מדורגים לפי ספירות"))
    without = cov["total"] - cov["with_coords"]
    if without or cov["years_without_coords"] or cov["outside_bbox"]:
        tail = ("אינן ממוקמות (נספרות רק אם שויכו למקטע)" if unit == "segments"
                else "נספרות — הצמתים ממוקמים לפי טבלת הצמתים (dim), התאונות עצמן אינן ממוקמות כנקודות")
        line = f"{without:,} מתוך {cov['total']:,} {POP_HE[unit]} {y0}–{y1}{scope} ללא קואורדינטות — {tail}"
        if cov["years_without_coords"]:
            line += " · שנים ללא קואורדינטות כלל: " + ", ".join(str(y) for y in cov["years_without_coords"])
        if cov["outside_bbox"]:
            line += f" · {cov['outside_bbox']:,} מחוץ לגבולות ישראל — לא ממוקמות"
    else:
        line = f"כל {cov['total']:,} {POP_HE[unit]} {y0}–{y1}{scope} נושאות קואורדינטות"
    out.append(line)
    omitted = sum(1 for r in rows if r[ci["latitude"]] is None or r[ci["longitude"]] is None)
    if omitted:
        why = "ללא תאונה ממוקמת" if unit == "segments" else "ללא קואורדינטות בטבלת הצמתים וללא תאונה ממוקמת"
        out.append(f"{omitted} מתוך {len(rows)} היחידות המוצגות {why} — ברשימה, לא במפה")
    if unit == "segments":
        parts = []
        if y1 >= EXPOSURE_YEARS[0]:
            parts.append(f"{EXPOSURE_YEARS[0]}+ גרסת גיאומטריה לשנה כמו segment_rates (תאונות: {cov['asof_matched']:,})")
        if y0 < EXPOSURE_YEARS[0]:
            parts.append(f"לפני {EXPOSURE_YEARS[0]} הגרסה האחרונה של traffic_segments כגיאומטריה קבועה "
                         f"(תאונות: {cov['static_matched']:,})")
        out.append(f"שיוך למקטע: {cov['matched']:,} מתוך {cov['total']:,} ({cov['pct']}%) — " + ", ".join(parts)
                   + " · ק״מ 0 = לא קודד")
        out.append("נקודה = ממוצע קואורדינטות התאונות המשויכות · שמות, ק״מ ומפתח האתר (road:<n>/<km>-<km>) לפי "
                   "הגרסה האחרונה של traffic_segments — המפתח מתאים ל-before_after")
    else:
        kind = "לא-עירוניות (road_type 3)" if unit == "njunctions" else "עירוניות (road_type 1)"
        line = (f"קוד צומת: {cov['matched']:,} מתוך {cov['total']:,} תאונות {kind} בצומת ({cov['pct']}%) נושאות קוד "
                f"אמיתי (0/99/9999/99999999 = לא קודד)")
        if cov["coded_off_junction"]:
            line += f" · {cov['coded_off_junction']:,} תאונות מחוץ לצומת נושאות קוד — נכללות"
        out.append(line)
        dim = "dim_junction_nonurban" if unit == "njunctions" else "dim_junction_urban (מפתח צומת+עיר)"
        dup = sum(1 for r in rows if (r[ci["dim_rows"]] or 0) > 1)
        from_dim = sum(1 for r in rows if r[ci["geometry_source"]] == "dim")
        no_dim_row = sum(1 for r in rows if (r[ci["dim_rows"]] or 0) == 0)
        dim_no_coords = sum(1 for r in rows if r[ci["geometry_source"]] != "dim" and (r[ci["dim_rows"]] or 0) > 0)
        name_rule = ("שם לפי min" if unit == "njunctions"
                     else "שם = זוג הרחובות הקטן לקסיקוגרפית מתוך שורה אחת — אותו כלל כמו before_after")
        line = (f"מיקום מ-{dim}: {from_dim} מתוך {len(rows)} צמתים ({dup} עם יותר משורת ממד אחת — מוזגו: ממוצע "
                f"קואורדינטות, {name_rule}) · ללא מיקום בממד: {dim_no_coords} עם שורת ממד ללא קואורדינטות, "
                f"{no_dim_row} ללא שורת ממד — ממוצע התאונות שלהם")
        if from_dim == len(rows) and not any((r[ci["geocoded"]] or 0) for r in rows):
            line += " · כל היחידות ממוקמות לפי הממד בלבד — אין תאונה ממוקמת בטווח"
        out.append(line)
    if unit == "segments":
        out.append(CAVEAT_COUNTS_NOT_RISK + " · שיעור לק״מ-רכב: segment_rates · excess: לאחר פריסת מודל אתר")
    else:
        out.append("צמתים מדורגים לפי ספירות בלבד — אין נפח תנועה לצמתים · " + CAVEAT_COUNTS_NOT_RISK
                   + " · שיעור לק״מ-רכב ו-excess קיימים למקטעים בלבד (segment_rates)")
    if points:
        available = sum(r[ci["geocoded"]] or 0 for r in rows)
        out.append(f"נקודות: {len(pts):,} מתוך {available:,} תאונות ממוקמות ביחידות המוצגות "
                   f"(תקרה {sqlkit.POINTS_PER_UNIT} ליחידה, {sqlkit.POINTS_TOTAL} בסך הכל, החדשות קודם)")
    return out


def _label(unit, r, ci) -> str:
    if unit == "segments":            # ← : in a Hebrew (RTL) line the arrow must point toward name_to, i.e. left
        return f"{r[ci['road']]}/{r[ci['seg']]} · {r[ci['name_from']] or ''} ← {r[ci['name_to']] or ''}"
    if unit == "njunctions":
        name = r[ci["name"]]
        return f"צומת {r[ci['code']]}" + (f" · {name}" if name else "")
    return (f"{r[ci['city_name']] or ''} · {r[ci['street1_name']] or ''} / {r[ci['street2_name']] or ''} "
            f"(צומת {r[ci['code']]})")


def _keys(unit, rows, ci):
    if unit == "segments":
        return [(r[ci["road"]], r[ci["seg"]]) for r in rows]
    if unit == "njunctions":
        return [(r[ci["code"]],) for r in rows]
    return [(r[ci["city"]], r[ci["code"]]) for r in rows]


def _geojson(unit, rows, ci, pts) -> dict:
    features = []
    for r in rows:
        lat, lon = r[ci["latitude"]], r[ci["longitude"]]
        if lat is None or lon is None:
            continue
        props = {"kind": "unit", "unit": unit, "site_key": r[ci["site_key"]], "label": _label(unit, r, ci),
                 "rank": r[ci["rank"]], "accidents": r[ci["accidents"]], "ksi_accidents": r[ci["ksi_accidents"]],
                 "geocoded": r[ci["geocoded"]], "first_year": r[ci["first_year"]], "last_year": r[ci["last_year"]]}
        if "excess" in ci:
            props.update(mu=r[ci["mu"]], excess=r[ci["excess"]], eb=r[ci["eb"]], lo90=r[ci["lo90"]],
                         hi90=r[ci["hi90"]], significant=r[ci["significant"]])
        if unit == "segments":
            props.update(road=r[ci["road"]], seg=r[ci["seg"]], km_from=r[ci["km_from"]], km_to=r[ci["km_to"]],
                         static_assigned=r[ci["static_assigned"]])
        else:
            props.update(code=r[ci["code"]], geometry_source=r[ci["geometry_source"]], dim_rows=r[ci["dim_rows"]])
            if unit == "ujunctions":
                props["city"] = r[ci["city"]]
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                         "properties": {k: scalar(v) for k, v in props.items()}})
    by_rank = {r[ci["rank"]]: r[ci["site_key"]] for r in rows}
    for p in pts:
        # columns: rank, key cols…, accident_id, case_type_code, year, accident_date, severity_code, severity_label[, road_km], lat, lon
        rank = p[0]
        lat, lon = p[-2], p[-1]
        n_key = 2 if unit in ("segments", "ujunctions") else 1
        aid, case, year, date, sev_code, sev_label = p[1 + n_key: 7 + n_key]
        props = {"kind": "accident", "site_key": by_rank.get(rank), "rank": rank, "accident_id": aid,
                 "case_type_code": case, "year": year, "date": date, "severity_code": sev_code,
                 "severity_label": sev_label}
        if unit == "segments":
            props["road_km"] = p[7 + n_key]
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                         "properties": {k: scalar(v) for k, v in props.items()}})
    return {"type": "FeatureCollection", "features": features}


def _bbox(placed, ci):
    if not placed:
        return None
    lats = [r[ci["latitude"]] for r in placed]
    lons = [r[ci["longitude"]] for r in placed]
    return [min(lons), min(lats), max(lons), max(lats)]


ACTION = Action(
    name="hotspot_map", label="מפת מוקדים · hotspot_map",
    help="Observed casualty-accident counts per unit (traffic count segment, non-urban junction or urban junction) "
         "ranked and placed on a map: a GeoJSON layer for the plugin page plus a server-drawn PNG twin. Counts are "
         "assigned exactly like segment_rates (2017+ per-year geometry; the latest traffic_segments vintage before). "
         "Counts are not risk: color_by=excess needs a deployed site model (studio) and falls back to observed.",
    inputs={
        "unit": Input(kind="choice", label="יחידה", default="segments", choices=list(HOTSPOT_UNITS),
                      help="segments = traffic count segments (interurban); njunctions / ujunctions = junction codes"),
        "road": Input(kind="number", label="כביש", default=0, help="0 = all roads; a road number for segments or njunctions"),
        "from_year": Input(kind="number", label="שנת התחלה", default=2008,
                           help=f"{DATA_YEARS[0]}-{DATA_YEARS[1]}; years before the first geocoded year carry no accident "
                                "coordinates (segments: counted only if assigned, not placed; junctions: placed from the dimension)"),
        "to_year": Input(kind="number", label="שנת סיום", default=2024, help="data ends 2024-12-31"),
        "color_by": Input(kind="choice", label="צביעה", default="observed", choices=list(HOTSPOT_COLOR_BY),
                          help="observed = counts; excess = observed minus the deployed site model's expectation (P4; falls back to observed)"),
        "top_n": Input(kind="number", label="מספר יחידות", default=30, help="1-200"),
        "points": Input(kind="bool", label="תאונות בודדות", default=False,
                        help=f"add the shown units' individual accidents to the geojson (internal use; capped "
                             f"{sqlkit.POINTS_PER_UNIT} per unit, {sqlkit.POINTS_TOTAL} total)"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
