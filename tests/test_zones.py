# -*- coding: utf-8 -*-
"""zone_ranking + city_ranking (P14): the cumulative geographic snapshot — a separate, undated universe.
Pins: exact fixture rows per measure (the per-capita and density ORDERS differ — the accident_index
story), the mandatory separate-universe / mismatch / index-density caveats, the 'קוד' fallback labels,
the min_pop and no-injured guards, the refusal path, and SQL-re-execution equality."""
from __future__ import annotations

import pytest

from nl2sql_roadsafety.actions import city_ranking, zone_ranking
from nl2sql_roadsafety.sqlkit import rows_safe
from helpers import json_safe, png_of, run

ZONE_COLS = ["label", "value", "accidents", "population", "area_km2", "land_use"]
CITY_COLS = ["city", "region", "value", "accidents", "killed", "area_km2"]


def test_no_year_inputs_by_design():
    assert set(zone_ranking.ACTION.inputs) == {"measure", "land_use", "min_pop", "top_n", "view"}
    assert set(city_ranking.ACTION.inputs) == {"measure", "top_n", "view"}


def test_zone_per_capita_default(ctx):
    r = run(ctx, "zone_ranking", view="chart")
    assert r.kind == "chart", r.data
    spec = r.data
    assert spec["type"] == "accidents/zone_ranking" and spec["measure"] == "per_capita"
    assert spec["columns"] == ZONE_COLS
    # min_pop 500 removes the through-traffic zone 102 (pop 200) and the zero-population zone 103
    assert spec["rows"] == [
        ["קוד 8888 · אזור 104", 30.0, 30, 1000, 4.0, 1],
        ["תל אביב - יפו · אזור 101", 20.0, 40, 2000, 1.0, 1],
        ["אשקלון · אזור 106", 10.0, 8, 800, 0.8, 5],
        ["אשקלון · אזור 105", 5.0, 25, 5000, 2.5, 4],
    ]
    assert spec["below_min_pop"] == 2 and spec["snapshot"] == 202604
    assert spec["universe"] == {"zones": 6, "accidents": 160, "killed": 4, "injured": 98, "population": 9000}
    c = spec["caveats"]
    assert c[0] == "סף אוכלוסייה מזערית (500 תושבים) הסיר 2 מתוך 6 אזורים בתחולה — בלעדיו אזורי תעסוקה ותנועה עוברת מזנקים לראש הדירוג"
    assert any("חותמת פרסום 202604" in x and "אין להשוות" in x for x in c)
    assert any("סך הצילום: 160 תאונות, 4 הרוגים ו-98 נפגעים" in x and "45 תאונות עם נפגעים ו-7 הרוגים" in x
               and "יקום נתונים נפרד" in x for x in c)
    assert any("אוכלוסיית 2018" in x for x in c)
    assert any("משויכות לאזור האירוע" in x for x in c)
    assert any("ממפת התוסף" in x for x in c)                       # no land-use field in code_lookups
    assert all(";" not in x and "\n" not in x for x in c)
    assert spec["denominator"]["kind"] == "exposure"
    assert spec["denominator"]["label"] == "ל-1,000 תושבים (אוכלוסיית 2018)"
    assert spec["basis"].isascii() and spec["stamp"].isascii() and "snapshot 202604" in spec["basis"]
    assert rows_safe(ctx.query(spec["sql"])[1]) == spec["rows"]    # the spec's SQL reproduces its rows
    png_of(spec)
    json_safe(r)


def test_zone_density_and_the_index_caveat(ctx):
    spec = run(ctx, "zone_ranking", measure="density", view="chart").data
    # density order differs from per-capita order (zone 102 leads here, 104 led there); 105 vs 106 tie on
    # 10.0 → the deterministic label tie-break
    assert spec["rows"] == [
        ["תל אביב - יפו · אזור 102", 90.0, 45, 200, 0.5, 2],
        ["תל אביב - יפו · אזור 101", 40.0, 40, 2000, 1.0, 1],
        ["אשקלון · אזור 105", 10.0, 25, 5000, 2.5, 4],
        ["אשקלון · אזור 106", 10.0, 8, 800, 0.8, 5],
        ["קוד 8888 · אזור 104", 7.5, 30, 1000, 4.0, 1],
        ["בני ברק · אזור 103", 6.0, 12, 0, 2.0, 3],
    ]
    # the analytical point: accident_index IS the density (planted equal → r pins at exactly 1.000)
    corr_line = next(x for x in spec["caveats"] if "מתאם" in x)
    assert "accident_index" in corr_line and "מתאם 1.000" in corr_line and "0.93" in corr_line
    assert spec["corr_index_density"] == pytest.approx(1.0, abs=1e-9)
    assert spec["denominator"]["kind"] == "exposure" and spec["denominator"]["label"] == 'לקמ"ר'
    assert rows_safe(ctx.query(spec["sql"])[1]) == spec["rows"]


