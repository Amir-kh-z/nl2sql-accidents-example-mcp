# -*- coding: utf-8 -*-
"""Register the server with Claude Desktop: merge ONE entry into its JSON config, keeping every other
server. Python rather than PowerShell because the installer runs under Windows PowerShell 5.1 (no
`ConvertFrom-Json -AsHashtable`), and a JSON merge belongs in a language that has a JSON library.

    python -m nl2sql_roadsafety.mcp.register --config <claude_desktop_config.json> --exe <roadsafety-mcp.exe>
                                             --db <israel_accidents.duckdb> [--name roadsafety] [--print-only]

Prints a one-line JSON report; exit 2 when the existing file is not valid JSON (never overwritten)."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sys
from pathlib import Path

DEFAULT_NAME = "roadsafety"
CONFIG_NAME = "claude_desktop_config.json"


def default_config_path() -> Path:
    """Where THIS machine's Claude Desktop reads its config. The MSIX build (Microsoft Store channel,
    `C:\\Program Files\\WindowsApps\\Claude_*`) runs under filesystem virtualization: its %APPDATA%\\Claude is
    really `%LOCALAPPDATA%\\Packages\\Claude_<id>\\LocalCache\\Roaming\\Claude`, and a file written to the real
    Roaming folder is never read (bit us 2026-09-23 — Desktop's main.log names the path it reads). Prefer the
    package path when it exists; the classic installer keeps the plain Roaming path."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        for pkg in sorted(Path(local, "Packages").glob("Claude_*")):
            virtual = pkg / "LocalCache" / "Roaming" / "Claude"
            if virtual.is_dir():
                return virtual / CONFIG_NAME
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Claude" / CONFIG_NAME


def entry_for(exe: str, db: str) -> dict:
    return {"command": str(exe), "args": [], "env": {"NL2SQL_ROADSAFETY_DB": str(db), "PYTHONUTF8": "1"}}


def register(config_path: str | Path, exe: str, db: str, *, name: str = DEFAULT_NAME) -> dict:
    """Merge `mcpServers[name]` into the config; back the previous file up first. Returns a report."""
    cfg = Path(config_path)
    doc: dict = {}
    backup = None
    if cfg.exists():
        raw = cfg.read_text("utf-8-sig")
        if raw.strip():
            doc = json.loads(raw)                       # a bad file raises → the caller reports, never overwrites
            if not isinstance(doc, dict):
                raise ValueError("the config's top level is not a JSON object")
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = cfg.with_name(cfg.name + f".bak-{stamp}")
        shutil.copyfile(cfg, backup)
    else:
        cfg.parent.mkdir(parents=True, exist_ok=True)
    servers = doc.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
        doc["mcpServers"] = servers
    servers[name] = entry_for(exe, db)
    cfg.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"config": str(cfg), "backup": str(backup) if backup else None, "name": name,
            "servers": sorted(servers)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="roadsafety-mcp-register")
    p.add_argument("--config", default=None, help=f"the {CONFIG_NAME} to merge into (default: detected — "
                                                  "the MSIX package path when Desktop is the Store build)")
    p.add_argument("--exe", default="", help="the roadsafety-mcp executable")
    p.add_argument("--db", default="", help="the israel_accidents.duckdb path")
    p.add_argument("--name", default=DEFAULT_NAME)
    p.add_argument("--print-only", action="store_true", help="print the entry to paste by hand; write nothing")
    p.add_argument("--print-path", action="store_true", help="print the detected config path; write nothing")
    a = p.parse_args(argv)
    config = a.config or str(default_config_path())
    if a.print_path:
        print(config)
        return 0
    if not a.exe or not a.db:
        p.error("--exe and --db are required unless --print-path")
    if a.print_only:
        print(json.dumps({a.name: entry_for(a.exe, a.db)}, indent=2, ensure_ascii=False))
        return 0
    try:
        print(json.dumps(register(config, a.exe, a.db, name=a.name), ensure_ascii=False))
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": f"{config} is not valid JSON: {exc}"}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
