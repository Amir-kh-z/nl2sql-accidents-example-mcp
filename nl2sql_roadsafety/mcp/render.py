# -*- coding: utf-8 -*-
"""A Result becomes chat content. The envelope already carries everything an honest answer needs
(denominator, caveats, credit, the SQL, the rows, the PNG twin) — this module only lays it out as
text a model reads and summarizes, plus the PNG as an image block Claude Desktop shows.

Blocks are plain dicts ({"type": "text", "text": ...} / {"type": "image", "data": ..., "mime_type": ...})
so nothing here depends on the MCP SDK; server.py converts them at the boundary."""
from __future__ import annotations

from dataclasses import dataclass, field

from nl2sql_engine.modules import Result

MAX_ROWS = 60           # a chat answer is not a report: the page shows all rows, the chat shows the head
MAX_CELL = 120          # one cell never floods the table
ERROR_PREFIX = "שגיאה"

DENOM_HE = {"exposure": "מכנה חשיפה", "counts": "ספירות בלבד", "none": "שיעור ללא מכנה תקף", "na": "לא רלוונטי"}

# M2: the column legend. On 2026-09-25 the model read trend's coverage column `people` (everyone involved,
# 33,333) as "injured" (22,986). A column's NAME is all a chat sees, so helper and technical columns carry a
# one-line meaning under every table; purely internal flags are hidden. Keep entries short — they cost context.
COLUMN_NOTES = {
    "people": "people = כל המעורבים בתאונות הסדרה, כולל מי שלא נפגע — בדיקת כיסוי, לא מספר הנפגעים",
    "casualty_accidents": "casualty_accidents = תאונות עם נפגעים (case_type_code = 1)",
    "fatal_accidents": "fatal_accidents = תאונות קטלניות (אירועים), לא הרוגים",
    "killed": "killed = הרוגים (אנשים)",
    "severe_injured": "severe_injured = פצועים קשה (אנשים)",
    "slight_injured": "slight_injured = פצועים קל (אנשים)",
    "casualties": "casualties = נפגעים (הרוגים + פצועים)",
    "mu": "mu = הצפי של המודל הפרוס",
    "excess": "excess = נצפה − צפוי",
    "eb": "eb = אומדן אמפירי-בייס (מוחלק)",
    "lo90": "lo90/hi90 = רווח 90% סביב הצפי",
    "ksi_observed": "ksi = תאונות עם הרוג או פצוע קשה",
    "ksi_accidents": "ksi = תאונות עם הרוג או פצוע קשה",
    "rate": "rate = תאונות ל-100 מיליון ק״מ-רכב",
    "rate_lo": "rate_lo/rate_hi = רווח פואסון 95%",
    "adt_asof": "adt_asof = נפח תנועה יומי ממוצע (as-of)",
    "ratio": "ratio = יחס (DiD) — אסוציאציה, לא סיבתיות",
    "p_baseline": "p_baseline/p_scenario = הסתברויות יחסיות לבסיס — לא הסתברות מוחלטת",
    "share_pct": "share_pct = חלק מכלל הנפגעים באחוזים",
    "z": "z = ציון דירוג, לא מובהקות",
    "site_key": "site_key = המפתח להעברה לכלי roadsafety_site / roadsafety_change_effect",
    "idx": "idx = מזהה הרשומה בפנקס (ל-roadsafety_finding op=card)",
}
HIDDEN_COLUMNS = frozenset({"covered"})          # internal flags — the gap band is already a caveat


@dataclass
class ToolResult:
    blocks: list[dict] = field(default_factory=list)
    is_error: bool = False

    @staticmethod
    def text(s: str, *, is_error: bool = False) -> "ToolResult":
        return ToolResult([{"type": "text", "text": s}], is_error)

    def texts(self) -> str:
        return "\n".join(b["text"] for b in self.blocks if b.get("type") == "text")

    def __add__(self, other: "ToolResult") -> "ToolResult":
        return ToolResult(self.blocks + other.blocks, self.is_error or other.is_error)


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "כן" if v else "לא"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        s = f"{v:,.3f}".rstrip("0").rstrip(".")
        return s if s not in ("", "-") else "0"
    s = str(v).replace("\n", " ").replace("|", "\\|")
    return s if len(s) <= MAX_CELL else s[:MAX_CELL] + "…"


