# -*- coding: utf-8 -*-
"""P12 — the severity explain faces: the coloring-policy honesty rules (pure), the deterministic
sampling/jitter, the Σφ = margin identity (fixture 1e-4, runtime guard on a corrupted φ), the planted-signal
direction assertions (the fixture's LCG effects must show up in φ), the dependence view's tick/NULL contract,
the per-prediction waterfalls on severity_predict/what_if, and the refusal/[ml] ladders."""
from __future__ import annotations

import sys

import pytest

from nl2sql_roadsafety.studio import constants, explain_severity as xs, registry, severity
from helpers import json_safe, png_of, run

# ── pure policy + math (no DB, no xgboost) ──


def test_coloring_policy_is_pinned():
    """The honesty differentiator: ONLY genuinely ordered features may carry a color scale; road_type is a
    2x2 and month is cyclic — nominal, whatever their codes look like."""
    assert set(xs.ORDERED) <= set(severity.FEATURES)
    nominal = set(severity.FEATURES) - set(xs.ORDERED)
    assert {"casualty_type_code", "involved_vehicle_type_code", "safety_equipment_code",
            "population_group_code", "road_type_code", "month"} == nominal
    assert set(xs.CLASS_CHOICES.values()) == {0, 1}                  # decision A: קל omitted
    assert list(xs.SAMPLES) == ["20k", "50k", "full"] and xs.SAMPLES["full"] is None


def test_lookup_field_mapping():
    """involved_vehicle_type_code decodes under the dictionary field vehicle_type_code (verified live);
    the numerics (hour/month/year_idx) have no dictionary at all."""
    assert xs.LOOKUP_FIELDS["involved_vehicle_type_code"] == "vehicle_type_code"
    assert "hour_of_day" not in xs.LOOKUP_FIELDS and "year_idx" not in xs.LOOKUP_FIELDS
    sql = xs.lookup_sql()
    assert sql.count("SELECT") == 1 and "arg_max" in sql
    assert "'vehicle_type_code'" in sql and "'involved_vehicle_type_code'" not in sql
    decode = {("vehicle_type_code", 8): "אופנוע עד חמישים", ("day_night_code", 5): "לילה"}
    assert xs.dot_label("involved_vehicle_type_code", 8, decode) == "אופנוע עד חמישים"
    assert xs.dot_label("day_night_code", 5, decode) == "לילה"
    assert xs.dot_label("speed_limit_code", 3, decode) == "3"        # no entry -> the number, honest
    assert xs.dot_label("hour_of_day", 22.0, decode) == "22"
    assert xs.dot_label("age_group_code", None, decode) == xs.NULL_LABEL


def test_stack_jitter_is_deterministic_and_bounded():
    vals = [0.1, 0.11, 0.12, 0.5, -0.3, 0.1, 0.11, 0.1]
    a = xs.stack_jitter(vals)
    assert a == xs.stack_jitter(vals)                                # rng-free
    assert len(a) == len(vals) and all(abs(j) <= 0.36 + 1e-9 for j in a)
    assert a[0] == 0.0                                               # the first dot of a bin sits on the line
    assert xs.stack_jitter([]) == []


def test_sample_indices_are_deterministic_and_sorted():
    a = xs.sample_indices(1000, 100)
    assert a == xs.sample_indices(1000, 100) and a == sorted(a) and len(a) == 100
    assert xs.sample_indices(50, 100) == list(range(50))             # size >= n -> everything
    assert xs.sample_indices(50, None) == list(range(50))            # full


def test_waterfall_parts_sum_to_the_margin():
    phi_row = [3.0, -1.0, 0.5, 0.2, 0.1, 0.05, -0.04, 0.03, 0.02, 0.01, 0.0, 0.0, 0.7]  # 12 + bias
    items, rest, bias = xs.waterfall_parts(phi_row, severity.FEATURES, severity.FEATURE_LABELS_HE, k=5)
    assert [i["phi"] for i in items] == [3.0, -1.0, 0.5, 0.2, 0.1]   # by |phi|, ties on contract order
    assert bias == 0.7
    assert sum(i["phi"] for i in items) + rest + bias == pytest.approx(sum(phi_row), abs=1e-9)
    assert items[0]["label"] == severity.FEATURE_LABELS_HE[severity.FEATURES[0]]


