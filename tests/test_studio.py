# -*- coding: utf-8 -*-
"""The studio on the synthetic panel: the panel SQL, the leakage rule, the shuffle, the gate math (worked
examples), the train→validate→deploy round trip with its refusals, the registry's tolerance, the [ml]-absent
errors, and the data-dir move."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from nl2sql_roadsafety.studio import constants, gate, panel, registry, severity
from helpers import json_safe, run
from studio_fixture import build_studio_db

SUMMARY = [[2017, 60, 587, 30, 30], [2018, 60, 604, 30, 30], [2019, 60, 570, 30, 30], [2020, 60, 508, 30, 30],
           [2021, 60, 537, 45, 15], [2022, 60, 632, 45, 15], [2023, 60, 576, 45, 15], [2024, 60, 579, 45, 15]]


def test_panel_sql_shape(studio_ctx):
    fill = panel.fetch_adt_fill(studio_ctx, 2022)
    assert fill["value"] == 31100.0 and fill["unit_years"] == 210
    cols, rows = panel.fetch_panel(studio_ctx, 2017, 2024, fill["value"])
    assert len(rows) == 480                                                  # the FULL 60 x 8 grid
    assert panel.panel_summary(cols, rows) == SUMMARY
    ci = {c: i for i, c in enumerate(cols)}
    assert all(r[ci["lag1"]] is not None for r in rows)                      # 2016 feeds 2017
    assert any(r[ci["y"]] == 0 for r in rows)                                # zero years included
    assert all(r[ci["adt_known"]] in (0, 1) for r in rows)
    assert not any(r[ci["year"]] == 2016 for r in rows)                      # the feed year never leaves the CTE
    sql = panel.panel_sql(2017, 2024, fill["value"])
    for needle in ("a.year = u.year", "a.road_km <> 0", "case_type_code = 1",
                   "lag(y) OVER (PARTITION BY road, seg ORDER BY year)"):
        assert needle in sql, needle
    assert "traffic_adt_filled" not in sql


def test_static_attrs_leakage(tmp_path):
    """The frozen attributes may not depend on the target window: removing every casualty row after the horizon
    must leave them byte-identical."""
    import duckdb

    full, dropped = tmp_path / "full.duckdb", tmp_path / "dropped.duckdb"
    build_studio_db(full)
    build_studio_db(dropped, drop_after=2020)
    sql = panel.static_attrs_sql(2020)
    a = duckdb.connect(str(full), read_only=True).execute(sql).fetchall()
    b = duckdb.connect(str(dropped), read_only=True).execute(sql).fetchall()
    assert a == b and len(a) == 60
    assert "BETWEEN 2005 AND 2020" in sql
    for row in a:
        for v in row[5:10]:                                                  # the pct_* attributes
            assert v is None or 0.0 <= v <= 1.0
        assert row[10] is None or 1.0 <= row[10] <= 8.0                      # speed_mix


def test_shuffle_is_deterministic():
    y = list(range(12))
    years = [2017 + i % 4 for i in range(12)]
    keys = [(1, 10 * i) for i in range(12)]
    a = panel.shuffle_target(y, years, keys, 2019, 42)
    assert a == panel.shuffle_target(y, years, keys, 2019, 42)               # same seed, same permutation
    assert a != panel.shuffle_target(y, years, keys, 2019, 43)
    ho = [i for i, yr in enumerate(years) if yr > 2019]
    assert all(a[i] == y[i] for i in ho)                                     # holdout untouched
    tr = [i for i, yr in enumerate(years) if yr <= 2019]
    assert sorted(a[i] for i in tr) == sorted(y[i] for i in tr)              # a permutation, not new values
    assert any(a[i] != y[i] for i in tr)


def test_gate_math_worked_examples():
    assert gate.spearman([3, 0, 0, 5], [4.0, 0.5, 0.5, 2.0]) == pytest.approx(0.778, abs=1e-3)
    assert gate.spearman([3, 0, 0, 5], [2.0, 0.5, 0.5, 4.0]) == pytest.approx(1.0)
    assert gate.spearman([1, 1, 1], [2.0, 3.0, 4.0]) == 0.0                  # a constant side carries no ranking
    assert gate.poisson_deviance_mean([0, 3], [0.5, 2.0]) == pytest.approx(0.716, abs=1e-3)
    assert gate.alpha_moments([6, 0, 0, 9], [2.0, 0.5, 0.5, 4.0]) == pytest.approx(1.607, abs=1e-3)
    assert gate.alpha_moments([3, 0, 0, 5], [2.0, 0.5, 0.5, 4.0]) == 0.0     # under-dispersed floors at Poisson
    lo, hi = gate.nb_interval([3.0, 3.5, 3.5], 0.2)
    assert lo == pytest.approx(3.28, abs=0.01) and hi == pytest.approx(16.72, abs=0.01)
    assert gate.eb(10.0, 18.0, 0.2) == pytest.approx(15.333, abs=1e-3)       # w = 1/3
    status, reasons = gate.verdict({"spearman": 0.21, "calibration": 1.35, "deviance_ratio": 1.79, "alpha": 0.0})
    assert status == "rejected" and len(reasons) == 3
    assert all(";" not in r for r in reasons)
    assert any("0.21" in r for r in reasons) and any("כלל התוסף" in r for r in reasons)
    assert gate.verdict({"spearman": 0.7, "calibration": 1.0, "deviance_ratio": 1.1, "alpha": 0.1})[0] == "validated"


def _trapezoid(fpr, tpr) -> float:
    return sum((fpr[i + 1] - fpr[i]) * (tpr[i + 1] + tpr[i]) / 2.0 for i in range(len(fpr) - 1))


def test_roc_curve_worked_examples():
    # no score ties: n=4 → threshold = sorted(y)[3] = 2 → ONE positive; its score tops every negative → AUC 1
    fpr, tpr, auc, info = gate.roc_curve([2, 0, 1, 0], [4.0, 1.0, 3.0, 2.0])
    assert auc == pytest.approx(1.0)
    assert fpr == pytest.approx([0.0, 0.0, 1 / 3, 2 / 3, 1.0]) and tpr == pytest.approx([0.0, 1.0, 1.0, 1.0, 1.0])
    assert info == {"positive_n": 1, "share": 0.25, "threshold": 2.0, "rule": "top-decile-observed"}
    # a positive TIED with a negative at score 3.0 counts half: pairs = (0.5 + 1 + 1) / 3 → AUC 5/6,
    # and the tie group is ONE step — the trapezoid over the collapsed points equals that Mann-Whitney value
    fpr, tpr, auc, _ = gate.roc_curve([2, 0, 1, 0], [3.0, 3.0, 1.0, 0.5])
    assert auc == pytest.approx(5 / 6, abs=1e-12)
    assert fpr == pytest.approx([0.0, 1 / 3, 2 / 3, 1.0]) and tpr == pytest.approx([0.0, 1.0, 1.0, 1.0])
    assert _trapezoid(fpr, tpr) == pytest.approx(auc, abs=1e-12)
    # ties AT the threshold are included: sorted(y)[9] = 2 catches BOTH 2s; the second positive (score 3.0)
    # loses only to the negative at 4.0 → AUC = (8 + 7) / 16
    y = [2, 2, 1, 0, 0, 0, 0, 0, 0, 0]
    fpr, tpr, auc, info = gate.roc_curve(y, [5.0, 3.0, 4.0, 2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4])
    assert auc == pytest.approx(15 / 16, abs=1e-12) and info["positive_n"] == 2 and info["share"] == 0.2
    assert fpr == sorted(fpr) and tpr == sorted(tpr) and fpr[-1] == 1.0 and tpr[-1] == 1.0
    # degenerate classes degrade to None, never an error: constant y → everything positive; too few rows
    assert gate.roc_curve([1, 1, 1, 1], [0.1, 0.2, 0.3, 0.4]) is None
    assert gate.roc_curve([0, 0], [0.5, 0.6]) is None
    assert gate.roc_curve([3], [1.0]) is None


def test_roc_curve_collapses_tied_scores():
    """The rival's staircase steps INSIDE a tie group; ours may not — a duplicated score adds NO new step."""
    y = [5, 5, 0, 0, 0, 0, 0, 0, 0, 0]
    scores = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05]
    fpr1, tpr1, auc1, info1 = gate.roc_curve(y, scores)
    assert len(fpr1) == len(set(scores)) + 1                                 # one step per DISTINCT score + origin
    fpr2, tpr2, auc2, info2 = gate.roc_curve(y + [0], scores + [0.5])        # duplicated score, same threshold
    assert len(fpr2) == len(fpr1)                                            # no new step appeared
    assert info2["positive_n"] == info1["positive_n"] == 2
    assert fpr2[-1] == 1.0 and tpr2[-1] == 1.0
    assert _trapezoid(fpr2, tpr2) == pytest.approx(auc2, abs=1e-12)


