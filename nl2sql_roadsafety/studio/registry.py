# -*- coding: utf-8 -*-
"""The model registry under the app's shared data dir: `accidents/models/<family>/<model_id>/{model.ubj, meta.json}`
plus one `deployed.json` pointer per family.

Rules learned the hard way elsewhere in this workspace: every write is atomic (tmp + os.replace — actions run in a
40-thread pool with no request timeout), every reader is tolerant (a garbled file becomes a readable status, never a
crash), and `about`'s shipped contract is honoured: `deployed.json` carries at least `model_id`.

Concurrency (P4 sweep): on Windows, os.replace onto a file ANY thread holds open raises PermissionError — Python
opens files without FILE_SHARE_DELETE — so with unserialized readers ~99 % of writes fail under load. One process
serves all requests (modules are cached in sys.modules), so a single module-wide RLock around every registry read
AND write removes the in-process race entirely; a bounded retry on os.replace covers external openers (antivirus,
an editor on meta.json). Multi-step invariants (save's collision check, deploy's demote→pointer→status) hold the
same lock across the whole sequence."""
from __future__ import annotations

import datetime as _dt
import json
import os
import threading
import time
from pathlib import Path

from . import constants

_LOCK = threading.RLock()
_REPLACE_TRIES = 40  # ~1 s worst case at 25 ms


def _replace(tmp: Path, path: Path) -> None:
    """os.replace with a bounded retry on Windows sharing violations; the tmp file never outlives a failure."""
    for i in range(_REPLACE_TRIES):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == _REPLACE_TRIES - 1:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
            time.sleep(0.025)


def root(ctx, family: str = constants.FAMILY_SITE) -> Path:
    return ctx.data_dir() / "accidents" / "models" / family


def model_dir(ctx, model_id: str, family: str = constants.FAMILY_SITE) -> Path:
    return root(ctx, family) / model_id


