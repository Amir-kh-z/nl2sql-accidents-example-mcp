# -*- coding: utf-8 -*-
"""ab_scan: the before/after discoverer — |z| is a rank score only. The top row is hand-verified against
did_math on the same four cells; determinism, the multiplicity caveat with its computed N/M, the thin
refusal, and the SQL face reproducing the sweep's input are all pinned on the plain fixture."""
from __future__ import annotations

import json
import math

from nl2sql_roadsafety.sqlkit import did_math, rows_safe
from helpers import json_safe, png_of, run

SCAN = {"from_year": 2012, "to_year": 2021, "min_cell": 1}


def test_top_row_matches_did_math_on_the_same_cells(ctx):
    r = run(ctx, "ab_scan", view="chart", **SCAN)
    assert r.kind == "chart", r.data
    spec = r.data
    assert spec["type"] == "accidents/ab_scan"
    assert spec["columns"] == ["site_key", "label", "change_year", "before", "after", "ratio", "z",
                               "controlled", "direction"]
    # ONE candidate on the plain fixture, NEW convention (event year excluded from both windows):
    # (1,10)'s strongest |z| is e=2015 — casualty before [2013,2014] = 5, after [2016,2017] = 1;
    # national network (whole country, both road types) 10 -> 5. e=2016 (the old convention's pick)
    # scores z=-0.7556, weaker than e=2015's -0.8637.
    assert len(spec["rows"]) == 1
    row = spec["rows"][0]
    d = did_math(5, 1, 10, 5, 1)                                 # the SAME four cells, by hand
    z = math.log(d["ratio"]) / math.sqrt(d["se2"])
    assert row[0] == "road:1/0-12"                               # latest vintage km range, before_after's syntax
    assert row[1] == "1/10 · צומת א ← צומת ב"                    # latest-vintage names, the house segment label
    assert row[2] == 2015 and row[3] == 5 and row[4] == 1
    assert row[5] == round(d["ratio"], 4) == 0.4
    assert row[6] == round(z, 4) == -0.8637
    # controlled: damage-only cells 4,4 (site) vs 8,8 (network) — all four >= min_cell -> 0.4 / 1.0
    assert row[7] == 0.4
    assert row[8] == "שיפור"                                     # ratio < 1 = improved more than the network
    assert spec["units_scanned"] == 3 and spec["event_years"] == 6      # e in [2014..2019]
    assert spec["handoff"] == {"action": "before_after", "site": "road:1/0-12", "change_year": 2015,
                               "window_years": 2, "min_cell": 1}
    assert spec["denominator"]["kind"] == "exposure" and "כל הרשת הארצית" in spec["denominator"]["label"]
    assert spec["basis"].isascii() and spec["stamp"].isascii() and "no CI by design" in spec["basis"]
    png_of(spec)
    json_safe(r)


def test_multiplicity_caveat_and_the_route_line(ctx):
    spec = run(ctx, "ab_scan", view="chart", **SCAN).data
    assert spec["caveats"][0] == ("נסרקו 3 יחידות על פני 6 שנות אירוע — ללא תיקון להשוואות מרובות · "
                                  "ציון z לדירוג בלבד, לא מבחן")
    route = spec["caveats"][-1]
    assert "before_after" in route and "road:1/0-12" in route and "2015" in route
    assert any("נסיגה לממוצע" in c for c in spec["caveats"])     # regression to the mean
    assert any("גילוי ואינו ייחוס" in c for c in spec["caveats"])
    assert any("hotspot_map" in c for c in spec["caveats"])      # the segments-only scope routes junctions
    assert all(";" not in c for c in spec["caveats"])
    assert "\n" not in run(ctx, "ab_scan", view="chart", **SCAN).note


def test_determinism_two_runs_byte_equal(ctx):
    a = run(ctx, "ab_scan", view="table", **SCAN).data
    b = run(ctx, "ab_scan", view="table", **SCAN).data
    assert json.dumps(a["rows"], ensure_ascii=False) == json.dumps(b["rows"], ensure_ascii=False)