def test_build_swarm_policy_and_determinism():
    import numpy as np

    k = len(severity.FEATURES)
    n = 40
    rng_free = [[(i * 7 + j * 3) % 10 / 10.0 - 0.4 for j in range(k)] for i in range(n)]
    X = []
    for i in range(n):
        row = [float((i + j) % 5 + 1) for j in range(k)]
        if i % 4 == 0:
            row[severity.FEATURES.index("safety_equipment_code")] = None    # a NULL column
        X.append(row)
    order, imp, dots = xs.build_swarm(rng_free, X, severity.FEATURES, set(xs.ORDERED),
                                      severity.FEATURE_LABELS_HE, {}, max_dots=25)
    assert [imp[j] for j in order] == sorted((imp[j] for j in order), reverse=True)
    assert len(dots["phi"]) <= k * 25 and len(set(dots["row"])) == k
    order2, imp2, dots2 = xs.build_swarm(rng_free, X, severity.FEATURES, set(xs.ORDERED),
                                         severity.FEATURE_LABELS_HE, {}, max_dots=25)
    assert order == order2 and imp == imp2 and dots == dots2         # byte-comparable across runs
    for row_i, vn, isnull, label in zip(dots["row"], dots["value_norm"], dots["is_null"], dots["label"]):
        f = severity.FEATURES[order[row_i]]
        if isnull:
            assert vn is None and label.endswith(xs.NULL_LABEL)
        elif f not in xs.ORDERED:
            assert vn is None                                        # nominal NEVER gets a color scale
        else:
            assert vn is not None and 0.0 <= vn <= 1.0
    nulls = [b for r, b in zip(dots["row"], dots["is_null"])
             if severity.FEATURES[order[r]] == "safety_equipment_code"]
    assert any(nulls)                                                # the planted NULLs surface as hollow dots
    del np


def test_build_dependence_ticks_and_jitter():
    k = len(severity.FEATURES)
    phi = [[0.1 * ((i + j) % 3 - 1) for j in range(k)] for i in range(30)]
    X = [[float(i % 3 + 1) for _ in range(k)] for i in range(30)]
    j_nom = severity.FEATURES.index("casualty_type_code")
    X[5][j_nom] = None
    dep = xs.build_dependence(phi, X, severity.FEATURES, j_nom, {("casualty_type_code", 1): "הולך רגל"})
    assert dep["ordered"] is False and dep["ticks"][-1] == [None, xs.NULL_LABEL]
    assert dep["ticks"][0] == [1, "הולך רגל"]                        # decoded tick
    assert all(abs(a - b) <= 0.301 for a, b in zip(dep["xj"], dep["x"]))     # jitter stays inside the slot
    assert dep == xs.build_dependence(phi, X, severity.FEATURES, j_nom, {("casualty_type_code", 1): "הולך רגל"})
    j_ord = severity.FEATURES.index("speed_limit_code")
    dep_o = xs.build_dependence(phi, X, severity.FEATURES, j_ord, {})
    assert dep_o["ordered"] is True and dep_o["ticks"] is None and dep_o["xj"] == dep_o["x"]
    assert dep_o["null_x"] is None                                   # no NULLs -> no strip


def test_build_dependence_ordered_nulls_get_the_strip():
    """The sweep's catch: ordered-axis NULLs were x=None and every renderer silently dropped them.
    Now they land jittered in the labelled null_x strip right of the known range — never dropped."""
    k = len(severity.FEATURES)
    phi = [[0.05 * (i % 5 - 2) for _ in range(k)] for i in range(40)]
    j_ord = severity.FEATURES.index("speed_limit_code")
    X = [[float(i % 4 + 1) for _ in range(k)] for i in range(40)]
    for i in (3, 11, 19, 27):
        X[i][j_ord] = None
    dep = xs.build_dependence(phi, X, severity.FEATURES, j_ord, {})
    assert dep["ordered"] is True and dep["null_x"] is not None and dep["null_label"] == xs.NULL_LABEL
    assert dep["null_x"] > 4.0                                       # right of the known range (max 4)
    null_xj = [xj for xj, nul in zip(dep["xj"], dep["is_null"]) if nul]
    assert len(null_xj) == 4 and all(x is not None for x in null_xj)  # NEVER dropped
    step = (dep["null_x"] - 4.0) / 1.5
    assert all(abs(x - dep["null_x"]) <= 0.45 * step + 1e-9 for x in null_xj)   # inside the strip
    known_xj = [xj for xj, nul in zip(dep["xj"], dep["is_null"]) if not nul]
    assert all(x <= 4.0 for x in known_xj)                           # known dots keep xj == x
    assert dep == xs.build_dependence(phi, X, severity.FEATURES, j_ord, {})     # deterministic


