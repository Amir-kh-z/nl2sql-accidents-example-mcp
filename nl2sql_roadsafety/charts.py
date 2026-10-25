# -*- coding: utf-8 -*-
"""Server-drawn PNGs: thread-safe (Figure + FigureCanvasAgg, never pyplot — the app's route runs in
a threadpool), lazy (matplotlib is imported inside the functions), Hebrew-safe (bidi shaping with a
digit-preserving fallback). Every frame carries the title, the denominator badge, the caveats, the
CBS credit and an ASCII provenance stamp.
"""
from __future__ import annotations

import base64
import io
import re
import threading

from .envelope import CREDIT

_HEB_RANGE = f"{chr(0x0590)}-{chr(0x05FF)}"           # the Hebrew block, spelled out (no literal RTL chars in source)
_HEB = re.compile(f"[{_HEB_RANGE}]")
_INK, _INK_SOFT, _INK_FAINT = "#26323d", "#5a6672", "#8b959e"
_TEAL, _ORANGE, _GRID = "#0d9488", "#f7931e", "#e8e4e0"
_AMBER_FACE, _AMBER_EDGE, _AMBER_TEXT = "#fff4e0", "#f7931e", "#8a5a00"
PNG_CAVEAT_CAP = 6          # P1's longest list is exactly 6: nothing P1 emits is truncated
CAVEAT_WRAP = 118           # characters per visual line at 7.5 pt on the 9.6-inch frame (longer lines were clipped)
_CAVEAT_TOP, _CAVEAT_FLOOR, _CAVEAT_PITCH = 0.245, 0.090, 0.034


_FONT_LOCK = threading.Lock()
_FONT_READY = False


def _ensure_font() -> None:
    """Register the bundled Assistant face (SIL OFL, `data/fonts/`) once per process and make it the family,
    with DejaVu as the PER-GLYPH fallback for symbols Assistant lacks (← and Σ; ≠ is native). Two traps this encodes:
    `font.family` must be the LIST (per-glyph fallback works ONLY there — `font.sans-serif` is a search list
    that picks one font for the whole text), and a missing bundle degrades silently to DejaVu (the same
    tolerance contract as the bidi fallback)."""
    global _FONT_READY
    if _FONT_READY:
        return
    with _FONT_LOCK:
        if _FONT_READY:
            return
        try:
            from pathlib import Path

            import matplotlib
            from matplotlib import font_manager

            fonts = sorted((Path(__file__).parent / "data" / "fonts").glob("*.ttf"))
            if fonts:
                for f in fonts:
                    font_manager.fontManager.addfont(str(f))
                matplotlib.rcParams["font.family"] = ["Assistant", "DejaVu Sans"]
        except Exception:  # noqa: BLE001 — a font problem must never break an answer
            pass
        _FONT_READY = True


def wrap_caveat(line: str, width: int = CAVEAT_WRAP) -> list[str]:
    """Split one caveat into visual lines at its ' · ' / ', ' seams so its logical end (the LEFT end in RTL) is
    never clipped off the frame. Seams INSIDE parentheses never split (a dangling paren gets re-oriented by the
    bidi pass — P8 sweep). Pure, so the geometry is unit-tested."""
    line = str(line)
    if len(line) <= width:
        return [line]
    chunks, cur, depth = [], "", 0
    for ch in line:
        depth += (ch == "(") - (ch == ")")
        cur += ch
        if depth <= 0 and (cur.endswith(" · ") or cur.endswith(", ")):
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    out, acc = [], ""
    for chunk in chunks:
        if acc and len(acc) + len(chunk) > width:
            out.append(acc.rstrip())
            acc = chunk
        else:
            acc += chunk
    if acc.strip():
        out.append(acc.rstrip())
    return out


# P8 bidi findings (the display fixture in test_charts.py pins all of this; two sweeps refined it):
# * base direction is ALWAYS "R": heb() only runs on Hebrew-containing strings, and every real chart string is a
#   Hebrew-context line. A first-strong auto heuristic (tried mid-P8) scrambled Hebrew caveats that OPEN with a
#   Latin acronym ("ADT ≠ AADT: …", "EB: M = 200 …") because the leading "• " bullet is neutral — the P8 sweep's
#   high. Forced R renders those correctly.
# * parenthesized groups whose content STARTS Latin/digit/math get LRM-pinned on BOTH sides: under raw UBA the
#   opening paren after a Latin/number run resolves L (unmirrored) while the closing one resolves R (mirrored) —
#   faces showed two "(" and zero ")". With LRMs both parens resolve L, pair correctly, and formulas like
#   exp(ln r ± 1.96·SE), SE² = Σ 1/(n+½) hold together as one LTR run. Hebrew-content parens are untouched.
# * en-dash number ranges flip under the UBA (2005–2024 -> 2024–2005): LRM wrapping pins them. TIGHT ranges only —
#   a SPACED em-dash (60/850 — 113) is a separator, never a range.
# * KEEP the legacy bidi.algorithm implementation: it applies rule L4 (paren mirroring); the newer Rust
#   bidi.get_display does NOT and would regress parentheses.
_NUM_RANGE = re.compile(r"\d[\d,.]*%?[–-]\d[\d,.]*%?")
_LTR_PAREN = re.compile(r"\((?=\s*[0-9A-Za-zΣ±½·])[^()]*\)")
_LRM = chr(0x200E)                          # LEFT-TO-RIGHT MARK (zero-width; constructed, not a literal)


def heb(text) -> str:
    """Visual-order Hebrew for matplotlib (which draws logical order left-to-right)."""
    s = str(text)
    if not _HEB.search(s):
        return s
    s = _LTR_PAREN.sub(lambda m: _LRM + m.group(0) + _LRM, s)
    s = _NUM_RANGE.sub(lambda m: _LRM + m.group(0) + _LRM, s)
    try:
        from bidi.algorithm import get_display
        return get_display(s, base_dir="R")
    except Exception:  # noqa: BLE001 — host bidi missing/broken
        return _mirror(s)


