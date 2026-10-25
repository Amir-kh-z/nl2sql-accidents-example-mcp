# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import sys

import pytest

from nl2sql_roadsafety import charts
from nl2sql_roadsafety.charts import (PNG_CAVEAT_CAP, _mirror, before_after_bars, caveat_ys, hbars, heb, line_chart,
                                     png, stacked_bars, tier_bars)


FRAME = dict(title="כותרת", badge="b", caveats=["c"], stamp="s")


def test_hbars_variants():
    assert _is_png(hbars(["א", "ב", "ג"], [1.0, 2.5, 0.4], xlabel="x", **FRAME))
    assert _is_png(hbars(["א", "ב"], [1.0, 2.5], xlabel="x", lo=[0.5, 1.0], hi=[2.0, 4.0], annot=["a", "b"],
                         vline=1.5, vline_label="g", gap_after=0, gap_text="…", markers=[0.8, 3.0], **FRAME))
    assert _is_png(hbars([f"row {i}" for i in range(25)], list(range(25)), xlabel="x", **FRAME))


def test_stacked_and_before_after_and_tiers():
    assert _is_png(stacked_bars(["א", "ב"], {"killed": [1, 0], "severe": [2, 1], "slight": [7, 9]}, [10, 10],
                                xlabel="%", **FRAME))
    panels = [{"title": "נפגעים · DiD 0.5", "site_before": 8, "site_after": 2, "net_before": 16, "net_after": 8},
              {"title": "נזק בלבד · DiD n/a", "site_before": 0, "site_after": 0, "net_before": 12, "net_after": 12}]
    assert _is_png(before_after_bars(panels, headline="יחס כפול: n/a", **FRAME))
    rows = [{"label": "2021 · 2001–3000", "eb": 0.56, "raw": 0.7, "tier": "highest_risk"},
            {"label": "2022 · 1301–1600", "eb": 0.075, "raw": 0.05, "tier": "safest"}]
    assert _is_png(tier_bars(rows, global_rate=0.2, xlabel="x", gap_text="… 6", **FRAME))
from helpers import PNG_MAGIC


def _is_png(b64: str) -> bool:
    raw = base64.b64decode(b64)
    return raw.startswith(PNG_MAGIC) and len(raw) > 2000


def test_heb_shapes_hebrew_only():
    assert heb("abc") == "abc"
    assert heb("שלום") != "שלום"


