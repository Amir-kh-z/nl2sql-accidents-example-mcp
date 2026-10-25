# -*- coding: utf-8 -*-
"""The answer envelope — the ONLY module that constructs a Result.

Every answer carries its denominator, its caveats, the exact SQL and the CBS credit inside the
Result itself (spec keys + a one-line note), so they survive any render surface, including the
generic Modules page. One action returns exactly one Result; the `view` input selects which face.
"""
from __future__ import annotations

import functools
import traceback

from nl2sql_engine.modules import Input, Result

from .sqlkit import ActionError, Refusal

CREDIT = "מקור הנתונים: הלשכה המרכזית לסטטיסטיקה (למ״ס); עיבוד: מעבדת הבטיחות בדרכים"
CREDIT_SHORT = "הלשכה המרכזית לסטטיסטיקה"
LAB_LINE = "מעבדת הבטיחות בדרכים · פועלת רק על מסד תאונות הדרכים (למ״ס)"   # refusal-card footer (never a CBS data credit)
REFUSAL_HEADING = "# ❌ לא ניתן לענות"          # single '#': Layer 0 renders deeper heading levels tiny
CAVEAT_DATA_END = "הנתונים מסתיימים ב-31.12.2024"
CAVEAT_COUNTS_NOT_RISK = "ספירות אינן סיכון — אין כאן מכנה חשיפה"

DENOM_KINDS = ("exposure", "counts", "none", "na")    # green / amber / red (a rate with no denominator) / grey (not a rate)


def denominator(kind: str, label: str, **extra) -> dict:
    """{"kind", "label", **extra} — extra carries the numbers behind the label (coverage etc.)."""
    if kind not in DENOM_KINDS:
        raise ValueError(f"unknown denominator kind {kind!r}; one of {', '.join(DENOM_KINDS)}")
    return {"kind": kind, "label": label, **extra}


ROUTE_HEADING = "# 🧭 ניתוב"          # single '#'


def route_card(title: str, head: str, body: list[str], actions: list[str]) -> Result:
    """A routing card (triage): which actions fit the question. No CBS data → lab-line footer, no credit."""
    lines = [ROUTE_HEADING, head] + list(body) + [f"- פעולה מתאימה: {a}" for a in actions] + [LAB_LINE]
    note = f"ניתוב · {head.splitlines()[0][:80]} · מעבדת הבטיחות בדרכים"
    return Result("markdown", "\n".join(lines), title, note)


DENOM_COUNTS = denominator("counts", "ספירות בלבד — ללא מכנה חשיפה")
DENOM_NA = denominator("na", "לא רלוונטי")

VIEWS = ("chart", "table", "sql", "markdown")
_VIEW_HELP = {"chart": "chart = PNG (+ the full answer in the spec)", "table": "table = the rows",
              "sql": "sql = the exact statement run", "markdown": "markdown = the explanation card"}


def version() -> str:
    try:
        from importlib.metadata import version as _v
        return _v("nl2sql-roadsafety-lab")
    except Exception:  # noqa: BLE001 — not installed (tests from a checkout)
        from . import __version__
        return __version__


def stamp_line(measure: str, granularity: str, road_type: str, y0: int, y1: int) -> str:
    """The PNG footer provenance — ASCII by construction (it is drawn un-shaped)."""
    return f"nl2sql-roadsafety-lab {version()} | {measure} / {granularity} / {road_type} | {y0}-{y1}"


def stamp(action: str, *parts) -> str:
    """Generic provenance stamp: `nl2sql-roadsafety-lab <v> | <action> | part | part` — ASCII by construction."""
    return f"nl2sql-roadsafety-lab {version()} | {action} | " + " | ".join(str(p) for p in parts)


def view_input(default: str, choices) -> Input:
    """The `view` input: tooltip built from THIS action's choices, never advertising a view it lacks."""
    choices = list(choices)
    return Input(kind="choice", label="תצוגה", default=default, choices=choices,
                 help="; ".join(_VIEW_HELP[c] for c in choices))


def note_line(denom: dict, caveats) -> str:
    """The one-line Layer-0 carrier: denominator · caveats · credit. Caveat texts never contain ';'."""
    caveats = list(caveats)
    return f"מכנה: {denom['label']} · הסתייגות: {'; '.join(caveats) or 'אין'} · מקור: {CREDIT_SHORT}"


