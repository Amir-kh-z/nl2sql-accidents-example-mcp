# -*- coding: utf-8 -*-
"""M1 — the MCP channel below the SDK: runner, renderer and the twelve tools on the fixture DBs.
Nothing here needs the `mcp` package."""
from __future__ import annotations

import asyncio
import json

import pytest
from nl2sql_engine.modules import Result

from nl2sql_roadsafety import MODULE
from nl2sql_roadsafety.envelope import CREDIT
from nl2sql_roadsafety.mcp import render
from nl2sql_roadsafety.mcp.runner import ENV_DB, Runner
from nl2sql_roadsafety.mcp.tools import (EXCLUDED_ACTIONS, TOOL_ACTIONS, build_tools, catalog_text,
                                         mapped_actions, view_for)


def tools_for(ctx, **kw) -> dict:
    return {t.name: t for t in build_tools(Runner(ctx.db_path), **kw)}


def audit_lines(runner: Runner) -> list[dict]:
    p = runner.audit_path()
    return [json.loads(l) for l in p.read_text("utf-8").splitlines() if l.strip()] if p.exists() else []


# ── the map ────────────────────────────────────────────────────────────────────────────────────────────
def test_every_action_is_mapped_or_excluded_on_purpose():
    declared = {a.name for a in MODULE.actions}
    assert mapped_actions() | EXCLUDED_ACTIONS == declared, (declared - mapped_actions() - EXCLUDED_ACTIONS)
    assert not (mapped_actions() & EXCLUDED_ACTIONS)
    for actions in TOOL_ACTIONS.values():
        for a in actions:
            assert MODULE.action(a) is not None, a


def test_thirteen_tools_with_clean_signatures(ctx):
    tools = tools_for(ctx)
    assert list(tools) == list(TOOL_ACTIONS) and len(tools) == 13
    import inspect
    for t in tools.values():
        sig = inspect.signature(t.fn)
        assert "steps" not in sig.parameters, t.name
        for p in sig.parameters.values():
            assert p.default is not inspect.Parameter.empty or (t.name, p.name) in (
                ("roadsafety_triage", "question"), ("roadsafety_find", "name")), (t.name, p.name)
        assert t.fn.__name__ == t.name and len(t.description) > 80
    assert "ctx" in inspect.signature(tools["roadsafety_studio"].fn).parameters     # the SDK injects it
    assert inspect.iscoroutinefunction(tools["roadsafety_studio"].fn)
    assert not tools["roadsafety_studio"].read_only
    assert all(t.read_only for n, t in tools.items() if n != "roadsafety_studio")


def test_catalog_names_every_tool_and_action():
    text = catalog_text()
    for tool, actions in TOOL_ACTIONS.items():
        assert tool in text
        for a in actions:
            assert f"- {a} (" in text
    assert "map_scene" in text


# ── faces ──────────────────────────────────────────────────────────────────────────────────────────────
def test_face_translates_to_each_actions_own_view():
    assert view_for("trend", "auto") == "chart" and view_for("trend", "table") == "table"
    assert view_for("trend", "card") == "chart"                    # no markdown face → the declared default
    assert view_for("site_profile", "card") == "markdown"
    assert view_for("studio_train_site", "auto") == "markdown"     # no chart face → default
    assert view_for("naive_vs_correct", "sql") == "sql"
    assert view_for("about", "table") is None                      # single-faced: no view input at all


# ── the renderer ───────────────────────────────────────────────────────────────────────────────────────
def test_render_every_result_kind():
    err = render.to_result(Result.error("boom"))
    assert err.is_error and err.texts().startswith("שגיאה: boom")
    md = render.to_result(Result("markdown", "מכנה: x\nline\n" + CREDIT, "כותרת", "note"))
    assert not md.is_error and md.texts().startswith("# כותרת\nמכנה: x")
    tbl = render.to_result(Result.table([(1, 2.5, None), (3, 4.0, "a|b")], ["a", "b", "c"], "T", "N"))
    assert "| a | b | c |" in tbl.texts() and "| 1 | 2.5 |  |" in tbl.texts() and "a\\|b" in tbl.texts()
    assert tbl.texts().endswith("N")
    sq = render.to_result(Result.sql("SELECT 1", "S"))
    assert "```sql\nSELECT 1\n```" in sq.texts()