def test_roc_auc_is_the_mann_whitney_statistic():
    """Cross-pin against severity.auc_binary on arrays WITH tied scores and ties at the threshold — the two
    families must agree exactly on what AUC means."""
    cases = [
        ([4, 4, 2, 0, 0, 1, 0, 0, 0, 4], [7.0, 5.0, 5.0, 5.0, 1.0, 2.0, 2.0, 0.5, 0.5, 3.0]),
        ([2, 0, 1, 0], [3.0, 3.0, 1.0, 0.5]),
        ([2, 2, 1, 0, 0, 0, 0, 0, 0, 0], [5.0, 3.0, 4.0, 2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4]),
    ]
    for y, scores in cases:
        fpr, tpr, auc, info = gate.roc_curve(y, scores)
        labels = [v >= info["threshold"] for v in y]
        assert auc == pytest.approx(severity.auc_binary(labels, scores), abs=1e-12), (y, scores)
        assert _trapezoid(fpr, tpr) == pytest.approx(auc, abs=1e-12), (y, scores)
        assert 0.0 <= auc <= 1.0


def test_gate_chart_diagnostics_and_markdown_stability(studio_ctx):
    """The chart face gains points + roc as DIAGNOSTICS; the markdown verdict and the table note stay
    byte-identical — ROC is reported, never gating."""
    pytest.importorskip("xgboost")
    run(studio_ctx, "studio_train_site", train_until=2022)
    md1 = run(studio_ctx, "studio_validate").data
    assert "עבר את השער" in md1 and "ROC" not in md1
    r = run(studio_ctx, "studio_validate", view="chart")
    assert r.kind == "chart"
    spec = r.data
    assert spec["renderer"] == "png" and spec["png_base64"]                  # the PNG twin stays the deciles image
    pts = spec["points"]
    assert 0 < len(pts) <= 600 and all(len(p) == 2 for p in pts)
    assert [p[0] for p in pts] == sorted(p[0] for p in pts)                  # sorted by mu
    roc = spec["roc"]
    assert 0.0 <= roc["auc"] <= 1.0 and roc["auc"] > 0.5                     # the planted signal ranks
    assert roc["fpr"][0] == 0.0 and roc["tpr"][0] == 0.0 and roc["fpr"][-1] == 1.0 and roc["tpr"][-1] == 1.0
    assert roc["fpr"] == sorted(roc["fpr"]) and roc["tpr"] == sorted(roc["tpr"])   # monotone non-decreasing
    assert roc["positive"]["rule"] == "top-decile-observed" and roc["positive"]["positive_n"] >= 1
    pos_caveat = [c for c in spec["caveats"] if c.startswith("מחלקה חיובית ל-ROC")]
    assert len(pos_caveat) == 1 and "כלל התוסף" in pos_caveat[0]             # plugin-tagged, like the deviance rule
    assert f"n={roc['positive']['positive_n']:,}" in pos_caveat[0]
    assert all(";" not in c for c in spec["caveats"])
    json_safe(r)
    t = run(studio_ctx, "studio_validate", view="table")
    assert "ROC" not in t.note                                               # table face untouched
    md2 = run(studio_ctx, "studio_validate").data
    assert md2 == md1                                                        # byte-stable: the gate itself unchanged