def test_display_sentinel_mask():
    """sex_code 0 = 'לא רלוונטי' live (3,797 era rows) — a sentinel, never a LEVEL on the color scale."""
    assert xs.DISPLAY_NULL_CODES == {"sex_code": (0,)}
    j_sex = severity.FEATURES.index("sex_code")
    rows = [[1.0] * len(severity.FEATURES) for _ in range(3)]
    rows[0][j_sex] = 0.0
    rows[1][j_sex] = 2.0
    rows[2][j_sex] = None
    masked = xs.mask_display_sentinels(rows)
    assert masked[0][j_sex] is None and masked[1][j_sex] == 2.0 and masked[2][j_sex] is None
    assert rows[0][j_sex] == 0.0                                     # the input is never mutated
    assert all(masked[i][0] == 1.0 for i in range(3))                # other columns untouched


def test_null_share_caveat_threshold():
    from nl2sql_roadsafety.actions.severity_explain import _null_share_caveat
    row = lambda share: ["f", "אמצעי בטיחות", 0.1, 0.0, "קטגוריאלי", share]  # noqa: E731
    assert _null_share_caveat([row(0.29), row(0.1)]) is None
    assert "30%" in _null_share_caveat([row(0.30), row(0.1)])
    line = _null_share_caveat([row(0.627)])
    assert line.startswith("אמצעי בטיחות: 63%") and ";" not in line


# ── the round trip on the planted signal ──


def _deploy_severity(studio_ctx) -> str:
    run(studio_ctx, "studio_train_severity")
    doc_id = registry.list_models(studio_ctx, severity.FAMILY)[-1]["model_id"]
    run(studio_ctx, "studio_validate_severity")
    run(studio_ctx, "studio_deploy", family="severity")
    return doc_id


