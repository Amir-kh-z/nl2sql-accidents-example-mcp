# -*- coding: utf-8 -*-
"""hotspot_map on the hand-planted fixture: every number below is derivable from conftest's rows (coordinates are
deterministic per location: interurban lat = 32 + road_km/1000, lon = 35 + road/100; urban lat = 32 + uj/10000,
lon = 34 + city/10000; S3 has a cell but no coordinates)."""
from __future__ import annotations

import pytest

from nl2sql_roadsafety import sqlkit
from nl2sql_roadsafety.envelope import CREDIT, LAB_LINE, REFUSAL_HEADING
from nl2sql_roadsafety.sqlkit import ASSIGN_JOIN, as_bool, assign_join, build_hotspot_sql, rows_safe
from helpers import json_safe, png_of, run

Y = {"from_year": 2019, "to_year": 2021}
COLS = ["road", "seg", "name_from", "name_to", "km_from", "km_to", "accidents", "ksi_accidents", "geocoded",
        "latitude", "longitude", "first_year", "last_year", "static_assigned", "site_key", "rank"]
ROW_1_10 = [1, 10, "צומת א", "צומת ב", 0.0, 12.0, 3, 1, 3, 32.056, 35.01, 2019, 2020, 0, "road:1/0-12", 1]
ROW_2_20 = [2, 20, "מחלף ג", "צומת ד", 5.0, 7.5, 2, 2, 2, 32.067, 35.02, 2020, 2021, 0, "road:2/5-7.5", 2]
ROW_1_11 = [1, 11, "צומת ב", "צומת ה", 9.5, 15.0, 1, 1, 0, None, None, 2019, 2019, 0, "road:1/9.5-15", 3]


def _units(spec):
    return [f for f in spec["geojson"]["features"] if f["properties"]["kind"] == "unit"]


def _points(spec):
    return [f for f in spec["geojson"]["features"] if f["properties"]["kind"] == "accident"]


def test_segment_counts_equal_segment_rates(ctx):
    r = run(ctx, "hotspot_map", view="table", **Y)
    assert r.kind == "table" and r.data["columns"] == COLS
    assert r.data["rows"] == [ROW_1_10, ROW_2_20, ROW_1_11]
    by_map = {(row[0], row[1]): (row[6], row[7]) for row in r.data["rows"]}
    sr = run(ctx, "segment_rates", view="table", order_by="count", **Y).data["rows"]
    assert by_map == {(row[0], row[1]): (row[6], row[7]) for row in sr} == {(1, 10): (3, 1), (2, 20): (2, 2), (1, 11): (1, 1)}


def test_coverage_geojson_and_caveats(ctx):
    r = run(ctx, "hotspot_map", view="chart", **Y)
    spec = r.data
    assert spec["type"] == "accidents/map" and spec["denominator"]["kind"] == "counts"
    assert spec["coverage"]["by_year"] == [[2019, "asof", 4, 3, 3, 2, 0], [2020, "asof", 3, 2, 3, 2, 0], [2021, "asof", 3, 1, 3, 1, 0]]
    cov = spec["coverage"]
    assert (cov["total"], cov["matched"], cov["pct"], cov["with_coords"], cov["asof_matched"], cov["static_matched"]) == (10, 6, 60.0, 9, 6, 0)
    assert cov["years_without_coords"] == [] and cov["outside_bbox"] == 0
    units = _units(spec)
    assert [f["properties"]["site_key"] for f in units] == ["road:1/0-12", "road:2/5-7.5"]
    assert units[0]["geometry"] == {"type": "Point", "coordinates": [35.01, 32.056]}
    assert units[0]["properties"]["label"] == "1/10 · צומת א ← צומת ב" and units[0]["properties"]["rank"] == 1
    assert units[0]["properties"]["km_from"] == 0.0 and units[0]["properties"]["km_to"] == 12.0
    assert spec["map"] == {"units_listed": 3, "units_placed": 2, "units_omitted": 1, "points": 0,
                           "bbox": [35.01, 32.056, 35.02, 32.067]}
    assert _points(spec) == []
    c = spec["caveats"]
    assert c[0] == "1 מתוך 10 תאונות לא-עירוניות עם נפגעים 2019–2021 ללא קואורדינטות — אינן ממוקמות (נספרות רק אם שויכו למקטע)"
    assert c[1] == "1 מתוך 3 היחידות המוצגות ללא תאונה ממוקמת — ברשימה, לא במפה"
    assert c[2] == "שיוך למקטע: 6 מתוך 10 (60.0%) — 2017+ גרסת גיאומטריה לשנה כמו segment_rates (תאונות: 6) · ק״מ 0 = לא קודד"
    assert "traffic_segments כגיאומטריה קבועה" not in c[2]                       # no empty static clause for a 2017+ range
    assert c[3].startswith("נקודה = ממוצע") and "before_after" in c[3]
    assert c[4].startswith("ספירות אינן סיכון") and len(c) == 5
    assert all(";" not in x for x in c)
    assert spec["basis"] == ("hotspot_map | unit=segments | road=all | color_by=observed | 2019-2021 | top 30 | listed 3 | "
                             "placed 2 | points 0 | coverage 6/10 (60.0%) | geocoded 9/10")
    assert spec["basis"].isascii() and spec["stamp"].isascii()
    assert spec["stamp"].endswith("| hotspot_map | segments | road=all | observed | 2019-2021 | top 30")
    assert r.title == "מפת מוקדים · מקטעים" and "\n" not in r.note and r.note.startswith("מכנה: ספירות")
    assert spec["credit"] == CREDIT
    png_of(spec)
    json_safe(r)