def test_render_chart_spec_carries_the_full_answer_and_the_image():
    spec = {"basis": "trend | killed", "rows": [(2024, 439)], "columns": ["year", "killed"], "sql": "SELECT 439",
            "denominator": {"kind": "counts", "label": "ספירות בלבד"}, "caveats": ["c1", "c2"], "credit": CREDIT,
            "png_base64": "QUJD", "model_id": "m-1"}
    out = render.to_result(Result("chart", spec, "מגמות", "n"))
    text = out.texts()
    for needle in ("# מגמות", "בסיס: trend | killed", "מכנה: ספירות בלבד [ספירות בלבד]", "מודל: m-1", "- c1", "- c2",
                   "| year | killed |", "| 2,024 | 439 |", CREDIT):
        assert needle in text, needle
    assert "```sql" not in text
    assert [b["type"] for b in out.blocks] == ["text", "image"] and out.blocks[1]["data"] == "QUJD"
    assert "```sql\nSELECT 439" in render.to_result(Result("chart", spec, "t"), with_sql=True).texts()
    assert [b["type"] for b in render.to_result(Result("chart", spec, "t"), image=False).blocks] == ["text"]


def test_render_legend_names_helper_columns_and_hides_internal_flags():
    text = render.table_text(["year", "killed", "people", "casualty_accidents", "covered"], [(2024, 439, 20981, 8315, True)])
    assert "| year | killed | people | casualty_accidents |" in text and "covered" not in text
    assert "מקרא:" in text and "people = כל המעורבים" in text and "killed = הרוגים" in text
    assert "| 2,024 | 439 | 20,981 | 8,315 |" in text
    assert "מקרא" not in render.table_text(["foo", "bar"], [(1, 2)])          # nothing to explain → no legend
    assert render.legend(["mu", "excess", "x"]).count("·") == 1


def test_render_row_cap_is_stated():
    text = render.table_text(["x"], [(i,) for i in range(200)])
    assert text.count("\n| ") == render.MAX_ROWS and "מוצגות 60 מתוך 200 שורות" in text
    assert "(אין שורות)" in render.table_text(["x"], [])


# ── the tools on the fixture ───────────────────────────────────────────────────────────────────────────
Y = {"from_year": 2022, "to_year": 2024}
RUNS = [
    ("roadsafety_orient", {}), ("roadsafety_orient", {"section": "models", "family": "severity"}),
    ("roadsafety_orient", {"section": "trap", "year": 2024}), ("roadsafety_orient", {"section": "catalog"}),
    ("roadsafety_trend", {**Y}), ("roadsafety_trend", {"measure": "accidents", "granularity": "month", **Y}),
    ("roadsafety_trend", {"face": "table", **Y}), ("roadsafety_trend", {"face": "sql", **Y}),
    ("roadsafety_breakdown", {**Y}), ("roadsafety_breakdown", {"by": "year", "display": "counts", **Y}),
    ("roadsafety_breakdown", {"by": "day_hour", **Y}), ("roadsafety_breakdown", {"by": "weather_vs_measured", "from_year": 2012, "to_year": 2016}),
    ("roadsafety_sites", {"rank_by": "rate", "from_year": 2019, "to_year": 2021}),
    ("roadsafety_sites", {"rank_by": "observed", "from_year": 2012, "to_year": 2021}),
    ("roadsafety_sites", {"rank_by": "zones"}), ("roadsafety_sites", {"rank_by": "cities", "measure": "total"}),
    ("roadsafety_site", {"site": "njunction:433", "from_year": 2012, "to_year": 2018}),
    ("roadsafety_change_effect", {"site": "njunction:433", "change_year": 2015, "window_years": 2}),
    ("roadsafety_change_effect", {"mode": "discover", "from_year": 2012, "to_year": 2021}),
    ("roadsafety_vehicles", {}), ("roadsafety_vehicles", {"kind": "cohort", "metric": "ksi"}),
    ("roadsafety_vehicles", {"kind": "two_wheelers", "from_year": 2019, "to_year": 2021}),
    ("roadsafety_finding", {}), ("roadsafety_finding", {"op": "card"}),
    ("roadsafety_triage", {"question": "איזה דגם רכב הכי בטוח?"}),
]


