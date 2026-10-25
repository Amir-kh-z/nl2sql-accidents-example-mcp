# -*- coding: utf-8 -*-
"""The studio: the site model's panel, gate, registry, predictor and the findings ledger.

Nothing here imports xgboost (or any heavy library) at module level — the app's discover() imports the package on
every request. xgboost is imported inside `model.require_xgboost()` only, and its absence is a readable error with
the exact pip command, never a crash.
"""