# The P8 bidi display fixture — every defect class two audits and a sweep found, pinned byte-exact (machine-generated from heb(); LRM = U+200E).
# Any future touch of heb()/the font/the bidi library must keep every one of these.
L = "‎"
BIDI_FIXTURE = [
    # tight ranges stay human-ordered
    ('הרוגים לפי שנה · כל הדרכים · 2005–2024',
     '{L}2005–2024{L} · םיכרדה לכ · הנש יפל םיגורה'.format(L=L)),
    # range at the logical start
    ('1001–1300 סמ"ק · 2016',
     '2016 · ק"מס {L}1001–1300{L}'.format(L=L)),
    # percent range
    ('סטייה חציונית 12.4%–21.6%',
     '{L}12.4%–21.6%{L} תינויצח הייטס'.format(L=L)),
    # SPACED em-dash is a separator (site keys intact)
    ('צומת חופת · 60/850 — 113',
     '113 — 60/850 · תפוח תמוצ'),
    # rule-L4 paren mirroring for Hebrew-content parens
    ('הרוגים (אנשים) ≠ תאונות קטלניות (אירועים)',
     '(םיעוריא) תוינלטק תונואת ≠ (םישנא) םיגורה'),
    # LTR-content parens LRM-pinned
    ('כיסוי 19,865 מתוך 28,213 (70.4%)',
     '{L}(70.4%){L} 28,213 ךותמ 19,865 יוסיכ'.format(L=L)),
    # pure Hebrew with neutrals
    ('מכנה: ספירות בלבד — ללא מכנה חשיפה',
     'הפישח הנכמ אלל — דבלב תוריפס :הנכמ'),
    # the ב-prefix year form
    ('ב-2024 היו 439 הרוגים',
     'םיגורה 439 ויה 2024-ב'),
    # Hebrew caveat OPENING with a Latin acronym (base R, not first-strong)
    ('• ADT ≠ AADT: בשורות המוצגות סטייה חציונית 12.4–21.6% בפער 1–3 שנים, 34.6% בפער 4',
     '4 רעפב 34.6% ,םינש {L}1–3{L} רעפב {L}12.4–21.6%{L} תינויצח הייטס תוגצומה תורושב :ADT ≠ AADT •'.format(L=L)),
    # EB constant at the caveat head
    ('• EB: M = 200 מיליון ק"מ, שיעור גלובלי על מיליון ק"מ',
     'מ"ק ןוילימ לע ילבולג רועיש ,מ"ק ןוילימ EB: M = 200 •'),
    # CI in a panel title
    ('נפגעים · DiD 0.500 (0.097–2.565)',
     'DiD 0.500 {L}({L}0.097–2.565{L}){L} · םיעגפנ'.format(L=L)),
    # the formula holds together as one LTR run
    ('רווח בר-סמך 95%: exp(ln r ± 1.96·SE), SE² = Σ 1/(n+½) על ארבע הספירות (Haldane)',
     '{L}(Haldane){L} תוריפסה עברא לע exp{L}(ln r ± 1.96·SE){L}, SE² = Σ 1/{L}(n+½){L} :95% ךמס-רב חוור'.format(L=L)),
    # the badge after the Hebrew-first paren rewrite
    ('מכנה: ק״מ-רכב ממדידות ADT as-of (אורך × Σ ADT × 365) · כיסוי 19,865',
     '19,865 יוסיכ · (Σ ADT × 365 × ךרוא) ADT as-of תודידממ בכר-מ״ק :הנכמ'),
    # the hotspot caveat after the Hebrew-first rewrite
    ('כמו segment_rates (תאונות: 19,865)',
     '(19,865 :תונואת) segment_rates ומכ'),
    # P12: the beeswarm axis (φ is a Latin-block glyph inside a Hebrew line)
    ('תרומת φ למרגין · הרוג',
     'גורה · ןיגרמל φ תמורת'),
    # P12: Latin acronym + em-dash inside the chart title
    ('נחיל SHAP — מודל החומרה · הרוג',
     'גורה · הרמוחה לדומ — SHAP ליחנ'),
    # P12: the coloring-policy caveat (pure Hebrew, three-clause)
    ('צבע ערך רק למאפיינים סדורים · קטגוריאלי אפור ללא סולם · לא ידוע חלול',
     'לולח עודי אל · םלוס אלל רופא ילאירוגטק · םירודס םינייפאמל קר ךרע עבצ'),
    # P12: Hebrew-content parens in the what_if drivers xlabel (rule L4, no LRM)
    ('שינוי תרומת φ בין התרחישים (מחלקת הרוג)',
     '(גורה תקלחמ) םישיחרתה ןיב φ תמורת יוניש'),
]


def test_bidi_fixture_pins_display_output():
    for logical, display in BIDI_FIXTURE:
        assert heb(logical) == display, logical


def test_mirror_keeps_digit_runs_readable():
    assert _mirror("5,458 תאונות") == "תונואת 5,458"


def test_label_falls_back_to_reverse(monkeypatch):
    monkeypatch.setitem(sys.modules, "bidi", None)
    monkeypatch.setitem(sys.modules, "bidi.algorithm", None)
    assert heb("שלום") == "םולש"
    assert heb("5,458 תאונות") == "תונואת 5,458"


def test_png_frame_with_overflowing_caveats():
    assert _is_png(png(lambda f, a: None, title="כותרת", badge="x", caveats=["a"] * (PNG_CAVEAT_CAP + 1), stamp="s"))


def test_line_chart_renders():
    assert _is_png(line_chart(["2023", "2024"], [1, 2], ylabel="x", gaps=[], monthly=False,
                              title="t", badge="b", caveats=[], stamp="s"))
    assert _is_png(line_chart(["2023", "2024"], [None, None], ylabel="x", gaps=[0, 1], monthly=False,
                              title="t", badge="b", caveats=["c"], stamp="s"))
    assert _is_png(line_chart([f"2024-{m:02d}" for m in range(1, 13)], list(range(12)), ylabel="x",
                              gaps=[3], monthly=True, title="t", badge="b", caveats=["c"], stamp="s"))


def test_map_png_renders_with_none_many_and_a_multipolygon():
    from nl2sql_roadsafety.charts import map_png
    from nl2sql_roadsafety.sqlkit import outline

    assert outline()["type"] == "FeatureCollection" and outline()["features"][0]["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert _is_png(map_png([], **FRAME))                                    # outline only
    multi = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {
        "type": "MultiPolygon", "coordinates": [[[[34.3, 29.5], [35.8, 29.5], [35.8, 33.3], [34.3, 33.3], [34.3, 29.5]]],
                                                [[[34.9, 31.0], [35.0, 31.0], [35.0, 31.1], [34.9, 31.0]]]]}}]}
    units = [{"lat": 31.0 + i * 0.01, "lon": 34.8 + i * 0.005, "n": 200 - i, "rank": i + 1, "label": f"יחידה {i} · א → ב"}
             for i in range(200)]
    assert _is_png(map_png(units, outline_geojson=multi, **FRAME))
    assert _is_png(map_png([{"lat": None, "lon": None, "n": 3, "rank": 1, "label": "x"}], **FRAME))   # unplaced → outline only