def _mirror(s: str) -> str:
    """[::-1] that keeps digit/Latin runs readable: reverse all, re-reverse the non-Hebrew runs."""
    return re.sub(f"[^{_HEB_RANGE}\\s]+", lambda m: m.group(0)[::-1], s[::-1])


def caveat_ys(n_shown: int) -> list[float]:
    """Figure-fraction tops of the caveat lines: the 0.034 pitch up to 5 lines, then compressed so the
    LAST line's top stays at 0.090 (above the credit). Pure, so the geometry is unit-tested."""
    pitch = min(_CAVEAT_PITCH, (_CAVEAT_TOP - _CAVEAT_FLOOR) / max(n_shown - 1, 1))
    return [_CAVEAT_TOP - i * pitch for i in range(n_shown)]


def png(draw, *, title: str, badge: str, caveats, stamp: str, figsize=(9.6, 5.8), dpi=140) -> str:
    """The frame every chart shares. `draw(fig, ax)` fills the plot area."""
    _ensure_font()
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    caveats = list(caveats)
    fig = Figure(figsize=figsize, dpi=dpi)
    FigureCanvasAgg(fig)
    fig.text(0.97, 0.955, heb(title), ha="right", va="top", fontsize=13, color=_INK, fontweight="bold")
    fig.text(0.97, 0.895, heb(badge), ha="right", va="top", fontsize=8.5, color=_AMBER_TEXT,
             bbox=dict(boxstyle="round,pad=0.35", facecolor=_AMBER_FACE, edgecolor=_AMBER_EDGE, linewidth=0.8))
    ax = fig.add_axes([0.08, 0.33, 0.89, 0.50])
    draw(fig, ax)
    shown = list(caveats[:PNG_CAVEAT_CAP])
    if len(caveats) > PNG_CAVEAT_CAP:
        shown.append(f"… ועוד {len(caveats) - PNG_CAVEAT_CAP} הסתייגויות (בהערה)")
    lines = []
    for c in shown:
        parts = wrap_caveat(c)
        lines.append((parts[0], False))
        lines.extend((p, True) for p in parts[1:])
    size = 7.5 if len(lines) <= 8 else 6.5
    for (part, cont), y in zip(lines, caveat_ys(len(lines))):
        # continuation indent belongs on the RIGHT of an RTL block — as a logical-order "   " prefix the
        # bidi step parked it on the left edge (P8 audit); an x-offset puts it where the eye expects
        fig.text(0.97 - (0.012 if cont else 0.0), y, heb(part if cont else "• " + part),
                 ha="right", va="top", fontsize=size, color=_INK_SOFT)
    fig.text(0.97, 0.03, heb(CREDIT), ha="right", va="bottom", fontsize=7, color=_INK_FAINT)
    fig.text(0.03, 0.03, stamp, ha="left", va="bottom", fontsize=6.5, color=_INK_FAINT, family="monospace")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    return base64.b64encode(buf.getvalue()).decode("ascii")


_RED, _GREEN = "#c0392b", "#0d9488"
_KILLED, _SEVERE, _SLIGHT = "#26323d", "#f7931e", "#0d9488"


def _fit_labels(ax, labels) -> None:
    """Widen the left margin for long category labels (the frame's default axes start at x = 0.08)."""
    longest = max((len(str(l)) for l in labels), default=0)
    left = min(0.36, 0.08 + 0.011 * max(0, longest - 6))
    ax.set_position([left, 0.33, 0.97 - left, 0.50])


def _style_axes(ax, xlabel: str | None = None):
    ax.grid(axis="x", color=_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8, colors=_INK_SOFT)
    if xlabel:
        ax.set_xlabel(heb(xlabel), fontsize=9, color=_INK_SOFT)


def hbars(labels, values, *, xlabel: str, lo=None, hi=None, annot=None, colors=None, vline=None,
          vline_label=None, gap_after=None, gap_text=None, markers=None, max_rows=None, **frame) -> str:
    """Horizontal bars, first row on top; optional CI whiskers (lo/hi), per-bar annotation, a vertical
    reference line, a dashed break after index `gap_after`, and hollow markers (e.g. the raw rate).
    `max_rows` caps the DRAWN rows (the table face keeps everything) with an honest overflow note —
    the P8 fix for the 30-row annotation soup."""
    total = len(labels)
    if max_rows is not None and total > max_rows:
        labels, values = labels[:max_rows], values[:max_rows]
        lo = lo[:max_rows] if lo is not None else None
        hi = hi[:max_rows] if hi is not None else None
        annot = annot[:max_rows] if annot is not None else None
        colors = colors[:max_rows] if colors is not None else None
        markers = markers[:max_rows] if markers is not None else None
        frame["caveats"] = [f"בתרשים {max_rows} העליונות מתוך {total} — הטבלה מציגה את כולן"] + list(
            frame.get("caveats") or [])
    labels = [heb(l) for l in labels]
    vals = [0.0 if v is None else float(v) for v in values]
    n = len(vals)
    dense = n > 15

    def draw(fig, ax):
        _fit_labels(ax, labels)
        ys = list(range(n))[::-1]
        cols = colors if colors else [_TEAL] * n
        ax.barh(ys, vals, color=cols, height=0.68 if dense else 0.62, zorder=2)
        marks = [0.0 if m is None else float(m) for m in markers] if markers is not None else None
        if lo is not None and hi is not None:
            left = [max(0.0, v - float(l or 0)) for v, l in zip(vals, lo)]
            right = [max(0.0, float(h or 0) - v) for v, h in zip(vals, hi)]
            ax.errorbar(vals, ys, xerr=[left, right], fmt="none", ecolor=_INK_SOFT,
                        elinewidth=1.6, capsize=3.5, capthick=1.6, zorder=3)
        if marks is not None:
            ax.plot(marks, ys, linestyle="none", marker="o", markerfacecolor="white",
                    markeredgecolor=_INK, markeredgewidth=1.4, markersize=5 if dense else 6, zorder=4)
        if vline is not None:
            ax.axvline(float(vline), color=_ORANGE, linestyle="--", linewidth=1.2, zorder=1)
            if vline_label:
                ax.text(float(vline), n - 0.4, heb(vline_label), color=_ORANGE, fontsize=7, ha="left", va="bottom")
        if gap_after is not None and 0 <= gap_after < n - 1:
            ygap = ys[gap_after] - 0.5
            ax.axhline(ygap, color=_INK_FAINT, linestyle=":", linewidth=1)
            if gap_text:
                ax.text(ax.get_xlim()[1] if vals else 0, ygap, heb(gap_text), fontsize=7, color=_INK_FAINT,
                        ha="right", va="center")
        # the x-range and each annotation clear EVERYTHING on the row — bar, whisker AND marker
        # (observed markers beyond the CI collided with the numbers in the P8 screenshots)
        xmax = max(vals + ([float(h or 0) for h in hi] if hi is not None else []) + (marks or []) + [1e-9])
        ax.set_xlim(0, xmax * 1.30)
        if annot:
            for i, (y, v, a) in enumerate(zip(ys, vals, annot)):
                edge = max(v, float(hi[i] or v) if hi is not None else v, marks[i] if marks else v)
                ax.text(edge + xmax * 0.025, y, heb(str(a)), fontsize=7 if dense else 7.5,
                        color=_INK_SOFT, va="center", ha="left")
        ax.set_yticks(ys)
        ax.set_yticklabels(labels, fontsize=7 if dense else 8)
        ax.set_ylim(-0.7, n - 0.3)
        _style_axes(ax, xlabel)

    return png(draw, **frame)


