# -*- coding: utf-8 -*-
"""The web channel (M3): the same server over streamable HTTP, behind a self-contained OAuth 2.1
authorization server, so claude.ai in a browser can add it as a custom connector.

claude.ai reaches only remote connectors (public HTTPS, OAuth in the browser, Dynamic Client Registration).
A laptop's server gets a public address from a tunnel (tools/web_tunnel.ps1) and this module gives it the
login: the SDK's authorization-server toolkit (/.well-known metadata, /register, /authorize, /token, /revoke,
bearer middleware) around ONE small provider — a Hebrew login page asking for a display name and the shared
passphrase (`NL2SQL_ROADSAFETY_WEB_PASSPHRASE`). The name becomes the `user` of every audit line.

What this is NOT: a hosting design. Exposure beyond the two plugin owners waits for the course owner's CBS
answer — aggregate answers and PNGs transit Anthropic's API like any chat message (README, GUIDE §8)."""
from __future__ import annotations

import hmac
import html
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ENV_PASSPHRASE = "NL2SQL_ROADSAFETY_WEB_PASSPHRASE"
STORE_REL = Path("accidents") / "mcp_web" / "oauth.json"
MCP_PATH = "/mcp"
LOGIN_PATH = "/login"
CODE_TTL = 300                 # seconds an authorization code stays valid
LOGIN_TTL = 600                # seconds a pending login page stays valid
TOKEN_TTL = 3600               # access token lifetime
REFRESH_TTL = 30 * 24 * 3600   # refresh token lifetime


class TooManyAttempts(Exception):
    """The global failed-login window is exhausted — answer 429, log nothing else."""


