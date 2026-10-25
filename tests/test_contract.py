# -*- coding: utf-8 -*-
"""The module contract and the Layer-0 discipline, as any frontend would see them."""
from __future__ import annotations

import io
import re
import tokenize
import tomllib
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import entry_points, version as meta_version
from pathlib import Path

import pytest

import nl2sql_roadsafety
from nl2sql_roadsafety import MODULE, __version__
from nl2sql_roadsafety.envelope import (CREDIT, CREDIT_SHORT, DENOM_KINDS, LAB_LINE, REFUSAL_HEADING, ROUTE_HEADING)
from nl2sql_roadsafety.sqlkit import MEASURES
from helpers import json_safe, needs_install, png_of, run, lines_of

LEGAL_KINDS = ("text", "number", "bool", "choice", "table", "column")
NAMES = {"trend", "naive_vs_correct", "about", "segment_rates", "hotspot_map", "map_scene", "site_profile",
         "site_ranking", "severity_profile", "vehicle_cells_ranking", "two_wheelers", "before_after", "ab_scan",
         "weather_check", "heat_matrix", "zone_ranking", "city_ranking",
         "studio_train_site", "studio_validate", "studio_deploy", "studio_explain",
         "studio_models", "ledger_list", "finding_card", "triage", "severity_predict", "what_if",
         "studio_train_severity", "studio_validate_severity", "severity_explain"}    # P15: 30 actions
LABELS = {"trend": "מגמות · trend", "naive_vs_correct": "המלכודת · naive_vs_correct", "about": "אודות · about",
          "segment_rates": "מקטעים · segment_rates", "hotspot_map": "מפת מוקדים · hotspot_map",
          "map_scene": "מפה חיה · map_scene", "site_profile": "פרופיל אתר · site_profile",
          "site_ranking": "דירוג אתרים לפי עודף · site_ranking",
          "severity_profile": "חומרה · severity_profile",
          "vehicle_cells_ranking": "תאי רכב · vehicle_cells_ranking", "before_after": "לפני ואחרי · before_after",
          "ab_scan": "סריקת שינויים · ab_scan",
          "weather_check": "מזג אוויר · weather_check", "heat_matrix": "מטריצת יום ושעה · heat_matrix",
          "zone_ranking": "דירוג אזורי תנועה · zone_ranking", "city_ranking": "דירוג יישובים · city_ranking",
          "studio_train_site": "אימון מודל אתר · studio_train_site", "studio_validate": "אימות מודל · studio_validate",
          "studio_deploy": "פריסת מודל · studio_deploy", "studio_models": "רישום מודלים · studio_models",
          "ledger_list": "פנקס ממצאים · ledger_list", "finding_card": "כרטיס ממצא · finding_card",
          "studio_explain": "תחזית והסבר לאתר · studio_explain", "two_wheelers": "דו-גלגלי · two_wheelers",
          "triage": "טריאז׳ · triage", "severity_predict": "פרופיל סיכון לחומרה · severity_predict",
          "what_if": "מה אם · what_if", "studio_train_severity": "אימון מודל חומרה · studio_train_severity",
          "studio_validate_severity": "אימות מודל חומרה · studio_validate_severity",
          "severity_explain": "הסבר מודל החומרה · severity_explain"}
CHART_ACTIONS = ("trend", "segment_rates", "hotspot_map", "map_scene", "site_profile", "site_ranking",
                 "severity_profile", "vehicle_cells_ranking", "two_wheelers", "before_after", "ab_scan",
                 "weather_check", "heat_matrix", "zone_ranking", "city_ranking",
                 "studio_explain", "severity_predict", "what_if", "severity_explain")
# P9: the model-face actions carry FOUR views — chart, the markdown card, table, sql
FOUR_VIEW = {"studio_explain", "severity_predict", "what_if", "site_profile", "severity_explain"}


def _action(name):
    return next(a for a in MODULE.actions if a.name == name)


