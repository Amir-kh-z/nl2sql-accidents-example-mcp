# -*- coding: utf-8 -*-
"""M3 — the web channel: streamable HTTP behind the self-contained OAuth server, exercised the way claude.ai
exercises it (metadata → dynamic client registration → authorize → our login page → code → token → MCP calls
with a bearer), plus the refusals (no token, wrong passphrase, expired code, foreign host)."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlparse

import pytest

mcp = pytest.importorskip("mcp")
from starlette.testclient import TestClient                                   # noqa: E402

from nl2sql_roadsafety.mcp import server as srv                                # noqa: E402
from nl2sql_roadsafety.mcp.runner import Runner                                # noqa: E402
from nl2sql_roadsafety.mcp.tools import TOOL_ACTIONS                           # noqa: E402
from nl2sql_roadsafety.mcp.web import (ENV_PASSPHRASE, PassphraseProvider, WebConfig, build_web_server,  # noqa: E402
                                       web_config_from_env)

PUBLIC = "https://lab.example.test"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
PASS = "sodi-sodot-123"
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def audit_lines(runner: Runner) -> list[dict]:
    p = runner.audit_path()
    return [json.loads(l) for l in p.read_text("utf-8").splitlines() if l.strip()] if p.exists() else []


@pytest.fixture()
def web(ctx, tmp_path):
    cfg = WebConfig(public_url=PUBLIC, passphrase=PASS, store_path=tmp_path / "web" / "oauth.json")
    runner = Runner(ctx.db_path, channel="web")
    server = build_web_server(runner, cfg)
    args = argparse.Namespace(port=8765)
    app = server.streamable_http_app(json_response=True, transport_security=srv.transport_security(args, cfg))
    with TestClient(app, base_url=PUBLIC) as client:
        yield client, server, cfg, runner


# ── the OAuth dance, step by step ──────────────────────────────────────────────────────────────────────
def register(c) -> str:
    r = c.post("/register", json={"redirect_uris": [REDIRECT], "token_endpoint_auth_method": "none",
                                   "client_name": "claude.ai test", "grant_types": ["authorization_code", "refresh_token"],
                                   "response_types": ["code"]})
    assert r.status_code == 201, r.text
    return r.json()["client_id"]


def login(c, client_id: str, challenge: str, *, state="xyz", passphrase=PASS, name="אמיר") -> dict:
    r = c.get("/authorize", params={"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
                                    "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
                                    "resource": PUBLIC + "/mcp"}, follow_redirects=False)
    assert r.status_code == 302, r.text
    loc = r.headers["location"]
    assert loc.startswith(PUBLIC + "/login?lid="), loc
    lid = parse_qs(urlparse(loc).query)["lid"][0]
    form = c.get("/login", params={"lid": lid})
    assert form.status_code == 200 and "מעבדת הבטיחות" in form.text and 'name="passphrase"' in form.text
    r = c.post("/login", data={"lid": lid, "name": name, "passphrase": passphrase}, follow_redirects=False)
    return {"status": r.status_code, "location": r.headers.get("location", ""), "text": r.text, "lid": lid}


def token(c, client_id: str, code: str, verifier: str) -> dict:
    r = c.post("/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
                               "client_id": client_id, "code_verifier": verifier})
    return {"status": r.status_code, **(r.json() if r.headers.get("content-type", "").startswith("application/json") else {})}


def rpc(c, bearer: str | None, method: str, params: dict | None = None, *, rid=1, session=None, proto=None):
    headers = dict(MCP_HEADERS)
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if session:
        headers["Mcp-Session-Id"] = session
    if proto:
        headers["MCP-Protocol-Version"] = proto
    body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if rid is not None:
        body["id"] = rid
    return c.post("/mcp", json=body, headers=headers)


def full_login(c) -> tuple[str, str, dict]:
    client_id = register(c)
    verifier, challenge = pkce()
    done = login(c, client_id, challenge)
    assert done["status"] == 302, done["text"]
    q = parse_qs(urlparse(done["location"]).query)
    assert done["location"].startswith(REDIRECT) and q["state"] == ["xyz"] and q["iss"] == [PUBLIC]
    tok = token(c, client_id, q["code"][0], verifier)
    assert tok["status"] == 200 and tok["token_type"] == "Bearer" and tok["refresh_token"], tok
    return client_id, tok["access_token"], tok


# ── tests ──────────────────────────────────────────────────────────────────────────────────────────────
def test_metadata_and_landing(web):
    c, _server, cfg, _ = web
    meta = c.get("/.well-known/oauth-authorization-server")
    assert meta.status_code == 200
    m = meta.json()
    assert m["authorization_endpoint"] == PUBLIC + "/authorize" and m["token_endpoint"] == PUBLIC + "/token"
    assert m["registration_endpoint"] == PUBLIC + "/register" and "S256" in m.get("code_challenge_methods_supported", ["S256"])
    unauth = rpc(c, None, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                          "clientInfo": {"name": "t", "version": "0"}})
    assert unauth.status_code == 401
    www = unauth.headers["www-authenticate"]
    assert "resource_metadata=" in www
    prm_url = www.split('resource_metadata="')[1].split('"')[0]
    assert prm_url.startswith(PUBLIC + "/.well-known/oauth-protected-resource")
    prm = c.get(urlparse(prm_url).path)
    assert prm.status_code == 200 and prm.json()["authorization_servers"][0].rstrip("/") == PUBLIC
    assert prm.json()["resource"].rstrip("/") == cfg.mcp_url
    assert cfg.mcp_url in c.get("/").text
    h = c.get("/healthz").json()
    assert h["ok"] is True and h["mcp"] == cfg.mcp_url and h["clients"] == 0


def test_login_refusals(web):
    c, server, _cfg, _ = web
    client_id = register(c)
    _v, challenge = pkce()
    bad = login(c, client_id, challenge, passphrase="wrong-wrong")
    assert bad["status"] == 401 and "שגוי" in bad["text"] and 'name="passphrase"' in bad["text"]
    # the pending login survives a wrong attempt; an empty name is refused too
    empty = c.post("/login", data={"lid": bad["lid"], "name": "  ", "passphrase": PASS}, follow_redirects=False)
    assert empty.status_code == 401
    # an unknown login id is a 400, never a crash
    assert c.get("/login", params={"lid": "nope"}).status_code == 400
    assert c.post("/login", data={"lid": "nope", "name": "x", "passphrase": PASS}).status_code == 400
    assert server.web_provider.counts()["codes"] == 0


def test_full_oauth_round_trip_then_tools_with_audit_user(web):
    c, server, cfg, runner = web
    _client_id, bearer, _tok = full_login(c)
    assert server.web_provider.counts() == {"clients": 1, "pending": 0, "codes": 0, "access": 1, "refresh": 1}
    init = rpc(c, bearer, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                          "clientInfo": {"name": "t", "version": "0"}})
    assert init.status_code == 200, init.text
    res = init.json()["result"]
    proto = res["protocolVersion"]
    assert res["serverInfo"]["name"] == "roadsafety"
    session = init.headers.get("mcp-session-id")
    note = rpc(c, bearer, "notifications/initialized", rid=None, session=session, proto=proto)
    assert note.status_code in (200, 202), note.text
    tools = rpc(c, bearer, "tools/list", rid=2, session=session, proto=proto)
    assert tools.status_code == 200, tools.text
    assert [t["name"] for t in tools.json()["result"]["tools"]] == list(TOOL_ACTIONS)
    call = rpc(c, bearer, "tools/call", {"name": "roadsafety_trend", "arguments": {"from_year": 2022, "to_year": 2024}},
               rid=3, session=session, proto=proto)
    assert call.status_code == 200, call.text
    content = call.json()["result"]["content"]
    assert content[0]["type"] == "text" and "| year" in content[0]["text"] or "|" in content[0]["text"]
    assert any(b["type"] == "image" for b in content)
    lines = audit_lines(runner)
    assert len(lines) == 1 and lines[0]["tool"] == "roadsafety_trend"
    assert lines[0]["channel"] == "web" and lines[0]["user"] == "אמיר"
    # a garbage bearer is refused; a revoked one too
    assert rpc(c, "nope", "tools/list", rid=4, session=session, proto=proto).status_code == 401


def test_refresh_rotates_and_revokes_the_old_access_token(web):
    c, server, _cfg, _ = web
    client_id, bearer, tok = full_login(c)
    r = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                               "client_id": client_id})
    assert r.status_code == 200, r.text
    fresh = r.json()
    assert fresh["access_token"] != bearer and fresh["refresh_token"] != tok["refresh_token"]
    old_ok = rpc(c, bearer, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": "t", "version": "0"}})
    assert old_ok.status_code == 401                                   # rotated away
    new_ok = rpc(c, fresh["access_token"], "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                           "clientInfo": {"name": "t", "version": "0"}})
    assert new_ok.status_code == 200
    # the old refresh token cannot be replayed
    again = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                                   "client_id": client_id})
    assert again.status_code == 400
    assert server.web_provider.counts()["access"] == 1 and server.web_provider.counts()["refresh"] == 1


def test_expired_code_and_one_use_code(web, monkeypatch):
    c, server, cfg, _ = web
    client_id = register(c)
    verifier, challenge = pkce()
    done = login(c, client_id, challenge)
    code = parse_qs(urlparse(done["location"]).query)["code"][0]
    first = token(c, client_id, code, verifier)
    assert first["status"] == 200
    second = token(c, client_id, code, verifier)                         # one use only
    assert second["status"] == 400
    # an expired code is refused by the SDK's token handler
    monkeypatch.setattr(cfg, "code_ttl", -1)
    verifier2, challenge2 = pkce()
    done2 = login(c, client_id, challenge2, state="s2")
    code2 = parse_qs(urlparse(done2["location"]).query)["code"][0]
    assert token(c, client_id, code2, verifier2)["status"] == 400
    # a wrong PKCE verifier is refused
    verifier3, challenge3 = pkce()
    monkeypatch.setattr(cfg, "code_ttl", 300)
    done3 = login(c, client_id, challenge3, state="s3")
    code3 = parse_qs(urlparse(done3["location"]).query)["code"][0]
    assert token(c, client_id, code3, "not-the-verifier-" + "x" * 40)["status"] == 400


def test_store_persists_clients_and_tokens(web, tmp_path):
    c, server, cfg, _ = web
    client_id, bearer, _ = full_login(c)
    assert cfg.store_path.exists()
    doc = json.loads(cfg.store_path.read_text("utf-8"))
    assert [x["client_id"] for x in doc["clients"]] == [client_id] and len(doc["access"]) == 1
    reloaded = PassphraseProvider(cfg)
    assert reloaded.counts()["clients"] == 1 and reloaded.counts()["access"] == 1
    # a corrupt store is an empty store, never a crash
    cfg.store_path.write_text("{not json", "utf-8")
    assert PassphraseProvider(cfg).counts()["clients"] == 0


def test_foreign_host_is_refused_on_the_mcp_endpoint(ctx, tmp_path):
    """DNS-rebinding protection: the tunnel's host and loopback pass, anything else is refused."""
    cfg = WebConfig(public_url=PUBLIC, passphrase=PASS, store_path=tmp_path / "oauth.json")
    server = build_web_server(Runner(ctx.db_path, channel="web"), cfg)

    def app():   # the SDK's session manager runs once per app instance — one app per client, one provider for all
        return server.streamable_http_app(json_response=True,
                                          transport_security=srv.transport_security(argparse.Namespace(port=8765), cfg))
    init = {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}
    with TestClient(app(), base_url=PUBLIC) as c:
        _cid, bearer, _tok = full_login(c)                   # a valid token, issued through the public host
    # the bearer check runs first (401 without a token); WITH a token the Host check is what refuses a stranger
    with TestClient(app(), base_url="https://evil.example.net") as c:
        assert rpc(c, None, "initialize", init).status_code == 401
        r = rpc(c, bearer, "initialize", init)
        assert r.status_code in (400, 421), r.text
    with TestClient(app(), base_url="http://127.0.0.1:8765") as c:   # the tunnel's --http-host-header form
        assert rpc(c, bearer, "initialize", init).status_code == 200