@dataclass
class WebConfig:
    public_url: str                      # https://<host> — no trailing slash, no path
    passphrase: str
    store_path: Path
    token_ttl: int = TOKEN_TTL
    code_ttl: int = CODE_TTL
    max_attempts_per_login: int = 5      # wrong passphrases before the login id is invalidated
    max_failures: int = 30               # failed attempts allowed per window, all logins together
    failure_window: int = 600            # seconds

    def __post_init__(self) -> None:
        self.public_url = self.public_url.rstrip("/")
        parsed = urlparse(self.public_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path not in ("", "/"):
            raise ValueError(f"public_url must be scheme://host[:port] with no path, got {self.public_url!r}")
        if not self.passphrase or len(self.passphrase) < 8:
            raise ValueError(f"the web passphrase ({ENV_PASSPHRASE}) must be at least 8 characters")

    @property
    def mcp_url(self) -> str:
        return self.public_url + MCP_PATH

    @property
    def host(self) -> str:
        return urlparse(self.public_url).netloc


def _now() -> float:
    return time.time()


class PassphraseProvider:
    """`OAuthAuthorizationServerProvider` for one lab: clients (DCR) and refresh/access tokens persist in a
    JSON file under the data dir; pending logins and authorization codes live in memory. Passphrase
    comparison is constant-time; every token is 256 bits of urandom."""

    def __init__(self, cfg: WebConfig):
        self.cfg = cfg
        self._lock = threading.RLock()
        self._clients: dict = {}
        self._codes: dict = {}
        self._access: dict = {}
        self._refresh: dict = {}
        self._pending: dict = {}      # lid -> (client_id, AuthorizationParams, expires)
        self._attempts: dict = {}     # lid -> failed passphrase attempts
        self._failures: list = []     # timestamps of failed attempts (global window)
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────────────────────────────────
    def _load(self) -> None:
        from mcp.server.auth.provider import AccessToken, RefreshToken
        from mcp.shared.auth import OAuthClientInformationFull
        p = self.cfg.store_path
        if not p.exists():
            return
        try:
            raw = json.loads(p.read_text("utf-8"))
        except Exception:  # noqa: BLE001 — a corrupt store is an empty store, never a crash
            return
        now = _now()
        with self._lock:
            for c in raw.get("clients", []):
                try:
                    info = OAuthClientInformationFull.model_validate(c)
                    self._clients[info.client_id] = info
                except Exception:  # noqa: BLE001
                    continue
            for t in raw.get("refresh", []):
                try:
                    rt = RefreshToken.model_validate(t)
                    if rt.expires_at is None or rt.expires_at > now:
                        self._refresh[rt.token] = rt
                except Exception:  # noqa: BLE001
                    continue
            for t in raw.get("access", []):
                try:
                    at = AccessToken.model_validate(t)
                    if at.expires_at is None or at.expires_at > now:
                        self._access[at.token] = at
                except Exception:  # noqa: BLE001
                    continue

    def _save(self) -> None:
        p = self.cfg.store_path
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                doc = {
                    "public_url": self.cfg.public_url,
                    "clients": [c.model_dump(mode="json", exclude_none=True) for c in self._clients.values()],
                    "refresh": [t.model_dump(mode="json", exclude_none=True) for t in self._refresh.values()],
                    "access": [t.model_dump(mode="json", exclude_none=True) for t in self._access.values()],
                }
            tmp = p.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, p)
        except Exception:  # noqa: BLE001 — persistence is a convenience; the in-memory state is authoritative
            pass

    # ── clients (Dynamic Client Registration) ────────────────────────────────────────────────────────────
    async def get_client(self, client_id: str):
        with self._lock:
            return self._clients.get(client_id)

    async def register_client(self, client_info) -> None:
        with self._lock:
            self._clients[client_info.client_id] = client_info
        self._save()

    # ── the login page ───────────────────────────────────────────────────────────────────────────────────
    async def authorize(self, client, params) -> str:
        """The /authorize endpoint parks the request and sends the browser to our login page."""
        lid = secrets.token_urlsafe(24)
        with self._lock:
            self._prune()
            self._pending[lid] = (client.client_id, params, _now() + LOGIN_TTL)
        return f"{self.cfg.public_url}{LOGIN_PATH}?lid={lid}"

    def pending(self, lid: str):
        with self._lock:
            self._prune()
            return self._pending.get(lid)

    # ── brute-force limits (M2): a public address must not be a passphrase oracle ──────────────────────
    def _too_many_failures(self) -> bool:
        now = _now()
        with self._lock:
            self._failures = [t for t in self._failures if t > now - self.cfg.failure_window]
            return len(self._failures) >= self.cfg.max_failures

    def _record_failure(self, lid: str) -> None:
        with self._lock:
            self._failures.append(_now())
            self._attempts[lid] = self._attempts.get(lid, 0) + 1
            if self._attempts[lid] >= self.cfg.max_attempts_per_login:
                self._pending.pop(lid, None)            # the person must start the flow again from Claude
                self._attempts.pop(lid, None)

    def complete_login(self, lid: str, name: str, passphrase: str) -> str | None:
        """Verify the passphrase; on success mint an authorization code and return the client's redirect URL.
        None = refused (unknown/expired login, bad passphrase or empty name). Raises TooManyAttempts when the
        global failure window is exhausted (the caller answers 429)."""
        from mcp.server.auth.provider import AuthorizationCode, construct_redirect_uri
        if self._too_many_failures():
            raise TooManyAttempts()
        entry = self.pending(lid)
        name = (name or "").strip()
        if entry is None:
            return None
        if not name or not hmac.compare_digest(passphrase.encode("utf-8"), self.cfg.passphrase.encode("utf-8")):
            self._record_failure(lid)
            return None
        client_id, params, _ = entry
        code = AuthorizationCode(
            code=secrets.token_urlsafe(32), scopes=params.scopes or [], expires_at=_now() + self.cfg.code_ttl,
            client_id=client_id, code_challenge=params.code_challenge, redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource, subject=name[:80])
        with self._lock:
            self._pending.pop(lid, None)
            self._attempts.pop(lid, None)
            self._codes[code.code] = code
        return construct_redirect_uri(str(params.redirect_uri), code=code.code, state=params.state,
                                      iss=self.cfg.public_url)

    # ── codes and tokens ─────────────────────────────────────────────────────────────────────────────────
    async def load_authorization_code(self, client, authorization_code: str):
        with self._lock:
            code = self._codes.get(authorization_code)
        if code is None or code.client_id != client.client_id:
            return None
        return code

    def _issue(self, client_id: str, scopes: list, resource, subject):
        from mcp.server.auth.provider import AccessToken, RefreshToken
        from mcp.shared.auth import OAuthToken
        now = _now()
        access = AccessToken(token=secrets.token_urlsafe(32), client_id=client_id, scopes=list(scopes),
                             expires_at=int(now + self.cfg.token_ttl), resource=resource or self.cfg.mcp_url,
                             subject=subject, claims={"iss": self.cfg.public_url})
        refresh = RefreshToken(token=secrets.token_urlsafe(32), client_id=client_id, scopes=list(scopes),
                               expires_at=int(now + REFRESH_TTL), resource=access.resource, subject=subject)
        with self._lock:
            self._access[access.token] = access
            self._refresh[refresh.token] = refresh
        self._save()
        return OAuthToken(access_token=access.token, token_type="Bearer", expires_in=self.cfg.token_ttl,
                          scope=" ".join(scopes) or None, refresh_token=refresh.token)

    async def exchange_authorization_code(self, client, authorization_code):
        with self._lock:
            self._codes.pop(authorization_code.code, None)       # one use only
        return self._issue(client.client_id, authorization_code.scopes, authorization_code.resource,
                           authorization_code.subject)

    async def load_refresh_token(self, client, refresh_token: str):
        with self._lock:
            rt = self._refresh.get(refresh_token)
        if rt is None or rt.client_id != client.client_id:
            return None
        return rt

    async def exchange_refresh_token(self, client, refresh_token, scopes: list):
        """Rotate: the old refresh token and every access token of its subject+client die with it."""
        with self._lock:
            self._refresh.pop(refresh_token.token, None)
            for tok, at in list(self._access.items()):
                if at.client_id == refresh_token.client_id and at.subject == refresh_token.subject:
                    self._access.pop(tok, None)
        return self._issue(client.client_id, scopes or refresh_token.scopes, refresh_token.resource,
                           refresh_token.subject)

    async def load_access_token(self, token: str):
        with self._lock:
            at = self._access.get(token)
            if at is not None and at.expires_at is not None and at.expires_at <= _now():
                self._access.pop(token, None)
                at = None
        return at

    async def revoke_token(self, token) -> None:
        with self._lock:
            self._access.pop(getattr(token, "token", ""), None)
            self._refresh.pop(getattr(token, "token", ""), None)
        self._save()

    async def exchange_identity_assertion(self, client, params):
        from mcp.server.auth.provider import TokenError
        raise TokenError(error="unsupported_grant_type",
                         error_description="The JWT bearer grant is not supported by this server")

    def _prune(self) -> None:
        now = _now()
        for lid, (_, _, exp) in list(self._pending.items()):
            if exp <= now:
                self._pending.pop(lid, None)
        for c, code in list(self._codes.items()):
            if code.expires_at <= now:
                self._codes.pop(c, None)

    # ── introspection for tests / status ─────────────────────────────────────────────────────────────────
    def counts(self) -> dict:
        with self._lock:
            return {"clients": len(self._clients), "pending": len(self._pending), "codes": len(self._codes),
                    "access": len(self._access), "refresh": len(self._refresh)}


