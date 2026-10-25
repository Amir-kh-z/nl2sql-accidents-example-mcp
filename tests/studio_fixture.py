# -*- coding: utf-8 -*-
"""The studio's synthetic panel DB — deterministic (an LCG, no `random`), no CBS data. 60 segments over 2016–2024
whose casualty counts follow a KNOWN Poisson rate built from the planted features, so a doc-11 model must pass the
gate and a shuffled-target model must fail it (margins are wide by construction: Spearman ≈ 0.8 vs ≈ −0.2).

Planted per segment index j (road 1–4 × 15 segments):
    adt = 5000 + 900·j · night share = 0.15 + 0.5·((7j) mod 10)/10 · junction share = 0.1 + 0.6·((3j) mod 5)/5
    λ(year) = adt/6000 · (1 + 1.5·night) · (1 + 0.5·junction) · (0.8 in 2020)
As-of coverage is deliberately uneven: j % 4 == 3 → never measured (static geometry + ADT fill), j % 4 == 2 →
measured from 2021 only, else 2017–2024; one overlapping vintage on j == 0 (the units CTE must discard it).
`drop_after=y` removes casualty rows after y — the leakage test's counterfactual."""
from __future__ import annotations

import datetime as dt
import math

from conftest import CODE_LOOKUPS, DDL

SEED = 20260830
PER_ROAD = 15
YEARS = range(2016, 2025)


