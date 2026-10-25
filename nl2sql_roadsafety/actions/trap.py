# -*- coding: utf-8 -*-
"""naive_vs_correct (dossier §5.2): the light-accident trap, run deliberately. The naive statement
counts severity_label = 'קלה' across both series; the correct one is the same statement plus one
line (case_type_code = 1). Both numbers, the ratio, and why."""
from __future__ import annotations

from nl2sql_engine.modules import Action, Input

from ..envelope import CAVEAT_DATA_END, denominator, dispatch, guard, make_spec, view_input
from ..sqlkit import as_choice, as_int, trap_statements, year_in_coverage


@guard("המלכודת של התאונות הקלות")
def run(ctx, year=2024, view="markdown"):
    y = year_in_coverage(as_int(year, "year"), "year")
    view = as_choice(view, "view", ("markdown", "sql"))
    s = trap_statements(y)
    naive = int(ctx.query(s["naive"])[1][0][0])
    correct = int(ctx.query(s["correct"])[1][0][0])
    by = {(int(c), int(sv)): int(n) for c, sv, n in ctx.query(s["breakdown"])[1]}
    dmg = by.get((3, 3), 0)
    fatal, severe, slight = by.get((1, 1), 0), by.get((1, 2), 0), by.get((1, 3), 0)
    ratio = round(naive / correct, 1) if correct else None
    body = [
        f"# {naive:,} לעומת {correct:,}",
        f"**נאיבי** — {naive:,} רשומות עם severity_label = 'קלה' בשנת {y} (ללא סינון סדרה)",
        f"**נכון** — {correct:,} תאונות קלות עם נפגעים (אותה שאילתה + case_type_code = 1)",
        (f"**הפער** — פי {ratio}: {naive - correct:,} רשומות נזק-בלבד (case_type_code = 3) נספרו כ\"קלות\""
         if ratio else f"**הפער** — אין תאונות קלות עם נפגעים ב-{y}"),
        "# למה זה קורה",
        "- בטבלה accidents שתי סדרות: 1 = תאונות עם נפגעים, 3 = נזק-בלבד",
        "- בסדרת הנזק-בלבד severity_code = 3 והתווית \"קלה\" פירושם \"ללא נפגעים\" — לא \"פצועים קל\"",
        "- לכן כל שאלה על נפגעים, חומרה או הרוגים חייבת case_type_code = 1 (או את המבט v_casualty_accidents)",
        "# בדיקה",
        f"- {correct:,} + {dmg:,} = {correct + dmg:,} — הפער הוא בדיוק סדרת הנזק-בלבד",
        f"- {y}, עם נפגעים: {fatal:,} קטלניות · {severe:,} קשות · {slight:,} קלות = {fatal + severe + slight:,}",
    ]
    if naive != correct + dmg:                       # never on this DB — printed, never hidden
        body.append(f"- הערה: הפער אינו מוסבר במלואו על-ידי סדרת הנזק-בלבד (הפרש {naive - correct - dmg:,})")
    caveats = [CAVEAT_DATA_END, "ספירת תאונות ≠ ספירת נפגעים (פצועים קל נספרים בטבלת involved)"]
    spec = make_spec("accidents/naive_vs_correct", basis=f"year={y} | three statements | accidents",
                     rows=[["naive", naive], ["correct", correct], ["damage_only_slight", dmg], ["ratio", ratio]],
                     columns=["measure", "value"], sql="\n\n".join(s.values()),
                     denominator=denominator("na", "לא רלוונטי (השוואת שתי ספירות)"), caveats=caveats,
                     year=y, naive=naive, correct=correct, damage_only=dmg, ratio=ratio,
                     breakdown=[[c, sv, n] for (c, sv), n in sorted(by.items())])
    return dispatch(view, spec, "המלכודת של התאונות הקלות", body=body)


# Declared LAST (Action.run is evaluated at import).
ACTION = Action(
    name="naive_vs_correct", label="המלכודת · naive_vs_correct",
    help="Runs the naive 'light accidents' count (the severity label alone - both series answer) and "
         "the correct one (the same statement + case_type_code = 1) for one year: both counts, the ratio, "
         "and why the damage-only series inflates it.",
    inputs={
        "year": Input(kind="number", label="שנה", default=2024, help="2005-2024"),
        "view": view_input("markdown", ["markdown", "sql"]),
    },
    run=run)