# ── the pages ────────────────────────────────────────────────────────────────────────────────────────────
_PAGE = """<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>מעבדת הבטיחות בדרכים · כניסה</title>
<style>body{{font-family:Assistant,Segoe UI,Arial,sans-serif;background:#f6f7f9;color:#1b1f24;margin:0;
display:flex;min-height:100vh;align-items:center;justify-content:center}}main{{background:#fff;border-radius:14px;
box-shadow:0 2px 14px rgba(0,0,0,.08);padding:28px 32px;max-width:420px;width:92%}}h1{{font-size:1.25rem;margin:0 0 4px}}
p{{margin:6px 0 14px;color:#4b5563;font-size:.95rem}}label{{display:block;font-size:.9rem;margin:10px 0 4px}}
input{{width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid #cfd4dc;border-radius:8px;font-size:1rem}}
button{{margin-top:16px;width:100%;padding:10px;border:0;border-radius:8px;background:#2563eb;color:#fff;font-size:1rem;cursor:pointer}}
.err{{background:#fde8e8;color:#9b1c1c;padding:8px 10px;border-radius:8px;font-size:.9rem}}
small{{display:block;margin-top:14px;color:#6b7280;font-size:.8rem}}</style></head><body><main>
<h1>🚦 מעבדת הבטיחות בדרכים</h1><p>חיבור צ׳אט למסד תאונות הדרכים (למ״ס). הזינו שם לתצוגה ואת ביטוי הכניסה שקיבלתם.</p>
{error}<form method="post" action="{action}"><input type="hidden" name="lid" value="{lid}">
<label for="name">שם (יופיע ביומן הביקורת)</label><input id="name" name="name" autocomplete="name" required maxlength="80" value="{name}">
<label for="passphrase">ביטוי כניסה</label><input id="passphrase" name="passphrase" type="password" autocomplete="current-password" required>
<button type="submit">כניסה</button></form>
<small>מקור הנתונים: הלשכה המרכזית לסטטיסטיקה (למ״ס); עיבוד: מעבדת הבטיחות בדרכים · Road Safety Lab MCP {version}</small>
</main></body></html>"""