def test_declarations_are_legal_for_any_frontend():
    assert MODULE.name == "roadsafety"
    assert MODULE.label.startswith("🚦")
    assert MODULE.requires_core == ">=1.0,<2.0"
    assert {a.name for a in MODULE.actions} == NAMES
    for name, label in LABELS.items():
        assert _action(name).label == label
    for action in MODULE.actions:
        assert action.help and action.help.isascii(), action.name
        for name, decl in action.inputs.items():
            assert decl.kind in LEGAL_KINDS, (action.name, name)
            assert decl.default is not None, (action.name, name)
            assert not re.search(r"\d", decl.label), (action.name, name, decl.label)
            if decl.kind == "choice":
                assert decl.default in decl.choices, (action.name, name)
            if decl.kind == "number":
                assert isinstance(decl.default, int) and not isinstance(decl.default, bool)


def test_views_and_choices_per_action():
    trend = _action("trend")
    assert trend.inputs["view"].choices == ["chart", "table", "sql"]
    assert list(trend.inputs["measure"].choices) == list(MEASURES) == ["accidents", "killed", "severe_injured",
                                                                        "slight_injured", "fatal_accidents"]
    trap = _action("naive_vs_correct")
    assert trap.inputs["view"].choices == ["markdown", "sql"]
    assert "chart" not in trap.inputs["view"].help and "table" not in trap.inputs["view"].help
    assert _action("about").inputs == {}
    for name in CHART_ACTIONS[1:]:
        if name in FOUR_VIEW:
            assert _action(name).inputs["view"].choices == ["chart", "markdown", "table", "sql"], name
            continue
        assert _action(name).inputs["view"].choices == ["chart", "table", "sql"], name
    assert "view" not in _action("triage").inputs and list(_action("triage").inputs) == ["question"]
    assert _action("weather_check").inputs["rain_threshold_mm"].kind == "choice"
    assert _action("studio_train_site").inputs["view"].choices == ["markdown", "table"]
    assert _action("studio_validate").inputs["view"].choices == ["markdown", "chart", "table"]
    assert _action("studio_train_severity").inputs["view"].choices == ["markdown", "table"]
    assert _action("studio_validate_severity").inputs["view"].choices == ["markdown", "chart", "table"]
    assert _action("studio_deploy").inputs["family"].choices == ["site", "severity"]
    assert _action("what_if").inputs["switch"].kind == "choice"
    for name in ("studio_deploy", "studio_models", "ledger_list", "finding_card"):
        assert "view" not in _action(name).inputs, name                      # single-faced by design


def test_version_pinned():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as fh:
        assert tomllib.load(fh)["project"]["version"] == __version__ == "0.14.3"


@needs_install
def test_installed_version_matches():
    assert meta_version("nl2sql-roadsafety-lab") == __version__


@needs_install
def test_install_lives_in_site_packages_exactly_once():
    """The repo-root egg-info satisfies `meta_version` through pytest's pythonpath even when the venv holds NO
    install (2026-10-16: a reinstall under Claude Desktop's running server failed halfway and left only a
    `~`-renamed dist-info corpse, which importlib still enumerates — the page was advertised twice)."""
    import sysconfig
    purelib = Path(sysconfig.get_paths()["purelib"])
    infos = sorted(p.name for p in purelib.iterdir() if p.is_dir() and p.name.endswith(".dist-info")
                   and "roadsafety" in p.name.lower())
    assert infos == [f"nl2sql_roadsafety_lab-{__version__}.dist-info"], infos
    assert not [p.name for p in purelib.iterdir() if p.name.startswith("~")], "pip left a failed-uninstall corpse"
    from importlib.metadata import entry_points
    pages = [ep for ep in entry_points(group="nl2sql.pages") if ep.name == "roadsafety"]
    assert len(pages) == 1, [(ep.dist.name, ep.dist.version) for ep in pages]


