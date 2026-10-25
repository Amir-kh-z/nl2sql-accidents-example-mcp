# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from nl2sql_roadsafety import __version__
from nl2sql_roadsafety.actions.trend import _caveats
from nl2sql_roadsafety.charts import PNG_CAVEAT_CAP
from nl2sql_roadsafety.envelope import CAVEAT_DATA_END, CREDIT, LAB_LINE
from nl2sql_roadsafety.sqlkit import rows_safe
from helpers import json_safe, png_of, run

Y = {"from_year": 2022, "to_year": 2024}


def _by_year(ctx, measure, road_type="all"):
    r = run(ctx, "trend", measure=measure, road_type=road_type, view="table", **Y)
    assert r.kind == "table", r.data
    return {row[0]: row[1] for row in r.data["rows"]}, r


@pytest.mark.parametrize("measure,road,expected", [
    ("accidents", "all", {2022: 2, 2023: 2, 2024: 6}),
    ("accidents", "urban", {2022: 1, 2023: 1, 2024: 2}),
    ("accidents", "nonurban", {2022: 1, 2023: 1, 2024: 3}),
    ("fatal_accidents", "all", {2022: 0, 2023: 1, 2024: 1}),
    ("fatal_accidents", "urban", {2022: 0, 2023: 0, 2024: 1}),
    ("fatal_accidents", "nonurban", {2022: 0, 2023: 1, 2024: 0}),
    ("killed", "all", {2022: None, 2023: 1, 2024: 2}),
    ("killed", "urban", {2022: None, 2023: 0, 2024: 2}),
    ("killed", "nonurban", {2022: 0, 2023: 1, 2024: 0}),
    ("severe_injured", "all", {2022: None, 2023: 0, 2024: 1}),
    ("slight_injured", "all", {2022: None, 2023: 1, 2024: 6}),
    ("slight_injured", "urban", {2022: None, 2023: 1, 2024: 2}),
    ("slight_injured", "nonurban", {2022: 0, 2023: 0, 2024: 3}),
])
def test_yearly_values(ctx, measure, road, expected):
    got, _ = _by_year(ctx, measure, road)
    assert got == expected


def test_columns_and_coverage_flags(ctx):
    _, r = _by_year(ctx, "killed")
    assert r.data["columns"] == ["year", "killed", "people", "casualty_accidents", "covered"]
    row2022 = next(row for row in r.data["rows"] if row[0] == 2022)
    assert row2022 == [2022, None, 1, 2, False]
    _, r = _by_year(ctx, "accidents")
    assert r.data["columns"] == ["year", "accidents"]


def test_monthly_zero_fill(ctx):
    r = run(ctx, "trend", measure="accidents", granularity="month", from_year=2024, to_year=2024, view="table")
    rows = r.data["rows"]
    assert len(rows) == 12
    assert {(row[0], row[1]): row[2] for row in rows} == {(2024, m): {1: 2, 2: 1, 3: 2, 5: 1}.get(m, 0)
                                                          for m in range(1, 13)}
    r = run(ctx, "trend", measure="killed", granularity="month", from_year=2024, to_year=2024, view="table")
    assert [row[2] for row in r.data["rows"]] == [2] + [0] * 11
    assert all(row[-1] is True for row in r.data["rows"])
    r = run(ctx, "trend", measure="killed", granularity="month", from_year=2022, to_year=2022, view="table")
    by_month = {row[1]: (row[2], row[-1]) for row in r.data["rows"]}
    assert by_month[11] == (0, True) and by_month[12] == (None, False)


def test_gap_caveat_leads_and_note_mentions_it(ctx):
    r = run(ctx, "trend", measure="killed", view="chart", **Y)
    spec = r.data
    assert spec["gap_periods"] == ["2022"]
    assert "2022: 1 רשומות מול 2 תאונות" in spec["caveats"][0]
    assert "2022" in r.note
    assert r.note.startswith("מכנה:") and "\n" not in r.note
    png_of(spec)
    json_safe(r)


