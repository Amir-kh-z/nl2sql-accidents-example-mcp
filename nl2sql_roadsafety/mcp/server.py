# -*- coding: utf-8 -*-
"""The MCP server: the thin SDK layer over tools.py (the course owner's slide 8 — one protocol, every client).

    roadsafety-mcp [--db PATH] [--data-dir DIR] [--no-images]        (console script, stdio)
    python -m nl2sql_roadsafety.mcp.server ...

Tools, resources (the golden rules, the catalog, live about/models/ledger) and prompts (procedures) are all
declared on one server. stdio discipline: nothing but the protocol on stdout — logging goes to stderr and
matplotlib is forced headless before anything imports it."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from importlib import resources as _res

from ..envelope import version
from .render import ToolResult
from .runner import Runner, resolve_db_path
from .tools import ToolDef, build_tools, catalog_text

SERVER_NAME = "roadsafety"
INSTRUCTIONS = """Road Safety Lab (מעבדת הבטיחות בדרכים) — the Israel road-accidents database (CBS, 2005-2024) through
correct-by-construction instruments. Rules for answering:
- Answer in the person's language (Hebrew by default). Report the numbers the tools return; never derive or
  extrapolate numbers from a capped table, and never answer from memory when a tool can answer.
- Every answer states what was counted (series: casualty accidents), the denominator kind and the caveats
  the tool returned; keep the CBS credit line in anything you write from these results.
- Counts are not risk. Per-km rates exist for interurban segments only; junctions and cities never get rates.
- Start with roadsafety_orient(section=about) once per conversation; when unsure whether a question is
  answerable, call roadsafety_triage first and relay its reason.
- roadsafety_studio op=train and op=deploy change shared state: ask the person for explicit approval, and
  only then call again with confirm=true (when the server can, it asks the person itself through a form).
  Never chain train → deploy without a validate in between.
- State a number ONLY with the column it came from, and read the legend (מקרא) under every table: `people` is
  everyone involved including the uninjured (a coverage check), `killed` counts people, `fatal_accidents`
  counts events, `mu` is the model's expectation, `excess` = observed − expected.
- When the person names a place (a junction, an interchange, a street, a town) rather than a code, call
  roadsafety_find first and pass the returned key to roadsafety_site / roadsafety_change_effect.
- roadsafety_finding op=card promotes a LEDGER entry (a tool run), never a chat message; use op=list to pick the idx.
- Hebrew terms → tools: "מודל חומרה" = family severity; "מודל אתר"/"מודל מקטע" = family site; "מסוכן"/"סיכון"
  = excess vs the model (rank_by=excess), never raw counts; "צומת" is a junction (no exposure denominator, no
  model measures) and "מקטע" is a segment (rates and model measures exist); "לפני/אחרי"/"האם השינוי עבד" =
  roadsafety_change_effect; "מה אם"/"חגור לעומת לא חגור" = roadsafety_predict with switch; "למה"/"מה מניע" =
  roadsafety_explain; "פנקס"/"ממצא"/"כרטיס" = roadsafety_finding.
- Read roadsafety://rules for the golden rules (the two-series trap, the composite key, the two universes)."""


def _rules_text() -> str:
    return (_res.files("nl2sql_roadsafety.mcp") / "knowledge" / "rules.md").read_text("utf-8")


