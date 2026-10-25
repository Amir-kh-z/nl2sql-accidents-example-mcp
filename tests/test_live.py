# -*- coding: utf-8 -*-
"""Smoke tests against the LIVE working copy (read-only). Skipped wherever the copy is absent.
Uses only the `live` fixture — never mix `ctx`/`other_ctx` in here: nl2sql_engine.configure() is
process-global, so every fixture that sets data_dir resets it in its own teardown."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

import nl2sql_engine
from nl2sql_engine.modules import Context

from nl2sql_roadsafety import __version__
from nl2sql_roadsafety.envelope import CREDIT, CREDIT_SHORT
from helpers import json_safe, png_of, run

LIVE = Path(r"C:\data\israel_accidents\israel_accidents.duckdb")
pytestmark = pytest.mark.skipif(not LIVE.exists(), reason="live CBS working copy absent")


@pytest.fixture()
def live(tmp_path):
    nl2sql_engine.configure(data_dir=tmp_path)
    yield Context(db_path=str(LIVE))
    nl2sql_engine.configure(data_dir=None)


def _year_map(r):
    return {row[0]: row[1] for row in r.data["rows"]}


def test_killed_by_year_with_the_2009_gap(live):
    r = run(live, "trend", view="chart")
    spec = r.data
    assert len(spec["rows"]) == 20
    by = _year_map(r)
    assert by[2005] == 476 and by[2023] == 361 and by[2024] == 439
    row2009 = next(row for row in spec["rows"] if row[0] == 2009)
    assert row2009 == [2009, None, 15, 16856, False]
    assert spec["gap_periods"] == ["2009"]
    assert "15 רשומות מול 16,856 תאונות" in spec["caveats"][0]
    assert "2009" in r.note and "\n" not in r.note
    assert spec["basis"] == "killed by year | road_type=all | 2005-2024 | 20 rows | involved WHERE case_type_code = 1"
    assert spec["stamp"] == f"nl2sql-roadsafety-lab {__version__} | killed / year / all | 2005-2024"
    assert spec["credit"] == CREDIT
    png_of(spec)
    json_safe(r)


def test_killed_by_road_group(live):
    urban = run(live, "trend", road_type="urban", view="chart").data
    assert len(urban["caveats"]) == 6
    assert "9 רשומות מול 12,091 תאונות" in urban["caveats"][0]
    assert urban["gap_periods"] == ["2009"]
    assert any("סכום שניהם" in c for c in urban["caveats"])
    assert {row[0]: row[1] for row in urban["rows"]}[2005] == 180      # composite key: a single-key join gives 373
    assert {row[0]: row[1] for row in urban["rows"]}[2024] == 150
    nonurban = run(live, "trend", road_type="nonurban", view="table").data
    assert "6 רשומות מול 4,765 תאונות" in run(live, "trend", road_type="nonurban", view="chart").data["caveats"][0]
    assert {row[0]: row[1] for row in nonurban["rows"]}[2024] == 289


def test_monthly_urban_has_exactly_twelve_uncovered_months(live):
    r = run(live, "trend", granularity="month", road_type="urban", view="table")
    rows = r.data["rows"]
    assert len(rows) == 240
    uncovered = [(row[0], row[1]) for row in rows if row[-1] is False]
    assert len(uncovered) == 12 and all(y == 2009 for y, _ in uncovered)
    spec = run(live, "trend", granularity="month", road_type="urban", view="chart").data
    assert "12 תקופות" in spec["caveats"][0] and "(9 רשומות מול 12,091 תאונות)" in spec["caveats"][0]


def test_accident_measures_2024(live):
    acc = _year_map(run(live, "trend", measure="accidents", view="table"))
    assert acc[2005] == 17509 and acc[2024] == 8315
    assert run(live, "trend", measure="accidents", view="chart").data["gap_periods"] == []
    y24 = {"from_year": 2024, "to_year": 2024, "view": "table"}
    assert _year_map(run(live, "trend", measure="fatal_accidents", **y24))[2024] == 405
    assert _year_map(run(live, "trend", measure="severe_injured", **y24))[2024] == 2808
    assert _year_map(run(live, "trend", measure="slight_injured", **y24))[2024] == 11203
    assert _year_map(run(live, "trend", measure="accidents", road_type="urban", **y24))[2024] == 5447
    assert _year_map(run(live, "trend", measure="accidents", road_type="nonurban", **y24))[2024] == 2868
    assert _year_map(run(live, "trend", measure="severe_injured", road_type="urban", **y24))[2024] == 1624
    assert _year_map(run(live, "trend", measure="fatal_accidents", road_type="nonurban", **y24))[2024] == 256
    monthly = run(live, "trend", measure="accidents", granularity="month", from_year=2024, to_year=2024,
                  view="table").data["rows"]
    assert len(monthly) == 12 and sum(row[2] for row in monthly) == 8315
    monthly = run(live, "trend", measure="fatal_accidents", granularity="month", road_type="nonurban",
                  from_year=2024, to_year=2024, view="table").data["rows"]
    assert sum(row[2] for row in monthly) == 256


def test_trap_live(live):
    d = run(live, "naive_vs_correct", year=2024).data
    for needle in ("50,145", "5,458", "44,687", "פי 9.2", "405 קטלניות · 2,452 קשות · 5,458 קלות = 8,315"):
        assert needle in d, needle
    assert "הערה:" not in d


def test_about_live(live):
    r = run(live, "about")
    d = r.data
    for needle in ("1,290,788", "270,723", "1,020,065", "2,987,206 (684,051", "2,297,533",
                   "43 (31 טבלאות + 12 מבטים)", "2005 עד 2024", "12/2024", "2024-12-31",
                   "**מודל אתר פרוס** — אין"):
        assert needle in d, needle
    assert r.note.endswith(CREDIT_SHORT) and "\n" not in r.note


# ── P2 ──

def test_segment_rates_live(live):
    from nl2sql_roadsafety.sqlkit import units_count_sql
    assert live.query(units_count_sql())[1] == [(6233, 1311)]
    d = run(live, "segment_rates", view="chart").data
    assert (d["coverage"]["matched"], d["coverage"]["total"], d["coverage"]["pct"]) == (19865, 28213, 70.4)   # km 0 = not coded (320 rows)
    assert [row[3] for row in d["coverage"]["by_year"]] == [53.7, 60.9, 65.5, 78.0, 83.2, 74.3, 72.1, 81.2]
    assert "coverage 19865/28213 (70.4%)" in d["basis"]
    assert d["caveats"][0].startswith("כיסוי לפי שנה: 53.7% (2017) עד 83.2% (2021) — לא מונוטוני")
    assert any("12.4–21.6% בפער 1–3 שנים, 34.6% בפער 4" in c for c in d["caveats"])          # from traffic_fill_validation
    png_of(d)
    r60 = run(live, "segment_rates", road=60, view="chart").data                           # coverage of the road shown
    assert (r60["coverage"]["matched"], r60["coverage"]["total"], r60["coverage"]["pct"]) == (581, 883, 65.8)
    assert "בכביש 60 (65.8%)" in r60["denominator"]["label"]
    top = run(live, "segment_rates", order_by="count", from_year=2019, to_year=2024, view="table").data["rows"][0]
    assert top[:2] == [70, 120] and top[2:4] == ["צומת יסיף", "כניסה לגדידה רח 115"] and top[6:8] == [176, 16]   # names: 2024 vintage
    assert top[10:14] == [908.3, 19.38, 16.62, 22.46]
    ksi = run(live, "segment_rates", severity="ksi", from_year=2019, to_year=2024, view="table").data["rows"][0]
    assert ksi[:2] == [411, 10] and ksi[6:8] == [16, 10] and ksi[10:12] == [45.5, 21.99]


def test_severity_profile_live(live):
    d = run(live, "severity_profile", by="involved_vehicle_type", view="chart").data
    assert d["uncovered_years"] == [2009] and "2009: 15 רשומות מול 16,856 תאונות" in d["caveats"][0]
    by_code = {row[0]: row[2] for row in d["rows"]}
    assert sum(by_code.values()) == 482347 and by_code[1] == 292420 and by_code[-1] == 58985
    assert {row[0]: row[2] for row in run(live, "severity_profile", by="casualty_type", view="table").data["rows"]}[1] == 58985
    # P11: the share-drift exhibit — the severe share roughly triples over the era (6.1% -> 19.4% live)
    yr = run(live, "severity_profile", by="year", view="table").data["rows"]
    severe_pct = {row[0]: row[8] for row in yr}                              # columns: ... severe_pct at 8
    assert [row[0] for row in yr] == sorted(row[0] for row in yr) and 2009 not in severe_pct
    assert severe_pct[2010] == pytest.approx(6.1, abs=1.0)
    assert severe_pct[2024] == pytest.approx(19.4, abs=2.0)
    assert severe_pct[2024] > 2 * severe_pct[2010]


def test_vehicle_cells_live(live):
    d = run(live, "vehicle_cells_ranking", view="chart").data
    assert len(d["rows"]) == 68 and d["excluded"]["cells"] == 13 and d["excluded"]["fleet"] == 465636
    assert d["global_rate"] == pytest.approx(0.19299, abs=1e-5) and d["tiers"] == {"safest": 14, "regular": 41, "highest_risk": 13}
    assert d["rows"][0][:2] == [2024, 0] and d["rows"][0][7] == 0.0277 and d["rows"][0][11] == "safest"
    assert d["rows"][-1][:2] == [2016, 5] and d["rows"][-1][7] == 0.8597
    assert run(live, "vehicle_cells_ranking", metric="ksi", view="table").data["rows"][0][8] == pytest.approx(0.03362, abs=1e-5)
    ke = run(live, "vehicle_cells_ranking", bands="known_engine", view="chart").data
    assert len(ke["rows"]) == 62                                              # 68 − 6 band-0 cells
    assert ke["excluded"]["band0_cells"] == 6 and ke["excluded"]["band0_fleet"] == 154924
    assert any("6 תאי נפח מנוע 0" in c and "5.7%" in c for c in ke["caveats"])
    assert any("ev_share 100%" in c for c in d["caveats"])
    png_of(d)


def test_before_after_live(live):
    d = run(live, "before_after", view="chart").data                     # road:60/96.0-98.8, 2017
    assert d["counts"] == {"casualty": [49, 6, 38867, 36102], "damage_only": [22, 23, 143423, 120421]}
    rows = {row[0]: row for row in d["rows"]}
    assert rows["casualty"][7:10] == [0.1318, 0.0582, 0.2987] and rows["damage_only"][7] == 1.2452
    assert rows["double"][7:10] == [0.1059, 0.0389, 0.2882]
    assert d["control_flag"] is False and "כיכר אדם" in d["site_label"]
    png_of(d)
    two = run(live, "before_after", site="road:2/21.9-24.0", change_year=2011, view="table").data["rows"]
    assert {row[0]: row[7] for row in two}["double"] == 1.0943
    j = run(live, "before_after", site="njunction:433", change_year=2015, view="chart").data
    assert "צומת העשור" in j["site_label"]


def test_ab_scan_live(live):
    """P15, one guarded pin: the default sweep returns candidates, every z is a finite rank score (never a
    CI), and no caveat smuggles a ';' into the note line."""
    d = run(live, "ab_scan", view="chart").data
    assert d["rows"] and len(d["rows"]) <= 20
    for row in d["rows"]:
        assert isinstance(row[6], float) and math.isfinite(row[6]), row
    assert all(";" not in c for c in d["caveats"])
    assert "ללא תיקון להשוואות מרובות" in d["caveats"][0]
    png_of(d)


def test_weather_live(live):
    d = run(live, "weather_check", view="chart").data
    by = {row[0]: row for row in d["rows"]}
    assert by["גשום"][1:5] == [8256, 4686, 56.8, 12.7]
    assert any("סף גשם: 0.1" in c and "עולה ל-67.0%" in c for c in d["caveats"])
    sub = run(live, "weather_check", from_year=2010, to_year=2012, view="chart").data
    assert any("עולה ל-65.8%" in c for c in sub["caveats"])
    assert by["בהיר"][1] == 183482 and by["בהיר"][3] == 3.7 and by["לא ידוע"][1] == 24896 and by["לא ידוע"][3] == 7.8
    assert d["years_without_cell"] == [2005, 2006, 2007] and "51,772" in d["caveats"][0]
    assert d["caveats"][1].startswith("807 מתוך 218,951")
    zero = {row[0]: row[3] for row in run(live, "weather_check", rain_threshold_mm="0", view="table").data["rows"]}
    assert zero["גשום"] == 67.0


def test_triage_live(live):
    r = run(live, "triage")
    assert r.data.startswith("# ❌") and "vehicle_cells_ranking" in r.data


# ── P13 ──

def test_heat_matrix_live(live):
    d = run(live, "heat_matrix", from_year=2023, to_year=2024, view="chart").data
    assert len(d["rows"]) == 168                                             # the zero-filled grid, always
    # honest arithmetic: placed + excluded == the known casualty total for 2023-2024
    # (live hour_of_day is complete, so excluded is 0 — the caveat says so instead of inventing one)
    assert sum(row[2] for row in d["rows"]) + d["unknown_hour_excluded"] == 17147
    assert d["day_labels"][0] == "ראשון" and d["day_labels"][6] == "שבת" and len(d["day_labels"]) == 7
    png_of(d)


# ── P14 ──

def test_zone_ranking_live(live):
    """The cumulative TAZ snapshot: density answers with real values, and the index-equals-density
    caveat carries the live correlation (r = 1.000 probed 2026-09-06)."""
    import re as _re
    d = run(live, "zone_ranking", measure="density", view="chart").data
    assert 0 < len(d["rows"]) <= 20 and d["rows"][0][1] > 0
    corr_line = next(c for c in d["caveats"] if "מתאם" in c)
    nums = [float(x) for x in _re.findall(r"\d+\.\d+", corr_line)]
    assert nums and max(nums) >= 0.99
    assert any("202604" in c for c in d["caveats"])                # the snapshot stamp on every answer
    png_of(d)


def test_city_ranking_live(live):
    """The municipality snapshot: at most top_n rows, and every city/region name resolved or an honest
    'קוד' fallback (live: 113 municipality rows have no dim_settlement row)."""
    d = run(live, "city_ranking", view="table").data
    assert 0 < len(d["rows"]) <= 20
    for row in d["rows"]:
        assert isinstance(row[0], str) and row[0].strip(), row
        assert isinstance(row[1], str) and (row[1].strip() or row[1].startswith("קוד")), row


def test_severity_profile_road_shape_live(live):
    import re as _re
    d = run(live, "severity_profile", by="road_shape", view="chart").data
    c9 = next(c for c in d["caveats"] if c.startswith("קוד 9"))              # the 2011 discontinuity caveat
    assert _re.search(r"= \d+(\.\d+)?% מהנפגעים בטווח שנבחר", c9)            # carries a computed share
    labels = {row[0]: row[1] for row in d["rows"]}
    assert labels[9] == "אחר"                                                # its own category, never folded away


# ── P4 ──

def test_studio_live_end_to_end(live):
    """Train → gate → deploy → rank → excess map on the live copy, in a tmp data dir (the shared dir is only
    seeded at acceptance). Gate numbers pinned with tolerance (xgboost's exact floats can drift across builds)."""
    pytest.importorskip("xgboost")
    r = run(live, "studio_train_site")                                       # doc-11 / 2023 (the default)
    assert r.kind == "markdown" and "מודל מועמד" in r.data, r.data
    assert "10,488 שורות מקטע-שנה (1311 מקטעים" in r.data.replace("1,311", "1311")
    v = run(live, "studio_validate")
    assert "עבר את השער" in v.data, v.data
    from nl2sql_roadsafety.studio import registry
    g = registry.list_models(live)[-1]["gate"]["metrics"]
    assert g["spearman"] == pytest.approx(0.69, abs=0.06)
    assert g["calibration"] == pytest.approx(1.17, abs=0.06)
    assert g["deviance_ratio"] < 1.0
    run(live, "studio_train_site", train_until=2022)
    v22 = run(live, "studio_validate")                                       # the 2023-24 decline rejects 2022
    assert "נדחה" in v22.data and "כיול 1.35" in v22.data, v22.data
    run(live, "studio_train_site", train_until=2018, features="shuffled")
    vsh = run(live, "studio_validate")
    assert "נדחה" in vsh.data and "Spearman 0.2" in vsh.data, vsh.data       # the demo script's straw man
    assert run(live, "studio_deploy", model_id=registry.list_models(live)[-1]["model_id"]).data.startswith("# ❌")
    d = run(live, "studio_deploy")                                           # newest VALIDATED = doc-11/2023
    assert "נפרס site-2023-doc11" in d.data
    sr = run(live, "site_ranking", view="table").data
    assert sr["rows"][0][:2] == [60, 850] and sr["rows"][0][13] is True      # the national excess leader
    r60 = {(row[0], row[1]): (row[9], row[16]) for row in run(live, "site_ranking", road=60, view="table").data["rows"]}
    assert r60[(60, 850)][1] == 1
    ex836, rank836 = r60[(60, 836)]
    assert ex836 < 0 and rank836 >= 5              # the 2017-treated demo site sits BELOW its model expectation
    m = run(live, "hotspot_map", color_by="excess", road=60, from_year=2019, view="chart").data
    assert m["color_by_effective"] == "excess" and m["rows"][0][:2] == [60, 850]
    assert m["denominator"]["kind"] == "exposure" and any("מודל site-2023-doc11" in c for c in m["caveats"])
    png_of(m)
    assert len(run(live, "ledger_list").data["rows"]) >= 8
    assert run(live, "finding_card", claim="מפת העודף פועלת").kind == "markdown"
    # ── P5: studio_explain on the deployed model (reusing this test's artifacts) ──
    import time
    t0 = time.perf_counter()
    ex = run(live, "studio_explain", site="60/850", view="table")
    t_site = time.perf_counter() - t0
    assert ex.kind == "table", ex.data
    phis = [c for c in ex.data["columns"] if c.startswith("phi_") and c != "phi_bias"]
    assert len(phis) == 5 and {"phi_adt_asof", "phi_lag1"} & set(phis)       # traffic + history lead, as the report says
    assert [row[0] for row in ex.data["rows"]] == list(range(2017, 2025))
    import math
    for row in ex.data["rows"]:                                              # the top-5 + bias carry MOST of ln mu
        mu, tail = row[2], sum(row[3:])
        assert abs(tail - math.log(mu)) < 0.25, row                          # 6 small φ are dropped from the table
    # (the EXACT identity over all 11 features + bias is pinned in test_explain.py on the full φ rows)
    t0 = time.perf_counter()
    g = run(live, "studio_explain")
    t_global = time.perf_counter() - t0
    assert g.kind == "chart" and g.data["png_base64"]
    print(f"\nstudio_explain: site {t_site:.2f}s, global (10,488-row contribs) {t_global:.2f}s")
    # ── P10: site_profile consumes the SAME deployment (the map's click panel, model block) ──
    sp = run(live, "site_profile", site="60/836", from_year=2019, to_year=2024, view="chart").data
    mb = sp["model"]
    assert mb["model_id"].startswith("site-2023-doc11") and mb["from_year"] == 2019
    assert mb["excess"] == pytest.approx(ex836, abs=0.05)                    # the ranking's number, same window
    assert mb["excess"] < 0 and mb["verdict"]                                # beat 3: below expectation (the −2
    assert "מעל" not in mb["verdict"]                                        # sits INSIDE the NB interval — never "above")
    assert sp["denominator"]["kind"] == "exposure" and "mu" in sp["columns"]
    assert 1 <= len(mb["drivers"]) <= 3 and sp["model_id"] == mb["model_id"]
    nj = run(live, "site_profile", site="njunction:323", view="chart").data
    assert "model" not in nj                                                 # junctions: counts only, even deployed
    # ── P10 follow-up: the map's excess mode — the EB screening as a layer (same deployment) ──
    ms = run(live, "map_scene", color_by="excess", from_year=2019, to_year=2024, twin=False, view="chart").data
    assert ms["color_by_effective"] == "excess" and ms["model_id"].startswith("site-2023-doc11")
    top = ms["sites"]["segments"][0]
    assert (top["road"], top["seg"]) == (60, 850) and top["excess"] > 30 and top["significant"] is True
    assert all("excess" not in e for e in ms["sites"]["njunctions"])         # the golden rule on the map layer
    assert ms["denominator"]["kind"] == "exposure"


def test_severity_live_end_to_end(live):
    """P9: train → gate → deploy → profile → what_if on the live copy (~25 s: 340,498 person rows, ~176 rounds).
    Gate numbers pinned with tolerance (xgboost floats drift across builds); the class weights are exact data
    facts of the working copy's train window."""
    pytest.importorskip("xgboost")
    r = run(live, "studio_train_severity")                                   # person-12 / 2022 (the default)
    assert r.kind == "markdown" and "מודל מועמד" in r.data, r.data
    assert "340,498" in r.data                                               # the 2010-2024 casualty person pool
    from nl2sql_roadsafety.studio import registry, severity
    meta = registry.list_models(live, severity.FAMILY)[-1]
    assert meta["class_weights"]["values"] == pytest.approx([69.48, 11.21, 1.116], rel=0.01)
    v = run(live, "studio_validate_severity")
    assert "עבר את השער" in v.data, v.data
    g = registry.list_models(live, severity.FAMILY)[-1]["gate"]["metrics"]
    assert g["fatal_recall"] == pytest.approx(0.64, abs=0.06)
    assert g["auc_fatal"] == pytest.approx(0.84, abs=0.03)
    assert g["overfit_auc_gap"] < 0.05
    d = run(live, "studio_deploy", family="severity")
    assert "נפרס severity-2022-person12" in d.data, d.data
    p = run(live, "severity_predict", casualty="הולך רגל", time="לילה", safety="ללא אמצעי בטיחות", view="table")
    rel = {row[1]: row[4] for row in p.data["rows"]}
    assert rel["הרוג"] > 3.0 and rel["פצוע קל"] < 0.5, rel                   # the profile beat: far above baseline
    w = run(live, "what_if", switch="חגור לעומת לא חגור", view="table")      # the demo's 5c switch
    ratio = {row[1]: row[4] for row in w.data["rows"]}
    assert ratio["הרוג"] > 1.2 and ratio["פצוע קל"] < 0.5, ratio             # unbelted moves mass up the scale
    chart = run(live, "severity_predict", casualty="הולך רגל", time="לילה").data
    assert chart["model_id"].startswith("severity-2022-person12") and chart["png_base64"]
    assert any("גורל של אדם" in c for c in chart["caveats"])                 # the relative-only line, every face
    png_of(chart)
    json_safe(w)
    # ── P10: the site panel's conditional severity block (relative only) on a junction ──
    sp = run(live, "site_profile", site="ujunction:5000/14900823", view="chart").data
    sev = sp["severity_rel"]
    assert sev["model_id"].startswith("severity-2022-person12") and sev["n_persons"] > 200
    assert len(sev["relative"]) == 3 and all(v > 0 for v in sev["relative"])
    assert "model" not in sp                                                 # never the site model on a junction
    assert sp["model_id"] == sev["model_id"]                                 # the chip keys on the severity model here
    assert any("יחסיות בלבד" in c for c in sp["caveats"])


def test_two_wheelers_live(live):
    """The direct statements against the curated view's cohort grain, plus the era pins."""
    import duckdb
    con = duckdb.connect(str(LIVE), read_only=True)
    try:
        assert con.execute("select count(*) from v_motorcycle_accident_rate").fetchone()[0] == 877
        # our numerator at cohort grain must equal the view's in_accidents (same golden-rule discipline)
        diff = con.execute("""
            WITH ours AS (
              SELECT a.year AS accident_year, v.vehicle_type_code AS engine_cc_band_code, v.manufacture_year,
                     count(*) AS n
              FROM vehicles v JOIN accidents a
                ON a.accident_id = v.accident_id AND a.case_type_code = v.case_type_code
              WHERE a.case_type_code = 1 AND a.year >= 2013 AND v.vehicle_type_code IN (8, 9, 10, 19)
              GROUP BY 1, 2, 3)
            SELECT count(*) FROM v_motorcycle_accident_rate vw
            JOIN ours USING (accident_year, engine_cc_band_code, manufacture_year)
            WHERE vw.in_accidents <> ours.n""").fetchone()[0]
        assert diff == 0
    finally:
        con.close()
    r = run(live, "two_wheelers", from_year=2019, to_year=2024, view="table")
    assert r.kind == "table", r.data
    moto = [row for row in r.data["rows"] if row[5] is not None]
    assert len(moto) == 24                                                   # 6 years x 4 bands, zero-filled grid
    fleets = {row[2]: row[5] for row in moto}
    assert sum(fleets.values()) > 100_000                                    # the FULL fleet, not accident cohorts
    assert run(live, "two_wheelers", from_year=2012, to_year=2024).data.startswith("# ❌")
    chart = run(live, "two_wheelers", from_year=2019, to_year=2024)
    assert chart.kind == "chart" and chart.data["png_base64"]


# ── P3 ──

def test_hotspot_map_live(live):
    d = run(live, "hotspot_map", from_year=2019, to_year=2024, view="chart").data
    row = d["rows"][0]                                                    # == segment_rates' top count row
    assert row[:4] == [70, 120, "צומת יסיף", "כניסה לגדידה רח 115"] and row[4:9] == [66.2, 67.4, 176, 16, 176]
    assert row[9:11] == [32.96137, 35.15391] and row[11:] == [2019, 2023, 0, "road:70/66.2-67.4", 1]
    cov = d["coverage"]
    assert (cov["matched"], cov["total"], cov["pct"], cov["with_coords"], cov["outside_bbox"]) == (15366, 20355, 75.5, 20247, 0)
    assert d["map"] == {"units_listed": 30, "units_placed": 30, "units_omitted": 0, "points": 0,
                        "bbox": [34.58164, 31.18852, 35.33113, 32.97858]}
    assert d["caveats"][0].startswith("108 מתוך 20,355") and len(d["caveats"]) == 4
    png_of(d)
    whole = run(live, "hotspot_map", from_year=2017, view="chart").data["coverage"]
    assert (whole["matched"], whole["total"]) == (19865, 28213)            # the segment_rates coverage pin
    default = run(live, "hotspot_map", view="chart").data                   # 2008-2024: static + as-of geometry
    assert default["rows"][0][:2] == [20, 13] and default["rows"][0][6] == 347 and default["rows"][0][13] == 167
    dc = default["coverage"]
    assert (dc["matched"], dc["total"], dc["static_matched"], dc["asof_matched"], dc["with_coords"]) == (49185, 64772, 29320, 19865, 64091)
    njd = run(live, "hotspot_map", unit="njunctions", view="chart").data
    nj = njd["rows"][0]
    assert nj[:3] == [323, "מחלף מורשה", 219] and nj[7:9] == ["dim", 2] and nj[11] == "njunction:323"
    assert (njd["coverage"]["matched"], njd["coverage"]["total"]) == (21972, 22517)       # one 99999999 row excluded
    ujd = run(live, "hotspot_map", unit="ujunctions", view="chart").data
    uj = ujd["rows"][0]
    assert uj[:5] == [5000, 14900823, "תל אביב - יפו", "חיל השריון", "קבוץ גלויות"]       # ONE row's pair, never "X / X"
    assert uj[5] == 270 and uj[10] == "dim" and uj[14] == "ujunction:5000/14900823"
    assert all(r[3] != r[4] for r in ujd["rows"]) and not any(r[1] == 99999999 for r in ujd["rows"])
    assert (ujd["coverage"]["matched"], ujd["coverage"]["total"], ujd["coverage"]["pct"]) == (66592, 70084, 95.0)
    label = next(f["properties"]["label"] for f in ujd["geojson"]["features"] if f["properties"]["kind"] == "unit")
    assert run(live, "before_after", site=uj[14], change_year=2015, view="chart").data["site_label"] == label
    r60 = run(live, "hotspot_map", road=60, view="table").data["rows"][0]
    assert r60[:2] == [60, 818] and r60[6] == 310 and r60[14] == "road:60/49.8-70.4"
    early = run(live, "hotspot_map", from_year=2005, to_year=2007)
    assert early.kind == "markdown" and early.data.startswith("# ❌") and "מ-2008" in early.data
    pts = run(live, "hotspot_map", from_year=2019, to_year=2024, top_n=5, points=True, view="chart").data
    assert pts["map"]["points"] == 702 and pts["caveats"][-1].startswith("נקודות: 702 מתוך 702")


# ── P10 ──

def test_map_scene_live(live):
    """The מפה חיה envelope on the live copy: the columnar cloud equals an inline count of its own predicate
    (equality, not a magic number), the site layers repeat the hotspot leaders, the gazetteer is real."""
    d = run(live, "map_scene", from_year=2019, to_year=2024, twin=False, view="chart").data
    cloud = d["cloud"]
    assert {len(cloud[k]) for k in ("lon", "lat", "year", "sev", "night")} == {cloud["n"]}
    import duckdb
    con = duckdb.connect(str(LIVE), read_only=True)
    try:
        n = con.execute("SELECT count(*) FROM accidents WHERE case_type_code = 1 AND year BETWEEN 2019 AND 2024"
                        " AND latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 36.0").fetchone()[0]
    finally:
        con.close()
    assert cloud["n"] == n == 62487 and not cloud["capped"]
    assert d["png_base64"] is None                                           # twin=False: the page's own fetch
    assert d["sites"]["segments"][0]["site_key"] == "road:70/66.2-67.4"      # the hotspot pin, same SQL, same years
    assert d["sites"]["njunctions"][0]["site_key"] == "njunction:433"        # 2019-2024 leaders (433=96, not 323)
    assert d["sites"]["ujunctions"][0]["site_key"] == "ujunction:3000/26510545"
    assert len(d["gazetteer"]) == 672 and d["gazetteer"][0]["n"] >= d["gazetteer"][-1]["n"]
    default = run(live, "map_scene", view="chart").data                      # 2008-2024, WITH the PNG twin
    assert default["cloud"]["n"] == 218144 and default["coverage"]["total"] == 218951
    assert not default["cloud"]["capped"] and default["denominator"]["kind"] == "counts"
    assert default["sites"]["njunctions"][0]["site_key"] == "njunction:323"  # the default-range hotspot pins
    assert default["sites"]["ujunctions"][0]["site_key"] == "ujunction:5000/14900823"
    png_of(default)
    early = run(live, "map_scene", from_year=2005, to_year=2007)
    assert early.kind == "markdown" and early.data.startswith("# ❌") and "מ-2008" in early.data
    capped = run(live, "map_scene", from_year=2019, to_year=2024, max_points=1000, twin=False, view="chart").data
    assert capped["cloud"]["n"] == 1000 and capped["cloud"]["capped"]
    assert any("הוגבל" in c for c in capped["caveats"])


def test_site_profile_live_counts_only_without_a_deployment(live):
    """The click panel on the live copy, no deployment in the tmp data dir: junctions carry the golden-rule
    caveat and NO model keys; a bare road/seg resolves to the hotspot's exact site key."""
    d = run(live, "site_profile", site="njunction:323", view="chart").data
    assert d["site"]["label"] == "צומת 323 · מחלף מורשה"
    assert d["splits"]["accidents"] == 219                                   # the hotspot njunction pin, 2008-2024
    assert "model" not in d and "severity_rel" not in d and "model_id" not in d
    assert any("אין נפח תנועה לצמתים" in c for c in d["caveats"])
    # bare 70/120 resolves via the LATEST vintage (66.2-67.4, src 2024) — every earlier vintage spans
    # 66.2-78.7, so the literal-km strip holds 44 while the per-year assignment counted 176: two instruments,
    # and the ROAD_STRIP_RULE caveat says so
    b = run(live, "site_profile", site="70/120", view="chart").data
    assert b["site"]["key"] == "road:70/66.2-67.4" and b["splits"]["accidents"] == 44
    assert any("טווח הק״מ המילולי" in c for c in b["caveats"])
    card = run(live, "site_profile", site="njunction:323", view="markdown")
    lines = card.data.splitlines()
    assert lines[0].startswith("מכנה:") and lines[-1].startswith("מקור הנתונים")
