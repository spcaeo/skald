"""The dashboard's "Refresh now" button: a tiny local helper.

nginx keeps the password check and forwards only POST <page>/refresh here
(127.0.0.1 only). The helper runs `skald live` - the same command the 2-minute
cron runs, which redraws the dashboard and never touches history or mail -
then sends the browser back to the page it came from.

Guards:
  * only POST, only paths shaped like /traffic/<site>/[<view>/]refresh
  * same-origin only (Sec-Fetch-Site / Origin), so another site cannot make a
    logged-in browser press the button
  * one run at a time, and at most one run per MIN_GAP seconds; a press inside
    the gap just goes back to the page
  * stdlib only, no request body is read

It also serves the internal-addresses list (ours_store.py) for the page:

  GET  <page>/ours            the list (config entries read-only, page ones editable)
  POST <page>/ours/add        ip, label            (form or JSON)
  POST <page>/ours/remove     ip
  POST <page>/ours/add-mine   label; the address is the caller's, from the
                              X-Real-IP header nginx sets - believed only when
                              the connection itself comes from 127.0.0.1

Same guards, plus: bodies of at most 4 KB, JSON answers, and a live run after
every change so the page shows it at once.

Release 3 (named users, funnels, the read-only API):

  GET  <page>/me                  {"user", "role"}: who nginx says logged in
                                  (X-Skald-User, believed from 127.0.0.1
                                  only) and their role (access.py); for an
                                  owner or admin also "update", a newer
                                  release (updates.py)
  GET  <page>/funnels             the page's funnels.json
  POST <page>/funnels/save        JSON {"name","source","steps"} (funnels.py)
  POST <page>/funnels/delete      {"name"}
  GET  <page>/api/v1/[<name>]     a data file, or the list of them
  GET  <page>/api/realtime        Overview > Real time (realtime_api.py)
  GET  /traffic-api/v1/<site>/[<view>/]<name>
                                  the same with "Authorization: Bearer <token>"
                                  and no password (tokens.py)

Changing internal addresses or funnels is for admins; a viewer gets 403.
Every change is logged with the user who made it.

And the AI crawler settings, GET and POST <page>/bot-policy
(bot_policy_api.py): the helper only stores the policy file; root applies it.

With `access: {mode: sessions}` (accounts; basic is the default and changes
nothing): /traffic-auth/* signs people in (auth_api.py, with nginx's
auth_request check), <page>/team, account, tokens and audit are the
Settings routes (team_api.py), <page>/settings and settings/* the
settings pages (settings_api.py), <page>/integrations and integrations/*
Settings > Integrations (integrations_api.py), <page>/people and people/* the person
lookup and the left-out lists (people/api.py), <page>/logo and logo/* the site's logo
(logo_api.py; the image itself in basic mode too), /me adds name, org, csrf, mode, install_admin
and totp_on, every POST but refresh also needs X-Skald-CSRF, an owner counts
as an admin, and /traffic-api/ checks tokens in accounts.sqlite. Every other
/traffic/ route reads the person from the session cookie itself, never from
X-Skald-User / X-Skald-Role (helper_sessions.py): no session is 401, another
organisation's site 403. The bot policy, funnels and internal addresses are
install-wide, so changing them needs an install admin. /traffic/sites.json,
<site>/data/sites.json and the switcher page are filtered to the caller's
organisations.

With `saas: {enabled: true}` as well (docs/SAAS.md; off by default):
/traffic-auth/signup and signup-finish (saas/signup_api.py), <page>/billing
and billing/checkout|portal (saas/billing_api.py), and Stripe's events at
POST /traffic-hooks/_billing/stripe. Off, every one of them answers 404.

Listening: 127.0.0.1:<port> (TCP), or, with `refresh: {socket: PATH}` in the
config, only a Unix socket at PATH (mode 0660, group `refresh.socket_group`,
default www-data) that nginx proxies to. A connection on the socket counts
as the proxy's (like 127.0.0.1): only nginx's group can open it.

Run:  python3 -m skald.refresh_server --config /etc/skald/config.yml
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import access, auth_api, bot_policy_api, helper_sessions, settings_api, team_api
from . import ingest, integrations_api, logo_api, realtime_api, sites_api, updates
from .saas import billing_api, signup_api
from .mcp import http as mcp_http
from .people import api as people_api

MIN_GAP = 15          # seconds between two runs
RUN_TIMEOUT = 90      # seconds a run may take before it is abandoned
PATH = re.compile(r"^/traffic/[a-z0-9.-]+/(?:[a-z0-9-]+/)?refresh$")
OURS_PATH = re.compile(r"^/traffic/[a-z0-9.-]+/(?:[a-z0-9-]+/)?ours(?:/(add|remove|add-mine))?$")
MAX_BODY = 4096
PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
ME_PATH = re.compile(PAGE + r"me$")
FUNNELS_PATH = re.compile(PAGE + r"funnels(?:/(?P<act>save|delete))?$")
API_PATH = re.compile(PAGE + r"api/v1/(?P<name>[a-z_]{1,40})?$")
COMPARE_PATH = re.compile(PAGE + r"api/compare$")
PAGE_STORY_PATH = re.compile(PAGE + r"api/page$")
TOKEN_PATH = re.compile(r"^/traffic-api/v1/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
                        r"(?P<name>[a-z_]{1,40})$")


def route(pattern: re.Pattern, path: str):
    path = path.split("?", 1)[0]
    if ".." in path:
        return None
    return pattern.match(path)


def data_file(out: Path | None, site: str, view: str | None, name: str) -> Path | None:
    """The data file a page or the API asks for, inside the dashboard only."""
    if out is None:
        return None
    folder = Path(out) / site / (view or "") / "data"
    path = folder / f"{name}.json"
    try:
        path.resolve().relative_to(Path(out).resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def ours_action(path: str) -> str | None:
    """"list", "add", "remove", "add-mine", or None when not an ours path."""
    path = path.split("?", 1)[0]
    m = OURS_PATH.match(path)
    if not m or ".." in path:
        return None
    return m.group(1) or "list"


def caller_address(headers, peer: str, config: dict | None = None) -> str | None:
    """The browser's address for add-mine: nginx's X-Real-IP, trusted only
    when the connection is nginx's own (127.0.0.1 or the Unix socket) and
    `access.trust_proxy_ip` is not false."""
    return access.proxy_ip(headers, peer, config)


def parse_body(raw: bytes, content_type: str) -> dict:
    """A small form-encoded or JSON body as {name: str}."""
    from urllib.parse import parse_qs
    text = raw.decode("utf-8", "replace")
    if "json" in (content_type or ""):
        try:
            data = json.loads(text or "{}")
        except ValueError:
            return {}
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    return {k: v[0] for k, v in parse_qs(text).items() if v}


def back_to(path: str) -> str | None:
    """The page a refresh came from, or None when the path is not one of ours."""
    path = path.split("?", 1)[0]
    if not PATH.match(path) or ".." in path:
        return None
    return path[: -len("refresh")]


def allowed_origins(given: list[str] | None) -> set[str]:
    """The origins named with --origin. Empty when none: no built-in default."""
    return {o.strip().rstrip("/") for o in (given or []) if o and o.strip()}


def same_origin(headers, allowed: set[str]) -> bool:
    """True when the browser says the request came from our own page."""
    site = headers.get("Sec-Fetch-Site")
    if site is not None:
        return site == "same-origin"
    origin = headers.get("Origin")
    return origin is not None and origin in allowed


class Runner:
    """Runs the live command at most once per MIN_GAP seconds, one at a time."""

    def __init__(self, command: list[str], cwd: Path, gap: float = MIN_GAP,
                 clock=time.monotonic, run=subprocess.run):
        self.command, self.cwd, self.gap = command, cwd, gap
        self.clock, self._run = clock, run
        self.lock = threading.Lock()
        self.last = None

    def refresh(self, force: bool = False) -> str:
        """'ran', 'failed', 'recent' (inside the gap) or 'busy'. `force` runs
        even inside the gap (after a change to the address list), waiting
        for a run in progress."""
        if not self.lock.acquire(blocking=force, timeout=RUN_TIMEOUT if force else -1):
            return "busy"
        try:
            now = self.clock()
            if not force and self.last is not None and now - self.last < self.gap:
                return "recent"
            self.last = now
            try:
                done = self._run(self.command, cwd=self.cwd, timeout=RUN_TIMEOUT,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            except subprocess.TimeoutExpired:
                return "failed"
            # 1 = today's figures withheld: the page says so, the run still worked.
            return "ran" if done.returncode in (0, 1) else "failed"
        finally:
            self.lock.release()


def make_handler(runner: Runner, allowed: set[str], config: dict | None = None,
                 out: Path | None = None, live_dir: Path | None = None,
                 history_path: Path | None = None, config_path: Path | None = None):
    from . import funnels, ours_store, tokens
    sessions_mode = access.mode(config) == "sessions"

    class Handler(BaseHTTPRequestHandler):
        server_version = "skald-refresh"

        def _json(self, code: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        # Sessions mode: the caller from the cookie (helper_sessions.gate), set
        # at the start of each request; None in basic mode.
        who = None

        def _user(self) -> tuple[str, str]:
            if sessions_mode:
                return (self.who or {}).get("email") or "", (self.who or {}).get("role") or ""
            peer = self.client_address[0]
            user = access.user_from(self.headers, peer, config)
            return user, access.role_of(config, live_dir, user, self.headers, peer)

        def _admin(self, install: bool = False) -> str | None:
            """The admin's name, or None after answering 403. In sessions mode
            `install` asks for an install admin (a change for every site), and
            the X-Skald-CSRF header must match the session."""
            if sessions_mode:
                if self.who is None or not helper_sessions.need(self, self.who, install):
                    return None
                return self.who["email"]
            user, role = self._user()
            if role not in ("admin", "owner"):
                self._json(403, {"ok": False, "error": "admins only", "role": role})
                return None
            return user or "admin"

        def _gated(self) -> bool:
            """Basic mode: True. Sessions mode: the cookie's caller is set, or
            False after answering 401/403 (helper_sessions.gate)."""
            self.who = None
            if not sessions_mode:
                return True
            self.who = helper_sessions.gate(self, config, live_dir)
            return self.who is not None

        def _body(self) -> dict | None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY:
                self._json(400, {"ok": False, "error": "body too large"})
                return None
            raw = self.rfile.read(length) if length else b""
            if "json" in self.headers.get("Content-Type", ""):
                try:
                    got = json.loads(raw.decode("utf-8", "replace") or "{}")
                except ValueError:
                    got = None
                if not isinstance(got, dict):
                    self._json(400, {"ok": False, "error": "a JSON object, please"})
                    return None
                return got
            return parse_body(raw, self.headers.get("Content-Type", ""))

        def _file(self, path: Path | None) -> None:
            if path is None:
                return self._json(404, {"ok": False, "error": "no such file"})
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _query(self) -> dict:
            from urllib.parse import parse_qsl
            raw = self.path.split("?", 1)[1] if "?" in self.path else ""
            return {k: v for k, v in parse_qsl(raw)[:20]}

        def _history_answer(self, m, what: str) -> None:
            """compare / page, from history opened read-only."""
            from datetime import datetime, timezone
            from . import compare, lifecycle
            from .store import History
            from .window import zone
            if history_path is None or not Path(history_path).exists():
                return self._json(503, {"ok": False, "error": "no history here"})
            q = self._query()
            tz = zone(config or {})
            history = History.reader(history_path)
            try:
                if what == "compare":
                    a, b = q.pop("a", ""), q.pop("b", "")
                    q.pop("view", None)
                    got = compare.compare(history, m.group("site"), m.group("view"), a, b, q,
                                          config or {}, tz)
                else:
                    got = lifecycle.story(history, m.group("site"), q.get("path", ""),
                                          config or {}, tz,
                                          datetime.now(timezone.utc).astimezone(tz).date())
            except compare.Invalid as why:
                return self._json(400, {"ok": False, "error": str(why)})
            finally:
                history.db.close()
            return self._json(200 if got.get("ok") else 404, got)

        def _api_list(self, site: str, view: str | None) -> None:
            folder = Path(out or ".") / site / (view or "") / "data"
            names = sorted(p.stem for p in folder.glob("*.json")) if out else []
            if not names:
                return self._json(404, {"ok": False, "error": "no such page"})
            self._json(200, {"ok": True, "version": "v1", "files": names,
                             "docs": "docs/API.md"})

        def _funnels(self, m) -> None:
            site, view, act = m.group("site"), m.group("view"), m.group("act")
            if act is None:
                return self._file(data_file(out, site, view, "funnels"))
            if not same_origin(self.headers, allowed):
                return self._json(403, {"ok": False, "error": "same-origin requests only"})
            who = self._admin(install=True)        # funnels.json is shared by every site
            if who is None:
                return None
            form = self._body()
            if form is None:
                return None
            try:
                if act == "save":
                    funnels.save(live_dir, form, who)
                else:
                    funnels.delete(live_dir, str(form.get("name") or ""), who)
            except (funnels.Invalid, OSError) as why:
                return self._json(400, {"ok": False, "error": str(why)})
            runner.refresh(force=True)
            path = data_file(out, site, view, "funnels")
            body = json.loads(path.read_text()) if path else {}
            return self._json(200, {"ok": True, **body})

        def _ours(self, action: str) -> None:
            if not same_origin(self.headers, allowed):
                return self._json(403, {"ok": False, "error": "same-origin requests only"})
            if action == "list":
                if sessions_mode:
                    if self.who["role"] not in ("owner", "admin"):
                        return self._json(403, {"ok": False, "error": "admins only",
                                                "role": self.who["role"]})
                    entries = helper_sessions.ours_listing(config, self.who)
                else:
                    entries = ours_store.listing(config)
                return self._json(200, {"ok": True, "limit": ours_store.LIMIT,
                                        "entries": entries,
                                        "can_add": ours_store.path_of(config) is not None})
            who = self._admin(install=True)        # the list applies to every site
            if who is None:
                return None
            site = helper_sessions.site_of(self.path) or ""
            listed = (lambda: helper_sessions.ours_listing(config, self.who)) if sessions_mode \
                else (lambda: ours_store.listing(config))
            form = self._body()
            if form is None:
                return None
            form = {k: str(v) for k, v in form.items()}
            try:
                if action == "add":
                    ours_store.add(config, form.get("ip"), form.get("label"), "page", by=who,
                                   site=site)
                elif action == "add-mine":
                    mine = caller_address(self.headers, self.client_address[0], config)
                    if mine is None:
                        raise ours_store.Invalid("your address is not known here")
                    ours_store.add(config, mine, form.get("label") or "My address",
                                   "page (my address)", by=who, site=site)
                else:
                    ours_store.remove(config, form.get("ip"), by=who)
            except ours_store.Full as why:
                return self._json(409, {"ok": False, "error": str(why), "entries": listed()})
            except (ours_store.Invalid, OSError) as why:
                return self._json(400, {"ok": False, "error": str(why), "entries": listed()})
            runner.refresh(force=True)
            return self._json(200, {"ok": True, "entries": listed()})

        def _send(self, code: int, location: str | None = None) -> None:
            self.send_response(code)
            if location:
                self.send_header("Location", location)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):
            self.who = None
            if ingest.is_ingest(self.path):             # shipped log lines (bearer token)
                return ingest.handle(self, config, live_dir, config_path)
            if sites_api.is_sites(self.path):           # Settings > Sites: add, remove
                return sites_api.handle(self, True, config, live_dir, allowed, same_origin,
                                        config_path, out)
            if mcp_http.is_mcp(self.path):
                return mcp_http.handle_http(self, config, live_dir, out, None,
                                            history_path=history_path, allowed_origins=allowed)
            if billing_api.is_hook(self.path):          # Stripe's signed events (saas)
                return billing_api.hook(self, config, live_dir)
            if signup_api.is_signup(self.path):         # before auth_api: /traffic-auth/signup
                return signup_api.handle(self, True, config, live_dir, allowed, same_origin,
                                         config_path, out)
            if auth_api.is_auth(self.path):
                return auth_api.handle(self, True, config, live_dir, allowed, same_origin)
            if billing_api.is_billing(self.path):       # Settings > Billing (saas)
                return billing_api.handle(self, True, config, live_dir, allowed, same_origin,
                                          history_path)
            if integrations_api.is_integrations(self.path):   # Settings > Integrations
                return integrations_api.handle(self, True, config, live_dir, allowed,
                                               same_origin, config_path)
            if settings_api.is_settings(self.path):     # before team_api: settings/audit
                return settings_api.handle(self, True, config, live_dir, allowed, same_origin,
                                           history_path, config_path)
            if team_api.is_team(self.path):
                return team_api.handle(self, True, config, live_dir, allowed, same_origin)
            if not self._gated():
                return None
            if logo_api.is_logo(self.path):             # the site's logo (2.6.0)
                return logo_api.handle(self, True, config, live_dir, allowed, same_origin,
                                       config_path, self.who)
            if bot_policy_api.is_policy(self.path):
                return bot_policy_api.handle(self, True, config, allowed, same_origin)
            m = route(FUNNELS_PATH, self.path)
            if m is not None and m.group("act"):
                return self._funnels(m)
            action = ours_action(self.path)
            if action is not None:
                if action == "list":
                    return self._send(405)
                return self._ours(action)
            page = back_to(self.path)
            if page is None:
                return self._send(404)
            if not same_origin(self.headers, allowed):
                return self._send(403)
            result = runner.refresh()
            if result == "failed":
                sys.stderr.write("refresh: live run failed\n")
            self._send(303, page)

        def do_GET(self):
            self.who = None
            if ingest.is_ingest(self.path):
                return ingest.handle(self, config, live_dir, config_path)
            if sites_api.is_sites(self.path):
                return sites_api.handle(self, False, config, live_dir, allowed, same_origin,
                                        config_path, out)
            if mcp_http.is_mcp(self.path):
                return mcp_http.handle_http(self, config, live_dir, out, None,
                                            history_path=history_path, allowed_origins=allowed)
            if signup_api.is_signup(self.path):
                return signup_api.handle(self, False, config, live_dir, allowed, same_origin,
                                         config_path, out)
            if auth_api.is_auth(self.path):
                return auth_api.handle(self, False, config, live_dir, allowed, same_origin)
            if billing_api.is_billing(self.path):
                return billing_api.handle(self, False, config, live_dir, allowed, same_origin,
                                          history_path)
            if integrations_api.is_integrations(self.path):
                return integrations_api.handle(self, False, config, live_dir, allowed,
                                               same_origin, config_path)
            if settings_api.is_settings(self.path):
                return settings_api.handle(self, False, config, live_dir, allowed, same_origin,
                                           history_path, config_path)
            if team_api.is_team(self.path):
                return team_api.handle(self, False, config, live_dir, allowed, same_origin)
            m = route(TOKEN_PATH, self.path)
            if m is not None:
                return self._token_get(m)
            if not self._gated():
                return None
            if sessions_mode and helper_sessions.is_listing(self.path):
                return helper_sessions.listing(self, out, self.who, config, live_dir, config_path)
            if logo_api.is_logo(self.path):
                return logo_api.handle(self, False, config, live_dir, allowed, same_origin,
                                       config_path, self.who)
            if bot_policy_api.is_policy(self.path):
                return bot_policy_api.handle(self, False, config, allowed, same_origin)
            if realtime_api.is_realtime(self.path):     # Overview > Real time, every 15 s
                return realtime_api.handle(self, config, live_dir, config_path)
            if people_api.is_people(self.path):         # the person lookup (2.4.0)
                return people_api.handle(self, config, live_dir, history_path, config_path,
                                         sessions_mode)
            if ours_action(self.path) == "list":
                return self._ours("list")
            m = route(ME_PATH, self.path)
            if m is not None:
                user, role = self._user()
                body = team_api.me(self, config, live_dir, m.group("site"), user, role) \
                    if sessions_mode else {"ok": True, "user": user or None, "role": role}
                # A newer release, for an owner or admin (updates.py, from updates.json).
                return self._json(200, updates.for_me(body, config, live_dir))
            m = route(FUNNELS_PATH, self.path)
            if m is not None and not m.group("act"):
                return self._funnels(m)
            m = route(COMPARE_PATH, self.path)
            if m is not None:
                return self._history_answer(m, "compare")
            m = route(PAGE_STORY_PATH, self.path)
            if m is not None:
                return self._history_answer(m, "page")
            m = route(API_PATH, self.path)
            if m is not None:
                if not m.group("name"):
                    return self._api_list(m.group("site"), m.group("view"))
                return self._file(data_file(out, m.group("site"), m.group("view"),
                                            m.group("name")))
            self._send(405)

        def _token_get(self, m) -> None:
            """/traffic-api/: a bearer token, no session (tokens.py, apitokens.py)."""
            if sessions_mode:
                ok, why = self._token_check(m)
            else:
                ok, why = tokens.check(tokens.path_for(config, live_dir),
                                       self.headers.get("Authorization"), m.group("site"),
                                       m.group("name"))
            if not ok:
                return self._json(401, {"ok": False, "error": why})
            if m.group("name") == "people":             # read_private (tokens.PRIVATE)
                return people_api.token(self, m, config, live_dir, history_path, config_path)
            return self._file(data_file(out, m.group("site"), m.group("view"),
                                        m.group("name")))

        def _token_check(self, m) -> tuple[bool, str]:
            """Sessions mode: the organisation's tokens in accounts.sqlite, scope read
            (and read_private for the files that hold addresses)."""
            db = auth_api.open_db(config, live_dir)
            if db is None:
                return False, "accounts are not set up here"
            try:
                ok, why, _ = auth_api.accounts.apitokens.check(
                    db, self.headers.get("Authorization"), m.group("site"), "read",
                    m.group("name"))
            finally:
                db.close()
            return ok, why

        def log_message(self, fmt, *args):  # no visitor details in the journal
            pass

    return Handler


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", required=True)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--origin", action="append", default=[],
                   help="the dashboard's own origin, e.g. https://<your site> "
                        "(repeatable). Only used for browsers that send no "
                        "Sec-Fetch-Site header; without it those are refused.")
    a = p.parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    runner = Runner([sys.executable, str(root / "bin/skald"), "--config", a.config, "live"], root)
    # No default: with no --origin, only browsers that say Sec-Fetch-Site:
    # same-origin get in. We never trust a domain nobody named.
    allowed = allowed_origins(a.origin)
    from .cli import _path
    from .config import load_config
    config = load_config(Path(a.config))
    out = _path(config, Path(a.config), "dashboard", "out", None)
    db = _path(config, Path(a.config), "history", "db", "history.sqlite")
    # The history file, so the install's mail settings and secrets.json are
    # found beside it (settings_store.py) for the account and test mails.
    config.setdefault("_resolved", {"history_db": str(db), "live_dir": str(db.parent)})
    server = make_server(config, make_handler(runner, allowed, config, out, db.parent, db,
                                              Path(a.config)), a.port)
    import signal                         # systemd's stop: close (and remove the socket)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


PROXY_PEER = (access.PROXY, 0)


class HelperServer(ThreadingHTTPServer):
    """The helper on 127.0.0.1. nginx asks it about every file a page loads
    (auth_request in sessions mode), often 20 at once: Python's default
    listen queue of 5 would drop some of them on Linux."""
    daemon_threads = True
    request_queue_size = 128


class UnixHelperServer(socketserver.ThreadingUnixStreamServer):
    """The helper on a Unix socket: only nginx's group can open it, so a peer
    counts as the proxy (client_address 127.0.0.1, as nginx's TCP connection
    would be). The socket file is removed on close."""
    daemon_threads = True
    request_queue_size = 128

    def get_request(self):
        sock, _ = super().get_request()
        return sock, PROXY_PEER

    def server_close(self):
        super().server_close()
        try:
            os.unlink(self.server_address)
        except OSError:
            pass


def socket_settings(config: dict | None) -> tuple[str | None, str]:
    """(`refresh.socket` or None, `refresh.socket_group`, default www-data)."""
    raw = (config or {}).get("refresh") or {}
    path = str(raw.get("socket") or "").strip() or None
    return path, str(raw.get("socket_group") or "www-data").strip()


def make_server(config: dict | None, handler, port: int = 8765):
    """127.0.0.1:<port>, or only the Unix socket `refresh.socket` (mode 0660,
    group `refresh.socket_group`). Raises SystemExit when the socket cannot
    be given its group: nginx could not open it."""
    path, group = socket_settings(config)
    if path is None:
        return HelperServer(("127.0.0.1", port), handler)
    import shutil
    try:
        os.unlink(path)                   # a socket left by a run that was killed
    except FileNotFoundError:
        pass
    old = os.umask(0o117)                 # born 0660, never wider for a moment
    try:
        server = UnixHelperServer(path, handler)
    finally:
        os.umask(old)
    try:
        os.chmod(path, 0o660)
        shutil.chown(path, group=group)
    except (LookupError, OSError) as why:
        server.server_close()
        raise SystemExit(f"refresh.socket: cannot give {path} the group {group!r} ({why}); "
                         "the service needs that group (SupplementaryGroups=, DEPLOY.md)")
    return server


if __name__ == "__main__":
    raise SystemExit(main())
