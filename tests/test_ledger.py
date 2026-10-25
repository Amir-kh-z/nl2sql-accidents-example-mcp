# -*- coding: utf-8 -*-
"""The findings ledger and its two actions: one line per answered run (refusals included, errors and the
ledger-exempt meta actions excluded), tolerant reads, the finding card's shape."""
from __future__ import annotations

import json

from nl2sql_roadsafety.envelope import CREDIT
from helpers import json_safe, run


def test_ledger_round_trip(ctx, tmp_path):
    run(ctx, "trend", from_year=2022, to_year=2024)                          # 1 · answer
    run(ctx, "before_after", site="road:1/0-10", change_year=2015, min_cell=2)   # 2 · answer
    run(ctx, "triage")                                                       # 3 · refusal (a finding too)
    run(ctx, "about")                                                        # exempt
    run(ctx, "studio_models")                                                # exempt since P13r2: registry
    # inspection is state, not a finding — the workbench auto-loads it on tab open (refusal here on the
    # empty fixture registry, and even that must not land in the ledger)
    assert run(ctx, "segment_rates", top_n=0).kind == "error"                # errors are never logged
    p = tmp_path / "accidents" / "ledger.jsonl"
    lines = p.read_text("utf-8").splitlines()
    assert len(lines) == 3
    entries = [json.loads(l) for l in lines]
    assert [e["action"] for e in entries] == ["trend", "before_after", "triage"]
    assert [e["shape"] for e in entries] == ["chart", "chart", "refusal"]
    assert all(len(l.encode("utf-8")) <= 4096 and "png_base64" not in l for l in lines)
    assert entries[1]["numbers"]["counts"] and entries[1]["inputs"]["site"] == "road:1/0-10"

    lst = run(ctx, "ledger_list", last_n=2)
    assert lst.kind == "table"
    assert [row[0] for row in lst.data["rows"]] == [2, 3]                    # absolute idx, oldest of the tail first
    assert lst.data["rows"][1][3] == "refusal"
    json_safe(lst)

    fc = run(ctx, "finding_card", entry="2", claim="באתר הזה הספירה ירדה")
    lines_fc = fc.data.split("\n")
    assert lines_fc[0].startswith("מכנה:") and lines_fc[-1] == CREDIT
    for needle in ("# ממצא", "באתר הזה הספירה ירדה", "# ראיות", "# שחזור", "before_after", "road:1/0-10"):
        assert needle in fc.data, needle
    latest = run(ctx, "finding_card")                                        # latest = the triage refusal
    assert "triage" in latest.data and "ללא טענה" in latest.data
    assert run(ctx, "finding_card", entry="99").data.startswith("# ❌")
    assert run(ctx, "finding_card", entry="abc").kind == "error"

    p.write_text(p.read_text("utf-8") + "not json at all\n", "utf-8")        # a corrupt line is counted, not fatal
    lst2 = run(ctx, "ledger_list")
    assert "שורות פגומות" in lst2.note                                       # the table face carries caveats in the note

    assert run(ctx, "ledger_list", last_n=0).kind == "error"


def test_oversized_entry_is_truncated_to_the_cap(ctx, tmp_path):
    """The final fallback used to keep `inputs` — the one unbounded field (16 keys x 400 chars x 4 UTF-8 bytes
    for emoji) — and never re-checked the cap: a 9.9 KB line landed (sweep finding). Every line now fits."""
    from types import SimpleNamespace

    from nl2sql_roadsafety import __version__
    from nl2sql_roadsafety.studio import ledger

    fat_inputs = {f"t{i}": "🚗" * 400 for i in range(6)}                     # ~9.6 KB once encoded
    result = SimpleNamespace(kind="markdown", data="# כותרת\nשורה", title="בדיקה", note="")
    ledger.append(ctx, ledger.entry_for("synthetic", fat_inputs, result, __version__))
    lines = (tmp_path / "accidents" / "ledger.jsonl").read_text("utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])                                             # parses AND fits
    assert len(lines[0].encode("utf-8")) <= 4096
    assert entry["action"] == "synthetic" and entry["inputs"] == {"truncated": True}
