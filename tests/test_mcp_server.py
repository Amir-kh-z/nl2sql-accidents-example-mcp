# -*- coding: utf-8 -*-
"""M1 — the SDK layer: the server over the real protocol, in-process and as a stdio subprocess."""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

mcp = pytest.importorskip("mcp")

from nl2sql_roadsafety.mcp.runner import Runner        # noqa: E402
from nl2sql_roadsafety.mcp.server import INSTRUCTIONS, build_server   # noqa: E402
from nl2sql_roadsafety.mcp.tools import TOOL_ACTIONS   # noqa: E402

RESOURCES = {"roadsafety://rules", "roadsafety://catalog", "roadsafety://about", "roadsafety://models",
             "roadsafety://ledger"}
PROMPTS = {"site_review", "the_trap", "model_governance"}


def _run(coro):
    return asyncio.run(coro)


async def _exercise(client, *, want_image: bool) -> None:
    from mcp.types import ImageContent, TextContent
    tools = (await client.list_tools()).tools
    assert [t.name for t in tools] == list(TOOL_ACTIONS)
    by_name = {t.name: t for t in tools}
    schema = by_name["roadsafety_predict"].input_schema
    assert "steps" not in schema["properties"] and "runner" not in schema["properties"]
    assert schema["properties"]["safety"]["enum"] == ["לא צוין", "חגור או קסדה", "ללא אמצעי בטיחות"]
    assert schema["properties"]["switch"]["enum"][0] == "none"
    assert by_name["roadsafety_trend"].input_schema["properties"]["from_year"]["anyOf"]
    assert by_name["roadsafety_studio"].annotations.read_only_hint is False
    assert by_name["roadsafety_trend"].annotations.read_only_hint is True
    assert by_name["roadsafety_triage"].input_schema["required"] == ["question"]
    assert "ctx" not in by_name["roadsafety_studio"].input_schema["properties"]      # injected, never a form field
    assert by_name["roadsafety_find"].input_schema["required"] == ["name"]

    r = await client.call_tool("roadsafety_trend", {"from_year": 2022, "to_year": 2024})
    assert not r.is_error
    kinds = [type(c) for c in r.content]
    assert kinds[0] is TextContent and "| year" in r.content[0].text or "|" in r.content[0].text
    assert (ImageContent in kinds) == want_image
    bad = await client.call_tool("roadsafety_studio", {"op": "train"})
    assert not bad.is_error and bad.content[0].text.startswith("# ⏸")

    res = (await client.list_resources()).resources
    assert {str(x.uri) for x in res} == RESOURCES
    rules = (await client.read_resource("roadsafety://rules")).contents[0].text
    assert "case_type_code = 1" in rules and "439" in rules
    about = (await client.read_resource("roadsafety://about")).contents[0].text
    assert about.strip()
    prompts = (await client.list_prompts()).prompts
    assert {p.name for p in prompts} == PROMPTS
    msg = (await client.get_prompt("site_review", {"site": "60/850"})).messages[0].content.text
    assert "60/850" in msg and "roadsafety_site" in msg


def test_server_in_process(ctx):
    from mcp import Client
    server = build_server(Runner(ctx.db_path))
    assert server.instructions == INSTRUCTIONS and "confirm=true" in INSTRUCTIONS

    async def go():
        async with Client(server) as client:
            await _exercise(client, want_image=True)
    _run(go())


def test_server_without_images(ctx):
    from mcp import Client
    server = build_server(Runner(ctx.db_path), images=False)

    async def go():
        async with Client(server) as client:
            await _exercise(client, want_image=False)
    _run(go())


