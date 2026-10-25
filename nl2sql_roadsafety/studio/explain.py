# -*- coding: utf-8 -*-
"""TreeSHAP helpers for `studio_explain` — pure functions over the φ matrix (`model.contribs`), plus the site-key
→ (road, seg) resolution. The φ values live on the LOG-RATE scale (count:poisson margin): Σφ_row = ln μ_row —
the exact-sum identity `tests/test_explain.py` pins."""
from __future__ import annotations

import math
import re

from ..sqlkit import STATIC_GEOMETRY_CTE, Refusal, parse_site_key
from . import constants

_ROAD_SEG = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")


def mean_abs_phi(phi: list[list[float]]) -> list[float]:
    """Mean |φ| per FEATURE column (the bias column is excluded)."""
    n = len(phi)
    k = len(constants.FEATURES)
    return [sum(abs(row[j]) for row in phi) / n for j in range(k)] if n else [0.0] * k


def mean_phi(phi: list[list[float]]) -> list[float]:
    n = len(phi)
    k = len(constants.FEATURES)
    return [sum(row[j] for row in phi) / n for j in range(k)] if n else [0.0] * k


def top_k(importance: list[float], k: int = constants.EXPLAIN_TOP_K) -> list[int]:
    """Indices of the k largest importances, largest first; ties break on doc-11 order (deterministic)."""
    order = sorted(range(len(importance)), key=lambda j: (-importance[j], j))
    return order[:k]


IDENTITY_TOL = 1e-3                        # the action refuses to ship φ that don't sum to ln μ within this


def check_identity(phi: list[list[float]], mu: list[float]) -> float:
    """max |Σφ − ln μ| over the rows. The ACTION enforces it against IDENTITY_TOL on every run (a corrupt or
    foreign artifact must fail loudly, not explain wrongly); the tests pin it tighter (1e-4)."""
    worst = 0.0
    for row, m in zip(phi, mu):
        worst = max(worst, abs(sum(row) - math.log(max(m, 1e-12))))
    return worst


def resolve_site(ctx, site: str) -> tuple[int, int]:
    """'60/836' (road/seg) or a `road:60/96.0-98.8` site key → the panel key (road, seg). Junction keys refuse —
    the site model covers interurban segments only."""
    s = str(site or "").strip()
    m = _ROAD_SEG.match(s)
    if m:
        return int(m.group(1)), int(m.group(2))
    parsed = parse_site_key(s)  # raises ActionError on malformed input
    if parsed.kind != "road":
        raise Refusal("מודל האתר מכסה מקטעים לא-עירוניים בלבד — אין הסבר מודל לצמתים",
                      ["hotspot_map (unit = njunctions / ujunctions) לספירות", "before_after לצומת עם בקרה"])
    sql = (f"WITH {STATIC_GEOMETRY_CTE}\n"
           f"SELECT road, seg FROM latest_segments WHERE road = {int(parsed.road)}"
           f" AND abs(km_from - {float(parsed.km_from)}) < 0.051 AND abs(km_to - {float(parsed.km_to)}) < 0.051")
    rows = ctx.query(sql)[1]
    if not rows:
        raise Refusal(f"לא נמצא מקטע עם המפתח {s} בגיאומטריה העדכנית",
                      ["site_ranking — עמודת site_key נותנת את המפתח המדויק", "אפשר גם road/seg, למשל 60/836"])
    return int(rows[0][0]), int(rows[0][1])
