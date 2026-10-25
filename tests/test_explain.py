# -*- coding: utf-8 -*-
"""studio_explain: the exact-sum identity (Σφ = ln μ on the log-rate scale), deterministic top-k, the site and
global faces, and the refusal set. Runs on the synthetic studio panel with a really-trained model."""
from __future__ import annotations

import math
import sys

import pytest

from nl2sql_roadsafety.studio import constants, explain, model, panel, registry
from helpers import json_safe, run


@pytest.fixture()
def deployed_ctx(studio_ctx):
    pytest.importorskip("xgboost")
    run(studio_ctx, "studio_train_site", train_until=2022)
    run(studio_ctx, "studio_validate")
    r = run(studio_ctx, "studio_deploy")
    assert "נפרס" in r.data, r.data
    return studio_ctx


def _matrix(ctx, meta):
    y0, y1 = meta["panel"]["years"]
    cols, rows = panel.fetch_panel(ctx, y0, y1, float(meta["adt_fill"]["value"]))
    static = {(r[0], r[1]): dict(zip(panel.STATIC_COLUMNS[2:], r[2:])) for r in meta["static_attrs"]["rows"]}
    return panel.matrix(cols, rows, static)


def test_exact_sum_identity_on_the_log_scale(deployed_ctx):
    _, meta = registry.deployed(deployed_ctx)
    raw = registry.model_bytes(deployed_ctx, meta["model_id"])
    X, _y, _years, _keys, _ksi = _matrix(deployed_ctx, meta)
    Xs = X[:40]
    mu = model.predict(raw, Xs)
    phi = model.contribs(raw, Xs)
    assert all(len(row) == len(constants.FEATURES) + 1 for row in phi)       # bias LAST
    for row, m in zip(phi, mu):
        assert abs(sum(row) - math.log(m)) < 1e-4, (sum(row), math.log(m))
    assert explain.check_identity(phi, mu) < 1e-4


def test_top_k_is_deterministic_with_ties():
    assert explain.top_k([0.5, 0.5, 0.2, 0.9, 0.0], k=3) == [3, 0, 1]        # ties break on doc-11 order
    assert explain.top_k([0.0] * 5, k=2) == [0, 1]


def test_site_profile_faces(deployed_ctx):
    top = run(deployed_ctx, "site_ranking", view="table", from_year=2019, to_year=2021).data["rows"][0]
    road, seg, site_key = top[0], top[1], top[15]
    r = run(deployed_ctx, "studio_explain", site=f"{road}/{seg}")
    assert r.kind == "chart", r.data
    spec = r.data
    assert spec["columns"][:3] == ["year", "observed", "mu"]
    assert len([c for c in spec["columns"] if c.startswith("phi_")]) == constants.EXPLAIN_TOP_K + 1  # + bias
    y0, y1 = 2017, 2024
    assert [row[0] for row in spec["rows"]] == list(range(y0, y1 + 1))       # the full panel era, one row per year
    assert spec["basis"].isascii() and spec["png_base64"]
    assert any("סקלת הלוג" in c for c in spec["caveats"])
    json_safe(r)
    via_key = run(deployed_ctx, "studio_explain", site=site_key, view="table")
    assert via_key.kind == "table" and via_key.data["rows"] == spec["rows"]


def test_global_profile(deployed_ctx):
    r = run(deployed_ctx, "studio_explain", view="table")
    assert r.kind == "table"
    rows = r.data["rows"]
    assert r.data["columns"] == ["feature", "label", "mean_abs_phi", "mean_phi"]
    assert len(rows) == len(constants.FEATURES)
    imps = [row[2] for row in rows]
    assert imps == sorted(imps, reverse=True)                                # largest importance first
    assert {row[0] for row in rows} == set(constants.FEATURES)
    chart = run(deployed_ctx, "studio_explain")
    assert chart.kind == "chart" and chart.data["png_base64"]
    json_safe(chart)


def test_refuses_without_a_deployment(studio_ctx):
    assert run(studio_ctx, "studio_explain").data.startswith("# ❌")          # nothing deployed on a fresh registry


def test_refusals(deployed_ctx):
    r = run(deployed_ctx, "studio_explain", model_id="no-such-model")
    assert r.data.startswith("# ❌") and "no-such-model" in r.data
    assert "צמתים" in run(deployed_ctx, "studio_explain", site="njunction:250").data
    assert run(deployed_ctx, "studio_explain", site="999/999").data.startswith("# ❌")
    assert run(deployed_ctx, "studio_explain", site="road:999/0.0-1.0").data.startswith("# ❌")
    assert run(deployed_ctx, "studio_explain", site="not-a-key").kind == "error"


def test_explains_a_non_deployed_model_with_a_status_caveat(deployed_ctx):
    run(deployed_ctx, "studio_train_site", train_until=2021)                  # a fresh CANDIDATE
    cand = registry.list_models(deployed_ctx)[-1]["model_id"]
    r = run(deployed_ctx, "studio_explain", model_id=cand, view="table")
    assert r.kind == "table"
    assert "candidate" in r.note                                              # the not-the-deployed-model caveat


def test_ml_missing_is_readable(deployed_ctx, monkeypatch):
    monkeypatch.setitem(sys.modules, "xgboost", None)
    r = run(deployed_ctx, "studio_explain")
    assert r.kind == "error" and "pip install" in r.data and "Traceback" not in r.data


def test_prediction_card(deployed_ctx):
    """P9's visibility card: the prediction said out loud, with interval, verdict, and drivers in words."""
    top = run(deployed_ctx, "site_ranking", view="table").data["rows"][0]
    r = run(deployed_ctx, "studio_explain", site=f"{top[0]}/{top[1]}", view="markdown")
    assert r.kind == "markdown", r.data
    for needle in ("# תחזית המודל לאתר", "המודל חוזה", "רווח ~90%", "בפועל:", "מה מזין את התחזית"):
        assert needle in r.data, needle
    g = run(deployed_ctx, "studio_explain", view="markdown")                 # empty site = the global drivers card
    assert "# מה מזין את תחזיות המודל" in g.data