def test_defaults_mix_static_and_asof_geometry(ctx):
    spec = run(ctx, "hotspot_map", view="chart").data                     # 2008-2024
    row = spec["rows"][0]
    assert row[:2] == [1, 10] and row[6:9] == [12, 4, 11] and row[9:11] == [32.05073, 35.01]
    assert row[11:14] == [2012, 2020, 9] and row[14:] == ["road:1/0-12", 1]
    cov = spec["coverage"]
    assert (cov["total"], cov["matched"], cov["pct"], cov["with_coords"]) == (32, 15, 46.9, 25)
    assert (cov["static_matched"], cov["asof_matched"]) == (9, 6)
    assert cov["years_without_coords"] == [2022, 2023, 2024]
    assert cov["by_year"][0] == [2012, "static", 5, 3, 5, 3, 0] and cov["by_year"][-1] == [2024, "asof", 3, 0, 0, 0, 0]
    assert "שנים ללא קואורדינטות כלל: 2022, 2023, 2024" in spec["caveats"][0]
    assert "(תאונות: 6)" in spec["caveats"][2] and "לפני 2017 הגרסה האחרונה" in spec["caveats"][2] and "(תאונות: 9)" in spec["caveats"][2]
    full = run(ctx, "hotspot_map", view="chart", road=2, **Y).data                # every accident geocoded → the positive line
    assert full["caveats"][0] == "כל 3 תאונות לא-עירוניות עם נפגעים 2019–2021 בכביש 2 נושאות קואורדינטות"
    assert "range(2019, 2017)" not in spec["sql"] and "range(2008, 2017)" in spec["sql"]


def test_road_filter_scopes_rows_and_coverage(ctx):
    spec = run(ctx, "hotspot_map", view="chart", road=1, **Y).data
    assert [row[:2] for row in spec["rows"]] == [[1, 10], [1, 11]]
    assert (spec["coverage"]["matched"], spec["coverage"]["total"], spec["coverage"]["pct"]) == (4, 7, 57.1)
    assert "road1_number = 1" in spec["coverage_sql"] and "בכביש 1" in spec["caveats"][0]
    assert "road=1" in spec["basis"]