def test_zone_ped_share_and_min_pop_one(ctx):
    spec = run(ctx, "zone_ranking", measure="ped_share", view="table")
    assert spec.kind == "table"
    # ped_share ships its denominator as a 7th column and breaks % ties by it (refuter 2026-09-06):
    # 104/105 tie on 40.0 → 105 first (25 injured > 15); zone 106 (no injured) is excluded + counted
    assert spec.data["columns"][-1] == "injured"
    assert spec.data["rows"] == [
        ["אשקלון · אזור 105", 40.0, 25, 5000, 2.5, 4, 25],
        ["קוד 8888 · אזור 104", 40.0, 30, 1000, 4.0, 1, 15],
        ["תל אביב - יפו · אזור 102", 30.0, 45, 200, 0.5, 2, 30],
        ["תל אביב - יפו · אזור 101", 25.0, 40, 2000, 1.0, 1, 20],
        ["בני ברק · אזור 103", 0.0, 12, 0, 2.0, 3, 8],
    ]
    chart = run(ctx, "zone_ranking", measure="ped_share", view="chart").data
    assert any(x.startswith("1 אזורים ללא נפגעים") for x in chart["caveats"])
    # the tiny-denominator honesty line: 104 (15) and 103 (8) are below twenty injured
    assert any(x.startswith("2 מתוך 5 השורות המוצגות עם פחות מעשרים נפגעים") for x in chart["caveats"])
    assert chart["denominator"]["kind"] == "counts"
    # scope = zones that CAN carry the measure (6 in scope − 1 with no injured), not the raw universe
    assert chart["denominator"]["zones_in_scope"] == 5 and "of 5 zones" in chart["basis"]
    # the population-vintage caveat belongs to per_capita only
    assert not any("אוכלוסיית 2018," in x for x in chart["caveats"])
    # min_pop=1: only the zero-population zone drops — the through-traffic zone 102 tops per-capita (225/1,000)
    low = run(ctx, "zone_ranking", min_pop=1, view="table").data
    assert low["rows"][0] == ["תל אביב - יפו · אזור 102", 225.0, 45, 200, 0.5, 2]
    assert [r[0] for r in low["rows"]] == ["תל אביב - יפו · אזור 102", "קוד 8888 · אזור 104",
                                            "תל אביב - יפו · אזור 101", "אשקלון · אזור 106", "אשקלון · אזור 105"]


def test_zone_land_use_scope_and_labels(ctx):
    spec = run(ctx, "zone_ranking", measure="density", land_use="1", view="chart").data
    assert spec["rows"] == [
        ["תל אביב - יפו · אזור 101", 40.0, 40, 2000, 1.0, 1],
        ["קוד 8888 · אזור 104", 7.5, 30, 1000, 4.0, 1],
    ]
    assert spec["land_use"] == "1"
    assert spec["land_use_labels"] == {"1": "מגורים", "2": "מסחר", "3": "תעשייה", "4": "מוסדות", "5": "אחר"}
    # the per-capita filter count is scoped to the chosen land use (only zone 103, pop 0, is below 500 in lu=3)
    lu3 = run(ctx, "zone_ranking", measure="ped_share", land_use="3", view="chart").data
    assert [r[0] for r in lu3["rows"]] == ["בני ברק · אזור 103"]


