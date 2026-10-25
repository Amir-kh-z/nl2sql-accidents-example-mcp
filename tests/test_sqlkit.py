# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import itertools
import math
from decimal import Decimal

import pytest

from nl2sql_roadsafety.sqlkit import (ActionError, GRANULARITY, MEASURES, PROFILE_DIMS, ROAD_TYPES, Refusal,
                                     as_choice, as_float, as_int, build_before_after_sql, build_segment_rates_sql,
                                     build_severity_profile_sql, build_trend_sql, build_vehicle_cells_sql,
                                     build_weather_check_sql, byar_ci, byar_sql, control_flag, did_math, double_did,
                                     exposure_year_range, ilit, lit, other_road_sql, parse_site_key, scalar, slit,
                                     units_count_sql, year_in_coverage, year_range)


def test_as_int_accepts_numbers_and_numeric_strings():
    assert as_int("2024", "y") == 2024
    assert as_int(2024.0, "y") == 2024
    assert as_int(" 2023.0 ", "y") == 2023
    assert as_int(0, "y") == 0


@pytest.mark.parametrize("bad", ["abc", True, 2023.5, float("nan"), None, ""])
def test_as_int_refuses_by_name(bad):
    with pytest.raises(ActionError, match="from_year"):
        as_int(bad, "from_year")


def test_year_in_coverage_refuses_outside_the_data():
    with pytest.raises(Refusal) as exc:
        year_in_coverage(2030, "year")
    assert "2030" in exc.value.reason and "31.12.2024" in exc.value.reason
    with pytest.raises(Refusal) as exc:
        year_in_coverage(2000, "year")
    assert "2005" in exc.value.reason
    assert year_in_coverage(2024, "year") == 2024


def test_year_range_orders_and_covers():
    with pytest.raises(ActionError, match="swap"):
        year_range(2024, 2005)
    assert year_range("2010", 2012.0) == (2010, 2012)


def test_as_choice_lists_the_legal_set():
    with pytest.raises(ActionError) as exc:
        as_choice("x", "measure", MEASURES)
    msg = str(exc.value)
    assert "Unknown measure 'x'" in msg
    assert {m for m in MEASURES if m in msg} == set(MEASURES)


def test_refusal_carries_detail():
    assert Refusal("r", detail="d").detail == "d"


def test_literals():
    assert ilit(7) == "7"
    with pytest.raises(ValueError):
        ilit(True)
    with pytest.raises(ValueError):
        ilit("7")
    assert slit("a'b") == "'a''b'"
    with pytest.raises(ValueError):
        lit(float("inf"))
    assert lit(2.5) == "2.5"


def test_scalar_is_json_safe():
    assert scalar(Decimal("1.5")) == 1.5
    assert scalar(float("nan")) is None
    assert scalar(float("inf")) is None
    assert scalar(dt.date(2024, 12, 31)) == "2024-12-31"
    assert scalar(True) is True
    assert scalar(3) == 3 and scalar("x") == "x" and scalar(None) is None


def test_byar_ci():
    lo, hi = byar_ci(10)
    assert lo == pytest.approx(4.79, abs=0.01) and hi == pytest.approx(18.39, abs=0.01)
    lo, hi = byar_ci(100)
    assert lo == pytest.approx(81.36, abs=0.01) and hi == pytest.approx(121.63, abs=0.01)
    lo, hi = byar_ci(0)
    assert lo == 0.0 and hi == pytest.approx(3.67, abs=0.01)
    lo2, hi2 = byar_ci(10, denom=2.0)
    assert lo2 == pytest.approx(byar_ci(10)[0] / 2) and hi2 == pytest.approx(byar_ci(10)[1] / 2)


@pytest.mark.parametrize("measure,granularity,road_type",
                         list(itertools.product(MEASURES, GRANULARITY, ROAD_TYPES)))
def test_build_trend_sql_honours_the_golden_rules(measure, granularity, road_type):
    sql = build_trend_sql(measure, granularity, road_type, 2020, 2024)
    person = MEASURES[measure][0] == "involved"
    assert "case_type_code = 1" in sql
    assert sql.splitlines()[0].isascii()
    composite = "a.accident_id = i.accident_id AND a.case_type_code = i.case_type_code"
    has_join_in_counts = "JOIN accidents a ON" in sql.split("counts AS")[1]
    assert has_join_in_counts == (person and road_type != "all")
    assert ("coverage AS" in sql) == person
    if "accident_id = i.accident_id" in sql:
        assert composite in sql
    assert not sql.rstrip().endswith(";")
    if granularity == "month":
        assert "range(1, 13)" in sql
    if road_type != "all":
        codes = ", ".join(str(c) for c in ROAD_TYPES[road_type][0])
        assert f"road_type_code IN ({codes})" in sql


def test_other_road_sql_shape():
    sql = other_road_sql(2022, 2024)
    assert "NOT IN (1, 2, 3, 4)" in sql and "case_type_code = 1" in sql


def test_other_road_sql_on_fixture(ctx):
    assert ctx.query(other_road_sql(2022, 2024))[1] == [(1,)]
    assert ctx.query(other_road_sql(2022, 2023))[1] == [(0,)]


# ── P2 helpers ──

