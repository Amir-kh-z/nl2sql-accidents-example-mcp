# -*- coding: utf-8 -*-
"""The validation gate and the ranking arithmetic — pure Python, no scipy, unit-tested on worked examples.

Spearman >= 0.3 and calibration within +-25% come from the methodology report; the overfit rule (mean per-row
Poisson deviance holdout/train <= 1.5) is the plugin's operationalisation of the report's unspecified overfit bound
— MEAN, not sum, because the panel grows yearly — and every card labels it as the plugin's rule."""
from __future__ import annotations

import math

from . import constants


def _ranks(values):
    """Average ranks (1-based) with ties."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(a, b) -> float:
    """Spearman rho via Pearson over average ranks; a constant side gives 0.0 (no ranking information)."""
    if len(a) != len(b) or len(a) < 2:
        return 0.0
    ra, rb = _ranks(list(a)), _ranks(list(b))
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def poisson_deviance_mean(y, mu) -> float:
    """Mean per-row Poisson deviance: d = 2*(y*ln(y/mu) - (y - mu)), the y*ln term 0 when y = 0; mu floored."""
    total = 0.0
    for yi, mi in zip(y, mu):
        m = max(float(mi), 1e-9)
        term = yi * math.log(yi / m) if yi > 0 else 0.0
        total += 2.0 * (term - (yi - m))
    return total / max(len(y), 1)


def calibration(y, mu):
    """Sum(mu)/Sum(y) — None when the observed sum is zero (no basis)."""
    sy = float(sum(y))
    return (float(sum(mu)) / sy) if sy > 0 else None


def alpha_moments(y, mu) -> float:
    """NB dispersion by moments on residuals: alpha = max(0, (Sum((y-mu)^2/mu) - n) / Sum(mu))."""
    n = len(y)
    if n == 0:
        return 0.0
    s = sum((yi - mi) ** 2 / max(float(mi), 1e-9) for yi, mi in zip(y, mu))
    denom = float(sum(mu))
    if denom <= 0:
        return 0.0
    return max(0.0, (s - n) / denom)


def evaluate(y, mu, years, train_until: int) -> dict:
    """The gate metrics over the holdout (years > train_until) plus the train-side deviance."""
    tr = [i for i, yr in enumerate(years) if yr <= train_until]
    ho = [i for i, yr in enumerate(years) if yr > train_until]
    y_ho, mu_ho = [y[i] for i in ho], [mu[i] for i in ho]
    y_tr, mu_tr = [y[i] for i in tr], [mu[i] for i in tr]
    dev_ho = poisson_deviance_mean(y_ho, mu_ho)
    dev_tr = poisson_deviance_mean(y_tr, mu_tr)
    return {
        "n": len(ho), "n_train": len(tr),
        "sum_obs": int(sum(y_ho)), "sum_mu": round(float(sum(mu_ho)), 1),
        "spearman": round(spearman(y_ho, mu_ho), 3),
        "calibration": round(calibration(y_ho, mu_ho), 3) if calibration(y_ho, mu_ho) is not None else None,
        "deviance_holdout": round(dev_ho, 4), "deviance_train": round(dev_tr, 4),
        "deviance_ratio": round(dev_ho / dev_tr, 3) if dev_tr > 0 else None,
        "alpha": round(alpha_moments(y_ho, mu_ho), 3),
    }


def verdict(metrics: dict) -> tuple[str, list[str]]:
    """('validated'|'rejected', reasons in Hebrew, no ';')."""
    reasons = []
    smin, _ = constants.GATE["spearman_min"]
    (clo, chi), _ = constants.GATE["calibration"]
    dmax, _ = constants.GATE["deviance_ratio_max"]
    if metrics["spearman"] < smin:
        reasons.append(f"Spearman {metrics['spearman']:g} מתחת ל-{smin:g}")
    c = metrics["calibration"]
    if c is None:
        reasons.append("אין תצפיות בשנות האימות — לא ניתן לכייל")
    elif not clo <= c <= chi:
        direction = "יותר" if c > 1 else "פחות"
        reasons.append(f"כיול {c:g} מחוץ ל-{clo:g}–{chi:g} (המודל צופה {abs(c - 1) * 100:.0f}% {direction} מהנצפה)")
    r = metrics["deviance_ratio"]
    if r is None or r > dmax:
        reasons.append(f"יחס סטייה {r if r is not None else 'לא מוגדר'} מעל {dmax:g} (כלל התוסף)")
    return ("validated" if not reasons else "rejected", reasons)


def roc_curve(y, score):
    """ROC diagnostics for the gate's chart face — REPORTED, never gating (verdict() above is untouched).

    Positive class (plugin-defined, deterministic, no RNG): observed count in the TOP DECILE — the threshold is
    the value at the 90th percentile of sorted y (index (9*n)//10, ascending) and every y >= it is positive,
    ties at the threshold included. The curve collapses TIED SCORES to one step per distinct score, so the
    trapezoid over the returned points equals the Mann-Whitney average-rank AUC; the AUC returned here is
    computed by that rank statistic directly (cross-pinned against severity.auc_binary in tests). A per-row
    staircase that steps inside a tie group would NOT be that statistic — the inspiration source's version has
    exactly that flaw, so this is a reimplementation, not a copy.

    Returns (fpr, tpr, auc, info) with info = {positive_n, share, threshold, rule}; returns None when the
    positive class is degenerate (every row positive, or fewer than two rows) — the caller degrades with a
    caveat, never an error."""
    n = len(y)
    if n < 2 or len(score) != n:
        return None
    ys = sorted(float(v) for v in y)
    thr = ys[(9 * n) // 10]
    labels = [float(v) >= thr for v in y]
    pos = sum(1 for lab in labels if lab)
    neg = n - pos
    if pos == 0 or neg == 0:                       # all-positive (constant y) or all-negative — degenerate
        return None
    scores = [float(s) for s in score]
    order = sorted(range(n), key=lambda i: -scores[i])
    fpr, tpr = [0.0], [0.0]
    tp = fp = 0
    i = 0
    while i < n:                                   # one step per DISTINCT score — ties collapse
        j = i
        while j + 1 < n and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for k in range(i, j + 1):
            if labels[order[k]]:
                tp += 1
            else:
                fp += 1
        tpr.append(tp / pos)
        fpr.append(fp / neg)
        i = j + 1
    ranks = _ranks(scores)                         # Mann-Whitney with average ranks — the exact AUC
    rank_sum_pos = sum(r for r, lab in zip(ranks, labels) if lab)
    auc = (rank_sum_pos - pos * (pos + 1) / 2.0) / (pos * neg)
    info = {"positive_n": pos, "share": round(pos / n, 4), "threshold": thr, "rule": "top-decile-observed"}
    return fpr, tpr, auc, info


def nb_interval(mu_by_year, alpha: float) -> tuple[float, float]:
    """90% interval for the sum over years: normal approx with Var = Sum(mu_t + alpha*mu_t^2), independence across
    years assumed (said in the caveat); alpha = 0 collapses to Poisson. lo floored at 0."""
    mu = float(sum(mu_by_year))
    var = sum(float(m) + alpha * float(m) ** 2 for m in mu_by_year)
    sd = math.sqrt(max(var, 0.0))
    return max(0.0, mu - constants.Z90 * sd), mu + constants.Z90 * sd


def eb(mu: float, observed: float, alpha: float) -> float:
    """EB estimate: w*mu + (1-w)*observed with w = 1/(1 + alpha*mu)."""
    w = 1.0 / (1.0 + alpha * mu) if mu >= 0 else 1.0
    return w * mu + (1.0 - w) * observed
