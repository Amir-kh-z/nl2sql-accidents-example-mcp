# -*- coding: utf-8 -*-
"""ledger_list: the tail of the findings ledger — what ran, when, and the headline it produced. The ledger is
written by the envelope on every answered run (answers and refusals, never errors)."""
from __future__ import annotations

import json

from nl2sql_engine.modules import Action, Input

from ..envelope import DENOM_NA, dispatch, guard, make_spec, stamp
from ..sqlkit import ActionError, Refusal, as_int
from ..studio import ledger

TITLE = "פנקס ממצאים"
COLS = ["idx", "ts", "action", "shape", "title", "headline", "inputs", "version"]


@guard(TITLE, ledger=False)
def run(ctx, last_n=20):
    last_n = as_int(last_n, "last_n")
    if not 1 <= last_n <= 500:
        raise ActionError(f"last_n must be between 1 and 500; got {last_n}.")
    entries, bad = ledger.read(ctx)
    if not entries:
        raise Refusal("הפנקס ריק — כל הרצה של פעולה (תשובה או סירוב) נרשמת בו אוטומטית",
                      ["הריצו פעולה כלשהי (למשל trend) וחזרו לכאן", "finding_card יהפוך רשומה לכרטיס ממצא"])
    start = max(0, len(entries) - last_n)
    rows = []
    for i, e in enumerate(entries[start:], start=start + 1):
        rows.append([i, e.get("ts", ""), e.get("action", "?"), e.get("shape", "?"), e.get("title", ""),
                     e.get("headline", ""), json.dumps(e.get("inputs", {}), ensure_ascii=False)[:200],
                     e.get("plugin_version", "")])
    caveats = ["הפנקס הוא רישום מקומי תחת ספריית הנתונים של האפליקציה — לא מסד הלמ״ס",
               "נרשמות תשובות וסירובים — לא שגיאות קלט · ללא תמונות וללא שורות נתונים"]
    if bad:
        caveats.append(f"{bad} שורות פגומות בפנקס דולגו")
    spec = make_spec("accidents/ledger",
                     basis=f"ledger_list | {len(rows)} of {len(entries)} entries | corrupt {bad}",
                     rows=rows, columns=COLS, sql="-- the ledger is a local JSONL file, not a SQL result",
                     denominator=DENOM_NA, caveats=caveats, stamp=stamp("ledger_list", f"last {last_n}"))
    return dispatch("table", spec, TITLE)


ACTION = Action(
    name="ledger_list", label="פנקס ממצאים · ledger_list",
    help="The tail of the findings ledger (accidents/ledger.jsonl under the app data dir): every answered run - "
         "answers and refusals - with its headline numbers. Use the idx with finding_card.",
    inputs={"last_n": Input(kind="number", label="מספר רשומות", default=20, help="1-500 latest entries")},
    run=run)
