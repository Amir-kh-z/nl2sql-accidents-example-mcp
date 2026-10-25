# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from nl2sql_roadsafety.sqlkit import rows_safe
from helpers import json_safe, png_of, run

EB_ORDER = [(2022, 6, 0.075), (2019, 8, 0.1167), (2023, 4, 0.125), (2017, 6, 0.1524), (2020, 6, 0.1545),
            (2016, 6, 0.2), (2018, 6, 0.2455), (2019, 0, 0.32), (2016, 5, 0.3667), (2021, 9, 0.5571)]


def test_eb_ranking_and_tiers(ctx):
    r = run(ctx, "vehicle_cells_ranking", view="chart")
    spec = r.data
    assert spec["group"] == "cell"                       # the P13 frontend switch, default mode
    ci = {c: spec["columns"].index(c) for c in spec["columns"]}
    assert [(row[ci["manufacture_year"]], row[ci["cc_band"]], row[ci["eb_rate_per_mkm"]]) for row in spec["rows"]] == EB_ORDER
    tiers = [row[ci["tier"]] for row in spec["rows"]]
    assert tiers == ["safest"] * 2 + ["regular"] * 6 + ["highest_risk"] * 2
    assert spec["global_rate"] == 0.2 and spec["tiers"] == {"safest": 2, "regular": 6, "highest_risk": 2}
    band0 = next(row for row in spec["rows"] if row[ci["cc_band"]] == 0)
    assert band0[ci["raw_rate_per_mkm"]] == 0.8 and band0[ci["tier"]] == "regular"
    assert band0[ci["cc_band_label"]] == "חשמלי/ללא נפח (קוד 0)" and band0[ci["ev_share"]] == 0.1
    assert spec["excluded"] == {"cells": 2, "fleet": 1500, "y0": 2025, "y1": 2026, "band0_cells": 1,
                                "band0_fleet": 10000, "fleet_all": 101500}
    assert spec["caveats"][0].startswith("2 תאים") and "1,500" in spec["caveats"][0]
    assert any("נפח מנוע 0" in c and "ev_share 10%" in c for c in spec["caveats"])
    assert not any("הושמטו לפי בחירה" in c for c in spec["caveats"])
    assert "tiers 2/6/2" in spec["basis"] and spec["basis"].isascii() and spec["stamp"].isascii()
    assert all(";" not in c for c in spec["caveats"])
    png_of(spec)
    json_safe(r)


def test_metrics(ctx):
    ksi = run(ctx, "vehicle_cells_ranking", metric="ksi", view="table").data["rows"]
    assert ksi[0][8] == 0.02 and [row[:2] for row in ksi] == [list(e[:2]) for e in EB_ORDER]
    fatal = run(ctx, "vehicle_cells_ranking", metric="fatal", view="table").data["rows"]
    assert fatal[0][:2] == [2022, 6] and fatal[-1][:2] == [2021, 9] and fatal[-2][:2] == [2019, 0]
    assert fatal[-1][11] == "highest_risk" and fatal[-2][11] == "highest_risk"


def test_cohort_rollup_math_and_contract(ctx):
    """P13: the cohort face — cells summed over cc_band per manufacture_year, EB by hand on the sums.
    2016 = bands 5+6: events 400+800 = 1200, exposure 1000+4000 = 5000 Mkm, raw 0.24,
    EB = (1200 + 200·0.2) / (5000 + 200) = 1240/5200 = 0.2385."""
    r = run(ctx, "vehicle_cells_ranking", group="cohort", view="chart")
    spec = r.data
    assert spec["group"] == "cohort"
    assert spec["columns"] == ["manufacture_year", "involvements", "exposure_mkm", "rate", "eb_rate", "tier"]
    years = [row[0] for row in spec["rows"]]
    assert years == [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023]        # year asc, zero-exposure years out
    by = {row[0]: row for row in spec["rows"]}
    assert by[2016][1:5] == [1200, 5000.0, 0.24, 0.2385]                    # the hand-pinned sum of two bands
    assert by[2019][1:3] == [140, 1050.0]                                   # band 0 (50 Mkm, 40 ev) INCLUDED here
    assert by[2021][5] == "highest_risk" and by[2022][5] == "safest" and by[2023][5] == "safest"
    assert spec["global_rate"] == 0.2                                       # same prior as cell mode (same cells)
    assert spec["tiers"] == {"safest": 2, "regular": 5, "highest_risk": 1}
    assert any("לא צי × שנים" in c for c in spec["caveats"])                # the honest-denominator line
    assert any("נכללים בתוך העוקבות" in c for c in spec["caveats"])         # band 0 named, not hidden
    assert all(";" not in c for c in spec["caveats"])
    assert "group=cohort" in spec["basis"] and spec["basis"].isascii() and spec["stamp"].isascii()
    assert spec["denominator"]["kind"] == "exposure" and "8 עוקבות" in spec["denominator"]["label"]
    assert rows_safe(ctx.query(spec["sql"])[1]) == spec["rows"]
    png_of(spec)
    json_safe(r)


def test_cohort_known_engine_drops_band0_first(ctx):
    d = run(ctx, "vehicle_cells_ranking", group="cohort", bands="known_engine", view="chart").data
    by = {row[0]: row for row in d["rows"]}
    assert by[2019][1:3] == [100, 1000.0]                                   # the band-0 cell left BEFORE the sum
    # EB by hand on the reduced prior: g = 3110/15700, (100 + 200·g)/1200 = 0.1163
    assert by[2019][4] == 0.1163
    assert d["global_rate"] == pytest.approx(0.19809, abs=1e-5)
    assert any("הושמטו לפי בחירה" in c for c in d["caveats"])               # the existing band-0 caveat, kept
    assert d["denominator"]["dropped_band0"] == 1
    assert "cc_band <> 0" in d["sql"]


def test_known_engine_bands(ctx):
    d = run(ctx, "vehicle_cells_ranking", bands="known_engine", view="chart").data
    assert len(d["rows"]) == 9 and all(row[1] != 0 for row in d["rows"])
    assert d["global_rate"] == pytest.approx(0.19809, abs=1e-5)
    assert not any(c.startswith("נפח מנוע 0") for c in d["caveats"])
    assert any("1 תאי נפח מנוע 0" in c and "הושמטו לפי בחירה" in c and "9.9%" in c for c in d["caveats"])
    assert "ועוד 1 תאי נפח 0" in d["denominator"]["label"] and d["denominator"]["dropped_band0"] == 1
    assert "cc_band <> 0" in d["sql"]
    assert rows_safe(ctx.query(d["sql"])[1]) == d["rows"]
    assert run(ctx, "vehicle_cells_ranking", metric="x").kind == "error"