def test_nonurban_junctions_dedupe_the_dimension(ctx):
    spec = run(ctx, "hotspot_map", view="chart", unit="njunctions").data
    assert spec["columns"] == ["code", "name", "accidents", "ksi_accidents", "geocoded", "latitude", "longitude",
                               "geometry_source", "dim_rows", "first_year", "last_year", "site_key", "rank"]
    assert len(spec["rows"]) == 1
    row = spec["rows"][0]
    assert row[:5] == [433, "צומת העשור", 7, 1, 7] and row[7:] == ["dim", 2, 2012, 2018, "njunction:433", 1]
    assert row[5] == pytest.approx(32.10005, abs=1e-5) and row[6] == pytest.approx(35.10005, abs=1e-5)
    cov = spec["coverage"]
    assert (cov["total"], cov["matched"], cov["pct"], cov["coded_off_junction"]) == (8, 7, 87.5, 0)
    units = _units(spec)
    assert len(units) == 1 and units[0]["properties"]["label"] == "צומת 433 · צומת העשור"
    assert units[0]["properties"]["geometry_source"] == "dim" and units[0]["properties"]["dim_rows"] == 2
    assert any("1 מתוך 1 צמתים (1 עם יותר משורת ממד אחת" in c and "ללא מיקום בממד: 0 עם שורת ממד ללא קואורדינטות, 0 ללא שורת ממד" in c
               for c in spec["caveats"])
    assert any(c.startswith("קוד צומת: 7 מתוך 8") for c in spec["caveats"])
    assert spec["caveats"][-1].startswith("צמתים מדורגים לפי ספירות בלבד") and "excess קיימים למקטעים בלבד" in spec["caveats"][-1]
    assert "הצמתים ממוקמים לפי טבלת הצמתים" in spec["caveats"][0]
    assert r"printf('njunction:%d'" in spec["sql"] and "GROUP BY junction_code" in spec["sql"]
    assert r.title if (r := run(ctx, "hotspot_map", unit="njunctions")) else None
    assert r.title == "מפת מוקדים · צמתים לא-עירוניים"


def test_urban_junctions_fall_back_to_the_accident_mean(ctx):
    spec = run(ctx, "hotspot_map", view="chart", unit="ujunctions").data
    assert spec["columns"][:5] == ["city", "code", "city_name", "street1_name", "street2_name"]
    row = spec["rows"][0]
    assert row[:8] == [5000, 777, "תל אביב - יפו", "רחוב א", "רחוב ב", 5, 1, 5]
    assert row[8:10] == [32.0777, 34.5] and row[10:] == ["accidents", 1, 2012, 2018, "ujunction:5000/777", 1]
    # population = urban rows at a junction (road_type 1) incl. the 99999999 sentinel row (not coded) → 8; coded 5
    assert (spec["coverage"]["total"], spec["coverage"]["matched"], spec["coverage"]["pct"]) == (8, 5, 62.5)
    assert any("ללא מיקום בממד: 1 עם שורת ממד ללא קואורדינטות, 0 ללא שורת ממד — ממוצע התאונות שלהם" in c for c in spec["caveats"])
    assert any("0/99/9999/99999999 = לא קודד" in c for c in spec["caveats"])
    assert not any("לאחר פריסת מודל אתר" in c for c in spec["caveats"])
    units = _units(spec)
    # B8 and B14 carry the streets swapped: the label is ONE row's pair (the smallest), never "רחוב א / רחוב א"
    assert units[0]["properties"]["label"] == "תל אביב - יפו · רחוב א / רחוב ב (צומת 777)" and units[0]["properties"]["city"] == 5000
    assert [row[1] for row in spec["rows"]] == [777]                       # the sentinel 99999999 never ranks
    ba = run(ctx, "before_after", site="ujunction:5000/777", change_year=2015, min_cell=1, view="chart").data
    assert ba["site_label"] == units[0]["properties"]["label"] == "תל אביב - יפו · רחוב א / רחוב ב (צומת 777)"   # one pair rule
    assert run(ctx, "hotspot_map", unit="ujunctions", road=1).kind == "error"
    assert run(ctx, "before_after", site="ujunction:5000/99999999").kind == "error"


def test_points_layer_and_its_cap(ctx, monkeypatch):
    spec = run(ctx, "hotspot_map", view="chart", points=True, **Y).data
    pts = _points(spec)
    assert [p["properties"]["accident_id"] for p in pts] == [2020000002, 2019000002, 2019000001, 2021000002, 2020000003]
    assert [p["properties"]["site_key"] for p in pts] == ["road:1/0-12"] * 3 + ["road:2/5-7.5"] * 2
    assert pts[0]["properties"]["date"] == "2020-02-15" and pts[0]["properties"]["road_km"] == 50.0
    assert pts[0]["geometry"]["coordinates"] == [35.01, 32.05]
    assert spec["map"]["points"] == 5 and spec["points"] is True
    assert spec["caveats"][-1] == "נקודות: 5 מתוך 5 תאונות ממוקמות ביחידות המוצגות (תקרה 300 ליחידה, 3000 בסך הכל, החדשות קודם)"
    assert len(rows_safe(ctx.query(spec["points_sql"])[1])) == 5
    json_safe(run(ctx, "hotspot_map", view="chart", points=True, **Y))
    monkeypatch.setattr(sqlkit, "POINTS_PER_UNIT", 2)
    capped = run(ctx, "hotspot_map", view="chart", points="true", **Y).data
    assert [p["properties"]["accident_id"] for p in _points(capped)] == [2020000002, 2019000002, 2021000002, 2020000003]
    assert "נקודות: 4 מתוך 5" in capped["caveats"][-1] and "(תקרה 2 ליחידה" in capped["caveats"][-1]
    assert _points(run(ctx, "hotspot_map", view="chart", points="0", **Y).data) == []
    assert run(ctx, "hotspot_map", points="maybe").kind == "error"