@pytest.mark.parametrize("tool,args", RUNS)
def test_tool_answers_without_error_on_the_fixture(ctx, tool, args):
    out = tools_for(ctx)[tool].fn(**args)
    assert not out.is_error, out.texts()[:300]
    text = out.texts()
    assert text.strip()
    if args.get("face") == "sql":
        assert "```sql" in text
    if args.get("face") == "table":
        assert "|---|" in text


def test_chart_faces_return_an_image_block_unless_disabled(ctx):
    out = tools_for(ctx)["roadsafety_trend"].fn(**Y)
    assert [b["type"] for b in out.blocks] == ["text", "image"]
    out = tools_for(ctx, images=False)["roadsafety_trend"].fn(**Y)
    assert [b["type"] for b in out.blocks] == ["text"]


def test_none_inputs_fall_back_to_the_actions_defaults(ctx):
    runner = Runner(ctx.db_path)
    step = runner.run("trend", from_year=None, to_year=None, view="table")
    assert step.result.kind == "table" and step.inputs == {"view": "table"}


def test_model_tools_refuse_readably_without_a_deployment(ctx):
    pytest.importorskip("xgboost")
    tools = tools_for(ctx)
    for tool, args in (("roadsafety_sites", {"rank_by": "excess"}), ("roadsafety_predict", {}),
                       ("roadsafety_predict", {"switch": "חגור לעומת לא חגור"}),
                       ("roadsafety_explain", {}), ("roadsafety_explain", {"family": "site"})):
        out = tools[tool].fn(**args)
        assert not out.is_error and "# ❌" in out.texts(), (tool, out.texts()[:200])


def test_switch_routes_to_what_if_and_drivers_appends_explain(ctx):
    pytest.importorskip("xgboost")
    runner = Runner(ctx.db_path)
    tools = {t.name: t for t in build_tools(runner)}
    tools["roadsafety_predict"].fn(switch="יום לעומת לילה")
    tools["roadsafety_site"].fn(site="60/836", drivers=True)
    tools["roadsafety_site"].fn(site="njunction:433", drivers=True)
    acts = [[a["action"] for a in line["actions"]] for line in audit_lines(runner)]
    assert acts == [["what_if"], ["site_profile", "studio_explain"], ["site_profile"]]


def test_audit_line_per_call_never_the_numbers(ctx):
    runner = Runner(ctx.db_path)
    tools = {t.name: t for t in build_tools(runner)}
    tools["roadsafety_trend"].fn(measure="killed", **Y)
    lines = audit_lines(runner)
    assert len(lines) == 1
    line = lines[0]
    assert line["tool"] == "roadsafety_trend" and line["args"]["measure"] == "killed" and not line["error"]
    assert line["actions"][0]["action"] == "trend" and line["actions"][0]["kind"] == "chart"
    assert "rows" not in json.dumps(line) and "439" not in json.dumps(line)
    # the findings ledger got its own line from the envelope's guard, as on the page
    from nl2sql_roadsafety.studio import ledger
    entries, bad = ledger.read(ctx)
    assert bad == 0 and entries[-1]["action"] == "trend"


