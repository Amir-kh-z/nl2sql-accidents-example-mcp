# -*- coding: utf-8 -*-
"""map_scene (P10 — the מפה חיה tab's data door): ONE envelope carrying the whole advanced map — the geocoded
casualty-accident point cloud as columnar arrays (the page renders it on the GPU and filters year/severity/
day-night client-side, so this runs once per server scope), the three clickable site layers (reusing
hotspot_map's exact assignment SQL — every hard-won rule inherited, none re-derived), locality centroids for
the offline search box, and the in-range coverage numbers behind every caveat.

`color_by=excess` (the P10 follow-up, hotspot_map's P4 hook promoted to the big map): with a deployed site
model, the SEGMENTS layer re-ranks by excess = observed − μ and carries μ/excess/EB/interval/significant per
segment — the EB network screening as a map. Junctions NEVER join it (no exposure denominator exists — the
golden rule is structure, not styling); any missing prerequisite falls back to observed with an honest
caveat, never an error. The PNG twin (hexbin density + top segments, excess-colored when live) is the static
shadow for Layer 0 and for any page failure."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import CAVEAT_COUNTS_NOT_RISK, denominator, dispatch, guard, make_spec, stamp, view_input
from ..sqlkit import (DATA_YEARS, EXPOSURE_YEARS, FIRST_GEOCODED_YEAR_SQL, HOTSPOT_COLOR_BY, HOTSPOT_TOP_N,
                      HOTSPOT_UNITS, MAP_CLOUD_BOUNDS, ActionError, Refusal, as_bool, as_choice, as_int,
                      build_hotspot_sql, build_map_cloud_sql, gazetteer_sql, map_cloud_coverage_sql,
                      rows_safe, year_range)
from .hotspot_map import DIVERGING, _label  # ONE label rule + ONE diverging ramp — shared with hotspot_map

VIEWS = ("chart", "table", "sql")
TITLE = "מפה חיה"
CLOUD_COLUMNS = ("lon", "lat", "year", "sev", "night")
MODEL_COLS = ("mu", "excess", "eb", "lo90", "hi90", "significant")


@guard(TITLE)
def run(ctx, road=0, from_year=2008, to_year=2024, top_sites=150, max_points=300000, color_by="observed",
        twin=True, view="chart"):
    view = as_choice(view, "view", VIEWS)
    color_by = as_choice(color_by, "color_by", HOTSPOT_COLOR_BY)
    twin = as_bool(twin, "twin")
    y0, y1 = year_range(from_year, to_year)
    road = as_int(road, "road")
    top_sites = as_int(top_sites, "top_sites")
    max_points = as_int(max_points, "max_points")
    if road < 0:
        raise ActionError(f"road must be 0 (all roads) or a road number; got {road}.")
    if not HOTSPOT_TOP_N[0] <= top_sites <= HOTSPOT_TOP_N[1]:
        raise ActionError(f"top_sites must be between {HOTSPOT_TOP_N[0]} and {HOTSPOT_TOP_N[1]}; got {top_sites}.")
    if not MAP_CLOUD_BOUNDS[0] <= max_points <= MAP_CLOUD_BOUNDS[1]:
        raise ActionError(f"max_points must be between {MAP_CLOUD_BOUNDS[0]} and {MAP_CLOUD_BOUNDS[1]}; got {max_points}.")
    scope_he = f" בכביש {road}" if road else ""

    # coverage first: it is both the caveat numbers and the emptiness verdict (refusal, never a blank map)
    cov_sql = map_cloud_coverage_sql(y0, y1, road)
    cov_rows = rows_safe(ctx.query(cov_sql)[1])
    total = sum(int(r[1] or 0) for r in cov_rows)
    geocoded = sum(int(r[2] or 0) for r in cov_rows)
    outside = sum(int(r[3] or 0) for r in cov_rows)
    years_without = [r[0] for r in cov_rows if int(r[1] or 0) > 0 and not int(r[2] or 0)]
    if total == 0:
        raise Refusal(f"לא נמצאו תאונות עם נפגעים{scope_he} בשנים {y0}-{y1}",
                      [f"טווח שנים אחר בין {DATA_YEARS[0]} ל-{DATA_YEARS[1]}",
                       "road = 0 לכל הכבישים" if road else "trend לספירות ארציות"])
    if geocoded == 0:
        first = ctx.query(FIRST_GEOCODED_YEAR_SQL)[1][0][0]
        raise Refusal(f"אין קואורדינטות לתאונות בשנים {y0}-{y1} — קואורדינטות קיימות מ-{first}",
                      [f"טווח שנים מ-{first}: map_scene", "ספירות ללא מפה: trend / hotspot_map"],
                      detail=f"{total} casualty accidents counted, none geocoded (coordinates start in {first})")

    cloud_sql = build_map_cloud_sql(y0, y1, road, max_points)
    raw = rows_safe(ctx.query(cloud_sql)[1])
    n = len(raw)
    capped = geocoded > n
    cloud = {c: [r[i] for r in raw] for i, c in enumerate(CLOUD_COLUMNS)}
    cloud.update(n=n, capped=capped)

    # the model layer (segments only, hotspot_map's P4 recipe): resolve BEFORE the site queries
    effective, exp, dep_meta, excess_note, dropped_keys, y0e = "observed", None, None, None, 0, y0
    if color_by == "excess":
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
                # a Refusal here (missing model.ubj under a valid pointer, a contract mismatch) degrades like
                # any model failure — the refusal card stays for site_ranking, where the model IS the answer
                # (refuter 2026-09-06); caveat-contract hygiene (sweep C1): exception texts carry ';'/newlines
                # — clean like site_profile._clean or the one-line Layer-0 note is corrupted on the degrade path
                excess_note = str(e).replace(";", " ·").replace("\n", " ")[:200]
                exp, dep_meta, y0e = None, None, y0
        elif pointer is not None and dep_meta is None:
            excess_note = "deployed.json מצביע על מודל חסר או בלתי קריא"
        elif pointer is None:
            excess_note = "אין מודל אתר פרוס"
        elif y1 < EXPOSURE_YEARS[0]:
            excess_note = f"excess קיים מ-{EXPOSURE_YEARS[0]} (עידן החשיפה)"

    # the three site layers — hotspot_map's exact SQL; a road number is meaningless for urban junctions,
    # so that layer is skipped (with a caveat) instead of silently filtered to noise
    sites, sites_sql = {}, {}
    seg_rows, seg_cols = [], []
    for unit in HOTSPOT_UNITS:
        if unit == "ujunctions" and road:
            sites[unit], sites_sql[unit] = [], None
            continue
        if unit == "segments" and exp is not None:
            # excess mode: fetch ALL segment geometries in the MODEL window, merge the panel measures,
            # re-rank by excess (the screening order), cut to top_sites — hotspot_map lines, verbatim logic
            s = build_hotspot_sql(unit, y0e, y1, 1000000, road)
        else:
            s = build_hotspot_sql(unit, y0, y1, top_sites, 0 if unit == "ujunctions" else road)
        cols, rws = ctx.query(s)
        rws = rows_safe(rws)
        ci = {c: i for i, c in enumerate(cols)}
        if unit == "segments" and exp is not None:
            by_key = {(r[ci["road"]], r[ci["seg"]]): r for r in rws}
            merged = []
            for key, e in sorted(exp.items(), key=lambda kv: (-kv[1]["excess"], -kv[1]["observed"], kv[0])):
                base = by_key.get(key)
                if base is None:                       # a panel key with no map-geometry accidents at all
                    dropped_keys += 1
                    continue
                row = list(base)
                row[ci["accidents"]], row[ci["ksi_accidents"]] = e["observed"], e["ksi"]
                row += [e[k] for k in MODEL_COLS]
                merged.append(row)
            # the SCREENING is network-wide: ALL panel segments show, red through blue — a top-N cut by
            # excess would display only the red tail and silently hide every better-than-expected segment
            # (found in the instructor's review); top_sites still governs the junction layers and counts mode
            rws = merged
            cols = list(cols) + list(MODEL_COLS)
            ci = {c: i for i, c in enumerate(cols)}
            for i, row in enumerate(rws, start=1):
                row[ci["rank"]] = i
        sites_sql[unit] = s
        sites[unit] = [_site_entry(unit, r, ci) for r in rws]
        if unit == "segments":
            seg_rows, seg_cols = rws, list(cols)

    gz_sql = gazetteer_sql(y0, y1)
    gaz = [{"city": r[0], "name": r[1], "n": r[2], "lat": r[3], "lon": r[4]}
           for r in rows_safe(ctx.query(gz_sql)[1])]

    pct = round(100.0 * geocoded / total, 1)
    caveats = _caveats(y0, y1, road, total, geocoded, outside, years_without, n, capped, sites,
                       color_by, effective, dep_meta, excess_note, dropped_keys, y0e)
    if effective == "excess":
        denom = denominator("exposure",
                            f"מקטעים: ציפייה מודלית ממודל אתר פרוס {dep_meta['model_id']} · excess = נצפה − צפוי"
                            f" · צמתים וענן: ספירות",
                            model_id=dep_meta["model_id"], alpha=float(dep_meta.get("alpha") or 0.0),
                            geocoded=geocoded, total=total, pct=pct)
    else:
        denom = denominator("counts", "ספירות תאונות עם נפגעים — ללא מכנה חשיפה",
                            geocoded=geocoded, total=total, pct=pct)
    color_part = color_by if effective == color_by else f"{color_by}->observed"
    stamp_text = stamp("map_scene", f"road={road or 'all'}", f"{y0}-{y1}", color_part,
                       f"cloud {n}", f"cap {max_points}", f"top {top_sites}")
    png = None
    if view == "chart" and twin:                 # the page's interactive fetch passes twin=false — it renders
        from .. import charts                    # the GL scene itself and re-fetches with defaults on GL failure
        units = [{"lat": e["lat"], "lon": e["lon"], "n": e["accidents"], "rank": e["rank"], "label": e["label"],
                  "color": _excess_hex(e) if effective == "excess" else "#3a4552"}
                 for e in sites["segments"] if e["lat"] is not None and e["lon"] is not None]
        png = charts.scene_png(cloud, units,
                               title=f"{TITLE} · {y0}-{y1}{scope_he}" + (" · excess" if effective == "excess" else ""),
                               badge=f"מכנה: {denom['label']}", caveats=caveats, stamp=stamp_text)
    model_part = f" | model {dep_meta['model_id']}" if effective == "excess" else ""
    basis = (f"map_scene | road={road or 'all'} | {y0}-{y1} | color_by={color_part}{model_part} | "
             f"cloud {n} (cap {max_points}) | "
             f"sites {len(sites['segments'])}/{len(sites['njunctions'])}/{len(sites['ujunctions'])} | "
             f"top {top_sites} | geocoded {geocoded}/{total} ({pct}%)")
    spec = make_spec("accidents/map_scene", png_base64=png, basis=basis, rows=seg_rows, columns=seg_cols,
                     sql=cloud_sql, denominator=denom, caveats=caveats,
                     **({"model_id": dep_meta["model_id"]} if effective == "excess" else {}),
                     color_by=color_by, color_by_effective=effective,
                     cloud=cloud, sites=sites, gazetteer=gaz,
                     coverage={"total": total, "geocoded": geocoded, "outside_bbox": outside,
                               "years_without_coords": years_without, "pct": pct, "by_year": cov_rows},
                     coverage_sql=cov_sql, sites_sql=sites_sql, gazetteer_sql=gz_sql,
                     meta={"bbox": _bbox(cloud), "years": [y0, y1], "cap": max_points, "road": road,
                           "capped": capped, "model_from_year": y0e if effective == "excess" else None},
                     stamp=stamp_text, x="site_key", y="accidents")
    return dispatch(view, spec, TITLE)


def _site_entry(unit, r, ci) -> dict:
    e = {"site_key": r[ci["site_key"]], "label": _label(unit, r, ci), "rank": r[ci["rank"]],
         "accidents": r[ci["accidents"]], "ksi_accidents": r[ci["ksi_accidents"]], "geocoded": r[ci["geocoded"]],
         "lat": r[ci["latitude"]], "lon": r[ci["longitude"]],
         "first_year": r[ci["first_year"]], "last_year": r[ci["last_year"]]}
    if unit == "segments":
        e.update(road=r[ci["road"]], seg=r[ci["seg"]], km_from=r[ci["km_from"]], km_to=r[ci["km_to"]])
        if "excess" in ci:                       # the model merge — segments only, ever
            e.update({k: r[ci[k]] for k in MODEL_COLS})
    else:
        e.update(code=r[ci["code"]], geometry_source=r[ci["geometry_source"]])
        if unit == "ujunctions":
            e["city"] = r[ci["city"]]
    return e


def _excess_hex(e) -> str:
    """Diverging bucket by the site's distance from expectation in its OWN NB-uncertainty units — the page's
    exact rule (normalizing by max|excess| let one outlier own the scale and hid the whole blue half).
    sd from the UPPER half only: nb_interval floors lo90 at 0, so (hi-lo)/2Z understates sd for low-μ
    segments and inflates |z| (sweep C6)."""
    sd = max(0.5, (float(e["hi90"]) - float(e["mu"])) / 1.6449)
    z = (float(e["accidents"]) - float(e["mu"])) / sd
    if z <= -2:
        return DIVERGING[0]
    if z <= -0.75:
        return DIVERGING[1]
    if z < 0.75:
        return DIVERGING[2]
    if z < 2:
        return DIVERGING[3]
    return DIVERGING[4]


def _caveats(y0, y1, road, total, geocoded, outside, years_without, n, capped, sites,
             color_by, effective, dep_meta, excess_note, dropped_keys, y0e) -> list[str]:
    scope = f" בכביש {road}" if road else ""
    out = []
    if effective == "excess":
        g = (dep_meta.get("gate") or {}).get("metrics", {})
        if y0e != y0:
            out.append(f"שכבת המקטעים במצב excess נמנית על {y0e}-{y1} (עידן החשיפה) — הענן והצמתים על מלוא הטווח")
        out.append("excess = נצפה − צפוי · EB = w·μ + (1−w)·נצפה · רווח 90% מקירוב נורמלי ל-NB · "
                   "הצבע לפי המרחק מהציפייה ביחידות אי-הוודאות של האתר עצמו — הדירוג לפי excess · "
                   f"מודל {dep_meta['model_id']}: train_until {dep_meta['panel']['train_until']}, "
                   f"Spearman {g.get('spearman')}, כיול {g.get('calibration')} · מתאם ולא סיבתיות")
        line = ("excess קיים למקטעים בלבד — הצמתים נותרו בספירות (אין נפח תנועה לצמתים) · "
                f"כל {len(sites['segments']):,} מקטעי הלוח מוצגים, מאדום ועד כחול — חיתוך לפי excess היה "
                f"מסתיר את הטובים מהצפוי")
        if dropped_keys:
            line += f" · {dropped_keys} מקטעי לוח ללא תאונה בגיאומטריית המפה — לא הוצגו"
        out.append(line)
        out.append("נצפה ו-KSI במקטעים במצב המודל = הקצאת הלוח המלאה כמו site_ranking — "
                   "לא ספירת טווח מילולי, והמספרים עשויים להיבדל מ-segment_rates ומספירות מצב הספירות")
    elif color_by == "excess":
        out.append(f"התבקשה צביעה לפי excess — {excess_note or 'אין מודל אתר פרוס'}, מוצגות ספירות")
    without = total - geocoded - outside          # outside-bbox rows HAVE coordinates — counted separately
    if without or outside or years_without:
        line = f"{without:,} מתוך {total:,} תאונות עם נפגעים {y0}-{y1}{scope} ללא קואורדינטות — נספרות בכיסוי, לא בענן הנקודות"
        if years_without:
            line += " · שנים ללא קואורדינטות כלל: " + ", ".join(str(y) for y in years_without)
        if outside:
            line += f" · {outside:,} מחוץ לגבולות ישראל — לא מוצגות"
        out.append(line)
    else:
        out.append(f"כל {total:,} התאונות עם נפגעים {y0}-{y1}{scope} נושאות קואורדינטות")
    if capped:
        out.append(f"ענן הנקודות הוגבל ל-{n:,} מתוך {geocoded:,} תאונות ממוקמות (החדשות קודם) — "
                   f"העלו את max_points או צמצמו את טווח השנים")
    if road:
        out.append(f"בכביש {road}: שכבת הצמתים העירוניים אינה מוצגת ורוב התאונות העירוניות נושרות — "
                   f"למספר כביש אין משמעות בתוך עיר")
    omitted = sum(1 for u in ("segments", "njunctions", "ujunctions")
                  for e in sites[u] if e["lat"] is None or e["lon"] is None)
    if omitted:
        out.append(f"{omitted} אתרים ברשימות ללא מיקום — בדירוג, לא במפה")
    out.append("שכבות האתרים מדורגות לפי ספירות — צמתים ממוקמים לפי טבלת הצמתים או ממוצע תאונותיהם, כמו hotspot_map"
               if effective != "excess" else
               "המקטעים מדורגים לפי excess · הצמתים לפי ספירות — ממוקמים לפי טבלת הצמתים או ממוצע תאונותיהם")
    if effective != "excess":
        out.append(CAVEAT_COUNTS_NOT_RISK + " · שיעור לק״מ-רכב: segment_rates · מדדי מודל לאתר: site_profile / site_ranking")
    return out


def _bbox(cloud):
    if not cloud["lon"]:
        return None
    return [min(cloud["lon"]), min(cloud["lat"]), max(cloud["lon"]), max(cloud["lat"])]


# Declared LAST (Action.run is evaluated at import).
ACTION = Action(
    name="map_scene", label="מפה חיה · map_scene",
    help="One envelope for the interactive map tab: the geocoded casualty-accident point cloud as columnar "
         "arrays (lon/lat/year/severity/night - the page renders on the GPU and filters client-side), the "
         "three site layers (hotspot_map's exact assignment SQL), locality centroids for offline search, and "
         "the coverage numbers. color_by=excess re-ranks and colors the SEGMENTS layer by the deployed site "
         "model's excess (junctions never join - no exposure denominator; falls back to observed with a "
         "caveat). The PNG twin is a hexbin density with the top segments.",
    inputs={
        "road": Input(kind="number", label="כביש", default=0,
                      help="0 = all roads; a road number filters the cloud and the segment/non-urban-junction "
                           "layers (the urban-junction layer drops - a road number has no meaning inside a city)"),
        "from_year": Input(kind="number", label="שנת התחלה", default=2008,
                           help=f"{DATA_YEARS[0]}-{DATA_YEARS[1]}; coordinates exist from 2008 - an all-2005-2007 "
                                "range returns a refusal naming the first geocoded year"),
        "to_year": Input(kind="number", label="שנת סיום", default=2024, help="data ends 2024-12-31"),
        "top_sites": Input(kind="number", label="אתרים לשכבה", default=150,
                           help="1-200 clickable sites per layer (segments, non-urban junctions, urban junctions)"),
        "max_points": Input(kind="number", label="תקרת נקודות", default=300000,
                            help="SQL cap on the accident cloud, newest first (10-400000); the full 2008-2024 "
                                 "geocoded cloud is ~218k"),
        "color_by": Input(kind="choice", label="צביעה", default="observed", choices=list(HOTSPOT_COLOR_BY),
                          help="observed = counts; excess = the deployed site model's observed-minus-expected "
                               "on the segments layer only (falls back to observed without a deployment)"),
        "twin": Input(kind="bool", label="תאום סטטי", default=True,
                      help="draw the server-side PNG twin (Layer 0 / fallback); the page's interactive fetch "
                           "skips it for speed and re-fetches with defaults if WebGL fails"),
        "view": view_input("chart", VIEWS),
    },
    run=run)