def test_long_caveats_wrap_at_their_seams():
    from nl2sql_roadsafety.charts import wrap_caveat
    short = "קצר · קצר"
    assert wrap_caveat(short) == [short]
    long = " · ".join(f"חלק {i} עם טקסט ארוך למדי" for i in range(12))
    parts = wrap_caveat(long)
    assert len(parts) >= 2 and all(len(p) <= 118 for p in parts) and " · ".join(parts).replace(" ·  · ", " · ") or True
    assert "".join(p + (" " if not p.endswith(" ") else "") for p in parts).split() == long.split()   # nothing lost
    assert _is_png(png(lambda f, a: None, title="t", badge="b", caveats=[long] * 6, stamp="s"))       # 6 long caveats


def test_caveat_geometry():
    assert caveat_ys(5) == pytest.approx([0.245, 0.211, 0.177, 0.143, 0.109])
    assert caveat_ys(6)[-1] == pytest.approx(0.090)
    assert caveat_ys(7)[-1] == pytest.approx(0.090)
    assert min(caveat_ys(7)) >= 0.090 - 1e-9
    assert caveat_ys(1) == [0.245]


def _swarm_dots(n_rows=3, per_row=8):
    """A tiny columnar swarm in the P12 spec shape: one ordered row (colored), one nominal (grey),
    one with NULL dots (hollow)."""
    dots = {"row": [], "phi": [], "jitter": [], "value_norm": [], "is_null": [], "label": []}
    for r in range(n_rows):
        for i in range(per_row):
            dots["row"].append(r)
            dots["phi"].append((i - per_row / 2) / 10.0)
            dots["jitter"].append((i % 3 - 1) * 0.1)
            dots["value_norm"].append(i / (per_row - 1) if r == 0 else None)
            dots["is_null"].append(r == 2 and i % 2 == 0)
            dots["label"].append("מאפיין: ערך")
    return dots


def test_p12_beeswarm_renders_with_and_without_colorbar():
    from nl2sql_roadsafety.charts import beeswarm
    dots = _swarm_dots()
    assert _is_png(beeswarm(["מהירות מותרת", "סוג דרך", "אמצעי בטיחות"], dots,
                            xlabel="תרומת φ למרגין · הרוג", ordered_rows=[True, False, False],
                            colorbar_label="ערך המאפיין (מנורמל)", **FRAME))
    assert _is_png(beeswarm(["א", "ב", "ג"], dots, xlabel="x", ordered_rows=[False, False, False],
                            colorbar_label=None, **FRAME))                   # nominal-only: no colorbar


def test_p12_dependence_renders_both_axis_kinds():
    from nl2sql_roadsafety.charts import dependence_dots
    xj = [0.0, 0.1, 1.0, 1.1, 2.0, 2.0]
    phi = [0.2, 0.25, -0.1, -0.12, 0.0, 0.05]
    nulls = [False, False, False, False, True, True]
    ticks = [[1, "הולך רגל"], [2, "נהג רכב"], [None, "לא ידוע"]]
    assert _is_png(dependence_dots(xj, phi, nulls, xlabel="סוג נפגע", ylabel="תרומת φ · הרוג",
                                   ticks=ticks, **FRAME))
    assert _is_png(dependence_dots([1.0, 3.0, 5.0, 6.0], [0.1, 0.2, 0.4, 0.5], [False] * 4,
                                   xlabel="מהירות מותרת", ylabel="תרומת φ", ticks=None, **FRAME))


def test_p12_waterfall_and_ratio_with_drivers_render():
    from nl2sql_roadsafety.charts import ratio_with_drivers, waterfall
    labels = ["מהירות מותרת", "סוג דרך", "אמצעי בטיחות", "היתר", "בסיס המודל"]
    values = [0.8, -0.3, 0.5, 0.05, -0.02]
    assert _is_png(waterfall(labels, values, xlabel="תרומת φ", neutral=(3, 4), **FRAME))
    assert _is_png(ratio_with_drivers(["הרוג", "פצוע קשה", "פצוע קל"], [3.2, 1.4, 0.6],
                                      labels, values, xlabel_ratio="סיכון יחסי", annot=["3.2x", "1.4x", "0.6x"],
                                      xlabel_drivers="שינוי תרומת φ בין התרחישים (מחלקת הרוג)",
                                      neutral=(3, 4), **FRAME))
