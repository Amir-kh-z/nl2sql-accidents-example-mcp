# -*- coding: utf-8 -*-
"""Find a site by NAME (M2). Phase A, question 4: asked about "צומת העשור", the model had no way to reach the
junction's code, so it never called the site profile. The site tools take keys — `60/836`, `road:60/96.0-98.8`,
`njunction:433`, `ujunction:5000/777` — and this helper turns a name fragment into those keys.

A navigation helper, not an instrument: it reads dimension and name columns through `ctx.query` (the engine's
read-only guardrail), constructs no Result and writes no ledger line (the audit line of the tool call is its
trace). Names come from the data (segment and junction names, city names, street names) — dimension data,
credited like everything else."""
from __future__ import annotations

from ..envelope import CREDIT
from ..sqlkit import JUNCTION_SENTINEL_CODES, slit

KINDS = ("all", "segments", "njunctions", "ujunctions", "cities")
MIN_QUERY = 2
MAX_LIMIT = 25


def _pattern(q: str) -> str:
    """A safe ILIKE pattern: the user's text as a literal substring (its own % and _ escaped)."""
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return slit(f"%{esc}%") + " ESCAPE '\\'"


def _sql(kind: str, q: str, limit: int) -> str:
    pat = _pattern(q)
    sentinels = ", ".join(str(c) for c in JUNCTION_SENTINEL_CODES)
    if kind == "segments":
        return f"""
SELECT road, seg, arg_max(name_from, src_year) AS name_from, arg_max(name_to, src_year) AS name_to,
       arg_max(km_from, src_year) AS km_from, arg_max(km_to, src_year) AS km_to
FROM traffic_segments
WHERE name_from ILIKE {pat} OR name_to ILIKE {pat}
GROUP BY road, seg ORDER BY road, seg LIMIT {limit}"""
    if kind == "njunctions":
        return f"""
SELECT junction_code, min(junction_name) AS name, min(least(road1_number, road2_number)) AS road1,
       max(greatest(road1_number, road2_number)) AS road2
FROM dim_junction_nonurban
WHERE junction_name ILIKE {pat}
GROUP BY junction_code ORDER BY junction_code LIMIT {limit}"""
    if kind == "ujunctions":
        return f"""
SELECT city_code, urban_junction_code, any_value(city_name) AS city, min(street1_name) AS street1,
       min(street2_name) AS street2, count(*) AS casualty_accidents
FROM accidents
WHERE case_type_code = 1 AND urban_junction_code IS NOT NULL AND urban_junction_code NOT IN ({sentinels})
  AND (street1_name ILIKE {pat} OR street2_name ILIKE {pat} OR city_name ILIKE {pat})
GROUP BY city_code, urban_junction_code ORDER BY casualty_accidents DESC, city_code, urban_junction_code LIMIT {limit}"""
    if kind == "cities":
        return f"""
SELECT city_code, city_name_he, city_name_en, region_name
FROM dim_settlement
WHERE city_name_he ILIKE {pat} OR city_name_en ILIKE {pat}
ORDER BY city_code LIMIT {limit}"""
    raise ValueError(kind)


def find(ctx, query: str, kind: str = "all", limit: int = 10) -> str:
    """Markdown text: for each kind, the matches with the site key the other tools accept."""
    q = (query or "").strip()
    if len(q) < MIN_QUERY:
        return f"# ❌ חיפוש קצר מדי\nהקלידו לפחות {MIN_QUERY} תווים משם מקטע, צומת, רחוב או יישוב."
    if kind not in KINDS:
        return f"# ❌ סוג חיפוש לא מוכר\nאחד מ: {', '.join(KINDS)}"
    limit = max(1, min(int(limit or 10), MAX_LIMIT))
    kinds = [k for k in KINDS if k != "all"] if kind == "all" else [kind]
    out = [f"# חיפוש אתר: «{q}»"]
    total = 0
    for k in kinds:
        cols, rows = ctx.query(_sql(k, q, limit))
        if not rows:
            continue
        total += len(rows)
        if k == "segments":
            out.append("## מקטעי כביש (traffic_segments) — המפתח ל-roadsafety_site / roadsafety_sites")
            for road, seg, nf, nt, k0, k1 in rows:
                out.append(f"- {nf} – {nt} · כביש {road} · ק״מ {k0}–{k1} · מפתח: `{road}/{seg}` או "
                           f"`road:{road}/{k0}-{k1}`")
        elif k == "njunctions":
            out.append("## צמתים לא-עירוניים (dim_junction_nonurban) — ללא מכנה חשיפה, ללא מדדי מודל")
            for code, name, r1, r2 in rows:
                roads = " / ".join(str(r) for r in (r1, r2) if r is not None)
                out.append(f"- {name} · כבישים {roads} · מפתח: `njunction:{code}`")
        elif k == "ujunctions":
            out.append("## צמתים עירוניים (לפי רחובות/יישוב בתאונות עם נפגעים) — ללא מכנה חשיפה")
            for city_code, code, city, s1, s2, n in rows:
                streets = " / ".join(s for s in (s1, s2) if s)
                out.append(f"- {city} · {streets} · {n:,} תאונות עם נפגעים · מפתח: `ujunction:{city_code}/{code}`")
        elif k == "cities":
            out.append("## יישובים (dim_settlement) — ל-roadsafety_sites rank_by=cities ולמפתחות ujunction")
            for code, he, en, region in rows:
                out.append(f"- {he}{f' ({en})' if en else ''} · {region or ''} · קוד יישוב {code}")
    if total == 0:
        out.append("לא נמצאו התאמות. נסו חלק קצר יותר מהשם, או שם צומת/מחלף כפי שמופיע בשלטים.")
    else:
        out.append(f"({total} התאמות, עד {limit} לכל סוג)")
    out.append(CREDIT)
    return "\n".join(out)
