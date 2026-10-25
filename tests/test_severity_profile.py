# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from nl2sql_roadsafety.sqlkit import rows_safe
from helpers import json_safe, png_of, run


def _rows(ctx, by, **kw):
    r = run(ctx, "severity_profile", by=by, view="table", **kw)
    assert r.kind == "table", r.data
    return {row[0]: (row[2], row[3], row[4], row[5]) for row in r.data["rows"]}, r


@pytest.mark.parametrize("by,expected", [
    # (+1 slight driver in 2016 since P3: the 99999999 sentinel-junction row Z1 — a casualty like any other here)
    ("casualty_type", {2: (33, 4, 2, 27), 1: (5, 2, 2, 1), 3: (5, 0, 2, 3), 4: (3, 1, 1, 1), 6: (1, 0, 0, 1)}),
    ("involved_vehicle_type", {1: (34, 4, 4, 26), -1: (5, 2, 2, 1), 9: (2, 1, 0, 1), 2: (1, 0, 0, 1), 3: (1, 0, 0, 1),
                               10: (1, 0, 1, 0), 11: (1, 0, 0, 1), 12: (1, 0, 0, 1), 15: (1, 0, 0, 1)}),
    ("road_type", {4: (23, 4, 4, 15), 1: (10, 2, 1, 7), 3: (9, 0, 2, 7), 2: (4, 1, 0, 3), 5: (1, 0, 0, 1)}),
    ("day_night", {1: (44, 7, 5, 32), 5: (3, 0, 2, 1)}),
    ("weather", {1: (43, 7, 4, 32), 2: (3, 0, 3, 0), 9: (1, 0, 0, 1)}),
    ("sex", {1: (39, 5, 5, 29), 2: (8, 2, 2, 4)}),
    # P13 accident-attribute dims — the fixture's deterministic rules (conftest _acc_row):
    # lighting: NULL light on the weather-9 row A5 → the explicit 'לא ידוע' bucket
    ("lighting", {1: (43, 7, 5, 31), 3: (3, 0, 2, 1), None: (1, 0, 0, 1)}),
    # hour buckets: 10:30 rows → בוקר (1), 22:30 rows → ערב (3), A5's NULL hour → key 9 'לא ידוע'
    ("hour_of_day", {1: (43, 7, 5, 31), 3: (3, 0, 2, 1), 9: (1, 0, 0, 1)}),
    ("day_of_week", {1: (6, 0, 2, 4), 2: (10, 4, 0, 6), 3: (4, 1, 0, 3), 4: (6, 0, 3, 3), 5: (7, 1, 1, 5),
                     6: (10, 1, 1, 8), 7: (4, 0, 0, 4)}),
    # speed limit: the rt-5 row carries sentinel 0 → 'לא ידוע', included, never dropped
    ("speed_limit", {4: (32, 4, 6, 22), 1: (14, 3, 1, 10), 0: (1, 0, 0, 1)}),
    # road shape: rt-3 rows carry code 9 'אחר' (its own category), the rt-5 row a NULL shape
    ("road_shape", {5: (23, 4, 4, 15), 8: (14, 3, 1, 10), 9: (9, 0, 2, 7), None: (1, 0, 0, 1)}),
])
def test_dimension_rows(ctx, by, expected):
    got, r = _rows(ctx, by)
    assert got == expected
    assert sum(v[0] for v in got.values()) == 47                # 2022 uncovered → dropped (+1: the 2016 sentinel row Z1)
    json_safe(r)


def test_by_year_is_the_share_drift_exhibit(ctx):
    """P11: severity composition per year — chronological order (never by size), the coverage rule intact,
    and the share-drift caveat that explains the severity gate's design."""
    r = run(ctx, "severity_profile", by="year", view="table")
    rows = r.data["rows"]
    years = [row[0] for row in rows]
    assert years == sorted(years) and 2022 not in years          # time axis, uncovered year dropped
    assert all(row[1] == str(row[0]) for row in rows)            # labels are the year strings
    assert sum(row[2] for row in rows) == 47                     # same census as every other dimension
    assert all(row[3] + row[4] + row[5] == row[2] for row in rows)
    spec = run(ctx, "severity_profile", by="year", view="chart").data
    assert any("נדידת שיעורים" in c and "הפרדה ולא כיול" in c for c in spec["caveats"])
    assert all(";" not in c for c in spec["caveats"])
    png_of(spec)
    json_safe(r)


def test_pedestrian_bucket_agrees_across_dimensions(ctx):
    by_type, _ = _rows(ctx, "casualty_type")
    by_veh, _ = _rows(ctx, "involved_vehicle_type")
    assert by_type[1] == by_veh[-1] == (5, 2, 2, 1)             # A7 carries vehicle code 1 but is a pedestrian


def test_age_labels_come_from_the_plugin_map(ctx):
    r = run(ctx, "severity_profile", by="age_group", view="table")
    labels = {row[0]: row[1] for row in r.data["rows"]}
    assert labels[2] == "5–9" and labels[7] == "30–34" and labels[99] == "לא ידוע" and labels[5] == "20–24"
    assert {row[0]: row[2] for row in r.data["rows"]}[5] == 29
    assert "05-ספטמבר" not in r.data["rows"].__repr__()


