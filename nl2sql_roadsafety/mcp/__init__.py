# -*- coding: utf-8 -*-
"""The MCP channel (M1): the same actions the page runs, callable from Claude's chat.

NEVER imported by the package's __init__ — the `mcp` SDK is an optional extra, and an import error
here must not take the module's actions down (the page.py rule). `runner`, `render` and `tools`
depend on nothing but the plugin and the engine; only `server.py` imports the SDK.
"""
