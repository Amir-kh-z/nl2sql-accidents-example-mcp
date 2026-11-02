# -*- coding: utf-8 -*-
"""The core as an in-process service provider (the course owner's slide 6): no port 8000, no HTTP — the engine's
own Context + Registry run the plugin's actions exactly as the app's adapters do (default filling,
validation and exception wrapping are the core's). Every tool call leaves one audit line
(`accidents/mcp_audit.jsonl` under the shared data dir): what was asked, which actions ran, how long,
what kind came back — never the numbers themselves (the findings ledger already holds those, written
by the envelope's guard for every answered run)."""
from __future__ import annotations

import datetime as _dt
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from nl2sql_engine.modules import Context, Registry, Result

from .. import MODULE

DEFAULT_DB = r"C:\data\israel_accidents\israel_accidents.duckdb"
ENV_DB = "NL2SQL_ROADSAFETY_DB"
AUDIT_REL = Path("accidents") / "mcp_audit.jsonl"
_AUDIT_LOCK = threading.Lock()


def resolve_db_path(explicit: str | None = None) -> str:
    """--db beats the environment beats the CBS working copy's absolute path."""
    return explicit or os.environ.get(ENV_DB) or DEFAULT_DB


@dataclass
class Step:
    """One action run inside a tool call, with its outcome (for the audit line)."""
    action: str
    inputs: dict
    result: Result
    ms: int


def current_user() -> str:
    """Who is asking: the OAuth login name on the web channel (the SDK's auth context), else "local"."""
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token
        tok = get_access_token()
        if tok is not None and tok.subject:
            return str(tok.subject)
    except Exception:  # noqa: BLE001 — no SDK, or no request in flight
        pass
    return "local"


@dataclass
class Runner:
    db_path: str
    audit_enabled: bool = True
    channel: str = "local"           # stdio (Desktop / Claude Code) = "local"; the web server sets "web"
    _registry: Registry = field(default_factory=Registry, repr=False)

    def __post_init__(self) -> None:
        if MODULE not in self._registry.modules:
            self._registry.modules.append(MODULE)

    @property
    def ctx(self) -> Context:
        return Context(db_path=self.db_path)

    def db_missing(self) -> str | None:
        """A readable reason when the database file is not there (never a crash at startup: the catalog
        still loads, and every tool answers with this sentence instead)."""
        p = Path(self.db_path)
        if not p.exists():
            return (f"database file not found: {self.db_path} — set {ENV_DB} (or --db) to the "
                    f"israel_accidents.duckdb working copy")
        return None

    def run(self, action: str, **inputs) -> Step:
        """One action through the real Registry: None values fall back to the declared defaults."""
        values = {k: v for k, v in inputs.items() if v is not None}
        t0 = time.perf_counter()
        result = self._registry.run(MODULE.name, action, self.ctx, values)
        return Step(action, values, result, int((time.perf_counter() - t0) * 1000))

    def audit_path(self) -> Path:
        return self.ctx.data_dir() / AUDIT_REL

    def audit(self, tool: str, args: dict, steps: list[Step], *, note: str = "") -> None:
        """Append one JSON line per tool call. Never raises — an audit failure must not break an answer."""
        if not self.audit_enabled:
            return
        try:
            entry = {
                "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                "tool": tool,
                "channel": self.channel,
                "user": current_user(),
                "args": {k: (v if isinstance(v, (bool, int, float)) or v is None else str(v)[:200])
                         for k, v in list(args.items())[:24]},
                "actions": [{"action": s.action, "kind": s.result.kind, "ms": s.ms} for s in steps],
                "error": any(s.result.kind == "error" for s in steps),
            }
            if note:
                entry["note"] = note[:200]
            p = self.audit_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            with _AUDIT_LOCK, open(p, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception:  # noqa: BLE001 — the audit must never break an answer
            pass