def test_coverage_rule_and_caveats(ctx):
    r = run(ctx, "severity_profile", view="chart")
    spec = r.data
    assert spec["uncovered_years"] == [2022]
    assert spec["caveats"][0].startswith("נתוני נפגעים") and "2022: 1 רשומות מול 2 תאונות" in spec["caveats"][0]
    assert all(";" not in c for c in spec["caveats"])
    assert spec["basis"] == ("severity_profile | by=casualty_type | display=shares | 2005-2024 | 5 rows | "
                             "uncovered years: 2022 | "
                             "involved WHERE case_type_code = 1 AND injury_severity_code IN (1, 2, 3)")
    assert spec["basis"].isascii() and spec["stamp"].isascii()
    png_of(spec)
    late = run(ctx, "severity_profile", from_year=2023, to_year=2024, view="table").data["rows"]
    assert len(late) == 1 and late[0][2] == 11 and late[0][6] == 100.0


def test_new_dimension_labels_orders_and_sentinels(ctx):
    """P13: label sources, chronological time-like axes, and the sentinel discipline — an unknown code is an
    explicit 'לא ידוע' bucket, never a silent drop (the census stays 47 in every dimension)."""
    r = run(ctx, "severity_profile", by="lighting", view="table")
    labels = {row[0]: row[1] for row in r.data["rows"]}
    assert labels[None] == "לא ידוע" and labels[1] == "אור יום רגיל"     # NULL light_code → explicit bucket
    r = run(ctx, "severity_profile", by="hour_of_day", view="table")
    assert [row[0] for row in r.data["rows"]] == [1, 3, 9]               # chronological, unknown (9) last
    hl = {row[0]: row[1] for row in r.data["rows"]}
    assert hl[1] == "בוקר (6–11)" and hl[3] == "ערב (18–23)" and hl[9] == "לא ידוע"
    r = run(ctx, "severity_profile", by="day_of_week", view="table")
    assert [row[0] for row in r.data["rows"]] == [1, 2, 3, 4, 5, 6, 7]   # ראשון..שבת, never by size
    assert {row[0]: row[1] for row in r.data["rows"]}[7] == "שבת"
    sp, _ = _rows(ctx, "speed_limit")
    assert 0 in sp and sum(v[0] for v in sp.values()) == 47              # sentinel bucket present, no drop
    assert {row[0]: row[1] for row in run(ctx, "severity_profile", by="speed_limit",
                                          view="table").data["rows"]}[0] == "לא ידוע"


def test_road_shape_caveat_carries_the_code9_share(ctx):
    spec = run(ctx, "severity_profile", by="road_shape", view="chart").data
    c9 = next(c for c in spec["caveats"] if c.startswith("קוד 9"))
    # data-driven: 9 of 47 casualties sit on code 9 in the fixture → 19.1%
    assert c9 == ("קוד 9 'אחר' = 19.1% מהנפגעים בטווח שנבחר — שינוי הקידוד ב-2011 הקפיץ אותו "
                  "(מכ-3% עד 2010 לכ-44% מ-2011 בנתונים החיים), ולכן השוואות צורת דרך על-פני 2011 שבורות")
    assert all(";" not in c for c in spec["caveats"])
    labels = {row[0]: row[1] for row in spec["rows"]}
    assert labels[9] == "אחר" and labels[None] == "לא ידוע"              # code 9 stays its own category
    png_of(spec)


def test_sql_joins_only_when_needed(ctx):
    joined = run(ctx, "severity_profile", by="road_type", view="sql").data
    assert "JOIN accidents a ON a.accident_id = i.accident_id AND a.case_type_code = i.case_type_code" in joined
    plain = run(ctx, "severity_profile", by="casualty_type", view="sql").data
    assert "JOIN accidents" not in plain and "injury_severity_code IN (1, 2, 3)" in plain
    spec = run(ctx, "severity_profile", by="age_group", view="chart").data
    assert rows_safe(ctx.query(spec["sql"])[1]) == spec["rows"]
    assert run(ctx, "severity_profile", by="bogus").kind == "error"


def test_counts_display_is_the_three_line_trend(ctx):
    """P13r2 (the instructor''s pick from the rival''s Trends tab): display=counts + by=year = three absolute
    severity lines with OUR gap discipline — the uncovered year rides spec.uncovered_years for the page''s
    band+break, the caveat leads with counts-are-not-risk, and the rows/columns stay the shares view''s."""
    r = run(ctx, "severity_profile", by="year", display="counts", view="chart")
    assert r.kind == "chart", r.data
    spec = r.data
    assert r.title == "מגמת חומרה · ספירות לפי שנה"
    assert spec["display"] == "counts" and spec["uncovered_years"] == [2022]
    assert spec["caveats"][0].startswith("ספירות אינן סיכון")
    assert "display=counts" in spec["basis"]
    # same statement as the shares view — the display never changes the data
    shares = run(ctx, "severity_profile", by="year", view="chart").data
    assert spec["rows"] == shares["rows"] and spec["columns"] == shares["columns"]
    assert shares["display"] == "shares"
    png_of(spec)
    json_safe(r)


def test_counts_display_needs_the_year_dim(ctx):
    r = run(ctx, "severity_profile", by="weather", display="counts")
    assert r.kind == "error" and "by=year" in r.data
    assert run(ctx, "severity_profile", display="nope").kind == "error"