@needs_install
def test_entry_point_resolves():
    eps = [ep for ep in entry_points(group="nl2sql.modules") if ep.name == "roadsafety"]
    assert eps and eps[0].load() is MODULE


@needs_install
def test_discovery_offers_accidents_without_problems():
    from nl2sql_engine.modules import discover
    reg = discover()
    assert not [p for p in reg.problems if p.name == "roadsafety"], reg.problems
    found = next((m for m in reg.modules if m.name == "roadsafety"), None)
    assert found is MODULE


Y = {"from_year": 2022, "to_year": 2024}
VIEW_RUNS = [
    ("trend", {"view": "chart", **Y}, "chart"), ("trend", {"view": "table", **Y}, "table"), ("trend", {"view": "sql", **Y}, "sql"),
    ("naive_vs_correct", {"view": "markdown"}, "markdown"), ("naive_vs_correct", {"view": "sql"}, "sql"),
    ("about", {}, "markdown"),
    ("segment_rates", {"view": "chart", "from_year": 2019, "to_year": 2021}, "chart"),
    ("segment_rates", {"view": "table", "from_year": 2019, "to_year": 2021}, "table"),
    ("segment_rates", {"view": "sql", "from_year": 2019, "to_year": 2021}, "sql"),
    ("hotspot_map", {"view": "chart", "from_year": 2019, "to_year": 2021}, "chart"),
    ("hotspot_map", {"view": "table", "from_year": 2019, "to_year": 2021}, "table"),
    ("hotspot_map", {"view": "sql", "from_year": 2019, "to_year": 2021}, "sql"),
    ("map_scene", {"view": "chart", "from_year": 2019, "to_year": 2021}, "chart"),
    ("map_scene", {"view": "table", "from_year": 2019, "to_year": 2021}, "table"),
    ("map_scene", {"view": "sql", "from_year": 2019, "to_year": 2021}, "sql"),
    # site_profile: {} = the default site "60/836", unknown on the fixture → a refusal card, not an error
    ("site_profile", {}, "markdown"),
    ("site_profile", {"view": "chart", "site": "road:1/0-10"}, "chart"),
    ("site_profile", {"view": "markdown", "site": "road:1/0-10"}, "markdown"),
    ("site_profile", {"view": "table", "site": "road:1/0-10"}, "table"),
    ("site_profile", {"view": "sql", "site": "road:1/0-10"}, "sql"),
    ("severity_profile", {"view": "chart"}, "chart"), ("severity_profile", {"view": "table"}, "table"),
    ("severity_profile", {"view": "sql"}, "sql"),
    ("vehicle_cells_ranking", {"view": "chart"}, "chart"), ("vehicle_cells_ranking", {"view": "table"}, "table"),
    ("vehicle_cells_ranking", {"view": "sql"}, "sql"),
    ("before_after", {"view": "chart", "site": "road:1/0-10", "change_year": 2015, "min_cell": 2}, "chart"),
    ("before_after", {"view": "table", "site": "road:1/0-10", "change_year": 2015, "min_cell": 2}, "table"),
    ("before_after", {"view": "sql", "site": "road:1/0-10", "change_year": 2015, "min_cell": 2}, "sql"),
    # P15: the discoverer answers on the fixture only with min_cell 1 (default 6 is honest thinness there)
    ("ab_scan", {"view": "chart", "from_year": 2012, "to_year": 2021, "min_cell": 1}, "chart"),
    ("ab_scan", {"view": "table", "from_year": 2012, "to_year": 2021, "min_cell": 1}, "table"),
    ("ab_scan", {"view": "sql", "from_year": 2012, "to_year": 2021, "min_cell": 1}, "sql"),
    ("weather_check", {"view": "chart", "from_year": 2012, "to_year": 2021}, "chart"),
    ("weather_check", {"view": "table", "from_year": 2012, "to_year": 2021}, "table"),
    ("weather_check", {"view": "sql", "from_year": 2012, "to_year": 2021}, "sql"),
    # P13: the zero-filled grid answers on ANY legal range (168 rows even where the fixture is empty)
    ("heat_matrix", {"view": "chart"}, "chart"), ("heat_matrix", {"view": "table"}, "table"),
    ("heat_matrix", {"view": "sql"}, "sql"),
    # P14: the cumulative geographic snapshot (no year inputs by design)
    ("zone_ranking", {"view": "chart"}, "chart"), ("zone_ranking", {"view": "table"}, "table"),
    ("zone_ranking", {"view": "sql"}, "sql"),
    ("city_ranking", {"view": "chart"}, "chart"), ("city_ranking", {"view": "table"}, "table"),
    ("city_ranking", {"view": "sql"}, "sql"),
    ("triage", {}, "markdown"), ("triage", {"question": "מגמת הרוגים"}, "markdown"),
    # P4: on the plain fixture the studio/site/ledger actions answer with refusal cards (empty registry/ledger,
    # no deployment) — except training, which runs for real (xgboost is a [dev,ml] test dependency)
    ("site_ranking", {}, "markdown"), ("studio_validate", {}, "markdown"), ("studio_deploy", {}, "markdown"),
    ("studio_models", {}, "markdown"), ("ledger_list", {}, "markdown"), ("finding_card", {}, "markdown"),
    ("studio_train_site", {"view": "markdown"}, "markdown"), ("studio_train_site", {"view": "table"}, "table"),
    # P5: studio_explain refuses on the plain fixture (no deployment); two_wheelers runs on the planted fleet
    ("studio_explain", {}, "markdown"),
    # P9: the severity family refuses on the plain fixture (empty registry / no deployment) — except training,
    # which runs for real; train_until 2018 because the default 2022 has no inner-fold rows here
    ("severity_predict", {}, "markdown"), ("what_if", {}, "markdown"), ("studio_validate_severity", {}, "markdown"),
    # P12: severity_explain refuses on the plain fixture the same way (empty registry, no deployment)
    ("severity_explain", {}, "markdown"),
    ("studio_train_severity", {"train_until": 2018, "view": "markdown"}, "markdown"),
    ("studio_train_severity", {"train_until": 2018, "view": "table"}, "table"),
    ("two_wheelers", {"view": "chart", "from_year": 2019, "to_year": 2021}, "chart"),
    ("two_wheelers", {"view": "table", "from_year": 2019, "to_year": 2021}, "table"),
    ("two_wheelers", {"view": "sql", "from_year": 2019, "to_year": 2021}, "sql"),
]


