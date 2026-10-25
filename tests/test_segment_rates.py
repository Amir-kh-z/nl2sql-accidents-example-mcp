# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from nl2sql_roadsafety import __version__
from nl2sql_roadsafety.envelope import CREDIT, LAB_LINE
from nl2sql_roadsafety.sqlkit import rows_safe
from helpers import json_safe, png_of, run

Y = {"from_year": 2019, "to_year": 2021}
COLS = ["road", "seg", "name_from", "name_to", "km_from", "km_to", "accidents", "ksi_accidents", "accident_years",
        "unit_years", "vkm_millions", "rate_per_100m_vkm", "rate_lo", "rate_hi", "max_gap_years"]
ROW_2_20 = [2, 20, "מחלף ג", "צומת ד", 5.0, 7.5, 2, 2, 2, 2, 36.5, 5.48, 0.62, 19.78, 0]
ROW_1_10 = [1, 10, "צומת א", "צומת ב", 0.0, 10.0, 3, 1, 2, 3, 109.5, 2.74, 0.55, 8.01, 0]
ROW_1_11 = [1, 11, "צומת ב", "צומת ה", 9.5, 15.0, 1, 1, 1, 1, 10.0, 9.96, 0.13, 55.43, 1]


def test_rows_by_order(ctx):
    r = run(ctx, "segment_rates", view="table", **Y)
    assert r.kind == "table" and r.data["columns"] == COLS
    assert r.data["rows"] == [ROW_2_20, ROW_1_10, ROW_1_11]                    # rate_lo: 0.62, 0.55, 0.13
    assert run(ctx, "segment_rates", view="table", order_by="rate", **Y).data["rows"] == [ROW_1_11, ROW_2_20, ROW_1_10]
    assert run(ctx, "segment_rates", view="table", order_by="count", **Y).data["rows"] == [ROW_1_10, ROW_2_20, ROW_1_11]


def test_ksi_rates(ctx):
    rows = run(ctx, "segment_rates", view="table", severity="ksi", **Y).data["rows"]
    assert [row[:2] for row in rows] == [[2, 20], [1, 11], [1, 10]]
    assert rows[2][11:14] == [0.91, 0.01, 5.08]                                  # 1 KSI over 109.5 M vkm


def test_coverage_and_caveats(ctx):
    r = run(ctx, "segment_rates", view="chart", **Y)
    spec = r.data
    assert spec["coverage"]["matched"] == 6 and spec["coverage"]["total"] == 10 and spec["coverage"]["pct"] == 60.0
    assert spec["coverage"]["by_year"] == [[2019, 4, 3, 75.0], [2020, 3, 2, 66.7], [2021, 3, 1, 33.3]]
    assert spec["caveats"][0].startswith("כיסוי לפי שנה") and "33.3% (2021)" in spec["caveats"][0]
    assert "— יורד," in spec["caveats"][0] and "לא מונוטוני" not in spec["caveats"][0]     # 75.0, 66.7, 33.3
    one = run(ctx, "segment_rates", view="chart", from_year=2021, to_year=2021).data["caveats"][0]
    assert one == "כיסוי 33.3% (2021) — תאונות ללא מקטע תואם אינן בשני הצדדים"
    assert "לא מונוטוני" in run(ctx, "segment_rates", view="chart").data["caveats"][0]     # 0, 0, 75, 66.7, 33.3, 0, 0, 0
    assert any("ADT ≠ AADT" in c and "12.4–21.6%" in c for c in spec["caveats"])           # constants: no validation table in the fixture
    assert any("מדד תיאורי של התוסף" in c for c in spec["caveats"])
    assert all(";" not in c for c in spec["caveats"])
    assert spec["denominator"]["kind"] == "exposure" and spec["denominator"]["matched"] == 6
    assert "כיסוי 6 מתוך 10" in r.note and "\n" not in r.note
    assert spec["basis"].isascii() and spec["stamp"].isascii()
    assert spec["basis"] == ("segment_rates | road=all | severity=all | order=rate_lo | 2019-2021 | "
                             "top 3 of 3 segments | coverage 6/10 (60.0%)")
    assert spec["stamp"] == f"nl2sql-roadsafety-lab {__version__} | segment_rates | road=all | all | rate_lo | 2019-2021"
    png_of(spec)
    json_safe(r)
    # default years: the whole exposure layer; coverage counts every interurban casualty accident 2017-2024
    d = run(ctx, "segment_rates", view="table").data
    assert d["rows"] == [ROW_2_20, ROW_1_10, ROW_1_11]
    cov = run(ctx, "segment_rates", view="chart").data["coverage"]
    assert (cov["matched"], cov["total"]) == (6, 18)


def test_sql_face_is_the_statement_that_ran(ctx):
    spec = run(ctx, "segment_rates", view="chart", **Y).data
    assert "road_km / 10.0 <  u.km_to" in spec["sql"] and "QUALIFY row_number() OVER (PARTITION BY a.accident_id" in spec["sql"]
    assert "case_type_code = 1" in spec["sql"] and "traffic_adt_filled" not in spec["sql"]
    assert "a.road_km <> 0" in spec["sql"] and "arg_max(name_from, src_year)" in spec["sql"]   # km 0 = not coded; latest names
    assert rows_safe(ctx.query(spec["sql"])[1]) == spec["rows"]
    assert rows_safe(ctx.query(spec["coverage_sql"])[1]) == spec["coverage"]["by_year"]
    assert run(ctx, "segment_rates", view="sql", **Y).data == spec["sql"]


def test_road_filter_and_refusals(ctx):
    rows = run(ctx, "segment_rates", view="table", road=1, **Y).data["rows"]
    assert [row[:2] for row in rows] == [[1, 10], [1, 11]]
    one_road = run(ctx, "segment_rates", view="chart", road=1, **Y).data                # coverage of the road shown, not national
    assert (one_road["coverage"]["matched"], one_road["coverage"]["total"], one_road["coverage"]["pct"]) == (4, 7, 57.1)
    assert "בכביש 1" in one_road["denominator"]["label"] and "coverage 4/7 (57.1%)" in one_road["basis"]
    assert "road1_number = 1" in one_road["coverage_sql"]
    r = run(ctx, "segment_rates", road=3)
    assert r.kind == "markdown" and r.data.startswith("# ❌") and "אין נתוני תנועה" in r.data and "3" in r.data
    r = run(ctx, "segment_rates", from_year=2010)
    assert r.kind == "markdown" and r.data.startswith("# ❌") and "2017" in r.data
    assert run(ctx, "segment_rates", top_n=0).kind == "error"
    assert run(ctx, "segment_rates", top_n=31).kind == "error"
    assert run(ctx, "segment_rates", road=-1).kind == "error"
    assert "Unknown order_by" in run(ctx, "segment_rates", order_by="x").data


def test_chart_annotation_matches_the_plotted_metric():
    from nl2sql_roadsafety.actions.segment_rates import _annot
    row = [411, 10, "a", "b", 0.0, 1.0, 16, 10, 3, 6, 45.5, 21.99, 10.53, 40.43, 2]
    assert _annot(COLS, [row], "all") == ["16 · 45.5 M"]
    assert _annot(COLS, [row], "ksi") == ["10 KSI מתוך 16 · 45.5 M"]


def test_refuses_on_a_foreign_database(other_ctx):
    r = run(other_ctx, "segment_rates")
    assert r.kind == "markdown" and r.data.split("\n")[-1] == LAB_LINE and CREDIT not in r.data