def test_train_validate_deploy_round_trip(studio_ctx):
    pytest.importorskip("xgboost")
    r = run(studio_ctx, "studio_train_site", train_until=2022)
    assert r.kind == "markdown" and "מודל מועמד" in r.data, r.data
    doc_meta = registry.list_models(studio_ctx)[-1]
    doc_id = doc_meta["model_id"]
    assert doc_meta["status"] == "candidate"
    assert doc_meta["features"] == list(constants.FEATURES)                  # the contract
    assert doc_meta["adt_fill"]["value"] == 31100.0
    assert doc_meta["static_attrs"]["segments_with_history"] == 60
    assert doc_meta["panel"]["n_train"] == 360 and doc_meta["panel"]["n_holdout"] == 120
    assert run(studio_ctx, "site_ranking").data.startswith("# ❌")           # nothing deployed yet
    v = run(studio_ctx, "studio_validate")
    assert "עבר את השער" in v.data, v.data
    g = registry.read_meta(studio_ctx, doc_id)["gate"]["metrics"]
    assert g["spearman"] == pytest.approx(0.82, abs=0.1)                     # the planted signal is strong
    assert g["calibration"] == pytest.approx(1.03, abs=0.12)
    assert g["deviance_ratio"] < constants.GATE["deviance_ratio_max"][0]
    run(studio_ctx, "studio_train_site", train_until=2018, features="shuffled")
    sh_id = registry.list_models(studio_ctx)[-1]["model_id"]
    assert "shuffled" in sh_id and sh_id != doc_id
    v2 = run(studio_ctx, "studio_validate")                                  # latest = the shuffled straw man
    assert "נדחה" in v2.data and "Spearman" in v2.data, v2.data
    d_rej = run(studio_ctx, "studio_deploy", model_id=sh_id)                 # THE governance refusal
    assert d_rej.data.startswith("# ❌") and "הסיבה" in d_rej.data
    assert registry.deployed(studio_ctx)[0] is None
    d_cand = run(studio_ctx, "studio_deploy", model_id=doc_id) if False else None  # doc is validated already
    d = run(studio_ctx, "studio_deploy")                                     # latest VALIDATED
    assert "נפרס" in d.data, d.data
    pointer, dep_meta = registry.deployed(studio_ctx)
    assert pointer["model_id"] == doc_id and dep_meta["status"] == "deployed"
    assert f"**מודל אתר פרוס** — {doc_id}" in run(studio_ctx, "about").data
    tbl = run(studio_ctx, "studio_models").data
    by_id = {row[0]: (row[1], row[2]) for row in tbl["rows"]}
    assert by_id[doc_id] == ("deployed", True) and by_id[sh_id][0] == "rejected"
    assert any("Spearman" in (row[-1] or "") for row in tbl["rows"])         # the reasons column
    d_again = run(studio_ctx, "studio_deploy", model_id=doc_id)
    assert "כבר פרוס" in d_again.data                                        # idempotent
    json_safe(v)
    json_safe(d_rej)