@pytest.mark.parametrize("action,inputs,kind", VIEW_RUNS)
def test_every_declared_view_returns_its_kind(ctx, action, inputs, kind):
    r = run(ctx, action, **inputs)
    assert r.kind == kind, r.data
    json_safe(r)
    assert "\n" not in r.note
    assert r.note.startswith(("מכנה:", "לא ניתן לענות", "ניתוב"))
    assert r.note.endswith(CREDIT_SHORT) or r.note.endswith("מעבדת הבטיחות בדרכים")
    assert not re.search(r"[0-9]", r.title), r.title


CHART_RUNS = [("trend", {"measure": m, **Y}) for m in MEASURES] + [
    ("segment_rates", {"from_year": 2019, "to_year": 2021}), ("hotspot_map", {}), ("hotspot_map", {"unit": "njunctions"}),
    ("map_scene", {"from_year": 2019, "to_year": 2021}),
    ("site_profile", {"site": "road:1/0-10"}),
    ("severity_profile", {}), ("vehicle_cells_ranking", {}), ("vehicle_cells_ranking", {"group": "cohort"}),
    ("before_after", {"site": "road:1/0-10", "change_year": 2015, "min_cell": 2}),
    ("ab_scan", {"from_year": 2012, "to_year": 2021, "min_cell": 1}),
    ("weather_check", {"from_year": 2012, "to_year": 2021}), ("heat_matrix", {}),
    ("zone_ranking", {}), ("zone_ranking", {"measure": "density"}), ("city_ranking", {}),
    ("two_wheelers", {"from_year": 2019, "to_year": 2021})]


