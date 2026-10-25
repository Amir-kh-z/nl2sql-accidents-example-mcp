# -*- coding: utf-8 -*-
"""finding_card: promote one ledger entry to a finding — the claim, the recorded evidence, the caveats it carried,
and the exact rerun recipe. 'This is what leaves the room.'"""
from __future__ import annotations

import json

from nl2sql_engine.modules import Action, Input

from ..envelope import denominator, guard, markdown_answer
from ..sqlkit import ActionError, Refusal
from ..studio import ledger

TITLE = "כרטיס ממצא"


@guard(TITLE, ledger=False)
def run(ctx, entry="latest", claim=""):
    entries, bad = ledger.read(ctx)
    if not entries:
        raise Refusal("הפנקס ריק — אין רשומה להפוך לממצא", ["הריצו פעולה כלשהי ואז finding_card",
                                                            "ledger_list לרשימת הרשומות"])
    s = str(entry or "").strip()
    if s in ("", "latest"):
        idx = len(entries)
    else:
        try:
            idx = int(s)
        except ValueError:
            raise ActionError(f"entry must be 'latest' or an index from ledger_list; got {entry!r}.") from None
        if not 1 <= idx <= len(entries):
            raise Refusal(f"אין רשומה מספר {idx} בפנקס — יש {len(entries)} רשומות", ["ledger_list"])
    e = entries[idx - 1]
    numbers = e.get("numbers") or {}
    claim_text = str(claim or "").strip()
    body = ["# ממצא", claim_text if claim_text else "ללא טענה — הראיות בלבד",
            "# ראיות",
            f"- פעולה: {e.get('action', '?')} ({e.get('shape', '?')}) · {e.get('title', '')}",
            f"- שורת הבסיס: {e.get('headline', '')}"]
    for k, v in list(numbers.items())[:12]:
        body.append(f"- {k}: {json.dumps(v, ensure_ascii=False, default=str)[:220]}")
    body += ["# שחזור",
             f"- פעולה: {e.get('action', '?')}",
             f"- קלטים: {json.dumps(e.get('inputs', {}), ensure_ascii=False)}",
             f"- גרסה: {e.get('plugin_version', '?')} · זמן הרישום: {e.get('ts', '?')}"]
    denom_label = (e.get("denominator") or {}).get("label") or "לא רלוונטי — הראיות כפי שנרשמו בזמן ההרצה"
    caveats = list(e.get("caveats") or [])
    caveats.append("הראיות הן המספרים שנרשמו בזמן ההרצה — הרצה חוזרת עם אותם קלטים משחזרת אותם")
    return markdown_answer(TITLE, body, denom=denominator("na", denom_label), caveats=caveats)


ACTION = Action(
    name="finding_card", label="כרטיס ממצא · finding_card",
    help="Promote one ledger entry to a finding card: the claim, the recorded evidence numbers, the caveats it "
         "carried and the exact rerun recipe (action + inputs + version). 'latest' or an idx from ledger_list.",
    inputs={
        "entry": Input(kind="text", label="רשומה", default="latest", help="'latest' or an idx from ledger_list"),
        "claim": Input(kind="text", label="טענה", default="", help="the claim this evidence supports (optional)"),
    },
    run=run)