def test_sql_face_is_the_statement_that_ran(ctx):
    chart = run(ctx, "trend", measure="killed", road_type="urban", view="chart", **Y)
    spec = chart.data
    assert "case_type_code = 1" in spec["sql"]
    assert "JOIN accidents a ON a.accident_id = i.accident_id AND a.case_type_code = i.case_type_code" in spec["sql"]
    assert rows_safe(ctx.query(spec["sql"])[1]) == spec["rows"]
    assert run(ctx, "trend", measure="killed", road_type="urban", view="sql", **Y).data == spec["sql"]
    assert run(ctx, "trend", measure="killed", road_type="urban", view="table", **Y).data["rows"] == spec["rows"]


def test_coercion_and_errors(ctx):
    r = run(ctx, "trend", from_year="2023", to_year=2024.0, view="table")
    assert r.kind == "table" and [row[0] for row in r.data["rows"]] == [2023, 2024]
    r = run(ctx, "trend", from_year="abc", to_year=2024)
    assert r.kind == "error" and "from_year" in r.data
    r = run(ctx, "trend", from_year=2024, to_year=2022)
    assert r.kind == "error" and "swap" in r.data
    r = run(ctx, "trend", measure="bogus", **Y)
    assert r.kind == "error" and {"accidents", "killed", "severe_injured", "slight_injured",
                                  "fatal_accidents"} <= set(r.data.replace(",", " ").replace(".", " ").split())
    r = run(ctx, "trend", view="png", **Y)
    assert r.kind == "error" and "chart" in r.data and "sql" in r.data


def test_out_of_coverage_is_a_refusal_card(ctx):
    r = run(ctx, "trend", from_year=2022, to_year=2030)
    assert r.kind == "markdown" and r.data.startswith("# ❌") and "2030" in r.data and "2005 ל-2024" in r.data
    r = run(ctx, "trend", from_year=2000, to_year=2024)
    assert r.kind == "markdown" and r.data.startswith("# ❌") and "2000" in r.data


def test_covid_and_road_caveats(ctx):
    long = run(ctx, "trend", from_year=2005, to_year=2024, view="table").data
    assert any("קורונה" in c for c in run(ctx, "trend", from_year=2005, to_year=2024, view="chart").data["caveats"])
    short = run(ctx, "trend", view="chart", **Y).data["caveats"]
    assert not any("קורונה" in c for c in short)
    assert not any("road_type_code" in c for c in short)
    urban = run(ctx, "trend", road_type="urban", view="chart", **Y).data["caveats"]
    assert any("1 תאונות עם קוד דרך אחר" in c for c in urban)
    urban23 = run(ctx, "trend", road_type="urban", from_year=2022, to_year=2023, view="chart").data["caveats"]
    assert any("סכום שניהם" in c for c in urban23)
    for cav in (short, urban, urban23):
        assert all(";" not in c for c in cav)


def test_six_caveats_keep_the_gap_first(ctx):
    unit = _caveats("killed", "urban", 2020, 2024, [("2022", 0, 1)], other_roads=1)
    assert len(unit) == 6 and unit[0].startswith("נתוני נפגעים") and 0 < PNG_CAVEAT_CAP
    r = run(ctx, "trend", measure="killed", road_type="urban", from_year=2020, to_year=2024, view="chart")
    spec = r.data
    assert len(spec["caveats"]) == 6
    assert spec["caveats"][0].startswith("נתוני נפגעים") and "2022: 0 רשומות מול 1 תאונות" in spec["caveats"][0]
    assert spec["caveats"][1] == CAVEAT_DATA_END
    png_of(spec)


def test_basis_and_stamp_are_ascii(ctx):
    spec = run(ctx, "trend", view="chart", **Y).data
    assert spec["basis"] == "killed by year | road_type=all | 2022-2024 | 3 rows | involved WHERE case_type_code = 1"
    assert spec["stamp"] == f"nl2sql-roadsafety-lab {__version__} | killed / year / all | 2022-2024"
    assert spec["basis"].isascii() and spec["stamp"].isascii()


def test_refuses_on_a_foreign_database(other_ctx):
    r = run(other_ctx, "trend")
    assert r.kind == "markdown" and r.title == "מגמה"
    lines = r.data.split("\n")
    assert lines[-1] == LAB_LINE and CREDIT not in r.data
    assert "no table named accidents" in r.data
    assert "\n" not in r.note