def stacked_bars(labels, parts: dict, totals, *, xlabel: str, **frame) -> str:
    """100 % stacked horizontal bars (killed / severe / slight), N annotated at the bar end."""
    labels = [heb(l) for l in labels]
    n = len(labels)
    names = list(parts)
    palette = {"killed": _KILLED, "severe": _SEVERE, "slight": _SLIGHT}
    he_names = {"killed": "הרוגים", "severe": "פצועים קשה", "slight": "פצועים קל"}

    def draw(fig, ax):
        _fit_labels(ax, labels)
        ys = list(range(n))[::-1]
        left = [0.0] * n
        for name in names:
            series = parts[name]
            shares = [100.0 * float(s) / float(t) if t else 0.0 for s, t in zip(series, totals)]
            ax.barh(ys, shares, left=left, color=palette.get(name, _TEAL), height=0.62,
                    label=heb(he_names.get(name, name)), zorder=2)
            left = [l + s for l, s in zip(left, shares)]
        for y, t in zip(ys, totals):
            ax.text(101.5, y, f"{int(t):,}", fontsize=7.5, color=_INK_SOFT, va="center", ha="left")
        ax.set_xlim(0, 118)
        ax.set_yticks(ys)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_ylim(-0.7, n - 0.3)
        handles, hlabels = ax.get_legend_handles_labels()
        # RTL reading order: the FIRST series belongs on the RIGHT (matplotlib lays legend columns LTR)
        ax.legend(handles[::-1], hlabels[::-1], loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  ncol=3, fontsize=7, frameon=False)
        _style_axes(ax, xlabel)

    return png(draw, **frame)


def severity_lines(years, parts: dict, *, uncovered=(), y0: int, y1: int, **frame) -> str:
    """The three severities as ABSOLUTE lines over the years (P13 round 2 — the rival's Trends view, kept
    honest): descending stroke weights (killed widest), uncovered years break the lines (NaN, never bridged,
    never zero) and are shaded — the rival draws straight through his missing years."""
    palette = {"killed": _KILLED, "severe": _SEVERE, "slight": _SLIGHT}
    widths = {"killed": 2.8, "severe": 2.2, "slight": 1.7}
    he_names = {"killed": "הרוגים", "severe": "פצועים קשה", "slight": "פצועים קל"}
    xs = list(range(y0, y1 + 1))
    by_year = {name: dict(zip(years, series)) for name, series in parts.items()}
    gap = set(uncovered)

    def draw(fig, ax):
        for y in sorted(gap):
            ax.axvspan(y - 0.5, y + 0.5, color=_GRID, alpha=0.55, zorder=1)
        for name in parts:
            vals = [float("nan") if x in gap else float(by_year[name].get(x, float("nan"))) for x in xs]
            ax.plot(xs, vals, color=palette[name], linewidth=widths[name], marker="o", markersize=3.4,
                    label=heb(he_names[name]), zorder=3)
        ax.set_xlim(y0 - 0.5, y1 + 0.5)
        ax.set_ylim(bottom=0)
        step = 1 if y1 - y0 <= 12 else 2
        ax.set_xticks(list(range(y0, y1 + 1, step)))
        ax.tick_params(axis="x", labelsize=7.5, labelrotation=0)
        handles, hlabels = ax.get_legend_handles_labels()
        # RTL reading order: the FIRST series belongs on the RIGHT (matplotlib lays legend columns LTR)
        ax.legend(handles[::-1], hlabels[::-1], loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  ncol=3, fontsize=7, frameon=False)
        _style_axes(ax, "שנה")

    return png(draw, **frame)