def test_missing_database_is_a_readable_error_never_a_crash(tmp_path):
    import nl2sql_engine
    nl2sql_engine.configure(data_dir=tmp_path)          # the audit line must land here, never on stage
    try:
        runner = Runner(str(tmp_path / "nope.duckdb"))
        assert ENV_DB in (runner.db_missing() or "")
        out = {t.name: t for t in build_tools(runner)}["roadsafety_trend"].fn()
        assert out.is_error and "nope.duckdb" in out.texts()
        lines = audit_lines(runner)
        assert len(lines) == 1 and lines[0]["note"] == "db missing" and lines[0]["actions"] == []
        assert runner.audit_path().is_relative_to(tmp_path)
    finally:
        nl2sql_engine.configure(data_dir=None)


# ── the confirm gate ───────────────────────────────────────────────────────────────────────────────────
def test_train_and_deploy_refuse_without_confirm_and_touch_nothing(studio_ctx):
    runner = Runner(studio_ctx.db_path)
    studio = {t.name: t for t in build_tools(runner)}["roadsafety_studio"]
    for op in ("train", "deploy"):
        out = asyncio.run(studio.fn(op=op, family="site"))
        assert not out.is_error and out.texts().startswith("# ⏸ נדרש אישור") and "confirm=true" in out.texts()
    assert not (studio_ctx.data_dir() / "accidents" / "models").exists()
    notes = [l.get("note") for l in audit_lines(runner)]
    assert notes == ["unconfirmed train", "unconfirmed deploy"]
    assert all(l["actions"] == [] for l in audit_lines(runner))


def test_confirmed_lifecycle_train_validate_deploy(studio_ctx):
    pytest.importorskip("xgboost")
    runner = Runner(studio_ctx.db_path)
    studio = {t.name: t for t in build_tools(runner)}["roadsafety_studio"]
    trained = asyncio.run(studio.fn(op="train", family="site", train_until=2022, confirm=True))
    assert not trained.is_error and "# ❌" not in trained.texts(), trained.texts()[:300]
    validated = asyncio.run(studio.fn(op="validate", family="site"))
    assert not validated.is_error
    deployed = asyncio.run(studio.fn(op="deploy", family="site", confirm=True))
    assert not deployed.is_error
    acts = [[a["action"] for a in l["actions"]] for l in audit_lines(runner)]
    assert acts == [["studio_train_site"], ["studio_validate"], ["studio_deploy"]]


# ── Claude Desktop registration (the installer's -Mcp step runs this module) ──────────────────────────
def test_register_merges_and_keeps_other_servers(tmp_path):
    from nl2sql_roadsafety.mcp import register
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {"gmail": {"command": "x"}}, "other": 1}), "utf-8")
    report = register.register(cfg, r"C:\app\.venv\Scripts\roadsafety-mcp.exe", r"C:\data\x.duckdb")
    doc = json.loads(cfg.read_text("utf-8"))
    assert doc["other"] == 1 and doc["mcpServers"]["gmail"] == {"command": "x"}
    assert doc["mcpServers"]["roadsafety"] == {"command": r"C:\app\.venv\Scripts\roadsafety-mcp.exe", "args": [],
                                               "env": {"NL2SQL_ROADSAFETY_DB": r"C:\data\x.duckdb", "PYTHONUTF8": "1"}}
    assert report["servers"] == ["gmail", "roadsafety"] and report["backup"] and cfg.with_name(
        cfg.name + report["backup"].rsplit(cfg.name, 1)[1]).exists()
    # second run: idempotent, a fresh backup each time
    register.register(cfg, "exe2", "db2")
    assert json.loads(cfg.read_text("utf-8"))["mcpServers"]["roadsafety"]["command"] == "exe2"