def legend(columns) -> str:
    """One line naming what the helper columns mean — only for columns present (context is not free)."""
    notes = [COLUMN_NOTES[c] for c in columns if c in COLUMN_NOTES]
    return ("מקרא: " + " · ".join(notes)) if notes else ""


def table_text(columns: list, rows: list, *, max_rows: int = MAX_ROWS) -> str:
    """A GitHub-style pipe table, capped, with the cap stated so the model never assumes it saw everything,
    hidden internal columns dropped, and the legend for the helper columns underneath."""
    columns = [str(c) for c in columns]
    if not columns:
        return "(אין עמודות)"
    keep = [i for i, c in enumerate(columns) if c not in HIDDEN_COLUMNS] or list(range(len(columns)))
    shown_cols = [columns[i] for i in keep]
    head = "| " + " | ".join(shown_cols) + " |\n|" + "---|" * len(shown_cols)
    shown = list(rows)[:max_rows]
    body = "\n".join("| " + " | ".join(_cell(r[i]) for i in keep if i < len(r)) + " |" for r in shown)
    out = head + ("\n" + body if body else "")
    n = len(rows)
    if n == 0:
        out += "\n(אין שורות)"
    elif n > max_rows:
        out += f"\n(מוצגות {max_rows} מתוך {n:,} שורות — הטבלה המלאה זמינה בעמוד המעבדה)"
    leg = legend(shown_cols)
    if leg:
        out += "\n" + leg
    return out


def _sql_block(sql: str) -> str:
    return "```sql\n" + str(sql).strip() + "\n```"


def chart_text(spec: dict, title: str, *, with_sql: bool) -> str:
    """The chart spec IS the full answer (envelope.make_spec): basis, denominator, caveats, rows, credit."""
    lines = [f"# {title}" if title else "# תשובה"]
    if spec.get("basis"):
        lines.append(f"בסיס: {spec['basis']}")
    denom = spec.get("denominator") or {}
    if denom:
        lines.append(f"מכנה: {denom.get('label', '')} [{DENOM_HE.get(denom.get('kind'), denom.get('kind', ''))}]")
    if spec.get("model_id"):
        lines.append(f"מודל: {spec['model_id']}")
    caveats = spec.get("caveats") or []
    if caveats:
        lines.append("הסתייגויות:")
        lines += [f"- {c}" for c in caveats]
    lines.append(table_text(spec.get("columns") or [], spec.get("rows") or []))
    if spec.get("credit"):
        lines.append(spec["credit"])
    if with_sql and spec.get("sql"):
        lines.append(_sql_block(spec["sql"]))
    return "\n".join(lines)


def to_result(result: Result, *, image: bool = True, with_sql: bool = False) -> ToolResult:
    """One Result → blocks. `with_sql` adds the statement to a chart face (face=sql on a chart-only
    instrument); the sql kind always carries its statement."""
    kind, data, title, note = result.kind, result.data, result.title or "", result.note or ""
    if kind == "error":
        return ToolResult.text(f"{ERROR_PREFIX}: {data}", is_error=True)
    if kind == "markdown":
        head = f"# {title}\n" if title and not str(data).startswith("#") else ""
        return ToolResult.text(head + str(data))
    if kind == "sql":
        return ToolResult.text("\n".join(x for x in (f"# {title}" if title else "", _sql_block(data), note) if x))
    if kind == "table":
        data = data if isinstance(data, dict) else {}
        body = table_text(data.get("columns") or [], data.get("rows") or [])
        return ToolResult.text("\n".join(x for x in (f"# {title}" if title else "", body, note) if x))
    if kind == "chart":
        spec = data if isinstance(data, dict) else {}
        out = ToolResult.text(chart_text(spec, title, with_sql=with_sql))
        png = spec.get("png_base64") if image else None
        if png:
            out.blocks.append({"type": "image", "data": png, "mime_type": "image/png"})
        return out
    return ToolResult.text(f"{ERROR_PREFIX}: unknown result kind {kind!r}", is_error=True)
