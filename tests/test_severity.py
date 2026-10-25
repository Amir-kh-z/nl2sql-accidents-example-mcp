# -*- coding: utf-8 -*-
"""The severity family (P9): the matrix SQL's structural leakage rule, the discrimination-gate math (worked
examples), the train→validate→deploy round trip on the planted person signal (person-12 passes, shuffled fails
by AUC), the profile/what_if faces with their refusals, and the [ml]-absent errors."""
from __future__ import annotations

import sys

import pytest

from nl2sql_roadsafety.studio import constants, registry, severity
from helpers import json_safe, png_of, run


def test_matrix_sql_is_structurally_leakage_free():
    """The exclusions are structural: the SQL selects only contract columns, so the outcome columns CANNOT
    enter — token-scan the statement itself."""
    sql = severity.matrix_sql(*severity.ERA)
    for forbidden in ("late_death", "injury_severity_score", "hospital", "discharge", "medical", "surgery"):
        assert forbidden not in sql, forbidden
    assert sql.count("injury_severity_code") == 2                            # the target select + the 1/2/3 filter
    assert "case_type_code = 1" in sql
    for f in severity.FEATURES[:-1]:                                         # year_idx is derived, not selected
        assert f.removesuffix("_code") in sql, f


def test_gate_math_worked_examples():
    # AUC via Mann-Whitney: all-concordant, a 3-of-4 case, a full tie, a degenerate side
    assert severity.auc_binary([1, 0, 0, 1], [0.9, 0.1, 0.4, 0.5]) == 1.0
    assert severity.auc_binary([1, 1, 0, 0], [0.9, 0.3, 0.5, 0.1]) == pytest.approx(0.75)
    assert severity.auc_binary([1, 0], [0.5, 0.5]) == pytest.approx(0.5)     # average ranks on ties
    assert severity.auc_binary([1, 1], [0.9, 0.1]) == 0.0                    # one class only carries no ranking
    # recall under argmax
    probs = [[0.6, 0.2, 0.2], [0.2, 0.6, 0.2], [0.1, 0.8, 0.1]]
    assert severity.recall_of_class([0, 0, 1], probs, 0) == pytest.approx(0.5)
    assert severity.recall_of_class([0, 0, 1], probs, 1) == 1.0
    assert severity.recall_of_class([0, 0, 1], probs, 2) == 0.0              # no such rows
    # 1/share weights: n/count(c), rare classes weigh more
    assert severity.class_weights([0] + [1] * 2 + [2] * 7) == [10.0, 5.0, 1.4286]
    assert severity.class_weights([2, 2])[0] == 2.0                          # an absent class floors at count 1
    # the verdict: three failures -> three Hebrew reasons, all plugin-labelled, none with ';'
    status, reasons = severity.verdict({"fatal_recall": 0.3, "auc_fatal": 0.7, "overfit_auc_gap": 0.2})
    assert status == "rejected" and len(reasons) == 3
    assert all(";" not in r and "כלל התוסף" in r for r in reasons)
    assert severity.verdict({"fatal_recall": 0.6, "auc_fatal": 0.85, "overfit_auc_gap": 0.03})[0] == "validated"
    # relative probabilities — the only exit door
    assert severity.relative([0.02, 0.2, 0.78], [0.01, 0.1, 0.78]) == pytest.approx([2.0, 2.0, 1.0])
    assert severity.relative([0.5], [0.0]) == [0.0]


def test_shuffle_is_deterministic_and_train_only():
    y = [i % 3 for i in range(12)]
    years = [2019 + i % 4 for i in range(12)]
    a = severity.shuffle_target(y, years, 2021, 42)
    assert a == severity.shuffle_target(y, years, 2021, 42)
    assert a != severity.shuffle_target(y, years, 2021, 43)
    ho = [i for i, yr in enumerate(years) if yr > 2021]
    assert all(a[i] == y[i] for i in ho)                                     # holdout untouched
    tr = [i for i, yr in enumerate(years) if yr <= 2021]
    assert sorted(a[i] for i in tr) == sorted(y[i] for i in tr)              # a permutation, not new values


def test_profile_row_and_fields():
    for col, _mapping in severity.PROFILE_FIELDS.values():
        assert col in severity.FEATURES                                      # every choice maps into the contract
    empty = severity.profile_row({})
    assert empty[severity.FEATURES.index("year_idx")] == severity.ERA[1] - severity.ERA[0]
    assert all(v is None for i, v in enumerate(empty) if severity.FEATURES[i] != "year_idx")
    row = severity.profile_row({"casualty": "הולך רגל", "time": "לילה", "safety": severity.UNSET})
    assert row[severity.FEATURES.index("casualty_type_code")] == 1
    assert row[severity.FEATURES.index("day_night_code")] == 5
    assert row[severity.FEATURES.index("safety_equipment_code")] is None     # UNSET stays honest missing