def test_register_creates_missing_config_and_refuses_bad_json(tmp_path, capsys):
    from nl2sql_roadsafety.mcp import register
    cfg = tmp_path / "Claude" / "claude_desktop_config.json"
    assert register.main(["--config", str(cfg), "--exe", "e", "--db", "d"]) == 0
    assert json.loads(cfg.read_text("utf-8"))["mcpServers"]["roadsafety"]["env"]["PYTHONUTF8"] == "1"
    cfg.write_text("{not json", "utf-8")
    assert register.main(["--config", str(cfg), "--exe", "e", "--db", "d"]) == 2
    assert cfg.read_text("utf-8") == "{not json"          # never overwritten
    assert register.main(["--config", str(cfg), "--exe", "e", "--db", "d", "--print-only"]) == 0
    assert '"roadsafety"' in capsys.readouterr().out


def test_register_detects_the_msix_virtualized_config(tmp_path, monkeypatch):
    r"""The Store build of Claude Desktop reads %LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude,
    never the real Roaming folder (2026-09-23)."""
    from nl2sql_roadsafety.mcp import register
    local, roaming = tmp_path / "Local", tmp_path / "Roaming"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(roaming))
    assert register.default_config_path() == roaming / "Claude" / "claude_desktop_config.json"
    virtual = local / "Packages" / "Claude_pzs8sxrjxfjjc" / "LocalCache" / "Roaming" / "Claude"
    virtual.mkdir(parents=True)
    assert register.default_config_path() == virtual / "claude_desktop_config.json"
    # main() without --config lands in the detected file and keeps Desktop's own preferences
    (virtual / "claude_desktop_config.json").write_text(json.dumps({"preferences": {"sidebarMode": "chat"}}), "utf-8")
    assert register.main(["--exe", "e", "--db", "d"]) == 0
    doc = json.loads((virtual / "claude_desktop_config.json").read_text("utf-8"))
    assert doc["preferences"] == {"sidebarMode": "chat"} and doc["mcpServers"]["roadsafety"]["command"] == "e"
    assert not (roaming / "Claude").exists()


def test_register_print_path_and_required_args(tmp_path, monkeypatch, capsys):
    from nl2sql_roadsafety.mcp import register
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "R"))
    assert register.main(["--print-path"]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "R" / "Claude" / "claude_desktop_config.json")
    with pytest.raises(SystemExit):
        register.main(["--exe", "e"])          # --db missing → argparse error


# ── find a site by name (M2) ───────────────────────────────────────────────────────────────────────────
def test_find_turns_names_into_site_keys(ctx):
    find = tools_for(ctx)["roadsafety_find"].fn
    t = find(name="העשור").texts()
    assert "`njunction:433`" in t and "צומת העשור" in t and "כבישים 9 / 90" in t
    assert "מקטעי כביש" not in t                                   # no segment carries that name
    t = find(name="צומת א", kind="segments").texts()
    assert "`1/10`" in t and "`road:1/0.0-12.0`" in t               # the LATEST vintage's km range
    t = find(name="רחוב א").texts()
    assert "`ujunction:5000/777`" in t and "תל אביב - יפו" in t and "תאונות עם נפגעים" in t
    t = find(name="תל אביב", kind="cities").texts()
    assert "קוד יישוב 5000" in t and "Tel Aviv-Yafo" in t
    assert "# ❌" in find(name="x").texts()                          # too short
    assert "לא נמצאו התאמות" in find(name="zzzz-nothing").texts()
    weird = find(name="a'%_\b").texts()                         # quotes and LIKE metacharacters are literals
    assert "לא נמצאו התאמות" in weird and "שגיאה" not in weird
    assert find(name="העשור", limit=99).texts().count("`njunction:") == 1


def test_find_is_audited_without_running_an_action(ctx):
    runner = Runner(ctx.db_path)
    {t.name: t for t in build_tools(runner)}["roadsafety_find"].fn(name="העשור")
    line = audit_lines(runner)[-1]
    assert line["tool"] == "roadsafety_find" and line["actions"] == [] and line["args"]["name"] == "העשור"
