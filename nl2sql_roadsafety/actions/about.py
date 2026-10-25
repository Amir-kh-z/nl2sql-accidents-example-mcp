# -*- coding: utf-8 -*-
"""about: connection probe, coverage, row counts per series, schema objects, golden rules, license,
and the deployed site model (read-only look at the P4 registry pointer)."""
from __future__ import annotations

import json

from nl2sql_engine.modules import Action

from ..envelope import CAVEAT_DATA_END, DENOM_NA, guard, markdown_answer, version
from ..sqlkit import ABOUT_KPI_SQL, ABOUT_SQL, rows_safe


def _deployed(ctx, family: str = "site") -> str:
    """The registry pointer (read-only; the tolerant reader lives in studio.registry)."""
    from ..studio import registry

    pointer, _meta = registry.deployed(ctx, family)
    if pointer is None:
        return "אין"
    if pointer.get("unreadable"):
        return "לא ברור (deployed.json אינו קריא)"
    return str(pointer.get("model_id", "?"))


@guard("אודות · מעבדת הבטיחות בדרכים", ledger=False)
def run(ctx):
    cols, rows = ctx.query(ABOUT_SQL)
    c = dict(zip(cols, rows_safe(rows)[0]))
    n_obj = len(ctx.tables())
    body = [
        f"# מעבדת הבטיחות בדרכים · nl2sql-roadsafety-lab {version()}",
        "**חיבור** — מסד תאונות הדרכים של הלמ״ס זוהה (accidents.case_type_code)",
        f"**כיסוי** — {c['first_year']} עד {c['last_year']} · חודש אחרון בנתונים: {c['last_month']}/{c['last_year']} · "
        f"הנתונים מסתיימים ב-{c['data_end']}",
        f"**תאונות** — {c['accidents_rows']:,} רשומות = {c['casualty_accidents']:,} עם נפגעים (case_type_code = 1) + "
        f"{c['damage_only']:,} נזק-בלבד (case_type_code = 3)",
        f"**מעורבים** — {c['involved_rows']:,} ({c['casualty_involved']:,} בסדרת הנפגעים) · **כלי רכב** — {c['vehicles_rows']:,}",
        f"**אובייקטים בסכמה** — {n_obj} ({c['n_tables']} טבלאות + {c['n_views']} מבטים); הצ'אט רואה את כולם — "
        f"בלי כללי הסדרה, המפתחות והמכנים",
        f"**מודל אתר פרוס** — {_deployed(ctx)} · **מודל חומרה פרוס** — {_deployed(ctx, 'severity')}",
        "# כללי הזהב",
        "- שאלות על נפגעים, חומרה או הרוגים: תמיד case_type_code = 1",
        "- צירוף למעורבים ולכלי רכב: על המפתח (accident_id, case_type_code)",
        "- הרוגים (אנשים) ≠ תאונות קטלניות (אירועים)",
        "- ספירות אינן סיכון בלי מכנה חשיפה",
        "# רישיון",
        "- נתוני למ״ס באישור אישי: המסד לא מועבר, לא מועלה לענן ולא נשמר בגיט",
        "- כל פלט נושא את קרדיט הלמ״ס",
        "# פעולות",
        # P10: the list is COMPLETE again (P5/P9 additions had drifted out of it — recorded deviation);
        # P12 sweep caught the SAME drift class once more — test_about now derives the roster from MODULE
        "- trend · naive_vs_correct · about · segment_rates · hotspot_map · map_scene · site_profile · "
        "site_ranking · severity_profile · vehicle_cells_ranking · two_wheelers · before_after · ab_scan · "
        "weather_check · heat_matrix · zone_ranking · city_ranking · severity_predict · what_if · "
        "severity_explain · triage",
        "- סטודיו: studio_train_site · studio_validate · studio_train_severity · studio_validate_severity · "
        "studio_deploy · studio_explain · studio_models — פנקס: ledger_list · finding_card",
    ]
    # P13: the page's KPI strip parses these exact lines — key inside ** **, values after the em-dash,
    # live-computed with the casualty filter (a naive count would take both series)
    kpi_cols, kpi_rows = ctx.query(ABOUT_KPI_SQL)
    k = dict(zip(kpi_cols, rows_safe(kpi_rows)[0]))
    body += [
        "# מדדים אחרונים",
        f"- **שנה אחרונה** — {k['latest_year']}",
        f"- **תאונות** — {k['accidents_latest']:,} · לפני: {k['accidents_prev']:,}",
        f"- **הרוגים** — {k['killed_latest']:,} · לפני: {k['killed_prev']:,}",
        f"- **פצועים קשה** — {k['severe_latest']:,} · לפני: {k['severe_prev']:,}",
    ]
    return markdown_answer("אודות · מעבדת הבטיחות בדרכים", body, denom=DENOM_NA, caveats=[CAVEAT_DATA_END])


# Declared LAST (Action.run is evaluated at import).
ACTION = Action(
    name="about", label="אודות · about",
    help="Connection probe (is this the CBS accidents database?), coverage and data end, row counts per "
         "series, schema object count, golden rules, license rules and the deployed site model (P4).",
    inputs={},          # run(ctx) with no kwargs; Layer 0 still renders a Run button
    run=run)
