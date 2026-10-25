# -*- coding: utf-8 -*-
"""heat_matrix: the zero-filled 7×24 grid — 168 rows always, unknown hour/day counted, never a hole."""
from __future__ import annotations

from nl2sql_roadsafety.sqlkit import rows_safe
from helpers import json_safe, png_of, run


def test_zero_filled_grid_and_unknown_exclusion(ctx):
    r = run(ctx, "heat_matrix", from_year=2005, to_year=2024, view="chart")
    assert r.kind == "chart", r.data
    spec = r.data
    assert spec["type"] == "accidents/heat_matrix"
    assert spec["columns"] == ["day_of_week", "hour_of_day", "accidents"]
    rows = spec["rows"]
    assert len(rows) == 168
    assert [(row[0], row[1]) for row in rows] == [(d, h) for d in range(1, 8) for h in range(24)]
    # 45 casualty accidents in the fixture; A5 (the weather-9 row) carries a NULL hour → 44 placed + 1 excluded
    assert sum(row[2] for row in rows) == 44 and spec["unknown_hour_excluded"] == 1
    nonzero = {(row[0], row[1]): row[2] for row in rows if row[2]}
    assert nonzero[(6, 10)] == 8 and nonzero[(2, 10)] == 7 and nonzero[(1, 22)] == 1
    assert len(nonzero) == 10                       # every other cell is a REAL zero, not a hole
    assert spec["day_labels"] == ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
    assert spec["caveats"][0] == "1 תאונות ללא שעה או יום תקינים הוחרגו מהמטריצה (2.2% מהטווח)"
    assert any("ספירות אינן סיכון" in c for c in spec["caveats"])
    assert all(";" not in c for c in spec["caveats"])
    assert spec["denominator"]["kind"] == "counts"
    assert spec["denominator"]["label"] == "ספירות תאונות עם נפגעים — ללא מכנה חשיפה"
    assert spec["basis"] == ("heat_matrix | 2005-2024 | 7x24 grid, 168 cells | 44 accidents placed | "
                             "unknown hour/day excluded: 1")
    assert spec["basis"].isascii() and spec["stamp"].isascii()
    png_of(spec)
    json_safe(r)


def test_faces_and_the_clean_range_caveat(ctx):
    t = run(ctx, "heat_matrix", view="table").data                 # default 2015-2024
    assert len(t["rows"]) == 168 and sum(row[2] for row in t["rows"]) == 29
    sql = run(ctx, "heat_matrix", view="sql").data
    assert "case_type_code = 1" in sql and "range(1, 8)" in sql and "LEFT JOIN" in sql
    spec = run(ctx, "heat_matrix", from_year=2005, to_year=2024, view="chart").data
    assert rows_safe(ctx.query(spec["sql"])[1]) == spec["rows"]    # the spec's SQL reproduces its rows
    clean = run(ctx, "heat_matrix", from_year=2019, to_year=2021, view="chart").data
    assert clean["unknown_hour_excluded"] == 0                     # no unknown-hour row in this range
    assert clean["caveats"][0] == "לכל התאונות בטווח שעה ויום ידועים — אף תאונה לא הוחרגה"
    assert len(clean["rows"]) == 168                               # the grid never shrinks


def test_refusals_and_errors(ctx):
    assert run(ctx, "heat_matrix", to_year=2030).data.startswith("# ❌")
    assert run(ctx, "heat_matrix", from_year=2024, to_year=2015).kind == "error"
    assert run(ctx, "heat_matrix", view="nope").kind == "error"