def make_spec(type_: str, *, basis: str, rows, columns, sql: str, denominator: dict, caveats,
              png_base64: str | None = None, **extra) -> dict:
    """The chart spec carries the FULL answer, so a page can draw png + table + SQL from one call."""
    columns = list(columns)
    spec = {
        "type": type_,
        "renderer": "png" if png_base64 else "data",
        "png_base64": png_base64,
        "basis": basis,
        "rows": rows,
        "columns": columns,
        "sql": sql,
        "denominator": denominator,
        "caveats": list(caveats),
        "credit": CREDIT,
        "plugin_version": version(),
        "x": columns[0] if columns else "x",
        "y": columns[-1] if columns else "y",
    }
    spec.update(extra)
    return spec


def dispatch(view: str, spec: dict, title: str, body: list[str] | None = None) -> Result:
    """One Result per action: the `view` selects which single kind is returned."""
    note = note_line(spec["denominator"], spec["caveats"])
    if view == "chart":
        return Result("chart", spec, title, note)
    if view == "table":
        return Result("table", {"rows": spec["rows"], "columns": spec["columns"]}, title, note)
    if view == "sql":
        return Result("sql", spec["sql"], title, note)
    if view == "markdown" and body is not None:
        return markdown_answer(title, body, denom=spec["denominator"], caveats=spec["caveats"])
    legal = [v for v in VIEWS if v != "markdown" or body is not None]
    raise ActionError(f"Unknown view {view!r}. One of: {', '.join(legal)}.")


def markdown_answer(title: str, body: list[str], *, denom: dict, caveats) -> Result:
    """An explanation card within the Modules page's markdown subset ('#' headings, '-' bullets,
    one paragraph per line): first line the denominator, last line the CBS credit."""
    caveats = list(caveats)
    lines = [f"מכנה: {denom['label']}"] + list(body)
    if caveats:
        lines += ["# הסתייגויות"] + [f"- {c}" for c in caveats]
    lines.append(CREDIT)
    return Result("markdown", "\n".join(lines), title, note_line(denom, caveats))


def refusal(reason: str, answerable=(), *, title: str, what_to_do: str | None = None,
            detail: str | None = None) -> Result:
    """A styled refusal: what cannot be answered, why, what to do, what IS answerable. The footer
    is the lab line, never a CBS credit (this is not CBS data output)."""
    lines = [REFUSAL_HEADING, reason]
    if detail:
        lines.append(f"- הסיבה: {detail}")
    if what_to_do:
        lines.append(f"- מה לעשות: {what_to_do}")
    lines += [f"- מה כן אפשר: {a}" for a in answerable]
    lines.append(LAB_LINE)
    head = reason.splitlines()[0][:80] if reason else ""
    note = f"לא ניתן לענות · {head} · מעבדת הבטיחות בדרכים"      # ONE line: head sentence only
    return Result("markdown", "\n".join(lines), title, note)


def guard(title: str, *, ledger: bool = True):
    """Decorator factory for every action: folds the DB probe in (one place — impossible to forget in
    P2), turns Refusal into a refusal card and ActionError into a one-sentence error. The app's
    module_run discards tracebacks, so unexpected failures come back WITH a short traceback.

    P4: the guard IS the dispatcher, so it also appends the findings-ledger line — for answers AND
    refusal cards (a refusal is a finding), never for errors, and the append itself can never break
    an answer. `ledger=False` for the meta actions (about, ledger_list, finding_card)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapped(ctx, **kw):
            try:
                from . import dbcheck
                dbcheck.require(ctx)
                result = fn(ctx, **kw)
            except Refusal as r:
                result = refusal(r.reason, r.answerable, title=title, what_to_do=r.what_to_do,
                                 detail=r.detail)
            except ActionError as e:
                return Result.error(str(e))
            except Exception as e:  # noqa: BLE001 — a bad action never crashes the app
                return Result.error(f"{type(e).__name__}: {e}\n\n{traceback.format_exc(limit=4)}")
            if ledger:
                _ledger_append(ctx, fn, kw, result)
            return result
        return wrapped
    return deco


def _ledger_append(ctx, fn, inputs, result) -> None:
    """One JSONL line per answered run (accidents/ledger.jsonl). Never raises."""
    try:
        from .studio import ledger as _ledger
        action = getattr(fn.__globals__.get("ACTION"), "name", None) or fn.__module__.rsplit(".", 1)[-1]
        _ledger.append(ctx, _ledger.entry_for(action, inputs, result, version()))
    except Exception:  # noqa: BLE001 — the ledger must never break an answer
        pass
