# -*- coding: utf-8 -*-
"""The deployed model's predictor — golden prediction rules (dossier §8): NO training at prediction time; inputs
rebuilt EXACTLY as trained (the contract lives in meta.json: feature list, ADT fill value, frozen static
attributes, the panel SQL); every output carries uncertainty. Shared by `site_ranking` and `hotspot_map(excess)`."""
from __future__ import annotations

from ..sqlkit import Refusal
from . import constants, gate, model, panel, registry


def contract_check(meta: dict) -> None:
    if int(meta.get("contract_version") or 0) != int(constants.CONTRACT_VERSION):
        # semantic panel-recipe drift can hide under unchanged feature NAMES — the version stamp is the tripwire
        # (a deployed model outlives plugin upgrades in the durable data dir); missing counts as a mismatch
        raise Refusal(
            "חוזה המאפיינים של המודל הפרוס אינו תואם את גרסת התוסף — יש לאמן ולפרוס מחדש",
            ["studio_train_site ואז studio_validate ו-studio_deploy"],
            detail=f"model contract_version {meta.get('contract_version')!r} != plugin {constants.CONTRACT_VERSION}")
    if list(meta.get("features") or []) != list(constants.FEATURES):
        raise Refusal(
            "חוזה המאפיינים של המודל הפרוס אינו תואם את גרסת התוסף — יש לאמן ולפרוס מחדש",
            ["studio_train_site ואז studio_validate ו-studio_deploy"],
            detail=f"model features {meta.get('features')} != plugin contract {list(constants.FEATURES)}")
    if not (meta.get("adt_fill") or {}).get("value"):
        raise Refusal("חוזה המודל הפרוס חסר את ערך מילוי ה-ADT — יש לאמן ולפרוס מחדש",
                      ["studio_train_site"], detail="meta.adt_fill.value missing")


def expected_by_segment(ctx, meta: dict, y0: int, y1: int, road: int = 0):
    """{(road, seg): {observed, ksi, mu, mu_by_year, excess, eb, lo90, hi90, significant, years_known}} over the
    requested years (already clipped to the panel era by the caller), plus the panel SQL text used."""
    contract_check(meta)
    raw = registry.model_bytes(ctx, meta["model_id"])
    if raw is None:
        raise Refusal("קובץ המודל הפרוס חסר מהרישום — יש לאמן ולפרוס מחדש", ["studio_models", "studio_train_site"],
                      detail=f"model.ubj missing for {meta['model_id']}")
    adt_fill = float(meta["adt_fill"]["value"])
    cols, rows = panel.fetch_panel(ctx, y0, y1, adt_fill)
    sql = panel.panel_sql(y0, y1, adt_fill)
    static = {(r[0], r[1]): dict(zip(panel.STATIC_COLUMNS[2:], r[2:])) for r in (meta.get("static_attrs") or {}).get("rows", [])}
    X, y, years, keys, ksi = panel.matrix(cols, rows, static)
    if road:
        keep = [i for i, k in enumerate(keys) if k[0] == road]
        X, y, years, keys, ksi = [X[i] for i in keep], [y[i] for i in keep], [years[i] for i in keep], \
            [keys[i] for i in keep], [ksi[i] for i in keep]
    if not X:                                             # e.g. a road with no panel segments
        return {}, sql
    mu = model.predict(raw, X)
    alpha = float(meta.get("alpha") or 0.0)
    ci = {c: i for i, c in enumerate(cols)}
    known = {}
    for i, r in enumerate(rows):
        k = (r[ci["road"]], r[ci["seg"]])
        if road and k[0] != road:
            continue
        known[k] = known.get(k, 0) + r[ci["adt_known"]]
    agg: dict = {}
    for i, k in enumerate(keys):
        e = agg.setdefault(k, {"observed": 0, "ksi": 0, "mu_by_year": []})
        e["observed"] += y[i]
        e["ksi"] += ksi[i]
        e["mu_by_year"].append(mu[i])
    for k, e in agg.items():
        m = float(sum(e["mu_by_year"]))
        lo, hi = gate.nb_interval(e["mu_by_year"], alpha)
        e.update(mu=round(m, 2), excess=round(e["observed"] - m, 2),
                 eb=round(gate.eb(m, e["observed"], alpha), 2), lo90=round(lo, 2), hi90=round(hi, 2),
                 significant=e["observed"] > hi, years_known=known.get(k, 0),
                 mu_by_year=[round(float(v), 3) for v in e["mu_by_year"]])
    return agg, sql