def test_severity_round_trip(studio_ctx):
    pytest.importorskip("xgboost")
    r = run(studio_ctx, "studio_train_severity")
    assert r.kind == "markdown" and "מודל מועמד" in r.data, r.data
    doc_meta = registry.list_models(studio_ctx, severity.FAMILY)[-1]
    doc_id = doc_meta["model_id"]
    assert doc_id.startswith("severity-2022-person12-") and doc_meta["status"] == "candidate"
    assert doc_meta["features"] == list(severity.FEATURES)                   # the contract
    assert doc_meta["class_weights"]["window"] == [2010, 2022]
    w = doc_meta["class_weights"]["values"]
    assert len(w) == 3 and w[0] > w[1] > w[2]                                # rare classes weigh more
    assert doc_meta["panel"]["n_train"] > 0 and doc_meta["panel"]["n_holdout"] > 0
    assert sum(doc_meta["panel"]["class_counts_train"]) == doc_meta["panel"]["n_train"]
    assert run(studio_ctx, "severity_predict").data.startswith("# ❌")        # nothing deployed yet
    assert run(studio_ctx, "what_if").data.startswith("# ❌")
    v = run(studio_ctx, "studio_validate_severity")
    assert "עבר את השער" in v.data, v.data
    g = registry.read_meta(studio_ctx, doc_id, family=severity.FAMILY)["gate"]["metrics"]
    assert g["auc_fatal"] == pytest.approx(0.845, abs=0.1)                   # the planted signal is strong
    assert g["fatal_recall"] >= severity.GATE["fatal_recall_min"][0]
    assert g["overfit_auc_gap"] <= severity.GATE["overfit_auc_gap_max"][0]
    run(studio_ctx, "studio_train_severity", features="shuffled")
    sh_id = registry.list_models(studio_ctx, severity.FAMILY)[-1]["model_id"]
    assert "shuffled" in sh_id and sh_id != doc_id
    v2 = run(studio_ctx, "studio_validate_severity")                         # latest = the straw man
    assert "נדחה" in v2.data and "AUC" in v2.data, v2.data
    d_rej = run(studio_ctx, "studio_deploy", model_id=sh_id, family="severity")
    assert d_rej.data.startswith("# ❌") and "הסיבה" in d_rej.data
    assert registry.deployed(studio_ctx, severity.FAMILY)[0] is None
    d = run(studio_ctx, "studio_deploy", family="severity")                  # latest VALIDATED in the family
    assert "נפרס" in d.data, d.data
    pointer, dep_meta = registry.deployed(studio_ctx, severity.FAMILY)
    assert pointer["model_id"] == doc_id and dep_meta["status"] == "deployed"
    assert registry.deployed(studio_ctx)[0] is None                          # the site family is untouched
    assert f"**מודל חומרה פרוס** — {doc_id}" in run(studio_ctx, "about").data
    tbl = run(studio_ctx, "studio_models", family="severity").data
    by_id = {row[0]: row[1] for row in tbl["rows"]}
    assert by_id[doc_id] == "deployed" and by_id[sh_id] == "rejected"
    assert "fatal_recall" in tbl["columns"]                                  # the family-switched metric columns
    # the profile face: pedestrian + night + unbelted must sit ABOVE the baseline on the fatal class
    p = run(studio_ctx, "severity_predict", casualty="הולך רגל", time="לילה",
            safety="ללא אמצעי בטיחות", view="table")
    assert p.kind == "table"
    fatal_row = p.data["rows"][0]
    assert fatal_row[1] == "הרוג" and fatal_row[4] > 1.0, fatal_row
    p_md = run(studio_ctx, "severity_predict", casualty="הולך רגל", time="לילה", view="markdown")
    assert "פי" in p_md.data and "גורל" in p_md.data                         # the relative-only framing
    # what_if: the planted night multiplier makes day->night raise the fatal ratio
    wf = run(studio_ctx, "what_if", view="table")
    assert wf.data["rows"][0][4] > 1.0, wf.data["rows"]
    wf_md = run(studio_ctx, "what_if", casualty="הולך רגל", view="markdown")
    assert "מה אם" in wf_md.data and "פי" in wf_md.data
    for action, kw in (("severity_predict", {}), ("what_if", {}), ("studio_validate_severity", {"view": "chart"})):
        rc = run(studio_ctx, action, **kw)                                   # the chart faces render real PNGs
        assert rc.kind == "chart", (action, rc.data)
        assert rc.data["basis"].isascii() and rc.data["stamp"].isascii(), (action, rc.data["basis"])
        png_of(rc.data)                                                      # (CHART_RUNS can't reach these —
    assert run(studio_ctx, "what_if").data["chip"]                           # they refuse on the plain fixture)
    json_safe(v)
    json_safe(p)
    json_safe(wf)


