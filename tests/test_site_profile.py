# -*- coding: utf-8 -*-
"""site_profile (P10): the golden-rule pins — junctions NEVER carry model measures (with and without
deployments), segments degrade to counts without a deployment and carry the full model block with one,
the severity block stays relative-only, bare road/seg resolution, refusals, and the Layer-0 card."""
from __future__ import annotations

import pytest

from nl2sql_roadsafety.actions.site_profile import _model_block
from nl2sql_roadsafety.envelope import CREDIT
from nl2sql_roadsafety.sqlkit import parse_site_key
from helpers import json_safe, run

FULL_SPAN = list(range(2008, 2025))


@pytest.fixture()
def deployed_ctx(studio_ctx):
    pytest.importorskip("xgboost")
    run(studio_ctx, "studio_train_site", train_until=2022)
    run(studio_ctx, "studio_validate")
    assert "נפרס" in run(studio_ctx, "studio_deploy").data
    return studio_ctx


@pytest.fixture()
def both_ctx(deployed_ctx):
    run(deployed_ctx, "studio_train_severity")
    assert "עבר את השער" in run(deployed_ctx, "studio_validate_severity").data
    assert "נפרס" in run(deployed_ctx, "studio_deploy", family="severity").data
    return deployed_ctx


def test_junction_profile_is_counts_only(ctx):
    r = run(ctx, "site_profile", site="njunction:433", view="chart")
    assert r.kind == "chart", r.data
    spec = r.data
    assert "model" not in spec and "severity_rel" not in spec and "model_id" not in spec
    assert "mu" not in spec["columns"]
    assert spec["denominator"]["kind"] == "counts"
    assert any("אין נפח תנועה לצמתים" in c for c in spec["caveats"])
    assert any("פרופיל החומרה המותנה אינו מוצג" in c for c in spec["caveats"])
    assert [row[0] for row in spec["rows"]] == FULL_SPAN                     # zero-filled: a quiet year is a zero
    a = spec["columns"].index("accidents")
    assert sum(row[a] for row in spec["rows"]) == spec["splits"]["accidents"] > 0
    json_safe(r)


def test_junction_model_block_is_structurally_unreachable(both_ctx):
    """The strong pin: even with a DEPLOYED site model, the model path is never entered for junction kinds —
    structure, not policy."""
    for key in ("njunction:433", "ujunction:5000/777"):
        block, mu_map, caveats = _model_block(both_ctx, parse_site_key(key), 2017, 2024)
        assert block is None and mu_map is None and caveats == []


def test_segment_degrades_without_deployment(ctx):
    # bare road/seg resolves to the LATEST vintage's key, so the model path reaches the registry and
    # degrades on "no deployment"; a literal km-range key may degrade earlier (not a panel key) — both honest
    r = run(ctx, "site_profile", site="1/10", view="chart")
    assert r.kind == "chart", r.data
    spec = r.data
    assert "model" not in spec
    assert spec["denominator"]["kind"] == "counts"
    assert any("אין מודל אתר פרוס" in c for c in spec["caveats"])
    assert any("ספירות אינן סיכון" in c for c in spec["caveats"])
    assert spec["site"]["kind"] == "road" and spec["site"]["lat"] is not None
    r2 = run(ctx, "site_profile", site="road:1/0-10", view="chart")
    assert r2.kind == "chart" and "model" not in r2.data
    assert any("מדדי המודל אינם מוצגים" in c or "אין מודל אתר פרוס" in c for c in r2.data["caveats"])


def test_segment_with_model_carries_the_full_block(both_ctx):
    top = run(both_ctx, "site_ranking", view="table").data["rows"][0]
    road, seg = top[0], top[1]
    r = run(both_ctx, "site_profile", site=f"{road}/{seg}", from_year=2008, to_year=2024, view="chart")
    assert r.kind == "chart", r.data
    spec = r.data
    mb = spec["model"]
    assert {"model_id", "mu", "excess", "eb", "lo90", "hi90", "significant", "verdict",
            "drivers", "from_year"} <= set(mb)
    assert mb["from_year"] == 2017                                           # the exposure-era clip
    assert any("עידן החשיפה" in c for c in spec["caveats"])
    assert spec["denominator"]["kind"] == "exposure" and spec["model_id"] == mb["model_id"]
    assert "mu" in spec["columns"]
    mu_col = spec["columns"].index("mu")
    assert all(row[mu_col] is None for row in spec["rows"] if row[0] < 2017)
    assert any(row[mu_col] is not None for row in spec["rows"] if row[0] >= 2017)
    assert 1 <= len(mb["drivers"]) <= 3 and all(d["label"] for d in mb["drivers"])
    sev = spec["severity_rel"]
    assert sev["n_persons"] > 0 and len(sev["relative"]) == 3
    assert any("יחסיות בלבד" in c for c in spec["caveats"])
    json_safe(r)
    card = run(both_ctx, "site_profile", site=f"{road}/{seg}", view="markdown")
    lines = card.data.splitlines()
    assert lines[0].startswith("מכנה:") and lines[-1] == CREDIT
    assert "המודל חוזה" in card.data and "פרופיל חומרה מותנה" in card.data


def test_bare_road_seg_resolves_via_the_latest_vintage(ctx):
    spec = run(ctx, "site_profile", site="1/10", view="chart").data
    assert spec["site"]["key"] == "road:1/0-12"                              # the 2020 vintage, not the 2019 one


def test_an_empty_legal_range_is_a_refusal(ctx):
    r = run(ctx, "site_profile", site="road:2/13-14")
    assert r.kind == "markdown" and r.data.startswith("# ❌"), r.data


def test_a_malformed_key_is_a_one_sentence_error(ctx):
    r = run(ctx, "site_profile", site="garbage")
    assert r.kind == "error" and "site must be" in r.data
