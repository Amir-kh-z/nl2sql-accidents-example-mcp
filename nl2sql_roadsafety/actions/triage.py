# -*- coding: utf-8 -*-
"""triage (refusal gate): no LLM — an ordered rule table over the question. What the data cannot answer gets a
refusal card with the honest reason and what IS answerable; everything else gets a routing card."""
from __future__ import annotations

import re

from nl2sql_engine.modules import Action, Input

from ..envelope import guard, route_card
from ..sqlkit import DATA_YEARS, Refusal

TITLE = "טריאז׳ · מה אפשר לשאול"

_MODEL = re.compile(r"דגם|יצרן|מותג|לוחית|מספר רישוי|טויוטה|מאזדה|יונדאי|קיה|סקודה|\bmodel\b(?!\s+year)"
                    r"|\bmakes?\s+(?:of|and model)\b|\bcar make\b|\bbrand\b|\bplate\b|corolla|mazda|toyota|hyundai", re.I)
# P5 sweep: English "model" also names the STATISTICAL model ("explain the site model") — explain-intent wording
# must reach the studio_explain route, not the make/model refusal
_MODEL_EXPLAIN = re.compile(r"explain|\bshap\b|\bwhy\b|prediction|\brank", re.I)
_PER_KM = re.compile(r'לק"מ|לק״מ|לקילומטר|per km|per kilomet|\bentry\b|לכניסה', re.I)
_URBAN = re.compile(r"עירוני|צומת|בעיר|ערים|urban|junction|intersection|\bcity\b|\bcities\b|\btown\b", re.I)
# "השנה" = "this year" only as a standalone time word (end of the question, after a past-tense verb, or with הזו/הזאת);
# "מה השנה עם…" / "לאורך השנה" are questions about years, not about the future.
_FUTURE = re.compile(r"(?:היו|קרו|נהרגו|נפצעו|עד עכשיו|עד היום)\s+השנה|השנה\s+(?:הזו|הזאת|הנוכחית)"
                     r"|(?<!לאורך )(?<!במהלך )(?<!כל )(?<!מה )(?<!איזו )(?<!איזה )השנה\s*[?!.]*\s*$"
                     r"|\bnext year\b|\bthis year\b", re.I)
_RESIDENCE = re.compile(r"מגורים|תושב|תושבי|גר ב|residence|lives in|living in", re.I)
_YEAR = re.compile(r"\b(20\d\d|19\d\d)\b")

ROUTES = [   # (name, pattern, action)
    ("מגמות לאורך זמן", re.compile(r"מגמה|מגמות|לאורך זמן|לפי שנה|כל שנה|trend|over time|per year", re.I), "trend"),
    ("המלכודת של התאונות הקלות", re.compile(r"קלות|קלה|נאיבי|naive|light accidents|slight", re.I), "naive_vs_correct"),
    ("שיעורים למקטע", re.compile(r'מקטע|כביש|ק"מ|ק״מ|segment|road \d|per km|rate', re.I), "segment_rates"),
    # P10: the interactive map — listed before the hotspot route so a "מפה חיה" question leads with it
    ("מפה חיה", re.compile(r"מפה חיה|אינטראקטיבי|ענן נקודות|interactive|point cloud|live map", re.I), "map_scene"),
    # anchored stems: רמפה (ramp), מפתח (key) and מוקדם/מוקדמות (early) are not map questions
    ("מפת מוקדים", re.compile(r"(?<!ר)מפה|מפת(?!ח)|מוקד(?![םמ])|hotspot|\bmap\b", re.I), "hotspot_map"),
    ("דירוג לפי עודף", re.compile(r"עודף|excess|\branking\b|דירוג אתרים", re.I), "site_ranking"),
    # P10: the click panel — one site's full honest profile
    ("פרופיל אתר", re.compile(r"פרופיל אתר|כרטיס אתר|על הצומת|על המקטע|site profile", re.I), "site_profile"),
    # P12: severity-model explain phrasing leads with severity_explain (the P5 הסברה anchoring kept); the
    # generic explain route below still lists studio_explain, so a bare "הסבר את המודל" offers both
    ("הסבר מודל החומרה", re.compile(r"נחיל|beeswarm|(?:הסבר(?![הות])|להסביר|explain|\bshap\b)[^.?!]*(?:חומרה|הרוג|נפגע|severity)"
                                     r"|(?:חומרה|severity)[^.?!]*(?:הסבר(?![הות])|להסביר|explain|\bshap\b)",
                                     re.I), "severity_explain"),
    # הסבר anchored against הסברה/הסברת (road-safety ADVOCACY, not model explanation) — the P5 sweep's catch
    ("תחזית והסבר המודל", re.compile(r"הסבר(?![הות])|להסביר|תחזית|תרומת|תרומה של|explain|\bshap\b|\bwhy\b|\bpredict",
                                      re.I), "studio_explain"),
    ("סטודיו ומודל האתר", re.compile(r"סטודיו|studio|לאמן|אימון מודל|מודל האתר|\bdeploy\b", re.I), "studio_models"),
    # אופנוע before the generic רכב route; אופן alone (manner) must not match — the stems are anchored
    ("דו-גלגלי", re.compile(r"אופנוע|דו[- ]גלגלי|אופניים|קורקינט|קטנוע|motorcycle|scooter|bicycle|\bbike\b|e-bike",
                            re.I), "two_wheelers"),
    ("פרופיל חומרה", re.compile(r"חומרה|הרוג|הרוגים|פצוע|גיל|הולך רגל|הולכי רגל|severity|killed|injured|age|pedestrian", re.I),
     "severity_profile"),
    ("מה אם ותרחישים", re.compile(r"מה אם|מה היה קורה|תרחיש|what.if|scenario", re.I), "what_if"),
    ("פרופיל סיכון לחומרה", re.compile(r"פרופיל סיכון|סיכוי להיהרג|סיכון לחומרה|risk profile", re.I),
     "severity_predict"),
    ("מזג אוויר", re.compile(r"גשם|מזג|weather|rain", re.I), "weather_check"),
    ("לפני ואחרי", re.compile(r"לפני|אחרי|שינוי|before|after|change", re.I), "before_after"),
    ("תאי רכב", re.compile(r"רכב|שנת ייצור|נפח|vehicle|engine|car\b|model year", re.I), "vehicle_cells_ranking"),
]
ALL_ACTIONS = ["trend", "naive_vs_correct", "segment_rates", "hotspot_map", "map_scene", "site_ranking",
               "severity_profile", "vehicle_cells_ranking", "two_wheelers", "before_after", "weather_check",
               "studio_models", "about"]


