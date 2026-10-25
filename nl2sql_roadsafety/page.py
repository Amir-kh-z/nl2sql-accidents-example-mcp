# -*- coding: utf-8 -*-
"""The `nl2sql.pages` hook: where the built page lives and how the sidebar names it.

Standard library only, and never imported by the package's __init__: loading this entry point imports the parent
package anyway, so this module must not add a failure of its own (no engine, no matplotlib, no data access).
The entry-point name (`roadsafety`) is the URL segment `/page/roadsafety/` and equals the Vite `base`.
"""
from pathlib import Path


def page():
    return {"path": str(Path(__file__).resolve().parent / "webdist"), "label": "🚦 מעבדת הבטיחות בדרכים"}
