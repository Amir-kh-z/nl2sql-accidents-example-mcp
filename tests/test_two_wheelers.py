# -*- coding: utf-8 -*-
"""two_wheelers on the planted fleet: the fleet-driven zero-filled grid, the rate arithmetic, the counts-only
rows, the era refusal, and the two traps (a damage-series motorcycle and a pre-era one never count)."""
from __future__ import annotations

from helpers import json_safe, run


def _split(rows):
    moto = [r for r in rows if r[5] is not None]
    counts = [r for r in rows if r[5] is None]
    return moto, counts


def test_rates_grid_and_counts(ctx):
    r = run(ctx, "two_wheelers", from_year=2019, to_year=2021, view="table")
    assert r.kind == "table", r.data
    moto, counts = _split(r.data["rows"])
    assert len(moto) == 12                                                   # 3 years x 4 bands, zero-filled
    by = {(row[0], row[2]): row for row in moto}
    assert by[(2019, 9)][3:] == [2, 1, 1000, 2.0, 1.0]                       # S1 + S2 (fatal) on fleet 1,000
    assert by[(2020, 9)][3:5] == [3, 0] and by[(2020, 9)][6] == 3.0
    assert by[(2021, 9)][3:5] == [1, 1] and by[(2021, 9)][6] == 1.0
    assert by[(2019, 19)][3] == 1 and by[(2019, 19)][6] == 2.0               # fleet 500
    assert by[(2020, 19)][3] == 0 and by[(2020, 19)][6] == 0.0               # a zero-accident cell IS a rate
    assert all(by[(y, b)][3] == 0 for y in (2019, 2020, 2021) for b in (8, 10))   # fleet, never an accident
    assert sum(row[3] for row in moto) == 8                                  # the case-3 and 2012 traps never count
    assert {(row[0], row[2], row[3]) for row in counts} == {(2019, 15, 1), (2021, 15, 1), (2020, 23, 1),
                                                            (2019, 21, 1)}
    assert all(row[6] is None and row[7] is None for row in counts)          # counts-only rows carry no rate
    json_safe(r)


def test_chart_and_scope_computed_caveats(ctx):
    r = run(ctx, "two_wheelers", from_year=2019, to_year=2021)
    assert r.kind == "chart" and r.data["png_base64"]
    assert any("4" in c and "ספירות בלבד" in c for c in r.data["caveats"])   # 4 count-only involvements in scope
    assert any("8" in c and "מעורבויות אופנוע" in c for c in r.data["caveats"])
    narrow = run(ctx, "two_wheelers", from_year=2020, to_year=2021)
    assert any("2" in c and "ספירות בלבד" in c for c in narrow.data["caveats"])   # the numbers move with the scope
    fatal = run(ctx, "two_wheelers", metric="fatal", from_year=2019, to_year=2021)
    assert fatal.kind == "chart" and "fatal" in fatal.data["basis"]
    json_safe(r)


def test_era_and_range_refusals(ctx):
    assert run(ctx, "two_wheelers", from_year=2012, to_year=2021).data.startswith("# ❌")
    assert run(ctx, "two_wheelers", from_year=2021, to_year=2019).kind == "error"
    assert run(ctx, "two_wheelers", metric="nope").kind == "error"


def test_sql_face_carries_both_statements(ctx):
    """The sql face must reproduce the WHOLE answer — the grid AND the counts-only statement (sweep finding)."""
    r = run(ctx, "two_wheelers", from_year=2019, to_year=2021, view="sql")
    assert r.kind == "sql"
    assert "case_type_code = 1" in r.data and "fleet_motorcycles" in r.data
    assert "IN (15, 21, 23)" in r.data.replace("(15,21,23)", "(15, 21, 23)")  # the counts statement is exposed
    assert "traffic_adt_filled" not in r.data
