# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from nl2sql_roadsafety import __version__
from nl2sql_roadsafety.actions import about
from nl2sql_roadsafety.envelope import CREDIT, LAB_LINE
from helpers import json_safe, run


def test_about_card(ctx):
    r = run(ctx, "about")
    assert r.kind == "markdown", r.data
    d = r.data
    for needle in ("98 רשומות = 45 עם נפגעים", "+ 53 נזק-בלבד", "**מעורבים** — 56 (53 בסדרת הנפגעים)",   # +1: the P3 sentinel row Z1
                   # P5: 16 vehicles rows (14 typed two-wheeler rows joined the 2), and fleet_motorcycles is table 11
                   # P12: code_lookups joined the fixture (the explain decode dictionary) -> 12 tables
                   # P13: the three geographic-aggregate fixture tables joined (accidents_by_taz,
                   # accidents_by_municipality, dim_settlement) -> 15 tables
                   "**כלי רכב** — 16", "2012 עד 2024", "12/2024", "2024-12-15", "18 (15 טבלאות + 3 מבטים)",
                   "**מודל אתר פרוס** — אין", __version__, "segment_rates", "triage",
                   # P13: the KPI strip — latest covered year vs the year before, live-computed with the
                   # casualty filter (fixture 2024: 6 casualty accidents, 2 killed, 1 severe; 2023: 2/1/0)
                   "# מדדים אחרונים",
                   "- **שנה אחרונה** — 2024",
                   "- **תאונות** — 6 · לפני: 2",
                   "- **הרוגים** — 2 · לפני: 1",
                   "- **פצועים קשה** — 1 · לפני: 0"):
        assert needle in d, needle
    assert d.split("\n")[-1] == CREDIT
    assert r.note == "מכנה: לא רלוונטי · הסתייגות: הנתונים מסתיימים ב-31.12.2024 · מקור: הלשכה המרכזית לסטטיסטיקה"
    json_safe(r)


def test_about_lists_every_action(ctx):
    """The roster is derived from MODULE so the P5/P9/P12 drift class (a new action missing from the
    'פעולות' block) can never recur — the P12 sweep caught it a third time."""
    from nl2sql_roadsafety import MODULE

    d = run(ctx, "about").data
    for a in MODULE.actions:
        assert a.name in d, a.name


def test_about_sees_a_deployment(ctx, tmp_path):
    p = tmp_path / "accidents" / "models" / "site" / "deployed.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"model_id": "site-x"}), encoding="utf-8")
    assert "**מודל אתר פרוס** — site-x" in run(ctx, "about").data


def test_about_refuses_on_a_foreign_database(other_ctx):
    r = run(other_ctx, "about")
    assert r.kind == "markdown" and r.title == "אודות · מעבדת הבטיחות בדרכים"
    assert "Traceback" not in r.data
    assert "no table named accidents" in r.data and "1 table:" in r.data
    assert r.data.split("\n")[-1] == LAB_LINE and CREDIT not in r.data
    assert "\n" not in r.note


def test_guard_turns_crashes_into_error_results(ctx, monkeypatch):
    def boom(ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr(about, "_deployed", boom)
    r = run(ctx, "about")
    assert r.kind == "error" and "RuntimeError: boom" in r.data and "Traceback" in r.data


def test_actions_write_only_the_ledger_under_data_dir(ctx, tmp_path):
    """P1-P3 wrote nothing; since P4 the ONLY write is the findings ledger (one line per answered run —
    `about` is ledger-exempt, so nine of the ten runs below appear)."""
    run(ctx, "trend", from_year=2022, to_year=2024)
    run(ctx, "naive_vs_correct")
    run(ctx, "about")
    run(ctx, "segment_rates", from_year=2019, to_year=2021)
    run(ctx, "hotspot_map", from_year=2019, to_year=2021, points=True)
    run(ctx, "severity_profile")
    run(ctx, "vehicle_cells_ranking")
    run(ctx, "before_after", site="road:1/0-10", change_year=2015, min_cell=2)
    run(ctx, "weather_check", from_year=2012, to_year=2021)
    run(ctx, "triage")
    files = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert files == ["accidents/ledger.jsonl", "accidents_test.duckdb"], files
    lines = (tmp_path / "accidents" / "ledger.jsonl").read_text("utf-8").splitlines()
    assert len(lines) == 9                                                   # all but `about`
    import json as _json
    shapes = [_json.loads(l)["shape"] for l in lines]
    assert shapes.count("refusal") == 1 and "png_base64" not in "".join(lines)   # triage's default refusal card