class LCG:
    """Knuth MMIX linear congruential generator — deterministic across Python versions and platforms."""

    def __init__(self, seed: int = SEED):
        self.x = seed & 0xFFFFFFFFFFFFFFFF

    def u(self) -> float:
        self.x = (6364136223846793005 * self.x + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return self.x / 2**64


def _poisson(lcg: LCG, lam: float) -> int:
    """Knuth's product method (λ is small here)."""
    limit = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= lcg.u()
        if p <= limit:
            return k
        k += 1


def segments():
    out = []
    for road in (1, 2, 3, 4):
        for i in range(PER_ROAD):
            j = (road - 1) * PER_ROAD + i
            out.append({
                "j": j, "road": road, "seg": 10 * i + 10,
                "km0": 100.0 * i, "km1": 100.0 * i + 8.0,
                "adt": 5000.0 + 900.0 * j,
                "night": 0.15 + 0.5 * ((7 * j) % 10) / 10,
                "junction": 0.1 + 0.6 * ((3 * j) % 5) / 5,
            })
    return out


def lam(s: dict, year: int) -> float:
    return s["adt"] / 6000.0 * (1 + 1.5 * s["night"]) * (1 + 0.5 * s["junction"]) * (0.8 if year == 2020 else 1.0)


def build_studio_db(path, drop_after: int | None = None) -> None:
    import duckdb

    con = duckdb.connect(str(path))
    for stmt in DDL.strip().split(";"):
        if stmt.strip():
            con.execute(stmt)
    lcg = LCG()
    acc = []
    aid = 0

    def acc_row(s, year, case, sev, rt, km, dn, shape, single, dual, surface, speed):
        nonlocal aid
        aid += 1
        road_km = round(km * 10.0, 1)                      # stored in 100-m units, never 0 (km >= 0.1)
        lat, lon = 31.0 + road_km / 10000.0, 34.2 + s["road"] / 100.0
        month = 1 + aid % 12
        return (aid, case, year, month, dt.date(year, month, 15), sev, {1: "קטלנית", 2: "קשה", 3: "קלה"}[sev],
                rt, "-", s["road"], road_km, 0, None, 0, 0, None, None, None, 1, "בהיר", dn,
                {1: "יום", 5: "לילה"}[dn], 10, dt.datetime(year, month, 15, 10, 0), None, lat, lon, "יבש",
                shape, single, dual, surface, speed)

    for s in segments():
        for year in YEARS:
            n = _poisson(lcg, lam(s, year))
            for _ in range(n):
                if drop_after is not None and year > drop_after:
                    for _skip in range(5):                 # km, junction, night, severity, surface — keep the stream aligned
                        lcg.u()
                    continue
                km = s["km0"] + 0.1 + lcg.u() * (s["km1"] - s["km0"] - 0.2)
                at_junction = lcg.u() < s["junction"]
                night = lcg.u() < s["night"]
                r = lcg.u()
                sev = 1 if r < 0.03 else (2 if r < 0.15 else 3)
                acc.append(acc_row(s, year, 1, sev, 3 if at_junction else 4, km, 5 if night else 1,
                                   8, 2 if s["j"] % 2 else 0, 0 if s["j"] % 2 else 3,
                                   2 if lcg.u() < 0.1 else 1, 4 + s["j"] % 3))
            for _ in range(_poisson(lcg, 2.0)):            # damage-only rows: live-like uncoded values
                km = s["km0"] + 0.1 + lcg.u() * (s["km1"] - s["km0"] - 0.2)
                acc.append(acc_row(s, year, 3, 3, 4, km, 1, 9, 9, 0, 9, 0))
    con.executemany("INSERT INTO accidents VALUES (" + ",".join("?" * 33) + ")", acc)

    adt_rows, seg_rows = [], []
    for s in segments():
        first = None if s["j"] % 4 == 3 else (2021 if s["j"] % 4 == 2 else 2017)
        if first is not None:
            for year in range(first, 2025):
                adt_rows.append((s["road"], s["seg"], s["km0"], s["km1"], year, s["adt"], year, 0))
        if s["j"] == 0:                                    # an overlapping, worse vintage the units CTE must discard
            adt_rows.append((s["road"], s["seg"], s["km0"], s["km1"] + 4.0, 2020, s["adt"] * 1.2, 2018, 2))
            seg_rows.append((s["road"], s["seg"], s["km0"], s["km1"] + 4.0, "מ-א", "מ-ב", "interurban", "loop",
                             2018, dt.datetime(2018, 1, 1)))
        seg_rows.append((s["road"], s["seg"], s["km0"], s["km1"], f"מקטע {chr(0x5D0 + s['j'] % 22)}", "סוף",
                         "interurban", "loop", 2020, dt.datetime(2020, 1, 1)))
    con.executemany("INSERT INTO traffic_adt_asof VALUES (?,?,?,?,?,?,?,?)", adt_rows)
    con.executemany("INSERT INTO traffic_segments VALUES (?,?,?,?,?,?,?,?,?,?)", seg_rows)

    # ── P9: person rows for the SEVERITY family — a SEPARATE LCG so every pinned accident stream stays
    # byte-identical. Planted signal on exactly the person-12 features: night, pedestrian/motorcycle,
    # no-safety-equipment and a high speed limit multiply the killed/severe odds, so a person-12 model must
    # clear the discrimination gate and a shuffled-target model must fail it.
    sev_lcg = LCG(SEED + 1)
    inv = []
    for a in acc:
        if a[1] != 1:                                       # casualty series only
            continue
        aid_, year_, month_ = a[0], a[2], a[3]
        night_ = a[20] == 5
        speed_hi = a[32] >= 5
        for pid in range(1, 2 + (sev_lcg.u() < 0.5)):
            r = sev_lcg.u()
            ctype = 1 if r < 0.15 else (4 if r < 0.25 else (2 if r < 0.70 else 3))
            safety = 4 if sev_lcg.u() < 0.30 else 1
            age = 1 + int(sev_lcg.u() * 18)
            sex = 1 if sev_lcg.u() < 0.6 else 2
            # margins wide BY CONSTRUCTION (the site fixture's principle): a low-risk cell is ~1 % killed,
            # a fully-loaded one ~60 % — the gate must be passable on real signal, not tuned to noise
            pk, ps = 0.008, 0.04
            for cond, mk, ms in ((night_, 3.5, 2.4), (ctype in (1, 4), 6.0, 3.2),
                                 (safety == 4, 5.0, 2.4), (speed_hi, 2.2, 1.8)):
                if cond:
                    pk, ps = pk * mk, ps * ms
            pk, ps = min(pk, 0.7), min(ps, 0.28)
            r2 = sev_lcg.u()
            inj = 1 if r2 < pk else (2 if r2 < pk + ps else 3)
            veh = 9 if ctype == 4 else (None if ctype == 1 else 1)
            inv.append((aid_, 1, pid, 1, year_, month_, inj, {1: "הרוג", 2: "פצוע קשה", 3: "פצוע קל"}[inj],
                        ctype, None, age, None, veh, None, sex, None, safety, 1 + (sev_lcg.u() < 0.3)))
    con.executemany("INSERT INTO involved VALUES (" + ",".join("?" * 18) + ")", inv)
    # P12: the decode dictionary (severity_explain hover labels) — same slice as the plain fixture
    con.executemany("INSERT INTO code_lookups VALUES (?,?,?,?,?)", CODE_LOOKUPS)
    con.close()
