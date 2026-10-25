# -*- coding: utf-8 -*-
"""Every action through the REAL Registry — default-filling and validation are the core's, exactly
as they will be in the app."""
from __future__ import annotations

import base64
import json
from importlib.metadata import entry_points

import pytest
from nl2sql_engine.modules import Registry

from nl2sql_roadsafety import MODULE

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

installed = any(ep.name == "roadsafety" for ep in entry_points(group="nl2sql.modules"))
needs_install = pytest.mark.skipif(not installed, reason="pip install -e . first")


def run(ctx, action, **inputs):
    reg = Registry()
    reg.modules.append(MODULE)
    return reg.run("roadsafety", action, ctx, inputs)


def json_safe(result) -> str:
    return json.dumps(result.to_dict(), allow_nan=False, ensure_ascii=False)


def png_of(spec) -> bytes:
    assert spec["renderer"] == "png"
    raw = base64.b64decode(spec["png_base64"])
    assert raw.startswith(PNG_MAGIC), "not a PNG"
    assert len(raw) > 2000, "suspiciously small image"
    return raw


def lines_of(result) -> list[str]:
    return str(result.data).split("\n")
