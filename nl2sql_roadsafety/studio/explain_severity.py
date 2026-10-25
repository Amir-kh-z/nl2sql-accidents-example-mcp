# -*- coding: utf-8 -*-
"""TreeSHAP for the SEVERITY family (P12): multiclass `pred_contribs` over the person matrix, plus the pure
builders the explain faces share — deterministic sampling, binned beeswarm jitter, the ordered/nominal coloring
policy, `code_lookups` decoding and the per-profile waterfall parts.

Scale honesty: multiclass φ live on the SOFTMAX MARGIN scale of one class — Σφ_row + bias = the raw margin of
that class (the identity the action enforces at 1e-3 and the tests pin at 1e-4), never probability units.
xgboost 3.4.1 multiclass contribs are 3-D (n, num_class, n_features + 1), bias LAST and it includes
base_margin (the P0/P5 note holds per class).

Coloring policy (the honesty differentiator vs the report's plot): value-color ONLY genuinely ordered
features; nominal codes draw neutral grey (no fake ordinal scale); NULL (sentinel) dots draw hollow —
"לא ידוע" is a real model input, shown as such."""
from __future__ import annotations

from . import model, severity

# decision A (instructor, 2026-09-05): הרוג default, קשה selectable; קל omitted (the majority complement —
# its beeswarm is roughly the mirror of the other two)
CLASS_CHOICES = {"הרוג": 0, "פצוע קשה": 1}
CLASS_SLUGS = {0: "fatal", 1: "severe"}                # spec.basis is strict ASCII
SAMPLES = {"20k": 20000, "50k": 50000, "full": None}   # contribs are linear: 20k ~2 s, full ~30 s (spike)
SAMPLE_SEED = 20260904                                 # one fixed seed: repeated runs are byte-comparable
MAX_DOTS = 300                                         # drawn dots per beeswarm row (the table keeps all stats)
DEPENDENCE_DOTS = 2000
IDENTITY_TOL = 1e-3                                    # runtime gate; the tests pin 1e-4 on the fixture

# ordered = a color scale is honest (monotone value axis, or a binary); everything else is NOMINAL —
# road_type is a 2x2 (urban x junction), month is cyclic: neither carries a scalar order
ORDERED = ("age_group_code", "speed_limit_code", "hour_of_day", "year_idx", "day_night_code", "sex_code")
NULL_LABEL = "לא ידוע"
NOMINAL_NOTE = "קטגוריאלי — ללא סולם צבע"

# display-side sentinels (P12 sweep): codes the FROZEN matrix contract keeps as values but an honest
# display must not present as LEVELS — sex_code 0 = "לא רלוונטי" (3,797 live era rows) would otherwise
# color as the low end of an ordered scale and bias the direction corr. Masked to NULL for coloring,
# direction, shares and dependence ONLY; the model still sees the raw value (a matrix-side 0->NULL is
# a CONTRACT_VERSION bump + retrain — parked for a later phase).
DISPLAY_NULL_CODES = {"sex_code": (0,)}


def mask_display_sentinels(X, features=None):
    """A display copy of the matrix with DISPLAY_NULL_CODES masked to None. Never feed the result to
    the model — contribs run on the RAW rows; only the value-presentation layers read this."""
    feats = list(features or severity.FEATURES)
    hit = {feats.index(f): set(codes) for f, codes in DISPLAY_NULL_CODES.items() if f in feats}
    if not hit:
        return [list(r) for r in X]
    out = []
    for row in X:
        r = list(row)
        for j, codes in hit.items():
            if r[j] is not None and int(r[j]) in codes:
                r[j] = None
        out.append(r)
    return out

# code_lookups field per coded feature — involved_vehicle_type_code's labels live under the involved-side
# dictionary field `vehicle_type_code` (verified live 2026-09-05); the pure numerics have no dictionary
LOOKUP_FIELDS = {
    "casualty_type_code": "casualty_type_code", "age_group_code": "age_group_code", "sex_code": "sex_code",
    "safety_equipment_code": "safety_equipment_code", "population_group_code": "population_group_code",
    "involved_vehicle_type_code": "vehicle_type_code", "road_type_code": "road_type_code",
    "day_night_code": "day_night_code", "speed_limit_code": "speed_limit_code",
}


def lookup_sql() -> str:
    """One statement: the latest-year label per (field, code) — labels drift across years (dossier §4.2),
    the newest reading is the display convention (the P5 resolution)."""
    fields = ", ".join(f"'{f}'" for f in sorted(set(LOOKUP_FIELDS.values())))
    return (f"SELECT field, code, arg_max(label_he, year) AS label_he\n"
            f"FROM code_lookups\nWHERE field IN ({fields})\nGROUP BY field, code")


