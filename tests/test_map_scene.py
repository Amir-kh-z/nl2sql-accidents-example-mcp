# -*- coding: utf-8 -*-
"""map_scene (P10): the columnar-cloud contract, the SQL cap, the site layers riding hotspot_map's rules,
the excess mode (segments only — the golden rule pinned with AND without a deployment), the gazetteer, the
road scope, the empty-range refusal and the ledger-line size."""
from __future__ import annotations

import json

import pytest

from nl2sql_roadsafety.sqlkit import MAP_CLOUD_BOUNDS
from nl2sql_roadsafety.studio import ledger
from helpers import json_safe, run

LAT_LO, LAT_HI, LON_LO, LON_HI = 29.0, 34.0, 34.0, 36.0        # GEO_PREDICATE, spelled out


def _spec(ctx, **inputs):
    r = run(ctx, "map_scene", view="chart", **inputs)
    assert r.kind == "chart", r.data
    json_safe(r)
    return r.data


def test_columnar_cloud_is_consistent_and_inside_the_bbox(ctx):
    spec = _spec(ctx)
    cloud = spec["cloud"]
    n = cloud["n"]
    assert n > 0 and not cloud["capped"]
    assert {len(cloud[k]) for k in ("lon", "lat", "year", "sev", "night")} == {n}
    assert all(LAT_LO <= v <= LAT_HI for v in cloud["lat"])
    assert all(LON_LO <= v <= LON_HI for v in cloud["lon"])
    assert set(cloud["sev"]) <= {1, 2, 3}
    assert set(cloud["night"]) <= {0, 1, 2}
    assert all(2008 <= y <= 2024 for y in cloud["year"])
    # uncapped, the cloud IS the geocoded population — the same predicate on both statements
    assert n == spec["coverage"]["geocoded"]
    lo0, la0, lo1, la1 = spec["meta"]["bbox"]
    assert LON_LO <= lo0 <= lo1 <= LON_HI and LAT_LO <= la0 <= la1 <= LAT_HI


def test_cap_is_honored_with_an_honest_caveat(ctx):
    spec = _spec(ctx, max_points=MAP_CLOUD_BOUNDS[0])
    cloud = spec["cloud"]
    assert cloud["n"] == MAP_CLOUD_BOUNDS[0] < spec["coverage"]["geocoded"]
    assert cloud["capped"] and spec["meta"]["capped"]
    assert any("הוגבל" in c for c in spec["caveats"])


def test_site_layers_ride_the_hotspot_rules(ctx):
    spec = _spec(ctx)
    sites = spec["sites"]
    assert set(sites) == {"segments", "njunctions", "ujunctions"}
    seg_keys = [e["site_key"] for e in sites["segments"]]
    assert seg_keys and all(k.startswith("road:") for k in seg_keys)
    assert [e["rank"] for e in sites["segments"]] == list(range(1, len(seg_keys) + 1))
    assert any(e["code"] == 433 for e in sites["njunctions"])
    uj_keys = [e["site_key"] for e in sites["ujunctions"]]
    assert "ujunction:5000/777" in uj_keys
    assert not any("99999999" in k for k in uj_keys)               # the Z1 sentinel never ranks
    assert all(e["label"] for layer in sites.values() for e in layer)
    # the table face = the segments ranking, hand-off compatible
    assert "site_key" in spec["columns"] and spec["x"] == "site_key" and spec["y"] == "accidents"


def test_road_scope_drops_the_urban_layer_and_filters_the_cloud(ctx):
    spec = _spec(ctx, road=1)
    assert spec["sites"]["ujunctions"] == [] and spec["sites_sql"]["ujunctions"] is None
    assert any("הצמתים העירוניים" in c for c in spec["caveats"])
    _, rows = ctx.query(
        "SELECT count(*) FROM accidents WHERE case_type_code = 1 AND year BETWEEN 2008 AND 2024 "
        "AND road1_number = 1 AND latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 36.0")
    assert spec["cloud"]["n"] == rows[0][0]


def test_twin_false_skips_the_png_and_flips_the_renderer(ctx):
    spec = _spec(ctx, twin=False)
    assert spec["png_base64"] is None and spec["renderer"] == "data"
    with_twin = _spec(ctx)
    assert with_twin["png_base64"] and with_twin["renderer"] == "png"


def test_gazetteer_lists_only_geocoded_localities(ctx):
    gaz = _spec(ctx)["gazetteer"]
    assert gaz and all(g["lat"] is not None and g["lon"] is not None and g["city"] > 0 for g in gaz)
    assert any(g["city"] == 5000 for g in gaz)


def test_a_legal_empty_range_is_a_refusal_card(ctx):
    r = run(ctx, "map_scene", from_year=2005, to_year=2007)
    assert r.kind == "markdown"
    assert r.data.startswith("# ❌"), r.data


@pytest.fixture()
def deployed_ctx(studio_ctx):
    pytest.importorskip("xgboost")
    run(studio_ctx, "studio_train_site", train_until=2022)
    run(studio_ctx, "studio_validate")
    assert "נפרס" in run(studio_ctx, "studio_deploy").data
    return studio_ctx


def test_excess_mode_reranks_segments_and_never_touches_junctions(deployed_ctx):
    d = run(deployed_ctx, "map_scene", color_by="excess", view="chart").data
    assert d["color_by_effective"] == "excess" and d["model_id"]
    segs = d["sites"]["segments"]
    assert segs and all(("excess" in e and "significant" in e and "mu" in e) for e in segs)
    assert [e["rank"] for e in segs] == list(range(1, len(segs) + 1))
    assert all(segs[i]["excess"] >= segs[i + 1]["excess"] for i in range(len(segs) - 1))
    for kind in ("njunctions", "ujunctions"):
        assert all("excess" not in e and "mu" not in e for e in d["sites"][kind])   # the golden rule, structural
    assert d["denominator"]["kind"] == "exposure"
    assert any("excess קיים למקטעים בלבד" in c for c in d["caveats"])
    assert "mu" in d["columns"] and "significant" in d["columns"]                   # the table face carries the merge
    json_safe(run(deployed_ctx, "map_scene", color_by="excess", view="chart"))


def test_excess_mode_falls_back_without_a_deployment(ctx):
    d = run(ctx, "map_scene", color_by="excess", from_year=2019, to_year=2021, view="chart").data
    assert d["color_by"] == "excess" and d["color_by_effective"] == "observed"
    assert "model_id" not in d and d["denominator"]["kind"] == "counts"
    assert any("אין מודל אתר פרוס" in c for c in d["caveats"])
    assert all("excess" not in e for e in d["sites"]["segments"])


def test_ledger_line_stays_small(ctx):
    r = run(ctx, "map_scene", view="chart")
    entry = ledger.entry_for("map_scene", {"view": "chart"}, r, "0.10.0")
    assert len(json.dumps(entry, ensure_ascii=False, default=str).encode("utf-8")) < 4096
