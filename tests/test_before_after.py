# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from nl2sql_roadsafety.envelope import CREDIT, LAB_LINE
from helpers import json_safe, png_of, run

SITE = {"site": "road:1/0-10", "change_year": 2015}


def _rows(r):
    return {row[0]: row for row in r.data["rows"]}


def test_defaults_give_na_on_the_thin_casualty_cell(ctx):
    r = run(ctx, "before_after", view="chart", **SITE)
    assert r.kind == "chart", r.data
    rows = _rows(r)
    assert rows["casualty"][1:7] == [8, 2, 0.25, 16, 8, 0.5] and rows["casualty"][-1] == "n/a"
    assert rows["damage_only"][1:7] == [6, 6, 1.0, 12, 12, 1.0]
    assert rows["damage_only"][7:11] == [1.0, 0.2617, 3.8206, "ok"]
    assert rows["double"][-1] == "n/a"
    spec = r.data
    assert spec["control_flag"] is True and spec["coding_share"] == {"before": 1.0, "after": 0.6667, "kind": "road"}
    assert spec["caveats"][0].startswith("בקרה מסומנת") and "100.0%" in spec["caveats"][0] and "66.7%" in spec["caveats"][0]
    assert spec["caveats"][1].startswith("תא דק")
    assert spec["site_label"] == "כביש 1 ק״מ 0–10 · צומת א ← צומת ב"          # ← points toward name_to in RTL
    assert spec["counts"] == {"casualty": [8, 2, 16, 8], "damage_only": [6, 6, 12, 12]}
    assert "double n/a" in spec["basis"] and spec["basis"].isascii() and spec["stamp"].isascii()
    assert all(";" not in c for c in spec["caveats"])
    png_of(spec)
    json_safe(r)


def test_min_cell_two_gives_the_double_ratio(ctx):
    r = run(ctx, "before_after", min_cell=2, view="chart", **SITE)
    rows = _rows(r)
    assert rows["casualty"][7:11] == [0.5, 0.0975, 2.5648, "ok"]
    assert rows["double"][7:11] == [0.5, 0.0604, 4.1417, "ok"]
    assert r.data["double"]["se2"] == pytest.approx(0.6959 + 0.467692, abs=1e-4)
    assert "יחס כפול 0.500" in r.data["headline"]
    assert not any(c.startswith("תא דק") for c in r.data["caveats"])
    png_of(r.data)


def test_windows_one_and_two(ctx):
    rows = _rows(run(ctx, "before_after", window_years=1, min_cell=1, view="table", **SITE))
    assert rows["casualty"][1:7] == [2, 1, 0.5, 4, 3, 0.75] and rows["casualty"][7] == 0.6667
    assert rows["double"][7] == 0.6667
    r = run(ctx, "before_after", window_years=2, min_cell=2, view="table", **SITE)
    rows = _rows(r)
    assert rows["casualty"][-1] == "n/a" and rows["damage_only"][7] == 1.0
    assert "75.0%" in r.note and "בקרה מסומנת" not in r.note          # 100 → 75 is exactly 25 %: not flagged


def test_junction_sites(ctx):
    r = run(ctx, "before_after", site="njunction:433", change_year=2015, min_cell=3, view="chart")
    rows = _rows(r)
    assert rows["casualty"][1:7] == [4, 3, 0.75, 16, 8, 0.5] and rows["casualty"][7] == 1.5
    assert rows["damage_only"][7] == 1.0 and rows["double"][7] == 1.5
    assert r.data["site_label"] == "צומת 433 · צומת העשור"          # deduped dimension: one label
    assert r.data["control_flag"] is False
    r = run(ctx, "before_after", site="ujunction:5000/777", change_year=2015, min_cell=1, view="table")
    rows = _rows(r)
    assert rows["casualty"][7] == 1.3333 and rows["damage_only"][-1] == "n/a" and rows["double"][-1] == "n/a"


def test_refusals_and_errors(ctx, other_ctx):
    r = run(ctx, "before_after", site="road:77/0-1", change_year=2015)
    assert r.kind == "markdown" and r.data.startswith("# ❌") and "לא נמצאו תאונות" in r.data
    r = run(ctx, "before_after", change_year=2023)
    assert r.kind == "markdown" and r.data.startswith("# ❌") and "2020–2026" in r.data
    r = run(ctx, "before_after", change_year=2007)
    assert r.kind == "markdown" and r.data.startswith("# ❌")
    assert run(ctx, "before_after", window_years=4).kind == "error"
    assert run(ctx, "before_after", min_cell=0).kind == "error"
    for bad in ("road:60/98.8-96.0", "road:60/-5-10", "road:60/96-96", "njunction:0", "njunction:99", "ujunction:5000", "foo"):
        assert run(ctx, "before_after", site=bad).kind == "error", bad
    r = run(other_ctx, "before_after")
    assert r.kind == "markdown" and r.data.split("\n")[-1] == LAB_LINE and CREDIT not in r.data


def test_sql_face_matches_counts(ctx):
    spec = run(ctx, "before_after", min_cell=2, view="chart", **SITE).data
    cells = {(int(row[0]), row[1]): row for row in ctx.query(spec["sql"])[1]}
    assert cells[(1, "before")][2:4] == (8, 16) and cells[(1, "after")][2:4] == (2, 8)
    assert cells[(3, "before")][2:4] == (6, 12) and cells[(3, "after")][2:4] == (6, 12)
    assert "case_type_code IN (1, 3)" in spec["sql"] and "road1_number = 1" in spec["sql"]
    assert run(ctx, "before_after", min_cell=2, view="sql", **SITE).data == spec["sql"]
