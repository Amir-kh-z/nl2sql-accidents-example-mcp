# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from nl2sql_roadsafety.actions.triage import classify
from nl2sql_roadsafety.envelope import CREDIT, LAB_LINE, REFUSAL_HEADING, ROUTE_HEADING
from helpers import json_safe, run


@pytest.mark.parametrize("question,needle", [
    ("איזה דגם רכב הכי בטוח?", "דגם"),
    ("Is a Corolla safer than a Mazda 3?", "דגם"),
    ("what is the risk per km at urban junctions?", "מכנה חשיפה"),
    ('סיכון לק"מ בצומת עירוני', "מכנה חשיפה"),
    ("how many accidents in 2026?", "31.12.2024"),
    ("כמה תאונות היו השנה?", "31.12.2024"),
    ("תאונות של תושבי חיפה", "מקום מגורים"),
    ("accidents where the driver lives in Haifa", "מקום מגורים"),
])
def test_refusals(ctx, question, needle):
    r = run(ctx, "triage", question=question)
    assert r.kind == "markdown", r.data
    lines = r.data.split("\n")
    assert lines[0] == REFUSAL_HEADING and lines[-1] == LAB_LINE and CREDIT not in r.data
    assert needle in r.data and "\n" not in r.note and r.note.startswith("לא ניתן לענות")
    assert "Traceback" not in r.data
    json_safe(r)


def test_model_rule_wins_over_routing(ctx):
    r = run(ctx, "triage", question="דגם רכב לפי שנת ייצור")
    assert r.data.startswith(REFUSAL_HEADING) and "vehicle_cells_ranking" in r.data
    assert r.note.count("לא ניתן לענות") == 1 and "hotspot_map" not in r.data
    urban = run(ctx, "triage", question="סיכון לק״מ בצומת עירוני")
    assert urban.data.startswith(REFUSAL_HEADING) and "hotspot_map" in urban.data     # the P3 map is a real answerable now


@pytest.mark.parametrize("question,actions", [
    ("כמה הרוגים היו בכל שנה?", ["trend", "severity_profile"]),
    ("trend of accidents over time", ["trend"]),
    ("איזה מקטע בכביש 6 הכי מסוכן?", ["segment_rates"]),
    ("does rain matter?", ["weather_check"]),
    ("מה קרה לפני ואחרי השינוי בצומת?", ["before_after"]),
    ("which engine volume is safest?", ["vehicle_cells_ranking"]),
    ("מה השנה עם הכי הרבה הרוגים?", ["severity_profile"]),          # "השנה" = "the year" here, not "this year"
    ("make a chart of killed per year", ["trend", "severity_profile"]),  # the verb "make" is not a car make
    ("which model year is safest?", ["vehicle_cells_ranking"]),     # "model year" is what the cells answer
    ("מפת מוקדים של תאונות", ["hotspot_map"]),
    ("show the hotspot map", ["hotspot_map"]),
    ("איפה המוקדים בכביש 4?", ["segment_rates", "hotspot_map"]),
])
def test_routes(ctx, question, actions):
    r = run(ctx, "triage", question=question)
    assert r.kind == "markdown"
    lines = r.data.split("\n")
    assert lines[0] == ROUTE_HEADING and lines[-1] == LAB_LINE
    assert [l.split(": ", 1)[1] for l in lines if l.startswith("- פעולה מתאימה: ")] == actions
    assert r.note.startswith("ניתוב") and "\n" not in r.note


def test_unknown_question_routes_everywhere(ctx):
    r = run(ctx, "triage", question="שלום")
    assert r.data.startswith(ROUTE_HEADING) and "כל הפעולות" in r.data and "- פעולה מתאימה: about" in r.data


def test_classify_is_pure():
    assert classify("Toyota")[0] == "refuse"
    assert classify("per km in the city")[0] == "refuse"
    assert classify("weather")[0] == "route"
    assert classify("the make of the car")[0] == "refuse" and classify("make and model")[0] == "refuse"
    assert classify("כמה נהרגו השנה")[0] == "refuse" and classify("השנה הזאת")[0] == "refuse"
    assert classify("לאורך השנה")[0] == "route" and classify("what happens in 2027?")[0] == "refuse"
    # the map route's stems are anchored: early-morning, a site key and a ramp are not map questions
    from nl2sql_roadsafety.actions.triage import ALL_ACTIONS
    assert classify("כמה תאונות קרו מוקדם בבוקר?")[3] == ALL_ACTIONS            # no route → the all-actions card
    assert classify("תאונות בשעות המוקדמות של הלילה")[3] == ALL_ACTIONS
    assert classify("מה מפתח האתר של המקטע בכביש 60?")[3] == ["segment_rates"]
    assert classify("רמפה בכביש 1")[3] == ["segment_rates"]
    assert classify("מפת המוקדים")[3] == ["hotspot_map"]


# ── P5 sweep regressions ──

def test_english_model_with_explain_intent_routes_not_refuses():
    """'model' in English also names the STATISTICAL model — explain-intent wording must reach studio_explain."""
    from nl2sql_roadsafety.actions.triage import classify

    for q in ("explain the site model", "why does the model rank this site high?", "shap of the deployed model"):
        verdict = classify(q)
        assert verdict[0] == "route", (q, verdict)
        assert "studio_explain" in verdict[3], (q, verdict[3])
    # the beat-4 refusal is untouched: make/model questions without explain intent still refuse
    assert classify("איזה דגם רכב הכי בטוח?")[0] == "refuse"
    assert classify("which car model is safest")[0] == "refuse"


def test_hasbara_is_not_a_model_explanation():
    """'הסברה' (advocacy) contains 'הסבר' — the anchored stem must not route it to TreeSHAP."""
    from nl2sql_roadsafety.actions.triage import classify

    verdict = classify("פעילות הסברה בבתי ספר למניעת תאונות")
    assert "studio_explain" not in (verdict[3] if verdict[0] == "route" else []), verdict
    verdict2 = classify("הסבר את המודל")                                     # the real thing still routes
    assert verdict2[0] == "route" and "studio_explain" in verdict2[3]


# ── P12 ──

def test_severity_explain_phrasing_leads_with_severity_explain():
    """Severity-model explain wording routes to severity_explain FIRST; bare model-explain wording keeps
    leading with studio_explain (both stay listed — the card offers candidates, not a verdict)."""
    from nl2sql_roadsafety.actions.triage import classify

    for q in ("הסבר את מודל החומרה", "beeswarm של מודל החומרה", "shap of the severity model"):
        verdict = classify(q)
        assert verdict[0] == "route" and verdict[3][0] == "severity_explain", (q, verdict)
    v = classify("נחיל SHAP")
    assert v[0] == "route" and "severity_explain" in v[3]
    assert classify("הסבר את המודל")[3][0] == "studio_explain"               # unchanged for the site model
    assert classify("פעילות הסברה על הרוגים")[0] == "route"                  # הסברה still never explains
    assert "severity_explain" not in classify("פעילות הסברה על הרוגים")[3]