def test_train_until_bounds_and_contract_refusals(studio_ctx):
    assert run(studio_ctx, "studio_train_severity", train_until=2016).data.startswith("# ❌")
    assert run(studio_ctx, "studio_train_severity", train_until=2024).data.startswith("# ❌")
    assert run(studio_ctx, "studio_train_severity", features="nope").kind == "error"
    mid = registry.save(studio_ctx, "severity-bad", _fake_meta("severity-bad", features=["not_the_contract"]),
                        b"x", family=severity.FAMILY)
    r = run(studio_ctx, "studio_validate_severity", model_id=mid)
    assert r.data.startswith("# ❌") and "חוזה המאפיינים" in r.data           # no xgboost needed to refuse


def _fake_meta(model_id: str, features=None) -> dict:
    return {"model_id": model_id, "family": severity.FAMILY, "status": "validated",
            "created_at": registry.now_utc(), "contract_version": constants.CONTRACT_VERSION,
            "preset": "person-12", "seed": 1, "features": list(features or severity.FEATURES),
            "panel": {"train_until": 2022, "years": list(severity.ERA)},
            "class_weights": {"values": [64.7, 10.3, 1.1]}, "class_shares_holdout": [0.015, 0.097, 0.888],
            "sql": {"matrix": "--"}, "gate": {"metrics": {}, "reasons": []}}


def test_contract_version_is_enforced_severity(studio_ctx):
    """The severity twin of the site tripwire (P9 sweep): matrix-recipe drift (sentinel sets, the year_idx
    anchor) hides under unchanged feature NAMES — a stored model outliving a plugin upgrade must refuse, not
    serve mis-built features. Missing counts as a mismatch."""
    from nl2sql_roadsafety.sqlkit import Refusal

    severity.contract_check(_fake_meta("severity-cv"))                       # current version passes
    for bad_version in (999, None):
        bad = _fake_meta("severity-cv")
        if bad_version is None:
            bad.pop("contract_version")
        else:
            bad["contract_version"] = bad_version
        with pytest.raises(Refusal, match="חוזה המאפיינים"):
            severity.contract_check(bad)
    mid = registry.save(studio_ctx, "severity-cv9", {**_fake_meta("severity-cv9"), "contract_version": 999},
                        b"x", family=severity.FAMILY)
    assert "חוזה המאפיינים" in run(studio_ctx, "studio_validate_severity", model_id=mid).data
    registry.set_deployed(studio_ctx, registry.read_meta(studio_ctx, mid, family=severity.FAMILY))
    for action in ("severity_predict", "what_if"):                           # the deployed readers refuse too
        r = run(studio_ctx, action)
        assert r.data.startswith("# ❌") and "חוזה המאפיינים" in r.data, (action, r.data)


def test_ml_missing_is_readable(studio_ctx, monkeypatch):
    mid = registry.save(studio_ctx, "severity-f", _fake_meta("severity-f"), b"not-a-model",
                        family=severity.FAMILY)
    registry.set_deployed(studio_ctx, registry.read_meta(studio_ctx, mid, family=severity.FAMILY))
    monkeypatch.setitem(sys.modules, "xgboost", None)
    for action, kw in (("studio_train_severity", {}), ("studio_validate_severity", {"model_id": mid}),
                       ("severity_predict", {}), ("what_if", {})):
        r = run(studio_ctx, action, **kw)
        assert r.kind == "error", (action, r.data)
        assert "pip install" in r.data and "Traceback" not in r.data, (action, r.data)


def test_validate_error_when_verdict_cannot_be_saved(studio_ctx, monkeypatch):
    pytest.importorskip("xgboost")
    run(studio_ctx, "studio_train_severity")
    monkeypatch.setattr(registry, "update_meta", lambda *a, **k: None)
    r = run(studio_ctx, "studio_validate_severity")
    assert r.kind == "error" and "was not saved" in r.data and "Traceback" not in r.data, r.data
