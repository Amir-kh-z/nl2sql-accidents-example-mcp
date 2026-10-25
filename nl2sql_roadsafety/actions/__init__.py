# -*- coding: utf-8 -*-
"""One module per action. Each defines `run` first and `ACTION` as its LAST statement
(`Action(run=run)` is evaluated at import time — a forward reference is a NameError that the app
turns into a Problem card)."""