def now_utc() -> str:
    """Microseconds on purpose: two models registered in the same second must still order by created_at."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds")


def new_model_id(train_until: int, preset: str, seed: int, now: str | None = None,
                 family: str = constants.FAMILY_SITE) -> str:
    ts = (now or now_utc()).replace("-", "").replace(":", "").replace("+0000", "").replace("T", "T")[:15]
    return f"{family}-{train_until}-{preset.replace('-', '')}-s{seed}-{ts}"


def write_json_atomic(path: Path, obj) -> None:
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(obj, fh, ensure_ascii=False, indent=1, default=str)
                fh.flush()
                os.fsync(fh.fileno())
            _replace(tmp, path)
        finally:
            if tmp.exists():
                try:
                    os.unlink(tmp)
                except OSError:
                    pass


def write_bytes_atomic(path: Path, data: bytes) -> None:
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            with open(tmp, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            _replace(tmp, path)
        finally:
            if tmp.exists():
                try:
                    os.unlink(tmp)
                except OSError:
                    pass


def save(ctx, model_id: str, meta: dict, model: bytes, family: str = constants.FAMILY_SITE) -> str:
    """Register a model; a same-second id collision gets a numeric suffix. Returns the final model_id."""
    with _LOCK:  # the collision check and the two writes are one atomic step
        final = model_id
        n = 2
        while model_dir(ctx, final, family).exists():
            final = f"{model_id}-{n}"
            n += 1
        meta = {**meta, "model_id": final}
        d = model_dir(ctx, final, family)
        write_bytes_atomic(d / "model.ubj", model)
        write_json_atomic(d / "meta.json", meta)
        return final


def read_meta(ctx, model_id: str, family: str = constants.FAMILY_SITE) -> dict | None:
    with _LOCK:  # a read overlapping os.replace is the WinError 5 trigger
        p = model_dir(ctx, model_id, family) / "meta.json"
        if not p.exists():
            return None
        try:
            meta = json.loads(p.read_text("utf-8"))
            return meta if isinstance(meta, dict) and meta.get("model_id") else None
        except Exception:  # noqa: BLE001 — a garbled file is a status, not a crash
            return None


def update_meta(ctx, model_id: str, family: str = constants.FAMILY_SITE, **fields) -> dict | None:
    """Read-modify-write under the lock. `family` is a parameter, not an updatable field (metas do
    carry a "family" key, but no caller updates it). Returns None WITHOUT writing when the meta is unreadable — callers on a
    write path must check (a silently lost gate verdict was a sweep finding)."""
    with _LOCK:
        meta = read_meta(ctx, model_id, family)
        if meta is None:
            return None
        meta.update(fields)
        write_json_atomic(model_dir(ctx, model_id, family) / "meta.json", meta)
        return meta


def record_gate(ctx, model_id: str, gate_block: dict, verdict: str, family: str = constants.FAMILY_SITE,
                **extra) -> dict | None:
    """Stamp a gate verdict — the status is derived from the CURRENT meta under the lock, never from a read
    taken before the multi-second validation compute (a concurrent same-family deploy inside that window used
    to resurrect a demoted 'deployed' status or stale-demote the pointer's model — P9 sweep finding). Returns
    the updated meta, or None when the meta is unreadable (callers on a write path must check)."""
    with _LOCK:
        meta = read_meta(ctx, model_id, family)
        if meta is None:
            return None
        status = "deployed" if (meta.get("status") == "deployed" and verdict == "validated") else verdict
        return update_meta(ctx, model_id, family, gate=gate_block, status=status, **extra)


def model_bytes(ctx, model_id: str, family: str = constants.FAMILY_SITE) -> bytes | None:
    with _LOCK:
        p = model_dir(ctx, model_id, family) / "model.ubj"
        return p.read_bytes() if p.exists() else None


def list_models(ctx, family: str = constants.FAMILY_SITE) -> list[dict]:
    """Every model directory, oldest first; unreadable ones appear with status 'unreadable' (never dropped)."""
    with _LOCK:
        r = root(ctx, family)
        if not r.exists():
            return []
        out = []
        for d in sorted(p for p in r.iterdir() if p.is_dir()):
            meta = read_meta(ctx, d.name, family)
            out.append(meta if meta else {"model_id": d.name, "status": "unreadable", "created_at": ""})
        out.sort(key=lambda m: str(m.get("created_at", "")))
        return out


def deployed(ctx, family: str = constants.FAMILY_SITE):
    """(pointer, meta) — pointer is None when nothing is deployed; meta is None when the pointed model is
    missing/unreadable (the callers say so instead of crashing)."""
    with _LOCK:
        p = root(ctx, family) / "deployed.json"
        if not p.exists():
            return None, None
        try:
            pointer = json.loads(p.read_text("utf-8"))
            model_id = pointer.get("model_id")
        except Exception:  # noqa: BLE001
            return {"model_id": None, "unreadable": True}, None
        if not model_id:
            return {"model_id": None, "unreadable": True}, None
        return pointer, read_meta(ctx, str(model_id), family)


def set_deployed(ctx, meta: dict) -> dict:
    pointer = {"family": meta.get("family", constants.FAMILY_SITE), "model_id": meta["model_id"],
               "deployed_at": now_utc(), "plugin_version": meta.get("plugin_version"),
               "train_until": (meta.get("panel") or {}).get("train_until"), "preset": meta.get("preset"),
               "alpha": meta.get("alpha")}
    write_json_atomic(root(ctx, meta.get("family", constants.FAMILY_SITE)) / "deployed.json", pointer)
    return pointer


def deploy(ctx, meta: dict) -> dict:
    """Demote every other deployed meta, write the pointer, mark this meta deployed — ONE atomic sequence.
    Two concurrent deploys used to leave two metas at status 'deployed' (sweep finding); under the lock the loser
    of the race demotes the winner's predecessor and the invariant (exactly one 'deployed' meta, matching the
    pointer) holds. A demote hitting an unreadable meta is skipped (nothing to demote); a failure to update THIS
    meta after the pointer moved is raised — the pointer is authoritative, but the caller must not report success
    with a stale status on show."""
    family = meta.get("family", constants.FAMILY_SITE)
    with _LOCK:
        for other in list_models(ctx, family):
            if other.get("status") == "deployed" and other.get("model_id") != meta["model_id"]:
                update_meta(ctx, other["model_id"], family, status="validated", deployed_at=None)
        pointer = set_deployed(ctx, meta)
        if update_meta(ctx, meta["model_id"], family, status="deployed", deployed_at=pointer["deployed_at"]) is None:
            raise RuntimeError(f"meta.json for {meta['model_id']} became unreadable while deploying")
        return pointer


def resolve_id(ctx, model_id, want: str = "any", family: str = constants.FAMILY_SITE):
    """'latest' -> the newest model (optionally the newest with status 'validated'); otherwise the exact id.
    Returns (meta | None, available_ids)."""
    models = list_models(ctx, family)
    ids = [m.get("model_id", "?") for m in models]
    s = str(model_id or "").strip()
    if s in ("", "latest"):
        pool = [m for m in models if want == "any" or m.get("status") == want]
        return (pool[-1] if pool else None), ids
    for m in models:
        if m.get("model_id") == s:
            return m, ids
    return None, ids