def test_excess_falls_back_to_observed_with_a_caveat(ctx):
    spec = run(ctx, "hotspot_map", view="chart", color_by="excess", **Y).data
    assert spec["denominator"]["kind"] == "counts" and spec["color_by_effective"] == "observed" and spec["color_by"] == "excess"
    assert spec["caveats"][0].startswith("התבקשה צביעה לפי excess — אין מודל אתר פרוס")
    assert "color_by=excess (fallback observed)" in spec["basis"] and "| excess->observed |" in spec["stamp"]
    j = run(ctx, "hotspot_map", view="chart", color_by="excess", unit="njunctions").data
    assert "excess קיים רק למקטעים" in j["caveats"][0]


def test_excess_color_matches_map_scene_rule():
    """ONE diverging rule: _excess_color must be byte-compatible with map_scene._excess_hex — z bands from the
    site's OWN NB sd (floored at 0.5), never excess/max|excess| (the rejected rule: one outlier owns the scale)."""
    from nl2sql_roadsafety.actions import hotspot_map, map_scene

    ci = {"accidents": 0, "mu": 1, "hi90": 2}
    cases = [
        # sd unfloored (mu=10, hi90-mu=3.29 → sd≈2): one case per band, away from the boundaries
        (2.0, 10.0, 13.29, hotspot_map.DIVERGING[0]),      # z ≈ -4
        (8.0, 10.0, 13.29, hotspot_map.DIVERGING[1]),      # z ≈ -1
        (10.5, 10.0, 13.29, hotspot_map.DIVERGING[2]),     # z ≈ 0.25
        (13.0, 10.0, 13.29, hotspot_map.DIVERGING[3]),     # z ≈ 1.5
        (18.0, 10.0, 13.29, hotspot_map.DIVERGING[4]),     # z ≈ 4
        # sd FLOOR (hi90-mu → raw sd < 0.5 → sd = 0.5 exactly): the boundaries, exact in float arithmetic
        (4.0, 5.0, 5.0, hotspot_map.DIVERGING[0]),         # z = -2 → the <= keeps deep blue
        (4.625, 5.0, 5.0, hotspot_map.DIVERGING[1]),       # z = -0.75 → the <= keeps light blue
        (5.0, 5.0, 5.2, hotspot_map.DIVERGING[2]),         # raw sd 0.12 floored to 0.5, z = 0
        (5.375, 5.0, 5.0, hotspot_map.DIVERGING[3]),       # z = 0.75 → < is strict, light red
        (6.0, 5.0, 5.0, hotspot_map.DIVERGING[4]),         # z = 2 → < is strict, deep red
    ]
    assert {want for *_, want in cases} == set(hotspot_map.DIVERGING)      # all five buckets exercised
    for acc, mu, hi90, want in cases:
        got = hotspot_map._excess_color([acc, mu, hi90], ci)
        assert got == want == map_scene._excess_hex({"accidents": acc, "mu": mu, "hi90": hi90}), (acc, mu, hi90, got)


