# -*- coding: utf-8 -*-
from __future__ import annotations

from nl2sql_roadsafety.sqlkit import rows_safe
from helpers import json_safe, png_of, run

Y = {"from_year": 2012, "to_year": 2021}


def test_threshold_rows(ctx):
    r = run(ctx, "weather_check", view="chart", **Y)
    assert r.kind == "chart", r.data
    assert r.data["rows"] == [["בהיר", 29, 1, 3.4, 25.0, 87.9, 6.9], ["גשום", 3, 2, 66.7, 14.0, 9.1, 100.0],
                              ["לא ידוע", 1, 1, 100.0, 18.0, 3.0, 100.0]]
    assert any("סף גשם: 0.1" in c and "עולה ל-100.0%" in c for c in r.data["caveats"])
    nothing = run(ctx, "weather_check", from_year=2022, to_year=2024, view="chart")     # no cell at all: a card, not a blank chart
    assert nothing.kind == "markdown" and nothing.data.startswith("# ❌") and "2022–2024" in nothing.data
    assert "weather_check" in nothing.data
    at_zero = run(ctx, "weather_check", rain_threshold_mm="0", view="chart", **Y).data
    assert not any("עולה ל-" in c for c in at_zero["caveats"])
    assert rows_safe(ctx.query(r.data["sql"])[1]) == r.data["rows"]
    png_of(r.data)
    json_safe(r)
    zero = run(ctx, "weather_check", rain_threshold_mm="0", view="table", **Y).data["rows"]
    assert [row[3] for row in zero] == [6.9, 100.0, 100.0]
    one = run(ctx, "weather_check", rain_threshold_mm="1", view="table", **Y).data["rows"]
    assert [row[3] for row in one] == [0.0, 33.3, 0.0]


def test_coverage_caveats(ctx):
    d = run(ctx, "weather_check", view="chart").data                      # 2005-2024 defaults
    assert d["years_without_cell"] == [2022, 2023, 2024]
    assert d["caveats"][0] == "שנים ללא תא מזג אוויר: 2022, 2023, 2024 (10 תאונות הושמטו)"
    assert d["caveats"][1].startswith("2 מתוך 35")                        # A6 and the P3 sentinel row Z1 carry no cell
    assert any(c.startswith("'לא ידוע'") and "100.0%" in c for c in d["caveats"])
    assert any("סף גשם: 0.1" in c and "100.0%" in c for c in d["caveats"])
    assert all(";" not in c for c in d["caveats"])
    assert d["basis"].isascii() and d["stamp"].isascii() and "33 with cell of 45" in d["basis"]   # 45: incl. the P3 sentinel row Z1
    assert d["rows"] == run(ctx, "weather_check", view="table", **Y).data["rows"]      # same rows: 2022+ have no cell
    assert run(ctx, "weather_check", rain_threshold_mm="2").kind == "error"
