# -*- coding: utf-8 -*-
"""The segment-year panel: the FULL segment x year grid (zero years included) with the doc-11 features.

Geometry per (road, seg, year): the as-of vintage where the segment-year has one (the same `units` CTE as
`segment_rates`), else the key's latest `traffic_segments` vintage — so every grid year has a geometry row and the
assignment join keeps its year equality (DuckDB 1.5.0 mis-binds a window over a pure range join). `lag()` runs over
the GRID, never over the range join. Never `traffic_adt_filled`."""
from __future__ import annotations

import hashlib

from ..sqlkit import ASSIGN_QUALIFY, STATIC_GEOMETRY_CTE, UNITS_CTE, assign_join, ilit, lit, rows_safe
from . import constants


def adt_median_sql(train_until: int) -> str:
    """The national ADT fill: the median as-of ADT over the units CTE up to the training horizon (frozen in meta)."""
    return (f"-- nl2sql-roadsafety-lab | studio | national ADT fill | units with year <= {train_until}\n"
            f"WITH {UNITS_CTE}\n"
            f"SELECT median(adt_asof) AS adt_median, count(*) AS unit_years FROM units WHERE year <= {ilit(train_until)}")


def panel_sql(y0: int, until_year: int, adt_fill: float) -> str:
    """The full grid rows y0..until_year with target, ksi, lag1, adt features and year_idx."""
    return (f"-- nl2sql-roadsafety-lab | studio panel | {y0}-{until_year} | adt fill {adt_fill:.1f} | lag feed {y0 - 1}\n"
            f"WITH {UNITS_CTE},\n{STATIC_GEOMETRY_CTE},\n"
            f"geom AS (                             -- one geometry per (road, seg, year): the as-of vintage where the segment-year has one, else the latest traffic_segments vintage\n"
            f"    SELECT g.road, g.seg, t.y AS year, coalesce(u.km_from, g.km_from) AS km_from, coalesce(u.km_to, g.km_to) AS km_to,\n"
            f"           coalesce(u.gap_years, 99) AS gap_years, u.adt_asof, u.gap_years AS asof_gap,\n"
            f"           CASE WHEN u.road IS NULL THEN 'static' ELSE 'asof' END AS geometry\n"
            f"    FROM latest_segments g\n"
            f"    CROSS JOIN range({ilit(y0 - 1)}, {ilit(until_year + 1)}) t(y)\n"
            f"    LEFT JOIN units u ON u.road = g.road AND u.seg = g.seg AND u.year = t.y\n"
            f"),\n"
            f"base AS (                             -- casualty series, interurban, the grid years + the lag feed year (dossier 5.1)\n"
            f"    SELECT accident_id, case_type_code, year, road1_number, road_km, severity_code\n"
            f"    FROM accidents\n"
            f"    WHERE case_type_code = 1\n"
            f"      AND year BETWEEN {ilit(y0 - 1)} AND {ilit(until_year)}\n"
            f"      AND road_type_code IN (3, 4)\n"
            f"),\n"
            f"matched AS (\n"
            f"    SELECT a.accident_id, a.case_type_code, a.year, a.severity_code, u.road, u.seg\n"
            f"    FROM base a\n    {assign_join('geom')}\n    {ASSIGN_QUALIFY}\n"
            f"),\n"
            f"counts AS (\n"
            f"    SELECT road, seg, year, count(*) AS y, count(*) FILTER (WHERE severity_code IN (1, 2)) AS ksi\n"
            f"    FROM matched GROUP BY 1, 2, 3\n"
            f"),\n"
            f"grid AS (\n"
            f"    SELECT g.road, g.seg, g.year, g.geometry, g.km_from, g.km_to,\n"
            f"           coalesce(c.y, 0) AS y, coalesce(c.ksi, 0) AS ksi, g.adt_asof, g.asof_gap\n"
            f"    FROM geom g LEFT JOIN counts c USING (road, seg, year)\n"
            f"),\n"
            f"lagged AS (                           -- a window over the GRID, never over the range join (DuckDB 1.5.0)\n"
            f"    SELECT *, lag(y) OVER (PARTITION BY road, seg ORDER BY year) AS lag1 FROM grid\n"
            f")\n"
            f"SELECT road, seg, year, geometry, km_from, km_to, y, ksi, lag1,\n"
            f"       CASE WHEN adt_asof IS NULL THEN {lit(adt_fill)} ELSE adt_asof END AS adt_asof,\n"
            f"       CASE WHEN adt_asof IS NULL THEN 0 ELSE 1 END AS adt_known,\n"
            f"       asof_gap, year - {ilit(constants.PANEL_YEARS[0])} AS year_idx\n"
            f"FROM lagged WHERE year >= {ilit(y0)} ORDER BY road, seg, year")


