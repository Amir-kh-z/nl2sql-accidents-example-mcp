# -*- coding: utf-8 -*-
"""Is this connection the CBS accidents database? The engine hands an action only a db_path, so the
plugin probes for the two-series schema itself and refuses readably anywhere else."""
from __future__ import annotations

from .sqlkit import Refusal

PROBE_SQL = "SELECT 1 FROM accidents WHERE case_type_code = 1 LIMIT 1"
REASON_HE = "החיבור הנוכחי אינו מסד תאונות הדרכים של הלמ״ס"          # one sentence, no newline — it heads the one-line note
WHAT_TO_DO = "בחרו את החיבור israel_accidents באפליקציה הראשית ופתחו את עמוד המודולים מחדש"
ANSWERABLE = ["EDA ו-Shapes פועלים על כל מסד נתונים"]


def check(ctx) -> str | None:
    """None on the accidents DB, else a reason a person can act on (three variants + a catch-all)."""
    try:
        tables = list(ctx.tables())
        if "accidents" not in tables:
            n = len(tables)
            return (f"no table named accidents in this connection ({n} table{'s' if n != 1 else ''}: "
                    f"{', '.join(tables[:6])}{', …' if n > 6 else ''})")
        if "case_type_code" not in ctx.columns("accidents"):
            return "accidents has no column case_type_code (not the CBS two-series schema)"
        if not ctx.query(PROBE_SQL)[1]:
            return "accidents holds no casualty rows (case_type_code = 1)"
    except Exception as exc:  # noqa: BLE001 — a foreign DB may raise anything
        first = str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__
        return f"accidents.case_type_code could not be read: {first}"
    return None


def require(ctx) -> None:
    reason = check(ctx)
    if reason:
        raise Refusal(REASON_HE, ANSWERABLE, what_to_do=WHAT_TO_DO, detail=reason)