def test_severity_explain_round_trip(studio_ctx):
    pytest.importorskip("xgboost")
    assert run(studio_ctx, "severity_explain").data.startswith("# ❌")        # nothing deployed yet
    run(studio_ctx, "studio_train_severity")
    cand_id = registry.list_models(studio_ctx, severity.FAMILY)[-1]["model_id"]
    r_cand = run(studio_ctx, "severity_explain", model_id=cand_id, view="table")
    assert r_cand.kind == "table"                                            # explicit non-deployed id works…
    cand_note = run(studio_ctx, "severity_explain", model_id=cand_id, view="chart")
    assert any("אינו המודל הפרוס" in c for c in cand_note.data["caveats"])    # …with the status caveat
    assert any("טרם אומת" in c for c in cand_note.data["caveats"])           # a candidate has no gate yet
    assert not any("None" in c for c in cand_note.data["caveats"])           # sweep: never a literal 'None'
    run(studio_ctx, "studio_validate_severity")
    run(studio_ctx, "studio_deploy", family="severity")

    r = run(studio_ctx, "severity_explain")
    assert r.kind == "chart", r.data
    spec = r.data
    png_of(spec)
    assert spec["basis"].startswith("severity_explain | class fatal | sample ")
    assert spec["basis"].isascii() and spec["stamp"].isascii()
    assert spec["denominator"]["kind"] == "counts" and spec["model_id"]
    assert all(";" not in c for c in spec["caveats"])
    swarm = spec["swarm"]
    assert len(swarm["features"]) == len(severity.FEATURES)
    assert len(swarm["ordered"]) == len(severity.FEATURES)
    assert len(swarm["phi"]) == len(swarm["jitter"]) == len(swarm["is_null"]) == len(swarm["label"])
    json_safe(r)
    r2 = run(studio_ctx, "severity_explain")                                 # determinism: same seed, same rows
    assert r2.data["rows"] == spec["rows"] and r2.data["swarm"] == swarm

    # planted-signal directions, straight from the core API on the deployed artifact
    _, meta = registry.deployed(studio_ctx, severity.FAMILY)
    raw = registry.model_bytes(studio_ctx, meta["model_id"], family=severity.FAMILY)
    X, _y, _years = severity.fetch_matrix(studio_ctx, *meta["panel"]["years"])
    phi3, margins = xs.contribs3(raw, X)
    assert xs.check_identity3(phi3, margins) < 1e-4                          # the fixture pin (runtime: 1e-3)
    kf = len(severity.FEATURES)
    phi_f = phi3[:, 0, :kf]
    j_night = severity.FEATURES.index("day_night_code")
    j_safety = severity.FEATURES.index("safety_equipment_code")
    j_speed = severity.FEATURES.index("speed_limit_code")
    j_ctype = severity.FEATURES.index("casualty_type_code")

    def mean_phi_where(j, pred):
        vals = [float(phi_f[i][j]) for i in range(len(X)) if pred(X[i][j])]
        return sum(vals) / len(vals)

    assert mean_phi_where(j_night, lambda v: v == 5) > mean_phi_where(j_night, lambda v: v == 1)
    assert mean_phi_where(j_safety, lambda v: v == 4) > mean_phi_where(j_safety, lambda v: v == 1)
    assert mean_phi_where(j_speed, lambda v: v is not None and v >= 5) > \
        mean_phi_where(j_speed, lambda v: v is not None and v < 5)
    assert mean_phi_where(j_ctype, lambda v: v in (1, 4)) > mean_phi_where(j_ctype, lambda v: v in (2, 3))

    # the severe class and the table/markdown faces
    r_sev = run(studio_ctx, "severity_explain", severity_class="פצוע קשה")
    assert "class severe" in r_sev.data["basis"]
    t = run(studio_ctx, "severity_explain", view="table")
    assert t.kind == "table" and len(t.data["rows"]) == len(severity.FEATURES)
    by_feature = {row[0]: row for row in t.data["rows"]}
    assert by_feature["casualty_type_code"][4] == "קטגוריאלי"                # nominal never gets a direction
    assert by_feature["involved_vehicle_type_code"][5] > 0                   # pedestrians -> NULL vehicle type
    md = run(studio_ctx, "severity_explain", view="markdown")
    assert "מה מזין את מודל החומרה" in md.data and "ארבע האזהרות" in md.data
    s = run(studio_ctx, "severity_explain", view="sql")
    assert s.kind == "sql" and "code_lookups" in s.data and "FROM involved" in s.data

    # dependence: ordered numeric axis vs nominal decoded ticks with the explicit NULL slot
    d_ord = run(studio_ctx, "severity_explain", feature="speed_limit_code")
    assert d_ord.kind == "chart" and d_ord.data["dependence"]["ordered"] is True
    png_of(d_ord.data)
    d_nom = run(studio_ctx, "severity_explain", feature="casualty_type_code")
    dep = d_nom.data["dependence"]
    assert dep["ticks"][-1] == [None, xs.NULL_LABEL]
    assert ["הולך רגל" in str(t[1]) for t in dep["ticks"]].count(True) == 1  # decoded from code_lookups
    assert any("אינטראקציות" in c for c in d_nom.data["caveats"])

    # the per-prediction waterfalls (P12 item 2)
    p = run(studio_ctx, "severity_predict", casualty="הולך רגל", time="לילה", safety="ללא אמצעי בטיחות")
    assert p.kind == "chart"
    drv = p.data["drivers"]
    assert drv["class_label"] == "הרוג" and len(drv["items"]) <= 5 and drv["bias"] is not None
    prow = severity.profile_row({"casualty": "הולך רגל", "time": "לילה", "safety": "ללא אמצעי בטיחות"})
    phi1, m1 = xs.contribs3(raw, [prow])
    total = sum(i["phi"] for i in drv["items"]) + drv["rest"] + drv["bias"]
    assert total == pytest.approx(float(m1[0][0]), abs=1e-2)                 # the waterfall sums to the margin
    png_of(p.data)
    wf = run(studio_ctx, "what_if")                                          # day -> night
    wdrv = wf.data["drivers"]
    assert wdrv["bias"] is None and wdrv["switch_feature"] == "day_night_code"
    switched = [i for i in wdrv["items"] if i["feature"] == "day_night_code"]
    assert switched and switched[0]["phi"] > 0                               # the night switch pushes fatal up
    p_md = run(studio_ctx, "severity_predict", casualty="הולך רגל", view="markdown")
    assert "מוביל" in p_md.data                                              # the drivers reach the card too
    json_safe(p)
    json_safe(wf)