def before_after_bars(panels, *, headline: str, **frame) -> str:
    """Two panels (casualty / damage-only): site vs network, before = 100, after = 100 × after/before,
    raw counts annotated; the double ratio as a headline between the badge and the panels."""
    def draw(fig, ax):
        ax.set_axis_off()
        fig.text(0.97, 0.855, heb(headline), ha="right", va="top", fontsize=11, color=_INK, fontweight="bold")
        boxes = [[0.08, 0.35, 0.40, 0.40], [0.57, 0.35, 0.40, 0.40]]
        for panel, box in zip(panels, boxes):
            px = fig.add_axes(box)
            groups = [("אתר", panel["site_before"], panel["site_after"]),
                      ("רשת", panel["net_before"], panel["net_after"])]
            xs = [0, 1, 2.6, 3.6]
            heights, cols, notes = [], [], []
            for _, b, a in groups:
                heights += [100.0 if b else 0.0, (100.0 * a / b) if b else 0.0]
                cols += [_INK_FAINT, _TEAL]
                notes += [f"{int(b):,}", f"{int(a):,}"]
            px.bar(xs, heights, color=cols, width=0.85, zorder=2)
            for x, h, note in zip(xs, heights, notes):
                px.text(x, h + 2, note, ha="center", va="bottom", fontsize=7.5, color=_INK_SOFT)
            px.set_xticks([0.5, 3.1])
            px.set_xticklabels([heb(g[0]) for g in groups], fontsize=8)
            px.set_ylim(0, max(heights + [100.0]) * 1.25)
            px.set_ylabel(heb("לפני = 100"), fontsize=8, color=_INK_SOFT)
            px.set_title(heb(panel["title"]), fontsize=9, color=_INK)
            px.grid(axis="y", color=_GRID, linewidth=0.8)
            px.set_axisbelow(True)
            for s in ("top", "right"):
                px.spines[s].set_visible(False)
            px.tick_params(labelsize=8, colors=_INK_SOFT)

    return png(draw, **frame)


def tier_bars(rows, *, global_rate: float, xlabel: str, **frame) -> str:
    """Vehicle-cell tiers: highest-risk cells on top (red), a break marker, safest at the bottom (teal);
    EB rate as the bar, raw rate as a hollow marker, the global rate as a dashed line.
    `rows` = list of dicts with label, eb, raw, tier (top-first order already applied by the caller)."""
    labels = [r["label"] for r in rows]
    values = [r["eb"] for r in rows]
    markers = [r["raw"] for r in rows]
    colors = [_RED if r["tier"] == "highest_risk" else _GREEN for r in rows]
    n_top = sum(1 for r in rows if r["tier"] == "highest_risk")
    gap_after = n_top - 1 if 0 < n_top < len(rows) else None
    return hbars(labels, values, xlabel=xlabel, colors=colors, markers=markers, vline=global_rate,
                 vline_label="שיעור גלובלי", gap_after=gap_after, gap_text=frame.pop("gap_text", None), **frame)


def cohort_bars(rows, *, global_rate: float, xlabel: str, **frame) -> str:
    """P13 vehicle-cohort bars: one bar per manufacture year IN YEAR ORDER (never tier-sorted — the cohort
    axis is the story), EB rate as the bar, raw rate as a hollow marker, the global rate dashed; highest-risk
    tier in red, everything else teal. `rows` = list of dicts with label, eb, raw, tier, annot."""
    return hbars([r["label"] for r in rows], [r["eb"] for r in rows], xlabel=xlabel,
                 annot=[r["annot"] for r in rows],
                 colors=[_RED if r["tier"] == "highest_risk" else _GREEN for r in rows],
                 markers=[r["raw"] for r in rows], vline=global_rate, vline_label="שיעור גלובלי", **frame)


def line_chart(labels, values, *, ylabel: str, gaps, monthly: bool, **frame) -> str:
    """A time series with uncovered periods drawn as a grey band + ✕ (never as a zero)."""
    from matplotlib.ticker import FuncFormatter

    labels = list(labels)
    gaps = list(gaps)

    def draw(fig, ax):
        ys = [float("nan") if v is None else float(v) for v in values]
        xs = list(range(len(ys)))
        ax.plot(xs, ys, color=_TEAL, linewidth=2, marker="o", markersize=3 if monthly else 4)
        for i in gaps:
            ax.axvspan(i - 0.5, i + 0.5, color="#f1f1f1", zorder=0)
            ax.plot([i], [0], marker="x", color=_ORANGE, markersize=7, markeredgewidth=1.6, clip_on=False)
            ax.annotate(heb("אין נתונים"), (i, 0), textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=7, color=_ORANGE, rotation=90 if monthly else 0)
        real = [(i, y) for i, y in enumerate(ys) if y == y]
        for i, y in ((real[0], real[-1]) if real else ()):
            ax.annotate(f"{int(y):,}", (i, y), textcoords="offset points", xytext=(0, 7),
                        ha="center", fontsize=8, color=_INK)
        ticks = [i for i, l in enumerate(labels) if (l.endswith("-01") if monthly else True)]
        ax.set_xticks(ticks)
        ax.set_xticklabels([heb(labels[i][:4] if monthly else labels[i]) for i in ticks],
                           rotation=45 if len(ticks) > 12 else 0, fontsize=8)
        top = max((y for y in ys if y == y), default=0.0)
        ax.set_ylim(0, max(1.0, top * 1.18))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
        ax.set_ylabel(heb(ylabel), fontsize=9, color=_INK_SOFT)
        ax.grid(axis="y", color=_GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)

    return png(draw, **frame)


# ── P13: the day × hour heat matrix ──

