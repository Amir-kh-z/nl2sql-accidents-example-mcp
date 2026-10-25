# -*- coding: utf-8 -*-
"""One constants block for the whole studio: the feature contract, the panel window, the training params and the
validation gate. Every threshold carries its source (the methodology report, or a plugin-chosen operationalisation
that every card must label as such). Read these THROUGH the module (`constants.X`) wherever a test may monkeypatch."""
from __future__ import annotations

# the doc-11 feature preset, in the exact order the matrix and the model contract use
FEATURES = ("adt_asof", "adt_known", "lag1", "pct_night", "pct_single_carr", "pct_at_junction",
            "pct_curve", "pct_wet_surface", "speed_mix", "years_active", "year_idx")
STATIC_FEATURES = FEATURES[3:10]           # frozen per segment from ALL records 2005..train_until (both series)
PRESETS = {
    "doc-11": "the methodology report's eleven features",
    "shuffled": "doc-11 with the TRAINING target permuted (a straw-man model that must fail the gate)",
}

PANEL_YEARS = (2017, 2024)                 # the full segment x year grid (as-of exposure era)
LAG_FEED_YEAR = 2016                       # lag1 for 2017 comes from 2016 counts on the panel geometry
HISTORY_START = 2005                       # static attributes pool starts here
TRAIN_UNTIL = (2018, 2023)                 # >= 1 inner-fold year after 2017 and >= 1 holdout year <= 2024
TRAIN_UNTIL_DEFAULT = 2023                 # 2022 is REJECTED by the gate on live (calibration 1.35: the 2023-24
                                           # casualty decline is outside what the features carry) - a deliberate,
                                           # recorded deviation from the planning docs' 2022

XGB_PARAMS = {"objective": "count:poisson", "max_depth": 2, "eta": 0.05, "min_child_weight": 5,
              "reg_lambda": 1.0, "subsample": 0.8, "colsample_bytree": 0.8, "nthread": 4, "verbosity": 0}
MAX_ROUNDS, EARLY_STOP = 1000, 30

# gate: value, source ("report" = the methodology report; "plugin" = plugin-chosen, labelled in every card)
GATE = {
    "spearman_min": (0.3, "report"),
    "calibration": ((0.75, 1.25), "report"),
    "deviance_ratio_max": (1.5, "plugin"),
}
Z90 = 1.6449                               # 90% two-sided normal quantile for the NB interval

# Hebrew feature labels for legends and tables (digit-free — the envelope's label rule), doc-11 order
FEATURE_LABELS_HE = {
    "adt_asof": "נפח תנועה (ADT)", "adt_known": "נפח תנועה ידוע", "lag1": "תאונות בשנה הקודמת",
    "pct_night": "שיעור לילה", "pct_single_carr": "שיעור חד-מסלולי", "pct_at_junction": "שיעור בצומת",
    "pct_curve": "שיעור עקומה", "pct_wet_surface": "שיעור כביש רטוב", "speed_mix": "תמהיל מהירות",
    "years_active": "שנות פעילות", "year_idx": "מדד שנה",
}
BIAS_LABEL_HE = "בסיס המודל"                # the pred_contribs bias column (includes base_margin)
EXPLAIN_TOP_K = 5

CONTRACT_VERSION = 1
FAMILY_SITE = "site"
ML_EXTRA_CMD = '..\\app\\.venv\\Scripts\\python -m pip install "nl2sql-roadsafety-lab[ml]"'
ML_MISSING = ("xgboost is not installed - the studio's ML actions need the [ml] extra. "
              "Run: " + ML_EXTRA_CMD + " (from the workspace root; then restart the app). "
              "Python >= 3.12 is required by xgboost.")