def decode_labels(ctx) -> dict:
    """{(lookup_field, code): label} — TOLERANT: decoding is garnish, a DB without code_lookups still
    explains (dots fall back to the numeric code)."""
    try:
        _, rows = ctx.query(lookup_sql())
        return {(str(r[0]), int(r[1])): str(r[2]) for r in rows if r[2] is not None}
    except Exception:  # noqa: BLE001 — the fixture/db may lack the dictionary
        return {}


def dot_label(feature: str, value, decode: dict) -> str:
    """The hover text for one dot's value: decoded Hebrew where a dictionary entry exists, the number
    otherwise, NULL always 'לא ידוע'."""
    if value is None:
        return NULL_LABEL
    field = LOOKUP_FIELDS.get(feature)
    if field is not None:
        lab = decode.get((field, int(value)))
        if lab:
            return lab
    return f"{value:g}" if isinstance(value, float) else str(value)


def contribs3(raw: bytes, X):
    """(phi (n, 3, k+1) bias last, margins (n, 3)) — a fresh Booster per call like the whole family."""
    xgb = model.require_xgboost()
    import numpy as np  # noqa: PLC0415

    bst = xgb.Booster()
    bst.load_model(bytearray(raw))
    dm = model._dmatrix(xgb, np, X, names=severity.FEATURES)
    phi = bst.predict(dm, pred_contribs=True)
    margins = bst.predict(dm, output_margin=True)
    return phi, margins


def check_identity3(phi, margins) -> float:
    """max |Σφ − margin| over rows × classes (phi includes the bias column; margins are output_margin)."""
    import numpy as np  # noqa: PLC0415

    return float(np.abs(np.asarray(phi).sum(axis=2) - np.asarray(margins)).max()) if len(phi) else 0.0


def sample_indices(n: int, size: int | None, seed: int = SAMPLE_SEED) -> list[int]:
    """Sorted deterministic sample of row indices (sorted → the matrix order survives, runs are comparable)."""
    if size is None or size >= n:
        return list(range(n))
    import numpy as np  # noqa: PLC0415

    rng = np.random.default_rng(seed)
    return sorted(int(i) for i in rng.choice(n, size=size, replace=False))