def heat_png(grid, day_labels, *, cbar_label: str, xlabel: str = "שעה ביום", **frame) -> str:
    """The 7×24 heat matrix: imshow over the zero-filled grid (row i = day_of_week i+1, so ראשון sits on top),
    a light→teal→red colormap (the map twin's ramp), hour ticks every 3, Hebrew day labels through the bidi
    shaping helper, and the colorbar in the beeswarm's slot. `grid` is the spec's 7 lists of 24 counts."""
    labels = [heb(l) for l in day_labels]

    def draw(fig, ax):
        from matplotlib.colors import LinearSegmentedColormap
        cmap = LinearSegmentedColormap.from_list("lab_heat", ["#f6f4f1", _TEAL, _RED])
        ax.set_position([0.10, 0.33, 0.83, 0.50])
        im = ax.imshow([[float(v) for v in row] for row in grid], aspect="auto", cmap=cmap,
                       interpolation="nearest", vmin=0.0)
        ax.set_xticks(list(range(0, 24, 3)))
        ax.set_xticklabels([str(h) for h in range(0, 24, 3)], fontsize=8)
        ax.set_yticks(list(range(len(labels))))
        ax.set_yticklabels(labels, fontsize=8)
        ax.tick_params(labelsize=8, colors=_INK_SOFT, length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xlabel(heb(xlabel), fontsize=9, color=_INK_SOFT)
        cax = fig.add_axes([0.945, 0.36, 0.012, 0.44])
        cb = fig.colorbar(im, cax=cax)
        cb.set_label(heb(cbar_label), fontsize=7, color=_INK_SOFT)
        cb.ax.tick_params(labelsize=6, colors=_INK_SOFT)
        cb.outline.set_visible(False)

    return png(draw, **frame)


# ── P5: multi-series lines (two_wheelers) and the SHAP two-panel (studio_explain) ──
_SERIES_COLORS = ["#0d9488", "#c0392b", "#f7931e", "#26323d", "#7d3c98", "#2471a3"]


def _line_axes(ax, ylabel: str):
    ax.grid(axis="y", color=_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8, colors=_INK_SOFT)
    ax.set_ylabel(heb(ylabel), fontsize=9, color=_INK_SOFT)


def multi_lines(x, series, *, ylabel: str, **frame) -> str:
    """One line per (label, values) pair over shared x (years). None values leave gaps, never zeros."""
    def draw(fig, ax):
        for (label, vals), color in zip(series, _SERIES_COLORS * 4):
            ys = [float("nan") if v is None else float(v) for v in vals]
            ax.plot(x, ys, color=color, linewidth=2, marker="o", markersize=4, label=heb(str(label)))
        ax.set_xticks(list(x))
        ax.set_xticklabels([heb(str(v)) for v in x], fontsize=8)
        ax.set_ylim(bottom=0)
        ax.legend(fontsize=7.5, loc="upper left", frameon=False)
        _line_axes(ax, ylabel)

    return png(draw, **frame)


def explain_png(years, phi_series, observed, mu, *, ylabel_phi: str, ylabel_right: str, **frame) -> str:
    """The SHAP two-panel (landscape): right panel (RTL: read first) = observed bars vs μ line per year;
    left panel = the top features' φ lines per year on the log-rate scale (0 = no contribution)."""
    def draw(fig, ax):
        ax.set_position([0.06, 0.33, 0.52, 0.50])
        for (label, vals), color in zip(phi_series, _SERIES_COLORS * 4):
            ys = [float("nan") if v is None else float(v) for v in vals]
            ax.plot(years, ys, color=color, linewidth=2, marker="o", markersize=4, label=heb(str(label)))
        ax.axhline(0, color=_INK_FAINT, linewidth=1)
        ax.set_xticks(list(years))
        ax.set_xticklabels([heb(str(y)) for y in years], fontsize=8)
        ax.legend(fontsize=7, loc="best", frameon=False)
        _line_axes(ax, ylabel_phi)
        ax2 = fig.add_axes([0.67, 0.33, 0.30, 0.50])
        ax2.bar(list(years), [0.0 if v is None else float(v) for v in observed], color=_TEAL, width=0.6,
                label=heb("נצפה"), zorder=2)
        ax2.plot(list(years), [float(v) for v in mu], color=_RED, linewidth=2, marker="o", markersize=4,
                 label=heb("צפוי"), zorder=3)
        ax2.set_xticks(list(years))
        ax2.set_xticklabels([heb(str(y)) for y in years], fontsize=7, rotation=45)
        ax2.set_ylim(bottom=0)
        ax2.legend(fontsize=7.5, loc="best", frameon=False)
        _line_axes(ax2, ylabel_right)

    return png(draw, figsize=(11.5, 5.8), **frame)


# ── P3: the map twin ──
_MAP_FACE, _MAP_EDGE = "#eef2f5", "#8b959e"
MAP_BBOX = (34.15, 35.95, 29.4, 33.45)          # lon_min, lon_max, lat_min, lat_max — Israel, WGS84


def _rings(geojson):
    """Outer rings of every Polygon / MultiPolygon in a GeoJSON Feature(Collection) or geometry."""
    feats = geojson.get("features", []) if geojson.get("type") == "FeatureCollection" else [geojson]
    for f in feats:
        g = f.get("geometry", f)
        if g.get("type") == "Polygon":
            yield g["coordinates"][0]
        elif g.get("type") == "MultiPolygon":
            for poly in g["coordinates"]:
                yield poly[0]


def map_png(units, *, outline_geojson=None, cloud=None, marker="o", **frame) -> str:
    """The map's static twin: the Israel outline (package data unless given) with one circle per unit
    (area proportional to its count), rank digits on the top five and a side list of the top twelve. Units
    only — never the individual accidents (this face is Layer 0 and the page's fallback). Figure/Agg only.
    P10: an optional `cloud` = {"lon": [...], "lat": [...]} draws a log-scaled hexbin density UNDER the
    circles (map_scene's twin — the density is an aggregate, so the Layer-0 face stays chart-frame-only)."""
    import math

    placed = sorted((u for u in units if u.get("lat") is not None and u.get("lon") is not None),
                    key=lambda u: -float(u.get("n") or 0))
    if outline_geojson is None:
        from .sqlkit import outline
        outline_geojson = outline()
    vmax = max((float(u.get("n") or 0) for u in placed), default=0.0) or 1.0
    lon0, lon1, lat0, lat1 = MAP_BBOX

    def draw(fig, ax):
        ax.set_position([0.04, 0.31, 0.42, 0.53])
        for ring in _rings(outline_geojson):
            ax.fill([p[0] for p in ring], [p[1] for p in ring], facecolor=_MAP_FACE, edgecolor=_MAP_EDGE,
                    linewidth=0.8, zorder=1)
        ax.set_xlim(lon0, lon1)
        ax.set_ylim(lat0, lat1)
        ax.set_aspect(1.0 / math.cos(math.radians((lat0 + lat1) / 2)))
        ax.axis("off")
        if cloud and cloud.get("lon"):
            from matplotlib.colors import LinearSegmentedColormap
            cmap = LinearSegmentedColormap.from_list("lab_density", [_MAP_FACE, _TEAL, _KILLED])
            ax.hexbin([float(x) for x in cloud["lon"]], [float(y) for y in cloud["lat"]],
                      gridsize=48, extent=(lon0, lon1, lat0, lat1), bins="log", mincnt=1,
                      cmap=cmap, linewidths=0.0, alpha=0.9, zorder=2)
        for u in placed:
            size = 4 + 14 * math.sqrt(float(u.get("n") or 0) / vmax)
            ax.plot(float(u["lon"]), float(u["lat"]), marker=marker, markersize=size,
                    color=u.get("color") or _TEAL, alpha=0.75,
                    markeredgecolor="white", markeredgewidth=0.6, linestyle="none", zorder=3)
        for u in placed:
            rank = int(u.get("rank") or 0)
            if 0 < rank <= 5:
                ax.text(float(u["lon"]), float(u["lat"]), str(rank), fontsize=7, ha="center", va="center",
                        color="white", fontweight="bold", zorder=4)
        side = fig.add_axes([0.50, 0.31, 0.47, 0.53])
        side.axis("off")
        shown = sorted(placed, key=lambda u: int(u.get("rank") or 0))[:12]
        for i, u in enumerate(shown):
            text = f"{u.get('rank', i + 1)}. {u.get('label', '')} — {int(u.get('n') or 0):,}"
            side.text(1.0, 1.0 - i * 0.078, heb(text), ha="right", va="top", fontsize=7.5, color=_INK,
                      transform=side.transAxes)
        if not placed:
            side.text(1.0, 1.0, heb("אין יחידות ממוקמות"), ha="right", va="top", fontsize=8, color=_INK_SOFT,
                      transform=side.transAxes)

    return png(draw, figsize=(9.6, 7.6), **frame)


def scene_png(cloud, units, **frame) -> str:
    """map_scene's Layer-0 twin (P10): the hexbin density of the whole point cloud under the top segment
    marks — SQUARES, the page's shape grammar (squares = segments, circles = junctions); the twin shows
    segments only, so every mark is a square. Aggregate density + unit marks, never rows."""
    return map_png(units, cloud=cloud, marker="s", **frame)


def site_card_png(years, accidents, ksi, mu=None, *, ylabel="תאונות עם נפגעים", **frame) -> str:
    """site_profile's twin (P10): yearly casualty-accident bars with the KSI portion inked, and the deployed
    site model's μ line where the model block ran (None where it did not). Years label as plain strings —
    never thousands-grouped."""
    def draw(fig, ax):
        idx = list(range(len(years)))
        ax.bar(idx, accidents, width=0.72, color=_TEAL, alpha=0.5, label=heb("תאונות עם נפגעים"), zorder=2)
        ax.bar(idx, ksi, width=0.72, color=_KILLED, alpha=0.9, label=heb("קשות וקטלניות"), zorder=3)
        if mu is not None and any(m is not None for m in mu):
            xs = [i for i, m in zip(idx, mu) if m is not None]
            ys = [float(m) for m in mu if m is not None]
            ax.plot(xs, ys, color=_RED, linewidth=1.6, marker="o", markersize=3.5,
                    label=heb("תחזית המודל"), zorder=4)
        ax.set_xticks(idx)
        step = max(1, len(years) // 12)                     # keep long spans legible
        ax.set_xticklabels([str(y) if i % step == 0 else "" for i, y in enumerate(years)], fontsize=7)
        ax.grid(axis="y", color=_GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(labelsize=8, colors=_INK_SOFT)
        ax.set_ylabel(heb(ylabel), fontsize=9, color=_INK_SOFT)
        ax.legend(loc="upper left", fontsize=7, frameon=False)

    return png(draw, **frame)


# ── P16: the studio training cards' PNG twins (the page builders in PlotlyChart.jsx share this data) ──

def _year_axes(ax, years, ylabel: str) -> list[int]:
    """Vertical-bar frame over a year axis: plain-string year labels (never thousands-grouped), the
    house grid/spines/ticks. Returns the bar x positions."""
    idx = list(range(len(years)))
    ax.set_xticks(idx)
    step = max(1, len(years) // 12)                     # keep long spans legible (site_card_png's rule)
    ax.set_xticklabels([str(y) if i % step == 0 else "" for i, y in enumerate(years)], fontsize=8)
    ax.grid(axis="y", color=_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8, colors=_INK_SOFT)
    ax.set_ylabel(heb(ylabel), fontsize=9, color=_INK_SOFT)
    return idx


def train_site_png(years, sum_y, adt_share, *, ylabel="תאונות בלוח", ylabel_right="% ADT ידוע",
                   **frame) -> str:
    """studio_train_site's twin: per-year panel target bars (sum_y) + the ADT-known share line on a right
    axis — the coverage the caveats cite. `adt_share` is percent 0–100 (None leaves a gap, never a zero)."""
    def draw(fig, ax):
        idx = _year_axes(ax, years, ylabel)
        ax.bar(idx, [0.0 if v is None else float(v) for v in sum_y], width=0.68, color=_TEAL,
               label=heb("תאונות בלוח"), zorder=2)
        ax.set_ylim(bottom=0)
        ax2 = ax.twinx()
        ax2.plot(idx, [float("nan") if v is None else float(v) for v in adt_share], color=_ORANGE,
                 linewidth=2, marker="o", markersize=4, label=heb("ADT ידוע"), zorder=3)
        ax2.set_ylim(0, 102)
        ax2.spines["top"].set_visible(False)
        ax2.tick_params(labelsize=8, colors=_INK_SOFT)
        ax2.set_ylabel(heb(ylabel_right), fontsize=9, color=_INK_SOFT)
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=7, frameon=False)

    return png(draw, **frame)


def train_severity_png(years, killed, severe, slight, *, ylabel="נפגעים", **frame) -> str:
    """studio_train_severity's twin: stacked per-year class counts (slight at the base, killed on top) —
    the share-drift story in raw counts. Legend reversed so the reading order matches the stack top-down."""
    def draw(fig, ax):
        idx = _year_axes(ax, years, ylabel)
        sl = [0.0 if v is None else float(v) for v in slight]
        sv = [0.0 if v is None else float(v) for v in severe]
        kl = [0.0 if v is None else float(v) for v in killed]
        ax.bar(idx, sl, width=0.68, color=_SLIGHT, label=heb("פצועים קל"), zorder=2)
        ax.bar(idx, sv, width=0.68, bottom=sl, color=_SEVERE, label=heb("פצועים קשה"), zorder=2)
        ax.bar(idx, kl, width=0.68, bottom=[a + b for a, b in zip(sl, sv)], color=_KILLED,
               label=heb("הרוגים"), zorder=2)
        top = max((a + b + c for a, b, c in zip(sl, sv, kl)), default=0.0)
        ax.set_ylim(0, max(1.0, top * 1.15))
        handles, hlabels = ax.get_legend_handles_labels()
        ax.legend(handles[::-1], hlabels[::-1], loc="upper left", fontsize=7, frameon=False)

    return png(draw, **frame)


# ── P12: the SHAP faces (beeswarm / dependence / waterfall) ──
_NOMINAL_GREY, _NULL_EDGE = "#9aa4ad", "#8b959e"


def beeswarm(row_labels, dots, *, xlabel: str, ordered_rows, colorbar_label: str | None = None,
             **frame) -> str:
    """The SHAP beeswarm: one row per feature (top = most important), dots at x = φ with the SERVER-computed
    jitter (`dots` is the spec's columnar block — the page never randomizes, both faces share one layout).
    Coloring policy drawn, not just declared: `value_norm` (0–1) colors ONLY ordered rows on the teal→orange
    scale; nominal dots are neutral grey; NULL dots are hollow — "לא ידוע" is a real model input."""
    labels = [heb(l) for l in row_labels]
    n = len(labels)
    show_bar = any(ordered_rows) and colorbar_label

    def draw(fig, ax):
        from matplotlib.colors import LinearSegmentedColormap
        cmap = LinearSegmentedColormap.from_list("lab_phi", [_TEAL, "#e8e4e0", _ORANGE])
        longest = max((len(str(l)) for l in labels), default=0)
        left = min(0.36, 0.08 + 0.011 * max(0, longest - 6))
        right = 0.935 if show_bar else 0.97
        ax.set_position([left, 0.33, right - left, 0.50])
        xs_f, ys_f, cs = [], [], []                      # colored (ordered) dots batched per draw call
        xs_g, ys_g = [], []                              # nominal grey
        xs_n, ys_n = [], []                              # NULL hollow
        for r, p, j, vn, isnull in zip(dots["row"], dots["phi"], dots["jitter"],
                                       dots["value_norm"], dots["is_null"]):
            y = (n - 1 - r) + j
            if isnull:
                xs_n.append(p); ys_n.append(y)
            elif vn is None:
                xs_g.append(p); ys_g.append(y)
            else:
                xs_f.append(p); ys_f.append(y); cs.append(float(vn))
        ax.scatter(xs_g, ys_g, s=9, c=_NOMINAL_GREY, alpha=0.55, linewidths=0, zorder=2)
        ax.scatter(xs_n, ys_n, s=9, facecolors="none", edgecolors=_NULL_EDGE, linewidths=0.7,
                   alpha=0.8, zorder=2)
        sc = ax.scatter(xs_f, ys_f, s=9, c=cs, cmap=cmap, vmin=0.0, vmax=1.0, alpha=0.75,
                        linewidths=0, zorder=3)
        ax.axvline(0, color=_INK_FAINT, linewidth=1, zorder=1)
        ax.set_yticks(list(range(n))[::-1])
        ax.set_yticklabels(labels, fontsize=7 if n > 10 else 8)
        ax.set_ylim(-0.7, n - 0.3)
        _style_axes(ax, xlabel)
        if show_bar:
            cax = fig.add_axes([0.945, 0.36, 0.012, 0.44])
            cb = fig.colorbar(sc, cax=cax)
            cb.set_label(heb(colorbar_label), fontsize=7, color=_INK_SOFT)
            cb.ax.tick_params(labelsize=6, colors=_INK_SOFT)
            cb.outline.set_visible(False)

    return png(draw, **frame)


def dependence_dots(xj, phi, is_null, *, xlabel: str, ylabel: str, ticks=None, null_x=None,
                    **frame) -> str:
    """The dependence face: monochrome dots at (value, φ) — vertical spread = interactions (the dossier's
    reading note rides as a caveat). `ticks` = [[code, label], …] switches to a categorical axis (the last
    tick is the explicit "לא ידוע" slot); on a numeric axis `null_x` marks the labelled strip the builder
    reserved for NULL dots. NULL dots draw hollow on both axis kinds — never dropped (P12 sweep)."""
    def draw(fig, ax):
        pairs = [(x, p, nul) for x, p, nul in zip(xj, phi, is_null) if x is not None]
        xs_k = [x for x, _p, nul in pairs if not nul]
        ys_k = [p for _x, p, nul in pairs if not nul]
        xs_n = [x for x, _p, nul in pairs if nul]
        ys_n = [p for _x, p, nul in pairs if nul]
        ax.scatter(xs_k, ys_k, s=10, c=_TEAL, alpha=0.5, linewidths=0, zorder=2)
        ax.scatter(xs_n, ys_n, s=10, facecolors="none", edgecolors=_NULL_EDGE, linewidths=0.7,
                   alpha=0.8, zorder=2)
        ax.axhline(0, color=_INK_FAINT, linewidth=1, zorder=1)
        if ticks:
            ax.set_xticks(list(range(len(ticks))))
            ax.set_xticklabels([heb(str(t[1])) for t in ticks], fontsize=7,
                               rotation=30 if len(ticks) > 6 else 0, ha="right" if len(ticks) > 6 else "center")
        elif null_x is not None and xs_n:
            known_hi = max(xs_k, default=0.0)
            ax.axvline((known_hi + null_x) / 2.0, color=_INK_FAINT, linestyle=":", linewidth=1, zorder=1)
            ax.text(null_x, 1.02, heb("לא ידוע"), transform=ax.get_xaxis_transform(),
                    fontsize=7, color=_INK_SOFT, ha="center", va="bottom")
        ax.grid(axis="y", color=_GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(labelsize=8, colors=_INK_SOFT)
        ax.set_xlabel(heb(xlabel), fontsize=9, color=_INK_SOFT)
        ax.set_ylabel(heb(ylabel), fontsize=9, color=_INK_SOFT)

    return png(draw, **frame)


def waterfall(labels, values, *, xlabel: str, neutral=(), **frame) -> str:
    """A signed driver hbar ("waterfall" reading): bars from 0, orange = pushes the margin up (risk),
    teal = down; indices in `neutral` (היתר, בסיס) draw grey. First label on top, RTL-safe annotations."""
    labels_v = [heb(l) for l in labels]
    vals = [float(v) for v in values]
    n = len(vals)

    def draw(fig, ax):
        longest = max((len(str(l)) for l in labels_v), default=0)
        left = min(0.36, 0.08 + 0.011 * max(0, longest - 6))
        ax.set_position([left, 0.33, 0.97 - left, 0.50])
        ys = list(range(n))[::-1]
        cols = [_NOMINAL_GREY if i in neutral else (_ORANGE if v >= 0 else _TEAL)
                for i, v in enumerate(vals)]
        ax.barh(ys, vals, color=cols, height=0.62, zorder=2)
        ax.axvline(0, color=_INK_FAINT, linewidth=1, zorder=1)
        span = max(abs(v) for v in vals + [1e-9])
        ax.set_xlim(-span * 1.35, span * 1.35)
        for y, v in zip(ys, vals):
            ax.text(v + (span * 0.03 if v >= 0 else -span * 0.03), y, f"{v:+.2f}",
                    fontsize=7, color=_INK_SOFT, va="center", ha="left" if v >= 0 else "right")
        ax.set_yticks(ys)
        ax.set_yticklabels(labels_v, fontsize=8)
        ax.set_ylim(-0.7, n - 0.3)
        _style_axes(ax, xlabel)

    return png(draw, **frame)


def ratio_with_drivers(ratio_labels, ratios, drv_labels, drv_values, *, xlabel_ratio: str,
                       xlabel_drivers: str, ratio_colors=None, annot=None, neutral=(), **frame) -> str:
    """severity_predict / what_if with the P12 drivers panel (landscape, explain_png's split): right panel
    (RTL: read first) = the relative-probability bars with the baseline line at one; left panel = the
    per-profile φ waterfall of the chosen class."""
    r_labels = [heb(l) for l in ratio_labels]
    d_labels = [heb(l) for l in drv_labels]
    r_vals = [float(v) for v in ratios]
    d_vals = [float(v) for v in drv_values]

    def draw(fig, ax):
        # left edge sized from the longest driver label, the waterfall/_fit_labels convention —
        # a fixed 0.06 clipped "קבוצת אוכלוסייה" off the figure (P12 sweep)
        longest = max((len(str(l)) for l in d_labels), default=0)
        left = min(0.25, 0.06 + 0.011 * max(0, longest - 6))
        ax.set_position([left, 0.33, 0.46 - left, 0.50])
        ys = list(range(len(d_vals)))[::-1]
        cols = [_NOMINAL_GREY if i in neutral else (_ORANGE if v >= 0 else _TEAL)
                for i, v in enumerate(d_vals)]
        ax.barh(ys, d_vals, color=cols, height=0.6, zorder=2)
        ax.axvline(0, color=_INK_FAINT, linewidth=1, zorder=1)
        span = max(abs(v) for v in d_vals + [1e-9])
        ax.set_xlim(-span * 1.4, span * 1.4)
        for y, v in zip(ys, d_vals):
            ax.text(v + (span * 0.04 if v >= 0 else -span * 0.04), y, f"{v:+.2f}",
                    fontsize=6.5, color=_INK_SOFT, va="center", ha="left" if v >= 0 else "right")
        ax.set_yticks(ys)
        ax.set_yticklabels(d_labels, fontsize=7)
        ax.set_ylim(-0.7, len(d_vals) - 0.3)
        _style_axes(ax, xlabel_drivers)
        ax2 = fig.add_axes([0.62, 0.33, 0.35, 0.50])
        ys2 = list(range(len(r_vals)))[::-1]
        ax2.barh(ys2, r_vals, color=ratio_colors or [_TEAL] * len(r_vals), height=0.55, zorder=2)
        ax2.axvline(1.0, color=_ORANGE, linestyle="--", linewidth=1.2, zorder=1)
        xmax = max(r_vals + [1e-9])
        ax2.set_xlim(0, xmax * 1.35)
        if annot:
            for y, v, a in zip(ys2, r_vals, annot):
                ax2.text(v + xmax * 0.03, y, heb(str(a)), fontsize=7.5, color=_INK_SOFT,
                         va="center", ha="left")
        ax2.set_yticks(ys2)
        ax2.set_yticklabels(r_labels, fontsize=8)
        ax2.set_ylim(-0.7, len(r_vals) - 0.3)
        _style_axes(ax2, xlabel_ratio)

    return png(draw, figsize=(11.5, 5.8), **frame)