@pytest.mark.parametrize("action,inputs", CHART_RUNS)
def test_chart_spec_carries_the_full_answer(ctx, action, inputs):
    r = run(ctx, action, view="chart", **inputs)
    assert r.kind == "chart", r.data
    spec = r.data
    assert {"type", "renderer", "png_base64", "basis", "rows", "columns", "sql", "denominator",
            "caveats", "credit", "plugin_version", "stamp"} <= set(spec)
    png_of(spec)
    assert spec["denominator"]["kind"] in DENOM_KINDS
    assert spec["credit"] == CREDIT
    assert spec["plugin_version"] == __version__
    assert spec["basis"].isascii() and spec["stamp"].isascii()
    assert all(";" not in c for c in spec["caveats"])
    json_safe(r)


def test_answer_markdowns_follow_the_layer0_discipline(ctx):
    for action, inputs in (("naive_vs_correct", {}), ("about", {})):
        r = run(ctx, action, **inputs)
        lines = lines_of(r)
        assert lines[0].startswith("מכנה:"), lines[0]
        assert lines[-1] == CREDIT
        _assert_layer0(lines)


def test_refusal_markdowns_follow_the_layer0_discipline(ctx, other_ctx):
    cases = [(other_ctx, a, {}) for a in NAMES] + [
        (ctx, "trend", {"to_year": 2030}), (ctx, "naive_vs_correct", {"year": 2030}),
        (ctx, "segment_rates", {"from_year": 2010}), (ctx, "before_after", {"change_year": 2023}), (ctx, "triage", {})]
    for c, action, inputs in cases:
        r = run(c, action, **inputs)
        assert r.kind == "markdown", (action, r.data)
        lines = lines_of(r)
        assert lines[0] == REFUSAL_HEADING, (action, lines[0])
        assert lines[-1] == LAB_LINE
        assert CREDIT not in r.data
        assert "\n" not in r.note
        _assert_layer0(lines)


def test_route_markdown_follows_the_layer0_discipline(ctx):
    r = run(ctx, "triage", question="מגמת הרוגים")
    lines = lines_of(r)
    assert lines[0] == ROUTE_HEADING and lines[-1] == LAB_LINE and CREDIT not in r.data
    _assert_layer0(lines)


def _assert_layer0(lines):
    for line in lines:
        assert not line.startswith("##"), line
        assert "|" not in line, line
        assert "```" not in line, line
        assert "](" not in line, line


def test_no_result_outside_envelope():
    """Only envelope.py may construct a Result — `Result(...)` or `Result.<factory>(...)`.
    Scanned as Python tokens, so docstrings and comments are exempt; `-> Result` annotations and
    `import Result` are not constructions and are allowed anywhere."""
    pkg = Path(nl2sql_roadsafety.__file__).parent
    offenders = {}
    for py in sorted(pkg.rglob("*.py")):
        toks = [t for t in tokenize.generate_tokens(io.StringIO(py.read_text(encoding="utf-8")).readline)
                if t.type in (tokenize.NAME, tokenize.OP)]
        hits = [a.start[0] for a, b in zip(toks, toks[1:])
                if a.type == tokenize.NAME and a.string == "Result"
                and b.type == tokenize.OP and b.string in ("(", ".")]
        if hits:
            offenders[py.relative_to(pkg).as_posix()] = hits
    assert set(offenders) == {"envelope.py"}, offenders


def test_png_is_thread_safe(ctx):
    def one(job):
        action, inputs = job
        r = run(ctx, action, view="chart", **inputs)
        assert r.kind == "chart", r.data
        return png_of(r.data)

    with ThreadPoolExecutor(4) as pool:
        pngs = list(pool.map(one, CHART_RUNS))
    assert len(pngs) == len(CHART_RUNS)