def test_config_validation():
    with pytest.raises(ValueError):
        WebConfig(public_url="https://x.test/mcp", passphrase=PASS, store_path="x")       # a path is not allowed
    with pytest.raises(ValueError):
        WebConfig(public_url="x.test", passphrase=PASS, store_path="x")                  # no scheme
    with pytest.raises(ValueError):
        WebConfig(public_url=PUBLIC, passphrase="short", store_path="x")                 # weak passphrase
    cfg = WebConfig(public_url=PUBLIC + "/", passphrase=PASS, store_path="x")
    assert cfg.public_url == PUBLIC and cfg.mcp_url == PUBLIC + "/mcp" and cfg.host == "lab.example.test"


def test_cli_args_and_make_server(ctx, tmp_path, monkeypatch):
    with pytest.raises(SystemExit):
        srv.parse_args(["--transport", "http"])                                          # no public url
    with pytest.raises(SystemExit):
        srv.parse_args(["--transport", "http", "--no-auth", "--host", "0.0.0.0"])      # no-auth off loopback
    args = srv.parse_args(["--transport", "http", "--no-auth", "--db", ctx.db_path, "--data-dir", str(tmp_path)])
    server, cfg = srv.make_server(args)
    assert cfg is None and server.instructions.startswith("Road Safety Lab")
    monkeypatch.setenv(ENV_PASSPHRASE, PASS)
    args = srv.parse_args(["--transport", "http", "--public-url", PUBLIC, "--db", ctx.db_path, "--data-dir", str(tmp_path)])
    server, cfg = srv.make_server(args)
    assert cfg is not None and cfg.mcp_url == PUBLIC + "/mcp" and str(cfg.store_path).startswith(str(tmp_path))
    ts = srv.transport_security(args, cfg)
    assert "lab.example.test" in ts.allowed_hosts and f"127.0.0.1:{args.port}" in ts.allowed_hosts
    assert PUBLIC in ts.allowed_origins and ts.enable_dns_rebinding_protection
    monkeypatch.delenv(ENV_PASSPHRASE)
    with pytest.raises(ValueError):
        web_config_from_env(PUBLIC, tmp_path)                                           # passphrase missing
    stdio = srv.parse_args(["--db", ctx.db_path])
    assert stdio.transport == "stdio" and stdio.channel is None


