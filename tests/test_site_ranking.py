# -*- coding: utf-8 -*-
"""site_ranking and the excess-mode map on the synthetic panel (a deployed model exists by construction)."""
from __future__ import annotations

import sys

import pytest

from helpers import json_safe, png_of, run

xgboost = pytest.importorskip("xgboost")


@pytest.fixture()
def deployed_ctx(studio_ctx):
    run(studio_ctx, "studio_train_site", train_until=2022)
    run(studio_ctx, "studio_validate")
    r = run(studio_ctx, "studio_deploy")
    assert "נפרס" in r.data, r.data
    return studio_ctx


def test_ranking_math_and_faces(deployed_ctx):
    r = run(deployed_ctx, "site_ranking", view="table")
    assert r.kind == "table", r.data
    cols, rows = r.data["columns"], r.data["rows"]
    ci = {c: i for i, c in enumerate(cols)}
    assert len(rows) == 30 and [row[ci["rank"]] for row in rows] == list(range(1, 31))
    for row in rows:
        assert row[ci["excess"]] == pytest.approx(row[ci["observed"]] - row[ci["mu"]], abs=0.02)
        assert row[ci["significant"]] == (row[ci["observed"]] > row[ci["hi90"]])
        assert row[ci["lo90"]] <= row[ci["mu"]] <= row[ci["hi90"]]
        assert min(row[ci["mu"]], row[ci["observed"]]) <= row[ci["eb"]] <= max(row[ci["mu"]], row[ci["observed"]])
        assert str(row[ci["site_key"]]).startswith("road:")
    assert rows == sorted(rows, key=lambda x: (-x[ci["excess"]], -x[ci["observed"]]))
    chart = run(deployed_ctx, "site_ranking", view="chart")
    spec = chart.data
    assert spec["denominator"]["kind"] == "exposure" and "מודל אתר פרוס" in spec["denominator"]["label"]
    assert any("excess = נצפה − צפוי" in c for c in spec["caveats"])
    assert any("מתאם ולא סיבתיות" in c for c in spec["caveats"])
    png_of(spec)
    json_safe(chart)
    sql_face = run(deployed_ctx, "site_ranking", view="sql").data
    assert "a.year = u.year" in sql_face and "traffic_adt_filled" not in sql_face
    r4 = run(deployed_ctx, "site_ranking", road=4, view="table").data
    assert r4["rows"] and all(row[0] == 4 for row in r4["rows"])
    assert run(deployed_ctx, "site_ranking", from_year=2010).data.startswith("# ❌")
    assert run(deployed_ctx, "site_ranking", top_n=0).kind == "error"
    assert run(deployed_ctx, "site_ranking", road=777).data.startswith("# ❌")


def test_excess_map_mode(deployed_ctx):
    m = run(deployed_ctx, "hotspot_map", color_by="excess", view="chart")
    spec = m.data
    assert spec["color_by_effective"] == "excess" and spec["denominator"]["kind"] == "exposure"
    assert spec["columns"][-6:] == ["mu", "excess", "eb", "lo90", "hi90", "significant"]
    ci = {c: i for i, c in enumerate(spec["columns"])}
    assert spec["rows"] == sorted(spec["rows"], key=lambda r: (-r[ci["excess"]], -r[ci["accidents"]]))
    ranking = run(deployed_ctx, "site_ranking", view="table").data["rows"]
    assert (spec["rows"][0][0], spec["rows"][0][1]) == (ranking[0][0], ranking[0][1])   # one ordering rule
    unit = next(f["properties"] for f in spec["geojson"]["features"] if f["properties"]["kind"] == "unit")
    assert {"mu", "excess", "eb", "lo90", "hi90", "significant"} <= set(unit)
    assert any(c.startswith("excess קיים מ-2017") for c in spec["caveats"])             # the 2008 default was clipped
    assert any("מודל site-" in c for c in spec["caveats"])
    assert "| model site-" in spec["basis"] and "excess" in spec["stamp"]
    assert not any(c.startswith("ספירות אינן סיכון") for c in spec["caveats"])
    png_of(spec)
    json_safe(m)
    m2 = run(deployed_ctx, "hotspot_map", view="chart").data                            # observed mode is untouched
    assert m2["color_by_effective"] == "observed" and "excess" not in m2["columns"]
    assert m2["denominator"]["kind"] == "counts"


def test_excess_falls_back_without_xgboost(deployed_ctx, monkeypatch):
    monkeypatch.setitem(sys.modules, "xgboost", None)
    m = run(deployed_ctx, "hotspot_map", color_by="excess", view="chart")
    assert m.kind == "chart", m.data
    spec = m.data
    assert spec["color_by_effective"] == "observed"
    # one merged degrade line (map_scene's rule, 2026-09-06) — the reason rides inside the excess caveat
    assert any("התבקשה צביעה לפי excess" in c and "pip install" in c for c in spec["caveats"])
    assert spec["denominator"]["kind"] == "counts"