def test_zone_refusal_and_errors(ctx):
    r = run(ctx, "zone_ranking", land_use="3")                     # per_capita in lu=3: only the pop-0 zone
    assert r.kind == "markdown" and r.data.startswith("# ❌"), r.data
    assert "מה לעשות" in r.data and "להקטין את סף האוכלוסייה" in r.data
    assert run(ctx, "zone_ranking", min_pop=0).kind == "error"
    assert run(ctx, "zone_ranking", top_n=0).kind == "error"
    assert run(ctx, "zone_ranking", top_n=101).kind == "error"
    assert run(ctx, "zone_ranking", measure="nope").kind == "error"
    assert run(ctx, "zone_ranking", view="nope").kind == "error"
    assert run(ctx, "zone_ranking", land_use="6").kind == "error"


def test_city_density_default(ctx):
    r = run(ctx, "city_ranking", view="chart")
    assert r.kind == "chart", r.data
    spec = r.data
    assert spec["type"] == "accidents/city_ranking" and spec["measure"] == "density"
    assert spec["columns"] == CITY_COLS
    assert spec["rows"] == [
        ["בני ברק", "רמת גן", 20.0, 140, 1, 7.0],
        ["תל אביב - יפו", "תל אביב", 7.7, 400, 5, 52.0],
        ["קוד 8888", "קוד 8888", 5.0, 50, 0, 10.0],
        ["אשקלון", "אשקלון", 2.0, 100, 2, 50.0],
    ]
    assert spec["snapshot"] == 202604 and spec["unnamed"] == 1
    assert spec["universe"] == {"cities": 4, "accidents": 690, "killed": 8, "area_km2": 119.0}
    c = spec["caveats"]
    assert any("חותמת פרסום 202604" in x and "אין להשוות" in x for x in c)
    assert any("סך הצילום: 690 תאונות ו-8 הרוגים על 119.0 קמ״ר" in x
               and "45 תאונות עם נפגעים ו-7 הרוגים" in x and "יקום נתונים נפרד" in x for x in c)
    assert any(x == "1 יישובים ללא שורה במילון היישובים מוצגים כקוד" for x in c)
    assert all(";" not in x and "\n" not in x for x in c)
    assert spec["denominator"]["kind"] == "exposure" and spec["denominator"]["label"] == 'לקמ"ר (שטח שיפוט)'
    assert spec["basis"].isascii() and "snapshot 202604" in spec["basis"]
    assert rows_safe(ctx.query(spec["sql"])[1]) == spec["rows"]
    png_of(spec)
    json_safe(r)


def test_city_total_and_ped_share(ctx):
    total = run(ctx, "city_ranking", measure="total", view="table").data
    assert total["rows"] == [
        ["תל אביב - יפו", "תל אביב", 400, 400, 5, 52.0],
        ["בני ברק", "רמת גן", 140, 140, 1, 7.0],
        ["אשקלון", "אשקלון", 100, 100, 2, 50.0],
        ["קוד 8888", "קוד 8888", 50, 50, 0, 10.0],
    ]
    chart = run(ctx, "city_ranking", measure="total", view="chart").data
    assert chart["denominator"]["kind"] == "counts"
    assert any("ספירות אינן סיכון" in x for x in chart["caveats"])
    ped = run(ctx, "city_ranking", measure="ped_share", view="chart").data
    assert ped["columns"][-1] == "injured"
    assert ped["rows"] == [
        ["בני ברק", "רמת גן", 30.0, 140, 1, 7.0, 100],
        ["תל אביב - יפו", "תל אביב", 20.0, 400, 5, 52.0, 300],
        ["אשקלון", "אשקלון", 12.5, 100, 2, 50.0, 80],
    ]
    assert any(x.startswith("1 יישובים ללא נפגעים") for x in ped["caveats"])
    # every shown denominator is >= 20 injured on this fixture — the tiny-denominator line stays silent
    assert not any("מכנה זעיר" in x for x in ped["caveats"])
    top2 = run(ctx, "city_ranking", top_n=2, view="table").data
    assert len(top2["rows"]) == 2 and top2["rows"][0][0] == "בני ברק"


def test_city_errors(ctx):
    assert run(ctx, "city_ranking", top_n=0).kind == "error"
    assert run(ctx, "city_ranking", top_n=200).kind == "error"
    assert run(ctx, "city_ranking", measure="per_capita").kind == "error"    # no population column here
    assert run(ctx, "city_ranking", view="nope").kind == "error"