def classify(question: str):
    """Returns ("refuse", Refusal) or ("route", head, body, actions)."""
    q = str(question or "").strip()
    low = q.lower()
    if _MODEL.search(low) and not _MODEL_EXPLAIN.search(low):
        return ("refuse", Refusal(
            "דגם, יצרן או מספר רישוי אינם ניתנים למענה",
            ["בטיחות לפי שנת ייצור × נפח מנוע עם חשיפה אמיתית: vehicle_cells_ranking"],
            what_to_do="הריצו vehicle_cells_ranking (metric = ksi)",
            detail="קבצי התאונות אינם נושאים דגם, לוחית או VIN ואין מפתח לרישום הרכבים — fleet_by_model / "
                   "vehicle_mileage carry make and model; accidents / involved / vehicles carry no plate, VIN or model "
                   "code - the finest linkable cell is manufacture_year x cc_band"))
    if _PER_KM.search(low) and _URBAN.search(low):
        return ("refuse", Refusal(
            "אין מכנה חשיפה לדרכים עירוניות ולצמתים",
            ["segment_rates (לא-עירוני)", "before_after לצומת עם בקרה",
             "דירוג לפי ספירות במפה: hotspot_map (unit = njunctions / ujunctions) — ספירות, לא סיכון"],
            detail="שיעור לק״מ קיים רק למקטעים לא-עירוניים 2017+ (נפחי תנועה as-of); "
                   "בערים ובצמתים אין נפח תנועה — דירוג יחסי בלבד"))
    years = [int(y) for y in _YEAR.findall(low)]
    if any(y > DATA_YEARS[1] for y in years) or _FUTURE.search(low):
        return ("refuse", Refusal(f"אין נתונים אחרי 31.12.{DATA_YEARS[1]}",
                                  [f"כל שנה בין {DATA_YEARS[0]} ל-{DATA_YEARS[1]}: trend"]))
    if _RESIDENCE.search(low):
        return ("refuse", Refusal("מקום מגורים ≠ מקום התאונה — עמודות residence_* מתארות את הנפגע, לא את המיקום",
                                  ["severity_profile לפי חתכי נפגעים", "segment_rates לפי מיקום"]))
    hits = [(name, action) for name, pat, action in ROUTES if pat.search(low)]
    if hits:
        actions = []
        for _, a in hits:
            if a not in actions:
                actions.append(a)
        return ("route", f"זוהו {len(actions)} פעולות מתאימות", [f"- {name}" for name, _ in hits], actions)
    return ("route", "לא זוהתה שאלה מוכרת — כל הפעולות", ["- נסו לנסח עם מילות מפתח: מגמה, מקטע, חומרה, גשם, לפני/אחרי, רכב"],
            ALL_ACTIONS)


@guard(TITLE)
def run(ctx, question="איזה דגם רכב הכי בטוח?"):
    verdict = classify(question)
    if verdict[0] == "refuse":
        raise verdict[1]
    _, head, body, actions = verdict
    return route_card(TITLE, head, body, actions)


ACTION = Action(
    name="triage", label="טריאז׳ · triage",
    help="Rule-based gate (no LLM): says what the data cannot answer - make/model safety, per-km risk in cities "
         "or at junctions, dates after 2024-12-31, residence as location - with the honest reason and what IS "
         "answerable; otherwise routes the question to the fitting actions.",
    inputs={"question": Input(kind="text", label="שאלה", default="איזה דגם רכב הכי בטוח?",
                              help="a question in Hebrew or English")},
    run=run)
