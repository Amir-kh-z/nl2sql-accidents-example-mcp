# -*- coding: utf-8 -*-
"""The findings ledger: one JSON line per action run (answers AND refusal cards — never errors), appended by the
envelope's guard to `accidents/ledger.jsonl` under the shared data dir. No PNG, no row data — the numbers that
carried the answer, capped at ~4 KB per line. The append must NEVER break an answer, and the reader tolerates
corrupt lines (skipped and counted)."""
from __future__ import annotations

import datetime as _dt
import json
import threading
from pathlib import Path

_LOCK = threading.Lock()
MAX_LINE_BYTES = 4096
# spec extras worth keeping as evidence (scalars/small dicts only — checked again at build time)
NUMBER_KEYS = ("basis", "headline", "gate", "metrics", "model_id", "alpha", "counts", "double", "coverage",
               "tiers", "global_rate", "excluded", "map", "coding_share", "control_flag", "threshold_mm",
               "unit", "color_by_effective", "year", "naive", "correct", "ratio")


def path(ctx) -> Path:
    return ctx.data_dir() / "accidents" / "ledger.jsonl"


def _small(v, depth: int = 0):
    """Keep scalars and small flat structures; drop anything big or deep."""
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return v if len(v) <= 400 else v[:400] + "…"
    if depth >= 2:
        return None
    if isinstance(v, dict):
        out = {k: _small(x, depth + 1) for k, x in list(v.items())[:16]}
        return {k: x for k, x in out.items() if x is not None}
    if isinstance(v, (list, tuple)):
        return [_small(x, depth + 1) for x in list(v)[:16]]
    return str(v)[:100]


def _shape(kind: str, data) -> str:
    if kind != "markdown":
        return kind
    first = str(data or "").split("\n", 1)[0]
    if first.startswith("# ❌"):
        return "refusal"
    if first.startswith("# 🧭"):
        return "route"
    return "answer"


def entry_for(action: str, inputs: dict, result, version: str) -> dict:
    kind = getattr(result, "kind", "?")
    data = getattr(result, "data", None)
    shape = _shape(kind, data)
    spec = data if kind == "chart" and isinstance(data, dict) else {}
    if kind == "markdown":
        lines = str(data or "").split("\n")
        headline = lines[1] if len(lines) > 1 else (lines[0] if lines else "")
    elif kind == "chart":
        headline = spec.get("basis", "")
    elif kind == "table" and isinstance(data, dict):
        headline = f"{len(data.get('rows', []))} rows"
    else:
        headline = kind
    numbers = {}
    if spec:
        numbers["n_rows"] = len(spec.get("rows") or [])
        cols, rows = spec.get("columns") or [], spec.get("rows") or []
        if cols and rows:
            numbers["top"] = {c: _small(v) for c, v in list(zip(cols, rows[0]))[:16]}
        for k in NUMBER_KEYS:
            if k in spec:
                v = _small(spec[k])
                if v is not None:
                    numbers[k] = v
    elif kind == "table" and isinstance(data, dict):
        numbers["n_rows"] = len(data.get("rows") or [])
    return {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "action": action, "inputs": _small(inputs) or {}, "kind": kind, "shape": shape,
        "title": getattr(result, "title", "") or "", "headline": _small(headline), "numbers": numbers,
        "denominator": _small(spec.get("denominator")) if spec else None,
        "caveats": [(c if len(c) <= 300 else c[:300] + "…") for c in (spec.get("caveats") or [])][:10] if spec else [],
        "plugin_version": version,
    }


def append(ctx, entry: dict) -> None:
    """Atomic-enough on Windows: one buffered write of a single line under a process-wide lock. Never raises."""
    try:
        line = json.dumps(entry, ensure_ascii=False, default=str)
        if len(line.encode("utf-8")) > MAX_LINE_BYTES:
            entry = dict(entry)
            entry.get("numbers", {}).pop("top", None)
            line = json.dumps(entry, ensure_ascii=False, default=str)
        if len(line.encode("utf-8")) > MAX_LINE_BYTES:
            entry["caveats"] = []
            entry["numbers"] = {"truncated": True}
            line = json.dumps(entry, ensure_ascii=False, default=str)
        if len(line.encode("utf-8")) > MAX_LINE_BYTES:
            # inputs is the only unbounded field left (16 keys x 400 chars x 4 UTF-8 bytes) — sweep finding
            entry = {"ts": entry.get("ts"), "action": entry.get("action"), "kind": entry.get("kind"),
                     "shape": entry.get("shape"), "title": str(entry.get("title", ""))[:120],
                     "inputs": {"truncated": True}, "numbers": {"truncated": True},
                     "plugin_version": entry.get("plugin_version")}
            line = json.dumps(entry, ensure_ascii=False, default=str)
            if len(line.encode("utf-8")) > MAX_LINE_BYTES:  # cannot happen with the bounds above; stay honest
                return
        p = path(ctx)
        p.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK, open(p, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001 — the ledger must never break an answer
        pass


def read(ctx, last_n: int | None = None):
    """(entries oldest-first, corrupt_count). Corrupt lines are skipped and counted, never fatal."""
    p = path(ctx)
    if not p.exists():
        return [], 0
    entries, bad = [], 0
    try:
        for line in p.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                entries.append(obj if isinstance(obj, dict) else {"raw": obj})
            except Exception:  # noqa: BLE001
                bad += 1
    except Exception:  # noqa: BLE001
        return [], bad + 1
    if last_n is not None and last_n >= 0:
        entries = entries[-last_n:] if last_n else []
    return entries, bad