def test_as_float_and_exposure_years():
    assert as_float("0.1", "t") == 0.1 and as_float(1, "t") == 1.0
    for bad in (True, "abc", float("nan"), float("inf")):
        with pytest.raises(ActionError, match="t "):
            as_float(bad, "t")
    with pytest.raises(Refusal) as exc:
        exposure_year_range(2016, 2020)
    assert "2017" in exc.value.reason
    with pytest.raises(ActionError, match="swap"):
        exposure_year_range(2024, 2017)
    assert exposure_year_range("2019", 2021.0) == (2019, 2021)


@pytest.mark.parametrize("n", [0, 1, 3, 10, 100])
def test_byar_sql_matches_byar_ci(ctx, n):
    lo, hi = byar_sql(str(n))
    got = ctx.query(f"SELECT {lo} AS lo, {hi} AS hi")[1][0]
    assert got[0] == pytest.approx(byar_ci(n)[0], abs=1e-6) and got[1] == pytest.approx(byar_ci(n)[1], abs=1e-6)


def test_units_cte_dedups_vintages(ctx):
    assert ctx.query(units_count_sql())[1] == [(6, 3)]
    rows = ctx.query("WITH " + units_count_sql().split("WITH ", 1)[1].split("\nSELECT")[0]
                     + "\nSELECT road, seg, year, km_to FROM units ORDER BY 1, 2, 3")[1]
    assert (1.0, 10.0, 2020, 10.0) in rows and len(rows) == 6


def test_parse_site_key():
    s = parse_site_key("road:60/96.0-98.8")
    assert (s.kind, s.road, s.km_from, s.km_to) == ("road", 60, 96.0, 98.8)
    assert parse_site_key(" njunction:433 ").code == 433
    u = parse_site_key("ujunction:5000/777")
    assert (u.city, u.code) == (5000, 777)
    for bad in ("road:60/98.8-96.0", "road:60/-5-10", "road:60/96-96", "njunction:0", "njunction:99",
                "ujunction:5000", "foo", "", "road:0/1-2"):
        with pytest.raises(ActionError):
            parse_site_key(bad)


def test_did_math_and_double():
    assert did_math(8, 2, 16, 8, 6)["status"] == "n/a"
    d = did_math(8, 2, 16, 8, 2)
    assert d["ratio"] == pytest.approx(0.5) and d["se2"] == pytest.approx(0.6959, abs=1e-4)
    assert d["lo"] == pytest.approx(0.0975, abs=1e-4) and d["hi"] == pytest.approx(2.5648, abs=1e-4)
    g = did_math(6, 6, 12, 12, 6)
    assert g["ratio"] == 1.0 and g["se2"] == pytest.approx(0.467692, abs=1e-6)
    x = double_did(d, g)
    assert x["ratio"] == pytest.approx(0.5) and x["se2"] == pytest.approx(1.163592, abs=1e-6)
    assert x["lo"] == pytest.approx(0.0604, abs=1e-4) and x["hi"] == pytest.approx(4.1417, abs=1e-4)
    assert did_math(0, 3, 10, 10, 1)["status"] == "n/a" and did_math(3, 3, 0, 10, 1)["status"] == "n/a"
    assert double_did(d, did_math(0, 0, 1, 1, 1))["status"] == "n/a"


def test_control_flag():
    assert control_flag(1.0, 0.667) is True
    assert control_flag(0.8861, 0.9538) is False
    assert control_flag(1.0, 0.75) is False            # exactly 25 %: strict
    assert control_flag(0, 0.5) is True and control_flag(None, None) is False


def test_p2_builders_honour_the_golden_rules():
    for order in ("rate_lo", "rate", "count"):
        for sev in ("all", "ksi"):
            sql = build_segment_rates_sql(0, 2019, 2021, sev, order, 10)
            assert sql.splitlines()[0].isascii() and not sql.rstrip().endswith(";")
            assert "case_type_code = 1" in sql and "road_km / 10.0 <  u.km_to" in sql
            assert "QUALIFY row_number() OVER (PARTITION BY a.accident_id, a.case_type_code" in sql
            assert "traffic_adt_filled" not in sql
    assert "d.road = 60" in build_segment_rates_sql(60, 2019, 2021, "all", "rate", 5)
    for by, (_, _, _, needs_join, _) in PROFILE_DIMS.items():
        sql = build_severity_profile_sql(by, 2005, 2024)
        assert ("JOIN accidents a ON a.accident_id = i.accident_id AND a.case_type_code = i.case_type_code" in sql) == needs_join
        assert "injury_severity_code IN (1, 2, 3)" in sql and sql.splitlines()[0].isascii()
    assert "cc_band <> 0" in build_vehicle_cells_sql("involvements", "known_engine")
    assert "cc_band <> 0" not in build_vehicle_cells_sql("ksi", "all")
    ba = build_before_after_sql(parse_site_key("road:60/96.0-98.8"), 2017, 3)
    assert "case_type_code IN (1, 3)" in ba and "road1_number = 60" in ba and "BETWEEN 2014 AND 2016" in ba
    body = ba.split("\n", 1)[1]
    assert "2017" not in body and "BETWEEN 2014 AND 2016" in body and "BETWEEN 2018 AND 2020" in body
    w = build_weather_check_sql(2005, 2024, 0.1)
    assert "precipitation_mm > 0.1" in w and "case_type_code = 1" in w
