# -*- coding: utf-8 -*-
from __future__ import annotations

from nl2sql_roadsafety.actions import trap
from nl2sql_roadsafety.envelope import CREDIT, LAB_LINE
from nl2sql_roadsafety.sqlkit import trap_statements
from helpers import json_safe, run


def test_trap_2024_markdown(ctx):
    r = run(ctx, "naive_vs_correct", year=2024)
    assert r.kind == "markdown", r.data
    lines = r.data.split("\n")
    assert lines[0].startswith("מכנה:") and lines[-1] == CREDIT
    assert "# 24 לעומת 4" in r.data
    assert "פי 6.0" in r.data
    assert "- 4 + 20 = 24" in r.data
    assert "1 קטלניות · 1 קשות · 4 קלות = 6" in r.data
    assert "case_type_code = 1" in r.data
    assert "הערה:" not in r.data
    json_safe(r)


def test_trap_other_years(ctx):
    assert "# 5 לעומת 1" in run(ctx, "naive_vs_correct", year=2023).data
    assert "פי 5.0" in run(ctx, "naive_vs_correct", year=2023).data
    assert "# 6 לעומת 1" in run(ctx, "naive_vs_correct", year="2022").data


def test_trap_sql_face(ctx):
    data = run(ctx, "naive_vs_correct", year=2024, view="sql").data
    s = trap_statements(2024)
    assert data == "\n\n".join(s.values())
    assert "-- 1. naive" in data and "-- 2. correct" in data and "-- 3. breakdown" in data
    assert data.count("severity_label = 'קלה'") == 2
    body = lambda sql: "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
    assert body(s["correct"]) == body(s["naive"]) + "\n  AND case_type_code = 1"
    assert s["naive"].count("case_type_code = 1") == 0
    assert data.count("\n  AND case_type_code = 1") == 1
    assert "code canon equivalent: case_type_code = 1 AND severity_code = 3" in data
    assert data.split("-- 2. correct")[0].count("case_type_code = 1") == 0
    assert ctx.query(s["naive"])[1] == [(24,)]


def test_trap_inputs_and_refusals(ctx, other_ctx):
    r = run(ctx, "naive_vs_correct", year=2030)
    assert r.kind == "markdown" and r.data.startswith("# ❌") and "31.12.2024" in r.data
    r = run(ctx, "naive_vs_correct", year="x")
    assert r.kind == "error" and "year" in r.data
    r = run(other_ctx, "naive_vs_correct")
    assert r.kind == "markdown" and r.data.split("\n")[-1] == LAB_LINE and "\n" not in r.note


def test_basis_is_ascii(ctx, monkeypatch):
    seen = {}
    real = trap.make_spec

    def recording(*args, **kwargs):
        spec = real(*args, **kwargs)
        seen.update(spec)
        return spec

    monkeypatch.setattr(trap, "make_spec", recording)
    run(ctx, "naive_vs_correct", year=2024)
    assert seen["basis"] == "year=2024 | three statements | accidents" and seen["basis"].isascii()