def test_sql_face_reproduces_the_sweep(ctx):
    spec = run(ctx, "ab_scan", view="chart", **SCAN).data
    assert run(ctx, "ab_scan", view="sql", **SCAN).data == spec["sql"]
    rows = rows_safe(ctx.query(spec["sql"])[1])
    unit = {(r[1], r[2], r[3]): (r[4], r[5]) for r in rows if r[0] == "unit"}
    net = {r[3]: (r[4], r[5]) for r in rows if r[0] == "network"}
    # rebuild the top candidate's four casualty cells from the re-executed statement — e=2015,
    # before [2013,2014], after [2016,2017]: the event year is in NEITHER window
    sb = sum(unit.get((1, 10, y), (0, 0))[0] for y in (2013, 2014))
    sa = sum(unit.get((1, 10, y), (0, 0))[0] for y in (2016, 2017))
    nb = sum(net.get(y, (0, 0))[0] for y in (2013, 2014))
    na = sum(net.get(y, (0, 0))[0] for y in (2016, 2017))
    assert (sb, sa, nb, na) == (5, 1, 10, 5)
    d = did_math(sb, sa, nb, na, 1)
    assert spec["rows"][0][5] == round(d["ratio"], 4)
    assert spec["rows"][0][6] == round(math.log(d["ratio"]) / math.sqrt(d["se2"]), 4)
    # the network rows are the WHOLE country: Z1's sentinel junction and the urban rows are counted
    assert net[2019] == (5, 0) and net[2012] == (6, 4)
    assert 2015 not in net                                       # an empty year is absent, summed as zero


def test_handoff_chain_reproduces_the_same_cells(ctx):
    """The regression that would have caught the geometry splice (refuter 2026-09-06): before_after on the
    emitted site/year/window must ACCEPT the hand-off and count the SAME site cells ab_scan ranked — one
    counting rule (latest-vintage literal km range, event year excluded) across the whole chain."""
    spec = run(ctx, "ab_scan", view="chart", **SCAN).data
    top = spec["rows"][0]
    h = spec["handoff"]
    ba = run(ctx, "before_after", view="chart", site=h["site"], change_year=h["change_year"],
             window_years=h["window_years"], min_cell=h["min_cell"])
    assert ba.kind == "chart", ba.data                            # accepted — never a range refusal
    bspec = ba.data
    ci = {c: i for i, c in enumerate(bspec["columns"])}
    site_cas = next(r for r in bspec["rows"]
                    if r[ci["series"]] in ("נפגעים", "casualty") or "נפגע" in str(r[ci["series"]]))
    assert (site_cas[ci["site_before"]], site_cas[ci["site_after"]]) == (top[3], top[4])
    # the last sweepable event year is verifiable too, by construction (e1 = to_year - w)
    last_ok = run(ctx, "before_after", view="chart", site=h["site"], change_year=2021 - 2,
                  window_years=2, min_cell=1)
    assert last_ok.kind in ("chart", "markdown")                  # in range — a refusal here would be the old bug
    if last_ok.kind == "markdown":
        assert "חורג מהנתונים" not in last_ok.data


def test_window_clamp(ctx):
    spec = run(ctx, "ab_scan", window_years=9, view="chart", **SCAN).data
    assert spec["window_years"] == 3                             # clamped, never an error
    spec1 = run(ctx, "ab_scan", window_years=0, view="chart", **SCAN).data
    assert spec1["window_years"] == 1


def test_refusals_and_errors(ctx):
    r = run(ctx, "ab_scan", from_year=2012, to_year=2021, min_cell=100)      # absurdly high: nothing passes
    assert r.kind == "markdown" and r.data.startswith("# ❌") and "100" in r.data
    r = run(ctx, "ab_scan", from_year=2012, to_year=2021)        # the default 6 is also thin on this fixture
    assert r.kind == "markdown" and r.data.startswith("# ❌")
    r = run(ctx, "ab_scan", from_year=2020, to_year=2021)        # no event year fits a 2+2 window
    assert r.kind == "markdown" and r.data.startswith("# ❌")
    r = run(ctx, "ab_scan", to_year=2030)                        # illegal range
    assert r.kind == "markdown" and r.data.startswith("# ❌")
    r = run(ctx, "ab_scan", road=77, from_year=2012, to_year=2021, min_cell=1)
    assert r.kind == "markdown" and r.data.startswith("# ❌")     # a road with no counted segments
    assert run(ctx, "ab_scan", from_year=2024, to_year=2012).kind == "error"
    assert run(ctx, "ab_scan", min_cell=0).kind == "error"
    assert run(ctx, "ab_scan", top_n=0).kind == "error"
    assert run(ctx, "ab_scan", top_n=51).kind == "error"
    assert run(ctx, "ab_scan", road=-1).kind == "error"
    assert run(ctx, "ab_scan", view="nope").kind == "error"