def test_candidate_cannot_deploy(studio_ctx):
    pytest.importorskip("xgboost")
    run(studio_ctx, "studio_train_site", train_until=2022)
    cand = registry.list_models(studio_ctx)[-1]["model_id"]
    r = run(studio_ctx, "studio_deploy", model_id=cand)
    assert r.data.startswith("# ❌") and "טרם אומת" in r.data


def _fake_meta(model_id: str, status: str) -> dict:
    return {"model_id": model_id, "family": "site", "status": status, "created_at": registry.now_utc(),
            "contract_version": constants.CONTRACT_VERSION,
            "preset": "doc-11", "seed": 1, "features": list(constants.FEATURES),
            "adt_fill": {"value": 10000.0}, "panel": {"train_until": 2023, "years": [2017, 2024]},
            "static_attrs": {"columns": list(panel.STATIC_COLUMNS), "rows": []},
            "sql": {"panel": "--", "static_attrs": "--", "adt_median": "--"}, "alpha": 0.1,
            "gate": {"metrics": {}, "reasons": []}}


def test_ml_missing_is_readable(studio_ctx, monkeypatch):
    mid = registry.save(studio_ctx, "site-x", _fake_meta("site-x", "validated"), b"not-a-model")
    registry.set_deployed(studio_ctx, registry.read_meta(studio_ctx, mid))
    monkeypatch.setitem(sys.modules, "xgboost", None)
    for action, kw in (("studio_train_site", {}), ("studio_validate", {"model_id": mid}), ("site_ranking", {})):
        r = run(studio_ctx, action, **kw)
        assert r.kind == "error", (action, r.data)
        assert "pip install" in r.data and "Traceback" not in r.data, (action, r.data)