def test_audit_channel_and_local_user(ctx):
    runner = Runner(ctx.db_path, channel="desk")
    from nl2sql_roadsafety.mcp.tools import build_tools
    {t.name: t for t in build_tools(runner)}["roadsafety_trend"].fn(from_year=2022, to_year=2024)
    line = audit_lines(runner)[-1]
    assert line["channel"] == "desk" and line["user"] == "local"


# ── M2: brute-force limits on the login page ───────────────────────────────────────────────────────────
def test_login_attempts_per_login_id_are_capped(web):
    c, server, cfg, _ = web
    client_id = register(c)
    _v, challenge = pkce()
    bad = login(c, client_id, challenge, passphrase="wrong-1")
    lid = bad["lid"]
    for i in range(2, cfg.max_attempts_per_login):
        r = c.post("/login", data={"lid": lid, "name": "x", "passphrase": f"wrong-{i}"}, follow_redirects=False)
        assert r.status_code == 401
    r = c.post("/login", data={"lid": lid, "name": "x", "passphrase": "wrong-last"}, follow_redirects=False)
    assert r.status_code == 400 and "יותר מדי" in r.text              # the login id is gone — start again
    assert server.web_provider.pending(lid) is None
    # even the RIGHT passphrase cannot ride the dead login id
    r = c.post("/login", data={"lid": lid, "name": "x", "passphrase": PASS}, follow_redirects=False)
    assert r.status_code == 400


def test_global_failure_window_answers_429(ctx, tmp_path):
    cfg = WebConfig(public_url=PUBLIC, passphrase=PASS, store_path=tmp_path / "oauth.json", max_failures=2,
                    max_attempts_per_login=10)
    server = build_web_server(Runner(ctx.db_path, channel="web"), cfg)
    app = server.streamable_http_app(json_response=True,
                                     transport_security=srv.transport_security(argparse.Namespace(port=8765), cfg))
    with TestClient(app, base_url=PUBLIC) as c:
        client_id = register(c)
        _v, challenge = pkce()
        bad = login(c, client_id, challenge, passphrase="wrong-1")
        lid = bad["lid"]
        assert c.post("/login", data={"lid": lid, "name": "x", "passphrase": "wrong-2"}).status_code == 401
        r = c.post("/login", data={"lid": lid, "name": "x", "passphrase": PASS})
        assert r.status_code == 429 and r.headers["retry-after"] == str(cfg.failure_window)