def test_identity_guard_raises_on_corrupt_phi(studio_ctx, monkeypatch):
    pytest.importorskip("xgboost")
    _deploy_severity(studio_ctx)
    real = xs.contribs3

    def corrupt(raw, X):
        phi, margins = real(raw, X)
        phi = phi.copy()
        phi[:, :, 0] += 1.0                                                  # break Σφ = margin
        return phi, margins

    monkeypatch.setattr(xs, "contribs3", corrupt)
    for action in ("severity_explain", "severity_predict", "what_if"):    # all three ride contribs_guarded
        r = run(studio_ctx, action)
        assert r.kind == "error" and "identity" in r.data and "Traceback" not in r.data, (action, r.data)


def test_explain_ml_missing_and_bad_ids(studio_ctx, monkeypatch):
    r = run(studio_ctx, "severity_explain", model_id="no-such-model")
    assert r.data.startswith("# ❌") and "לא נמצא" in r.data
    pytest.importorskip("xgboost")
    _deploy_severity(studio_ctx)
    monkeypatch.setitem(sys.modules, "xgboost", None)
    r2 = run(studio_ctx, "severity_explain")
    assert r2.kind == "error" and "pip install" in r2.data and "Traceback" not in r2.data


def test_decode_tolerance_without_code_lookups(studio_ctx, monkeypatch):
    """The §8.1 contract: a DB without the dictionary still explains — dots fall back to numeric codes.
    Simulated by pointing the lookup at a missing table, so decode_labels' except-branch actually runs."""
    pytest.importorskip("xgboost")
    _deploy_severity(studio_ctx)
    monkeypatch.setattr(xs, "lookup_sql", lambda: "SELECT field, code, label_he FROM no_such_table_p12")
    r = run(studio_ctx, "severity_explain", feature="casualty_type_code")
    assert r.kind == "chart", r.data
    dep = r.data["dependence"]
    assert dep["ticks"][0][1] == "1"                                  # numeric fallback, honest and alive
    assert dep["ticks"][-1] == [None, xs.NULL_LABEL]


def test_empty_matrix_is_a_refusal(studio_ctx, monkeypatch):
    pytest.importorskip("xgboost")
    _deploy_severity(studio_ctx)
    monkeypatch.setattr(severity, "fetch_matrix", lambda *a, **k: ([], [], []))
    r = run(studio_ctx, "severity_explain")
    assert r.kind == "markdown" and r.data.startswith("# ❌") and "severity_profile" in r.data, r.data


def test_site_beeswarm_style(studio_ctx):
    """P12 item 4: studio_explain's global face gains style=נחיל — full coloring is legitimate there
    (every site feature is ordered)."""
    pytest.importorskip("xgboost")
    run(studio_ctx, "studio_train_site")
    run(studio_ctx, "studio_validate")
    run(studio_ctx, "studio_deploy")
    r = run(studio_ctx, "studio_explain", style="נחיל")
    assert r.kind == "chart", r.data
    swarm = r.data["swarm"]
    assert len(swarm["features"]) == len(constants.FEATURES)
    assert all(swarm["ordered"])                                             # ALL site features carry the scale
    assert all(vn is not None for vn, isnull in zip(swarm["value_norm"], swarm["is_null"]) if not isnull)
    png_of(r.data)
    r_prof = run(studio_ctx, "studio_explain")                               # the default stays byte-stable
    assert "swarm" not in r_prof.data
    json_safe(r)