def test_server_over_stdio_subprocess(ctx, tmp_path):
    """The console entry as Claude Desktop / Claude Code launch it: a real subprocess, protocol on stdout."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters
    env = {**os.environ, "PYTHONUTF8": "1", "NL2SQL_CORE_DATA_DIR": str(tmp_path / "data")}
    params = StdioServerParameters(command=sys.executable,
                                   args=["-m", "nl2sql_roadsafety.mcp.server", "--db", ctx.db_path,
                                         "--data-dir", str(tmp_path / "data")], env=env)

    async def go():
        async with Client(params) as client:
            tools = (await client.list_tools()).tools
            assert len(tools) == 13
            r = await client.call_tool("roadsafety_orient", {"section": "about"})
            assert not r.is_error and r.content[0].text.strip()
            assert (await client.read_resource("roadsafety://catalog")).contents[0].text.startswith("# קטלוג")
    _run(go())
    assert (tmp_path / "data" / "accidents" / "mcp_audit.jsonl").exists()


def test_server_starts_without_a_database(tmp_path):
    """A missing DB never crashes startup: the catalog loads and every tool explains."""
    import nl2sql_engine
    from mcp import Client
    nl2sql_engine.configure(data_dir=tmp_path)          # the audit line must land here, never on stage
    try:
        server = build_server(Runner(str(tmp_path / "missing.duckdb")))

        async def go():
            async with Client(server) as client:
                assert len((await client.list_tools()).tools) == 13
                r = await client.call_tool("roadsafety_trend", {})
                assert r.is_error and "missing.duckdb" in r.content[0].text
        _run(go())
    finally:
        nl2sql_engine.configure(data_dir=None)


# ── M2: the hard confirmation gate through elicitation, and the read-only allow-list ───────────────────
def _elicit(answer):
    """A client-side elicitation handler: answer = "accept" | "decline" | "cancel"; records every ask."""
    from mcp.types import ElicitResult
    asked = []

    async def cb(_context, params):
        asked.append(params.message)
        if answer == "accept":
            return ElicitResult(action="accept", content={"approve": True})
        return ElicitResult(action=answer)
    return cb, asked


def _models_dir(ctx):
    return ctx.data_dir() / "accidents" / "models" / "site"


def test_elicitation_gate_declined_runs_nothing(ctx):
    from mcp import Client
    server = build_server(Runner(ctx.db_path))
    cb, asked = _elicit("decline")

    async def go():
        async with Client(server, elicitation_callback=cb, mode="legacy") as client:   # streams = back-channel
            r = await client.call_tool("roadsafety_studio", {"op": "train", "family": "site", "train_until": 2018,
                                                             "confirm": True})      # the flag is NOT enough here
            assert not r.is_error and r.content[0].text.startswith("# ⛔"), r.content[0].text
    _run(go())
    assert len(asked) == 1 and "אימון מודל" in asked[0] and "train_until=2018" in asked[0]
    assert not _models_dir(ctx).exists()


def test_elicitation_gate_accept_trains(ctx):
    pytest.importorskip("xgboost")
    from mcp import Client
    server = build_server(Runner(ctx.db_path))
    cb, asked = _elicit("accept")

    async def go():
        async with Client(server, elicitation_callback=cb, mode="legacy") as client:   # streams = back-channel
            r = await client.call_tool("roadsafety_studio", {"op": "train", "family": "site", "train_until": 2018})
            assert not r.is_error and "# ❌" not in r.content[0].text and "# ⏸" not in r.content[0].text, r.content[0].text
            v = await client.call_tool("roadsafety_studio", {"op": "validate", "family": "site"})
            assert not v.is_error
    _run(go())
    assert asked == [asked[0]] and len(asked) == 1          # validate never asks; train asked exactly once
    assert _models_dir(ctx).exists() and any(_models_dir(ctx).iterdir())


def test_without_elicitation_the_flag_path_still_holds(ctx):
    from mcp import Client
    server = build_server(Runner(ctx.db_path))

    async def go():
        async with Client(server) as client:                 # no callback → no capability → the ⏸ card
            r = await client.call_tool("roadsafety_studio", {"op": "deploy", "family": "site"})
            assert r.content[0].text.startswith("# ⏸")
    _run(go())


def test_read_only_catalog_leaves_the_studio_out(ctx):
    from mcp import Client
    server = build_server(Runner(ctx.db_path), read_only=True)

    async def go():
        async with Client(server) as client:
            names = [t.name for t in (await client.list_tools()).tools]
            assert "roadsafety_studio" not in names and len(names) == 12 and "roadsafety_find" in names
    _run(go())
    from nl2sql_roadsafety.mcp import server as srv
    args = srv.parse_args(["--tools", "read-only", "--db", ctx.db_path])
    assert args.tools == "read-only"
