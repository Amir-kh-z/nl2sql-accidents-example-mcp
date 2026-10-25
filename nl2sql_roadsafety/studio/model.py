# -*- coding: utf-8 -*-
"""The xgboost half of the studio — imported lazily, native API only (`xgb.train` / `Booster` / `DMatrix`;
`XGBRegressor` needs scikit-learn, which the [ml] extra deliberately does not pull). A missing xgboost is a
readable ActionError with the exact pip command, never a traceback."""
from __future__ import annotations

from ..sqlkit import ActionError
from . import constants


def require_xgboost():
    try:
        import xgboost  # noqa: PLC0415 — lazy on purpose

        return xgboost
    except Exception as exc:  # noqa: BLE001 — ImportError or a broken install
        raise ActionError(constants.ML_MISSING) from exc


def _dmatrix(xgb, np, X, y=None, names=None, weight=None):
    """names defaults to the SITE feature contract; the severity family passes its own (P9). `weight` is the
    per-row sample weight (class weights ride here for multi:softprob)."""
    arr = np.array([[np.nan if v is None else float(v) for v in row] for row in X], dtype=np.float64)
    return xgb.DMatrix(arr, label=(np.array(y, dtype=np.float64) if y is not None else None),
                       missing=np.nan, feature_names=list(names or constants.FEATURES),
                       weight=(np.array(weight, dtype=np.float64) if weight is not None else None))


def train(X, y, years, train_until: int, seed: int, params: dict | None = None):
    """Early stopping on a temporal inner fold (the LAST training year), then a refit on all training years with
    the best round count. Returns (raw_ubj: bytes, best_rounds: int, inner_score: float)."""
    xgb = require_xgboost()
    import numpy as np  # noqa: PLC0415 — host library, lazy

    p = dict(constants.XGB_PARAMS if params is None else params)
    p["seed"] = int(seed)
    inner_tr = [i for i, yr in enumerate(years) if yr < train_until]
    inner_va = [i for i, yr in enumerate(years) if yr == train_until]
    if not inner_tr or not inner_va:
        raise ActionError(f"train_until {train_until} leaves no inner fold (needs training years before it).")
    d_tr = _dmatrix(xgb, np, [X[i] for i in inner_tr], [y[i] for i in inner_tr])
    d_va = _dmatrix(xgb, np, [X[i] for i in inner_va], [y[i] for i in inner_va])
    bst = xgb.train(p, d_tr, num_boost_round=constants.MAX_ROUNDS, evals=[(d_va, "inner")],
                    early_stopping_rounds=constants.EARLY_STOP, verbose_eval=False)
    best = int(getattr(bst, "best_iteration", constants.MAX_ROUNDS - 1)) + 1
    inner_score = float(getattr(bst, "best_score", float("nan")))
    fit_idx = [i for i, yr in enumerate(years) if yr <= train_until]
    d_all = _dmatrix(xgb, np, [X[i] for i in fit_idx], [y[i] for i in fit_idx])
    final = xgb.train(p, d_all, num_boost_round=best)
    return bytes(final.save_raw(raw_format="ubj")), best, inner_score


def predict(raw: bytes, X) -> list[float]:
    """A fresh Booster from bytes per call — safe under the app's 40-thread pool."""
    xgb = require_xgboost()
    import numpy as np  # noqa: PLC0415

    bst = xgb.Booster()
    bst.load_model(bytearray(raw))
    return [float(v) for v in bst.predict(_dmatrix(xgb, np, X))]


def contribs(raw: bytes, X) -> list[list[float]]:
    """Per-row TreeSHAP contributions (`pred_contribs=True`): len(FEATURES) + 1 columns, bias LAST (it includes
    base_margin — P0 spike). On count:poisson the margin is log μ, so every row sums to ln(μ) — the exact-sum
    identity the tests pin. A fresh Booster per call, like predict."""
    xgb = require_xgboost()
    import numpy as np  # noqa: PLC0415

    bst = xgb.Booster()
    bst.load_model(bytearray(raw))
    out = bst.predict(_dmatrix(xgb, np, X), pred_contribs=True)
    return [[float(v) for v in row] for row in out]