def test_registry_atomic_and_tolerant(studio_ctx):
    mid1 = registry.save(studio_ctx, "site-t", _fake_meta("site-t", "candidate"), b"a")
    mid2 = registry.save(studio_ctx, "site-t", _fake_meta("site-t", "validated"), b"b")
    assert (mid1, mid2) == ("site-t", "site-t-2")                            # a collision re-suffixes, never overwrites
    root = registry.root(studio_ctx)
    assert not list(root.rglob("*.tmp"))                                     # atomic writes leave no droppings
    (registry.model_dir(studio_ctx, "site-t") / "meta.json").write_text("{oops", "utf-8")
    models = {m["model_id"]: m["status"] for m in registry.list_models(studio_ctx)}
    assert models["site-t"] == "unreadable" and models["site-t-2"] == "validated"
    registry.write_json_atomic(root / "deployed.json", {"model_id": "site-t-2"})   # the P1-test pointer shape
    pointer, meta = registry.deployed(studio_ctx)
    assert pointer["model_id"] == "site-t-2" and meta["status"] == "validated"
    latest, _ = registry.resolve_id(studio_ctx, "latest", want="validated")
    assert latest["model_id"] == "site-t-2"


def test_registry_survives_a_data_dir_move(tmp_path):
    """The durability story: the registry is plain files under the data dir; moving the dir moves the registry.
    NL2SQL_CORE_DATA_DIR is read once per process, so each step is its own subprocess."""
    repo = Path(__file__).resolve().parents[1]
    a, b = tmp_path / "dir-a", tmp_path / "dir-b"
    env = {**os.environ, "PYTHONPATH": f"{repo};{repo / 'tests'}", "PYTHONUTF8": "1"}
    script = (
        "import sys\n"
        "from nl2sql_engine.modules import Context\n"
        "from nl2sql_roadsafety.studio import registry\n"
        "ctx = Context(db_path='unused')\n"
        "if sys.argv[1] == 'write':\n"
        "    meta = {'model_id': 'site-move', 'family': 'site', 'status': 'validated',\n"
        "            'created_at': registry.now_utc(), 'preset': 'doc-11', 'alpha': 0.1,\n"
        "            'panel': {'train_until': 2023}}\n"
        "    mid = registry.save(ctx, 'site-move', meta, b'model-bytes')\n"
        "    registry.set_deployed(ctx, registry.read_meta(ctx, mid))\n"
        "pointer, meta = registry.deployed(ctx)\n"
        "print('DEPLOYED=' + str(pointer and pointer['model_id']))\n"
    )
    out1 = subprocess.run([sys.executable, "-c", script, "write"], env={**env, "NL2SQL_CORE_DATA_DIR": str(a)},
                          capture_output=True, text=True, timeout=120)
    assert "DEPLOYED=site-move" in out1.stdout, out1.stdout + out1.stderr
    a.rename(b)
    out2 = subprocess.run([sys.executable, "-c", script, "read"], env={**env, "NL2SQL_CORE_DATA_DIR": str(b)},
                          capture_output=True, text=True, timeout=120)
    assert "DEPLOYED=site-move" in out2.stdout, out2.stdout + out2.stderr
    assert (b / "accidents" / "models" / "site" / "site-move" / "model.ubj").read_bytes() == b"model-bytes"


def test_contract_version_is_enforced(studio_ctx):
    """The version stamp is a tripwire for semantic panel drift under unchanged feature names (sweep finding:
    it was write-only). A missing stamp counts as a mismatch — deployed models outlive plugin upgrades."""
    from nl2sql_roadsafety.sqlkit import Refusal
    from nl2sql_roadsafety.studio import predict

    ok = _fake_meta("site-cv", "deployed")
    predict.contract_check(ok)                                               # current version passes
    for bad_version in (999, None):
        bad = dict(ok)
        if bad_version is None:
            bad.pop("contract_version")
        else:
            bad["contract_version"] = bad_version
        with pytest.raises(Refusal, match="חוזה המאפיינים"):
            predict.contract_check(bad)