def test_excess_model_failure_degrades_clean_and_unclipped(ctx, monkeypatch):
    """The degrade path: a model-path exception must fall back to observed WITHOUT silently narrowing the
    range to the exposure era (y0e reset) and WITHOUT smuggling ';'/newlines into the one-line note."""
    from nl2sql_roadsafety.studio import model as studio_model, predict as studio_predict, registry as studio_registry

    monkeypatch.setattr(studio_registry, "deployed", lambda ctx, family=None: ("site-x", {"model_id": "site-x"}))
    monkeypatch.setattr(studio_model, "require_xgboost", lambda: None)     # reach the line AFTER the y0e clip

    def boom(*args, **kwargs):
        raise ValueError("boom; contaminated\nline2")

    monkeypatch.setattr(studio_predict, "expected_by_segment", boom)
    r = run(ctx, "hotspot_map", view="chart", color_by="excess", from_year=2008, to_year=2024)
    assert r.kind == "chart", r.data
    spec = r.data
    assert spec["color_by"] == "excess" and spec["color_by_effective"] == "observed"
    assert spec["denominator"]["kind"] == "counts" and "excess" not in spec["columns"]
    # ONE merged degrade line (map_scene's rule): the real reason, never a false "no deployment" claim beside it
    assert spec["caveats"][0] == "התבקשה צביעה לפי excess — boom · contaminated line2 · מוצגות ספירות observed"
    assert not any(c.startswith("נפילה חזרה") for c in spec["caveats"])
    assert sum("התבקשה צביעה לפי excess" in c for c in spec["caveats"]) == 1
    assert all(";" not in c and "\n" not in c for c in spec["caveats"])
    assert "\n" not in r.note and r.note.count(";") == len(spec["caveats"]) - 1        # only the legal separators
    # y0e was reset: the fallback runs the FULL requested range, static branch included, not 2017+
    assert spec["from_year"] == 2008 and "range(2008, 2017)" in spec["sql"]
    assert min(row[11] for row in spec["rows"]) < 2017                                 # first_year — pre-2017 rows shown
    assert "color_by=excess (fallback observed)" in spec["basis"] and "| 2008-2024 |" in spec["basis"]
    assert "| excess->observed | 2008-2024 |" in spec["stamp"]


def test_excess_notes_are_honest_with_a_deployment(ctx, monkeypatch):
    """Refuter 2026-09-06: with a DEPLOYED model, (1) a range ending before the exposure era must say
    excess-from-2017 — the missing elif fell through to the false 'no deployment' default (map_scene's arm,
    ported); (2) a junction unit must lead with the TRUE segments-only cause — its branch never consults
    the registry, so a deployment claim either way would be invented."""
    from nl2sql_roadsafety.studio import registry as studio_registry

    monkeypatch.setattr(studio_registry, "deployed", lambda ctx, family=None: ("site-x", {"model_id": "site-x"}))
    spec = run(ctx, "hotspot_map", view="chart", color_by="excess", from_year=2012, to_year=2016).data
    assert spec["color_by_effective"] == "observed" and spec["denominator"]["kind"] == "counts"
    assert spec["caveats"][0] == "התבקשה צביעה לפי excess — excess קיים מ-2017 (עידן החשיפה) · מוצגות ספירות observed"
    assert not any("אין מודל" in c for c in spec["caveats"])
    assert spec["from_year"] == 2012 and spec["to_year"] == 2016            # the degrade never clips the range
    j = run(ctx, "hotspot_map", view="chart", color_by="excess", unit="njunctions").data
    assert j["caveats"][0] == ("התבקשה צביעה לפי excess — excess קיים רק למקטעים · מוצגות ספירות observed"
                               " · צמתים מדורגים לפי ספירות")
    assert j["caveats"][0].count("excess קיים רק למקטעים") == 1             # the tail never repeats the note
    assert not any("אין מודל" in c for c in j["caveats"])


def test_missing_artifact_refusal_degrades_to_observed(ctx, monkeypatch):
    """Refuter 2026-09-06: predict.expected_by_segment raises sqlkit's Refusal when model.ubj is gone under
    a valid pointer — for the MAP that is a model failure like any other: observed fallback with the
    refusal's reason inside the ONE merged line, never a refusal card (the docstring's 'never an error')."""
    from nl2sql_roadsafety.studio import model as studio_model, predict as studio_predict, registry as studio_registry

    monkeypatch.setattr(studio_registry, "deployed", lambda ctx, family=None: ("site-x", {"model_id": "site-x"}))
    monkeypatch.setattr(studio_model, "require_xgboost", lambda: None)

    def gone(*args, **kwargs):
        raise sqlkit.Refusal("קובץ המודל הפרוס חסר מהרישום — יש לאמן ולפרוס מחדש",
                             ["studio_models", "studio_train_site"], detail="model.ubj missing for site-x")

    monkeypatch.setattr(studio_predict, "expected_by_segment", gone)
    r = run(ctx, "hotspot_map", view="chart", color_by="excess", **Y)
    assert r.kind == "chart", r.data
    spec = r.data
    assert spec["color_by"] == "excess" and spec["color_by_effective"] == "observed"
    assert spec["denominator"]["kind"] == "counts" and "excess" not in spec["columns"] and "model_id" not in spec
    assert spec["caveats"][0] == ("התבקשה צביעה לפי excess — קובץ המודל הפרוס חסר מהרישום — יש לאמן ולפרוס מחדש"
                                  " · מוצגות ספירות observed")
    assert sum("התבקשה צביעה לפי excess" in c for c in spec["caveats"]) == 1
    assert all(";" not in c and "\n" not in c for c in spec["caveats"])
    assert "color_by=excess (fallback observed)" in spec["basis"] and "| excess->observed |" in spec["stamp"]


