# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from nl2sql_roadsafety.envelope import (CREDIT, DENOM_COUNTS, DENOM_NA, LAB_LINE, REFUSAL_HEADING, ROUTE_HEADING,
                                       denominator, dispatch, make_spec, note_line, refusal, route_card, stamp,
                                       stamp_line, version, view_input)


def test_p2_envelope_additions():
    assert denominator("exposure", "x", matched=1)["matched"] == 1
    s = stamp("a", "b=c", "2019-2024")
    assert s == f"nl2sql-roadsafety-lab {version()} | a | b=c | 2019-2024" and s.isascii()
    r = route_card("t", "head\nmore", ["- x"], ["trend"])
    lines = r.data.split("\n")
    assert lines[0] == ROUTE_HEADING and lines[-1] == LAB_LINE and "- פעולה מתאימה: trend" in lines
    assert r.note.startswith("ניתוב · head ·") and "\n" not in r.note and CREDIT not in r.data
from nl2sql_roadsafety.sqlkit import ActionError


def test_note_line_exact():
    assert note_line(DENOM_COUNTS, ["a", "b"]) == \
        "מכנה: ספירות בלבד — ללא מכנה חשיפה · הסתייגות: a; b · מקור: הלשכה המרכזית לסטטיסטיקה"
    assert note_line(DENOM_NA, []).endswith("הסתייגות: אין · מקור: הלשכה המרכזית לסטטיסטיקה")


def test_denominator_kinds():
    with pytest.raises(ValueError):
        denominator("bogus", "x")
    assert denominator("exposure", "vkm") == {"kind": "exposure", "label": "vkm"}


def test_dispatch_refuses_unknown_views():
    spec = make_spec("t", basis="b", rows=[], columns=["x"], sql="SELECT 1", denominator=DENOM_NA, caveats=[])
    with pytest.raises(ActionError) as exc:
        dispatch("xml", spec, "t")
    assert "chart" in str(exc.value) and "sql" in str(exc.value)
    assert dispatch("table", spec, "t").kind == "table"
    assert dispatch("sql", spec, "t").data == "SELECT 1"
    assert spec["plugin_version"] == version()
    assert spec["credit"] == CREDIT


def test_refusal_shape():
    r = refusal("x", title="t")
    lines = r.data.split("\n")
    assert lines[0] == REFUSAL_HEADING and lines[-1] == LAB_LINE
    r = refusal("x\ny", title="t", detail="d", what_to_do="w", answerable=["a"])
    assert "\n" not in r.note
    assert "- הסיבה: d" in r.data and "- מה לעשות: w" in r.data and "- מה כן אפשר: a" in r.data
    assert r.note.startswith("לא ניתן לענות · x ·")


def test_stamp_and_view_help():
    s = stamp_line("killed", "year", "all", 2005, 2024)
    assert s == f"nl2sql-roadsafety-lab {version()} | killed / year / all | 2005-2024" and s.isascii()
    assert view_input("markdown", ["markdown", "sql"]).help == \
        "markdown = the explanation card; sql = the exact statement run"