def test_registry_concurrency(studio_ctx):
    """The sweep's stress findings: on Windows, os.replace onto a file another thread holds open raises
    PermissionError, save's collision check was check-then-act, and two deploys could leave two 'deployed' metas.
    All three are exercised here under real threads — the registry lock must keep every invariant."""
    import threading

    mid = registry.save(studio_ctx, "site-c", _fake_meta("site-c", "validated"), b"m")
    stop = threading.Event()
    errors = []

    def writer():
        n = 0
        while not stop.is_set():
            n += 1
            try:
                assert registry.update_meta(studio_ctx, mid, n=n) is not None
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

    def reader():
        while not stop.is_set():
            try:
                registry.read_meta(studio_ctx, mid)
                registry.list_models(studio_ctx)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

    threads = [threading.Thread(target=writer)] + [threading.Thread(target=reader) for _ in range(4)]
    for t in threads:
        t.start()
    import time
    time.sleep(1.0)
    stop.set()
    for t in threads:
        t.join()
    assert not errors, errors[:3]                                            # 99 % of writes failed before the lock
    assert registry.read_meta(studio_ctx, mid)["status"] == "validated"
    assert not list(registry.root(studio_ctx).rglob("*.tmp"))

    barrier = threading.Barrier(2)                                           # concurrent same-id saves re-suffix
    ids = []

    def saver(marker):
        barrier.wait()
        ids.append(registry.save(studio_ctx, "site-race", _fake_meta("site-race", "validated"), marker))

    ts = [threading.Thread(target=saver, args=(m,)) for m in (b"one", b"two")]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(ids) == ["site-race", "site-race-2"], ids
    for i in ids:                                                            # meta and model stay a matched pair
        assert registry.read_meta(studio_ctx, i)["model_id"] == i
        assert registry.model_bytes(studio_ctx, i) in (b"one", b"two")

    m1 = registry.save(studio_ctx, "site-d1", _fake_meta("site-d1", "validated"), b"1")
    m2 = registry.save(studio_ctx, "site-d2", _fake_meta("site-d2", "validated"), b"2")
    barrier2 = threading.Barrier(2)

    def deployer(i):
        barrier2.wait()
        registry.deploy(studio_ctx, registry.read_meta(studio_ctx, i))

    ts = [threading.Thread(target=deployer, args=(i,)) for i in (m1, m2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    pointer, _ = registry.deployed(studio_ctx)
    live = [m["model_id"] for m in registry.list_models(studio_ctx) if m.get("status") == "deployed"]
    assert live == [pointer["model_id"]], (live, pointer)                     # exactly ONE deployed meta == pointer


def test_validate_error_when_verdict_cannot_be_saved(studio_ctx, monkeypatch):
    """A verdict shown on the card but silently lost from the registry was a sweep finding — now a loud error."""
    pytest.importorskip("xgboost")
    run(studio_ctx, "studio_train_site", train_until=2022)
    monkeypatch.setattr(registry, "update_meta", lambda *a, **k: None)
    r = run(studio_ctx, "studio_validate")
    assert r.kind == "error" and "was not saved" in r.data and "Traceback" not in r.data, r.data


def test_train_until_bounds(studio_ctx):
    assert run(studio_ctx, "studio_train_site", train_until=2016).data.startswith("# ❌")
    assert run(studio_ctx, "studio_train_site", train_until=2024).data.startswith("# ❌")
    assert run(studio_ctx, "studio_train_site", features="nope").kind == "error"


def test_registry_is_family_correct_with_two_families(studio_ctx):
    """P9's prerequisite regression: read_meta/save/update_meta/model_bytes were family-blind — a second family's
    metas were looked up under site/ and every severity model came back 'unreadable'."""
    m_site = registry.save(studio_ctx, "site-x2", _fake_meta("site-x2", "validated"), b"site-bytes")
    sev_meta = {**_fake_meta("severity-x", "validated"), "family": "severity"}
    m_sev = registry.save(studio_ctx, "severity-x", sev_meta, b"sev-bytes", family="severity")
    # per-family listing reads the RIGHT metas (no cross-family 'unreadable')
    assert [m["status"] for m in registry.list_models(studio_ctx, "severity")] == ["validated"]
    assert all(m["status"] != "unreadable" for m in registry.list_models(studio_ctx))
    assert registry.read_meta(studio_ctx, m_sev, family="severity")["model_id"] == m_sev
    assert registry.read_meta(studio_ctx, m_sev) is None                     # site/ really does not have it
    assert registry.model_bytes(studio_ctx, m_sev, family="severity") == b"sev-bytes"
    # independent per-family pointers; deploy demotes only within its family
    registry.deploy(studio_ctx, registry.read_meta(studio_ctx, m_site))
    registry.deploy(studio_ctx, registry.read_meta(studio_ctx, m_sev, family="severity"))
    assert registry.deployed(studio_ctx)[0]["model_id"] == m_site
    assert registry.deployed(studio_ctx, "severity")[0]["model_id"] == m_sev
    assert registry.read_meta(studio_ctx, m_site)["status"] == "deployed"
    assert registry.update_meta(studio_ctx, m_sev, "severity", note="x")["note"] == "x"
    assert registry.new_model_id(2022, "person-12", 7, family="severity").startswith("severity-2022-person12-s7-")