def test_faces_are_the_statements_that_ran(ctx):
    spec = run(ctx, "hotspot_map", view="chart", **Y).data
    assert rows_safe(ctx.query(spec["sql"])[1]) == spec["rows"]
    assert rows_safe(ctx.query(spec["coverage_sql"])[1]) == spec["coverage"]["by_year"]
    assert run(ctx, "hotspot_map", view="sql", **Y).data == spec["sql"]
    assert run(ctx, "hotspot_map", view="table", **Y).data == {"rows": spec["rows"], "columns": spec["columns"]}
    for needle in ("a.road_km <> 0", "a.year = u.year", "arg_max(name_from, src_year)", "case_type_code = 1",
                   "QUALIFY row_number() OVER (PARTITION BY a.accident_id, a.case_type_code",
                   "latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 36.0", "JOIN geom u"):
        assert needle in spec["sql"], needle
    assert "traffic_adt_filled" not in spec["sql"]
    assert spec["points_sql"] is None


def test_refusals_and_errors(ctx):
    for inputs, needle in (({"from_year": 2022, "to_year": 2024}, "2022–2024"),
                           ({"unit": "njunctions", **Y}, "2019–2021"),
                           ({"from_year": 2008, "to_year": 2011}, "2008–2011"),
                           ({"to_year": 2030}, "31.12.2024")):
        r = run(ctx, "hotspot_map", **inputs)
        assert r.kind == "markdown", (inputs, r.data)
        lines = r.data.split("\n")
        assert lines[0] == REFUSAL_HEADING and lines[-1] == LAB_LINE and needle in r.data and CREDIT not in r.data
    for bad in ({"top_n": 0}, {"top_n": 201}, {"road": -1}, {"unit": "x"}, {"color_by": "x"}, {"from_year": 2021, "to_year": 2019}):
        assert run(ctx, "hotspot_map", **bad).kind == "error", bad


def test_sqlkit_units():
    assert assign_join() == ASSIGN_JOIN and assign_join("geom").startswith("JOIN geom u\n")
    assert ASSIGN_JOIN.startswith("JOIN units u\n      ON a.road1_number = u.road\n     AND a.road_km <> 0\n")
    assert as_bool(True, "p") is True and as_bool("False", "p") is False and as_bool(1, "p") is True and as_bool("", "p") is False
    for bad in ("maybe", 2, None, [1]):
        with pytest.raises(sqlkit.ActionError):
            as_bool(bad, "p")
    assert "range(2019, 2017)" in build_hotspot_sql("segments", 2019, 2021, 10)          # the empty static branch
    assert "range(2008, 2017)" in build_hotspot_sql("segments", 2008, 2024, 10)
    assert "range(2008, 2013)" in build_hotspot_sql("segments", 2008, 2012, 10)
    with pytest.raises(ValueError):
        sqlkit.hotspot_points_sql("segments", 2019, 2021, [])
    assert sqlkit.JUNCTION_SENTINELS == "(0, 99, 9999, 99999999)"
    for key in ("ujunction:5000/99999999", "njunction:99999999", "njunction:9999", "ujunction:5000/0"):
        with pytest.raises(sqlkit.ActionError):
            sqlkit.parse_site_key(key)
    assert "99999999" in sqlkit.site_coding_exprs(sqlkit.parse_site_key("ujunction:5000/777"))[0]


def test_refuses_on_a_foreign_database(other_ctx):
    r = run(other_ctx, "hotspot_map")
    assert r.kind == "markdown" and r.data.split("\n")[-1] == LAB_LINE and CREDIT not in r.data