def static_attrs_sql(train_until: int) -> str:
    """Per-segment attributes frozen from ALL accident records on the latest-vintage geometry, BOTH series,
    2005..train_until — no row from the target window can enter (the leakage rule; tested). The five coding
    columns are effectively casualty-coded (the damage-only series carries ~0% of them) — the averages run over
    the CODED rows only (the CASE WHEN … END forms), and the card says so."""
    return (f"-- nl2sql-roadsafety-lab | studio static attributes | both series {constants.HISTORY_START}-{train_until} on the latest vintage\n"
            f"WITH {STATIC_GEOMETRY_CTE},\n"
            f"geom AS (\n"
            f"    SELECT g.road, g.seg, t.y AS year, g.km_from, g.km_to, 99 AS gap_years\n"
            f"    FROM latest_segments g CROSS JOIN range({ilit(constants.HISTORY_START)}, {ilit(train_until + 1)}) t(y)\n"
            f"),\n"
            f"base AS (\n"
            f"    SELECT accident_id, case_type_code, year, road1_number, road_km, road_type_code, day_night_code,\n"
            f"           road_shape_code, single_carriageway_code, dual_carriageway_code, road_surface_code, speed_limit_code\n"
            f"    FROM accidents\n"
            f"    WHERE case_type_code IN (1, 3)\n"
            f"      AND year BETWEEN {ilit(constants.HISTORY_START)} AND {ilit(train_until)}\n"
            f"      AND road_type_code IN (3, 4)\n"
            f"),\n"
            f"matched AS (SELECT a.*, u.road, u.seg FROM base a\n    {assign_join('geom')}\n    {ASSIGN_QUALIFY}\n)\n"
            f"SELECT road, seg, count(*) AS records, count(*) FILTER (WHERE case_type_code = 1) AS casualty_records,\n"
            f"       count(DISTINCT year) AS years_active,\n"
            f"       avg(CASE WHEN day_night_code = 5 THEN 1.0 WHEN day_night_code = 1 THEN 0.0 END) AS pct_night,\n"
            f"       avg(CASE WHEN single_carriageway_code BETWEEN 1 AND 4 THEN 1.0 WHEN dual_carriageway_code BETWEEN 1 AND 5 THEN 0.0 END) AS pct_single_carr,\n"
            f"       avg(CASE WHEN road_type_code = 3 THEN 1.0 ELSE 0.0 END) AS pct_at_junction,\n"
            f"       avg(CASE WHEN road_shape_code IN (4, 5) THEN 1.0 WHEN road_shape_code IN (1, 2, 3, 6, 7, 8, 10, 11) THEN 0.0 END) AS pct_curve,\n"
            f"       avg(CASE WHEN road_surface_code = 2 THEN 1.0 WHEN road_surface_code BETWEEN 1 AND 6 THEN 0.0 END) AS pct_wet_surface,\n"
            f"       avg(CASE WHEN speed_limit_code BETWEEN 1 AND 8 THEN speed_limit_code END) AS speed_mix\n"
            f"FROM matched GROUP BY road, seg ORDER BY road, seg")


STATIC_COLUMNS = ("road", "seg", "records", "casualty_records", "years_active", "pct_night", "pct_single_carr",
                  "pct_at_junction", "pct_curve", "pct_wet_surface", "speed_mix")


def fetch_adt_fill(ctx, train_until: int) -> dict:
    cols, rows = ctx.query(adt_median_sql(train_until))
    med, n = rows_safe(rows)[0]
    return {"value": float(med) if med is not None else 0.0, "unit_years": n,
            "rule": "median adt_asof over the units CTE with year <= train_until"}


def fetch_panel(ctx, y0: int, y1: int, adt_fill: float):
    cols, rows = ctx.query(panel_sql(y0, y1, adt_fill))
    return cols, rows_safe(rows)


def fetch_static(ctx, train_until: int) -> dict:
    """{(road, seg): {attr: value|None}} — frozen into meta.json as the contract's static block."""
    cols, rows = ctx.query(static_attrs_sql(train_until))
    safe = rows_safe(rows)
    assert list(cols) == list(STATIC_COLUMNS)
    return {(r[0], r[1]): dict(zip(cols[2:], r[2:])) for r in safe}


def matrix(cols, rows, static: dict):
    """The X/y arrays in the FEATURES order (plain lists; None = missing). Returns (X, y, years, keys, ksi)."""
    ci = {c: i for i, c in enumerate(cols)}
    X, y, years, keys, ksi = [], [], [], [], []
    for r in rows:
        key = (r[ci["road"]], r[ci["seg"]])
        s = static.get(key, {})
        X.append([
            r[ci["adt_asof"]], r[ci["adt_known"]], r[ci["lag1"]],
            s.get("pct_night"), s.get("pct_single_carr"), s.get("pct_at_junction"),
            s.get("pct_curve"), s.get("pct_wet_surface"), s.get("speed_mix"), s.get("years_active"),
            r[ci["year_idx"]],
        ])
        y.append(r[ci["y"]])
        years.append(r[ci["year"]])
        keys.append(key)
        ksi.append(r[ci["ksi"]])
    return X, y, years, keys, ksi


def shuffle_target(y, years, keys, train_until: int, seed: int):
    """The 'shuffled' preset: the TRAINING rows' targets permuted deterministically (holdout untouched).
    Order = sha256('{seed}:{road}:{seg}:{year}') — stable across Python versions and platforms."""
    idx = [i for i, yr in enumerate(years) if yr <= train_until]

    def h(i):
        r, s = keys[i]
        return hashlib.sha256(f"{seed}:{r}:{s}:{years[i]}".encode()).hexdigest()

    order = sorted(idx, key=h)
    values = [y[i] for i in order]
    out = list(y)
    for slot, value in zip(sorted(order), values):        # values in hash order fill the slots in index order
        out[slot] = value
    return out


def panel_summary(cols, rows):
    """Per-year [year, rows, sum_y, adt_known, static_assigned] for the training card and meta."""
    ci = {c: i for i, c in enumerate(cols)}
    by = {}
    for r in rows:
        e = by.setdefault(r[ci["year"]], [0, 0, 0, 0])
        e[0] += 1
        e[1] += r[ci["y"]]
        e[2] += r[ci["adt_known"]]
        e[3] += 1 if r[ci["geometry"]] == "static" else 0
    return [[yr, *by[yr]] for yr in sorted(by)]