def build_server(runner: Runner, *, images: bool = True, read_only: bool = False, **mcp_kwargs):
    """Every tool, resource and prompt on one MCPServer. Imports the SDK here, never at module level.
    `mcp_kwargs` pass through to MCPServer — the web channel (web.py) adds `auth` and `auth_server_provider`
    this way; stdio passes nothing. `read_only=True` (the `--tools read-only` allow-list, M2) leaves the studio
    out of the catalog entirely — for an automation channel or a shared server nobody should train from."""
    from mcp.server.mcpserver import MCPServer
    from mcp.types import CallToolResult, ImageContent, TextContent, ToolAnnotations

    def wrap(res: ToolResult) -> CallToolResult:
        blocks = []
        for b in res.blocks:
            if b["type"] == "image":
                blocks.append(ImageContent(type="image", data=b["data"], mime_type=b.get("mime_type", "image/png")))
            else:
                blocks.append(TextContent(type="text", text=b["text"]))
        return CallToolResult(content=blocks, is_error=res.is_error)

    server = MCPServer(name=SERVER_NAME, title="Road Safety Lab · מעבדת הבטיחות בדרכים",
                       instructions=INSTRUCTIONS, version=version(), **mcp_kwargs)

    tool: ToolDef
    for tool in build_tools(runner, wrap=wrap, images=images):
        if read_only and not tool.read_only:
            continue
        ann = ToolAnnotations(read_only_hint=tool.read_only, destructive_hint=not tool.read_only,
                              idempotent_hint=tool.read_only, open_world_hint=False)
        server.tool(name=tool.name, description=tool.description, annotations=ann)(tool.fn)

    # ── resources: what the co-pilot should know ──────────────────────────────────────────────────────
    @server.resource("roadsafety://rules", name="rules", title="הכללים הזהובים", mime_type="text/markdown",
                     description="The golden rules of the CBS accidents database: the two-series trap, the "
                                 "composite key, denominators, the two universes, what cannot be answered.")
    def rules() -> str:
        return _rules_text()

    @server.resource("roadsafety://catalog", name="catalog", title="קטלוג הכלים", mime_type="text/markdown",
                     description="Every tool and the plugin actions behind it, with their defaults.")
    def catalog() -> str:
        return catalog_text()

    def _text_of(action: str, **inputs) -> str:
        from .render import to_result
        missing = runner.db_missing()
        if missing:
            return f"שגיאה: {missing}"
        return to_result(runner.run(action, **inputs).result, image=False).texts()

    @server.resource("roadsafety://about", name="about", title="אודות המסד", mime_type="text/markdown",
                     description="Live: is this the CBS database, coverage, row counts, the deployed models.")
    def about() -> str:
        return _text_of("about")

    @server.resource("roadsafety://models", name="models", title="רישום המודלים", mime_type="text/markdown",
                     description="Live: the model registry of both families with gate verdicts.")
    def models() -> str:
        return "# site\n" + _text_of("studio_models", family="site") + "\n\n# severity\n" + \
               _text_of("studio_models", family="severity")

    @server.resource("roadsafety://ledger", name="ledger", title="פנקס הממצאים", mime_type="text/markdown",
                     description="Live: the last 20 answered runs (answers and refusals) with headline numbers.")
    def ledger() -> str:
        return _text_of("ledger_list", last_n=20)

    # ── prompts: how to do it right ───────────────────────────────────────────────────────────────────
    @server.prompt(name="site_review", title="סקירת אתר", description="The full honest review of one site.")
    def site_review(site: str = "60/836") -> str:
        return (f"סקור את האתר {site} במסד תאונות הדרכים. סדר הפעולות: (1) roadsafety_site עם drivers=true — "
                "הרצועה השנתית, החומרה, ומדדי המודל אם זהו מקטע; (2) roadsafety_sites rank_by=excess לאותו כביש "
                "כדי למקם את האתר ביחס לרשת; (3) אם ידועה שנת שינוי — roadsafety_change_effect mode=evaluate; "
                "אחרת mode=discover ואז evaluate על המועמד. סכם בעברית: מה נצפה, מה המודל ציפה, מה ההסתייגויות, "
                "ומה אי אפשר לומר (צמתים ללא מכנה חשיפה). שמור את שורת הקרדיט של הלמ״ס.")

    @server.prompt(name="the_trap", title="המלכודת", description="Why a naive count is wrong by a factor of nine.")
    def the_trap(year: int = 2024) -> str:
        return (f"הדגם את המלכודת של שתי הסדרות לשנת {year}: קרא roadsafety_orient section=trap, הסבר מדוע "
                "הספירה הנאיבית (ללא case_type_code = 1) מנופחת, ואז קרא roadsafety_trend measure=slight_injured "
                "לאותה שנה. הצג את שני המספרים זה מול זה ואת היחס, בעברית פשוטה.")

    @server.prompt(name="model_governance", title="ממשל מודלים",
                   description="The lifecycle rule: validate before deploy, confirm before any state change.")
    def model_governance() -> str:
        return ("לפני כל פעולה במודלים: roadsafety_orient section=models לשתי המשפחות. אימון או פריסה משנים מצב — "
                "בקש אישור מפורש מהמשתמש, ורק אז קרא roadsafety_studio עם confirm=true. לעולם לא לפרוס מודל שלא "
                "עבר roadsafety_studio op=validate; מודל שנדחה נשאר ברישום כעדות (הסבר את סיבות הדחייה).")

    return server