_LANDING = """<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><title>Road Safety Lab MCP</title>
<style>body{{font-family:Assistant,Segoe UI,Arial,sans-serif;max-width:640px;margin:48px auto;padding:0 16px;color:#1b1f24}}
code{{background:#eef1f5;padding:2px 6px;border-radius:6px;direction:ltr;display:inline-block}}</style></head><body>
<h1>🚦 מעבדת הבטיחות בדרכים · שרת MCP</h1>
<p>זהו שרת כלים ל-Claude, לא אתר. כדי להשתמש בו: claude.ai → Settings → Connectors → Add custom connector →
הדביקו את הכתובת <code>{mcp_url}</code>. תתבקשו להזין שם וביטוי כניסה.</p>
<p>גרסה {version} · הכלים עונים על מסד תאונות הדרכים של הלמ״ס; כל קריאה נרשמת ביומן הביקורת.</p></body></html>"""


def build_web_server(runner, cfg: WebConfig, *, images: bool = True, read_only: bool = False):
    """The MCPServer of server.build_server, with the OAuth authorization server, the login page, a landing
    page and a health endpoint. The SDK mounts /.well-known/*, /register, /authorize, /token, /revoke and the
    bearer middleware itself from `auth` + `token_verifier` + `auth_server_provider`."""
    from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

    from ..envelope import version
    from .server import build_server

    provider = PassphraseProvider(cfg)
    auth = AuthSettings(
        issuer_url=cfg.public_url,
        resource_server_url=cfg.mcp_url,
        client_registration_options=ClientRegistrationOptions(enabled=True),
        revocation_options=RevocationOptions(enabled=True),
        # every token this server issues is for this server — the verifier IS the issuer, so the RFC 8707
        # check is redundant here, and a client that omits `resource` must still work
        validate_token_resource=False,
    )
    # the SDK builds the bearer verifier from the provider itself (ProviderTokenVerifier) — passing both is refused
    server = build_server(runner, images=images, read_only=read_only, auth=auth, auth_server_provider=provider)
    server.web_provider = provider          # type: ignore[attr-defined] — tests and status read it
    ver = version()

    def page(lid: str, *, error: str = "", name: str = "", status: int = 200) -> Response:
        err = f'<div class="err">{html.escape(error)}</div>' if error else ""
        return HTMLResponse(_PAGE.format(error=err, action=LOGIN_PATH, lid=html.escape(lid),
                                         name=html.escape(name), version=html.escape(ver)), status_code=status,
                            headers={"Cache-Control": "no-store"})

    @server.custom_route(LOGIN_PATH, methods=["GET"])
    async def login_form(request: Request) -> Response:
        lid = request.query_params.get("lid", "")
        if not lid or provider.pending(lid) is None:
            return HTMLResponse("<p dir='rtl'>בקשת הכניסה פגה או אינה מוכרת — חזרו ל-Claude והתחברו שוב.</p>",
                                status_code=400)
        return page(lid)

    @server.custom_route(LOGIN_PATH, methods=["POST"])
    async def login_submit(request: Request) -> Response:
        form = await request.form()
        lid = str(form.get("lid", ""))
        name = str(form.get("name", ""))
        passphrase = str(form.get("passphrase", ""))
        if not lid or provider.pending(lid) is None:
            return HTMLResponse("<p dir='rtl'>בקשת הכניסה פגה — חזרו ל-Claude והתחברו שוב.</p>", status_code=400)
        try:
            target = provider.complete_login(lid, name, passphrase)
        except TooManyAttempts:
            return HTMLResponse("<p dir='rtl'>יותר מדי ניסיונות כניסה שגויים. נסו שוב בעוד כמה דקות.</p>",
                                status_code=429, headers={"Retry-After": str(cfg.failure_window)})
        if target is None:
            if provider.pending(lid) is None:          # the login id was just invalidated by repeated failures
                return HTMLResponse("<p dir='rtl'>יותר מדי ניסיונות — חזרו ל-Claude והתחברו שוב.</p>", status_code=400)
            return page(lid, error="ביטוי הכניסה שגוי או שהשם ריק.", name=name, status=401)
        return RedirectResponse(target, status_code=302, headers={"Cache-Control": "no-store"})

    @server.custom_route("/", methods=["GET"])
    async def landing(_request: Request) -> Response:
        return HTMLResponse(_LANDING.format(mcp_url=html.escape(cfg.mcp_url), version=html.escape(ver)))

    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(_request: Request) -> Response:
        return JSONResponse({"ok": True, "version": ver, "mcp": cfg.mcp_url, "db_missing": runner.db_missing(),
                             **provider.counts()})

    return server


def web_config_from_env(public_url: str, data_dir: Path, *, passphrase: str | None = None) -> WebConfig:
    pw = passphrase if passphrase is not None else os.environ.get(ENV_PASSPHRASE, "")
    return WebConfig(public_url=public_url, passphrase=pw, store_path=Path(data_dir) / STORE_REL)