def stack_jitter(vals: list[float], cap: float = 0.36, bins: int = 48) -> list[float]:
    """Deterministic density jitter: bin the φ axis, stack dots symmetrically (0, +1, −1, +2, −2 …) within a
    bin, normalize to ±cap. Pure and rng-free — the spec rows are byte-comparable across runs."""
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    counts: dict[int, int] = {}
    steps = []
    for v in vals:
        b = int((v - lo) / span * (bins - 1))
        k = counts.get(b, 0)
        counts[b] = k + 1
        steps.append((k + 1) // 2 * (1 if k % 2 == 1 else -1))
    m = max(abs(s) for s in steps) or 1
    return [cap * s / m for s in steps]


def build_swarm(phi_cls, X, features, ordered, labels_he, decode, seed: int = SAMPLE_SEED,
                max_dots: int = MAX_DOTS) -> tuple[list[int], list[float], dict]:
    """The beeswarm's columnar dots (rows = features by mean|φ| desc; ≤ max_dots per row, deterministic
    subsample + jitter). Returns (importance order, mean|φ| per feature, dots columns). `phi_cls` is the
    (n, k) φ slice of ONE class WITHOUT the bias column; family-neutral on purpose (the site face reuses it)."""
    import numpy as np  # noqa: PLC0415

    phi_cls = np.asarray(phi_cls)
    k = len(features)
    imp = [float(np.abs(phi_cls[:, j]).mean()) if len(phi_cls) else 0.0 for j in range(k)]
    order = sorted(range(k), key=lambda j: (-imp[j], j))
    dots = {"row": [], "phi": [], "jitter": [], "value_norm": [], "is_null": [], "label": []}
    for row_i, j in enumerate(order):
        idx = list(range(len(X)))
        if len(idx) > max_dots:
            rng = np.random.default_rng(seed + 1 + j)     # per-feature stream: rows stay independent
            idx = sorted(int(i) for i in rng.choice(len(idx), size=max_dots, replace=False))
        phis = [float(phi_cls[i, j]) for i in idx]
        jit = stack_jitter(phis)
        vals = [X[i][j] for i in idx]
        known = [float(v) for v in vals if v is not None]
        lo, hi = (min(known), max(known)) if known else (0.0, 1.0)
        span = (hi - lo) or 1.0
        is_ordered = features[j] in ordered
        for p, v, jt in zip(phis, vals, jit):
            dots["row"].append(row_i)
            dots["phi"].append(round(p, 4))
            dots["jitter"].append(round(jt, 3))
            dots["value_norm"].append(None if (v is None or not is_ordered)
                                      else round((float(v) - lo) / span, 3))
            dots["is_null"].append(v is None)
            dots["label"].append(f"{labels_he[features[j]]}: {dot_label(features[j], v, decode)}")
    return order, imp, dots


def value_phi_corr(phi_cls, X, j) -> float | None:
    """Pearson corr(value, φ) over the non-null rows — the table's direction column (ordered features only;
    on a nominal code the number would fake an order, so callers never ask)."""
    import numpy as np  # noqa: PLC0415

    pairs = [(float(X[i][j]), float(phi_cls[i][j])) for i in range(len(X)) if X[i][j] is not None]
    if len(pairs) < 10:
        return None
    v = np.array([p[0] for p in pairs])
    f = np.array([p[1] for p in pairs])
    if float(v.std()) == 0.0 or float(f.std()) == 0.0:
        return 0.0
    return float(np.corrcoef(v, f)[0, 1])


def null_share(X, j) -> float:
    """Share of NULL (sentinel → 'לא ידוע') values in column j of the sample."""
    n = len(X)
    return round(sum(1 for row in X if row[j] is None) / n, 3) if n else 0.0


def build_dependence(phi_cls, X, features, j, decode, seed: int = SAMPLE_SEED,
                     max_dots: int = DEPENDENCE_DOTS) -> dict:
    """The dependence face's columns: x = the feature's value (tick index for nominals, the number for
    ordered), y = φ(f); NULL is an explicit slot on BOTH axis kinds, never dropped — the last tick on a
    nominal axis, a labelled strip right of the numeric range on an ordered one (`null_x`; the P12
    sweep's catch — x=None dots were silently skipped by every renderer). Monochrome by design. `xj` is
    the DRAWN x — slots get the deterministic stack jitter server-side (both faces share one layout,
    the page never randomizes); on an ordered axis known dots keep xj == x."""
    import numpy as np  # noqa: PLC0415

    feature = features[j]
    idx = list(range(len(X)))
    if len(idx) > max_dots:
        rng = np.random.default_rng(seed + 101 + j)
        idx = sorted(int(i) for i in rng.choice(len(idx), size=max_dots, replace=False))
    is_ordered = feature in ORDERED
    ticks = None
    slot = {}
    null_x = None
    if not is_ordered:
        codes = sorted({int(X[i][j]) for i in idx if X[i][j] is not None})
        ticks = [[c, dot_label(feature, c, decode)] for c in codes] + [[None, NULL_LABEL]]
        slot = {c: t for t, c in enumerate(codes)}
        null_x = len(slot)
    else:
        known = [float(X[i][j]) for i in idx if X[i][j] is not None]
        if any(X[i][j] is None for i in idx):
            lo, hi = (min(known), max(known)) if known else (0.0, 0.0)
            step = ((hi - lo) / 8.0) or 1.0
            null_x = round(hi + 1.5 * step, 3)
    out = {"x": [], "phi": [], "is_null": [], "label": []}
    for i in idx:
        v = X[i][j]
        if is_ordered:
            out["x"].append(None if v is None else float(v))
        else:
            out["x"].append(null_x if v is None else slot[int(v)])
        out["phi"].append(round(float(phi_cls[i][j]), 4))
        out["is_null"].append(v is None)
        out["label"].append(dot_label(feature, v, decode))
    if is_ordered:
        xj = list(out["x"])
        nulls = [p for p, b in enumerate(out["is_null"]) if b]
        if nulls:
            known_max = max((v for v in out["x"] if v is not None), default=0.0)
            step = (abs(null_x - known_max) / 1.5) or 1.0    # the 1.5-step gap null_x was built with
            jit = stack_jitter([out["phi"][p] for p in nulls], cap=0.45 * step)
            for p, jt in zip(nulls, jit):
                xj[p] = round(null_x + jt, 3)
        out["xj"] = xj
    else:
        by_slot: dict[int, list[int]] = {}
        for pos, x in enumerate(out["x"]):
            by_slot.setdefault(int(x), []).append(pos)
        xj = [0.0] * len(out["x"])
        for s, positions in sorted(by_slot.items()):
            jit = stack_jitter([out["phi"][p] for p in positions], cap=0.30)
            for p, jt in zip(positions, jit):
                xj[p] = round(s + jt, 3)
        out["xj"] = xj
    return {"feature": feature, "ordered": is_ordered, "ticks": ticks,
            "null_x": (null_x if any(out["is_null"]) else None), "null_label": NULL_LABEL, **out}


def waterfall_parts(phi_row, features, labels_he, k: int = 5):
    """One profile's drivers: top-k φ by |φ| (ties on contract order), the rest folded into 'היתר', bias last.
    `phi_row` is the (n_features + 1) φ vector of ONE class INCLUDING the bias column. The parts sum to the
    row's raw margin — the same identity, per profile (a test pins it)."""
    body = [float(v) for v in phi_row[:len(features)]]
    bias = float(phi_row[len(features)])
    order = sorted(range(len(features)), key=lambda j: (-abs(body[j]), j))
    top = [{"feature": features[j], "label": labels_he[features[j]], "phi": round(body[j], 4)}
           for j in order[:k]]
    rest = round(sum(body[j] for j in order[k:]), 4)
    return top, rest, round(bias, 4)