LOOPBACK = ("127.0.0.1", "localhost", "::1")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="roadsafety-mcp",
                                     description="Road Safety Lab MCP server — stdio (Desktop / Claude Code) or "
                                                 "http (the web channel behind OAuth; see tools/web_tunnel.ps1)")
    parser.add_argument("--db", default=None, help="path to israel_accidents.duckdb (else $NL2SQL_ROADSAFETY_DB)")
    parser.add_argument("--data-dir", default=None, help="the shared data dir (else the engine's own resolution)")
    parser.add_argument("--no-images", action="store_true", help="text only — no PNG blocks in tool results")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1", help="http: bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="http: bind port (default 8765)")
    parser.add_argument("--public-url", default=None,
                        help="http: the public https://host the tunnel exposes — the OAuth issuer; required unless --no-auth")
    parser.add_argument("--no-auth", action="store_true",
                        help="http: no OAuth — allowed ONLY on a loopback --host (dev and tests)")
    parser.add_argument("--channel", default=None, help="audit label (default: local for stdio, web for http)")
    parser.add_argument("--tools", choices=("all", "read-only"), default="all",
                        help="read-only leaves roadsafety_studio out of the catalog (automation, shared servers)")
    args = parser.parse_args(argv)
    if args.transport == "http":
        if args.no_auth and args.host not in LOOPBACK:
            parser.error("--no-auth is allowed only with a loopback --host (127.0.0.1 / localhost)")
        if not args.no_auth and not args.public_url:
            parser.error("--transport http needs --public-url https://<host> (the tunnel's address), or --no-auth on loopback")
    return args


def make_server(args: argparse.Namespace):
    """Runner + server from parsed args (no .run() — tests build without serving)."""
    import nl2sql_engine
    if args.data_dir:
        nl2sql_engine.configure(data_dir=args.data_dir)
    channel = args.channel or ("web" if args.transport == "http" else "local")
    runner = Runner(resolve_db_path(args.db), channel=channel)
    if runner.db_missing():
        logging.getLogger(SERVER_NAME).warning(runner.db_missing())   # the catalog still loads; tools explain
    read_only = args.tools == "read-only"
    if args.transport == "http" and not args.no_auth:
        from .web import web_config_from_env, build_web_server
        cfg = web_config_from_env(args.public_url, nl2sql_engine.resolve_data_dir())
        return build_web_server(runner, cfg, images=not args.no_images, read_only=read_only), cfg
    return build_server(runner, images=not args.no_images, read_only=read_only), None


def transport_security(args: argparse.Namespace, cfg):
    """DNS-rebinding protection on the MCP endpoint: loopback forms always; the tunnel's host when public."""
    from mcp.server.transport_security import TransportSecuritySettings
    hosts = [f"127.0.0.1:{args.port}", f"localhost:{args.port}", "127.0.0.1", "localhost"]
    origins = [f"http://127.0.0.1:{args.port}", f"http://localhost:{args.port}"]
    if cfg is not None:
        hosts += [cfg.host, f"{cfg.host}:443"]
        origins += [cfg.public_url]
    return TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hosts,
                                     allowed_origins=origins)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    os.environ.setdefault("MPLBACKEND", "Agg")                 # headless before matplotlib is ever imported
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    server, cfg = make_server(args)
    if args.transport == "stdio":
        server.run("stdio")
        return
    log = logging.getLogger(SERVER_NAME)
    log.warning("http on %s:%s%s", args.host, args.port, f" — public {cfg.mcp_url}" if cfg else " — NO AUTH (loopback)")
    server.run("streamable-http", host=args.host, port=args.port, transport_security=transport_security(args, cfg))


if __name__ == "__main__":
    main()
